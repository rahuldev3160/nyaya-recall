"""Question bank + streak endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.db import get_conn
from backend.services import question_server as qs
from backend.services import streak as streak_svc
from backend.services import username as username_svc
from backend.services.srs import compute_srs_update

router = APIRouter()


def _get_user_id() -> str:
    return "user_1"


# ── Due count (dashboard red badge) ───────────────────────────────────────────

@router.get("/due-count")
def due_count(user_id: str = Depends(_get_user_id)):
    return {"count": qs.qp12_due_count(user_id)}


# ── Daily challenge ────────────────────────────────────────────────────────────

@router.get("/daily-challenge")
def daily_challenge():
    questions = qs.qp9_daily_challenge()
    return {"questions": questions, "count": len(questions)}


# ── Overconfidence drill (Pro insight) ────────────────────────────────────────

@router.get("/overconfidence")
def overconfidence(
    days: int = 30,
    limit: int = 20,
    user_id: str = Depends(_get_user_id),
):
    return {"questions": qs.qp8_overconfidence_drill(user_id, days=days, limit=limit)}


# ── Cross-exam discovery (Pro) ─────────────────────────────────────────────────

@router.get("/cross-exam/{subtopic_id}")
def cross_exam(subtopic_id: str):
    return {"appearances": qs.qp10_cross_exam_discovery(subtopic_id)}


# ── Log an answer + update SRS ────────────────────────────────────────────────

class LogAnswerPayload(BaseModel):
    question_id: str
    session_id: str | None = None
    exam_context: str = "adaptive"
    user_answer: str | None = None
    is_correct: bool | None = None
    confidence: str = "guess"
    time_taken_sec: int | None = None
    skipped: bool = False


@router.post("/log")
def log_answer(
    payload: LogAnswerPayload,
    user_id: str = Depends(_get_user_id),
):
    with get_conn() as con:
        # Fetch existing SRS state for this question if any
        existing = con.execute(
            """SELECT interval_days, ease_factor, repetition_count
               FROM user_question_log
               WHERE user_id = ? AND question_id = ?
               ORDER BY answered_at DESC LIMIT 1""",
            [user_id, payload.question_id],
        ).fetchone()

        interval_days = existing["interval_days"] if existing else 1
        ease_factor = existing["ease_factor"] if existing else 2.5
        repetition_count = existing["repetition_count"] if existing else 0

        srs = {}
        if payload.is_correct is not None and not payload.skipped:
            srs = compute_srs_update(
                interval_days=interval_days,
                ease_factor=ease_factor,
                repetition_count=repetition_count,
                is_correct=payload.is_correct,
                confidence=payload.confidence,
            )

        con.execute(
            """INSERT INTO user_question_log
               (user_id, question_id, session_id, exam_context,
                user_answer, is_correct, confidence, time_taken_sec, skipped,
                interval_days, ease_factor, next_review_at, repetition_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                user_id, payload.question_id, payload.session_id,
                payload.exam_context, payload.user_answer,
                int(payload.is_correct) if payload.is_correct is not None else None,
                payload.confidence, payload.time_taken_sec,
                int(payload.skipped),
                srs.get("interval_days", interval_days),
                srs.get("ease_factor", ease_factor),
                srs.get("next_review_at"),
                srs.get("repetition_count", repetition_count),
            ],
        )

        # Update aggregate accuracy on the question
        con.execute(
            """UPDATE question_bank
               SET times_served = times_served + 1,
                   times_correct = times_correct + ?,
                   global_accuracy = CAST(times_correct + ? AS REAL) /
                                     NULLIF(times_served + 1, 0)
               WHERE id = ?""",
            [
                1 if payload.is_correct else 0,
                1 if payload.is_correct else 0,
                payload.question_id,
            ],
        )

    return {"ok": True, "srs": srs}


# ── Streak ─────────────────────────────────────────────────────────────────────

@router.get("/streak")
def get_streak(user_id: str = Depends(_get_user_id)):
    return streak_svc.get_or_create(user_id)


class StreakConfigPayload(BaseModel):
    shield_enabled: bool
    max_grace_per_week: int  # 0 | 1 | 2


@router.put("/streak/config")
def update_streak_config(
    payload: StreakConfigPayload,
    user_id: str = Depends(_get_user_id),
):
    try:
        cfg = streak_svc.update_config(
            user_id, payload.shield_enabled, payload.max_grace_per_week
        )
        return cfg
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/streak/activity")
def record_streak_activity(user_id: str = Depends(_get_user_id)):
    """Call after any completed session to record today's activity."""
    return streak_svc.record_activity(user_id)


# ── Username ───────────────────────────────────────────────────────────────────

@router.get("/username/options")
def username_options():
    """Return 3 available username suggestions for onboarding."""
    return {"options": username_svc.generate_options(3)}


class ClaimUsernamePayload(BaseModel):
    username: str


@router.post("/username/claim")
def claim_username(
    payload: ClaimUsernamePayload,
    user_id: str = Depends(_get_user_id),
):
    try:
        ok = username_svc.claim(user_id, payload.username)
        if not ok:
            raise HTTPException(status_code=409, detail="Username already taken")
        return {"ok": True, "username": payload.username}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
