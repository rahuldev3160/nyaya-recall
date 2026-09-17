"""Real-PYQ drill mode for exams whose content lives in nyaya-core, not this repo's own
upsc.db — currently PFRDA Grade A and UPSC EPFO-APFC/EO-AO. Zero LLM calls, zero
hallucination risk: every question served here is a real, previously-asked question
nyaya-core has already ingested and (mostly) verified against a real answer key.

Deliberately a new, separate router — not a change to routes/pyq.py, which is
structurally keyed by `year -> subject_id -> int question_id` against this repo's own
`upsc.db` and doesn't fit nyaya-core's `exam_id/paper_id/topic_id` string-keyed schema.
All state (questions, attempts, coverage) lives in nyaya-core's own `core.db` via its
API — this router holds no local DB connection at all, and existing routes/tables in
this repo are untouched.

If nyaya-core's local API isn't running, every endpoint here fails loudly (502) — there
is no local fallback content for these two exams to degrade to.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nyaya_core_client import (
    NyayaCoreClientError,
    NyayaCoreUnavailableError,
    get_pyq,
    get_topics,
    post_attempt,
)

router = APIRouter()


class AttemptRequest(BaseModel):
    question_id: str
    chosen_option: str


def _priority_score(weight: float | None) -> float:
    # coverage_depth isn't known per-question here (nyaya-core's /pyq doesn't expose
    # per-topic coverage_depth today) — real per-topic weight is still a meaningful
    # ordering signal on its own; a finer coverage-aware ordering can call nyaya-core's
    # /attempt-fed topic_coverage directly if this needs sharpening later.
    return weight if weight is not None else 1.0


@router.get("/topics")
def list_topics(exam_id: str, paper_id: str | None = None):
    try:
        return get_topics(exam_id, paper_id)
    except NyayaCoreUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except NyayaCoreClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/quiz")
def get_quiz(exam_id: str, paper_id: str | None = None, topic_id: str | None = None, n: int = 10):
    """Real PYQs only: `question_format=mcq`, non-void, non-null correct_option — mirrors
    nyaya-core's own scripts/quiz.py::fetch_candidate_questions filter exactly, applied
    here via the API instead of a direct DB read."""
    try:
        topics = get_topics(exam_id, paper_id)
        weight_by_topic = {t["topic_id"]: t.get("weight") for t in topics}

        candidates = get_pyq(exam_id, paper_id=paper_id, topic_id=topic_id, question_format="mcq", limit=2000)
        candidates = [
            q for q in candidates
            if q.get("status") != "void" and q.get("correct_option") and q.get("topic_id")
        ]
    except NyayaCoreUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except NyayaCoreClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="No quizzable real PYQs found for the given filters "
                   "(need status != 'void', a recorded correct_option, and a topic_id).",
        )

    candidates.sort(key=lambda q: _priority_score(weight_by_topic.get(q["topic_id"])), reverse=True)
    selected = candidates[:n]
    # correct_option is withheld from the response — the client must call POST /attempt
    # to find out if it was right, same as a real exam (and so a curious user can't just
    # read it out of the network tab before answering).
    return [{k: v for k, v in q.items() if k != "correct_option"} for q in selected]


@router.post("/attempt")
def record_attempt(req: AttemptRequest):
    try:
        return post_attempt(req.question_id, req.chosen_option)
    except NyayaCoreUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except NyayaCoreClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
