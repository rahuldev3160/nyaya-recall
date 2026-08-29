"""Self-Assessment Reliability (SAR) system."""
import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = os.getenv("DB_PATH", "data/upsc.db")

SAR_MIN = 0.20
SAR_MAX = 0.90
SAR_DEFAULT = 0.50

CLAIMED_LEVELS = {"strong": 70.0, "very_strong": 85.0, "expert": 95.0}


def get_sar(user_id: str = "user_1") -> float:
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT sar FROM sar_scores WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return row[0] if row else SAR_DEFAULT


def compute_effective_level(claimed_label: str, validation_score: float, user_id: str = "user_1") -> dict:
    sar = get_sar(user_id)
    claimed_level = CLAIMED_LEVELS.get(claimed_label, 70.0)
    effective = (validation_score * (1 - sar)) + (claimed_level * sar)
    discrepancy = abs(claimed_level - validation_score)

    if discrepancy < 10:
        delta = +0.05
    elif discrepancy < 20:
        delta = 0.0
    elif discrepancy < 35:
        delta = -0.05
    else:
        delta = -0.10

    new_sar = max(SAR_MIN, min(SAR_MAX, sar + delta))
    _update_sar(user_id, new_sar)

    return {
        "claimed_level": claimed_level,
        "validation_score": round(validation_score, 1),
        "effective_level": round(effective, 1),
        "sar_before": round(sar, 2),
        "sar_after": round(new_sar, 2),
        "discrepancy": round(discrepancy, 1),
    }


def record_attestation(subject_id: str, result: dict, user_id: str = "user_1") -> None:
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO subject_attestations
        (user_id, subject_id, claimed_level, validation_score, effective_level, sar_at_time)
        VALUES (?,?,?,?,?,?)
    """, (user_id, subject_id, result["claimed_level"], result["validation_score"],
          result["effective_level"], result["sar_before"]))
    con.execute("""
        INSERT INTO sar_scores (user_id, sar, total_claims, updated_at) VALUES (?, ?, 1, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            sar=excluded.sar, total_claims=sar_scores.total_claims+1, updated_at=excluded.updated_at
    """, (user_id, result["sar_after"], datetime.now(timezone.utc).isoformat()))
    con.commit()
    con.close()


def _update_sar(user_id: str, new_sar: float) -> None:
    # Was a plain UPDATE ... WHERE user_id=?, which silently affects 0 rows for
    # any user_id that has no existing sar_scores row (B-4: only 'user_1' is ever
    # seeded) -- a second real user's SAR was computed but never persisted.
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO sar_scores (user_id, sar, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET sar=excluded.sar, updated_at=excluded.updated_at
    """, (user_id, new_sar, datetime.now(timezone.utc).isoformat()))
    con.commit()
    con.close()
