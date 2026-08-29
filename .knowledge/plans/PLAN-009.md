---
id: PLAN-009
type: plan
project: devthorium
date: 2026-08-29
status: PROPOSED
---

# PLAN-009: Multi-source ingestion pipeline, personalization signal, and phased build order

**Scope note:** Architecture only. No code. Assumes PLAN-007's schema and PLAN-008's RBI
migration are the target shape this pipeline writes into and the signal reads from.

## 1. One ingestion path per source type

All four paths write into `question_bank` using PLAN-007's `source_type`/`source_ref`/
`source_document_id`/`generation_batch_id` columns. All four share one non-negotiable rule
carried over from §3's quality gates: **nothing reaches `active`/servable status without
passing its gate — no exceptions for "this source feels safer."** BUG-035 was exactly a case
where a source (a coaching-site scrape) felt low-risk enough to skip verification on, and
65–90% of it was garbage.

### A. Official PYQ
Script shape mirrors the already-built `ingest_pyq.py` / Sprint 1 pattern: official PDF →
`pdfplumber` extraction → question/option/answer-key join by `(year, q_number)` →
`source_type='official_pyq'`, `answer_source='upsc_official_key'`. **For RBI specifically, this
bucket's existence is unconfirmed** — RBI does not publish Phase 1 objective papers with an
official key the way UPSC does. Verify with Rahul (official RBI recruitment site) before
building this path for `rbi_grade_b` at all; if it doesn't exist, RBI leans more heavily on
buckets B and D below, which is a legitimate outcome, not a gap to force-fill.

### B. Similar-exam PYQ
Reuses `ingest_cross_exam.py`'s exact shape (already built for CDS/NDA/CAPF): official PDF →
extraction → Haiku classification into `(subject_id, topic_id, subtopic_id)` →
`source_type='similar_exam_pyq'`, `source_ref={"source_exam": "...", "year": ..., "q_number": ...}`.
For RBI: NABARD Grade A, SEBI Grade A, IBPS SO (Finance/Economics stream), UPSC EPFO. Same
official-source-only rule as bucket A — no coaching-site aggregation of "similar exam" papers
either, for the same BUG-035 reason.

### C. AI-generated current affairs (evolving)
**Cadence: monthly batch**, matching how current-affairs content is actually consumed by
aspirants (a "July 2026 Current Affairs" compilation is the standard unit, not a daily drip).
`scripts/generate_current_affairs_batch.py --exam-source rbi_grade_b --month 2026-07`:

1. Reads `source_documents` rows for that `exam_source` + month (populated by bucket D's
   ingestion, run first).
2. Generates candidate questions **grounded in a specific document** — the prompt must cite
   which `source_document_id` a question comes from; this is the fact-grounding mechanism, not
   a free-form "write a current-affairs question about repo rate" prompt with no source pinned.
3. Writes candidates with `generation_batches.review_status='draft'`, `question_bank.active`
   left unset/false (PLAN-007's `retired_at IS NULL` convention needs a matching "not yet
   published" state — add `question_bank.status TEXT NOT NULL DEFAULT 'draft'` alongside
   PLAN-007's other new columns, enum `'draft' | 'active' | 'retired'`, since PLAN-007's
   `retired_at` alone only expresses "was once active, now isn't" — this is the one addition
   PLAN-007 should fold in before its ALTER TABLE ships, not a separate migration).
4. **Never auto-promotes `draft` → `active`.** Promotion requires §3's manual gate.

**How "evolving" avoids contradicting or duplicating already-served questions:**

- *Duplication*: before a candidate is written, embed its `question_text` (reuse the existing
  ChromaDB vector store already in this stack — no new infra) and query nearest neighbors
  against already-`active` rows for the same `exam_source`+`subject_id`; reject or flag for
  manual merge above a similarity threshold.
- *Contradiction with an in-flight competition*: **this risk is smaller than it first appears,
  by construction, not by a new mechanism.** Arena's `competitions.question_set_ref` freezes the
  exact filter (including a `seed`) at competition-creation time, and `attempts.question_ids`
  freezes the actual resolved question objects at `start` time (`IMPLEMENTATION_PLAN.md`
  §2/§3.3). A new batch published mid-competition does not retroactively alter a competition
  that already resolved its question set — it only changes what a *future* fetch call returns.
  The one real rule this imposes on `question_bank`: **never edit a question's `question_text`
  or `correct_answer` in place once it has ever been served** (any attempt anywhere may hold its
  ID). A fact that goes stale (repo rate changes) is handled via `superseded_by` (PLAN-007) —
  the old row is retired, a new row is created, nothing already-served silently changes meaning
  underneath an in-progress or completed attempt.
- *Old questions never vanish*: `retired_at`/`status='retired'` is a soft flag, never a
  `DELETE`. Serving queries filter `WHERE status='active'`; historical joins from
  `user_question_log`/`attempts` by `question_bank.id` resolve regardless of status. This is the
  literal mechanism for "old questions shouldn't silently vanish from history just because the
  current-affairs DB refreshes" — nothing about a refresh ever removes a row, it only adds new
  ones and retires superseded ones.

### D. Official communication documents
Ingestion targets, by exam (concrete, per task requirement):
- **RBI**: circulars, Master Directions, MPC press releases from rbi.org.in's Notifications page.
- **UPSC-adjacent**: PIB releases (pib.gov.in), ministry press notes, Economic Survey, Union
  Budget documents, gazette notifications.

Pipeline: fetch → extract text → store in `source_documents` (PLAN-007) with `content_hash` for
de-dupe → feed into bucket C's generation step. **This bucket's own output is not itself
question content** — it's the grounding material bucket C consumes. A document with zero
questions generated from it yet is a legitimate, expected state, not a failure.

**Source allowlist (script-enforced, not manually eyeballed per-fetch):** `source_url` must
resolve to `rbi.org.in`, `pib.gov.in`, a `.gov.in` gazette domain, or another domain Rahul
explicitly adds — hard-coded allowlist in the ingestion script, request rejected otherwise. This
is the direct structural fix for BUG-035's root cause (a scraper pointed at an unofficial
coaching-site aggregator, not a government source).

## 2. Quality gates — concrete, per source type, before any content reaches a real user

The BUG-035 postmortem's real lesson isn't "add a validation script" (a script can be gamed by
its own blind spots, same as the ingestion it's checking) — it's that **a human looked at 6
random rows per bucket and found 6/6 junk in every one.** The gate is the human sample, not a
substitute automated check:

| Source type | Automated pre-screen | Mandatory human gate |
|---|---|---|
| Official PYQ | Cross-validate `correct_answer` via existing 3-tier consensus matcher (`build_answer_consensus.py` pattern — hash → normalized text → alpha-only) against a second independent official/community source | 10-sample manual spot-check before `answer_source` is trusted for scoring |
| Similar-exam PYQ | Same official-source-only allowlist as bucket D | 10-sample manual spot-check per new exam added (once per exam, not per batch — content is static once ingested) |
| AI current-affairs | Fact-grounding check: generated question's claim must substring/paraphrase-match its cited `source_document_id`'s extracted text; near-duplicate check (§1.C) | **10-sample manual review every batch** (recurring, since this bucket recurs monthly) — `generation_batches.review_status` cannot move `draft → published` without `reviewed_by` set |
| Official documents | URL-domain allowlist (script-enforced, not manual) | Spot-check only if a document's extracted text looks malformed (OCR garbage) — not a per-document human gate, since the document itself isn't served content, only grounding material |

No batch, of any source type, sets `question_bank.status='active'` (or, for PYQ buckets,
leaves `answer_source` implying trust) without its gate passing. This applies identically to
every future exam this platform adds — the gate is a property of the pipeline, not something
re-decided per exam.

## 3. Personalization signal — `user_topic_mastery`, and why it should be a SQL view, not application code

### Correcting the ground truth before designing on top of it

The task brief states "`score_engine.py` / `difficulty_engine.py` already implement SM-2-based
per-subtopic spaced-repetition mastery tracking." Direct inspection shows this isn't quite
right, and the distinction matters for this design:

- `scripts/difficulty_engine.py`'s `subtopic_difficulty` table has **no `user_id` column at
  all** — `get_difficulty(subtopic_id)` / `update_difficulty(subtopic_id, subject_id, accuracy)`
  operate on a single global tier per subtopic, shared across every user. This is a **question
  difficulty calibration** mechanism (crowd-sourced, matches the already-locked B-3 decision to
  keep it global) — orthogonal to personalization, not a form of it.
- The actual per-user SM-2 implementation is `backend/services/srs.py`'s
  `compute_srs_update()`, writing `ease_factor`/`interval_days`/`repetition_count`/
  `next_review_at` into `user_question_log` (which **is** keyed by `user_id`, per-question).
  This — not `difficulty_engine.py` — is the real prior art for a per-user mastery signal, and
  it already includes a confidence modifier (`sure`+wrong penalized harder than `guess`+wrong)
  that's more sophisticated than RBI's current `rbi_topic_mastery` (plain correct/attempts
  ratio, no confidence weighting).

This is exactly the kind of thing dev-protocol Rule 2 (verify before building) and this
project's own DECIDE-13 precedent (RBI-is-MCQ) exist to catch — worth stating plainly rather
than silently building on a description that doesn't match the code.

### The signal: a view, aggregating `user_question_log` up to topic level

```sql
CREATE VIEW user_topic_mastery AS
SELECT
    uql.user_id,
    qb.exam_source,
    qb.subject_id,
    qb.topic_id,
    qb.subtopic_id,
    COUNT(*)                                                   AS attempts,
    SUM(CASE WHEN uql.is_correct THEN 1 ELSE 0 END)            AS correct,
    AVG(CASE WHEN uql.is_correct THEN 1.0 ELSE 0.0 END)        AS raw_accuracy,
    AVG(uql.ease_factor)                                       AS avg_ease_factor,
    -- recency/confidence-aware mastery: weights each attempt by how many successful
    -- repetitions it has survived (repetition_count), same spirit as SM-2's own intent
    SUM(CASE WHEN uql.is_correct THEN 1.0 ELSE 0.0 END
        * (0.5 + 0.5 * MIN(uql.repetition_count, 5) / 5.0)) / COUNT(*)   AS mastery_score
FROM user_question_log uql
JOIN question_bank qb ON qb.id = uql.question_id
WHERE uql.skipped = 0
GROUP BY uql.user_id, qb.exam_source, qb.subject_id, qb.topic_id, qb.subtopic_id;
```

### View vs application code — the actual argument, not the default

**Chosen: a SQL view, in each product's own database, one per product (not one shared table
spanning products).** Two separate questions were tangled together in the task brief and need
separating:

1. *Should the computation be SQL or Python?* **SQL.** It's pure relational aggregation — no
   external I/O, no LLM call, no branching logic that doesn't fit `CASE WHEN`. This is squarely
   what a view is for, and it directly serves Rahul's stated goal (`PERSONALIZATION_PLAN.md`
   §1–2): a view is something he can `SELECT * FROM user_topic_mastery WHERE user_id = ...`
   himself in his analyst role, and — critically — **redefine himself** with
   `CREATE OR REPLACE VIEW` if he wants to try a different weighting formula, with no deploy, no
   Python change, no Claude session needed. Application code would require every formula
   iteration to go through a code change and redeploy — directly working against the stated
   goal of Rahul tuning this hands-on. It also matches the precedent Arena already set: its
   leaderboard is "a computed query, not cached" (`FOUNDATION.md`) — this product family already
   treats "read-time SQL aggregate" as the default shape for a personalization/ranking signal,
   not an exception.
2. *Should there be one shared table/view Arena and Scribe both read?* **No — this is the part
   that doesn't work, and inventing it would be wrong, not just unnecessary.** Recall, Scribe,
   and Arena have three disjoint user-identity spaces today (Arena's DECIDE-02 is explicit that
   this is deliberate). A `user_topic_mastery` row keyed by a Recall `user_id` has no defined
   meaning for a Scribe or Arena user — there is no join key. Solving that would mean solving
   cross-product identity linking first, which `DECIDE-09` already scoped out as future work,
   not something this redesign should quietly smuggle in via a shared-signal table.

**What "owned by Recall, consumed by multiple products" therefore actually means:** Recall owns
the *canonical formula* (the view definition above, plus a short written spec of the weighting
rationale) as the reference implementation. Each product that needs its own version of this
signal — Scribe for RBI, Arena for competitions — implements the **same formula** as a native
view over **its own** attempt table, in its own database engine's dialect:

- Scribe's existing `rbi_topic_mastery` already computes something structurally equivalent
  (accuracy over attempts, weighted by `base_weight`/coverage) — it should be *upgraded* to
  match Recall's formula shape (add the recency/repetition weighting `user_question_log` uses,
  if Scribe starts tracking an equivalent `repetition_count` per RBI question) rather than
  replaced outright — no reason to throw away working code that already does 80% of this.
- Arena computes its own view over its own Postgres `attempts` table (same weighting logic,
  Postgres dialect — window functions and `CASE WHEN` translate directly), keyed by Arena's own
  `user_id`. This is exactly what `PERSONALIZATION_PLAN.md` already anticipated ("reuse Recall's
  `difficulty_engine.py` and Scribe's `rbi_topic_mastery` math rather than reinventing") — this
  plan corrects *which* Recall code is the right thing to reuse (§ above) and makes the reuse
  concrete (the view SQL, not just "the math" in the abstract).

**How this actually changes what gets served — no contract change needed.** Contract 1.1
(`GET /internal/v1/questions`) already accepts a `topic` filter. Arena's `start` handler already
decides which filters to pass. Personalization is: Arena queries its own `user_topic_mastery`
view for the calling user, picks their 2–3 weakest topics, and passes those as `topic` filter
values across a few calls (or a widened single call) instead of a flat unweighted draw. Same
story for Scribe's `get_smart_questions()` — it already does exactly this today, using
`rbi_topic_mastery.flag_impact`; post-PLAN-008 migration it does the identical thing, just
against topic weights now sourced from Recall's `topic_weights` table (PLAN-007) via the
internal API instead of a local join. **No new subsystem, no contract change — a signal feeding
a parameter that already exists**, exactly as `PERSONALIZATION_PLAN.md` already concluded for
Arena; this plan extends that conclusion to Recall being the reference implementation multiple
products copy, rather than leaving "the math" underspecified.

## 4. Phased build order

Ordered so nothing is built twice and nothing blocks on the wrong prerequisite. Each phase
states what it's genuinely gated on.

**Phase 0 — PLAN-007 schema (no Rahul dependency to *design*; execution needs B-11 approval).**
Write the batched ALTER TABLE + 3 new tables + the `status` column addition noted in §1.C above.
Not blocked on B-1/B-2 (Supabase) or B-4 (`sar_scores`) — purely additive to a DB that already
exists, same reasoning Arena's Phase 1 used for its own additive routes.

**Phase 1 — PLAN-008 RBI migration, §2–3 (copy + feature flag), gated on Phase 0 done +
B-11 approved, and additionally B-12 approved for Scribe's `rbi_attempts.source` column.**
Two independent approval gates, both must clear before this phase's cutover (not just the copy)
can go live — the copy itself (read from `rbi.db`, write to Recall's `question_bank`) can start
the moment B-11 is approved, even before B-12, since the copy doesn't touch `rbi_attempts` at
all; only the cutover flag flip needs B-12.

**Phase 2 — Internal API auth generalization (PLAN-008 §4).** Pure code, additive, no schema —
can run in parallel with Phase 1, no dependency either direction except that Scribe's client
(Phase 1's cutover) needs a registered `SCRIBE_RBI` key to call with.

**Phase 3 — Scribe cutover rollout (PLAN-008 §3 staged rollout + §6 thin-proxy).** Gated on
Phase 1 + Phase 2. Two sub-tracks that can run in parallel with each other: (a) Scribe's own
`rbi_prep_bp.py` cutover for its live users, staged per PLAN-008 §3; (b) `internal_api_bp.py`
becoming a thin proxy for Arena's benefit, per PLAN-008 §6 — deliberately sequenced to not risk
Arena's already-working Phase 4 while (a) is still being validated, so (b) should not start
until (a)'s staged rollout has cleared its dev/local verification step, even though nothing
*technically* forces that order.

**Phase 4 — Ingestion pipelines, buckets A/B/D (§1).** Independent of Phases 1–3 entirely —
these are new content for both RBI and UPSC-adjacent tracks and don't depend on RBI's *existing*
321 questions having moved anywhere. Only real dependency: Phase 0's schema (`source_type` etc.
must exist to tag anything correctly). Gated additionally on: (a) verify-before-build research
on whether bucket A even applies to RBI (§1.A); (b) Rahul confirming a source allowlist for
bucket D beyond the defaults named in §1.D, if he wants more domains than the ones in this plan.

**Phase 5 — Bucket C (AI current-affairs), gated on Phase 4's bucket D having ingested at least
one month of source documents to generate from** — bucket C cannot run meaningfully with zero
grounding material. First real batch should be treated as a dry run against §2's quality gate,
not shipped straight to `active`.

**Phase 6 — Personalization signal (§3).** Gated on real attempt volume existing to compute
over — per `PERSONALIZATION_PLAN.md`'s own explicit caution, a mastery score from 2 attempts is
noise. Practically: sequence this after Phase 3's RBI cutover has been live long enough to
accumulate real `rbi_attempts`/`user_question_log` rows, and after Arena's own UPSC/RBI tracks
(already in Arena's separate `IMPLEMENTATION_PLAN.md` Phase 2/4) have real `attempts` rows.
Nothing in Phases 0–5 depends on Phase 6 — it is purely additive read-side value once there's
data worth reading.

**Honest cross-plan dependency summary:**
```
PLAN-007 (schema)
  │  [B-11 approval]
  ├──► PLAN-008 copy (rbi_questions → question_bank)          [no further Rahul gate]
  │       │ [B-12 approval]
  │       └──► PLAN-008 cutover flag + staged rollout
  │                └──► internal_api_bp.py thin-proxy (sequenced after, not blocked by)
  ├──► Ingestion buckets A/B/D  (independent of RBI migration entirely)
  │       └──► Bucket C (needs ≥1 month of bucket-D documents)
  └──► Personalization view (needs real attempt volume from RBI cutover AND/OR Arena's own tracks)

Internal API auth generalization: parallel to everything, feeds PLAN-008's cutover as a
prerequisite for the client to authenticate with.
```

## 5. New DECIDE / RISK / blocker items surfaced by this design

Logged in `SPRINT_BOARD.md`'s existing table conventions (`B-#` blockers, `INFRA DECISIONS
LOCKED` table) — see cross-file update accompanying this plan set, not duplicated here in full.
Summary for context:

- **B-11** — approve PLAN-007's batched `question_bank` ALTER + 3 new tables.
- **B-12** — approve PLAN-008's `rbi_attempts.source` column ALTER (live-user table).
- **B-13** — confirm whether RBI Grade B has an official-PYQ-with-answer-key source at all
  (§1.A) before building that ingestion path for RBI.
- **New risk** — `rbi.db`'s original tables must never be deleted, indefinitely, not just during
  an initial migration window, because historical `rbi_attempts` rows depend on them remaining
  queryable for as long as anyone might review old attempt history (PLAN-008 §3, §7).
- **New risk** — the AI current-affairs bucket's mandatory 10-sample-per-batch manual review
  (§2) depends on Rahul's own review bandwidth; a monthly cadence is chosen specifically to keep
  this sustainable, but a faster cadence later would need either more of his time or a change to
  the gate itself — not a reason to weaken the gate now.
