# UPSC 10-Day Adaptive Prep System — Master Plan

## What this is

A local-only, AI-powered UPSC Prelims preparation system that:
- Runs entirely on the user's Mac (no cloud servers, no subscriptions)
- Ingests the user's own study material (PDFs, notes, GoodNotes exports)
- Diagnoses preparation level across the full syllabus in Day 1–2
- Adapts revision and quiz sessions for Day 3–10 based on diagnosed weaknesses
- Targets full syllabus coverage + exam readiness by Day 11 morning

Only external service: **Anthropic Claude API** (pay-per-use, ~$20–35 total)

---

## System Architecture

```
Desktop study files (PDF/DOCX/GoodNotes exports)
    ↓
scripts/ingest.py  ← run once; re-run for new files (incremental)
    ↓
ChromaDB (local vector store) + SQLite (structured data)
    ↓
backend/server.py (FastAPI, port 8000) ← phone accesses via local WiFi IP
    ↓
web/ (Next.js, localhost:3000)
    ├── Dashboard + Tracker
    ├── Diagnostic mode (Day 1–2)
    ├── Adaptive Session (Day 3–10)
    ├── Planner (10-day calendar)
    ├── Analysis
    ├── Strategy
    └── CSAT (separate, user-triggered)
```

### Data stores

| Store | What lives here |
|---|---|
| `ChromaDB` | Chunked text from all study material (500-token chunks, 50-token overlap) |
| `SQLite (upsc.db)` | PYQ questions, session history, answers, scores, prep profile |
| `data/prep_profile.json` | Current GS readiness state (updated each sync) |
| `data/prep_profile_csat.json` | CSAT readiness (separate, independent) |
| `data/study_plan.json` | Today + tomorrow sessions (AI-generated on demand) |
| `data/syllabus.json` | Full UPSC Prelims taxonomy: subjects → topics → subtopics |
| `cache/explanations.json` | All AI-generated explanations (never regenerated) |
| `scripts/ingestion_log.json` | Tracks processed files by hash (skip on re-run) |

---

## PYQ Ingestion — Three-Tier Strategy

```
Tier 1: Year-wise PDFs (2016–2025)
  → Year known from filename → clean year tagging
  → Extract: question text, options A–D, correct answer
  → Claude API classifies: subject → topic → subtopic → concept
  → Stored in SQLite: pyq_questions table

Tier 2: Compiled PDF (2009–2025, subject/topic arranged)
  → Extract: question text + year (parsed from within text)
  → IGNORE existing topic classification — re-classify independently
  → Cross-reference Tier 1 by question hash to avoid duplicates
  → Covers 2009–2015 (7 additional years of weighting data)

Tier 3: Merged PDF (all years combined)
  → Cross-reference only — catch any questions missed in Tier 1+2
  → Not processed independently for already-covered questions
```

**Result:** 17 years of PYQ data (2009–2025), fully re-classified by Claude,
year-tagged, stored in SQLite. Never re-processed.

---

## Topic Priority Weighting Formula

Every subtopic gets a priority score before diagnostic question ordering:

```python
Priority Score = Σ (decay_weight(year) × questions_asked_on_topic_that_year)

decay_weight(year) = 0.9 ^ (current_year - year)

# Examples:
# 2025 → 1.00   2024 → 0.90   2023 → 0.81
# 2020 → 0.59   2015 → 0.35   2010 → 0.21   2009 → 0.19
```

High-priority subtopics (high score) are tested first and allocated more questions.
Low-priority subtopics are tested later or skipped if time runs short.

Current affairs from user's PIB material is woven into questions wherever a
recent development links to a topic — makes diagnostic test both static knowledge
AND current awareness simultaneously.

---

## Diagnostic Phase (Day 1–2)

### Subject priority order (by PYQ frequency weight)
1. Polity & Governance
2. History (Ancient + Medieval + Modern + Art & Culture)
3. Environment & Ecology
4. Economy
5. Geography
6. Science & Technology
7. Current Affairs (from user's PIB/downloaded material only)
8. CSAT → separate, user decides when

### Per-subject session config (user sets at start of each subject)

**Mode A — Time-boxed:**
User sets duration (e.g., 30 min). Questions served continuously until timer ends.
System records: answers, time-per-question, skipped questions.

**Mode B — Fixed set:**
User sets N questions + time cap. Ends when all answered or time runs out.
Unanswered = skipped (useful signal: slow or unsure).

### Per-subtopic adaptive questioning

```
Round 1: 5 high-priority subtopics × 5 questions each (from PYQ bank + AI-generated)
  Score each subtopic:
    > 75%   → "Assessed: Strong" — stop, move on
    50–75%  → "Uncertain" — run Round 2
    < 50%   → "Assessed: Weak"  — stop, level is clear

Round 2 (Uncertain subtopics only):
  5 more questions, slightly harder
    > 70%   → "Moderate-Strong"
    ≤ 70%   → "Moderate-Weak"
```

### Mid-day confidence check (automatic, after each subject completed)

```
Condition A — Jump to Phase 2 early
  4+ subjects fully assessed
  + PrepProfile confidence > 80%
  + Consistent scores (low variance)
  → Trigger bulk analysis now → Phase 2 begins

Condition B — Continue diagnostic, increase difficulty
  4+ subjects assessed
  + High average but high variance (some 90%, some 55%)
  → Harder questions on uncertain subjects, not Phase 2 yet

Condition C — Stop diagnosing, clearly weak
  3+ subjects consistently < 50%
  → Trigger analysis immediately
  → Phase 2 starts with foundational notes + easy-medium questions
```

User can also manually trigger analysis anytime via "Pause & Analyse Now" button.

### Content buffer strategy (cost efficiency)

At start of each day, batch-generate ALL session content in 2–3 API calls (~$0.15).
Content cached in study_plan.json. Zero API calls during actual quiz sessions.
Analysis + next-day planning = 2 more API calls at user's trigger.

---

## Self-Attestation System

User can claim "I'm fully prepared in [Subject]" to skip diagnostic.
System validates the claim with a light quiz and assigns a weighted effective score.

### Self-Assessment Reliability (SAR) score
- Starts at 0.50 for all users (neutral trust)
- Updates after each validated claim
- Range: 0.20 (min) to 0.90 (max)

```python
effective_prep_level = (validation_score × (1 - SAR)) + (claimed_level × SAR)

# SAR update:
discrepancy = abs(claimed_level - validation_score)
if discrepancy < 10%:   SAR += 0.05   # Accurate assessor
if discrepancy < 20%:   SAR unchanged
if discrepancy < 35%:   SAR -= 0.05   # Overconfident
if discrepancy >= 35%:  SAR -= 0.10   # Significantly miscalibrated
```

### Validation quiz
- 12 questions: top-weighted PYQs + 2 current affairs questions on subject
- User sets timed or untimed
- Result feeds into effective_prep_level calculation
- SAR is shown transparently to user in tracker

---

## Adaptive Revision Phase (Day 3–10)

### Session format decision (AI decides per subtopic)

```
Score < 50%   → Notes summary shown first (from ChromaDB), then quiz
Score 50–75%  → Light notes highlight + standard quiz
Score > 75%   → Quiz only, harder questions, PYQ-style
```

### Daily flow

```
Morning: "Plan Today" button
  → 1 API call: reads prep_profile.json → generates today's sessions
  → Prioritises: weakest topics × highest PYQ weight × days remaining
  → Saves to study_plan.json

During day: Sessions run from local cache (zero API cost per answer)

Evening: "Sync & Plan" button (user-triggered)
  → batch_analyse.py collects all session data
  → 1 API call: analyses full day → updates prep_profile.json
  → 1 API call: generates tomorrow's plan
```

---

## CSAT — Fully Separate

```
Separate tracker: data/prep_profile_csat.json
Separate session config (user decides when to start)
Subtypes: Comprehension / Logical Reasoning / Data Interpretation / Basic Numeracy
No interaction with GS prep_profile
Own analysis cycle, own adaptive session logic
```

---

## Preparation Tracker

Per subject/topic:
- Readiness score (0–100%)
- Trend (improving / stable / declining)
- Last tested timestamp
- Estimated additional hours to reach 75% threshold

Gap analysis panel:
- Shows exactly which topics are below threshold
- Calculates rough time commitment to bridge each gap
- Updates after each "Sync & Plan"

Day 11 view:
- Final readiness summary
- Personalised attempt order for exam (based on actual scores)
- Last-minute focus list (top 5 subtopics to skim)

---

## Phone + PC Integration

**Primary — same WiFi:**
FastAPI and Next.js bind to local network IP (not just localhost).
Phone opens `192.168.x.x:3000` in browser → full app, data saves to Mac's SQLite.
One-time setup: get Mac IP via `ipconfig getifaddr en0`, save as phone bookmark.

**Fallback — off-network:**
App exports a session as a self-contained offline HTML quiz file.
User answers on phone → taps "Export Responses" → downloads JSON.
Back on Mac: drag JSON into app → "Import Session" → merged into SQLite.
AirDrop is fastest transfer method.

---

## Project Structure

```
project_root/
├── .env                          ← ANTHROPIC_API_KEY (never commit)
├── .gitignore                    ← .env, vector_store/, raw paths
├── CLAUDE.md
├── PLAN.md                       ← this file
│
├── data/
│   ├── syllabus.json             ← UPSC Prelims full taxonomy
│   ├── upsc.db                   ← SQLite: pyq_questions, sessions, answers, scores
│   ├── prep_profile.json         ← GS readiness (auto-updated on sync)
│   ├── prep_profile_csat.json    ← CSAT readiness (separate)
│   └── study_plan.json           ← today + tomorrow sessions
│
├── scripts/
│   ├── requirements.txt
│   ├── ingest.py                 ← orchestrator: detects type, routes, tracks log
│   ├── ingest_pyq.py             ← PYQ-specific: 3-tier extraction + Claude classify
│   ├── batch_analyse.py          ← end-of-day: 1 API call, updates prep_profile
│   ├── plan_generator.py         ← generates study_plan.json via API
│   ├── score_engine.py           ← pure Python scoring (zero API cost)
│   ├── priority_scorer.py        ← calculates weighted PYQ priority per subtopic
│   ├── self_attestation.py       ← SAR score management
│   ├── content_cache.py          ← read/write explanations.json
│   ├── ingestion_log.json        ← auto-generated
│   └── parsers/
│       ├── digital_pdf.py        ← pdfplumber
│       ├── scanned_pdf.py        ← pdf2image + tesseract
│       ├── handwritten_pdf.py    ← pdf2image + Claude Vision API
│       └── docx_parser.py        ← python-docx
│
├── prompts/                      ← prompt templates (text files, not in context)
│   ├── pyq_classify.txt
│   ├── diagnostic_quiz.txt
│   ├── adaptive_session.txt
│   ├── batch_analysis.txt
│   ├── plan_generation.txt
│   ├── validation_quiz.txt
│   └── explanation.txt
│
├── cache/
│   ├── explanations.json         ← AI explanations cached by topic+question hash
│   └── ingestion_log.json
│
├── vector_store/                 ← ChromaDB persistent (auto-generated, ~2–4 GB)
│
├── backend/
│   ├── server.py                 ← FastAPI, binds to 0.0.0.0 (local network)
│   ├── models.py                 ← Pydantic models (web-ready from day 1)
│   └── routes/
│       ├── quiz.py
│       ├── sessions.py
│       ├── analysis.py
│       ├── plan.py
│       ├── tracker.py
│       ├── attestation.py
│       └── csat.py
│
└── web/
    ├── package.json
    └── src/
        ├── app/
        │   ├── page.tsx              ← Dashboard + tracker
        │   ├── diagnostic/           ← Day 1–2 flow
        │   ├── session/              ← Active adaptive session
        │   ├── analysis/             ← Performance analytics
        │   ├── planner/              ← 10-day calendar
        │   ├── strategy/             ← Exam day plan
        │   └── csat/                 ← CSAT (independent)
        ├── components/
        └── lib/
            ├── api.ts                ← FastAPI calls
            └── storage.ts            ← localStorage for UI state only
```

---

## Cost Breakdown

| Item | Cost | When |
|---|---|---|
| GoodNotes OCR (~2,000 pages × $0.006) | ~$12 | One-time, first ingestion |
| PYQ classification via Claude (one-time) | ~$3 | One-time, first ingestion |
| Daily content batch generation | ~$0.15/day | Each morning |
| End-of-day analysis + plan | ~$0.08/day | Each evening sync |
| Validation quiz generation | ~$0.02/claim | When user self-attests |
| Explanation cache misses | ~$0.01–0.03 | First time per topic only |
| Embeddings (sentence-transformers) | $0 | Always free, runs locally |
| **10-day total estimate** | **~$20–35** | Billed end of month by Anthropic |

Set a $40 spend limit on Anthropic account to be safe.

---

## AI Model Split (cost optimisation)

| Task | Model | Reason |
|---|---|---|
| PYQ classification (one-time) | claude-haiku-4-5 | Simple classification, high volume |
| Question generation | claude-sonnet-4-6 | Quality matters |
| Batch analysis | claude-sonnet-4-6 | Complex reasoning |
| Plan generation | claude-sonnet-4-6 | Needs full context |
| Explanation generation | claude-sonnet-4-6 | Cached after first use |

---

## Build Phases

| Phase | What gets built | Est. time |
|---|---|---|
| 1. Ingestion pipeline | ingest.py, all parsers, PYQ 3-tier extractor, priority scorer | 4–5 hrs |
| 2. Ingestion run | 10k pages + PYQ classification (runs overnight) | 6–8 hrs unattended |
| 3. Backend | FastAPI, all routes, SQLite schema, score engine | 3–4 hrs |
| 4. Diagnostic UI | Session config, quiz flow, mid-day trigger, self-attestation | 3–4 hrs |
| 5. Adaptive + Tracker | Revision sessions, planner, tracker, gap analysis | 4–5 hrs |
| 6. CSAT + Strategy | Independent CSAT flow, exam strategy page | 2–3 hrs |
| 7. Polish + Phone | Network binding, export/import, end-to-end test | 2 hrs |

---

## Actions Required from User

| When | Action |
|---|---|
| Before start | Get Anthropic API key: console.anthropic.com → API Keys → Create |
| Before start | Provide Desktop folder path for study files |
| Before start | Provide path to PYQ year-wise folder |
| Before start | Provide path to compiled PYQ PDF (2009–2025) |
| Ingestion night | Keep Mac plugged in, lid open |
| Each morning | Click "Plan Today" (30 seconds) |
| Each evening | Click "Sync & Plan" (30 seconds) |
| Adding new files | Drop in folder → run `python scripts/ingest.py` |

---

## Web/Public Expansion (post-exam, future)

Architecture is already ready for this:
- SQLite → PostgreSQL (single connection string change)
- FastAPI already has proper REST structure, add JWT auth middleware
- User ID concept in SQLite even now (hardcoded to "user_1", swap to dynamic later)
- All file paths in .env (no hardcoded paths anywhere)
- Docker-composable structure from the start
