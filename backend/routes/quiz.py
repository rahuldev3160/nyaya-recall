from __future__ import annotations
import os
import sys
import json
import uuid
import sqlite3
from pathlib import Path
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
_SUBJECT_ALIAS = {"history": "history_amac"}

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

    prompt_file = "adaptive_session.txt" if session_type == "adaptive" else "diagnostic_quiz.txt"
    prompt_template = (PROMPT_DIR / prompt_file).read_text()

    if subtopic_id:
        # ── Single-subtopic mode (session from plan or user-chosen subtopic) ────
        chunks = fetch_chunks(subject_id, subtopic_id)
        ca_chunks = fetch_ca_chunks(subtopic_id.replace("_", " "))
        if not chunks:
            chunks = [
                f"Standard UPSC Prelims content on {subject_id}: "
                f"{subtopic_id.replace('_', ' ')}. Generate from canonical syllabus knowledge."
            ]
        subtopic_allocation = (
            f"Subtopic: {subtopic_id}\n"
            f"Generate all {num_q} questions on this subtopic. "
            f"Set subtopic_id = \"{subtopic_id}\" in every question."
        )
        content_chunks_str = "\n\n---\n\n".join(chunks)
        ca_str = "\n\n---\n\n".join(ca_chunks)
    else:
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
    )

    response = client.messages.create(
        model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()

    # Parse JSON — handle both array and object with questions key
    try:
        start = raw.find("[") if "[" in raw else raw.find("{")
        end = (raw.rfind("]") + 1) if "[" in raw else (raw.rfind("}") + 1)
        parsed = json.loads(raw[start:end])
        questions = parsed if isinstance(parsed, list) else parsed.get("questions", [])
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
