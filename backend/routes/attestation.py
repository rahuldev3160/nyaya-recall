import os
import json
import sqlite3
from pathlib import Path
from fastapi import APIRouter, HTTPException
import anthropic
import chromadb
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from self_attestation import compute_effective_level, record_attestation
from score_engine import close_session
from priority_scorer import rank_subtopics

from db import get_conn, DB_PATH

router = APIRouter()
CHROMA_PATH = os.getenv("CHROMA_PATH", "vector_store")
PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "validation_quiz.txt"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


@router.post("/claim")
def submit_claim(body: dict):
    subject_id = body.get("subject_id")
    claimed_label = body.get("claimed_label", "strong")
    if not subject_id:
        raise HTTPException(status_code=400, detail="subject_id required")

    top_subtopics = rank_subtopics(subject_id)[:6]
    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    col = chroma.get_or_create_collection("upsc_content")
    chunks = col.query(
        query_texts=[subject_id.replace("_", " ")], n_results=4,
        where={"subject_id": subject_id}
    )
    content = "\n\n---\n\n".join(chunks["documents"][0]) if chunks["documents"] else ""

    prompt = PROMPT_PATH.read_text()\
        .replace("{{subject_name}}", subject_id)\
        .replace("{{claimed_label}}", claimed_label)\
        .replace("{{claimed_level}}", str({"strong": 70, "very_strong": 85, "expert": 95}.get(claimed_label, 70)))\
        .replace("{{top_subtopics}}", json.dumps([s["subtopic_id"] for s in top_subtopics]))\
        .replace("{{content_chunks}}", content)

    response = client.messages.create(
        model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()
    start, end = raw.find("["), raw.rfind("]") + 1
    questions = json.loads(raw[start:end])

    return {"questions": questions, "claimed_label": claimed_label, "subject_id": subject_id}


@router.post("/validate")
def submit_validation(body: dict):
    subject_id = body.get("subject_id")
    claimed_label = body.get("claimed_label")
    answers = body.get("answers", [])
    if not answers:
        raise HTTPException(status_code=400, detail="No answers provided")

    correct = sum(1 for a in answers if a.get("is_correct"))
    validation_score = (correct / len(answers)) * 100
    result = compute_effective_level(claimed_label, validation_score)
    record_attestation(subject_id, result)
    return result
