import sys
from pathlib import Path
from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from batch_analyse import run_analysis

router = APIRouter()


@router.post("/sync")
def sync_and_analyse(body: dict = {}):
    """Trigger end-of-session/day batch analysis."""
    force = bool(body.get("force", False))
    result = run_analysis(force=force)
    return result or {"message": "No unsynced sessions found"}
