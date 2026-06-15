#!/usr/bin/env python3
"""
Pre-generate structured concept explanations for PYQ questions using Haiku Batch API.
Explanations are stored in `question_explanations` table and served zero-cost at runtime.

Eligible questions: answer_source IN (community_validated, community_consensus, upsc_official_key)
                    AND correct_answer IS NOT NULL
                    AND no explanation exists yet

Cost estimate: ~$0.001 per question with Haiku Batch (50% off standard)
               ~$0.97 for all 1,000 community_validated questions

Usage:
    cd scripts
    python generate_pyq_explanations.py              # all eligible questions
    python generate_pyq_explanations.py --subject polity
    python generate_pyq_explanations.py --year 2024
    python generate_pyq_explanations.py --limit 50   # small test batch
    python generate_pyq_explanations.py --poll        # poll an in-flight batch
    python generate_pyq_explanations.py --apply       # apply results from cache to DB
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

DB_PATH    = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))
CACHE_DIR  = Path(__file__).parent.parent / "cache" / "pyq_explanation_results"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "pyq_explanation.txt"
BATCH_ID_FILE = Path(__file__).parent.parent / "data" / "pyq_explanations_batch.txt"

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 600

VALID_SOURCES = ("community_validated", "community_consensus", "upsc_official_key")


def get_conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def ensure_table(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS question_explanations (
            question_id         INTEGER PRIMARY KEY REFERENCES pyq_questions(id),
            concept_tested      TEXT NOT NULL,
            correct_explanation TEXT NOT NULL,
            option_a_note       TEXT,
            option_b_note       TEXT,
            option_c_note       TEXT,
            option_d_note       TEXT,
            memory_hook         TEXT,
            model_used          TEXT NOT NULL DEFAULT 'claude-haiku-4-5-20251001',
            generated_at        TEXT NOT NULL DEFAULT (datetime('now')),
            version             INTEGER NOT NULL DEFAULT 1
        )
    """)
    con.commit()


def load_pending(
    con: sqlite3.Connection,
    subject: str | None = None,
    year: int | None = None,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    params: list = list(VALID_SOURCES)
    placeholders = ",".join("?" * len(VALID_SOURCES))
    where = f"p.answer_source IN ({placeholders}) AND p.correct_answer IS NOT NULL AND e.question_id IS NULL"
    if subject:
        where += " AND p.subject_id = ?"
        params.append(subject)
    if year:
        where += " AND p.year = ?"
        params.append(year)
    sql = f"""
        SELECT p.id, p.year, p.question_text, p.correct_answer,
               p.option_a, p.option_b, p.option_c, p.option_d,
               p.subject_id
        FROM pyq_questions p
        LEFT JOIN question_explanations e ON p.id = e.question_id
        WHERE {where}
        ORDER BY p.year DESC, p.id
    """
    if limit:
        sql += f" LIMIT {limit}"
    return con.execute(sql, params).fetchall()


def build_prompt(row: sqlite3.Row, template: str) -> str:
    option_map = {"a": row["option_a"], "b": row["option_b"], "c": row["option_c"], "d": row["option_d"]}
    correct_key = (row["correct_answer"] or "").strip().lower()
    correct_text = option_map.get(correct_key, "")
    return (
        template
        .replace("{{question_text}}", row["question_text"] or "")
        .replace("{{option_a}}", row["option_a"] or "")
        .replace("{{option_b}}", row["option_b"] or "")
        .replace("{{option_c}}", row["option_c"] or "")
        .replace("{{option_d}}", row["option_d"] or "")
        .replace("{{correct_answer_letter}}", correct_key.upper())
        .replace("{{correct_answer_text}}", correct_text)
        .replace("{{subject_id}}", row["subject_id"] or "")
        .replace("{{year}}", str(row["year"]))
    )


def submit_batch(rows: list[sqlite3.Row], template: str) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    requests = [
        {
            "custom_id": str(row["id"]),
            "params": {
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "messages": [{"role": "user", "content": build_prompt(row, template)}],
            },
        }
        for row in rows
    ]
    batch = client.messages.batches.create(requests=requests)
    batch_id = batch.id
    BATCH_ID_FILE.write_text(batch_id)
    print(f"Batch submitted: {batch_id}  ({len(rows)} requests)")
    print(f"Batch ID saved to: {BATCH_ID_FILE}")
    return batch_id


def poll_batch(batch_id: str) -> bool:
    """Returns True when the batch is ended (succeeded or errored)."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        status = batch.processing_status
        counts = batch.request_counts
        print(f"  Status: {status} | processing={counts.processing} errored={counts.errored} succeeded={counts.succeeded}")
        if status == "ended":
            return True
        time.sleep(30)


def stream_results(batch_id: str) -> None:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_file = CACHE_DIR / f"{batch_id}.jsonl"
    with out_file.open("w") as f:
        for result in client.messages.batches.results(batch_id):
            f.write(result.model_dump_json() + "\n")
    print(f"Results saved to: {out_file}")


def apply_results(batch_id: str) -> None:
    result_file = CACHE_DIR / f"{batch_id}.jsonl"
    if not result_file.exists():
        print(f"ERROR: Results file not found: {result_file}")
        print("Run with --poll first to download results.")
        sys.exit(1)

    con = get_conn()
    ensure_table(con)

    inserted = skipped = errors = 0
    with result_file.open() as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                errors += 1
                continue

            question_id = int(entry.get("custom_id", 0))
            if not question_id:
                errors += 1
                continue

            result_type = entry.get("result", {}).get("type")
            if result_type != "succeeded":
                print(f"  SKIP q_id={question_id}: result_type={result_type}")
                skipped += 1
                continue

            content_blocks = entry.get("result", {}).get("message", {}).get("content", [])
            raw_text = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    raw_text = block["text"]
                    break

            # Strip markdown fences if model added them
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
            raw_text = re.sub(r"\s*```$", "", raw_text)

            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                print(f"  PARSE ERROR q_id={question_id}: {raw_text[:80]}")
                errors += 1
                continue

            try:
                con.execute(
                    """
                    INSERT OR IGNORE INTO question_explanations
                        (question_id, concept_tested, correct_explanation,
                         option_a_note, option_b_note, option_c_note, option_d_note,
                         memory_hook, model_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        question_id,
                        data.get("concept_tested", ""),
                        data.get("correct_explanation", ""),
                        data.get("option_a_note"),
                        data.get("option_b_note"),
                        data.get("option_c_note"),
                        data.get("option_d_note"),
                        data.get("memory_hook"),
                        MODEL,
                    ),
                )
                inserted += 1
            except sqlite3.Error as e:
                print(f"  DB ERROR q_id={question_id}: {e}")
                errors += 1

    con.commit()
    con.close()
    print(f"\nDone — inserted={inserted} skipped={skipped} errors={errors}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PYQ concept explanations via Haiku Batch API.")
    parser.add_argument("--subject", help="Filter by subject_id (e.g. polity)")
    parser.add_argument("--year",    type=int, help="Filter by year (e.g. 2024)")
    parser.add_argument("--limit",   type=int, help="Max questions to process (for testing)")
    parser.add_argument("--poll",    action="store_true", help="Poll in-flight batch and download results")
    parser.add_argument("--apply",   action="store_true", help="Apply cached results to DB (no API call)")
    args = parser.parse_args()

    if args.poll or args.apply:
        if not BATCH_ID_FILE.exists():
            print("ERROR: No batch ID file found. Run without --poll/--apply first.")
            return 1
        batch_id = BATCH_ID_FILE.read_text().strip()
        if args.poll:
            poll_batch(batch_id)
            stream_results(batch_id)
        apply_results(batch_id)
        return 0

    if not PROMPT_PATH.exists():
        print(f"ERROR: Prompt file not found: {PROMPT_PATH}")
        return 1

    template = PROMPT_PATH.read_text()
    con = get_conn()
    ensure_table(con)

    rows = load_pending(con, subject=args.subject, year=args.year, limit=args.limit)
    con.close()

    if not rows:
        print("No pending questions found (all already have explanations, or no validated answers).")
        return 0

    print(f"Found {len(rows)} questions to explain")
    print(f"Estimated cost: ~${len(rows) * 0.001:.2f} (Haiku Batch)")
    confirm = input("Proceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return 0

    batch_id = submit_batch(rows, template)
    print(f"\nBatch running. Check status with:")
    print(f"  python generate_pyq_explanations.py --poll")
    print(f"  python generate_pyq_explanations.py --apply   # after polling completes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
