"""
Single serving point for all question fetches.
12 pre-planned query patterns (QP-1 to QP-12) — all pure SQL, zero AI calls.
AI generation is triggered externally only when audit_qb_coverage finds < 5 Qs for a subtopic.
"""
from __future__ import annotations
import json
from datetime import date
from backend.db import get_conn


def _to_dict(row) -> dict:
    if row is None:
        return {}
    d = dict(row)
    if d.get("tags") and isinstance(d["tags"], str):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
    return d


# ── QP-1 ──────────────────────────────────────────────────────────────────────
def qp1_adaptive_diagnostic(user_id: str, subject_id: str, limit: int = 10) -> list[dict]:
    """Untested subtopics, sorted by UPSC relevance. For first diagnostics."""
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT qb.* FROM question_bank qb
            WHERE qb.subject_id = ?
              AND qb.subtopic_id NOT IN (
                  SELECT DISTINCT subtopic_id
                  FROM user_question_log WHERE user_id = ?
              )
              AND qb.cancelled = 0
              AND qb.answer_source != 'ai_inferred'
            ORDER BY qb.upsc_relevance DESC, qb.times_served ASC
            LIMIT ?
            """,
            [subject_id, user_id, limit],
        ).fetchall()
    return [_to_dict(r) for r in rows]


# ── QP-2 ──────────────────────────────────────────────────────────────────────
def qp2_daily_drill(user_id: str, subject_id: str, limit: int = 10) -> list[dict]:
    """Weak subtopics (avg < 70%) not seen in last 30 days."""
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT qb.* FROM question_bank qb
            JOIN (
                SELECT subtopic_id, AVG(is_correct) AS score
                FROM user_question_log WHERE user_id = ? GROUP BY subtopic_id
            ) scores ON qb.subtopic_id = scores.subtopic_id
            WHERE qb.subject_id = ?
              AND scores.score < 0.7
              AND qb.id NOT IN (
                  SELECT question_id FROM user_question_log
                  WHERE user_id = ? AND answered_at > datetime('now', '-30 days')
              )
              AND qb.cancelled = 0
            ORDER BY scores.score ASC, qb.upsc_relevance DESC
            LIMIT ?
            """,
            [user_id, subject_id, user_id, limit],
        ).fetchall()
    return [_to_dict(r) for r in rows]


# ── QP-3 ──────────────────────────────────────────────────────────────────────
def qp3_srs_due(user_id: str, limit: int = 10) -> list[dict]:
    """Spaced-repetition reviews due now."""
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT qb.*, uql.ease_factor, uql.repetition_count,
                   uql.next_review_at, uql.interval_days
            FROM user_question_log uql
            JOIN question_bank qb ON qb.id = uql.question_id
            WHERE uql.user_id = ?
              AND uql.next_review_at <= datetime('now')
              AND uql.is_correct = 0
              AND qb.cancelled = 0
            ORDER BY uql.next_review_at ASC
            LIMIT ?
            """,
            [user_id, limit],
        ).fetchall()
    return [_to_dict(r) for r in rows]


# ── QP-4 ──────────────────────────────────────────────────────────────────────
def qp4_pyq_browser(year: int, subject_id: str) -> list[dict]:
    """PYQ Browser: all CS questions for a given year + subject."""
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT * FROM question_bank
            WHERE exam_source = 'upsc_cse'
              AND year = ? AND subject_id = ? AND cancelled = 0
            ORDER BY q_number ASC
            """,
            [year, subject_id],
        ).fetchall()
    return [_to_dict(r) for r in rows]


# ── QP-5 ──────────────────────────────────────────────────────────────────────
def qp5_exam_simulation(user_id: str, subject_id: str, quota: int) -> list[dict]:
    """Questions for exam simulation — user hasn't seen, UPSC exam sources."""
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT * FROM question_bank
            WHERE subject_id = ?
              AND exam_source IN ('upsc_cse','upsc_cds','upsc_nda','upsc_capf')
              AND id NOT IN (
                  SELECT question_id FROM user_question_log WHERE user_id = ?
              )
              AND cancelled = 0
            ORDER BY upsc_relevance DESC, RANDOM()
            LIMIT ?
            """,
            [subject_id, user_id, quota],
        ).fetchall()
    return [_to_dict(r) for r in rows]


# ── QP-6 ──────────────────────────────────────────────────────────────────────
def qp6_subtopic_deep_dive(user_id: str, subtopic_id: str) -> list[dict]:
    """All questions on one subtopic, hardest first, with user attempt status."""
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT qb.*, COALESCE(uql.is_correct, -1) AS user_status,
                   uql.answered_at AS last_attempted
            FROM question_bank qb
            LEFT JOIN (
                SELECT question_id, is_correct, answered_at
                FROM user_question_log
                WHERE user_id = ?
                GROUP BY question_id
                HAVING answered_at = MAX(answered_at)
            ) uql ON qb.id = uql.question_id
            WHERE qb.subtopic_id = ? AND qb.cancelled = 0
            ORDER BY qb.upsc_relevance DESC, COALESCE(qb.global_accuracy, 0.5) ASC
            """,
            [user_id, subtopic_id],
        ).fetchall()
    return [_to_dict(r) for r in rows]


# ── QP-7 ──────────────────────────────────────────────────────────────────────
def qp7_follow_up_wrong(
    user_id: str,
    subtopic_id: str,
    dimension_id: str | None,
    exclude_id: str,
    limit: int = 5,
) -> list[dict]:
    """More questions on the same concept after a wrong answer."""
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT * FROM question_bank
            WHERE subtopic_id = ?
              AND (dimension_id = ? OR ? IS NULL)
              AND id != ?
              AND id NOT IN (
                  SELECT question_id FROM user_question_log
                  WHERE user_id = ? AND answered_at > datetime('now', '-7 days')
              )
              AND cancelled = 0
            ORDER BY exam_source = 'upsc_cse' DESC, upsc_relevance DESC
            LIMIT ?
            """,
            [subtopic_id, dimension_id, dimension_id, exclude_id, user_id, limit],
        ).fetchall()
    return [_to_dict(r) for r in rows]


# ── QP-8 ──────────────────────────────────────────────────────────────────────
def qp8_overconfidence_drill(
    user_id: str, days: int = 30, limit: int = 20
) -> list[dict]:
    """'Sure' + wrong — the user's dangerous blind spots."""
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT qb.*, uql.answered_at, uql.user_answer
            FROM user_question_log uql
            JOIN question_bank qb ON qb.id = uql.question_id
            WHERE uql.user_id = ?
              AND uql.confidence = 'sure'
              AND uql.is_correct = 0
              AND uql.answered_at > datetime('now', ? || ' days')
              AND qb.cancelled = 0
            ORDER BY uql.answered_at DESC
            LIMIT ?
            """,
            [user_id, f"-{days}", limit],
        ).fetchall()
    return [_to_dict(r) for r in rows]


# ── QP-9 ──────────────────────────────────────────────────────────────────────
def qp9_daily_challenge() -> list[dict]:
    """Today's leaderboard challenge — same 10 questions for every user."""
    today = date.today().isoformat()
    with get_conn() as con:
        row = con.execute(
            "SELECT question_ids FROM daily_challenge WHERE challenge_date = ?",
            [today],
        ).fetchone()
        if not row:
            return []
        qids: list[str] = json.loads(row["question_ids"])
        placeholders = ",".join("?" * len(qids))
        rows = con.execute(
            f"SELECT * FROM question_bank WHERE id IN ({placeholders})", qids
        ).fetchall()
    id_map = {r["id"]: _to_dict(r) for r in rows}
    return [id_map[qid] for qid in qids if qid in id_map]


# ── QP-10 ─────────────────────────────────────────────────────────────────────
def qp10_cross_exam_discovery(subtopic_id: str) -> list[dict]:
    """All exam appearances of a concept — for the Pro cross-exam insight card."""
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT exam_source, year, q_number, question_text,
                   correct_answer, upsc_relevance
            FROM question_bank
            WHERE subtopic_id = ? AND cancelled = 0
            ORDER BY upsc_relevance DESC, year DESC
            """,
            [subtopic_id],
        ).fetchall()
    return [_to_dict(r) for r in rows]


# ── QP-11 ─────────────────────────────────────────────────────────────────────
def qp11_coverage_gaps() -> list[dict]:
    """Subtopics with < 5 questions — triggers AI gap-fill pipeline."""
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT subtopic_id, subject_id,
                   COUNT(*) AS question_count,
                   AVG(upsc_relevance) AS avg_relevance
            FROM question_bank
            WHERE cancelled = 0
            GROUP BY subtopic_id, subject_id
            HAVING COUNT(*) < 5
            ORDER BY avg_relevance DESC
            """
        ).fetchall()
    return [_to_dict(r) for r in rows]


# ── QP-12 ─────────────────────────────────────────────────────────────────────
def qp12_due_count(user_id: str) -> int:
    """How many questions are due today — drives the red badge on the dashboard."""
    with get_conn() as con:
        srs_due = con.execute(
            """
            SELECT COUNT(*) FROM user_question_log
            WHERE user_id = ? AND next_review_at <= datetime('now') AND is_correct = 0
            """,
            [user_id],
        ).fetchone()[0]
        unseen = con.execute(
            """
            SELECT COUNT(*) FROM question_bank
            WHERE cancelled = 0
              AND id NOT IN (
                  SELECT question_id FROM user_question_log WHERE user_id = ?
              )
            LIMIT 50
            """,
            [user_id],
        ).fetchone()[0]
    return min(srs_due + unseen, 99)


# ── Waterfall serving entry point ─────────────────────────────────────────────
def serve_questions(
    user_id: str,
    subject_id: str | None,
    count: int,
    context: str = "adaptive",
) -> list[dict]:
    """
    Priority waterfall — single entry point for all quiz generation.
    context: 'adaptive' | 'diagnostic' | 'simulation' | 'challenge' | 'srs'
    Each returned question is tagged with _served_via for analytics.
    """
    if context == "challenge":
        qs = qp9_daily_challenge()
        for q in qs:
            q["_served_via"] = "daily_challenge"
        return qs[:count]

    result: list[dict] = []

    # 1. SRS reviews due (always highest priority)
    if len(result) < count:
        for q in qp3_srs_due(user_id, limit=count - len(result)):
            q["_served_via"] = "srs_review"
            result.append(q)

    # 2. Unseen CS PYQs
    if len(result) < count and subject_id:
        for q in qp1_adaptive_diagnostic(user_id, subject_id, limit=count - len(result)):
            q["_served_via"] = "pyq_unseen"
            result.append(q)

    # 3. Weak subtopics not seen recently
    if len(result) < count and subject_id:
        for q in qp2_daily_drill(user_id, subject_id, limit=count - len(result)):
            q["_served_via"] = "weak_drill"
            result.append(q)

    return result[:count]
