# Feature Plan: Timed Mode Enforcement

**Status:** Planned (spec only — awaiting Rahul approval before implementation)
**Priority:** P1
**Effort estimate:** ~2.5 hours across 2 phases
**Depends on:** Nothing — `time_boxed` mode and close endpoint already exist
**Unlocks:** Honest exam-condition practice; score data from timed sessions becomes comparable to real UPSC conditions

---

## Problem

`time_boxed` sessions collect a time limit at session start (stored in the `config` JSON blob on `quiz_sessions`, passed as `time_minutes` in the payload to `/quiz/generate`) but the frontend never reads it back, never shows a countdown, and never enforces the limit. A user can take 3 hours on a "20-minute" timed session. The `mode` column in `quiz_sessions` is set to `time_boxed` correctly, but nothing acts on it. Any questions not reached by the user when time expires are silently lost — they never get recorded as skipped, so the session closes with only attempted answers and the coverage picture is incomplete.

---

## Scope

### In scope
- Live countdown timer visible during `time_boxed` sessions on the diagnostic page (`web/src/app/diagnostic/page.tsx`)
- Timer turns red at `<= 5` minutes remaining
- Auto-close on expiry: all unanswered questions are submitted as skipped, then `POST /sessions/{id}/close` is called, session transitions to the finished state
- Server-side secondary enforcement: any request to an open `time_boxed` session that arrives after `start_time + config.time_minutes` automatically triggers `close_session()` and returns the closed summary — prevents the frontend crash-and-reload exploit
- A `time_expired` boolean in the close summary so the finished screen can show "Time's up!" vs. "Session Complete"

### Out of scope
- Timer on the `session/page.tsx` plan-driven sessions (those sessions use `fixed_set` mode; `time_boxed` is diagnostic-only today)
- Timer persistence across page refresh (see refresh behaviour below)
- Audio alert at timer end
- Mid-session pause functionality

---

## Frontend changes

### Where the timer lives
File: `web/src/app/diagnostic/page.tsx`

The countdown banner sits between the progress line ("Q N / M") and the question card, rendered only when `mode === "time_boxed"` and the session is active (`session !== null && !finished`). It must be always visible without scrolling — fixed to the top of the question view, not in the scrollable question card area.

Suggested layout:
```
┌─────────────────────────────────────────────────┐
│  Q 3 / 15          [subject name]               │
│                                                 │
│  ⏱ 14:32 remaining  ←── green (> 5 min)        │
│  ⏱  4:58 remaining  ←── red   (<= 5 min)       │
└─────────────────────────────────────────────────┘
```

### Timer state management
New state variables added inside `DiagnosticPage`:
```ts
const [timeRemainingSeconds, setTimeRemainingSeconds] = useState<number | null>(null);
const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
```

Initialize in the block that sets `session` after a successful `startSession()` call:
```ts
if (payload.mode === "time_boxed" && payload.time_minutes) {
  setTimeRemainingSeconds(payload.time_minutes * 60);
}
```

Timer effect — runs once when `session` becomes non-null and `mode === "time_boxed"`:
```ts
useEffect(() => {
  if (!session || mode !== "time_boxed" || timeRemainingSeconds === null) return;

  timerRef.current = setInterval(() => {
    setTimeRemainingSeconds((prev) => {
      if (prev === null) return null;
      if (prev <= 1) {
        // Will trigger auto-close in a separate effect watching for 0
        return 0;
      }
      return prev - 1;
    });
  }, 1000);

  return () => {
    if (timerRef.current) clearInterval(timerRef.current);
  };
}, [session?.session_id]); // eslint-disable-line react-hooks/exhaustive-deps
```

Auto-close effect — watches for `timeRemainingSeconds === 0`:
```ts
useEffect(() => {
  if (timeRemainingSeconds !== 0) return;
  if (timerRef.current) clearInterval(timerRef.current);
  handleTimerExpiry(); // defined below
}, [timeRemainingSeconds]); // eslint-disable-line react-hooks/exhaustive-deps
```

### handleTimerExpiry function
This function must:
1. Record all unanswered questions as skipped (same payload shape as the existing skip path, `skipped: true`, `user_answer: null`, `is_correct: false`)
2. Call `api.closeSession(session.session_id)`
3. Set `finished(true)` and a new `timedOut` flag so the results screen shows "Time's up!"

```ts
const handleTimerExpiry = async () => {
  if (!session) return;
  // Submit every question not yet in `answers` or `skipped` as skipped
  const skipPromises = session.questions.map(async (q: any, idx: number) => {
    if (answers[idx] !== undefined || skipped[idx]) return; // already answered or skipped
    return api.submitAnswer({
      session_id: session.session_id,
      question_hash: `${session.session_id}_${idx}`,
      question_text: q.question_text,
      options: { a: q.option_a ?? "", b: q.option_b ?? "", c: q.option_c ?? "", d: q.option_d ?? "" },
      correct_answer: q.correct_answer,
      user_answer: null,
      is_correct: false,
      time_taken_sec: 0,
      skipped: true,
      subject_id: selected, // subject_id from page-level state
      subtopic_id: q.subtopic_id ?? "",
    }).catch(() => {});
  });
  await Promise.allSettled(skipPromises);
  try { await api.closeSession(session.session_id); } catch {}
  setTimedOut(true);  // new boolean state
  setFinished(true);
};
```

Add `const [timedOut, setTimedOut] = useState(false);` to the state block.

### Timer display component (inline JSX, not a separate file)
```tsx
{mode === "time_boxed" && session && !finished && timeRemainingSeconds !== null && (
  <div className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-mono font-medium mb-2 ${
    timeRemainingSeconds <= 300
      ? "bg-red-950/60 border border-red-800 text-red-300"
      : "bg-gray-900 border border-gray-800 text-gray-300"
  }`}>
    <span>{timeRemainingSeconds <= 300 ? "⏱" : "⏱"}</span>
    <span>
      {String(Math.floor(timeRemainingSeconds / 60)).padStart(2, "0")}:
      {String(timeRemainingSeconds % 60).padStart(2, "0")} remaining
    </span>
  </div>
)}
```

### Finished screen — "Time's up!" variant
In the `finished` block, add a conditional banner above the score:
```tsx
{timedOut && (
  <div className="bg-red-950/60 border border-red-800 rounded-xl px-5 py-3 text-center text-red-300 font-medium">
    Time&apos;s up — session auto-closed
  </div>
)}
```

### Page-refresh behaviour (deliberate non-feature)
Sessions are not resumable (see `plans/session_resumption.md`). If the user refreshes mid-session, the diagnostic page resets to the setup screen. The session row in SQLite remains open (`end_time IS NULL`). This is acceptable in the short term because:
- The server-side enforcement (Phase 2) will catch the stale open session on any subsequent request and close it
- A future "Session Resumption" feature may address this more holistically

Do NOT persist the timer to localStorage. Restarting the timer from 0 would give extra time; not restarting it at all leaves an open session — server-side enforcement covers the cleanup.

---

## Backend changes

### Does the backend need changes?

Yes, for secondary enforcement only. The close endpoint (`POST /sessions/{session_id}/close` in `backend/routes/sessions.py`) already calls `close_session()` from `score_engine.py`. No changes needed there.

The secondary safeguard is a guard added to `get_session()` (the `GET /sessions/{session_id}` route used by the frontend's localStorage restore path) and optionally to `submit_answer()`.

### Where to add the server-side expiry check

In `backend/routes/sessions.py`, add a helper:

```python
def _maybe_auto_close_expired(session_id: str, con: sqlite3.Connection) -> bool:
    """
    If session is time_boxed and start_time + time_minutes < now, close it.
    Returns True if session was auto-closed.
    """
    row = con.execute(
        "SELECT mode, config, start_time, end_time FROM quiz_sessions WHERE id=?",
        (session_id,)
    ).fetchone()
    if not row or row["end_time"]:
        return False
    if row["mode"] != "time_boxed":
        return False
    try:
        cfg = json.loads(row["config"] or "{}")
        time_minutes = cfg.get("time_minutes") or cfg.get("time_limit_min")
        if not time_minutes:
            return False
        start = datetime.fromisoformat(row["start_time"].replace("Z", "+00:00"))
        deadline = start + timedelta(minutes=int(time_minutes))
        if datetime.now(timezone.utc) >= deadline:
            close_session(session_id)  # already handles its own connection
            return True
    except Exception:
        pass
    return False
```

Call this helper at the top of `get_session()`, before returning the session data. If it returns `True`, re-fetch the session and return it as closed.

Also call it at the top of `submit_answer()` — if the session is expired, return a 409 response rather than recording the answer:
```python
@router.post("/answer")
def submit_answer(answer: dict):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    expired = _maybe_auto_close_expired(answer["session_id"], con)
    con.close()
    if expired:
        raise HTTPException(status_code=409, detail="Session expired — time limit reached")
    ...
```

The frontend ignores errors on `submitAnswer` calls during timer expiry (wrapped in `.catch(() => {})`), so the 409 is safe.

### config JSON key for time_minutes
The diagnostic page currently sends `time_minutes` in the payload. The `quiz.py` generate endpoint stores the whole config blob in `quiz_sessions.config`. The helper reads `cfg.get("time_minutes")`. No new columns needed — the limit is already in the `config` blob.

---

## Data model

No new columns required.

- `quiz_sessions.mode` = `"time_boxed"` already identifies timer sessions
- `quiz_sessions.config` (JSON TEXT) already contains `time_minutes`
- `quiz_sessions.start_time` already set at session creation in `quiz.py`
- `quiz_sessions.skipped` counter already incremented by `close_session()` in `score_engine.py` — auto-skipped questions at expiry will correctly increment it

The only optional addition is a `time_expired` flag in the `close_session()` return dict (not stored to DB, just returned to the client) so the finished screen knows to show "Time's up!" vs. "Session Complete". This is returned from `end_session()` in `sessions.py` as:
```python
summary["time_expired"] = True  # add this when called by _maybe_auto_close_expired
```

Or the frontend can infer it from the new `timedOut` state set in `handleTimerExpiry`.

Recommendation: **no new DB columns.** `time_expired` is session-local UI state only.

---

## Why unanswered questions must be recorded as skipped

Rahul's coverage framework applies here: a `time_boxed` session that auto-closes must not silently drop the questions that were never reached. If 5 of 15 questions were never seen:

- Without recording: `close_session()` sees 10 answers, `total_questions = 15`, score = `correct / 10`. But `subtopic_scores` only updates for the 10 answered subtopics — the 5 never-reached subtopics are invisible to coverage tracking.
- With recording: all 15 questions are in `session_answers`; skipped=True questions are excluded from `score` numerator but counted in `total_questions`; `_update_subtopic_scores()` sees `skipped=1` rows and correctly ignores them. Coverage stays accurate.

The `handleTimerExpiry` function in the frontend handles this by calling `api.submitAnswer` with `skipped: true` for every unreached question before calling `closeSession`.

---

## Implementation phases

### Phase 1 — Frontend countdown + auto-close (standalone, no backend change)

**Files touched:**
- `web/src/app/diagnostic/page.tsx` — add timer state, `useEffect` interval, `handleTimerExpiry`, timer display JSX, "Time's up!" banner on finished screen

**Scope:** Pure frontend. Does not require any backend change. The existing `api.closeSession()` and `api.submitAnswer()` calls are unchanged.

**Effort:** ~1.5 hrs

**Independently mergeable:** Yes — no backend deployment needed.

### Phase 2 — Server-side expiry enforcement

**Files touched:**
- `backend/routes/sessions.py` — add `_maybe_auto_close_expired()` helper, call it in `get_session()` and `submit_answer()`

**Scope:** Defensive backend guard. Handles the stale-session-after-refresh case. No frontend changes.

**Effort:** ~1 hr

**Independently mergeable:** Yes — additive only, no existing logic altered.

---

## How to test

1. Go to `/diagnostic`
2. Select any subject (e.g. Polity), set mode to "Time-boxed", set time to 1 minute, set questions to 5
3. Click "Start Diagnostic"
4. Verify: a countdown appears above the question card showing `01:00` in green
5. Answer 1 question, skip 1 question, leave 3 unanswered
6. Wait for the timer to reach `00:05` — verify it turns red
7. Let it reach `00:00` — verify: (a) session transitions to the finished screen, (b) "Time's up — session auto-closed" banner appears, (c) score shown is X/2 (only the 1 answered question, not the 3 unanswered)
8. In SQLite, verify: `SELECT answered, skipped, score FROM quiz_sessions ORDER BY start_time DESC LIMIT 1` — expect `answered=1, skipped=4, score=...`
9. Also verify `session_answers` has 5 rows for that session_id — 1 answered, 1 manually skipped, 3 auto-skipped by timer (all with `skipped=1, user_answer=NULL`)

For Phase 2 (server-side enforcement):
10. Start a 1-minute session, answer 1 question, then immediately navigate away (do not close the session via UI)
11. Wait 2 minutes
12. Open the browser console and call `fetch('/api/backend/sessions/<id>').then(r=>r.json()).then(console.log)` — response should show `end_time` is set (session auto-closed)

---

## Risks and watch-outs

### Race condition: user submits last answer as timer fires
If the user clicks "Submit Answer" for the last question at the same moment `timeRemainingSeconds` hits 0, two things happen concurrently:
- The timer's `handleTimerExpiry` submits all unreached questions as skipped and calls `closeSession`
- The user's `submitAnswer` for question N also fires

Mitigations:
- `handleTimerExpiry` uses `if (answers[idx] !== undefined || skipped[idx]) return` — it skips any question already in the `answers` or `skipped` state maps, so a concurrently submitted answer is not double-recorded
- `close_session()` in `score_engine.py` is idempotent for already-closed sessions: `UPDATE quiz_sessions SET end_time=? WHERE id=?` — if the session is already closed, the WHERE clause still matches and `end_time` is just overwritten with a slightly later timestamp (harmless)
- The 409 from the Phase 2 server-side guard on `submit_answer` is caught by `.catch(() => {})` in the frontend

Residual risk: low. No data can be lost. At worst, a final answer is not recorded if the timer fires between the user clicking and the network response returning.

### Existing fixed_set sessions unaffected
The timer only renders when `mode === "time_boxed"`. All existing `fixed_set` sessions on `/diagnostic` and all plan-driven sessions on `/session` are unaffected — they never set `timeRemainingSeconds` to a non-null value.

### Timer drift on mobile / background tab
`setInterval` is throttled by browsers when the tab is backgrounded (to 1 Hz or less). This means the countdown may run slightly slower than real time. On a 20-minute session this is negligible. On a 1-minute test session the drift could be a few seconds. The server-side enforcement (Phase 2) is the authoritative deadline — the frontend timer is a convenience display, not the canonical source of truth.

### No timer on session/page.tsx
Plan-driven sessions in `web/src/app/session/page.tsx` always use `mode: "fixed_set"` (hardcoded in `startSession()`). No timer work needed there for this feature. If Rahul later wants timed plan sessions, that is a separate feature.
