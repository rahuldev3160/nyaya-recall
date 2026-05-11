import os
import json
import sqlite3
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")
PROFILE_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "prep_profile.json"
SYLLABUS_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "syllabus.json"


@router.get("/profile")
def get_profile():
    if not PROFILE_PATH.exists():
        return {"subjects": {}, "overall_readiness": 0, "phase": "diagnostic", "day_number": 1}
    return json.loads(PROFILE_PATH.read_text())


@router.get("/subjects")
def get_all_subjects():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT subject_id,
               AVG(score) as avg_score,
               COUNT(*) as subtopics_assessed,
               SUM(CASE WHEN confidence_level='strong' THEN 1 ELSE 0 END) as strong_count,
               SUM(CASE WHEN confidence_level='weak' THEN 1 ELSE 0 END) as weak_count
        FROM subtopic_scores WHERE user_id='user_1'
        GROUP BY subject_id
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


@router.get("/subtopics/{subject_id}")
def get_subtopics(subject_id: str):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT subtopic_id, topic_id, score, confidence_level, total_attempts, trend, last_tested
        FROM subtopic_scores WHERE user_id='user_1' AND subject_id=?
        ORDER BY score ASC
    """, (subject_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


@router.get("/gaps")
def get_gaps():
    """Returns subjects/subtopics still below 75% threshold with time estimates."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT subject_id, subtopic_id, topic_id, score, total_attempts
        FROM subtopic_scores WHERE user_id='user_1' AND score < 75
        ORDER BY score ASC
    """).fetchall()
    con.close()

    gaps = []
    for r in rows:
        hrs = max(0.5, round((75 - r["score"]) / 25 * 1.5, 1))
        gaps.append({**dict(r), "estimated_hours_to_75": hrs})
    return gaps


@router.get("/sar")
def get_sar():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM sar_scores WHERE user_id='user_1'").fetchone()
    con.close()
    if not row:
        return {"sar": 0.5, "total_claims": 0}
    return {"sar": row["sar"], "total_claims": row["total_claims"], "updated_at": row["updated_at"]}
