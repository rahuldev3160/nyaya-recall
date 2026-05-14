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

*(none)*

---

## Reviewed — Claude analysis written

*(Ideas where analysis is complete. Viable ones get staged to FEATURES.md; others flagged.)*

---

## Staged — moved to FEATURES.md queue

*(These ideas have been evaluated, accepted, and added to FEATURES.md 📋 Queued. Spec may exist in plans/.)*

---

## Won't Build (Suggested) — awaiting Rahul's confirmation

*(Claude flagged these as not worth building. Rahul must explicitly confirm before they move to Won't Build (Confirmed). Do NOT delete until confirmed.)*

### IDEA-002 — test feature from terminal after shell reload
**Logged:** 2026-05-14
**Source:** terminal
**Status:** Won't Build (Suggested)

**[Claude] Recommendation:** Drop
**[Claude] Verdict:** This is a test log entry for verifying the `log-feature` alias works. No real feature idea here.
**[Claude] If dropping — reason:** Test entry — no functional idea to build.

---

### IDEA-001 — Test: verify feature inbox pipeline works end-to-end
**Logged:** 2026-05-14
**Source:** GitHub Issue #1
**Status:** Won't Build (Suggested)

**[Claude] Recommendation:** Drop
**[Claude] Verdict:** Pipeline is confirmed working (this entry was successfully synced and reviewed). No code to build.
**[Claude] If dropping — reason:** Test entry — pipeline verified, nothing to implement.

---

## Won't Build (Confirmed)

*(Closed ideas — kept as a record so we don't re-log the same thing twice.)*

---

## Next IDEA number: 003
