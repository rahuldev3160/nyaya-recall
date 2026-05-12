# HANDOFF.md — Dev Session Update (May 11, 2026)

> Read `COLLAB.md` first for the full project context and architecture overview.
> This file covers what changed in the most recent dev session and what still needs work.

---

## TL;DR for your friend

Rahul is actively studying using this system starting today. The core loop now works correctly
end-to-end: diagnostics run, scores are tracked per subtopic, the end-of-day analysis produces
real numbers, and the plan generator knows what hasn't been tested yet.

Before this session, several scoring bugs meant the system was technically running but
measuring nothing — everything showed 0% despite completed sessions. Those are all fixed.

**What you can do right now:** pick up any item from the Open Problems section below and ship
it as a PR. Rahul will test it live during his study sessions.

---

## What was fixed in this session

### 1. Mobile access (Tailscale)
Phone was showing 0% despite Mac showing correct data.

**Root cause:** Next.js dev server (`npm run dev`) hangs on concurrent fetch calls from
external IPs. Three fetches fired in parallel on page load; each timed out waiting for the
others.

**Fix:**
- `web/src/app/page.tsx` — changed concurrent `Promise.all` fetches to sequential `await`
- `web/src/lib/api.ts` — changed API base to relative `/api/backend`, added 8s AbortController timeout
- `backend/routes/config.py` — added `redirect_slashes=False` to prevent 307 redirects
  leaking through the proxy
- Server: switched from `npm run dev` to `npm run build && npm run start -- -H 0.0.0.0`

**How to start the server after a Mac restart:**
```
# Tab 1
cd backend && uvicorn server:app --host 0.0.0.0 --port 8000

# Tab 2
cd web && npm run start -- -H 0.0.0.0
```
Phone connects via Tailscale IP (`100.113.107.75:3000`) from any network.

---

### 2. Weighted readiness scoring (the big one)

Old system: two history sessions on the same subtopic (Indus Valley Civilization) → history
marked "strong". Completely wrong.

**New formula (computed in Python, no LLM):**
```
subject_readiness = Σ(tested_score × PYQ_weight) / Σ(all_subtopic_weights_in_subject)
overall_readiness = Σ(subject_readiness × avg_questions_per_year) / Σ(avg_q_per_year)
```

- Untested subtopics contribute **score = 0** until tested. Can't be "strong" with gaps.
- PYQ weight = `Σ(0.9^(2026 − year))` for each year the subtopic appeared in the exam
  (2009–2025 coverage). Higher weight = more historically tested in the real exam.
- Claude only writes insight text. Numbers come entirely from Python.

**Files changed:** `scripts/batch_analyse.py`, `prompts/batch_analysis.txt`

---

### 3. Four cascading bugs that caused subtopic_scores to always be empty

All four were independent root causes, all causing score writes to silently fail:

| # | Bug | Fix |
|---|-----|-----|
| 1 | `subtopic_scores.topic_id` had `NOT NULL` constraint, inserts failed when topic_id was NULL | Recreated table with `topic_id TEXT` (nullable) |
| 2 | `WHERE topic_id = ?` with Python `None` is always false in SQL | Changed to `WHERE topic_id IS ?` — SQLite's `IS` handles NULL equality |
| 3 | `sqlite3.Row` has no `.get()` method — `a.get("concept_expanded")` raised AttributeError | Changed to `a["concept_expanded"]` |
| 4 | Subject alias: quiz stores `subject_id = "history"` but syllabus and scoring use `"history_amac"` | Added `SUBJECT_ALIASES = {"history": "history_amac"}` in batch_analyse.py and quiz.py |

**File changed:** `scripts/score_engine.py`

---

### 4. Polity/economy subtopic tracking was completely broken

General diagnostics (no specific subtopic in config) stored `subtopic_id = ""` for all answers.
`_update_subtopic_scores` skips empty subtopic_ids → nothing accumulated → 0% forever.

**Fixes:**
- `scripts/score_engine.py` `close_session()`: converts `sqlite3.Row` answers to dicts,
  backfills missing `topic_id`/`subtopic_id` from session config when blank
- `backend/routes/quiz.py`: when no subtopic in config, injects the subject's valid subtopic
  list and tells Claude to tag each question individually (was previously sending an empty
  string placeholder Claude dutifully copied)
- **Historical data repair:** `scripts/repair_subtopics.py` — one-time Claude Haiku call to
  classify all 22 existing polity/economy questions by subtopic. Run and complete. Can be
  deleted if you want to clean up.

---

### 5. Quiz clustering — all questions on one subtopic

A general polity diagnostic fetched 5 ChromaDB chunks from wherever semantic search landed
(often all from election commission content), then Claude generated all 10 questions from
those same 5 chunks. No subject breadth at all.

**Fix:** `backend/routes/quiz.py` — `_allocate_questions_across_subtopics()`

Algorithm:
1. Load all syllabus subtopics for the subject
2. Sort: **untested subtopics first**, then by PYQ weight descending within each group
3. Select top `N` subtopics (where N = num_questions, covering 1 unique subtopic per question)
4. Allocate questions proportionally to PYQ weight (minimum 1 each)
5. Fetch 2 ChromaDB chunks **per subtopic** separately
6. Pass structured allocation table to Claude with exact counts and `[UNTESTED]` labels

`prompts/diagnostic_quiz.txt` rewritten to use `{{subtopic_allocation}}` block instead of a
single subtopic placeholder.

**Result:** 10-question polity diagnostic now covers 10 different untested subtopics, one each.

---

### 6. Plan generator was scheduling blind

Claude was generating tomorrow's plan with only the prep profile (subject-level scores) and
no knowledge of *which* subtopics remain untested.

**Fix:** `scripts/plan_generator.py` — `compute_subtopic_coverage()` reads syllabus +
subtopic_scores + PYQ weights, builds per-subject lists of untested subtopics sorted by
priority weight. This is injected into the plan prompt as `{{subtopic_coverage}}`.

`prompts/plan_generation.txt` now has 8 explicit scheduling rules:
- Untested high-weight subtopics fill today's slots first
- Minimum 3 subjects per day
- Lower-weight untested subtopics are deferred with explicit "queue for Day X" rationale
- Re-test rules tied to score thresholds and days remaining
- Day 8–10 switches to hard difficulty and drops new diagnostics

---

### 7. Minor: tracker.py SAR endpoint

`backend/routes/tracker.py` — SAR endpoint used fragile tuple index access (`row[1]`, `row[2]`)
on a connection without `row_factory`. Fixed to named column access with `row_factory = sqlite3.Row`.

---

## Current state (Day 6 of 10)

```
Overall readiness: 3.0%   ← honest. 15/205 subtopics tested.

polity:         12.5%  (6/41 tested)   — election_commission heavy, 50% accuracy
economy:        24.2%  (8/24 tested)   — mixed scores across 8 subtopics
history_amac:    3.3%  (1/29 tested)   — IVC only, 100% but 1 subtopic
modern_history:  0.0%  (0/14 tested)
geography:       0.0%  (0/25 tested)
environment:     0.0%  (0/22 tested)
science_tech:    0.0%  (0/15 tested)
current_affairs: 0.0%  (0/12 tested)
ir_governance:   0.0%  (0/12 tested)
csat:            0.0%  (0/11 tested)
```

DB: 1,081 PYQ questions loaded, 15 subtopics tracked in subtopic_scores.

---

## Open problems — pick one up

These are listed in rough priority order. The top items have the most impact on scoring accuracy.

---

### P1 — PYQ weights are all 1.0 for most subtopics [HIGH IMPACT]

`priority_scorer.py` computes weights from the `pyq_questions` table using the `subtopic_id`
column. Most subtopics show weight 1.0 because the `subtopic_id` values in `pyq_questions`
don't match the IDs in `syllabus.json`.

**Diagnose with:**
```sql
SELECT subtopic_id, COUNT(*) FROM pyq_questions
WHERE subtopic_id IS NOT NULL
GROUP BY subtopic_id ORDER BY 2 DESC LIMIT 30;
```

Compare output against `data/syllabus.json` subtopic IDs. If the IDs diverge, a normalisation
map (like `SUBJECT_ALIASES` but for subtopics) or a re-ingestion pass that tags questions
with canonical syllabus IDs will fix the priority ordering. Until this is done,
"priority-based scheduling" degrades to "random order" across subtopics.

---

### P2 — ChromaDB content coverage unknown [HIGH IMPACT]

When ChromaDB returns no chunks for a subtopic, `quiz.py` falls back to:
```
"Standard UPSC Prelims content on X — generate from canonical syllabus knowledge."
```
This means questions come from Claude's training knowledge, not Rahul's study material.
The RAG pipeline advantage is lost.

**Diagnose:** query ChromaDB to see what's indexed and for which subjects. A simple script
to list all distinct `subject_id` metadata values and chunk counts per subject would show
the gaps. Then re-run `scripts/ingest.py` for missing subjects.

---

### P3 — Session summaries not backfilled after subtopic repair [MEDIUM IMPACT]

`session_summaries.weak_subtopics` and `session_summaries.strong_subtopics` are JSON arrays
computed at session close time. The historical polity/economy sessions computed these when
`subtopic_id = ""`, so both arrays are `[]` for all past sessions.

`batch_analyse.py`'s `get_persistently_weak_subtopics()` reads from session_summaries to
find subtopics that were weak in 2+ sessions. It currently can't identify any persistent
weaknesses from historical data.

**Fix:** after `repair_subtopics.py` classified all historical answers, re-compute
`weak_subtopics` and `strong_subtopics` for past sessions using the corrected subtopic data,
and UPDATE the session_summaries rows.

---

### P4 — No cross-session question deduplication [MEDIUM IMPACT]

Every `generate_quiz` call is fully independent. Running a polity diagnostic twice can
produce identical questions. The DB has a `question_hash` column in `session_answers` but
it's never used to filter what Claude generates.

**Fix options:**
- Before generating, fetch recent `question_hash` values for the subject from `session_answers`
  (last 30 days) and pass them to Claude as "do not repeat these question hashes"
- Simpler: pass the last N question texts as excluded topics in the prompt

---

### P5 — Difficulty engine incompatible with 1-question-per-subtopic mode [LOW IMPACT]

`_update_subtopic_difficulties` in `score_engine.py` requires 3+ answers per subtopic before
updating the difficulty tier. The new multi-subtopic allocation gives 1 question per subtopic.
Difficulty never updates in diagnostic mode.

**Fix:** either lower the threshold to 1 for diagnostics, or separate the difficulty-tracking
logic from the per-subtopic answer grouping so single-answer sessions still move the dial
(perhaps with a dampened update).

---

### P6 — Plan scheduling is LLM-decided, not deterministically enforced [LOW IMPACT]

The plan generator passes scheduling rules to Claude and trusts the output. Claude can ignore
the rules or make suboptimal choices. There's no post-generation validation.

**Fix:** add a Python function that validates Claude's plan output against the rules (session
time fits hours budget, minimum 3 subjects covered, no re-testing >75% subtopics) and
either corrects violations programmatically or retries the Claude call with the specific
rule that was broken.

---

### P7 — No auto-start on Mac reboot [LOW IMPACT / NICE TO HAVE]

Both servers (uvicorn + Next.js) must be manually started after every Mac restart.

**Fix:** `pm2` process manager or two macOS `launchd` plist files that start the servers
at login. See `PLAN.md` for the earlier notes on this.

---

### P8 — CSAT system exists but is completely untested

`backend/routes/csat.py` and `web/src/app/csat/page.tsx` exist but have never been run.
The CSAT prep profile (`data/prep_profile_csat.json`) doesn't exist yet. Treat it as a
separate mini-project: get CSAT diagnostic sessions working the same way the GS system now works.

---

## How to run locally

```bash
# Install Python deps (from project root)
pip install -r requirements.txt

# Install frontend deps
cd web && npm install

# Copy env (ask Rahul for the .env file — contains ANTHROPIC_API_KEY)
cp .env.example .env

# Start backend
cd backend && uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Start frontend (dev)
cd web && npm run dev
# OR for phone access:
cd web && npm run build && npm run start -- -H 0.0.0.0
```

Key env vars: `ANTHROPIC_API_KEY`, `DB_PATH` (default `data/upsc.db`),
`CHROMA_PATH` (default `vector_store`), `PROJECT_PATH` (root of repo).

---

## What changed — May 12 (per-question time capture)

Per-question time capture: `time_taken_sec` now populated from frontend timer in `diagnostic/page.tsx`.

- Added `questionStartTime` state (initialised to `Date.now()`)
- `useEffect` resets the timer whenever `currentQ` changes
- `startSession` also resets the timer on new session start
- Both `submitAnswer` and `skipQuestion` compute `Math.round((Date.now() - questionStartTime) / 1000)` and pass it as `time_taken_sec` (was always `0`)
- `useEffect` import added to the React import line

No backend changes needed — the DB column and API field already existed.

---

## Files changed in this session

```
backend/routes/config.py      redirect_slashes fix
backend/routes/quiz.py        multi-subtopic allocation, chunk fetching per subtopic
backend/routes/tracker.py     SAR endpoint row_factory fix
prompts/batch_analysis.txt    added coverage_report section, Claude no longer sets numbers
prompts/diagnostic_quiz.txt   rewritten to use {{subtopic_allocation}} block
prompts/plan_generation.txt   rewritten with 8 scheduling rules + {{subtopic_coverage}}
scripts/batch_analyse.py      compute_weighted_readiness(), SUBJECT_ALIASES, coverage_report
scripts/plan_generator.py     compute_subtopic_coverage(), syllabus+DB+PYQ integration
scripts/repair_subtopics.py   one-time historical data fix (can delete)
scripts/score_engine.py       close_session backfill, IS ? NULL fix, .get() → [] fix
web/src/app/page.tsx          sequential fetches, handleSync fix
web/src/lib/api.ts            relative BASE url, AbortController timeout
```
