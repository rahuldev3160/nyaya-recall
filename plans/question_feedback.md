# Feature Plan: Question & Session Feedback

**Status:** Planned
**Priority:** P1
**Effort estimate:** ~6.5 hours across 5 phases
**Depends on:** Nothing — can start immediately
**Unlocks:** Self-correcting question quality, richer difficulty engine signal, ChromaDB gap detection, flagged question review in Tracker

---

## Problem

The system generates questions and sessions but has no loop to detect when something is wrong:
- A question with the wrong correct answer keeps appearing and corrupting subtopic scores
- A question pulled from unrelated ChromaDB content keeps being served to the user
- The difficulty engine adjusts based only on correct/incorrect — a user can guess right or know the concept but misread, both look identical
- Systemic session problems (all questions from one chunk, all too easy) are invisible

Without structured user feedback, bad questions silently degrade data quality over time.

---

## Solution overview

Three capture points, all structured (no open-ended text):

**1. Difficulty rating** (per question, always shown, 1 click)
After answer reveals, before Next button:
```
[ Too Easy ]  [ About Right ]  [ Too Hard ]
```

**2. Quality flag** (per question, optional — tap to expand)
Small link below the difficulty buttons. Does not show options until clicked:
```
Flag this question ▾
  → [ Unclear / Ambiguous ]  [ Wrong answer marked ]  [ Off syllabus ]  [ Repetitive ]
```

**3. Session feedback** (end of session, fully skippable, 3 questions)
Shown after score screen, before returning to dashboard:
```
Quick session check (optional — tap Skip to go to dashboard)

Difficulty overall:  [ Too Easy ]  [ Mixed ]  [ Too Hard ]
Topic spread:        [ Too clustered ]  [ Good spread ]
Material source:     [ Felt from my notes ]  [ Felt generic / made up ]

                                            [ Skip ]  [ Save feedback → ]
```

---

## Data model

### New table: `question_feedback`

```sql
CREATE TABLE question_feedback (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_answer_id   INTEGER NOT NULL,   -- FK → session_answers.id
    session_id          TEXT    NOT NULL,
    user_id             TEXT    NOT NULL DEFAULT 'user_1',
    question_hash       TEXT    NOT NULL,
    subject_id          TEXT,
    subtopic_id         TEXT,

    -- Per-question signals
    difficulty_rating   TEXT,   -- 'too_easy' | 'right' | 'too_hard'
    quality_flag        TEXT,   -- 'unclear' | 'wrong_answer' | 'off_syllabus' | 'repetitive'

    created_at          TEXT    DEFAULT (datetime('now'))
);
```

### New table: `session_feedback`

```sql
CREATE TABLE session_feedback (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT    NOT NULL UNIQUE,
    user_id             TEXT    NOT NULL DEFAULT 'user_1',

    -- Session-level signals
    session_difficulty  TEXT,   -- 'too_easy' | 'mixed' | 'too_hard'
    topic_spread        TEXT,   -- 'too_clustered' | 'good_spread'
    material_source     TEXT,   -- 'from_notes' | 'felt_generic'

    created_at          TEXT    DEFAULT (datetime('now'))
);
```

---

## How feedback feeds existing systems

| Signal | Where it goes | Effect |
|--------|--------------|--------|
| `difficulty_rating = 'too_easy'` | `difficulty_engine.py` | Weighted alongside correct/incorrect — pushes subtopic toward harder tier |
| `difficulty_rating = 'too_hard'` | `difficulty_engine.py` | Pushes subtopic toward easier tier |
| `quality_flag = 'wrong_answer'` | Flagged questions list in Tracker | Question marked for review; excluded from scoring until cleared |
| `quality_flag = 'off_syllabus'` | Flagged questions list in Tracker | Surfaced for manual review / re-ingestion |
| `material_source = 'felt_generic'` | ChromaDB gap signal per subtopic in Tracker | Signals that ChromaDB returned no relevant chunks — shows as coverage gap |
| `session_difficulty` | Plan generator context | Informs next session's difficulty parameter for that subject |
| `topic_spread = 'too_clustered'` | Logged against session in DB | Future: feeds multi-subtopic allocation tuning |

### Zero new API calls
All signal processing is pure Python arithmetic or DB flag writes. No Claude calls triggered by feedback.

---

## UI spec

### Per-question: difficulty rating (always shown)

Appears below the explanation block, above the Next button.
Same row as the existing "Dive deeper →" link area.

```
┌─────────────────────────────────────────────┐
│  Explanation text...                         │
│                                             │
│  Difficulty?  [ Too Easy ] [ Right ] [ Hard ] │
│  Flag this question ▾                        │
└─────────────────────────────────────────────┘
[ Next Question → ]
```

One click → saved immediately via API → button row greys out (no undo needed).

### Per-question: quality flag (optional expand)

"Flag this question ▾" expands inline on tap:
```
[ Unclear ]  [ Wrong answer ]  [ Off syllabus ]  [ Repetitive ]
```
One click → saved → row collapses to "Flagged ✓".
If user already clicked Next, the flag is gone — flag is available only before Next.

### End-of-session feedback screen

Shown after score display, as a second card below the score:

```
Session check  (optional)

How was the difficulty?    [ Too Easy ]  [ Mixed ]  [ Too Hard ]
Topic spread?              [ Too clustered ]  [ Good spread ]
Did questions feel like    [ From my notes ]  [ Generic / made up ]
your study material?

                                         [ Skip ]  [ Save → ]
```

Entire block is skippable. Saving any subset of answers is fine — partial rows are allowed (nullable columns).

### Tracker page: flagged questions section

New section at the bottom of the Tracker page:

```
Flagged Questions  (3)

  ✗ Wrong answer    Polity / Election Commission
    "Which of the following is NOT a function of ECI..."
    Flagged: May 12                        [ Review ] [ Dismiss ]

  ✗ Off syllabus    Economy / Digital Payments
    "With reference to CBDC pilot launched in..."
    Flagged: May 11                        [ Review ] [ Dismiss ]
```

"Review" opens the question text + options for manual inspection.
"Dismiss" clears the flag (keeps the question in rotation).
No AI needed — pure DB read + render.

---

## API contract

### POST `/sessions/feedback/question`

```json
{
  "session_answer_id": 42,
  "session_id": "uuid",
  "question_hash": "abc123",
  "subject_id": "polity",
  "subtopic_id": "election_commission",
  "difficulty_rating": "too_hard",
  "quality_flag": null
}
```

Use `INSERT OR REPLACE` keyed on `session_answer_id`.
Two calls max per question — one for difficulty (immediate), one for quality flag (if user taps).

### POST `/sessions/feedback/session`

```json
{
  "session_id": "uuid",
  "session_difficulty": "too_hard",
  "topic_spread": "good_spread",
  "material_source": "felt_generic"
}
```

`UNIQUE` constraint on `session_id` — one row per session, `INSERT OR REPLACE`.

### GET `/tracker/flagged`

Returns questions with `quality_flag IN ('wrong_answer', 'off_syllabus')` joined with question text from `session_answers`. Used by Tracker page flagged questions section.

---

## Implementation sequence

### Phase 1 — Data layer · ~1 hr
1. Add `question_feedback` and `session_feedback` tables (migration script)
2. Add `POST /sessions/feedback/question` endpoint
3. Add `POST /sessions/feedback/session` endpoint
4. Add `GET /tracker/flagged` endpoint

Test: call endpoints with curl, verify rows in DB.

### Phase 2 — Per-question difficulty rating UI · ~1 hr
**File:** `web/src/app/diagnostic/page.tsx`
1. Add `difficultyRating` state `Record<number, string>`
2. After answer reveals, show 3-button difficulty row
3. On click: call `POST /sessions/feedback/question` with `difficulty_rating`, grey out row

Test: answer questions, verify `question_feedback` rows have `difficulty_rating` set.

### Phase 3 — Quality flag UI · ~1 hr
**File:** `web/src/app/diagnostic/page.tsx`
1. Add "Flag this question ▾" link below difficulty row
2. On tap: expand 4-option flag selector
3. On flag click: call `POST /sessions/feedback/question` with `quality_flag`, collapse to "Flagged ✓"
4. Flag link hidden after Next is clicked

Test: flag a question, verify `quality_flag` in DB.

### Phase 4 — End-of-session feedback UI · ~1.5 hrs
**File:** `web/src/app/diagnostic/page.tsx`
1. After score card on finish screen, add session feedback card
2. Three 2-option button rows (or 3-option for difficulty)
3. Skip button → go to dashboard immediately
4. Save → call `POST /sessions/feedback/session`, then go to dashboard

Test: complete session, submit session feedback, verify `session_feedback` row in DB.

### Phase 5 — Integration with difficulty engine + Tracker · ~2 hrs
**Files:** `scripts/difficulty_engine.py`, `web/src/app/tracker/page.tsx`, `backend/routes/tracker.py`
1. `difficulty_engine.py`: read `question_feedback.difficulty_rating` alongside correct/incorrect when computing tier updates. Weight: performance = 0.7, self-reported difficulty = 0.3.
2. `tracker.py`: add `GET /tracker/flagged` route
3. `tracker/page.tsx`: add Flagged Questions section using the new endpoint

Test: flag a question as "wrong answer", verify it appears in Tracker.

---

## Scalability notes

- `question_hash` links feedback to a specific question text, not a session — if the same question appears in two sessions, both feedbacks are aggregatable
- `user_id` on every row — multi-user extension needs no schema changes
- No exam-specific fields — works identically for CSAT, mock tests, any future quiz type
- Session feedback table is one row per session — lightweight, never grows large
