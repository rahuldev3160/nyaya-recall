# Feature Plan: Streak + Daily Goal Tracker

**Status:** Planned
**Priority:** High
**Trigger:** Onboarding redesign discussion — need a hook to bring users back daily

---

## Problem

Nothing in the current app creates daily return habit.
User completes a session, closes the tab, might not open it again for 2 days.
10 days of prep = 10 days of consistent use. Streaks enforce this.

---

## Proposed Design

### Dashboard widget (top of page, below header)
```
🔥 Day 3 streak  |  Today: 2/3 sessions done  |  45 min studied
[███████░░░] 67% of today's goal
```

### What counts as "a day done"
- At least 1 diagnostic or adaptive session completed AND closed
- Batch analysis run (optional bonus — adds a star ⭐ to the day)

### Streak display
- 0 days: "Start your streak today"
- 1 day: "Day 1 — great start"
- 3+ days: "🔥 X day streak"
- 7+ days: "🔥🔥 X day streak — you're on fire"
- Streak broken: "Streak reset. Day 1 — no worries, let's go."

### Calendar view (on Tracker page)
Small calendar showing:
- Green dot = session completed that day
- Amber dot = analysis run
- Empty = missed
- Today = pulsing ring

---

## Implementation Notes

### New DB table: `daily_activity`
```sql
CREATE TABLE IF NOT EXISTS daily_activity (
    activity_date  TEXT PRIMARY KEY,
    sessions_done  INTEGER DEFAULT 0,
    minutes_studied INTEGER DEFAULT 0,
    analysis_run   INTEGER DEFAULT 0,
    streak_day     INTEGER DEFAULT 0
);
```

### Backend
- `GET /activity/streak` → returns current streak, today's sessions, today's minutes
- `GET /activity/calendar?days=30` → returns last 30 days of activity dots
- Auto-updated by `close_session()` and `run_analysis()`

### Frontend
- Dashboard: streak widget between header and quick-action buttons
- Tracker: calendar grid at bottom of page

---

## Files to create/change
- `scripts/db_init.py` — add `daily_activity` table
- `scripts/score_engine.py` — update `close_session()` to record daily activity
- `scripts/batch_analyse.py` — update `run_analysis()` to mark analysis_run
- `backend/routes/activity.py` — new route file
- `backend/server.py` — add activity router
- `web/src/app/page.tsx` — add streak widget
- `web/src/app/tracker/page.tsx` — add calendar view

---

## Merge condition
Build after onboarding redesign is complete.
Estimated build time: 1.5 hours.
