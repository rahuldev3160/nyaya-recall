# Agent charter — Implementation (primary chain)

## Role

Ship code and tests that match an agreed spec (issue + `plans/*.md` or issue-only).

## May edit

- `backend/**`, `web/**`, `scripts/**`, `prompts/**`
- Root `README.md`, `CONTRIBUTING.md` when behavior changes require it

## Should also update

- `PROJECT.md` when a feature ships or simulation status changes materially.
- `docs/CHRONICLE.md` when the change reflects a **decision** (not every bugfix).

## Must not do without explicit approval

- Change `data/syllabus.json` taxonomy IDs.
- Add per-question API calls during an active quiz session.
- Reintroduce Next.js proxy for long-running Claude calls (use direct backend per `COLLAB.md`).

## Inputs

- GitHub issue, `PROJECT.md`, relevant `plans/<feature>.md`.

## Definition of done

- PR-sized change with **how to test** steps.
- Prompts remain in `prompts/*.txt`, not inline in Python/TS.
