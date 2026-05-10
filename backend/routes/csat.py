from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def csat_status():
    return {
        "status": "placeholder",
        "message": "CSAT module ready. Add content to /Users/rahulsingh/Desktop/UPSC/CSAT and run ingest.py to activate."
    }
