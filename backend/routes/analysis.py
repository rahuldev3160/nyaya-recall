import sys
from pathlib import Path
from fastapi import APIRouter, Depends

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from batch_analyse import run_analysis

router = APIRouter()


def _get_user_id() -> str:
    return "user_1"


@router.post("/sync")
def sync_and_analyse(body: dict = {}, user_id: str = Depends(_get_user_id)):
    """Trigger end-of-session/day batch analysis."""
    force = bool(body.get("force", False))
    result = run_analysis(force=force, user_id=user_id)
    return result or {"message": "No unsynced sessions found"}
