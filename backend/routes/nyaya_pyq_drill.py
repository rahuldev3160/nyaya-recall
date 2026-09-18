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

import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nyaya_core_client import (
    NyayaCoreClientError,
    NyayaCoreUnavailableError,
    get_attempted_question_ids,
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


def _is_answerable_mcq(q: dict) -> bool:
    """A real, presentable multiple-choice question — not just 'has a correct_option'.

    Found live in nyaya-core's data (2026-09-18): 158/454 PFRDA MCQ-tagged rows have
    `options` that's null or down to a single {letter: text} entry (the source coaching
    paper-book's reasoning/puzzle section only recorded the solved answer, not the full
    option set — real ingestion defect, not a display bug). Both real exams' genuine
    option counts are 4 (EPFO) or 5 (PFRDA), so >=4 cleanly separates real MCQs from
    broken ones (verified against the live DB, not assumed) — it also catches EPFO's own
    handful of chunk-boundary-truncated rows (BUG-13/14's known class). Also requires
    `correct_option` to actually be one of the option keys — a truncated options dict can
    otherwise carry a correct_option letter that no longer resolves to real text.
    """
    options = q.get("options")
    correct = q.get("correct_option")
    return (
        isinstance(options, dict)
        and len(options) >= 4
        and correct is not None
        and correct in options
    )


def _dedupe_topics(topics: list[dict]) -> list[dict]:
    """nyaya-core's /topics returns one row per (exam_id, paper_id, topic_id) — a topic
    linked under 2+ papers (74/195 of PFRDA's own topics, e.g. General-stream subjects
    tested in both Phase 1 and Phase 2) comes back as visually identical duplicate rows
    in a flat picker. Merge by topic_id, keeping the highest real weight seen."""
    by_id: dict[str, dict] = {}
    for t in topics:
        tid = t["topic_id"]
        if tid not in by_id or (t.get("weight") or 0) > (by_id[tid].get("weight") or 0):
            by_id[tid] = t
    return list(by_id.values())


@router.get("/topics")
def list_topics(exam_id: str, paper_id: str | None = None):
    """Only topics with at least one real, answerable PYQ — a topic can be registered in
    nyaya-core's taxonomy with zero ingested content yet (e.g. PFRDA's `pfrda_costing`,
    confirmed live: 0 pyq_bank rows), and showing it as a normal, clickable choice is a
    real dead end — the drill returns 404 for it. Filtering here means every topic the
    picker shows is guaranteed quizzable."""
    try:
        topics = _dedupe_topics(get_topics(exam_id, paper_id))
        candidates = get_pyq(exam_id, paper_id=paper_id, question_format="mcq", limit=2000)
    except NyayaCoreUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except NyayaCoreClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    quizzable_topic_ids = {q["topic_id"] for q in candidates if _is_answerable_mcq(q) and q.get("topic_id")}
    return [t for t in topics if t["topic_id"] in quizzable_topic_ids]


@router.get("/quiz")
def get_quiz(exam_id: str, paper_id: str | None = None, topic_id: str | None = None, n: int = 10):
    """Real PYQs only, and a genuinely answerable set (see `_is_answerable_mcq`).

    Randomized and repeat-aware: previously the top-`n` by weight was served in the same
    order every single call — a real, reported bug (same questions, same order, session
    after session). Now shuffles, and prefers questions the user hasn't attempted yet
    (via nyaya-core's `/attempts`, additive endpoint added for this), only falling back
    to already-seen ones once the unseen pool in this selection runs out.
    """
    try:
        topics = get_topics(exam_id, paper_id)
        weight_by_topic = {t["topic_id"]: t.get("weight") for t in topics}

        candidates = get_pyq(exam_id, paper_id=paper_id, topic_id=topic_id, question_format="mcq", limit=2000)
        candidates = [q for q in candidates if q.get("status") != "void" and _is_answerable_mcq(q)]

        attempted_ids = set(get_attempted_question_ids(exam_id))
    except NyayaCoreUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except NyayaCoreClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="No quizzable real PYQs found for the given filters "
                   "(need status != 'void', a real 4+ option answer set, and a topic_id).",
        )

    def weighted_shuffle(pool: list[dict]) -> list[dict]:
        # Higher-weight topics should still surface more often on average, but never in
        # a fixed order — sample without replacement, weighted by topic priority.
        pool = pool[:]
        weights = [max(_priority_score(weight_by_topic.get(q["topic_id"])), 0.01) for q in pool]
        ordered = []
        while pool:
            picked = random.choices(range(len(pool)), weights=weights, k=1)[0]
            ordered.append(pool.pop(picked))
            weights.pop(picked)
        return ordered

    unattempted = weighted_shuffle([q for q in candidates if q["question_id"] not in attempted_ids])
    seen_again = weighted_shuffle([q for q in candidates if q["question_id"] in attempted_ids])
    selected = (unattempted + seen_again)[:n]

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
