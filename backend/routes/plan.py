import os
import json
import math
import sqlite3
import datetime
from pathlib import Path
from fastapi import APIRouter
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from plan_generator import generate_plan

router = APIRouter()
PLAN_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "study_plan.json"
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")


@router.get("/today")
def get_plan():
    if not PLAN_PATH.exists():
        return {"message": "No plan yet. Click 'Plan Today' to generate."}
    try:
        return json.loads(PLAN_PATH.read_text())
    except Exception:
        return {"message": "Plan file is corrupted. Generate a new one."}


@router.get("/today-status")
def get_plan_status():
    """Return which plan session subtopics have been completed in quiz sessions today."""
    if not PLAN_PATH.exists():
        return {"completed_subtopics": []}
    try:
        plan = json.loads(PLAN_PATH.read_text())
    except Exception:
        return {"completed_subtopics": []}

    plan_subtopics = [s.get("subtopic_id") for s in plan.get("sessions", []) if s.get("subtopic_id")]
    if not plan_subtopics:
        return {"completed_subtopics": []}

    completed: list[str] = []
    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            """
            SELECT DISTINCT sa.subtopic_id
            FROM session_answers sa
            JOIN quiz_sessions qs ON qs.id = sa.session_id
            WHERE qs.end_time IS NOT NULL
            AND substr(qs.start_time, 1, 10) = date('now')
            """
        ).fetchall()
        con.close()
        today_subtopics = {r[0] for r in rows if r[0]}
        completed = [st for st in plan_subtopics if st in today_subtopics]
    except Exception:
        pass

    return {"completed_subtopics": completed}


@router.post("/generate")
def create_plan(body: dict = {}):
    hours = body.get("available_hours", 8.0)
    plan = generate_plan(hours)
    return plan


PREP_PROFILE_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "prep_profile.json"
EXAM_DATE = datetime.date(2026, 5, 20)

_SUBJECT_NAMES = {
    "polity": "Polity & Governance",
    "economy": "Economy",
    "history_amac": "History (A/M/AC)",
    "modern_history": "Modern History",
    "geography": "Geography",
    "environment": "Environment",
    "science_tech": "Science & Tech",
    "current_affairs": "Current Affairs",
    "ir_governance": "IR & Governance",
}


@router.get("/trajectory")
def get_trajectory():
    today = datetime.date.today()
    days_remaining = max((EXAM_DATE - today).days, 0)

    if not PREP_PROFILE_PATH.exists():
        return {"error": "No prep profile found. Run batch_analyse.py first."}

    try:
        profile = json.loads(PREP_PROFILE_PATH.read_text())
    except Exception:
        return {"error": "Prep profile is corrupted."}

    subjects_raw = profile.get("subjects", {})
    overall_readiness = profile.get("overall_readiness", 0.0)

    subject_list = []
    at_risk_subjects = []

    for subj_id, name in _SUBJECT_NAMES.items():
        s = subjects_raw.get(subj_id, {})
        if not s:
            continue

        tested = s.get("tested_subtopics", 0)
        total = s.get("total_subtopics", 0)
        remaining = max(total - tested, 0)
        avg_score = s.get("avg_score", 0.0)
        coverage_pct = s.get("coverage_pct", 0.0)
        weak = s.get("weak_subtopics", [])

        if days_remaining > 0:
            daily_target = math.ceil(remaining / days_remaining) if remaining > 0 else 0
        else:
            daily_target = remaining

        if daily_target > 6:
            risk_level = "high"
        elif daily_target >= 3:
            risk_level = "medium"
        else:
            risk_level = "low"

        if risk_level == "high" or (remaining > 0 and coverage_pct < 50):
            at_risk_subjects.append(name)

        subject_list.append({
            "id": subj_id,
            "name": name,
            "readiness_pct": round(avg_score, 1),
            "coverage_pct": round(coverage_pct, 1),
            "subtopics_total": total,
            "subtopics_tested": tested,
            "subtopics_remaining": remaining,
            "daily_target": daily_target,
            "risk_level": risk_level,
            "top_priority_untested": weak[:5],
        })

    today_sessions_count = 0
    if PLAN_PATH.exists():
        try:
            plan = json.loads(PLAN_PATH.read_text())
            today_sessions_count = len(plan.get("sessions", []))
        except Exception:
            pass

    if days_remaining > 0:
        total_subtopics = sum(s["subtopics_total"] for s in subject_list)
        tested_by_exam = sum(
            min(s["subtopics_tested"] + s["daily_target"] * days_remaining, s["subtopics_total"])
            for s in subject_list
        )
        trajectory_note = (
            f"At current pace, {tested_by_exam}/{total_subtopics} subtopics covered by exam day."
        )
    else:
        trajectory_note = "Exam day is today — focus on revision and strategy."

    return {
        "exam_date": EXAM_DATE.isoformat(),
        "days_remaining": days_remaining,
        "overall_readiness": overall_readiness,
        "subjects": subject_list,
        "at_risk_subjects": at_risk_subjects,
        "trajectory_note": trajectory_note,
        "today_sessions_count": today_sessions_count,
    }
