from __future__ import annotations
import hashlib
import os
import sys
import json
import uuid
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import quote
from fastapi import APIRouter, HTTPException
import anthropic
import chromadb
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

router = APIRouter()

DB_PATH = os.getenv("DB_PATH", "data/upsc.db")
CHROMA_PATH = os.getenv("CHROMA_PATH", "vector_store")
PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"
_SYLLABUS_PATH = Path(__file__).parent.parent.parent / "data" / "syllabus.json"
_NOTES_CACHE_PATH = Path(__file__).parent.parent.parent / "cache" / "explanations.json"
_PLAN_PATH = Path(os.getenv("PLAN_PATH", "data/study_plan.json"))
_SUBJECT_ALIAS = {"history": "history_amac"}

# How many Chroma chunks to retrieve for notes synthesis.
_NOTES_QUERY_K = 14

_syllabus_cache: dict | None = None


def _load_syllabus() -> dict:
    global _syllabus_cache
    if _syllabus_cache is None:
        try:
            _syllabus_cache = json.loads(_SYLLABUS_PATH.read_text())
        except Exception:
            _syllabus_cache = {}
    return _syllabus_cache


def _get_subtopic_dimensions(subject_id: str, subtopic_id: str) -> str:
    """Return a formatted string of available dimension ids + names for a subtopic.

    Reads from the 'dimensions' key in syllabus.json (populated by Phase 1 script).
    Returns a plain-text list suitable for prompt injection as {{available_dimensions}}.
    Falls back to a generic placeholder if dimensions haven't been generated yet.

    # TODO (Phase 3): once session_answers.dimension_id column exists, also pass
    # dimensions_covered_this_session so Claude avoids re-testing them.
    """
    if not subtopic_id:
        return "No dimensions available — subtopic not specified."
    sid = _SUBJECT_ALIAS.get(subject_id, subject_id)
    syllabus = _load_syllabus()
    for subj in syllabus.get("subjects", []):
        if subj["id"] != sid:
            continue
        for topic in subj.get("topics", []):
            for st in topic.get("subtopics", []):
                if st["id"] == subtopic_id:
                    dims = st.get("dimensions", [])
                    if not dims:
                        return (
                            f"Dimensions not yet generated for {subtopic_id}. "
                            "Use your best judgment to identify the main testable angles."
                        )
                    lines = [f"- {d['id']}: {d['name']}" for d in dims]
                    return "\n".join(lines)
    return "Subtopic not found in syllabus — use your best judgment for dimension_id."


def get_canonical_topic_id(subject_id: str, subtopic_id: str) -> str | None:
    """Look up topic_id from syllabus.json for a given subject+subtopic pair."""
    sid = _SUBJECT_ALIAS.get(subject_id, subject_id)
    syllabus = _load_syllabus()
    for subj in syllabus.get("subjects", []):
        if subj["id"] != sid:
            continue
        for topic in subj.get("topics", []):
            for st in topic.get("subtopics", []):
                if st["id"] == subtopic_id:
                    return topic["id"]
    return None

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
chroma = chromadb.PersistentClient(path=CHROMA_PATH)


def _get_subject_subtopics(subject_id: str) -> list[str]:
    """Return all subtopic IDs for a subject from syllabus.json."""
    sid = _SUBJECT_ALIAS.get(subject_id, subject_id)
    try:
        syllabus = json.loads(_SYLLABUS_PATH.read_text())
        for subj in syllabus.get("subjects", []):
            if subj["id"] == sid:
                return [
                    st["id"]
                    for topic in subj.get("topics", [])
                    for st in topic.get("subtopics", [])
                ]
    except Exception:
        pass
    return []


def _get_tested_subtopics_for_subject(subject_id: str) -> set[str]:
    """Return subtopic_ids already in subtopic_scores for this subject."""
    sid = _SUBJECT_ALIAS.get(subject_id, subject_id)
    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            "SELECT subtopic_id FROM subtopic_scores WHERE user_id='user_1' AND subject_id=?",
            (sid,),
        ).fetchall()
        con.close()
        return {r[0] for r in rows if r[0]}
    except Exception:
        return set()


def _fetch_recent_question_texts(subject_id: str, days: int = 30, limit: int = 40) -> list[str]:
    """Return up to `limit` question texts seen for this subject in the last `days` days."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            """
            SELECT sa.question_text
            FROM session_answers sa
            JOIN quiz_sessions qs ON sa.session_id = qs.id
            WHERE sa.subject_id = ?
              AND sa.question_text IS NOT NULL
              AND sa.question_text != ''
              AND qs.start_time >= ?
            ORDER BY qs.start_time DESC
            LIMIT ?
            """,
            (subject_id, since, limit),
        ).fetchall()
        con.close()
        return [r[0] for r in rows if r[0]]
    except Exception:
        return []


def _build_recent_questions_block(subject_id: str) -> str:
    """Build the {{recent_questions_block}} prompt injection string."""
    texts = _fetch_recent_question_texts(subject_id)
    if not texts:
        return ""
    lines = ["IMPORTANT — Avoid repeating these questions the student has already seen:"]
    for i, text in enumerate(texts, 1):
        lines.append(f"{i}. {text[:100]}")
    lines.append(
        "Generate completely new questions on different facts/angles, "
        "even if the subtopic overlaps."
    )
    return "\n".join(lines)


def _get_quiz_intelligence(subject_id: str, subtopic_id: str | None = None) -> dict:
    """
    Queries DB for context that makes question generation smarter.
    Returns:
    {
      "excluded_hashes": list[str],        # question_hash seen in last 30 days for this subject
      "wrong_concepts": list[str],         # subtopic_ids where user got answers wrong recently
      "question_texts_seen": list[str],    # last 20 question_texts (for semantic dedup)
      "user_notes_context": str,           # confusion/mnemonic notes for this subtopic (empty = neutral)
    }
    If no history exists, return empty lists/strings (neutral signal).
    """
    result: dict = {
        "excluded_hashes": [],
        "wrong_concepts": [],
        "question_texts_seen": [],
        "user_notes_context": "",
    }
    try:
        con = sqlite3.connect(DB_PATH)

        # excluded_hashes: question_hash seen in last 30 days for this subject
        try:
            rows = con.execute(
                """SELECT DISTINCT question_hash FROM session_answers
                   WHERE subject_id=? AND created_at >= date('now','-30 days')
                   AND question_hash IS NOT NULL""",
                (subject_id,),
            ).fetchall()
            result["excluded_hashes"] = [r[0] for r in rows if r[0]]
        except sqlite3.OperationalError:
            pass

        # wrong_concepts: subtopic_ids with wrong answers in last 30 days
        try:
            rows = con.execute(
                """SELECT DISTINCT subtopic_id FROM session_answers
                   WHERE subject_id=? AND is_correct=0
                   AND (skipped IS NULL OR skipped=0)
                   AND created_at >= date('now','-30 days')
                   AND subtopic_id IS NOT NULL""",
                (subject_id,),
            ).fetchall()
            result["wrong_concepts"] = [r[0] for r in rows if r[0]]
        except sqlite3.OperationalError:
            pass

        # question_texts_seen: last 20 question_text values for this subject
        try:
            rows = con.execute(
                """SELECT question_text FROM session_answers
                   WHERE subject_id=? AND question_text IS NOT NULL
                   ORDER BY created_at DESC LIMIT 20""",
                (subject_id,),
            ).fetchall()
            result["question_texts_seen"] = [r[0] for r in rows if r[0]]
        except sqlite3.OperationalError:
            pass

        # user_notes_context: confusion/mnemonic for this subtopic
        if subtopic_id:
            try:
                row = con.execute(
                    """SELECT confusion, mnemonic FROM session_user_notes
                       WHERE subtopic_id=? AND user_id='user_1'
                       ORDER BY updated_at DESC LIMIT 1""",
                    (subtopic_id,),
                ).fetchone()
                if row:
                    parts = []
                    if row[0]:
                        parts.append(f"User confusion: {row[0]}")
                    if row[1]:
                        parts.append(f"User mnemonic: {row[1]}")
                    result["user_notes_context"] = "\n".join(parts)
            except sqlite3.OperationalError:
                # session_user_notes may not exist yet
                pass

        con.close()
    except Exception:
        pass

    return result


def _get_spillover_subtopics(subject_id: str, primary_subtopic: str, n: int = 2) -> str:
    """
    Read data/study_plan.json and find untested subtopics for subject_id
    that aren't primary_subtopic. Returns a formatted spillover instruction string,
    or "" if none found or plan doesn't exist.
    """
    try:
        plan_path = _PLAN_PATH
        if not plan_path.is_absolute():
            plan_path = Path(__file__).parent.parent.parent / plan_path
        if not plan_path.exists():
            return ""

        plan = json.loads(plan_path.read_text())
        today_sessions = plan.get("today", {}).get("sessions", [])

        tested = _get_tested_subtopics_for_subject(subject_id)

        spillover_candidates: list[str] = []
        for session in today_sessions:
            if session.get("subject_id") != subject_id:
                continue
            st = session.get("subtopic_id")
            if st and st != primary_subtopic and st not in tested:
                spillover_candidates.append(st)

        if not spillover_candidates:
            return ""

        selected = spillover_candidates[:n]
        return (
            f"Spillover: if all distinct question dimensions for the primary subtopic "
            f"are exhausted before reaching {{num_q}}, generate remaining questions on: "
            f"{', '.join(selected)}"
        )
    except Exception:
        return ""


def _allocate_questions_across_subtopics(subject_id: str, num_q: int) -> list[dict]:
    """
    Returns priority-ordered list: [{subtopic_id, num_questions, weight, is_tested}].

    Ordering rule:
      1. Untested subtopics first (higher diagnostic value).
      2. Within each group, sorted by PYQ priority weight descending.

    Question counts are proportional to PYQ weight, minimum 1 per subtopic,
    covering at most num_q subtopics so every question maps to a unique subtopic.
    """
    all_subtopics = _get_subject_subtopics(subject_id)
    if not all_subtopics:
        return []

    try:
        from priority_scorer import compute_all_priorities
        pyq_weights = compute_all_priorities()
    except Exception:
        pyq_weights = {}

    tested = _get_tested_subtopics_for_subject(subject_id)

    # Sort: untested before tested, then by PYQ weight descending within each group
    ordered = sorted(
        all_subtopics,
        key=lambda st: (st in tested, -pyq_weights.get(st, 1.0)),
    )

    # Cover at most num_q subtopics (floor is 1 question each)
    n_cover = min(num_q, len(ordered))
    selected = ordered[:n_cover]
    raw_w = [max(pyq_weights.get(st, 1.0), 0.5) for st in selected]
    total_w = sum(raw_w)

    # Proportional allocation
    allocs = [max(1, int(round(num_q * w / total_w))) for w in raw_w]

    # Fix rounding so total == num_q exactly
    diff = num_q - sum(allocs)
    i = 0
    while diff != 0:
        step = 1 if diff > 0 else -1
        if step < 0 and allocs[i % n_cover] <= 1:
            i += 1
            continue
        allocs[i % n_cover] += step
        diff -= step
        i += 1

    return [
        {
            "subtopic_id": st,
            "num_questions": allocs[idx],
            "weight": round(raw_w[idx], 2),
            "is_tested": st in tested,
        }
        for idx, st in enumerate(selected)
    ]


def get_collection():
    return chroma.get_or_create_collection("upsc_content")


# ── quiz_session_subtopics table helpers ──────────────────────────────────────

def _ensure_session_subtopics_table(con: sqlite3.Connection) -> None:
    """Create additive quiz_session_subtopics table — never ALTERs existing tables."""
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_session_subtopics (
            session_id   TEXT NOT NULL,
            subtopic_ids TEXT NOT NULL,
            PRIMARY KEY (session_id)
        )
        """
    )
    con.commit()


def _store_session_subtopics(session_id: str, subtopic_ids: list[str]) -> None:
    """Persist the full subtopic_ids list for a session in the new additive table."""
    con = sqlite3.connect(DB_PATH)
    _ensure_session_subtopics_table(con)
    con.execute(
        "INSERT OR REPLACE INTO quiz_session_subtopics (session_id, subtopic_ids) VALUES (?, ?)",
        (session_id, json.dumps(subtopic_ids)),
    )
    con.commit()
    con.close()


# ── PYQ weight helpers for explicit subtopic_ids lists ────────────────────────

def _get_pyq_weights_for_subtopics(subtopic_ids: list[str]) -> dict[str, float]:
    """Return {subtopic_id: pyq_weight} for the given list. Falls back to 1.0 if missing."""
    try:
        from priority_scorer import compute_all_priorities
        all_weights = compute_all_priorities()
        return {st: all_weights.get(st, 1.0) for st in subtopic_ids}
    except Exception:
        return {st: 1.0 for st in subtopic_ids}


def _allocate_questions_for_subtopic_ids(
    subtopic_ids: list[str], num_q: int
) -> list[dict]:
    """
    Proportional question allocation for an explicit list of subtopic_ids.
    Returns [{subtopic_id, num_questions, weight}].
    Weights from PYQ priority; equal allocation if weights unavailable.
    Ensures total == num_q exactly (rounding correction applied).
    """
    if not subtopic_ids:
        return []
    weights_map = _get_pyq_weights_for_subtopics(subtopic_ids)
    raw_w = [max(weights_map.get(st, 1.0), 0.5) for st in subtopic_ids]
    total_w = sum(raw_w)
    allocs = [max(1, int(round(num_q * w / total_w))) for w in raw_w]

    # Fix rounding so total == num_q
    diff = num_q - sum(allocs)
    n = len(subtopic_ids)
    i = 0
    while diff != 0:
        step = 1 if diff > 0 else -1
        if step < 0 and allocs[i % n] <= 1:
            i += 1
            continue
        allocs[i % n] += step
        diff -= step
        i += 1

    return [
        {
            "subtopic_id": st,
            "num_questions": allocs[idx],
            "weight": round(raw_w[idx], 2),
        }
        for idx, st in enumerate(subtopic_ids)
    ]


# ── Chunk count scaling ───────────────────────────────────────────────────────

def _chunk_k(q_per_subtopic: int) -> int:
    """Scale ChromaDB chunks with question count: more questions → richer context.
    Formula: min(8, max(3, q + 2))
    1Q→3, 3Q→5, 5Q→7, 6Q+→8 (capped)
    """
    return min(8, max(3, q_per_subtopic + 2))


# ── Multi-subtopic chunk fetching ─────────────────────────────────────────────

def fetch_chunks_merged(
    subject_id: str, subtopic_ids: list[str], k_per_subtopic: int = 3
) -> tuple[str, str]:
    """
    Fetch ChromaDB chunks for each subtopic in subtopic_ids.
    Returns (subtopic_allocation_str, content_chunks_str) ready for prompt injection.
    Chunks are labelled by subtopic so Sonnet can assign correct subtopic_id per question.
    """
    allocation = _allocate_questions_for_subtopic_ids(subtopic_ids, 10)  # placeholder n
    alloc_map = {a["subtopic_id"]: a for a in allocation}

    alloc_lines: list[str] = []
    chunk_sections: list[str] = []

    for st_id in subtopic_ids:
        st_chunks = fetch_chunks(subject_id, st_id, k=k_per_subtopic)
        if not st_chunks:
            st_chunks = [
                f"Standard UPSC Prelims content on {subject_id}: "
                f"{st_id.replace('_', ' ')}. Generate from canonical syllabus knowledge."
            ]
        weight = alloc_map[st_id]["weight"] if st_id in alloc_map else 1.0
        alloc_lines.append(f"  {st_id}  (PYQ weight {weight})")
        header = f"[{st_id}]"
        chunk_sections.append(header + "\n" + "\n---\n".join(st_chunks))

    subtopic_allocation_str = (
        "Subtopics covered in this merged session:\n" + "\n".join(alloc_lines)
    )
    content_chunks_str = "\n\n".join(chunk_sections)
    return subtopic_allocation_str, content_chunks_str


def _build_merged_subtopic_allocation_str(
    allocation: list[dict],
) -> str:
    """Build the subtopic_allocation block for an explicit multi-subtopic session."""
    lines: list[str] = [
        "Subtopic coverage — generate EXACTLY these counts "
        "(each question's subtopic_id must equal the subtopic_id listed here):"
    ]
    for item in allocation:
        st_id = item["subtopic_id"]
        n = item["num_questions"]
        w = item["weight"]
        lines.append(f"  {st_id}: {n} question{'s' if n > 1 else ''}  (PYQ weight {w})")
    return "\n".join(lines)


def _build_merged_content_chunks_str(
    subject_id: str, allocation: list[dict], k_per_subtopic: int | None = None
) -> str:
    """Fetch and merge ChromaDB chunks for all subtopics in allocation list."""
    sections: list[str] = []
    for item in allocation:
        st_id = item["subtopic_id"]
        n = item["num_questions"]
        k = k_per_subtopic if k_per_subtopic is not None else _chunk_k(n)
        st_chunks = fetch_chunks(subject_id, st_id, k=k)
        if not st_chunks:
            st_chunks = [
                f"Standard UPSC Prelims content on {subject_id}: "
                f"{st_id.replace('_', ' ')}. Generate from canonical syllabus knowledge."
            ]
        header = f"[{st_id}  —  {n} question{'s' if n > 1 else ''}]"
        sections.append(header + "\n" + "\n---\n".join(st_chunks))
    return "\n\n".join(sections)


# ── Cross-subtopic notes helpers ──────────────────────────────────────────────

def _build_cross_subtopic_prompt_section(subtopic_ids: list[str]) -> str:
    """Return the Cross-Subtopic Linkages section instruction for the notes prompt."""
    if len(subtopic_ids) <= 1:
        return ""
    names = ", ".join(st.replace("_", " ") for st in subtopic_ids)
    return (
        "## Cross-Subtopic Linkages\n"
        f"You are generating notes for a MERGED session covering: {names}.\n"
        "Identify 2–3 concrete conceptual bridges between these subtopics. "
        "For each bridge: (1) name the linkage, (2) explain why both subtopics connect, "
        "and (3) give a 1-sentence example of how UPSC tests this connection."
    )


def _notes_cache_key_multi(subtopic_ids: list[str], chunk_texts: list[str]) -> str:
    content = "|".join(subtopic_ids) + "|" + "|".join(chunk_texts)
    return "notes_multi:" + hashlib.sha256(content.encode()).hexdigest()[:20]


def synthesize_notes_multi_cached(
    subject_id: str,
    subtopic_ids: list[str],
) -> str:
    """
    Generate merged revision notes for a list of subtopics (max 4).
    Fetches chunks for each subtopic, builds merged content, injects Cross-Subtopic Linkages.
    Cached by subtopic_ids list + chunk content hash.
    """
    if not subtopic_ids:
        return ""

    # Single subtopic — delegate to existing cached function
    if len(subtopic_ids) == 1:
        rows = fetch_chunks_with_meta(subject_id, subtopic_ids[0], k=_NOTES_QUERY_K)
        return synthesize_notes_cached(rows, subtopic_ids[0], subject_id)

    # Gather chunks for all subtopics (fewer per subtopic to keep prompt size bounded)
    k_each = max(4, _NOTES_QUERY_K // len(subtopic_ids))
    all_rows: list[dict[str, Any]] = []
    chunk_sections: list[str] = []
    for st_id in subtopic_ids:
        rows = fetch_chunks_with_meta(subject_id, st_id, k=k_each)
        all_rows.extend(rows)
        texts = [r["text"] for r in rows]
        if texts:
            chunk_sections.append(f"[{st_id}]\n" + "\n---\n".join(texts))
        else:
            stub = (
                f"Standard UPSC Prelims content on {subject_id}: "
                f"{st_id.replace('_', ' ')}. Generate from canonical syllabus knowledge."
            )
            chunk_sections.append(f"[{st_id}]\n" + stub)

    all_chunk_texts = [r["text"] for r in all_rows]
    cache_key = _notes_cache_key_multi(subtopic_ids, all_chunk_texts)

    cache: dict = {}
    if _NOTES_CACHE_PATH.exists():
        try:
            cache = json.loads(_NOTES_CACHE_PATH.read_text())
        except Exception:
            pass

    if cache_key in cache:
        return cache[cache_key]

    # Build and call the notes prompt with multi-subtopic variables
    prompt_template = (PROMPT_DIR / "session_notes.txt").read_text()
    subtopics_list = ", ".join(st.replace("_", " ") for st in subtopic_ids)
    cross_section = _build_cross_subtopic_prompt_section(subtopic_ids)
    merged_chunks = "\n\n".join(chunk_sections)

    prompt = (
        prompt_template
        .replace("{{subject_name}}", subject_id)
        .replace("{{subtopics_list}}", subtopics_list)
        .replace("{{subtopic_name}}", subtopics_list)  # backward compat placeholder
        .replace("{{content_chunks}}", merged_chunks)
        .replace("{{cross_subtopic_section}}", cross_section)
    )

    resp = client.messages.create(
        model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
        max_tokens=1400,
        messages=[{"role": "user", "content": prompt}],
    )
    synth_md = resp.content[0].text.strip()

    source_links = _build_source_links_md(all_rows)
    if source_links:
        synth_md = synth_md + "\n\n---\n\n" + source_links

    cache[cache_key] = synth_md
    try:
        _NOTES_CACHE_PATH.parent.mkdir(exist_ok=True)
        _NOTES_CACHE_PATH.write_text(json.dumps(cache, indent=2))
    except Exception:
        pass

    return synth_md


def fetch_chunks(subject_id: str, subtopic_id: str, k: int = 5) -> list[str]:
    col = get_collection()
    results = col.query(
        query_texts=[subtopic_id.replace("_", " ")],
        n_results=k,
        where={"subject_id": subject_id}
    )
    return results["documents"][0] if results["documents"] else []


def _content_root_path() -> Path:
    return Path(os.getenv("UPSC_CONTENT_PATH", "/Users/rahulsingh/Desktop/UPSC/Prelims")).expanduser().resolve()


def fetch_chunks_with_meta(subject_id: str, subtopic_id: str, k: int) -> list[dict[str, Any]]:
    """Chroma excerpts with ingestion metadata (source_file, file_path) for notes + links."""
    col = get_collection()
    results = col.query(
        query_texts=[subtopic_id.replace("_", " ")],
        n_results=k,
        where={"subject_id": subject_id},
        include=["documents", "metadatas"],
    )
    docs = results["documents"][0] if results.get("documents") else []
    metas = results["metadatas"][0] if results.get("metadatas") else []
    if not metas:
        metas = [{}] * len(docs)
    return [{"text": d, "meta": m or {}} for d, m in zip(docs, metas)]


def _library_link_url(rel_posix: str) -> str:
    return f"/api/backend/library/file?rel={quote(rel_posix, safe='')}"


def _meta_rel_label(meta: dict[str, Any]) -> tuple[str | None, str]:
    """Relative path under UPSC_CONTENT_PATH (for API link), and display label."""
    file_path = (meta or {}).get("file_path") or ""
    source_file = (meta or {}).get("source_file") or ""
    label = source_file or (Path(file_path).name if file_path else "source")
    if not file_path:
        return None, label
    root = _content_root_path()
    try:
        fp = Path(str(file_path)).expanduser().resolve()
        rel = fp.relative_to(root)
        return str(rel).replace("\\", "/"), label
    except Exception:
        return None, label


def _build_source_links_md(rows: list[dict[str, Any]]) -> str:
    """Return a '### Sources' markdown block with library links, or empty string."""
    seen_docs: dict[str, str] = {}
    for row in rows:
        rel, label = _meta_rel_label(row["meta"])
        if rel and rel not in seen_docs:
            seen_docs[rel] = label
    if not seen_docs:
        return ""
    lines = ["### Sources", ""]
    for rel, label in sorted(seen_docs.items(), key=lambda x: x[1].lower()):
        lines.append(f"- [{label}]({_library_link_url(rel)})")
    return "\n".join(lines)


def _notes_cache_key(subtopic_id: str, chunk_texts: list[str]) -> str:
    content = subtopic_id + "|" + "|".join(chunk_texts)
    return "notes:" + hashlib.sha256(content.encode()).hexdigest()[:20]


def synthesize_notes_cached(
    rows: list[dict[str, Any]],
    subtopic_id: str,
    subject_id: str,
) -> str:
    """LLM-synthesised revision notes, cached by subtopic+content hash."""
    chunk_texts = [r["text"] for r in rows]
    cache_key = _notes_cache_key(subtopic_id, chunk_texts)

    cache: dict = {}
    if _NOTES_CACHE_PATH.exists():
        try:
            cache = json.loads(_NOTES_CACHE_PATH.read_text())
        except Exception:
            pass

    if cache_key in cache:
        return cache[cache_key]

    if not rows:
        synth_md = (
            f"## {subtopic_id.replace('_', ' ').title()}\n\n"
            f"No indexed materials found for this subtopic. "
            f"Add study materials under `UPSC_CONTENT_PATH` and run `scripts/ingest.py`."
        )
    else:
        prompt_template = (PROMPT_DIR / "session_notes.txt").read_text()
        subtopic_display = subtopic_id.replace("_", " ")
        prompt = (
            prompt_template
            .replace("{{subject_name}}", subject_id)
            .replace("{{subtopics_list}}", subtopic_display)
            .replace("{{subtopic_name}}", subtopic_display)
            .replace("{{content_chunks}}", "\n\n---\n\n".join(chunk_texts))
            .replace("{{cross_subtopic_section}}", "")  # single subtopic — no cross section
        )
        resp = client.messages.create(
            model=os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001"),
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        synth_md = resp.content[0].text.strip()

    source_links = _build_source_links_md(rows)
    if source_links:
        synth_md = synth_md + "\n\n---\n\n" + source_links

    cache[cache_key] = synth_md
    try:
        _NOTES_CACHE_PATH.parent.mkdir(exist_ok=True)
        _NOTES_CACHE_PATH.write_text(json.dumps(cache, indent=2))
    except Exception:
        pass

    return synth_md


def fetch_ca_chunks(topic_keyword: str, k: int = 2) -> list[str]:
    col = get_collection()
    results = col.query(
        query_texts=[topic_keyword],
        n_results=k,
        where={"subject_id": "current_affairs"}
    )
    return results["documents"][0] if results["documents"] else []


def _build_multi_subtopic_prompt_parts(
    subject_id: str, allocation: list[dict]
) -> tuple[str, str]:
    """
    Returns (subtopic_allocation_str, content_chunks_str) for multi-subtopic mode.
    Fetches 2 ChromaDB chunks per subtopic; falls back to syllabus stub if none found.
    """
    alloc_lines: list[str] = []
    chunk_sections: list[str] = []

    for item in allocation:
        st_id = item["subtopic_id"]
        n = item["num_questions"]
        w = item["weight"]
        tag = "[UNTESTED — diagnose first]" if not item["is_tested"] else "[tested]"
        alloc_lines.append(f"  {st_id}: {n} question{'s' if n > 1 else ''}  {tag}  (PYQ weight {w})")

        st_chunks = fetch_chunks(subject_id, st_id, k=_chunk_k(n))
        if not st_chunks:
            st_chunks = [
                f"Standard UPSC Prelims content on {subject_id}: "
                f"{st_id.replace('_', ' ')}. Generate from canonical syllabus knowledge."
            ]
        header = f"[{st_id}  —  {n} question{'s' if n > 1 else ''}]"
        chunk_sections.append(header + "\n" + "\n---\n".join(st_chunks))

    subtopic_allocation = (
        "Subtopic coverage — generate EXACTLY these counts "
        "(each question's subtopic_id must equal the subtopic_id listed here):\n"
        + "\n".join(alloc_lines)
    )
    content_chunks_str = "\n\n".join(chunk_sections)
    return subtopic_allocation, content_chunks_str


@router.post("/generate")
def generate_quiz(config: dict):
    subject_id = config.get("subject_id", "")
    subtopic_id = config.get("subtopic_id", "")

    # ── Multi-subtopic resolution ─────────────────────────────────────────────
    # If subtopic_ids (list) is provided and has ≥2 entries, use merged mode.
    # Otherwise fall back to single subtopic_id (existing behaviour unchanged).
    raw_subtopic_ids: list[str] | None = config.get("subtopic_ids")
    if raw_subtopic_ids and len(raw_subtopic_ids) >= 2:
        # Clamp to max 4 subtopics per design decision
        subtopic_ids: list[str] = [s for s in raw_subtopic_ids[:4] if s]
        # Primary subtopic = highest PYQ weight; if weights unavailable, first in list
        weights_map = _get_pyq_weights_for_subtopics(subtopic_ids)
        primary_subtopic_id = max(subtopic_ids, key=lambda s: weights_map.get(s, 1.0))
        # Override subtopic_id to primary for backward-compat downstream
        subtopic_id = primary_subtopic_id
        is_merged = True
    else:
        subtopic_ids = [subtopic_id] if subtopic_id else []
        primary_subtopic_id = subtopic_id
        is_merged = False

    # Resolve canonical topic_id from syllabus; prefer over whatever the caller sent
    topic_id = (
        get_canonical_topic_id(subject_id, primary_subtopic_id)
        if primary_subtopic_id
        else config.get("topic_id", "")
    ) or config.get("topic_id", "")
    num_q = config.get("num_questions", 10)
    session_type = config.get("session_type", "diagnostic")

    if "difficulty" in config:
        difficulty = config["difficulty"]
    elif primary_subtopic_id:
        try:
            from difficulty_engine import get_difficulty
            difficulty = get_difficulty(primary_subtopic_id)
        except Exception:
            difficulty = "easy"
    else:
        difficulty = "mixed"  # subject-level diagnostics use mixed difficulty

    prebuilt_notes: str | None = None

    # ── Gather quiz intelligence (dedup, wrong concepts, user notes) ─────────
    intel = _get_quiz_intelligence(subject_id, primary_subtopic_id or None)

    # ── Prompt file selection ─────────────────────────────────────────────────
    if session_type == "deep_dive":
        prompt_file = "deep_dive_quiz.txt"
        # deep_dive always uses single-subtopic mode — merged sessions cannot be deep dives
        if not primary_subtopic_id:
            raise HTTPException(status_code=400, detail="deep_dive session_type requires subtopic_id")

    # ── MERGED multi-subtopic path (subtopic_ids list with ≥2 entries) ────────
    if is_merged:
        allocation = _allocate_questions_for_subtopic_ids(subtopic_ids, num_q)
        subtopic_allocation = _build_merged_subtopic_allocation_str(allocation)
        content_chunks_str = _build_merged_content_chunks_str(subject_id, allocation)  # uses _chunk_k scaling
        ca_chunks = fetch_ca_chunks(subject_id.replace("_", " "), k=2)
        ca_str = "\n\n---\n\n".join(ca_chunks)
        spillover_block = ""

        # Notes: use Sonnet for merged sessions; include cross-subtopic linkages
        if config.get("show_notes"):
            prebuilt_notes = synthesize_notes_multi_cached(subject_id, subtopic_ids)

        if session_type not in ("adaptive", "deep_dive"):
            prompt_file = "diagnostic_quiz.txt"
        elif session_type == "adaptive":
            prompt_file = "adaptive_quiz_only.txt" if config.get("show_notes") else "adaptive_session.txt"

    elif primary_subtopic_id:
        # ── Single-subtopic mode (session from plan or user-chosen subtopic) ────
        ca_chunks = fetch_ca_chunks(primary_subtopic_id.replace("_", " "))
        use_vector_notes = (
            session_type == "adaptive"
            and config.get("show_notes")
        )
        if use_vector_notes:
            # Synthesise structured notes via Haiku (cached by subtopic+content hash).
            note_rows = fetch_chunks_with_meta(subject_id, primary_subtopic_id, k=_NOTES_QUERY_K)
            if not note_rows:
                chunks = [
                    f"Standard UPSC Prelims content on {subject_id}: "
                    f"{primary_subtopic_id.replace('_', ' ')}. Generate from canonical syllabus knowledge."
                ]
            else:
                chunks = [r["text"] for r in note_rows]
            prebuilt_notes = synthesize_notes_cached(note_rows, primary_subtopic_id, subject_id)
            if session_type != "deep_dive":
                prompt_file = "adaptive_quiz_only.txt"
        else:
            chunks = fetch_chunks(subject_id, primary_subtopic_id, k=_chunk_k(num_q))
            if not chunks:
                chunks = [
                    f"Standard UPSC Prelims content on {subject_id}: "
                    f"{primary_subtopic_id.replace('_', ' ')}. Generate from canonical syllabus knowledge."
                ]
            if session_type not in ("adaptive", "deep_dive"):
                prompt_file = "diagnostic_quiz.txt"
            elif session_type == "adaptive":
                prompt_file = "adaptive_session.txt"
            # deep_dive keeps prompt_file set above

        subtopic_allocation = (
            f"Subtopic: {primary_subtopic_id}\n"
            f"Generate all {num_q} questions on this subtopic. "
            f"Set subtopic_id = \"{primary_subtopic_id}\" in every question."
        )
        content_chunks_str = "\n\n---\n\n".join(chunks)
        ca_str = "\n\n---\n\n".join(ca_chunks)

        # Spillover logic for adaptive sessions only
        spillover_block = ""
        if session_type == "adaptive":
            spillover_block = _get_spillover_subtopics(subject_id, primary_subtopic_id, n=2)

    else:
        if session_type != "deep_dive":
            prompt_file = "adaptive_session.txt" if session_type == "adaptive" else "diagnostic_quiz.txt"
        # ── Subject-level multi-subtopic diagnostic mode (no subtopic_id given) ─
        allocation = _allocate_questions_across_subtopics(subject_id, num_q)
        if allocation:
            subtopic_allocation, content_chunks_str = _build_multi_subtopic_prompt_parts(
                subject_id, allocation
            )
            # Single CA search for the whole subject
            ca_chunks = fetch_ca_chunks(subject_id.replace("_", " "), k=2)
            ca_str = "\n\n---\n\n".join(ca_chunks)
        else:
            # Fallback when syllabus has no entries for this subject
            chunks = fetch_chunks(subject_id, subject_id)
            ca_chunks = fetch_ca_chunks(subject_id.replace("_", " "))
            if not chunks:
                chunks = [f"Standard UPSC Prelims content on {subject_id.replace('_', ' ')}."]
            subtopic_allocation = (
                f"Topic: {subject_id} (general)\n"
                f"Generate {num_q} questions spread across diverse subtopics. "
                f"Use snake_case subtopic_id values that reflect each question's content."
            )
            content_chunks_str = "\n\n---\n\n".join(chunks)
            ca_str = "\n\n---\n\n".join(ca_chunks)
        spillover_block = ""

    recent_questions_block = _build_recent_questions_block(subject_id)

    # ── Dimension-aware context (Phase 2 of FEATURE-027) ─────────────────────
    # For merged sessions use primary subtopic for dimension context
    available_dimensions = _get_subtopic_dimensions(subject_id, primary_subtopic_id)

    prompt_template = (PROMPT_DIR / prompt_file).read_text()
    prompt = (
        prompt_template
        .replace("{{subject_name}}",           subject_id)
        .replace("{{subtopic_allocation}}",    subtopic_allocation)
        .replace("{{num_questions}}",          str(num_q))
        .replace("{{difficulty}}",             difficulty)
        .replace("{{content_chunks}}",         content_chunks_str)
        .replace("{{current_affairs_chunks}}", ca_str)
        .replace("{{recent_questions_block}}", recent_questions_block)
        # legacy placeholders kept for adaptive_session.txt compatibility
        .replace("{{topic_name}}",             topic_id)
        .replace("{{subtopic_name}}",          primary_subtopic_id)
        .replace("{{subtopic_id}}",            primary_subtopic_id)
        .replace("{{format}}",                 config.get("format", "quiz_only"))
        .replace("{{current_score}}",          str(config.get("current_score", 0)))
        .replace("{{#if show_notes}}",         "" if config.get("show_notes") else "<!--")
        .replace("{{else}}",                   "-->" if config.get("show_notes") else "")
        .replace("{{/if}}",                    "" if not config.get("show_notes") else "-->")
        # ── Quiz intelligence replacements ────────────────────────────────────
        .replace("{{excluded_question_hashes}}",
                 ", ".join(intel["excluded_hashes"][:50]) or "none")
        .replace("{{wrong_concepts_to_revisit}}",
                 ", ".join(intel["wrong_concepts"]) or "none")
        .replace("{{questions_seen_preview}}",
                 "; ".join(t[:80] for t in intel["question_texts_seen"][:20]) or "none")
        .replace("{{user_notes_context}}",     intel["user_notes_context"])
        .replace("{{spillover_subtopics}}",    spillover_block)
        # ── Dimension labeling (FEATURE-027 Phase 2) ─────────────────────────
        .replace("{{available_dimensions}}",   available_dimensions)
    )

    response = client.messages.create(
        model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()

    # Parse JSON — handle both array and object with questions key.
    # IMPORTANT: object responses like {"notes_summary":"...","questions":[...]}
    # contain "[" inside the string; naive "prefer [" would slice only the array
    # and drop notes_summary. Prefer top-level object when "{" comes first.
    try:
        first_brace = raw.find("{")
        first_bracket = raw.find("[")
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            start, end = first_brace, raw.rfind("}") + 1
        else:
            start, end = first_bracket, raw.rfind("]") + 1
        parsed = json.loads(raw[start:end])
        questions = parsed if isinstance(parsed, list) else parsed.get("questions", [])
        if prebuilt_notes is not None:
            notes = prebuilt_notes
        else:
            notes = None if isinstance(parsed, list) else parsed.get("notes_summary")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse quiz JSON: {e}")

    # Create session record — subtopic_id = primary (highest weight or first in list)
    # Full subtopic list stored in additive quiz_session_subtopics table
    session_id = str(uuid.uuid4())
    stored_config = {**config, "topic_id": topic_id or config.get("topic_id", "")}
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO quiz_sessions (id, session_type, subject_id, topic_id, mode, config, start_time, total_questions)
        VALUES (?,?,?,?,?,?,?,?)
    """, (session_id, session_type, subject_id, topic_id, config.get("mode", "fixed_set"),
          json.dumps(stored_config), datetime.now(timezone.utc).isoformat(), len(questions)))
    con.commit()
    con.close()

    # Persist multi-subtopic list in the additive quiz_session_subtopics table
    if subtopic_ids:
        _store_session_subtopics(session_id, subtopic_ids)

    return {
        "session_id": session_id,
        "questions": questions,
        "notes_summary": notes,
        "topic_id": topic_id or None,
        # Expose subtopic_ids to frontend so session card can show all subtopic names
        "subtopic_ids": subtopic_ids if is_merged else None,
    }


def _build_exam_sim_allocation(
    subtopic_ids: list[str],
    num_q: int,
    syllabus: dict,
) -> list[dict]:
    """
    Allocate questions proportionally by PYQ weight across selected subtopics.
    Returns list of {subtopic_id, subject_id, topic_id, num_questions, weight}.
    Falls back to equal distribution if priority_scorer unavailable.
    """
    try:
        from priority_scorer import compute_all_priorities
        pyq_weights = compute_all_priorities()
    except Exception:
        pyq_weights = {}

    # Build subtopic → (subject_id, topic_id) lookup from syllabus
    st_meta: dict[str, tuple[str, str]] = {}
    for subj in syllabus.get("subjects", []):
        for topic in subj.get("topics", []):
            for st in topic.get("subtopics", []):
                if st["id"] in subtopic_ids:
                    st_meta[st["id"]] = (subj["id"], topic["id"])

    if not subtopic_ids:
        return []

    raw_w = [max(pyq_weights.get(st, 1.0), 0.5) for st in subtopic_ids]
    total_w = sum(raw_w)
    allocs = [max(1, int(round(num_q * w / total_w))) for w in raw_w]

    # Fix rounding so total == num_q exactly
    diff = num_q - sum(allocs)
    n = len(allocs)
    i = 0
    while diff != 0:
        step = 1 if diff > 0 else -1
        if step < 0 and allocs[i % n] <= 1:
            i += 1
            continue
        allocs[i % n] += step
        diff -= step
        i += 1

    result = []
    for idx, st_id in enumerate(subtopic_ids):
        subject_id, topic_id = st_meta.get(st_id, ("", ""))
        result.append({
            "subtopic_id": st_id,
            "subject_id": subject_id,
            "topic_id": topic_id,
            "num_questions": allocs[idx],
            "weight": round(raw_w[idx], 2),
        })
    return result


def _build_exam_sim_prompt_parts(
    allocation: list[dict],
) -> tuple[str, str]:
    """
    Returns (subtopic_allocation_str, content_chunks_str) for exam sim mode.
    Fetches _chunk_k(n) chunks per subtopic (scales with question count, 3–8); falls back to syllabus stub if none found.
    """
    alloc_lines: list[str] = []
    chunk_sections: list[str] = []

    for item in allocation:
        st_id = item["subtopic_id"]
        subject_id = item["subject_id"]
        n = item["num_questions"]
        w = item["weight"]
        alloc_lines.append(
            f"  subtopic_id={st_id!r}  subject_id={subject_id!r}  "
            f"{n} question{'s' if n > 1 else ''}  (PYQ weight {w})"
        )

        st_chunks = fetch_chunks(subject_id, st_id, k=_chunk_k(n)) if subject_id else []
        if not st_chunks:
            st_chunks = [
                f"Standard UPSC Prelims content on {subject_id or 'general'}: "
                f"{st_id.replace('_', ' ')}. Generate from canonical syllabus knowledge."
            ]
        header = (
            f"[{st_id}  —  subject: {subject_id}  —  {n} question{'s' if n > 1 else ''}]"
        )
        chunk_sections.append(header + "\n" + "\n---\n".join(st_chunks))

    subtopic_allocation_str = (
        "Allocate questions EXACTLY as follows "
        "(each question MUST carry the subtopic_id and subject_id shown here):\n"
        + "\n".join(alloc_lines)
    )
    content_chunks_str = "\n\n".join(chunk_sections)
    return subtopic_allocation_str, content_chunks_str


@router.post("/start")
def start_exam_simulation(config: dict):
    """
    Start an exam simulation session.
    Accepts: session_type="exam_simulation", subtopic_ids=[...], n_questions=N,
             timed_duration_minutes=M.
    Generates all N questions upfront in a single Sonnet call.
    """
    session_type = config.get("session_type", "exam_simulation")
    if session_type != "exam_simulation":
        raise HTTPException(
            status_code=400, detail="Use /quiz/generate for non-exam-sim sessions"
        )

    subtopic_ids: list[str] = config.get("subtopic_ids", [])
    if not subtopic_ids:
        raise HTTPException(status_code=400, detail="subtopic_ids required for exam_simulation")

    num_q: int = int(config.get("n_questions", 50))
    if not (1 <= num_q <= 100):
        raise HTTPException(status_code=400, detail="n_questions must be between 1 and 100")

    timed_minutes: int | None = config.get("timed_duration_minutes")

    # Load syllabus for subject/topic lookups
    syllabus = _load_syllabus()

    # Allocate questions across selected subtopics by PYQ weight
    allocation = _build_exam_sim_allocation(subtopic_ids, num_q, syllabus)
    if not allocation:
        raise HTTPException(status_code=400, detail="No valid subtopics found in syllabus")

    # Gather quiz intelligence across all unique subjects selected
    unique_subjects = list({item["subject_id"] for item in allocation if item["subject_id"]})
    all_excluded_hashes: list[str] = []
    for subj in unique_subjects:
        intel = _get_quiz_intelligence(subj, None)
        all_excluded_hashes.extend(intel.get("excluded_hashes", []))
    excluded_hashes_str = ", ".join(all_excluded_hashes[:60]) or "none"

    # Build prompt parts
    subtopic_allocation_str, content_chunks_str = _build_exam_sim_prompt_parts(allocation)

    # Fetch CA chunks per subject and join (exam sim spans multiple subjects)
    ca_sections: list[str] = []
    for subj in unique_subjects:
        ca = fetch_ca_chunks(subj.replace("_", " "), k=3)
        if ca:
            ca_sections.append(f"[{subj}]\n" + "\n\n---\n\n".join(ca))
    ca_str = "\n\n".join(ca_sections) if ca_sections else "No current-affairs chunks available."

    # Build dimensions block: one section per unique (subject, subtopic) in allocation
    dim_sections: list[str] = []
    seen_subtopics: set[str] = set()
    for item in allocation:
        st_id = item["subtopic_id"]
        subj = item["subject_id"]
        if st_id and st_id not in seen_subtopics:
            seen_subtopics.add(st_id)
            dims = _get_subtopic_dimensions(subj, st_id)
            dim_sections.append(f"[{st_id}]\n{dims}")
    available_dimensions_str = "\n\n".join(dim_sections) if dim_sections else "No dimensions available."

    # Build recent questions block (aggregate across all subjects)
    recent_blocks: list[str] = []
    for subj in unique_subjects:
        blk = _build_recent_questions_block(subj)
        if blk:
            recent_blocks.append(blk)
    recent_questions_block = "\n\n".join(recent_blocks)

    prompt_template = (PROMPT_DIR / "exam_simulation.txt").read_text()
    prompt = (
        prompt_template
        .replace("{{num_questions}}", str(num_q))
        .replace("{{subtopic_allocation}}", subtopic_allocation_str)
        .replace("{{content_chunks}}", content_chunks_str)
        .replace("{{current_affairs_chunks}}", ca_str)
        .replace("{{available_dimensions}}", available_dimensions_str)
        .replace("{{recent_questions_block}}", recent_questions_block)
        .replace("{{excluded_question_hashes}}", excluded_hashes_str)
    )

    try:
        response = client.messages.create(
            model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
            max_tokens=16000,
            betas=["output-128k-2025-02-19"],
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")

    try:
        first_brace = raw.find("{")
        first_bracket = raw.find("[")
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            start, end = first_brace, raw.rfind("}") + 1
        else:
            start, end = first_bracket, raw.rfind("]") + 1
        parsed = json.loads(raw[start:end])
        questions = parsed if isinstance(parsed, list) else parsed.get("questions", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse exam sim JSON: {e}")

    # Build authoritative subtopic → allocation lookup.
    # Claude may drift on subject_id/topic_id in multi-subject sets — override with
    # the allocation which was built from the syllabus and is always correct.
    alloc_map: dict[str, dict] = {item["subtopic_id"]: item for item in allocation}
    for q in questions:
        # Content-based hash so excluded_hashes deduplication works across sessions.
        q["question_hash"] = hashlib.sha256(
            (q.get("question_text") or "").encode()
        ).hexdigest()[:16]
        # Fix subject_id/topic_id from allocation (source of truth).
        st_id = q.get("subtopic_id")
        if st_id and st_id in alloc_map:
            q["subject_id"] = alloc_map[st_id]["subject_id"]
            q["topic_id"]   = alloc_map[st_id]["topic_id"]

    # Create session record
    session_id = str(uuid.uuid4())
    mode = "time_boxed" if timed_minutes else "fixed_set"
    stored_config: dict = {
        **config,
        "subtopic_ids": subtopic_ids,
        "n_questions": num_q,
        "timed_duration_minutes": timed_minutes,
    }
    if timed_minutes:
        stored_config["time_minutes"] = timed_minutes

    # subject_id stored as comma-joined list so existing columns are populated
    combined_subject = ",".join(
        sorted({a["subject_id"] for a in allocation if a["subject_id"]})
    )

    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        INSERT INTO quiz_sessions
            (id, session_type, subject_id, topic_id, mode, config, start_time, total_questions)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            session_id,
            "exam_simulation",
            combined_subject,
            "",
            mode,
            json.dumps(stored_config),
            datetime.now(timezone.utc).isoformat(),
            len(questions),
        ),
    )
    con.commit()
    con.close()

    return {
        "session_id": session_id,
        "questions": questions,
        "notes_summary": None,
        "timed_duration_minutes": timed_minutes,
    }


@router.post("/pyq")
def get_pyq_questions(params: dict):
    """Fetch real PYQ questions from the database."""
    subject_id = params.get("subject_id")
    subtopic_id = params.get("subtopic_id")
    limit = params.get("limit", 10)
    year_from = params.get("year_from", 2016)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    query = "SELECT * FROM pyq_questions WHERE year >= ?"
    args: list = [year_from]

    if subject_id:
        query += " AND subject_id = ?"
        args.append(subject_id)
    if subtopic_id:
        query += " AND subtopic_id = ?"
        args.append(subtopic_id)

    query += " ORDER BY year DESC LIMIT ?"
    args.append(limit)

    rows = con.execute(query, args).fetchall()
    con.close()
    return [dict(r) for r in rows]
