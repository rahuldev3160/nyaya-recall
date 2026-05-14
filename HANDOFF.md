# HANDOFF.md — Dev Session Update (May 14, 2026)

> Read `COLLAB.md` first for the full project context and architecture overview.
> This file covers what changed in the most recent dev session and what still needs work.

---

## What changed — May 14, 2026 (Session 2)

### 1. ISSUE-008: Session history + review page — PR #4 open, awaiting merge

| File | What changed |
|------|-------------|
| `backend/routes/sessions.py` | New `GET /sessions/` endpoint — lists last 30 completed sessions |
| `web/src/lib/api.ts` | `getSessionHistory()`, `getSession(id)` |
| `web/src/app/sessions/page.tsx` | New: session history list with score, date, subject |
| `web/src/app/sessions/[id]/page.tsx` | New: full Q&A review — correct/wrong highlighting, explanations, Dive Deeper |
| `web/src/app/layout.tsx` | "History" nav link added |

After merging, Rahul can click History in the nav → see all past sessions → click any session to review questions.

### 2. ISSUES.md triaged — all unnumbered issues now have IDs (009–023)

All 15+ unnamed issues that were logged via terminal in May 13–14 now have:
- Assigned ISSUE numbers (ISSUE-009 through ISSUE-023)
- "Current state of the code" investigation filled in by Claude
- "What's needed to fix" specifics
- Status updated to Resolved for issues already fixed in `fix/explanation-quality` or `fix/session-ux-improvements`

### 3. PR #3 opened for `fix/explanation-quality`

Covers ISSUE-009 (revision deck contradictions), ISSUE-010 (verbose preamble), ISSUE-011 (statement formatting), ISSUE-013 (wrong-option explanations), notes synthesis, feature inbox.

**Merge order:** PR #3 (explanation quality) first → then PR #2 (session UX) → then PR #4 (session history).

### 4. `scripts/check_chroma_coverage.py` — ChromaDB audit script (PR #4)

Run: `python3 scripts/check_chroma_coverage.py`

Shows chunk count per subject and flags subjects with < 50 chunks or no chunks at all (those are falling back to Claude's training knowledge instead of Rahul's study material).

---

## What changed — May 14, 2026 (Session 1)

### Session UX fixes — PR #2 open (fix/session-ux-improvements), awaiting merge

| Issue | What changed | File |
|-------|-------------|------|
| ISSUE-021 | Submit button before answer reveal — option click highlights blue, Submit reveals | `web/src/app/diagnostic/page.tsx`, `web/src/app/session/page.tsx` |
| ISSUE-007 | ← Previous button on both quiz pages, currentQ > 0 only | same |
| ISSUE-016 | Session finish screen now shows score % + correct/total | `web/src/app/session/page.tsx` |
| ISSUE-023 | Completed sessions show green ✓ badge in Today's Sessions list | `web/src/app/session/page.tsx` |
| ISSUE-012 | CSAT excluded from GS1 readiness in `_build_syllabus_map()` | `scripts/batch_analyse.py` |

Also added `whitespace-pre-wrap` to question text on both pages (fixes statement formatting).

### Feature idea inbox system — shipped to fix/explanation-quality branch

- `FEATURE_IDEAS.md` — structured idea inbox (Raw → Reviewed → Staged → Won't Build)
- `scripts/log_feature.sh` — `log-feature "idea"` from terminal, auto-commits
- `~/.zshrc` — `log-feature` alias added

### GitHub auth configured

`gh` CLI now authenticated as `rahuldev3160`. Token in macOS keychain. Use `GH_TOKEN=$(security find-internet-password -s github.com -a rahuldev3160 -w)` prefix in bash scripts since keychain isn't available in subshells.

---

## Open issues — current priority order

| # | Issue | Status | Notes |
|---|-------|--------|-------|
| ISSUE-019 | Note-taking resets per question + autosaves | Open P1 | Needs `question_notes` table + frontend state; awaiting feedback_training.md spec answers |
| ISSUE-017 | Note-taking as model feedback/training | Open P1 | Awaits answers to 3 questions in `plans/feedback_training.md` Section 10 |
| ISSUE-022 | Session notes missing deep concept explanation | Open P1 | May be fixed in fix/explanation-quality — verify after merge |
| ISSUE-008 | Revisit completed sessions | PR #4 | Merge when ready |
| ISSUE-002 | Notes-then-quiz session fix | In progress | Rahul to confirm notes appear in live session |
| ISSUE-014 | Time tracker | Open P2 | Needs spec |

---

## Pending terminal actions (Rahul to run)

### Retag PYQs (~$0.05 Haiku spend) — still pending
```bash
cd "/Users/rahulsingh/Desktop/Claude Projects/Last 10 Day AI powered Preparation"
python3 scripts/retag_pyq_subtopics.py --dry-run   # preview first
python3 scripts/retag_pyq_subtopics.py              # approve and run
```
Impact: 903 of 1,081 PYQ questions currently have no canonical subtopic ID → question prioritisation is half-blind. This fixes it.

### ChromaDB coverage audit — now available (free)
```bash
python3 scripts/check_chroma_coverage.py
```
Shows which subjects have indexed study material. Subjects with 0 chunks are generating questions from Claude's training knowledge only.

---

## Branch state

| Branch | State | Action needed |
|--------|-------|---------------|
| `main` | 22 commits ahead of origin/main — push pending | `git push origin main` |
| `fix/explanation-quality` | PR #3 open | Rahul to merge first |
| `fix/session-ux-improvements` | PR #2 open | Merge after PR #3 |
| `fix/issue-008-session-review` | PR #4 open | Merge after PR #2 |

---

## Start commands (unchanged)

```bash
# Tab 1 — Backend
cd "/Users/rahulsingh/Desktop/Claude Projects/Last 10 Day AI powered Preparation/backend"
uvicorn server:app --host 0.0.0.0 --port 8000

# Tab 2 — Frontend
cd "/Users/rahulsingh/Desktop/Claude Projects/Last 10 Day AI powered Preparation/web"
npm run start -- -H 0.0.0.0

# Phone (Tailscale): http://100.113.107.75:3000
```

After merging all 3 PRs, rebuild frontend: `npm run build && npm run start -- -H 0.0.0.0`

---

## Historical changes (earlier sessions)

### What changed — May 13, 2026

A. **Submit button before answer reveal** — `web/src/app/diagnostic/page.tsx` + `session/page.tsx`. `pendingAnswer` state; clicking option only selects (blue highlight), "Submit Answer" fires actual API call.

B. **Post-session revision notes for wrong answers** (ISSUE-018) — `POST /sessions/{session_id}/revision-notes` in `backend/routes/sessions.py`, new `prompts/revision_notes.txt` (Haiku), cached by SHA256 in `cache/explanations.json`. Finish screen fetches and displays "Concepts to Review".

C. **Session notes core concept depth** (ISSUE-022) — `prompts/session_notes.txt` Core Concept section expanded.

D. **Completed sessions marking** (ISSUE-023) — `session/page.tsx` Today's Sessions list tracks `completedSessions` (Set<number> in state). Finished sessions show green ✓, "Completed" badge, muted card.

---

### What changed — May 12 (PYQ subtopic ID normalisation)

`priority_scorer.py` now uses subject-scoped token-overlap to normalise free-text PYQ subtopic descriptors to canonical syllabus IDs. 139 subtopics now have real varied weights (was 0).

For full coverage (~70% of questions still unmatched), run `scripts/retag_pyq_subtopics.py` (costs ~$0.05).

---

### Current state (Day 7 of 10, May 14)

```
Overall readiness: ~3–5% (honest — ~20/205 subtopics tested as of May 14 morning)

polity:         ~12–15%  tested
economy:        ~24%     tested
ir_governance:  ~87%     (1 session, 86.7% accuracy)
history_amac:    3.3%    (1 subtopic)
All others:      0%      (untested)
```

DB: 1,081 PYQ questions loaded. Exam: May 20, 2026.
