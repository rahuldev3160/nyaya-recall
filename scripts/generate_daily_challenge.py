#!/usr/bin/env python3
"""
Generate today's 10-question leaderboard challenge.
Run daily at 00:01 IST via Railway Cron or launchd.
Same question set for every user — powers the leaderboard.
"""
import json
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db import get_conn


def generate():
    today = date.today().isoformat()

    with get_conn() as con:
        if con.execute(
            "SELECT 1 FROM daily_challenge WHERE challenge_date = ?", [today]
        ).fetchone():
            print(f"Challenge for {today} already exists — skipping.")
            return

        # Candidates: medium difficulty, not AI-generated, not used in last 30 days
        rows = con.execute(
            """
            SELECT id, subject_id FROM question_bank
            WHERE cancelled = 0
              AND answer_source != 'ai_generated'
              AND COALESCE(global_accuracy, 0.5) BETWEEN 0.3 AND 0.7
              AND id NOT IN (
                  SELECT json_each.value
                  FROM daily_challenge, json_each(question_ids)
                  WHERE challenge_date > date('now', '-30 days')
              )
            ORDER BY exam_source = 'upsc_cse' DESC, RANDOM()
            LIMIT 100
            """
        ).fetchall()

        if not rows:
            print("WARNING: no candidates found — question bank may be empty.")
            return

        # Pick 10 with subject diversity (max 3 per subject)
        by_subject: dict[str, list[str]] = {}
        for r in rows:
            by_subject.setdefault(r["subject_id"], []).append(r["id"])

        selected: list[str] = []
        rounds = 0
        while len(selected) < min(10, len(rows)) and rounds < 50:
            rounds += 1
            for subj in list(by_subject.keys()):
                if len(selected) >= 10:
                    break
                pool = by_subject[subj]
                if pool:
                    selected.append(pool.pop(0))
                    if not pool:
                        del by_subject[subj]

        random.shuffle(selected)
        subjects_covered = len({r["subject_id"] for r in rows if r["id"] in selected})

        con.execute(
            "INSERT INTO daily_challenge (challenge_date, question_ids) VALUES (?, ?)",
            [today, json.dumps(selected)],
        )

    print(
        f"Daily challenge {today}: {len(selected)} questions "
        f"from {subjects_covered} subjects."
    )


if __name__ == "__main__":
    generate()
