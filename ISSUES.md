# ISSUES.md — Running Issue Log

> Log of bugs, UX gaps, and problems noticed during actual use.
> Different from FEATURES.md (which tracks pre-planned items) — issues here are
> discovered organically, often by Rahul during study sessions.
>
> Keeping this log prevents repeating the same problems and gives future contributors
> the full context of when an issue arose, what was tried, and how it was resolved.

---

## Format

```
### ISSUE-NNN — Short title
**Noticed:** YYYY-MM-DD  
**Reported by:** Rahul / Friend / Claude  
**Status:** Open | In progress | Resolved | Won't fix  
**Priority:** P0–P3  
**Linked feature:** FEATURES.md item or plan file if applicable  

**What happened:** (context — what the user was doing when they noticed it)  
**The problem:** (what's wrong or missing)  
**Current state of the code:** (what exists vs what's missing — saves investigation time)  
**What's needed to fix:** (specific work required)  
**Resolution:** (how it was fixed, date, commit — fill in when done)  
```

---

## Open

---

### ISSUE-001 — No skip button in quiz UI
**Noticed:** 2026-05-11
**Reported by:** Rahul
**Status:** Resolved
**Priority:** P1
**Linked feature:** `FEATURES.md` queue item to add; extends `plans/metacognition_capture.md`

**What happened:**
Rahul noted during study sessions that there is no way to skip a question intentionally.
In the real UPSC Prelims, skipping is a deliberate strategy — candidates skip when uncertain
to avoid negative marking (−0.66 per wrong answer). The current quiz forces a selection or
abandonment of the session, which doesn't reflect actual exam conditions.

**The problem:**
No Skip button exists in the diagnostic session UI. Users cannot intentionally skip a
question the way they would in the real exam. This also means:
- No record of which questions the user chose not to attempt
- No data on skip patterns per subject/topic (which would signal uncertainty clusters)
- Exam strategy practice is unrealistic without the skip option

**Current state of the code:**
Backend is **100% complete** — no backend work needed:
- `session_answers.skipped` column exists in the DB schema
- `score_engine.record_answer()` already stores the `skipped` flag (`answer.get("skipped")`)
- `close_session()` already excludes skipped answers from score: `correct / max(total - skipped, 1)`
- `_store_session_summary()`, `_update_subtopic_scores()`, `_update_subtopic_difficulties()`
  all already handle `skipped=True` rows correctly

Frontend (`web/src/app/diagnostic/page.tsx`): **zero skip functionality** — no button, no
state, nothing. Grep for "skip" returns no results in the file.

**What's needed to fix:**

*Part A — Skip button (est. ~1–2 hrs frontend only):*
1. Add a `[Skip →]` button below the answer options (before the user has selected anything)
2. On click: call `api.submitAnswer({ ..., skipped: true, user_answer: null, is_correct: false })`
3. Button should disappear once an option is selected or answer is revealed
4. Advance to next question the same way a normal answer does

*Part B — Skip metacognition (est. ~1 hr, depends on `plans/metacognition_capture.md` Phase 2):*
After user clicks Skip, show a lightweight prompt before advancing:
```
Why are you skipping?
[ Uncertain — can't decide ]   [ Risky — avoiding negative marking ]
[ Completely unfamiliar ]      [ Running out of time ]
                                                    [ Skip without reason → ]
```
Store as a new `skip_reason` field in `answer_metacognition` table.
This data signals: is the user applying good exam strategy (skipping tactically) or
skipping out of disengagement?

*Part B is optional and should be built as part of the metacognition capture feature, not
as a prerequisite for Part A. Ship Part A first independently.*

**Resolution:** Fixed 2026-05-11. Added `skipQuestion()` in `web/src/app/diagnostic/page.tsx` — calls `api.submitAnswer` with `skipped: true, user_answer: null`, sets `revealed` so Next/Finish buttons appear. Skip button hidden once any option is selected. Skipped card shows correct answer. Finish screen shows skipped count separately; score % is calculated over attempted questions only (not skipped). Backend was already complete.

---

## Resolved

### ISSUE-001 — see Open section above (moved to Resolved 2026-05-11)

---

## Won't fix

*(none yet)*

---

## How to add a new issue

1. Copy the format block at the top
2. Increment the issue number (ISSUE-002, etc.)
3. Fill in all fields — especially "Current state of the code" so the next person
   doesn't have to re-investigate
4. Add it under **Open**
5. When resolved: move it to **Resolved**, fill in the Resolution field, commit
