from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import date
from fastapi import APIRouter

router = APIRouter()
CONFIG_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "prep_config.json"


@router.get("/")
def get_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {"total_days": 10, "daily_hours": 6, "start_date": date.today().isoformat()}


@router.post("/")
def save_config(body: dict):
    if not body.get("start_date"):
        body["start_date"] = date.today().isoformat()
    body["total_days"] = int(body.get("total_days", 10))
    body["daily_hours"] = float(body.get("daily_hours", 6))
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(body, indent=2))
    return body
