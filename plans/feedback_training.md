# Spec: Real-Time Feedback and Prompt Training

**Status:** Spec — awaiting Rahul approval before implementation  
**Priority:** P1  
**Linked issues:** ISSUE (unnamed — note-taking as training data), ISSUE (note-taking box resets per question), ISSUE (notes coverage weak on core concept)  
**Effort estimate:** ~18 hours across 3 phases  
**Depends on:** `plans/question_feedback.md` (shares `question_feedback` table — do not duplicate)  
**Unlocks:** Self-improving prompts, indexed personal notes per question, richer training signal

---

## 1. Relationship to `plans/question_feedback.md`

`question_feedback.md` already specifies structured signal capture (difficulty rating, quality flag, session-level feedback) and the `question_feedback` and `session_feedback` tables. **This spec does not duplicate that.** Instead this spec adds:

1. A richer **content feedback** layer (what was correct / what was missing / what was wrong in the generated content itself — question text, explanation, notes section)
2. **Per-question note reset and autosave** (currently notes are one blob per session, not per question)
3. The **prompt improvement pipeline** — a script that reads aggregated feedback and produces actionable prompt patches
4. Storage design for querying feedback by subject, subtopic, and content block type

Implement `question_feedback.md` first (or in parallel). The new tables here reference `session_answers.id` the same way.

---

## 2. Schema Additions

Two new tables. Never ALTER existing tables — only CREATE IF NOT EXISTS.

### 2a. `content_feedback`

Captures Rahul's qualitative verdict on any generated content block (a question's explanation, a notes section, an entire question).

```sql
CREATE TABLE IF NOT EXISTS content_feedback (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             TEXT    NOT NULL DEFAULT 'user_1',

    -- What content this feedback applies to
    content_type        TEXT    NOT NULL,  -- 'question' | 'explanation' | 'notes_section'
    session_id          TEXT    NOT NULL,
    question_hash       TEXT,              -- set when content_type in ('question','explanation')
    subtopic_id         TEXT    NOT NULL,
    subject_id          TEXT    NOT NULL,
    notes_section       TEXT,              -- set when content_type='notes_section':
                                           --   'core_concept' | 'pyq_angles' |
                                           --   'current_affairs' | 'broader_linkages'

    -- Verdict (user picks exactly one)
    verdict             TEXT    NOT NULL,  -- 'correct' | 'missing' | 'omit' | 'wrong'

    -- Optional free text (max 2000 chars, user-typed)
    note_text           TEXT    DEFAULT '',

    -- Prompt file this feedback should feed into (set by backend, not user)
    prompt_file         TEXT,              -- e.g. 'diagnostic_quiz.txt', 'session_notes.txt'

    created_at          TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cf_subtopic   ON content_feedback(subtopic_id, content_type);
CREATE INDEX IF NOT EXISTS idx_cf_subject    ON content_feedback(subject_id, verdict);
CREATE INDEX IF NOT EXISTS idx_cf_qhash      ON content_feedback(question_hash);
CREATE INDEX IF NOT EXISTS idx_cf_prompt     ON content_feedback(prompt_file, verdict);
```

**Verdict meanings:**

| verdict | Label shown to Rahul | Meaning |
|---------|---------------------|---------|
| `correct` | Looks good | Content is accurate and well-framed |
| `missing` | Something's missing | Concept, angle, or fact should have been included |
| `omit` | Should be omitted | Content is irrelevant, distracting, or too obscure |
| `wrong` | Factually incorrect | Content contains an error |

`prompt_file` is set server-side based on `content_type`:
- `content_type = 'question'` or `'explanation'` → `diagnostic_quiz.txt` (or `adaptive_session.txt` for session questions)
- `content_type = 'notes_section'` → `session_notes.txt`

### 2b. `question_notes`

Replaces the current single-blob `session_user_notes` design with per-question notes. The existing `session_user_notes` table is kept for backward compatibility.

```sql
CREATE TABLE IF NOT EXISTS question_notes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             TEXT    NOT NULL DEFAULT 'user_1',
    session_id          TEXT    NOT NULL,
    question_hash       TEXT    NOT NULL,
    question_index      INTEGER NOT NULL,
    subtopic_id         TEXT    NOT NULL,
    subject_id          TEXT    NOT NULL,
    note_text           TEXT    DEFAULT '',
    still_weak          INTEGER DEFAULT 0,
    updated_at          TEXT    DEFAULT (datetime('now')),
    UNIQUE(session_id, question_hash)
);

CREATE INDEX IF NOT EXISTS idx_qn_session    ON question_notes(session_id);
CREATE INDEX IF NOT EXISTS idx_qn_subtopic   ON question_notes(subtopic_id, still_weak);
CREATE INDEX IF NOT EXISTS idx_qn_qhash      ON question_notes(question_hash);
```

**Why a separate table (not columns on `session_answers`):** `question_notes` may be updated many times before the session closes (autosave on every keystroke after 700 ms debounce). `session_answers` is write-once per question. Keeping them separate preserves the immutability of scoring data.

---

## 3. UI Design

### 3a. Per-Question Inline Feedback (after answer reveal)

Location: below the explanation block, above the "Next" row. Shown only after answer reveal. Available on both `/diagnostic` and `/session` pages.

```
┌──────────────────────────────────────────────────────────┐
│  Explanation text ...                                     │
│                                                          │
│  Rate this question:                                     │
│  [ Looks good ]  [ Something's missing ]                 │
│  [ Should be omitted ]  [ Factually incorrect ]          │
│                                                          │
│  Optional note: _________________________ (1 line input) │
└──────────────────────────────────────────────────────────┘
[ Dive deeper → ]                    [ Next → ]
```

Interaction rules:
- Clicking a verdict button immediately calls `POST /feedback/content` and dims all four buttons
- Optional note saves when user clicks Next (does not block navigation)
- "Looks good" is the happy path — one click
- Row is hidden after Next is clicked

### 3b. Per-Section Notes Feedback (session notes card)

One compact feedback row beneath each of the 4 section headings (Core Concept, PYQ Angles, Current Affairs Linkages, Broader Linkages):

```
## Core Concept
[text content of section]
[ Looks good ] [ Something's missing ] [ Should be omitted ] [ Factually incorrect ]
```

- `content_type = 'notes_section'`, `notes_section` set to the section slug
- After click: buttons grey out, show "Saved ✓"

| Section heading | `notes_section` value |
|----------------|----------------------|
| Core Concept | `core_concept` |
| PYQ Angles | `pyq_angles` |
| Current Affairs Linkages | `current_affairs` |
| Broader Linkages | `broader_linkages` |

### 3c. Note-Taking Box — Per-Question Reset and Autosave

**Current problem:** Notes drawer is one blob per session stored in `session_user_notes`, not per question.

**Fix:**
- When `currentQ` changes, note textarea clears and loads the note for the new question from `question_notes`
- Autosave: 700 ms debounce → `PUT /sessions/{session_id}/question-notes/{question_hash}`
- Panel header: "Notes for Q{n} — {subtopic_name}"
- "Still weak" checkbox stays, saves `still_weak = 1` on the `question_notes` row
- Collapse two-field design (confusion / mnemonic) into one textarea
- On session start: load all notes for session via `GET /sessions/{session_id}/question-notes` → populate a `Record<string, string>` map keyed by `question_hash`
- On Finish: flush unsaved note before closing

---

## 4. API Contract

### POST `/feedback/content`
```json
{
  "session_id": "uuid",
  "content_type": "question",
  "question_hash": "uuid_0",
  "subtopic_id": "election_commission",
  "subject_id": "polity",
  "notes_section": null,
  "verdict": "missing",
  "note_text": "Should have mentioned model code of conduct"
}
```
Response: `{"status": "saved", "id": 42}`

Use `INSERT` (not upsert) — multiple verdicts allowed. Aggregation script takes the latest per `(session_id, question_hash, content_type, notes_section)`.

### PUT `/sessions/{session_id}/question-notes/{question_hash}`
```json
{
  "question_index": 2,
  "subtopic_id": "election_commission",
  "subject_id": "polity",
  "note_text": "ECI is an independent constitutional body...",
  "still_weak": false
}
```
Uses `INSERT OR REPLACE`. Response: `{"status": "saved"}`

### GET `/sessions/{session_id}/question-notes`
Response:
```json
{
  "notes": [
    {"question_hash": "uuid_0", "question_index": 0, "note_text": "...", "still_weak": false}
  ]
}
```

### GET `/feedback/content/summary`
Query params: `?since=2026-05-01`

Response:
```json
{
  "by_prompt_file": {
    "session_notes.txt": {
      "missing": [{"subtopic_id": "brics", "notes_section": "core_concept", "note_text": "...", "count": 3}],
      "wrong": [], "omit": []
    }
  },
  "total_feedback_items": 47
}
```

---

## 5. Prompt Improvement Pipeline

**Semi-automatic:** `scripts/apply_feedback.py` reads aggregated feedback, calls Haiku once per prompt file with feedback, and **prints suggestions to stdout**. Rahul reviews and manually edits the prompt `.txt` files. The script does NOT directly write to prompt files.

**Trigger:** Run manually (suggested cadence: every 2–3 days, or after 20+ new feedback items). Can optionally be added to end-of-day sync — if so, write output to `logs/prompt_suggestions_{date}.txt`.

**Haiku prompt** (stored at `prompts/feedback_aggregation.txt`):
```
You are helping improve an AI prompt used to generate UPSC Prelims study content.

CURRENT PROMPT:
---
{{current_prompt_text}}
---

USER FEEDBACK (aggregated from real study sessions):
{{aggregated_feedback_json}}

Based on the feedback, suggest specific edits to the prompt above.
For each suggestion:
1. Quote the exact line or phrase from the current prompt you are proposing to change
2. Write the replacement text
3. In one sentence, explain why this change addresses the feedback

Only suggest changes supported by at least 2 feedback items.
Targeted line-level edits only — do not rewrite the entire prompt.

Format:
SUGGESTION 1
Current: "<quoted line>"
Replace with: "<new line>"
Why: <one sentence>

If no changes are warranted: NO CHANGES SUGGESTED — feedback is too sparse or contradictory.
```

**Output example:**
```
=== Suggestions for prompts/session_notes.txt ===

SUGGESTION 1
Current: "2–4 sentences: what this subtopic is, why it matters..."
Replace with: "3–6 sentences: explain clearly enough that a student who has never read about it..."
Why: 5 feedback items on 'core_concept' rated 'missing' saying the explanation was too shallow.
```

---

## 6. Token Cost Estimate (Ongoing)

| Step | Model | Cost per run |
|------|-------|-------------|
| `apply_feedback.py` for `session_notes.txt` | Haiku | ~$0.0003 |
| `apply_feedback.py` for `diagnostic_quiz.txt` | Haiku | ~$0.0003 |
| `apply_feedback.py` for `adaptive_session.txt` | Haiku | ~$0.0003 |
| **Total per run** | | **< $0.001** |

Per-feedback-item saves: **0 tokens** (pure DB writes).  
Per-question note autosave: **0 tokens** (pure DB writes).

---

## 7. Implementation Order

### Phase 1 — Data layer and note-reset (~5 hours)

1. Add `content_feedback` and `question_notes` tables to `scripts/db_init.py`
2. Add backend endpoints: `POST /feedback/content`, `PUT /sessions/{session_id}/question-notes/{question_hash}`, `GET /sessions/{session_id}/question-notes`
3. Update `session/page.tsx` note box: per-question reset + autosave to new endpoint
4. Add note box to `diagnostic/page.tsx` (currently has none)
5. Update `plan_generator.fetch_user_notes_signals()` to also read from `question_notes WHERE still_weak = 1`

### Phase 2 — Per-question content feedback UI (~6 hours)

1. Create shared `ContentFeedback` component (`web/src/components/ContentFeedback.tsx`)
2. Wire into `/diagnostic/page.tsx` after explanation reveals
3. Wire into `/session/page.tsx` after explanation reveals
4. Wire into session notes card — one row per section
5. Add `GET /feedback/content/summary` endpoint

### Phase 3 — Prompt improvement script (~7 hours)

1. Create `prompts/feedback_aggregation.txt` (Haiku prompt template)
2. Implement `scripts/apply_feedback.py`
3. Add `logs/` directory and `logs/feedback_runs.log`
4. Update `CLAUDE.md` commands section
5. Update `FEATURES.md`

---

## 8. Decisions Made

| Decision | Rationale |
|----------|-----------|
| Semi-automatic prompt updates | Prompt files are the heart of content quality. Automatic overwrite risks regressions. 2-minute review is worth the safety. |
| Haiku (not Sonnet) for aggregation | Pattern-matching over structured feedback, not creative synthesis. 1/20th the cost. |
| INSERT (not upsert) for `content_feedback` | Multiple verdicts per block are valid. Script takes latest. |
| `question_notes` as a separate table | `session_answers` is write-once; notes autosave many times. Mixing them violates scoring immutability. |
| Keep `session_user_notes` | Backward compatibility for existing sessions. |
| Four-category verdict (not 1–5 rating) | Actionable immediately without normalisation. |

---

## 9. Open Questions (Rahul must decide before Phase 2 build starts)

1. **Notes section feedback on mobile:** Four verdict buttons in a horizontal row will wrap on a 375px phone. Options: (a) icons only (✓ / + / − / ✗) with tooltips, or (b) two buttons per row. Which do you prefer?

2. **Feedback on skipped questions:** Should the content feedback row appear even when a question is skipped (no answer, no explanation shown)? Recommended default: show feedback row but hide the optional note input.

3. **`apply_feedback.py` run trigger:** Manual (as specced) or automatic as part of end-of-day sync? If automatic, output goes to `logs/prompt_suggestions_{date}.txt` not stdout.
