"""Generate testable dimensions for an exam's topics, grounded in real PYQ text pulled
from nyaya-core — NOT from Haiku's own training-knowledge guess.

Why this exists as a separate script, not a change to generate_syllabus_dimensions.py:
that script sends Haiku only {subtopic_id, name} and asks it to "ground dimensions in
real UPSC exam patterns (2009-2025)" using its own training knowledge — zero actual PYQ
text is ever passed in (confirmed by reading it; it has no PYQ-fetching code at all). For
UPSC Prelims (extremely well-represented in training data) that may be an acceptable risk;
for PFRDA/EPFO (far more niche exams) it is not — this script instead injects the real
question text nyaya-core has already verified, and instructs the model to derive
dimensions ONLY from patterns visible in that text. This is a genuine improvement over
generate_syllabus_dimensions.py's method, not just parity — see DECIDE-37 in nyaya-core's
docs/decisions.md.

Real per-exam PYQ distribution (checked against nyaya-core's live data): PFRDA is
long-tailed — 94 topics, average 5.0 real PYQs each, many with exactly 1 — so a fixed
minimum-evidence threshold (MIN_REAL_PYQS) is enforced per topic; below it, this script
writes `insufficient_pyq_evidence: true` for that topic instead of inventing dimensions
to fill a quota (same "flag, don't guess" principle as nyaya-core's ReviewNeededError).

Output: data/dimensions/{exam_id}.json — a NEW file per exam, never syllabus.json, which
stays untouched for UPSC Prelims.

Usage:
    /opt/homebrew/bin/python3.11 scripts/generate_dimensions_from_pyqs.py --exam_id pfrda_gradea
    /opt/homebrew/bin/python3.11 scripts/generate_dimensions_from_pyqs.py --exam_id upsc_epfo_apfc_eo_ao --force
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DIMENSIONS_DIR = PROJECT_ROOT / "data" / "dimensions"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "generate_dimensions_from_pyqs.txt"

NYAYA_CORE_API_URL = os.getenv("NYAYA_CORE_API_URL", "http://127.0.0.1:8420")
API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL_FAST = os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001")

MIN_REAL_PYQS = 3  # below this, flag insufficient_pyq_evidence rather than invent
RETRY_LIMIT = 3
RETRY_DELAY = 5

if not API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set. Check .env at project root.")
    sys.exit(1)

client = anthropic.Anthropic(api_key=API_KEY)


class NyayaCoreUnavailableError(RuntimeError):
    """nyaya-core's local API didn't respond — never silently fall back to invented
    content (same principle as nyaya-core's own DECIDE-10 score-floor design)."""


def _get_json(path: str, params: dict[str, Any]) -> Any:
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{NYAYA_CORE_API_URL}{path}?{query}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise NyayaCoreUnavailableError(
            f"Could not reach nyaya-core's API at {NYAYA_CORE_API_URL} ({exc}). "
            "Start it with: .venv/bin/python -m src.api.main (from the nyaya-core repo)."
        ) from exc


def fetch_topics(exam_id: str) -> list[dict]:
    return _get_json("/topics", {"exam_id": exam_id})


def fetch_real_pyqs(exam_id: str, topic_id: str) -> list[dict]:
    """MCQ rows only, void excluded — a void item was dropped by the exam board itself,
    not real signal about what's testable. Both verified and unverified rows are used:
    an unverified row's question_text is still real, recorded exam content even if its
    correct_option hasn't been checked against an official key yet."""
    rows = _get_json(
        "/pyq", {"exam_id": exam_id, "topic_id": topic_id, "question_format": "mcq", "limit": 500}
    )
    return [r for r in rows if r.get("status") != "void"]


def _format_pyq_for_prompt(pyq: dict) -> str:
    lines = [f"Q: {pyq['question_text']}"]
    if pyq.get("options"):
        for letter, text in sorted(pyq["options"].items()):
            lines.append(f"  {letter}) {text}")
    return "\n".join(lines)


def _call_haiku(topic_name: str, real_pyqs: list[dict], prompt_template: str, attempt: int = 1) -> list[dict]:
    pyq_block = "\n\n".join(_format_pyq_for_prompt(p) for p in real_pyqs)
    prompt = prompt_template.replace("{{topic_name}}", topic_name).replace("{{real_pyqs}}", pyq_block)

    try:
        response = client.messages.create(
            model=MODEL_FAST, max_tokens=2048, messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON array found in response")
        return json.loads(raw[start:end])
    except Exception as exc:
        if attempt < RETRY_LIMIT:
            print(f"    Retry {attempt}/{RETRY_LIMIT} after error: {exc}")
            time.sleep(RETRY_DELAY * attempt)
            return _call_haiku(topic_name, real_pyqs, prompt_template, attempt + 1)
        print(f"    FAILED after {RETRY_LIMIT} attempts: {exc}")
        return []


def build_topic_entry(topic: dict, real_pyqs: list[dict], prompt_template: str) -> dict:
    topic_id = topic["topic_id"]
    if len(real_pyqs) < MIN_REAL_PYQS:
        return {
            "topic_id": topic_id,
            "name": topic["name"],
            "insufficient_pyq_evidence": True,
            "real_pyq_count": len(real_pyqs),
            "dimensions": [],
        }

    raw_dims = _call_haiku(topic["name"], real_pyqs, prompt_template)
    dimensions = []
    for d in raw_dims:
        dimensions.append(
            {
                "id": d.get("id", f"{topic_id}_dim"),
                "name": d.get("name", "Unnamed dimension"),
                "is_core_concept": bool(d.get("is_core_concept", True)),
                # pyq_weight/final_weight deliberately NOT computed here — nyaya-core's
                # real exam_topics.weight (returned in `topic["weight"]`) is the
                # authoritative, recency-decayed real-frequency signal; recomputing a
                # second, ungrounded weight here would just create two sources of truth.
            }
        )
    return {
        "topic_id": topic_id,
        "name": topic["name"],
        "weight": topic.get("weight"),  # real exam_topics.weight, from nyaya-core
        "insufficient_pyq_evidence": False,
        "real_pyq_count": len(real_pyqs),
        "source_question_ids": [p["question_id"] for p in real_pyqs],
        "dimensions": dimensions,
    }


def run(exam_id: str, force: bool) -> None:
    if not PROMPT_PATH.exists():
        print(f"ERROR: prompt template not found at {PROMPT_PATH}")
        sys.exit(1)
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")

    out_path = DIMENSIONS_DIR / f"{exam_id}.json"
    existing: dict[str, dict] = {}
    if out_path.exists() and not force:
        existing = {e["topic_id"]: e for e in json.loads(out_path.read_text())}
        print(f"Resuming: {len(existing)} topic(s) already done in {out_path.name} (use --force to redo all).")

    raw_topics = fetch_topics(exam_id)
    if not raw_topics:
        print(f"No topics found for exam_id='{exam_id}' via /topics — check it's registered in nyaya-core.")
        return
    # /topics returns one row per (exam_id, paper_id, topic_id) — a topic linked under 2+
    # papers (real, e.g. pfrda_gradea's General/Research-stream overlap) appears more than
    # once with the same real weight each time (verified live: 74/195 of PFRDA's rows are
    # such duplicates, weight identical every time) — dedupe here so this script doesn't
    # spend a real Haiku call twice on the same topic.
    topics = list({t["topic_id"]: t for t in raw_topics}.values())
    if len(topics) < len(raw_topics):
        print(f"{len(raw_topics)} topic row(s) from /topics, {len(topics)} unique topic_id(s) "
              f"after dedup (a topic linked under 2+ papers appears once per paper).")
    else:
        print(f"{len(topics)} topic(s) registered for '{exam_id}'.")

    DIMENSIONS_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = dict(existing)

    for i, topic in enumerate(topics, start=1):
        topic_id = topic["topic_id"]
        if topic_id in existing:
            continue
        real_pyqs = fetch_real_pyqs(exam_id, topic_id)
        entry = build_topic_entry(topic, real_pyqs, prompt_template)
        results[topic_id] = entry

        if entry["insufficient_pyq_evidence"]:
            print(f"  [{i}/{len(topics)}] {topic_id}: only {entry['real_pyq_count']} real PYQ(s) — flagged, skipped.")
        else:
            print(
                f"  [{i}/{len(topics)}] {topic_id}: {len(entry['dimensions'])} dimensions "
                f"from {entry['real_pyq_count']} real PYQs (weight={entry['weight']})."
            )

        out_path.write_text(json.dumps(list(results.values()), indent=2, ensure_ascii=False))

    n_flagged = sum(1 for e in results.values() if e["insufficient_pyq_evidence"])
    print(f"\nDone: {len(results)} topics written to {out_path}. {n_flagged} flagged insufficient_pyq_evidence.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exam_id", required=True)
    parser.add_argument("--force", action="store_true", help="Redo every topic, ignoring existing output.")
    args = parser.parse_args()
    try:
        run(args.exam_id, args.force)
    except NyayaCoreUnavailableError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
