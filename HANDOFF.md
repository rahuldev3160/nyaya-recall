# HANDOFF.md — Dev Session Update (May 14, 2026 — evening)

### Quick wins — ISSUE-022 / ISSUE-020 / ISSUES.md housekeeping — 2026-05-14
- prompts/session_notes.txt: Core Concept section rewritten with substantive explanation requirement
- web: difficulty badge now shows "Medium difficulty" instead of raw "medium"
- ISSUES.md: ISSUE-007, 008, 012, 016, 021, 023 marked Resolved (were fixed in merged PRs)

---

### ISSUE-018 + ISSUE-019 — session/page.tsx revision deck + per-question notes — May 14

- `web/src/app/session/page.tsx`: revision deck now shows after adaptive session finish (matches diagnostic page) — `revisionNotes` + `revisionLoading` state added, `finishSession()` calls `api.getRevisionNotes`, finished view renders wrong-answer cards with explanation.
- `web/src/app/session/page.tsx` + `backend/routes/sessions.py`: notes textarea in My Notes drawer resets per question (`perQuestionNotes[currentQ]` state), autosaves with 700ms debounce linked to `question_context_index`, reloads saved note on question return. Backend adds `session_question_notes` table (lazy `CREATE TABLE IF NOT EXISTS`, no ALTER TABLE) and extends PUT/GET user-notes endpoints to handle per-question rows.

---

> Read `COLLAB.md` first for the full project context and architecture overview.
> This file covers what changed in the most recent dev session and what still needs work.

---

## What changed — May 14 evening session

### 1. All 4 PRs merged and live

All open PRs were merged and servers restarted with the full build:

| PR | Branch | What it shipped |
|----|--------|----------------|
| PR #3 | fix/explanation-quality | Explanation quality overhaul (ISSUE-009/010/011/013), feature inbox, audio scripts |
| PR #2 | fix/session-ux-improvements | Submit button, ← Previous, finish score, completed badge, CSAT exclusion |
| PR #4 | fix/issue-008-session-review | Session history page (`/sessions`), session review page (`/sessions/[id]`), ChromaDB audit script |

Frontend rebuilt (`npm run build`) — both servers running as background processes.

### 2. Sound alert on approval gates

**Problem:** Rahul studies in another window and misses approval requests.

**Fix:**
- `~/.claude/settings.json` — added `Notification` hook (`afplay Ping.aiff`) + added `Bash(afplay *)` and `Bash(pkill *)` to allow list
- `CLAUDE.md` — new rule under Approval Gates: run `afplay /System/Library/Sounds/Ping.aiff` before writing any approval question
- Memory saved: `feedback_sound_alert.md`

**How it works:** `Notification` hook fires for background system events. For mid-conversation approval questions, Claude must manually call `afplay` as a Bash tool before asking.

---

## Open issues — current priority order

### 1. Session UX fixes — PR #2 open (fix/session-ux-improvements), awaiting merge

Five issues fixed in one PR:

| Issue | What changed | File |
|-------|-------------|------|
| ISSUE-021 | Submit button before answer reveal — option click highlights blue, Submit reveals | `web/src/app/diagnostic/page.tsx`, `web/src/app/session/page.tsx` |
| ISSUE-007 | ← Previous button on both quiz pages, currentQ > 0 only | same |
| ISSUE-016 | Session finish screen now shows score % + correct/total | `web/src/app/session/page.tsx` |
| ISSUE-023 | Completed sessions show green ✓ badge in Today's Sessions list | `web/src/app/session/page.tsx` |
| ISSUE-012 | CSAT excluded from GS1 readiness in `_build_syllabus_map()` | `scripts/batch_analyse.py` |

Also added `whitespace-pre-wrap` to question text on both pages (fixes statement formatting).

**Next action:** Rahul to merge PR #2 from phone. No approval gates — all UI-only or additive changes.

---

### 2. Feature idea inbox system — shipped to fix/explanation-quality branch

New files:
- `FEATURE_IDEAS.md` — structured idea inbox (Raw → Reviewed → Staged → Won't Build)
- `scripts/log_feature.sh` — `log-feature "idea"` from terminal, auto-commits
- `~/.zshrc` — `log-feature` alias added
- `CLAUDE.md` — session-start workflow: sync GitHub Issues with `feature-request` label, evaluate Raw ideas, route to FEATURES.md or Won't Build (Suggested)
- `.github/ISSUE_TEMPLATE/feature_request.md` — updated for phone logging

**Phone logging flow:** GitHub mobile app → repo Issues → New Issue → Feature request template → add `feature-request` label → submit. Claude picks up at next session start.

**GitHub auth:** `gh` CLI now authenticated as `rahuldev3160`. Token in macOS keychain. Use `GH_TOKEN=$(security find-internet-password -s github.com -a rahuldev3160 -w)` prefix in bash scripts since keychain isn't available in subshells.

---

### 3. fix/explanation-quality branch — NOT yet merged to main

This branch has important fixes that should be merged before or alongside PR #2:
- Explanation quality overhaul (ISSUE-009, 010, 011, 013): options context in prompts, no preamble in revision deck, per-wrong-option explanations
- Notes synthesis + audio scripts
- Feature inbox files (FEATURE_IDEAS.md etc.)

**Next action:** open a PR for fix/explanation-quality → merge it → then merge PR #2.

---

### 4. Global Claude Code permissions configured

`~/.claude/settings.json` updated — routine dev tools (git, npm, python, gh, ls, find, grep, curl, etc.) are auto-approved. Private folders (~/Documents, ~/Downloads, ~/Library, /etc, /System) are denied. No prompts for routine work.

---

## Open issues — current priority order

| # | Issue | Priority | Notes |
|---|-------|----------|-------|
| ISSUE-007/016/021 | ← Previous + score + submit confirm in `session/page.tsx` | P1 | Patterns already done in `diagnostic/page.tsx` — one PR |
| ISSUE-023 | Sessions not marked complete in Today's plan | P1 | Need to investigate which component renders plan sessions |
| ISSUE-020 | "Medium" label unclear | P1 | Replace with "Medium difficulty" or add context |
| ISSUE-019 | Note box doesn't reset/autosave per question | P1 | `session_user_notes` table exists; wire per-question index |
| ISSUE-022 | Session notes missing core concept depth | P1 | Rewrite Core Concept section in `prompts/session_notes.txt` |
| ISSUE-018 | No revision notes on session finish (adaptive) | P1 | Diagnostic has it; check if `session/page.tsx` also calls it |
| ISSUE-012 | CSAT in tracker UI / readiness scoring | P1 | Audit `batch_analyse.py` + tracker page |
| ISSUE-017 | Note-taking as feedback/training data | P1 | Spec needed first → `plans/feedback_training.md` |
| ISSUE-014 | Portal time tracker | P2 | Spec needed |
| ISSUE-015 | AI chat integration evaluation | P2 | Cost/benefit analysis needed |

## Pending one-time tasks (need Rahul go-ahead)

| Task | Cost | What it does |
|------|------|--------------|
| `python3 scripts/retag_pyq_subtopics.py` | ~$0.05 | Better PYQ→subtopic matching; improves readiness scoring |
| `python3 scripts/check_chroma_coverage.py` | Free | Audit which subjects have thin/missing study material in ChromaDB |

---

## Branch state

| Branch | State |
|--------|-------|
| `main` | All 4 PRs merged and live. Clean. |

---

## Start commands (unchanged)

```bash
# Tab 1 — Backend
cd "/Users/rahulsingh/Desktop/Claude Projects/Last 10 Day AI powered Preparation/backend"
uvicorn server:app --host 0.0.0.0 --port 8000

# Tab 2 — Frontend
cd "/Users/rahulsingh/Desktop/Claude Projects/Last 10 Day AI powered Preparation/web"
npm run start -- -H 0.0.0.0

# Phone (Tailscale): http://100.113.107.75:3000
```

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

### ✅ P1 — PYQ weights fixed (May 12) [RESOLVED]

`priority_scorer.py` now uses subject-scoped token-overlap to normalise free-text PYQ
subtopic descriptors to canonical syllabus IDs. 139 subtopics now have real varied weights.

For full coverage (~70% of questions still unmatched by token overlap), run:
```bash
python3 scripts/retag_pyq_subtopics.py --dry-run   # preview
python3 scripts/retag_pyq_subtopics.py              # costs ~$0.05 Haiku
```

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

## What changed — May 12 (PYQ subtopic ID normalisation)

### Root cause found
`priority_scorer.py` was returning weight 1.0 (default floor) for virtually every syllabus
subtopic because `pyq_questions.subtopic_id` values are free-text descriptors generated by
Claude at ingestion time (e.g. `directive_principles`, `rbi_operations`) — not the 205
canonical IDs in `data/syllabus.json`. Only 14 of 979 PYQ subtopic IDs matched directly.

### Fix applied (Option B — fuzzy normalisation in priority_scorer.py)
Added `_normalise(pyq_subtopic_id, subject_id)` in `priority_scorer.py`:
1. Direct match check (fast path)
2. Subject-scoped token-overlap: splits both IDs on `_`, computes `|intersection|/|min(|A|,|B|)|`
3. Falls back to full-syllabus search if subject-scoped fails
4. Discards matches below threshold 0.5

Result: `compute_all_priorities()` now returns **139 syllabus subtopics with real varied weights**
(was 0). Top weights: `rivers_india: 8.66`, `space_applications: 5.58`, `parliamentary_procedures: 5.48`.

### Remaining gap — ~70% of PYQ questions still unmatched
903 of 979 PYQ subtopic IDs appear only once (highly specific: `bodhisattva_concept`,
`congress_split`, etc.) and share no tokens with the 205 syllabus IDs.

### Option C script written (DO NOT RUN — costs ~$0.05)
`scripts/retag_pyq_subtopics.py` — one-time Claude Haiku script that classifies every PYQ
question against the relevant syllabus subtopic list and UPDATEs the DB in-place.

**When to run:** once Rahul approves the API spend. Run with `--dry-run` first to preview.
After running, all 1069 PYQ questions will have canonical subtopic IDs and the fuzzy fallback
becomes a no-op.

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

## What changed — May 12 (synthesised session notes — ISSUE-005 / ISSUE-006)

Session notes in `notes_then_quiz` sessions now use Claude Haiku to synthesise structured
revision notes instead of dumping raw vector excerpts. Notes cover 4 fixed sections:
Core Concept · PYQ Angles · Current Affairs Linkages · Broader Linkages.
Results are cached by `SHA256(subtopic_id + chunk_texts)` in `cache/explanations.json` —
cache hit = 0 API tokens for repeat sessions on the same subtopic.

Source links (from ISSUE-003) are preserved and appended after the synthesised section.

CSAT sessions removed from today's plan and excluded from future plan generation.

**Files changed:**
```
prompts/session_notes.txt     new — Haiku prompt for structured notes synthesis
backend/routes/quiz.py        synthesize_notes_cached() replaces build_notes_from_vector_chunks()
scripts/prewarm_notes_cache.py  new — pre-warms cache for today's notes_then_quiz sessions
data/study_plan.json          CSAT sessions removed
scripts/plan_generator.py     CSAT excluded from subject list for future plans
```

---

## Files changed in this session

```
backend/routes/config.py      redirect_slashes fix
backend/routes/quiz.py        multi-subtopic allocation, chunk fetching per subtopic; synthesised notes (May 12)
backend/routes/tracker.py     SAR endpoint row_factory fix
prompts/batch_analysis.txt    added coverage_report section, Claude no longer sets numbers
prompts/diagnostic_quiz.txt   rewritten to use {{subtopic_allocation}} block
prompts/plan_generation.txt   rewritten with 8 scheduling rules + {{subtopic_coverage}}
prompts/session_notes.txt     new — Haiku notes synthesis prompt (May 12)
scripts/batch_analyse.py      compute_weighted_readiness(), SUBJECT_ALIASES, coverage_report
scripts/plan_generator.py     compute_subtopic_coverage(), syllabus+DB+PYQ integration; CSAT excluded (May 12)
scripts/prewarm_notes_cache.py  new — prewarm notes cache for today (May 12)
scripts/repair_subtopics.py   one-time historical data fix (can delete)
scripts/score_engine.py       close_session backfill, IS ? NULL fix, .get() → [] fix
web/src/app/page.tsx          sequential fetches, handleSync fix
web/src/lib/api.ts            relative BASE url, AbortController timeout
```

---

## What changed — May 14 (explanation quality overhaul — ISSUE-009/010/011/013)

### Root causes fixed

**Revision deck contradictory/false explanations (ISSUE-009):**
`get_revision_notes()` in `sessions.py` was selecting only `question_text, correct_answer, user_answer` — the option texts were never fetched from the DB. Haiku was generating explanations for options it couldn't read, causing hallucinated or contradictory content.

**Fix:**
- `backend/routes/sessions.py` — SELECT now includes `options` (stored as JSON); parsed and injected as `{{option_a}}` / `{{option_b}}` / `{{option_c}}` / `{{option_d}}` into the prompt.
- `prompts/revision_notes.txt` — rewritten: includes all 4 option texts, explicit instruction not to restate "you chose X / correct is Y" (UI already shows this), leads with the correct fact then explains why each wrong option is wrong.
- `max_tokens` bumped 300 → 600 (needed for full 4-option explanation).
- Cache key changed to `:v2` — stale entries (generated without option texts) will not be served; all past wrong-answer sessions will regenerate on next view.

**Per-question explanation enrichment (ISSUE-013):**
All three quiz generation prompts had weak/empty explanation specs. Updated in all three files to: lead with the core fact for the correct option, then one sentence per wrong option.

**Statement-based question formatting (ISSUE-011):**
No prompt instruction to use `\n` between statements; question text paragraphs lacked `whitespace-pre-wrap`. Fixed in both prompts and both frontend pages.

### Files changed (May 14)

```
prompts/diagnostic_quiz.txt    explanation spec + statement \n format rule
prompts/adaptive_session.txt   explanation spec updated (was "...")
prompts/adaptive_quiz_only.txt explanation spec + statement \n format rule
prompts/revision_notes.txt     full rewrite — options context, no preamble, explains wrong options
backend/routes/sessions.py     fetch options column, parse + inject into prompt, max_tokens 600, cache :v2
web/src/app/diagnostic/page.tsx whitespace-pre-wrap on question text and revision deck question text
web/src/app/session/page.tsx   whitespace-pre-wrap on question text
ISSUES.md                      all unnumbered issues assigned ISSUE-009 through ISSUE-023; ISSUE-002 resolved; ISSUE-004 won't fix
```

### Watch-outs
- All cached revision notes from previous sessions will regenerate on next view (by design — stale cache was the problem). Cost: ~$0.001 per wrong answer (Haiku).
- Quiz generation prompts changed — new sessions will produce longer explanations (4-6 sentences instead of 2-3). This increases output tokens slightly per quiz generation call.
