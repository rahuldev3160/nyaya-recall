"""Internal API for Nyaya Arena — stateless, service-credential-authenticated.

Frozen spec: /Users/rahulsingh/Desktop/Claude Projects/Nyaya-Arena/docs/API_CONTRACTS.md
Contract 1 (Recall -> Arena). These routes never write to question_bank, sar_scores,
quiz_sessions, or session_answers — see that doc's "Statelessness" section for why.

Auth is a separate, static X-Arena-Api-Key credential (ARENA_SERVICE_API_KEY env var) —
deliberately independent of backend/auth.py's (unconfigured) end-user JWT middleware.
"""
from __future__ import annotations

import hmac
import os
import random

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, field_validator

from backend.db import get_conn

router = APIRouter()

_OPTION_COLUMNS = {"A": "option_a", "B": "option_b", "C": "option_c", "D": "option_d"}
_DEFAULT_MARKS_PER_QUESTION = 2.0  # UPSC Prelims convention; question_bank has no per-row marks column.


def _error(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


def verify_arena_api_key(x_arena_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("ARENA_SERVICE_API_KEY")
    if not expected or not x_arena_api_key or not hmac.compare_digest(x_arena_api_key, expected):
        raise _error(401, "AUTH_FAILED", "Missing or invalid X-Arena-Api-Key.")


def _difficulty_bucket(global_accuracy: float | None) -> str:
    """Derived at read-time from historical accuracy — question_bank has no difficulty column.
    No history yet (global_accuracy IS NULL) defaults to 'medium'."""
    if global_accuracy is None:
        return "medium"
    if global_accuracy >= 70:
        return "easy"
    if global_accuracy >= 40:
        return "medium"
    return "hard"


# ── 1.1  GET /internal/v1/questions ─────────────────────────────────────────

@router.get("/questions")
def get_questions(
    exam_source: str,
    count: int,
    subject: str | None = None,
    topic: str | None = None,
    difficulty: str = "mixed",
    exclude_question_ids: str | None = None,
    seed: str | None = None,
    x_arena_api_key: str | None = Header(default=None),
):
    verify_arena_api_key(x_arena_api_key)
    if not (1 <= count <= 200):
        raise _error(400, "INVALID_PARAMS", "count must be between 1 and 200.")
    if difficulty not in ("easy", "medium", "hard", "mixed"):
        raise _error(400, "INVALID_PARAMS", "difficulty must be one of easy|medium|hard|mixed.")

    con = get_conn()
    known_sources = {r["exam_source"] for r in con.execute(
        "SELECT DISTINCT exam_source FROM question_bank"
    ).fetchall()}
    if exam_source not in known_sources:
        con.close()
        raise _error(400, "INVALID_PARAMS", f"Unknown exam_source '{exam_source}'.",
                     {"known_exam_sources": sorted(known_sources)})

    where = ["exam_source = ?", "cancelled = 0"]
    params: list = [exam_source]
    if subject:
        where.append("subject_id = ?")
        params.append(subject)
    if topic:
        where.append("topic_id = ?")
        params.append(topic)
    exclude_ids = [x for x in (exclude_question_ids or "").split(",") if x]
    if exclude_ids:
        where.append(f"id NOT IN ({','.join('?' * len(exclude_ids))})")
        params.extend(exclude_ids)

    rows = con.execute(
        f"""SELECT id, question_text, option_a, option_b, option_c, option_d,
                   subject_id, topic_id, global_accuracy
            FROM question_bank
            WHERE {' AND '.join(where)}""",
        params,
    ).fetchall()
    con.close()

    candidates = [r for r in rows if difficulty == "mixed" or _difficulty_bucket(r["global_accuracy"]) == difficulty]

    if len(candidates) < count:
        raise _error(404, "INSUFFICIENT_QUESTIONS",
                     f"Only {len(candidates)} questions match the given filters, {count} requested.",
                     {"available_count": len(candidates)})

    rng = random.Random(seed) if seed else random.Random()
    chosen = rng.sample(candidates, count)

    questions = [
        {
            "question_id": r["id"],
            "question_text": r["question_text"],
            "options": {
                "A": r["option_a"], "B": r["option_b"],
                "C": r["option_c"], "D": r["option_d"],
            },
            "subject": r["subject_id"],
            "topic": r["topic_id"],
            "difficulty": _difficulty_bucket(r["global_accuracy"]),
            "marks": _DEFAULT_MARKS_PER_QUESTION,
        }
        for r in chosen
    ]
    return {"exam_source": exam_source, "count": len(questions), "questions": questions}


# ── 1.2  POST /internal/v1/score-attempt ────────────────────────────────────

class MarkingScheme(BaseModel):
    correct: float = 2.0
    wrong: float = -0.66
    unattempted: float = 0.0


class AnswerIn(BaseModel):
    question_id: str
    selected_option: str | None = None

    @field_validator("selected_option")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class ScoreAttemptRequest(BaseModel):
    answers: list[AnswerIn]
    marking_scheme: MarkingScheme = MarkingScheme()


@router.post("/score-attempt")
def score_attempt(payload: ScoreAttemptRequest, x_arena_api_key: str | None = Header(default=None)):
    verify_arena_api_key(x_arena_api_key)
    if not payload.answers:
        raise _error(400, "INVALID_PARAMS", "answers must not be empty.")

    ids = [a.question_id for a in payload.answers]
    con = get_conn()
    placeholders = ",".join("?" * len(ids))
    rows = con.execute(
        f"""SELECT id, correct_answer, explanation_short, explanation_full
            FROM question_bank WHERE id IN ({placeholders})""",
        ids,
    ).fetchall()
    con.close()

    by_id = {r["id"]: r for r in rows}
    unknown = [qid for qid in ids if qid not in by_id]
    if unknown:
        raise _error(404, "UNKNOWN_QUESTION_IDS", "One or more question_ids do not exist.",
                     {"unknown_ids": unknown})

    scheme = payload.marking_scheme
    results = []
    correct_count = wrong_count = unattempted_count = 0
    score = 0.0

    for a in payload.answers:
        row = by_id[a.question_id]
        correct_option = (row["correct_answer"] or "").upper() or None
        if a.selected_option is None:
            marks_awarded = scheme.unattempted
            is_correct = False
            unattempted_count += 1
        elif correct_option is not None and a.selected_option == correct_option:
            marks_awarded = scheme.correct
            is_correct = True
            correct_count += 1
        else:
            marks_awarded = scheme.wrong
            is_correct = False
            wrong_count += 1

        score += marks_awarded
        results.append({
            "question_id": a.question_id,
            "selected_option": a.selected_option,
            "correct_option": correct_option,
            "is_correct": is_correct,
            "marks_awarded": marks_awarded,
            "explanation": row["explanation_short"] or row["explanation_full"] or "",
        })

    max_score = len(payload.answers) * scheme.correct
    return {
        "score": round(score, 2),
        "max_score": max_score,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "unattempted_count": unattempted_count,
        "results": results,
    }
