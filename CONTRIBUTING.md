# Contributing Guide

This project has two roles:

**Rahul (aspirant/tester)** — uses the app 7–8 hours daily for real UPSC prep, hits real bugs, files issues with screenshots and context in real time.

**Friend (SE/developer)** — picks up issues from GitHub, implements, opens PRs. Claude Code is your AI pair programmer.

---

## How issues work

Rahul files issues during actual study sessions — these are real bugs and real friction points, not hypothetical ones. Every issue has a screenshot and a description of what was expected vs what happened.

When you pick up an issue:
1. Read `PROJECT.md` first — it shows what's shipped, what's in-progress, and what's planned
2. Check `plans/` for a matching `.md` file — if one exists, the design is already specced
3. If no plan file exists, the issue is self-explanatory enough to implement directly

---

## Local setup

Follow README.md setup steps. Key things:
- Copy `.env.example` → `.env` and fill in your values
- You don't need `UPSC_CONTENT_PATH` to be a real folder to develop — the backend works without content ingested (quiz generation falls back to a generic syllabus prompt)
- Run `python3 scripts/db_init.py` before starting the backend

---

## Running the project

```bash
# Backend (from /backend)
PATH="/opt/homebrew/bin:$PATH" python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Frontend (from /web)
npm run dev
```

---

## Code conventions

- Python: use `from __future__ import annotations` at top of every file (required for `X | None` on Python 3.9)
- AI prompts: all live in `prompts/*.txt` — never inline prompt strings in code
- API calls: `base_url = http://localhost:8000` — frontend calls backend directly (no proxy)
- DB: `user_id = 'user_1'` is hardcoded for now — single user system
- New backend routes: add a file in `backend/routes/`, then `include_router` in `server.py`
- New DB tables: add to `db_init.py` with `CREATE TABLE IF NOT EXISTS`, then add an `ALTER TABLE` migration call for existing DBs

---

## Branch + PR workflow

```
main         ← always deployable, Rahul runs this locally
feature/*    ← your feature branches
fix/*        ← bugfix branches
```

- Open a PR against `main`
- PR description: what changed + how to test
- Rahul tests the PR branch locally before merge

---

## Issue labels

| Label | Meaning |
|-------|---------|
| `bug` | Something broken, confirmed by Rahul during real use |
| `ux` | Works but feels wrong — friction in the study flow |
| `feature-request` | New capability |
| `high-priority` | Blocks daily study — fix today |
| `post-exam` | Good idea, but not needed before May 20 |

---

## Architecture in 60 seconds

- Backend is FastAPI. Each feature is one file in `backend/routes/`.
- Frontend is Next.js App Router. Each page is `web/src/app/<name>/page.tsx`.
- All AI calls go through `scripts/` (Python) or `backend/routes/sessions.py` (expand-concept).
- `data/prep_profile.json` = user's readiness state, written by `batch_analyse.py`
- `data/study_plan.json` = today's sessions, written by `plan_generator.py`
- SQLite schema is in `scripts/db_init.py` — all tables with `IF NOT EXISTS`

Read `CLAUDE.md` for deeper architecture notes.
