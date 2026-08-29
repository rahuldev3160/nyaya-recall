---
id: AUDIT-001
type: audit
project: devthorium
date: 2026-08-29
---

# AUDIT-001: Mock-competition reuse audit (Nyaya Arena scoping)

## Scope
Read-only investigation of whether Devthorium/Recall's existing architecture could support a
new multi-user, ranked "mock competition" feature (Nyaya Arena), as part of a broader scoping
session for a DU UPSC mock competition + law-exam-prep initiative.

## Findings
- Memory (54-day-old note) claiming "not publicly launched, single-user" is **stale on the
  single-user point**: `user_id` is already threaded through all routes (PR #43, Sprint 2),
  and `backend/auth.py` has full JWT auth middleware written, just unconfigured (missing
  Supabase env keys — B-1).
- `question_bank` is already multi-exam by design via `exam_source` (not hardcoded to UPSC) —
  7,166 questions across 8 subject categories, cross-exam pipeline already exists.
- Scoring (`score_engine.py`) is pure local Python, SM-2 SRS-based, no per-answer API call.
- **Daily-challenge + leaderboard mechanic already exists**: `generate_daily_challenge.py` and
  a `/leaderboard` Next.js page are built. `GET /leaderboard/daily` currently returns `[]` with
  a code comment stating it's pending multi-user auth — the core "same question set, ranked"
  mechanic Arena needs is not net-new.
- Remaining gap to activate: (a) B-1/B-2 (Supabase/Railway setup, Rahul's action items,
  unrelated to this audit), (b) B-4 (`sar_scores` bare `user_id` PK — will crash on a second
  real user, approval-gated ALTER TABLE), (c) the actual `/leaderboard/daily` aggregation query
  (aggregate `quiz_sessions`/`session_answers` by `challenge_date`, rank by score+time — not written),
  (d) a synchronized/scheduled competition-window entity if fixed start/end times are wanted
  beyond the current async daily-challenge model.

## Conclusion
Recall's contribution to Nyaya Arena is materially cheaper than a from-scratch build. See
[PLAN-006](../plans/PLAN-006.md) for the resulting architecture decision (reuse Recall's engine,
separate identity layer in the new Arena project).
