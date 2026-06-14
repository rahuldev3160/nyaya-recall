# Track 2: Architecture Analysis

**Audit date:** 2026-05-17
**Auditor:** Claude Sonnet 4.6 (architectural review pass)
**Files read:** PLAN.md, CLAUDE.md, backend/server.py, backend/models.py, all 7 route files, scripts/db_init.py, score_engine.py, batch_analyse.py, plan_generator.py, priority_scorer.py, difficulty_engine.py, web/src/lib/api.ts, web/src/app/page.tsx, data/syllabus.json, data/prep_config.json, data/prep_profile.json

---

## 1. Architecture Overview — What Was Intended vs What Was Built

**Intended:** A single-user local AI prep system with a strict separation between batch AI calls (pre-session content generation) and zero-cost runtime (quiz sessions answered from cached content). The design called for clean layering: ChromaDB for vectors, SQLite for structured data, FastAPI for routing, Next.js for UI.

**What was actually built:** The intent has been largely realised, but several significant gaps and deviations exist:

| Intention | Reality |
|---|---|
| Zero API calls during quiz sessions | VIOLATED: `sessions.py` calls Haiku on every `expand-concept` and `expand-notes-selection` request, both of which can be triggered mid-session |
| Prompts in `prompts/` as .txt files, never inline | MOSTLY KEPT: all prompt files exist, but substitution is done via fragile `.replace("{{placeholder}}", value)` string templating with no validation |
| All file paths in .env | PARTIALLY KEPT: `UPSC_CONTENT_PATH` is hardcoded to `/Users/rahulsingh/Desktop/UPSC/Prelims` in `quiz.py` line 629 as a fallback, leaking a machine-specific path |
| CSAT fully separate | LARGELY KEPT: `csat.py` is a one-route placeholder stub returning `"status": "placeholder"` — CSAT is declared separate but never built |
| Schema managed by `db_init.py` | VIOLATED: schema is spread across `db_init.py`, `server.py` lifespan hooks, `sessions.py` (`_ensure_question_notes_table`, `_ensure_question_notes_table_v2`), and `quiz.py` (`_ensure_session_subtopics_table`) |
| SQLite upgradeable to PostgreSQL | STRUCTURALLY POSSIBLE but blocked by raw `sqlite3` usage — no ORM, no connection pooling, no async driver |
| Model split: Haiku for simple, Sonnet for complex | Mostly followed, with one inversion: `synthesize_notes_cached()` in `quiz.py` uses Haiku for single-subtopic notes but Sonnet for merged sessions — inconsistent without documented rationale |

---

## 2. Data Layer Flaws

### Flaw 1: Schema evolution managed by ad-hoc runtime guards, not migrations

**Issue:** The canonical schema lives in `scripts/db_init.py`, but additive tables are also created in three other places: `server.py` lifespan (`session_user_notes`, `question_notes`, `content_feedback`), `sessions.py` (`session_question_notes` via `_ensure_question_notes_table`), and `quiz.py` (`quiz_session_subtopics` via `_ensure_session_subtopics_table`). There are two distinct functions for the `question_notes` table alone — `_ensure_question_notes_table` and `_ensure_question_notes_table_v2` — with different schemas. The `db_init.py` version includes indices; the `sessions.py` version does not.

**Impact:** A fresh install that runs `db_init.py` gets one schema. A system that was started before `db_init.py` was updated gets a different schema created by lifespan hooks. Schema divergence across installations is guaranteed over time. The duplicate `question_notes` ensure-functions risk creating a table missing indices in some code paths.

**Recommendation:** Consolidate all schema definitions exclusively in `db_init.py`. Remove all `CREATE TABLE IF NOT EXISTS` statements from route files and `server.py`. Add a `schema_version` table and a lightweight migration runner. Enforce via a CI check that no `CREATE TABLE` appears outside `db_init.py`.

---

### Flaw 2: Missing index on `quiz_sessions.synced` — the most query-critical column

**Issue:** `batch_analyse.py` and `plan_generator.py` repeatedly query `WHERE synced=0 AND end_time IS NOT NULL`. The existing indices cover `end_time` (`idx_qs_end`) and `start_time` (`idx_qs_start`), but there is no index on `synced`. With 100–500 sessions accumulated over 10 days, SQLite will full-scan `quiz_sessions` for every sync operation.

**Impact:** Low now (single user, small table), but the sync query also appears in `plan_generator.py`'s `_get_todays_completed_subtopics()` which runs on every plan generation. Any regression to a larger dataset would degrade noticeably.

**Recommendation:** Add `CREATE INDEX IF NOT EXISTS idx_qs_synced ON quiz_sessions(synced, end_time)` in `db_init.py`.

---

### Flaw 3: `subtopic_scores` has no UNIQUE constraint on `(user_id, subject_id, subtopic_id)` for the common upsert path

**Issue:** `db_init.py` defines `UNIQUE(user_id, subject_id, topic_id, subtopic_id)` — a 4-column unique key. But `score_engine.py`'s `_update_subtopic_scores()` queries on `(user_id, subject_id, subtopic_id)` only (deliberately ignoring `topic_id` because "topic_id varies across sessions"). This means the UPDATE can affect zero rows if a prior INSERT was done with a different `topic_id`, silently inserting a duplicate row instead.

**Impact:** Silent duplicate subtopic score rows. The tracker shows inflated `subtopics_assessed` counts. Coverage percentages overstate real coverage. `batch_analyse.py`'s `compute_weighted_readiness()` could double-count a subtopic's score contribution.

**Recommendation:** Change the UNIQUE constraint to `UNIQUE(user_id, subject_id, subtopic_id)` and drop `topic_id` from the constraint. Store `topic_id` as a non-keyed informational column, updated on upsert. This matches the actual query pattern in `score_engine.py`.

---

### Flaw 4: `explanations.json` is a single growing JSON file with no eviction or compaction

**Issue:** `cache/explanations.json` accumulates all AI-generated notes and explanations, written via `_save_cache()` which does a full read-parse-write on every cache miss. The file grows without bound. In `synthesize_notes_cached()` and `synthesize_notes_multi_cached()` in `quiz.py`, the cache is read from disk twice per call (once to check, once to write).

**Impact:** At ~2KB per notes entry and ~200 subtopics with 5 cache key variants each, the file can reach 2MB+. Full JSON parse on every cache write is O(n) where n is the number of cached entries. This will degrade perceptibly after Day 5 when most subtopics have been visited once.

**Recommendation:** Replace the flat JSON cache with SQLite (a `cache` table with `key TEXT PRIMARY KEY, value TEXT, created_at TEXT`). This gives O(log n) lookups, atomic writes, and trivial size management. Alternatively, at minimum, add a file-size guard that compacts entries older than 7 days.

---

### Flaw 5: `prep_profile.json` is the single source of truth for readiness, with no rollback

**Issue:** `batch_analyse.py`'s `save_profile()` overwrites `prep_profile.json` atomically but without keeping a backup. If the Claude API returns malformed JSON mid-write, or the process is killed during `PROFILE_PATH.write_text(...)`, the file is corrupted. There is no `.bak` or versioned copy.

**Impact:** A single bad API response or a `Ctrl-C` at the wrong moment destroys the entire readiness history. The system has no recovery path — the user would need to re-do all sessions.

**Recommendation:** Write to a temp file first, then atomically rename: `tmp = PROFILE_PATH.with_suffix('.json.tmp'); tmp.write_text(...); tmp.rename(PROFILE_PATH)`. Additionally keep a rolling backup of the last 3 versions: `prep_profile.json.bak1`, `.bak2`, `.bak3`.

---

### Flaw 6: PYQ subtopic normalisation match rate is ~30%

**Issue:** `priority_scorer.py` documents explicitly that only ~30% of PYQ questions get matched to canonical syllabus subtopic IDs via fuzzy token overlap. The remaining ~70% are silently discarded (returned `None` from `_normalise()`). This means 70% of 17 years of PYQ frequency data contributes zero signal to `compute_all_priorities()`.

**Impact:** The PYQ priority weights driving question ordering, difficulty allocation, and plan generation are based on a severely incomplete signal. High-frequency subtopics may receive low weights if their PYQ tags don't token-overlap with syllabus IDs. The system recommends a fix (`retag_pyq_subtopics.py`) but it has not been run as part of the standard setup.

**Recommendation:** Make `retag_pyq_subtopics.py` a mandatory step in the setup sequence (document in PLAN.md Build Phase 1). Add a health check endpoint that reports the PYQ-to-syllabus match rate and warns when it falls below 60%.

---

## 3. Backend Layer Flaws

### Flaw 1: Business logic concentrated in `quiz.py` — the route file is 1,277 lines

**Issue:** `backend/routes/quiz.py` contains: ChromaDB query logic (`fetch_chunks`, `fetch_chunks_with_meta`), cache read/write (`synthesize_notes_cached`, `synthesize_notes_multi_cached`), question allocation algorithms (`_allocate_questions_across_subtopics`, `_allocate_questions_for_subtopic_ids`), syllabus traversal helpers (`get_canonical_topic_id`, `_get_subtopic_dimensions`), prompt rendering, and the anthropic API call — all in one file that is also a FastAPI router. There is no service layer.

**Impact:** The `generate_quiz()` function alone is ~250 lines with three deeply nested conditional branches (is_merged, primary_subtopic_id, else). Adding or testing any single piece of logic requires understanding the whole function. The lack of unit tests is more dangerous because the logic is untestable in isolation.

**Recommendation:** Extract a `services/quiz_service.py` containing: `QuizAllocator` class (allocation logic), `NotesCache` class (cache I/O), `ChromaRetriever` class (vector fetch). The route handlers become thin orchestrators calling service methods. Target: route handlers under 40 lines each.

---

### Flaw 2: Direct `sqlite3.connect()` per request — no connection pooling or async

**Issue:** Every route that touches the database calls `sqlite3.connect(DB_PATH)`, executes queries, and calls `con.close()`. There are at least 35 such call sites across the routes and scripts. SQLite's WAL mode is not enabled, so concurrent writes (from phone + desktop simultaneously) will raise `OperationalError: database is locked`.

**Impact:** The phone access use case (two connections open simultaneously) is a documented feature in PLAN.md. Under the current architecture, a phone submitting an answer while the desktop is closing a session will produce a database lock error. The system silently swallows many exceptions via bare `except Exception: pass`, hiding these failures.

**Recommendation:** Enable WAL mode on first connection: `con.execute("PRAGMA journal_mode=WAL")`. Create a `db.py` module with a context manager `get_db()` that standardises connection settings (WAL, row_factory, timeout). All route files import from `db.py` rather than calling `sqlite3.connect()` directly.

---

### Flaw 3: `analysis.py` route is a one-liner that makes a blocking LLM call in the request thread

**Issue:** `backend/routes/analysis.py` contains a single route `POST /analysis/sync` that calls `run_analysis()` synchronously. `run_analysis()` makes a Sonnet API call that can take 15–30 seconds. FastAPI is running under uvicorn with default single-worker configuration. During the analysis call, the entire server is blocked and cannot respond to any other request.

**Impact:** If the user triggers sync from the phone while the desktop is also active, or if the plan generation is running at the same time, one request blocks all others. The 8-second timeout in `api.ts`'s `get()` function would expire on other concurrent requests.

**Recommendation:** Offload `run_analysis()` to a background task using FastAPI's `BackgroundTasks` or an `asyncio` thread pool executor. Return a job ID immediately; add `GET /analysis/status/{job_id}` for the frontend to poll. This also allows the UI to show a progress indicator instead of a frozen spinner.

---

### Flaw 4: `Anthropic` client and `ChromaDB` client instantiated at module import time in `quiz.py`

**Issue:** Lines 88–89 of `quiz.py`:
```python
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
chroma = chromadb.PersistentClient(path=CHROMA_PATH)
```
These execute at import time, before the FastAPI lifespan hook runs. If `ANTHROPIC_API_KEY` is not set or `CHROMA_PATH` doesn't exist, the entire server fails to start with a cryptic import error rather than a clean startup-check error.

**Impact:** Debugging startup failures is harder than necessary. The `sessions.py` file also loads two prompt files at module import: `_EXPAND_PROMPT` and `_EXPAND_NOTES_PROMPT` — if the files are missing, the import crashes.

**Recommendation:** Move all external client initialisation into the FastAPI lifespan handler. Use dependency injection (`Depends(get_anthropic_client)`) so routes receive pre-validated clients. Add explicit startup checks that produce clear error messages.

---

### Flaw 5: `expand-concept` and `expand-notes-selection` make real-time API calls during sessions

**Issue:** `sessions.py` routes `POST /sessions/expand-concept` and `POST /sessions/expand-notes-selection` both call the Anthropic Haiku API synchronously and return the result. These are user-triggered mid-session (while answering questions). They are not cached — the `expand-concept` response is saved to `session_answers.concept_expanded=1` flag but the explanation text itself is not stored for reuse.

**Impact:** This directly violates the "zero API calls during quiz sessions" rule in CLAUDE.md. On a slow network or Anthropic API latency spike, the user waits 3–5 seconds mid-question. Each expand call costs ~$0.001–0.002, not budgeted in the PLAN.md cost breakdown.

**Recommendation:** Cache expand-concept responses in `explanations.json` keyed by `SHA256(question_hash + ":expand")`. On cache hit, return instantly with zero API cost. This converts a real-time dependency into a one-time cost. For expand-notes-selection, cache by `SHA256(selected_excerpt[:200])`.

---

### Flaw 6: No request validation on `generate_quiz` — accepts raw `dict`

**Issue:** `quiz.py`'s `generate_quiz(config: dict)` and `start_exam_simulation(config: dict)` accept an untyped Python `dict`. There is no Pydantic validation. `SessionConfig` in `models.py` exists but is not used by these endpoints. Invalid input (missing `subject_id`, negative `num_questions`, unknown `session_type`) propagates into the business logic where it causes untrapped exceptions.

**Impact:** Malformed requests from the frontend (bugs during development, or unexpected state) produce 500 errors with internal exception details rather than 400 validation errors. The frontend cannot distinguish "bad request" from "server error".

**Recommendation:** Change `generate_quiz(config: dict)` to `generate_quiz(config: SessionConfig)` and extend `SessionConfig` to cover all fields used inside the function. Use Pydantic validators for enum constraints on `session_type` and `difficulty`.

---

## 4. Frontend Layer Flaws

### Flaw 1: All API state in `page.tsx` uses `useState<any>` — no type safety

**Issue:** `web/src/app/page.tsx` stores `profile`, `plan`, and `config` as `useState<any>`. All access is untyped: `profile?.subjects?.[s.id]`, `plan?.sessions`, `config?.total_days`. The same pattern likely recurs in other pages (`/diagnostic`, `/session`, `/analysis`, `/tracker`).

**Impact:** TypeScript provides zero protection against API shape changes. When `batch_analyse.py` changes the `prep_profile.json` structure (which it has — adding `topics[]`, `expanded_interests`, `priority_focus`), the frontend silently renders `undefined` rather than failing at compile time. Type errors accumulate silently.

**Recommendation:** Define typed interfaces in `web/src/lib/types.ts` for `PrepProfile`, `StudyPlan`, `SubjectProfile`, `PlanSession`. Replace `useState<any>` with `useState<PrepProfile | null>` etc. The types are partially defined in `api.ts` but not used for state.

---

### Flaw 2: No client-side state management — every page fetch is independent

**Issue:** `page.tsx` fetches `profile`, `plan`, and `config` in a `useEffect` on mount. Other pages (`/tracker`, `/analysis`, `/session`) likely do the same independently. There is no shared cache, context, or state manager. Every navigation re-fetches the same data.

**Impact:** The user navigates from Dashboard to Tracker, then back — two `GET /tracker/profile` calls fire, both returning the same data. More critically, after sync (`handleSync`), the profile update is only reflected in `page.tsx`. The Tracker page will show stale data until its next mount.

**Recommendation:** Introduce React Query (TanStack Query) or SWR for all API calls. This provides: automatic deduplication of concurrent requests, shared cache across pages, stale-while-revalidate on navigation, and manual invalidation after mutations (e.g., invalidate `profile` after sync).

---

### Flaw 3: The `/api/backend` Next.js proxy is not visible in the codebase

**Issue:** `api.ts` uses `const BASE = "/api/backend"` as the API base, implying a Next.js API route that proxies to `localhost:8000`. This proxy file (likely `web/src/app/api/backend/[...path]/route.ts`) was not found in the files reviewed. If it exists, its error handling and timeout settings are invisible. If it does not exist and Next.js rewrites are used instead, the phone access scenario (`192.168.x.x:3000`) would route API calls to `192.168.x.x:8000` only if the rewrite uses an absolute URL.

**Impact:** If the proxy uses `localhost:8000` as the target (common default), phone access works for serving the Next.js UI but all API calls fail because `localhost:8000` from the phone's perspective points to the phone itself, not the Mac.

**Recommendation:** Verify the proxy implementation resolves the FastAPI backend using the host machine's LAN IP or an environment variable (`NEXT_PUBLIC_BACKEND_URL`). Document this in CLAUDE.md. Add a health check indicator on the dashboard that calls `GET /api/backend/health` and shows a "Backend offline" warning.

---

### Flaw 4: `SUBJECTS` constant hardcoded in `page.tsx` and likely duplicated across pages

**Issue:** `page.tsx` line 4–15 defines a `SUBJECTS` array with 9 entries. The same list almost certainly appears in `/diagnostic`, `/tracker`, `/session`, and `/analysis` pages. The canonical list is `_GS1_SUBJECTS` in `plan.py` and `_SUBJECT_NAMES` in `plan.py` — three different definitions of the same concept.

**Impact:** When a new subject is added (e.g., separating `modern_history` from `history_amac`), it must be added in multiple places. The current state shows `modern_history` in `page.tsx` but `history_amac` is the syllabus ID — there is already a mismatch: the dashboard shows "Modern History" as a separate subject but the syllabus uses `history_amac` as the combined subject.

**Recommendation:** Expose `GET /config/subjects` that returns the canonical subject list from `syllabus.json`. All frontend pages consume this list. Remove the hardcoded `SUBJECTS` array from the frontend.

---

## 5. AI/LLM Integration Architecture Assessment

### Cost Efficiency

The batch-before-session architecture is sound and well-implemented. The bulk of cost control works as designed. The documented gaps are:

1. **Unbudgeted real-time calls:** `expand-concept` and `expand-notes-selection` are not in the PLAN.md cost table. At 10 expands per session × 4 sessions/day × 10 days = 400 uncached calls ≈ $0.40–0.80 additional cost. Not catastrophic but untracked.
2. **Notes synthesis on every session start (if show_notes=true):** `synthesize_notes_multi_cached()` is cached by subtopic list + chunk content hash, so repeat visits are free. First visit costs ~$0.02. This is correctly handled.
3. **Model selection inversion for notes:** Single-subtopic notes use Haiku (`AI_MODEL_FAST`); multi-subtopic merged notes use Sonnet (`AI_MODEL_SMART`). This is 4x the cost for a merged session's notes with no documented quality justification. Haiku is capable of notes synthesis for UPSC content.

### Caching Effectiveness

The `explanations.json` cache is the right idea but has implementation gaps:
- Cache keys for notes are SHA256 of subtopic_id + chunk texts, meaning a re-ingestion of study material invalidates all cached notes (chunk texts change). This is correct behaviour but not documented.
- The `revision_notes` endpoint caches by `SHA256(question_hash + ":revision:v2")`. The `:v2` suffix suggests a previous cache was invalidated by a schema change — a manual versioning approach that will grow messy. A structured approach would use a `cache_version` column.
- There is no cache warming for the current day's planned subtopics. `prewarm_notes_cache.py` exists in scripts but is not part of the automated flow.

### Prompt Management

Prompt files are properly externalised in `prompts/`. The substitution mechanism is fragile:
- `.replace("{{placeholder}}", value)` has no validation that all placeholders are present in the template.
- If a prompt file is missing, `(PROMPT_DIR / prompt_file).read_text()` raises an unhandled `FileNotFoundError` that propagates as a 500 error.
- The `prompt_file` variable in `generate_quiz()` can be referenced before assignment when `session_type == "deep_dive"` and `is_merged == True` (lines 839–843 set `prompt_file` for deep_dive but then the merged path at line 858 overwrites it without checking).

### Model Selection Strategy

The Haiku/Sonnet split is well-reasoned in PLAN.md and largely followed. The one structural weakness is that model names are environment variables (`AI_MODEL_SMART`, `AI_MODEL_FAST`) with hardcoded fallback strings. If a model version is deprecated, every fallback must be updated individually across `quiz.py`, `sessions.py`, and `batch_analyse.py`.

---

## 6. System Reliability Risks

### Risk 1: No process manager — both servers die on terminal close

**Issue:** The server is started with `uvicorn server:app --host 0.0.0.0 --port 8000 --reload` and `npm run dev`. Both processes are tied to the terminal session. Closing the terminal, Mac sleep, or a kernel update terminates both servers. The `--reload` flag is for development — it watches for file changes and restarts, creating unnecessary CPU load during actual study sessions.

**Impact:** Mid-study session interruption if the terminal is accidentally closed. On Mac, background terminal sessions are terminated on logout.

**Recommendation:** Create a `scripts/start.sh` that uses `nohup` or `launchd` plists to keep both servers running as background daemons. Remove `--reload` from the production start command. A `scripts/stop.sh` for clean shutdown.

---

### Risk 2: The `close_session()` function is the only way to persist scores — an incomplete session loses all data

**Issue:** `score_engine.py`'s `close_session()` updates `quiz_sessions.end_time`, writes to `session_summaries`, and calls `_update_subtopic_scores()`. Individual answers are persisted immediately via `record_answer()`. But subtopic scores and session summaries are only written on explicit session close. If the browser crashes or the server restarts mid-session, the answers exist in `session_answers` but `quiz_sessions.end_time` is NULL and `quiz_sessions.synced=0`. `batch_analyse.py` queries `WHERE synced=0 AND end_time IS NOT NULL` — so these orphaned sessions are never analysed.

**Impact:** A browser crash after answering 15 questions loses the score computation for that session. The user's readiness profile will not reflect that work.

**Recommendation:** Add a `backfill_incomplete_sessions()` function in `batch_analyse.py` that finds sessions with answers but NULL `end_time`, calls `close_session()` on them before the main analysis loop. Run this at the start of every `run_analysis()` call.

---

### Risk 3: `plan_generator.py` hardcodes exam date logic — EXAM_DATE is also hardcoded in `plan.py`

**Issue:** `plan.py` line 214 contains `EXAM_DATE = datetime.date(2026, 5, 20)`. This is a hardcoded date in a route file. When the exam date passes or the user wants to prepare for a different exam, this requires a code change.

**Impact:** The trajectory endpoint `GET /plan/trajectory` returns `days_remaining = 0` after May 20, 2026. The system becomes partially unusable after the hardcoded date without code changes. The `prep_config.json` exists and has a `start_date` field — a `target_date` field should be added there and used universally.

**Recommendation:** Add `target_date` to `prep_config.json` (defaulting to `start_date + total_days`). Replace the `EXAM_DATE` constant in `plan.py` and any similar hardcoded date with `config.get("target_date")`.

---

### Risk 4: `batch_analyse.py` runs as a blocking subprocess in the request thread

**Issue:** `analysis.py` route calls `run_analysis()` synchronously. The function opens multiple SQLite connections, makes one Sonnet API call (15–30 seconds), and writes to `prep_profile.json`. If any step raises an exception, the HTTP request returns a 500 error and the profile is left in a partially-updated state (session IDs already marked `synced=1` via `mark_synced()` which runs inside `run_analysis()` before the save, leaving them permanently skipped even if the profile write failed).

**Impact:** A Sonnet API timeout (common at 30+ second prompts) marks sessions as synced but does not update the profile. Those sessions are permanently excluded from future analysis.

**Recommendation:** Move `mark_synced()` to AFTER `save_profile()` succeeds. Use a database transaction: mark sessions synced only after the profile file is written without error.

---

### Risk 5: CORS is set to `allow_origins=["*"]`

**Issue:** `server.py` sets `allow_origins=["*"]`. On a local network, this means any device that can reach port 8000 (any device on the home WiFi) can make API calls — including cross-site requests from any origin.

**Impact:** Low risk for a home network, but if the user ever connects to a public WiFi (café, library) and forgets to stop the server, the SQLite database is exposed to any device on that network without authentication. There is no auth layer.

**Recommendation:** Set `allow_origins` to a specific list: `["http://localhost:3000", f"http://{LAN_IP}:3000"]`. Add a startup log message that prints the LAN IP and the allowed CORS origins so the user can verify the configuration.

---

## 7. Scalability Assessment

### What Breaks First Under Load

**For the current single-user use case (10 days), nothing will break at scale** — the system is sized correctly. The bottlenecks that matter in the future:

| Bottleneck | Trigger | Failure Mode |
|---|---|---|
| `explanations.json` full JSON rewrite | >500 cached entries | 100ms+ write latency per cache miss; noticeable lag on notes generation |
| SQLite WAL not enabled | Phone + desktop simultaneous write | `OperationalError: database is locked`; one submission silently fails |
| `run_analysis()` blocking the request thread | Any concurrent request during sync | All API calls time out for 15–30 seconds |
| `priority_scorer.compute_all_priorities()` called per request | More PYQ data loaded | Full table scan on `pyq_questions` on every quiz generation; add `@lru_cache` or persist computed weights |

### Path to Multi-User

The codebase has `user_id='user_1'` hardcoded in approximately 40 places across 6 files. The PLAN.md acknowledges this and calls it "designed to swap to dynamic." The actual swap requires:

1. Add JWT auth middleware to FastAPI (one day of work).
2. Replace all `user_id='user_1'` literals with `current_user.id` from the auth token — requires touching every route and `score_engine.py`, `batch_analyse.py`, `plan_generator.py`.
3. Replace SQLite with PostgreSQL (connection string change, but also: `sqlite3.Row` is not compatible with `asyncpg`; all cursor patterns must change).
4. Replace `prep_profile.json` (single file) with a database table per user.
5. Replace `study_plan.json` with a database table per user.
6. Replace `cache/explanations.json` with a shared Redis cache or DB table.

This is a significant rewrite of the persistence layer, not a single connection string change. The "upgradeable to PostgreSQL" claim in PLAN.md understates the effort.

### Path to Multi-Exam

The syllabus taxonomy (`data/syllabus.json`) is UPSC GS-specific. The `avg_questions_per_year` field is hardcoded per subject for UPSC. The decay formula in `priority_scorer.py` uses `CURRENT_YEAR = 2026` as a global constant. Expanding to a second exam (UPSC Mains, State PSC) would require:

1. A parameterised syllabus loader keyed by `exam_id`.
2. Separate SQLite databases or a multi-tenant schema with `exam_id` everywhere.
3. Separate ChromaDB collections per exam (currently hardcoded to `"upsc_content"`).

---

## 8. Knowledge Hierarchy Coverage (Architectural Perspective)

### Hierarchy Depth and Completeness

The syllabus.json implements the full five-level hierarchy:
```
exam (UPSC GS Paper 1)
  → subject (10 subjects, 9 GS + 1 CSAT)
    → topic (9 topics avg per subject, range 3–9)
      → subtopic (205 total across GS subjects)
        → dimension (1,267 total, avg 6.2 per subtopic)
```

This is genuinely well-structured. All 205 GS subtopics have dimensions populated (0 missing). The `subtopic_dimension_scores` table (FEATURE-027) exists and is being populated. The framework is architecturally sound.

### Where the Architecture Fails to Track the Hierarchy

**Gap 1: Dimension coverage is tracked but not surfaced in planning.**
`batch_analyse.py` computes `_compute_subtopic_dim_coverage()` and uses it in readiness scores. But `plan_generator.py` sends only `subtopic_coverage` to Claude — a flat list of tested/untested subtopics with no dimension breakdown. Claude cannot plan at dimension granularity because it never receives dimension data. The planner operates at subtopic level despite the schema supporting dimension level.

**Gap 2: The quiz generator tracks dimensions inconsistently.**
`session_answers.dimension_id` column exists. `quiz.py` injects `{{available_dimensions}}` into prompts. But there is a `# TODO (Phase 3)` comment in `_get_subtopic_dimensions()` noting that `dimensions_covered_this_session` is not yet passed to the prompt. Claude is shown available dimensions but not told which ones were already tested this session — it may regenerate questions on the same dimension.

**Gap 3: Topic-level coverage is computed but not persisted as a first-class metric.**
`batch_analyse.py`'s `_compute_topic_coverage()` produces topic-level `coverage_pct` and `risk_level`. These are stored inside `prep_profile.json → subjects → {subject} → topics[]`. But the tracker route `GET /tracker/subtopics/{subject_id}` returns only subtopic rows from `subtopic_scores` — there is no `subtopic_scores` equivalent at topic level. Topic coverage is a derived field in the profile JSON, not in SQLite, making it unavailable to ad-hoc queries.

**Gap 4: CSAT has zero architecture implementation.**
`csat.py` is a one-route stub. The syllabus has 11 CSAT subtopics and 64 dimensions fully specified. `prep_profile_csat.json` is referenced in PLAN.md and CLAUDE.md but does not exist (or is not read by any code). The CSAT architecture is documented but unbuilt.

**Gap 5: Cross-subtopic linkages exist in notes but not in the knowledge graph.**
`quiz.py`'s `_build_cross_subtopic_prompt_section()` generates cross-subtopic bridge text for merged sessions. This insight is never stored — it is generated and displayed, then lost. No table captures "subtopic A and B are linked via concept C," which would be valuable for future session planning.

**Gap 6: The `dimension_id` in `session_answers` is written by Claude in the JSON response but never validated against `syllabus.json`.**
Claude generates a `dimension_id` string in each question's JSON. This string is stored as-is in `session_answers.dimension_id`. There is no validation that the dimension ID exists in `syllabus.json` for the given subtopic. Hallucinated or mismatched dimension IDs would silently corrupt `subtopic_dimension_scores`.

---

## 9. Top 10 Architecture Recommendations

### P0 — Fix Before Next Study Session

**Rec 1: Enable SQLite WAL mode and centralise database connections**
- Problem it solves: Database lock errors when phone and desktop are used simultaneously; connection management scattered across 35+ call sites.
- How it improves the system: Phone + desktop concurrent use becomes reliable. A single `db.py` module with `get_db()` context manager standardises connection settings (WAL, row_factory=sqlite3.Row, timeout=10).
- Implementation: Create `backend/db.py`; add `PRAGMA journal_mode=WAL` on first connection; update all route files to import `get_db`.
- Priority: **P0** — the phone access feature is documented as core functionality and currently silently fails under concurrent access.

**Rec 2: Fix the `mark_synced()` / profile write ordering in `batch_analyse.py`**
- Problem it solves: Sessions marked synced before profile is saved, causing permanent data loss on API timeout.
- How it improves the system: A Sonnet API timeout no longer permanently discards session data. Sessions remain available for the next sync attempt.
- Implementation: Move `mark_synced(session_ids)` to after `save_profile(profile)` succeeds. Wrap both in a try/except so sync status is only updated on full success.
- Priority: **P0** — this is a data loss scenario on an operation the user performs daily.

**Rec 3: Cache `expand-concept` and `expand-notes-selection` responses**
- Problem it solves: Real-time API calls during quiz sessions violate the core "zero API cost mid-session" rule and cause perceptible latency.
- How it improves the system: First expand on a question costs ~$0.001; all subsequent views of the same question are instant and free.
- Implementation: In `sessions.py`, check `cache/explanations.json` with key `SHA256(question_hash + ":expand")` before making the API call. Write on miss.
- Priority: **P0** — this is a stated architectural invariant in CLAUDE.md that is currently violated.

### P1 — Fix in Next Sprint

**Rec 4: Consolidate schema management in `db_init.py`**
- Problem it solves: Schema drift between installations; duplicate `question_notes` table definitions with different index sets; `session_question_notes` created in `sessions.py` but not in `db_init.py`.
- How it improves the system: Fresh install and upgraded install produce identical schemas. A schema version table enables safe future migrations.
- Priority: **P1** — currently safe only because the system has one user, but any reinstall risks schema inconsistency.

**Rec 5: Replace `explanations.json` with a SQLite cache table**
- Problem it solves: Full JSON rewrite on every cache miss becomes slow as the cache grows; no atomic writes; no size management.
- How it improves the system: O(log n) lookups, atomic row-level writes, trivial TTL management via `created_at` column.
- Implementation: Add `CREATE TABLE IF NOT EXISTS notes_cache (cache_key TEXT PRIMARY KEY, value TEXT, created_at TEXT)` to `db_init.py`. Update all cache read/write code in `quiz.py` and `sessions.py`.
- Priority: **P1** — degrades perceptibly after ~Day 5 when the cache grows large.

**Rec 6: Make `retag_pyq_subtopics.py` a mandatory setup step and add a health check**
- Problem it solves: 70% of PYQ frequency data is silently discarded, making the priority weighting system operate on a fraction of its intended signal.
- How it improves the system: Correct PYQ weights mean question ordering and plan generation reflect actual UPSC exam patterns, not a 30%-sampled approximation.
- Implementation: Add `python scripts/retag_pyq_subtopics.py` to PLAN.md Phase 1 setup. Add `GET /health/data` endpoint returning PYQ-to-syllabus match rate; warn UI if below 60%.
- Priority: **P1** — the core intelligence of the system (adaptive difficulty, plan prioritisation) is impaired.

**Rec 7: Add atomic write protection for `prep_profile.json`**
- Problem it solves: A process kill during `write_text()` corrupts the entire readiness history with no recovery path.
- How it improves the system: The profile survives any crash scenario. Rolling backups allow recovery from a bad API response.
- Implementation: In `batch_analyse.py`'s `save_profile()`, write to `.json.tmp` then rename. Keep 3 rotated backups.
- Priority: **P1** — data loss risk on the most important file in the system.

### P2 — Improve Before Day 8

**Rec 8: Add a background task runner for `run_analysis()` and `generate_plan()`**
- Problem it solves: 15–30 second blocking API calls freeze the entire FastAPI server, causing timeouts on concurrent requests.
- How it improves the system: Sync + plan operations run in the background; the frontend polls for completion; the server remains responsive.
- Implementation: Use FastAPI `BackgroundTasks`. Add `GET /analysis/status` returning `{status: "running"|"done"|"error", result: ...}`. Store job state in SQLite.
- Priority: **P2** — single-user single-device usage means concurrent requests are rare, but the phone + desktop scenario makes it realistic.

**Rec 9: Pass dimension coverage data to `plan_generator.py`**
- Problem it solves: The planner operates at subtopic level despite the architecture supporting dimension-level precision. Subtopics with 3/6 dimensions tested are treated the same as 6/6 tested.
- How it improves the system: Claude can plan sessions targeting specific untested dimensions within an otherwise "tested" subtopic, enabling true fine-grained coverage tracking.
- Implementation: In `plan_generator.py`'s `compute_subtopic_coverage()`, join `subtopic_dimension_scores` to add `dimensions_tested` and `dimensions_total` per subtopic. Include in the prompt payload.
- Priority: **P2** — the data infrastructure exists; only the planner prompt connection is missing.

**Rec 10: Validate `dimension_id` values written to `session_answers` against `syllabus.json`**
- Problem it solves: Claude-generated dimension IDs are stored as-is with no validation against the syllabus. Hallucinated IDs silently corrupt `subtopic_dimension_scores`.
- How it improves the system: Dimension-level readiness metrics become trustworthy. Bad IDs are caught at answer-submit time, not discovered later during analysis.
- Implementation: In `score_engine.py`'s `record_answer()`, validate `answer.get("dimension_id")` against the syllabus. If not found, store `NULL` and log a warning. Add a `GET /health/dimensions` endpoint reporting the mismatch rate.
- Priority: **P2** — FEATURE-027's dimension tracking is the most architecturally sophisticated part of the system; it's only valuable if the data is clean.
