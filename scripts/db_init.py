"""Run once to create the SQLite schema. Safe to re-run (IF NOT EXISTS)."""
import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS pyq_questions (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        year             INTEGER NOT NULL,
        question_text    TEXT NOT NULL,
        option_a         TEXT,
        option_b         TEXT,
        option_c         TEXT,
        option_d         TEXT,
        correct_answer   TEXT,
        subject_id       TEXT,
        topic_id         TEXT,
        subtopic_id      TEXT,
        concepts         TEXT,
        source_file      TEXT,
        question_hash    TEXT UNIQUE,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS quiz_sessions (
        id               TEXT PRIMARY KEY,
        user_id          TEXT DEFAULT 'user_1',
        session_type     TEXT,
        subject_id       TEXT,
        topic_id         TEXT,
        mode             TEXT,
        config           TEXT,
        start_time       TIMESTAMP,
        end_time         TIMESTAMP,
        total_questions  INTEGER,
        answered         INTEGER DEFAULT 0,
        skipped          INTEGER DEFAULT 0,
        score            REAL,
        synced           INTEGER DEFAULT 0,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS session_answers (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id       TEXT REFERENCES quiz_sessions(id),
        question_hash    TEXT,
        question_text    TEXT,
        options          TEXT,
        correct_answer   TEXT,
        user_answer      TEXT,
        is_correct       INTEGER,
        time_taken_sec   INTEGER,
        skipped          INTEGER DEFAULT 0,
        subject_id       TEXT,
        topic_id         TEXT,
        subtopic_id      TEXT,
        dimension_id     TEXT,
        concept_expanded INTEGER DEFAULT 0,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS subtopic_scores (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          TEXT DEFAULT 'user_1',
        subject_id       TEXT NOT NULL,
        topic_id         TEXT NOT NULL,
        subtopic_id      TEXT NOT NULL,
        score            REAL DEFAULT 0,
        confidence_level TEXT DEFAULT 'unassessed',
        total_attempts   INTEGER DEFAULT 0,
        correct_count    INTEGER DEFAULT 0,
        last_tested      TIMESTAMP,
        trend            TEXT DEFAULT 'stable',
        updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, subject_id, topic_id, subtopic_id)
    );

    CREATE TABLE IF NOT EXISTS sar_scores (
        user_id          TEXT PRIMARY KEY DEFAULT 'user_1',
        sar              REAL DEFAULT 0.5,
        total_claims     INTEGER DEFAULT 0,
        updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS subject_attestations (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          TEXT DEFAULT 'user_1',
        subject_id       TEXT,
        claimed_level    REAL,
        validation_score REAL,
        effective_level  REAL,
        sar_at_time      REAL,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS study_plan_log (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          TEXT DEFAULT 'user_1',
        plan_date        TEXT,
        plan_json        TEXT,
        generated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS session_summaries (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id              TEXT UNIQUE REFERENCES quiz_sessions(id),
        subject_id              TEXT,
        session_date            TEXT,
        total_questions         INTEGER,
        correct                 INTEGER,
        accuracy_pct            REAL,
        difficulty_attempted    TEXT,
        avg_time_sec            REAL,
        weak_subtopics          TEXT,
        strong_subtopics        TEXT,
        question_type_breakdown TEXT,
        expanded_subtopics      TEXT,
        created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS subtopic_difficulty (
        subtopic_id         TEXT PRIMARY KEY,
        subject_id          TEXT,
        current_difficulty  TEXT DEFAULT 'easy',
        consecutive_good    INTEGER DEFAULT 0,
        consecutive_bad     INTEGER DEFAULT 0,
        total_sessions      INTEGER DEFAULT 0,
        last_updated        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

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
    );

    INSERT OR IGNORE INTO sar_scores (user_id) VALUES ('user_1');

    CREATE INDEX IF NOT EXISTS idx_sa_session ON session_answers(session_id);
    CREATE INDEX IF NOT EXISTS idx_sa_subj_sub ON session_answers(subject_id, subtopic_id);
    CREATE INDEX IF NOT EXISTS idx_qs_end ON quiz_sessions(end_time);
    CREATE INDEX IF NOT EXISTS idx_qs_start ON quiz_sessions(start_time);
    CREATE INDEX IF NOT EXISTS idx_subtopic_scores_lookup ON subtopic_scores(user_id, subject_id);
    """)
    con.commit()
    con.close()
    print(f"Database initialised at {DB_PATH}")


if __name__ == "__main__":
    init_db()
