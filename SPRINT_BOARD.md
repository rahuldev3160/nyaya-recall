# SPRINT BOARD — Nyaya Recall
**Project:** Nyaya Recall (Devthorium rebranded for public SaaS launch)
**Status:** Sprint 0 DONE | Sprint 2 starts next | Sprint 1 BLOCKED (Rahul PDF download)
**Updated:** 2026-06-15 (post 3-agent audit synthesis)
**Build capacity:** 2–4 hrs/day solo
**IES exam:** Jun 19–21 — no coding
**Revenue targets:** First ₹ July | ₹5–8k Jul 31 | ₹20–25k Sep

**Audit documents:**
- `docs/migration/01_codebase_audit.md` — 41 hardcoded user_1 sites, all silent breaks
- `docs/migration/02_infra_architecture.md` — Railway reuse, cost model, 3 top risks

---

## SPRINT 0 — DONE ✅
**Merged:** Jun 15, 2026 | **PR #42**

| Bug | File | Fix |
|-----|------|-----|
| C7 — hardcoded exam date | `backend/routes/plan.py:214` | `_get_exam_date()` reads `target_date` from `prep_config.json`. RAS Nov 29 set. |
| C6 — KeyError on fresh DB | `scripts/score_engine.py:312` | `a["concept_expanded"]` → `a.get("concept_expanded")` |
| C2 — SQLite WAL mode missing | new `backend/db.py` | WAL pragma + busy_timeout=5000. `enable_wal()` at startup (WAL is durable). |

**Remaining WAL gap (Sprint 2 prerequisite):** All 10 route files still call `sqlite3.connect()` directly, bypassing `get_conn()`'s `busy_timeout`. WAL mode itself is durable (set at file level by `enable_wal()`), so concurrent reads are safe. But concurrent writers queue without timeout — first public traffic spike will hit 500 errors. Fix in Sprint 2 before deploy.

---

## SPRINT 1 — BLOCKED ⏸
**Estimate:** 1 build day (after Rahul data arrives)
**Feature:** PYQ Data Foundation (FEATURE-17)
**Blocker owner:** Rahul — download UPSC PDFs

### Rahul must do (no code substitutes this)
- [ ] Go to https://upsc.gov.in/examinations/previous-year-question-papers
- [ ] Download **Final Answer Keys** for GS Paper I, 2013–2025 (use Final Key, not provisional)
- [ ] Download GS Paper I PDFs for 2013 + any gap years with <95 questions in DB
- [ ] Convert answer keys to CSV: `year,q_number,correct_answer,cancelled,dispute_note`
- [ ] Estimated time: 1–2 hours

### Pre-build scripts (no blocker — start now)

| Task | File | Hours |
|------|------|-------|
| `scripts/import_answer_keys.py` | new | 2h |
| `scripts/audit_pyq_completeness.py` | new | 1h |
| `scripts/fix_year_zero.py` | new | 1h |
| Update `ingest_pyq.py` to capture `q_number` | existing | 1h |

### Approval gates (flag before executing)
- ⚠️ `ALTER TABLE pyq_questions` — add `answer_source`, `answer_disputed`, `dispute_note`, `q_number`
- ⚠️ `DELETE FROM pyq_questions` — fix 2014 duplication (~32 rows removed)

### Exit criteria
- All 2013–2025 years: ≥95 rows each
- Zero `answer_source = 'ai_inferred'`
- `audit_pyq_completeness.py` passes all years

---

## SPRINT 2 — NEXT ▶ (Auth + Multi-tenancy + PostgreSQL)
**Estimate:** 5–6 build days (revised up from 3 — audit found 41 sites across 9 files, not 16)
**Can start:** Jun 15 (Clusters A + C) — waiting on Rahul for Supabase keys only (10 min)
**Does NOT depend on:** Sprint 1 data

> **Architecture decision locked (Jun 15):** PostgreSQL migration happens in Sprint 2, not later.
> SQLite + WAL handles ~50 concurrent active users, but multi-tenancy + PostgreSQL must be one migration to avoid data format drift. Reuse Railway — add Recall as a second service on the same Railway project as Nyaya Scribe.

### Infra decisions before Sprint 2 starts

1. **Rahul creates Supabase project** (10 min): supabase.com → New project → copy `Project URL` + `Anon Key` + `JWT Secret` into `.env`
2. **Rahul creates Railway service for Recall** (15 min): Railway dashboard → same project as Scribe → New Service → link GitHub repo → add PostgreSQL addon (shared with Scribe or new one)
3. **Architectural decision: `subtopic_difficulty` table** — currently global (one difficulty tier per subtopic, shared across all users). Options:
   - **KEEP GLOBAL (recommended):** crowd-sourced difficulty across users = better signal. Simpler. No ALTER TABLE.
   - **Per-user:** ALTER TABLE + difficulty engine redesign. More accurate for edge-case users but complex.
   - ⚠️ Rahul approves before Sprint 2 starts.

### Cluster breakdown — parallel agent execution

---

#### CLUSTER A — Supabase Auth Backend ▶ START NOW
**Parallel with:** Cluster C
**Hours:** 4h
**Output:** `backend/auth.py` + pilot route wired

Tasks:
- [ ] Install `PyJWT`: add to `requirements.txt`
- [ ] Write `backend/auth.py`:
  - `get_current_user(authorization: str = Header(...)) → str` — returns Supabase UUID
  - JWT decode with HS256 + `audience="authenticated"` + `SUPABASE_JWT_SECRET`
  - `HTTPException(401)` on invalid/expired token
- [ ] Wire `Depends(get_current_user)` into pilot route (`POST /quiz/generate`) — validate pattern before spreading
- [ ] Add to `.env`: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`

**Watch-outs:**
- Supabase uses HS256 by default — confirm in your project's Settings → API → JWT Settings
- `is_pro` must come from our `user_profiles` table, NOT Supabase user metadata (users can edit metadata)

---

#### CLUSTER B — DB Schema + PostgreSQL Migration
**Parallel with:** Cluster C (independent until user_id type confirmed)
**Sequential after:** Cluster A (needs user_id type = Supabase UUID TEXT confirmed)
**Hours:** 6h

**Key audit finding:** 41 hardcoded `'user_1'` sites across 9 files — all are SILENT_BREAK.

Tasks:
- [ ] Add `get_conn()` calls to all route files (replace all `sqlite3.connect(DB_PATH)` — 29 sites in backend alone)
- [ ] Replace all `'user_1'` literals with dynamic `user_id` from `Depends(get_current_user)` — 41 sites:
  - `sessions.py`: 10 sites
  - `score_engine.py`: 9 sites (pass `user_id` as parameter to all `_update_*` functions)
  - `plan_generator.py`: 3 sites (add `user_id` param to `generate_plan()`, `compute_subtopic_coverage()`)
  - `batch_analyse.py`: 2 sites (add `user_id` param to `run_analysis()` — biggest refactor)
  - `tracker.py`: 4 sites
  - `feedback.py`: 2 sites
  - `quiz.py`: 2 sites
  - `server.py` DDL: 3 sites (remove DEFAULT 'user_1' from DDL — let NOT NULL enforce it)
  - `db_init.py` DDL: 10 sites (same)
- [ ] Write new `user_profiles` table:
  ```sql
  CREATE TABLE user_profiles (
      user_id       TEXT PRIMARY KEY,
      display_name  TEXT,
      email         TEXT,
      exam_type     TEXT DEFAULT 'upsc_prelims',
      target_date   DATE,
      daily_hours   REAL DEFAULT 2.0,
      tier          TEXT DEFAULT 'free',
      created_at    TIMESTAMPTZ DEFAULT NOW()
  );
  ```
- [ ] Fix `sar_scores` schema: change `user_id TEXT PRIMARY KEY` → `id SERIAL PRIMARY KEY, user_id TEXT UNIQUE` (current PK breaks multi-user INSERT)
- [ ] Write PostgreSQL DDL for all tables (`scripts/migrate_to_postgres.py`)
- [ ] Write data migration script (DO NOT EXECUTE until Rahul approves):
  ```sql
  UPDATE quiz_sessions SET user_id='<rahul_uuid>' WHERE user_id='user_1';
  -- + 8 more tables (see docs/migration/02_infra_architecture.md §3)
  ```

**Approval gates:**
- ⚠️ `ALTER TABLE sar_scores` — change PRIMARY KEY structure
- ⚠️ `UPDATE ... SET user_id='<rahul_uuid>'` — execute only after Rahul confirms UUID

---

#### CLUSTER C — Frontend Auth Flow ▶ START NOW
**Parallel with:** Cluster A
**Hours:** 4h

**Key audit finding:** Frontend has ZERO auth infrastructure. `api.ts` sends 30+ calls with no Authorization header.

Tasks:
- [ ] `npm install @supabase/supabase-js` in `web/`
- [ ] Create `web/src/lib/supabase.ts` — Supabase client singleton
- [ ] Create `web/src/lib/auth.ts` — `getSession()`, `signInWithMagicLink()`, `signOut()`
- [ ] Create `web/src/app/login/page.tsx` — magic link form + Google OAuth
- [ ] Create `web/src/app/auth/callback/page.tsx` — OAuth redirect handler
- [ ] Create `web/src/components/AuthGuard.tsx` — redirects to /login if no session
- [ ] Update `web/src/lib/api.ts` — add `Authorization: Bearer <token>` to ALL 30+ `fetch()` calls
- [ ] Update `web/src/app/layout.tsx` — wrap with `<AuthGuard>`
- [ ] Update `web/next.config.ts` — add `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`

**Watch-outs:**
- `NEXT_PUBLIC_*` vars go in `web/.env.local`, NOT root `.env`
- `SUPABASE_JWT_SECRET` is backend-only — never expose to frontend
- Magic link email delivery needs Supabase email templates configured before testing

---

#### CLUSTER D — File-Based State → DB + Profile Namespacing
**Sequential after:** Cluster B (needs `user_profiles` table)
**Hours:** 4h

**Key audit finding:** `prep_profile.json`, `study_plan.json`, `prep_config.json` are global singletons. User B's sync call overwrites User A's profile. This is the #1 silent failure risk.

Tasks:
- [ ] `batch_analyse.py`: add `user_id` param to `run_analysis()`, `get_unsynced_summaries()` — filter all DB reads by user_id; write profile to `data/profiles/{user_id}/prep_profile.json`
- [ ] `plan_generator.py`: add `user_id` param to `generate_plan()`, `compute_subtopic_coverage()` — write to `data/profiles/{user_id}/study_plan.json`
- [ ] `backend/routes/plan.py`: read profile from `data/profiles/{user_id}/prep_profile.json`
- [ ] `backend/routes/config.py`: read/write `data/profiles/{user_id}/prep_config.json`; read `user_profiles` table for exam_type/target_date
- [ ] `backend/routes/tracker.py`: pass `user_id` from `Depends(get_current_user)` to all queries
- [ ] `backend/routes/analysis.py`: pass `user_id` to `run_analysis()`
- [ ] Write rollback script: `scripts/rollback_user_migration.py`

---

### Sprint 2 execution order

```
Jun 15–18 (before IES exam):
  Day 1: Cluster A (auth.py) + Cluster C frontend shell — in parallel
  Day 2: Cluster B Part 1 — replace 41 user_1 literals + get_conn() migration
  Day 3: Cluster B Part 2 — PostgreSQL DDL + migration scripts

Jun 19–21: IES exam — NO CODING

Jun 22–23 (post-exam):
  Day 4: Cluster D — JSON file → DB migration + batch_analyse.py refactor
  Day 5: Wire Cluster A into all routes + PostgreSQL deploy + end-to-end test
  Day 6 (if needed): Fix any test failures
```

### Sprint 2 exit criteria
- Any Supabase user signs up → working session → quiz → sync — all isolated from other users
- All routes return 401 without JWT
- Rahul's existing data works under `user_id='<rahul_uuid>'` post-migration
- `data/upsc.db` data successfully migrated to Railway PostgreSQL
- `npx tsc --noEmit` + lint pass

---

## SPRINT 3 — PYQ Browser
**Estimate:** 1 build day
**Depends on:** Sprint 1 (official answers) + Sprint 2 (auth)
**Spec:** `plans/pyq_browser.md`

Sub-tasks (all parallel within sprint):

| Task | File | Hours | Parallel? |
|------|------|-------|-----------|
| `pyq_attempts` table + indexes | `scripts/db_init.py` | 0.5h | Yes |
| 5 backend endpoints | `backend/routes/pyq.py` (new) | 3h | Yes |
| `YearGrid.tsx` | `web/src/components/YearGrid.tsx` | 1h | Yes — build with mock now |
| `SubjectCards.tsx` | `web/src/components/SubjectCards.tsx` | 1h | Yes — build with mock now |
| `TopicAccordion.tsx` | `web/src/components/TopicAccordion.tsx` | 1h | Yes — adapts from Tracker |
| `PYQQuizRunner.tsx` | `web/src/components/PYQQuizRunner.tsx` | 2h | After backend routes |
| `/pyq` page | `web/src/app/pyq/page.tsx` | 2h | After components |

---

## SPRINT 4 — PYQ Explanations + Pro Gating
**Estimate:** 1 build day + overnight batch
**Depends on:** Sprint 1 (official answers required — do NOT run batch on AI-inferred answers) + Sprint 3
**One-time cost:** ~₹85 (~$1) Haiku Batch for ~1,300 questions

> **Start Razorpay KYC in this sprint** (not Sprint 8). KYC takes 3–7 days.
> If not started by Sprint 4, July revenue target is at risk.

Sub-tasks:

| Task | File | Hours | Parallel? |
|------|------|-------|-----------|
| Write `prompts/pyq_explanation.txt` | new | 0.5h | Yes — build now |
| Write `scripts/generate_pyq_explanations.py` | new | 2h | Yes — build now |
| `explanations_cache` table (shared across all users — shared cache = ~95% hit rate) | `scripts/db_init.py` | 0.5h | Yes |
| Run batch (~3h runtime) | script | 3h wait | After Sprint 1 data |
| `GET /pyq/explanation/{id}` | `backend/routes/pyq.py` | 0.5h | After table |
| `ExplanationCard.tsx` (blurred free / full Pro) | `web/src/components/ExplanationCard.tsx` | 1.5h | Yes — build now |
| Wire into PYQQuizRunner | `PYQQuizRunner.tsx` | 0.5h | After card |
| `graded_answer_credits` table | new | 0.5h | Yes |
| Razorpay KYC — Rahul action | external | — | Start now, wait 3–7 days |

---

## SPRINT 5 — Onboarding + Per-User Exam Date
**Estimate:** 1 build day
**Depends on:** Sprint 2 (auth)

| Task | File | Hours | Parallel? |
|------|------|-------|-----------|
| `/onboarding` page | `web/src/app/onboarding/page.tsx` | 2h | Yes |
| `POST /users/profile` endpoint | `backend/routes/users.py` (new) | 1h | Yes |
| Save exam target + daily_hours → `user_profiles` | routes/users.py | 0.5h | Yes |
| Per-user exam date drives countdown (permanent C7 fix) | `backend/routes/plan.py` | 0.5h | After users table |
| Redirect new users to /onboarding after signup | `auth/callback/page.tsx` | 0.5h | Yes |

---

## SPRINT 6 — Multi-Exam Question Bank (CDS/NDA PYQs)
**Estimate:** 1.5 build days
**Depends on:** Sprint 2 (auth)
**Blocker on Rahul (secondary):** CDS/NDA/CAPF/CISF PDFs from upsc.gov.in (batch with Sprint 1 download session — same website)

| Task | File | Hours | Parallel? |
|------|------|-------|-----------|
| `question_bank` + `user_question_history` tables | `scripts/db_init.py` | 0.5h | Yes |
| CDS GK ingest (~2,400 questions) | `scripts/ingest_cds.py` (new) | 2h | Yes |
| NDA GAT GK ingest (~1,500 questions) | `scripts/ingest_nda.py` (new) | 2h | Yes |
| CAPF + CISF ingest (~2,250 questions) | `scripts/ingest_capf_cisf.py` (new) | 2h | Yes |
| Retag new rows via `retag_pyq_subtopics.py` | existing | 1h runtime | After ingestion |
| Haiku gap-fill for <10-question subtopics (~₹75) | `scripts/gap_fill_questions.py` (new) | 2h | After retag |
| Rewrite `POST /quiz/generate` — 4-phase serving algorithm | `backend/routes/quiz.py` | 3h | After question_bank |

---

## SPRINT 7 — Analytics + Weakness Engine
**Estimate:** 3 build days
**Depends on:** Sprint 2 + Sprint 6

| Task | File | Hours | Parallel? |
|------|------|-------|-----------|
| `/analytics/weakness-report` endpoint | `backend/routes/analytics.py` (new) | 3h | Yes |
| `/analytics/study-next` — highest ROI recommendation | same | 2h | Yes |
| Adapt `batch_analyse.py` for multi-user PostgreSQL | existing | 4h | Yes |
| Simulation mode with −⅔ negative marking | `quiz.py` + new page | 4h | Yes |
| Post-simulation analytics page | `web/src/app/sim-results/page.tsx` | 3h | After route |
| Topic gap heatmap UI | `web/src/app/analytics/page.tsx` | 3h | Yes |
| "Study Next" widget | `web/src/components/StudyNext.tsx` | 1h | After endpoint |
| Accuracy trend charts | `/analytics/page.tsx` | 2h | Yes |

---

## SPRINT 8 — Deploy + Launch
**Estimate:** 1 build day
**Depends on:** All sprints complete

| Task | Service | Hours | Parallel? |
|------|---------|-------|-----------|
| Railway: FastAPI service deployment | Railway | 1h | Yes |
| Railway: env vars configured | Railway dashboard | 0.5h | Yes |
| Vercel: Next.js deployment | Vercel | 0.5h | Yes |
| Domain config (nyaya.app) | DNS + Vercel | 1h | After both deploys |
| CORS restriction (replace `"*"` with prod domain) | `backend/server.py` | 0.1h | Yes |
| Smoke test auth end-to-end on prod | manual | 0.5h | After deploy |
| Reddit r/upsc launch post (analytics screenshots) | Reddit | 0.5h | After domain |

**Watch-outs:**
- ChromaDB is on Railway volume — single point of failure. Add `/health/chroma` endpoint before launch.
- `cache/explanations.json` must be migrated to `explanations_cache` PostgreSQL table before deploy (Sprint 4).
- CORS: change `allow_origins=["*"]` to `["https://nyaya.app"]` before any public traffic.
- Razorpay KYC must be complete (started Sprint 4, ~7-day lead time).

---

## PARALLEL WORK AVAILABLE NOW (zero blockers)

These can start today. No dependency on PYQ PDFs or Supabase setup:

| Task | Sprint | Hours | Notes |
|------|--------|-------|-------|
| `backend/auth.py` scaffold | S2 | 2h | Use placeholder JWT_SECRET; wire real keys when Rahul sets up Supabase |
| Frontend auth shell (login page, AuthGuard, api.ts headers) | S2 | 4h | Use mock user_id; wire real JWT when auth.py done |
| `scripts/import_answer_keys.py` | S1 | 2h | Script writing; no data needed |
| `scripts/audit_pyq_completeness.py` | S1 | 1h | Reads existing DB; outputs gap report |
| `scripts/fix_year_zero.py` | S1 | 1h | 30-row fix; Haiku cost ~₹0.80 |
| `prompts/pyq_explanation.txt` | S4 | 0.5h | Pure prompt writing |
| `scripts/generate_pyq_explanations.py` | S4 | 2h | Script; won't run until S1 data |
| `ExplanationCard.tsx` | S4 | 1.5h | Mock data; slot in real data later |
| `YearGrid.tsx`, `SubjectCards.tsx`, `TopicAccordion.tsx` | S3 | 3h | Mock data |
| `scripts/migrate_to_postgres.py` | S2 | 3h | Script writing; dry-run mode; do NOT execute |

---

## TASK DEPENDENCY MAP

```
Sprint 0 ✅ (C7+C6+C2 fixed — PR #42)
  │
  ├── Sprint 1 ⏸ BLOCKED (Rahul: UPSC PDFs + answer keys)
  │     │     [Meanwhile: import_answer_keys.py, audit scripts — no blocker]
  │     │
  │     └──► Sprint 3 (PYQ Browser) ←─── also needs Sprint 2
  │                │
  │                └──► Sprint 4 (Explanations + Pro gating + Razorpay KYC)
  │
  ├── Sprint 2 ▶ START NOW
  │     Cluster A (auth.py) ──────┐
  │     Cluster C (frontend)  ────┤ parallel
  │     Cluster B (DB schema) ←───┘ sequential after A
  │     Cluster D (JSON→DB)  ←── sequential after B
  │     │
  │     ├──► Sprint 5 (Onboarding)
  │     ├──► Sprint 6 (Multi-exam bank) ←── also needs Rahul: CDS/NDA PDFs
  │     │          │
  │     │          └──► Sprint 7 (Analytics + Weakness Engine)
  │     │                    │
  │     │                    └──► Sprint 8 (Deploy + Launch)
  │     │
  │     └──► Sprint 3 (above)

TRULY INDEPENDENT (start anytime):
  - All frontend components with mock data (YearGrid, SubjectCards, ExplanationCard)
  - All script scaffolds (import_answer_keys, fix_year_zero, audit_pyq_completeness)
  - prompts/pyq_explanation.txt
  - PostgreSQL migration script (write only — do not run)
```

---

## OPEN BLOCKERS — RAHUL ACTION REQUIRED

| # | What | Blocks | Time needed |
|---|------|--------|-------------|
| B-1 | Create Supabase project → copy 3 keys to `.env` | Sprint 2 Cluster A | 10 min |
| B-2 | Create Railway service for Recall + PostgreSQL addon | Sprint 2 deploy | 15 min |
| B-3 | Approve: `subtopic_difficulty` global vs per-user | Sprint 2 schema | 2 min decision |
| B-4 | Approve: `ALTER TABLE sar_scores` (PK change) | Sprint 2 schema | approval gate |
| B-5 | Download UPSC PYQ PDFs + Final Answer Keys 2013–2025 | Sprint 1 data | 1–2 hrs |
| B-6 | Approve: `ALTER TABLE pyq_questions` (add 4 columns) | Sprint 1 import | approval gate |
| B-7 | Approve: `DELETE FROM pyq_questions` (2014 dedup) | Sprint 1 clean | approval gate |
| B-8 | Approve: `UPDATE ... SET user_id='<rahul_uuid>'` | Sprint 2 go-live | approval gate |
| B-9 | Start Razorpay KYC (3–7 day external wait) | Sprint 4 revenue | 30 min + docs |
| B-10 | Download CDS/NDA/CAPF/CISF PDFs (same session as B-5) | Sprint 6 | 2–3 hrs |

**Critical path blocker:** B-5 (UPSC PDFs). If resolved by Jun 18, launch Jul 4 is achievable. If delayed past Jun 25, Sprint 3+4 shift right and Jul 31 ₹5-8k target is at risk.

---

## INFRA DECISIONS LOCKED (Jun 15)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Railway reuse | Add Recall as 2nd service on same Railway project as Scribe | No second billing, shared PostgreSQL addon |
| SQLite→PostgreSQL timing | Sprint 2 (not later) | Avoids two migrations; WAL threshold is 50 concurrent writers |
| RLS vs application-layer filtering | Application-layer `WHERE user_id=?` in Sprint 2 | Simpler, debuggable; add RLS in Sprint 7 if needed |
| Supabase Auth tier | Free tier through all 8 sprints | 50k MAU limit — won't hit before ₹1L/month revenue |
| `subtopic_difficulty` | **PENDING RAHUL** — recommend: keep global | Crowd-sourced difficulty = better signal; no ALTER TABLE |
| explanations cache | Shared PostgreSQL table (not per-user) | One PYQ explanation serves all users; ~95% cache hit rate from day 1 |
| Payment soft launch | Manual UPI + credit top-up for soft launch | Decouples Razorpay KYC from critical path; Razorpay KYC runs in parallel from Sprint 4 |

---

## COST MODEL SUMMARY

| Scale | MAU | Monthly Cost | Gross Revenue | Gross Margin |
|-------|-----|-------------|--------------|-------------|
| Launch | 100 | ~$39 (~₹3,250) | ₹8–10k | ~65% |
| Sep target | 500 | ~$71 (~₹5,920) | ₹25–35k | ~83% |
| 12-month | 1000 | ~$163 (~₹13,600) | ₹60–75k | ~85% |

Key cost lever: shared `explanations_cache` table — one Haiku call per PYQ question, shared across all users.

---

## TIMELINE ESTIMATE

```
Jun 15–18   Sprint 2 Cluster A + C (auth + frontend shell) — parallel
            Sprint 1 scripts pre-built (parallel — no blocker)
Jun 19–21   IES exam — NO CODING
Jun 22–23   Sprint 2 Cluster B + D (DB schema + JSON migration)
Jun 24      Sprint 2 wrap + PostgreSQL deploy + end-to-end test
            Sprint 1 data arrives (if Rahul downloads Jun 15–18)
Jun 25      Sprint 1 data ingestion (1 day build)
Jun 26      Sprint 3 (PYQ Browser) — 1 day
Jun 27      Sprint 4 (Explanations batch) — start Razorpay KYC same day
Jun 28      Sprint 5 (Onboarding) — 1 day
Jun 29–30   Sprint 6 (Multi-Exam Bank)
Jul 1–3     Sprint 7 (Analytics)
Jul 4       Sprint 8 (Deploy + Launch)
Jul 5–7     First paying users
Jul 31      Target: ₹5–8k (10–16 Pro subscribers)
```

**This timeline holds only if B-5 (UPSC PDFs) is resolved by Jun 18.**
