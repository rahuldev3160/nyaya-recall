# Feature Plan: User-Editable Daily Plan (IDEA-003)

**Status:** Spec (awaiting Rahul review)
**Priority:** P2
**Source:** FEATURE_IDEAS.md IDEA-003
**Logged:** 2026-05-16

---

## Problem

The AI-generated daily plan is a fixed artifact: once `plan_generator.py` writes `study_plan.json`, it is consumed by the Session page as-is. There is no mechanism for Rahul to make targeted edits before starting sessions. Real friction points:

- A session covers a subtopic he already feels confident about today — he skips it mentally but the planner keeps it.
- He wants to front-load a high-stakes session instead of it sitting at position 5.
- The format recommendation (`notes_then_quiz`) doesn't match his current energy level — he wants to flip it to `quiz_only`.
- A session's estimated time is obviously wrong (45 min for 12 questions) — he wants to correct it so his mental schedule is accurate.
- The plan has 9 sessions but he only has 5 hours today instead of 8 — he needs to trim without regenerating and burning another Sonnet call.

The edited plan — not the raw model output — should be what drives session generation.

---

## User Flow (what the user sees / does — step by step)

1. Rahul visits `/planner` and clicks "Plan Today" (unchanged from today).
2. Plan renders as a list of session cards (unchanged).
3. Each session card now has an **Edit** icon (pencil) in the top-right corner.
4. Clicking the Edit icon expands the card into an inline edit form showing:
   - Format selector: `quiz_only` | `notes_then_quiz` | `open_practice`
   - Duration: number input (minutes)
   - Number of questions: number input
   - Difficulty: `easy` | `medium` | `hard` | `mixed`
   - A **Remove session** button (trash icon)
5. A **Reorder** handle (drag icon) on each card lets him drag sessions up/down to reprioritise.
6. A **+ Add session** button below the list opens a form to add a new session manually (subject, subtopic, format, duration, num_questions).
7. As he edits, the total estimated time recalculates live in the plan header.
8. An **"Apply edits"** button saves the edited plan. The original AI output is preserved separately — a **"Reset to AI plan"** link discards all edits and restores it.
9. The Session page (`/session`) consumes the edited plan (same `GET /plan/today` endpoint — no change to session page code).

---

## What's Editable (specific fields per session)

| Field | UI Control | Constraint |
|---|---|---|
| `format` | 3-button toggle | One of: `quiz_only`, `notes_then_quiz`, `open_practice` |
| `estimated_minutes` | Number input | Min 10, max 180 |
| `num_questions` | Number input | Min 5, max 30 |
| `difficulty` | Dropdown | `easy`, `medium`, `hard`, `mixed` |
| Session order | Drag handle | Reorder only — no gaps in `order` field |
| Remove session | Trash button | Soft-delete from sessions array |
| Add session | Form | Requires: `subject_id`, `subtopic_id`, `format`; defaults: 30 min, 10 questions, medium |

**Not editable in v1:** `subject_id`, `subtopic_id`, `topic_id` of existing sessions (avoids breaking downstream quiz generation), `rationale`, `daily_goal`, `skip_subjects`.

---

## Persistence Approach

### Options considered

**Option A — Edit study_plan.json in-place**
Overwrite `data/study_plan.json` with the edited version. Simple. But destroys the AI output — no way to "reset to AI plan".

**Option B — New file `data/study_plan_user.json`**
Keep `study_plan.json` as the pristine AI output. Write edits to `study_plan_user.json`. `GET /plan/today` returns user version if it exists, falls back to AI version. A `DELETE /plan/user-overrides` endpoint resets to AI plan. File is automatically deleted when plan is regenerated.

**Option C — New DB table `plan_overrides`**
Store per-session overrides in SQLite with a `plan_date` key. More structured, queryable. But adds migration complexity and per-session granularity is hard to use for "add session" or "reorder".

### Recommendation: Option B

Rationale:
- `study_plan.json` is already a well-understood contract. Adding a parallel `study_plan_user.json` is zero-risk — the fallback keeps existing behaviour intact.
- File-based approach matches all other data files in this project (no new DB tables).
- Plan regeneration can simply delete `study_plan_user.json` before writing `study_plan.json` — zero edit carryover risk.
- "Reset to AI plan" is one file delete.
- No schema migration needed. No approval gate required.

**Edit index:** The user plan file adds a top-level `"user_edits": true` flag and `"edited_at": "<ISO timestamp>"` so the plan history (HANDOFF notes, debugging) can distinguish user-edited plans from AI-generated ones. Each modified session gets `"user_edited": true` added inline for audit.

---

## API Changes Needed

### New endpoints (additive — no approval required)

| Method | Path | Purpose |
|---|---|---|
| `PATCH /plan/user-sessions` | Save edited sessions array to `study_plan_user.json` | Body: `{ sessions: [...], daily_goal?: string }` |
| `DELETE /plan/user-overrides` | Delete `study_plan_user.json` → restores AI plan | Response: `{ reset: true }` |

### Modified endpoints

| Method | Path | Change |
|---|---|---|
| `GET /plan/today` | No signature change | Checks for `study_plan_user.json` first; falls back to `study_plan.json`. Returns a new field `is_user_edited: bool` so the frontend can show "Edited" badge. |

### Unchanged endpoints
- `POST /plan/generate` — triggers `plan_generator.py`, which deletes `study_plan_user.json` before writing (to be added inside `generate_plan()`).
- All session/quiz endpoints — they consume plan fields from `GET /plan/today`, which already returns the right version.

---

## Key Files to Change

| File | What changes | Rough lines |
|---|---|---|
| `backend/routes/plan.py` | `GET /plan/today` reads user plan first; add `PATCH /plan/user-sessions`; add `DELETE /plan/user-overrides` | +40 lines |
| `scripts/plan_generator.py` | In `generate_plan()`: delete `study_plan_user.json` if it exists before writing the new AI plan | +5 lines |
| `web/src/app/planner/page.tsx` | Inline edit form per session card; drag-to-reorder; Add Session form; Apply Edits / Reset buttons; live total time counter | +150–200 lines |
| `web/src/lib/api.ts` | Add `patchUserPlan()` and `deleteUserPlanOverrides()` calls | +15 lines |

No new DB tables. No prompt changes. No score engine changes.

---

## Edge Cases

**1. Editing after a session has already started**
The session page creates a quiz session (`POST /sessions/start`) which captures `subject_id`, `subtopic_id`, `format`, `num_questions` at start time. Editing the plan after start does not affect an in-progress session — those fields are already sent to the backend. Only future sessions in the same day's plan are affected. No guard needed, but the UI should grey out "completed" sessions (already done in session page via `completedSessions` set) and not allow editing them.

**2. Plan regeneration overwrites user edits**
Plan regeneration calls `POST /plan/generate`. The backend deletes `study_plan_user.json` before writing the new AI plan. A confirmation modal should appear in the planner UI if `is_user_edited: true`: "You have a custom plan for today. Regenerating will discard your edits. Continue?" This prevents accidental overwrites.

**3. Add-session subtopic not in syllabus**
The "Add session" form should offer a searchable dropdown of valid `subject_id` + `subtopic_id` pairs (loaded from `GET /sessions/subtopics` or similar). Free-text entry risks entering invalid IDs that break quiz generation. If a full subtopic picker is out of scope for v1, accept free-text but add a disclaimer: "Subtopic must match syllabus IDs exactly."

**4. Drag-to-reorder on mobile (phone access)**
Rahul uses the app on his phone via Tailscale. Touch-based drag-and-drop requires a touch-enabled DnD library (e.g. `@dnd-kit/core` which supports both mouse and touch). Fallback: up/down arrow buttons on each card. Arrow buttons are simpler to implement and work on all devices — recommend as v1.

**5. User adds a session with no study material in ChromaDB**
Quiz generation for a subtopic with no indexed chunks returns stub questions. This is pre-existing behaviour, not caused by this feature. The disclaimer on the Add Session form should note: "Questions depend on indexed study material."

**6. study_plan_user.json left from a previous day**
If today's date doesn't match the `generated_at` date in `study_plan_user.json`, `GET /plan/today` should treat it as stale and fall back to `study_plan.json`. Add a date-check guard when reading the user plan.

---

## Effort Breakdown

| Component | Tasks | Estimate |
|---|---|---|
| **Backend** | `GET /plan/today` user-plan fallback + `is_user_edited` flag; `PATCH /plan/user-sessions`; `DELETE /plan/user-overrides`; stale-date guard | 1.5 hrs |
| **`plan_generator.py`** | Delete user plan on regeneration | 0.25 hrs |
| **Frontend — edit form** | Inline edit per session card (format toggle, duration, num_questions, difficulty, remove button) | 2.5 hrs |
| **Frontend — add session** | Add Session form with subject/subtopic inputs, defaults | 1.5 hrs |
| **Frontend — reorder** | Up/down arrows per session card (skip DnD library for v1) | 0.5 hrs |
| **Frontend — confirmation modal** | "Regenerate will discard edits" guard | 0.5 hrs |
| **API client** | `patchUserPlan`, `deleteUserPlanOverrides` in `api.ts` | 0.25 hrs |
| **Total** | | **~7 hrs** |

---

## Decision Required from Rahul

No approval gates are triggered (no ALTER TABLE, no score engine changes, no prompt changes, no .env changes). This is fully autonomous to build.

One design question worth flagging before building:

> **v1 scope: should "Add Session" require an exact subtopic ID, or show a searchable dropdown?**
>
> A dropdown requires either a new `GET /sessions/subtopics` endpoint or loading the syllabus.json on the frontend (file is large, ~200KB). A free-text field is simpler but error-prone. Recommended: free-text in v1 with a note, and upgrade to dropdown in v2 when there is more time. Rahul can confirm this via a PR comment.

No other blocking decisions. The feature is low-risk: it only modifies a sidecar file and adds new endpoints. No existing data, scoring logic, or session flow is changed.
