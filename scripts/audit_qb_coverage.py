#!/usr/bin/env python3
"""
Audit question_bank coverage per subtopic.
Prints subtopics with < 5 questions — those need AI gap-fill or more ingestion.
Run after any new batch ingestion to check coverage health.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db import get_conn


def audit(threshold: int = 5):
    with get_conn() as con:
        total = con.execute(
            "SELECT COUNT(*) FROM question_bank WHERE cancelled = 0"
        ).fetchone()[0]

        subtopic_count = con.execute(
            "SELECT COUNT(DISTINCT subtopic_id) FROM question_bank WHERE cancelled = 0"
        ).fetchone()[0]

        by_source = con.execute(
            """
            SELECT exam_source, COUNT(*) as cnt
            FROM question_bank WHERE cancelled = 0
            GROUP BY exam_source ORDER BY cnt DESC
            """
        ).fetchall()

        gaps = con.execute(
            f"""
            SELECT subtopic_id, subject_id,
                   COUNT(*) AS question_count,
                   AVG(upsc_relevance) AS avg_relevance
            FROM question_bank
            WHERE cancelled = 0
            GROUP BY subtopic_id, subject_id
            HAVING COUNT(*) < {threshold}
            ORDER BY avg_relevance DESC
            """
        ).fetchall()

    print(f"\n{'='*50}")
    print(f"  Question Bank Coverage Audit")
    print(f"{'='*50}")
    print(f"  Total questions (non-cancelled): {total:,}")
    print(f"  Subtopics with coverage:         {subtopic_count}")
    print(f"\n  By source:")
    for r in by_source:
        print(f"    {r['exam_source']:25s} {r['cnt']:>5,} questions")

    print(f"\n  Subtopics with < {threshold} questions: {len(gaps)}")
    if gaps:
        print(f"\n  Priority gaps (need AI gap-fill or more ingestion):")
        for g in gaps:
            bar = "█" * g["question_count"] + "░" * (threshold - g["question_count"])
            print(
                f"    [{bar}] {g['subject_id']:20s} / {g['subtopic_id']:35s} "
                f"{g['question_count']}q  (weight={g['avg_relevance']:.2f})"
            )
    else:
        print(f"\n  ✓ All subtopics have ≥ {threshold} questions.")
    print()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Audit question bank coverage")
    p.add_argument("--threshold", type=int, default=5, help="Min questions per subtopic")
    args = p.parse_args()
    audit(args.threshold)
