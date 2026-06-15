"""Auto-generated usernames in format AdjectiveUpscTerm_NN (e.g. BoldPolity_07)."""
import random
import re
from backend.db import get_conn

_ADJECTIVES = [
    "Swift", "Bold", "Sharp", "Deep", "Clear", "Calm", "Keen",
    "Bright", "Quick", "Solid", "Wise", "Firm", "Steady", "Just",
    "Rare", "Prime", "Core", "True", "Pure", "Stark",
]

_TERMS = [
    "Polity", "Economy", "History", "Geography", "Science", "Enviro",
    "Ethics", "Mains", "Prelims", "Aspirant", "Scholar", "Recall",
    "IAS", "Civils", "Admin", "UPSC",
]

_VALID_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")


def generate() -> str:
    adj = random.choice(_ADJECTIVES)
    term = random.choice(_TERMS)
    num = random.randint(10, 99)
    return f"{adj}{term}_{num:02d}"


def is_available(username: str) -> bool:
    with get_conn() as con:
        return con.execute(
            "SELECT 1 FROM user_profiles WHERE username = ?", [username]
        ).fetchone() is None


def is_valid(username: str) -> bool:
    return bool(_VALID_RE.match(username))


def generate_options(count: int = 3) -> list[str]:
    """Return `count` unique available username options."""
    options: list[str] = []
    attempts = 0
    while len(options) < count and attempts < 60:
        candidate = generate()
        if is_available(candidate) and candidate not in options:
            options.append(candidate)
        attempts += 1
    return options


def claim(user_id: str, username: str) -> bool:
    """Claim a username. Returns False if taken or invalid."""
    if not is_valid(username):
        raise ValueError("Username must be 3–30 alphanumeric/underscore chars")
    try:
        with get_conn() as con:
            con.execute(
                "UPDATE user_profiles SET username=? WHERE user_id=?",
                [username, user_id],
            )
        return True
    except Exception:
        return False
