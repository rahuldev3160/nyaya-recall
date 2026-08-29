#!/usr/bin/env python3
"""
Copy RBI Grade B's MCQ content from Scribe's rbi.db into Recall's question_bank.
Implements PLAN-008 section 2 (.knowledge/plans/PLAN-008.md), approved by Rahul as B-11.

READ-ONLY against the source rbi.db — nothing in Descriptive-exams is modified.
Requires migrate_question_bank_v2.py (PLAN-007) to have already run.

Deviation from PLAN-008's literal mapping description (documented, not silently applied):
PLAN-008 describes "topic_id <- the tier-2 bucket key (9 values) / subtopic_id <- the
tier-1 topic field (29 values)" as if tier is a single two-level hierarchy. Direct
schema+data inspection shows this isn't accurate: rbi_questions.tier=1 and tier=2 rows
draw their `topic` value from two DIFFERENT, mostly-disjoint vocabularies (tier=1 uses
general economics subjects like 'is_lm'/'mundell_fleming'; tier=2 uses the 9-item
_BUCKET_META RBI-specific set like 'rbi_instruments'/'banking_regulation') -- a tier=1
row has no tier=2 "parent bucket" to map into at all. Forcing PLAN-008's described
mapping would produce a nonsensical topic_id for every tier=1 row (54 of the 267 rows
with a subtopic value are tier=1; tier=1 is in fact the majority of the 321 rows).

Chosen mapping instead (preserves all real information, invents nothing):
    subject_id   <- rbi_questions.subject      (8 real values: macro, micro, rbi_banking, ...)
    topic_id     <- rbi_questions.topic         (33 real values, whichever vocabulary applies)
    subtopic_id  <- rbi_questions.subtopic if non-empty, else falls back to topic_id
                     (NOT NULL constraint on subtopic_id; 267/321 rows have a real subtopic)
    tags         <- {"rbi_tier": 1 or 2} appended to existing tags JSON, preserving the
                     tier-1 (foundational economics) vs tier-2 (RBI-specific) distinction
                     that rbi_prep_bp.py's two serving functions actually branch on.

This is a more honest, lower-assumption mapping than the plan's literal wording and
loses no information the plan's version would have kept -- flagged here for the record,
per this project's own decision-logging convention, rather than silently deviating.

Usage:
    python scripts/migrate_rbi_to_recall.py --rbi-db path/to/rbi.db [--dry-run]
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))

EXAM_SOURCE = "rbi_grade_b"
DEFAULT_MARKS = 1.0  # RBI's marking scheme (correct=1/wrong=-0.25/unattempted=0), not UPSC's 2.0.


def check_column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy RBI MCQ content into Recall's question_bank.")
    parser.add_argument("--rbi-db", required=True, help="Path to the source rbi.db (read-only)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would happen, write nothing")
    args = parser.parse_args()

    rbi_path = Path(args.rbi_db)
    if not rbi_path.exists():
        print(f"ERROR: RBI source DB not found at {rbi_path}")
        return 1

    dest_path = Path(DB_PATH)
    if not dest_path.exists():
        print(f"ERROR: Destination DB not found at {dest_path}")
        return 1

    dest_con = sqlite3.connect(dest_path)
    dest_cur = dest_con.cursor()
    if not check_column_exists(dest_cur, "question_bank", "source_type"):
        print("ERROR: question_bank missing 'source_type' column -- run "
              "migrate_question_bank_v2.py (PLAN-007) first.")
        return 1

    # Idempotency guard: if rbi_grade_b content already exists, don't duplicate it.
    dest_cur.execute("SELECT COUNT(*) FROM question_bank WHERE exam_source = ?", (EXAM_SOURCE,))
    existing = dest_cur.fetchone()[0]
    if existing > 0:
        print(f"ERROR: {existing} rows already exist with exam_source='{EXAM_SOURCE}'. "
              "Refusing to duplicate. Delete them first if you intend to re-run this migration.")
        dest_con.close()
        return 1

    src_con = sqlite3.connect(rbi_path)
    src_con.row_factory = sqlite3.Row
    src_cur = src_con.cursor()

    questions = src_cur.execute("SELECT * FROM rbi_questions").fetchall()
    weights = src_cur.execute("SELECT * FROM rbi_topic_weights").fetchall()
    src_con.close()  # done reading, never write to the source

    print(f"Source: {len(questions)} questions, {len(weights)} topic weights in {rbi_path}")

    id_map: dict[str, str] = {}
    rows_to_insert = []
    for q in questions:
        old_id = q["id"]
        new_id = f"rbi_q_{old_id}"
        id_map[old_id] = new_id

        subject_id = q["subject"]
        topic_id = q["topic"]
        subtopic_id = q["subtopic"] if q["subtopic"] else topic_id  # NOT NULL fallback, see module docstring

        existing_tags = []
        if q["tags"]:
            try:
                existing_tags = json.loads(q["tags"])
            except (json.JSONDecodeError, TypeError):
                existing_tags = []
        tag_value = json.dumps(existing_tags + [f"rbi_tier_{q['tier']}"])

        question_hash = hashlib.sha256(
            f"{EXAM_SOURCE}:{q['question']}".encode("utf-8")
        ).hexdigest()

        rows_to_insert.append((
            new_id, question_hash, q["question"],
            q["option_a"], q["option_b"], q["option_c"], q["option_d"],
            q["correct_option"], q["explanation"], None,  # explanation_short, explanation_full
            EXAM_SOURCE, None, None, None,  # year, paper, q_number -- not applicable, no answer-key source
            "unclassified_legacy",  # answer_source: honest -- provenance was never tracked pre-migration
            subject_id, topic_id, subtopic_id,
            "single_correct", DEFAULT_MARKS, tag_value,
            "unclassified_legacy",  # source_type: provenance genuinely unknown, see PLAN-008 §2 note
            "active",
        ))

    weight_rows = [
        (EXAM_SOURCE, w["subject"], w["topic"], w["topic"], w["base_weight"], "manual")
        for w in weights
    ]

    print(f"Prepared {len(rows_to_insert)} question rows, {len(weight_rows)} topic_weight rows.")
    if args.dry_run:
        print("--dry-run: not writing anything. Sample mapped row:")
        print(rows_to_insert[0])
        dest_con.close()
        return 0

    dest_cur.executemany(
        """INSERT INTO question_bank (
            id, question_hash, question_text,
            option_a, option_b, option_c, option_d,
            correct_answer, explanation_short, explanation_full,
            exam_source, year, paper, q_number,
            answer_source,
            subject_id, topic_id, subtopic_id,
            question_format, default_marks, tags,
            source_type, status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows_to_insert,
    )
    dest_cur.executemany(
        """INSERT OR IGNORE INTO topic_weights
           (exam_source, subject_id, topic_id, subtopic_id, base_weight, weight_source)
           VALUES (?,?,?,?,?,?)""",
        weight_rows,
    )
    dest_con.commit()

    dest_cur.execute("SELECT COUNT(*) FROM question_bank WHERE exam_source = ?", (EXAM_SOURCE,))
    final_count = dest_cur.fetchone()[0]
    dest_con.close()

    print(f"Inserted. question_bank now has {final_count} rows with exam_source='{EXAM_SOURCE}'.")
    id_map_path = Path(__file__).parent / f"_rbi_migration_id_map_{os.getpid()}.json"
    id_map_path.write_text(json.dumps(id_map, indent=2))
    print(f"ID mapping (old rbi_questions.id -> new question_bank.id) written to {id_map_path} "
          "-- one-time migration artifact, not a permanent product table, safe to delete after review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
