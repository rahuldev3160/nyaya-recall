"""
One-time repair: classifies subtopic_id for session_answers where it is empty/NULL.
Only touches polity and economy records. Uses a single Claude call per subject batch.
Run from project root: python3 scripts/repair_subtopics.py
"""
from __future__ import annotations
import os
import json
import sqlite3
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = os.getenv("DB_PATH", "data/upsc.db")
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

POLITY_SUBTOPICS = [
    "making_constitution", "preamble", "union_territories", "citizenship",
    "constitutional_amendments", "right_to_equality", "right_to_freedom",
    "right_against_exploitation", "right_to_religion", "cultural_educational_rights",
    "right_to_constitutional_remedies", "dpsp", "fundamental_duties",
    "president", "vice_president", "prime_minister_cabinet", "attorney_general",
    "rajya_sabha", "lok_sabha", "parliamentary_procedures", "bills_legislation",
    "parliamentary_committees", "budget_process", "supreme_court", "high_courts",
    "judicial_review", "tribunals", "distribution_powers", "interstate_relations",
    "emergency_provisions", "special_provisions_states", "panchayati_raj",
    "urban_local_bodies", "fifth_sixth_schedules", "election_commission",
    "cag", "upsc_spsc", "finance_commission", "national_commissions",
    "statutory_bodies", "schedules_overview",
]

ECONOMY_SUBTOPICS = [
    "gdp_national_income", "inflation_indices", "fiscal_policy_budget",
    "monetary_policy_rbi", "rbi_functions", "banking_types_nbfc",
    "financial_markets", "digital_payments_fintech", "budget_2026_highlights",
    "budget_2025_highlights", "gst_structure", "direct_indirect_taxes",
    "msp_food_security", "agriculture_schemes", "agriculture_revolutions",
    "wto_agreements", "india_ftas", "imf_worldbank", "bop_exchange_rate",
    "eco_survey_2025_26", "eco_survey_2024_25", "india_rankings_reports",
    "poverty_measurement_lines", "social_sector_schemes",
]

SUBTOPICS_BY_SUBJECT = {"polity": POLITY_SUBTOPICS, "economy": ECONOMY_SUBTOPICS}


def classify_batch(subject_id: str, rows: list[dict]) -> dict[int, str]:
    """
    rows: list of {db_id, question_text}
    Returns {db_id: subtopic_id}.
    Uses sequential index keys internally to avoid DB ID confusion.
    """
    valid = SUBTOPICS_BY_SUBJECT.get(subject_id, [])
    # Use sequential index starting at 1; store mapping idx -> db_id separately
    idx_to_db_id = {i + 1: r["db_id"] for i, r in enumerate(rows)}
    numbered = "\n".join(
        f"{i+1}. {r['question_text'][:200]}"
        for i, r in enumerate(rows)
    )
    prompt = (
        f"Classify each UPSC Prelims {subject_id} question by its subtopic.\n"
        f"Valid subtopic IDs (choose ONLY from this list): {', '.join(valid)}\n\n"
        f"Questions:\n{numbered}\n\n"
        f"Return a JSON object mapping the question number (1, 2, 3...) to a subtopic_id.\n"
        f"Example: {{\"1\": \"election_commission\", \"2\": \"preamble\"}}\n"
        f"Output ONLY the JSON object."
    )
    response = client.messages.create(
        model=os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001"),
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    seq_map = json.loads(raw[start:end])

    # Convert sequential index -> db_id
    result: dict[int, str] = {}
    for seq_str, subtopic_id in seq_map.items():
        seq = int(seq_str)
        db_id = idx_to_db_id.get(seq)
        if db_id is not None and subtopic_id in valid:
            result[db_id] = subtopic_id
    return result


def run():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    for subject_id in ("polity", "economy"):
        # Fetch rows that need subtopic (including wrongly-set economy subtopics on polity)
        if subject_id == "polity":
            # Re-do all polity rows since last repair set wrong subtopics from economy
            rows = con.execute(
                "SELECT id, question_text FROM session_answers WHERE subject_id=?",
                (subject_id,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT id, question_text FROM session_answers "
                "WHERE subject_id=? AND (subtopic_id IS NULL OR subtopic_id='')",
                (subject_id,),
            ).fetchall()

        if not rows:
            print(f"{subject_id}: nothing to fix")
            continue

        print(f"{subject_id}: classifying {len(rows)} question(s)...")
        batch = [{"db_id": r["id"], "question_text": r["question_text"] or ""} for r in rows]
        id_map = classify_batch(subject_id, batch)

        updated = 0
        for db_id, subtopic_id in id_map.items():
            con.execute(
                "UPDATE session_answers SET subtopic_id=? WHERE id=?",
                (subtopic_id, db_id),
            )
            updated += 1

        con.commit()
        print(f"  {subject_id}: updated {updated}/{len(rows)} rows")
        if id_map:
            sample = list(id_map.items())[:5]
            for db_id, st in sample:
                print(f"    id={db_id} → {st}")

    con.close()
    print("\nDone. Run batch_analyse.py to refresh subtopic_scores and prep_profile.")


if __name__ == "__main__":
    run()
