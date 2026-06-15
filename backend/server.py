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

from routes import quiz, sessions, analysis, plan, tracker, attestation, csat, config, library, feedback
from db import enable_wal, get_conn, DB_PATH


def _ensure_session_user_notes_table() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = get_conn()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS session_user_notes (
            session_id               TEXT PRIMARY KEY,
            user_id                  TEXT NOT NULL,
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


def _ensure_user_profiles_table() -> None:
    con = get_conn()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id      TEXT PRIMARY KEY,
            display_name TEXT,
            email        TEXT,
            exam_type    TEXT DEFAULT 'upsc_prelims',
            target_date  TEXT,
            daily_hours  REAL DEFAULT 2.0,
            tier         TEXT DEFAULT 'free',
            created_at   TEXT DEFAULT (datetime('now'))
        )
        """
    )
    con.commit()
    con.close()


def _ensure_question_notes_and_feedback_tables() -> None:
    """Create ISSUE-017 Phase 1 tables if they do not exist. Safe to re-run."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = get_conn()
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS question_notes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT    NOT NULL,
            session_id      TEXT    NOT NULL,
            question_hash   TEXT    NOT NULL,
            question_index  INTEGER NOT NULL,
            subtopic_id     TEXT    NOT NULL,
            subject_id      TEXT    NOT NULL,
            note_text       TEXT    DEFAULT '',
            still_weak      INTEGER DEFAULT 0,
            updated_at      TEXT    DEFAULT (datetime('now')),
            UNIQUE(session_id, question_hash)
        );

        CREATE INDEX IF NOT EXISTS idx_qn_session  ON question_notes(session_id);
        CREATE INDEX IF NOT EXISTS idx_qn_subtopic ON question_notes(subtopic_id, still_weak);
        CREATE INDEX IF NOT EXISTS idx_qn_qhash    ON question_notes(question_hash);

        CREATE TABLE IF NOT EXISTS content_feedback (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT    NOT NULL,
            content_type    TEXT    NOT NULL,
            session_id      TEXT    NOT NULL,
            question_hash   TEXT,
            subtopic_id     TEXT    NOT NULL,
            subject_id      TEXT    NOT NULL,
            notes_section   TEXT,
            verdict         TEXT    NOT NULL,
            note_text       TEXT    DEFAULT '',
            prompt_file     TEXT,
            created_at      TEXT    DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_cf_subtopic ON content_feedback(subtopic_id, content_type);
        CREATE INDEX IF NOT EXISTS idx_cf_subject  ON content_feedback(subject_id, verdict);
        CREATE INDEX IF NOT EXISTS idx_cf_qhash    ON content_feedback(question_hash);
        CREATE INDEX IF NOT EXISTS idx_cf_prompt   ON content_feedback(prompt_file, verdict);
        """
    )
    con.commit()
    con.close()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    enable_wal(DB_PATH)
    _ensure_user_profiles_table()
    _ensure_session_user_notes_table()
    _ensure_question_notes_and_feedback_tables()
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
app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])


@app.get("/health")
def health():
    return {"status": "ok"}
