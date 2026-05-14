import os
import sqlite3
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from routes import quiz, sessions, analysis, plan, tracker, attestation, csat, config, library

DB_PATH = os.getenv("DB_PATH", "data/upsc.db")


def _ensure_session_user_notes_table() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS session_user_notes (
            session_id               TEXT PRIMARY KEY,
            user_id                  TEXT DEFAULT 'user_1',
            subject_id               TEXT,
            subtopic_id              TEXT NOT NULL,
            confusion                TEXT DEFAULT '',
            mnemonic                 TEXT DEFAULT '',
            still_weak               INTEGER DEFAULT 0,
            question_context_index   INTEGER,
            updated_at               TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.commit()
    con.close()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _ensure_session_user_notes_table()
    yield


app = FastAPI(title="UPSC 10-Day Prep API", version="1.0.0", lifespan=_lifespan)

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
app.include_router(library.router, prefix="/library", tags=["library"])


@app.get("/health")
def health():
    return {"status": "ok"}
