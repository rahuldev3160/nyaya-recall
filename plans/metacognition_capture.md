# Feature Plan: Metacognition Capture

**Status:** Planned
**Priority:** P1
**Effort estimate:** ~15 hours across 5 independent phases
**Depends on:** Nothing — can start immediately
**Unlocks:** Richer batch analysis, strategy readiness dimension in prep_profile, portable user profile

---

## Problem

The system currently captures *what* the user answered and *whether* it was correct.
It does not capture *how* the user thought.

Two users can both answer a polity question wrong. One didn't know the fact. The other
knew the fact but was misled by a plausible distractor. The third misread the question
under time pressure. All three look identical in the current data. They need completely
different remediation.

Without this signal the system cannot distinguish:
- Fact recall gaps (need memorisation drills)
- Concept understanding gaps (need re-reading / notes)
- Application failures (understand concept, can't apply to question)
- Strategy errors (elimination technique misused, misreads, overconfidence)
- Calibration quality (does "certain" actually correlate with being correct?)

---

## Solution overview

Two lightweight capture points per question:

**1. Pre-reveal confidence gate** (always shown, 1 click, ~3 seconds)
After user clicks an option, before the answer reveals, ask:
> How confident were you?
> [Certain] [Likely right] [Complete guess]

**2. Post-reveal reflection** (configurable: inline / end-of-session / off)
After answer reveals, prompt varies by outcome:

- Correct → light prompt (method used)
- Wrong → deeper prompt (what went wrong, what the gap was)

User can skip the post-reveal section at any time. Skip is recorded as a data point.

---

## User settings

New field in `data/prep_config.json`:

```json
{
  "metacognition_mode": "inline"
}
```

| Mode | Behaviour |
|------|-----------|
| `inline` | Post-reveal prompts appear immediately after each question (default) |
| `end_of_session` | All prompts collected after "Finish & Save" in a review screen |
| `off` | No post-reveal prompts. Confidence gate still captures (1 click, always on). |

Confidence capture is **never skippable** — it's 1 click and produces the highest-value
portable signal. The skip option only applies to the post-reveal detailed prompts.

---

## Data model

### New table: `answer_metacognition`

```sql
CREATE TABLE answer_metacognition (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_answer_id    INTEGER NOT NULL,   -- FK → session_answers.id
    session_id           TEXT    NOT NULL,
    user_id              TEXT    NOT NULL DEFAULT 'user_1',

    -- Pre-reveal (always captured)
    confidence           TEXT,   -- 'certain' | 'likely' | 'guess'

    -- Post-reveal — correct answers
    method               TEXT,   -- 'direct_recall' | 'elimination' | 'reasoning' | 'lucky'

    -- Post-reveal — wrong answers
    options_ruled_out    TEXT,   -- JSON array e.g. '["a","c"]'
    error_reason         TEXT,   -- see enum below
    knowledge_gap_type   TEXT,   -- see enum below

    -- Meta
    post_reveal_skipped  INTEGER DEFAULT 0,  -- 1 if user skipped post-reveal
    capture_mode         TEXT,   -- 'inline' | 'end_of_session'
    created_at           TEXT    DEFAULT (datetime('now'))
);
```

**`error_reason` enum:**
- `confused_similar_facts` — mixed up two similar facts/names/dates
- `sounded_familiar` — option looked like a recent scheme/current affair
- `misread_question` — understood the content, misread the question text
- `concept_gap` — underlying concept not understood
- `all_plausible` — all options seemed valid, no basis to choose

**`knowledge_gap_type` enum:**
- `fact_recall` — knew the concept, couldn't recall the specific fact
- `concept_understanding` — the underlying concept is unclear
- `application` — understands concept, couldn't apply to this question format
- `misread_pressure` — knew it, error was mechanical not knowledge-based

### Prep config addition

```json
// data/prep_config.json
{
  "total_days": 10,
  "daily_hours": 6,
  "start_date": "2026-05-06",
  "metacognition_mode": "inline"   // ← new field
}
```

### Prep profile additions (written by batch_analyse)

```json
// data/prep_profile.json — new top-level key
{
  "metacognition": {
    "confidence_calibration": {
      "certain_correct_rate": 0.85,
      "likely_correct_rate": 0.62,
      "guess_correct_rate": 0.33,
      "overconfidence_rate": 0.12
    },
    "error_patterns": {
      "dominant_error": "confused_similar_facts",
      "by_subject": {
        "polity": "concept_gap",
        "economy": "sounded_familiar"
      }
    },
    "method_distribution": {
      "direct_recall": 0.45,
      "elimination": 0.30,
      "reasoning": 0.20,
      "lucky": 0.05
    },
    "strategy_readiness": "developing",
    "skip_rate": 0.15,
    "sessions_with_metacognition": 5
  }
}
```

---

## UI spec

### Confidence gate (pre-reveal)

Appears inline between the option the user clicked and the answer reveal.
Replaces the "Next" action until confidence is selected.

```
┌─────────────────────────────────────────────────────┐
│  Before we reveal — how confident were you?          │
│                                                      │
│  [  Certain  ]  [ Likely right ]  [ Complete guess ] │
└─────────────────────────────────────────────────────┘
```

One click → confidence saved → answer reveals immediately.

---

### Post-reveal: CORRECT answer

```
✅  Correct

How did you get it?
[ Direct recall ]  [ Eliminated wrong options ]  [ Conceptual reasoning ]  [ Lucky guess ]

                                                                        [ Skip → ]
```

---

### Post-reveal: WRONG answer

Shown in three short steps to avoid overwhelming:

**Step 1 — What you ruled out**
```
✗  Correct answer was (B)

Which options did you correctly eliminate?
(Select all that apply — exclude the one you chose)

  [ ] Option A      [ ] Option C      [ ] Option D

                                         [ None / Skip → ]
```

**Step 2 — Why you picked yours**
```
Why did you pick your answer?

[ Confused two similar facts ]   [ Option sounded familiar / recent ]
[ Misread the question ]         [ Genuine concept gap ]
[ All options seemed valid ]

                                                      [ Skip → ]
```

**Step 3 — Knowledge gap type**
```
What was the root gap?

[ Fact not memorised ]               [ Concept not understood ]
[ Right concept, wrong detail ]      [ Knew it — misread under pressure ]

                                                      [ Skip → ]
```

---

### End-of-session review screen (when mode = `end_of_session`)

After "Finish & Save Session", before showing the score summary:

```
Session Review  (answer 3 questions — takes ~2 minutes)

  Q3  ✗  [ confidence not set ]  →  [ Fill in ]
  Q7  ✗  [ confidence not set ]  →  [ Fill in ]
  Q9  ✓  [ confidence not set ]  →  [ Fill in ]

                         [ Skip all ]    [ Start Review → ]
```

Shows only questions where confidence was not captured (edge case) or post-reveal was
deferred. User goes through them one by one with the same prompt structure above.

---

### Settings page addition

Add to `web/src/app/setup/page.tsx` (or a new `/settings` page):

```
Metacognition Mode
How would you like to reflect on each question?

  ● Inline (after each answer)     — most accurate, adds ~20s per question
  ○ End of session review          — less friction during quiz
  ○ Off (confidence only)          — minimal mode, confidence gate still active

  Note: skipping reflection is recorded and factored into your profile.
```

---

## API contract

### POST `/session/metacognition`

Save metacognition for a single answer. Called:
- After confidence selection (pre-reveal) → sends `confidence` only
- After post-reveal prompts → sends full object

```json
{
  "session_answer_id": 42,
  "session_id": "uuid",
  "confidence": "certain",
  "method": null,
  "options_ruled_out": ["a", "c"],
  "error_reason": "confused_similar_facts",
  "knowledge_gap_type": "fact_recall",
  "post_reveal_skipped": false,
  "capture_mode": "inline"
}
```

Two calls per question maximum:
1. When user clicks confidence (pre-reveal) — `confidence` field only, upsert by `session_answer_id`
2. When user completes post-reveal — remaining fields, upsert same row

Use `INSERT OR REPLACE` keyed on `session_answer_id`.

### GET `/session/{session_id}/metacognition`

Returns all metacognition rows for a session. Used by end-of-session review mode
to know which questions still need post-reveal input.

```json
[
  {
    "session_answer_id": 42,
    "question_text": "...",
    "is_correct": false,
    "confidence": "certain",
    "post_reveal_skipped": false,
    "error_reason": null   ← null means post-reveal not yet done
  }
]
```

### PATCH `/config` (extend existing)

`metacognition_mode` field added to the existing config endpoint. No new endpoint needed.

---

## Analysis integration

### `scripts/batch_analyse.py` — new function

```python
def get_metacognition_summary(session_ids: list[str]) -> dict:
    """
    Aggregates metacognition data across sessions.
    Returns structured summary for Claude's analysis prompt.
    """
    # Confidence calibration: by subject, was "certain" actually correct?
    # Error anatomy: most common error_reason per subject/subtopic
    # Method distribution: how often is elimination used vs direct recall?
    # Overconfidence: questions where confidence=certain AND is_correct=0
    # Skip rate: post_reveal_skipped / total questions
```

### `prompts/batch_analysis.txt` — new section

Add after `{{session_summaries}}`:

```
Metacognition summary (structured self-report data from this session):
{{metacognition_summary}}

Analyse:
- Confidence calibration: when the user said "certain" were they right?
  Flag overconfidence (certain + wrong) as a separate risk from knowledge gaps.
- Error anatomy: what type of errors dominate (fact recall vs concept vs misread)?
  Are wrong answers coming from being misled by distractors, or genuine knowledge gaps?
- Strategy signals: is elimination working? If user ruled out 2 options but still got it
  wrong, the problem is the final 50/50 decision, not knowledge breadth.
- Skip rate: if > 30%, note that metacognition data is sparse for this session.
```

### New `prep_profile.json` fields

`batch_analyse.py` writes a `metacognition` key to the profile after each sync.
Claude uses this when generating insights and the plan generator reads it for
strategy-specific scheduling (e.g., if overconfidence rate is high, schedule more
hard-difficulty sessions).

---

## Implementation sequence

Build in this order — each phase is independently deployable:

### Phase 1 — Data layer (no UI) · ~2 hrs
**Files:** `scripts/` (one-time migration), `backend/routes/sessions.py`

1. Add `answer_metacognition` table to SQLite schema (migration script)
2. Add `POST /session/metacognition` endpoint (upsert by session_answer_id)
3. Add `GET /session/{id}/metacognition` endpoint
4. Add `metacognition_mode` to config endpoints (GET + POST `/config`)

Test: call the endpoint directly with curl, verify rows appear in DB.

---

### Phase 2 — Confidence gate (always shown) · ~2 hrs
**Files:** `web/src/app/diagnostic/page.tsx`

1. Add a `confidence` state per question index
2. After user clicks an option: show 3-button confidence prompt, block reveal
3. On confidence click: call `POST /session/metacognition` with confidence only, then reveal
4. Ensure it works in both inline and end-of-session modes (just set confidence, no post-reveal yet)

Test: complete a session, verify every `answer_metacognition` row has `confidence` set.

---

### Phase 3 — Post-reveal prompts (inline mode) · ~4 hrs
**Files:** `web/src/app/diagnostic/page.tsx`

1. After answer reveals, check `is_correct` from the submitted answer
2. If correct: show 4-option method prompt + Skip button
3. If wrong: show 3-step prompt (options ruled out → error reason → gap type) + Skip at each step
4. On complete or skip: call `POST /session/metacognition` with post-reveal fields
5. Then show Next button

Test: answer questions both correctly and incorrectly, verify DB rows are complete.

---

### Phase 4 — End-of-session review mode · ~3 hrs
**Files:** `web/src/app/diagnostic/page.tsx`, new review component

1. When mode = `end_of_session`, skip all post-reveal prompts inline (confidence still shows)
2. After "Finish & Save", fetch `GET /session/{id}/metacognition`
3. Show review screen with questions where post-reveal is null
4. Same prompt components, same API call — just displayed after the session

Test: complete a session in end-of-session mode, verify review screen shows correct questions.

---

### Phase 5 — Settings UI + analysis integration · ~4 hrs
**Files:** `web/src/app/setup/page.tsx`, `scripts/batch_analyse.py`, `prompts/batch_analysis.txt`

1. Add metacognition_mode toggle to setup/settings page
2. Add `get_metacognition_summary()` to `batch_analyse.py`
3. Add `{{metacognition_summary}}` to batch_analysis.txt prompt
4. Add `metacognition` key to prep_profile schema (written by batch_analyse)
5. Update plan generator prompt to reference `metacognition.strategy_readiness`

Test: run batch_analyse after sessions with metacognition data, verify profile has metacognition fields.

---

## Scalability notes

The schema is fully exam-agnostic:
- `confidence`, `method`, `error_reason`, `knowledge_gap_type` are universal MCQ concepts
- `session_answer_id` links to a question, not to UPSC specifically
- When extended to another exam (CAT, GATE, State PCS), the table, API, and UI are identical
- Only the analysis prompt changes — and that's a `.txt` file

The user profile built here is portable. A user who prepares for UPSC and then for CAT
carries their metacognitive pattern ("overconfident on quantitative, underconfident on verbal")
without needing to rebuild it from scratch.

`user_id` is present on every row — multi-user extension requires no schema changes.

---

## Open questions (resolve before building Phase 3)

1. **Confidence gate on mobile:** the 3-button layout needs to be thumb-friendly on small screens.
   Consider full-width stacked buttons instead of horizontal row on mobile viewport.

2. **End-of-session review length:** if a user answers 20 questions and gets 12 wrong, the review
   screen shows 12 prompts. At ~30 seconds each that's 6 minutes. Consider capping at 5 worst
   questions (lowest confidence + wrong) for the review queue.

3. **Retroactive data:** sessions before this feature ships have no metacognition data.
   The analysis layer should handle null metacognition gracefully (not error, just note "no data").
