"""SM-2 spaced repetition with confidence modifier."""
from datetime import datetime, timedelta


def compute_srs_update(
    interval_days: int,
    ease_factor: float,
    repetition_count: int,
    is_correct: bool,
    confidence: str,
) -> dict:
    """
    confidence: 'sure' | 'unsure' | 'guess'
    'sure' + wrong gets a harsher penalty — surfaces dangerous blind spots faster.
    """
    if is_correct and confidence == "sure":
        q = 5
    elif is_correct and confidence == "unsure":
        q = 4
    elif is_correct and confidence == "guess":
        q = 3
    elif not is_correct and confidence == "sure":
        q = 2  # overconfidence — harsher reset
    elif not is_correct and confidence == "unsure":
        q = 1
    else:
        q = 0

    new_ease = max(1.3, ease_factor + 0.1 - (5 - q) * 0.08)
    n = repetition_count

    if q < 3:
        new_interval = 1
        n = 0
    elif n == 0:
        new_interval = 1
    elif n == 1:
        new_interval = 6
    else:
        new_interval = round(interval_days * new_ease)

    next_review = (datetime.utcnow() + timedelta(days=new_interval)).isoformat()

    return {
        "interval_days": new_interval,
        "ease_factor": round(new_ease, 4),
        "repetition_count": n + 1,
        "next_review_at": next_review,
    }
