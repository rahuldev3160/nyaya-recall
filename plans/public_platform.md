# Public Platform Plan — Devthorium MCQ Testing Engine
_Created: 2026-05-30 | Last updated: 2026-05-30_

## Vision

**One-line positioning:** "The practice layer for UPSC aspirants who already have content. We diagnose your gaps and drill them until they're gone."

A public, multi-user MCQ testing platform. No teaching, no notes, no videos. Users come to be tested, get precise weakness analytics, and are told exactly which subtopic to go study. They learn elsewhere and return to test again.

**Two-platform architecture (long-term):**
- MCQ Engine (this) → UPSC Prelims first, then BPSC/UPPSC/MPSC/SSC
- Descriptive Engine (Descriptive-exams project) → UPSC Mains, IES, RBI Grade B

---

## Market Context

| Signal | Data |
|--------|------|
| Active UPSC aspirants | 15–25 lakh |
| Prelims test series market | ₹160–750 crore |
| Closest competitor | SprintUPSC (₹3,999, static bank, no AI generation) |
| Window before incumbents copy | 12–24 months |
| All-in infra + API cost at 10k MAU | ~₹18,500/month (~$220) |

**Key gap:** No platform does cumulative session-to-session weakness tracking that drives question routing. All analytics are post-test dashboards, not adaptive engines.

---

## Pricing Model

| Tier | Price | Includes |
|------|-------|---------|
| Free | ₹0 | All PYQs (practice), correct answer revealed, subject-level dashboard, 3 simulations/month |
| Pro | ₹3,999/year or ₹499/month | Full concept explanations per question, adaptive engine, AI-generated questions, unlimited simulations, detailed weakness diagnosis, "study next" signal |

**Key upgrade hook:** Free users practice PYQs and see correct answers. The full explanation card (concept + wrong option analysis + memory hook) is Pro-only. User hits a confusing question, wants to understand WHY — that's the upgrade moment.

Break-even: ~15 Pro subscribers cover all infra costs. At 1,000 Pro: ₹40L/year revenue.

---

## Technical Architecture

### Stack
| Layer | Choice | Why |
|-------|--------|-----|
| Auth | Supabase magic link + Google OAuth | Zero backend code, managed |
| Database | Supabase (PostgreSQL) | SQLite migration is ~3 hours of syntax changes |
| Backend | Railway (FastAPI) | Push-to-deploy, no devops |
| Frontend | Vercel (Next.js) | Native support, free tier |
| ChromaDB | Railway volume initially → Pinecone at scale | Only for background generation |
| Background jobs | Railway Cron / Inngest | Question pool refresh |

### Question Bank Architecture

**Two-table design — clean separation:**

| Table | Contents | Shown as |
|-------|----------|---------|
| `pyq_questions` | Civil Services GS Prelims 2013–2025 only | "PYQ Browser" (named feature) |
| `question_bank` | CDS/NDA/CAPF/CISF PYQs + AI-generated gap-fill | Powers diagnostics, simulations, adaptive engine |

**Core insight:** Real PYQs from other UPSC exams (CDS, NDA, CAPF) provide ~6,500–7,000 questions with official answer keys at zero cost. AI generation only fills remaining gaps.

**Serving algorithm (4 phases, pure SQL):**
1. Civil Services PYQs user hasn't seen (pyq_questions), year DESC
2. question_bank (CDS/NDA/CAPF/AI) user hasn't seen, lowest times_served first
3. Questions user got wrong (spaced repetition)
4. Generate new via AI (only triggers when subtopic exhausted, async background job)

**Question bank sources:**
- CDS GK papers (10 years × 2/year × 120q) = **~2,400 questions**
- NDA GAT GK sections (10 years × 2/year × ~75 GK q) = **~1,500 questions**
- CAPF Paper I (10 years × 125q) = **~1,250 questions**
- CISF AC GK (10 years × 100q) = **~1,000 questions**
- AI gap-fill for underrepresented subtopics = **~1,000–2,000 questions**
- **Total: ~7,000–8,000 questions**
- All UPSC exams have official answer keys on upsc.gov.in — zero answer reliability risk

**AI gap-fill cost (one-time, Haiku Batch):**
- Only for subtopics with < 10 questions in the bank
- Estimated: ~₹50–100 total

**PYQ explanations (Pro content):**
- Civil Services PYQs 2013–2025 (~1,300 questions after data foundation)
- One-time Haiku Batch generation: **~₹85 ($1.00)**
- See: `plans/pyq_explanations.md`

Full question bank spec: `plans/multi_exam_bank.md`

### Cost at Scale

| MAU | Monthly infra | Monthly Anthropic | Total/month |
|-----|--------------|-------------------|-------------|
| 100 | ~$0 | ~$2 | ~$2 |
| 1,000 | ~$32 | ~$15 | ~$47 |
| 10,000 | ~$90 | ~$120 | ~$210 |

---

## Analytics & Weakness Engine

**Five layers (all computed in Python, zero LLM calls):**
1. Subject Readiness Dashboard — existing batch_analyse.py formula, multi-user
2. Topic Gap Map — heatmap of topics by coverage + risk level
3. Weak Subtopic Rankings — scored by (PYQ frequency × score gap)
4. Accuracy Trends — daily accuracy per subject, last 30 days
5. Time-per-Question Analysis — flags overconfidence (< 15s wrong) and knowledge gaps (> 90s)

**"Study Next" signal output:**
> "Go study Directive Principles of State Policy. It appeared 14 times in UPSC Prelims (2018–2024). Your current score: 31%. Highest ROI gap in your profile."

---

## Simulation Mode

- 100 questions, 120 minutes, all 9 subjects, negative marking (−⅔)
- Pre-fetched as single payload — zero API calls during simulation
- UPSC-accurate subject distribution (Polity 18, History 20, Environment 15, Economy 12...)
- Post-sim: subject breakdown, time analysis, improvement signals
- Percentile: shown once 200+ simulations logged across users

---

## Build Phases

### Phase 0: PYQ Data Foundation ⚠️ MUST DO FIRST
_Spec: `plans/pyq_data_foundation.md`_

**What:** Get Civil Services GS Prelims PYQs (2013–2025) into the DB with official UPSC correct answers. Scope is 2013 onwards — older years (2009–2012) are not needed for the public PYQ Browser.

**Tasks:**
- [ ] Source official UPSC final answer keys for 2013–2025 (Rahul downloads from upsc.gov.in)
- [ ] ALTER TABLE pyq_questions: add answer_source, answer_disputed, dispute_note, q_number (**approval gate**)
- [ ] Build `scripts/import_answer_keys.py` — CSV → DB answer update
- [ ] Fix 2014 duplicates (132 rows → ~100) (**approval gate for DELETE**)
- [ ] Re-ingest gap years (2015–2024 all under 100 questions)
- [ ] Run fix_year_zero.py (30 questions from Microthemes compilation)
- [ ] Run audit_pyq_completeness.py — validate 2013–2025 at expected count

**Exit criteria:**
- Every year 2013–2025 has ≥95 questions
- Every question has answer_source = 'official' or 'cancelled'
- Zero answer_source = 'ai_inferred' remaining

---

### Phase 1: PYQ Browser
_Spec: `plans/pyq_browser.md`_

**What:** Year → Subject → Topic → Subtopic navigation. Structured PYQ practice (not simulation).

**Tasks:**
- [ ] Create `pyq_attempts` table (new, no approval needed)
- [ ] Build `backend/routes/pyq.py` with all browse + attempt endpoints
- [ ] Build `/pyq` frontend page (year grid → subject cards → topic accordion)
- [ ] Build `PYQQuizRunner` component (reuses quiz runner, calls /pyq/attempt)
- [ ] Add PYQ nav link

**Exit criteria:**
- User can navigate to any year/subject/topic and attempt questions
- Attempts are recorded in pyq_attempts table
- Progress shown in year grid (% attempted, % correct)

---

### Phase 2: PYQ Explanations (Pro Content)
_Spec: `plans/pyq_explanations.md`_

**What:** Pre-generate concept explanations for all PYQs. Gate behind Pro tier.

**Tasks:**
- [ ] Create `prompts/pyq_explanation.txt`
- [ ] Build `scripts/generate_pyq_explanations.py` (Haiku Batch + JSONL cache)
- [ ] Run generation — ~₹81 one-time cost, ~3 hours batch processing
- [ ] Create `question_explanations` table
- [ ] Add GET /pyq/explanation/{id} endpoint
- [ ] Build `ExplanationCard.tsx` component
- [ ] Wire into PYQ Browser (shows after answer reveal)
- [ ] Free/Pro gating (blurred card + upgrade CTA for Free)

**Exit criteria:**
- Every PYQ with official answer has a generated explanation
- Explanation card shows correctly after answer reveal
- Free users see blurred/locked card with upgrade prompt

---

### Phase 3: Auth + Multi-tenancy
_Required before public launch_

**Tasks:**
- [ ] Supabase project setup (PostgreSQL + Auth)
- [ ] `backend/auth.py`: Supabase JWT verification middleware
- [ ] Replace `user_id='user_1'` with authenticated user UUID (query-level change across all routes)
- [ ] `users` table (Supabase handles auth, we store preferences)
- [ ] Onboarding flow: exam target, study hours/day
- [ ] Magic link + Google OAuth frontend pages
- [ ] SQLite → PostgreSQL migration (~3 hours syntax changes)

---

### Phase 4: Question Bank Serving
_Enables adaptive engine with real PYQs from other UPSC exams + AI gap-fill_
_Spec: `plans/multi_exam_bank.md`_

**Tasks:**
- [ ] `question_bank` + `user_question_history` tables
- [ ] Migrate existing ~860 AI-generated questions to question_bank
- [ ] Ingest CDS GK papers (10 years) → question_bank (~2,400 questions)
- [ ] Ingest NDA GAT GK sections (10 years, filter Maths) → question_bank (~1,500 questions)
- [ ] Ingest CAPF + CISF GK papers (10 years each) → question_bank (~2,250 questions)
- [ ] Run retag_pyq_subtopics.py on all new rows
- [ ] AI gap-fill for subtopics with < 10 questions via Haiku Batch (~₹75)
- [ ] Rewrite `POST /quiz/generate` to use 4-phase serving algorithm (zero API calls at runtime)
- [ ] Background job: detect exhausted subtopics, trigger new batch generation async

---

### Phase 5: Analytics + Weakness Engine
_The core value-add over competitors_

**Tasks:**
- [ ] `/analytics/weakness-report` — subtopic gap analysis
- [ ] `/analytics/study-next` — highest ROI recommendation
- [ ] Multi-user batch_analyse adaptation (runs per user, PostgreSQL writes)
- [ ] Simulation mode with negative marking
- [ ] Post-simulation analytics page

---

### Phase 6: Deploy + Launch
_One day_

**Tasks:**
- [ ] Railway FastAPI deployment + env vars
- [ ] Vercel Next.js deployment
- [ ] Domain setup
- [ ] Auth pages (magic link flow)
- [ ] Smoke test → flip DNS
- [ ] Reddit r/UPSC launch post (analytics screenshots, before/after diagnostic)
- [ ] Telegram UPSC groups posts

**Total build time estimate: ~13 days solo + Claude Code**
- Phase 0: 1 day build + 2–4 hours Rahul data sourcing
- Phase 1: 1 day
- Phase 2: 1 day
- Phase 3: 2 days
- Phase 4: 2 days
- Phase 5: 3 days
- Phase 6: 1 day

---

## PYQ Data Requirements (must fix before Phase 1)

See full detail in `plans/pyq_data_foundation.md`.

1. **Missing years 2009–2013** — source year-wise PDFs from upsc.gov.in
2. **Incomplete years 2015–2024** — re-ingest with better quality PDFs
3. **2014 duplication** — 132 rows vs expected ~100
4. **518/1,081 questions have no correct_answer** — all existing answers are AI-inferred
5. **Must import official UPSC final answer keys for all years** — this is a launch blocker
6. **Disputed answers** — tag questions where UPSC's answer was challenged (court cases, objection-period revisions)
7. **No dimension_id** — add later (post-Phase 2), not a launch blocker

---

## Go-to-Market (Solo, Zero Budget)

1. Reddit r/UPSC (800k+ members) — post analytics screenshots, show before/after diagnostic
2. Telegram UPSC groups (50k–500k members each)
3. Free PYQ tier as distribution — every free user is a potential paid user + referrer
4. No paid ads until 100+ paid users validate product-market fit

---

## Key Files for Implementation

- `backend/routes/quiz.py` — rewrite generation path to serve from question_bank
- `backend/routes/pyq.py` — new: all PYQ browse + attempt + explanation endpoints
- `scripts/score_engine.py` — add user_id param, write to user_question_history
- `scripts/batch_analyse.py` — adapt for PostgreSQL multi-user writes
- `scripts/generate_pyq_explanations.py` — new: one-time Haiku Batch explanation generation
- `backend/server.py` — auth middleware, CORS restriction
- `scripts/priority_scorer.py` — carries over unchanged
