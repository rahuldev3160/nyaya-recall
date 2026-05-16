"""Generate 4-8 testable dimensions per subtopic in data/syllabus.json using Claude Haiku.

Usage:
    python3 scripts/generate_syllabus_dimensions.py

Idempotent — skips subtopics that already have a 'dimensions' key.
Processes subtopics in batches of 10 per Haiku call.
Writes dimensions directly into data/syllabus.json.

Weight formula per dimension:
    final_weight = pyq_weight × (1.5 if has_current_affairs else 1.0) × (2.0 if is_core_concept else 1.0)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SYLLABUS_PATH = PROJECT_ROOT / "data" / "syllabus.json"
PROMPT_PATH   = PROJECT_ROOT / "prompts" / "generate_dimensions.txt"
DB_PATH       = os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "upsc.db"))

API_KEY       = os.getenv("ANTHROPIC_API_KEY")
MODEL_FAST    = os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001")

BATCH_SIZE    = 3           # subtopics per Haiku call (10 caused JSON truncation at 4096 tokens)
RETRY_LIMIT   = 3
RETRY_DELAY   = 5           # seconds between retries

if not API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set. Check .env at project root.")
    sys.exit(1)

client = anthropic.Anthropic(api_key=API_KEY)


# ---------------------------------------------------------------------------
# PYQ weight helpers
# ---------------------------------------------------------------------------

def _load_pyq_weights() -> dict[str, float]:
    """Load PYQ priority weights for subtopics.

    Tries priority_scorer.compute_all_priorities() first (live DB query).
    Falls back to empty dict — missing weights default to 1.0 later.
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from priority_scorer import compute_all_priorities
        weights = compute_all_priorities()
        print(f"  Loaded PYQ weights for {len(weights)} subtopics from priority_scorer.")
        return weights
    except Exception as exc:
        print(f"  Warning: could not load PYQ weights ({exc}). Defaulting all to 1.0.")
        return {}


# ---------------------------------------------------------------------------
# Dimension generation
# ---------------------------------------------------------------------------

def _compute_final_weight(pyq_weight: float, has_ca: bool, is_core: bool) -> float:
    """Apply the dimension weight formula from the spec."""
    return round(pyq_weight * (1.5 if has_ca else 1.0) * (2.0 if is_core else 1.0), 4)


def _call_haiku_batch(
    batch: list[dict[str, str]],
    prompt_template: str,
    attempt: int = 1,
) -> list[dict[str, Any]]:
    """Call Claude Haiku with a batch of subtopics, return list of dimension objects."""
    batch_json = json.dumps(
        [{"subtopic_id": s["id"], "name": s["name"]} for s in batch],
        ensure_ascii=False,
    )
    prompt = prompt_template.replace("{{subtopics_batch}}", batch_json)

    try:
        response = client.messages.create(
            model=MODEL_FAST,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON array found in response")
        return json.loads(raw[start:end])
    except Exception as exc:
        if attempt < RETRY_LIMIT:
            print(f"    Retry {attempt}/{RETRY_LIMIT} after error: {exc}")
            time.sleep(RETRY_DELAY * attempt)
            return _call_haiku_batch(batch, prompt_template, attempt + 1)
        print(f"    FAILED after {RETRY_LIMIT} attempts: {exc}")
        return []


def _enrich_dimensions(
    raw_dims: list[dict[str, Any]],
    subtopic_id: str,
    pyq_weight: float,
) -> list[dict[str, Any]]:
    """Attach pyq_weight, base_weight, and final_weight to each dimension."""
    enriched: list[dict[str, Any]] = []
    for d in raw_dims:
        has_ca   = bool(d.get("has_current_affairs", False))
        is_core  = bool(d.get("is_core_concept", True))
        base_w   = pyq_weight                          # base_weight = subtopic-level PYQ weight
        final_w  = _compute_final_weight(pyq_weight, has_ca, is_core)
        enriched.append({
            "id":                  d.get("id", f"{subtopic_id}_dim"),
            "name":                d.get("name", "Unnamed dimension"),
            "pyq_weight":          round(pyq_weight, 4),
            "has_current_affairs": has_ca,
            "is_core_concept":     is_core,
            "base_weight":         round(base_w, 4),
            "final_weight":        final_w,
        })
    return enriched


# ---------------------------------------------------------------------------
# Syllabus traversal
# ---------------------------------------------------------------------------

def _collect_subtopics_needing_dims(syllabus: dict) -> list[dict[str, str]]:
    """Return list of {id, name, subject_id} for subtopics without 'dimensions'."""
    missing: list[dict[str, str]] = []
    for subj in syllabus.get("subjects", []):
        for topic in subj.get("topics", []):
            for st in topic.get("subtopics", []):
                if "dimensions" not in st:
                    missing.append({
                        "id":         st["id"],
                        "name":       st["name"],
                        "subject_id": subj["id"],
                    })
    return missing


def _write_dimensions_to_syllabus(
    syllabus: dict,
    dimensions_map: dict[str, list[dict[str, Any]]],
) -> dict:
    """Mutate syllabus in-place, adding 'dimensions' to each subtopic."""
    for subj in syllabus.get("subjects", []):
        for topic in subj.get("topics", []):
            for st in topic.get("subtopics", []):
                st_id = st["id"]
                if st_id in dimensions_map:
                    st["dimensions"] = dimensions_map[st_id]
    return syllabus


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== generate_syllabus_dimensions.py ===\n")

    # Load prompt template
    if not PROMPT_PATH.exists():
        print(f"ERROR: Prompt template not found at {PROMPT_PATH}")
        sys.exit(1)
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")

    # Load syllabus
    if not SYLLABUS_PATH.exists():
        print(f"ERROR: syllabus.json not found at {SYLLABUS_PATH}")
        sys.exit(1)
    syllabus = json.loads(SYLLABUS_PATH.read_text(encoding="utf-8"))

    # Find subtopics that need dimensions
    pending = _collect_subtopics_needing_dims(syllabus)
    total_subtopics = sum(
        len(st.get("subtopics", []))
        for subj in syllabus.get("subjects", [])
        for st in subj.get("topics", [])
    )
    print(f"Total subtopics in syllabus : {total_subtopics}")
    print(f"Already have dimensions     : {total_subtopics - len(pending)}")
    print(f"Needs dimensions            : {len(pending)}")

    if not pending:
        print("\nAll subtopics already have dimensions. Nothing to do.")
        return

    # Load PYQ weights
    print("\nLoading PYQ weights...")
    pyq_weights = _load_pyq_weights()

    # Process in batches
    dimensions_map: dict[str, list[dict[str, Any]]] = {}
    n_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\nProcessing {len(pending)} subtopics in {n_batches} batch(es) of up to {BATCH_SIZE}...\n")

    for i in range(n_batches):
        batch = pending[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        batch_ids = [s["id"] for s in batch]
        print(f"Batch {i+1}/{n_batches}: {batch_ids}")

        raw_results = _call_haiku_batch(batch, prompt_template)

        # Map results back to subtopic_id
        result_by_id: dict[str, list[dict]] = {}
        for result in raw_results:
            st_id = result.get("subtopic_id")
            if st_id and isinstance(result.get("dimensions"), list):
                result_by_id[st_id] = result["dimensions"]

        # Enrich and accumulate
        for st in batch:
            st_id    = st["id"]
            pyq_w    = pyq_weights.get(st_id, 1.0)
            raw_dims = result_by_id.get(st_id, [])

            if not raw_dims:
                print(f"  WARNING: no dimensions returned for {st_id} — skipping")
                continue

            enriched = _enrich_dimensions(raw_dims, st_id, pyq_w)
            dimensions_map[st_id] = enriched
            print(f"  {st_id}: {len(enriched)} dimensions (pyq_weight={pyq_w:.2f})")

        # Save after every batch (resilient to interruption)
        updated_syllabus = _write_dimensions_to_syllabus(syllabus, dimensions_map)
        SYLLABUS_PATH.write_text(
            json.dumps(updated_syllabus, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  [saved] syllabus.json updated ({len(dimensions_map)} subtopics done)\n")

        # Small pause between batches to be kind to the API
        if i < n_batches - 1:
            time.sleep(1)

    # Final summary
    skipped = len(pending) - len(dimensions_map)
    print(f"\n=== Done ===")
    print(f"  Dimensions generated : {len(dimensions_map)} subtopics")
    if skipped:
        print(f"  Skipped (no output)  : {skipped} subtopics — re-run to retry")
    print(f"  syllabus.json        : {SYLLABUS_PATH}")

    # Quick sanity check — print first subtopic of first subject
    print("\nSanity check — first subtopic of polity:")
    for subj in syllabus.get("subjects", []):
        if subj["id"] == "polity":
            first_st = subj["topics"][0]["subtopics"][0]
            print(json.dumps(first_st, indent=2, ensure_ascii=False))
            break


if __name__ == "__main__":
    main()
