"""
End-of-day batch analysis. Called when user clicks "Sync & Plan".
Uses session summaries as primary input (~80% token reduction vs raw answers).
Fetches raw answers only for subtopics that are persistently weak (2+ consecutive sessions).
"""
from __future__ import annotations
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = os.getenv("DB_PATH", "data/upsc.db")
PROFILE_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "prep_profile.json"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "batch_analysis.txt"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_profile() -> dict:
    if PROFILE_PATH.exists():
        try:
            return json.loads(PROFILE_PATH.read_text())
        except Exception:
            pass
    return {"subjects": {}, "overall_readiness": 0, "phase": "diagnostic",
            "last_updated": None, "day_number": 1}


def save_profile(profile: dict):
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile["last_updated"] = datetime.now(timezone.utc).isoformat()
    PROFILE_PATH.write_text(json.dumps(profile, indent=2))


def get_unsynced_summaries() -> tuple[list[dict], list[str]]:
    """Fetch session summaries for all unsynced sessions.
    Falls back to minimal raw stats if a summary wasn't computed yet."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    sessions = con.execute(
        "SELECT * FROM quiz_sessions WHERE synced=0 AND end_time IS NOT NULL"
    ).fetchall()

    summaries: list[dict] = []
    session_ids: list[str] = []
    for s in sessions:
        session_ids.append(s["id"])
        row = con.execute(
            "SELECT * FROM session_summaries WHERE session_id=?", (s["id"],)
        ).fetchone()
        if row:
            summaries.append(dict(row))
        else:
            # Summary missing — compute minimal version from raw answers
            answers = con.execute(
                "SELECT subject_id, subtopic_id, is_correct, skipped FROM session_answers WHERE session_id=?",
                (s["id"],)
            ).fetchall()
            total = len(answers)
            correct = sum(1 for a in answers if a["is_correct"] and not a["skipped"])
            summaries.append({
                "session_id": s["id"],
                "subject_id": s["subject_id"],
                "session_date": (s["end_time"] or "")[:10],
                "total_questions": total,
                "correct": correct,
                "accuracy_pct": round((correct / max(total, 1)) * 100, 1),
                "note": "summary_missing_raw_fallback",
            })
    con.close()
    return summaries, session_ids


def get_persistently_weak_subtopics(session_ids: list[str]) -> list[str]:
    """Subtopics that appear in weak_subtopics of 2+ of the given sessions."""
    if not session_ids:
        return []
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    weak_count: dict[str, int] = {}
    for sid in session_ids:
        row = con.execute(
            "SELECT weak_subtopics FROM session_summaries WHERE session_id=?", (sid,)
        ).fetchone()
        if row and row["weak_subtopics"]:
            for sub in _safe_json_list(row["weak_subtopics"]):
                weak_count[sub] = weak_count.get(sub, 0) + 1
    con.close()
    return [sub for sub, cnt in weak_count.items() if cnt >= 2]


def get_raw_answers_for_subtopics(session_ids: list[str], subtopics: list[str]) -> list[dict]:
    """Raw answers for persistent-weak subtopics only (deep-drill data)."""
    if not subtopics or not session_ids:
        return []
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    ph_s = ",".join("?" * len(session_ids))
    ph_t = ",".join("?" * len(subtopics))
    rows = con.execute(
        f"SELECT session_id, question_text, correct_answer, user_answer, is_correct, "
        f"subtopic_id, subject_id FROM session_answers "
        f"WHERE session_id IN ({ph_s}) AND subtopic_id IN ({ph_t})",
        session_ids + subtopics,
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def _safe_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []


def mark_synced(session_ids: list[str]):
    con = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" * len(session_ids))
    con.execute(f"UPDATE quiz_sessions SET synced=1 WHERE id IN ({placeholders})", session_ids)
    con.commit()
    con.close()


def run_analysis() -> dict:
    summaries, session_ids = get_unsynced_summaries()
    if not session_ids:
        print("No unsynced sessions found.")
        return {}

    print(f"Analysing {len(session_ids)} session(s) via summaries...")
    profile = load_profile()

    persistent_weak = get_persistently_weak_subtopics(session_ids)
    deep_drill = get_raw_answers_for_subtopics(session_ids, persistent_weak)

    if persistent_weak:
        print(f"  Deep-drill raw data for {len(persistent_weak)} persistently weak subtopic(s)")

    prompt_template = PROMPT_PATH.read_text()
    prompt = (
        prompt_template
        .replace("{{current_profile}}", json.dumps(profile, indent=2))
        .replace("{{session_summaries}}", json.dumps(summaries, indent=2))
        .replace("{{deep_drill_subtopics}}", json.dumps(persistent_weak))
        .replace("{{deep_drill_answers}}", json.dumps(deep_drill, indent=2))
    )

    response = client.messages.create(
        model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    analysis = json.loads(raw[start:end])

    for sub_update in analysis.get("subject_updates", []):
        sid = sub_update["subject_id"]
        profile["subjects"][sid] = sub_update

    profile["overall_readiness"] = analysis.get("overall_readiness", profile["overall_readiness"])
    profile["phase"] = analysis.get("phase_recommendation", profile["phase"])
    profile["last_analysis"] = analysis.get("summary", "")
    profile["priority_focus"] = analysis.get("priority_focus", [])
    profile["time_estimates"] = analysis.get("time_estimates", {})
    profile["day_number"] = profile.get("day_number", 1) + 1

    # Aggregate expansion signals across all synced sessions
    all_expanded: list[str] = []
    for s in summaries:
        all_expanded.extend(_safe_json_list(s.get("expanded_subtopics")))
    if all_expanded:
        profile["expanded_interests"] = list(dict.fromkeys(all_expanded))

    save_profile(profile)
    mark_synced(session_ids)

    print(f"✅ Analysis complete. Overall readiness: {profile['overall_readiness']}%")
    print(f"   Phase: {profile['phase']}")
    print(f"   Summary: {profile['last_analysis']}")
    return analysis


if __name__ == "__main__":
    run_analysis()
