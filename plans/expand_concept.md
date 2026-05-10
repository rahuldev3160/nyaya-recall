---
Feature: Expand Concept ("Dive Deeper →")
Status: In Progress
Priority: High
Triggered: Simulation Step 3 — user wanted deeper context on E-Jagriti question
---

## Problem

After getting an explanation for a wrong answer, user has no way to go deeper.
Current explanation is 2-3 sentences. Complex concepts (e.g. E-Jagriti, NFSA clauses)
need a fuller treatment — timeline, implications, exam angles.

Also: the expansion click is a valuable learning signal. If a user dives into
"constitutional amendments" repeatedly, the batch analyser should know that and
personalise prep around that interest.

---

## Design

### UI — below existing explanation block

```
[ Explanation text already shown ]

  [ Dive deeper → ]          ← button, only after answer revealed

  ↓ on click: expands inline (no page change)

  ┌─────────────────────────────────────────────┐
  │  Deep Dive: E-Jagriti                        │
  │                                              │
  │  E-Jagriti is an integrated consumer...      │
  │  [300-500 word explanation with context,     │
  │   timeline, why it matters for exam]         │
  │                                              │
  │  Key UPSC angles:                            │
  │  • Often tested as statement-true/false      │
  │  • Compare with: UMANG, DigiLocker, CPGRAMS  │
  └─────────────────────────────────────────────┘
```

### What's recorded
- `concept_expanded = 1` in `session_answers` for that question row
- Expansion tracked per subtopic: counts how many concepts user drilled into

### How batch analyser uses it
- Summaries include `expanded_subtopics: [...]`
- Prompt notes: "User chose to expand concept on these subtopics — indicates
  deeper interest or confusion. Consider allocating more focused time."

---

## Implementation

### DB changes
- Add `concept_expanded INTEGER DEFAULT 0` to `session_answers`
- Run `ALTER TABLE` migration for existing DB

### Backend
- New endpoint: `POST /sessions/expand-concept`
  Body: `{session_id, question_hash, question_text, subtopic_id, subject_id}`
  - Calls Claude Haiku with dedicated prompt
  - Sets `concept_expanded=1` for matching row in `session_answers`
  - Returns `{explanation: "..."}`
- Prompt: `prompts/expand_concept.txt`

### Frontend
- `api.expandConcept(body)` in api.ts
- In diagnostic/page.tsx: "Dive deeper →" button below explanation block
  - State: `expanded: Record<number, string>` (question index → expanded text)
  - `expandLoading: Record<number, boolean>`
- In session/page.tsx: same pattern

### Batch analyser
- `score_engine._store_session_summary()`: add `expanded_subtopics` field
  (list of subtopic_ids where concept_expanded=1)
- `batch_analyse.get_unsynced_summaries()`: include `expanded_subtopics` from summary
- `prompts/batch_analysis.txt`: add line about expansion signals

---

## Files to change
- `scripts/db_init.py` — add concept_expanded column
- `backend/routes/sessions.py` — add expand-concept endpoint
- `scripts/score_engine.py` — include expanded_subtopics in summary
- `scripts/batch_analyse.py` — pass expanded_subtopics to prompt
- `prompts/expand_concept.txt` — new prompt file
- `prompts/batch_analysis.txt` — add expansion signal note
- `web/src/lib/api.ts` — add expandConcept()
- `web/src/app/diagnostic/page.tsx` — add Dive Deeper button + expanded view
- `web/src/app/session/page.tsx` — same

---

## Merge condition
Build immediately — triggered by simulation. Estimated: 45 min.
