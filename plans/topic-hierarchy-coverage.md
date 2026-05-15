# Plan: Topic-Level Hierarchical Coverage (FEATURE-028)

## What problem this solves

Today the system tracks coverage at the subtopic level only. The middle tier — **topics** —
is invisible. You can be 100% covered on polity's subtopics while having completely skipped
an entire topic (e.g. "Local Government" which has 3 subtopics). The plan generator doesn't
group by topic — Claude gets a flat sorted list of subtopics with no sense of which topic
each belongs to, so it may over-schedule one topic's subtopics while never touching another.

Additionally, `topic_id` is broken in the DB:
- `session_answers.topic_id` = NULL in all 701 rows
- `subtopic_scores.topic_id` = non-canonical free-text aliases in 28/173 rows
- ~70% of PYQ weights are stuck at DEFAULT_WEIGHT=1.0 (retag script exists but not run)

This feature fixes the data plumbing and adds topic-level visibility.

---

## Research findings (Agent B, May 16)

| Level | Stored in DB | Used in coverage | Used in planning |
|---|---|---|---|
| Subject | Yes | Yes | Yes |
| **Topic** | **Broken** (NULL or non-canonical) | **No** | **No** |
| Subtopic | Yes — primary | Yes | Yes |
| Dimension | Doesn't exist | N/A | N/A |

Syllabus: 194 GS subtopics across 52 topics in 9 subjects.
Total testable content: 9 subjects → 52 topics → 194 subtopics.

---

## Implementation phases

### Phase 0 — Run retag_pyq_subtopics.py (prerequisite, already exists)
**Cost:** ~$0.05 one-time | **Time:** 2 minutes
```bash
python3 scripts/retag_pyq_subtopics.py
```
Unlocks real PYQ weights for 70% of subtopics currently showing DEFAULT_WEIGHT=1.0.
Must run before Phase 1 so topic-level weights use real data.

---

### Phase 1 — Fix topic_id propagation
**Branch:** `fix/topic-id-canonical`
**Files:** `backend/routes/quiz.py`, `scripts/score_engine.py`, `scripts/db_init.py`

**Root cause:** quiz generation receives `subtopic_id` but looks up `topic_id` from
`pyq_questions` (which has free-text tags), not from `syllabus.json` (which has canonical IDs).

**Fix:** In `quiz.py`, when building the quiz config, look up the canonical `topic_id` from
`syllabus.json` for the given `subtopic_id` and pass it through. A utility function:

```python
def get_canonical_topic_id(subject_id: str, subtopic_id: str) -> str | None:
    """Look up topic_id from syllabus.json for a given subject+subtopic pair."""
    syllabus = load_syllabus()  # cached
    for subj in syllabus['subjects']:
        if subj['id'] != subject_id:
            continue
        for topic in subj.get('topics', []):
            for st in topic.get('subtopics', []):
                if st['id'] == subtopic_id:
                    return topic['id']
    return None
```

Pass this canonical `topic_id` into `record_answer()` and `close_session()` so both
`session_answers` and `subtopic_scores` are updated with correct values going forward.

**Note:** A backfill script will be needed to fix historical rows. Write it alongside this fix.

---

### Phase 2 — Topic-level coverage in batch_analyse.py
**Branch:** `feature/topic-coverage`
**Files:** `scripts/batch_analyse.py`, `data/prep_profile.json` (schema addition)

Add `topics` array to each subject in `prep_profile.json`:

```json
{
  "subjects": {
    "polity": {
      "coverage_pct": 100.0,
      "topics": [
        {
          "id": "constitutional_framework",
          "name": "Constitutional Framework",
          "subtopics_total": 5,
          "subtopics_tested": 5,
          "coverage_pct": 100.0,
          "readiness": 78.3,
          "risk_level": "low"
        },
        {
          "id": "local_government",
          "name": "Local Government",
          "subtopics_total": 3,
          "subtopics_tested": 0,
          "coverage_pct": 0.0,
          "readiness": 0.0,
          "risk_level": "high"
        }
      ]
    }
  }
}
```

Topic readiness = `Σ(subtopic_readiness × pyq_weight) / Σ(subtopic_weights)` — same
formula as subject-level, scoped to the topic.

Topic risk level:
- `high` if coverage_pct < 50% or any subtopic untested with high pyq_weight
- `medium` if coverage_pct 50-80%
- `low` if coverage_pct > 80%

---

### Phase 3 — Plan generator: topic-balanced scheduling
**Branch:** `feature/topic-balanced-planning`
**Files:** `scripts/plan_generator.py`

Currently the plan generator sends a flat subtopic list sorted by pyq_weight. Claude may
pick 5 subtopics from the same high-pyq-weight topic and skip an entire low-weight topic.

**Fix:** Pass topic structure to Claude:

```json
{
  "untested_by_topic": [
    {
      "topic_id": "local_government",
      "topic_name": "Local Government",
      "topic_pyq_weight": 2.1,
      "untested_subtopics": [
        {"id": "panchayati_raj", "pyq_weight": 1.8},
        {"id": "urban_local_bodies", "pyq_weight": 1.4}
      ]
    }
  ]
}
```

Add scheduling rule to prompt: "Ensure at least 1 subtopic from each topic that has untested
subtopics, before scheduling 2+ subtopics from any single topic."

---

### Phase 4 — Topic coverage UI on Tracker and Strategy pages
**Branch:** `feature/topic-coverage-ui`
**Files:** `web/src/app/tracker/page.tsx`, `web/src/app/strategy/page.tsx`

Tracker: expand the subject readiness cards to show topic-level breakdown when clicked
(accordion: "Show topics"). Each topic row shows coverage bar + risk badge.

Strategy: in the Superplan subject grid, add "Uncovered topics" count as a subtitle:
"Polity · 100% covered · 0 topics at risk" vs
"History (A/M/AC) · 24% covered · 6 of 8 topics not started"

---

## Sequencing

```
Phase 0 (2min, free) → Phase 1 (3hrs) → Phase 2 (4hrs) → Phase 3 (2hrs) → Phase 4 (3hrs)
```

Total: ~12 hours. Can be done in 2 sessions.

**Should run before FEATURE-027 (Dimension Coverage):** canonical topic_ids from Phase 1
are a prerequisite for dimension-level PYQ weight computation in that feature.

---

## Priority order of the two features

1. **FEATURE-028 (this file) first** — fixes broken data plumbing, unlocks real PYQ weights,
   adds topic-level visibility. Simpler, fewer schema changes.
2. **FEATURE-027 (dimension coverage) second** — depends on canonical topic_ids and real PYQ
   weights from this feature being in place.

Combined roadmap: ~25-30 hours total dev time across 4-5 sessions post-exam.
