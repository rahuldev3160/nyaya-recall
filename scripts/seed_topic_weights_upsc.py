"""
Seed topic_weights for UPSC Prelims GS Paper 1 (exam_source='upsc_prelims'),
using the real 2026 paper's subject-level split (PLAN-011 Area 2). Idempotent:
safe to re-run (INSERT OR REPLACE).

Subject-level % (from published 2026 paper analysis):
  History/Art&Culture 20% (split between history_amac + modern_history by
    subtopic count, since syllabus.json splits History into two subject_ids),
  Sci-Tech 17, Economy 16, IR/Defense 13 (-> ir_governance), Polity 12,
  Environment 10, Geography 9, CA/misc 3. CSAT excluded (separate system).

Each subject's % is distributed evenly across its own subtopics -- no finer
real data exists than subject-level, so even split within-subject is the
least-arbitrary default.

Run: python3 scripts/seed_topic_weights_upsc.py
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "upsc.db"
SYLLABUS_PATH = ROOT / "data" / "syllabus.json"
EXAM_SOURCE = "upsc_prelims"

SUBJECT_PCT = {
    "science_tech": 17.0,
    "economy": 16.0,
    "ir_governance": 13.0,
    "polity": 12.0,
    "environment": 10.0,
    "geography": 9.0,
    "current_affairs": 3.0,
    # history_amac + modern_history filled in below (share 20% by subtopic count)
}
HISTORY_BUCKET_PCT = 20.0
HISTORY_SUBJECTS = ("history_amac", "modern_history")


def main():
    syllabus = json.loads(SYLLABUS_PATH.read_text())
    subjects = {s["id"]: s for s in syllabus["subjects"]}

    history_subtopic_counts = {}
    for sid in HISTORY_SUBJECTS:
        n = sum(len(t.get("subtopics", [])) for t in subjects[sid]["topics"])
        history_subtopic_counts[sid] = n
    total_history_st = sum(history_subtopic_counts.values())
    for sid, n in history_subtopic_counts.items():
        SUBJECT_PCT[sid] = HISTORY_BUCKET_PCT * n / total_history_st

    assert abs(sum(SUBJECT_PCT.values()) - 100.0) < 0.01, f"weights sum to {sum(SUBJECT_PCT.values())}, not 100"

    rows = []
    for subject_id, pct in SUBJECT_PCT.items():
        subj = subjects[subject_id]
        subtopics = [
            (topic["id"], st["id"])
            for topic in subj["topics"]
            for st in topic.get("subtopics", [])
        ]
        n = len(subtopics)
        if n == 0:
            continue
        per_st_weight = pct / n
        for topic_id, st_id in subtopics:
            rows.append((EXAM_SOURCE, subject_id, topic_id, st_id, per_st_weight, "manual_subject_split_2026_paper"))

    conn = sqlite3.connect(DB_PATH)
    conn.executemany(
        """INSERT INTO topic_weights (exam_source, subject_id, topic_id, subtopic_id, base_weight, weight_source)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(exam_source, subject_id, topic_id, subtopic_id) DO UPDATE SET
             base_weight = excluded.base_weight, weight_source = excluded.weight_source""",
        rows,
    )
    conn.commit()

    total = conn.execute(
        "SELECT SUM(base_weight) FROM topic_weights WHERE exam_source=?", (EXAM_SOURCE,)
    ).fetchone()[0]
    count = conn.execute(
        "SELECT COUNT(*) FROM topic_weights WHERE exam_source=?", (EXAM_SOURCE,)
    ).fetchone()[0]
    print(f"Seeded {count} rows for exam_source={EXAM_SOURCE!r}, weights sum to {total:.2f} (should be ~100)")
    for subject_id, pct in sorted(SUBJECT_PCT.items(), key=lambda x: -x[1]):
        print(f"  {subject_id}: {pct:.2f}%")
    conn.close()


if __name__ == "__main__":
    main()
