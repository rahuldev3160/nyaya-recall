# Spec: Open-ended Quiz Mode + UX Mode Rename

**Feature refs:** Queued #4 (Open-ended quiz mode) + Queued #8 (quiz mode UX rename)
**Effort estimate:** ~3.5 hrs total across 2 PRs
**Branch:** `feature/open-ended-quiz-mode`
**Status:** Queued → Planned (pending Rahul approval of this spec)

---

## 1. Problem Statement

Rahul studies 5–6 hours a day. Sometimes he wants a quick 3-question warmup before a hard
session. Other times he opens a topic and keeps going until he runs out of steam. In both
cases, the current quiz setup forces him to commit to a count upfront: he must choose 10, 15,
or 20 questions before starting. Committing to a number up front creates friction:

- Too short: a 5-question session feels trivial to commit to on the session page
- Too long: committing to 20 questions then stopping at 6 feels like a failure, so he either
  pushes through when tired or abandons the session entirely (no score recorded)
- No current mode supports "I'll study until I want to stop"

**Open Practice mode** removes this friction entirely: start a session, answer questions one
at a time, and click "Save & Close" whenever ready. The session closes as complete (not
paused) with whatever was answered so far.

---

## 2. Scope

### In Scope
- New `open_ended` mode value stored in `quiz_sessions.mode`
- 10-question initial buffer generated at session start (same as today's fixed_set flow)
- Lazy-load 8 more questions when the buffer has fewer than 2 unanswered questions remaining
- "Save & Close" button rendered after each answer is submitted or question is skipped,
  before the user moves to the next question
- Pressing "Save & Close" calls `POST /sessions/{id}/close` and redirects to results
- Results page shows only actually-answered/skipped questions (not the full buffer)
- Mode selector on the Diagnostic page gains a third option: "Open Practice"
- UX label rename: `fixed_set` → "Practice Set", `time_boxed` → "Timed Quiz" (Diagnostic page only)
- No new DB tables — `mode` column already exists in `quiz_sessions`

### Out of Scope
- **Session resumption / resume-later**: a closed session is final. "Save & Close" is
  save-as-complete, not pause. This is a deliberate design decision documented in
  `plans/session_resumption.md`.
- Enforcing a time limit in open_ended sessions
- Open Practice mode from the daily plan page (`/session`) — only from Diagnostic page in Phase 1
- Any changes to `score_engine.py` scoring formula
- Any ALTER TABLE or DROP TABLE on existing tables

---

## 3. Session Creation Changes

### Mode value
Use `"open_ended"` (not `"open_practice"`) as the stored value. Rationale: the DB/backend
uses snake_case internal IDs; "Open Practice" is only a UI label. Keeping the internal value
consistent with `fixed_set` / `time_boxed` naming avoids confusion when reading raw DB rows.

### Parameters vs other modes
| Parameter | fixed_set | time_boxed | open_ended |
|---|---|---|---|
| `num_questions` | Required | Required | Not present (defaults to 10 for initial buffer) |
| `time_limit_min` | Not used | Required | Not present |
| `mode` | `"fixed_set"` | `"time_boxed"` | `"open_ended"` |

When the frontend sends `mode: "open_ended"`, it omits `num_questions` from the payload.
The backend `POST /quiz/generate` already defaults `num_q = config.get("num_questions", 10)`,
so no change is needed there — the initial buffer is always 10 questions.

### How the backend stores it
In `backend/routes/quiz.py`, `generate_quiz()` already writes `config.get("mode", "fixed_set")`
to `quiz_sessions.mode`. Sending `mode: "open_ended"` in the payload is sufficient — no
backend code changes needed for session creation.

### Initial buffer size
Generate **10 questions** at session start. This is the same as today's default. The buffer
strategy:

- Frontend tracks `bufferQuestions: any[]` (all questions fetched so far) and
  `displayedCount: number` (how many the user has seen/advanced through)
- When `bufferQuestions.length - displayedCount < 2`, fetch 8 more questions via another
  `POST /quiz/generate` call (same subject/subtopic/mode payload)
- Append the new questions to `bufferQuestions`
- Cap total buffer at 50 questions to prevent runaway API calls; if cap reached, show only
  a "Finish session" button (no more "Next" navigation)

### New `api.ts` method
Add `generateMoreQuestions` — identical to `generateQuiz` but called mid-session. The
frontend reuses `api.generateQuiz(config)` with the same payload; no new API endpoint needed.

---

## 4. Frontend Changes

### Files to change
- `web/src/app/diagnostic/page.tsx` — mode selector + open_ended session state machine
- `web/src/lib/api.ts` — no change needed (reuses existing `generateQuiz` and `closeSession`)

### Mode selector UI (Diagnostic page)

Replace the current two-button row at line 274–286 of `web/src/app/diagnostic/page.tsx`:

```tsx
// Current: ["fixed_set", "time_boxed"]
// New: three-option row
const MODES = [
  {
    value: "fixed_set" as const,
    label: "Practice Set",
    desc: "Fixed question count",
  },
  {
    value: "time_boxed" as const,
    label: "Timed Quiz",
    desc: "Race the clock",
  },
  {
    value: "open_ended" as const,
    label: "Open Practice",
    desc: "Study until you stop",
  },
];
```

Render as three equal-width buttons. The active state uses `border-amber-500 bg-amber-500/10
text-amber-400`; inactive uses `border-gray-700 text-gray-400`. Below each button render the
`desc` text in `text-xs text-gray-500`.

When `open_ended` is selected:
- Hide the "Questions" and "Minutes" number inputs (they're irrelevant)
- Show a brief note: `"Answer as many as you want. Save & Close after any question."`

### State machine additions (open_ended only)

Add to the component state:
```tsx
const [bufferQuestions, setBufferQuestions] = useState<any[]>([]);
const [displayedCount, setDisplayedCount] = useState(0);
const [fetchingMore, setFetchingMore] = useState(false);
const [bufferCapped, setBufferCapped] = useState(false);
```

`bufferQuestions` replaces `session.questions` as the live question list for open_ended.
For `fixed_set` / `time_boxed`, the existing `session.questions` flow is unchanged.

On session start with `open_ended`:
```
setBufferQuestions(data.questions);
setDisplayedCount(0);
```

The question displayed is always `bufferQuestions[currentQ]`.

### Save & Close button placement

Render the "Save & Close" button **after an answer is submitted or a question is skipped**,
in the button row below the options — positioned alongside the existing "Next →" button:

```tsx
{revealed[currentQ] && mode === "open_ended" && (
  <button
    onClick={handleSaveAndClose}
    className="border border-gray-600 hover:border-red-500 text-gray-400 hover:text-red-300 px-4 py-2 rounded-lg text-sm transition-colors"
  >
    Save & Close
  </button>
)}
```

It is a secondary/destructive-looking button (not green) to avoid accidental taps. "Next →"
remains the primary action.

### `handleSaveAndClose` function

```tsx
const handleSaveAndClose = async () => {
  if (!session) return;
  await flushPendingNotes(); // if notes panel is open
  try {
    const result = await api.closeSession(session.session_id);
    setScore(result);
  } catch {}
  setFinished(true);
  // Trigger revision notes for wrong answers answered so far
  setRevisionLoading(true);
  try {
    const data = await api.getRevisionNotes(session.session_id);
    setRevisionNotes(data.notes ?? []);
  } catch {
    setRevisionNotes([]);
  } finally {
    setRevisionLoading(false);
  }
};
```

This is structurally identical to `finishSession()` — the difference is only that it can be
called before the last question.

### Lazy-load trigger

After `setCurrentQ(currentQ + 1)` in the "Next →" handler:

```tsx
// Lazy-load for open_ended mode
if (mode === "open_ended") {
  const newDisplayed = displayedCount + 1;
  setDisplayedCount(newDisplayed);
  const remaining = bufferQuestions.length - newDisplayed;
  if (remaining < 2 && !fetchingMore && !bufferCapped) {
    setFetchingMore(true);
    api.generateQuiz(sessionConfig)  // same subject/subtopic/mode payload saved at start
      .then((data: any) => {
        setBufferQuestions((prev) => {
          const combined = [...prev, ...data.questions];
          if (combined.length >= 50) setBufferCapped(true);
          return combined.slice(0, 50);
        });
      })
      .catch(() => {}) // silent — user can still Save & Close
      .finally(() => setFetchingMore(false));
  }
}
```

### Question counter display

Replace the current `Q {currentQ + 1} / {quiz.questions.length}` counter with:
- For `fixed_set` / `time_boxed`: keep as-is
- For `open_ended`: show `Q {currentQ + 1}` only (no total, since buffer is infinite)
  with a sub-label `{Object.keys(answers).length + Object.keys(skipped).length} answered`

### Results screen (finished state)

The existing results screen uses `quiz.questions.length` as the total. For open_ended, use
only answered + skipped questions:

```tsx
const total = mode === "open_ended"
  ? Object.keys(answers).length + Object.keys(skipped).length
  : quiz?.questions?.length ?? 0;
```

The `close_session` API already computes the score based on actual `session_answers` rows,
so the `score` returned from the backend will naturally reflect only answered questions.

---

## 5. Backend Changes

### None required for core flow

The existing `POST /sessions/{id}/close` endpoint calls `close_session(session_id)` from
`scripts/score_engine.py`. That function already scores only from `session_answers` rows —
it doesn't look at `total_questions` from the session config for score computation. It sets:

```python
total = len(answers)           # only rows actually inserted by record_answer()
correct = sum(...)
skipped = sum(...)
score = (correct / max(total - skipped, 1)) * 100
```

So closing a session early (after 3 questions) with `POST /sessions/{id}/close` will
correctly report 3 questions. No backend changes needed.

### One minor inconsistency to fix

In `backend/routes/quiz.py`, line 668:
```python
(session_id, session_type, subject_id, topic_id, config.get("mode", "fixed_set"),
 json.dumps(stored_config), datetime.now(timezone.utc).isoformat(), len(questions))
```

`total_questions` is set to `len(questions)` (the initial buffer size, e.g. 10). For
open_ended, this is misleading — the user may answer only 3. This is fine because
`close_session()` does not use `total_questions` for score computation; it uses the actual
`session_answers` count. The `total_questions` column is only displayed in the session list
view and is acceptable as "buffer size" for open_ended sessions. No code change needed.

### No new DB tables or ALTER TABLE required

The `mode` column already exists in `quiz_sessions`. Storing `"open_ended"` requires no
migration.

---

## 6. Scoring Integrity

This is the critical guarantee for Rahul's anti-false-positive coverage rule.

**Rule:** Coverage is only credited for actually-attempted questions. An open_ended session
closed after 3 questions must report exactly 3 questions of data — nothing from the other
7 questions in the buffer that were never presented to the user.

**How it works end-to-end:**

1. `api.submitAnswer()` is called for each question only after the user selects/skips.
   Questions never shown to the user have no `session_answers` rows.

2. `close_session()` in `score_engine.py` reads only `session_answers` for this session_id.
   Unanswered buffer questions have no rows → they contribute zero to score, zero to
   `_update_subtopic_scores()`, and zero to `_store_session_summary()`.

3. `_update_subtopic_scores()` only updates subtopics with actual answer rows. If a subtopic
   appeared in the buffer but was never answered, its `subtopic_scores` record is untouched.

4. The results screen on the frontend explicitly uses the count from answered state keys,
   not `bufferQuestions.length`.

**Verification:** After a 3-question Save & Close, check:
```sql
SELECT COUNT(*) FROM session_answers WHERE session_id='<id>';
-- Should return 3
SELECT total_questions, answered FROM quiz_sessions WHERE id='<id>';
-- total_questions=10 (buffer), answered=3 (correct by close_session)
```

---

## 7. Implementation Phases

### Phase 1: Core open_ended mode — Diagnostic page (PR 1)

**Scope:** Everything needed for a working open_ended session from the Diagnostic page.

Changes:
- `web/src/app/diagnostic/page.tsx`:
  - Add `open_ended` to the mode type union: `"fixed_set" | "time_boxed" | "open_ended"`
  - Add MODES array with labels + descriptions
  - Rewrite mode selector buttons (3-up layout)
  - Add buffer state: `bufferQuestions`, `displayedCount`, `fetchingMore`, `bufferCapped`
  - Save session config payload for lazy-load reuse: `sessionConfig` state
  - Add `handleSaveAndClose()` function
  - Add lazy-load trigger in "Next →" handler
  - Update `isLast` computed value: `currentQ === bufferQuestions.length - 1 || bufferCapped`
    (for open_ended); keep original for other modes
  - Update question counter display
  - Update results total computation
  - Render "Save & Close" button in the revealed-answer row

**Effort:** ~2.5 hrs

### Phase 2: UX rename only — no functional change (PR 2, can merge independently)

**Scope:** Rename labels in the mode selector. Backend mode values stay the same.

Changes:
- `web/src/app/diagnostic/page.tsx` (same file):
  - "Fixed Questions" → "Practice Set"
  - "Time-boxed" → "Timed Quiz"
  - These are UI labels in the button text only — no DB or backend changes

Note: Phase 2 is intentionally bundled into Phase 1's PR since they touch the same button
row. Keeping them as a single PR is cleaner. They are listed separately only because
FEATURES.md tracks them as items #4 and #8.

**Effort:** ~15 mins (included in Phase 1)

---

## 8. Effort Estimate

| Phase | Est. Hours | Notes |
|---|---|---|
| Phase 1 (core open_ended + UX rename) | 2.5–3 hrs | Frontend only; no backend changes |
| Phase 2 (UX rename) | Bundled in Phase 1 | 15 min within Phase 1 PR |
| **Total** | **~3 hrs** | Under the 3–4 hr estimate in FEATURES.md |

---

## 9. How to Test

1. Start the backend: `cd backend && uvicorn server:app --host 0.0.0.0 --port 8000 --reload`
2. Start the frontend: `cd web && npm run dev`
3. Navigate to `/diagnostic`
4. Verify mode selector shows three buttons: "Practice Set", "Timed Quiz", "Open Practice"
   (confirms UX rename for items #4 and #8)
5. Select any subject (e.g. Polity), select "Open Practice"
6. Confirm the Questions/Minutes inputs are hidden and the note "Answer as many as you want..."
   is visible
7. Click "Start Session"
8. Answer Question 1: verify "Save & Close" button appears after answer, alongside "Next →"
9. Click "Next →" to go to Q2
10. Skip Q2 (click Skip): verify "Save & Close" appears after skip
11. On Q3, answer it — then click "Save & Close" (do NOT click Next first)
12. Verify results screen shows:
    - "3 / 3" (or "2 / 3" with 1 skipped) — only the questions actually answered
    - Score percentage computed over 3 questions
    - Revision notes appear for any wrong answers from those 3 questions
13. In the DB, verify:
    ```sql
    SELECT COUNT(*) FROM session_answers WHERE session_id='<from console>';
    -- Expected: 3
    SELECT mode FROM quiz_sessions WHERE id='<id>';
    -- Expected: open_ended
    SELECT answered, skipped FROM quiz_sessions WHERE id='<id>';
    -- Expected: answered=2, skipped=1 (or whatever matches what you did)
    ```
14. Run Sync & Plan on the dashboard — confirm readiness profile updated with the 3
    answered subtopics only, not all 10 buffer subtopics

---

## 10. Risks and Watch-outs

### Buffer exhaustion
If the lazy-load API call fails (network error, Claude timeout), the user is stuck at the
last question with no "Next →". Mitigation: "Save & Close" is always visible after an
answer, so the user can always exit. The lazy-load failure is silent — the button just
doesn't advance, and "Save & Close" is the escape hatch.

### `total_questions` column mismatch
`quiz_sessions.total_questions` stores the initial buffer size (10), not the actual
attempted count. This is visible in the session history list (`/sessions`). Document it as
expected behavior: for open_ended, `total_questions` = initial buffer, `answered` = actual.
The session history page (`web/src/app/sessions/page.tsx`) should add a note "(open)" next
to open_ended sessions if displaying total_questions.

### Code that assumes `question_count` is always set
- `session/page.tsx` line 286: `num_questions: session.num_questions ?? 10` — this is for
  the plan-driven session flow, which is not changed in Phase 1. The plan sessions always
  have `num_questions` set by the planner. Open Practice is Diagnostic-page-only for now.
- `diagnostic/page.tsx`: the `numQ` state defaults to 15 and is used in `fixed_set` and
  `time_boxed` payloads. For `open_ended`, `num_questions` is simply not sent. The backend
  defaults to 10. This is correct behavior.

### "Questions answered so far" counter
Yes — show a live counter in the question header for open_ended mode:
`Q {currentQ + 1}  ·  {answeredCount} answered`. This gives the user a sense of progress
without committing them to a total. `answeredCount = Object.keys(answers).length + Object.keys(skipped).length`.

### Accidentally mixing open_ended buffer questions into plan completion
The daily plan (`/session` page) marks subtopics as complete via `completedSessions` state.
Open Practice sessions from the Diagnostic page do not touch this state. No risk of
false-positive plan completion.

### isLast computation for open_ended
Current: `const isLast = currentQ === quiz.questions.length - 1;`
For open_ended with a growing buffer, `isLast` should be:
`const isLast = bufferCapped && currentQ === bufferQuestions.length - 1;`
Until the buffer is capped, there is always a "Next →" available (potentially after a
lazy-load fetch). The "Finish Session" button (shown on `isLast`) should not appear in
open_ended mode — "Save & Close" is the only exit path.

---

## 11. UX Rename — Detailed File Changes (Item #8)

The rename is display-only. Backend `mode` values (`fixed_set`, `time_boxed`) are unchanged
everywhere. Only the button labels change.

**File:** `web/src/app/diagnostic/page.tsx`

| Location | Old text | New text |
|---|---|---|
| Line 283 (button label) | `"Fixed Questions"` | `"Practice Set"` |
| Line 283 (button label) | `"Time-boxed"` | `"Timed Quiz"` |
| (new) third button | — | `"Open Practice"` |

No other files need changing. The session history page (`/sessions`) displays the raw `mode`
value from the DB — acceptable, no rename needed there.

---

## Appendix: Key existing functions referenced

| Function | File | What it does |
|---|---|---|
| `generate_quiz(config)` | `backend/routes/quiz.py:493` | Creates session, generates questions via Claude |
| `record_answer(session_id, answer)` | `scripts/score_engine.py:70` | Inserts one answer row |
| `close_session(session_id)` | `scripts/score_engine.py:96` | Scores from actual answer rows, updates subtopic_scores |
| `end_session(session_id)` | `backend/routes/sessions.py:334` | HTTP wrapper around `close_session()` |
| `api.closeSession(id)` | `web/src/lib/api.ts:55` | `POST /sessions/{id}/close` |
| `api.generateQuiz(config)` | `web/src/lib/api.ts:53` | `POST /quiz/generate` — reused for lazy-load |
| `finishSession()` | `web/src/app/diagnostic/page.tsx:211` | Template for `handleSaveAndClose()` |
