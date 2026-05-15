"""
One-time backfill: populate topic_id from syllabus.json for historical rows.

Updates:
  - session_answers: rows where topic_id IS NULL and subtopic_id + subject_id are set
  - subtopic_scores: rows where topic_id IS NULL and subtopic_id + subject_id are set

Usage:
    python3 scripts/backfill_topic_ids.py
    python3 scripts/backfill_topic_ids.py --dry-run
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = os.getenv("DB_PATH", "data/upsc.db")
SYLLABUS_PATH = Path(__file__).parent.parent / "data" / "syllabus.json"
_ALIAS = {"history": "history_amac"}


def _build_lookup() -> dict[tuple[str, str], str]:
    """Returns {(subject_id, subtopic_id): topic_id} from syllabus.json."""
    lookup: dict[tuple[str, str], str] = {}
    syllabus = json.loads(SYLLABUS_PATH.read_text())
    for subj in syllabus.get("subjects", []):
        sid = subj["id"]
        for topic in subj.get("topics", []):
            tid = topic["id"]
            for st in topic.get("subtopics", []):
                lookup[(sid, st["id"])] = tid
    return lookup


def backfill(dry_run: bool = False) -> None:
    lookup = _build_lookup()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # --- session_answers ---
    rows = con.execute(
        "SELECT id, subject_id, subtopic_id FROM session_answers "
        "WHERE topic_id IS NULL AND subject_id IS NOT NULL AND subtopic_id IS NOT NULL"
    ).fetchall()

    sa_updated = 0
    sa_skipped = 0
    for row in rows:
        sid = _ALIAS.get(row["subject_id"], row["subject_id"])
        topic_id = lookup.get((sid, row["subtopic_id"]))
        if not topic_id:
            sa_skipped += 1
            continue
        if not dry_run:
            con.execute(
                "UPDATE session_answers SET topic_id=? WHERE id=?",
                (topic_id, row["id"]),
            )
        sa_updated += 1

    # --- subtopic_scores ---
    rows = con.execute(
        "SELECT id, subject_id, subtopic_id, total_attempts, correct_count, last_tested "
        "FROM subtopic_scores "
        "WHERE (topic_id IS NULL OR topic_id = '') AND subject_id IS NOT NULL AND subtopic_id IS NOT NULL"
    ).fetchall()

    ss_updated = 0
    ss_merged = 0
    ss_skipped = 0
    for row in rows:
        sid = _ALIAS.get(row["subject_id"], row["subject_id"])
        topic_id = lookup.get((sid, row["subtopic_id"]))
        if not topic_id:
            ss_skipped += 1
            continue

        # Check for conflict: existing row with the same (user_1, subject_id, topic_id, subtopic_id)
        conflict = con.execute(
            "SELECT id, total_attempts, correct_count, last_tested FROM subtopic_scores "
            "WHERE user_id='user_1' AND subject_id=? AND topic_id=? AND subtopic_id=?",
            (row["subject_id"], topic_id, row["subtopic_id"]),
        ).fetchone()

        if conflict:
            # Merge: accumulate attempts+correct, recompute score, keep newer last_tested
            new_attempts = (row["total_attempts"] or 0) + (conflict["total_attempts"] or 0)
            new_correct = (row["correct_count"] or 0) + (conflict["correct_count"] or 0)
            new_score = (new_correct / max(new_attempts, 1)) * 100
            last_tested = max(
                row["last_tested"] or "",
                conflict["last_tested"] or "",
            ) or None
            if not dry_run:
                con.execute(
                    "UPDATE subtopic_scores SET total_attempts=?, correct_count=?, score=?, last_tested=? "
                    "WHERE id=?",
                    (new_attempts, new_correct, new_score, last_tested, conflict["id"]),
                )
                con.execute("DELETE FROM subtopic_scores WHERE id=?", (row["id"],))
            ss_merged += 1
        else:
            if not dry_run:
                con.execute(
                    "UPDATE subtopic_scores SET topic_id=? WHERE id=?",
                    (topic_id, row["id"]),
                )
            ss_updated += 1

    if not dry_run:
        con.commit()
    con.close()

    mode = "[DRY RUN] " if dry_run else ""
    print(f"{mode}session_answers: {sa_updated} updated, {sa_skipped} subtopics not in syllabus")
    print(f"{mode}subtopic_scores: {ss_updated} updated, {ss_merged} merged (deduped), {ss_skipped} not in syllabus")
    if dry_run:
        print("Re-run without --dry-run to apply changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    backfill(dry_run=args.dry_run)
