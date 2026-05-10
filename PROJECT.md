# UPSC AI Prep System — Project Tracker

> This file is the source of truth for everything in progress, planned, and shipped.
> Each feature gets its own sub-plan in `plans/`. Merge means: code shipped + plan archived.

**Decisions + batched tracker:** see [`docs/CHRONICLE.md`](docs/CHRONICLE.md), [`docs/PROJECT_TRACKER.md`](docs/PROJECT_TRACKER.md), and `python3 scripts/sync_tracker.py` (git-delta summaries). Agent roles: [`docs/agents/`](docs/agents/).

---

## Live Status

| Layer | Status |
|-------|--------|
| Backend (FastAPI :8000) | ✅ Running |
| Frontend (Next.js :3000) | ✅ Running |
| SQLite DB | ✅ 9 tables live |
| ChromaDB (vector store) | ✅ 11,146 chunks |
| PYQ ingestion | ✅ 1,081 questions (2009–2025) |

---

## Simulation Log — 2026-05-11

Running live 2-hour simulation. Findings recorded in real time.

→ See [`plans/simulation_log.md`](plans/simulation_log.md)

| Step | Status | Finding |
|------|--------|---------|
| 1. Setup (10-day sprint, 6h/day) | ✅ Done | Dashboard shows Day 1 of 10 correctly |
| 2. Diagnostic — Polity (10 Qs) | ✅ Done | 70% score, 30–40s generation, no errors |
| 3. Diagnostic — Economy (10 Qs) | ✅ Done | 70% score, E-Jagriti / NFSA questions confirmed |
| 4. Batch Analysis | ✅ Done | 35% readiness, Polity 65%, Economy 70% |
| 5. Plan generation | ⏳ Pending | — |
| 6. Self-Attestation | ⏳ Pending | — |
| 7. Adaptive session from plan | ⏳ Pending | — |
| 8. Second batch analysis | ⏳ Pending | — |

---

## Features — In Progress

| Feature | Plan file | Target merge |
|---------|-----------|-------------|
| Expand Concept ("Dive deeper →") | [`plans/expand_concept.md`](plans/expand_concept.md) | ✅ Shipped |
| Engaging onboarding redesign | [`plans/onboarding_redesign.md`](plans/onboarding_redesign.md) | After simulation |
| Simulation-driven bug fixes | [`plans/simulation_log.md`](plans/simulation_log.md) | Rolling |

---

## Features — Planned (not started)

| Feature | Plan file | Priority |
|---------|-----------|----------|
| Streak + daily goal tracker | [`plans/streak_tracker.md`](plans/streak_tracker.md) | High |
| Offline / phone export mode | — | Medium |
| Mock test mode (timed full paper) | — | High |
| Spaced repetition for weak subtopics | — | Medium |
| WhatsApp daily brief (digest) | — | Low |

---

## Features — Shipped

| Feature | Shipped | Notes |
|---------|---------|-------|
| PYQ ingestion (1,081 Qs, 2009–2025) | 2026-05-10 | Microthemes PDF |
| Session summaries + question type detection | 2026-05-11 | score_engine.py |
| Adaptive difficulty per subtopic | 2026-05-11 | difficulty_engine.py |
| Configurable prep duration (5–90 days) | 2026-05-11 | /setup page |
| Proxy bypass (direct backend calls) | 2026-05-11 | api.ts BASE fix |
| All 12 bug fixes | 2026-05-11 | See SIMULATION.md |
| Self-attestation + SAR | 2026-05-10 | /attestation page |
| Batch analysis (summary-based, hybrid) | 2026-05-11 | batch_analyse.py |
| Expand Concept — "Dive deeper →" button | 2026-05-11 | sessions.py, diagnostic/session pages |

---

## How to use this file

- **During a session:** Update the Simulation Log table above in real time as steps complete.
- **New feature idea:** Create `plans/<feature_name>.md` and add a row to "Planned".
- **Feature ready to build:** Move row to "In Progress", open the plan file and flesh it out.
- **Feature shipped:** Move row to "Shipped", archive the plan file.
- **Merge all pending plans:** Tell Claude "merge all in-progress plans" — it reads each plan file, implements, and marks shipped.
