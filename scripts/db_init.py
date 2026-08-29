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
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, question_hash)
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

    -- B-4 fix: surrogate id PK, user_id UNIQUE (was bare user_id PRIMARY KEY --
    -- broken for multi-user, see .knowledge/plans/PLAN-010.md). Only affects
    -- fresh installs; scripts/fix_sar_scores_pk.py migrates an existing DB.
    CREATE TABLE IF NOT EXISTS sar_scores (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          TEXT NOT NULL UNIQUE DEFAULT 'user_1',
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

    -- FEATURE-027 Phase 4: per-dimension accuracy tracking
    CREATE TABLE IF NOT EXISTS subtopic_dimension_scores (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         TEXT DEFAULT 'user_1',
        subject_id      TEXT NOT NULL,
        subtopic_id     TEXT NOT NULL,
        dimension_id    TEXT NOT NULL,
        attempts        INTEGER DEFAULT 0,
        correct_count   INTEGER DEFAULT 0,
        score           REAL DEFAULT 0.0,
        last_tested     TIMESTAMP,
        UNIQUE(user_id, subject_id, subtopic_id, dimension_id)
    );

    -- ISSUE-017 Phase 1: per-question note storage (replaces single-blob session_user_notes for new sessions)
    CREATE TABLE IF NOT EXISTS question_notes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         TEXT    NOT NULL DEFAULT 'user_1',
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

    -- ISSUE-017 Phase 1: qualitative content feedback on questions / explanations / notes sections
    CREATE TABLE IF NOT EXISTS content_feedback (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         TEXT    NOT NULL DEFAULT 'user_1',
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

    CREATE INDEX IF NOT EXISTS idx_sa_session ON session_answers(session_id);
    CREATE INDEX IF NOT EXISTS idx_sa_subj_sub ON session_answers(subject_id, subtopic_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_session_qhash ON session_answers(session_id, question_hash);
    CREATE INDEX IF NOT EXISTS idx_qs_end ON quiz_sessions(end_time);
    CREATE INDEX IF NOT EXISTS idx_qs_start ON quiz_sessions(start_time);
    CREATE INDEX IF NOT EXISTS idx_subtopic_scores_lookup ON subtopic_scores(user_id, subject_id);
    CREATE INDEX IF NOT EXISTS idx_dim_scores_lookup ON subtopic_dimension_scores(user_id, subject_id, subtopic_id);
    """)
    con.commit()
    con.close()
    print(f"Database initialised at {DB_PATH}")


if __name__ == "__main__":
    init_db()
