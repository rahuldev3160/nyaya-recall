"""Per-subtopic adaptive difficulty tracking. Tiers: easy → medium → hard → exam."""
from __future__ import annotations
import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")

TIERS = ["easy", "medium", "hard", "exam"]
GOOD_THRESHOLD = 75
BAD_THRESHOLD = 45
CONSECUTIVE_TO_CHANGE = 2


def get_difficulty(subtopic_id: str) -> str:
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT current_difficulty FROM subtopic_difficulty WHERE subtopic_id=?", (subtopic_id,)
    ).fetchone()
    con.close()
    return row[0] if row else "easy"


def update_difficulty(subtopic_id: str, subject_id: str, accuracy: float) -> dict:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM subtopic_difficulty WHERE subtopic_id=?", (subtopic_id,)
    ).fetchone()

    if row:
        current = row["current_difficulty"]
        consec_good = row["consecutive_good"]
        consec_bad = row["consecutive_bad"]
        total_sessions = row["total_sessions"]
    else:
        current = "easy"
        consec_good = 0
        consec_bad = 0
        total_sessions = 0

    if accuracy >= GOOD_THRESHOLD:
        consec_good += 1
        consec_bad = 0
    elif accuracy < BAD_THRESHOLD:
        consec_bad += 1
        consec_good = 0
    else:
        consec_good = 0
        consec_bad = 0

    total_sessions += 1

    try:
        idx = TIERS.index(current)
    except ValueError:
        idx = 0
        current = "easy"

    if consec_good >= CONSECUTIVE_TO_CHANGE and idx < len(TIERS) - 1:
        new_difficulty = TIERS[idx + 1]
        consec_good = 0
    elif consec_bad >= CONSECUTIVE_TO_CHANGE and idx > 0:
        new_difficulty = TIERS[idx - 1]
        consec_bad = 0
    else:
        new_difficulty = current

    now = datetime.now(timezone.utc).isoformat()
    if row:
        con.execute("""
            UPDATE subtopic_difficulty
            SET current_difficulty=?, consecutive_good=?, consecutive_bad=?,
                total_sessions=?, last_updated=?
            WHERE subtopic_id=?
        """, (new_difficulty, consec_good, consec_bad, total_sessions, now, subtopic_id))
    else:
        con.execute("""
            INSERT INTO subtopic_difficulty
            (subtopic_id, subject_id, current_difficulty, consecutive_good,
             consecutive_bad, total_sessions, last_updated)
            VALUES (?,?,?,?,?,?,?)
        """, (subtopic_id, subject_id, new_difficulty, consec_good, consec_bad, total_sessions, now))

    con.commit()
    con.close()

    exam_ready = new_difficulty == "exam" and accuracy >= GOOD_THRESHOLD
    return {"subtopic_id": subtopic_id, "difficulty": new_difficulty, "exam_ready": exam_ready}


def get_difficulty_profile(subject_id: str | None = None) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    if subject_id:
        rows = con.execute(
            "SELECT * FROM subtopic_difficulty WHERE subject_id=? ORDER BY last_updated DESC",
            (subject_id,)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM subtopic_difficulty ORDER BY last_updated DESC"
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]
