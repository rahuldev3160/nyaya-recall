# Plan: PYQ Browser
_Priority: P1 — first public-facing feature after data foundation_
_Created: 2026-05-30_
_Depends on: pyq_data_foundation.md (must have official answers before exposing to users)_

## Goal

A structured PYQ practice interface. User navigates: **Year → Subject → Topic → Subtopic → Attempt questions**.

Different from Exam Sim (random simulation). This is deliberate, structured practice — user picks exactly what they want to drill.

---

## User Flow

```
/pyq
 └── Year selector (2009–2025, pill grid)
      └── Subject grid (9 subjects, with question counts per year)
           └── Topic list (accordion, count per topic)
                └── Subtopic list (count + attempted status)
                     └── Question set (quiz runner, same UI as existing session page)
```

Optional shortcuts:
- "Practice all questions from 2019" (year-level attempt, all subjects)
- "All Polity PYQs (any year)" (subject-level across years)
- Filter: "Only unattempted" / "Only wrong" / "All"

---

## API Endpoints

All read-only, zero AI calls. Pure SQL.

### GET /pyq/years
```json
[
  {"year": 2025, "total": 100, "attempted": 0, "correct": 0},
  {"year": 2024, "total": 100, "attempted": 34, "correct": 22},
  ...
]
```

### GET /pyq/{year}/subjects
```json
[
  {"subject_id": "polity", "label": "Polity", "total": 18, "attempted": 10, "correct": 7},
  ...
]
```

### GET /pyq/{year}/{subject_id}/topics
```json
[
  {"topic_id": "fundamental_rights", "label": "Fundamental Rights", "total": 5, "attempted": 2, "correct": 1},
  ...
]
```

### GET /pyq/{year}/{subject_id}/{topic_id}/questions
```json
[
  {
    "id": 123,
    "question_text": "...",
    "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...",
    "correct_answer": "b",
    "answer_source": "official",
    "answer_disputed": false,
    "user_answer": null,
    "user_correct": null
  }
]
```

### POST /pyq/attempt
Records user's answer for a PYQ. Creates a PYQ-type session_answer row.
```json
{"question_id": 123, "answer": "b", "time_taken_sec": 42}
```

Returns: `{"correct": true, "correct_answer": "b"}`

### GET /pyq/stats/summary (optional, for dashboard widget)
```json
{"total_attempted": 234, "total_correct": 156, "accuracy_pct": 67, "years_touched": [2023, 2024, 2025]}
```

---

## DB Changes

No new tables needed. Uses existing `pyq_questions` (after data foundation adds official answers).

For tracking user attempts on PYQs, two options:

**Option A (simpler):** Reuse `session_answers` table with a `session_type = 'pyq_practice'` session row
- Pros: zero schema change, all existing scoring logic applies
- Cons: PYQ attempts mixed with regular quiz sessions in batch_analyse

**Option B:** New `pyq_attempts` table
```sql
CREATE TABLE pyq_attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT NOT NULL DEFAULT 'user_1',
    question_id   INTEGER NOT NULL REFERENCES pyq_questions(id),
    user_answer   TEXT,
    is_correct    INTEGER,
    time_taken_sec INTEGER,
    attempted_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_pyq_attempts_user ON pyq_attempts(user_id, question_id);
```
- Pros: clean separation, easier to query PYQ-specific stats
- Cons: new table, need new scoring path

**Recommendation: Option B.** PYQ practice is a different mode — mixing it with adaptive quiz sessions would corrupt the readiness scoring that batch_analyse computes.

---

## Frontend: `/pyq` page

### Page structure
```
Header: "PYQ Practice" | Filter: [All Years ▼] [All Subjects ▼] [Status: All ▼]

Year Grid (2x8 pills)
  [ 2025  100q ]  [ 2024  100q ]  [ 2023  100q ]  ...
  [ 2017  100q ]  [ 2016  100q ]  [ 2015  100q ]  ...

→ Click year → subject cards appear below
→ Click subject → topic accordion
→ Click topic → subtopic list → "Start Practice" button
→ Start Practice → existing quiz runner (same component as /session)
```

### Components needed
- `YearGrid.tsx` — pill grid of years with progress indicator
- `SubjectCards.tsx` — 3×3 grid, count + accuracy badge
- `TopicAccordion.tsx` — expandable list with subtopic drill-down (reuse Tracker accordion pattern)
- `PYQQuizRunner.tsx` — wraps existing quiz runner, uses POST /pyq/attempt instead of session endpoints

### Key UX decisions
- After revealing answer: show correct answer immediately (no "Submit all" — PYQ practice is one-by-one)
- Explanation card (if Pro): appears after correct answer is shown — see `pyq_explanations.md`
- Disputed answer badge: small ⚠️ icon on question if `answer_disputed = true` with tooltip

---

## Files to Create/Modify

| File | Action | Notes |
|------|--------|-------|
| `backend/routes/pyq.py` | Create | All /pyq/* endpoints |
| `backend/server.py` | Modify | Include pyq router |
| `web/src/app/pyq/page.tsx` | Create | Main browser page |
| `web/src/app/pyq/[year]/page.tsx` | Create | Year drill-down |
| `web/src/components/YearGrid.tsx` | Create | |
| `web/src/components/TopicAccordion.tsx` | Reuse/adapt from Tracker | |
| `web/src/components/PYQQuizRunner.tsx` | Create | Wraps existing runner |
| `web/src/app/nav.tsx` (or nav component) | Modify | Add "PYQ" nav link |

---

## Out of Scope (deferred to public platform build)

- Per-user attempt history (public platform needs auth first)
- Percentile ranking vs other users
- "Difficult questions for this year" sorting (needs multi-user data)
- Export PYQ session as PDF

---

## Effort Estimate

- Backend routes: 3 hours
- DB table + indexes: 30 min
- Frontend browser page: 4 hours
- PYQQuizRunner component: 2 hours
- Testing + edge cases: 1 hour

**Total: ~1 day**
