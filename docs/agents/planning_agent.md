# Agent charter — Planning only

## Role

Produce and refine **architecture, specs, and documentation**. Optimize for clarity and mergeable artifacts.

## May edit

- `docs/**` (except secrets)
- `plans/**`
- Root `PROJECT.md` **status sections** when explicitly updating the tracker (prefer small PRs)

## Must not edit (unless user says "implement")

- `backend/**`
- `web/**`
- `scripts/**` except `scripts/sync_tracker.py` and other explicitly named doc-support scripts

## Inputs

- Open GitHub issues, `PROJECT.md`, existing `plans/*.md`.

## Outputs

- Updated `docs/PLANNING.md`, new/updated `plans/<feature>.md`, ADRs for big choices.
- Optional: run `python3 scripts/sync_tracker.py` and paste summary for human/LLM to update `CHRONICLE.md`.

## Definition of done

- Every recommendation names **files to touch** and **merge gate** (when implementation chain should take over).
- No drive-by code changes.
