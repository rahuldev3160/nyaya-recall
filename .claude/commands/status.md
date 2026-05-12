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
[Top 3 from FEATURES.md Queued/Planned]

### Servers
[Run: lsof -i:3000 -i:8000 | grep LISTEN to check if backend and frontend are running]
---
