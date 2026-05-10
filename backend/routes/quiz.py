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

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
chroma = chromadb.PersistentClient(path=CHROMA_PATH)


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


@router.post("/generate")
def generate_quiz(config: dict):
    subject_id = config.get("subject_id", "")
    topic_id = config.get("topic_id", "")
    subtopic_id = config.get("subtopic_id", "")
    num_q = config.get("num_questions", 10)
    session_type = config.get("session_type", "diagnostic")

    # Use adaptive difficulty if not explicitly overridden in config
    if "difficulty" in config:
        difficulty = config["difficulty"]
    elif subtopic_id:
        try:
            from difficulty_engine import get_difficulty
            difficulty = get_difficulty(subtopic_id)
        except Exception:
            difficulty = "easy"
    else:
        difficulty = "easy"

    chunks = fetch_chunks(subject_id, subtopic_id)
    ca_chunks = fetch_ca_chunks(subtopic_id.replace("_", " "))

    if not chunks:
        chunks = [f"General UPSC knowledge on {subject_id.replace('_', ' ')} — {subtopic_id.replace('_', ' ')}. "
                  "Generate questions based on standard UPSC Prelims syllabus for this topic."]

    prompt_file = "adaptive_session.txt" if session_type == "adaptive" else "diagnostic_quiz.txt"
    prompt_template = (PROMPT_DIR / prompt_file).read_text()

    prompt = prompt_template\
        .replace("{{subject_name}}", subject_id)\
        .replace("{{topic_name}}", topic_id)\
        .replace("{{subtopic_name}}", subtopic_id)\
        .replace("{{subtopic_id}}", subtopic_id)\
        .replace("{{num_questions}}", str(num_q))\
        .replace("{{difficulty}}", difficulty)\
        .replace("{{content_chunks}}", "\n\n---\n\n".join(chunks))\
        .replace("{{current_affairs_chunks}}", "\n\n---\n\n".join(ca_chunks))\
        .replace("{{format}}", config.get("format", "quiz_only"))\
        .replace("{{current_score}}", str(config.get("current_score", 0)))\
        .replace("{{#if show_notes}}", "" if config.get("show_notes") else "<!--")\
        .replace("{{else}}", "-->" if config.get("show_notes") else "")\
        .replace("{{/if}}", "" if not config.get("show_notes") else "-->")

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
