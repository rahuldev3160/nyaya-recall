# Nyaya Recall — Infrastructure Architecture Design
**Document:** `docs/migration/02_infra_architecture.md`
**Date:** 2026-06-15
**Status:** Design-only. No code changes.
**Scope:** Sprint 2 through launch (Sprint 8) and 12-month post-launch horizon.

---

## 0. Verified Architecture Baseline

Before designing the target state, the following was verified directly from source files:

- **`backend/server.py`:** FastAPI app with CORS `allow_origins=["*"]` (production risk). 10 route modules registered. WAL enabled on startup via `enable_wal()`. No auth middleware. No rate limiting.
- **`backend/db.py`:** WAL + `busy_timeout=5000ms` on every connection. All routes use raw `sqlite3` directly (not via `get_conn()`). [RISK: routes calling `sqlite3.connect()` directly bypass the WAL helper. Must audit during Sprint 2.]
- **`scripts/db_init.py`:** 11 tables. Every table with `user_id` has `DEFAULT 'user_1'`. `sar_scores` uses `user_id` as PRIMARY KEY — this is a breaking constraint for multi-tenancy. `session_answers` has no `user_id` column — must be derived through `quiz_sessions` join.
- **`backend/routes/config.py`:** Reads/writes `data/prep_config.json` as a flat file. No user namespacing.
- **`data/prep_config.json`:** Has `target_date` field (C7 is fixed). Shape: `{total_days, daily_hours, start_date, target_date}`.
- **`sessions.py` / `quiz.py`:** Hardcoded `anthropic.Anthropic()` client instantiated at module load — no lazy init. Prompt files read at module load too — startup crash if file missing.

---

## 1. Current vs Target Architecture

| Layer | Current (local, single-user) | Target (Sprint 8, public SaaS) |
|---|---|---|
| **Auth** | None — all requests accepted | Supabase Auth (email+password, Google OAuth). JWT validated in FastAPI `Depends(get_current_user)` |
| **Database** | SQLite (`data/upsc.db`), WAL mode, single file | PostgreSQL on Railway (managed). SQLite retained locally for dev only |
| **User identity** | `user_id = 'user_1'` hardcoded in 16 sites | `user_id = supabase_uid` (UUID), extracted from JWT per-request |
| **Storage — flat files** | `data/prep_config.json`, `data/prep_profile.json`, `data/study_plan.json` per-process | PostgreSQL `user_profiles` table, keyed by `user_id` |
| **Storage — embeddings** | ChromaDB local (`vector_store/`) | ChromaDB persisted on Railway volume (1 shared instance, read-heavy) |
| **Storage — cache** | `cache/explanations.json` local | PostgreSQL `explanations_cache` table (keyed by SHA256 hash, shared across users) |
| **Deployment** | Local Mac, `0.0.0.0:8000` + `0.0.0.0:3000` | Railway: FastAPI service + PostgreSQL addon. Vercel: Next.js frontend |
| **CORS** | `allow_origins=["*"]` | `allow_origins=["https://nyaya.app", "https://www.nyaya.app"]` |
| **AI calls** | Haiku for classification, Sonnet for generation. No rate limiting | Same models. Per-user rate limiting via Railway env + in-process token counter |
| **Estimated monthly cost** | ~$5–10 (Anthropic API only) | $25–60 depending on user count (see Section 6) |

---

## 2. Migration Path — Use Existing Infra First

### Reuse Railway (Nyaya Scribe is already there)

Rahul already has Railway running Nyaya Scribe (Descriptive-exams). The correct path:

1. **Add Nyaya Recall as a second Railway service** on the same Railway project. Railway supports multiple services per project — they share the project dashboard and billing, but run independently.
2. **Share one Railway PostgreSQL addon** between both services. Each service gets its own schema namespace (`recall.*`, `scribe.*`) or separate databases within the same PostgreSQL instance. [VERIFY: Railway PostgreSQL supports multiple databases in one addon — standard PostgreSQL behaviour, but confirm Railway UI allows `CREATE DATABASE` on managed instances.]
3. **Frontend:** Vercel deployment for Next.js (free tier, zero config from GitHub). Do not deploy Next.js on Railway — it wastes compute.

This avoids spinning up a second Railway project, second billing account, or second DB addon.

### SQLite → PostgreSQL: When to Migrate

**SQLite + WAL is viable up to this threshold:**

> **Migrate to PostgreSQL when any of these is true:**
> - Concurrent active writers exceed ~5 simultaneous (WAL handles concurrent readers, not writers)
> - User count exceeds 50 registered users who are active in overlapping sessions
> - Any route needs row-level security (RLS) — SQLite has no native RLS
> - Data must be shared between multiple Railway service replicas (SQLite is per-process, not network-accessible)

**Current WAL behaviour (verified from `db.py`):** `busy_timeout=5000ms` means writers queue for up to 5 seconds before returning SQLITE_BUSY. With 1–10 concurrent users, this is adequate. At 50+ simultaneous quiz sessions all writing `session_answers`, lock contention becomes user-visible.

**Sprint 2 decision:** Since Sprint 2 adds Supabase auth and multi-tenancy simultaneously, doing the PostgreSQL migration in Sprint 2 is correct. The alternative — adding multi-tenancy on SQLite first, then migrating later — creates two migrations instead of one and risks data format drift. Do both in Sprint 2.

**For pre-launch (Sprints 3–7):** Stay on SQLite locally. Deploy Sprint 2 directly to Railway PostgreSQL. Do not run a SQLite→PostgreSQL interim production deployment.

---

## 3. Supabase Auth Layer Design

### JWT Flow

```
Browser (Next.js)
  │
  ├─ POST /auth/v1/token (Supabase SDK)
  │    └─ Returns: access_token (JWT), refresh_token
  │
  ├─ All API calls: Authorization: Bearer <access_token>
  │
FastAPI backend
  ├─ Middleware: extract Bearer token from header
  ├─ Verify JWT against Supabase JWT secret (HS256 or RS256)
  ├─ Extract sub claim → user_id (UUID)
  └─ Inject into request via Depends(get_current_user)
```

**`get_current_user` dependency (design, not code):**

```python
# backend/auth.py — to be created in Sprint 2
from fastapi import Depends, HTTPException, Header
import jwt  # PyJWT

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")  # from Supabase project settings

async def get_current_user(authorization: str = Header(...)) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"],
                             audience="authenticated")
        return payload["sub"]  # Supabase user UUID
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
```

All route handlers replace `user_id = 'user_1'` with `user_id: str = Depends(get_current_user)`.

### Session Strategy: Bearer Token (not Cookie)

Use **Bearer token** (Authorization header), not cookies, because:
- Next.js App Router makes `fetch()` calls from client components — cookie management across domain boundaries (Vercel → Railway) is messy
- Supabase JS SDK handles token refresh automatically in the browser
- No CSRF surface area with Bearer tokens

Supabase JS SDK stores tokens in `localStorage` by default. For a study app (not banking), this is acceptable. If Rahul later wants SSR with cookies, Supabase's `@supabase/ssr` package supports it — but this is a Sprint 6+ concern.

### Supabase Free Tier Limits [VERIFIED]

Source: supabase.com/pricing, fetched 2026-06-15.

| Limit | Free Tier | Pro Tier ($25/month) |
|---|---|---|
| Monthly Active Users | **50,000 MAU** | 100,000 MAU (then $0.00325/MAU) |
| Database storage | 500 MB | 8 GB included |
| Projects | 2 active | Unlimited |
| Row-Level Security | Yes | Yes |

**Implication:** The free tier handles 50,000 MAU — Nyaya Recall will not hit this before ₹25k/month revenue. Stay on Supabase free tier through all 8 sprints and beyond. Upgrade to Pro only if approaching 50k MAU or needing >500MB auth DB.

**[UNVERIFIED — needs check]:** Supabase free tier projects pause after 1 week of inactivity. For a public SaaS this is unacceptable. Confirm whether Railway-hosted backend's health check pings Supabase or whether Supabase project itself needs a keep-alive. Workaround: upgrade to Pro ($25/month) which removes the inactivity pause. This is the most likely reason to pay Supabase before hitting MAU limits.

### Auth Tables: Supabase Manages vs Our DB Manages

| Concern | Managed by | Table / Location |
|---|---|---|
| User identity, email, password hash | Supabase | `auth.users` (Supabase internal) |
| Google OAuth tokens | Supabase | `auth.identities` (Supabase internal) |
| Sessions / refresh tokens | Supabase | `auth.sessions` (Supabase internal) |
| User display name, exam type, target_date | Our PostgreSQL | `user_profiles` (new table, Sprint 2) |
| Subscription tier (free/pro) | Our PostgreSQL | `user_profiles.tier` column |
| Per-user prep config | Our PostgreSQL | `user_profiles` (replaces prep_config.json) |

**Our DB never stores passwords.** It stores only the `user_id` (Supabase UUID) as a foreign key reference.

### Rahul's Data Migration (approval-gated)

```sql
-- Run ONCE after Sprint 2 deploy, ONLY after Rahul approves
-- Migrates all user_1 data to Rahul's actual Supabase UUID

UPDATE quiz_sessions       SET user_id = '<rahul_supabase_uuid>' WHERE user_id = 'user_1';
UPDATE subtopic_scores     SET user_id = '<rahul_supabase_uuid>' WHERE user_id = 'user_1';
UPDATE sar_scores          SET user_id = '<rahul_supabase_uuid>' WHERE user_id = 'user_1';
UPDATE subject_attestations SET user_id = '<rahul_supabase_uuid>' WHERE user_id = 'user_1';
UPDATE study_plan_log      SET user_id = '<rahul_supabase_uuid>' WHERE user_id = 'user_1';
UPDATE session_user_notes  SET user_id = '<rahul_supabase_uuid>' WHERE user_id = 'user_1';
UPDATE question_notes      SET user_id = '<rahul_supabase_uuid>' WHERE user_id = 'user_1';
UPDATE content_feedback    SET user_id = '<rahul_supabase_uuid>' WHERE user_id = 'user_1';
UPDATE subtopic_dimension_scores SET user_id = '<rahul_supabase_uuid>' WHERE user_id = 'user_1';
```

**`session_answers` has no `user_id` column** — it joins through `quiz_sessions`. No migration needed there; existing session data is automatically associated with Rahul's sessions.

**`sar_scores` uses `user_id` as PRIMARY KEY** — the UPDATE will succeed since 'user_1' is the only row, but the constraint change from 'user_1' to a UUID violates the primary key if any other user row exists. Wrap in a transaction. Add a `UNIQUE(user_id)` constraint to the new PostgreSQL schema instead of PRIMARY KEY to allow multiple users with unique user_ids.

---

## 4. PostgreSQL Migration Design (Sprint 2)

### Schema Changes Required

Tables that need `user_id` FK and RLS, with specific issues flagged:

| Table | user_id column? | Issue | Action |
|---|---|---|---|
| `quiz_sessions` | Yes (`DEFAULT 'user_1'`) | OK | Add FK reference to `user_profiles(user_id)`, add index |
| `session_answers` | **No** | Inherited from quiz_sessions join | Add `user_id` column for RLS (denormalised for performance) |
| `subtopic_scores` | Yes, UNIQUE constraint includes it | OK | FK + RLS policy |
| `sar_scores` | Yes, is PRIMARY KEY | **Breaking for multi-user** | Change PK to `id SERIAL`, add `UNIQUE(user_id)` |
| `subject_attestations` | Yes | OK | FK + RLS |
| `study_plan_log` | Yes | OK | FK + RLS |
| `session_user_notes` | Yes, but session_id is PK | OK | FK + RLS |
| `subtopic_dimension_scores` | Yes, UNIQUE includes it | OK | FK + RLS |
| `question_notes` | Yes | OK | FK + RLS |
| `content_feedback` | Yes | OK | FK + RLS |
| `pyq_questions` | **No** | Shared content, no user_id needed | No change — this is global read-only data |
| `subtopic_difficulty` | **No** | Per-subtopic, not per-user | OK as global. If per-user tracking needed later, add user_id then |
| `session_summaries` | **No** | Joins through quiz_sessions | Add user_id for RLS |

**New table for Sprint 2:**

```sql
CREATE TABLE user_profiles (
    user_id       TEXT PRIMARY KEY,           -- Supabase UUID
    display_name  TEXT,
    email         TEXT,
    exam_type     TEXT DEFAULT 'upsc_prelims',
    target_date   DATE,
    daily_hours   REAL DEFAULT 2.0,
    tier          TEXT DEFAULT 'free',        -- 'free' | 'pro'
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

**New table for Sprint 4 (Pro gating):**

```sql
CREATE TABLE graded_answer_credits (
    user_id       TEXT REFERENCES user_profiles(user_id),
    credits       INTEGER DEFAULT 0,          -- 1 credit = 1 graded answer
    purchased_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id)
);
```

### RLS Policy Pattern

```sql
-- Example for quiz_sessions
ALTER TABLE quiz_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_isolation ON quiz_sessions
    USING (user_id = current_setting('app.user_id'));
```

FastAPI sets `SET LOCAL app.user_id = '<uuid>'` at the start of each request within a transaction. This is the standard pattern for PostgreSQL RLS with a backend service.

**Alternative — skip RLS, do application-layer filtering:** For a team of 1 developer with 1000 max users, application-layer `WHERE user_id = ?` on every query is simpler and debuggable. RLS adds complexity and makes debugging slow. **Recommendation: use application-layer filtering in Sprint 2, add RLS in Sprint 7 (analytics phase) when you have time to test it properly.**

### SQLite → PostgreSQL Data Migration Strategy

1. **Dump SQLite to CSV per table:** `sqlite3 data/upsc.db .dump` — produces SQL inserts
2. **Transform `user_1` → Rahul's UUID** in the dump file (sed or Python script)
3. **Replay into PostgreSQL** via `psql` or `asyncpg` bulk insert
4. **Verify row counts** match before deleting SQLite

Estimated time: **30–45 minutes** for Rahul's existing data. The heaviest table is `session_answers` — likely <50k rows after months of solo use.

### Connection Pooling

**Use Railway's built-in PostgreSQL connection string directly** for Sprint 2–7. Do not add pgBouncer yet.

Railway PostgreSQL supports ~100 concurrent connections by default. FastAPI + asyncpg (or psycopg2) with a pool size of 10 handles 100 concurrent HTTP requests comfortably — each request holds a connection for <50ms for typical queries.

**Add pgBouncer only when:** connection count consistently exceeds 80/100 (visible in Railway metrics dashboard). This will not happen before 500+ DAU. Until then, pgBouncer adds operational overhead with no benefit.

**[UNVERIFIED — needs check]:** Railway's managed PostgreSQL max connection limit. Default PostgreSQL `max_connections=100` but Railway may set a higher or lower cap depending on the plan. Check Railway dashboard after provisioning.

---

## 5. File-Based State → DB Migration

### Current flat files and their fates

| File | Contents | When to migrate | Target schema |
|---|---|---|---|
| `data/prep_config.json` | `{total_days, daily_hours, start_date, target_date}` | **Sprint 2** (multi-tenancy requires it) | `user_profiles.target_date`, `user_profiles.daily_hours` columns |
| `data/prep_profile.json` | Per-subject readiness scores, coverage maps | **Sprint 2** | `subtopic_scores` table (already exists, just needs user_id routing) |
| `data/prep_profile_csat.json` | CSAT-specific readiness | **Sprint 2** | Same `subtopic_scores` table, `subject_id = 'csat'` |
| `data/study_plan.json` | Today's + tomorrow's sessions | **Sprint 2** | `study_plan_log` table (already exists) |
| `cache/explanations.json` | SHA256 → explanation text | **Sprint 3** (before PYQ explanations launch) | `explanations_cache(question_hash TEXT PK, explanation TEXT, model TEXT, created_at)` — shared across all users |

### Per-User Namespacing Design

- `prep_config.json` fields → `user_profiles` table, one row per user. FastAPI reads from DB, not filesystem.
- `prep_profile.json` → Already in `subtopic_scores` per `(user_id, subject_id, subtopic_id)`. The file is a cache/computed view — batch_analyse.py populates it. In multi-user, batch_analyse.py runs per-user on a schedule.
- `study_plan.json` → `study_plan_log` already has `user_id`. plan_generator.py needs `user_id` parameter.
- `cache/explanations.json` → Shared PostgreSQL table. Question content is the same for all users — the explanation is not user-specific. One shared cache = ~95% cache hit rate from day 1 for new users.

### Migration of Flat Files for Existing Rahul Data

1. Read `prep_config.json` → INSERT into `user_profiles` row for Rahul's UUID
2. `prep_profile.json` readiness scores are already in `subtopic_scores` table (batch_analyse.py writes both). No migration needed beyond user_id update above.
3. `cache/explanations.json` → bulk INSERT into `explanations_cache` table

---

## 6. Cost Model at Scale

### Verified Pricing (fetched 2026-06-15)

**Railway:**
- RAM: $10/GB/month
- CPU: $20/vCPU/month
- Volume storage: $0.15/GB/month
- Egress: $0.05/GB
- Hobby plan: $5/month (includes $5 usage credit)
- Pro plan: $20/month/seat (includes $20 usage credit)

**Supabase:**
- Free: 50,000 MAU, 500 MB DB, 2 projects
- Pro: $25/month, 100,000 MAU, 8 GB DB

**Anthropic (verified from docs, 2026-06-15):**
- Claude Haiku 4.5: $1.00/MTok input, $5.00/MTok output
- Claude Sonnet 4.6: $3.00/MTok input, $15.00/MTok output

### Workload Assumptions

| User scenario | Session behaviour | AI call profile |
|---|---|---|
| 1 quiz session | 20 questions, ~5 answered incorrectly | 0 Haiku (questions from DB), ~2000 tokens Sonnet if explanations viewed |
| 1 graded answer (Pro) | 1 descriptive question | ~1500 tokens input + ~600 tokens output Sonnet |
| Batch analysis (nightly) | Per-user, ~50 subtopics | ~3000 tokens Haiku per user |

### Monthly Cost Tables

**100 Active Users (launch baseline, ~₹5–8k/month revenue target)**

| Component | Config | Monthly Cost |
|---|---|---|
| Railway — FastAPI service | 0.5 GB RAM, 0.25 vCPU | ~$6.25 |
| Railway — PostgreSQL | 1 GB RAM, 0.5 vCPU, 5 GB volume | ~$11.75 |
| Railway Pro plan seat | Base subscription | $20.00 |
| Supabase Auth | Free tier (well under 50k MAU) | $0 |
| Anthropic — Haiku | 100 users × 3000 tokens/month | ~$0.03 |
| Anthropic — Sonnet | 100 users × 2 explanations × 2600 tokens avg | ~$0.78 |
| Anthropic — Graded answers (assume 20% pro) | 20 users × 5 answers × 2100 tokens | ~$0.47 |
| Vercel (Next.js) | Free tier (Hobby) | $0 |
| **Total** | | **~$39/month (~₹3,250)** |

Revenue at 100 users, 20 Pro (₹499/month or ₹4.50/answer): ~₹8,000–10,000/month. **Healthy margin.**

---

**500 Active Users (₹20–25k/month revenue target)**

| Component | Config | Monthly Cost |
|---|---|---|
| Railway — FastAPI service | 1 GB RAM, 0.5 vCPU | ~$12.50 |
| Railway — PostgreSQL | 2 GB RAM, 1 vCPU, 20 GB volume | ~$23.00 |
| Railway Pro plan | Base subscription | $20.00 |
| Supabase Auth | Free tier | $0 |
| Anthropic — Haiku | 500 users × 3000 tokens | ~$0.15 |
| Anthropic — Sonnet | 500 users × avg 4 explanation views × 2600 tokens | ~$7.80 |
| Anthropic — Graded answers (25% pro) | 125 users × 8 answers × 2100 tokens | ~$7.88 |
| Vercel | Free tier | $0 |
| **Total** | | **~$71/month (~₹5,920)** |

Revenue at 500 users, 125 Pro: ~₹25,000–35,000/month. **Strong margin — ~83% gross.**

---

**1000 Active Users (12-month target)**

| Component | Config | Monthly Cost |
|---|---|---|
| Railway — FastAPI service | 2 GB RAM, 1 vCPU | ~$25.00 |
| Railway — PostgreSQL | 4 GB RAM, 2 vCPU, 50 GB volume | ~$50.00 |
| Railway Pro plan | Base subscription | $20.00 |
| Supabase Auth | Free tier (still under 50k MAU) | $0 |
| Anthropic — Haiku | 1000 users × 3000 tokens | ~$0.30 |
| Anthropic — Sonnet | 1000 users × avg 5 explanation views × 2600 tokens | ~$19.50 |
| Anthropic — Graded answers (30% pro) | 300 users × 10 answers × 2100 tokens | ~$28.35 |
| Vercel | Pro ($20/month if bandwidth high) | ~$20.00 |
| **Total** | | **~$163/month (~₹13,600)** |

Revenue at 1000 users, 300 Pro at ₹499/month: ~₹60,000–75,000/month. **85%+ gross margin.**

**Key insight:** Anthropic API cost scales roughly linearly with Pro users using graded answers. The biggest cost lever is explanation caching — the shared `explanations_cache` table means the same PYQ explanation is generated once and served to all users for free thereafter.

---

## 7. Long-Term Architecture (12 Months)

### At Sprint 8 (launch, ~Sep 2026)

```
[Users] → Vercel (Next.js) → Railway (FastAPI + PostgreSQL) → Supabase (Auth)
                                    ↓
                             ChromaDB (Railway volume)
                             Anthropic API (per-request)
```

Single Railway project, two services (FastAPI + PostgreSQL), one Vercel deployment. This is the entire architecture. No Kubernetes, no Redis, no message queues.

### Between Sprint 8 and ₹25k/month Revenue

These changes happen in response to scale, not ahead of it:

| Trigger | Change |
|---|---|
| Cache hit rate for explanations < 80% | Pre-generate explanations for all PYQ questions via batch API (50% cheaper than synchronous). One-time job. |
| Response time > 2s on explanation endpoint | Add in-memory LRU cache in FastAPI (Python `functools.lru_cache` or `cachetools`). No Redis needed at this scale. |
| Nightly batch_analyse.py takes > 10 min | Move to Railway cron jobs (native feature). Currently it's a CLI script — needs a small wrapper. |
| Multiple Railway service restarts disrupt users | Add Railway's zero-downtime deploy (health check config). Already supported. |
| First DPDP Act compliance question | Add data export endpoint and account deletion. Required by Indian law if handling personal data at scale. [UNVERIFIED — consult legal; DPDP Act enforcement timeline unclear as of mid-2026] |
| 500+ users, explanation cache > 500 MB | Migrate `explanations_cache` to a separate Railway PostgreSQL volume or use Supabase Storage for blob storage |
| Revenue > ₹50k/month | Hire part-time content curator; replace some Anthropic calls with curated explanations (lower cost, higher quality) |

### What does NOT change before ₹1 lakh/month revenue

- Railway stays (not AWS/GCP — not worth the operational overhead for a solo developer)
- FastAPI stays (not switching to Django/Node.js)
- Supabase Auth stays (not building custom auth)
- PostgreSQL on Railway stays (not moving to RDS/Supabase DB)
- Vercel stays (not self-hosting Next.js)

---

## 8. Top 3 Architectural Risks

### RISK-01 — SQLite WAL routes bypass the WAL helper [HIGH PROBABILITY, HIGH IMPACT]

**The problem:** `backend/db.py` defines `get_conn()` with WAL pragma, but routes (`quiz.py`, `sessions.py`, etc.) call `sqlite3.connect(DB_PATH)` directly. The `enable_wal()` call at startup sets WAL for the file, but any direct `sqlite3.connect()` that does not also execute `PRAGMA journal_mode=WAL` gets default journal mode if the WAL file was not persisted. Under concurrent writes, this is silent data corruption or `SQLITE_BUSY` errors.

**What could go wrong:** Two users submit quiz answers simultaneously. One route uses `get_conn()` (WAL), another calls `sqlite3.connect()` directly (rollback journal). The WAL reader sees inconsistent state. Low probability of data loss, but high probability of `database is locked` 500 errors on first public traffic spike.

**Mitigation:** Audit all 10 route files for direct `sqlite3.connect()` calls before Sprint 2 deploy. Replace all with `from db import get_conn`. This is a Sprint 2 prerequisite, not a nice-to-have.

---

### RISK-02 — ChromaDB on Railway volume is a single point of failure [MEDIUM PROBABILITY, HIGH IMPACT]

**The problem:** ChromaDB (`vector_store/`) is a local directory. On Railway, this means a persistent volume attached to the FastAPI service container. Railway volumes are durable, but:
- If the service is scaled to >1 replica, both replicas cannot share the same volume (Railway volumes are single-writer)
- Volume snapshots are not automatic on Railway free/hobby tier [UNVERIFIED — check Railway volume backup policy]
- If the volume is corrupted or the service is moved to a new region, re-ingestion takes hours

**What could go wrong:** Railway redeploys the FastAPI service to a new instance (e.g., during plan upgrade or region change). If the volume is not re-attached correctly, the vector store is empty. All notes synthesis endpoints return empty results. Users see no study notes — the core value proposition breaks.

**Mitigation:**
1. For Sprint 2–5: keep ChromaDB on Railway volume, but ensure `ingest.py` and the vector store can be fully rebuilt from source documents in <2 hours
2. For Sprint 6+: migrate ChromaDB to a managed vector store (Pinecone free tier or Turso) to eliminate the single-volume dependency. This is not urgent until launch.
3. Immediate action: add a `/health/chroma` endpoint that verifies ChromaDB is accessible and has expected collection counts. Wire to Railway health check so the service restarts if ChromaDB is unreachable.

---

### RISK-03 — The ₹4.50/graded-answer monetisation model has no payment infrastructure designed [HIGH PROBABILITY IF IGNORED]

**The problem:** The business plan depends on ₹4.50 per graded answer. But as of Sprint 8 design, there is no:
- Payment gateway integration (Razorpay, Stripe India, or similar)
- Credit purchase flow (how does a user buy 10 credits?)
- Credit deduction on answer grading (transactional — must be atomic with the grading call)
- Refund handling for failed gradings

This is not an architecture risk in the technical sense, but it is the single decision that could force a Sprint 8 rewrite if the payment model is wrong. Razorpay's India integration typically takes 3–7 days for KYC approval. If not started before Sprint 7, launch is blocked.

**What could go wrong:** Sprint 8 is ready but payment gateway KYC is pending. Launch is delayed 2 weeks while Razorpay processes documents. Revenue target for Jul 31 is missed.

**Mitigation:**
1. Start Razorpay KYC during Sprint 5 or Sprint 6 (not Sprint 8). Account approval is independent of code.
2. Design the credit system in Sprint 4 (when Pro gating is built) — even if payment gateway is not live, the credit table and deduction logic should be built then.
3. For soft launch (Sprint 8): accept manual payments via UPI + manual credit top-up by Rahul. This removes the payment gateway dependency from the critical path and allows launch on schedule.

---

## Appendix: Assumptions Flagged for Verification

| ID | Assumption | How to verify |
|---|---|---|
| [UNVERIFIED-01] | Railway PostgreSQL allows `CREATE DATABASE` on managed instances | Create a Railway project, provision PostgreSQL, check psql permissions |
| [UNVERIFIED-02] | Supabase free tier projects pause after 1 week inactivity | Check Supabase docs: platform.supabase.com/docs/guides/platform/going-into-prod |
| [UNVERIFIED-03] | Railway managed PostgreSQL default `max_connections` | Check Railway dashboard after PostgreSQL provisioning; run `SHOW max_connections;` |
| [UNVERIFIED-04] | Railway volume backup policy (automatic snapshots?) | Check Railway docs: docs.railway.com/reference/volumes |
| [UNVERIFIED-05] | DPDP Act enforcement timeline for small SaaS | Consult meity.gov.in or a legal professional before crossing 500 Indian users |
