# System Audit Fix Plan — UPSC AI Prep
**Branch:** `fix/system-audit-phase1`

## Context

A full audit of the UPSC AI prep system (May 2026) identified a set of correctness bugs spanning the backend quiz routes, score engine, LLM prompts, and frontend dashboard. This plan implements the **Phase 1 + Phase 2** fixes from that audit — the issues that are provably broken from code inspection and can be shipped autonomously (no approval gates, no schema destructives).

**What's already fixed (audit was based on older state):**
- C-04 (localStorage hydration) — already implemented in `session/page.tsx`
- M-08 (per-question notes not pre-populated) — `getQuestionNotes` already called + merged into state
- H-05 (duplicate answer recording for question_notes) — `UNIQUE(session_id, question_hash)` exists, but it's on `question_notes`, not `session_answers` — see below

---

## Issues to Fix

### 1. C-01 — Exam sim missing CA chunks + dimension context
**Files:** `prompts/exam_simulation.txt`, `backend/routes/quiz.py` (around line 1166)

**Problem:** `start_exam_simulation()` builds the prompt with only `{{content_chunks}}`, `{{subtopic_allocation}}`, `{{recent_questions_block}}`, and `{{excluded_question_hashes}}`. It never fetches current-affairs chunks and never injects `{{available_dimensions}}`. The template hardcodes `"dimension_id": null`.

**Fix — two-part:**

A. `prompts/exam_simulation.txt` — add two blocks and fix the output schema:
- After the content_chunks block, add:
  ```
  Recent current-affairs context (use to write contemporary-linkage questions where relevant):
  {{current_affairs_chunks}}
  ```
- After the subtopic allocation block, add:
  ```
  Available dimension_ids for this exam (assign dimension_id to each question — do NOT leave null):
  {{available_dimensions}}
  ```
- In the JSON schema, change `"dimension_id": null` to `"dimension_id": "<dimension_id from available list>"`

B. `backend/routes/quiz.py` — in `start_exam_simulation()` after building `content_chunks_str` (line ~1166):
- Fetch CA chunks per subject: for each unique subject in allocation, call `fetch_ca_chunks(subj.replace("_", " "), k=3)`, collect and join
- Build dimensions string: for each unique (subject_id, subtopic_id) pair in allocation, call `_get_subtopic_dimensions(subject_id, subtopic_id)`, join sections with a header per subtopic
- Add both to the prompt `.replace()` chain:
  ```python
  .replace("{{current_affairs_chunks}}", ca_str)
  .replace("{{available_dimensions}}", available_dimensions_str)
  ```

---

### 2. C-02 — Single-subtopic non-notes path uses k=5 hardcoded
**File:** `backend/routes/quiz.py` line 884

**Problem:** In the single-subtopic non-notes branch, `fetch_chunks(subject_id, primary_subtopic_id)` uses the default `k=5`. The `_chunk_k()` scaling function exists but isn't called here.

**Fix:** Change line 884 from:
```python
chunks = fetch_chunks(subject_id, primary_subtopic_id)
```
to:
```python
chunks = fetch_chunks(subject_id, primary_subtopic_id, k=_chunk_k(num_q))
```

---

### 3. C-05 — close_session() writes across 5 tables without a transaction
**File:** `scripts/score_engine.py` lines 97–159

**Problem:** `close_session()` opens one `con`, commits the `quiz_sessions` UPDATE at line 146, then calls `_update_subtopic_scores`, `_update_subtopic_dimension_scores`, and `_store_session_summary` on that same `con` — but `_update_subtopic_difficulties()` at line 155 opens **its own** separate connection via `difficulty_engine.update_difficulty()`. If the process dies after the first commit (line 146) but before the second (line 158), `quiz_sessions` is updated while subtopic scores are not. There is no `BEGIN TRANSACTION` wrapping the whole operation.

**Fix:**
- Wrap the entire body of `close_session()` after the initial fetch in a single `try/except` with explicit `con.execute("BEGIN IMMEDIATE")` at the start and a single `con.commit()` at the end.
- Move `_update_subtopic_difficulties()` to receive the `con` object (or re-open and commit inside a finally block). The simplest correct fix: move the `_update_subtopic_difficulties(answers)` call to **after** `con.commit()` + `con.close()` — difficulty updates are idempotent and not required for session correctness.

Revised structure:
```python
def close_session(session_id: str) -> dict:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    # ... fetch answers and session_row ...

    try:
        con.execute("BEGIN IMMEDIATE")
        # UPDATE quiz_sessions
        # _store_exam_sim_record or _update_subtopic_scores + _update_subtopic_dimension_scores
        # _store_session_summary
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

    # Difficulty update is idempotent — run outside transaction
    if not is_exam_sim:
        _update_subtopic_difficulties(answers)
    ...
```

---

### 4. H-05 — session_answers has no UNIQUE guard against duplicate submissions
**Files:** `scripts/db_init.py`, `scripts/score_engine.py` line 70

**Problem:** `session_answers` schema (db_init.py lines 52–69) has no `UNIQUE(session_id, question_hash)` constraint. Frontend retries of a failed answer submission record the same answer twice, inflating `subtopic_scores`.

**Fix:**

A. `scripts/db_init.py` — add to `session_answers` CREATE TABLE:
```sql
UNIQUE(session_id, question_hash)
```
This applies to fresh DBs.

B. Add an `ALTER TABLE` migration that runs on startup (in `db_init.py` or a one-time migration script):
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_session_qhash
    ON session_answers(session_id, question_hash);
```
Using a unique index is safe on an existing table — if there are existing duplicates, the index will fail; add `ON CONFLICT IGNORE` via the INSERT change below.

C. `scripts/score_engine.py` line 70 — change the INSERT to:
```python
con.execute("INSERT OR IGNORE INTO session_answers (...) VALUES (...)", ...)
```

---

### 5. H-06 — batch_analyse truncated at max_tokens=8192
**File:** `scripts/batch_analyse.py` line 647

**Problem:** Input prompt can reach ~30K tokens; `max_tokens=8192` output cap can silently truncate the analysis JSON mid-object.

**Fix:** Add extended-output beta and raise cap:
```python
response = client.messages.create(
    model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
    max_tokens=16000,
    betas=["output-128k-2025-02-19"],
    messages=[{"role": "user", "content": prompt}],
)
```

---

### 6. H-08 — plan_generator truncated at max_tokens=4096
**File:** `scripts/plan_generator.py` line 320

**Problem:** Worst-case plan prompt is ~55K tokens; `max_tokens=4096` means plans with more than ~4 sessions are silently dropped.

**Fix:** Same pattern as H-06:
```python
response = client.messages.create(
    model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
    max_tokens=8192,
    betas=["output-128k-2025-02-19"],
    messages=[{"role": "user", "content": prompt}]
)
```

---

### 7. H-07 — plan_generator reads stale profile without freshness check
**File:** `scripts/plan_generator.py` lines 282–284

**Problem:** `generate_plan()` reads `prep_profile.json` with no check on `last_updated`. If batch analysis hasn't been run, today's plan is built on yesterday's data.

**Fix:** After loading the profile, add:
```python
last_updated = profile.get("last_updated")
if last_updated:
    age_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(last_updated)).total_seconds() / 3600
    if age_hours > 12:
        print(f"⚠️  WARNING: prep_profile.json is {age_hours:.0f}h old. Run batch_analyse.py first for an accurate plan.")
```

---

### 8. M-09 — Dashboard shows no staleness indicator
**File:** `web/src/app/page.tsx`

**Problem:** `profile.last_updated` is written by batch_analyse.py and returned by `/tracker/profile`, but the dashboard never displays it. Users may act on hours-old readiness data.

**Fix:** In the dashboard component, after the readiness percentage display, add a small "Last synced X hours ago" line:
```tsx
{profile?.last_updated && (() => {
  const ageMs = Date.now() - new Date(profile.last_updated).getTime();
  const ageH = Math.floor(ageMs / 3_600_000);
  const label = ageH === 0 ? "just now" : ageH === 1 ? "1 hour ago" : `${ageH} hours ago`;
  return (
    <p className={`text-xs mt-1 ${ageH >= 12 ? "text-amber-400" : "text-gray-500"}`}>
      Last synced {label}
    </p>
  );
})()}
```
Amber color for ≥12h staleness draws attention.

---

## Diagram — data flow after fixes

```
Quiz session (regular)
  fetch_chunks(subtopic, k=_chunk_k(num_q))  ← C-02 fix
  fetch_ca_chunks(subtopic_name, k=3)          ← already correct
  → generate_quiz()
  → record_answer() [INSERT OR IGNORE]          ← H-05 fix
  → close_session()
      BEGIN IMMEDIATE
      UPDATE quiz_sessions
      _update_subtopic_scores
      _update_subtopic_dimension_scores
      _store_session_summary
      COMMIT
      [after close] _update_subtopic_difficulties   ← C-05 fix

Exam simulation
  fetch_chunks(per subtopic, k=_chunk_k(n))
  fetch_ca_chunks(per subject, k=3)            ← C-01 fix
  _get_subtopic_dimensions(per subtopic)       ← C-01 fix
  → start_exam_simulation()
  → exam_simulation.txt with all 3 contexts injected

Batch analysis
  max_tokens=16000 + extended-output beta      ← H-06 fix
  → updates prep_profile.json with last_updated

Plan generator
  freshness check on last_updated              ← H-07 fix
  max_tokens=8192 + extended-output beta       ← H-08 fix

Dashboard
  shows "last synced X hours ago"              ← M-09 fix
```

---

## Critical files to modify

| File | Changes |
|---|---|
| `prompts/exam_simulation.txt` | Add `{{current_affairs_chunks}}` + `{{available_dimensions}}` blocks; fix `dimension_id` schema |
| `backend/routes/quiz.py` (line ~1166) | Fetch CA + dimensions in `start_exam_simulation()` |
| `backend/routes/quiz.py` (line 884) | Pass `k=_chunk_k(num_q)` to `fetch_chunks()` |
| `scripts/score_engine.py` (lines 97–159) | Wrap in `BEGIN IMMEDIATE` / `COMMIT`, move difficulty update after close |
| `scripts/score_engine.py` (line 70) | Change INSERT to `INSERT OR IGNORE` |
| `scripts/db_init.py` | Add `UNIQUE(session_id, question_hash)` to `session_answers`; add migration index |
| `scripts/batch_analyse.py` (line 647) | Raise `max_tokens=16000`, add extended-output beta |
| `scripts/plan_generator.py` (line 320) | Raise `max_tokens=8192`, add extended-output beta |
| `scripts/plan_generator.py` (line 282) | Add freshness warning |
| `web/src/app/page.tsx` | Add "last synced" staleness indicator |

---

## Out of scope (deferred)

- **C-03 (CSAT)** — deferred pending Rahul confirmation on priority vs. exam timeline
- **H-01 / M-01 (ChromaDB subtopic_id metadata)** — requires full re-ingest of 11,146 chunks; one-time but destructive to run — needs separate planning session
- **H-03 / H-04 (orphaned prompt templates)** — batch_analysis.txt and generate_dimensions.txt wiring — lower impact, separate PR
- **H-02 (CA query by topic not subject for merged/exam sessions)** — partially addressed by C-01 fix for exam sim; merged-session CA query improvement is separate

---

## Verification

1. **C-01**: Start an exam simulation with 10Q. Inspect the returned `questions[]` — all should have a non-null `dimension_id`. Backend logs should show CA chunks fetched.
2. **C-02**: Start a 20-question adaptive session on a single subtopic; add a debug print (or log) to confirm k=22 is clamped to 8 via `_chunk_k(20)`.
3. **C-05**: Add a deliberate exception after the first commit in `close_session()` (in dev), confirm the DB is clean (session not partially written).
4. **H-05**: Submit the same answer twice (simulate with `curl`); confirm only one row in `session_answers`.
5. **H-06 / H-08**: Run `batch_analyse.py` and `plan_generator.py` after 5+ sessions; confirm JSON output is not truncated.
6. **H-07**: Set `last_updated` to 24h ago in `prep_profile.json`; run `plan_generator.py`; confirm warning is printed.
7. **M-09**: Load the dashboard; confirm "last synced X hours ago" appears next to readiness %.
8. Run `cd web && npx tsc --noEmit` and `cd web && npm run lint` — must pass.
