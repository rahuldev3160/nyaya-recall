Read FEATURES.md, ISSUES.md, and HANDOFF.md then output a concise status report in this format:

---
## Model status — [today's date]

### Open issues (blocking)
[List all ISSUES.md Open items with status]

### In-flight (branches not yet merged)
[Run: git branch -a | grep -v main to list active branches]

### Shipped recently
[Last 5 items from FEATURES.md ✅ Shipped section]

### Up next (top 3 by priority)
[Top 3 from FEATURES.md Queued/Planned — skip any struck-through rows]

### Servers
[Run: lsof -i:3000 -i:8000 | grep LISTEN to check if backend and frontend are running]

### Stale item check ⚠️
Cross-check HANDOFF.md open problems against FEATURES.md and ISSUES.md.
For each item in HANDOFF.md NOT marked ✅:
- If it appears struck through (~~) in FEATURES.md Queued → flag it as STALE
- If it appears in ISSUES.md Resolved → flag it as STALE
- If it appears in FEATURES.md ✅ Shipped → flag it as STALE

List any stale items found as:
  ⚠️ STALE: "[item name]" — in HANDOFF.md as open but already resolved in [FEATURES.md / ISSUES.md]
  → Run /close-task to fix

If no stale items: print "✅ No stale items — all tracking files in sync"
---
