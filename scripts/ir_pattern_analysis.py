"""
IR Pattern Analysis — extracts all International Relations PYQs from 2022–2025,
cross-references with ChromaDB content (IR notes, PIB e-books, Economic Survey,
Budget, places in news), and runs a single Sonnet analysis to produce a structured
pattern report + 2026 prediction list.

Usage:
    cd /path/to/project && python scripts/ir_pattern_analysis.py

Output:
    exports/ir_pattern_2022_2025.md

Cost: ~$0.05–0.10 (one Sonnet call, ~8–12k tokens context)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import chromadb
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH       = os.getenv("DB_PATH", "data/upsc.db")
CHROMA_PATH   = os.getenv("CHROMA_PATH", "vector_store")
PROJECT_ROOT  = Path(__file__).parent.parent
EXPORTS_DIR   = PROJECT_ROOT / "exports"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# IR keyword clusters for cross-subject PYQ extraction
# ---------------------------------------------------------------------------

IR_KEYWORD_GROUPS = {
    "organisations_forums": [
        "organisation", "organization", "brics", "g20", "g-20", "sco", "quad",
        "bimstec", "saarc", "asean", "nato", "un ", "united nations",
        "wto", "imf", "world bank", "ibrd", "ifc", "who", "iaea",
        "commonwealth", "non-aligned", "nam ", "interpol", "fatf",
        "apec", "rcep", "opec", "oecd", "icc", "icj", "csto", "aukus",
        "turkic", "g7", "g-7", "miga", "aiib", "ndb ", "adb ",
    ],
    "agreements_treaties": [
        "agreement", "treaty", "convention", "protocol", "declaration",
        "framework", "charter", "compact", "accord", "pact", "mou",
        "polar code", "unclos", "paris agreement", "talanoa", "hague",
        "alma-ata", "under2", "common framework", "credentials",
        "sanctions", "embargo",
    ],
    "bilateral_relations": [
        "india-", "india –", "bilateral", "india and china", "india and us",
        "india and russia", "india and pakistan", "india and sri lanka",
        "india and bangladesh", "india and nepal", "india and bhutan",
        "india and myanmar", "india and afghanistan", "india and iran",
        "india and israel", "india and saudi", "india and uae",
        "india and japan", "india and south korea", "india and australia",
        "arab ", "israel", "ukraine", "russia-", "sino-", "instc",
    ],
    "military_exercises": [
        "exercise", "mitra shakti", "yudh abhyas", "tasman sabre",
        "vajra prahar", "shakti", "garuda", "agni warrior", "surya kiran",
        "ekuverin", "nomadic elephant", "hand-in-hand", "dharma guardian",
        "milan ", "indra ", "simbex", "varuna ", "indra-", "prabal dostyk",
        "military", "joint drill", "naval exercise", "air exercise",
        "defence cooperation",
    ],
    "geopolitics_disputes": [
        "senkaku", "south china sea", "east china sea", "taiwan strait",
        "ukraine", "crimea", "gaza", "west bank", "kashmir", "doklam",
        "south tibet", "arunachal", "aksai chin", "strait of hormuz",
        "bosphorus", "suez", "malacca", "migration", "refugee",
        "sanctions", "terrorism", "security council", "veto",
        "polar region", "arctic", "antarctic",
    ],
    "economic_diplomacy": [
        "corridor", "bri ", "belt and road", "instc", "chabahar",
        "trade route", "free trade", "fta ", "upi ", "digital payment",
        "currency swap", "imf quota", "debt relief", "common framework",
        "grains council", "critical mineral", "mineral security",
        "semiconductor", "supply chain", "export control",
    ],
}

# Subjects to search for cross-subject IR questions
CROSS_SUBJECTS = {
    "ir_governance", "current_affairs", "environment", "economy", "geography"
}

# ChromaDB subjects to query for current affairs cross-reference
CHROMA_QUERY_MAP = {
    "ir_governance": {
        "subjects": ["ir_governance"],
        "queries": [
            "international organisations multilateral forums bilateral agreements India",
            "India foreign policy BRICS SCO G20 QUAD ASEAN BIMSTEC",
            "international treaties conventions agreements India UN",
        ],
        "n_results": 8,
    },
    "pib_current_affairs": {
        "subjects": ["current_affairs"],
        "queries": [
            "India bilateral summit agreement MOU foreign policy 2025 2026",
            "India military exercise defence cooperation foreign nations",
            "international organisations India membership UN SCO G20",
            "India foreign relations PIB press information bureau",
        ],
        "n_results": 8,
    },
    "military_exercises": {
        "subjects": ["geography", "current_affairs"],
        "queries": [
            "military exercise India joint bilateral naval air army",
            "places in news military exercises India foreign country",
        ],
        "n_results": 6,
    },
    "economic_survey_budget": {
        "subjects": ["economy"],
        "queries": [
            "India trade agreements international economic cooperation corridor",
            "foreign investment bilateral trade India economic survey",
            "critical minerals supply chain international partnerships India budget",
            "India export import international economic diplomacy",
        ],
        "n_results": 6,
    },
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _db_connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _extract_ir_pyqs(con: sqlite3.Connection) -> list[dict]:
    """Pull all IR-relevant PYQs 2022–2025 from the DB.

    Two passes:
      1. All ir_governance subject questions
      2. Keyword scan across other subjects
    Deduplicates by question_hash or question_text.
    """
    rows = con.execute("""
        SELECT id, year, subject_id, topic_id, subtopic_id,
               question_text, option_a, option_b, option_c, option_d,
               correct_answer, question_hash
        FROM pyq_questions
        WHERE year >= 2022
        ORDER BY year DESC, subject_id
    """).fetchall()

    seen: set[str] = set()
    results: list[dict] = []

    # All keywords flattened for quick scan
    all_keywords = [kw for kws in IR_KEYWORD_GROUPS.values() for kw in kws]

    for r in rows:
        qid = r["question_hash"] or r["id"]
        if qid in seen:
            continue

        is_ir_subject = r["subject_id"] == "ir_governance"
        q_lower = r["question_text"].lower()
        keyword_hit = any(kw in q_lower for kw in all_keywords)

        if not (is_ir_subject or keyword_hit):
            continue
        if r["subject_id"] not in CROSS_SUBJECTS:
            continue

        # Determine cluster
        cluster = _classify_cluster(q_lower)

        seen.add(str(qid))
        results.append({
            "year": r["year"],
            "subject_id": r["subject_id"],
            "subtopic_id": r["subtopic_id"] or "",
            "question_text": r["question_text"],
            "option_a": r["option_a"] or "",
            "option_b": r["option_b"] or "",
            "option_c": r["option_c"] or "",
            "option_d": r["option_d"] or "",
            "correct_answer": r["correct_answer"] or "",
            "cluster": cluster,
        })

    return results


def _classify_cluster(q_lower: str) -> str:
    # Score each cluster by keyword hits; pick the highest
    scores: dict[str, int] = {k: 0 for k in IR_KEYWORD_GROUPS}
    for cluster, keywords in IR_KEYWORD_GROUPS.items():
        for kw in keywords:
            if kw in q_lower:
                scores[cluster] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general_ir"


def _summarise_pyqs(pyqs: list[dict]) -> dict:
    """Compute frequency stats for the analysis prompt."""
    by_year: dict[int, list] = {}
    by_cluster: dict[str, list] = {}
    by_subject: dict[str, int] = {}

    for q in pyqs:
        by_year.setdefault(q["year"], []).append(q)
        by_cluster.setdefault(q["cluster"], []).append(q)
        by_subject[q["subject_id"]] = by_subject.get(q["subject_id"], 0) + 1

    # Detect question format from text patterns
    format_counts = {"statement_based": 0, "match_pairs": 0, "direct_factual": 0}
    for q in pyqs:
        ql = q["question_text"].lower()
        if re.search(r"statement[- ]?[i1]|consider the following statements", ql):
            format_counts["statement_based"] += 1
        elif re.search(r"match|pair|column", ql):
            format_counts["match_pairs"] += 1
        else:
            format_counts["direct_factual"] += 1

    return {
        "total": len(pyqs),
        "by_year": {yr: len(qs) for yr, qs in sorted(by_year.items(), reverse=True)},
        "by_cluster": {cl: len(qs) for cl, qs in sorted(by_cluster.items(), key=lambda x: -len(x[1]))},
        "by_subject": by_subject,
        "question_formats": format_counts,
    }


# ---------------------------------------------------------------------------
# ChromaDB helpers
# ---------------------------------------------------------------------------

def _query_chroma(col: chromadb.Collection, queries: list[str],
                  subject_filter: list[str], n_results: int) -> list[str]:
    """Query ChromaDB across multiple subjects and return unique text chunks."""
    seen_texts: set[str] = set()
    chunks: list[str] = []

    for subject in subject_filter:
        for query in queries:
            try:
                results = col.query(
                    query_texts=[query],
                    n_results=n_results,
                    where={"subject_id": subject},
                )
                for doc in results["documents"][0]:
                    key = doc[:100]
                    if key not in seen_texts and len(doc.strip()) > 50:
                        seen_texts.add(key)
                        chunks.append(doc[:600])
            except Exception:
                continue

    return chunks


def _gather_ca_content(col: chromadb.Collection) -> dict[str, list[str]]:
    """Query ChromaDB for each content category."""
    print("  Querying ChromaDB — IR notes...")
    ir_chunks = _query_chroma(
        col,
        CHROMA_QUERY_MAP["ir_governance"]["queries"],
        CHROMA_QUERY_MAP["ir_governance"]["subjects"],
        CHROMA_QUERY_MAP["ir_governance"]["n_results"],
    )

    print("  Querying ChromaDB — PIB & current affairs...")
    pib_chunks = _query_chroma(
        col,
        CHROMA_QUERY_MAP["pib_current_affairs"]["queries"],
        CHROMA_QUERY_MAP["pib_current_affairs"]["subjects"],
        CHROMA_QUERY_MAP["pib_current_affairs"]["n_results"],
    )

    print("  Querying ChromaDB — military exercises & places in news...")
    mil_chunks = _query_chroma(
        col,
        CHROMA_QUERY_MAP["military_exercises"]["queries"],
        CHROMA_QUERY_MAP["military_exercises"]["subjects"],
        CHROMA_QUERY_MAP["military_exercises"]["n_results"],
    )

    print("  Querying ChromaDB — Economic Survey & Budget...")
    eco_chunks = _query_chroma(
        col,
        CHROMA_QUERY_MAP["economic_survey_budget"]["queries"],
        CHROMA_QUERY_MAP["economic_survey_budget"]["subjects"],
        CHROMA_QUERY_MAP["economic_survey_budget"]["n_results"],
    )

    return {
        "ir_notes": ir_chunks,
        "pib_current_affairs": pib_chunks,
        "military_exercises": mil_chunks,
        "economic_survey_budget": eco_chunks,
    }


# ---------------------------------------------------------------------------
# Sonnet analysis call
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """You are a UPSC Prelims expert analyst. Analyse the provided PYQ data and current affairs content for International Relations (IR) and produce a detailed pattern report.

## INPUT DATA

### PYQ Statistics (2022–2025)
{stats_json}

### All IR-Relevant PYQs 2022–2025 (full text)
{pyqs_text}

### IR Notes & Conceptual Content (from study material)
{ir_notes}

### PIB & Current Affairs Content (2025–2026)
{pib_chunks}

### Military Exercises & Places in News
{mil_chunks}

### Economic Survey & Budget IR Linkages
{eco_chunks}

---

## YOUR TASK

Produce a comprehensive markdown report with these exact sections:

---

# IR Pattern Analysis — UPSC Prelims 2022–2025

## Section 1: Pattern Dashboard

Create a table showing question count per year, then a table for question format breakdown (statement-based / match-pairs / direct factual). Write 3–4 sentences on the overall trend — is UPSC asking more or fewer IR questions? Is the focus shifting? What changed from 2022 to 2025?

## Section 2: Theme-by-Theme Breakdown

For each of these 6 clusters — **Organisations & Forums**, **Agreements & Treaties**, **Bilateral Relations**, **Military Exercises**, **Geopolitics & Disputes**, **Economic Diplomacy** — write:

### [Cluster Name]
**Questions tested (2022–2025):** list the specific orgs/agreements/events that appeared as actual questions
**What UPSC is testing:** exactly what knowledge the questions require (e.g. membership rules, founding year, India's role, specific clause of a treaty)
**Question format pattern:** how questions on this theme are typically framed
**Current affairs linkage (2025–2026):** from the PIB/CA content provided, identify 3–5 specific events, summits, agreements, or developments that are high probability for 2026 Prelims
**Economic Survey / Budget angle:** if the ES or Budget content links to this theme, note the specific data point or scheme

## Section 3: 2026 Prediction List

List 20 high-probability IR topics for 2026 Prelims. Organise into three tiers:

**Tier 1 — Almost Certain (8 topics):** Topics with strong PYQ recency + dense CA coverage in 2025–26
**Tier 2 — High Probability (7 topics):** Topics with clear UPSC interest pattern + current affairs trigger
**Tier 3 — Watch These (5 topics):** Topics not yet tested but aligning with UPSC's expansion of IR scope

For each topic: one line on WHY (PYQ history + current affairs hook + what specific fact UPSC might test).

## Section 4: What UPSC Actually Wants From IR

Write a 200-word synthesis: what cognitive skills does UPSC test through IR questions? (E.g. matching India's role in an org vs knowing org founding facts vs understanding geopolitical significance.) This tells Rahul HOW to study IR, not just WHAT.

## Section 5: All Raw Questions (2022–2025)

List every IR-relevant question with full text, organised by year then cluster. Format:

**[YEAR] [CLUSTER] [SUBTOPIC]**
> [Full question text]
Options: A) ... B) ... C) ... D) ...
Correct: [answer]

---

Be specific. Use actual organisation names, treaty names, and current affairs events from the provided content. Do not be vague or generic. Every prediction must have a specific reason tied to PYQ data or CA content provided.
"""


def _build_pyqs_text(pyqs: list[dict]) -> str:
    lines = []
    for q in pyqs:
        lines.append(
            f"[{q['year']}] [{q['cluster']}] [{q['subtopic_id']}]"
        )
        lines.append(q["question_text"])
        if q["option_a"]:
            lines.append(f"A) {q['option_a']}  B) {q['option_b']}  C) {q['option_c']}  D) {q['option_d']}")
        if q["correct_answer"]:
            lines.append(f"Correct: {q['correct_answer']}")
        lines.append("")
    return "\n".join(lines)


def _truncate_chunks(chunks: list[str], max_chars: int) -> str:
    out = []
    used = 0
    for chunk in chunks:
        if used + len(chunk) > max_chars:
            break
        out.append(chunk.strip())
        used += len(chunk)
    return "\n\n---\n\n".join(out) if out else "(no content retrieved)"


def _run_analysis(pyqs: list[dict], stats: dict,
                  ca_content: dict[str, list[str]]) -> str:
    print("  Calling Claude Sonnet for pattern analysis...")

    prompt = ANALYSIS_PROMPT.format(
        stats_json=json.dumps(stats, indent=2),
        pyqs_text=_build_pyqs_text(pyqs),
        ir_notes=_truncate_chunks(ca_content["ir_notes"], 4000),
        pib_chunks=_truncate_chunks(ca_content["pib_current_affairs"], 4000),
        mil_chunks=_truncate_chunks(ca_content["military_exercises"], 2000),
        eco_chunks=_truncate_chunks(ca_content["economic_survey_budget"], 2500),
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(analysis_text: str, stats: dict, pyq_count: int):
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORTS_DIR / "ir_pattern_2022_2025.md"

    header = (
        f"<!-- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} -->\n"
        f"<!-- PYQs analysed: {pyq_count} questions (2022–2025) -->\n"
        f"<!-- Cost: ~$0.05–0.10 (one Sonnet call) -->\n\n"
    )
    out_path.write_text(header + analysis_text, encoding="utf-8")
    print(f"\n  Report saved → {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n=== IR Pattern Analysis ===\n")

    # 1. Extract PYQs
    print("Step 1: Extracting IR-relevant PYQs (2022–2025)...")
    con = _db_connect()
    pyqs = _extract_ir_pyqs(con)
    con.close()
    stats = _summarise_pyqs(pyqs)

    print(f"  Found {stats['total']} IR-relevant questions")
    print(f"  By year: {stats['by_year']}")
    print(f"  By cluster: {stats['by_cluster']}")

    if stats["total"] == 0:
        print("ERROR: No IR questions found. Check DB_PATH and year filter.")
        sys.exit(1)

    # 2. Gather CA content from ChromaDB
    print("\nStep 2: Querying ChromaDB for current affairs content...")
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    col = chroma_client.get_collection("upsc_content")
    ca_content = _gather_ca_content(col)

    total_chunks = sum(len(v) for v in ca_content.values())
    print(f"  Retrieved {total_chunks} content chunks across 4 categories")

    # 3. Run Sonnet analysis
    print("\nStep 3: Running Sonnet analysis (this takes ~30–60 seconds)...")
    analysis_text = _run_analysis(pyqs, stats, ca_content)

    # 4. Write report
    print("\nStep 4: Writing report...")
    out_path = _write_report(analysis_text, stats, stats["total"])

    print(f"\n=== Done! ===")
    print(f"Open: {out_path}\n")


if __name__ == "__main__":
    main()
