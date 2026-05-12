#!/bin/bash
# log-issue: quickly append a new issue to ISSUES.md from anywhere
# Usage: log-issue "description of the problem"
# Example: log-issue "skip button disappears too early on mobile"

PROJECT_DIR="/Users/rahulsingh/Desktop/Claude Projects/Last 10 Day AI powered Preparation"
ISSUES_FILE="$PROJECT_DIR/ISSUES.md"

if [ -z "$1" ]; then
  echo "Usage: log-issue \"description of the problem\""
  exit 1
fi

DESCRIPTION="$1"
DATE=$(date +%Y-%m-%d)

# Find the next issue number
LAST_NUM=$(grep -o 'ISSUE-[0-9]*' "$ISSUES_FILE" | grep -o '[0-9]*' | sort -n | tail -1)
NEXT_NUM=$(printf "%03d" $((LAST_NUM + 1)))
ISSUE_ID="ISSUE-$NEXT_NUM"

# Build the new issue entry
NEW_ENTRY="
### $ISSUE_ID — $DESCRIPTION
**Noticed:** $DATE
**Reported by:** Rahul
**Status:** Open
**Priority:** P1
**Linked feature:** *(to be linked)*

**What happened:**
*(fill in — what were you doing when you noticed this)*

**The problem:**
$DESCRIPTION

**Current state of the code:**
*(Claude to investigate)*

**What's needed to fix:**
*(Claude to determine)*

**Resolution:** *(pending)*

---"

# Insert after the "## Open" header and the "---" separator
# Find the line number of the first "---" after "## Open"
OPEN_LINE=$(grep -n "^## Open" "$ISSUES_FILE" | head -1 | cut -d: -f1)
INSERT_AFTER=$((OPEN_LINE + 2))

# Use Python for reliable multi-line insertion
python3 - <<PYEOF
with open("$ISSUES_FILE", "r") as f:
    lines = f.readlines()

insert_at = $INSERT_AFTER
entry = """$NEW_ENTRY\n"""

lines.insert(insert_at, entry)

with open("$ISSUES_FILE", "w") as f:
    f.writelines(lines)

print("✓ Logged $ISSUE_ID: $DESCRIPTION")
print("  File: $ISSUES_FILE")
PYEOF

# Auto-commit so it's immediately visible on GitHub
cd "$PROJECT_DIR" && git add ISSUES.md && git commit -m "Log $ISSUE_ID: $DESCRIPTION" --quiet 2>/dev/null && echo "  Pushed to git ✓" || echo "  (git commit skipped — check remote)"
