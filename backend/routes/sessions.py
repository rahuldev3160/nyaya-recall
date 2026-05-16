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
