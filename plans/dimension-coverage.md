# Plan: Dimension-Aware Subtopic Coverage Tracking (FEATURE-027)

## What problem this solves

Today a subtopic is marked "tested" after a single session touching it, regardless of how many
of its testable dimensions were actually covered. A subtopic like `monetary_policy_rbi` has at
least 6 distinct dimensions (RBI tools, monetary transmission, inflation targeting, liquidity
management, regulatory role, recent policy actions). Covering only the first two and calling it
"done" inflates coverage numbers and creates exam blind spots.

The goal: a subtopic is fully covered **only when every dimension has been tested at sufficient
depth**, weighted by how often that dimension appears in PYQs and current affairs.

---

## Research findings (Agent A, May 16)

### What exists today
- Syllabus is 3-level only: subject → topic → subtopic (no dimensions field)
- `session_answers` has no `dimension` column
- Claude's quiz output JSON has no `dimension` field
- `subtopic_scores` tracks accuracy per subtopic — no per-dimension granularity
- `deep_dive_quiz.txt` defines 6 coverage dimensions as generation mandate but does NOT ask
  Claude to label which dimension each question tests

### What's missing
- A `dimensions[]` array per subtopic in `syllabus.json`
- A `dimension` field in quiz question JSON (all 4 prompt files need update)
- A `dimension` column in `session_answers`
- A new `subtopic_dimension_scores` table
- Coverage formula updated from "subtopics tested / total subtopics" to dimension-weighted avg

---

## Implementation phases (run in this order — each phase is a separate PR)

### Phase 0 — Prerequisite: run retag_pyq_subtopics.py (~$0.05, 2 minutes)
This already-written script fixes PYQ weights for 70% of subtopics currently stuck at
DEFAULT_WEIGHT=1.0. Must run before Phase 1 so dimension weights can use real PYQ data.
```bash
python3 scripts/retag_pyq_subtopics.py
```

---

### Phase 1 — Populate dimensions in syllabus.json
**Branch:** `feature/syllabus-dimensions`
**File:** `data/syllabus.json`, new `scripts/generate_syllabus_dimensions.py`

Write a script that iterates every subtopic and asks Claude Haiku to generate 4-8 testable
dimensions per subtopic, tagged with:
```json
{
  "id": "rbi_functions",
  "name": "RBI — Structure & Functions",
  "dimensions": [
    {
      "id": "rbi_establishment_structure",
      "name": "Establishment, structure and governance of RBI",
      "pyq_weight": 1.8,
      "has_current_affairs": false,
      "is_core_concept": true,
      "base_weight": 2.0
    },
    {
      "id": "monetary_policy_tools",
      "name": "Monetary policy tools — repo, reverse repo, CRR, SLR",
      "pyq_weight": 3.2,
      "has_current_affairs": true,
      "is_core_concept": true,
      "base_weight": 3.0
    }
  ]
}
```

**Weight formula per dimension:**
```
final_weight = pyq_weight × (1.5 if has_current_affairs else 1.0) × (2.0 if is_core_concept else 1.0)
```

**PYQ weight:** computed by matching dimension to PYQ question texts using the existing
`priority_scorer.py` decay logic — same formula, scoped to questions matching this dimension.

**Effort:** ~4 hrs | **Cost:** ~$0.50 for Haiku calls across 194 subtopics

---

### Phase 2 — Add dimension field to quiz generation
**Branch:** `feature/dimension-labeling`
**Files:** `backend/routes/quiz.py`, `prompts/diagnostic_quiz.txt`,
`prompts/adaptive_session.txt`, `prompts/adaptive_quiz_only.txt`, `prompts/deep_dive_quiz.txt`

Change quiz JSON output schema to include `dimension_id`:
```json
{
  "question_text": "...",
  "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...",
  "correct_answer": "A",
  "explanation": "...",
  "subtopic_id": "rbi_functions",
  "dimension_id": "monetary_policy_tools",
  "difficulty": "medium"
}
```

Pass the dimension list for the target subtopic into the prompt as `{{available_dimensions}}` so
Claude picks from the canonical list rather than free-texting.

Also inject `{{dimensions_covered_this_session}}` (from `_get_quiz_intelligence()`) so Claude
avoids re-testing dimensions already covered this session.

---

### Phase 3 — Schema: add dimension column to session_answers
**Branch:** `feature/dimension-schema`
**Files:** `scripts/db_init.py`, `backend/routes/sessions.py` (record_answer)

```sql
ALTER TABLE session_answers ADD COLUMN dimension_id TEXT;
```

Add `dimension_id` to the `record_answer()` call in `score_engine.py`. This is additive — old
rows will have NULL dimension_id, new rows will have it populated.

**Note: Requires CLAUDE.md approval gate (ALTER TABLE on existing table).** Flag to Rahul.

---

### Phase 4 — New table: subtopic_dimension_scores
**Branch:** `feature/dimension-scores-table` (can merge with Phase 3)
**Files:** `scripts/db_init.py`, `scripts/score_engine.py`

```sql
CREATE TABLE IF NOT EXISTS subtopic_dimension_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT DEFAULT 'user_1',
    subject_id      TEXT NOT NULL,
    subtopic_id     TEXT NOT NULL,
    dimension_id    TEXT NOT NULL,
    attempts        INTEGER DEFAULT 0,
    correct_count   INTEGER DEFAULT 0,
    score           REAL DEFAULT 0.0,
    last_tested     TIMESTAMP,
    UNIQUE(user_id, subject_id, subtopic_id, dimension_id)
);
```

Update `close_session()` in `score_engine.py` to upsert into this table (group session_answers
by dimension_id, compute accuracy, running average with prior rows).

---

### Phase 5 — Update coverage formula in batch_analyse.py
**Branch:** `feature/dimension-coverage-formula`
**Files:** `scripts/batch_analyse.py`

Replace the current subtopic coverage formula with:

```python
def compute_subtopic_dimension_coverage(subtopic_id, dimensions):
    """Returns (coverage_pct, readiness_score) for a subtopic based on dimension coverage."""
    total_weight = sum(d['final_weight'] for d in dimensions)
    covered_weight = 0.0
    readiness_sum = 0.0

    for dim in dimensions:
        row = db.get_dimension_score(subtopic_id, dim['id'])
        if row is None:
            continue  # untested dimension — contributes 0

        score = row['score']
        # Determine if this dimension needs more testing
        if score >= 0.75:
            coverage_depth = 1.0   # strong — tested once is enough
        elif score >= 0.45:
            coverage_depth = score  # partial — needs more
        else:
            coverage_depth = score * 0.5  # weak — significantly penalised

        covered_weight += dim['final_weight'] * coverage_depth
        readiness_sum += score * dim['final_weight']

    coverage_pct = covered_weight / total_weight if total_weight > 0 else 0.0
    readiness = readiness_sum / total_weight if total_weight > 0 else 0.0
    return coverage_pct, readiness
```

Subject-level coverage becomes `Σ(subtopic_coverage × subtopic_weight) / Σ(subtopic_weights)`.

---

### Phase 6 — Update plan_generator to target untested dimensions
**Branch:** `feature/dimension-aware-planning`
**Files:** `scripts/plan_generator.py`

Pass to Claude: for each scheduled subtopic, which dimensions still need coverage. Claude can
then instruct quiz generation to focus on those specific dimensions via the `{{available_dimensions}}`
prompt variable.

---

## Sequencing

```
Phase 0 → Phase 1 → Phase 2 → Phase 3+4 → Phase 5 → Phase 6
  ↑              ↑           ↑           ↑          ↑
 2min         4hrs        3hrs     needs approval   2hrs
 free         $0.50       free        Rahul        free
```

Total effort: ~12-15 hours dev time. Best done in 2-3 sessions post-exam.

**Approval gate needed:** Phase 3 (ALTER TABLE session_answers) — flag to Rahul before running.
