"""
PYQ Browser endpoints — pure SQL, zero AI calls.

All read-only except POST /pyq/attempt.
Gracefully handles missing columns (answer_source, q_number, answer_disputed)
until ALTER TABLE pyq_questions is approved and executed.
"""
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from db import get_conn

router = APIRouter()

_SUBJECT_LABELS = {
    "polity":          "Polity & Governance",
    "economy":         "Economy",
    "history_amac":    "History (A/M/AC)",
    "modern_history":  "Modern History",
    "geography":       "Geography",
    "environment":     "Environment",
    "science_tech":    "Science & Tech",
    "current_affairs": "Current Affairs",
    "ir_governance":   "IR & Governance",
}


def _get_user_id() -> str:
    return "user_1"


@router.get("/years")
def get_years(user_id: str = Depends(_get_user_id)):
    """List all years with question counts and user attempt stats."""
    con = get_conn()
    rows = con.execute(
        """
        SELECT year, COUNT(*) AS total
        FROM pyq_questions
        WHERE year > 0
        GROUP BY year
        ORDER BY year DESC
        """
    ).fetchall()

    # Attempted / correct from pyq_attempts (may not exist yet — graceful fallback)
    attempts_map: dict[int, dict] = {}
    try:
        a_rows = con.execute(
            """
            SELECT pq.year, COUNT(*) AS attempted,
                   SUM(CASE WHEN pa.is_correct=1 THEN 1 ELSE 0 END) AS correct
            FROM pyq_attempts pa
            JOIN pyq_questions pq ON pq.id = pa.question_id
            WHERE pa.user_id=?
            GROUP BY pq.year
            """,
            (user_id,),
        ).fetchall()
        for r in a_rows:
            attempts_map[r["year"]] = {"attempted": r["attempted"], "correct": r["correct"]}
    except Exception:
        pass

    con.close()
    return [
        {
            "year": r["year"],
            "total": r["total"],
            "attempted": attempts_map.get(r["year"], {}).get("attempted", 0),
            "correct":   attempts_map.get(r["year"], {}).get("correct", 0),
        }
        for r in rows
    ]


@router.get("/{year}/subjects")
def get_subjects(year: int, user_id: str = Depends(_get_user_id)):
    """List subjects for a given year with question counts."""
    con = get_conn()
    rows = con.execute(
        """
        SELECT subject_id, COUNT(*) AS total
        FROM pyq_questions
        WHERE year=? AND subject_id IS NOT NULL
        GROUP BY subject_id
        ORDER BY subject_id
        """,
        (year,),
    ).fetchall()

    attempts_map: dict[str, dict] = {}
    try:
        a_rows = con.execute(
            """
            SELECT pq.subject_id,
                   COUNT(*) AS attempted,
                   SUM(CASE WHEN pa.is_correct=1 THEN 1 ELSE 0 END) AS correct
            FROM pyq_attempts pa
            JOIN pyq_questions pq ON pq.id = pa.question_id
            WHERE pa.user_id=? AND pq.year=?
            GROUP BY pq.subject_id
            """,
            (user_id, year),
        ).fetchall()
        for r in a_rows:
            attempts_map[r["subject_id"]] = {"attempted": r["attempted"], "correct": r["correct"]}
    except Exception:
        pass

    con.close()
    return [
        {
            "subject_id": r["subject_id"],
            "label":      _SUBJECT_LABELS.get(r["subject_id"], r["subject_id"]),
            "total":      r["total"],
            "attempted":  attempts_map.get(r["subject_id"], {}).get("attempted", 0),
            "correct":    attempts_map.get(r["subject_id"], {}).get("correct", 0),
        }
        for r in rows
    ]


@router.get("/{year}/{subject_id}/topics")
def get_topics(year: int, subject_id: str, user_id: str = Depends(_get_user_id)):
    """List topics for a year + subject with question counts."""
    con = get_conn()
    rows = con.execute(
        """
        SELECT topic_id, COUNT(*) AS total
        FROM pyq_questions
        WHERE year=? AND subject_id=? AND topic_id IS NOT NULL
        GROUP BY topic_id
        ORDER BY topic_id
        """,
        (year, subject_id),
    ).fetchall()

    attempts_map: dict[str, dict] = {}
    try:
        a_rows = con.execute(
            """
            SELECT pq.topic_id,
                   COUNT(*) AS attempted,
                   SUM(CASE WHEN pa.is_correct=1 THEN 1 ELSE 0 END) AS correct
            FROM pyq_attempts pa
            JOIN pyq_questions pq ON pq.id = pa.question_id
            WHERE pa.user_id=? AND pq.year=? AND pq.subject_id=?
            GROUP BY pq.topic_id
            """,
            (user_id, year, subject_id),
        ).fetchall()
        for r in a_rows:
            if r["topic_id"]:
                attempts_map[r["topic_id"]] = {"attempted": r["attempted"], "correct": r["correct"]}
    except Exception:
        pass

    con.close()
    return [
        {
            "topic_id":  r["topic_id"],
            "label":     r["topic_id"].replace("_", " ").title() if r["topic_id"] else "Uncategorised",
            "total":     r["total"],
            "attempted": attempts_map.get(r["topic_id"], {}).get("attempted", 0),
            "correct":   attempts_map.get(r["topic_id"], {}).get("correct", 0),
        }
        for r in rows
    ]


@router.get("/{year}/{subject_id}/{topic_id}/questions")
def get_questions(year: int, subject_id: str, topic_id: str, user_id: str = Depends(_get_user_id)):
    """Return questions for a year/subject/topic with user attempt status."""
    con = get_conn()

    rows = con.execute(
        """
        SELECT id, question_text,
               option_a, option_b, option_c, option_d,
               correct_answer, subtopic_id,
               answer_source, answer_disputed, q_number
        FROM pyq_questions
        WHERE year=? AND subject_id=? AND topic_id=?
        ORDER BY COALESCE(q_number, id)
        """,
        (year, subject_id, topic_id),
    ).fetchall()

    # Fetch user's past attempts on these questions
    question_ids = [r["id"] for r in rows]
    attempts: dict[int, dict] = {}
    if question_ids:
        try:
            ph = ",".join("?" * len(question_ids))
            a_rows = con.execute(
                f"SELECT question_id, user_answer, is_correct FROM pyq_attempts "
                f"WHERE user_id=? AND question_id IN ({ph}) "
                f"ORDER BY attempted_at DESC",
                [user_id] + question_ids,
            ).fetchall()
            for a in a_rows:
                if a["question_id"] not in attempts:
                    attempts[a["question_id"]] = {"user_answer": a["user_answer"], "is_correct": bool(a["is_correct"])}
        except Exception:
            pass

    con.close()
    return [
        {
            "id":              r["id"],
            "question_text":   r["question_text"],
            "option_a":        r["option_a"],
            "option_b":        r["option_b"],
            "option_c":        r["option_c"],
            "option_d":        r["option_d"],
            "correct_answer":  r["correct_answer"],
            "subtopic_id":     r["subtopic_id"],
            "q_number":        r["q_number"],
            "answer_source":   r["answer_source"] or "ai_inferred",
            "answer_disputed": bool(r["answer_disputed"]),
            "user_answer":     attempts.get(r["id"], {}).get("user_answer"),
            "user_correct":    attempts.get(r["id"], {}).get("is_correct"),
        }
        for r in rows
    ]


@router.post("/attempt")
def record_attempt(body: dict, user_id: str = Depends(_get_user_id)):
    """Record a user's answer to a PYQ question."""
    question_id    = body.get("question_id")
    user_answer    = body.get("answer")
    time_taken_sec = body.get("time_taken_sec")

    if not question_id or not user_answer:
        raise HTTPException(status_code=400, detail="question_id and answer are required")

    try:
        con = get_conn()
        row = con.execute(
            "SELECT correct_answer, answer_source FROM pyq_questions WHERE id=?", (question_id,)
        ).fetchone()
        if not row:
            con.close()
            raise HTTPException(status_code=404, detail="Question not found")

        correct_answer = row["correct_answer"]
        if not correct_answer:
            con.close()
            return {"correct": None, "correct_answer": None, "unverified": True}

        is_correct = int(
            str(user_answer).strip().lower() == str(correct_answer).strip().lower()
        )
        con.execute(
            """
            INSERT INTO pyq_attempts (user_id, question_id, user_answer, is_correct, time_taken_sec)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, question_id, user_answer, is_correct, time_taken_sec),
        )
        con.commit()
        con.close()
        return {"correct": bool(is_correct), "correct_answer": correct_answer}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/explanation/{question_id}")
def get_explanation(question_id: int):
    """Return pre-generated concept explanation for a PYQ. Zero API calls."""
    try:
        con = get_conn()
        row = con.execute(
            """
            SELECT concept_tested, correct_explanation,
                   option_a_note, option_b_note, option_c_note, option_d_note,
                   memory_hook, model_used, generated_at
            FROM question_explanations
            WHERE question_id = ?
            """,
            (question_id,),
        ).fetchone()
        con.close()
        if not row:
            return {"available": False}
        return {
            "available": True,
            "concept_tested":      row["concept_tested"],
            "correct_explanation": row["correct_explanation"],
            "option_a_note":       row["option_a_note"],
            "option_b_note":       row["option_b_note"],
            "option_c_note":       row["option_c_note"],
            "option_d_note":       row["option_d_note"],
            "memory_hook":         row["memory_hook"],
            "model_used":          row["model_used"],
            "generated_at":        row["generated_at"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
def get_stats_summary(user_id: str = Depends(_get_user_id)):
    """Summary stats for dashboard widget."""
    con = get_conn()
    try:
        row = con.execute(
            """
            SELECT COUNT(*) AS attempted,
                   SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) AS correct
            FROM pyq_attempts
            WHERE user_id=?
            """,
            (user_id,),
        ).fetchone()
        year_rows = con.execute(
            """
            SELECT DISTINCT pq.year
            FROM pyq_attempts pa
            JOIN pyq_questions pq ON pq.id = pa.question_id
            WHERE pa.user_id=?
            ORDER BY pq.year DESC
            """,
            (user_id,),
        ).fetchall()
        con.close()
        attempted = row["attempted"] or 0
        correct   = row["correct"] or 0
        return {
            "total_attempted": attempted,
            "total_correct":   correct,
            "accuracy_pct":    round(correct / max(attempted, 1) * 100, 1),
            "years_touched":   [r["year"] for r in year_rows],
        }
    except Exception:
        con.close()
        return {"total_attempted": 0, "total_correct": 0, "accuracy_pct": 0.0, "years_touched": []}
