#!/bin/bash
# log-feature: quickly append a new idea to FEATURE_IDEAS.md from anywhere
# Usage: log-feature "idea description"
# Example: log-feature "add a heatmap of subtopics studied per day"

PROJECT_DIR="/Users/rahulsingh/Desktop/Claude Projects/Last 10 Day AI powered Preparation"
IDEAS_FILE="$PROJECT_DIR/FEATURE_IDEAS.md"

if [ -z "$1" ]; then
  echo "Usage: log-feature \"idea description\""
  exit 1
fi

DESCRIPTION="$1"
DATE=$(date +%Y-%m-%d)

# Find the next IDEA number
LAST_NUM=$(grep -o 'IDEA-[0-9]*' "$IDEAS_FILE" | grep -o '[0-9]*' | sort -n | tail -1)
NEXT_NUM=$(printf "%03d" $((LAST_NUM + 1)))
IDEA_ID="IDEA-$NEXT_NUM"

# Build the new idea entry
NEW_ENTRY="
### $IDEA_ID — $DESCRIPTION
**Logged:** $DATE
**Source:** terminal
**Status:** Raw
**Priority guess:** P2

**What's the idea:**
$DESCRIPTION

**Why it matters:**
*(fill in — what friction does this solve?)*

---

**[Claude] Recommendation:** *(to be filled)*
**[Claude] Feasibility:** *(to be filled)*
**[Claude] Impact on prep:** *(to be filled)*
**[Claude] Effort estimate:** *(to be filled)*
**[Claude] Verdict:** *(to be filled)*
**[Claude] If dropping — reason:** *(to be filled)*

---"

# Insert after the "## Raw — not yet reviewed" header and its separator line
python3 - <<PYEOF
with open("$IDEAS_FILE", "r") as f:
    content = f.read()

# Find the insertion point: after "## Raw — not yet reviewed\n\n*(Claude reviews..."  line's paragraph
marker = "## Raw — not yet reviewed"
marker_pos = content.find(marker)
if marker_pos == -1:
    print("ERROR: Could not find '## Raw — not yet reviewed' section in FEATURE_IDEAS.md")
    exit(1)

# Find the end of the italics note line after the header (insert after the blank line following it)
insert_after = content.find("\n\n---", marker_pos)
if insert_after == -1:
    insert_after = content.find("\n---", marker_pos)

entry = """$NEW_ENTRY\n"""
new_content = content[:insert_after] + "\n" + entry + content[insert_after:]

# Update the "Next IDEA number" line
import re
new_content = re.sub(r'## Next IDEA number: \d+', f'## Next IDEA number: {int("$NEXT_NUM") + 1:03d}', new_content)

with open("$IDEAS_FILE", "w") as f:
    f.write(new_content)

print("✓ Logged $IDEA_ID: $DESCRIPTION")
print("  File: $IDEAS_FILE")
PYEOF

# Auto-commit so it's immediately visible on GitHub
cd "$PROJECT_DIR" && git add FEATURE_IDEAS.md && git commit -m "Log $IDEA_ID: $DESCRIPTION" --quiet 2>/dev/null && echo "  Committed to git ✓" || echo "  (git commit skipped — check remote)"
