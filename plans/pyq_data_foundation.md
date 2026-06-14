# Plan: PYQ Data Foundation
_Priority: P0 — must complete before any public launch work_
_Created: 2026-05-30_

## Goal

Get Civil Services GS Prelims PYQs **2013–2025** into the DB with:
- Correct question count per year (~100 for 2013–2025)
- Official UPSC correct answer for every question
- Cancelled questions tagged explicitly
- Disputed answers flagged with notes
- Year / subject / topic / subtopic all filled

**Scope decision:** 2013 onwards only. Years 2009–2012 are not needed for the public PYQ Browser feature. If needed later (e.g., for the wider question bank), they can be added to the `question_bank` table via `plans/multi_exam_bank.md` rather than `pyq_questions`.

---

## Current State (audited 2026-05-30)

Scope: 2013–2025 only (2009–2012 out of scope for pyq_questions table).

| Year | DB count | Expected | Gap | Answer coverage |
|------|----------|----------|-----|----------------|
| 2013 | 0        | ~100     | -100 | — |
| 2014 | **132**  | ~100     | +32 duplication | 62/132 (47%) |
| 2015 | 87       | ~100     | -13  | 57/87 (66%) |
| 2016 | 84       | ~100     | -16  | 44/84 (52%) |
| 2017 | 88       | ~100     | -12  | 68/88 (77%) |
| 2018 | **72**   | ~100     | -28  | 43/72 (60%) |
| 2019 | 98       | ~100     | -2   | 52/98 (53%) |
| 2020 | 76       | ~100     | -24  | 42/76 (55%) |
| 2021 | 91       | ~100     | -9   | 56/91 (62%) |
| 2022 | 76       | ~100     | -24  | 36/76 (47%) |
| 2023 | 71       | ~100     | -29  | 29/71 (41%) |
| 2024 | 84       | ~100     | -16  | 21/84 (25%) |
| 2025 | 92       | ~100     | -8   | 30/92 (33%) |
| year=0 | 30    | —        | tag needed | 23/30 |

**All current correct_answer values are AI-inferred by Claude Haiku — not from official UPSC keys.**

---

## UPSC Format Reference (2013–2025)

| Years | Format |
|-------|--------|
| 2013–2025 | 100 questions, 200 marks, 120 min |

Some years have 1–3 UPSC-cancelled questions (all 4 options get credit, effectively null correct answer).
UPSC publishes final answer keys (post-objection review) — those are the authoritative source.

---

## Step 1: DB Schema Changes

⚠️ **APPROVAL GATE** — ALTER TABLE on existing pyq_questions requires Rahul's explicit OK before running.

```sql
ALTER TABLE pyq_questions ADD COLUMN answer_source TEXT DEFAULT 'ai_inferred';
-- Values: 'official' | 'ai_inferred' | 'cancelled' | 'unverified'

ALTER TABLE pyq_questions ADD COLUMN answer_disputed INTEGER DEFAULT 0;
-- 1 if the UPSC answer has been challenged in court / objection period with strong grounds

ALTER TABLE pyq_questions ADD COLUMN dispute_note TEXT;
-- Free text: "HC petition filed 2019, objection upheld in revision" etc.

ALTER TABLE pyq_questions ADD COLUMN q_number INTEGER;
-- Question number within the year's paper (1–100 or 1–150)
-- Needed to match answer key rows to DB rows reliably
```

After adding columns, backfill existing rows:
```sql
UPDATE pyq_questions SET answer_source = 'ai_inferred' WHERE answer_source IS NULL AND correct_answer IS NOT NULL;
UPDATE pyq_questions SET answer_source = 'unverified' WHERE answer_source IS NULL AND correct_answer IS NULL;
```

---

## Step 2: Source Official Materials

### Question papers (for missing + incomplete years)
URL pattern: `https://upsc.gov.in/examinations/previous-year-question-papers`
- Section: Civil Services (Preliminary) → General Studies Paper I
- Download PDFs for 2013 (missing) and any gap years with < 95 questions
- Naming convention for ingest_pyq.py: match existing pattern (e.g. `01_Paper_2013.pdf`)

### Answer keys (2013–2025)
- URL pattern: same page, look for "Answer Keys" section
- UPSC publishes: Provisional Key → Final Key (after objection review)
- Always use the **Final Key** — some answers change after review
- Format: PDF table with Q_no | Correct Option columns
- Secondary sources (Vision IAS, Insights IAS answer key PDFs) acceptable if UPSC PDF is unavailable for older years

### Known disputed years (flag these for manual review)
- 2019 — several objection-period revisions, always use final key for that year
- Any year where total final answered count < 100 means cancellations occurred

---

## Step 3: Ingest Missing Year (2013)

1. Place downloaded 2013 GS Paper 1 PDF in `UPSC_CONTENT_PATH` directory
2. Run `scripts/ingest_pyq.py` for 2013
3. Verify count after ingestion:
   ```bash
   sqlite3 data/upsc.db "SELECT year, COUNT(*) FROM pyq_questions WHERE year = 2013"
   ```
4. Expect ~100 rows

Note: 2009–2012 PDFs are NOT ingested here. If they're needed for the question_bank (diagnostic use), that's handled separately in `plans/multi_exam_bank.md`.

---

## Step 4: Fix Incomplete Years (2015–2024)

The gap in these years is likely from OCR failures in original PDF ingestion. Two approaches:

**Option A (preferred):** Re-download better quality PDFs and re-ingest
- Re-run `ingest_pyq.py` with `INSERT OR IGNORE` on `question_hash` — won't duplicate
- Fills in the missing questions

**Option B:** Manual gap identification
- For each year, compare count to expected 100
- Export current questions for that year → identify which topic areas are absent → targeted ingest

**2014 duplication fix:**
```sql
-- Find duplicates by question_hash
SELECT question_hash, COUNT(*) as n FROM pyq_questions WHERE year=2014 GROUP BY question_hash HAVING n > 1;
-- Delete duplicates keeping lowest id
DELETE FROM pyq_questions WHERE year=2014 AND id NOT IN (
    SELECT MIN(id) FROM pyq_questions WHERE year=2014 GROUP BY question_hash
);
```
⚠️ Requires Rahul approval before running DELETE.

---

## Step 5: Build Answer Key Import Script

**New file: `scripts/import_answer_keys.py`**

Input: CSV file per year, format:
```
year,q_number,correct_answer,cancelled,dispute_note
2023,1,b,0,
2023,2,a,0,
2023,47,d,0,"UPSC revised in final key from 'c'"
2023,83,,1,"Cancelled — no single correct answer"
```

Script logic:
1. Load CSV
2. For each row:
   - Find matching DB row: `WHERE year = ? AND q_number = ?` (needs q_number column added in Step 1)
   - If cancelled: `SET correct_answer = NULL, answer_source = 'cancelled'`
   - If answer + dispute_note: `SET correct_answer = ?, answer_source = 'official', answer_disputed = 1, dispute_note = ?`
   - Otherwise: `SET correct_answer = ?, answer_source = 'official'`
3. Print summary: updated / skipped / not-found counts

**Challenge — matching by q_number:**
- The `q_number` column doesn't exist yet (Step 1 adds it)
- During ingest_pyq.py, question numbers must be captured from the PDF
- This requires updating `ingest_pyq.py` to extract and store q_number
- Alternative: match by question_hash if UPSC PDF question order is deterministic

---

## Step 6: Fix year=0 Rows (30 questions)

These 30 questions came from the `Microthemes_PYQs_2009-2025.pdf` compilation where year detection failed.

```python
# scripts/fix_year_zero.py
# For each year=0 question, send to Haiku with question text:
# "What year's UPSC Prelims exam is this question from? Return only the year as a 4-digit integer."
# Update year in DB
# Estimated cost: 30 questions × minimal tokens ≈ <$0.01
```

After fixing year, the 30 rows join their correct year buckets.

---

## Step 7: Validate Completeness

**New file: `scripts/audit_pyq_completeness.py`**

Output format:
```
Year  Expected  Actual  Gap   Answer Coverage  Disputed  Source
2009  150       150     0     150/150 (100%)   0         official
2010  150       149     -1    148/149 (99%)    1         official (1 cancelled)
...
2025  100       100     0     97/100 (97%)     0         3 cancelled
```

Pass criteria:
- Every year: actual ≥ expected - 5 (allow for confirmed UPSC cancellations)
- Every question: answer_source != 'ai_inferred' (all replaced with official/cancelled)
- No year=0 rows remaining

---

## Step 8: Subject / Topic / Subtopic Health Check

After all ingestion is done, verify classification coverage:
```sql
SELECT 
    year,
    COUNT(*) as total,
    SUM(CASE WHEN subject_id IS NULL THEN 1 ELSE 0 END) as missing_subject,
    SUM(CASE WHEN topic_id IS NULL THEN 1 ELSE 0 END) as missing_topic,
    SUM(CASE WHEN subtopic_id IS NULL THEN 1 ELSE 0 END) as missing_subtopic
FROM pyq_questions
GROUP BY year
ORDER BY year;
```

For any nulls in classification: run `retag_pyq_subtopics.py` (already exists, does fuzzy matching + Haiku fallback).

---

## Execution Order

1. Get Rahul approval for ALTER TABLE (Step 1) and DELETE duplication fix (Step 4)
2. Download PDFs + answer key CSVs (manual, Rahul does this):
   - 2013 question paper PDF
   - Official final answer keys for 2013–2025
3. Apply schema changes (ALTER TABLE)
4. Run ingest for 2013
5. Run fix_year_zero.py (~$0.01)
6. Build and run import_answer_keys.py for all years
7. Fix 2014 duplicates (DELETE with approval)
8. Re-ingest gap years (2015–2024 under 100 questions)
9. Run audit_pyq_completeness.py
10. Run retag_pyq_subtopics.py if null classification found

**Estimated build time (Claude Code):** 1 day
**Estimated data sourcing time (Rahul):** 1–2 hours (2013–2025 only; answer keys downloadable as PDFs)
**API cost:** ~$0.01 for year=0 fix via Haiku; zero for everything else
