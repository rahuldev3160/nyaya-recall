# Project tracker — batched view

**Detailed tables** (simulation steps, shipped features): see root [`PROJECT.md`](../PROJECT.md).

This file is optimized for **quick scans** and **sync-time updates** (with [`scripts/sync_tracker.py`](../scripts/sync_tracker.py)).

---

## Now (this week)

- [ ] Complete simulation steps pending in `PROJECT.md` (plan generation → attestation → adaptive session → second batch analysis).
- [ ] Keep GitHub issues labeled (`bug`, `high-priority`, etc.).

## Next (queued)

- [ ] Mock test mode spec in `plans/` (see `COLLAB.md` rough spec).
- [ ] Streak + daily goal tracker ([`plans/streak_tracker.md`](../plans/streak_tracker.md)).

## Later / post-exam

- [ ] Onboarding redesign.
- [ ] Offline / phone export.
- [ ] Multi-user / dynamic `user_id` (major).

## Blocked

- None recorded.

---

## How to update

1. Run `python3 scripts/sync_tracker.py` from repo root.
2. Use the printed git summary + your notes to adjust **Now / Next / Later** above.
3. For anything shipped or decided, add a dated entry to [`CHRONICLE.md`](CHRONICLE.md) and move rows in [`PROJECT.md`](../PROJECT.md).
