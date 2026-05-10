# Collaboration Guide

> Read this once. It's everything you need to contribute without needing a call.

---

## The situation

Rahul is using this app as his primary UPSC prep tool for the next 10 days (exam: May 20).
He studies 7–8 hours daily using it, which means he's also the highest-signal tester possible — every bug he files is a real bug that blocked real study time. Every feature request comes from actual friction, not imagination.

His constraint: he cannot context-switch to explain things or make decisions mid-study.
Your job: pick up GitHub issues and ship without needing him to unblock you.

This document + the codebase + `PROJECT.md` should give you everything to do that.

---

## What the project is

A fully local, AI-powered adaptive prep system for UPSC Prelims (India's hardest civil services exam). Think: a personalised tutoring engine that runs on the user's own machine against their own study material.

**Core loop:**
1. User runs a **diagnostic session** → AI generates 10 UPSC-style MCQs from their notes via ChromaDB vector search + Claude Sonnet
2. User answers questions → scores recorded locally in SQLite, zero API calls during quiz
3. After session, **batch analysis** runs → Claude analyses session summaries to identify weak subtopics, question-type gaps, learning patterns
4. **Daily plan** is generated → prioritised study sessions for tomorrow based on the readiness profile
5. Adaptive difficulty per subtopic auto-adjusts (easy → medium → hard → exam) based on streak performance

Secondary features:
- **Self-attestation** — user claims confidence level in a subject, system validates it with a quiz, computes a reliability score (SAR) that blends claim + evidence
- **"Dive deeper" expansion** — button on each question that generates a 400-word concept deep-dive via Haiku, click is recorded as a learning signal
- **Tracker** — subject-level readiness bars, gaps list, SAR score

**What it is NOT:** a SaaS app, a mobile app, a multi-user system. It's a single-user local tool. `user_id = 'user_1'` is hardcoded everywhere. That's fine for now.

---

## Current state (as of May 11)

| Component | Status |
|-----------|--------|
| Backend (FastAPI :8000) | Running, all routes working |
| Frontend (Next.js :3000) | Running, all pages working |
| SQLite DB | 9 tables, live |
| ChromaDB | 11,146 chunks from Rahul's study material |
| PYQ bank | 1,081 questions (2009–2025) ingested |
| Session flow | Diagnostic + adaptive sessions working end-to-end |
| Batch analysis | Working, tested |
| Plan generation | Working |
| Self-attestation | Working |
| Expand concept | Working (just shipped) |

**Readiness profile after Day 1:** 35% overall. Polity 65%, Economy 70%. 7 subjects untested.

---

## Architecture

```
backend/           FastAPI app
  server.py        mounts all routers
  routes/          one file per feature — add new features here
    quiz.py        question generation (calls Claude Sonnet + ChromaDB)
    sessions.py    answer recording, session close, expand-concept endpoint
    analysis.py    batch analysis trigger (calls batch_analyse.py)
    tracker.py     readiness profile + subject scores (reads prep_profile.json)
    plan.py        daily plan read/generate (reads/writes study_plan.json)
    attestation.py self-attestation + SAR
    config.py      prep duration config (reads/writes prep_config.json)

scripts/           pure Python, no FastAPI
  db_init.py       schema (safe to re-run, IF NOT EXISTS everywhere)
  score_engine.py  local scoring, session summaries — ZERO API calls
  difficulty_engine.py  per-subtopic tier logic (easy/medium/hard/exam)
  batch_analyse.py end-of-day Claude analysis
  plan_generator.py    daily session planning
  self_attestation.py  SAR score management

web/src/app/       Next.js App Router, one folder per page
  page.tsx         dashboard
  diagnostic/      diagnostic quiz flow
  session/         adaptive session flow (reads study_plan.json sessions)
  tracker/         subject readiness
  analysis/        batch analysis trigger UI
  planner/         plan generation UI
  attestation/     self-attestation flow
  setup/           prep duration config

prompts/           ALL AI prompts as .txt files — never inline prompts in code
data/              SQLite DB + JSON state files (gitignored except syllabus)
vector_store/      ChromaDB (gitignored — Rahul's personal content)
plans/             feature plan specs (.md files per feature)
PROJECT.md         live project tracker — read this before picking up any issue
```

### Data flow in plain English

- `data/upsc.db` — the source of truth for all session data (answers, scores, summaries)
- `data/prep_profile.json` — written by `batch_analyse.py` after each sync; read by `/tracker/profile` and the dashboard. This is Rahul's readiness state.
- `data/study_plan.json` — written by `plan_generator.py`; read by `/plan/today`. Today's sessions.
- `data/prep_config.json` — written by the `/setup` page; total_days, daily_hours, start_date.

These three JSON files are the main "global state" of the app. Everything else is derived from SQLite.

### Key architectural decisions (don't reverse without discussion)

- **Frontend calls backend directly** at `http://localhost:8000`, not through Next.js proxy. This was a deliberate fix — the proxy dropped long Claude API calls with ECONNRESET. Don't add a proxy layer back.
- **Zero API calls during quiz sessions** — all scoring is local Python. Latency during a quiz must stay zero.
- **Session summaries over raw answers** — batch analysis uses compact summaries (~80% token saving). Raw answers are only fetched for subtopics that are persistently weak (2+ sessions). Don't change this pattern without checking token costs first.
- **Prompts in `prompts/` as .txt files** — never inline prompt strings in Python/TS code. If you need to tweak a prompt, edit the .txt file.

---

## Roles

### Rahul — power user + issue reporter

- Uses the app for real UPSC prep, 7–8 hours/day
- Hits real bugs, real UX friction, has real feature ideas
- Files GitHub Issues with a screenshot and a short description
- Labels issues and sets priority (see below)
- Does **not** write code, does **not** review PRs in detail — a thumbs up or "LGTM" is enough
- Merges PRs once you flag them as ready

### You — builder

- Picks up issues from GitHub
- Reads `PROJECT.md` + `plans/<feature>.md` before starting anything
- Opens a `feature/*` or `fix/*` branch, ships, opens PR
- Writes a one-paragraph PR description: what changed + how to test locally
- Tags Rahul in the PR with `@Deviridium ready to merge` when done
- Does **not** need Rahul to explain the codebase — everything is documented

---

## Async communication protocol

The goal is zero blocking. Rahul should never have to pause studying to answer a question you could answer by reading the code or docs.

**How Rahul files issues:**
- Screenshot of the problem
- One sentence: what happened
- One sentence: what he expected
- Label: `bug` / `ux` / `feature-request`
- Priority tag: `high-priority` (blocked study) or `post-exam` (nice-to-have)

**How you pick up issues:**
1. Check `PROJECT.md` — is there a `plans/` file for this feature? If yes, read it. The design is specced.
2. If no plan file, the issue description is the spec. Use your judgement.
3. If genuinely ambiguous — leave a comment on the issue with a specific yes/no question. Don't ask open-ended questions like "what do you want this to look like?" — propose a solution and ask "does this work?"

**PR → merge flow:**
- You open PR, write description + test steps
- Comment `@Deviridium ready` on the PR
- Rahul merges it when he has 5 minutes (between sessions, not mid-session)
- Rahul pulls and restarts the backend — takes 2 minutes

**Disagreements on approach:**
- If it's a UI/UX call → Rahul decides (he's the user)
- If it's a technical/architecture call → you decide, leave a note in the PR explaining the tradeoff
- If it's a cost-impacting call (adds new AI API calls) → comment on the issue first, don't just ship it

---

## Feature backlog and priorities

See `PROJECT.md` for the full live list. Summary:

**Build during the 10-day sprint (before May 20):**

| Feature | Why it matters now | Plan file |
|---------|-------------------|-----------|
| Mock test mode | Needed for Day 8–9 simulation (timed 100Q paper) | Not yet written — you can spec it |
| Streak + daily goal tracker | Habit enforcement for the sprint | `plans/streak_tracker.md` |
| Loading state improvements | 30–40s quiz generation with no feedback is painful | Add to diagnostic/session pages |

**Post-exam (good ideas, wrong timing):**
- Onboarding redesign (3-step guided flow) — `plans/onboarding_redesign.md`
- WhatsApp daily digest
- Offline/phone export mode
- Multi-user support

**Rough spec for mock test mode** (not yet in a plan file):
- Timed full paper: 100 questions, 2 hours, subjects weighted by PYQ frequency
- No explanations shown during the test (UPSC doesn't give them)
- Score card at end: section-wise breakdown, time per question, weak areas
- Results feed into batch analysis like a normal session
- New session_type = "mock_test" in quiz_sessions table

---

## Cost guardrails

The app uses Anthropic API. Rough daily spend at normal usage: ~$2/day. Don't break this.

| Operation | Model | When |
|-----------|-------|------|
| Quiz generation | Sonnet | Once per session, unavoidable |
| Batch analysis | Sonnet | Once per day, ~3K tokens |
| Plan generation | Sonnet | Once per day, ~2K tokens |
| Expand concept | Haiku | On user click, ~1K tokens |
| Explanation cache | — | Check `cache/explanations.json` before any explanation call |

**Rules:**
- Never add a per-question API call during a quiz session
- Always use Haiku for anything interactive/fast (expand concept, simple decisions)
- Always use Sonnet for generation and analysis
- Check `cache/` before calling the API for explanations — they're keyed by SHA256(topic + question)
- If you're adding a new AI-powered feature, comment in the issue what the estimated token cost is

---

## Local setup without Rahul's content

You don't need his 500MB study library to develop. The backend has a fallback: if ChromaDB returns no chunks, it generates questions from the UPSC syllabus directly. So `python3 scripts/ingest.py` is optional for dev work.

Minimum setup to run the full app:
```bash
git clone https://github.com/Deviridium/upsc-ai-prep
cd upsc-ai-prep
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, PROJECT_PATH (absolute path to this repo)
# DB_PATH, CHROMA_PATH can be relative inside the repo

pip install -r scripts/requirements.txt
python3 scripts/db_init.py

# Terminal 1
cd backend && PATH="/opt/homebrew/bin:$PATH" python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
cd web && npm install && npm run dev
```

Open http://localhost:3000. Go to Setup, pick 10 days, start a diagnostic.

---

## What not to touch

- `.env` — never commit, never share. Use `.env.example` for new variables.
- `data/upsc.db`, `data/prep_profile.json`, `data/study_plan.json` — Rahul's personal data. Gitignored.
- `vector_store/` — his 11K content chunks. Gitignored. Rebuild with `ingest.py` on your own content.
- `data/syllabus.json` — the UPSC Prelims taxonomy (source of truth for subject/topic/subtopic IDs). Don't edit this without flagging it — everything in the DB references these IDs.
- The `user_id = 'user_1'` pattern — it's everywhere. Don't refactor to dynamic auth right now, it'll break everything and add zero value for a single-user app.

---

## Python version note

The project runs on Python 3.9. Every `.py` file that uses `X | None` type hints must have `from __future__ import annotations` at the top. This is already in all existing files — maintain it in any new ones.

---

## If you're stuck

1. Read `CLAUDE.md` — deep architecture notes, cost patterns, key design decisions
2. Read `plans/<feature>.md` — most features have a spec
3. Read `PROJECT.md` — current state of everything
4. Check the existing routes in `backend/routes/` — they're all short and follow the same pattern
5. Last resort: leave a comment on the issue. Be specific.
