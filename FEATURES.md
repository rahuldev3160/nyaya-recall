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

---

## 🔵 Planned — spec written, ready to build

| Feature | Priority | Problem it solves | Spec | Effort |
|---------|----------|--------------------|------|--------|
| **Topic-level hierarchical coverage (FEATURE-028)** | P1 | topic_id is NULL/non-canonical everywhere; plan generator gives Claude a flat list with no topic grouping; you can skip an entire topic while showing 100% subject coverage. Fixes data plumbing + adds topic-level visibility on tracker/strategy. | [`plans/topic-hierarchy-coverage.md`](plans/topic-hierarchy-coverage.md) | ~12 hrs, 2 sessions |
| **Dimension-aware subtopic coverage (FEATURE-027)** | P1 | A subtopic is marked "done" after touching any one of its 4-8 testable dimensions. Coverage formula ignores whether core concept, PYQ-heavy, or current-affairs-linked dimensions were actually tested. Needs FEATURE-028 first. | [`plans/dimension-coverage.md`](plans/dimension-coverage.md) | ~15 hrs, 3 sessions |

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
| 1 | ~~PYQ subtopic ID normalisation~~ | ~~P1~~ | ~~SHIPPED~~ | ~~`HANDOFF.md → P1`~~ |
| 2 | ChromaDB content audit + re-ingestion | P1 | Unknown how much study material is actually indexed. Most quiz questions fall back to generic stubs. Audit per-subject coverage and re-ingest gaps. | `HANDOFF.md → P2` |
| 3 | Timed mode enforcement | P1 | Add live countdown display to `time_boxed` mode. Auto-close session when timer hits 0 — saves questions answered so far, skips remainder. Currently time limit is collected but never enforced. ~2–3 hrs. | Session planning May 12 |
| 4 | Open-ended quiz mode | P1 | New quiz mode: no fixed question count or time limit. "Save & Close" button after each answered/skipped question closes the session as complete with questions done so far (save-as-complete, not resume-later). ~3–4 hrs. | Session planning May 12 |
| 5 | Session summaries backfill | P2 | Historical polity/economy `session_summaries.weak_subtopics` arrays are empty (computed before subtopic fix). `get_persistently_weak_subtopics()` can't see past session weakness patterns. | `HANDOFF.md → P3` |
| 6 | Question deduplication | P2 | No mechanism to prevent same question appearing in two sessions. `question_hash` column exists but unused for filtering. | `HANDOFF.md → P4` |
| 7 | Streak + daily time dashboard widget | P2 | Dashboard widget showing: consecutive days studied (streak), today's session count, and total study minutes today and this week. Derivable from session timestamps — no new DB columns needed. | [`plans/streak_tracker.md`](plans/streak_tracker.md) |
| 8 | Quiz mode UX rename | P2 | Rename `fixed_set` → "Practice Set", `time_boxed` → "Timed Quiz", add "Open Practice" for the open-ended mode. Restructure the mode selector to be self-explanatory. ~1 hr UI only. | Session planning May 12 |
| 9 | Difficulty engine — 1-question threshold | P2 | Difficulty never updates in multi-subtopic diagnostic mode (requires 3+ answers per subtopic, but allocation gives 1 each). | `HANDOFF.md → P5` |
| 10 | Plan validation layer | P2 | Plan scheduling is LLM-decided with no post-generation validation. Claude can ignore rules. Add deterministic Python checks: time budget, subject spread, re-test rules. | `HANDOFF.md → P6` |
| 11 | CSAT activation | P2 | CSAT routes and pages exist but have never been run. Profile doesn't exist. Needs a first-run setup and its own diagnostic flow. | `HANDOFF.md → P8` |
| 12 | Onboarding redesign | P3 | First-run experience is rough. User needs guided setup for API key, study material ingestion, and first diagnostic. | [`plans/onboarding_redesign.md`](plans/onboarding_redesign.md) |
| 13 | Mock test mode | P3 | Full UPSC Prelims simulation: 100 questions, 2 hours, mixed subjects, auto-scored with strategy analysis. | [`plans/github_collab.md`](plans/github_collab.md) — rough notes |
| 14 | Auto-start on Mac reboot | P3 | Both servers must be manually started after every restart. `pm2` or `launchd` plist files would fix this. | `HANDOFF.md → P7` |
| 15 | Multi-user / dynamic user_id | P3 | `user_id = 'user_1'` is hardcoded everywhere. Making it dynamic unlocks multi-user. | `docs/PLANNING.md` |
| 16 | Session resumption — resume later | P3 | Resume a paused quiz session from the exact question after page reload or app close. Deferred — needs cost/scope evaluation post-exam. Full thought process and decision criteria documented. | [`plans/session_resumption.md`](plans/session_resumption.md) |

---

## How to contribute

1. Pick a queued item → write a spec in `plans/<feature_name>.md` → move it to the Planned section above
2. Pick a planned item → implement it → open a PR → move it to Shipped
3. Found a new bug? Add it to Queued with priority and description

See `COLLAB.md` for full contribution guide and branch/PR conventions.
See `HANDOFF.md` for the latest dev session context (what changed, what to watch out for).
