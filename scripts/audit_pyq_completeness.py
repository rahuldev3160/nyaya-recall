#!/usr/bin/env python3
"""
Audit PYQ completeness per year in pyq_questions table.
Flags years with <95 rows. Exits 1 if any year 2013–2025 fails the threshold.
"""
from __future__ import annotations
import os
import sqlite3
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))
AUDIT_YEARS = range(2013, 2026)
LOW_THRESHOLD = 95
DUPE_THRESHOLD = 100


def check_column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def main() -> int:
    db_path = Path(DB_PATH)
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return 1

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    has_answer_source = check_column_exists(cur, "pyq_questions", "answer_source")
    if not has_answer_source:
        print("NOTE: 'answer_source' column not present yet (ALTER TABLE pending approval). Skipping that check.\n")

    cur.execute("SELECT year, COUNT(*) FROM pyq_questions GROUP BY year ORDER BY year")
    rows = cur.fetchall()
    con.close()

    counts: dict[int, int] = {year: count for year, count in rows}

    print(f"{'Year':<6} {'Questions':<12} {'Status'}")
    print("-" * 36)

    any_low = False
    for year in AUDIT_YEARS:
        count = counts.get(year, 0)
        if count == 0:
            status = "MISSING (0 rows)"
            any_low = True
        elif count < LOW_THRESHOLD:
            status = f"LOW (<{LOW_THRESHOLD})"
            any_low = True
        elif count > DUPE_THRESHOLD:
            status = f"DUPE RISK (>{DUPE_THRESHOLD} — possible {year} duplication)"
        else:
            status = "OK"
        print(f"{year:<6} {count:<12} {status}")

    years_outside_range = {y: c for y, c in counts.items() if y not in AUDIT_YEARS}
    if years_outside_range:
        print("\nYears outside 2013–2025 audit range:")
        for year, count in sorted(years_outside_range.items()):
            print(f"  {year}: {count} rows")

    print()
    if any_low:
        print("RESULT: FAIL — one or more years below threshold or missing.")
        return 1

    print("RESULT: PASS — all years 2013–2025 meet the 95-question threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
