#!/usr/bin/env python3
"""
Schema migration: generalize question_bank for multi-exam, multi-source, multi-format
MCQ content. Implements PLAN-007 (.knowledge/plans/PLAN-007.md), approved by Rahul as B-11.

Adds 8 new columns to question_bank (source_type, source_ref, source_document_id,
generation_batch_id, question_format, default_marks, retired_at, superseded_by) plus a
9th column (status) folded in per PLAN-009 section 1.C, and 3 new tables
(source_documents, generation_batches, topic_weights). Backfills existing rows'
source_type per PLAN-007's exact UPDATE statements.

Idempotent: safe to re-run. Checks column/table existence before adding anything.

Usage:
    python scripts/migrate_question_bank_v2.py
"""
from __future__ import annotations
import os
import sqlite3
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))


def check_column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def check_table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


NEW_COLUMNS = [
    ("source_type", "TEXT NOT NULL DEFAULT 'unclassified_legacy'"),
    ("source_ref", "TEXT"),
    ("source_document_id", "TEXT REFERENCES source_documents(id)"),
    ("generation_batch_id", "TEXT REFERENCES generation_batches(id)"),
    ("question_format", "TEXT NOT NULL DEFAULT 'single_correct'"),
    ("default_marks", "REAL NOT NULL DEFAULT 2.0"),
    ("retired_at", "TEXT"),
    ("superseded_by", "TEXT REFERENCES question_bank(id)"),
    # Folded in per PLAN-009 §1.C: 'draft' | 'active' | 'retired'. Default 'active' for
    # backfilled legacy rows so existing serving behavior (which assumes every row is
    # servable) does not change.
    ("status", "TEXT NOT NULL DEFAULT 'active'"),
]

NEW_TABLES = """
CREATE TABLE IF NOT EXISTS source_documents (
    id             TEXT PRIMARY KEY,
    doc_type       TEXT NOT NULL,
    title          TEXT NOT NULL,
    source_url     TEXT NOT NULL,
    publish_date   TEXT,
    ingested_at    TEXT DEFAULT (datetime('now')),
    exam_source    TEXT NOT NULL,
    raw_text_ref   TEXT,
    content_hash   TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS generation_batches (
    id                TEXT PRIMARY KEY,
    batch_date        TEXT NOT NULL,
    exam_source       TEXT NOT NULL,
    source_month      TEXT,
    model             TEXT NOT NULL,
    prompt_version    TEXT NOT NULL,
    review_status     TEXT NOT NULL DEFAULT 'draft',
    reviewed_by       TEXT,
    question_count    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS topic_weights (
    exam_source   TEXT NOT NULL,
    subject_id    TEXT NOT NULL,
    topic_id      TEXT NOT NULL,
    subtopic_id   TEXT NOT NULL,
    base_weight   REAL NOT NULL,
    weight_source TEXT NOT NULL DEFAULT 'manual',
    PRIMARY KEY (exam_source, subject_id, topic_id, subtopic_id)
);
"""

# PLAN-007's exact backfill statements for existing rows.
BACKFILL_STATEMENTS = [
    (
        "UPDATE question_bank SET source_type = 'third_party_bank', "
        "source_ref = '{\"vendor\":\"vision_ias\"}' WHERE exam_source = 'vision_ias' "
        "AND source_type = 'unclassified_legacy'"
    ),
    (
        "UPDATE question_bank SET source_type = 'similar_exam_pyq' "
        "WHERE exam_source IN ('cds', 'nda', 'capf', 'cisf') AND answer_source != 'ai_inferred' "
        "AND source_type = 'unclassified_legacy'"
    ),
    (
        "UPDATE question_bank SET source_type = 'ai_gap_fill' "
        "WHERE exam_source IN ('cds', 'nda', 'capf', 'cisf') AND answer_source = 'ai_inferred' "
        "AND source_type = 'unclassified_legacy'"
    ),
]


def main() -> int:
    db_path = Path(DB_PATH)
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return 1

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    if not check_table_exists(cur, "question_bank"):
        print("ERROR: question_bank table does not exist. Run the app once first "
              "(_ensure_question_bank_tables) before this migration.")
        con.close()
        return 1

    print(f"Migrating {db_path} ...")

    added = []
    skipped = []
    for col_name, col_def in NEW_COLUMNS:
        if check_column_exists(cur, "question_bank", col_name):
            skipped.append(col_name)
            continue
        cur.execute(f"ALTER TABLE question_bank ADD COLUMN {col_name} {col_def}")
        added.append(col_name)
    con.commit()
    print(f"  Columns added: {added or '(none)'}")
    print(f"  Columns already present, skipped: {skipped or '(none)'}")

    cur.executescript(NEW_TABLES)
    con.commit()
    print("  New tables ensured: source_documents, generation_batches, topic_weights")

    total_backfilled = 0
    for stmt in BACKFILL_STATEMENTS:
        cur.execute(stmt)
        total_backfilled += cur.rowcount
    con.commit()
    print(f"  Backfill rows updated: {total_backfilled}")

    cur.execute(
        "SELECT source_type, COUNT(*) FROM question_bank GROUP BY source_type ORDER BY 2 DESC"
    )
    print("  source_type distribution after backfill:")
    for source_type, count in cur.fetchall():
        print(f"    {source_type}: {count}")

    con.close()
    print("Migration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
