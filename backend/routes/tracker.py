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


@router.get("/time-stats")
def get_time_stats():
    """Returns study time totals: today, all-time, per-subject, avg Q time, 10-day breakdown."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # Total today — prefer end_time-start_time when end_time exists, else fall back to session_answers
    today_row = con.execute("""
        SELECT
            SUM(
                CASE
                    WHEN end_time IS NOT NULL
                    THEN (julianday(end_time) - julianday(start_time)) * 1440
                    ELSE (
                        SELECT COALESCE(SUM(sa.time_taken_sec), 0) / 60.0
                        FROM session_answers sa
                        WHERE sa.session_id = qs.id
                    )
                END
            ) as total_min
        FROM quiz_sessions qs
        WHERE date(start_time) = date('now')
    """).fetchone()
    total_today_min = round(today_row["total_min"] or 0, 1)

    # Total all-time
    alltime_row = con.execute("""
        SELECT
            SUM(
                CASE
                    WHEN end_time IS NOT NULL
                    THEN (julianday(end_time) - julianday(start_time)) * 1440
                    ELSE (
                        SELECT COALESCE(SUM(sa.time_taken_sec), 0) / 60.0
                        FROM session_answers sa
                        WHERE sa.session_id = qs.id
                    )
                END
            ) as total_min
        FROM quiz_sessions qs
    """).fetchone()
    total_all_time_min = round(alltime_row["total_min"] or 0, 1)

    # Per-subject breakdown
    subject_rows = con.execute("""
        SELECT
            subject_id,
            COUNT(*) as sessions,
            SUM(
                CASE
                    WHEN end_time IS NOT NULL
                    THEN (julianday(end_time) - julianday(start_time)) * 1440
                    ELSE (
                        SELECT COALESCE(SUM(sa.time_taken_sec), 0) / 60.0
                        FROM session_answers sa
                        WHERE sa.session_id = qs.id
                    )
                END
            ) as total_min
        FROM quiz_sessions qs
        WHERE subject_id IS NOT NULL
        GROUP BY subject_id
        ORDER BY total_min DESC
    """).fetchall()
    by_subject = [
        {
            "subject_id": r["subject_id"],
            "total_min": round(r["total_min"] or 0, 1),
            "sessions": r["sessions"],
        }
        for r in subject_rows
    ]

    # Average time per question (across all answered questions with time_taken_sec > 0)
    avg_row = con.execute("""
        SELECT AVG(time_taken_sec) as avg_sec
        FROM session_answers
        WHERE time_taken_sec IS NOT NULL AND time_taken_sec > 0
    """).fetchone()
    avg_time_per_question_sec = round(avg_row["avg_sec"] or 0, 1)

    # Daily breakdown — last 10 days
    daily_rows = con.execute("""
        SELECT
            date(start_time) as date,
            SUM(
                CASE
                    WHEN end_time IS NOT NULL
                    THEN (julianday(end_time) - julianday(start_time)) * 1440
                    ELSE (
                        SELECT COALESCE(SUM(sa.time_taken_sec), 0) / 60.0
                        FROM session_answers sa
                        WHERE sa.session_id = qs.id
                    )
                END
            ) as total_min
        FROM quiz_sessions qs
        WHERE date(start_time) >= date('now', '-9 days')
        GROUP BY date(start_time)
        ORDER BY date(start_time) ASC
    """).fetchall()
    daily_breakdown = [
        {"date": r["date"], "total_min": round(r["total_min"] or 0, 1)}
        for r in daily_rows
    ]

    con.close()

    return {
        "total_today_min": total_today_min,
        "total_all_time_min": total_all_time_min,
        "by_subject": by_subject,
        "avg_time_per_question_sec": avg_time_per_question_sec,
        "daily_breakdown": daily_breakdown,
    }
