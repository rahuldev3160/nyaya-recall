"""Streak tracking with user-configurable shield (0 / 1 / 2 grace days per week)."""
from datetime import date, timedelta
from backend.db import get_conn


def get_or_create(user_id: str) -> dict:
    with get_conn() as con:
        row = con.execute(
            "SELECT * FROM streak_config WHERE user_id = ?", [user_id]
        ).fetchone()
        if row:
            return dict(row)
        monday = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        con.execute(
            """INSERT INTO streak_config
               (user_id, shield_enabled, max_grace_per_week, grace_used_this_week,
                week_start_date, current_streak, longest_streak, last_activity_date)
               VALUES (?, 1, 1, 0, ?, 0, 0, NULL)""",
            [user_id, monday],
        )
    return get_or_create(user_id)


def record_activity(user_id: str) -> dict:
    """Call once per completed quiz session. Returns updated streak state."""
    cfg = get_or_create(user_id)
    today = date.today().isoformat()

    if cfg["last_activity_date"] == today:
        return cfg  # already studied today, no change needed

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    monday = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    # Reset weekly grace on new week
    if cfg["week_start_date"] != monday:
        cfg["grace_used_this_week"] = 0
        cfg["week_start_date"] = monday

    if cfg["last_activity_date"] == yesterday:
        cfg["current_streak"] += 1
    elif (
        cfg["shield_enabled"]
        and cfg["grace_used_this_week"] < cfg["max_grace_per_week"]
    ):
        cfg["grace_used_this_week"] += 1
        cfg["current_streak"] += 1
    else:
        cfg["longest_streak"] = max(cfg["longest_streak"], cfg["current_streak"])
        cfg["current_streak"] = 1

    cfg["last_activity_date"] = today
    cfg["longest_streak"] = max(cfg["longest_streak"], cfg["current_streak"])
    cfg["updated_at"] = today

    with get_conn() as con:
        con.execute(
            """UPDATE streak_config SET
               shield_enabled=?, max_grace_per_week=?, grace_used_this_week=?,
               week_start_date=?, current_streak=?, longest_streak=?,
               last_activity_date=?, updated_at=?
               WHERE user_id=?""",
            [
                cfg["shield_enabled"], cfg["max_grace_per_week"],
                cfg["grace_used_this_week"], cfg["week_start_date"],
                cfg["current_streak"], cfg["longest_streak"],
                cfg["last_activity_date"], cfg["updated_at"],
                user_id,
            ],
        )
    return cfg


def update_config(user_id: str, shield_enabled: bool, max_grace_per_week: int) -> dict:
    """User adjusts their own accountability settings. max_grace_per_week: 0, 1, or 2."""
    if max_grace_per_week not in (0, 1, 2):
        raise ValueError("max_grace_per_week must be 0, 1, or 2")
    get_or_create(user_id)  # ensure row exists
    with get_conn() as con:
        con.execute(
            "UPDATE streak_config SET shield_enabled=?, max_grace_per_week=? WHERE user_id=?",
            [int(shield_enabled), max_grace_per_week, user_id],
        )
    return get_or_create(user_id)
