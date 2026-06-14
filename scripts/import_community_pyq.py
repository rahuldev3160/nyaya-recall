"""
Import UPSC Prelims PYQs from Aquib-Nawaz/Questions (GitHub).
Source: 76 topic-wise JSON files with question_text, options (a-d), correct_answer, explanation.

What it does:
  - Clones the repo (shallow) to /tmp/aquib_nawaz_questions
  - Parses each question, extracts year from [YYYY] tag in question_text
  - Maps filename → subject_id using keyword rules
  - Inserts into pyq_questions with source_file='community:Aquib-Nawaz'
  - Skips duplicates (INSERT OR IGNORE on question_hash)
  - Creates question_explanations table if missing, inserts explanations
  - Prints per-year before/after counts

Run: cd scripts && python import_community_pyq.py
     cd scripts && python import_community_pyq.py --dry-run   # preview only
     cd scripts && python import_community_pyq.py --years 2014 2025  # year range filter
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "upsc.db"
REPO_URL = "https://github.com/Aquib-Nawaz/Questions.git"
CLONE_DIR = Path("/tmp/aquib_nawaz_questions")
PYQ_DIR = CLONE_DIR / "json_pyq"


# ---------------------------------------------------------------------------
# Subject mapping — keyword match on filename (lowercased, underscores)
# ---------------------------------------------------------------------------

SUBJECT_RULES: list[tuple[list[str], str]] = [
    # Polity / Constitution
    (["fundamental_rights", "indian_constitution", "judiciary_and_judicial",
      "dpsps_and_fundamental", "elections_election_commission", "important_acts_and_constitutional",
      "indian_political_system", "ministers_ministries", "panchayati_raj",
      "political_theory", "president_vice_president", "union_and_state_legislature",
      "various_constitutional", "important_acts"], "polity"),

    # Modern History
    (["advent_of_europeans", "civil_disobedience", "development_of_modern_education",
      "establishment_of_british", "establishment_of_congress",
      "events_from_1933", "freedom_struggle_before_gandhi",
      "last_phase_of_british", "literature_in_modern", "post_independence",
      "revolutionaries", "revolt_of_1857", "social_reforms_and_reformers",
      "tribal_and_peasant"], "modern_history"),

    # Ancient/Medieval History, Art & Culture
    (["architecture_in_ancient", "art_architecture_and_literature", "in_medieval_india",
      "art_and_craft", "important_rulers", "indian_culture_and_heritage",
      "literature_in_ancient", "politics_and_society_in_ancient",
      "religion_and_philosophy_in_ancient", "religion_and_philosophy_in_medieval"], "history_amac"),

    # Geography
    (["climatology", "map", "mountains_glaciers", "oceanography",
      "physical_geography", "roads_railways", "rocks_soil_minerals",
      "population_and_demography"], "geography"),

    # Environment & Ecology
    (["climate_change", "environment_ecology", "environmental_pollution",
      "global_initiatives_for_the_environment", "india_biodiversity",
      "biodiversity", "renewable_and_alternative"], "environment"),

    # Economy
    (["agriculture_and_environment", "agriculture", "capital_market",
      "economic_institutions", "employment_and_skill", "five_year_plans",
      "functions_of_rbi", "government_budgeting", "industries_and_other_major",
      "industries", "international_economic_organizations", "international_trade",
      "macroeconomy", "poverty_development", "taxation_system"], "economy"),

    # Science & Technology
    (["astrophysics_and_space", "biology", "chemistry", "diseases",
      "electronics_and_it", "physics", "renewable_and_alternative"], "science_tech"),

    # IR & Governance
    (["defence", "international_organizations", "international_relations",
      "nuclear_weapons"], "ir_governance"),

    # Current Affairs / General
    (["general_knowledge"], "current_affairs"),
]


def filename_to_subject(filename: str) -> str | None:
    key = filename.lower().replace(" ", "_").replace(",", "").replace("&", "and").replace("'", "")
    for keywords, subject_id in SUBJECT_RULES:
        if any(k in key for k in keywords):
            return subject_id
    return None


# ---------------------------------------------------------------------------
# Hash — must match ingest_pyq.py format: SHA256(f"{year}:{text[:200]}")[:20]
# ---------------------------------------------------------------------------

def make_hash(year: int, question_text: str) -> str:
    return hashlib.sha256(f"{year}:{question_text[:200]}".encode()).hexdigest()[:20]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clone_or_update_repo() -> bool:
    if CLONE_DIR.exists():
        print(f"  Repo already cloned at {CLONE_DIR}, pulling latest…")
        result = subprocess.run(["git", "-C", str(CLONE_DIR), "pull", "--ff-only"],
                                capture_output=True, text=True)
        print(f"  git pull: {result.stdout.strip() or result.stderr.strip()}")
    else:
        print(f"  Cloning {REPO_URL} → {CLONE_DIR} …")
        result = subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(CLONE_DIR)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}")
            return False
        print("  Clone complete.")
    return True


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def ensure_explanations_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS question_explanations (
            question_id         INTEGER PRIMARY KEY REFERENCES pyq_questions(id),
            concept_tested      TEXT,
            correct_explanation TEXT NOT NULL,
            option_a_note       TEXT,
            option_b_note       TEXT,
            option_c_note       TEXT,
            option_d_note       TEXT,
            memory_hook         TEXT,
            model_used          TEXT NOT NULL DEFAULT 'community_import',
            generated_at        TEXT NOT NULL DEFAULT (datetime('now')),
            version             INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.commit()


def year_counts(conn: sqlite3.Connection) -> dict[int, int]:
    rows = conn.execute(
        "SELECT year, COUNT(*) FROM pyq_questions WHERE year BETWEEN 2014 AND 2025 GROUP BY year"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------------
# Main import
# ---------------------------------------------------------------------------

def run_import(dry_run: bool = False, year_min: int = 2014, year_max: int = 2025) -> None:
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Importing community PYQs ({year_min}–{year_max})\n")

    if not clone_or_update_repo():
        sys.exit(1)

    if not PYQ_DIR.exists():
        print(f"ERROR: Expected directory not found: {PYQ_DIR}")
        sys.exit(1)

    json_files = sorted(PYQ_DIR.glob("*.json"))
    print(f"  Found {len(json_files)} topic JSON files\n")

    conn = get_db()
    ensure_explanations_table(conn)

    before = year_counts(conn)

    inserted_q = 0
    skipped_dup = 0
    skipped_no_year = 0
    skipped_out_of_range = 0
    inserted_exp = 0

    subject_miss: list[str] = []  # filenames with no subject match

    for jf in json_files:
        try:
            questions = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  SKIP {jf.name}: parse error — {e}")
            continue

        if not isinstance(questions, list):
            continue

        subject_id = filename_to_subject(jf.stem)
        if subject_id is None:
            subject_miss.append(jf.name)

        file_inserted = 0
        for q in questions:
            raw_text: str = q.get("question_text", "").strip()
            options: dict = q.get("options", {})
            correct: str | None = q.get("correct_answer", "").strip().lower() or None
            explanation: str = q.get("explanation", "").strip()

            # Extract year from [YYYY] or [YYYY/X-NN] tag (e.g. [2025/A-83])
            m = re.search(r"\[(\d{4})(?:[^\]]*)\]", raw_text)
            if not m:
                skipped_no_year += 1
                continue
            year = int(m.group(1))

            if not (year_min <= year <= year_max):
                skipped_out_of_range += 1
                continue

            # Strip year tag (both formats) from question text for clean storage
            clean_text = re.sub(r"\s*\[\d{4}[^\]]*\]\s*", " ", raw_text).strip()

            qhash = make_hash(year, clean_text)

            opt_a = options.get("a", "").strip() or None
            opt_b = options.get("b", "").strip() or None
            opt_c = options.get("c", "").strip() or None
            opt_d = options.get("d", "").strip() or None

            if not dry_run:
                cur = conn.execute("""
                    INSERT OR IGNORE INTO pyq_questions
                        (year, question_text, option_a, option_b, option_c, option_d,
                         correct_answer, subject_id, source_file, question_hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (year, clean_text, opt_a, opt_b, opt_c, opt_d,
                      correct, subject_id, "community:Aquib-Nawaz", qhash))

                if cur.rowcount == 1:
                    inserted_q += 1
                    file_inserted += 1

                    # Insert explanation if we have one
                    if explanation:
                        new_id = cur.lastrowid
                        conn.execute("""
                            INSERT OR IGNORE INTO question_explanations
                                (question_id, correct_explanation, model_used)
                            VALUES (?,?,'community_import')
                        """, (new_id, explanation))
                        inserted_exp += 1
                else:
                    skipped_dup += 1
            else:
                # Dry run — just count
                exists = conn.execute(
                    "SELECT 1 FROM pyq_questions WHERE question_hash=?", (qhash,)
                ).fetchone()
                if exists:
                    skipped_dup += 1
                else:
                    inserted_q += 1
                    file_inserted += 1

        if file_inserted:
            print(f"  {jf.stem[:55]:<55}  +{file_inserted}")

    if not dry_run:
        conn.commit()

    after = year_counts(conn)

    # -------------------------------------------------------------------
    print(f"\n{'─'*65}")
    print(f"{'Year':<6} {'Before':>8} {'After':>8} {'Added':>8}  {'Target':>8}  {'Gap':>6}")
    print(f"{'─'*65}")
    all_years = sorted(set(list(before.keys()) + list(after.keys()) + list(range(year_min, year_max + 1))))
    for yr in all_years:
        b = before.get(yr, 0)
        a = after.get(yr, 0)
        delta = a - b
        gap = 100 - a
        gap_str = f"{gap:+d}" if gap > 0 else "✅ OK"
        print(f"{yr:<6} {b:>8} {a:>8} {delta:>8}  {'~100':>8}  {gap_str:>6}")
    print(f"{'─'*65}")
    print(f"\nInserted questions : {inserted_q}")
    print(f"Inserted explanations: {inserted_exp}")
    print(f"Skipped (duplicate): {skipped_dup}")
    print(f"Skipped (no year)  : {skipped_no_year}")
    print(f"Skipped (out of range {year_min}–{year_max}): {skipped_out_of_range}")

    if subject_miss:
        print(f"\n⚠  No subject mapping for {len(subject_miss)} file(s) — stored with subject_id=NULL:")
        for f in subject_miss:
            print(f"     {f}")
        print("   Run retag_pyq_subtopics.py after import to fix these.")

    conn.close()
    print(f"\n{'[DRY RUN — nothing written]' if dry_run else 'Done.'}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import community PYQs from Aquib-Nawaz/Questions")
    parser.add_argument("--dry-run", action="store_true", help="Preview counts without writing to DB")
    parser.add_argument("--years", nargs=2, type=int, metavar=("MIN", "MAX"),
                        default=[2014, 2025], help="Year range to import (default: 2014 2025)")
    args = parser.parse_args()
    run_import(dry_run=args.dry_run, year_min=args.years[0], year_max=args.years[1])
