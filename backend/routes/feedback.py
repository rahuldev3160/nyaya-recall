from __future__ import annotations
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

router = APIRouter()
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")

# Maps content_type to the prompt file that generated it
_ADAPTIVE_SESSION_TYPES = {"adaptive", "session"}

VALID_VERDICTS = {"correct", "missing", "omit", "wrong"}
VALID_CONTENT_TYPES = {"question", "explanation", "notes_section"}
VALID_NOTES_SECTIONS = {"core_concept", "pyq_angles", "current_affairs", "broader_linkages"}


def _ensure_feedback_table(con: sqlite3.Connection) -> None:
    """Create content_feedback table if it does not exist. Safe to call on every request."""
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS content_feedback (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT    NOT NULL DEFAULT 'user_1',
            content_type    TEXT    NOT NULL,
            session_id      TEXT    NOT NULL,
            question_hash   TEXT,
            subtopic_id     TEXT    NOT NULL,
            subject_id      TEXT    NOT NULL,
            notes_section   TEXT,
            verdict         TEXT    NOT NULL,
            note_text       TEXT    DEFAULT '',
            prompt_file     TEXT,
            created_at      TEXT    DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_cf_subtopic ON content_feedback(subtopic_id, content_type);
        CREATE INDEX IF NOT EXISTS idx_cf_subject  ON content_feedback(subject_id, verdict);
        CREATE INDEX IF NOT EXISTS idx_cf_qhash    ON content_feedback(question_hash);
        CREATE INDEX IF NOT EXISTS idx_cf_prompt   ON content_feedback(prompt_file, verdict);
        """
    )
    con.commit()


def _resolve_prompt_file(content_type: str, session_id: str, con: sqlite3.Connection) -> str:
    """
    Determine which prompt file to tag the feedback against.
    Adaptive / session quiz questions → adaptive_session.txt.
    Diagnostic questions / explanations → diagnostic_quiz.txt.
    Notes sections always → session_notes.txt.
    """
    if content_type == "notes_section":
        return "session_notes.txt"
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT session_type FROM quiz_sessions WHERE id=?", (session_id,)
    ).fetchone()
    if row and row["session_type"] in _ADAPTIVE_SESSION_TYPES:
        return "adaptive_session.txt"
    return "diagnostic_quiz.txt"


# ── POST /feedback/content ────────────────────────────────────────────────────

@router.post("/content")
def post_content_feedback(body: dict):
    """
    Record qualitative feedback on a question, explanation, or notes section.
    Uses INSERT (not upsert) — multiple verdicts are allowed; aggregation reads the latest.
    No AI calls — pure DB write.
    """
    session_id = (body.get("session_id") or "").strip()
    content_type = (body.get("content_type") or "").strip()
    verdict = (body.get("verdict") or "").strip()
    subtopic_id = (body.get("subtopic_id") or "").strip()
    subject_id = (body.get("subject_id") or "").strip()

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    if content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"content_type must be one of {sorted(VALID_CONTENT_TYPES)}",
        )
    if verdict not in VALID_VERDICTS:
        raise HTTPException(
            status_code=400,
            detail=f"verdict must be one of {sorted(VALID_VERDICTS)}",
        )
    if not subtopic_id:
        raise HTTPException(status_code=400, detail="subtopic_id required")
    if not subject_id:
        raise HTTPException(status_code=400, detail="subject_id required")

    question_hash = (body.get("question_hash") or "").strip() or None
    notes_section = (body.get("notes_section") or "").strip() or None
    note_text = str(body.get("note_text") or "")[:2000]

    if content_type == "notes_section":
        if notes_section not in VALID_NOTES_SECTIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"notes_section must be one of {sorted(VALID_NOTES_SECTIONS)} "
                    "when content_type='notes_section'"
                ),
            )
    else:
        if not question_hash:
            raise HTTPException(
                status_code=400,
                detail="question_hash required when content_type is 'question' or 'explanation'",
            )

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    _ensure_feedback_table(con)

    prompt_file = _resolve_prompt_file(content_type, session_id, con)

    cur = con.execute(
        """
        INSERT INTO content_feedback
            (user_id, content_type, session_id, question_hash, subtopic_id, subject_id,
             notes_section, verdict, note_text, prompt_file)
        VALUES ('user_1', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            content_type,
            session_id,
            question_hash,
            subtopic_id,
            subject_id,
            notes_section,
            verdict,
            note_text,
            prompt_file,
        ),
    )
    con.commit()
    row_id = cur.lastrowid
    con.close()

    return {"status": "saved", "id": row_id}


# ── GET /feedback/content/summary ─────────────────────────────────────────────

@router.get("/content/summary")
def get_content_feedback_summary(since: str = Query(default="", description="ISO date string e.g. 2026-05-01")):
    """
    Aggregate content_feedback rows grouped by prompt_file and verdict.
    Used by apply_feedback.py (Phase 3) to surface actionable prompt issues.

    Query params:
      since — optional ISO date string (YYYY-MM-DD). If omitted, returns all-time data.

    Response shape:
      {
        "by_prompt_file": {
          "session_notes.txt": {
            "missing": [{"subtopic_id": ..., "notes_section": ..., "note_text": ..., "count": N}],
            "wrong":   [...],
            "omit":    [...],
            "correct": [...]
          },
          ...
        },
        "total_feedback_items": N
      }
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    _ensure_feedback_table(con)

    # Build date filter clause
    date_clause = ""
    params: list = []
    if since and since.strip():
        date_clause = " AND created_at >= ?"
        params.append(since.strip())

    # Fetch all rows matching the filter
    rows = con.execute(
        f"""
        SELECT
            prompt_file,
            verdict,
            subtopic_id,
            notes_section,
            note_text,
            COUNT(*) AS cnt
        FROM content_feedback
        WHERE 1=1{date_clause}
        GROUP BY prompt_file, verdict, subtopic_id, notes_section
        ORDER BY cnt DESC
        """,
        params,
    ).fetchall()

    # Total count (ungrouped)
    total_row = con.execute(
        f"SELECT COUNT(*) AS n FROM content_feedback WHERE 1=1{date_clause}",
        params,
    ).fetchone()
    total = total_row["n"] if total_row else 0
    con.close()

    # Reshape into nested dict
    by_prompt: dict = {}
    for row in rows:
        pf = row["prompt_file"] or "unknown"
        v = row["verdict"]
        if pf not in by_prompt:
            by_prompt[pf] = {vk: [] for vk in VALID_VERDICTS}
        if v not in by_prompt[pf]:
            by_prompt[pf][v] = []
        by_prompt[pf][v].append({
            "subtopic_id": row["subtopic_id"],
            "notes_section": row["notes_section"],
            "note_text": row["note_text"] or "",
            "count": row["cnt"],
        })

    return {
        "by_prompt_file": by_prompt,
        "total_feedback_items": total,
    }
