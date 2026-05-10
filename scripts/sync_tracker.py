#!/usr/bin/env python3
"""Cheap tracker sync helper: git summary only (no full-repo LLM ingest).

Usage (from repo root):
  python3 scripts/sync_tracker.py
  python3 scripts/sync_tracker.py --write-state

Updates docs/tracker_state.json last_sync_* when --write-state is passed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        return f"(error {p.returncode}) {p.stderr.strip() or p.stdout.strip()}"
    return p.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Print git delta summary for tracker sync.")
    parser.add_argument(
        "--write-state",
        action="store_true",
        help="Write last_sync_at and last_sync_git_sha to docs/tracker_state.json",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    state_path = repo_root / "docs" / "tracker_state.json"
    if not state_path.is_file():
        print(f"Missing {state_path}", file=sys.stderr)
        return 1

    state = json.loads(state_path.read_text(encoding="utf-8"))
    last_sha = state.get("last_sync_git_sha")

    head = _run(["git", "rev-parse", "HEAD"], repo_root)
    short = _run(["git", "rev-parse", "--short", "HEAD"], repo_root)
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    last_log = _run(["git", "log", "-1", "--oneline"], repo_root)

    print("=== Tracker sync (git delta only) ===")
    print(f"Repo: {repo_root}")
    print(f"Branch: {branch}")
    print(f"HEAD: {short} ({head})")
    print(f"Last commit: {last_log}")
    print(f"interval_mode (informational): {state.get('interval_mode', 'manual')}")

    if last_sha:
        rng = f"{last_sha}..HEAD"
        stat = _run(["git", "diff", "--stat", rng], repo_root)
        logs = _run(["git", "log", "--oneline", rng], repo_root)
        print(f"\nCommits since last_sync_git_sha ({last_sha[:7]}..):\n{logs or '(none)'}")
        print(f"\nDiff stat:\n{stat or '(no diff)'}")
    else:
        print("\nNo last_sync_git_sha set — next run after --write-state will show deltas.")

    if args.write_state:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state["last_sync_at"] = now
        state["last_sync_git_sha"] = head
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {state_path} (last_sync_at, last_sync_git_sha).")

    print("\nNext: update docs/PROJECT_TRACKER.md + docs/CHRONICLE.md if decisions changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
