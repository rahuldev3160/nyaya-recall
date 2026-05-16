"""
Prompt improvement pipeline — reads aggregated content_feedback rows from SQLite,
calls Haiku once per prompt file, and prints suggestions to stdout.

Usage:
    python scripts/apply_feedback.py
    python scripts/apply_feedback.py --since 2026-05-01
    python scripts/apply_feedback.py --output          # writes to logs/prompt_suggestions_YYYY-MM-DD.txt

The script does NOT modify any prompt files — Rahul reviews and edits manually.
Cost: ~$0.001 per full run (Haiku, 3 prompt files).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH      = os.getenv("DB_PATH", "data/upsc.db")
PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR  = PROJECT_ROOT / "prompts"
LOGS_DIR     = PROJECT_ROOT / "logs"

# The three prompt files that content_feedback feeds into
PROMPT_FILES = [
    "diagnostic_quiz.txt",
    "adaptive_session.txt",
    "session_notes.txt",
]

# Minimum occurrences in a feedback group before it is reported to Haiku
MIN_GROUP_COUNT = 2

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _db_connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def fetch_feedback(con: sqlite3.Connection, since: str) -> dict[str, list[sqlite3.Row]]:
    """
    Returns {prompt_file: [rows]} for all content_feedback rows newer than `since`.
    Only includes rows where prompt_file is not NULL.
    """
    if not _table_exists(con, "content_feedback"):
        return {}

    rows = con.execute(
        """
        SELECT prompt_file, subtopic_id, content_type, notes_section, verdict, note_text
        FROM content_feedback
        WHERE prompt_file IS NOT NULL
          AND created_at >= ?
        ORDER BY prompt_file, subtopic_id, content_type, notes_section, verdict
        """,
        (since,),
    ).fetchall()

    result: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        pf = row["prompt_file"]
        result.setdefault(pf, []).append(row)
    return result


def aggregate(rows: list[sqlite3.Row]) -> list[dict]:
    """
    Groups rows by (subtopic_id, content_type, notes_section, verdict),
    counts occurrences, collects up to 3 note_text samples per group.
    Returns only groups with count >= MIN_GROUP_COUNT.
    """
    groups: dict[tuple, dict] = {}
    for row in rows:
        key = (
            row["subtopic_id"] or "",
            row["content_type"] or "",
            row["notes_section"] or "",
            row["verdict"] or "",
        )
        if key not in groups:
            groups[key] = {"count": 0, "note_samples": []}
        groups[key]["count"] += 1
        note = (row["note_text"] or "").strip()
        if note and len(groups[key]["note_samples"]) < 3:
            groups[key]["note_samples"].append(note)

    result = []
    for (subtopic_id, content_type, notes_section, verdict), data in groups.items():
        if data["count"] < MIN_GROUP_COUNT:
            continue
        entry: dict = {
            "subtopic_id":  subtopic_id,
            "content_type": content_type,
            "verdict":      verdict,
            "count":        data["count"],
            "note_samples": data["note_samples"],
        }
        if notes_section:
            entry["notes_section"] = notes_section
        result.append(entry)

    return result


# ---------------------------------------------------------------------------
# Haiku call
# ---------------------------------------------------------------------------

def call_haiku(prompt_file: str, aggregated: list[dict]) -> str:
    """
    Calls Haiku with the feedback_aggregation.txt template and returns
    the raw suggestion text.
    """
    template_path = PROMPTS_DIR / "feedback_aggregation.txt"
    if not template_path.exists():
        return f"ERROR: {template_path} not found — cannot generate suggestions."

    prompt_path = PROMPTS_DIR / prompt_file
    if not prompt_path.exists():
        return f"ERROR: prompts/{prompt_file} not found — skipping."

    current_prompt_text = prompt_path.read_text()
    template = template_path.read_text()

    filled = (
        template
        .replace("{{current_prompt_text}}", current_prompt_text)
        .replace("{{aggregated_feedback_json}}", json.dumps(aggregated, indent=2))
    )

    response = client.messages.create(
        model=os.getenv("AI_MODEL_FAST", "claude-haiku-4-5"),
        max_tokens=1024,
        messages=[{"role": "user", "content": filled}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build_output(results: dict[str, str]) -> str:
    lines: list[str] = []
    for prompt_file, suggestion in results.items():
        lines.append(f"\n{'=' * 60}")
        lines.append(f"=== Suggestions for prompts/{prompt_file} ===")
        lines.append(f"{'=' * 60}\n")
        lines.append(suggestion)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate prompt improvement suggestions from content_feedback data."
    )
    parser.add_argument(
        "--since",
        default=None,
        metavar="YYYY-MM-DD",
        help="Only include feedback from this date onward (default: last 30 days).",
    )
    parser.add_argument(
        "--output",
        action="store_true",
        help="Write suggestions to logs/prompt_suggestions_YYYY-MM-DD.txt instead of stdout.",
    )
    args = parser.parse_args()

    since = args.since or (date.today() - timedelta(days=30)).isoformat()

    con = _db_connect()

    if not _table_exists(con, "content_feedback"):
        print("content_feedback table does not exist yet — no feedback to analyse.")
        con.close()
        return

    feedback_by_file = fetch_feedback(con, since)
    con.close()

    if not feedback_by_file:
        print(f"No feedback rows found since {since}.")
        return

    results: dict[str, str] = {}
    any_actionable = False

    for prompt_file in PROMPT_FILES:
        rows = feedback_by_file.get(prompt_file, [])
        if not rows:
            continue

        aggregated = aggregate(rows)
        if not aggregated:
            continue

        any_actionable = True
        print(f"Calling Haiku for {prompt_file} ({len(aggregated)} actionable group(s))...",
              flush=True)
        suggestion = call_haiku(prompt_file, aggregated)
        results[prompt_file] = suggestion

    if not any_actionable:
        print("No actionable feedback yet — keep collecting.")
        return

    output_text = build_output(results)

    if args.output:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = LOGS_DIR / f"prompt_suggestions_{date.today().isoformat()}.txt"
        out_path.write_text(output_text)
        print(f"\nSuggestions written to {out_path}")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
