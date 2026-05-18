---
type: project
date: 2026-05-17
slug: system-audit-phase1
---

# System Audit Phase 1 — Resolved 2026-05-17

## What was done

A full correctness audit of the UPSC AI prep system was conducted and 8 bugs were fixed in a single branch (`fix/system-audit-phase1`).

## What was found (already fixed — do not re-open)

| ID | Issue | Status |
|----|-------|--------|
| C-01 | Exam sim missing CA chunks + dimensions in prompt | ✅ Fixed |
| C-02 | Single-subtopic chunk k=5 hardcoded (should use `_chunk_k(num_q)`) | ✅ Fixed |
| C-05 | `close_session()` had no transaction wrapper | ✅ Fixed |
| H-05 | `session_answers` had no UNIQUE guard on (session_id, question_hash) | ✅ Fixed |
| H-06 | `batch_analyse.py` max_tokens=8192 could truncate analysis JSON | ✅ Fixed (now 16000 + extended-output beta) |
| H-07 | `plan_generator.py` read profile without freshness check | ✅ Fixed (warns at >12h) |
| H-08 | `plan_generator.py` max_tokens=4096 truncated long plans | ✅ Fixed (now 8192 + extended-output beta) |
| M-09 | Dashboard showed no last-synced indicator | ✅ Fixed |

## What was already fixed before this session (audit draft was stale)

- **C-04 (localStorage session hydration)** — `ACTIVE_QUIZ_KEY` was already fully implemented in `session/page.tsx` before this session. Do NOT re-raise.
- **M-08 (per-question notes not pre-populated)** — `getQuestionNotes` was already called and merged into `questionNotesMap` React state. Do NOT re-raise.
- **H-05 for question_notes** — `question_notes` table already had `UNIQUE(session_id, question_hash)`. The gap was in `session_answers`, which is now fixed.

## Still open (out of scope for this session)

- C-03 (CSAT): placeholder only — deferred pending Rahul confirmation
- H-01/M-01 (ChromaDB subtopic_id metadata re-index): needs separate planning session
- H-02 (CA query by topic not subject for merged sessions): partially addressed by C-01; merged-session improvement is separate
- H-03/H-04 (orphaned batch_analysis.txt + generate_dimensions.txt): lower impact, separate PR

## How to apply

Do not re-raise any item in the table above as an open issue. All 8 fixes are committed in `fix/system-audit-phase1`.
