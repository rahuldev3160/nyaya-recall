"""
ChromaDB coverage audit.
Shows chunk counts per subject and flags subjects with no indexed material.
Run: python3 scripts/check_chroma_coverage.py
"""
import os
import json
import sys
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv
import chromadb

load_dotenv(Path(__file__).parent.parent / ".env")

CHROMA_PATH = Path(os.getenv("CHROMA_PATH", "vector_store"))
SYLLABUS_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "syllabus.json"


def main():
    if not CHROMA_PATH.exists():
        print(f"ERROR: vector_store not found at {CHROMA_PATH}")
        sys.exit(1)

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        collection = client.get_collection("upsc_content")
    except Exception:
        print("ERROR: 'upsc_content' collection not found. Run scripts/ingest.py first.")
        sys.exit(1)

    total = collection.count()
    print(f"\nTotal chunks in ChromaDB: {total}\n")

    # Get all metadata — fetch in batches to avoid memory issues
    batch_size = 5000
    subject_counts: Counter = Counter()
    offset = 0
    while True:
        result = collection.get(
            limit=batch_size,
            offset=offset,
            include=["metadatas"],
        )
        metas = result.get("metadatas") or []
        if not metas:
            break
        for m in metas:
            subj = m.get("subject_id") or m.get("subject") or "unknown"
            subject_counts[subj] += 1
        offset += len(metas)
        if len(metas) < batch_size:
            break

    # Load syllabus to know which subjects should exist
    known_subjects = set()
    if SYLLABUS_PATH.exists():
        syllabus = json.loads(SYLLABUS_PATH.read_text())
        for subj in syllabus:
            known_subjects.add(subj.get("id") or subj.get("subject_id") or "")

    print(f"{'Subject':<30} {'Chunks':>8}  {'Status'}")
    print("-" * 55)

    # Print indexed subjects
    for subj, count in sorted(subject_counts.items(), key=lambda x: -x[1]):
        status = "ok" if count >= 50 else "LOW — may produce thin questions"
        print(f"{subj:<30} {count:>8}  {status}")

    # Print missing subjects
    missing = known_subjects - set(subject_counts.keys()) - {""}
    if missing:
        print()
        print("MISSING (no chunks indexed — falling back to Claude training knowledge):")
        for subj in sorted(missing):
            print(f"  {subj:<30}   0  RE-RUN ingest.py for this subject")

    # Summary
    print()
    indexed = len(subject_counts)
    total_subjects = len(known_subjects) if known_subjects else "?"
    print(f"Indexed: {indexed} subjects | Missing: {len(missing)} subjects (of {total_subjects} in syllabus)")

    if missing:
        print("\nTo re-ingest missing subjects:")
        print("  python3 scripts/ingest.py")
        print("  (ensure source PDFs exist under UPSC_CONTENT_PATH for those subjects)")


if __name__ == "__main__":
    main()
