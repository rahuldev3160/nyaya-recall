# UPSC AI Prep System

An AI-powered adaptive preparation system for UPSC Prelims. Built for a 10-day final sprint but designed to scale for any prep window.

---

## What it does

- **Adaptive diagnostics** — generates UPSC-style MCQs from your personal study material, tracks accuracy per subtopic
- **Batch analysis** — uses Claude to identify weak question types, subtopics, and learning patterns
- **Daily plan generation** — builds a personalised study schedule based on your readiness profile
- **Self-attestation** — validates your claimed confidence levels against actual quiz performance (SAR score)
- **"Dive deeper" expansion** — click any question's explanation to get a 400-word deep dive; clicks are tracked as learning signals
- **Adaptive difficulty** — per-subtopic difficulty tiers (easy → medium → hard → exam) auto-adjust based on streak performance

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + uvicorn (port 8000) |
| Frontend | Next.js 14 App Router + TypeScript + Tailwind (port 3000) |
| Database | SQLite (9 tables) |
| Vector store | ChromaDB (local persistent) |
| AI | Claude API — Haiku for fast tasks, Sonnet for generation/analysis |

---

## Setup (first time)

### 1. Clone and install

```bash
git clone <repo-url>
cd "Last 10 Day AI powered Preparation"

# Python deps
pip install -r requirements.txt

# Frontend deps
cd web && npm install && cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in your ANTHROPIC_API_KEY and file paths
```

### 3. Initialise the database

```bash
python3 scripts/db_init.py
```

### 4. Ingest your study material (optional — required for vector search)

Put your UPSC PDFs and notes in the folder set as `UPSC_CONTENT_PATH` in `.env`, then:

```bash
python3 scripts/ingest.py        # your notes/PDFs → ChromaDB
python3 scripts/ingest_pyq.py    # PYQ bank (2009–2025) → SQLite
```

> Ingestion takes 4–8 hours for a large content library. Run it once overnight.

### 5. Start servers

```bash
# Terminal 1 — backend
cd backend
PATH="/opt/homebrew/bin:$PATH" python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd web
npm run dev
```

Open http://localhost:3000.

---

## Project structure

```
backend/
  server.py          # FastAPI app, mounts all routers
  routes/            # One file per feature area
    quiz.py          # Question generation
    sessions.py      # Answer recording, session close, expand-concept
    analysis.py      # Batch analysis trigger
    tracker.py       # Profile + subject readiness
    plan.py          # Daily plan read/generate
    attestation.py   # Self-attestation + SAR
    config.py        # Prep duration config
    csat.py          # CSAT (separate system)

scripts/
  db_init.py         # Schema creation (safe to re-run)
  score_engine.py    # Pure Python scoring, session summaries
  difficulty_engine.py  # Adaptive tier logic
  batch_analyse.py   # End-of-day Claude analysis
  plan_generator.py  # Daily session plan generation
  self_attestation.py  # SAR score management
  ingest.py          # Content ingestion → ChromaDB
  ingest_pyq.py      # PYQ PDF → SQLite

web/src/app/
  page.tsx           # Dashboard
  diagnostic/        # Diagnostic session flow
  session/           # Adaptive session flow
  tracker/           # Subject readiness tracker
  analysis/          # Batch analysis UI
  planner/           # Plan generation
  attestation/       # Self-attestation
  setup/             # Prep duration config
  strategy/          # Exam strategy

prompts/             # All AI prompt templates (.txt)
data/                # SQLite DB + JSON profiles (gitignored)
vector_store/        # ChromaDB (gitignored — rebuild via ingest.py)
plans/               # Feature plans and simulation log
PROJECT.md           # Live project tracker — read this first
```

---

## Development workflow

See `CONTRIBUTING.md` for the full collaboration guide.

Quick reference:
- Feature ideas → file a GitHub Issue with label `feature-request`
- Bugs → file a GitHub Issue with label `bug`, attach screenshot
- Active plans live in `plans/` folder as `.md` files
- `PROJECT.md` is the source of truth for what's shipped / in-progress / planned

---

## Key design decisions

- **Zero API calls during quizzes** — all scoring is local Python, no latency
- **Session summaries over raw answers** — batch analysis uses compact summaries (~80% token saving), only fetches raw answers for persistently weak subtopics
- **Direct backend calls** — frontend calls port 8000 directly, bypassing Next.js proxy (avoids ECONNRESET on long Claude API calls)
- **Prompt templates in `prompts/`** — never inline prompts in code; change prompts without touching Python
