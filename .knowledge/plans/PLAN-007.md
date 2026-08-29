---
id: PLAN-007
type: plan
project: devthorium
date: 2026-08-29
status: PROPOSED
---

# PLAN-007: Generalized multi-exam, multi-source, multi-format MCQ schema

**Scope note:** Architecture only. No code, no migration script execution. Written for a later
Sonnet-driven implementation pass to build against directly.

## Why this has to happen before PLAN-008 (RBI migration)

`question_bank` today (`backend/server.py::_ensure_question_bank_tables`) has `exam_source`,
`subject_id`/`topic_id`/`subtopic_id`, `answer_source`/`answer_disputed`/`dispute_note`,
`is_evergreen`/`expires_after_year` — real prior art, but built for one shape: a single bulk
import of third-party test-series content (`vision_ias`, 5,181 rows, the only `exam_source`
value that actually exists today) plus AI gap-fill for cross-exam PYQs. There is no column that
answers "where did this specific row come from, in the sense of official-PYQ vs similar-exam vs
AI-current-affairs vs document-derived" — `answer_source` tracks *how the correct answer was
established*, a different axis entirely.

If RBI's 321 questions are copied into `question_bank` as-is (PLAN-008) before this schema
lands, every RBI row would need a second ALTER-and-backfill pass once provenance tracking is
added — the exact "build before verifying the real shape" mistake this session already caught
once (DECIDE-13, RBI-is-MCQ correction). This plan is the schema; PLAN-008 assumes it is already
migrated.

## Decision: extend `question_bank` with new columns + two new tables, not a parallel content model

**Rejected: a fully separate content model per source type (e.g. `official_pyq_bank`,
`ai_current_affairs_bank`, ...).** Every consumer (`/internal/v1/questions`, the SRS log, the
daily-challenge picker, Arena's Contract 1) already queries one table by `(exam_source,
subject_id, topic_id, subtopic_id)`. Splitting by source type would force every one of those
call sites to `UNION` N tables just to answer "give me 20 RBI monetary-policy questions,
I don't care where they came from" — which is the *normal* query shape (a learner drilling a
topic, or Arena assembling a competition, doesn't care about provenance; provenance is a
research view, not a serving view). `question_bank` already generalizes serving; provenance
should be columns on the row being served, plus link tables for the parts that genuinely have
their own lifecycle (a source document; a generation run).

**Chosen — one ALTER TABLE batch + two new tables:**

```sql
-- Columns added to question_bank (single migration, see "Approval gate" below)
ALTER TABLE question_bank ADD COLUMN source_type TEXT NOT NULL DEFAULT 'unclassified_legacy';
  -- enum (enforced in application code, SQLite has no native CHECK-enum-add-later):
  -- 'official_pyq' | 'similar_exam_pyq' | 'ai_current_affairs' | 'ai_gap_fill'
  -- | 'third_party_bank' | 'official_document_derived' | 'unclassified_legacy'
  -- 'unclassified_legacy' exists ONLY as the default for rows that predate this column
  -- (today's 5,181 vision_ias rows become 'third_party_bank' on backfill; existing
  -- cross-exam AI gap-fill rows become 'ai_gap_fill' — see backfill note below).
ALTER TABLE question_bank ADD COLUMN source_ref TEXT;              -- JSON, shape varies by source_type (below)
ALTER TABLE question_bank ADD COLUMN source_document_id TEXT REFERENCES source_documents(id);
ALTER TABLE question_bank ADD COLUMN generation_batch_id TEXT REFERENCES generation_batches(id);
ALTER TABLE question_bank ADD COLUMN question_format TEXT NOT NULL DEFAULT 'single_correct';
  -- 'single_correct' | 'statement_based' | 'assertion_reason' | 'match_following' | 'multi_select'
ALTER TABLE question_bank ADD COLUMN default_marks REAL NOT NULL DEFAULT 2.0;
  -- data-driven per-row marks value — replaces internal_arena.py's hardcoded
  -- _DEFAULT_MARKS_PER_QUESTION=2.0, which is wrong for RBI (1 mark) the moment RBI content lands.
ALTER TABLE question_bank ADD COLUMN retired_at TEXT;              -- NULL = active; never DELETE, see PLAN-009 §2
ALTER TABLE question_bank ADD COLUMN superseded_by TEXT REFERENCES question_bank(id);
  -- self-reference: a fact-based question a later event made stale (e.g. repo rate changed)
  -- points to its replacement without breaking any attempt that already references the old id.

CREATE TABLE source_documents (
    id             TEXT PRIMARY KEY,
    doc_type       TEXT NOT NULL,   -- 'rbi_circular' | 'rbi_master_direction' | 'rbi_press_release'
                                     -- | 'pib_release' | 'ministry_press_note' | 'budget_document'
                                     -- | 'economic_survey' | 'gazette_notification'
    title          TEXT NOT NULL,
    source_url     TEXT NOT NULL,   -- must resolve to an allowlisted official domain, see PLAN-009 §3
    publish_date   TEXT,
    ingested_at    TEXT DEFAULT (datetime('now')),
    exam_source    TEXT NOT NULL,   -- which track this document feeds
    raw_text_ref   TEXT,            -- path to the extracted text blob, not stored inline
    content_hash   TEXT UNIQUE      -- de-dupe re-ingestion of the same circular
);

CREATE TABLE generation_batches (
    id                TEXT PRIMARY KEY,
    batch_date        TEXT NOT NULL,
    exam_source       TEXT NOT NULL,
    source_month      TEXT,          -- e.g. '2026-07', for the current-affairs bucket
    model             TEXT NOT NULL,
    prompt_version    TEXT NOT NULL,
    review_status     TEXT NOT NULL DEFAULT 'draft',  -- 'draft' | 'sample_reviewed' | 'published' | 'retired'
    reviewed_by       TEXT,          -- 'rahul' once sample review happens — see PLAN-009 §3 gate
    question_count    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE topic_weights (
    exam_source   TEXT NOT NULL,
    subject_id    TEXT NOT NULL,
    topic_id      TEXT NOT NULL,
    subtopic_id   TEXT NOT NULL,
    base_weight   REAL NOT NULL,
    weight_source TEXT NOT NULL DEFAULT 'manual',   -- 'manual' | 'pyq_frequency_computed'
    PRIMARY KEY (exam_source, subject_id, topic_id, subtopic_id)
);
```

**Why `topic_weights` is new rather than reusing `priority_scorer.py`'s existing PYQ-frequency
weighting:** that script computes weight purely from `Σ(0.9^(years_ago))` — it needs PYQ history
to exist. `rbi_topic_weights` (Scribe, `base_weight` column) is *manually curated* — someone
decided monetary policy matters more than, say, one obscure NBFC sub-rule, independent of how
many times it appeared in a PYQ, because RBI Grade B doesn't have UPSC's 15-year PYQ depth to
compute frequency from in the first place. Generalizing this as `weight_source` lets UPSC keep
its PYQ-computed weights (`weight_source='pyq_frequency_computed'`, populated by the existing
script, unchanged) while RBI (and any future exam without a deep PYQ archive) uses manually-set
weights — same table, same consumer query shape, two legitimate ways to fill it in.

### `source_ref` JSON shapes (documented, not DB-enforced — SQLite has no native JSON schema)

| `source_type` | `source_ref` example |
|---|---|
| `official_pyq` | `{"year": 2024, "paper": "GS1", "q_number": 47}` — reuses existing `year`/`paper`/`q_number` columns as the primary fields; `source_ref` only needed when a source has no natural (year, paper, q_number) tuple. |
| `similar_exam_pyq` | `{"source_exam": "sebi_grade_a", "year": 2023, "q_number": 12}` |
| `ai_current_affairs` | `{"source_month": "2026-07", "generation_batch_id": "gb_2026_07_rbi"}` (redundant with the FK column, kept for quick inspection without a join) |
| `official_document_derived` | `{}` — provenance lives in `source_document_id`, this stays empty |
| `third_party_bank` | `{"vendor": "vision_ias"}` |

### Concrete examples per exam, per source type (per task requirement)

| Source type | RBI Grade B | UPSC-adjacent |
|---|---|---|
| Official PYQ | **Unconfirmed — flag to Rahul.** RBI does not publish Phase 1 objective papers with an official answer key the way UPSC does; verify before building this ingestion path for RBI at all (dev-protocol Rule 2 — official source first, don't assume). | UPSC Prelims official Final Answer Keys, 2013–2025 (already Sprint 1's target — `pyq_questions` table, separate from `question_bank` per PLAN-001) |
| Similar-exam PYQ | NABARD Grade A, SEBI Grade A, IBPS SO (Finance/Economics), UPSC EPFO | CDS / NDA / CAPF / CISF (already built — `ingest_cross_exam.py`) |
| AI-generated current affairs (evolving) | Monthly batch off RBI monetary policy statements, repo-rate decisions | Monthly batch off PIB/ministry releases relevant to GS Prelims |
| Official communication documents | RBI circulars, Master Directions, MPC press releases (rbi.org.in) | PIB releases, ministry press notes, Economic Survey, Union Budget documents, gazette notifications |

## Multi-format support

`question_format` is a rendering/generation hint, not a structural rewrite of the 4-option
schema — UPSC-style "which of the statements is/are correct" and assertion-reason questions
still resolve to one of 4 lettered options (the *combination*, e.g. "1 and 2 only"), so
`option_a`–`option_d` stay as-is. A `statements` JSON column (nullable, additive) is a
**Phase-2, non-blocking nice-to-have** — it would let the frontend render "Statement 1 / 2 / 3"
as a structured list instead of one text blob, but nothing in the current serving path breaks
without it. Not included in the batched ALTER above to keep that migration's blast radius
minimal; add it later as its own single-column ALTER if the frontend team actually wants
structured rendering.

## Backfill for existing rows (part of the same migration, not a separate approval)

```sql
UPDATE question_bank SET source_type = 'third_party_bank', source_ref = '{"vendor":"vision_ias"}'
  WHERE exam_source = 'vision_ias';
UPDATE question_bank SET source_type = 'similar_exam_pyq'
  WHERE exam_source IN ('cds', 'nda', 'capf', 'cisf') AND answer_source != 'ai_inferred';
UPDATE question_bank SET source_type = 'ai_gap_fill'
  WHERE exam_source IN ('cds', 'nda', 'capf', 'cisf') AND answer_source = 'ai_inferred';
-- Anything left at 'unclassified_legacy' after this is a genuine unknown — do not guess further.
```

## Approval gate (flag to Rahul before executing)

Per this project's own `CLAUDE.md` ("Any ALTER TABLE ... on existing DB tables" requires
explicit sign-off): the 8-column `question_bank` ALTER + the 3 new `CREATE TABLE`s above should
be **one batched migration, one approval ask** — not eight separate asks across phases. Logged
as **B-11** in `SPRINT_BOARD.md` (see cross-file update). This is additive-only to Recall's own
DB (not yet publicly live, no real end users on it yet per Sprint 2 status) — lower stakes than
the Scribe-side ALTER in PLAN-008, but the same gate applies mechanically regardless of live-user
exposure, per the project's own stated rule, not by my judgment call.

## What this does NOT touch

`sar_scores` (B-4) — unrelated table, no column here references it, no write path here touches
it. `pyq_questions` (the separate Civil-Services-Prelims-only table per PLAN-001's two-table
architecture) — untouched; that table's own pending ALTER (B-3/B-6 in `SPRINT_BOARD.md`) is
independent of this one and should not be conflated into the same approval ask.
