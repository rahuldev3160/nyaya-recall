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

---

## 🔵 Planned — spec written, ready to build

| Feature | Priority | Problem it solves | Spec | Effort |
|---------|----------|--------------------|------|--------|
| **Metacognition capture** | P1 | No record of HOW user thinks — only what they answered. Can't distinguish fact gaps from concept gaps from strategy errors. | [`plans/metacognition_capture.md`](plans/metacognition_capture.md) | ~15 hrs |

---

## 📋 Queued — identified, needs spec

These are ordered by impact. Pick from the top.

| # | Feature / Fix | Priority | Description | Source |
|---|---------------|----------|-------------|--------|
| 1 | PYQ subtopic ID normalisation | P1 | `priority_scorer` returns weight 1.0 for most subtopics because PYQ table uses different subtopic_id values than `syllabus.json`. Fix the mapping so priority ordering actually works. | `HANDOFF.md → P1` |
| 2 | ChromaDB content audit + re-ingestion | P1 | Unknown how much study material is actually indexed. Most quiz questions fall back to generic stubs. Audit per-subject coverage and re-ingest gaps. | `HANDOFF.md → P2` |
| 3 | Session summaries backfill | P2 | Historical polity/economy `session_summaries.weak_subtopics` arrays are empty (computed before subtopic fix). `get_persistently_weak_subtopics()` can't see past session weakness patterns. | `HANDOFF.md → P3` |
| 4 | Question deduplication | P2 | No mechanism to prevent same question appearing in two sessions. `question_hash` column exists but unused for filtering. | `HANDOFF.md → P4` |
| 5 | Streak + daily goal tracker | P2 | No daily return habit mechanism. Dashboard widget showing streak, today's session count, study minutes. | [`plans/streak_tracker.md`](plans/streak_tracker.md) |
| 6 | Difficulty engine — 1-question threshold | P2 | Difficulty never updates in multi-subtopic diagnostic mode (requires 3+ answers per subtopic, but allocation gives 1 each). | `HANDOFF.md → P5` |
| 7 | Plan validation layer | P2 | Plan scheduling is LLM-decided with no post-generation validation. Claude can ignore rules. Add deterministic Python checks: time budget, subject spread, re-test rules. | `HANDOFF.md → P6` |
| 8 | CSAT activation | P2 | CSAT routes and pages exist but have never been run. Profile doesn't exist. Needs a first-run setup and its own diagnostic flow. | `HANDOFF.md → P8` |
| 9 | Onboarding redesign | P3 | First-run experience is rough. User needs guided setup for API key, study material ingestion, and first diagnostic. | [`plans/onboarding_redesign.md`](plans/onboarding_redesign.md) |
| 10 | Mock test mode | P3 | Full UPSC Prelims simulation: 100 questions, 2 hours, mixed subjects, auto-scored with strategy analysis. | [`plans/github_collab.md`](plans/github_collab.md) — rough notes |
| 11 | Auto-start on Mac reboot | P3 | Both servers must be manually started after every restart. `pm2` or `launchd` plist files would fix this. | `HANDOFF.md → P7` |
| 12 | Multi-user / dynamic user_id | P3 | `user_id = 'user_1'` is hardcoded everywhere. Making it dynamic unlocks multi-user. | `docs/PLANNING.md` |

---

## How to contribute

1. Pick a queued item → write a spec in `plans/<feature_name>.md` → move it to the Planned section above
2. Pick a planned item → implement it → open a PR → move it to Shipped
3. Found a new bug? Add it to Queued with priority and description

See `COLLAB.md` for full contribution guide and branch/PR conventions.
See `HANDOFF.md` for the latest dev session context (what changed, what to watch out for).
