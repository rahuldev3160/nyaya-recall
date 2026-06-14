# Plan: Multi-Exam Question Bank
_Priority: P1 — feeds all adaptive quizzes, diagnostics, simulations_
_Created: 2026-05-30_
_Depends on: pyq_data_foundation.md (schema + ingest pipeline already works)_

## Goal

Build a large, free, high-quality question bank by harvesting PYQs from other UPSC exams
(CDS, NDA, CAPF, CISF, CMS) and tagging them into the same subject/topic/subtopic taxonomy.

This bank feeds: diagnostic quizzes, simulations, adaptive question serving — everywhere the
user needs a question but it doesn't have to be a "Civil Services PYQ specifically."

**Why this before AI generation:** Real PYQs have official UPSC answer keys (free, zero cost,
authoritative). AI-generated questions have a cost and introduce answer reliability risk.
Exhaust the real PYQ bank first, then fill remaining gaps with AI.

---

## Volume Estimate (10-year lookback)

| Exam | Exams/year | GK/GS questions per paper | 10-year volume | Relevance to GS Prelims |
|------|-----------|--------------------------|----------------|------------------------|
| CDS (GK paper) | 2 | ~120 | **~2,400** | High — Polity, History, Geography, Economy, Science |
| NDA (GAT paper) | 2 | ~150 (GK portion ~50%) | **~1,500 GK** | High for GK sections; filter out Maths/English |
| CAPF (Paper I) | 1 | ~125 | **~1,250** | High — same subjects as Civil Services |
| CISF AC (GK) | 1 | ~100 | **~1,000** | Medium — slightly more current affairs heavy |
| CMS (Gen. Ability) | 1 | ~50 GK | **~500** | Medium — basic GK, good for easy difficulty level |
| Geoscientist | 1 | (specialized geology) | ~200 relevant | Low — useful for Geography/Environment only |

**Estimated total: ~6,500–7,000 relevant questions** before any AI generation.
Already have: ~860 AI-generated questions in the current system (migrateable to question_bank).

---

## DB Architecture

### Separation of concerns

| Table | Contents | Used by |
|-------|----------|---------|
| `pyq_questions` | Civil Services GS Prelims ONLY (2013–2025) | PYQ Browser feature |
| `question_bank` | All other questions: CDS/NDA/CAPF + AI-generated | Adaptive engine, diagnostics, simulations |

Both tables share the same subject/topic/subtopic taxonomy so the serving algorithm can draw
from either without knowing the source.

### `question_bank` schema

```sql
CREATE TABLE question_bank (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text  TEXT NOT NULL,
    option_a       TEXT NOT NULL,
    option_b       TEXT NOT NULL,
    option_c       TEXT NOT NULL,
    option_d       TEXT NOT NULL,
    correct_answer TEXT NOT NULL,       -- 'a'|'b'|'c'|'d'
    answer_source  TEXT NOT NULL,       -- 'official' | 'ai_generated'
    source_exam    TEXT NOT NULL,       -- 'cds'|'nda'|'capf'|'cisf'|'cms'|'geoscientist'|'ai'
    source_year    INTEGER,             -- exam year
    subject_id     TEXT NOT NULL,
    topic_id       TEXT,
    subtopic_id    TEXT,
    dimension_id   TEXT,
    difficulty     TEXT DEFAULT 'medium', -- 'easy'|'medium'|'hard'
    question_hash  TEXT UNIQUE,         -- SHA256 dedup
    times_served   INTEGER DEFAULT 0,
    times_correct  INTEGER DEFAULT 0,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_qb_subtopic ON question_bank(subtopic_id, times_served);
CREATE INDEX idx_qb_subject ON question_bank(subject_id, source_exam);
CREATE INDEX idx_qb_hash ON question_bank(question_hash);

-- Tracks per-user serving history (prevents repeats)
CREATE TABLE user_question_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT NOT NULL DEFAULT 'user_1',
    question_id  INTEGER NOT NULL,
    source_table TEXT NOT NULL DEFAULT 'question_bank', -- 'question_bank'|'pyq_questions'
    served_at    TEXT DEFAULT (datetime('now')),
    user_answer  TEXT,
    is_correct   INTEGER,
    time_taken_sec INTEGER
);
CREATE UNIQUE INDEX idx_uqh_user_question ON user_question_history(user_id, question_id, source_table);
```

---

## Ingestion Pipeline

### Step 1: Download exam papers + answer keys

From upsc.gov.in (all free, official):
- CDS I & II: GK paper, last 10 years (2015–2025)
- NDA I & II: General Ability Test, last 10 years — extract GK sections (Part B), skip Part A (Maths)
- CAPF Paper I: GK, last 10 years
- CISF AC GK paper, last 5–10 years

Naming convention for download:
```
pyq_source/cds/CDS_I_2023_GK.pdf
pyq_source/cds/CDS_I_2023_AnswerKey.pdf
pyq_source/nda/NDA_I_2023_GAT.pdf
pyq_source/nda/NDA_I_2023_AnswerKey.pdf
...
```

### Step 2: Adapt ingest_pyq.py for multi-exam

The current `ingest_pyq.py` already does: PDF → Claude Haiku → classify → SQLite.

Changes needed:
- Add `--exam` argument: `python ingest_pyq.py --exam cds --year 2023`
- Route to `question_bank` table instead of `pyq_questions`
- Pass exam context to `pyq_classify.txt` prompt: "This is a CDS exam GK paper. Questions may be simpler/more factual than Civil Services."
- Extract NDA Part B only (skip Part A which is Maths)
- Set `answer_source = 'official'` after importing answer key CSV (same import_answer_keys.py)

**Prompt tweak for non-Civil-Services exams:**
The `pyq_classify.txt` prompt asks for difficulty inference. For CDS/NDA, default difficulty should start at 'easy'/'medium' since these exams are generally less demanding than Civil Services Prelims.

### Step 3: Classification and tagging

Run `retag_pyq_subtopics.py` (already exists) on the new question_bank rows — maps question text to canonical subject/topic/subtopic IDs.

After tagging, run gap analysis:
```sql
SELECT subtopic_id, COUNT(*) as total
FROM question_bank
GROUP BY subtopic_id
ORDER BY total ASC
LIMIT 30;
```

Subtopics with < 10 questions in the bank → candidates for AI generation.

### Step 4: AI generation for gap-filling only

Run `scripts/generate_questions.py` (to be built, modelled on Descriptive-exams generate_answers.py):
- Input: list of (subtopic_id, target_count, difficulty)
- Only runs for subtopics below threshold (< 10 questions in bank)
- Uses Haiku Batch — ~$0.05 per 50 questions
- Stores with `answer_source = 'ai_generated'`, `source_exam = 'ai'`

**One-time AI generation budget for remaining gaps:** ~₹50–100

---

## Serving Algorithm (4 phases, pure SQL)

For diagnostic quiz / simulation / any "give me questions" request:

```sql
-- Phase 1: PYQs user hasn't seen (Civil Services, source_exam context)
SELECT q.id, 'pyq_questions' as source_table, q.question_text, ...
FROM pyq_questions q
LEFT JOIN user_question_history h 
    ON h.question_id = q.id AND h.source_table = 'pyq_questions' AND h.user_id = ?
WHERE q.subject_id = ? AND h.id IS NULL
ORDER BY q.year DESC
LIMIT ?

UNION ALL

-- Phase 2: question_bank unseen, lowest times_served first
SELECT q.id, 'question_bank' as source_table, q.question_text, ...
FROM question_bank q
LEFT JOIN user_question_history h 
    ON h.question_id = q.id AND h.source_table = 'question_bank' AND h.user_id = ?
WHERE q.subject_id = ? AND h.id IS NULL
ORDER BY q.times_served ASC
LIMIT ?

UNION ALL

-- Phase 3: previously wrong (spaced repetition)
SELECT q.id, h.source_table, q.question_text, ...
FROM user_question_history h
JOIN question_bank q ON q.id = h.question_id
WHERE h.user_id = ? AND h.is_correct = 0
ORDER BY h.served_at ASC  -- oldest wrong first
LIMIT ?
```

Phase 4 (generate new) only triggers if Phases 1–3 are exhausted for a subtopic.

---

## Relevance Filter for NDA/CDS

Not all questions from CDS/NDA map to Civil Services Prelims GS syllabus.

Filter OUT:
- NDA Part A (Mathematics entirely)
- CDS English paper
- Pure current affairs questions (date-bounded, expire quickly)
- Questions requiring lab/practical knowledge

Filter IN (keep):
- Polity, Constitution, Governance
- History (Ancient, Medieval, Modern)
- Geography (Physical, Human, Economic)
- Economy / Economic Development
- Environment & Ecology
- Science & Technology (general, not specialized)
- International Relations, Defence, Security

This filtering happens at classification time — the `pyq_classify.txt` prompt can include:
> "If this question is about mathematics, English language, or highly specialized technical knowledge outside UPSC GS syllabus, set subject_id to 'out_of_scope'."

Then filter `WHERE subject_id != 'out_of_scope'` when serving.

---

## Files to Create/Modify

| File | Action | Notes |
|------|--------|-------|
| `data/upsc.db` | Modify | Add question_bank + user_question_history tables |
| `scripts/ingest_pyq.py` | Modify | Add --exam flag, route to question_bank table |
| `scripts/import_answer_keys.py` | Modify | Accept source_table param (question_bank vs pyq_questions) |
| `scripts/generate_questions.py` | Create | AI gap-fill script, Haiku Batch |
| `backend/routes/quiz.py` | Modify | Rewrite generation to use serving algorithm |
| `prompts/pyq_classify.txt` | Modify | Add exam context, out_of_scope tag, difficulty default by exam |
| `scripts/audit_question_bank.py` | Create | Per-subtopic count, coverage heatmap |

---

## Execution Order

1. Phase 0 (pyq_data_foundation.md) must run first — establishes schema patterns + classification pipeline
2. Download CDS/NDA/CAPF PDFs (Rahul: ~2–3 hours, 10 years × 3 exams)
3. Add question_bank + user_question_history tables to DB
4. Adapt ingest_pyq.py for --exam flag
5. Run ingestion for CDS (largest, highest relevance first)
6. Run ingestion for NDA (filter Maths section)
7. Run ingestion for CAPF + CISF
8. Run retag on all new rows
9. Run audit_question_bank.py → identify gaps
10. Run generate_questions.py for gap subtopics only

**Estimated build time:** 1.5 days
**Data sourcing (Rahul):** 2–3 hours downloading PDFs
**API cost:** Zero for ingestion (reuses existing Haiku classify pipeline). ~₹50–100 for AI gap-fill only.
