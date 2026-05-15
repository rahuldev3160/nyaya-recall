"""
Backfill weak_subtopics and strong_subtopics in session_summaries for historical sessions
where both fields were computed as [] (before subtopic repair fixed session_answers).

Usage:
    python3 scripts/backfill_session_summaries.py           # apply updates
    python3 scripts/backfill_session_summaries.py --dry-run # preview only
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = os.getenv("DB_PATH", "data/upsc.db")

WEAK_THRESHOLD = 45.0   # accuracy % — matches score_engine.py
STRONG_THRESHOLD = 75.0


def backfill(dry_run: bool = False) -> None:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # Find sessions where both arrays were stored as empty (the broken historical ones)
    stale = con.execute(
        """
        SELECT session_id, subject_id
        FROM session_summaries
        WHERE weak_subtopics = '[]' AND strong_subtopics = '[]'
        """
    ).fetchall()

    if not stale:
        print("No sessions with empty weak/strong arrays found — nothing to backfill.")
        con.close()
        return

    print(f"Found {len(stale)} session(s) with empty weak/strong arrays.\n")

    updated = 0
    skipped = 0

    for row in stale:
        session_id = row["session_id"]
        subject_id = row["subject_id"]

        # Group session_answers by subtopic_id (skip blank subtopic_ids)
        answers = con.execute(
            """
            SELECT subtopic_id,
                   SUM(is_correct) AS correct,
                   COUNT(*)        AS total
            FROM session_answers
            WHERE session_id = ?
              AND subtopic_id IS NOT NULL
              AND subtopic_id != ''
            GROUP BY subtopic_id
            """,
            (session_id,),
        ).fetchall()

        if not answers:
            print(f"  {session_id} ({subject_id}): SKIP — no repaired subtopic data in answers")
            skipped += 1
            continue

        weak = []
        strong = []
        for a in answers:
            accuracy_pct = (a["correct"] / a["total"]) * 100 if a["total"] > 0 else 0.0
            if accuracy_pct < WEAK_THRESHOLD:
                weak.append(a["subtopic_id"])
            elif accuracy_pct >= STRONG_THRESHOLD:
                strong.append(a["subtopic_id"])

        print(
            f"  {session_id} ({subject_id}): "
            f"weak={weak} strong={strong}"
            + (" [DRY RUN]" if dry_run else "")
        )

        if not dry_run:
            con.execute(
                "UPDATE session_summaries SET weak_subtopics = ?, strong_subtopics = ? WHERE session_id = ?",
                (json.dumps(weak), json.dumps(strong), session_id),
            )
        updated += 1

    if not dry_run:
        con.commit()
        print(f"\nUpdated {updated} session(s), skipped {skipped}.")
        print("Run `python3 scripts/batch_analyse.py` to refresh persistent-weakness detection.")
    else:
        print(f"\n[DRY RUN] Would update {updated} session(s), skip {skipped}. No changes written.")

    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill session_summaries weak/strong subtopics")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()
    backfill(dry_run=args.dry_run)
