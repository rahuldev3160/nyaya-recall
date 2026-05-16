from __future__ import annotations
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
import sys
import anthropic
import hashlib
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from score_engine import record_answer, close_session

router = APIRouter()
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")


def _maybe_auto_close_expired(session_id: str, con: sqlite3.Connection) -> bool:
    """If session is time_boxed and deadline passed, close it. Returns True if auto-closed."""
    row = con.execute(
        "SELECT mode, config, start_time, end_time FROM quiz_sessions WHERE id=?",
        (session_id,),
    ).fetchone()
    if not row or row["end_time"] or row["mode"] != "time_boxed":
        return False
    try:
        cfg = json.loads(row["config"] or "{}")
        time_minutes = cfg.get("time_minutes") or cfg.get("time_limit_min")
        if not time_minutes:
            return False
        start = datetime.fromisoformat(str(row["start_time"]).replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        deadline = start + timedelta(minutes=int(time_minutes))
        if datetime.now(timezone.utc) >= deadline:
            close_session(session_id)
            return True
    except Exception:
        pass
    return False
_EXPAND_PROMPT = (Path(__file__).parent.parent.parent / "prompts" / "expand_concept.txt").read_text()
_EXPAND_NOTES_PROMPT = (
    Path(__file__).parent.parent.parent / "prompts" / "expand_notes_selection.txt"
).read_text()
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_REVISION_PROMPT = (Path(__file__).parent.parent.parent / "prompts" / "revision_notes.txt").read_text()
_CACHE_PATH = Path(__file__).parent.parent.parent / "cache" / "explanations.json"


def _load_cache() -> dict:
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


@router.get("/")
def list_sessions(limit: int = 30):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT id, subject_id, topic_id, score, start_time, end_time,
                  total_questions, answered, skipped
           FROM quiz_sessions
           WHERE end_time IS NOT NULL
           ORDER BY start_time DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


@router.post("/answer")
def submit_answer(answer: dict):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    expired = _maybe_auto_close_expired(answer["session_id"], con)
    con.close()
    if expired:
        raise HTTPException(status_code=409, detail="Session expired — time limit reached")
    try:
        record_answer(answer["session_id"], answer)
        return {"status": "recorded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expand-concept")
def expand_concept(body: dict):
    session_id = body.get("session_id")
    question_hash = body.get("question_hash")
    question_text = body.get("question_text", "")
    subtopic_id = body.get("subtopic_id", "")

    if not question_text:
        raise HTTPException(status_code=400, detail="question_text required")

    prompt = (
        _EXPAND_PROMPT.replace("{{question_text}}", question_text).replace("{{subtopic_id}}", subtopic_id)
    )
    try:
        response = _client.messages.create(
            model=os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001"),
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        explanation = response.content[0].text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI error: {e}")

    if session_id and question_hash:
        try:
            con = sqlite3.connect(DB_PATH)
            con.execute(
                "UPDATE session_answers SET concept_expanded=1 WHERE session_id=? AND question_hash=?",
                (session_id, question_hash),
            )
            con.commit()
            con.close()
        except Exception:
            pass

    return {"explanation": explanation}


@router.post("/expand-notes-selection")
def expand_notes_selection(body: dict):
    selected = (body.get("selected_excerpt") or "").strip()
    subtopic_id = body.get("subtopic_id", "") or "general"
    subject_id = body.get("subject_id", "") or "general"

    if len(selected) < 12:
        raise HTTPException(status_code=400, detail="selected_excerpt too short (min ~12 chars)")
    if len(selected) > 4000:
        selected = selected[:4000]

    prompt = (
        _EXPAND_NOTES_PROMPT.replace("{{selected_excerpt}}", selected)
        .replace("{{subtopic_id}}", subtopic_id)
        .replace("{{subject_id}}", subject_id)
    )
    try:
        response = _client.messages.create(
            model=os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001"),
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        explanation = response.content[0].text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI error: {e}")

    return {"explanation": explanation}


def _ensure_question_notes_table(con: sqlite3.Connection) -> None:
    """Create per-question notes table if it doesn't exist (additive — no ALTER TABLE)."""
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS session_question_notes (
            session_id   TEXT NOT NULL,
            question_index INTEGER NOT NULL,
            user_id      TEXT DEFAULT 'user_1',
            note_text    TEXT DEFAULT '',
            updated_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (session_id, question_index)
        )
        """
    )
    con.commit()


@router.get("/{session_id}/user-notes")
def get_user_notes(session_id: str):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    _ensure_question_notes_table(con)
    row = con.execute(
        "SELECT * FROM session_user_notes WHERE session_id=? AND user_id='user_1'",
        (session_id,),
    ).fetchone()
    # Also return per-question notes as a dict keyed by question index
    q_rows = con.execute(
        "SELECT question_index, note_text FROM session_question_notes WHERE session_id=? AND user_id='user_1'",
        (session_id,),
    ).fetchall()
    con.close()
    per_question: dict = {str(r["question_index"]): r["note_text"] for r in q_rows}
    if not row:
        return {
            "session_id": session_id,
            "confusion": "",
            "mnemonic": "",
            "still_weak": False,
            "question_context_index": None,
            "subtopic_id": "",
            "subject_id": "",
            "per_question_notes": per_question,
        }
    d = dict(row)
    d["still_weak"] = bool(d.get("still_weak"))
    d["per_question_notes"] = per_question
    return d


@router.put("/{session_id}/user-notes")
def put_user_notes(session_id: str, body: dict):
    subtopic_id = body.get("subtopic_id")
    if not subtopic_id:
        raise HTTPException(status_code=400, detail="subtopic_id required")

    con = sqlite3.connect(DB_PATH)
    _ensure_question_notes_table(con)
    exists = con.execute("SELECT 1 FROM quiz_sessions WHERE id=?", (session_id,)).fetchone()
    if not exists:
        con.close()
        raise HTTPException(status_code=404, detail="quiz session not found")

    confusion = str(body.get("confusion", "") or "")[:8000]
    mnemonic = str(body.get("mnemonic", "") or "")[:4000]
    still_weak = 1 if body.get("still_weak") else 0
    qidx = body.get("question_context_index")
    try:
        qidx = int(qidx) if qidx is not None and qidx != "" else None
    except (TypeError, ValueError):
        qidx = None
    subject_id = str(body.get("subject_id", "") or "")
    now = datetime.now(timezone.utc).isoformat()

    # Save session-level fields (mnemonic, still_weak) and per-question confusion note
    con.execute(
        """
        INSERT INTO session_user_notes
        (session_id, user_id, subject_id, subtopic_id, confusion, mnemonic, still_weak, question_context_index, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(session_id) DO UPDATE SET
            subject_id=excluded.subject_id,
            subtopic_id=excluded.subtopic_id,
            confusion=excluded.confusion,
            mnemonic=excluded.mnemonic,
            still_weak=excluded.still_weak,
            question_context_index=excluded.question_context_index,
            updated_at=excluded.updated_at
        """,
        (
            session_id,
            "user_1",
            subject_id,
            subtopic_id,
            confusion,
            mnemonic,
            still_weak,
            qidx,
            now,
        ),
    )

    # If a per-question note is included, save it keyed by question_index
    note_text = body.get("note_text")
    if note_text is not None and qidx is not None:
        con.execute(
            """
            INSERT INTO session_question_notes (session_id, question_index, user_id, note_text, updated_at)
            VALUES (?, ?, 'user_1', ?, ?)
            ON CONFLICT(session_id, question_index) DO UPDATE SET
                note_text=excluded.note_text,
                updated_at=excluded.updated_at
            """,
            (session_id, qidx, str(note_text)[:8000], now),
        )

    con.commit()
    con.close()
    return {"status": "saved"}


@router.post("/{session_id}/revision-notes")
def get_revision_notes(session_id: str):
    """Generate (and cache) brief correction notes for wrong answers in a session."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT question_hash, question_text, correct_answer, user_answer, options
        FROM session_answers
        WHERE session_id=? AND is_correct=0 AND (skipped IS NULL OR skipped=0)
        ORDER BY id
        """,
        (session_id,),
    ).fetchall()
    con.close()

    if not rows:
        return {"notes": []}

    cache = _load_cache()
    results = []
    cache_updated = False

    for row in rows:
        cache_key = hashlib.sha256(f"{row['question_hash']}:revision:v2".encode()).hexdigest()
        if cache_key in cache:
            results.append({
                "question_text": row["question_text"],
                "correct_answer": row["correct_answer"],
                "user_answer": row["user_answer"],
                "explanation": cache[cache_key],
            })
            continue

        opts: dict = {}
        try:
            opts = json.loads(row["options"] or "{}")
        except Exception:
            pass
        prompt = (
            _REVISION_PROMPT
            .replace("{{question_text}}", row["question_text"] or "")
            .replace("{{user_answer}}", row["user_answer"] or "?")
            .replace("{{correct_answer}}", row["correct_answer"] or "?")
            .replace("{{option_a}}", opts.get("a", "—"))
            .replace("{{option_b}}", opts.get("b", "—"))
            .replace("{{option_c}}", opts.get("c", "—"))
            .replace("{{option_d}}", opts.get("d", "—"))
        )
        try:
            response = _client.messages.create(
                model=os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001"),
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            explanation = response.content[0].text.strip()
        except Exception as e:
            explanation = f"Unable to generate note: {e}"

        cache[cache_key] = explanation
        cache_updated = True
        results.append({
            "question_text": row["question_text"],
            "correct_answer": row["correct_answer"],
            "user_answer": row["user_answer"],
            "explanation": explanation,
        })

    if cache_updated:
        try:
            _save_cache(cache)
        except Exception:
            pass

    return {"notes": results}


@router.post("/{session_id}/close")
def end_session(session_id: str):
    summary = close_session(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found or already closed")
    return summary


@router.get("/{session_id}")
def get_session(session_id: str):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    _maybe_auto_close_expired(session_id, con)
    session = con.execute("SELECT * FROM quiz_sessions WHERE id=?", (session_id,)).fetchone()
    if not session:
        con.close()
        raise HTTPException(status_code=404, detail="Session not found")
    answers = con.execute("SELECT * FROM session_answers WHERE session_id=?", (session_id,)).fetchall()
    con.close()
    return {"session": dict(session), "answers": [dict(a) for a in answers]}


def _ensure_question_notes_table_v2(con: sqlite3.Connection) -> None:
    """Create the ISSUE-017 question_notes table if it does not exist. Additive only."""
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS question_notes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT    NOT NULL DEFAULT 'user_1',
            session_id      TEXT    NOT NULL,
            question_hash   TEXT    NOT NULL,
            question_index  INTEGER NOT NULL,
            subtopic_id     TEXT    NOT NULL,
            subject_id      TEXT    NOT NULL,
            note_text       TEXT    DEFAULT '',
            still_weak      INTEGER DEFAULT 0,
            updated_at      TEXT    DEFAULT (datetime('now')),
            UNIQUE(session_id, question_hash)
        );

        CREATE INDEX IF NOT EXISTS idx_qn_session  ON question_notes(session_id);
        CREATE INDEX IF NOT EXISTS idx_qn_subtopic ON question_notes(subtopic_id, still_weak);
        CREATE INDEX IF NOT EXISTS idx_qn_qhash    ON question_notes(question_hash);
        """
    )
    con.commit()


@router.put("/{session_id}/question-notes/{question_hash}")
def put_question_note(session_id: str, question_hash: str, body: dict):
    """
    Upsert a per-question note (ISSUE-017 Phase 1).
    Called on 700 ms debounce from the note textarea — pure DB write, no AI calls.
    """
    subtopic_id = (body.get("subtopic_id") or "").strip()
    subject_id = (body.get("subject_id") or "").strip()
    note_text = str(body.get("note_text") or "")[:8000]
    still_weak = 1 if body.get("still_weak") else 0

    try:
        question_index = int(body.get("question_index", 0))
    except (TypeError, ValueError):
        question_index = 0

    if not subtopic_id:
        raise HTTPException(status_code=400, detail="subtopic_id required")

    now = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    _ensure_question_notes_table_v2(con)

    exists = con.execute("SELECT 1 FROM quiz_sessions WHERE id=?", (session_id,)).fetchone()
    if not exists:
        con.close()
        raise HTTPException(status_code=404, detail="quiz session not found")

    con.execute(
        """
        INSERT INTO question_notes
            (user_id, session_id, question_hash, question_index, subtopic_id, subject_id,
             note_text, still_weak, updated_at)
        VALUES ('user_1', ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, question_hash) DO UPDATE SET
            note_text    = excluded.note_text,
            still_weak   = excluded.still_weak,
            updated_at   = excluded.updated_at
        """,
        (
            session_id,
            question_hash,
            question_index,
            subtopic_id,
            subject_id,
            note_text,
            still_weak,
            now,
        ),
    )
    con.commit()
    con.close()
    return {"status": "saved"}


@router.get("/{session_id}/question-notes")
def get_question_notes(session_id: str):
    """
    Return all per-question notes for a session (ISSUE-017 Phase 1).
    Frontend calls this on session start to pre-populate note textareas.
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    _ensure_question_notes_table_v2(con)

    rows = con.execute(
        """
        SELECT question_hash, question_index, note_text, still_weak
        FROM question_notes
        WHERE session_id=? AND user_id='user_1'
        ORDER BY question_index
        """,
        (session_id,),
    ).fetchall()
    con.close()

    notes = [
        {
            "question_hash": r["question_hash"],
            "question_index": r["question_index"],
            "note_text": r["note_text"] or "",
            "still_weak": bool(r["still_weak"]),
        }
        for r in rows
    ]
    return {"notes": notes}


@router.get("/{session_id}/exam-results")
def get_exam_results(session_id: str):
    """
    Return per-subject and per-topic breakdown for an exam_simulation session.
    Reads session_answers joined with the syllabus to resolve topic names.
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    session_row = con.execute(
        "SELECT session_type, config FROM quiz_sessions WHERE id=?", (session_id,)
    ).fetchone()
    if not session_row:
        con.close()
        raise HTTPException(status_code=404, detail="Session not found")

    answers = con.execute(
        """
        SELECT subject_id, subtopic_id, is_correct, skipped
        FROM session_answers
        WHERE session_id=?
        ORDER BY id
        """,
        (session_id,),
    ).fetchall()
    con.close()

    # Load syllabus to resolve names and group subtopics → topics → subjects
    syllabus_path = Path(__file__).parent.parent.parent / "data" / "syllabus.json"
    try:
        syllabus_raw = json.loads(syllabus_path.read_text())
    except Exception:
        syllabus_raw = {}

    # Build lookup: subtopic_id → {subject_id, subject_name, topic_id, topic_name, subtopic_name}
    st_lookup: dict[str, dict] = {}
    for subj in syllabus_raw.get("subjects", []):
        for topic in subj.get("topics", []):
            for st in topic.get("subtopics", []):
                st_lookup[st["id"]] = {
                    "subject_id": subj["id"],
                    "subject_name": subj.get("name", subj["id"]),
                    "topic_id": topic["id"],
                    "topic_name": topic.get("name", topic["id"]),
                    "subtopic_name": st.get("name", st["id"]),
                }

    # Aggregate answers into subject → topic → subtopic buckets
    # Structure: { subject_id: { "name": ..., "topics": { topic_id: { "name": ..., "q": 0, "c": 0 } }, "q": 0, "c": 0 } }
    subj_buckets: dict[str, dict] = {}
    total_q = 0
    total_correct = 0
    total_attempted = 0

    for row in answers:
        subject_id = (row["subject_id"] or "").split(",")[0].strip()
        subtopic_id = row["subtopic_id"] or ""
        is_correct = bool(row["is_correct"])
        skipped = bool(row["skipped"])

        total_q += 1
        if not skipped:
            total_attempted += 1
        if is_correct and not skipped:
            total_correct += 1

        # Resolve names from syllabus; fall back to raw IDs
        meta = st_lookup.get(subtopic_id)
        if meta:
            resolved_subject_id = meta["subject_id"]
            subject_name = meta["subject_name"]
            topic_id = meta["topic_id"]
            topic_name = meta["topic_name"]
        else:
            resolved_subject_id = subject_id or "unknown"
            subject_name = (subject_id or "unknown").replace("_", " ").title()
            topic_id = "unknown"
            topic_name = "Unknown Topic"

        if resolved_subject_id not in subj_buckets:
            subj_buckets[resolved_subject_id] = {
                "subject_id": resolved_subject_id,
                "subject_name": subject_name,
                "q": 0,
                "c": 0,
                "topics": {},
            }
        sb = subj_buckets[resolved_subject_id]
        sb["q"] += 1
        if is_correct and not skipped:
            sb["c"] += 1

        if topic_id not in sb["topics"]:
            sb["topics"][topic_id] = {"topic_id": topic_id, "topic_name": topic_name, "q": 0, "c": 0}
        tb = sb["topics"][topic_id]
        tb["q"] += 1
        if is_correct and not skipped:
            tb["c"] += 1

    # Build output
    by_subject = []
    for sb in sorted(subj_buckets.values(), key=lambda x: x["subject_name"]):
        topics_out = []
        for tb in sorted(sb["topics"].values(), key=lambda x: x["topic_name"]):
            acc = round(tb["c"] / tb["q"] * 100, 1) if tb["q"] else 0.0
            topics_out.append({
                "topic_id": tb["topic_id"],
                "topic_name": tb["topic_name"],
                "questions": tb["q"],
                "correct": tb["c"],
                "accuracy_pct": acc,
            })
        s_acc = round(sb["c"] / sb["q"] * 100, 1) if sb["q"] else 0.0
        by_subject.append({
            "subject_id": sb["subject_id"],
            "subject_name": sb["subject_name"],
            "questions": sb["q"],
            "correct": sb["c"],
            "accuracy_pct": s_acc,
            "topics": topics_out,
        })

    overall_acc = round(total_correct / total_q * 100, 1) if total_q else 0.0

    return {
        "total_correct": total_correct,
        "total_attempted": total_attempted,
        "total_questions": total_q,
        "accuracy_pct": overall_acc,
        "by_subject": by_subject,
    }


@router.post("/import")
def import_session(data: dict):
    """Import a session exported from phone (offline HTML export)."""
    session = data.get("session", {})
    answers = data.get("answers", [])
    if not session.get("id"):
        raise HTTPException(status_code=400, detail="Missing session id")

    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        INSERT OR IGNORE INTO quiz_sessions
        (id, session_type, subject_id, topic_id, mode, config, start_time, end_time, total_questions, answered, skipped, score)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """,
        (
            session.get("id"),
            session.get("session_type"),
            session.get("subject_id"),
            session.get("topic_id"),
            session.get("mode"),
            json.dumps(session.get("config", {})),
            session.get("start_time"),
            session.get("end_time"),
            session.get("total_questions", len(answers)),
            session.get("answered", len(answers)),
            session.get("skipped", 0),
            session.get("score"),
        ),
    )

    for a in answers:
        record_answer(session["id"], a)

    con.commit()
    con.close()
    return {"status": "imported", "answers": len(answers)}
