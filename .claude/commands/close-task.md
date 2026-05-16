Run the following close-out sequence after completing ANY task — feature, bug fix, script execution, or investigation. The goal is to eliminate stale open-item entries that regenerate work already done. Do every step; do not skip any even if it "seems fine."

---

## Step 1 — FEATURES.md reconciliation

Read FEATURES.md. For each item in the Queued table:
- If it has a strikethrough (`~~`) → check HANDOFF.md "Open Problems" section. If HANDOFF.md still lists it as an open problem (not marked ✅), update HANDOFF.md to mark it resolved. Add the audit result or outcome in 1–2 sentences.
- If it was completed this session and NOT yet struck through → strike it through in the Queued table AND add it to the ✅ Shipped section with a one-line description and "Shipped [date]" note.

## Step 2 — ISSUES.md reconciliation

Read ISSUES.md Open section. For each issue:
- If the fix was shipped in a merged PR this session → move it from Open to Resolved. Fill in the Resolution field: what changed, which file, which PR, date.
- If a new issue was discovered this session and not yet logged → add it with the next ISSUE-NNN number (check "Next issue number:" at the bottom of ISSUES.md) and fill all fields.

## Step 3 — HANDOFF.md top-of-file update

Add a new entry at the very TOP of HANDOFF.md (before existing entries) with this structure:

```
### [Feature/Fix name] — [YYYY-MM-DD]

**What changed:**
- [bullet: file modified and what changed]
- [bullet: any DB changes, new tables, new endpoints]

**Watch-outs:**
- [anything that could break, need follow-up, or requires Rahul's awareness]

**Branch:** [branch name] — merged as PR #N (or: committed to main)
```

If the task was a script execution or investigation with no code change, use this instead:
```
### [Task name] — YYYY-MM-DD (no code change)

**What ran:** [script name and what it did]
**Result:** [key finding or outcome in 1–2 sentences]
**Status:** Closed — no further action needed / [or: follow-up required: X]
```

## Step 4 — Memory write

For any item that was:
- Previously listed as open/queued AND is now resolved, OR
- A factual finding (audit result, DB state, one-time script output) that future sessions should know

Write a memory entry:
1. Create `memory/project_<slug>.md` with frontmatter type: project
2. Add a one-line pointer to MEMORY.md

The memory entry should answer: "What would the next Claude session need to know to avoid re-opening this?" Include the result, the date, and a "How to apply" note that says explicitly: do not re-raise this as an open item.

## Step 5 — Cross-check (the leak detector)

Run this check every time:

```
For each item in HANDOFF.md that is NOT marked ✅:
  → Is it struck through in FEATURES.md Queued? → If yes, mark it ✅ in HANDOFF.md.
  → Is it listed as Resolved in ISSUES.md? → If yes, mark it ✅ in HANDOFF.md.
  → Is it in FEATURES.md ✅ Shipped? → If yes, mark it ✅ in HANDOFF.md.
```

This is the step that caught the ChromaDB leak. HANDOFF.md is the source that status.md and next-task.md read — if it has stale open items, every future session picks them up.

## Step 6 — Commit the doc updates

Stage and commit only the tracking file changes (FEATURES.md, ISSUES.md, HANDOFF.md) with a commit message like:
```
docs: post-task close-out — [brief description of what was completed]
```

Push to main directly if all changes are documentation only. Open a PR only if there are code changes mixed in.

---

## What NOT to do

- Do not create new ISSUES.md entries for things already in FEATURES.md Queued — they are tracked there.
- Do not move a HANDOFF.md entry to "resolved" unless the code/script actually ran and was verified.
- Do not write memory for ephemeral task state (branch names, in-progress steps) — only for permanent factual findings.
- Do not update HANDOFF.md "What changed" with speculation — only things that actually happened.
