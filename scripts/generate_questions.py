#!/usr/bin/env python3
"""
AI gap-fill: generate MCQs for subtopics with < N questions in question_bank.
Uses Haiku Batch API (~₹0.05 per 50 questions). Run AFTER cross-exam ingestion.

Usage:
    cd scripts
    python generate_questions.py                          # all subtopics below threshold
    python generate_questions.py --threshold 10           # custom threshold (default 5)
    python generate_questions.py --subject polity         # single subject only
    python generate_questions.py --subtopic article_32    # single subtopic
    python generate_questions.py --dry-run               # show what would be generated
    python generate_questions.py --poll                   # poll in-flight batch
    python generate_questions.py --apply                  # apply results from cache to DB
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import uuid
import hashlib
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic not installed. Run: pip install anthropic")
    sys.exit(1)

DB_PATH       = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))
SYLLABUS_PATH = Path(__file__).parent.parent / "data" / "syllabus.json"
CACHE_DIR     = Path(__file__).parent.parent / "cache" / "generate_questions_results"
BATCH_ID_FILE = Path(__file__).parent.parent / "data" / "generate_questions_batch.txt"

MODEL      = "claude-haiku-4-5-20251001"
MAX_TOKENS = 2048
DEFAULT_THRESHOLD = 5
QUESTIONS_PER_REQUEST = 5  # generate 5 per subtopic per batch request

GENERATE_PROMPT = """Generate {count} high-quality UPSC Prelims-style MCQs for the following subtopic.

Subject: {subject_id}
Topic: {topic_id}
Subtopic: {subtopic_id}

Requirements:
- Mix question types: direct fact, statement-based (which are correct?), assertion-reason, matching
- All 4 options must be plausible — avoid obviously wrong distractors
- Each option should test a specific misconception or nearby fact
- Difficulty: UPSC Prelims standard (medium)
- Questions must be evergreen (not based on recent events)

Return ONLY a JSON array of {count} objects, no markdown:
[
  {{
    "question_text": "...",
    "option_a": "...",
    "option_b": "...",
    "option_c": "...",
    "option_d": "...",
    "correct_answer": "a" | "b" | "c" | "d",
    "question_type": "direct" | "statement_based" | "matching" | "assertion_reason" | "correct_incorrect",
    "memory_hook": "one memorable line to lock the concept"
  }}
]"""


def get_conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def question_hash(question_text: str) -> str:
    return hashlib.sha256(f"ai:{question_text[:200]}".encode()).hexdigest()[:24]


def load_gaps(
    threshold: int,
    subject: str | None = None,
    subtopic: str | None = None,
) -> list[dict]:
    con = get_conn()

    if subtopic:
        rows = con.execute(
            """
            SELECT COALESCE(s.subtopic_id, q.subtopic_id) as subtopic_id,
                   COALESCE(s.topic_id, q.topic_id) as topic_id,
                   COALESCE(s.subject_id, q.subject_id) as subject_id,
                   COUNT(q.id) as count
            FROM (SELECT ? as subtopic_id, NULL as topic_id, NULL as subject_id) s
            LEFT JOIN question_bank q ON q.subtopic_id = ? AND q.cancelled = 0
            GROUP BY 1
            """,
            (subtopic, subtopic),
        ).fetchall()
    else:
        sql = """
            SELECT subtopic_id, topic_id, subject_id, COUNT(*) as count
            FROM question_bank
            WHERE cancelled = 0
            GROUP BY subtopic_id
            HAVING COUNT(*) < ?
        """
        params: list = [threshold]
        if subject:
            sql += " AND subject_id = ?"
            params.append(subject)
        rows = con.execute(sql, params).fetchall()

    con.close()
    return [dict(r) for r in rows if r["subtopic_id"]]


def load_syllabus_context(subtopic_id: str) -> tuple[str, str, str]:
    """Return (subject_id, topic_id, subtopic_label) from syllabus.json."""
    if not SYLLABUS_PATH.exists():
        return "unknown", "unknown", subtopic_id
    syllabus = json.loads(SYLLABUS_PATH.read_text())
    for subject_id, subject_data in syllabus.get("subjects", {}).items():
        for topic in subject_data.get("topics", []):
            for sub in topic.get("subtopics", []):
                if sub.get("id") == subtopic_id:
                    return subject_id, topic.get("id", ""), sub.get("name", subtopic_id)
    return "unknown", subtopic_id, subtopic_id


def submit_batch(gaps: list[dict], count_per_subtopic: int) -> str:
    client_obj = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    requests = []
    for gap in gaps:
        subtopic_id = gap["subtopic_id"]
        subject_id  = gap.get("subject_id") or "unknown"
        topic_id    = gap.get("topic_id") or subtopic_id
        prompt = GENERATE_PROMPT.format(
            count=count_per_subtopic,
            subject_id=subject_id,
            topic_id=topic_id,
            subtopic_id=subtopic_id,
        )
        requests.append({
            "custom_id": subtopic_id,
            "params": {
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "messages": [{"role": "user", "content": prompt}],
            },
        })
    batch = client_obj.messages.batches.create(requests=requests)
    BATCH_ID_FILE.write_text(batch.id)
    print(f"Batch submitted: {batch.id}  ({len(requests)} subtopics × {count_per_subtopic} Qs each)")
    return batch.id


def poll_batch(batch_id: str) -> None:
    client_obj = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    while True:
        batch = client_obj.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        print(f"  {batch.processing_status}: processing={counts.processing} succeeded={counts.succeeded} errored={counts.errored}")
        if batch.processing_status == "ended":
            break
        time.sleep(30)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = CACHE_DIR / f"{batch_id}.jsonl"
    with out.open("w") as f:
        for result in client_obj.messages.batches.results(batch_id):
            f.write(result.model_dump_json() + "\n")
    print(f"Results saved: {out}")


def apply_results(batch_id: str) -> None:
    result_file = CACHE_DIR / f"{batch_id}.jsonl"
    if not result_file.exists():
        print(f"ERROR: {result_file} not found. Run --poll first.")
        sys.exit(1)

    con = get_conn()
    inserted = errors = 0

    with result_file.open() as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                errors += 1
                continue

            subtopic_id = entry.get("custom_id", "")
            if entry.get("result", {}).get("type") != "succeeded":
                errors += 1
                continue

            raw = ""
            for block in entry.get("result", {}).get("message", {}).get("content", []):
                if block.get("type") == "text":
                    raw = block["text"]
                    break
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw)

            try:
                questions = json.loads(raw)
            except json.JSONDecodeError:
                errors += 1
                continue

            subject_id, topic_id, _ = load_syllabus_context(subtopic_id)

            for q in questions:
                qt = (q.get("question_text") or "").strip()
                if len(qt) < 10:
                    continue
                qhash = question_hash(qt)
                try:
                    con.execute(
                        """
                        INSERT OR IGNORE INTO question_bank
                            (id, question_hash, question_text,
                             option_a, option_b, option_c, option_d,
                             correct_answer, answer_source, exam_source,
                             subject_id, topic_id, subtopic_id, question_type,
                             upsc_relevance, is_evergreen)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ai_generated', 'ai',
                                ?, ?, ?, ?, 0.7, 1)
                        """,
                        (
                            str(uuid.uuid4()), qhash, qt,
                            q.get("option_a", ""), q.get("option_b", ""),
                            q.get("option_c", ""), q.get("option_d", ""),
                            (q.get("correct_answer") or "").lower() or None,
                            subject_id, topic_id, subtopic_id,
                            q.get("question_type", "direct"),
                        ),
                    )
                    if con.execute("SELECT changes()").fetchone()[0]:
                        inserted += 1
                except sqlite3.Error as e:
                    print(f"  DB error ({subtopic_id}): {e}")
                    errors += 1

    con.commit()
    con.close()
    print(f"Done — inserted={inserted} errors={errors}")


def main() -> int:
    parser = argparse.ArgumentParser(description="AI gap-fill for question_bank subtopics.")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Generate for subtopics with < N questions (default {DEFAULT_THRESHOLD})")
    parser.add_argument("--subject",   help="Limit to one subject_id")
    parser.add_argument("--subtopic",  help="Target a single subtopic_id")
    parser.add_argument("--count",     type=int, default=QUESTIONS_PER_REQUEST,
                        help=f"Questions to generate per subtopic (default {QUESTIONS_PER_REQUEST})")
    parser.add_argument("--dry-run",   action="store_true", help="Show gaps without generating")
    parser.add_argument("--poll",      action="store_true", help="Poll in-flight batch and download results")
    parser.add_argument("--apply",     action="store_true", help="Apply cached results to DB")
    args = parser.parse_args()

    if args.poll or args.apply:
        if not BATCH_ID_FILE.exists():
            print("ERROR: No batch ID file. Run without --poll/--apply first.")
            return 1
        batch_id = BATCH_ID_FILE.read_text().strip()
        if args.poll:
            poll_batch(batch_id)
        if args.apply:
            apply_results(batch_id)
        return 0

    gaps = load_gaps(args.threshold, subject=args.subject, subtopic=args.subtopic)
    if not gaps:
        print("No subtopics below threshold — question_bank coverage is good!")
        return 0

    print(f"Found {len(gaps)} subtopics below threshold ({args.threshold} questions each):")
    for g in gaps[:20]:
        print(f"  {g['subtopic_id']:40s}  current={g['count']}")
    if len(gaps) > 20:
        print(f"  … and {len(gaps)-20} more")

    total_to_generate = len(gaps) * args.count
    print(f"\nTotal questions to generate: {total_to_generate}")
    print(f"Estimated cost: ~${total_to_generate * 0.0002:.2f} (Haiku Batch)")

    if args.dry_run:
        return 0

    confirm = input("Proceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return 0

    submit_batch(gaps, args.count)
    print("\nPoll with:  python generate_questions.py --poll")
    print("Apply with: python generate_questions.py --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
