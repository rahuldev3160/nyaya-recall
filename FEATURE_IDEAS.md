# FEATURE_IDEAS.md — Idea Inbox

> Raw feature ideas captured during study sessions or from phone.
> Different from FEATURES.md (which tracks planned/shipped work) — this is the unfiltered inbox.
> Claude evaluates every Raw idea at session start, writes a recommendation, and routes it:
> viable ideas → FEATURES.md queue + stub spec; weak ideas → Won't Build (Suggested) for confirmation.

---

## How to log a new idea

**From terminal:**
```bash
log-feature "your idea in one line"
```

**From phone:**
Open GitHub mobile app → Top Repositories → this repo → Issues → New Issue → choose "Feature request" template → add `feature-request` label → submit.
Claude picks it up at the next session start.

---

## Format

```
### IDEA-NNN — Short title
**Logged:** YYYY-MM-DD
**Source:** terminal | GitHub Issue #N
**Status:** Raw | Reviewed | Staged | Won't Build (Suggested) | Won't Build (Confirmed)
**Priority guess:** P1 / P2 / P3

**What's the idea:**
(one-liner or description from Rahul)

**Why it matters:**
(what friction does it solve / context)

---

**[Claude] Recommendation:** Implement | Spec first | Defer post-exam | Drop
**[Claude] Feasibility:** (can it be built with FastAPI + Next.js + SQLite + Claude API?)
**[Claude] Impact on prep:** (does it meaningfully help UPSC study in the remaining days?)
**[Claude] Effort estimate:** (~N hrs)
**[Claude] Verdict:** (one sentence)
**[Claude] If dropping — reason:**
```

---

## Raw — not yet reviewed

*(Claude reviews these at session start and fills in the analysis block)*

### IDEA-002 — test feature from terminal after shell reload
**Logged:** 2026-05-14
**Source:** terminal
**Status:** Raw
**Priority guess:** P2

**What's the idea:**
test feature from terminal after shell reload

**Why it matters:**
*(fill in — what friction does this solve?)*

---

**[Claude] Recommendation:** *(to be filled)*
**[Claude] Feasibility:** *(to be filled)*
**[Claude] Impact on prep:** *(to be filled)*
**[Claude] Effort estimate:** *(to be filled)*
**[Claude] Verdict:** *(to be filled)*
**[Claude] If dropping — reason:** *(to be filled)*

---


---

### IDEA-001 — Test: verify feature inbox pipeline works end-to-end
**Logged:** 2026-05-14
**Source:** GitHub Issue #1
**Status:** Raw
**Priority guess:** P3

**What's the idea:**
Test run to confirm Claude can read GitHub Issues from the phone and sync them into this file.

**Why it matters:**
Validates the full phone → GitHub Issue → FEATURE_IDEAS.md → Claude review pipeline before relying on it.

---

**[Claude] Recommendation:** *(to be filled)*
**[Claude] Feasibility:** *(to be filled)*
**[Claude] Impact on prep:** *(to be filled)*
**[Claude] Effort estimate:** *(to be filled)*
**[Claude] Verdict:** *(to be filled)*
**[Claude] If dropping — reason:** *(to be filled)*

---

## Reviewed — Claude analysis written

*(Ideas where analysis is complete. Viable ones get staged to FEATURES.md; others flagged.)*

---

## Staged — moved to FEATURES.md queue

*(These ideas have been evaluated, accepted, and added to FEATURES.md 📋 Queued. Spec may exist in plans/.)*

---

## Won't Build (Suggested) — awaiting Rahul's confirmation

*(Claude flagged these as not worth building. Rahul must explicitly confirm before they move to Won't Build (Confirmed). Do NOT delete until confirmed.)*

---

## Won't Build (Confirmed)

*(Closed ideas — kept as a record so we don't re-log the same thing twice.)*

---

## Next IDEA number: 003
