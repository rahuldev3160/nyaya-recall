# Project documentation

| File | Purpose |
|------|---------|
| [CHRONICLE.md](CHRONICLE.md) | Dated **decisions** (what, why, alternatives, impact) |
| [PLANNING.md](PLANNING.md) | Forward planning, open questions, next merge gates |
| [PROJECT_TRACKER.md](PROJECT_TRACKER.md) | Batched **Now / Next / Later** (sync with `scripts/sync_tracker.py`) |
| [tracker_state.json](tracker_state.json) | Last sync anchor for cheap git-delta summaries |
| [adr/](adr/) | Architecture Decision Records (numbered) |
| [agents/](agents/) | Reusable **agent charters** (planning vs implementation vs audit) |

**Single source of truth for shipped features:** root [`../PROJECT.md`](../PROJECT.md).

**Collaboration context:** root [`../COLLAB.md`](../COLLAB.md) and [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

## Updating the tracker (cost-aware)

1. Run from repo root: `python3 scripts/sync_tracker.py`
2. Paste the printed **Git delta summary** into your AI session (or use it yourself).
3. Append a new dated section to `CHRONICLE.md` only for **meaningful** decisions.
4. Update `PROJECT_TRACKER.md` **Now / Next / Later**; refresh detailed tables in `PROJECT.md` when something ships.

Do **not** re-summarize the entire repo each time; the script only uses `git log` / `git diff --stat` since `last_sync_git_sha`.
