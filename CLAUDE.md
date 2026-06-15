# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Knowledge Base — ALWAYS CHECK FIRST
Before any audit, bug investigation, or architecture review:
1. Read `.knowledge/INDEX.md` — open bugs, pending approvals, queued features snapshot
2. Read `~/.claude/knowledge/patterns/PATTERNS.md` — cross-project patterns before investigating from scratch
3. For full detail: `ISSUES.md` (bugs), `FEATURES.md` (features), `HANDOFF.md` (session history)

## Knowledge Base — ALWAYS UPDATE AFTER
After any audit, multi-agent task, significant fix, or architecture decision — write synthesized
records to `.knowledge/` and update `INDEX.md` before finishing the response.

## Brand
- Umbrella: **NYAYA** (`nyaya.app` — primary domain)
- This product: **Nyaya Recall** — the memory faculty (adaptive MCQ, spaced repetition, PYQ-anchored)
- Tagline: *"The logic of getting in."*
- Sibling product: Nyaya Scribe (descriptive answer writing) → Descriptive-exams project

## Project

A local-only, AI-powered 10-day UPSC Prelims adaptive preparation system.
Full plan is in PLAN.md — read that first before any session.

## Stack

| Layer | Technology |
|---|---|
| Ingestion | Python 3.11+, pdfplumber, pdf2image, pytesseract, python-docx, anthropic |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 (M-series GPU, free) |
| Vector store | ChromaDB (local persistent, `vector_store/`) |
| Structured data | SQLite (`data/upsc.db`) — upgradeable to PostgreSQL |
| Backend | FastAPI + uvicorn, binds to `0.0.0.0` for phone access on local WiFi |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind |
| AI | Claude API — Haiku for classification, Sonnet for generation/analysis |

## Commands

```bash
# Ingestion (run once, then incrementally for new files)
cd scripts && python ingest.py

# PYQ extraction + classification (one-time)
cd scripts && python ingest_pyq.py

# Backend
cd backend && uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd web && npm run dev

# End-of-day batch analysis
cd scripts && python batch_analyse.py

# Generate tomorrow's plan
cd scripts && python plan_generator.py

# Prompt improvement suggestions (run manually every 2-3 days, or when batch_analyse warns you)
# Prints to stdout; add --output to save to logs/prompt_suggestions_YYYY-MM-DD.txt
cd scripts && python apply_feedback.py
cd scripts && python apply_feedback.py --since 2026-05-01   # filter by date
cd scripts && python apply_feedback.py --output             # write to logs/

# Type check
cd web && npx tsc --noEmit

# Lint
cd web && npm run lint
```

## Critical architecture rules

- **Zero API calls during quiz sessions** — all content is batch-generated beforehand and cached locally
- **All AI outputs cached** in `cache/explanations.json` by hash — never regenerate the same explanation
- **score_engine.py is pure Python** — no API calls for scoring individual answers
- **prompt templates live in `prompts/`** as .txt files — never inline prompts in code
- **All file paths go in .env** — no hardcoded paths anywhere in the codebase
- **SQLite user_id = "user_1"** hardcoded for now — designed to swap to dynamic for multi-user

## Key data files

- `data/syllabus.json` — UPSC Prelims full taxonomy (source of truth for subjects/topics)
- `data/upsc.db` — SQLite: pyq_questions, sessions, answers, scores, sar_scores tables
- `data/prep_profile.json` — GS readiness state, updated by batch_analyse.py
- `data/prep_profile_csat.json` — CSAT readiness (fully independent from GS)
- `data/study_plan.json` — today + tomorrow sessions, written by plan_generator.py
- `cache/explanations.json` — keyed by SHA256(topic + question_text)

## Self-Assessment Reliability (SAR) score

Users can self-attest preparedness in a subject. SAR (0.20–0.90, starts 0.50) controls
how much the claim is trusted vs the validation quiz score:

```
effective_level = (validation_score × (1 - SAR)) + (claimed_level × SAR)
```

SAR managed by `scripts/self_attestation.py`. Stored in `upsc.db` sar_scores table.

## PYQ priority weighting

Subtopic priority = Σ(0.9^(current_year - year) × questions_on_topic_that_year)
Computed by `scripts/priority_scorer.py`. Used to order diagnostic questions.
2009–2025 coverage (17 years) from 3-tier ingestion (see PLAN.md).

## CSAT

Fully separate system. Independent prep_profile, independent session flow.
Routes: `backend/routes/csat.py`. Pages: `web/src/app/csat/`.
Never share data with GS prep_profile.

## Phone access

Backend binds to `0.0.0.0:8000`, frontend to `0.0.0.0:3000`.
Phone on same WiFi accesses via Mac's local IP (`ipconfig getifaddr en0`).
Off-network fallback: export session as offline HTML → import JSON responses.

## Cost guardrails

- Haiku for: PYQ classification, topic tagging, simple decisions
- Sonnet for: question generation, batch analysis, plan generation, explanations
- Never call API per individual answer — always batch
- Check `cache/explanations.json` before any explanation API call

---

## Autonomous agent workflow

Rahul is the sole tester and product owner. He flags issues and features during live study
sessions. Everything is logged in FEATURES.md, ISSUES.md, and plans/. An AI agent (Claude
Code) picks up tasks from those files and implements them. Rahul approves via GitHub PR on
his phone. He is not a developer — keep him in the loop only for critical approvals.

### Feature idea inbox — run this FIRST at every session start

Before picking up any dev work, process the feature idea inbox:

1. **Sync GitHub Issues:**
   ```bash
   /opt/homebrew/bin/gh issue list --repo rahuldev3160/upsc-ai-prep --label feature-request --state open --json number,title,body,createdAt
   ```
   For each issue not already referenced in `FEATURE_IDEAS.md` (check for `GitHub Issue #N`):
   - Assign next IDEA-NNN (read `## Next IDEA number:` from the file)
   - Add it to the `## Raw` section with Source: `GitHub Issue #N`
   - Close the GitHub Issue with comment: `"Logged as IDEA-NNN in FEATURE_IDEAS.md — will be evaluated this session."`

2. **Evaluate every idea in `## Raw`:**
   For each Raw idea, fill in the `[Claude]` analysis block:
   - **Feasibility:** can it be built with FastAPI + Next.js + SQLite + Claude API in <1 day?
   - **Impact on prep:** does it meaningfully help UPSC study in the remaining days?
   - **Effort estimate:** rough hours
   - **Recommendation:** one of — `Implement` | `Spec first` | `Defer post-exam` | `Drop`
   - Move the idea from `## Raw` to `## Reviewed`

3. **Route reviewed ideas:**
   - `Implement` or `Spec first` → add to `FEATURES.md → 📋 Queued`, create stub `plans/<slug>.md` (3-4 bullet outline), move idea to `## Staged`
   - `Drop` → move to `## Won't Build (Suggested)`, do NOT delete
   - `Defer post-exam` → move to `## Reviewed` (leave there, low priority)

4. **Flag Won't Build (Suggested) ideas to Rahul:**
   At the start of the session summary, list any ideas in `## Won't Build (Suggested)` and ask:
   `"IDEA-NNN ('title') flagged for removal: [reason]. Confirm to move to Won't Build (Confirmed)?"`
   Only move to `## Won't Build (Confirmed)` after explicit confirmation.

5. **Update `## Next IDEA number:`** at the bottom of `FEATURE_IDEAS.md` after any additions.

---

### How to pick up work each session

1. Read `ISSUES.md` → any **Open** items are highest priority (live bugs blocking study)
2. Read `FEATURES.md → 🔵 Planned` → spec exists, ready to implement
3. Read `FEATURES.md → 📋 Queued` → needs a spec first before implementing
4. Pick the highest-priority item, check for a spec in `plans/`, and begin

If a Queued item has no plan file: write the spec in `plans/<feature>.md`, commit it,
open a spec-only PR titled `Spec: <feature name>` — do NOT implement until Rahul approves
the spec. Specs for P1 items should be drafted proactively.

### Branch naming

```
feature/<short-name>         e.g. feature/per-question-timer
fix/<issue-id>-<short>       e.g. fix/issue-002-notes-parser
spec/<feature-name>          e.g. spec/metacognition-capture
```

Never push directly to `main`. Always work on a branch and open a PR.

### Before opening every PR — checklist

- [ ] `cd web && npx tsc --noEmit` passes (zero TypeScript errors)
- [ ] `cd web && npm run lint` passes
- [ ] FEATURES.md updated — item moved to correct status (Planned or Shipped)
- [ ] ISSUES.md updated if this fixes an issue — Status → Resolved, Resolution field filled
- [ ] HANDOFF.md updated with what changed and any watch-outs

### PR description format (always use this structure)

```
## What changed
- bullet points of what was implemented

## Files touched
- list key files modified

## How to test
- specific steps Rahul can follow in the browser to verify it works

## Risks / watch-outs
- anything affecting existing data, scoring logic, or live sessions

## Needs approval before merge?
Yes / No — reason
```

### Approval gates — ALWAYS stop and flag, never proceed autonomously

**Sound alert rule:** Before asking Rahul for any approval, always run:
```bash
afplay /System/Library/Sounds/Ping.aiff
```
Rahul studies in another window and cannot see the terminal. The sound is his only signal to look. Do this BEFORE writing the question, not after.

These require an explicit message or PR comment from Rahul before any work continues:

- Any ALTER TABLE or DROP TABLE on existing DB tables
- Any change to score calculation logic in `scripts/score_engine.py`
- Any change to the readiness formula in `scripts/batch_analyse.py`
- Any change to `prompts/plan_generation.txt` scheduling rules
- Deleting files that are referenced by other active code
- Any change touching `.env`, API keys, or authentication
- Force-pushing or rewriting git history

### Autonomous — no approval needed, implement and open PR

- New frontend UI components and pages
- New additive API endpoints (not changing existing ones)
- New DB tables (CREATE TABLE only — never ALTER or DROP existing)
- Bug fixes where root cause is clearly identified in ISSUES.md
- New prompt files in `prompts/`
- New scripts that don't modify existing DB data
- Updating FEATURES.md, ISSUES.md, HANDOFF.md documentation
- Adding plan spec files in `plans/`

### After completing a task

Run `/close-task` (`.claude/commands/close-task.md`) — it handles the full close-out sequence.
The explicit steps it covers (do not skip any):

1. **FEATURES.md** — strike through the completed Queued item; add to ✅ Shipped with date
2. **ISSUES.md** — move fixed issue to Resolved; fill Resolution field (date + file + PR)
3. **HANDOFF.md** — add a new entry at the TOP with what changed and watch-outs; mark any previously-open problem ✅ if resolved this session
4. **Memory** — write a `memory/project_<slug>.md` entry for any factual finding or resolved open item so future sessions don't re-open it
5. **Cross-check** — for every item still open in HANDOFF.md, verify it hasn't already been struck through in FEATURES.md or marked Resolved in ISSUES.md (this is the leak detector)
6. **PR** — open using the format above; doc-only changes can go straight to main

**HANDOFF.md is the most important file to keep current.** Every future session reads it to find open problems. If a resolved item is still listed as open there, it will be picked up as work again — wasting a full session. Always mark HANDOFF.md items ✅ when done, even if the fix was trivial.

Do not start the next task until the current PR is merged or explicitly unblocked by Rahul.

### Communicating with Rahul

- Keep PR descriptions short and scannable — he reads them on his phone
- Lead with impact: "This adds X which means Y" not a technical explanation
- If blocked: leave a comment on the PR explaining exactly what decision is needed
- Never send long messages asking multiple questions — one clear question at a time
- If a decision will take >5 minutes of his attention, break it into a smaller question
