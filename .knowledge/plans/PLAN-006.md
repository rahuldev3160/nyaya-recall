---
id: PLAN-006
type: plan
project: devthorium
date: 2026-08-29
status: DECIDED
---

# PLAN-006: Nyaya Arena — DU UPSC Mock Competition reuses Recall's engine, own identity

## Decision
- The new "Nyaya Arena" DU UPSC mock-competition feature (sibling project, being scaffolded at
  `/Users/rahulsingh/Desktop/Claude Projects/Nyaya-Arena`) reuses Recall's existing daily-challenge
  mechanic, `/leaderboard` UI, and exam-agnostic `question_bank` (new `exam_source` values for
  DU/competition content) instead of building a new quiz engine.
- Arena does NOT depend on Recall's Supabase auth going live. It gets its own lightweight
  identity + leaderboard/ranking store, and reads Recall's `question_bank` through an internal
  API contract (to be designed) rather than direct DB access.

## Rationale
Architecture audit (2026-08-29, multi-agent scoping session) found the competition mechanic
~70% already built here: `generate_daily_challenge.py`, the `/leaderboard` page, and
`GET /leaderboard/daily` all exist — the endpoint just returns `[]` pending multi-user auth.
Building Arena's own identity layer means it isn't blocked on B-1/B-2 (Rahul's pending Supabase/
Railway setup), and Scribe's live production auth (95 real users) isn't touched either.

## Rejected
- Building a separate MCQ engine for Arena — Recall's `question_bank`/`exam_source` design is
  already exam-agnostic, a new engine would duplicate PLAN-001's two-table architecture for no reason.
- Unifying identity under Supabase now — couples Arena's launch to B-1/B-2 completion and forces
  a live-user auth migration on Scribe before its paywall ships. Revisit once Recall's own
  Supabase deploy is actually live.

## Cross-project impact
B-4 (`ALTER TABLE sar_scores` PK fix, SPRINT_BOARD.md) is now also a blocker for Arena, not just
Recall's own multi-user rollout — any second real user writing scores hits the same bare-`user_id`
PK collision. Must ship before Arena's leaderboard goes live with real participants.

## Full context: parent conversation scoping session, 2026-08-29 (Nyaya Arena / law + UPSC mock competition initiative)
