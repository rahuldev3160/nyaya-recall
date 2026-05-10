# Planning — open questions and merge gates

## Active goals

1. Keep `main` stable for daily study use (Rahul).
2. Ship high-priority fixes via `fix/*` and features via `feature/*` + PR.
3. Batch documentation updates (CHRONICLE + PROJECT_TRACKER) to reduce token noise.

## Open questions

| Topic | Question | Owner | Target date |
|-------|----------|-------|-------------|
| Multi-user | When to replace `user_id = 'user_1'` (if ever)? | TBD | Post-exam |
| Chronicle automation | Optional: hook `sync_tracker.py` to CI for diff-only comments? | TBD | Backlog |

## Next merge gates (you choose when)

- [ ] **Gate A:** Simulation log in `PROJECT.md` complete through plan generation + attestation.
- [ ] **Gate B:** Friend confirms local clone + `.env` + ingest optional path.
- [ ] **Gate C:** First PR that only touches `docs/` + `scripts/sync_tracker.py` merged (workflow proof).

## Planning session (Claude Code) — standing instruction

> Use the **planning-only** session. Prefer edits under `docs/` and `plans/`. Do not change `backend/` or `web/` unless the user explicitly says **implement**.

See [agents/planning_agent.md](agents/planning_agent.md).
