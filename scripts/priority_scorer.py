"""Weighted PYQ priority scoring. decay = 0.9^(current_year - year).

Normalisation note
------------------
PYQ questions in `pyq_questions` were tagged by Claude during ingestion with
free-text subtopic descriptors (e.g. ``directive_principles``, ``rbi_operations``)
that do NOT directly match the 205 canonical subtopic IDs in ``data/syllabus.json``.
Only 14 of ~979 PYQ subtopic IDs match directly.

Fix (Option B — fuzzy normalisation):
  Before accumulating scores, map each PYQ subtopic_id to the best-matching
  syllabus subtopic_id using subject-scoped token-overlap.  Matches below
  FUZZY_THRESHOLD are discarded (treated as unrecognised PYQ tags).

  Coverage: ~30 % of questions get matched this way.  The remaining ~70 %
  use highly specific one-off descriptors that share no tokens with the 205
  syllabus IDs.  For full coverage run ``scripts/retag_pyq_subtopics.py``
  (one-time, ~$0.05 Haiku) which re-classifies every PYQ question against
  the syllabus and updates the DB in-place.
"""
from __future__ import annotations
import sqlite3
import json
import os
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")
SYLLABUS_PATH = Path(os.getenv("PROJECT_PATH", str(Path(__file__).parent.parent))) / "data" / "syllabus.json"
CURRENT_YEAR = 2026
DECAY = 0.9
FUZZY_THRESHOLD = 0.5   # minimum token-overlap score to accept a match


# ---------------------------------------------------------------------------
# Syllabus helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_syllabus_map() -> dict[str, list[str]]:
    """Returns {subject_id: [canonical_subtopic_id, ...]}."""
    try:
        syllabus = json.loads(SYLLABUS_PATH.read_text())
    except Exception:
        return {}
    result: dict[str, list[str]] = {}
    all_ids: list[str] = []
    for subj in syllabus.get("subjects", []):
        sids = [
            st["id"]
            for topic in subj.get("topics", [])
            for st in topic.get("subtopics", [])
        ]
        result[subj["id"]] = sids
        all_ids.extend(sids)
    # Sentinel key "_all" holds every subtopic across all subjects
    result["_all"] = all_ids
    return result


def _token_overlap(a: str, b: str) -> float:
    """Fraction of tokens in the shorter string that appear in the longer string."""
    ta = set(a.split("_"))
    tb = set(b.split("_"))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _normalise(pyq_subtopic_id: str, subject_id: str | None) -> str | None:
    """Map a PYQ subtopic_id to the nearest canonical syllabus subtopic_id.

    Returns ``None`` if no match exceeds ``FUZZY_THRESHOLD``.
    """
    smap = _load_syllabus_map()
    if not smap:
        return None

    # Direct match — fastest path
    all_ids: list[str] = smap.get("_all", [])
    if pyq_subtopic_id in set(all_ids):
        return pyq_subtopic_id

    # Subject-scoped candidates first, fall back to all subjects
    candidates = smap.get(subject_id or "", all_ids) or all_ids

    best_id, best_score = max(
        ((c, _token_overlap(pyq_subtopic_id, c)) for c in candidates),
        key=lambda x: x[1],
        default=(None, 0.0),
    )
    if best_score >= FUZZY_THRESHOLD:
        return best_id

    # Retry across all subjects if subject-scoped failed
    if candidates is not all_ids:
        best_id2, best_score2 = max(
            ((c, _token_overlap(pyq_subtopic_id, c)) for c in all_ids),
            key=lambda x: x[1],
            default=(None, 0.0),
        )
        if best_score2 >= FUZZY_THRESHOLD:
            return best_id2

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_all_priorities() -> dict[str, float]:
    """Returns {canonical_subtopic_id: priority_score} for subtopics with PYQ data.

    PYQ subtopic IDs are normalised to syllabus IDs before accumulation so the
    returned keys match the IDs used in ``data/syllabus.json``.
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT subtopic_id, subject_id, year FROM pyq_questions WHERE subtopic_id IS NOT NULL"
    ).fetchall()
    con.close()

    scores: dict[str, float] = {}
    for row in rows:
        canonical = _normalise(row["subtopic_id"], row["subject_id"])
        if canonical is None:
            continue
        weight = DECAY ** (CURRENT_YEAR - row["year"])
        scores[canonical] = scores.get(canonical, 0.0) + weight

    return scores


def rank_subtopics(subject_id: str | None = None) -> list[dict]:
    """Return subtopics sorted by priority descending, optionally filtered by subject."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    query = """
        SELECT subtopic_id, subject_id, topic_id, year
        FROM pyq_questions WHERE subtopic_id IS NOT NULL
    """
    params: list = []
    if subject_id:
        query += " AND subject_id = ?"
        params.append(subject_id)

    rows = con.execute(query, params).fetchall()
    con.close()

    scores: dict[str, dict] = {}
    for row in rows:
        canonical = _normalise(row["subtopic_id"], row["subject_id"])
        if canonical is None:
            continue
        if canonical not in scores:
            scores[canonical] = {
                "subtopic_id": canonical,
                "subject_id": row["subject_id"],
                "topic_id": row["topic_id"],
                "priority_score": 0.0,
            }
        scores[canonical]["priority_score"] += DECAY ** (CURRENT_YEAR - row["year"])

    return sorted(scores.values(), key=lambda x: x["priority_score"], reverse=True)
