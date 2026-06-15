"""Pure Python scoring — zero API calls."""
from __future__ import annotations
import re
import sys
import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
from db_helper import get_conn, DB_PATH
_SYLLABUS_PATH = Path(__file__).parent.parent / "data" / "syllabus.json"
_syllabus_cache: dict | None = None


def _load_syllabus() -> dict:
    global _syllabus_cache
    if _syllabus_cache is None:
        try:
            _syllabus_cache = json.loads(_SYLLABUS_PATH.read_text())
        except Exception:
            _syllabus_cache = {}
    return _syllabus_cache


def _canonical_topic_id(subject_id: str, subtopic_id: str) -> str | None:
    """Look up canonical topic_id from syllabus.json for a subject+subtopic pair."""
    _ALIAS = {"history": "history_amac"}
    sid = _ALIAS.get(subject_id, subject_id)
    for subj in _load_syllabus().get("subjects", []):
        if subj["id"] != sid:
            continue
        for topic in subj.get("topics", []):
            for st in topic.get("subtopics", []):
                if st["id"] == subtopic_id:
                    return topic["id"]
    return None

sys.path.insert(0, str(Path(__file__).parent))

_STATEMENT_RE = re.compile(
    r'consider the following|which\s+of\s+the\s+following\s+statement|'
    r'statement\s+[1-4ivIV]+\s+is|statements?\s+are\s+(correct|true|false)', re.I
)
_MATCH_RE = re.compile(
    r'match.{0,25}(list|column|pair)|list\s+[iI]+\s.*list\s+[iI]+|'
    r'column\s+[iI]+', re.I
)
_MAP_RE = re.compile(
    r'\b(map|geographical|location|situated\s+in|located\s+in)\b.{0,80}'
    r'\b(figure|diagram|given|above|below)\b', re.I | re.S
)
_CA_RE = re.compile(r'\b(recently|launched|in the news|news item|2024|2025)\b', re.I)


def detect_question_type(text: str) -> str:
    if _MATCH_RE.search(text):
        return "match_pairs"
    if _MAP_RE.search(text):
        return "map_based"
    if _STATEMENT_RE.search(text):
        return "statement_based"
    if _CA_RE.search(text):
        return "current_affairs"
    return "direct_fact"


def record_answer(session_id: str, answer: dict, user_id: str = "user_1") -> None:
    """Persist a single answer immediately after submission."""
    con = get_conn()
    con.execute("""
        INSERT OR IGNORE INTO session_answers
        (session_id, question_hash, question_text, options, correct_answer,
         user_answer, is_correct, time_taken_sec, skipped, subject_id, topic_id, subtopic_id, dimension_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        session_id,
        answer.get("question_hash"),
        answer.get("question_text"),
        json.dumps(answer.get("options", {})),
        answer.get("correct_answer"),
        answer.get("user_answer"),
        1 if answer.get("is_correct") else 0,
        answer.get("time_taken_sec", 0),
        1 if answer.get("skipped") else 0,
        answer.get("subject_id"),
        answer.get("topic_id"),
        answer.get("subtopic_id"),
        answer.get("dimension_id"),
    ))
    con.commit()
    con.close()


def close_session(session_id: str, user_id: str = "user_1") -> dict:
    """Mark session as ended, compute score, store summary, update difficulty."""
    con = get_conn()
    con.row_factory = sqlite3.Row
    answers = con.execute(
        "SELECT * FROM session_answers WHERE session_id = ?", (session_id,)
    ).fetchall()

    if not answers:
        con.close()
        return {}

    # Convert to mutable dicts; backfill missing subtopic/topic from session config
    answers = [dict(a) for a in answers]
    session_row = con.execute(
        "SELECT session_type, config FROM quiz_sessions WHERE id=?", (session_id,)
    ).fetchone()
    session_type = session_row["session_type"] if session_row else None
    is_exam_sim = session_type == "exam_simulation"
    cfg: dict = {}
    if session_row and session_row["config"]:
        try:
            cfg = json.loads(session_row["config"])
            cfg_topic    = cfg.get("topic_id")    or None
            cfg_subtopic = cfg.get("subtopic_id") or None
            if cfg_topic or cfg_subtopic:
                for a in answers:
                    if not a.get("topic_id"):
                        a["topic_id"] = cfg_topic
                    if not a.get("subtopic_id"):
                        a["subtopic_id"] = cfg_subtopic
        except Exception:
            pass

    # Second pass: for answers still missing topic_id, look up from syllabus per subtopic
    for a in answers:
        if not a.get("topic_id") and a.get("subject_id") and a.get("subtopic_id"):
            a["topic_id"] = _canonical_topic_id(a["subject_id"], a["subtopic_id"])

    total = len(answers)
    correct = sum(1 for a in answers if a["is_correct"])
    skipped = sum(1 for a in answers if a["skipped"])
    score = (correct / max(total - skipped, 1)) * 100

    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("""
            UPDATE quiz_sessions
            SET end_time=?, answered=?, skipped=?, score=?
            WHERE id=?
        """, (datetime.now(timezone.utc).isoformat(), total - skipped, skipped, score, session_id))

        if is_exam_sim:
            # Exam sim is a test — do NOT pollute subtopic_scores or prep_profile.
            # Write to dedicated exam_sim_records table instead.
            _store_exam_sim_record(con, session_id, answers, score, cfg, user_id)
        else:
            _update_subtopic_scores(con, answers, user_id)
            _update_subtopic_dimension_scores(con, answers, user_id)

        _store_session_summary(con, session_id, answers, score)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

    # Difficulty update is idempotent — run after the main transaction closes
    if not is_exam_sim:
        _update_subtopic_difficulties(answers)

    return {
        "session_id": session_id,
        "total": total,
        "correct": correct,
        "skipped": skipped,
        "score": round(score, 1),
    }


def _store_exam_sim_record(
    con: sqlite3.Connection,
    session_id: str,
    answers: list[dict],
    score: float,
    cfg: dict,
    user_id: str = "user_1",
) -> None:
    """Write a row to exam_sim_records for dedicated mock-test history tracking."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS exam_sim_records (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id       TEXT NOT NULL UNIQUE,
            user_id          TEXT NOT NULL,
            session_date     TEXT,
            total_questions  INTEGER,
            correct          INTEGER,
            skipped          INTEGER,
            accuracy_pct     REAL,
            timed_minutes    INTEGER,
            subjects_covered TEXT,
            subject_breakdown TEXT,
            created_at       TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    total = len(answers)
    correct = sum(1 for a in answers if a["is_correct"] and not a["skipped"])
    skipped = sum(1 for a in answers if a["skipped"])
    timed = cfg.get("timed_duration_minutes") or cfg.get("time_minutes")

    # Per-subject breakdown
    subj_buckets: dict[str, dict] = {}
    for a in answers:
        sid = (a.get("subject_id") or "").split(",")[0].strip()
        if not sid:
            continue
        b = subj_buckets.setdefault(sid, {"correct": 0, "total": 0, "skipped": 0})
        b["total"] += 1
        if a["skipped"]:
            b["skipped"] += 1
        elif a["is_correct"]:
            b["correct"] += 1

    subjects_covered = list(subj_buckets.keys())
    subject_breakdown = {
        sid: {
            "correct": v["correct"],
            "total": v["total"],
            "skipped": v["skipped"],
            "accuracy_pct": round(v["correct"] / max(v["total"] - v["skipped"], 1) * 100, 1),
        }
        for sid, v in subj_buckets.items()
    }

    con.execute("""
        INSERT OR REPLACE INTO exam_sim_records
            (session_id, user_id, session_date, total_questions, correct, skipped,
             accuracy_pct, timed_minutes, subjects_covered, subject_breakdown)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        user_id,
        datetime.now(timezone.utc).date().isoformat(),
        total,
        correct,
        skipped,
        round(score, 1),
        int(timed) if timed else None,
        json.dumps(subjects_covered),
        json.dumps(subject_breakdown),
    ))


def _store_session_summary(
    con: sqlite3.Connection, session_id: str, answers, session_score: float
) -> None:
    # For exam simulation sessions spanning multiple subjects, collect all unique
    # non-empty subject IDs and join them. Single-subject sessions stay as-is.
    unique_subjects = list(dict.fromkeys(
        a["subject_id"] for a in answers if a.get("subject_id")
    ))
    subject_id = ",".join(unique_subjects) if unique_subjects else None
    session_date = datetime.now(timezone.utc).date().isoformat()

    total = len(answers)
    correct = sum(1 for a in answers if a["is_correct"] and not a["skipped"])

    # Question type breakdown
    type_totals: dict[str, int] = {}
    type_correct: dict[str, int] = {}
    for a in answers:
        if a["skipped"]:
            continue
        qtype = detect_question_type(a["question_text"] or "")
        type_totals[qtype] = type_totals.get(qtype, 0) + 1
        if a["is_correct"]:
            type_correct[qtype] = type_correct.get(qtype, 0) + 1

    type_breakdown = {
        qt: {
            "total": type_totals[qt],
            "correct": type_correct.get(qt, 0),
            "accuracy": round((type_correct.get(qt, 0) / type_totals[qt]) * 100, 1),
        }
        for qt in type_totals
    }

    # Per-subtopic accuracy for this session
    sub_acc: dict[str, list[int]] = {}
    for a in answers:
        if a["skipped"] or not a["subtopic_id"]:
            continue
        s = a["subtopic_id"]
        sub_acc.setdefault(s, [0, 0])
        sub_acc[s][1] += 1
        if a["is_correct"]:
            sub_acc[s][0] += 1

    weak = [s for s, (c, t) in sub_acc.items() if t > 0 and (c / t) * 100 < 45]
    strong = [s for s, (c, t) in sub_acc.items() if t > 0 and (c / t) * 100 >= 75]

    times = [a["time_taken_sec"] for a in answers if not a["skipped"] and a["time_taken_sec"]]
    avg_time = round(sum(times) / len(times), 1) if times else 0.0

    difficulty = "mixed"
    row = con.execute("SELECT config FROM quiz_sessions WHERE id=?", (session_id,)).fetchone()
    if row and row[0]:
        try:
            difficulty = json.loads(row[0]).get("difficulty", "mixed")
        except Exception:
            pass

    # Track which subtopics the user chose to expand — learning interest signal
    expanded = list({
        a["subtopic_id"] for a in answers
        if a.get("concept_expanded") and a["subtopic_id"]
    })

    con.execute("""
        INSERT OR REPLACE INTO session_summaries
        (session_id, subject_id, session_date, total_questions, correct, accuracy_pct,
         difficulty_attempted, avg_time_sec, weak_subtopics, strong_subtopics,
         question_type_breakdown, expanded_subtopics)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        session_id, subject_id, session_date, total, correct, round(session_score, 1),
        difficulty, avg_time, json.dumps(weak), json.dumps(strong), json.dumps(type_breakdown),
        json.dumps(expanded),
    ))


def _update_subtopic_difficulties(answers) -> None:
    """Update difficulty tier for each subtopic after session closes."""
    from difficulty_engine import update_difficulty

    grouped: dict[str, list] = {}
    for a in answers:
        if not a["subtopic_id"] or a["skipped"]:
            continue
        grouped.setdefault(a["subtopic_id"], []).append(a)

    for subtopic_id, ans in grouped.items():
        if not ans:
            continue
        correct = sum(1 for a in ans if a["is_correct"])
        accuracy = (correct / len(ans)) * 100
        update_difficulty(subtopic_id, ans[0]["subject_id"], accuracy)


def _update_subtopic_scores(con: sqlite3.Connection, answers, user_id: str = "user_1") -> None:
    # Group by (subject_id, subtopic_id) only — topic_id varies across sessions for the
    # same subtopic (canonical vs session-assigned), causing duplicate rows when included.
    grouped: dict[tuple, list] = {}
    for a in answers:
        key = (a["subject_id"], a["subtopic_id"])
        grouped.setdefault(key, []).append(a)

    for (subject_id, subtopic_id), ans in grouped.items():
        if not subject_id or not subtopic_id:
            continue
        correct = sum(1 for a in ans if a["is_correct"] and not a["skipped"])
        attempted = sum(1 for a in ans if not a["skipped"])
        if attempted == 0:
            continue  # never write a row for an all-skipped session — prevents ghost rows
        session_score = (correct / max(attempted, 1)) * 100
        # Use the most recently resolved topic_id from this session's answers
        topic_id = next((a["topic_id"] for a in ans if a.get("topic_id")), None)

        existing = con.execute("""
            SELECT score, total_attempts, correct_count FROM subtopic_scores
            WHERE user_id=? AND subject_id=? AND subtopic_id=?
        """, (user_id, subject_id, subtopic_id)).fetchone()

        if existing:
            new_total = existing["total_attempts"] + attempted
            new_correct = existing["correct_count"] + correct
            new_score = (new_correct / max(new_total, 1)) * 100
            old_score = existing["score"]
            trend = (
                "improving" if new_score > old_score + 5
                else "declining" if new_score < old_score - 5
                else "stable"
            )
            confidence = _confidence_label(new_score, new_total)
            con.execute("""
                UPDATE subtopic_scores
                SET topic_id=?, score=?, total_attempts=?, correct_count=?, trend=?,
                    confidence_level=?, last_tested=?, updated_at=?
                WHERE user_id=? AND subject_id=? AND subtopic_id=?
            """, (
                topic_id, new_score, new_total, new_correct, trend, confidence,
                datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(),
                user_id, subject_id, subtopic_id,
            ))
        else:
            confidence = _confidence_label(session_score, attempted)
            con.execute("""
                INSERT INTO subtopic_scores
                (user_id, subject_id, topic_id, subtopic_id, score, total_attempts,
                 correct_count, confidence_level, last_tested)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                user_id, subject_id, topic_id, subtopic_id, session_score, attempted, correct,
                confidence, datetime.now(timezone.utc).isoformat(),
            ))


def _update_subtopic_dimension_scores(con: sqlite3.Connection, answers, user_id: str = "user_1") -> None:
    """Update per-dimension accuracy after a session closes.
    Mirrors _update_subtopic_scores but groups by (subject_id, subtopic_id, dimension_id).
    Skips answers with no dimension_id — most sessions won't have any yet.
    """
    grouped: dict[tuple, list] = {}
    for a in answers:
        if not a.get("dimension_id") or not a.get("subject_id") or not a.get("subtopic_id"):
            continue
        if a.get("skipped"):
            continue
        key = (a["subject_id"], a["subtopic_id"], a["dimension_id"])
        grouped.setdefault(key, []).append(a)

    for (subject_id, subtopic_id, dimension_id), ans in grouped.items():
        correct  = sum(1 for a in ans if a["is_correct"])
        attempted = len(ans)
        if attempted == 0:
            continue
        session_score = (correct / attempted) * 100

        existing = con.execute("""
            SELECT score, attempts, correct_count FROM subtopic_dimension_scores
            WHERE user_id=? AND subject_id=? AND subtopic_id=? AND dimension_id=?
        """, (user_id, subject_id, subtopic_id, dimension_id)).fetchone()

        if existing:
            new_attempts = existing["attempts"] + attempted
            new_correct  = existing["correct_count"] + correct
            new_score    = (new_correct / max(new_attempts, 1)) * 100
            con.execute("""
                UPDATE subtopic_dimension_scores
                SET attempts=?, correct_count=?, score=?, last_tested=?
                WHERE user_id=? AND subject_id=? AND subtopic_id=? AND dimension_id=?
            """, (
                new_attempts, new_correct, new_score,
                datetime.now(timezone.utc).isoformat(),
                user_id, subject_id, subtopic_id, dimension_id,
            ))
        else:
            con.execute("""
                INSERT INTO subtopic_dimension_scores
                (user_id, subject_id, subtopic_id, dimension_id, attempts, correct_count, score, last_tested)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, subject_id, subtopic_id, dimension_id,
                attempted, correct, session_score,
                datetime.now(timezone.utc).isoformat(),
            ))


def _confidence_label(score: float, attempts: int) -> str:
    if attempts < 5:
        return "unassessed"
    if score >= 75:
        return "strong"
    if score >= 50:
        return "moderate"
    return "weak"


def get_subject_summary(subject_id: str, user_id: str = "user_1") -> dict:
    con = get_conn()
    rows = con.execute("""
        SELECT subtopic_id, score, confidence_level, total_attempts, trend
        FROM subtopic_scores WHERE user_id=? AND subject_id=?
    """, (user_id, subject_id)).fetchall()
    con.close()
    if not rows:
        return {"subject_id": subject_id, "avg_score": 0, "subtopics": []}
    avg = sum(r["score"] for r in rows) / len(rows)
    return {
        "subject_id": subject_id,
        "avg_score": round(avg, 1),
        "subtopics": [dict(r) for r in rows],
    }
