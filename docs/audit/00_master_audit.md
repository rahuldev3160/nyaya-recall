# Devthorium Master Audit Report

**Date:** 2026-05-17  
**Auditors:** Three specialist agents (Product, Architecture, Code Quality) + synthesis  
**Source tracks:** `01_product_feature_gap.md`, `02_architecture_analysis.md`, `03_code_quality_review.md`  
**Purpose:** Inform the next development sprint — understand what was built, what's broken, and what to fix first.

---

## Executive Summary

Devthorium is a technically ambitious local AI prep system. The core infrastructure (quiz engine, scoring, PYQ weighting, vector notes, tracker, planner) is real and functional. The quiz UX is polished. The knowledge hierarchy (subject → topic → subtopic → dimension) is among the most sophisticated data models in any self-study tool.

**But the system's central claim — "adaptive 10-day UPSC prep" — is only half-true.**

The adaptive loop's most important feature (knowing when to stop diagnosing and start revising) was never built. CSAT is a stub page. The Day 11 exam-eve experience doesn't exist. The content pre-batching that eliminates the 30–40 second loading wait was never built. Approximately 40% of what shipped was reactive scope creep that displaced original P0 commitments.

There are also 6 critical bugs that silently corrupt data (wrong scores, lost SAR updates, stale timer closures) and 3 P0 architecture risks (concurrent DB lock, data loss on sync timeout, real-time API calls mid-session).

The system is usable and valuable today. But it has a floor, not a ceiling — and that floor is lower than the documentation suggests.

---

## Section 1: Vision vs Reality

### What was promised (PLAN.md)

| Original Feature | Reality | Verdict |
|---|---|---|
| Two-round adaptive diagnostic (Round 1 → assess → Round 2 for Uncertain) | Not built. Every subtopic gets one pass only. | **Missing** |
| Mid-day confidence check (Conditions A/B/C — auto-pivot diagnostic→revision) | Not built. User decides manually. | **Missing** |
| Content pre-batching ($0.15/day, zero API cost during sessions) | Not built. Sessions generate on-demand, 30–40s wait. | **Missing** |
| CSAT — fully separate system | Stub page. Zero functional implementation. | **Missing** |
| Day 11 / exam-eve personalised view | Not built. Strategy page is generic hardcoded advice. | **Missing** |
| Offline HTML export + JSON import | Not built. Tailscale makes it lower priority but gap exists. | **Missing** |
| Plan validation layer (deterministic scheduling rules) | Not built. Claude decides plan; rules are prompt-only constraints. | **Missing** |
| Spaced repetition for weak subtopics | Not built. Not even specced. | **Missing** |
| Topic priority weighting (PYQ decay formula) | Built but operates on ~30% of PYQ signal. 70% discarded. | **Partial** |
| Adaptive revision — score-based session format | Built structurally, but LLM-decided (not deterministically enforced). | **Partial** |
| Self-attestation + SAR | Built, but SAR silently fails on first attestation (BUG-04). | **Partial** |
| Per-question time capture | Built in diagnostic page. Hardcoded to 0 in session page (data corrupt). | **Partial** |
| Phone access (WiFi) | Exceeded — Tailscale works any-network. | **Exceeded** |
| Core quiz engine + scoring | Shipped and functional. | **Done** |
| PYQ ingestion (1,081 Q, 2009–2025) | Shipped. | **Done** |
| Tracker (topic/subtopic breakdown) | Shipped, minus trend arrows. | **Done** |
| Session history + review | Shipped (unplanned, user-requested). | **Done (unplanned)** |
| Dimension-aware scoring (FEATURE-027) | Shipped but dimension IDs unvalidated; thresholds possibly inverted. | **Done (needs fix)** |
| Exam simulation mode | Shipped (unplanned, exceeded rough spec). | **Done (unplanned)** |

### Scope Creep Pattern

~40% of what shipped (dimension scoring, multi-subtopic sessions, exam sim, content feedback, user-editable plan, session history) was not in the original PLAN.md. These are individually valuable but collectively displaced the completion of P0 original commitments (mid-day confidence check, Round 2 diagnostic, CSAT, Day 11 view).

---

## Section 2: Critical Issues — Fix Before Next Study Session

These are P0: silent data corruption, daily data loss risk, or system-breaking failures.

---

### CRITICAL-01 — `time_taken_sec` always 0 in adaptive sessions (data corruption)

**Track:** Product (P0) + Code (TS)  
**File:** `web/src/app/session/page.tsx` — `submitAnswer()` hardcodes `time_taken_sec: 0`  
**Problem:** Per-question timing data is correctly captured in `diagnostic/page.tsx` but hardcoded to 0 in `session/page.tsx`. Adaptive sessions (the majority of daily use) produce zero timing data. The difficulty engine and metacognition analysis run on corrupt data.  
**How it improves the system:** Fixes the difficulty engine signal source for all adaptive sessions; makes time-per-question analytics meaningful.  
**Fix:** Add `const questionStartTime = useRef(Date.now())` and reset it in the `currentQ` useEffect. Compute `Math.round((Date.now() - questionStartTime.current) / 1000)` in `submitAnswer()`. Identical pattern is already in `diagnostic/page.tsx`.  
**Effort:** 1 hour.

---

### CRITICAL-02 — SQLite WAL mode not enabled (concurrent access DB lock)

**Track:** Architecture (P0)  
**File:** All route files — `sqlite3.connect(DB_PATH)` with no WAL pragma  
**Problem:** Phone and desktop used simultaneously triggers `OperationalError: database is locked`. The phone access use case is a documented core feature. Under the current architecture it silently fails under dual-use. There are also 5+ connections opened per quiz generation request.  
**How it improves the system:** Phone + desktop concurrent use becomes reliable. One connection manager eliminates the 5-connection overhead per quiz generation.  
**Fix:** Create `backend/db.py` with a `get_db()` context manager that runs `PRAGMA journal_mode=WAL; PRAGMA timeout=10000;` on first use. All routes import from `db.py`.  
**Effort:** 2–3 hours (mechanical — same pattern repeated across 6 route files).

---

### CRITICAL-03 — `mark_synced()` runs before `save_profile()` — permanent data loss on API timeout

**Track:** Architecture (P0)  
**File:** `scripts/batch_analyse.py` — `run_analysis()` function  
**Problem:** Sessions are marked `synced=1` before the Claude API call completes and the profile is saved. A Sonnet API timeout (common at 30+ second prompts) marks sessions as permanently synced but the profile is never updated. Those sessions are excluded from all future analysis. The user's study history is silently discarded.  
**How it improves the system:** A sync timeout no longer loses data. Sessions remain available for the next sync attempt. The readiness profile always reflects the actual DB state.  
**Fix:** Move `mark_synced(session_ids)` to AFTER `save_profile(profile)` succeeds. Wrap both in a try/except that only commits on full success.  
**Effort:** 30 minutes.

---

### CRITICAL-04 — `expand-concept` and `expand-notes-selection` make real-time API calls mid-session

**Track:** Architecture (P0)  
**File:** `backend/routes/sessions.py`  
**Problem:** Both endpoints call the Anthropic Haiku API synchronously mid-session. This directly violates the "zero API calls during quiz sessions" rule in CLAUDE.md. On API latency, the user waits 3–5 seconds mid-question. Responses are not cached — every "Dive deeper" click on the same question makes a new API call.  
**How it improves the system:** First expand on a question costs ~$0.001; all subsequent views are instant and free. Restores the core architectural invariant.  
**Fix:** In `sessions.py`, check `cache/explanations.json` with key `SHA256(question_hash + ":expand")` before the API call. Write result on cache miss.  
**Effort:** 2 hours.

---

### CRITICAL-05 — SAR silently fails on first attestation after any DB reset

**Track:** Code (BUG-04, P0)  
**File:** `scripts/self_attestation.py` — `record_attestation()` and `_update_sar()`  
**Problem:** Both functions use bare `UPDATE ... WHERE user_id=?`. If no row exists in `sar_scores` (first attestation, or after a DB reset), the UPDATE silently affects 0 rows. SQLite does not raise an error. The SAR value is lost, the improvement feedback loop is broken from session 1.  
**How it improves the system:** SAR updates correctly from the very first attestation. The calibration system actually works as designed.  
**Fix:** Change both `UPDATE` statements to `INSERT INTO sar_scores (...) VALUES (...) ON CONFLICT(user_id) DO UPDATE SET ...` pattern.  
**Effort:** 30 minutes.

---

### CRITICAL-06 — `close_session` crashes with KeyError on `concept_expanded` column

**Track:** Code (PY-10, P1 escalated)  
**File:** `scripts/score_engine.py` line 218  
**Problem:** `a["concept_expanded"]` raises KeyError on any DB that predates the column addition. `close_session` crashes silently (bare `except`), the session end_time is not written, and the session is permanently orphaned — never scored, never synced.  
**How it improves the system:** Session close never crashes for DB column reasons. All sessions score correctly regardless of schema vintage.  
**Fix:** Change to `a.get("concept_expanded") and a.get("subtopic_id")`.  
**Effort:** 5 minutes.

---

### CRITICAL-07 — Hardcoded exam date in `plan.py` — system breaks after May 20, 2026

**Track:** Architecture (P0)  
**File:** `backend/routes/plan.py` line 214 — `EXAM_DATE = datetime.date(2026, 5, 20)`  
**Problem:** The trajectory endpoint returns `days_remaining = 0` after May 20. The system becomes partially non-functional after the hardcoded date without a code change. `prep_config.json` has a `start_date` field but no `target_date`.  
**How it improves the system:** System works correctly for any exam date. Reusable across future exam cycles.  
**Fix:** Add `target_date` to `prep_config.json` (auto-set to `start_date + total_days`). Replace `EXAM_DATE` constant with `config.get("target_date")`.  
**Effort:** 1 hour.

---

## Section 3: Design Flaws and Recommendations

### DESIGN-01 — The adaptive loop is incomplete ("adaptive" claim is partially false)

**Problem it solves:** Users have no system signal for when to stop diagnosing and start revising. The two-round adaptive cycle (Round 1 → 75%/50% thresholds → Round 2 for Uncertain) was never built. The mid-day confidence check (Conditions A/B/C from PLAN.md) doesn't exist. The system cannot autonomously recommend phase transitions.  
**How it improves the system:** After completing each subject diagnostic, the backend checks: total subjects assessed, average confidence level, score variance. It surfaces a recommendation banner: "You've assessed 5 subjects. Your profile is confident enough — begin revision today." This turns the system from a passive quiz tool into an actual adaptive guide.  
**Priority:** P0 — the adaptive claim is the product's central value proposition.  
**Effort:** 1–2 days.

---

### DESIGN-02 — Day 11 / Exam-eve personalised view missing

**Problem it solves:** The most high-stakes moment (exam morning) has no personalised support. Strategy page shows hardcoded generic content — attempt order, PYQ patterns — that doesn't use the user's actual prep_profile scores.  
**How it improves the system:** A Day 11 view that auto-activates when `days_remaining ≤ 1`: (a) overall readiness with confidence label, (b) top 5 subtopics below 65% with highest PYQ weight (quick revision list), (c) personalised attempt order from actual subject scores, (d) a "watch out for X" message from the profile.  
**Priority:** P0 — this is the promised Day 11 experience in PLAN.md.  
**Effort:** 1 day.

---

### DESIGN-03 — CSAT is a dead stub despite being a qualifying requirement

**Problem it solves:** UPSC Prelims requires clearing the CSAT cutoff (33%). A system claiming "10-day Prelims prep" provides zero CSAT support. The routes, frontend page, and syllabus entries (11 subtopics, 64 dimensions) all exist — nothing is wired.  
**How it improves the system:** Activate the existing CSAT backend routes, create `prep_profile_csat.json`, enable a CSAT diagnostic (comprehension + reasoning — skip numeracy per ISSUE-012's lesson on LLM calculation errors). Show a CSAT readiness score separate from GS on the dashboard.  
**Priority:** P1 — Paper II is a qualifying barrier. Its absence is a product-completeness gap.  
**Effort:** 3–4 days.

---

### DESIGN-04 — Content pre-batching never built — 30–40 second loading wait

**Problem it solves:** The original plan promised `$0.15/day` upfront content batch so quiz sessions have zero API latency. What was actually built generates questions on-demand at session start, producing a 30–40 second wait with no feedback. On the exam-sim page, this extends to 60+ seconds for 50-question sets.  
**How it improves the system:** Pre-batch all day's sessions in 2–3 API calls each morning (extended `prewarm_notes_cache.py` to also pre-generate quiz questions and cache them keyed by session config). Sessions then start in <1 second.  
**Priority:** P1 — the loading experience is the most trust-breaking moment in the product.  
**Effort:** 2–3 days.

---

### DESIGN-05 — Strategy page is hardcoded generic advice, not profile-driven

**Problem it solves:** The attempt order table (Polity first, Environment second, etc.) is static JSX. A user who is weak at Polity and strong at Economy should see a different recommended attempt order.  
**How it improves the system:** Read `prep_profile.json` subject readiness scores and generate: (a) personalised attempt order (highest readiness first for momentum, unless a weak subject has very high PYQ frequency), (b) "Focus areas" filtered to only the subjects where the user is at risk.  
**Priority:** P1 — the Strategy page is the exam-day guide. It must be personalised.  
**Effort:** Half a day.

---

### DESIGN-06 — Plan validation layer never built — scheduling rules are prompt suggestions, not constraints

**Problem it solves:** Claude decides the plan. The 10 scheduling rules in `plan_generation.txt` are prompt constraints only — Claude can silently violate them (wrong subject count, over-testing a covered subtopic, ignoring topic balance). There's no way to know.  
**How it improves the system:** A post-generation Python validator checks: (a) total session time ≤ daily hours budget, (b) ≥ 3 subjects covered, (c) no re-testing >75% subtopics more than once this week, (d) untested high-weight subtopics represented. Violations are corrected deterministically or trigger a Claude retry with specific feedback.  
**Priority:** P1 — without this, the scheduling rules are aspirational, not enforced.  
**Effort:** 1 day.

---

### DESIGN-07 — Onboarding is a form, not an experience

**Problem it solves:** New users land on a setup page with sliders but no exam date input, no emotional hook, no "start here" gate. If setup is skipped, the dashboard shows 0% with unclear next steps.  
**How it improves the system:** The `plans/onboarding_redesign.md` spec is already written. Implement the 3-step flow: exam date picker → daily hours commitment → plan preview with "Start My Prep" CTA. Auto-calculate `total_days` from exam date. Show a full-width onboarding prompt if no config exists.  
**Priority:** P1 — first impression determines trust.  
**Effort:** 1 day (spec exists).

---

### DESIGN-08 — Multi-exam expansion requires 8 architectural changes

**Problem it solves:** The current system bakes in UPSC Prelims MCQ format across the data layer, scoring engine, and UI. Expanding to UPSC Mains, IES, or RBI Grade B requires systematic changes, not config toggles.  
**How it improves the system:** The minimum viable expansion path is IES Prelims (MCQ, heavy Economy overlap, 2–3 weeks). Requires: `exam_type` field in `prep_config.json`, separate `syllabus_ies.json`, separate prep profile file, `exam_id` column in `quiz_sessions` and `session_answers`. UPSC Mains requires a fundamentally different session loop (descriptive answers, Claude-evaluated scoring) — 6–8 weeks of new development.  
**Priority:** P2 — post-exam work, but plan for it now to avoid architectural lock-in.

---

## Section 4: Architecture Flaws and Recommendations

### ARCH-01 — Schema management spread across 4 places — drift guaranteed

**Problem:** `db_init.py`, `server.py` lifespan, `sessions.py` (two different `_ensure_question_notes_table` functions with different schemas), and `quiz.py` all create tables. There are two functions for the `question_notes` table with different index sets. Fresh install vs upgraded install produce different schemas.  
**How it improves the system:** Consolidating all `CREATE TABLE` statements in `db_init.py` with a `schema_version` table and lightweight migration runner means any install has a known, consistent schema. Add a CI check: no `CREATE TABLE` outside `db_init.py`.  
**Priority:** P1.

---

### ARCH-02 — `quiz.py` is 1,277 lines — no service layer

**Problem:** Route handlers, ChromaDB queries, cache I/O, question allocation algorithms, syllabus traversal, prompt rendering, and Anthropic API calls are all fused in one file. `generate_quiz()` is ~250 lines with three deeply nested conditional branches. Adding or testing any piece requires understanding the whole function. With no tests, this logic is untestable in isolation.  
**How it improves the system:** Extract `services/quiz_service.py` with `QuizAllocator`, `NotesCache`, `ChromaRetriever` classes. Route handlers become thin orchestrators <40 lines each. Individual service classes become testable and independently extensible.  
**Priority:** P1.

---

### ARCH-03 — `explanations.json` flat JSON cache degrades after Day 5

**Problem:** Full read-parse-write on every cache miss. Two separate cache systems (`content_cache.py` and `sessions.py`) both write to the same file with different key formats. No atomic writes. No TTL. Will grow to 2MB+ by Day 5 causing perceptible write latency.  
**How it improves the system:** Replace with a SQLite `notes_cache` table (O(log n) reads, atomic row writes, trivial TTL via `created_at`). Unify both cache modules into one.  
**Priority:** P1.

---

### ARCH-04 — `prep_profile.json` has no atomic write protection

**Problem:** `batch_analyse.py` writes the readiness profile with `PROFILE_PATH.write_text(...)`. A process kill or disk full during this write corrupts the entire readiness history. No backup exists.  
**How it improves the system:** Write to `.json.tmp` then atomically rename. Keep 3 rotated backups. Recovery from any crash scenario is possible.  
**Priority:** P1.

---

### ARCH-05 — 70% of PYQ priority signal is silently discarded

**Problem:** `priority_scorer.py` documents that only ~30% of PYQ questions are matched to canonical syllabus subtopic IDs via fuzzy token overlap. The adaptive difficulty, question ordering, and plan prioritisation run on 30% of the intended signal. `retag_pyq_subtopics.py` exists to fix this but is optional.  
**How it improves the system:** Making `retag_pyq_subtopics.py` a mandatory setup step (documented in PLAN.md Phase 1) ensures the priority weighting reflects actual UPSC exam patterns. Add a health check endpoint reporting PYQ match rate; warn UI when below 60%.  
**Priority:** P1 — the core intelligence of the system is impaired.

---

### ARCH-06 — Dimension coverage data tracked but never reaches the plan generator

**Problem:** `batch_analyse.py` computes dimension-level coverage (dimensions tested per subtopic). `plan_generator.py` plans at subtopic granularity only. A subtopic with 3/6 dimensions tested is treated identically to one with 6/6. The dimension infrastructure exists; the planner connection is missing.  
**How it improves the system:** `compute_subtopic_coverage()` in `plan_generator.py` joins `subtopic_dimension_scores` to add `dimensions_tested`/`dimensions_total` per subtopic. Claude can then plan sessions targeting specific untested dimensions, enabling true fine-grained coverage.  
**Priority:** P2.

---

### ARCH-07 — `run_analysis()` blocks the entire FastAPI server for 15–30 seconds

**Problem:** `analysis.py` calls `run_analysis()` synchronously in the request thread. During the Sonnet API call (15–30 seconds), the entire server is blocked. Any concurrent request (from phone, or plan generation) times out.  
**How it improves the system:** Move to a FastAPI `BackgroundTasks` pattern. Return a job ID immediately. Frontend polls `GET /analysis/status/{job_id}`. Server stays responsive during sync.  
**Priority:** P2.

---

### ARCH-08 — `dimension_id` values written to DB are never validated against syllabus

**Problem:** Claude writes `dimension_id` values in question JSON. These are stored as-is in `session_answers.dimension_id` with no validation against `syllabus.json`. Hallucinated or mismatched dimension IDs silently corrupt `subtopic_dimension_scores`.  
**How it improves the system:** In `score_engine.py`'s `record_answer()`, validate `dimension_id` against the syllabus. Store `NULL` and log a warning on mismatch. Makes dimension-level readiness metrics trustworthy.  
**Priority:** P2.

---

## Section 5: Code Flaws and Fixes

### CODE-01 — Readiness formula double-counts "extra" subtopics in denominator (BUG-03)

**File:** `scripts/batch_analyse.py` lines 337–351  
**Problem:** `total_weight` is computed from `all_subtopics`, then extra subtopics add to it again. The denominator and numerator are computed using different weight sets. Readiness scores are consistently understated for subjects with subtopic ID mismatches.  
**How it improves the system:** Corrects the readiness formula; scores will be slightly higher and more accurate, especially for subjects with many extra subtopics.  
**Priority:** P1.

---

### CODE-02 — Trend computation is cumulative vs cumulative — hides real regressions (BUG-02)

**File:** `scripts/score_engine.py` lines 280–286  
**Problem:** Both `new_score` and `old_score` are lifetime cumulative values. A user scoring 50% today on a subtopic they historically scored 90% will see "stable" trend, not "declining." The trend labels passed to Claude and shown in the tracker are misleading.  
**How it improves the system:** Trend reflects actual recent performance. Users receive accurate "declining" alerts and the plan generator responds with urgency.  
**Priority:** P1 — fix by adding a `last_session_score` column to `subtopic_scores` (additive, no ALTER needed if using a sidecar table).

---

### CODE-03 — Dimension score thresholds use 0–1 range but scores may be stored as 0–100 (BUG-11)

**File:** `scripts/batch_analyse.py` lines 169–174  
**Problem:** `_compute_subtopic_dim_coverage()` uses thresholds `>= 0.75` and `>= 0.45`. If `subtopic_dimension_scores.score` stores values in the 0–100 range (consistent with `subtopic_scores`), virtually every dimension shows `depth=1.0` — massive overestimation of readiness.  
**How it improves the system:** If confirmed as a 0–100 mismatch, fixing the thresholds to `>= 75` and `>= 45` makes FEATURE-027 dimension tracking actually reflect real preparedness.  
**Priority:** P1 — verify schema first, then fix.

---

### CODE-04 — Two overlapping per-question note tables — UI shows v1, planner uses v2 (DB-05)

**File:** `backend/routes/sessions.py`  
**Problem:** `session_question_notes` (v1, created lazily in sessions.py) and `question_notes` (v2, created in server.py lifespan) are both per-question note stores. The UI session page reads v1; `plan_generator.fetch_user_notes_signals()` reads v2. Notes saved in the session UI are invisible to the plan generator.  
**How it improves the system:** Notes the user takes during a session correctly influence tomorrow's plan (which subtopics to revisit, where confusion persists). The feedback loop that was built actually works.  
**Priority:** P1.

---

### CODE-05 — `{num_q}` appears as literal string in spillover prompt (PROMPT-02)

**File:** `backend/routes/quiz.py` line 283  
**Problem:** The f-string uses `{{num_q}}` which Python evaluates to the literal string `{num_q}`. Claude sees the placeholder text, not the actual question count. The spillover instruction is broken.  
**How it improves the system:** Spillover questions correctly reference the actual question count, enabling proper dimension exhaustion spillover.  
**Priority:** P1 — 5-minute fix.

---

### CODE-06 — Infinite loop risk in question allocation (BUG-06)

**File:** `backend/routes/quiz.py` lines 329–337  
**Problem:** The rounding correction loop `while diff != 0` has no iteration limit. When all allocations are floored at 1 and `diff < 0`, every index fails the guard and `i` increments forever.  
**How it improves the system:** Quiz generation never hangs. The server stays responsive under unusual weight distributions.  
**Priority:** P1 — add `max_iters = n_cover * (abs(diff) + 1)` guard.

---

### CODE-07 — Client-computed finish score ignores server score (TS-01)

**File:** `web/src/app/session/page.tsx` lines 554–557  
**Problem:** The finish screen computes the score from React state. If any answer failed to submit silently (network error caught by `.catch(() => {})`), the displayed score is higher than what was recorded in the DB. The server-returned score from `api.closeSession()` is thrown away.  
**How it improves the system:** Score displayed to user matches what's stored and what drives the readiness calculation. No discrepancy between "I saw 85%" and "tracker shows 70%."  
**Priority:** P1.

---

### CODE-08 — Timer expiry fires on stale closure — may re-submit answered questions as skipped (TS-08)

**File:** `web/src/app/diagnostic/page.tsx` line 200  
**Problem:** The timer effect only re-runs on `session_id` change. `handleTimerExpiry` captures stale `answers` and `skipped` state at creation time. If the user answers quickly after session start, the timer expiry may submit already-answered questions as skipped again.  
**How it improves the system:** Timed mode correctly records the user's actual answers, not a stale snapshot. Timed quiz scores become accurate.  
**Priority:** P1.

---

### CODE-09 — Cache keys use 16–20 char hash prefixes — collision risk (PY-03/04/05)

**Files:** `backend/routes/quiz.py` (20 chars), `scripts/content_cache.py` (16 chars)  
**Problem:** Short hash prefixes increase collision risk. With hundreds of subtopics, question texts, and cache entry types, two different questions could map to the same key and one receives the wrong cached explanation.  
**How it improves the system:** Using 32+ char prefixes (128-bit collision resistance) effectively eliminates cache key collisions for any realistic dataset size.  
**Priority:** P2 — 5-minute fix in 3 locations.

---

### CODE-10 — CORS wildcard + no auth on local network (SEC-02)

**File:** `backend/server.py` line 100  
**Problem:** `allow_origins=["*"]` with no authentication means any device on the same WiFi can read all study data, inject answers, close sessions, or corrupt scores.  
**How it improves the system:** Restricting to `["http://localhost:3000", f"http://{LAN_IP}:3000"]` closes the attack surface on public WiFi.  
**Priority:** P2 — low risk at home, meaningful risk at library/café.

---

## Section 6: Improvement Roadmap

### Sprint 1 — Fix Before Studying (1–2 days)

| Fix | File | Effort |
|---|---|---|
| CRITICAL-01: `time_taken_sec = 0` in session page | `web/src/app/session/page.tsx` | 1 hr |
| CRITICAL-03: `mark_synced` after `save_profile` | `scripts/batch_analyse.py` | 30 min |
| CRITICAL-05: SAR silent fail — `INSERT OR REPLACE` | `scripts/self_attestation.py` | 30 min |
| CRITICAL-06: `concept_expanded` KeyError | `scripts/score_engine.py` | 5 min |
| CRITICAL-07: Hardcoded exam date in `plan.py` | `backend/routes/plan.py` | 1 hr |
| CODE-05: `{num_q}` f-string literal in prompt | `backend/routes/quiz.py` | 5 min |
| CODE-06: Infinite loop guard in allocation | `backend/routes/quiz.py` | 30 min |
| CODE-09: Hash length to 32 chars | quiz.py, content_cache.py | 5 min |

---

### Sprint 2 — Core Architecture (3–5 days)

| Fix | Effort |
|---|---|
| CRITICAL-02: SQLite WAL + `db.py` module | 3 hrs |
| CRITICAL-04: Cache expand-concept responses | 2 hrs |
| ARCH-01: Consolidate schema in `db_init.py` | 2 hrs |
| ARCH-04: Atomic write for `prep_profile.json` | 1 hr |
| CODE-04: Merge two `question_notes` tables into one | 2 hrs |
| CODE-02: Fix trend computation (session vs cumulative) | 2 hrs |
| CODE-03: Verify + fix dimension score thresholds | 1 hr |
| CODE-01: Fix extra-subtopic double-count in readiness | 1 hr |
| CODE-07: Use server score on session finish screen | 1 hr |
| CODE-08: Fix timer expiry stale closure | 2 hrs |

---

### Sprint 3 — Product Completeness (1–2 weeks)

| Feature | Effort |
|---|---|
| DESIGN-01: Mid-day confidence check (Conditions A/B/C) | 2 days |
| DESIGN-02: Day 11 / exam-eve personalised view | 1 day |
| DESIGN-05: Profile-driven Strategy page | 0.5 day |
| DESIGN-07: Onboarding redesign (spec exists) | 1 day |
| DESIGN-06: Plan validation layer | 1 day |
| ARCH-05: Make `retag_pyq_subtopics.py` mandatory setup | 0.5 day |
| ARCH-06: Dimension data in plan generator | 1 day |

---

### Sprint 4 — Scale & Expand (2–4 weeks)

| Feature | Effort |
|---|---|
| DESIGN-03: CSAT functional first-run | 3–4 days |
| DESIGN-04: Content pre-batching | 2–3 days |
| ARCH-02: Service layer for `quiz.py` | 3 days |
| ARCH-03: SQLite cache table (replace explanations.json) | 2 days |
| ARCH-07: Background task runner for sync | 2 days |
| DESIGN-08: Multi-exam expansion (IES Prelims first) | 2–3 weeks |

---

## Section 7: Flaw Register (All Issues, Priority Order)

| ID | Track | File | Issue | Priority |
|---|---|---|---|---|
| CRITICAL-01 | Product+Code | session/page.tsx | `time_taken_sec` hardcoded to 0 — all adaptive session timing corrupt | P0 |
| CRITICAL-02 | Architecture | All routes | No SQLite WAL — concurrent phone+desktop causes DB lock | P0 |
| CRITICAL-03 | Architecture | batch_analyse.py | `mark_synced` before `save_profile` — sessions lost on API timeout | P0 |
| CRITICAL-04 | Architecture | sessions.py | `expand-concept` makes real-time API calls mid-session | P0 |
| CRITICAL-05 | Code | self_attestation.py | `UPDATE` on missing SAR row — silently drops all SAR updates | P0 |
| CRITICAL-06 | Code | score_engine.py | `a["concept_expanded"]` KeyError crashes `close_session` | P0 |
| CRITICAL-07 | Architecture | plan.py | Hardcoded exam date 2026-05-20 — system breaks after that date | P0 |
| DESIGN-01 | Product | — | Mid-day confidence check (Phase gate) never built | P0 |
| DESIGN-02 | Product | strategy/page.tsx | Day 11 personalised view missing | P0 |
| CODE-01 | Code | batch_analyse.py | Readiness formula double-counts extra subtopics (BUG-03) | P1 |
| CODE-02 | Code | score_engine.py | Trend is cumulative vs cumulative — hides real regressions (BUG-02) | P1 |
| CODE-03 | Code | batch_analyse.py | Dimension score thresholds 0–1 vs 0–100 possible inversion (BUG-11) | P1 |
| CODE-04 | Code | sessions.py | Two overlapping `question_notes` tables — UI/planner split-brain (DB-05) | P1 |
| CODE-05 | Code | quiz.py:283 | `{num_q}` literal in spillover prompt — wrong question count (PROMPT-02) | P1 |
| CODE-06 | Code | quiz.py:329 | Infinite loop in allocation rounding correction (BUG-06) | P1 |
| CODE-07 | Code | session/page.tsx | Client score shown to user, not server score (TS-01) | P1 |
| CODE-08 | Code | diagnostic/page.tsx | Timer fires on stale closure — may re-submit answered questions (TS-08) | P1 |
| ARCH-01 | Architecture | db_init.py+3 others | Schema spread across 4 files — drift guaranteed | P1 |
| ARCH-04 | Architecture | batch_analyse.py | `prep_profile.json` no atomic write — corruption risk | P1 |
| ARCH-05 | Architecture | priority_scorer.py | 70% PYQ signal discarded — adaptive system impaired | P1 |
| CODE-04b | Code | sessions.py | SAR record_attestation no row guard (BUG-04, see CRITICAL-05) | P1 |
| DESIGN-03 | Product | csat/page.tsx | CSAT is a stub — zero functional implementation | P1 |
| DESIGN-05 | Product | strategy/page.tsx | Strategy page is hardcoded generic advice | P1 |
| DESIGN-06 | Product | plan_generator.py | No plan validation layer — scheduling rules are suggestions | P1 |
| DESIGN-07 | Product | setup/page.tsx | Onboarding is a form, not an experience | P1 |
| ARCH-02 | Architecture | quiz.py | 1,277-line route file — no service layer | P1 |
| ARCH-03 | Architecture | explanations.json | Flat JSON cache degrades after Day 5 | P1 |
| ARCH-06 | Architecture | plan_generator.py | Dimension data tracked but never reaches planner | P2 |
| ARCH-07 | Architecture | analysis.py | `run_analysis()` blocks server for 15–30 seconds | P2 |
| ARCH-08 | Architecture | score_engine.py | dimension_id not validated against syllabus | P2 |
| CODE-09 | Code | quiz.py, content_cache.py | 16–20 char hash keys — collision risk | P2 |
| CODE-10 | Code | server.py | CORS wildcard — any LAN device can access all data | P2 |
| DESIGN-04 | Product | — | Content pre-batching never built — 30–40s loading wait | P1 |
| DESIGN-08 | Product | — | Multi-exam expansion requires 8 architectural changes | P2 |

---

## Appendix: Quick-Fix One-Liners

These can be fixed in a single sitting (30 min total):

```python
# CRITICAL-06: score_engine.py line 218 — KeyError guard
# Before:
if a["concept_expanded"] and a["subtopic_id"]
# After:
if a.get("concept_expanded") and a.get("subtopic_id")

# CODE-05: quiz.py line 283 — f-string literal fix
# Before:  f"...before reaching {{num_q}}, generate remaining..."
# After:   f"...before reaching {num_q}, generate remaining..."

# CODE-09: quiz.py — full hash (do in 3 places)
# Before: hexdigest()[:20]   or   hexdigest()[:16]
# After:  hexdigest()[:32]

# CRITICAL-03: batch_analyse.py — move mark_synced after save_profile
# Find: mark_synced(session_ids) (runs before save_profile)
# Move: to after save_profile(profile) succeeds

# CRITICAL-05: self_attestation.py — INSERT OR REPLACE pattern
# Replace bare UPDATE ... WHERE user_id=? with
# INSERT INTO sar_scores(user_id, sar, ...) VALUES(?, ?, ...) ON CONFLICT(user_id) DO UPDATE SET ...

# PY-06: plan.py — deprecated utcnow
# Before: datetime.datetime.utcnow().isoformat()
# After:  datetime.datetime.now(datetime.timezone.utc).isoformat()

# CACHE-02: quiz.py line 531 — order-independent multi-subtopic cache key
# Before: "|".join(subtopic_ids) + "|" + ...
# After:  "|".join(sorted(subtopic_ids)) + "|" + ...
```

---

*Full detail for each finding is in the individual track reports:*  
- *`01_product_feature_gap.md` — product/UX/feature completeness*  
- *`02_architecture_analysis.md` — structural and system-level issues*  
- *`03_code_quality_review.md` — code-level bugs, security, prompt quality*
