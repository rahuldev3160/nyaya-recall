Read the following files in order and then output a precise, actionable briefing for the next task:
1. FEATURES.md — find the highest-priority Open item (P0 first, then P1, then P2). Check ISSUES.md Open section first — open bugs beat feature work.
2. If the item is in 🔵 Planned, read the linked spec file in plans/.
3. HANDOFF.md — read "What was fixed" and "Open problems" sections.
4. CLAUDE.md — re-read the "Autonomous agent workflow" section.

Then output EXACTLY this structure (no other text):

---
## Next task
**Item:** [feature/issue name and ID]
**Priority:** [P0/P1/P2]
**Type:** [Bug fix / Feature / Spec]
**Spec file:** [path to plans/ file, or "None — write spec first"]

## Context (what you need to know)
[3-5 bullet points: current state of the code, what exists, what's missing]

## What to implement
[Numbered steps from the spec, or steps you derive from the issue description]

## Files to touch
[List the specific files — be precise]

## Definition of done
[What passing looks like: typecheck passes, behaviour in browser, DB rows created, etc.]

## Branch name
[feature/... or fix/...]
---

After outputting the briefing, immediately begin implementation without waiting for further instructions.
