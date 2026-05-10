# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A local-only, AI-powered 10-day UPSC Prelims adaptive preparation system.
Full plan is in PLAN.md — read that first before any session.

## Stack

| Layer | Technology |
|---|---|
| Ingestion | Python 3.11+, pdfplumber, pdf2image, pytesseract, python-docx, anthropic |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 (M-series GPU, free) |
| Vector store | ChromaDB (local persistent, `vector_store/`) |
| Structured data | SQLite (`data/upsc.db`) — upgradeable to PostgreSQL |
| Backend | FastAPI + uvicorn, binds to `0.0.0.0` for phone access on local WiFi |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind |
| AI | Claude API — Haiku for classification, Sonnet for generation/analysis |

## Commands

```bash
# Ingestion (run once, then incrementally for new files)
cd scripts && python ingest.py

# PYQ extraction + classification (one-time)
cd scripts && python ingest_pyq.py

# Backend
cd backend && uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd web && npm run dev

# End-of-day batch analysis
cd scripts && python batch_analyse.py

# Generate tomorrow's plan
cd scripts && python plan_generator.py

# Type check
cd web && npx tsc --noEmit

# Lint
cd web && npm run lint
```

## Critical architecture rules

- **Zero API calls during quiz sessions** — all content is batch-generated beforehand and cached locally
- **All AI outputs cached** in `cache/explanations.json` by hash — never regenerate the same explanation
- **score_engine.py is pure Python** — no API calls for scoring individual answers
- **prompt templates live in `prompts/`** as .txt files — never inline prompts in code
- **All file paths go in .env** — no hardcoded paths anywhere in the codebase
- **SQLite user_id = "user_1"** hardcoded for now — designed to swap to dynamic for multi-user

## Key data files

- `data/syllabus.json` — UPSC Prelims full taxonomy (source of truth for subjects/topics)
- `data/upsc.db` — SQLite: pyq_questions, sessions, answers, scores, sar_scores tables
- `data/prep_profile.json` — GS readiness state, updated by batch_analyse.py
- `data/prep_profile_csat.json` — CSAT readiness (fully independent from GS)
- `data/study_plan.json` — today + tomorrow sessions, written by plan_generator.py
- `cache/explanations.json` — keyed by SHA256(topic + question_text)

## Self-Assessment Reliability (SAR) score

Users can self-attest preparedness in a subject. SAR (0.20–0.90, starts 0.50) controls
how much the claim is trusted vs the validation quiz score:

```
effective_level = (validation_score × (1 - SAR)) + (claimed_level × SAR)
```

SAR managed by `scripts/self_attestation.py`. Stored in `upsc.db` sar_scores table.

## PYQ priority weighting

Subtopic priority = Σ(0.9^(current_year - year) × questions_on_topic_that_year)
Computed by `scripts/priority_scorer.py`. Used to order diagnostic questions.
2009–2025 coverage (17 years) from 3-tier ingestion (see PLAN.md).

## CSAT

Fully separate system. Independent prep_profile, independent session flow.
Routes: `backend/routes/csat.py`. Pages: `web/src/app/csat/`.
Never share data with GS prep_profile.

## Phone access

Backend binds to `0.0.0.0:8000`, frontend to `0.0.0.0:3000`.
Phone on same WiFi accesses via Mac's local IP (`ipconfig getifaddr en0`).
Off-network fallback: export session as offline HTML → import JSON responses.

## Cost guardrails

- Haiku for: PYQ classification, topic tagging, simple decisions
- Sonnet for: question generation, batch analysis, plan generation, explanations
- Never call API per individual answer — always batch
- Check `cache/explanations.json` before any explanation API call
