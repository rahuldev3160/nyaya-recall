# Plan: Efficiency + Fast-Track Improvements

## Context

Day 6 of a 10-day UPSC Prelims sprint. Currently 3.0% overall readiness, 15/205 subtopics tested. User wants to complete preparation 1-2 days early (buffer before exam), reduce wasted API tokens, and automate manual orchestration steps. User prefers a manually-triggered "sprint mode" for aggressive quiz-only scheduling rather than auto-activation.

**Key finding on prompt caching:** NOT viable here. Prompt templates are all under the 1024-token minimum for Sonnet caching. API calls happen once per day max — far outside the 5-minute TTL window. The existing `cache/explanations.json` SHA256 cache already handles the biggest repeated computation. Skip prompt caching entirely.

---

## Changes

### 1. Fast-Track: exam_buffer_days + sprint_mode config fields
**File:** `data/prep_config.json`

Add two fields:
```json
{
  "exam_buffer_days": 2,
  "sprint_mode": false
}
```
- `exam_buffer_days: 2` — tells the plan generator to treat the exam as 2 days sooner
- `sprint_mode: false` — user flips to `true` manually when they want quiz-only for everything

No approval gate needed — purely additive to config.

---

### 2. Patch days_remaining() to respect buffer
**File:** `scripts/plan_generator.py` — `days_remaining()` function (~line 136–142)

```python
def days_remaining() -> int:
    config = load_config()
    start_str = config.get("start_date") or date.today().isoformat()
    total = int(config.get("total_days", 10))
    buffer = int(config.get("exam_buffer_days", 0))
    start = date.fromisoformat(start_str)
    elapsed = max(0, (date.today() - start).days)
    return max(1, total - elapsed - buffer)
```

**Effect today (Day 6, real days_remaining=4):** With buffer=2, plan generator sees `days_remaining=2` → late-sprint rules trigger 2 days early (hard difficulty, re-test all weak subtopics, mixed format based on score).

---

### 3. Sprint mode flag in plan_generation.txt
**File:** `prompts/plan_generation.txt`

Add a `{{sprint_mode}}` placeholder. In `plan_generator.py`, pass `sprint_mode` from config. When `sprint_mode=true`, override all session formats to `quiz_only`.

**Prompt addition (after current rule 5, or as a new rule 9):**
```
9. SPRINT MODE: If sprint_mode=true, ALL sessions must use format=quiz_only regardless of score or test status. Maximize subtopic breadth — do not assign notes_then_quiz under any condition. This is user-controlled.
```

**In plan_generator.py**, add `sprint_mode` to the template context dict (same place as `days_remaining`, `available_hours`, etc.).

To activate: user edits `data/prep_config.json` and sets `"sprint_mode": true`, then runs plan generator.

---

### 4. Right-size max_tokens (4 call sites)

Output tokens are billed at actual usage — this doesn't cut cost directly. But correct ceilings prevent model verbosity drift and reduce API timeout risk.

| File | Line | Change |
|------|------|--------|
| `backend/routes/quiz.py` | ~403 | `8192 → 3000` (10-20 questions ~1,500 tokens) |
| `scripts/batch_analyse.py` | ~328 | `4096 → 2000` (JSON insights ~1,300 tokens) |
| `scripts/plan_generator.py` | ~189 | `4096 → 2048` (plan JSON ~1,500 tokens) |
| `backend/routes/attestation.py` | ~48 | `4096 → 1500` (12 questions ~900 tokens) |

Leave `sessions.py` calls as-is — `expand_concept` (1024), `expand_notes_selection` (1024), `revision_notes` (600) are already correctly sized.

---

### 5. Parallel revision notes via ThreadPoolExecutor
**File:** `backend/routes/sessions.py` — `get_revision_notes()` function (~lines 198–271)

Current: N sequential Haiku calls (1 per wrong answer) → ~2s × N latency.  
Fix: Split into cached (instant) and uncached rows. Fire uncached in parallel via `ThreadPoolExecutor(max_workers=min(N, 5))`. Write cache once after all futures resolve.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def _fetch_one_revision(row, cache, client, prompt_template):
    # build prompt, call client.messages.create(), return (cache_key, explanation)
    ...

# In get_revision_notes():
cached_results = {}
uncached_rows = []
for row in rows:
    key = sha256(...)
    if key in cache:
        cached_results[row["id"]] = cache[key]
    else:
        uncached_rows.append(row)

with ThreadPoolExecutor(max_workers=min(len(uncached_rows), 5)) as ex:
    futures = {ex.submit(_fetch_one_revision, row, cache, _client, tmpl): row for row in uncached_rows}
    for f in as_completed(futures):
        key, explanation = f.result()
        cache[key] = explanation

_save_cache(cache)  # once, after all parallel calls done
# reassemble in original row order
```

**Result:** 5+ wrong answers go from ~10-16s → ~3s.

**Note:** Do NOT use the Batch API here — it has a 24-hour SLA and this is a user-facing synchronous endpoint.

---

### 6. Automated morning prewarm via server lifespan hook
**File:** `backend/server.py` — `_lifespan()` context manager (~lines 40–43)

Add a background subprocess call to `scripts/prewarm_notes_cache.py` on server startup. Use `asyncio.to_thread` so it doesn't block startup.

```python
import asyncio, subprocess, sys
from pathlib import Path

_PREWARM = Path(__file__).parent.parent / "scripts" / "prewarm_notes_cache.py"

def _run_prewarm():
    try:
        subprocess.run([sys.executable, str(_PREWARM)], capture_output=True, timeout=300)
    except Exception:
        pass  # non-fatal

@asynccontextmanager
async def _lifespan(_app):
    _ensure_session_user_notes_table()
    asyncio.create_task(asyncio.to_thread(_run_prewarm))
    yield
```

Prewarm only fires for `notes_then_quiz` sessions. When `sprint_mode=true`, the plan has no such sessions → prewarm exits immediately (no-op). Safe either way.

---

### 7. Schedule evening automation via Claude Code `schedule` skill
Currently: user manually clicks "Sync & Plan" each evening to run `batch_analyse.py` + `plan_generator.py`.

Use the `schedule` skill to create a cron job that runs these two scripts automatically each evening at 10 PM. This is a one-command setup:
```
/schedule — run evening analysis + plan generation at 10 PM daily
```

This removes one manual step from the daily routine so the next day's plan is ready when user wakes up.

---

## What we're NOT doing (and why)

| Idea | Why skipped |
|------|-------------|
| Prompt caching (`cache_control`) | Prompt templates < 1024 token minimum; calls too spread out for 5-min TTL |
| Batch API for revision notes | 24-hour SLA — incompatible with synchronous user-facing endpoint |
| Streaming for quiz generation | Requires frontend changes; limited UX benefit for structured JSON output |
| AsyncAnthropic client | All routes are sync; refactor risk outweighs benefit in 4-day window |

---

## Implementation Order

| Step | Change | Effort | Risk |
|------|--------|--------|------|
| 1 | Add `exam_buffer_days: 2`, `sprint_mode: false` to prep_config.json | 1 min | None |
| 2 | Patch `days_remaining()` in plan_generator.py | 5 min | Low |
| 3 | Add `sprint_mode` placeholder to plan_generation.txt + wire in plan_generator.py | 10 min | Low |
| 4 | Right-size max_tokens (4 files) | 5 min | Low |
| 5 | Prewarm lifespan hook in server.py | 10 min | Low |
| 6 | Parallel revision notes in sessions.py | 20-30 min | Medium |
| 7 | Set up evening schedule via `/schedule` skill | 5 min | Low |

Steps 1-5 can ship as one PR. Step 6 as a second PR. Step 7 is a CLI command.

---

## Verification

1. **Fast-track:** Run `python scripts/plan_generator.py`, confirm `days_remaining` in output JSON = actual_days - 2. Open `data/study_plan.json` and verify session difficulty shifted to `hard` and format is more aggressive.
2. **Sprint mode:** Set `sprint_mode: true` in `prep_config.json`, re-run plan generator, confirm ALL sessions have `format: quiz_only`.
3. **max_tokens:** Start a quiz session, observe no truncation in question output. Check server logs for any `max_tokens` overflow warnings.
4. **Prewarm:** Restart backend server, watch logs for prewarm subprocess completing before first request.
5. **Parallel revision notes:** Finish a quiz with 5+ wrong answers, time the revision notes endpoint — should respond in < 5 seconds.
