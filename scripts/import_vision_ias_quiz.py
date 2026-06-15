#!/usr/bin/env python3
"""
Import Vision IAS daily quiz MCQs from Aquib-Nawaz/Questions (GitHub).
Source: json_quiz/ folder — 55 files, 2021–2026, all major UPSC subjects.

What it does:
  - Downloads each json_quiz file via GitHub API (no cloning needed)
  - Parses year + subject from filename
  - Inserts into question_bank table (dedup via question_hash)
  - Stores explanation in explanation_full field
  - answer_source = 'community_validated' (Vision IAS curated)
  - exam_source   = 'vision_ias'

Usage:
    cd scripts
    python import_vision_ias_quiz.py            # import all files
    python import_vision_ias_quiz.py --dry-run  # preview only
    python import_vision_ias_quiz.py --year 2024  # single year
    python import_vision_ias_quiz.py --force      # re-import already-processed files
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

DB_PATH  = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))
LOG_PATH = Path(__file__).parent / "vision_ias_ingestion_log.json"

REPO_API     = "https://api.github.com/repos/Aquib-Nawaz/Questions/contents/json_quiz"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# ---------------------------------------------------------------------------
# Subject filename → subject_id mapping
# ---------------------------------------------------------------------------

FILENAME_SUBJECT_MAP: list[tuple[list[str], str]] = [
    (["polity", "governance", "constitution"], "polity"),
    (["economy", "economic"], "economy"),
    (["ancient", "medieval", "art_and_culture", "art_&_culture", "art &"], "history_amac"),
    (["modern_india", "modern india", "modern_history"], "modern_history"),
    (["history"], "modern_history"),   # "History" files are mostly modern + medieval mix
    (["geography", "geo"], "geography"),
    (["environment", "ecology"], "environment"),
    (["science_and_technology", "science &", "science_&"], "science_tech"),
    (["ir", "international"], "ir_governance"),
]

# Override for files that mix subjects — assign the dominant one
FILENAME_OVERRIDES: dict[str, str] = {
    "2022_science_&_technology_and_ir": "science_tech",
    "2022_ancient_&_medieval_india_+_art_&_culture": "history_amac",
    "2023_unknown": "current_affairs",
    "2024_unknown": "current_affairs",
}


def subject_from_filename(name: str) -> str:
    stem = Path(name).stem.lower()

    # Exact override first
    if stem in FILENAME_OVERRIDES:
        return FILENAME_OVERRIDES[stem]

    for keywords, subject_id in FILENAME_SUBJECT_MAP:
        for kw in keywords:
            if kw in stem:
                return subject_id

    return "current_affairs"  # fallback


def year_from_filename(name: str) -> int:
    m = re.match(r"^(\d{4})_", Path(name).stem)
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def question_hash(question_text: str) -> str:
    normalized = re.sub(r"\s+", " ", question_text.strip().lower())
    return hashlib.sha256(f"vision_ias:{normalized[:300]}".encode()).hexdigest()[:24]


# ---------------------------------------------------------------------------
# GitHub fetching
# ---------------------------------------------------------------------------

def _headers() -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    token = GITHUB_TOKEN or os.getenv("GH_TOKEN", "")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def list_quiz_files() -> list[dict]:
    resp = requests.get(REPO_API, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_file(download_url: str) -> list[dict]:
    """Download a json_quiz file and return its parsed contents."""
    resp = requests.get(download_url, headers=_headers(), timeout=60)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Insertion
# ---------------------------------------------------------------------------

def insert_questions(
    con: sqlite3.Connection,
    questions: list[dict],
    subject_id: str,
    year: int,
    filename: str,
    dry_run: bool,
) -> tuple[int, int]:
    inserted = dupes = 0

    for q in questions:
        qt = (q.get("question_text") or "").strip()
        if not qt or len(qt) < 15:
            continue

        # Clean markdown bold markers from question text
        qt = re.sub(r"\*\*(.+?)\*\*", r"\1", qt)
        qt = qt.strip()

        opts = q.get("options") or {}
        a = (opts.get("a") or "").strip()
        b = (opts.get("b") or "").strip()
        c = (opts.get("c") or "").strip()
        d = (opts.get("d") or "").strip()
        if not all([a, b, c, d]):
            continue

        correct = (q.get("correct_answer") or "").strip().lower()
        if correct not in ("a", "b", "c", "d"):
            correct = None

        explanation = (q.get("explanation") or "").strip() or None
        if explanation:
            # Clean markdown from explanation
            explanation = re.sub(r"\*\*(.+?)\*\*", r"\1", explanation)

        qhash = question_hash(qt)
        qid   = str(uuid.uuid4())

        # Detect question type from text
        if re.search(r"consider the following|statement[s]?\s+\d|which of the (above|following) statement", qt, re.I):
            qtype = "statement_based"
        elif re.search(r"match.{0,20}(list|pair|column)", qt, re.I):
            qtype = "matching"
        elif re.search(r"assertion.*reason|reason.*assertion", qt, re.I):
            qtype = "assertion_reason"
        elif re.search(r"arrange.*chronolog|chronological order", qt, re.I):
            qtype = "chronological"
        else:
            qtype = "direct"

        if dry_run:
            print(f"  [DRY] {subject_id} {year}: {qt[:70]}…")
            inserted += 1
            continue

        try:
            cur = con.execute(
                """
                INSERT OR IGNORE INTO question_bank
                    (id, question_hash, question_text,
                     option_a, option_b, option_c, option_d,
                     correct_answer, explanation_full,
                     answer_source, exam_source, year,
                     subject_id, topic_id, subtopic_id,
                     question_type, upsc_relevance, is_evergreen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'vision_ias', ?, ?, ?, ?, ?, 0.85, 1)
                """,
                (
                    qid, qhash, qt,
                    a, b, c, d,
                    correct, explanation,
                    "community_validated",
                    year,
                    subject_id,
                    subject_id,            # topic_id = subject_id for now (retag later)
                    subject_id,            # subtopic_id = subject_id for now
                    qtype,
                ),
            )
            if cur.rowcount:
                inserted += 1
            else:
                dupes += 1
        except sqlite3.Error as e:
            print(f"  DB error: {e}")

    if not dry_run and inserted:
        con.commit()

    return inserted, dupes


# ---------------------------------------------------------------------------
# Log helpers
# ---------------------------------------------------------------------------

def load_log() -> dict:
    return json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else {}


def save_log(log: dict) -> None:
    LOG_PATH.write_text(json.dumps(log, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Import Vision IAS quiz MCQs into question_bank.")
    parser.add_argument("--dry-run", action="store_true", help="Parse but do NOT write to DB")
    parser.add_argument("--year",    type=int, help="Only import files from this year")
    parser.add_argument("--force",   action="store_true", help="Re-import already-processed files")
    args = parser.parse_args()

    log = load_log()

    # Verify question_bank table exists before fetching anything
    try:
        check_con = get_conn()
        check_con.execute("SELECT 1 FROM question_bank LIMIT 1")
        check_con.close()
    except Exception:
        print("ERROR: question_bank table does not exist.")
        print("Start the backend once (`uvicorn server:app`) to create it, then re-run.")
        return 1

    print("Fetching file list from GitHub…")
    try:
        files = list_quiz_files()
    except Exception as e:
        print(f"ERROR fetching file list: {e}")
        return 1

    files = [f for f in files if f["name"].endswith(".json")]
    print(f"Found {len(files)} JSON files")

    if args.year:
        files = [f for f in files if year_from_filename(f["name"]) == args.year]
        print(f"Filtered to {len(files)} files for year {args.year}")

    con = get_conn() if not args.dry_run else None  # type: ignore[assignment]

    grand_inserted = grand_dupes = 0

    for file_meta in sorted(files, key=lambda x: x["name"]):
        fname    = file_meta["name"]
        dl_url   = file_meta["download_url"]
        year     = year_from_filename(fname)
        subject  = subject_from_filename(fname)

        if fname in log and not args.force and not args.dry_run:
            print(f"  SKIP (already imported): {fname}")
            continue

        print(f"  {fname:55s} year={year} subject={subject}")

        try:
            questions = fetch_file(dl_url)
        except Exception as e:
            print(f"    ERROR fetching: {e}")
            time.sleep(2)
            continue

        if not isinstance(questions, list):
            print(f"    Unexpected format: {type(questions)}")
            continue

        ins, dup = insert_questions(
            con,        # type: ignore[arg-type]
            questions,
            subject,
            year,
            fname,
            args.dry_run,
        )
        print(f"    {len(questions)} questions → inserted={ins} dupes={dup}")
        grand_inserted += ins
        grand_dupes    += dup

        if not args.dry_run:
            log[fname] = {"inserted": ins, "dupes": dup, "subject": subject, "year": year}
            save_log(log)

        time.sleep(0.2)   # gentle rate limiting

    if con:
        con.close()

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Total: inserted={grand_inserted} dupes={grand_dupes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
