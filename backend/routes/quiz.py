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
from datetime import datetime, timezone

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
        prompt = (
            prompt_template
            .replace("{{subject_name}}", subject_id)
            .replace("{{subtopic_name}}", subtopic_id.replace("_", " "))
            .replace("{{content_chunks}}", "\n\n---\n\n".join(chunk_texts))
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

        st_chunks = fetch_chunks(subject_id, st_id, k=2)
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
    topic_id   = config.get("topic_id", "")
    subtopic_id = config.get("subtopic_id", "")
    num_q = config.get("num_questions", 10)
    session_type = config.get("session_type", "diagnostic")

    if "difficulty" in config:
        difficulty = config["difficulty"]
    elif subtopic_id:
        try:
            from difficulty_engine import get_difficulty
            difficulty = get_difficulty(subtopic_id)
        except Exception:
            difficulty = "easy"
    else:
        difficulty = "mixed"  # subject-level diagnostics use mixed difficulty

    prebuilt_notes: str | None = None

    # ── Gather quiz intelligence (dedup, wrong concepts, user notes) ─────────
    intel = _get_quiz_intelligence(subject_id, subtopic_id or None)

    # ── Prompt file selection ─────────────────────────────────────────────────
    if session_type == "deep_dive":
        prompt_file = "deep_dive_quiz.txt"
        # deep_dive always uses single-subtopic mode, no multi-subtopic allocation
        if not subtopic_id:
            raise HTTPException(status_code=400, detail="deep_dive session_type requires subtopic_id")

    if subtopic_id:
        # ── Single-subtopic mode (session from plan or user-chosen subtopic) ────
        ca_chunks = fetch_ca_chunks(subtopic_id.replace("_", " "))
        use_vector_notes = (
            session_type == "adaptive"
            and config.get("show_notes")
        )
        if use_vector_notes:
            # Synthesise structured notes via Haiku (cached by subtopic+content hash).
            note_rows = fetch_chunks_with_meta(subject_id, subtopic_id, k=_NOTES_QUERY_K)
            if not note_rows:
                chunks = [
                    f"Standard UPSC Prelims content on {subject_id}: "
                    f"{subtopic_id.replace('_', ' ')}. Generate from canonical syllabus knowledge."
                ]
            else:
                chunks = [r["text"] for r in note_rows]
            prebuilt_notes = synthesize_notes_cached(note_rows, subtopic_id, subject_id)
            if session_type != "deep_dive":
                prompt_file = "adaptive_quiz_only.txt"
        else:
            chunks = fetch_chunks(subject_id, subtopic_id)
            if not chunks:
                chunks = [
                    f"Standard UPSC Prelims content on {subject_id}: "
                    f"{subtopic_id.replace('_', ' ')}. Generate from canonical syllabus knowledge."
                ]
            if session_type not in ("adaptive", "deep_dive"):
                prompt_file = "diagnostic_quiz.txt"
            elif session_type == "adaptive":
                prompt_file = "adaptive_session.txt"
            # deep_dive keeps prompt_file set above

        subtopic_allocation = (
            f"Subtopic: {subtopic_id}\n"
            f"Generate all {num_q} questions on this subtopic. "
            f"Set subtopic_id = \"{subtopic_id}\" in every question."
        )
        content_chunks_str = "\n\n---\n\n".join(chunks)
        ca_str = "\n\n---\n\n".join(ca_chunks)

        # Spillover logic for adaptive sessions only
        spillover_block = ""
        if session_type == "adaptive":
            spillover_block = _get_spillover_subtopics(subject_id, subtopic_id, n=2)

    else:
        if session_type != "deep_dive":
            prompt_file = "adaptive_session.txt" if session_type == "adaptive" else "diagnostic_quiz.txt"
        # ── Multi-subtopic diagnostic mode ───────────────────────────────────────
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

    prompt_template = (PROMPT_DIR / prompt_file).read_text()
    prompt = (
        prompt_template
        .replace("{{subject_name}}",           subject_id)
        .replace("{{subtopic_allocation}}",    subtopic_allocation)
        .replace("{{num_questions}}",          str(num_q))
        .replace("{{difficulty}}",             difficulty)
        .replace("{{content_chunks}}",         content_chunks_str)
        .replace("{{current_affairs_chunks}}", ca_str)
        # legacy placeholders kept for adaptive_session.txt compatibility
        .replace("{{topic_name}}",             topic_id)
        .replace("{{subtopic_name}}",          subtopic_id)
        .replace("{{subtopic_id}}",            subtopic_id)
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

    # Create session record
    session_id = str(uuid.uuid4())
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO quiz_sessions (id, session_type, subject_id, topic_id, mode, config, start_time, total_questions)
        VALUES (?,?,?,?,?,?,?,?)
    """, (session_id, session_type, subject_id, topic_id, config.get("mode", "fixed_set"),
          json.dumps(config), datetime.now(timezone.utc).isoformat(), len(questions)))
    con.commit()
    con.close()

    return {"session_id": session_id, "questions": questions, "notes_summary": notes}


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
