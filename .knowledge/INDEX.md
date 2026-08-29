# Knowledge Base — Devthorium (UPSC AI Prep)
Last updated: 2026-06-05

## How to use
- Scan this file at the start of any session before opening FEATURES.md or ISSUES.md
- This is a SUMMARY layer — full records live in the project's existing doc system
- Bugs: `ISSUES.md` (canonical), bugs/ here has the synthesized records
- Features: `FEATURES.md` (canonical), plans/ here has architectural decisions
- Audits: `audits/` — records of deliberate code reviews or multi-agent analyses
- Patterns: `~/.claude/knowledge/patterns/PATTERNS.md` — cross-project patterns

---

## Project Snapshot
**Stack:** FastAPI (Python 3.11) + Next.js 14 + SQLite (`data/upsc.db`) + ChromaDB  
**AI:** Claude Haiku (fast tasks) + Sonnet (generation/analysis)  
**Data:** 9 SQLite tables, vector store for study material  
**Status:** v1 active development. devthorium_beta = planning-only mode.  
**Last PR merged:** #41 — exam sim score isolation + history panel

---

## Open Bugs (from ISSUES.md)

| ID | Status | Priority | Summary | ISSUES.md ref |
|----|--------|----------|---------|---------------|
| [BUG-001](bugs/BUG-001.md) | OPEN | P2 | PYQ correct_answers are AI-inferred, not validated against official keys | ISSUES.md note |
| [BUG-002](bugs/BUG-002.md) | OPEN | P1 | ALTER TABLE pyq_questions pending — needs explicit Rahul approval before running | HANDOFF.md |
| [BUG-003](bugs/BUG-003.md) | OPEN | P1 | DELETE to fix 2014 PYQ duplication (~132→100 rows) — needs explicit approval | HANDOFF.md |
| [BUG-004](bugs/BUG-004.md) | INFO | P2 | CSAT system exists (backend/routes/csat.py) but is untested | FEATURES.md |

---

## Plans / Architecture Decisions

| ID | Title | Status | File |
|----|-------|--------|------|
| [PLAN-001](plans/PLAN-001.md) | Two-table question bank architecture | DECIDED | plans/multi_exam_bank.md |
| [PLAN-002](plans/PLAN-002.md) | Public platform phases (6-phase roadmap) | PLANNED | plans/public_platform.md |
| [PLAN-003](plans/PLAN-003.md) | PYQ Data Foundation — official answer keys | BLOCKED (needs Rahul download) | plans/pyq_data_foundation.md |
| [PLAN-004](plans/PLAN-004.md) | PYQ Browser (FEATURE-18) | QUEUED (blocked on PLAN-003) | plans/pyq_browser.md |
| [PLAN-005](plans/PLAN-005.md) | PYQ Explanations (FEATURE-19) | QUEUED (blocked on PLAN-003) | plans/pyq_explanations.md |
| [PLAN-006](plans/PLAN-006.md) | Nyaya Arena reuses Recall's engine, own identity | DECIDED | plans/PLAN-006.md |
| [PLAN-007](plans/PLAN-007.md) | Generalized multi-exam/multi-source/multi-format `question_bank` schema | PROPOSED | plans/PLAN-007.md |
| [PLAN-008](plans/PLAN-008.md) | RBI Grade B migration: Scribe → Recall, staged/reversible cutover | PROPOSED | plans/PLAN-008.md |
| [PLAN-009](plans/PLAN-009.md) | Multi-source MCQ ingestion pipeline + personalization signal + build order | PROPOSED | plans/PLAN-009.md |

---

## Queued Features (next to build)

| Feature ID | Priority | Summary | Blocked by |
|------------|----------|---------|------------|
| FEATURE-17 | P0 | PYQ Data Foundation — official answer keys | Rahul to download UPSC PDFs |
| FEATURE-18 | P1 | PYQ Browser (year→subject→topic→subtopic nav) | FEATURE-17 |
| FEATURE-19 | P1 | PYQ Explanations (Haiku Batch, ~₹81 one-time) | FEATURE-17 (need correct_answers first) |

---

## Audits

| ID | Date | Scope | Findings |
|----|------|-------|----------|
| [AUDIT-001](audits/AUDIT-001.md) | 2026-08-29 | Mock-competition reuse (Nyaya Arena scoping) | Daily-challenge/leaderboard mechanic already exists, ~70% built; blocked on B-1/B-2/B-4 |

---

## Critical Approval Gates
These MUST be flagged to Rahul before executing:
- `ALTER TABLE pyq_questions` (add answer_source, answer_disputed, dispute_note, q_number)
- `DELETE FROM pyq_questions` — fix 2014 duplication
- Any DB schema changes or score logic changes (per CLAUDE.md gating rules)
- ~~B-11~~ — batched `question_bank` ALTER (8 columns) + 3 new tables, PLAN-007 — **approved by Rahul 2026-08-29**, already run (backup at `data/upsc.db.bak-pre-plan007-*`)
- ~~B-12~~ — Scribe's `rbi_attempts.source` ALTER (live-user table), PLAN-008 — **approved by Rahul 2026-08-29**, already run (additive, non-destructive)
- Internal-API auth key rename (`X-Arena-Api-Key` → `X-Internal-Api-Key`, PLAN-008 §4) — **approved by Rahul 2026-08-29**; real key values now set in `.env` (see HANDOFF.md)

---

## Existing Documentation System
This project has comprehensive docs — use them:
- `PLAN.md` — master project plan (read at session start)
- `FEATURES.md` — shipped / planned / queued feature tracker
- `ISSUES.md` — organic bug log with full context
- `HANDOFF.md` — chronological session notes
- `plans/` — detailed specs per feature
- `MASTER_INDEX.md` — artefact catalogue (exists in devthorium_beta, not yet in v1)

---

## Patterns Reference
`~/.claude/knowledge/patterns/PATTERNS.md`

| Pattern | Relevance to Devthorium |
|---------|------------------------|
| DB-001 (read-modify-write race) | Applicable to score_engine.py counter updates |
