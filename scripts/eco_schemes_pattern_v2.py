"""
eco_schemes_pattern_v2.py — Economics & Government Schemes Pattern Analysis (v2)

Architecture improvements over v1:
  • Haiku analyzes each PYQ individually: maps to canonical concept, extracts
    cognitive skill, and traces what each wrong option exploits
  • ChromaDB queries are concept-targeted (not broad generic dumps)
  • Sonnet is called once per theme (~4-6 concepts), with focused context only
  • Synthesis call receives compact processed signal, not raw noise
  • Concept Bank traps are derived from actual wrong options in real questions

Usage:
    cd /path/to/project && python scripts/eco_schemes_pattern_v2.py
    python scripts/eco_schemes_pattern_v2.py --reset-cache   # force re-run Haiku

Outputs:
    exports/eco_schemes_pattern_v2.md
    cache/eco_pyq_analysis.json   (reusable Haiku cache)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
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
CACHE_DIR    = PROJECT_ROOT / "cache"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ---------------------------------------------------------------------------
# Canonical concept taxonomy
# Each entry: desc (shown to Haiku for mapping), theme (Sonnet grouping),
#             query (targeted ChromaDB retrieval string)
# ---------------------------------------------------------------------------
CANONICAL_CONCEPTS: dict[str, dict] = {
    # Monetary Policy & Banking
    "repo_bank_rate_msf": {
        "desc": "Repo rate, reverse repo, MSF, bank rate — RBI policy rates, rate corridor, relationships",
        "theme": "Monetary Policy & Banking",
        "query": "repo rate MSF bank rate reverse repo RBI liquidity corridor SDF",
    },
    "crr_slr": {
        "desc": "CRR and SLR — purpose, what counts toward each, current levels, who decides",
        "theme": "Monetary Policy & Banking",
        "query": "CRR SLR cash reserve ratio statutory liquidity ratio RBI banks interest",
    },
    "omo_mss_sterilisation": {
        "desc": "OMO vs MSS vs sterilisation — how RBI manages liquidity and neutralises capital inflow impact",
        "theme": "Monetary Policy & Banking",
        "query": "open market operations MSS sterilisation capital inflows RBI G-sec",
    },
    "bank_types": {
        "desc": "Scheduled, commercial, cooperative, payments bank, small finance bank — definitions and distinctions",
        "theme": "Monetary Policy & Banking",
        "query": "payment bank small finance bank cooperative scheduled commercial bank India",
    },
    "nbfc": {
        "desc": "NBFC — what NBFCs can and cannot do vs banks, LAF access, shadow banking, NBFC-MFI",
        "theme": "Monetary Policy & Banking",
        "query": "NBFC non-banking financial company deposit LAF shadow banking regulation",
    },
    "digital_payments": {
        "desc": "UPI, RTGS, NEFT, IMPS — settlement timing, charges, limits, CBDC",
        "theme": "Monetary Policy & Banking",
        "query": "UPI RTGS NEFT IMPS digital payment settlement charges India RBI",
    },
    # Fiscal Policy & Budget
    "deficit_types": {
        "desc": "Revenue deficit, fiscal deficit, primary deficit, effective revenue deficit — what each excludes",
        "theme": "Fiscal Policy & Budget",
        "query": "revenue deficit fiscal deficit primary deficit effective revenue India budget",
    },
    "receipts_classification": {
        "desc": "Capital receipts vs revenue receipts — where borrowings, disinvestment, taxes, and grants fall",
        "theme": "Fiscal Policy & Budget",
        "query": "capital receipts revenue receipts government budget disinvestment borrowing grant",
    },
    "expenditure_classification": {
        "desc": "Capital vs revenue expenditure — asset-creation criterion, plan vs non-plan",
        "theme": "Fiscal Policy & Budget",
        "query": "capital expenditure revenue expenditure asset creation government spending India",
    },
    "frbm": {
        "desc": "FRBM Act — fiscal deficit target, escape clauses, Medium Term Fiscal Policy Statement",
        "theme": "Fiscal Policy & Budget",
        "query": "FRBM fiscal responsibility budget management act escape clause India target",
    },
    "finance_commission": {
        "desc": "Finance Commission — constitutional role, devolution formula, grants-in-aid vs NITI Aayog",
        "theme": "Fiscal Policy & Budget",
        "query": "Finance Commission tax devolution grants states India Article 280 NITI",
    },
    # Inflation & GDP
    "cpi_wpi": {
        "desc": "CPI vs WPI — what they measure, base year, who releases, India's inflation targeting anchor",
        "theme": "Inflation & GDP",
        "query": "CPI WPI consumer price index wholesale price India base year release CSO",
    },
    "core_headline_inflation": {
        "desc": "Core vs headline inflation, base effect, demand-pull vs cost-push",
        "theme": "Inflation & GDP",
        "query": "core inflation headline inflation base effect food fuel India",
    },
    "gdp_gva_national_income": {
        "desc": "GDP, GNP, NNP, GVA — measurement approaches, factor cost vs market price, what India uses",
        "theme": "Inflation & GDP",
        "query": "GDP GVA GNP NNP national income India factor cost market price measurement",
    },
    "real_nominal_gdp": {
        "desc": "Real vs nominal GDP, GDP deflator, PPP, advance estimate schedule",
        "theme": "Inflation & GDP",
        "query": "real GDP nominal GDP deflator purchasing power parity advance estimate India",
    },
    # Agriculture & Food Security
    "msp_computation": {
        "desc": "MSP — CACP recommends, Cabinet announces, A2 vs A2+FL vs C2 cost formula, which crops",
        "theme": "Agriculture & Food Security",
        "query": "MSP minimum support price CACP A2 FL C2 formula kharif rabi India",
    },
    "fci_pds_buffer": {
        "desc": "FCI roles, PDS entitlements under NFSA, buffer stock norms",
        "theme": "Agriculture & Food Security",
        "query": "FCI food corporation buffer stock PDS public distribution NFSA procurement",
    },
    "enam_apmc": {
        "desc": "e-NAM — online agricultural market, SFAC manages, APMC reform requirement",
        "theme": "Agriculture & Food Security",
        "query": "e-NAM online agriculture market SFAC APMC reform India",
    },
    "pmkisan": {
        "desc": "PM-KISAN — Rs 6000/year in three instalments, eligibility exclusions, DBT linkage",
        "theme": "Agriculture & Food Security",
        "query": "PM-KISAN farmer income support 6000 exclusions DBT land record India",
    },
    "pmfby": {
        "desc": "PMFBY — actuarial vs farmer premium, government subsidy split, voluntary since 2020",
        "theme": "Agriculture & Food Security",
        "query": "PMFBY crop insurance actuarial premium kharif rabi farmer state centre India",
    },
    # Government Schemes
    "pli_scheme": {
        "desc": "PLI — incentive on incremental sales over base year, eligible sectors, Budget 2025 allocation",
        "theme": "Government Schemes",
        "query": "PLI production linked incentive scheme sectors India Budget allocation",
    },
    "ibc_insolvency": {
        "desc": "IBC — NCLT adjudicates, NCLAT appellate, 180+90-day timeline, waterfall for proceeds",
        "theme": "Government Schemes",
        "query": "IBC insolvency bankruptcy NCLT NCLAT waterfall timeline India resolution",
    },
    "mudra_loans": {
        "desc": "MUDRA — Shishu (≤50k), Kishore (50k-5L), Tarun (5L-10L), Tarun Plus (10L-20L, Budget 2024)",
        "theme": "Government Schemes",
        "query": "MUDRA Shishu Kishore Tarun loan microfinance collateral India tier",
    },
    "jandhan_dbt": {
        "desc": "PMJDY — zero-balance account, RuPay card, Rs 10000 overdraft, backbone of DBT",
        "theme": "Government Schemes",
        "query": "Jan Dhan PMJDY zero balance overdraft RuPay DBT India",
    },
    # Financial Markets
    "fdi_fpi": {
        "desc": "FDI vs FPI — 10% equity threshold, automatic vs government approval route, sectoral caps",
        "theme": "Financial Markets",
        "query": "FDI FPI FII 10 percent threshold automatic approval route sectoral cap India",
    },
    "masala_green_bonds": {
        "desc": "Masala bonds (rupee-denominated offshore) vs Sovereign Green Bonds — issuer, currency risk, proceeds",
        "theme": "Financial Markets",
        "query": "masala bond sovereign green bond rupee denominated offshore India proceeds",
    },
    "government_securities": {
        "desc": "T-bills (91/182/364-day, zero coupon), G-secs (dated, coupon), SDL (state governments)",
        "theme": "Financial Markets",
        "query": "treasury bill T-bill G-sec dated securities SDL state development loan tenure",
    },
    # External Sector & Trade
    "bop_accounts": {
        "desc": "BOP — current account (goods + services + transfers) vs capital account vs financial account",
        "theme": "External Sector & Trade",
        "query": "balance of payments current account capital financial account India BOP structure",
    },
    "current_account_deficit": {
        "desc": "CAD — merchandise trade deficit + net invisibles + transfers; India's typical CAD/GDP",
        "theme": "External Sector & Trade",
        "query": "current account deficit CAD India merchandise invisibles remittances GDP",
    },
    "neer_reer": {
        "desc": "NEER (not inflation-adjusted) vs REER (inflation-adjusted); REER > 100 = overvalued",
        "theme": "External Sector & Trade",
        "query": "NEER REER nominal real effective exchange rate depreciation overvalued India",
    },
    # Taxation
    "gst_structure": {
        "desc": "GST — CGST/SGST (intrastate) vs IGST (interstate); GST Council voting (3/4 majority); compensation cess",
        "theme": "Taxation",
        "query": "GST CGST SGST IGST council voting three-fourth majority compensation cess India",
    },
    "direct_indirect_tax": {
        "desc": "Direct tax (incidence = impact) vs indirect (shiftable); progressive vs regressive",
        "theme": "Taxation",
        "query": "direct tax indirect tax incidence impact progressive regressive India",
    },
    "tax_buoyancy": {
        "desc": "Tax buoyancy — % change in tax revenue / % change in GDP; buoyancy > 1 = tax grows faster than GDP",
        "theme": "Taxation",
        "query": "tax buoyancy elasticity GDP tax revenue India ratio target",
    },
    # Concepts missing from initial taxonomy — added after first run
    "rbi_income_functions": {
        "desc": "RBI income sources (interest on G-secs/forex reserves, printing charges), surplus/dividend transfer to government, Contingency Risk Buffer threshold",
        "theme": "Monetary Policy & Banking",
        "query": "RBI income sources surplus transfer government contingency risk buffer dividend",
    },
    "imf_facilities_sdr": {
        "desc": "IMF lending facilities (SBA, EFF, RCF, RFI); SDR as accounting unit not currency; India's IMF quota and voting share",
        "theme": "External Sector & Trade",
        "query": "IMF lending facility SDR special drawing rights RCF RFI India quota reserve tranche",
    },
    "money_capital_markets": {
        "desc": "Money market (< 1 year: T-bills, CP, CDs, CBLO/TREPS, call money) vs capital market (equities, bonds, debentures, G-secs)",
        "theme": "Financial Markets",
        "query": "money market capital market instruments T-bills commercial paper equity bonds India",
    },
    "cblo_treps": {
        "desc": "CBLO (Collateral Borrowing and Lending Obligation) — secured money market instrument using G-secs as collateral; replaced by TREPS in 2018",
        "theme": "Financial Markets",
        "query": "CBLO collateral borrowing lending TREPS money market India secured G-sec",
    },
    "social_security_schemes": {
        "desc": "PM-SYM (unorganised workers pension, ₹3000/month at 60, entry 18-40), APY, PM Surakshit Matritva Abhiyan (free antenatal care on 9th of month)",
        "theme": "Government Schemes",
        "query": "PM-SYM APY unorganised workers pension insurance Surakshit Matritva Abhiyan India",
    },
    "black_money_benami": {
        "desc": "Black Money Act 2015 (foreign undisclosed assets/income), Benami Transactions Prohibition Act 1988 amended 2016 — which agency investigates each, attachment powers",
        "theme": "Fiscal Policy & Budget",
        "query": "black money benami act undisclosed income foreign assets ED attachment India",
    },
}

# Compact concept list for Haiku prompt
_CONCEPTS_LIST = "\n".join(
    f"{cid}: {data['desc']}" for cid, data in CANONICAL_CONCEPTS.items()
)

# Theme → [concept_ids] grouping
_THEME_CONCEPTS: dict[str, list[str]] = defaultdict(list)
for _cid, _cdata in CANONICAL_CONCEPTS.items():
    _THEME_CONCEPTS[_cdata["theme"]].append(_cid)


# ---------------------------------------------------------------------------
# PYQ extraction (same logic as v1, slightly tightened)
# ---------------------------------------------------------------------------

_ECO_SUBJECTS = {"economy", "polity", "current_affairs", "environment", "science_tech"}

_ECO_SUBTOPICS = {
    "monetary_policy_rbi", "fiscal_policy_budget", "banking_types_nbfc",
    "agriculture_schemes", "gdp_national_income", "bop_exchange_rate",
    "financial_markets", "msp_food_security", "agriculture_revolutions",
    "digital_payments_fintech", "rbi_functions", "inflation_indices",
    "imf_worldbank", "wto_agreements", "social_sector_schemes", "pli_scheme",
    "direct_indirect_taxes", "gst_structure", "real_vs_financial_sector",
    "rbi_governance", "india_rankings_reports", "ownership_structures",
    "foreign_investment_rules", "commercial_transactions",
}

_ECO_KEYWORDS = [
    # Core monetary/fiscal
    "rbi", "repo rate", "monetary policy", "fiscal deficit", "gdp", "inflation",
    "cpi ", "wpi ", "msp ", "pds ", "mudra", "jan dhan", "pmkisan", "sebi",
    "gst ", "fdi ", "fpi ", "wto ", "balance of payment", "nbfc", "frbm",
    "ibc ", "nclt", "pli scheme", "finance commission", "disinvestment",
    "exchange rate", "current account", "tax buoyancy", "masala bond",
    "treasury bill", "g-sec", "neer ", "reer ", "pmfby", "enam",
    "bank rate", "crr ", "slr ", "open market", "sterilisation",
    "payment bank", "small finance", "omo ", "mss ", "cblo", "treps",
    # Government schemes & social sector
    "scheme", "yojana", "mission ", "programme", "pradhan mantri", "pm-",
    "ayushman", "ujjwala", "swachh bharat", "jal jeevan", "poshan",
    "mnrega", "mgnrega", "skill india", "startup india", "stand up india",
    "make in india", "digital india", "pmay", "rera ", "pm-sym", "pm sym",
    "matritva", "antenatal", "social security", "pension ", "atal pension",
    "national pension", "nps ", "labour code", "insolvency",
    # Financial instruments & markets
    "bond ", "debenture", "equity ", "mutual fund", "ipo ", "sdl ",
    "collateral", "money market", "capital market",
    # External sector & international
    "imf ", "world bank", "ibrd", "ida ", "sdl ", "sdr ",
    "rapid financing", "rapid credit", "reserve tranche",
    # Other economy terms
    "beta ", "black money", "benami", "indirect transfer",
    "total fertility", "fiscal federalism", "cess ", "surcharge",
]


def _extract_pyqs(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute("""
        SELECT id, year, subject_id, topic_id, subtopic_id,
               question_text, option_a, option_b, option_c, option_d,
               correct_answer, question_hash
        FROM pyq_questions
        WHERE year >= 2022
        ORDER BY year DESC
    """).fetchall()

    seen: set[str] = set()
    results: list[dict] = []

    for r in rows:
        qid = r["question_hash"] or str(r["id"])
        if qid in seen:
            continue
        if r["subject_id"] not in _ECO_SUBJECTS:
            continue

        q_lower = r["question_text"].lower()
        is_eco = (
            r["subject_id"] == "economy"
            or r["subtopic_id"] in _ECO_SUBTOPICS
            or any(kw in q_lower for kw in _ECO_KEYWORDS)
        )
        if not is_eco:
            continue

        seen.add(qid)
        results.append({
            "id": str(r["id"]),
            "year": r["year"],
            "subject_id": r["subject_id"],
            "subtopic_id": r["subtopic_id"] or "",
            "question_text": r["question_text"],
            "option_a": r["option_a"] or "",
            "option_b": r["option_b"] or "",
            "option_c": r["option_c"] or "",
            "option_d": r["option_d"] or "",
            "correct_answer": r["correct_answer"] or "",
        })

    return results


# ---------------------------------------------------------------------------
# Haiku: per-question concept analysis
# ---------------------------------------------------------------------------

_HAIKU_PROMPT = """\
Analyze these UPSC Prelims economics/schemes questions. Return ONLY a JSON array — no markdown fences, no explanation.

Map each question to a concept from this taxonomy (use the concept_id exactly as listed):
{concepts_list}

For each question return one JSON object:
{{
  "q_index": <0-based integer>,
  "concept_id": "<exact id from taxonomy, or 'other_<shortword>' if genuinely not covered>",
  "cognitive_skill": "<one of: definition_recall | threshold_knowledge | concept_relationship | india_application | elimination_logic>",
  "correct_reasoning": "<one sentence: why the correct answer is right>",
  "traps": {{"<wrong_option_letter>": "<misconception this option exploits>"}},
  "key_facts": ["<specific fact 1>", "<specific fact 2>"]
}}

Questions:
{questions_block}

Return ONLY the JSON array."""


def _fmt_question_block(questions: list[dict]) -> str:
    parts = []
    for i, q in enumerate(questions):
        lines = [f"[Q{i}] Year: {q['year']} | subtopic: {q['subtopic_id']}"]
        lines.append(q["question_text"])
        if q["option_a"]:
            lines += [
                f"A) {q['option_a']}",
                f"B) {q['option_b']}",
                f"C) {q['option_c']}",
                f"D) {q['option_d']}",
            ]
        if q["correct_answer"]:
            lines.append(f"Correct: {q['correct_answer']}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _parse_json_safe(text: str) -> list:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return []


def _haiku_batch(questions: list[dict], batch_start: int) -> list[dict]:
    prompt = _HAIKU_PROMPT.format(
        concepts_list=_CONCEPTS_LIST,
        questions_block=_fmt_question_block(questions),
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        items = _parse_json_safe(resp.content[0].text)
        for item in items:
            item["q_index"] = batch_start + int(item.get("q_index", 0))
        return items
    except Exception as e:
        print(f"      [warn] Haiku batch failed: {e}")
        return []


def _haiku_analyze_all(pyqs: list[dict], reset_cache: bool = False) -> list[dict]:
    cache_path = CACHE_DIR / "eco_pyq_analysis.json"
    if cache_path.exists() and not reset_cache:
        cached = json.loads(cache_path.read_text())
        if len(cached) == len(pyqs):
            print("  Loaded from cache.")
            return cached
        print("  Cache size mismatch — re-running Haiku...")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    BATCH = 6
    total_batches = (len(pyqs) + BATCH - 1) // BATCH
    print(f"  Haiku analyzing {len(pyqs)} questions in {total_batches} batches...")

    all_items: list[dict] = []
    for i in range(0, len(pyqs), BATCH):
        bn = i // BATCH + 1
        print(f"    Batch {bn}/{total_batches}...", end=" ", flush=True)
        items = _haiku_batch(pyqs[i : i + BATCH], i)
        all_items.extend(items)
        print(f"{len(items)} analyzed")
        time.sleep(0.4)

    by_idx = {item["q_index"]: item for item in all_items}

    enriched: list[dict] = []
    for i, q in enumerate(pyqs):
        a = by_idx.get(i, {})
        enriched.append({
            **q,
            "concept_id":        a.get("concept_id", "other_unknown"),
            "cognitive_skill":   a.get("cognitive_skill", "definition_recall"),
            "correct_reasoning": a.get("correct_reasoning", ""),
            "traps":             a.get("traps", {}),
            "key_facts":         a.get("key_facts", []),
        })

    cache_path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
    print(f"  Cached → {cache_path}")
    return enriched


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def _compute_stats(enriched: list[dict]) -> dict:
    by_year:    dict[int, int] = defaultdict(int)
    by_concept: dict[str, int] = defaultdict(int)
    by_theme:   dict[str, int] = defaultdict(int)
    fmt = {"statement_based": 0, "how_many": 0, "match_pairs": 0, "direct": 0}

    for q in enriched:
        by_year[q["year"]] += 1
        cid = q["concept_id"]
        by_concept[cid] += 1
        theme = CANONICAL_CONCEPTS.get(cid, {}).get("theme", "Other")
        by_theme[theme] += 1

        ql = q["question_text"].lower()
        if re.search(r"how many of the following", ql):
            fmt["how_many"] += 1
        elif re.search(r"consider the following statements|statement[- ]?[i1]", ql):
            fmt["statement_based"] += 1
        elif re.search(r"\bmatch\b|\bpair\b|\bcolumn", ql):
            fmt["match_pairs"] += 1
        else:
            fmt["direct"] += 1

    return {
        "total": len(enriched),
        "by_year": dict(sorted(by_year.items(), reverse=True)),
        "by_concept": dict(sorted(by_concept.items(), key=lambda x: -x[1])),
        "by_theme": dict(sorted(by_theme.items(), key=lambda x: -x[1])),
        "question_formats": fmt,
    }


# ---------------------------------------------------------------------------
# ChromaDB: targeted per-concept retrieval
# ---------------------------------------------------------------------------

def _chroma_query(col: chromadb.Collection, query: str, n: int = 5) -> list[dict]:
    try:
        res = col.query(
            query_texts=[query],
            n_results=n,
            include=["documents", "metadatas"],
        )
        chunks, seen = [], set()
        for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
            key = doc[:120]
            if key in seen or len(doc.strip()) < 60:
                continue
            seen.add(key)
            src = (
                meta.get("source_file")
                or meta.get("source")
                or meta.get("subject_id")
                or "?"
            )
            chunks.append({"text": doc[:650], "source": src})
        return chunks
    except Exception:
        return []


def _gather_theme_content(col: chromadb.Collection, concept_ids: list[str]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for cid in concept_ids:
        query = CANONICAL_CONCEPTS.get(cid, {}).get("query", cid.replace("_", " "))
        for chunk in _chroma_query(col, query, n=4):
            k = chunk["text"][:120]
            if k not in seen:
                seen.add(k)
                parts.append(f"[{chunk['source']}]\n{chunk['text']}")
    return "\n\n---\n\n".join(parts) if parts else "(no content retrieved)"


# ---------------------------------------------------------------------------
# Sonnet: per-theme concept analysis
# ---------------------------------------------------------------------------

_THEME_PROMPT = """\
Write dense UPSC revision material for the theme: **{theme}**

You have {n_qs} actual UPSC PYQs (2022-2025) analyzed below — concept tested, why correct, what each wrong option exploits.
You also have targeted study content retrieved for this theme's concepts.

=== PYQ ANALYSES ({n_qs} questions) ===
{q_analyses}

=== STUDY CONTENT (concept-targeted retrieval) ===
{content}

=== CONCEPTS TO COVER ===
{concepts}

---

For EACH concept listed above, write exactly this format:

### [Concept Name]

[4-6 sentences. Must include: what it is, how it works in India, specific current figures/thresholds (repo rate %, CRR %, MUDRA tier limits, etc.), and the precise angle UPSC tested. No filler. If the concept had no directly-testing question above, end with "(not yet directly tested as UPSC PYQ)".]

**UPSC Traps:**
- [Trap traced to a specific wrong option from the questions above — name the misconception]
- [Second trap]
- [Third trap if applicable]

**Question format:** [How UPSC frames this: statement-based / direct / pairs / how-many format; what cognitive error it is designed to catch]

---

Rules:
- Each concept explanation must be self-contained — do NOT refer to or repeat content from another concept in this section
- Every trap must trace to an actual wrong option from the PYQ analyses above, not a generic textbook trap
- Do not pad or repeat the same idea with different wording
"""


def _fmt_q_analyses(questions: list[dict]) -> str:
    parts = []
    for q in questions:
        trap_str = (
            "; ".join(f"Opt {k}: {v}" for k, v in q["traps"].items())
            if q["traps"] else "—"
        )
        facts_str = ", ".join(q["key_facts"]) if q["key_facts"] else "—"
        parts.append(
            f"[{q['year']}] concept={q['concept_id']} skill={q['cognitive_skill']}\n"
            f"Q: {q['question_text'][:200]}\n"
            f"Why correct: {q['correct_reasoning'] or '—'}\n"
            f"Wrong-option traps: {trap_str}\n"
            f"Key facts needed: {facts_str}"
        )
    return "\n\n".join(parts) if parts else "(no direct PYQs mapped to this theme)"


def _sonnet_theme(theme: str, questions: list[dict],
                  content: str, concept_ids: list[str]) -> str:
    concepts_block = "\n".join(
        f"- **{cid}** — {CANONICAL_CONCEPTS[cid]['desc']}"
        for cid in concept_ids
        if cid in CANONICAL_CONCEPTS
    )
    prompt = _THEME_PROMPT.format(
        theme=theme,
        n_qs=len(questions),
        q_analyses=_fmt_q_analyses(questions),
        content=content[:5500],
        concepts=concepts_block,
    )
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3500,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


# ---------------------------------------------------------------------------
# Sonnet: synthesis (patterns + predictions + study strategy)
# ---------------------------------------------------------------------------

_SYNTHESIS_PROMPT = """\
You are a UPSC analytics expert. Write the meta-analysis sections of a pattern report.

=== PYQ STATISTICS (2022-2025) ===
{stats}

=== CONCEPT COVERAGE (concept | count | years | dominant skill) ===
{coverage}

---

Write these three sections precisely:

## Pattern Dashboard

| Year | Questions | Format breakdown | Key shift |
|---|---|---|---|
[fill from stats above]

| Theme | Questions | Most-tested concepts |
|---|---|---|
[fill from stats above]

**Trend analysis (4-5 sentences):** What direction is UPSC moving in economics — more application-based or more factual? Are statement-based questions rising or falling? What changed 2022 → 2025? Are new themes emerging?

---

## 2026 Prediction List

### Tier 1 — Almost Certain (8 topics)
**[concept/topic]** — [specific PYQ evidence: concept_id + year(s)] + [exactly what fact/threshold/rule UPSC will test]

### Tier 2 — High Probability (6 topics)
Same format.

### Tier 3 — Watch These (4 topics)
Same format.

---

## How UPSC Tests Economics

[200-word synthesis: what cognitive skills are actually tested beyond memorisation, and what study approach this demands — be specific about what "understanding economics" means for UPSC vs for a university exam]

---

Rules:
- Every Tier 1/2 prediction must cite a specific concept_id from the coverage table AND a plausible specific trigger (a threshold, a scheme update, a policy change)
- No filler — every sentence must carry information
"""


def _build_coverage(enriched: list[dict]) -> str:
    cov: dict[str, dict] = defaultdict(lambda: {"count": 0, "years": [], "skills": []})
    for q in enriched:
        cid = q["concept_id"]
        cov[cid]["count"] += 1
        cov[cid]["years"].append(q["year"])
        cov[cid]["skills"].append(q["cognitive_skill"])
    rows = []
    for cid, d in sorted(cov.items(), key=lambda x: -x[1]["count"]):
        skill = max(set(d["skills"]), key=d["skills"].count) if d["skills"] else "?"
        years = ", ".join(str(y) for y in sorted(set(d["years"]), reverse=True))
        rows.append(f"{cid} | {d['count']} | {years} | {skill}")
    return "\n".join(rows)


def _sonnet_synthesis(enriched: list[dict], stats: dict) -> str:
    prompt = _SYNTHESIS_PROMPT.format(
        stats=json.dumps(stats, indent=2),
        coverage=_build_coverage(enriched),
    )
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


# ---------------------------------------------------------------------------
# Raw questions section
# ---------------------------------------------------------------------------

def _raw_questions(enriched: list[dict]) -> str:
    lines = ["## All Raw Questions (2022–2025)\n"]
    cur_year = None
    for q in sorted(enriched, key=lambda x: (-x["year"], x.get("concept_id", ""))):
        if q["year"] != cur_year:
            cur_year = q["year"]
            lines.append(f"\n### {cur_year}\n")
        cid = q.get("concept_id", "")
        theme = CANONICAL_CONCEPTS.get(cid, {}).get("theme", "Other")
        lines.append(f"**[{theme}]** `{cid}`")
        lines.append(f"> {q['question_text']}")
        if q["option_a"]:
            lines.append(
                f"A) {q['option_a']}  "
                f"B) {q['option_b']}  "
                f"C) {q['option_c']}  "
                f"D) {q['option_d']}"
            )
        if q["correct_answer"]:
            lines.append(f"Correct: {q['correct_answer']}")
        if q.get("correct_reasoning"):
            lines.append(f"*Why: {q['correct_reasoning']}*")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    reset_cache = "--reset-cache" in sys.argv

    print("\n=== Economics & Schemes Pattern Analysis v2 ===\n")

    # Step 1 — Extract PYQs
    print("Step 1: Extracting PYQs (2022-2025)...")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    pyqs = _extract_pyqs(con)
    con.close()
    print(f"  Found {len(pyqs)} questions")
    if not pyqs:
        print("ERROR: No questions found. Check DB_PATH.")
        sys.exit(1)

    # Step 2 — Haiku per-question analysis
    print("\nStep 2: Haiku concept mapping + trap extraction...")
    enriched = _haiku_analyze_all(pyqs, reset_cache=reset_cache)

    stats = _compute_stats(enriched)
    print(f"  Theme distribution: { {k: v for k, v in list(stats['by_theme'].items())} }")

    # Step 3 — ChromaDB retrieval + Sonnet per theme
    print("\nStep 3: Per-theme ChromaDB retrieval + Sonnet concept analysis...")
    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    col = chroma.get_collection("upsc_content")

    by_theme: dict[str, list[dict]] = defaultdict(list)
    for q in enriched:
        theme = CANONICAL_CONCEPTS.get(q["concept_id"], {}).get("theme", "Other")
        by_theme[theme].append(q)

    theme_sections: list[str] = []
    for theme in sorted(_THEME_CONCEPTS.keys()):
        concept_ids = _THEME_CONCEPTS[theme]
        qs = by_theme.get(theme, [])
        print(f"  [{theme}] {len(qs)} PYQs, {len(concept_ids)} concepts...", end=" ", flush=True)
        content = _gather_theme_content(col, concept_ids)
        analysis = _sonnet_theme(theme, qs, content, concept_ids)
        theme_sections.append(f"## {theme}\n\n{analysis}")
        print("done")
        time.sleep(0.5)

    # Step 4 — Synthesis
    print("\nStep 4: Synthesis (patterns + predictions + strategy)...")
    synthesis = _sonnet_synthesis(enriched, stats)

    # Step 5 — Assemble and write
    print("\nStep 5: Writing report...")
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORTS_DIR / "eco_schemes_pattern_v2.md"

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    concept_bank = "\n\n---\n\n".join(theme_sections)

    report = (
        f"<!-- Generated: {ts} | v2 per-question architecture | {stats['total']} questions -->\n\n"
        f"# Economics & Government Schemes — UPSC Prelims Pattern Analysis 2022–2025\n\n"
        f"{synthesis}\n\n"
        f"---\n\n"
        f"# Concept Bank\n\n"
        f"{concept_bank}\n\n"
        f"---\n\n"
        f"{_raw_questions(enriched)}\n"
    )

    out_path.write_text(report, encoding="utf-8")
    sz = out_path.stat().st_size
    print(f"  Saved → {out_path}  ({sz:,} bytes)")
    print(f"\n=== Done! ===\nOpen: {out_path}\n")


if __name__ == "__main__":
    main()
