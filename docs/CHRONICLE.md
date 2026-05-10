# Chronicle — project decisions

Structured log of **significant** decisions. Small fixes and typos do not need entries.

**Format per entry:**

```text
## YYYY-MM-DD — Short title

- **Context:** …
- **Decision:** …
- **Alternatives considered:** …
- **Impact:** …
- **Owner:** …
```

---

## 2026-05-11 — Documentation: chronicle, batched tracker, agent charters

- **Context:** GitHub collaboration is live; need reusable planning methodology and cheap tracker updates.
- **Decision:** Add `docs/CHRONICLE.md`, `docs/PROJECT_TRACKER.md`, `docs/PLANNING.md`, ADR template, agent charters, and `scripts/sync_tracker.py` (git-delta only).
- **Alternatives considered:** Log every change in chat (noisy, expensive); duplicate all of `PROJECT.md` in `docs/` (drift risk).
- **Impact:** Decisions and batched status live in git; collaborators merge planning docs via PRs.
- **Owner:** Team consensus.
