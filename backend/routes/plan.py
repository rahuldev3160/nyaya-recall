import os
import json
import sqlite3
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
