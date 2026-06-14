# Plan: PYQ Explanations as Paid Content
_Priority: P1 — strong Pro upgrade driver_
_Created: 2026-05-30_
_Depends on: pyq_data_foundation.md (official correct answers required before generating explanations)_

## Goal

Pre-generate a structured explanation for every PYQ that covers:
1. **Concept tested** — what principle/fact makes the correct answer right
2. **Wrong option analysis** — what concept each distractor tests and why it's wrong
3. **Memory hook** — one sharp, memorable line to lock the concept

Gate explanations behind the Pro tier. Free users see the correct answer; Pro users get the full concept closure card.

---

## Why this beats coaching platforms

Current market standard: "Correct answer is B. [2-line explanation]"

Our card:
```
✅ CORRECT: B — Article 356

CONCEPT TESTED
President's Rule is imposed under Article 356 when constitutional machinery
of a state breaks down. The 44th Amendment (1978) added mandatory Parliamentary
approval within 2 months.

WHY EACH OPTION IS WRONG
A — Article 352: National Emergency (external aggression / armed rebellion).
    Common mix-up — both are emergency provisions, different triggers.
C — Article 360: Financial Emergency. Tests financial vs constitutional breakdown.
D — Article 370: Special status of J&K (now abrogated). Included as a
    number-proximity distractor for students who memorise without understanding.

LOCK IT
"352=War, 356=State breakdown, 360=Finance. The number sequence matches severity."
```

This is the "stop going to coaching for one question" feature. Users who engage with this card once will never get the question wrong again.

---

## Cost to Generate

Token estimates: avg question ~350 input tokens, ~420 output tokens (4 sections).

| Model | Batch API (50% off) | Total for 1,081 PYQs | In ₹ |
|-------|--------------------|-----------------------|------|
| Haiku | ~$0.97 | ~$0.97 | ~₹81 |
| Sonnet | ~$3.65 | ~$3.65 | ~₹305 |

**Recommendation: Haiku.** UPSC MCQ topics (polity, history, economy, geography) are well within Haiku's knowledge. Sonnet for edge cases only. One-time cost, serve forever.

When 2009–2013 PYQs are added (~500 more questions, total ~1,600):
- Haiku Batch total: ~$1.45 (≈₹121) — still negligible.

---

## DB Schema

```sql
CREATE TABLE question_explanations (
    question_id       INTEGER PRIMARY KEY REFERENCES pyq_questions(id),
    concept_tested    TEXT NOT NULL,
    correct_explanation TEXT NOT NULL,
    option_a_note     TEXT,
    option_b_note     TEXT,
    option_c_note     TEXT,
    option_d_note     TEXT,
    memory_hook       TEXT,
    model_used        TEXT NOT NULL DEFAULT 'claude-haiku-4-5-20251001',
    generated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    version           INTEGER NOT NULL DEFAULT 1
);
```

No user_id — explanations are shared across all users. One row per question.

---

## Prompt Design

**File: `prompts/pyq_explanation.txt`**

```
You are a UPSC Prelims expert explainer.

For the given question and official correct answer, produce a structured JSON explanation that will help an aspirant understand WHY the correct answer is right AND why each wrong option is wrong — so they never get confused on this concept again.

Rules:
- Be precise and concise. No padding.
- For each wrong option: name the concept it tests, not just "this is wrong"
- The memory hook must be one short, memorable line — use patterns, mnemonics, or contrast
- Assume the reader has basic UPSC preparation knowledge

Return ONLY valid JSON:
{
  "concept_tested": "...",
  "correct_explanation": "...",
  "option_a_note": "...",
  "option_b_note": "...",
  "option_c_note": "...",
  "option_d_note": "...",
  "memory_hook": "..."
}

The note for the correct answer's option should explain why it is specifically right (not just "this is correct").
```

---

## Generation Script

**New file: `scripts/generate_pyq_explanations.py`**

Pattern: identical to `Descriptive-exams/scripts/generate_answers.py` — Anthropic Batch API + local JSONL cache.

```python
CACHE_DIR = Path(__file__).parent.parent / "cache" / "pyq_explanation_results"
BATCH_ID_FILE = Path(__file__).parent.parent / "data" / "pyq_explanations_batch.txt"

def load_pending(conn) -> list[dict]:
    """Questions with official correct_answer but no explanation yet."""
    return conn.execute("""
        SELECT p.id, p.question_text, p.correct_answer,
               p.option_a, p.option_b, p.option_c, p.option_d,
               p.subject_id, p.topic_id
        FROM pyq_questions p
        LEFT JOIN question_explanations e ON p.id = e.question_id
        WHERE p.correct_answer IS NOT NULL
          AND p.answer_source = 'official'
          AND e.question_id IS NULL
        ORDER BY p.year DESC
    """).fetchall()
```

Same pattern as generate_answers.py:
1. Load pending questions (no explanation yet)
2. Build batch requests (one per question)
3. Submit via `client.messages.batches.create()`
4. Save batch_id to BATCH_ID_FILE
5. Poll until ended
6. Stream results → JSONL cache → parse → INSERT OR IGNORE into question_explanations
7. Validate: print count by subject

**CLI:**
```bash
cd scripts && python generate_pyq_explanations.py
cd scripts && python generate_pyq_explanations.py --subject polity  # single subject
cd scripts && python generate_pyq_explanations.py --year 2024        # single year
```

---

## API Endpoint

**Add to `backend/routes/pyq.py`:**

```python
@router.get("/explanation/{question_id}")
def get_explanation(question_id: int):
    """Returns pre-generated explanation for a PYQ. Zero API calls."""
    row = db.execute(
        "SELECT * FROM question_explanations WHERE question_id = ?", (question_id,)
    ).fetchone()
    if not row:
        return {"available": False}
    return {"available": True, **dict(row)}
```

---

## Frontend: Explanation Card

**Component: `web/src/components/ExplanationCard.tsx`**

Appears in the PYQ Browser after user submits an answer and correct answer is revealed.

```
┌─────────────────────────────────────────────────────┐
│ 📖 CONCEPT EXPLANATION                    [Pro] ✨   │
├─────────────────────────────────────────────────────┤
│ CONCEPT TESTED                                       │
│ [concept_tested text]                                │
│                                                      │
│ WHY EACH OPTION IS WRONG                             │
│ A — [option_a_note]                                  │
│ B — ✅ [correct_explanation]   ← correct option      │
│ C — [option_c_note]                                  │
│ D — [option_d_note]                                  │
│                                                      │
│ 🔒 LOCK IT                                           │
│ "[memory_hook]"                                      │
└─────────────────────────────────────────────────────┘
```

**Free user view:** Card is blurred with overlay: "Unlock full explanations with Pro — ₹3,999/year"

**Implementation:**
- Check `user.tier === 'pro'` (from auth context once public platform is live)
- For now (local/personal use): always show full card (no gating needed until multi-user)
- `answer_disputed` = true → show ⚠️ banner: "Note: UPSC's answer for this question has been disputed. [dispute_note]"

---

## Files to Create/Modify

| File | Action | Notes |
|------|--------|-------|
| `prompts/pyq_explanation.txt` | Create | Explanation prompt |
| `scripts/generate_pyq_explanations.py` | Create | Batch generation script |
| `backend/routes/pyq.py` | Modify | Add GET /explanation/{id} endpoint |
| `web/src/components/ExplanationCard.tsx` | Create | |
| `web/src/app/pyq/[year]/page.tsx` | Modify | Wire in ExplanationCard after answer reveal |

---

## Execution Order

1. ✅ Wait for `pyq_data_foundation.md` to be complete (official answers in DB)
2. Create prompt file (`prompts/pyq_explanation.txt`)
3. Build generation script
4. Run in Haiku Batch mode — ~2-3 hours processing time
5. Verify output: spot-check 20 explanations across subjects
6. Build ExplanationCard component
7. Wire into PYQ Browser

**Total build time:** ~6 hours
**API cost:** ~₹81 (Haiku Batch, one-time forever)
