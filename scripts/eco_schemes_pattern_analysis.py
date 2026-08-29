"""
Economics & Government Schemes Pattern Analysis — extracts all Economy/Schemes PYQs
from 2022–2025, cross-references with ChromaDB content (Economic Survey, Budget,
PT365, Current Affairs), and produces a structured pattern report with:
  - Theme-by-theme breakdown
  - Concept Bank (para + bullet traps) for key concepts
  - 2026 prediction list
  - All raw questions

Usage:
    cd /path/to/project && python scripts/eco_schemes_pattern_analysis.py

Output:
    exports/eco_schemes_pattern_2022_2025.md

Cost: ~$0.10–0.15 (one Sonnet call, ~15–20k tokens context)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import chromadb
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH      = os.getenv("DB_PATH", "data/upsc.db")
CHROMA_PATH  = os.getenv("CHROMA_PATH", "vector_store")
PROJECT_ROOT = Path(__file__).parent.parent
EXPORTS_DIR  = PROJECT_ROOT / "exports"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# Theme clusters — keywords to classify PYQs
# ---------------------------------------------------------------------------

THEME_KEYWORD_GROUPS = {
    "monetary_policy_banking": [
        "rbi", "reserve bank", "repo rate", "reverse repo", "slr", "crr",
        "cash reserve", "statutory liquidity", "monetary policy", "mpc ",
        "open market operation", "laf ", "liquidity", "bank rate",
        "nbfc", "non-banking", "scheduled bank", "commercial bank",
        "cooperative bank", "payment bank", "small finance bank",
        "npa ", "bad loan", "asset reconstruction", "credit rating",
        "rtgs", "neft", "imps", "digital payment", "upi", "fintech",
        "sterilisation", "currency", "money supply", "m1", "m2", "m3",
    ],
    "fiscal_policy_budget": [
        "fiscal deficit", "revenue deficit", "primary deficit", "budget",
        "fiscal policy", "frbm", "fiscal responsibility", "capital receipt",
        "revenue receipt", "capital expenditure", "revenue expenditure",
        "disinvestment", "market borrowing", "treasury bill",
        "government bond", "g-sec", "dated securities", "ways and means",
        "contingency fund", "public account", "consolidated fund",
        "finance commission", "tax devolution", "cess ", "surcharge",
        "subsidies", "fiscal federalism",
    ],
    "inflation_price_indices": [
        "inflation", "deflation", "cpi", "wpi", "consumer price",
        "wholesale price", "core inflation", "headline inflation",
        "base effect", "demand pull", "cost push", "stagflation",
        "gdp deflator", "price stability", "inflation targeting",
        "food inflation", "index number",
    ],
    "gdp_national_income": [
        "gdp", "gnp", "nnp", "national income", "per capita",
        "gross domestic product", "gross national", "net national",
        "real gdp", "nominal gdp", "purchasing power parity", "ppp",
        "gva", "gross value added", "base year", "advance estimate",
        "economic growth", "recession", "business cycle",
        "real sector", "financial sector",
    ],
    "agriculture_food_security": [
        "msp", "minimum support price", "procurement", "food corporation",
        "fci ", "buffer stock", "food security", "pds ", "public distribution",
        "agriculture scheme", "pm-kisan", "pm kisan", "kisan", "farmer",
        "crop insurance", "pmfby", "agricultural credit", "kisan credit",
        "green revolution", "white revolution", "blue revolution",
        "yellow revolution", "pink revolution", "silver revolution",
        "gokul", "rashtriya gokul", "e-nam", "enam", "apmc",
        "agriculture infrastructure", "ethanol", "biofuel",
    ],
    "government_schemes_social": [
        "scheme", "yojana", "mission", "programme", "ayushman",
        "jan dhan", "pradhan mantri", "pm-jay", "mudra", "swachh bharat",
        "jal jeevan", "ujjwala", "poshan", "anaemia", "mnrega", "mgnrega",
        "skill india", "pmkvy", "startup india", "stand up india",
        "make in india", "pli scheme", "production linked incentive",
        "digital india", "pmay", "housing for all", "rera",
        "national pension", "nps ", "atal pension", "social security",
        "maternity benefit", "labour code", "insolvency",
        "ibc ", "msme", "gem portal", "government e-marketplace",
    ],
    "financial_markets_investment": [
        "bond", "debenture", "equity", "share", "mutual fund",
        "sebi", "stock exchange", "sensex", "nifty", "ipo",
        "fii", "fpi", "fdi", "portfolio investment", "foreign direct",
        "sovereign wealth", "masala bond", "green bond", "sdl",
        "asset backed", "derivatives", "futures", "options",
        "commodity exchange", "hedge fund", "venture capital",
        "private equity", "angel investor",
    ],
    "external_sector_trade": [
        "balance of payment", "bop", "current account", "capital account",
        "trade deficit", "trade surplus", "exchange rate", "rupee",
        "dollar", "forex", "foreign exchange", "neer", "reer",
        "imf", "world bank", "ibrd", "ifc", "ida ", "miga",
        "wto", "trade agreement", "fta ", "rcep", "export",
        "import", "customs duty", "anti-dumping", "countervailing",
        "current account deficit", "cat", "capital account convertibility",
    ],
    "taxation": [
        "gst", "goods and services tax", "direct tax", "indirect tax",
        "income tax", "corporate tax", "wealth tax", "property tax",
        "customs duty", "excise duty", "service tax",
        "tax reform", "tax structure", "progressive tax", "regressive",
        "tax incidence", "tax buoyancy", "laffer curve",
        "double taxation", "dtaa", "transfer pricing",
    ],
}

# Subjects to scan for cross-subject extraction
SCAN_SUBJECTS = {"economy", "polity", "current_affairs", "environment", "science_tech"}

# Subtopics that are purely economy/scheme regardless of keyword match
ECONOMY_SUBTOPICS = {
    "monetary_policy_rbi", "fiscal_policy_budget", "banking_types_nbfc",
    "agriculture_schemes", "gdp_national_income", "bop_exchange_rate",
    "financial_markets", "msp_food_security", "agriculture_revolutions",
    "digital_payments_fintech", "rbi_functions", "inflation_indices",
    "imf_worldbank", "wto_agreements", "rbi_governance", "india_rankings_reports",
    "direct_indirect_taxes", "gst_structure", "ownership_structures",
    "pli_scheme", "precious_metals_trade", "risk_metrics", "social_sector_schemes",
    "commercial_transactions", "convertible_bonds", "foreign_investment_rules",
    "imf_lending_facilities", "indirect_transfers", "industrial_disputes",
    "inflation_control", "real_vs_financial_sector",
}

# ChromaDB query map
CHROMA_QUERY_MAP = {
    "economic_survey": {
        "subjects": ["economy"],
        "queries": [
            "fiscal deficit revenue deficit capital receipts budget India economic survey",
            "monetary policy RBI repo rate inflation CPI WPI India",
            "GDP growth national income economic indicators India 2025 2026",
            "agriculture MSP food security PDS India economic survey",
            "India trade balance of payment current account deficit exchange rate",
            "banking sector NPA NBFC financial inclusion India",
        ],
        "n_results": 10,
    },
    "budget_schemes": {
        "subjects": ["economy", "current_affairs"],
        "queries": [
            "government scheme yojana mission pradhan mantri budget 2025 2026",
            "PLI production linked incentive scheme India budget allocation",
            "MSME startup digital India make in India government scheme",
            "social sector spending health education housing scheme India budget",
            "agriculture scheme PM-KISAN crop insurance MSP food security budget",
        ],
        "n_results": 8,
    },
    "current_affairs_economy": {
        "subjects": ["current_affairs"],
        "queries": [
            "India economic policy reform scheme launch 2025 2026",
            "PIB government scheme announcement India 2025",
            "India financial sector reform digital payment UPI fintech",
        ],
        "n_results": 6,
    },
    "pt365_economy": {
        "subjects": ["economy"],
        "queries": [
            "UPSC prelims economy current affairs important concept 2026",
            "India economic survey budget key highlights prelims 2026",
            "monetary policy fiscal policy important terms UPSC economy",
            "government flagship scheme important facts UPSC prelims",
        ],
        "n_results": 8,
    },
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _db_connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _extract_eco_pyqs(con: sqlite3.Connection) -> list[dict]:
    """Pull all Economy + Government Scheme PYQs 2022–2025."""
    rows = con.execute("""
        SELECT id, year, subject_id, topic_id, subtopic_id,
               question_text, option_a, option_b, option_c, option_d,
               correct_answer, question_hash
        FROM pyq_questions
        WHERE year >= 2022
        ORDER BY year DESC, subject_id
    """).fetchall()

    all_keywords = [kw for kws in THEME_KEYWORD_GROUPS.values() for kw in kws]
    seen: set[str] = set()
    results: list[dict] = []

    for r in rows:
        qid = r["question_hash"] or str(r["id"])
        if qid in seen:
            continue

        is_economy_subject = r["subject_id"] == "economy"
        is_economy_subtopic = r["subtopic_id"] in ECONOMY_SUBTOPICS
        q_lower = r["question_text"].lower()
        keyword_hit = any(kw in q_lower for kw in all_keywords)

        if not (is_economy_subject or is_economy_subtopic or keyword_hit):
            continue
        if r["subject_id"] not in SCAN_SUBJECTS:
            continue

        seen.add(qid)
        cluster = _classify_cluster(q_lower, r["subtopic_id"])

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


def _classify_cluster(q_lower: str, subtopic_id: str) -> str:
    # Subtopic-based fast path
    subtopic_map = {
        "monetary_policy_rbi": "monetary_policy_banking",
        "rbi_functions": "monetary_policy_banking",
        "rbi_governance": "monetary_policy_banking",
        "banking_types_nbfc": "monetary_policy_banking",
        "digital_payments_fintech": "monetary_policy_banking",
        "fiscal_policy_budget": "fiscal_policy_budget",
        "gdp_national_income": "gdp_national_income",
        "real_vs_financial_sector": "gdp_national_income",
        "inflation_indices": "inflation_price_indices",
        "bop_exchange_rate": "external_sector_trade",
        "imf_worldbank": "external_sector_trade",
        "wto_agreements": "external_sector_trade",
        "foreign_investment_rules": "external_sector_trade",
        "financial_markets": "financial_markets_investment",
        "agriculture_schemes": "agriculture_food_security",
        "agriculture_revolutions": "agriculture_food_security",
        "msp_food_security": "agriculture_food_security",
        "social_sector_schemes": "government_schemes_social",
        "pli_scheme": "government_schemes_social",
        "direct_indirect_taxes": "taxation",
        "gst_structure": "taxation",
    }
    if subtopic_id in subtopic_map:
        return subtopic_map[subtopic_id]

    scores: dict[str, int] = {k: 0 for k in THEME_KEYWORD_GROUPS}
    for cluster, keywords in THEME_KEYWORD_GROUPS.items():
        for kw in keywords:
            if kw in q_lower:
                scores[cluster] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general_economy"


def _summarise_pyqs(pyqs: list[dict]) -> dict:
    by_year: dict[int, int] = {}
    by_cluster: dict[str, int] = {}
    by_subject: dict[str, int] = {}
    format_counts = {"statement_based": 0, "match_pairs": 0, "direct_factual": 0,
                     "how_many": 0}

    for q in pyqs:
        by_year[q["year"]] = by_year.get(q["year"], 0) + 1
        by_cluster[q["cluster"]] = by_cluster.get(q["cluster"], 0) + 1
        by_subject[q["subject_id"]] = by_subject.get(q["subject_id"], 0) + 1

        ql = q["question_text"].lower()
        if re.search(r"how many of the following", ql):
            format_counts["how_many"] += 1
        elif re.search(r"statement[- ]?[i1]|consider the following statements", ql):
            format_counts["statement_based"] += 1
        elif re.search(r"match|pair|column", ql):
            format_counts["match_pairs"] += 1
        else:
            format_counts["direct_factual"] += 1

    # Subtopic frequency for concept bank decisions
    subtopic_freq = Counter(q["subtopic_id"] for q in pyqs)

    return {
        "total": len(pyqs),
        "by_year": dict(sorted(by_year.items(), reverse=True)),
        "by_cluster": dict(sorted(by_cluster.items(), key=lambda x: -x[1])),
        "by_subject": by_subject,
        "question_formats": format_counts,
        "subtopic_frequency": dict(subtopic_freq.most_common(20)),
    }


# ---------------------------------------------------------------------------
# ChromaDB helpers
# ---------------------------------------------------------------------------

def _query_chroma(col: chromadb.Collection, queries: list[str],
                  subject_filter: list[str], n_results: int) -> list[str]:
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
                        chunks.append(doc[:700])
            except Exception:
                continue
    return chunks


def _gather_content(col: chromadb.Collection) -> dict[str, list[str]]:
    print("  Querying ChromaDB — Economic Survey 2024-25 & 2025-26...")
    es_chunks = _query_chroma(
        col,
        CHROMA_QUERY_MAP["economic_survey"]["queries"],
        CHROMA_QUERY_MAP["economic_survey"]["subjects"],
        CHROMA_QUERY_MAP["economic_survey"]["n_results"],
    )

    print("  Querying ChromaDB — Budget & Schemes...")
    budget_chunks = _query_chroma(
        col,
        CHROMA_QUERY_MAP["budget_schemes"]["queries"],
        CHROMA_QUERY_MAP["budget_schemes"]["subjects"],
        CHROMA_QUERY_MAP["budget_schemes"]["n_results"],
    )

    print("  Querying ChromaDB — Current Affairs economy...")
    ca_chunks = _query_chroma(
        col,
        CHROMA_QUERY_MAP["current_affairs_economy"]["queries"],
        CHROMA_QUERY_MAP["current_affairs_economy"]["subjects"],
        CHROMA_QUERY_MAP["current_affairs_economy"]["n_results"],
    )

    print("  Querying ChromaDB — PT365 Economy...")
    pt_chunks = _query_chroma(
        col,
        CHROMA_QUERY_MAP["pt365_economy"]["queries"],
        CHROMA_QUERY_MAP["pt365_economy"]["subjects"],
        CHROMA_QUERY_MAP["pt365_economy"]["n_results"],
    )

    return {
        "economic_survey": es_chunks,
        "budget_schemes": budget_chunks,
        "current_affairs": ca_chunks,
        "pt365": pt_chunks,
    }


# ---------------------------------------------------------------------------
# Sonnet prompt
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """You are a UPSC Prelims expert analyst. Analyse the Economics and Government Schemes PYQ data and study content below, then produce a comprehensive pattern report.

## INPUT DATA

### PYQ Statistics (2022–2025)
{stats_json}

### All Economics & Schemes PYQs 2022–2025 (full text)
{pyqs_text}

### Economic Survey Content (2024–25 & 2025–26)
{es_chunks}

### Budget 2025–26 & Government Schemes Content
{budget_chunks}

### PT365 Economy & Current Affairs
{pt_chunks}

### Additional Current Affairs Economy Content
{ca_chunks}

---

## YOUR TASK

Produce a comprehensive markdown report with the exact sections below. Be specific — use real scheme names, real figures, real clause numbers. No vague generalisations.

---

# Economics & Government Schemes — UPSC Prelims Pattern Analysis 2022–2025

---

## Section 1: Pattern Dashboard

**Table 1: Question Count Per Year**
| Year | Economy Qs | Format Breakdown | Notable Shift |

**Table 2: Theme Distribution (2022–2025)**
| Theme | Question Count | Key Subtopics Tested |

**Overall Trend (4–5 sentences):** What is UPSC's direction in economics? Is it moving toward application/analysis or pure facts? What changed between 2022 and 2025?

---

## Section 2: Theme-by-Theme Breakdown

Cover all 8 themes in this order. For each:

### [Theme Name]

**Questions tested (2022–2025):** bullet list of specific topics/concepts that actually appeared as PYQs

**What UPSC is testing:** the exact cognitive skill — definition precision, numerical threshold knowledge, India-specific application of a concept, scheme eligibility conditions, etc.

**Question format pattern:** how these questions are framed (statement-based vs direct vs pairs) and what the traps look like

**Current affairs linkage (2025–2026):** 3–4 specific Economic Survey data points, Budget announcements, or policy changes that create 2026 Prelims triggers — cite specific figures or scheme names from the content provided

**Prediction for 2026:** 2–3 most likely questions from this theme

---

Themes to cover:
1. Monetary Policy & Banking (RBI, repo, CRR/SLR, NBFC, digital payments)
2. Fiscal Policy & Budget (deficit types, capital/revenue classification, FRBM, devolution)
3. Inflation & Price Indices (CPI, WPI, core inflation, base effect)
4. GDP & National Income (measurement, real vs nominal, GVA, sector classification)
5. Agriculture & Food Security (MSP, PDS, crop insurance, Gokul Mission, ethanol, e-NAM)
6. Government Schemes & Social Sector (PM flagship schemes, PLI, MSME, labour codes, IBC)
7. Financial Markets & Investment (bonds, mutual funds, SEBI, FDI/FII, Masala bonds)
8. External Sector & Trade (BOP, exchange rate, IMF, WTO, current account)
9. Taxation (GST structure, direct/indirect tax, DTAA, tax incidence)

---

## Section 3: Concept Bank

This is the critical section. For each concept in the list below, provide:

**Concept Name**

*[4–6 sentence paragraph explaining what the concept is, why it matters for India's economy, and exactly how UPSC tests it — written as a clear explanation, not bullet points]*

**UPSC Traps:**
- Trap 1: [specific wrong belief UPSC exploits]
- Trap 2: [another common confusion]
- Trap 3 (if applicable): [third trap]

---

Mandatory concepts to cover (these appeared frequently or are analytically complex):

**Monetary Policy Concepts:**
1. Repo Rate vs Reverse Repo Rate vs Bank Rate vs MSF
2. CRR vs SLR — purpose, current levels, who decides
3. Open Market Operations (OMO) vs Market Stabilisation Scheme (MSS)
4. Types of Banks — scheduled, commercial, cooperative, payment, small finance
5. NBFC — definition, regulatory differences from banks, shadow banking concern
6. Sterilisation of Capital Flows

**Fiscal Policy Concepts:**
7. Revenue Deficit vs Fiscal Deficit vs Primary Deficit vs Effective Revenue Deficit
8. Capital Receipts vs Revenue Receipts — classification of borrowings, disinvestment, dividends
9. Capital Expenditure vs Revenue Expenditure
10. FRBM Act — targets, escape clauses, fiscal council
11. Finance Commission vs Planning Commission/NITI Aayog — who decides what

**Inflation & GDP Concepts:**
12. CPI vs WPI — what they measure, base year, who releases
13. Core Inflation vs Headline Inflation
14. Base Effect in inflation calculation
15. GDP vs GNP vs NNP vs GVA — what each measures, which India uses for budgeting
16. Real GDP vs Nominal GDP — deflator, purchasing power parity

**Agriculture Concepts:**
17. MSP — who recommends, who announces, how computed (A2, FL, C2)
18. Procurement vs Open Market Availability — FCI's dual role
19. e-NAM — how it works, who manages, linkage to APMC reform
20. PM-KISAN — eligibility, exclusions, amount, DBT mechanism
21. PMFBY (crop insurance) — premium sharing, actuarial premium concept

**Government Scheme Concepts:**
22. PLI (Production Linked Incentive) — how it works, which sectors, Budget 2025 updates
23. IBC (Insolvency and Bankruptcy Code) — NCLT, NCLAT, timelines, waterfall mechanism
24. MUDRA Loans — Shishu/Kishore/Tarun tiers, who lends, collateral rule
25. Jan Dhan Yojana — key features, overdraft facility, linkage to DBT

**Financial Market Concepts:**
26. FDI vs FPI/FII — definitions, automatic vs approval route, sectoral caps
27. Masala Bonds — who issues, in which currency, denominated in rupees
28. Green Bonds / Sovereign Green Bonds — India's issuance, use of proceeds
29. T-Bills vs G-Secs vs SDL — tenure, issuer, who can buy

**External Sector Concepts:**
30. Current Account vs Capital Account in BOP — what goes where
31. CAD (Current Account Deficit) — components, India's typical CAD, Economic Survey figure
32. NEER vs REER — nominal vs real effective exchange rate, what depreciation means

**Taxation Concepts:**
33. GST — CGST/SGST/IGST structure, GST Council voting, compensation cess
34. Direct vs Indirect Tax — incidence vs impact, progressive vs regressive nature
35. Tax Buoyancy — definition, India's buoyancy target

---

## Section 4: 2026 Prediction List

### Tier 1 — Almost Certain (8 topics)
With specific reasoning: PYQ frequency + Economic Survey/Budget data point that creates the 2026 trigger.

### Tier 2 — High Probability (6 topics)
With specific reasoning tied to recent policy changes.

### Tier 3 — Watch These (4 topics)
Emerging themes UPSC hasn't tested yet but is moving toward.

---

## Section 5: How UPSC Tests Economics

200-word synthesis on the cognitive architecture of economics questions — what skills are tested beyond memorisation, and what study approach this demands.

---

## Section 6: All Raw Questions (2022–2025)

List every question with full text, organised by year then theme. Format:

**[YEAR] [THEME] [SUBTOPIC]**
> [Full question text]
Options: A) ... B) ... C) ... D) ...
Correct: [answer if available]

---

IMPORTANT: In the Concept Bank section, write every concept explanation as if teaching a smart student who knows nothing — be clear, be precise, include specific numbers and thresholds (e.g., CRR is currently X%, repo rate is Y%), and always anchor the trap to an actual UPSC question pattern observed in the PYQs provided.
"""


def _build_pyqs_text(pyqs: list[dict]) -> str:
    lines = []
    current_year = None
    for q in sorted(pyqs, key=lambda x: (-x["year"], x["cluster"])):
        if q["year"] != current_year:
            current_year = q["year"]
            lines.append(f"\n### {current_year}\n")
        lines.append(f"[{q['cluster']}] [{q['subtopic_id']}]")
        lines.append(q["question_text"])
        if q["option_a"]:
            lines.append(
                f"A) {q['option_a']}  B) {q['option_b']}  "
                f"C) {q['option_c']}  D) {q['option_d']}"
            )
        if q["correct_answer"]:
            lines.append(f"Correct: {q['correct_answer']}")
        lines.append("")
    return "\n".join(lines)


def _truncate_chunks(chunks: list[str], max_chars: int) -> str:
    out: list[str] = []
    used = 0
    for chunk in chunks:
        if used + len(chunk) > max_chars:
            break
        out.append(chunk.strip())
        used += len(chunk)
    return "\n\n---\n\n".join(out) if out else "(no content retrieved)"


def _run_analysis(pyqs: list[dict], stats: dict,
                  content: dict[str, list[str]]) -> str:
    print("  Calling Claude Sonnet for analysis (this takes 60–90 seconds)...")

    prompt = ANALYSIS_PROMPT.format(
        stats_json=json.dumps(stats, indent=2),
        pyqs_text=_build_pyqs_text(pyqs),
        es_chunks=_truncate_chunks(content["economic_survey"], 5000),
        budget_chunks=_truncate_chunks(content["budget_schemes"], 4000),
        pt_chunks=_truncate_chunks(content["pt365"], 3000),
        ca_chunks=_truncate_chunks(content["current_affairs"], 2000),
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=12000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(analysis_text: str, pyq_count: int) -> Path:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORTS_DIR / "eco_schemes_pattern_2022_2025.md"
    header = (
        f"<!-- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} -->\n"
        f"<!-- PYQs analysed: {pyq_count} questions (2022–2025) -->\n"
        f"<!-- Covers: Economy (primary) + cross-subject scheme/fiscal questions -->\n\n"
    )
    out_path.write_text(header + analysis_text, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n=== Economics & Government Schemes Pattern Analysis ===\n")

    print("Step 1: Extracting PYQs (2022–2025)...")
    con = _db_connect()
    pyqs = _extract_eco_pyqs(con)
    con.close()
    stats = _summarise_pyqs(pyqs)

    print(f"  Found {stats['total']} questions")
    print(f"  By year: {stats['by_year']}")
    print(f"  By cluster: {stats['by_cluster']}")

    if stats["total"] == 0:
        print("ERROR: No questions found. Check DB_PATH.")
        sys.exit(1)

    print("\nStep 2: Querying ChromaDB...")
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    col = chroma_client.get_collection("upsc_content")
    content = _gather_content(col)
    total_chunks = sum(len(v) for v in content.values())
    print(f"  Retrieved {total_chunks} content chunks")

    print("\nStep 3: Running Sonnet analysis...")
    analysis_text = _run_analysis(pyqs, stats, content)

    print("\nStep 4: Writing report...")
    out_path = _write_report(analysis_text, stats["total"])
    print(f"  Report saved → {out_path}")

    print(f"\n=== Done! ===")
    print(f"Open: {out_path}\n")


if __name__ == "__main__":
    main()
