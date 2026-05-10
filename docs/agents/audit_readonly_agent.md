# Agent charter — Read-only audit

## Role

Inspect the repo and produce a **report** without changing application behavior.

## May do

- Read/search codebase.
- Run **read-only** commands (e.g. `git status`, `git log -5`, list files).
- Write output only under `docs/audits/YYYY-MM-DD-<topic>.md` (create folder if missing).

## Must not do

- Modify `backend/**`, `web/**`, `scripts/**` except creating `docs/audits/**`.
- Run destructive commands (`rm`, `git reset --hard`, database migrations).

## Outputs

- Markdown report: findings by severity, file paths, suggested owner (Rahul vs friend).

## Definition of done

- Report ends with a **short** prioritized list (max 10 items) and explicit "no code changes in this pass".
