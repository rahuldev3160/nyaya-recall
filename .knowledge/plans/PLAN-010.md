---
id: PLAN-010
type: plan
project: devthorium
date: 2026-08-29
status: PENDING RAHUL APPROVAL (B-4)
---

# PLAN-010: Fix sar_scores' broken multi-user primary key (B-4)

**Scope note:** Fix drafted and tested on branch `fix/sar-scores-pk`, NOT merged to
main, NOT run against `data/upsc.db`. Devthorium's CLAUDE.md lists any ALTER TABLE
on an existing table as a hard approval gate — this is ready to merge/run the moment
Rahul approves, not before.

## The real bug (confirmed by reading every read/write site, not assumed)

`sar_scores` schema: `user_id TEXT PRIMARY KEY DEFAULT 'user_1'`. Only one row is ever
seeded — `'user_1'`, once, at `db_init.py` time. No code path anywhere inserts a row
for any other `user_id`.

- `backend/routes/tracker.py`'s `GET /sar` reads with a safe fallback (`if not row:
  return {"sar": 0.5, ...}`) — **not broken**, already handles a missing row.
- `scripts/self_attestation.py`'s `_update_sar()` and `record_attestation()` write via
  plain `UPDATE sar_scores SET ... WHERE user_id=?` — for any `user_id` other than
  `'user_1'`, this affects **zero rows, silently, no error**. A second real user's SAR
  score is computed correctly in memory (returned in the API response) but **never
  persisted**. Next read falls back to the 0.50 default again — their self-attestation
  reliability tracking silently never accumulates.

This is a live-data-silent-drop bug, not (currently) a crash — a bare PRIMARY KEY on
`user_id` doesn't itself throw on a second user, because nothing ever tries to INSERT
a second user's row in the first place. The PK design is still wrong (it's the reason
no INSERT path was ever safely addable), and `scripts/migrate_to_postgres.py` already
independently arrived at the same corrected target schema for the eventual Postgres
migration (its own comment: "PRIMARY KEY changed from user_id (broken for multi-user)
→ id SERIAL") — this PR makes the same fix on the current SQLite side now, so the bug
doesn't wait on a Postgres migration that has no committed date yet.

**Not a blocker for Nyaya Arena's leaderboard**, despite PLAN-006's original note —
grep-verified this session: Arena's own code never reads or writes `sar_scores` at
all (separate Postgres project, stateless internal-API design, DECIDE-09). This fix is
solely about Recall's own multi-user correctness once real Supabase auth brings a
second real person into Recall itself.

## The fix (implemented, tested, not merged)

1. **`scripts/db_init.py`** — fresh-install schema: `sar_scores` gets a surrogate
   `id INTEGER PRIMARY KEY AUTOINCREMENT`, `user_id` becomes `TEXT NOT NULL UNIQUE`
   instead of the PK. Only affects new installs.
2. **`scripts/fix_sar_scores_pk.py`** (new) — one-off, idempotent migration for the
   existing `data/upsc.db`: rename table, recreate with the new schema, copy rows
   over, drop the old table. Tested against a throwaway copy of the real DB (never
   touched the original): 1 pre-existing row preserved exactly, running it twice is
   a safe no-op.
3. **`scripts/self_attestation.py`** — `_update_sar()` and `record_attestation()`
   changed from blind `UPDATE` to `INSERT ... ON CONFLICT(user_id) DO UPDATE`
   (SQLite upsert). Tested directly: a synthetic second user (`user_2_real`) now gets
   a real row created on first attestation and correctly incremented on the second,
   where before both writes would have silently no-op'd.

## To approve and apply

```
git checkout fix/sar-scores-pk
python scripts/fix_sar_scores_pk.py          # runs against data/upsc.db (real DB)
git checkout main && git merge fix/sar-scores-pk
```

Do this before Recall has any real second user (Supabase auth wiring, or any local
testing with more than `user_1`) — until then this bug stays invisible.
