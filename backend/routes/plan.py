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
PLAN_PATH      = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "study_plan.json"
USER_PLAN_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "study_plan_user.json"
SYLLABUS_PATH  = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "syllabus.json"
DB_PATH        = os.getenv("DB_PATH", "data/upsc.db")

_GS1_SUBJECTS = {"polity", "economy", "history_amac", "modern_history", "geography",
                  "environment", "science_tech", "current_affairs", "ir_governance"}


def _ensure_edit_log_table():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS plan_edit_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date    TEXT NOT NULL,
            session_index   INTEGER NOT NULL,
            original_session TEXT NOT NULL,
            edited_session  TEXT NOT NULL,
            edit_timestamp  TEXT NOT NULL,
            changed_fields  TEXT
        )
    """)
    con.commit()
    con.close()


def _load_active_plan() -> dict:
    """Return user-edited plan for today if it exists, else the AI-generated plan."""
    today = datetime.date.today().isoformat()
    if USER_PLAN_PATH.exists():
        try:
            user_plan = json.loads(USER_PLAN_PATH.read_text())
            if user_plan.get("session_date") == today:
                return {**user_plan, "is_user_edited": True}
        except Exception:
            pass
    if not PLAN_PATH.exists():
        return {"message": "No plan yet. Click 'Plan Today' to generate."}
    try:
        plan = json.loads(PLAN_PATH.read_text())
        # Strip CSAT sessions from GS1 plan view
        plan["sessions"] = [s for s in plan.get("sessions", []) if s.get("subject_id") != "csat"]
        return {**plan, "is_user_edited": False}
    except Exception:
        return {"message": "Plan file is corrupted. Generate a new one."}


@router.get("/today")
def get_plan():
    return _load_active_plan()


@router.get("/syllabus-tree")
def get_syllabus_tree():
    """Return subject → topic → subtopic hierarchy for plan-edit dropdowns."""
    if not SYLLABUS_PATH.exists():
        return []
    try:
        raw = json.loads(SYLLABUS_PATH.read_text())
        subjects = raw if isinstance(raw, list) else raw.get("subjects", [])
        result = []
        for s in subjects:
            if s.get("id") not in _GS1_SUBJECTS:
                continue
            result.append({
                "id": s["id"],
                "name": s.get("name", s["id"]),
                "topics": [
                    {
                        "id": t["id"],
                        "name": t.get("name", t["id"]),
                        "subtopics": [
                            {
                                "id": st["id"],
                                "name": st.get("name", st["id"]),
                                "dimensions": [d if isinstance(d, str) else d.get("id", d) for d in st.get("dimensions", [])],
                            }
                            for st in t.get("subtopics", [])
                        ],
                    }
                    for t in s.get("topics", [])
                ],
            })
        return result
    except Exception:
        return []


@router.patch("/user-sessions")
def patch_user_sessions(body: dict):
    """Save user-edited plan. Log delta against model's original for every changed session."""
    edited_sessions = body.get("sessions")
    if not edited_sessions:
        return {"error": "No sessions provided"}

    _ensure_edit_log_table()
    today = datetime.date.today().isoformat()

    # Load model's original for delta comparison
    original_sessions: list = []
    if PLAN_PATH.exists():
        try:
            original_sessions = json.loads(PLAN_PATH.read_text()).get("sessions", [])
        except Exception:
            pass

    DELTA_FIELDS = ("subject_id", "topic_id", "subtopic_id", "format", "difficulty",
                    "num_questions", "estimated_minutes")
    try:
        con = sqlite3.connect(DB_PATH)
        now = datetime.datetime.utcnow().isoformat()
        for i, edited in enumerate(edited_sessions):
            original = original_sessions[i] if i < len(original_sessions) else {}
            changed = [k for k in DELTA_FIELDS if edited.get(k) != original.get(k)]
            if changed:
                con.execute(
                    """INSERT INTO plan_edit_log
                       (session_date, session_index, original_session, edited_session, edit_timestamp, changed_fields)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (today, i, json.dumps(original), json.dumps(edited), now, json.dumps(changed)),
                )
        con.commit()
        con.close()
    except Exception:
        pass

    user_plan = {
        "sessions": edited_sessions,
        "session_date": today,
        "user_edited": True,
        "edited_at": datetime.datetime.utcnow().isoformat(),
    }
    USER_PLAN_PATH.write_text(json.dumps(user_plan, indent=2))
    return {"ok": True, "sessions_saved": len(edited_sessions)}


@router.delete("/user-overrides")
def delete_user_overrides():
    """Discard user edits — revert to AI-generated plan."""
    if USER_PLAN_PATH.exists():
        USER_PLAN_PATH.unlink()
    return {"ok": True, "reset": True}


@router.get("/today-status")
def get_plan_status():
    """Return which plan session subtopics have been completed in quiz sessions today."""
    try:
        plan = _load_active_plan()
    except Exception:
        return {"completed_subtopics": []}
    if "message" in plan:
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
            AND date(qs.end_time) = date('now')
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

        topics = s.get("topics", [])
        uncovered_topics = sum(1 for t in topics if t.get("coverage_pct", 0) == 0)
        at_risk_topics   = sum(1 for t in topics if t.get("risk_level") == "high")

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
            "topics_total": len(topics),
            "uncovered_topics_count": uncovered_topics,
            "at_risk_topics_count": at_risk_topics,
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
