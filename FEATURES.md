# FEATURES.md — Master Tracker

> Single source of truth for every feature: done, in progress, planned, and queued.
> Updated after every dev session. Detailed specs live in `plans/`.

---

## How to read this

| Symbol | Meaning |
|--------|---------|
| ✅ | Shipped and working |
| 🔵 | Planned — spec written, ready to build |
| 📋 | Queued — identified, not yet specced |
| 🐛 | Known bug / open problem |
| ⛔ | Blocked |

**Priority:** P0 = exam-blocking / P1 = high impact / P2 = medium / P3 = nice-to-have

---

## ✅ Shipped

| Feature | Priority | What it does | Notes |
|---------|----------|--------------|-------|
| Core quiz engine | P0 | Generates MCQs via Claude Sonnet from ChromaDB chunks + PYQ context | `backend/routes/quiz.py` |
| Score engine | P0 | Records answers, computes session scores, zero API calls | `scripts/score_engine.py` |
| Subtopic scores | P0 | Tracks per-subtopic accuracy with running average | `subtopic_scores` table |
| Batch analysis | P0 | End-of-day Claude call — weighted readiness + insights | `scripts/batch_analyse.py` |
| Plan generator | P0 | Generates tomorrow's sessions from readiness profile | `scripts/plan_generator.py` |
| Difficulty engine | P1 | Auto-adjusts question difficulty per subtopic after 3+ attempts | `scripts/difficulty_engine.py` |
| Self-attestation (SAR) | P1 | User claims subject confidence; system validates and blends claim + evidence | `backend/routes/attestation.py` |
| Dive deeper (expand) | P1 | Per-question concept deep-dive via Haiku; click recorded as learning signal | `backend/routes/sessions.py` |
| Tracker page | P1 | Subject readiness bars, gaps list, subtopic drill-down | `web/src/app/tracker/` |
| Setup / config page | P1 | Set total days, daily hours, start date | `web/src/app/setup/` |
| CSAT system | P2 | Separate diagnostic + profile for Paper II | `backend/routes/csat.py` — exists, untested |
| **Weighted PYQ readiness scoring** | P0 | `subject_readiness = Σ(score×weight)/Σ(all_weights)` — untested subtopics = 0, Claude never sets numbers | Fixed May 11 |
| **Mobile Tailscale access** | P0 | Phone works via Tailscale from any network using production build | Fixed May 11 |
| **Multi-subtopic quiz allocation** | P1 | 10-question diagnostic now covers 10 different untested subtopics, 2 chunks each, priority-ordered | Fixed May 11 |
| **Plan generator subtopic awareness** | P1 | Planner receives full untested subtopic list sorted by PYQ weight; 8 scheduling rules | Fixed May 11 |
| **Subtopic tracking fix** | P0 | Polity/economy answers now correctly tagged with subtopic_id; historical data repaired | Fixed May 11 |
| **SQL NULL handling** | P0 | `WHERE col IS ?` instead of `=` for nullable columns; `topic_id NOT NULL` constraint removed | Fixed May 11 |
| **Subject alias** | P0 | `history` → `history_amac` mapping in scoring and quiz generation | Fixed May 11 |
| **Skip button in quiz UI** | P1 | Skip → button per question; skipped answers sent to backend with `skipped: true`; correct answer shown; score % calculated over attempted questions only | Fixed May 11 |
| **Notes deep-links + selection explain** | P1 | Vector-built notes include per-excerpt *Open full source* links to `/library/file`; “Explain selected text” in Key Concepts calls Haiku on demand (`expand_notes_selection.txt`, `POST /sessions/expand-notes-selection`) | Shipped May 12 |
| **Parallel session notes + plan signals** | P1 | “My notes” drawer on Session page (starts closed); confusion / mnemonic / still_weak; debounced `PUT /sessions/{id}/user-notes`; `session_user_notes` table; planner prompt includes `{{user_notes_signals}}` | Shipped May 12 |
| **Per-question time capture** | P1 | `time_taken_sec` in `session_answers` now populated from a React timer; resets on each question; feeds difficulty engine and metacognition analysis | Shipped May 12 |
| **PYQ subtopic ID normalisation** | P1 | Subject-scoped token-overlap fuzzy matching in `priority_scorer.py` maps PYQ free-text descriptors → canonical syllabus IDs; 139 subtopics now have real varied weights (was 0). `retag_pyq_subtopics.py` written for full coverage (~$0.05 one-time) | Shipped May 12 |
| **FEATURE-028: Topic-level hierarchical coverage** | P1 | topic_id canonical plumbing (score_engine + quiz.py); `_compute_topic_coverage()` in batch_analyse writes topics[] to prep_profile; plan_generator topic-balanced scheduling + Rule 9; Tracker accordion + Strategy topic counts | Shipped May 16 (PRs #17–#21) |
| **FEATURE-027: Dimension-aware subtopic coverage (all phases)** | P1 | 205 subtopics × 4–8 testable dimensions in syllabus.json; quiz labels dimension_id per question; session_answers stores dimension_id; subtopic_dimension_scores table tracks per-dimension accuracy; batch_analyse uses dimension-weighted readiness with fallback to subtopic scores | Shipped May 16 (PRs #22–28) |
| **Timed mode enforcement** | P1 | Live countdown in Timed Quiz mode; auto-close on expiry submitting all unreached questions as skipped; server-side expiry guard in sessions.py (409 on stale submit, auto-close on get_session) | Shipped May 16 (PR #29) |
| **Open-ended quiz mode ("Open Practice")** | P1 | No upfront count — 10-question lazy-load buffer, +8 more when <2 remain, Save & Close after each revealed answer; UX rename: Practice Set / Timed Quiz / Open Practice | Shipped May 16 (PR #29) |
| **ChromaDB coverage audit** | P1 | Ran `check_chroma_coverage.py` — 11,146 chunks, all 9 GS subjects healthy. CSAT excluded (separate system). No re-ingestion needed. | Resolved May 16 |
| **Session summaries backfill** | P2 | Ran `scripts/backfill_session_summaries.py` — 17 historical sessions processed. All had neutral-zone accuracy (45–75%), correctly producing `weak=[]` and `strong=[]`. `get_persistently_weak_subtopics()` in batch_analyse.py is now unblocked for future sessions. | Shipped May 16 (PR #7) |
| **Real-time feedback + prompt training (ISSUE-017)** | P1 | Per-question notes reset/autosave; `content_feedback` + `question_notes` tables; `ContentFeedback` 2×2 verdict UI on session + diagnostic + notes sections; `apply_feedback.py` prompt improvement pipeline (Haiku, manual); `batch_analyse.py` reminder at 20+ items. | Shipped May 17 (PRs #33, #34) |
| **Multi-subtopic merged sessions** | P1 | Planner editor: select up to 4 subtopics per session (topic-grouped, PYQ-weight-proportional Q allocation). Notes gain "Cross-Subtopic Linkages" section when >1 subtopic. `quiz_session_subtopics` table stores full list. | Shipped May 17 (PR #35) |
| **Exam simulation mode** | P1 | `/exam-sim` page: subject→topic→subtopic tree selector, configurable Q count (1–100) + duration. Timed quiz runner. Results screen with per-subject + per-topic accuracy breakdown. | Shipped May 17 (PR #35) |
| **Exam sim score write-back + scheduling bias fixes** | P0 | Exam sim questions now get subject_id/topic_id overridden from authoritative allocation map; SHA256 question_hash generated server-side; empty subject_id guard in score_engine; needs_retest concept (< 3 attempts) in plan_generator; 2-session/subject daily cap; k=8 chunk scaling; batch_analyse max_tokens 8192 + topics[] stripped | Shipped May 17 (PR #37) |
| **System audit phase 1 — correctness fixes** | P0 | C-01: exam sim now injects CA chunks + dimensions; C-02: single-subtopic chunk k scales with num_questions; C-05: close_session wrapped in BEGIN IMMEDIATE/COMMIT/ROLLBACK; H-05: session_answers UNIQUE(session_id, question_hash) + INSERT OR IGNORE; H-06: batch_analyse max_tokens 16000 + extended-output beta; H-07: plan_generator freshness warning at 12h; H-08: plan_generator max_tokens 8192 + extended-output beta; M-09: dashboard shows last-synced staleness indicator | Shipped May 17 (branch: fix/system-audit-phase1) |
| **Sprint 0 — 3 critical launch blockers** | P0 | C7: hardcoded `EXAM_DATE(2026-05-20)` in plan.py → `_get_exam_date()` reading `target_date` from prep_config.json; C6: `a["concept_expanded"]` KeyError on fresh DB → `.get()`; C2: SQLite WAL mode missing → `backend/db.py` with `get_conn()` + `enable_wal()` at startup | Shipped Jun 15, 2026 (PR #42) |
| **Sprint 2 Cluster D — JSON namespacing + auth stubs** | P0 | `prep_profile.json`, `study_plan.json`, `prep_config.json` moved to `data/profiles/{user_id}/`; legacy auto-migration for `user_1`; `user_profiles` table; `AuthGuard.tsx` (Supabase-aware, skips if not configured); PostgreSQL DDL skeleton in `scripts/migrate_to_postgres.py` | Shipped Jun 15, 2026 (PR #44) |
| **Sprint 3 — PYQ Browser** | P1 | Year → Subject → Topic drill-down; `pyq_attempts` table; 6 backend endpoints; `YearGrid`, `SubjectCards`, `TopicAccordion`, `PYQQuizRunner` components; one-by-one answer reveal; auto-resume from first unattempted; graceful fallback for missing `answer_source`/`answer_disputed` columns | Shipped Jun 15, 2026 (PR #45) |

---

## 🔵 Planned — spec written, ready to build

_Nothing currently planned — all P1 specs shipped._

---

## 🔵 Previously planned

| Feature | Priority | Problem it solves | Spec | Effort |
|---------|----------|--------------------|------|--------|
| **Metacognition capture** | P1 | No record of HOW user thinks — only what they answered. Can't distinguish fact gaps from concept gaps from strategy errors. | [`plans/metacognition_capture.md`](plans/metacognition_capture.md) | ~15 hrs |
| **Question & session feedback** | P1 | Bad questions (wrong answer, off-syllabus, unclear) silently corrupt scoring data. Difficulty engine has only correct/incorrect signal — no self-reported signal. ChromaDB gaps are invisible. | [`plans/question_feedback.md`](plans/question_feedback.md) | ~6.5 hrs |
| **Audio revision export (NotebookLM)** | P1 | No audio revision path. Rahul studies 5-6 hrs/day but commute/exercise time is unused. System has all the data (gaps, PYQs, notes) but no way to export it for audio consumption. | [`plans/audio_revision.md`](plans/audio_revision.md) | ~5 hrs |

---

## 📋 Queued — identified, needs spec

These are ordered by impact. Pick from the top.

| # | Feature / Fix | Priority | Description | Source |
|---|---------------|----------|-------------|--------|
| 17 | **PYQ Data Foundation** | **P0** | Official UPSC answer keys for 2013–2025 (scope: 2013 onwards for PYQ Browser). Fix incomplete years (2018 lowest at 72 of 100), fix 2014 duplication (132 rows), tag cancelled + disputed answers. Blocker for PYQ Browser + Explanations. | [`plans/pyq_data_foundation.md`](plans/pyq_data_foundation.md) |
| 18 | ~~**PYQ Browser**~~ | ~~P1~~ | ~~SHIPPED PR #45~~ | ~~[`plans/pyq_browser.md`](plans/pyq_browser.md)~~ |
| 19 | **PYQ Explanations (Paid Content)** | P1 | Pre-generate concept explanation per PYQ via Haiku Batch (~₹85 one-time). Covers: concept tested, why each wrong option is wrong, memory hook. Pro-gated explanation card in PYQ Browser. | [`plans/pyq_explanations.md`](plans/pyq_explanations.md) |
| 20 | **Multi-Exam Question Bank** | P1 | Harvest CDS/NDA/CAPF/CISF PYQs (~6,500–7,000 questions, official UPSC answer keys, zero AI cost) into `question_bank` table. AI gap-fill only for underrepresented subtopics (~₹75). Feeds all diagnostics, simulations, adaptive engine. | [`plans/multi_exam_bank.md`](plans/multi_exam_bank.md) |
| 1 | ~~PYQ subtopic ID normalisation~~ | ~~P1~~ | ~~SHIPPED~~ | ~~`HANDOFF.md → P1`~~ |
| 2 | ~~ChromaDB content audit + re-ingestion~~ | ~~P1~~ | ~~AUDITED May 16: 11,146 chunks across 9 GS subjects — all healthy. ir_governance lowest at 320 chunks (above threshold). CSAT has 0 chunks (intentional — separate system). No re-ingestion needed.~~ | ~~Resolved May 16~~ |
| 2b | ~~User-editable daily plan~~ | ~~P2~~ | ~~SHIPPED — Rahul can edit sessions inline before starting; edits saved to `study_plan_user.json`; delta log persists what Claude suggested vs what was changed.~~ | ~~PR #32 — Spec: [`plans/user_editable_plan.md`](plans/user_editable_plan.md)~~ |
| 3 | ~~Timed mode enforcement~~ | ~~P1~~ | ~~SHIPPED~~ | ~~PR #29~~ |
| 4 | ~~Open-ended quiz mode~~ | ~~P1~~ | ~~SHIPPED~~ | ~~PR #29~~ |
| 5 | ~~Session summaries backfill~~ | ~~P2~~ | ~~SHIPPED~~ | ~~PR #7 — executed May 16~~ |
| 6 | Question deduplication | P2 | No mechanism to prevent same question appearing in two sessions. `question_hash` column exists but unused for filtering. | `HANDOFF.md → P4` |
| 7 | Streak + daily time dashboard widget | P2 | Dashboard widget showing: consecutive days studied (streak), today's session count, and total study minutes today and this week. Derivable from session timestamps — no new DB columns needed. | [`plans/streak_tracker.md`](plans/streak_tracker.md) |
| 8 | Quiz mode UX rename | P2 | Rename `fixed_set` → "Practice Set", `time_boxed` → "Timed Quiz", add "Open Practice" for the open-ended mode. Restructure the mode selector to be self-explanatory. ~1 hr UI only. | Session planning May 12 |
| 9 | Difficulty engine — 1-question threshold | P2 | Difficulty never updates in multi-subtopic diagnostic mode (requires 3+ answers per subtopic, but allocation gives 1 each). | `HANDOFF.md → P5` |
| 10 | Plan validation layer | P2 | Plan scheduling is LLM-decided with no post-generation validation. Claude can ignore rules. Add deterministic Python checks: time budget, subject spread, re-test rules. | `HANDOFF.md → P6` |
| 11 | CSAT activation | P2 | CSAT routes and pages exist but have never been run. Profile doesn't exist. Needs a first-run setup and its own diagnostic flow. | `HANDOFF.md → P8` |
| 12 | Onboarding redesign | P3 | First-run experience is rough. User needs guided setup for API key, study material ingestion, and first diagnostic. | [`plans/onboarding_redesign.md`](plans/onboarding_redesign.md) |
| 13 | Mock test mode | P3 | Full UPSC Prelims simulation: 100 questions, 2 hours, mixed subjects, auto-scored with strategy analysis. | [`plans/github_collab.md`](plans/github_collab.md) — rough notes |
| 14 | Auto-start on Mac reboot | P3 | Both servers must be manually started after every restart. `pm2` or `launchd` plist files would fix this. | `HANDOFF.md → P7` |
| 15 | **Multi-user auth + multi-tenancy + PostgreSQL (Sprint 2)** | **P0** | 41 hardcoded `'user_1'` sites across 9 files (all SILENT_BREAK). Supabase JWT auth, user_profiles table, JSON file → DB migration, PostgreSQL on Railway. 5–6 build days. Full spec in `SPRINT_BOARD.md` and `docs/migration/`. | `SPRINT_BOARD.md §Sprint2` |
| 21 | **Automated UPSC answer key pipeline (Sprint 1 unblock)** | **P0** | `scripts/download_answer_keys.py` fetches official UPSC PDFs programmatically + iaseth/prelimspattern JSON; `scripts/import_answer_keys.py` extracts Q#→A/B/C/D via pdfplumber and updates `correct_answer` + sets `answer_source='upsc_official_key'`. Eliminates manual PDF download blocker. Needs ALTER TABLE approval first. | `SPRINT_BOARD.md §Sprint1` |
| 16 | Session resumption — resume later | P3 | Resume a paused quiz session from the exact question after page reload or app close. Deferred — needs cost/scope evaluation post-exam. Full thought process and decision criteria documented. | [`plans/session_resumption.md`](plans/session_resumption.md) |

---

## How to contribute

1. Pick a queued item → write a spec in `plans/<feature_name>.md` → move it to the Planned section above
2. Pick a planned item → implement it → open a PR → move it to Shipped
3. Found a new bug? Add it to Queued with priority and description

See `COLLAB.md` for full contribution guide and branch/PR conventions.
See `HANDOFF.md` for the latest dev session context (what changed, what to watch out for).
