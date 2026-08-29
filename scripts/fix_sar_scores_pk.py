"""One-off migration (B-4): fix sar_scores' broken multi-user primary key.

DO NOT run this against data/upsc.db without Rahul's explicit approval (B-4 is a
tracked approval gate — see .knowledge/INDEX.md / SPRINT_BOARD.md). This script
is meant to be reviewed, then run once, manually:

    python scripts/fix_sar_scores_pk.py [path/to/db]

Root cause (see .knowledge/plans/PLAN-010.md for the full writeup):
- `sar_scores` used bare `user_id TEXT PRIMARY KEY`. Only 'user_1' is ever seeded
  (scripts/db_init.py). No code path ever INSERTs a row for any other user_id.
- scripts/self_attestation.py's `_update_sar()` / `record_attestation()` write via
  plain UPDATE ... WHERE user_id=?, which silently affects 0 rows for any user_id
  that has no existing row. A second real user's SAR score is computed correctly
  in-memory but never persisted -- not a crash, a silent no-op.
- Fix has two parts: (1) this schema migration (surrogate `id` PK, `user_id`
  UNIQUE -- matches the target already drafted in scripts/migrate_to_postgres.py's
  Postgres DDL), and (2) the upsert fix in scripts/self_attestation.py (same PR).

This migration is idempotent -- safe to run twice, no-ops if already applied.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def already_migrated(con: sqlite3.Connection) -> bool:
    cols = {row[1] for row in con.execute("PRAGMA table_info(sar_scores)").fetchall()}
    return "id" in cols


def migrate(db_path: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        if already_migrated(con):
            print(f"{db_path}: sar_scores already has a surrogate id PK, nothing to do.")
            return

        con.execute("PRAGMA foreign_keys=OFF")
        with con:
            con.execute("ALTER TABLE sar_scores RENAME TO sar_scores_old")
            con.execute("""
                CREATE TABLE sar_scores (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      TEXT NOT NULL UNIQUE,
                    sar          REAL DEFAULT 0.5,
                    total_claims INTEGER DEFAULT 0,
                    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("""
                INSERT INTO sar_scores (user_id, sar, total_claims, updated_at)
                SELECT user_id, sar, total_claims, updated_at FROM sar_scores_old
            """)
            con.execute("DROP TABLE sar_scores_old")

        before_after = con.execute("SELECT COUNT(*) FROM sar_scores").fetchone()[0]
        print(f"{db_path}: migrated sar_scores to surrogate PK, {before_after} row(s) preserved.")
    finally:
        con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db_path", nargs="?", default=os.getenv("DB_PATH", "data/upsc.db"))
    args = parser.parse_args()
    migrate(args.db_path)
