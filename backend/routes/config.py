from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import date
from fastapi import APIRouter, Depends

router = APIRouter(redirect_slashes=False)

_PROJECT_PATH = Path(os.getenv("PROJECT_PATH", "."))
_LEGACY_CONFIG = _PROJECT_PATH / "data" / "prep_config.json"


def _config_path(user_id: str) -> Path:
    return _PROJECT_PATH / "data" / "profiles" / user_id / "prep_config.json"


def _get_user_id() -> str:
    return "user_1"


@router.get("")
def get_config(user_id: str = Depends(_get_user_id)):
    path = _config_path(user_id)
    if not path.exists() and user_id == "user_1" and _LEGACY_CONFIG.exists():
        import shutil
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_LEGACY_CONFIG, path)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {"total_days": 10, "daily_hours": 6, "start_date": date.today().isoformat()}


@router.post("")
def save_config(body: dict, user_id: str = Depends(_get_user_id)):
    if not body.get("start_date"):
        body["start_date"] = date.today().isoformat()
    body["total_days"] = int(body.get("total_days", 10))
    body["daily_hours"] = float(body.get("daily_hours", 6))
    path = _config_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2))
    return body
