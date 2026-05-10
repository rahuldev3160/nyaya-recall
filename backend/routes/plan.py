import os
import json
from pathlib import Path
from fastapi import APIRouter
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from plan_generator import generate_plan

router = APIRouter()
PLAN_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "study_plan.json"


@router.get("/today")
def get_plan():
    if not PLAN_PATH.exists():
        return {"message": "No plan yet. Click 'Plan Today' to generate."}
    try:
        return json.loads(PLAN_PATH.read_text())
    except Exception:
        return {"message": "Plan file is corrupted. Generate a new one."}


@router.post("/generate")
def create_plan(body: dict = {}):
    hours = body.get("available_hours", 8.0)
    plan = generate_plan(hours)
    return plan
