"""
Fill topic_id + subtopic_id for community-imported pyq_questions rows.

WHY THIS EXISTS
---------------
import_community_pyq.py sets subject_id correctly (via filename → subject mapping)
but cannot set topic_id or subtopic_id — there is no source for that classification.

retag_pyq_subtopics.py only handles rows WHERE subtopic_id IS NOT NULL (it re-maps
existing free-text IDs to canonical syllabus IDs). This script fills the NULL rows.

WHAT IT DOES
------------
1. Loads syllabus.json → builds:
   - subject → [(subtopic_id, subtopic_name, topic_id)] list
   - (subject_id, subtopic_id) → topic_id reverse lookup
2. Queries WHERE subtopic_id IS NULL AND subject_id IS NOT NULL
   (skips NULL subject rows — those are corrupted/Hindi OCR failures)
3. Groups by subject_id
4. Sends batches of 20 questions to Haiku with candidate subtopics (id + name)
5. Derives topic_id from subtopic via reverse lookup
6. UPDATEs both topic_id + subtopic_id — NEVER touches rows that already have subtopic_id
7. Commits per subject so progress is preserved if interrupted
8. Prints per-year, per-subject coverage after completion

SAFETY
------
- Only queries WHERE subtopic_id IS NULL — already-indexed rows are never touched
- All UPDATEs are guarded by WHERE id = ? AND subtopic_id IS NULL (double safety)
- Dry-run mode shows proposed changes without writing anything

COST ESTIMATE
-------------
~916 questions / 20 per batch ≈ 46 Haiku calls
~800 input + ~200 output tokens each → ~$0.005 total

Usage:
    cd scripts && python3 tag_pyq_questions.py
    cd scripts && python3 tag_pyq_questions.py --dry-run
    cd scripts && python3 tag_pyq_questions.py --subject economy  # single subject
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))
SYLLABUS_PATH = Path(__file__).parent.parent / "data" / "syllabus.json"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

BATCH_SIZE = 20
VALID_SUBJECTS = {
    "polity", "history_amac", "modern_history", "geography",
    "economy", "environment", "science_tech", "current_affairs", "ir_governance",
}


# ---------------------------------------------------------------------------
# Syllabus helpers
# ---------------------------------------------------------------------------

def load_syllabus() -> tuple[dict[str, list[dict]], dict[tuple[str, str], str]]:
    """
    Returns:
      subject_map:  {subject_id: [{"id": subtopic_id, "name": subtopic_name, "topic_id": ...}]}
      topic_lookup: {(subject_id, subtopic_id): topic_id}
    """
    syllabus = json.loads(SYLLABUS_PATH.read_text())
    subject_map: dict[str, list[dict]] = {}
    topic_lookup: dict[tuple[str, str], str] = {}

    for subj in syllabus.get("subjects", []):
        sid = subj["id"]
        entries: list[dict] = []
        for topic in subj.get("topics", []):
            tid = topic["id"]
            for st in topic.get("subtopics", []):
                entry = {"id": st["id"], "name": st["name"], "topic_id": tid}
                entries.append(entry)
                topic_lookup[(sid, st["id"])] = tid
        subject_map[sid] = entries

    return subject_map, topic_lookup


# ---------------------------------------------------------------------------
# Haiku classification
# ---------------------------------------------------------------------------

def classify_batch(
    questions: list[dict],
    subtopics: list[dict],
    subject_id: str,
) -> dict[int, str]:
    """
    Ask Haiku to classify a batch of questions into canonical subtopic IDs.

    questions:  list of {"id": int, "question_text": str}
    subtopics:  list of {"id": str, "name": str}

    Returns {question_id: subtopic_id} — only IDs present in the candidate list.
    """
    q_lines = "\n".join(
        f"{i + 1}. [id={q['id']}] {q['question_text'][:220]}"
        for i, q in enumerate(questions)
    )
    subtopic_lines = "\n".join(
        f"  {st['id']} — {st['name']}"
        for st in subtopics
    )

    prompt = f"""You are classifying UPSC Civil Services Prelims questions into canonical subtopic categories.

Subject: {subject_id}

Available subtopics (ONLY use IDs from this list):
{subtopic_lines}

Questions to classify:
{q_lines}

For each question, respond with exactly one line:
<question_id>: <subtopic_id>

where <question_id> is the numeric id shown in brackets and <subtopic_id> is one of the IDs above.
Pick the CLOSEST matching subtopic even if the question is broad or cross-cutting.
Output ONLY these lines, nothing else."""

    msg = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()

    valid_ids = {st["id"] for st in subtopics}
    result: dict[int, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        parts = line.split(":", 1)
        try:
            qid = int(parts[0].strip())
            subtopic = parts[1].strip()
            if subtopic in valid_ids:
                result[qid] = subtopic
        except (ValueError, IndexError):
            continue
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dry_run: bool = False, only_subject: str | None = None) -> None:
    subject_map, topic_lookup = load_syllabus()

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # Query only rows that need tagging
    rows = con.execute(
        "SELECT id, year, subject_id, question_text "
        "FROM pyq_questions "
        "WHERE subtopic_id IS NULL AND subject_id IS NOT NULL"
    ).fetchall()

    # Group by subject_id
    by_subject: dict[str, list[dict]] = {}
    for row in rows:
        sid = row["subject_id"]
        by_subject.setdefault(sid, []).append(dict(row))

    total_updated = 0
    total_failed = 0
    total_skipped_subject = 0

    subjects_to_process = sorted(by_subject.keys())
    if only_subject:
        subjects_to_process = [only_subject] if only_subject in by_subject else []
        if not subjects_to_process:
            print(f"No untagged rows found for subject '{only_subject}'.")
            con.close()
            return

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Tagging {len(rows)} untagged pyq_questions rows\n")

    for subject_id in subjects_to_process:
        questions = by_subject[subject_id]
        subtopics = subject_map.get(subject_id, [])

        if not subtopics:
            print(f"[SKIP] {subject_id}: not in syllabus ({len(questions)} rows skipped)")
            total_skipped_subject += len(questions)
            continue

        if subject_id not in VALID_SUBJECTS:
            print(f"[SKIP] {subject_id}: not a standard GS subject ({len(questions)} rows skipped)")
            total_skipped_subject += len(questions)
            continue

        print(f"[{subject_id}] {len(questions)} questions → {len(subtopics)} candidate subtopics")

        subject_updated = 0
        subject_failed = 0

        # Process in batches
        mapping: dict[int, str] = {}
        for i in range(0, len(questions), BATCH_SIZE):
            chunk = questions[i: i + BATCH_SIZE]
            batch_result = classify_batch(chunk, subtopics, subject_id)
            mapping.update(batch_result)
            print(f"  batch {i // BATCH_SIZE + 1}/{-(-len(questions) // BATCH_SIZE)}: "
                  f"classified {len(batch_result)}/{len(chunk)}")

        # Apply updates
        for q in questions:
            subtopic_id = mapping.get(q["id"])
            if not subtopic_id:
                subject_failed += 1
                continue

            topic_id = topic_lookup.get((subject_id, subtopic_id))
            if not topic_id:
                subject_failed += 1
                continue

            if dry_run:
                print(f"  DRY-RUN id={q['id']} year={q['year']} → "
                      f"topic={topic_id} subtopic={subtopic_id}")
            else:
                # Double-safety: only update if subtopic_id is still NULL
                con.execute(
                    "UPDATE pyq_questions SET topic_id=?, subtopic_id=? "
                    "WHERE id=? AND subtopic_id IS NULL",
                    (topic_id, subtopic_id, q["id"]),
                )
            subject_updated += 1

        if not dry_run:
            con.commit()

        total_updated += subject_updated
        total_failed += subject_failed
        print(f"  → {subject_updated} tagged, {subject_failed} unclassified\n")

    # ---------------------------------------------------------------------------
    # Post-run coverage report
    # ---------------------------------------------------------------------------
    print(f"{'─' * 70}")
    print(f"{'Year':<6} {'Total':>7} {'Tagged':>8} {'Untagged':>10}  {'Coverage':>10}")
    print(f"{'─' * 70}")

    year_rows = con.execute(
        "SELECT year, "
        "COUNT(*) as total, "
        "SUM(CASE WHEN subtopic_id IS NOT NULL THEN 1 ELSE 0 END) as tagged "
        "FROM pyq_questions "
        "WHERE year BETWEEN 2014 AND 2025 "
        "GROUP BY year ORDER BY year"
    ).fetchall()

    for r in year_rows:
        untagged = r["total"] - r["tagged"]
        pct = r["tagged"] / r["total"] * 100 if r["total"] else 0
        flag = "✅" if pct >= 90 else ("⚠️ " if pct >= 60 else "❌")
        print(f"{r['year']:<6} {r['total']:>7} {r['tagged']:>8} {untagged:>10}  {pct:>8.1f}% {flag}")

    print(f"{'─' * 70}")
    print(f"\nSubject breakdown (after run):")
    subj_rows = con.execute(
        "SELECT subject_id, COUNT(*) as total, "
        "SUM(CASE WHEN subtopic_id IS NOT NULL THEN 1 ELSE 0 END) as tagged "
        "FROM pyq_questions "
        "WHERE year BETWEEN 2014 AND 2025 "
        "GROUP BY subject_id ORDER BY subject_id"
    ).fetchall()

    for r in subj_rows:
        untagged = r["total"] - r["tagged"]
        pct = r["tagged"] / r["total"] * 100 if r["total"] else 0
        flag = "✅" if pct >= 90 else ("⚠️ " if pct >= 60 else "❌")
        sid = r["subject_id"] or "(null)"
        print(f"  {sid:<22} {r['tagged']:>4}/{r['total']:<4} ({pct:>5.1f}%) {flag} — {untagged} untagged")

    print(f"\nTotal: {total_updated} tagged, {total_failed} unclassified, "
          f"{total_skipped_subject} skipped (unknown subject)")
    if dry_run:
        print("\n[DRY RUN — nothing written to DB]")
    else:
        print("\nDone. Run priority_scorer.py next to recompute PYQ weights.")

    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fill topic_id + subtopic_id for untagged pyq_questions rows."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show proposed changes without writing to DB.")
    parser.add_argument("--subject", metavar="SUBJECT_ID",
                        help="Process a single subject only (e.g. economy).")
    args = parser.parse_args()
    run(dry_run=args.dry_run, only_subject=args.subject)
