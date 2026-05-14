#!/usr/bin/env python3
"""Pre-warm synthesised notes cache for today's planned sessions.

Run once after updating the plan or after first install:
    python3 scripts/prewarm_notes_cache.py
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "routes"))
sys.path.insert(0, str(ROOT / "scripts"))

# Load .env so ANTHROPIC_API_KEY is available without sourcing the shell
_env_file = ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            if _k.strip() not in os.environ:
                os.environ[_k.strip()] = _v.strip()

PLAN_PATH = ROOT / "data" / "study_plan.json"


def main() -> None:
    from routes.quiz import fetch_chunks_with_meta, synthesize_notes_cached  # type: ignore

    plan = json.loads(PLAN_PATH.read_text())
    sessions = plan.get("sessions", [])
    targets = [
        s for s in sessions
        if s.get("format") == "notes_then_quiz" and s.get("subtopic_id")
    ]

    if not targets:
        print("No notes_then_quiz sessions in today's plan.")
        return

    print(f"Pre-warming notes for {len(targets)} session(s)...\n")
    for s in targets:
        subject_id = s["subject_id"]
        subtopic_id = s["subtopic_id"]
        label = f"{subject_id}/{subtopic_id}"
        print(f"  {label} ...", end=" ", flush=True)
        rows = fetch_chunks_with_meta(subject_id, subtopic_id, k=14)
        synthesize_notes_cached(rows, subtopic_id, subject_id)
        chunk_count = len(rows)
        print(f"done ({chunk_count} chunk{'s' if chunk_count != 1 else ''})")

    print("\nAll notes cached. Sessions will load instantly.")


if __name__ == "__main__":
    main()
