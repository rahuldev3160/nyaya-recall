"""
plan_validator.py — deterministic post-Claude plan rule enforcement.

Public API:
    validate_and_fix(plan, available_hours, subtopic_coverage) -> dict

Called by plan_generator.py immediately after the plan is parsed from Claude's
response and before the CSAT safety filter. The function mutates and returns
the plan dict, appending a `validation` key with corrections and warnings.

Rules enforced (in order):
    A — Per-subject cap: max 2 sessions per subject per day
    B — Subject spread: at least 3 distinct subjects (warning only — no auto-add)
    C — Time budget: total estimated_minutes <= available_hours * 60
    D — needs_retest priority: warn if a lower-weight untested subtopic is
        scheduled while a higher-weight needs_retest subtopic is not
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str = "") -> str:
    if isinstance(value, str):
        return value
    return default if value is None else str(value)


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------

def _rule_a_subject_cap(
    sessions: list[dict],
    corrections: list[str],
) -> list[dict]:
    """
    Rule A — Per-subject cap: keep at most 2 sessions per subject per day.
    Sessions with lower `order` values are considered higher priority and are
    kept. Any session beyond the second occurrence of a subject is dropped.
    """
    # Sort by order so we consistently keep the earliest sessions
    def _order_key(s: dict) -> int:
        return _safe_int(s.get("order"), default=9999)

    sorted_sessions = sorted(sessions, key=_order_key)
    subject_count: dict[str, int] = {}
    kept: list[dict] = []

    for session in sorted_sessions:
        sid = _safe_str(session.get("subject_id"), default="__unknown__")
        count = subject_count.get(sid, 0)
        if count < 2:
            kept.append(session)
            subject_count[sid] = count + 1
        else:
            label = f"{sid} (order={session.get('order', '?')}, subtopic={session.get('subtopic_id', '?')})"
            corrections.append(
                f"Rule A: removed extra session for subject '{sid}' — already has 2 sessions. "
                f"Dropped: {label}"
            )

    return kept


def _rule_b_subject_spread(
    sessions: list[dict],
    subtopic_coverage: dict,
    warnings: list[str],
) -> None:
    """
    Rule B — Subject spread: flag a warning if fewer than 3 distinct subjects
    are scheduled AND other subjects have content to cover. No auto-fix.
    """
    scheduled_subjects = {
        _safe_str(s.get("subject_id"))
        for s in sessions
        if s.get("subject_id")
    }
    n_scheduled = len(scheduled_subjects)

    if n_scheduled >= 3:
        return  # Fine — nothing to warn about

    # Check how many other subjects have actionable content
    unscheduled_with_content: list[str] = []
    for subject_id, coverage in subtopic_coverage.items():
        if subject_id in scheduled_subjects:
            continue
        has_untested = bool(coverage.get("untested"))
        has_retest = bool(coverage.get("needs_retest"))
        if has_untested or has_retest:
            unscheduled_with_content.append(subject_id)

    if unscheduled_with_content:
        warnings.append(
            f"Rule B: only {n_scheduled} subject(s) scheduled "
            f"({', '.join(sorted(scheduled_subjects)) or 'none'}). "
            f"Subjects with untested/needs-retest content not scheduled: "
            f"{', '.join(sorted(unscheduled_with_content))}. "
            "Consider regenerating the plan."
        )


def _rule_c_time_budget(
    sessions: list[dict],
    available_hours: float,
    corrections: list[str],
) -> list[dict]:
    """
    Rule C — Time budget: trim sessions from the end (highest order = lowest
    priority) until total estimated_minutes <= available_hours * 60.
    Sessions without an `order` field are treated as lowest priority.
    """
    budget_minutes = int(available_hours * 60)

    # Sort descending by order so we trim low-priority sessions first
    def _order_key(s: dict) -> int:
        return _safe_int(s.get("order"), default=9999)

    current_sessions = sorted(sessions, key=_order_key)  # ascending
    total = sum(_safe_int(s.get("estimated_minutes"), 0) for s in current_sessions)

    if total <= budget_minutes:
        return current_sessions  # already within budget

    # Trim from the tail (highest order index = lowest priority)
    trimmed: list[dict] = list(current_sessions)  # copy
    while trimmed and total > budget_minutes:
        dropped = trimmed.pop()  # remove last (lowest priority)
        mins = _safe_int(dropped.get("estimated_minutes"), 0)
        total -= mins
        label = (
            f"subject={dropped.get('subject_id', '?')}, "
            f"subtopic={dropped.get('subtopic_id', '?')}, "
            f"order={dropped.get('order', '?')}, "
            f"minutes={mins}"
        )
        corrections.append(
            f"Rule C: trimmed session to stay within {available_hours}h budget. "
            f"Dropped: {label}"
        )

    return trimmed


def _rule_d_retest_priority(
    sessions: list[dict],
    subtopic_coverage: dict,
    warnings: list[str],
) -> None:
    """
    Rule D — needs_retest priority: for each subject that has needs_retest
    subtopics, check whether any scheduled session for that subject is for an
    untested subtopic with a lower pyq_weight than an unscheduled needs_retest
    subtopic. Log a warning; do NOT auto-swap.
    """
    # Build a set of scheduled subtopic_ids per subject
    scheduled_by_subject: dict[str, set[str]] = {}
    for session in sessions:
        sid = _safe_str(session.get("subject_id"))
        st = _safe_str(session.get("subtopic_id"))
        if sid and st:
            scheduled_by_subject.setdefault(sid, set()).add(st)

    for subject_id, coverage in subtopic_coverage.items():
        needs_retest: list[dict] = coverage.get("needs_retest", [])
        if not needs_retest:
            continue

        untested: list[dict] = coverage.get("untested", [])
        scheduled_subtopics = scheduled_by_subject.get(subject_id, set())

        # Unscheduled needs_retest subtopics
        unscheduled_retest = [
            nr for nr in needs_retest
            if nr.get("id") not in scheduled_subtopics
        ]
        if not unscheduled_retest:
            continue  # all needs_retest are scheduled — great

        # Scheduled untested subtopics with their weights
        scheduled_untested = [
            ut for ut in untested
            if ut.get("id") in scheduled_subtopics
        ]
        if not scheduled_untested:
            continue  # no untested subtopics scheduled for this subject

        # Find cases where a scheduled untested subtopic has lower weight
        # than an unscheduled needs_retest subtopic
        max_unscheduled_retest_weight = max(
            (nr.get("pyq_weight", 0.0) for nr in unscheduled_retest),
            default=0.0,
        )
        low_priority_scheduled = [
            ut for ut in scheduled_untested
            if (ut.get("pyq_weight", 0.0) or 0.0) < max_unscheduled_retest_weight
        ]

        if low_priority_scheduled:
            top_unscheduled = max(
                unscheduled_retest, key=lambda x: x.get("pyq_weight", 0.0)
            )
            low_names = ", ".join(
                f"{ut['id']} (weight={ut.get('pyq_weight', '?')})"
                for ut in low_priority_scheduled
            )
            warnings.append(
                f"Rule D: subject '{subject_id}' — unscheduled needs_retest subtopic "
                f"'{top_unscheduled['id']}' (weight={top_unscheduled.get('pyq_weight', '?')}) "
                f"has higher pyq_weight than scheduled untested subtopic(s): {low_names}. "
                "Manual review recommended — retest subtopics take priority."
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_and_fix(
    plan: dict,
    available_hours: float,
    subtopic_coverage: dict,
) -> dict:
    """
    Validate and auto-correct Claude's generated study plan against hard rules.

    Args:
        plan:               The dict returned by Claude (has 'sessions' list).
        available_hours:    Float from config, e.g. 6.0.
        subtopic_coverage:  Output of compute_subtopic_coverage() — keyed by
                            subject_id with 'untested', 'needs_retest', etc.

    Returns:
        The (possibly mutated) plan dict with a 'validation' key added.
    """
    corrections: list[str] = []
    warnings: list[str] = []

    # Guard: ensure sessions is a list; if missing/malformed, warn and skip
    raw_sessions = plan.get("sessions")
    if not isinstance(raw_sessions, list):
        warnings.append(
            "Validator: 'sessions' key missing or not a list — skipping all rule checks."
        )
        plan["validation"] = {
            "corrections": corrections,
            "warnings": warnings,
            "checked_at": _iso_now(),
        }
        return plan

    # Guard: if empty, nothing to validate
    if not raw_sessions:
        warnings.append("Validator: 'sessions' list is empty — no sessions to validate.")
        plan["validation"] = {
            "corrections": corrections,
            "warnings": warnings,
            "checked_at": _iso_now(),
        }
        return plan

    # Drop sessions with missing subject_id (malformed Claude output)
    valid_sessions = [
        s for s in raw_sessions
        if isinstance(s, dict) and s.get("subject_id")
    ]
    n_dropped_malformed = len(raw_sessions) - len(valid_sessions)
    if n_dropped_malformed > 0:
        corrections.append(
            f"Pre-check: dropped {n_dropped_malformed} session(s) with missing or "
            "null 'subject_id' field."
        )

    # --- Rule A: per-subject cap ---
    sessions_after_a = _rule_a_subject_cap(valid_sessions, corrections)

    # --- Rule B: subject spread (warning only) ---
    _rule_b_subject_spread(sessions_after_a, subtopic_coverage, warnings)

    # --- Rule C: time budget ---
    sessions_after_c = _rule_c_time_budget(sessions_after_a, available_hours, corrections)

    # --- Rule D: needs_retest priority (warning only) ---
    _rule_d_retest_priority(sessions_after_c, subtopic_coverage, warnings)

    # --- Renumber order fields sequentially ---
    # Sort by original order to preserve Claude's intent, then reassign 1-N
    def _original_order(s: dict) -> int:
        return _safe_int(s.get("order"), default=9999)

    final_sessions = sorted(sessions_after_c, key=_original_order)
    for idx, session in enumerate(final_sessions, start=1):
        session["order"] = idx

    plan["sessions"] = final_sessions

    plan["validation"] = {
        "corrections": corrections,
        "warnings": warnings,
        "checked_at": _iso_now(),
    }

    return plan
