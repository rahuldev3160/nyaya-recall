import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from routes import quiz, sessions, analysis, plan, tracker, attestation, csat, config

app = FastAPI(title="UPSC 10-Day Prep API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local only; restrict for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
app.include_router(plan.router, prefix="/plan", tags=["plan"])
app.include_router(tracker.router, prefix="/tracker", tags=["tracker"])
app.include_router(attestation.router, prefix="/attestation", tags=["attestation"])
app.include_router(csat.router, prefix="/csat", tags=["csat"])
app.include_router(config.router, prefix="/config", tags=["config"])


@app.get("/health")
def health():
    return {"status": "ok"}
