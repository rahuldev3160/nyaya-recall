---
id: PLAN-008
type: plan
project: devthorium
date: 2026-08-29
status: PROPOSED
---

# PLAN-008: RBI Grade B migration — Scribe → Recall, staged and reversible

**Scope note:** Architecture only. No code, no migration execution. Depends on PLAN-007's
schema landing first — do not begin §2 below until PLAN-007's ALTER TABLE is approved and run.

## 1. What actually moves, and what deliberately stays in Scribe

| Data | Today | After this plan | Why |
|---|---|---|---|
| `rbi_questions` (321 rows, 4-option MCQ) | `rbi.db`, Scribe | Copied into Recall's `question_bank`, `exam_source='rbi_grade_b'` | This is content — Recall's whole purpose per this redesign. |
| `rbi_topic_weights` (29 topics) | `rbi.db`, Scribe | Copied into Recall's `topic_weights` (PLAN-007), `weight_source='manual'` | Same reasoning — it's content metadata (which topics matter), not user data. |
| `rbi_attempts` | `rbi.db`, Scribe, keyed by real Scribe `user_id` | **Stays in Scribe**, unchanged ownership | This is Scribe's own users' attempt history. Recall's internal contracts are stateless by design (Arena's DECIDE-09) — there is no mechanism, and should be none invented, for Recall to hold a Scribe user's identity. |
| `rbi_topic_mastery` | `rbi.db`, Scribe, keyed by real Scribe `user_id` | **Stays in Scribe**, unchanged ownership | Same reasoning; also this is *derived* from `rbi_attempts`, so it has to live wherever the attempts live. |
| `rbi_key_data` (RBI facts/circular-derived reference cards, "Key Data" tab) | `rbi.db`, Scribe | **Stays in Scribe.** | This is not MCQ content — no options, no correct_option, it's flashcard-style reference facts. The task scope is RBI's *MCQ* data and architecture; `rbi_key_data` is a different Scribe feature that happens to share a database file. Moving it would be scope creep past what was asked, and it has no natural home in a table shaped for four-option questions. If a later phase wants Recall's `source_documents` (PLAN-007) to become the canonical place official RBI circulars are stored, `rbi_key_data` could be re-pointed to read from there — that is an explicit future call for Rahul, not assumed here. |

## 2. Migration mechanics — copy, never move, never delete

1. **Snapshot.** `rbi.db` is copied to a dated backup path before anything else runs. This file
   is never deleted by this plan, at any stage, indefinitely — see §5's rollback reasoning for why
   that permanence is load-bearing, not just caution.
2. **ID mapping table** (new, lives wherever the migration script runs — a one-time artifact, not
   a permanent product table): `old_rbi_id → new_question_bank_id`. New IDs follow the pattern
   `rbi_q_{old_id:05d}` so they're recognizable in logs, but are otherwise just Recall's normal
   `question_bank.id` values.
3. **Copy `rbi_questions` → `question_bank`:**
   - `exam_source = 'rbi_grade_b'`
   - `subject_id` ← RBI's `subject` field directly (e.g. `macro`, `rbi_banking`) — already close
     enough to Recall's subject taxonomy shape to reuse verbatim; a full remap to Recall's own
     subject vocabulary is not required for serving to work, only for cross-exam readiness
     rollups to look natural later (non-blocking follow-up).
   - `topic_id` ← the **tier-2 bucket key** (`rbi_instruments`, `banking_regulation`, ... — 9
     values, `_BUCKET_META` in `rbi_prep_bp.py`). This is the natural middle layer: RBI's own
     schema already has a coarser 9-bucket grouping sitting one level above the 29 fine-grained
     tier-1 topics — it was just never named `topic_id` because RBI's schema predates this
     3-level model.
   - `subtopic_id` ← the tier-1 `topic` field (the 29 fine-grained values, e.g.
     `monetary_policy`). **Note the naming collision this resolves, not creates:** RBI's own
     `rbi_questions.topic` column means two different granularities depending on `tier` (1 vs 2)
     — a quirk of the existing schema, not introduced by this migration. Recall's 3-level
     `subject_id`/`topic_id`/`subtopic_id` actually disambiguates this for free.
   - `question_format = 'single_correct'` (all 321 are plain 4-option MCQs, confirmed by schema
     inspection — no assertion-reason/statement-based rows in RBI content today).
   - `default_marks = 1.0` (RBI's marking scheme, per `internal_api_bp.py`'s
     `_DEFAULT_MARKING_SCHEME`, correct=1/wrong=-0.25/unattempted=0 — not UPSC's 2/-0.66/0).
   - `source_type = 'unclassified_legacy'` (PLAN-007). **This is an honest gap, not an
     oversight:** nothing in `rbi_questions` records whether a given question is an official
     PYQ, a similar-exam PYQ, or hand-written — that provenance was never tracked before this
     redesign. Flag to Rahul as an open question (B-13, see cross-file update) rather than
     guess a classification that would look authoritative but isn't.
   - `tags` (existing free-text column) gets `{"rbi_tier": 1}` or `{"rbi_tier": 2}` so the
     tier-1-drill vs tier-2-quiz pedagogical distinction (currently load-bearing in
     `rbi_prep_bp.py`'s two different serving functions) survives the move and both serving
     functions can still filter on it via Recall's `/internal/v1/questions` (needs a `tags`
     filter param added — additive, non-breaking change to that endpoint).
4. **Copy `rbi_topic_weights` → `topic_weights`** (PLAN-007), `exam_source='rbi_grade_b'`,
   `weight_source='manual'`. `subject`/`topic` map the same way as step 3.
5. `rbi.db`'s `rbi_questions`/`rbi_topic_weights` tables are **left in place, untouched, read
   accessible** — not dropped, not truncated. They become dead weight only once the flag in §3
   below has been on `recall` for a sustained period Rahul is comfortable with; deleting them is
   explicitly out of scope for this plan and would need its own future approval-gated decision.

## 3. Cutover mechanics — feature flag, not a rewrite

New Scribe-side module `web/blueprints/_recall_client.py` (naming illustrative — actual
placement is an implementation-pass decision): thin HTTP client wrapping
`GET /internal/v1/questions?exam_source=rbi_grade_b&...` and
`POST /internal/v1/score-attempt` (both **already built and merged** — this plan reuses them
as-is; RBI needs no new Recall endpoint, only a new registered caller and a new `exam_source`
value, see §4).

`rbi_prep_bp.py`'s `get_smart_questions()` / `get_filtered_questions()` and
`rbi_dashboard_bp.py`'s topic-weight reads branch on a new env var:

```
RBI_CONTENT_SOURCE = local | recall     # default: local (today's behavior, unchanged)
```

- `local`: existing code path, byte-for-byte unchanged. Zero risk to the live feature while this
  flag is off.
- `recall`: fetch/score go through the Recall client; `_update_mastery()` and `save_attempt()`
  **keep writing to `rbi_attempts`/`rbi_topic_mastery` exactly as today** — only the *source* of
  the question content and the *scoring* changes, not where Scribe's own bookkeeping lands.

This is the same shape Arena already validated for Contract 1/2 (stateless upstream, caller
persists under its own identity) — Scribe becomes a second caller of that pattern, not a
special case, per the task's explicit framing.

### One real schema wrinkle: `rbi_attempts.question_id` after the ID space changes

Historical `rbi_attempts` rows store the **old** local integer IDs. Post-cutover, new attempts
will carry Recall's new string IDs (`rbi_q_00187`-style). Two ways to handle this, and the
chosen one:

- **Rejected:** backfill historical `rbi_attempts.question_id` values to the new IDs using the
  mapping table from §2, so every row is on one consistent ID space. This forces a perfect,
  irreversible rewrite of live users' attempt history before cutover can even start, for a
  benefit (one consistent ID space) that nothing currently needs — no query joins
  `rbi_attempts.question_id` back to `question_bank` today except within `rbi_prep_bp.py`
  itself, and that code can branch.
- **Chosen:** add one column, `rbi_attempts.source TEXT NOT NULL DEFAULT 'local'`, populated
  `'recall'` for any new attempt row written while the flag is `recall`. Historical rows keep
  their old local IDs and stay resolvable against the still-un-deleted `rbi.db` copy of
  `rbi_questions` (§2 step 5) for as long as anything needs to show old question text (session
  review, explanations). Nothing about old data has to be perfect or migrated before go-live —
  this is a smaller, safer, and fully reversible change. **This is itself an ALTER TABLE on a
  live table with real user attempt history — the highest-stakes schema change in this whole
  design.** Logged as **B-12** (see cross-file update), separate from PLAN-007's B-11 because it
  is Scribe's own live-user table, not Recall's pre-launch one, and deserves its own explicit
  approval ask rather than being bundled.

### Staged rollout, concretely

1. Ship the flag defaulted to `local` — no behavior change, safe to merge and deploy immediately.
2. Flip to `recall` in a local/dev run only; manually compare question sets and scored results
   for parity against the `local` path for a sample of topics (Rahul spot-checks — same
   BUG-035-lesson instinct as PLAN-009's ingestion quality gates, applied to a migration instead
   of new content).
3. **Open question, not assumed:** whether Scribe has any staging/preview environment distinct
   from the Railway production deploy is not established in the ground truth for this task —
   verify with Rahul before assuming step 2 can run anywhere other than local. If none exists,
   step 2 has to happen locally against a copy of production data, or gated behind a
   Rahul-only account flag if one exists in Scribe's auth layer (not confirmed here either).
4. Flip to `recall` in production only after step 2/3 passes. No cohort/percentage rollout
   mechanism exists in Scribe today and building one is out of scope for this plan (Rule 4 — a
   flag with two values is the smallest thing that satisfies "staged and reversible"; a
   percentage-rollout system would be solving a problem this feature's real user count doesn't
   have yet).

## 4. Internal API auth — generalize away from "Arena-only" now that Scribe is a second caller

Today: `X-Arena-Api-Key` / `ARENA_SERVICE_API_KEY`, one shared secret, one consumer, per
`docs/API_CONTRACTS.md`'s explicit note that this is "deliberately minimal" because "Arena is
the only internal consumer either product has today." That premise is now false the moment
Scribe calls Recall's own `/internal/v1/questions` for its own RBI feature (not on Arena's
behalf — a genuinely new, second, independent internal caller).

**Chosen: per-caller named keys under a generalized header, not a second Arena-shaped
special case.**

```
Header:   X-Internal-Api-Key: <key>
Env vars: INTERNAL_API_KEY_ARENA=...
          INTERNAL_API_KEY_SCRIBE_RBI=...
```

`verify_arena_api_key()` in `backend/routes/internal_arena.py` (and its Scribe-side twin,
`_check_arena_key()` in `internal_api_bp.py` — the direction this migration reverses, since
Scribe is now also a *caller* of Recall, not just a *callee* of Arena) becomes
`verify_internal_caller()`: constant-time-compares the provided key against each known caller's
key in turn, returns which caller matched (for logging), 401s if none match. Rejected: one
still-shared secret for both callers — cheap today, but the moment either key needs rotating
(compromise, or Scribe's RBI feature is ever decommissioned) a shared secret forces rotating
both callers' access together for no reason. Per-caller keys cost one extra env var and pay for
themselves the first time a key needs to be revoked independently.

This is a pure-code, additive change to already-merged files — no schema impact, no approval
gate under this project's own rules, but flag to Rahul as a heads-up per the same courtesy
Arena's Phase 1 already established for non-schema changes to a project with its own
conventions.

## 5. Does this trigger `sar_scores` (B-4)? Explicit answer: No.

`sar_scores` is Recall's own UPSC-Prelims self-attestation table — subject-level, keyed by a
Recall `user_id`. Nothing in this migration reads or writes it:

- Recall's `/internal/v1/questions` and `/internal/v1/score-attempt` are stateless (write
  nothing at all, to any table) — unchanged by adding `exam_source='rbi_grade_b'` as a valid
  value; the query just returns different rows.
- Scribe's own write path (`rbi_attempts`, `rbi_topic_mastery`) never touched `sar_scores` before
  this migration and doesn't start now — RBI and UPSC self-attestation are unrelated features in
  unrelated databases.
- B-4 remains exactly as scoped in `SPRINT_BOARD.md` today: it blocks a second concurrent writer
  to `sar_scores` specifically, and nothing in this plan is a second writer to that table.

## 6. `internal_api_bp.py` (Scribe) — recommendation: keep, convert to a thin proxy, do not remove

Nyaya Arena's Contract 2 (`docs/API_CONTRACTS.md`) is a **frozen spec** that Arena's Phase 3/4
already built and tested against (per `IMPLEMENTATION_PLAN.md`'s own instruction: "do not
redesign contracts while implementing — file a new DECIDE/RISK item instead"). Two options once
RBI content's source of truth moves to Recall:

- **Rejected — point Arena directly at Recall's Contract 1 for RBI, retire Scribe's Contract 2
  entirely.** Cleaner in the abstract (no double-hop), but it means changing a frozen,
  already-implemented, already-tested contract that a separate sibling project (Arena) depends
  on, purely for Recall/Scribe's own internal tidiness. That is exactly the kind of change
  IMPLEMENTATION_PLAN.md's own instruction exists to prevent.
- **Chosen — `internal_api_bp.py` stays exactly where it is, keeps exactly its current external
  shape (`GET /internal/v1/exams/rbi/questions`, `POST /internal/v1/exams/rbi/score`), and its
  internal implementation becomes a translation shim**: it calls Recall's
  `GET /internal/v1/questions?exam_source=rbi_grade_b&...` /
  `POST /internal/v1/score-attempt` (registering as the `SCRIBE_RBI` caller from §4) instead of
  querying `rbi_questions` directly, and translates Recall's response shape back into Contract
  2's documented shape (which, per DECIDE-13's correction, are already nearly identical —
  both are stateless deterministic MCQ fetch+score with the same field names). Arena's Phase 3/4
  code needs **zero changes**. This is reversible on its own (revert the shim, point back at
  local `rbi.db`, independent of whether Scribe's own `rbi_prep_bp.py` cutover in §3 has
  happened) and can be sequenced any time after §4's generalized auth lands — it does not block,
  and is not blocked by, Scribe's own live-user rollout in §3.

Logged as a **new decision** in `SPRINT_BOARD.md` (cross-file update) rather than left implicit,
since it's a real architectural fork with a rejected alternative, matching this project's own
decision-logging convention.

## 7. Rollback plan

At every stage, `rbi.db`'s original tables are intact (§2 step 5) and `rbi_attempts`/
`rbi_topic_mastery` were never touched by anything except the addition of one new nullable-
default column (§3's `source`). Reverting `RBI_CONTENT_SOURCE` to `local` at any point:

- Immediately restores byte-for-byte original behavior for question fetch and scoring.
- Loses nothing — attempts written while the flag was `recall` remain valid rows referencing
  valid (never-deleted) `question_bank` IDs; they just won't be the ones served next, since new
  fetches go back to local content. No attempt history is invalidated by reverting.
- Requires no data migration to undo, because §3's chosen approach never migrated old data in
  the first place — the only genuinely hard-to-reverse action in this whole plan would have been
  the rejected backfill-all-history approach, which is exactly why it was rejected.
