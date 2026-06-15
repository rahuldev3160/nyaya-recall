#!/usr/bin/env python3
"""
Fix pyq_questions rows where year=0 or year IS NULL.
Interactive: previews affected rows, prompts for target year, then updates.
"""
from __future__ import annotations
import os
import sqlite3
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))


def main() -> int:
    db_path = Path(DB_PATH)
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return 1

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute("""
        SELECT id, year, question_text
        FROM pyq_questions
        WHERE year = 0 OR year IS NULL
        ORDER BY id
    """)
    bad_rows = cur.fetchall()

    if not bad_rows:
        print("No rows with year=0 or year=NULL found. Nothing to fix.")
        con.close()
        return 0

    print(f"{'ID':<8} {'Year':<8} {'Question (first 80 chars)'}")
    print("-" * 80)
    for row_id, year, text in bad_rows:
        year_display = str(year) if year is not None else "NULL"
        snippet = (text or "")[:80].replace("\n", " ")
        print(f"{row_id:<8} {year_display:<8} {snippet}")

    print()

    cur.execute("""
        SELECT COALESCE(year, 'NULL') as y_val, COUNT(*)
        FROM pyq_questions
        WHERE year = 0 OR year IS NULL
        GROUP BY y_val
    """)
    print("Count by year value:")
    for y_val, count in cur.fetchall():
        print(f"  year={y_val}: {count} rows")

    print()
    answer = input(f"Found {len(bad_rows)} rows with year=0/NULL. Continue? (y/N) ").strip().lower()
    if answer != "y":
        print("Aborted. No changes made.")
        con.close()
        return 0

    target_year_str = input("Enter target year to assign (e.g. 2014): ").strip()
    if not target_year_str.isdigit():
        print("ERROR: Target year must be a 4-digit integer. Aborted.")
        con.close()
        return 1

    target_year = int(target_year_str)
    if not (2009 <= target_year <= 2025):
        confirm = input(f"WARNING: {target_year} is outside the expected 2009–2025 range. Proceed anyway? (y/N) ").strip().lower()
        if confirm != "y":
            print("Aborted. No changes made.")
            con.close()
            return 0

    cur.execute("""
        UPDATE pyq_questions
        SET year = ?
        WHERE year = 0 OR year IS NULL
    """, (target_year,))
    updated = cur.rowcount
    con.commit()
    con.close()

    print(f"Updated {updated} rows → year={target_year}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
