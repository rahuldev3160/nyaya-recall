#!/usr/bin/env python3
"""
Import official UPSC answer keys from a CSV and update pyq_questions.

Expected CSV columns: year, q_number, correct_answer, cancelled, dispute_note

Requires q_number and answer_source columns in pyq_questions.
Run ALTER TABLE (needs Rahul's approval) before using this script.

Usage:
    python import_answer_keys.py --input path/to/answer_key.csv
"""
from __future__ import annotations
import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))

REQUIRED_COLUMNS = {"year", "q_number", "correct_answer", "cancelled", "dispute_note"}


def check_column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def main() -> int:
    parser = argparse.ArgumentParser(description="Import UPSC official answer keys into pyq_questions.")
    parser.add_argument("--input", required=True, help="Path to CSV file with answer keys")
    args = parser.parse_args()

    csv_path = Path(args.input)
    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        return 1

    db_path = Path(DB_PATH)
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return 1

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    missing_db_cols = []
    for col in ("q_number", "answer_source", "answer_disputed", "dispute_note"):
        if not check_column_exists(cur, "pyq_questions", col):
            missing_db_cols.append(col)

    if "q_number" in missing_db_cols:
        print(
            "ERROR: 'q_number' column not found in pyq_questions — "
            "run ALTER TABLE first and re-run this script.\n"
            "Other missing columns: " + (", ".join(c for c in missing_db_cols if c != "q_number") or "none")
        )
        con.close()
        return 1

    if missing_db_cols:
        print(
            f"WARNING: Some columns are missing and will be skipped: {', '.join(missing_db_cols)}\n"
            "Run ALTER TABLE for those columns and re-run to import them."
        )

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("ERROR: CSV file is empty or has no header row.")
            con.close()
            return 1

        csv_cols = set(reader.fieldnames)
        missing_csv_cols = REQUIRED_COLUMNS - csv_cols
        if missing_csv_cols:
            print(f"ERROR: CSV is missing required columns: {', '.join(sorted(missing_csv_cols))}")
            con.close()
            return 1

        rows = list(reader)

    if not rows:
        print("ERROR: CSV file has a header but no data rows.")
        con.close()
        return 1

    matched = 0
    unmatched: list[tuple[str, str]] = []

    for row in rows:
        try:
            year = int(row["year"])
            q_number = int(row["q_number"])
        except ValueError:
            print(f"  SKIP: Invalid year/q_number in row: {row}")
            continue

        correct_answer = (row.get("correct_answer") or "").strip() or None
        cancelled = int(row.get("cancelled") or 0)
        dispute_note = (row.get("dispute_note") or "").strip() or None

        cur.execute(
            "SELECT id FROM pyq_questions WHERE year = ? AND q_number = ?",
            (year, q_number),
        )
        existing = cur.fetchone()

        if not existing:
            unmatched.append((str(year), str(q_number)))
            continue

        set_clauses = ["correct_answer = ?"]
        params: list = [correct_answer]

        if "answer_source" not in missing_db_cols:
            set_clauses.append("answer_source = ?")
            params.append("upsc_official_key")

        if "answer_disputed" not in missing_db_cols:
            set_clauses.append("answer_disputed = CASE WHEN ? = 1 THEN 1 ELSE 0 END")
            params.append(cancelled)

        if "dispute_note" not in missing_db_cols:
            set_clauses.append("dispute_note = ?")
            params.append(dispute_note)

        params.extend([year, q_number])
        cur.execute(
            f"UPDATE pyq_questions SET {', '.join(set_clauses)} WHERE year = ? AND q_number = ?",
            params,
        )
        matched += 1

    con.commit()
    con.close()

    print(f"\nSummary:")
    print(f"  Matched and updated : {matched}")
    print(f"  Unmatched           : {len(unmatched)}")
    if unmatched:
        print("\nUnmatched (year, q_number) pairs:")
        for year, qnum in unmatched:
            print(f"  year={year}, q_number={qnum}")

    return 0 if not unmatched else 2


if __name__ == "__main__":
    sys.exit(main())
