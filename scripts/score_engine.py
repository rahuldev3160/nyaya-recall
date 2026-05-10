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
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")

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


def record_answer(session_id: str, answer: dict) -> None:
    """Persist a single answer immediately after submission."""
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO session_answers
        (session_id, question_hash, question_text, options, correct_answer,
         user_answer, is_correct, time_taken_sec, skipped, subject_id, topic_id, subtopic_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
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
    ))
    con.commit()
    con.close()


def close_session(session_id: str) -> dict:
    """Mark session as ended, compute score, store summary, update difficulty."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    answers = con.execute(
        "SELECT * FROM session_answers WHERE session_id = ?", (session_id,)
    ).fetchall()

    if not answers:
        con.close()
        return {}

    total = len(answers)
    correct = sum(1 for a in answers if a["is_correct"])
    skipped = sum(1 for a in answers if a["skipped"])
    score = (correct / max(total - skipped, 1)) * 100

    con.execute("""
        UPDATE quiz_sessions
        SET end_time=?, answered=?, skipped=?, score=?
        WHERE id=?
    """, (datetime.now(timezone.utc).isoformat(), total - skipped, skipped, score, session_id))
    con.commit()

    _update_subtopic_scores(con, answers)
    _store_session_summary(con, session_id, answers, score)
    con.commit()
    con.close()

    # Difficulty updates open their own connections — do after main commit
    _update_subtopic_difficulties(answers)

    return {
        "session_id": session_id,
        "total": total,
        "correct": correct,
        "skipped": skipped,
        "score": round(score, 1),
    }


def _store_session_summary(
    con: sqlite3.Connection, session_id: str, answers, session_score: float
) -> None:
    subject_id = answers[0]["subject_id"] if answers else None
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
        if len(ans) < 3:
            continue
        correct = sum(1 for a in ans if a["is_correct"])
        accuracy = (correct / len(ans)) * 100
        update_difficulty(subtopic_id, ans[0]["subject_id"], accuracy)


def _update_subtopic_scores(con: sqlite3.Connection, answers) -> None:
    grouped: dict[tuple, list] = {}
    for a in answers:
        key = (a["subject_id"], a["topic_id"], a["subtopic_id"])
        grouped.setdefault(key, []).append(a)

    for (subject_id, topic_id, subtopic_id), ans in grouped.items():
        if not subtopic_id:
            continue
        correct = sum(1 for a in ans if a["is_correct"] and not a["skipped"])
        attempted = sum(1 for a in ans if not a["skipped"])
        session_score = (correct / max(attempted, 1)) * 100

        existing = con.execute("""
            SELECT score, total_attempts, correct_count FROM subtopic_scores
            WHERE user_id='user_1' AND subject_id=? AND topic_id=? AND subtopic_id=?
        """, (subject_id, topic_id, subtopic_id)).fetchone()

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
                SET score=?, total_attempts=?, correct_count=?, trend=?, confidence_level=?,
                    last_tested=?, updated_at=?
                WHERE user_id='user_1' AND subject_id=? AND topic_id=? AND subtopic_id=?
            """, (
                new_score, new_total, new_correct, trend, confidence,
                datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(),
                subject_id, topic_id, subtopic_id,
            ))
        else:
            confidence = _confidence_label(session_score, attempted)
            con.execute("""
                INSERT INTO subtopic_scores
                (user_id, subject_id, topic_id, subtopic_id, score, total_attempts,
                 correct_count, confidence_level, last_tested)
                VALUES ('user_1',?,?,?,?,?,?,?,?)
            """, (
                subject_id, topic_id, subtopic_id, session_score, attempted, correct,
                confidence, datetime.now(timezone.utc).isoformat(),
            ))


def _confidence_label(score: float, attempts: int) -> str:
    if attempts < 5:
        return "unassessed"
    if score >= 75:
        return "strong"
    if score >= 50:
        return "moderate"
    return "weak"


def get_subject_summary(subject_id: str) -> dict:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT subtopic_id, score, confidence_level, total_attempts, trend
        FROM subtopic_scores WHERE user_id='user_1' AND subject_id=?
    """, (subject_id,)).fetchall()
    con.close()
    if not rows:
        return {"subject_id": subject_id, "avg_score": 0, "subtopics": []}
    avg = sum(r["score"] for r in rows) / len(rows)
    return {
        "subject_id": subject_id,
        "avg_score": round(avg, 1),
        "subtopics": [dict(r) for r in rows],
    }
