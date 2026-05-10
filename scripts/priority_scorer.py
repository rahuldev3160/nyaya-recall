"""Weighted PYQ priority scoring. decay = 0.9^(current_year - year)."""
from __future__ import annotations
import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")
CURRENT_YEAR = 2026
DECAY = 0.9


def compute_all_priorities() -> dict[str, float]:
    """Returns {subtopic_id: priority_score} for all subtopics with PYQ data."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT subtopic_id, year FROM pyq_questions WHERE subtopic_id IS NOT NULL"
    ).fetchall()
    con.close()

    scores: dict[str, float] = {}
    for row in rows:
        sid = row["subtopic_id"]
        weight = DECAY ** (CURRENT_YEAR - row["year"])
        scores[sid] = scores.get(sid, 0.0) + weight

    return scores


def rank_subtopics(subject_id: str | None = None) -> list[dict]:
    """Return subtopics sorted by priority descending, optionally filtered by subject."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    query = """
        SELECT subtopic_id, subject_id, topic_id, year
        FROM pyq_questions WHERE subtopic_id IS NOT NULL
    """
    params = []
    if subject_id:
        query += " AND subject_id = ?"
        params.append(subject_id)

    rows = con.execute(query, params).fetchall()
    con.close()

    scores: dict[str, dict] = {}
    for row in rows:
        sid = row["subtopic_id"]
        if sid not in scores:
            scores[sid] = {"subtopic_id": sid, "subject_id": row["subject_id"],
                           "topic_id": row["topic_id"], "priority_score": 0.0}
        scores[sid]["priority_score"] += DECAY ** (CURRENT_YEAR - row["year"])

    return sorted(scores.values(), key=lambda x: x["priority_score"], reverse=True)
