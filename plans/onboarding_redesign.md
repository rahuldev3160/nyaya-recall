# Feature Plan: Engaging Onboarding / First-Open Experience

**Status:** Planned
**Priority:** High
**Trigger:** Simulation Step 1 — current setup is functional but not emotionally engaging

---

## Problem

The current `/setup` page is a form. It works, but:
- User can ignore it and go straight to dashboard (no hard gate)
- 10-day default is pre-filled — users accept it without thinking
- No emotional hook to their actual exam date / urgency
- Nothing that makes them *want* to come back tomorrow

## Goal

Make the first-open experience feel like a commitment ritual, not a settings screen.
User should leave Setup feeling: "This system knows my situation and has a plan for me."

---

## Proposed Flow (3 screens, ~2 min total)

### Screen 1 — Exam date anchor
```
"When is your UPSC Prelims exam?"
[Date picker — defaulting to June 1, 2026]

Days remaining: 21 days          ← auto-calculated, big number, amber
"That's tight. Let's make every day count."   ← dynamic message based on days
```
Dynamic messages:
- ≤7 days: "Final sprint mode. We'll focus only on high-frequency topics."
- 8–14 days: "Intensive mode. Diagnostic first, then targeted revision."
- 15–45 days: "Solid window. Diagnostic → Learning → Revision → Mock."
- >45 days: "Great runway. We'll go deep on every subject systematically."

### Screen 2 — Daily commitment
```
"How many hours can you realistically study each day?"
[Visual tiles, not slider]
  [2h]  [3h]  [4h]  [5h]  [6h]  [8h]  [10h]
  "Light"       "Standard"      "Intensive"  "All-in"

Total study hours available: 126h
```

### Screen 3 — Plan preview + confirm
```
"Here's your personalised plan"

[Timeline bar: Diagnostic 2d | Learning 5d | Revision 8d | Mock 6d]

Daily targets:
  📖 Morning: 1 diagnostic session (45 min)
  🔁 Afternoon: 1 revision session (60 min)
  📊 Evening: Review + 15 min batch analysis

[  Start My Prep  ]
```

---

## Implementation Notes

- All 3 screens are within `/setup/page.tsx` using a `step` state variable (1 | 2 | 3)
- Exam date → auto-calculates `total_days` (no manual entry)
- `total_days` and `daily_hours` still saved to `data/prep_config.json` via `/config/` API
- Hard gate: if no config exists, dashboard shows a full-width CTA that blocks the quick-action buttons (soft gate — user can still scroll past, but the message is prominent)
- After save, confetti animation (CSS only, 1 second) then redirect to dashboard
- Returning users: `/setup` shows current config pre-filled with "Edit" mode

---

## Files to change
- `web/src/app/setup/page.tsx` — full rewrite as 3-step flow
- `web/src/app/page.tsx` — strengthen the "no config" CTA to be more prominent

---

## Merge condition
Build this after simulation is complete and all simulation bugs are fixed.
Estimated build time: 45 minutes.
