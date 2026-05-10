from __future__ import annotations
import os
import json
import sqlite3
from fastapi import APIRouter, HTTPException
import sys
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from score_engine import record_answer, close_session

router = APIRouter()
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")
_EXPAND_PROMPT = (Path(__file__).parent.parent.parent / "prompts" / "expand_concept.txt").read_text()
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


@router.post("/answer")
def submit_answer(answer: dict):
    try:
        record_answer(answer["session_id"], answer)
        return {"status": "recorded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    session = con.execute("SELECT * FROM quiz_sessions WHERE id=?", (session_id,)).fetchone()
    if not session:
        con.close()
        raise HTTPException(status_code=404, detail="Session not found")
    answers = con.execute("SELECT * FROM session_answers WHERE session_id=?", (session_id,)).fetchall()
    con.close()
    return {"session": dict(session), "answers": [dict(a) for a in answers]}


@router.post("/expand-concept")
def expand_concept(body: dict):
    session_id = body.get("session_id")
    question_hash = body.get("question_hash")
    question_text = body.get("question_text", "")
    subtopic_id = body.get("subtopic_id", "")

    if not question_text:
        raise HTTPException(status_code=400, detail="question_text required")

    prompt = (
        _EXPAND_PROMPT
        .replace("{{question_text}}", question_text)
        .replace("{{subtopic_id}}", subtopic_id)
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


@router.post("/import")
def import_session(data: dict):
    """Import a session exported from phone (offline HTML export)."""
    session = data.get("session", {})
    answers = data.get("answers", [])
    if not session.get("id"):
        raise HTTPException(status_code=400, detail="Missing session id")

    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT OR IGNORE INTO quiz_sessions
        (id, session_type, subject_id, topic_id, mode, config, start_time, end_time, total_questions, answered, skipped, score)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (session.get("id"), session.get("session_type"), session.get("subject_id"),
          session.get("topic_id"), session.get("mode"), json.dumps(session.get("config", {})),
          session.get("start_time"), session.get("end_time"),
          session.get("total_questions", len(answers)),
          session.get("answered", len(answers)), session.get("skipped", 0), session.get("score")))

    for a in answers:
        record_answer(session["id"], a)

    con.commit()
    con.close()
    return {"status": "imported", "answers": len(answers)}
