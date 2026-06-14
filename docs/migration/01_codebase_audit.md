# Sprint 2 Pre-Migration Codebase Audit
**Prepared:** 2026-06-15  
**Scope:** Nyaya Recall (Devthorium) — full audit for Supabase auth + multi-tenancy + SQLite → PostgreSQL migration  
**Method:** Direct file reads of all backend routes, scripts, DB schema, and frontend source

---

## 1. Hardcoded user_id Sites — Complete List

Total occurrences of `'user_1'` hardcoded as a string literal across active code: **41 sites** across 9 files.

### backend/routes/sessions.py

| Line | Context (1 line) | Severity |
|------|-----------------|----------|
| 78 | `user_id TEXT DEFAULT 'user_1'` in `CREATE TABLE IF NOT EXISTS exam_sim_records` (DDL in runtime code) | SILENT_BREAK — new user sessions land in 'user_1' bucket |
| 96 | `WHERE user_id='user_1'` — `exam_sim_history()` SELECT for `/exam-sim/history` | SILENT_BREAK — User B sees User A's exam history |
| 223 | `user_id TEXT DEFAULT 'user_1'` in `CREATE TABLE IF NOT EXISTS session_question_notes` (DDL in runtime code) | SILENT_BREAK — notes written to wrong user |
| 239 | `WHERE session_id=? AND user_id='user_1'` — `get_user_notes()` SELECT | SILENT_BREAK — User B reads User A's session notes |
| 244 | `WHERE session_id=? AND user_id='user_1'` — per-question notes SELECT | SILENT_BREAK — same as above |
| 307 | `"user_1"` literal in `put_user_notes()` INSERT VALUES | SILENT_BREAK — User B's notes written as user_1 |
| 324 | `VALUES (?, ?, 'user_1', ?, ?)` — session_question_notes INSERT | SILENT_BREAK — User B's notes written as user_1 |
| 442 | `user_id TEXT NOT NULL DEFAULT 'user_1'` in `question_notes` DDL (runtime) | SILENT_BREAK |
| 496 | `VALUES ('user_1', ?, ?, ?, ?, ?, ?, ?, ?)` — `put_question_note()` INSERT | SILENT_BREAK — User B's question notes stored as user_1 |
| 532 | `WHERE session_id=? AND user_id='user_1'` — `get_question_notes()` SELECT | SILENT_BREAK — cross-user data leak |

### backend/routes/feedback.py

| Line | Context (1 line) | Severity |
|------|-----------------|----------|
| 29 | `user_id TEXT NOT NULL DEFAULT 'user_1'` in `content_feedback` DDL (runtime) | SILENT_BREAK |
| 132 | `VALUES ('user_1', ?, ?, ?, ?, ?, ?, ?, ?, ?)` — `post_content_feedback()` INSERT | SILENT_BREAK — all user feedback silently tagged user_1 |

### backend/routes/quiz.py

| Line | Context (1 line) | Severity |
|------|-----------------|----------|
| 115 | `WHERE user_id='user_1' AND subject_id=?` — `_get_tested_subtopics_for_subject()` SELECT | SILENT_BREAK — question dedup uses User A's test history for User B |
| 228 | `WHERE subtopic_id=? AND user_id='user_1'` — `_get_quiz_intelligence()` user notes context SELECT | SILENT_BREAK — User B gets User A's confusion notes injected into quiz prompt |

### backend/routes/tracker.py

| Line | Context (1 line) | Severity |
|------|-----------------|----------|
| 31 | `WHERE user_id='user_1' AND subject_id != 'csat'` — `get_all_subjects()` | SILENT_BREAK — User B sees User A's subject scores |
| 44 | `WHERE user_id='user_1' AND subject_id=?` — `get_subtopics()` | SILENT_BREAK — User B sees User A's subtopic drill-down |
| 58 | `WHERE user_id='user_1' AND score < 75` — `get_gaps()` | SILENT_BREAK — User B's gap analysis is User A's data |
| 74 | `WHERE user_id='user_1'` — `get_sar()` SAR score fetch | SILENT_BREAK — User B's attestation trust level corrupted |

### backend/server.py (startup DDL)

| Line | Context (1 line) | Severity |
|------|-----------------|----------|
| 26 | `user_id TEXT DEFAULT 'user_1'` in `session_user_notes` DDL | SILENT_BREAK |
| 49 | `user_id TEXT NOT NULL DEFAULT 'user_1'` in `question_notes` DDL | SILENT_BREAK |
| 67 | `user_id TEXT NOT NULL DEFAULT 'user_1'` in `content_feedback` DDL | SILENT_BREAK |

### scripts/score_engine.py

| Line | Context (1 line) | Severity |
|------|-----------------|----------|
| 190 | `user_id TEXT DEFAULT 'user_1'` in `exam_sim_records` DDL (created inline) | SILENT_BREAK |
| 236 | `VALUES (?, 'user_1', ?, ?, ...)` — `_store_exam_sim_record()` INSERT | SILENT_BREAK — exam sim records always stored as user_1 |
| 367 | `WHERE user_id='user_1' AND subject_id=? AND subtopic_id=?` — subtopic_scores SELECT | SILENT_BREAK — scores read for wrong user |
| 385 | `WHERE user_id='user_1' AND subject_id=? AND subtopic_id=?` — subtopic_scores UPDATE | SILENT_BREAK — User B's answers update User A's scores |
| 397 | `VALUES ('user_1',?,?,?,?,?,?,?,?)` — subtopic_scores INSERT | SILENT_BREAK — new score rows always owned by user_1 |
| 427 | `WHERE user_id='user_1' AND ...` — subtopic_dimension_scores SELECT | SILENT_BREAK |
| 437 | `WHERE user_id='user_1' AND ...` — subtopic_dimension_scores UPDATE | SILENT_BREAK |
| 447 | `VALUES ('user_1', ?, ?, ...)` — subtopic_dimension_scores INSERT | SILENT_BREAK |
| 470 | `WHERE user_id='user_1' AND subject_id=?` — `get_subject_summary()` SELECT | SILENT_BREAK |

### scripts/batch_analyse.py

| Line | Context (1 line) | Severity |
|------|-----------------|----------|
| 105 | `WHERE user_id='user_1'` — `_get_tested_subtopics()` SELECT (all subtopic_scores) | SILENT_BREAK — overall readiness computed only from user_1's data for all users |
| 124 | `WHERE user_id='user_1' AND subject_id=?` — `_get_dimension_scores()` SELECT | SILENT_BREAK |

### scripts/plan_generator.py

| Line | Context (1 line) | Severity |
|------|-----------------|----------|
| 84 | `WHERE user_id='user_1'` — `compute_subtopic_coverage()` subtopic_scores SELECT | SILENT_BREAK — plan generated from User A's coverage for all users |
| 198 | `WHERE user_id='user_1'` — `fetch_user_notes_signals()` session_user_notes SELECT | SILENT_BREAK — User B's plan personalized with User A's notes |
| 225 | `WHERE user_id='user_1' AND still_weak=1` — question_notes SELECT | SILENT_BREAK |

### scripts/db_init.py (schema DDL only — not runtime data access)

Lines 36, 74, 89, 97, 108, 143, 153, 158, 172, 191: All `DEFAULT 'user_1'` in CREATE TABLE statements. Severity: **SILENT_BREAK** — every new record auto-assigns user_1 if caller doesn't pass user_id.

---

## 2. Complete DB Schema Inventory

### Tables without user_id (globally shared — safe across users)

| Table | Notes |
|-------|-------|
| `pyq_questions` | Global question bank — UPSC PYQs shared by all users. No user_id needed. CORRECT. |
| `session_answers` | Has no user_id column. Scoped only by session_id. Risk: if session_id is known to another user, cross-read is possible. LOW risk in practice if sessions are UUID-based. |
| `session_summaries` | No user_id column. Scoped by session_id. Same risk as session_answers. |
| `subtopic_difficulty` | No user_id column. `subtopic_id` is PRIMARY KEY. This is **GLOBAL STATE** — difficulty tier is shared across all users. User A's quiz performance changes difficulty for User B. ARCHITECTURAL PROBLEM. |
| `quiz_session_subtopics` | No user_id column. Scoped by session_id. Low risk if UUIDs are unguessable. |
| `plan_edit_log` | No user_id column. Contains user's plan edits. Should be per-user. |

### Tables with user_id and DEFAULT 'user_1'

| Table | user_id Position | Default | UNIQUE Constraint | Flag |
|-------|-----------------|---------|-------------------|------|
| `quiz_sessions` | Column 2 | `'user_1'` | None on user_id | SILENT_BREAK — sessions created without user_id param default to user_1 |
| `subtopic_scores` | Column 2 | `'user_1'` | UNIQUE(user_id, subject_id, topic_id, subtopic_id) | Safe if user_id populated — UNIQUE constraint is multi-tenant compatible |
| `sar_scores` | PRIMARY KEY | `'user_1'` | PRIMARY KEY = user_id | SILENT_BREAK — only one SAR row per user_id; default 'user_1' means all users share one SAR |
| `subject_attestations` | Column 2 | `'user_1'` | None | SILENT_BREAK |
| `study_plan_log` | Column 2 | `'user_1'` | None | SILENT_BREAK |
| `session_user_notes` | Column 2 | `'user_1'` | PRIMARY KEY = session_id (not user_id!) | CRITICAL — primary key is session_id, so user_id is decorative; two users in same session impossible but query filter on user_id='user_1' will exclude User B's notes |
| `subtopic_dimension_scores` | Column 2 | `'user_1'` | UNIQUE(user_id, subject_id, subtopic_id, dimension_id) | Safe once user_id populated |
| `question_notes` | Column 2 | `'user_1'` | UNIQUE(session_id, question_hash) — NOT including user_id! | SILENT_BREAK — two users' notes for the same session+question will conflict |
| `content_feedback` | Column 2 | `'user_1'` | None | SILENT_BREAK |
| `exam_sim_records` | Column 2 | `'user_1'` | UNIQUE = session_id | user_id is filter only — safe if populated |

### Tables that are truly global (no user_id needed)

- `pyq_questions` — shared question bank
- `syllabus` (file-based) — shared across all users

### Critical schema issues

1. **`sar_scores.user_id` is PRIMARY KEY** — correct design, but `db_init.py:153` does `INSERT OR IGNORE INTO sar_scores (user_id) VALUES ('user_1')`. This seeds exactly one row. New users will have no SAR row until their first attestation; `get_sar()` defaults to 0.5 which is acceptable, but the seeding is single-user.

2. **`question_notes` UNIQUE(session_id, question_hash)** — does not include user_id. If User A and User B happen to answer the same question in different sessions with the same hash (content-based hash), no collision. But both users in a shared session would collide. Low risk for now.

3. **`subtopic_difficulty` has no user_id** — every user's quiz performance mutates a single global difficulty state per subtopic. This is an architectural choice that needs review for multi-user launch.

---

## 3. File-Level Auth Injection Map

### backend/routes/sessions.py

| Endpoint | Method | Writes data? | Needs Depends(get_current_user)? | Notes |
|----------|--------|-------------|----------------------------------|-------|
| `GET /exam-sim/history` | GET | No | YES | Filters by hardcoded `user_id='user_1'` |
| `GET /` (list_sessions) | GET | No | YES | No user_id filter at all — returns ALL sessions |
| `POST /answer` | POST | YES via score_engine | YES | Calls `record_answer()` — no user_id passed |
| `POST /expand-concept` | POST | YES | YES | Writes `concept_expanded=1` to session_answers |
| `POST /expand-notes-selection` | POST | No DB write | YES | AI call — no auth needed for data isolation but access control needed |
| `GET /{session_id}/user-notes` | GET | No | YES | Hardcoded `user_id='user_1'` in query |
| `PUT /{session_id}/user-notes` | PUT | YES | YES | Hardcoded `'user_1'` in INSERT |
| `POST /{session_id}/revision-notes` | POST | No (reads cache only) | YES | Reads any session's wrong answers — no user filter |
| `POST /{session_id}/close` | POST | YES | YES | Calls close_session — updates scores for user_1 |
| `GET /{session_id}` | GET | No | YES | No user filter — any user can read any session |
| `PUT /{session_id}/question-notes/{hash}` | PUT | YES | YES | Hardcoded `'user_1'` in INSERT |
| `GET /{session_id}/question-notes` | GET | No | YES | Hardcoded `user_id='user_1'` in query |
| `GET /{session_id}/exam-results` | GET | No | YES | No user filter — any user can read any session results |
| `POST /import` | POST | YES | YES | Imports session without user scoping |

### backend/routes/quiz.py

| Endpoint | Method | Writes data? | Needs auth? | Notes |
|----------|--------|-------------|-------------|-------|
| `POST /generate` | POST | YES | YES | Creates quiz_sessions row; calls `_get_quiz_intelligence()` with hardcoded user_1 |
| `POST /start` (exam sim) | POST | YES | YES | Creates quiz_sessions row; no user_id passed |
| `POST /pyq` | POST | No | YES | Reads from global pyq_questions — could be public |

### backend/routes/tracker.py

| Endpoint | Method | Writes data? | Needs auth? | Notes |
|----------|--------|-------------|-------------|-------|
| `GET /profile` | GET | No | YES | Reads file-based prep_profile.json — currently single-file |
| `GET /subjects` | GET | No | YES | Hardcoded `user_id='user_1'` |
| `GET /subtopics/{subject_id}` | GET | No | YES | Hardcoded `user_id='user_1'` |
| `GET /gaps` | GET | No | YES | Hardcoded `user_id='user_1'` |
| `GET /sar` | GET | No | YES | Hardcoded `user_id='user_1'` |
| `GET /time-stats` | GET | No | YES | No user_id filter — returns time stats for ALL sessions |

### backend/routes/plan.py

| Endpoint | Method | Writes data? | Needs auth? | Notes |
|----------|--------|-------------|-------------|-------|
| `GET /today` | GET | No | YES | Reads single shared `data/study_plan.json` |
| `GET /syllabus-tree` | GET | No | Could be public | Syllabus is global |
| `PATCH /user-sessions` | PATCH | YES | YES | Writes to single `data/study_plan_user.json` — will clobber User A's edits |
| `DELETE /user-overrides` | DELETE | YES | YES | Deletes single `data/study_plan_user.json` |
| `GET /today-status` | GET | No | YES | Reads all completed sessions — no user filter |
| `POST /generate` | POST | YES | YES | Writes to single `data/study_plan.json` |
| `GET /trajectory` | GET | No | YES | Reads single `data/prep_profile.json` |

### backend/routes/feedback.py

| Endpoint | Method | Writes data? | Needs auth? | Notes |
|----------|--------|-------------|-------------|-------|
| `POST /content` | POST | YES | YES | Hardcoded `'user_1'` in INSERT |
| `GET /content/summary` | GET | No | YES | Returns ALL users' feedback aggregated — no user filter |

### backend/routes/analysis.py

| Endpoint | Method | Writes data? | Needs auth? | Notes |
|----------|--------|-------------|-------------|-------|
| `POST /sync` | POST | YES | YES | Calls `run_analysis()` — reads all unsynced sessions regardless of user; writes to single `data/prep_profile.json` |

### backend/routes/attestation.py

| Endpoint | Method | Writes data? | Needs auth? | Notes |
|----------|--------|-------------|-------------|-------|
| `POST /claim` | POST | No | YES | Generates quiz — no data write |
| `POST /validate` | POST | YES | YES | Calls `record_attestation(subject_id, result)` with default `user_id='user_1'` in self_attestation.py |

### backend/routes/config.py

| Endpoint | Method | Writes data? | Needs auth? | Notes |
|----------|--------|-------------|-------------|-------|
| `GET /` | GET | No | YES | Reads single `data/prep_config.json` |
| `POST /` | POST | YES | YES | Writes to single `data/prep_config.json` — User B overwrites User A's exam date |

### backend/routes/library.py

| Endpoint | Method | Writes data? | Needs auth? | Notes |
|----------|--------|-------------|-------------|-------|
| `GET /file` | GET | No | YES | Serves files from local UPSC_CONTENT_PATH — acceptable to lock to authenticated users |

### Summary: Endpoints that write data WITHOUT a user_id (will corrupt multi-user data)

Critical write endpoints with no user scoping (SILENT_BREAK on second user):

1. `POST /sessions/answer` → `record_answer()` — session_answers row has no user_id; session_id is the only scope
2. `POST /sessions/{id}/close` → `close_session()` → `_update_subtopic_scores()` — always writes user_1
3. `PUT /sessions/{id}/user-notes` — hardcoded 'user_1'
4. `PUT /sessions/{id}/question-notes/{hash}` — hardcoded 'user_1'
5. `POST /feedback/content` — hardcoded 'user_1'
6. `POST /analysis/sync` — writes to single prep_profile.json
7. `POST /plan/generate` — writes to single study_plan.json
8. `PATCH /plan/user-sessions` — writes to single study_plan_user.json
9. `POST /config` — writes to single prep_config.json
10. `POST /attestation/validate` — calls record_attestation with user_id='user_1'

---

## 4. File-Based State (Non-DB Concerns)

The following JSON files are **global singletons** — not per-user:

| File | Written by | Read by | Multi-user risk |
|------|-----------|---------|-----------------|
| `data/prep_profile.json` | `batch_analyse.py:save_profile()`, read by `batch_analyse.py`, `plan_generator.py`, `backend/routes/tracker.py` `GET /profile`, `backend/routes/plan.py` `GET /trajectory` | All tracker/plan routes | CRITICAL — User B's sync call overwrites User A's readiness profile. There is ONE prep_profile.json for the entire app. |
| `data/prep_profile_csat.json` | (CSAT system — placeholder) | Separate CSAT routes | Same risk as above |
| `data/study_plan.json` | `plan_generator.py:generate_plan()`, read by `backend/routes/plan.py` | Plan routes, frontend planner page | CRITICAL — User B generating a plan overwrites User A's plan for the day |
| `data/study_plan_user.json` | `backend/routes/plan.py PATCH /user-sessions` | Plan routes | CRITICAL — User B's edits clobber User A's |
| `data/prep_config.json` | `backend/routes/config.py POST /config` | All plan/trajectory routes | HIGH — User B setting their exam date overwrites User A's |
| `cache/explanations.json` | `quiz.py:synthesize_notes_cached()`, `sessions.py:_save_cache()` | Quiz and session routes | LOW — cache is keyed by content hash, not user; sharing cache is acceptable |
| `data/syllabus.json` | Ingestion scripts (never by API) | All routes | SAFE — truly global read-only config |

**Impact when User B syncs:**  
`batch_analyse.py:run_analysis()` reads `quiz_sessions WHERE synced=0` — this will pull ALL users' unsynced sessions (no user filter), aggregate them as if they are one user, then write a single merged prep_profile.json. If User A synced at 8 PM and User B synced at 9 PM, the second sync will include User B's sessions in User A's readiness profile.

**Impact when User B generates a plan:**  
`plan_generator.py:generate_plan()` reads `prep_profile.json` (single file), computes coverage from `subtopic_scores WHERE user_id='user_1'` (wrong user), then writes to `data/study_plan.json` — overwriting User A's plan.

**Required fix:**  
Move all per-user files to `data/profiles/{user_id}/prep_profile.json`, `data/profiles/{user_id}/study_plan.json`, `data/profiles/{user_id}/prep_config.json`. File path construction must use authenticated user_id.

---

## 5. Frontend Concerns

### How the frontend identifies the current user

**There is no user identity on the frontend.** The Next.js app (`web/src/`) has zero authentication logic:

- `web/src/lib/api.ts` — all requests go to `/api/backend` (Next.js proxy → FastAPI on port 8000) with no Authorization header, no token, no user cookie, no session management
- No `useSession()`, no `useUser()`, no Supabase client import anywhere in `web/src/`
- No login page, no logout, no protected routes
- The `BASE = "/api/backend"` pattern in api.ts means all fetch calls are anonymous

### Frontend file-by-file assessment

| File | User assumptions | Risk |
|------|-----------------|------|
| `web/src/lib/api.ts` | None — no user context | NOISY_BREAK after auth added (all calls will 401 until token injection added) |
| `web/src/app/page.tsx` (dashboard) | None — calls `api.getProfile()`, `api.getPlan()`, `api.getConfig()` | Data isolation breaks silently (see Section 4) |
| `web/src/app/session/page.tsx` | None — session_id from URL | Safe — session_id scoping is correct if sessions are user-owned in DB |
| `web/src/app/tracker/page.tsx` | None — calls tracker endpoints | SILENT_BREAK — tracker endpoints return user_1 data for everyone |
| `web/src/app/planner/page.tsx` | None | SILENT_BREAK — plan endpoints serve user_1's plan to all |
| `web/src/app/attestation/page.tsx` | None | SILENT_BREAK — SAR score shared |
| `web/src/app/analysis/page.tsx` | None | SILENT_BREAK |
| `web/src/app/exam-sim/page.tsx` | None | SILENT_BREAK |
| `web/src/app/setup/page.tsx` | None — writes to `POST /config` | CRITICAL — User B's exam date overwrites User A's |

### What Sprint 2 must add to the frontend

1. Supabase client initialization (`@supabase/supabase-js`)
2. Auth provider wrapping the app in `layout.tsx`
3. Login/signup page (or Supabase Auth UI)
4. Bearer token injection in `web/src/lib/api.ts` — every `fetch()` call needs `Authorization: Bearer <token>` header
5. Protected route middleware in `web/next.config.ts` or via middleware.ts
6. Redirect to login when 401 received

---

## 6. Migration Complexity Score

### Per-table complexity

| Table | Complexity | Reason |
|-------|-----------|--------|
| `quiz_sessions` | LOW | Has user_id column with DEFAULT 'user_1'. One-time UPDATE: `SET user_id='rahul' WHERE user_id='user_1'`. Then all route code must pass authenticated user_id instead of relying on default. |
| `session_answers` | MEDIUM | No user_id column — must derive from parent `quiz_sessions.user_id` via JOIN for all multi-user queries. Adding a user_id column requires ALTER TABLE (approval gate). Alternatively, access via session_id FK is sufficient if quiz_sessions is properly user-scoped. |
| `subtopic_scores` | LOW | Has user_id. UNIQUE(user_id, subject_id, topic_id, subtopic_id) is correct multi-user design. One-time UPDATE + code changes to pass current user. |
| `subtopic_dimension_scores` | LOW | Same as subtopic_scores — user_id present, UNIQUE includes user_id. |
| `sar_scores` | LOW | user_id is PRIMARY KEY — correct. One row per user. Seed new users on first attestation. |
| `subject_attestations` | LOW | Has user_id column. Code fix only. |
| `session_summaries` | MEDIUM | No user_id column. Either add user_id column (ALTER TABLE approval needed) or access via session_id FK chain. |
| `session_user_notes` | MEDIUM | Has user_id but PRIMARY KEY is `session_id` — current schema means only one notes row per session regardless of user. Not a problem if sessions are user-owned. Code fix to use dynamic user_id. |
| `question_notes` | MEDIUM | Has user_id but UNIQUE(session_id, question_hash) does not include user_id. If two users ever share a session (not current design), notes would conflict. In practice sessions are per-user so this is LOW risk. Code fix to pass user_id. |
| `content_feedback` | LOW | Has user_id with DEFAULT. Code fix only. |
| `exam_sim_records` | LOW | Has user_id with DEFAULT. Code fix only. |
| `subtopic_difficulty` | HIGH | No user_id column. This is a global difficulty tier per subtopic. Architectural decision needed: (a) keep global (simplest, may produce better difficulty estimation across users) or (b) make per-user. If per-user: ALTER TABLE to add user_id + redesign difficulty_engine.py. |
| `study_plan_log` | LOW | Has user_id but is append-only log. Code fix only. |
| `plan_edit_log` | MEDIUM | No user_id column. Should be per-user log. ALTER TABLE needed or derive from session context. |
| `quiz_session_subtopics` | LOW | No user_id but scoped by session_id. If sessions are user-owned, this is implicitly per-user. |
| `pyq_questions` | NONE | Truly global. No changes needed. |

### File-based state migration complexity

| File path pattern | Current | Target | Complexity |
|------------------|---------|--------|-----------|
| `data/prep_profile.json` | Single file | `data/profiles/{user_id}/prep_profile.json` | HIGH — affects batch_analyse.py, plan_generator.py, 4 route files |
| `data/study_plan.json` | Single file | `data/profiles/{user_id}/study_plan.json` | HIGH — affects plan_generator.py, plan.py routes |
| `data/study_plan_user.json` | Single file | `data/profiles/{user_id}/study_plan_user.json` | MEDIUM — affects plan.py routes only |
| `data/prep_config.json` | Single file | `data/profiles/{user_id}/prep_config.json` | MEDIUM — affects config.py, plan_generator.py, batch_analyse.py, plan.py |
| `cache/explanations.json` | Single cache | Keep shared — content-hash keyed | NONE — sharing is safe |

### Overall migration risk: HIGH

Rationale: The file-based state problem (prep_profile.json, study_plan.json, prep_config.json) is architectural — it isn't just about swapping `'user_1'` to a dynamic value. The batch analysis engine (`batch_analyse.py`) reads all unsynced sessions globally, then writes to a single profile file. This requires redesigning the analysis pipeline to be user-scoped. Combined with 41 hardcoded `'user_1'` sites across 9 files plus frontend authentication missing entirely, this is a multi-day effort, hence the Sprint 2 allocation of 3 build days.

---

## 7. Top 5 Silent Failure Risks

Ranked by severity when a second user (User B) exists alongside User A (Rahul):

### Rank 1: CRITICAL — batch_analyse.py corrupts readiness profile for all users

**What happens:** User B clicks "Sync" from the frontend. `POST /analysis/sync` calls `run_analysis()`. The function queries `quiz_sessions WHERE synced=0 AND end_time IS NOT NULL` — no user_id filter. It picks up User B's sessions AND any remaining unsynced sessions from User A. It aggregates them as if they belong to one person, computes weighted readiness, then calls `save_profile()` which overwrites `data/prep_profile.json`. User A's readiness scores are now contaminated with User B's quiz performance.

**Detection:** Will NOT raise an error. User A will see their readiness change unexpectedly after User B syncs. Very hard to debug without understanding the architecture.

**Severity:** Data corruption of core prep metric. Affects every downstream feature: plan generation, trajectory, gap analysis.

### Rank 2: CRITICAL — score_engine.py writes subtopic scores to wrong user

**What happens:** User B completes a quiz session. `POST /sessions/{id}/close` calls `close_session()`. `_update_subtopic_scores()` hardcodes `WHERE user_id='user_1'` in both SELECT (to find existing row) and UPDATE. User B's correct answers credit User A's subtopic_scores. User A's tracker shows artificially inflated scores for subjects they never studied.

**Detection:** Will NOT raise an error. User A's tracker data silently improves. User B's tracker stays at zero (no rows created for user_b's user_id).

**Severity:** Core product feature (progress tracking) is completely wrong for both users.

### Rank 3: HIGH — quiz_sessions has DEFAULT 'user_1' but no code enforces it per-user at generation time

**What happens:** User B starts a quiz via `POST /quiz/generate`. The session is created with `user_id='user_1'` (the column default fires because the INSERT statement in quiz.py does not include user_id). `GET /sessions/` (list_sessions) has no user_id filter — it returns ALL sessions from ALL users sorted by start_time. User B sees User A's entire session history on their sessions page.

**Detection:** Will NOT raise an error. Users see each other's full session lists.

**Severity:** Cross-user data exposure — privacy violation and confusing UX.

### Rank 4: HIGH — plan generation overwrites shared plan file for all users

**What happens:** User B clicks "Plan Today" from the frontend. `POST /plan/generate` calls `generate_plan()` which reads the single `data/prep_profile.json` (populated with user_1's data from risk #1), builds a plan based on user_1's coverage state, and writes it to `data/study_plan.json`. User A's plan for the day is destroyed and replaced by a plan built on User B's study state (which itself is based on User A's quiz history — a compounding failure).

**Detection:** Will NOT raise an error. User A's plan silently disappears mid-session.

**Severity:** Core daily workflow (plan-driven study sessions) breaks for whoever generates a plan second.

### Rank 5: HIGH — quiz intelligence uses cross-user history to personalize question generation

**What happens:** `_get_quiz_intelligence()` in quiz.py queries `session_answers` and `session_user_notes` with hardcoded `user_id='user_1'`. User B's quiz gets injected with User A's excluded question hashes, wrong concepts, and confusion notes. User B's quiz is therefore personalized toward User A's weaknesses, not User B's. Additionally, `_get_tested_subtopics_for_subject()` reads User A's tested subtopic list — so User B's quiz engine believes User B has already tested subtopics they have never seen, and skips diagnostic questions for those subtopics.

**Detection:** Will NOT raise an error. Subtle UX degradation — User B's quiz quality is wrong in a non-obvious way.

**Severity:** The adaptive quiz engine — the core AI feature of Nyaya Recall — produces incorrect personalization for all users except the one whose data is in user_1.

---

## Summary of Key Pre-Migration Actions Required

### Phase A: Code changes (no schema migration — do before Supabase setup)
1. Create `backend/auth.py` with Supabase JWT middleware (`get_current_user` dependency)
2. Thread `current_user` through all 14 route files — replace every `'user_1'` literal
3. Move file paths to per-user namespace: `data/profiles/{user_id}/prep_profile.json` etc.
4. Add user_id parameter to `batch_analyse.run_analysis()`, `plan_generator.generate_plan()`, and all score_engine functions
5. Add `Authorization: Bearer <token>` to all fetch calls in `web/src/lib/api.ts`
6. Add auth provider, login page, and protected routes to Next.js app

### Phase B: Schema migration (requires approval gates per CLAUDE.md)
1. `ALTER TABLE session_answers ADD COLUMN user_id TEXT` — approval required
2. `ALTER TABLE session_summaries ADD COLUMN user_id TEXT` — approval required
3. `ALTER TABLE plan_edit_log ADD COLUMN user_id TEXT` — approval required
4. Decision required: keep `subtopic_difficulty` global or add user_id
5. One-time data migration: `UPDATE ... SET user_id='rahul' WHERE user_id='user_1'` — approval required before execution

### Phase C: SQLite → PostgreSQL (Sprint 2 completion)
- Switch `sqlite3.connect(DB_PATH)` → SQLAlchemy async session
- Replace `sqlite3.Row` with SQLAlchemy ORM or raw asyncpg
- WAL mode not needed (PostgreSQL handles concurrency natively)
- `db.py:enable_wal()` can be removed

---

*Audit completed: 2026-06-15. All findings derived from direct source file reads. No code was modified.*
