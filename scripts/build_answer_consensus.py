"""
Community consensus answer updater.

Pulls PYQ correct answers from open-source datasets, matches them to existing
pyq_questions rows, and updates correct_answer + answer_source where ≥2 sources agree.

Sources used:
  S1 — Aquib-Nawaz/Questions   (topic-wise JSON with [YYYY] year tags)
  S2 — iaseth/prelimspattern   (year-wise JSON, q_number + answer keyed)

Matching strategy (in priority order):
  1. Exact question_hash match (SHA256 of year:text[:200], same formula as ingest_pyq.py)
  2. Normalised text match (lowercase + collapse whitespace + strip punctuation, prefix 200 chars)

answer_source values written:
  community_consensus  — ≥2 sources agree on the same answer
  community_single     — exactly 1 source has an answer (AI answer absent or differs)
  community_validated  — our existing ai_inferred answer matched by ≥1 community source
  ai_inferred          — no community match found (unchanged)
  unverified           — no answer anywhere (unchanged)

Usage:
  cd scripts && python build_answer_consensus.py            # dry run (safe)
  cd scripts && python build_answer_consensus.py --apply    # write to DB
  cd scripts && python build_answer_consensus.py --apply --verbose  # row-by-row log
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "upsc.db"

# Source repos
_AQUIB_URL  = "https://github.com/Aquib-Nawaz/Questions.git"
_AQUIB_DIR  = Path("/tmp/aquib_nawaz_questions")
_AQUIB_PYQ  = _AQUIB_DIR / "json_pyq"

_IASETH_URL = "https://github.com/iaseth/prelimspattern.git"
_IASETH_DIR = Path("/tmp/iaseth_prelimspattern")


# ---------------------------------------------------------------------------
# Normalisation and hashing
# ---------------------------------------------------------------------------

def _qhash(year: int, text: str) -> str:
    return hashlib.sha256(f"{year}:{text[:200]}".encode()).hexdigest()[:20]


def _norm(text: str) -> str:
    """Lowercase, strip non-alphanum, collapse whitespace. Used for fuzzy matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]


# ---------------------------------------------------------------------------
# Repo fetch
# ---------------------------------------------------------------------------

def _clone_or_pull(url: str, dest: Path, name: str) -> bool:
    if dest.exists():
        r = subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"],
                           capture_output=True, text=True)
        print(f"  [{name}] pull: {r.stdout.strip() or r.stderr.strip()}")
    else:
        r = subprocess.run(["git", "clone", "--depth", "1", url, str(dest)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  [{name}] clone FAILED: {r.stderr.strip()}")
            return False
        print(f"  [{name}] cloned to {dest}")
    return True


# ---------------------------------------------------------------------------
# Source parsers — each returns list of {year, norm_key, qhash, answer, source}
# ---------------------------------------------------------------------------

def _load_aquib() -> list[dict]:
    """Aquib-Nawaz/Questions: topic-wise JSON, year in [YYYY] tag."""
    records: list[dict] = []
    if not _AQUIB_PYQ.exists():
        print("  [Aquib-Nawaz] json_pyq dir not found — skipping")
        return records

    for jf in sorted(_AQUIB_PYQ.glob("*.json")):
        try:
            qs = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(qs, list):
            continue
        for q in qs:
            raw = q.get("question_text", "").strip()
            answer = (q.get("correct_answer") or "").strip().lower()
            if not answer:
                continue
            m = re.search(r"\[(\d{4})(?:[^\]]*)\]", raw)
            if not m:
                continue
            year = int(m.group(1))
            if not (2009 <= year <= 2025):
                continue
            clean = re.sub(r"\s*\[\d{4}[^\]]*\]\s*", " ", raw).strip()
            records.append({
                "year":     year,
                "norm_key": _norm(clean),
                "qhash":    _qhash(year, clean),
                "answer":   answer,
                "source":   "Aquib-Nawaz",
            })
    print(f"  [Aquib-Nawaz] loaded {len(records)} questions with answers")
    return records


def _load_iaseth() -> list[dict]:
    """
    iaseth/prelimspattern: the repo's data structure varies. We look for:
      - JSON files named YYYY.json or similar
      - Each with a list of questions: {question, options:{a,b,c,d}, answer}
        or {id, question, ...}
    """
    records: list[dict] = []
    if not _IASETH_DIR.exists():
        print("  [iaseth] dir not found — skipping")
        return records

    # Discover JSON files recursively
    json_files = list(_IASETH_DIR.rglob("*.json"))
    print(f"  [iaseth] found {len(json_files)} JSON files")

    for jf in json_files:
        # Try to infer year from filename (e.g. 2022.json, prelims_2022.json)
        m = re.search(r"(20\d{2})", jf.stem)
        year_from_name = int(m.group(1)) if m else None

        try:
            raw = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue

        # iaseth format can be a list or a dict with 'questions' key
        if isinstance(raw, dict):
            year_from_data = raw.get("year") or raw.get("Year")
            qs = raw.get("questions") or raw.get("Questions") or []
        elif isinstance(raw, list):
            year_from_data = None
            qs = raw
        else:
            continue

        year = year_from_data or year_from_name
        if not year or not (2009 <= int(year) <= 2025):
            continue
        year = int(year)

        for q in qs:
            if not isinstance(q, dict):
                continue
            # Question text — various keys
            text = (q.get("question") or q.get("question_text") or
                    q.get("Question") or q.get("text") or "").strip()
            if not text:
                continue
            # Answer — various keys: 'answer', 'correct_answer', 'Answer'
            answer = (q.get("answer") or q.get("correct_answer") or
                      q.get("Answer") or q.get("correct") or "")
            if not answer:
                continue
            answer = str(answer).strip().lower()
            # Normalise: accept a/b/c/d or A/B/C/D or 1/2/3/4
            if answer in ("1",): answer = "a"
            if answer in ("2",): answer = "b"
            if answer in ("3",): answer = "c"
            if answer in ("4",): answer = "d"
            if answer not in ("a", "b", "c", "d"):
                continue

            records.append({
                "year":     year,
                "norm_key": _norm(text),
                "qhash":    _qhash(year, text),
                "answer":   answer,
                "source":   "iaseth",
            })

    print(f"  [iaseth] loaded {len(records)} questions with answers")
    return records


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _load_db(con: sqlite3.Connection) -> tuple[dict, dict]:
    """
    Returns:
      hash_idx  : {qhash: row_dict}
      norm_idx  : {(year, norm_key): row_dict}
    """
    rows = con.execute(
        "SELECT id, year, question_text, correct_answer, answer_source, question_hash "
        "FROM pyq_questions WHERE year > 0"
    ).fetchall()
    hash_idx: dict[str, dict] = {}
    norm_idx: dict[tuple, dict] = {}
    for r in rows:
        row = dict(zip(["id", "year", "question_text", "correct_answer", "answer_source", "question_hash"], r))
        if row["question_hash"]:
            hash_idx[row["question_hash"]] = row
        key = (row["year"], _norm(row["question_text"]))
        norm_idx[key] = row
    return hash_idx, norm_idx


# ---------------------------------------------------------------------------
# Consensus engine
# ---------------------------------------------------------------------------

def _match_row(rec: dict, hash_idx: dict, norm_idx: dict) -> dict | None:
    """Find the best DB row for a source record."""
    # 1. Exact hash
    r = hash_idx.get(rec["qhash"])
    if r:
        return r
    # 2. Normalised text
    key = (rec["year"], rec["norm_key"])
    return norm_idx.get(key)


def build_consensus(sources: list[list[dict]], hash_idx: dict, norm_idx: dict,
                    verbose: bool = False) -> dict[int, dict]:
    """
    Returns {db_id: {answer, source_label, votes, db_row}}
    Only rows where we're confident enough to update.
    """
    # Aggregate votes per DB row: {id: {answer: [sources]}}
    votes: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    row_map: dict[int, dict] = {}

    for source_records in sources:
        for rec in source_records:
            db_row = _match_row(rec, hash_idx, norm_idx)
            if db_row is None:
                continue
            db_id = db_row["id"]
            votes[db_id][rec["answer"]].append(rec["source"])
            row_map[db_id] = db_row

    updates: dict[int, dict] = {}
    for db_id, answer_votes in votes.items():
        db_row = row_map[db_id]
        existing_answer = (db_row["correct_answer"] or "").strip().lower()
        existing_source = db_row["answer_source"] or "ai_inferred"

        # Find the answer with most votes
        best_answer = max(answer_votes, key=lambda a: len(answer_votes[a]))
        best_sources = answer_votes[best_answer]
        n_sources = len(best_sources)
        all_agree = len(answer_votes) == 1  # all sources gave same answer

        if n_sources >= 2 and all_agree:
            new_source = "community_consensus"
        elif n_sources >= 1 and existing_source == "unverified":
            new_source = "community_single"
        elif n_sources >= 1 and existing_answer == best_answer:
            new_source = "community_validated"
        elif n_sources >= 1 and existing_source == "ai_inferred" and existing_answer != best_answer:
            # Community contradicts AI — take community but flag as single
            new_source = "community_single"
        else:
            continue  # nothing useful to write

        # Skip if nothing changes
        if existing_answer == best_answer and existing_source == new_source:
            continue

        updates[db_id] = {
            "answer":     best_answer,
            "new_source": new_source,
            "old_answer": existing_answer or None,
            "old_source": existing_source,
            "sources":    best_sources,
            "n_votes":    n_sources,
            "db_row":     db_row,
        }
        if verbose:
            print(f"  Q{db_id} ({db_row['year']}) {existing_answer!r}→{best_answer!r} "
                  f"[{existing_source}→{new_source}] via {best_sources}")

    return updates


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Community consensus answer updater")
    parser.add_argument("--apply",   action="store_true", help="Write updates to DB (default: dry run)")
    parser.add_argument("--verbose", action="store_true", help="Print per-row changes")
    args = parser.parse_args()

    print("\n" + ("━" * 60))
    print(f"  Community Answer Consensus {'[DRY RUN]' if not args.apply else '[APPLYING]'}")
    print("━" * 60)

    # 1. Fetch sources
    print("\n▶ Fetching source repos…")
    _clone_or_pull(_AQUIB_URL,  _AQUIB_DIR,  "Aquib-Nawaz")
    _clone_or_pull(_IASETH_URL, _IASETH_DIR, "iaseth")

    # 2. Load records
    print("\n▶ Parsing sources…")
    aquib   = _load_aquib()
    iaseth  = _load_iaseth()
    all_sources = [aquib, iaseth]
    total_source_records = sum(len(s) for s in all_sources)
    print(f"\n  Total source records with answers: {total_source_records}")

    # 3. Load DB
    print("\n▶ Loading DB index…")
    con = sqlite3.connect(DB_PATH)
    hash_idx, norm_idx = _load_db(con)
    print(f"  DB rows indexed: {len(hash_idx)} (by hash), {len(norm_idx)} (by norm text)")

    # 4. Consensus
    print("\n▶ Computing consensus…")
    if args.verbose:
        print()
    updates = build_consensus(all_sources, hash_idx, norm_idx, verbose=args.verbose)

    # 5. Stats breakdown
    by_new_source: dict[str, int] = defaultdict(int)
    answer_changed = 0
    for u in updates.values():
        by_new_source[u["new_source"]] += 1
        if u["old_answer"] and u["old_answer"] != u["answer"]:
            answer_changed += 1

    print(f"\n{'━'*60}")
    print(f"  Rows to update: {len(updates)}")
    for src, n in sorted(by_new_source.items()):
        print(f"    {src:<28} {n:>5}")
    print(f"  Answer changes (AI → community): {answer_changed}")
    print(f"  Rows untouched (no match):        {len(hash_idx) - len(updates)}")
    print("━" * 60)

    # 6. Year breakdown
    year_stats: dict[int, dict] = defaultdict(lambda: {"matched": 0, "consensus": 0, "validated": 0})
    for u in updates.values():
        yr = u["db_row"]["year"]
        year_stats[yr]["matched"] += 1
        if u["new_source"] == "community_consensus":
            year_stats[yr]["consensus"] += 1
        elif u["new_source"] == "community_validated":
            year_stats[yr]["validated"] += 1

    print(f"\n  {'Year':<6} {'Matched':>8} {'Consensus':>10} {'Validated':>10}")
    print(f"  {'─'*40}")
    for yr in sorted(year_stats):
        s = year_stats[yr]
        print(f"  {yr:<6} {s['matched']:>8} {s['consensus']:>10} {s['validated']:>10}")

    if not args.apply:
        print(f"\n  [DRY RUN] Nothing written. Re-run with --apply to commit.\n")
        con.close()
        return

    # 7. Apply
    print(f"\n▶ Writing {len(updates)} updates…")
    updated = 0
    for db_id, u in updates.items():
        con.execute(
            "UPDATE pyq_questions SET correct_answer=?, answer_source=? WHERE id=?",
            (u["answer"], u["new_source"], db_id),
        )
        updated += 1

    con.commit()
    con.close()
    print(f"  Done. {updated} rows updated.\n")

    # Summary of remaining gaps
    con2 = sqlite3.connect(DB_PATH)
    row = con2.execute(
        "SELECT answer_source, COUNT(*) FROM pyq_questions WHERE year > 0 GROUP BY answer_source"
    ).fetchall()
    con2.close()
    print("  Final answer_source distribution:")
    for src, n in sorted(row, key=lambda r: -r[1]):
        print(f"    {src or 'NULL':<28} {n:>5}")
    print()


if __name__ == "__main__":
    main()
