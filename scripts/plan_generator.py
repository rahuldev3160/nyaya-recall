"""
Generates tomorrow's study plan from current prep_profile.
Called after batch_analyse.py completes.
Writes to data/study_plan.json.
"""
from __future__ import annotations
import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, date, timezone
import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

PROFILE_PATH  = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "prep_profile.json"
PLAN_PATH     = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "study_plan.json"
CONFIG_PATH   = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "prep_config.json"
SYLLABUS_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "syllabus.json"
PROMPT_PATH   = Path(__file__).parent.parent / "prompts" / "plan_generation.txt"
DB_PATH       = os.getenv("DB_PATH", "data/upsc.db")

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _get_todays_completed_subtopics() -> dict[str, dict[str, float]]:
    """
    Returns {subject_id: {subtopic_id: score}} for quiz sessions completed today
    that may not yet be in subtopic_scores (unsynced).
    Score is computed from today's session_answers (% correct, 0–100).
    """
    result: dict[str, dict[str, float]] = {}
    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            """
            SELECT sa.subject_id, sa.subtopic_id,
                   COUNT(*) AS total,
                   SUM(CASE WHEN sa.is_correct = 1 THEN 1 ELSE 0 END) AS correct
            FROM session_answers sa
            JOIN quiz_sessions qs ON qs.id = sa.session_id
            WHERE qs.end_time IS NOT NULL
            AND substr(qs.start_time, 1, 10) = date('now')
            AND sa.subtopic_id IS NOT NULL
            AND (sa.skipped IS NULL OR sa.skipped = 0)
            GROUP BY sa.subject_id, sa.subtopic_id
            """
        ).fetchall()
        con.close()
        for subj_id, st_id, total, correct in rows:
            if subj_id and st_id and total:
                result.setdefault(subj_id, {})[st_id] = round((correct / total) * 100, 1)
    except Exception:
        pass
    return result


def compute_subtopic_coverage() -> dict:
    """
    Returns {subject_id: {total, untested: [{id, pyq_weight}], tested: [{id, score, pyq_weight}]}}.
    untested list is sorted by pyq_weight descending — this is the scheduling priority order.
    Merges today's completed quiz sessions (even unsynced) so re-planning mid-day
    doesn't re-schedule subtopics already done this session.
    """
    try:
        syllabus = json.loads(SYLLABUS_PATH.read_text())
    except Exception:
        return {}

    try:
        from priority_scorer import compute_all_priorities
        weights = compute_all_priorities()
    except Exception:
        weights = {}

    tested_map: dict[str, dict[str, float]] = {}
    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            "SELECT subject_id, subtopic_id, score FROM subtopic_scores WHERE user_id='user_1'"
        ).fetchall()
        con.close()
        for subj_id, st_id, sc in rows:
            if st_id:
                tested_map.setdefault(subj_id, {})[st_id] = sc
    except Exception:
        pass

    # Merge today's completed sessions (may not be in subtopic_scores yet if unsynced)
    todays_done = _get_todays_completed_subtopics()
    for subj_id, st_scores in todays_done.items():
        for st_id, score in st_scores.items():
            if st_id not in tested_map.get(subj_id, {}):
                tested_map.setdefault(subj_id, {})[st_id] = score

    # CSAT excluded — user is not preparing for CSAT
    _EXCLUDED_SUBJECTS = {"csat"}

    result: dict = {}
    for subj in syllabus.get("subjects", []):
        sid = subj["id"]
        if sid in _EXCLUDED_SUBJECTS:
            continue
        all_subs = [
            st["id"]
            for topic in subj.get("topics", [])
            for st in topic.get("subtopics", [])
        ]
        tested_in_subj = tested_map.get(sid, {})

        untested = sorted(
            [{"id": st, "pyq_weight": round(weights.get(st, 1.0), 2)} for st in all_subs if st not in tested_in_subj],
            key=lambda x: -x["pyq_weight"],
        )
        tested_list = sorted(
            [{"id": st, "score": round(sc, 1), "pyq_weight": round(weights.get(st, 1.0), 2)} for st, sc in tested_in_subj.items()],
            key=lambda x: -x["pyq_weight"],
        )

        # Topic-grouped view of untested subtopics — used for topic-balance scheduling rule
        untested_by_topic: list[dict] = []
        for topic in subj.get("topics", []):
            topic_untested = [
                {"id": st["id"], "pyq_weight": round(weights.get(st["id"], 1.0), 2)}
                for st in topic.get("subtopics", [])
                if st["id"] not in tested_in_subj
            ]
            if not topic_untested:
                continue  # skip fully-tested topics
            topic_untested.sort(key=lambda x: -x["pyq_weight"])
            topic_weight = round(sum(x["pyq_weight"] for x in topic_untested), 2)
            untested_by_topic.append({
                "topic_id":           topic["id"],
                "topic_name":         topic.get("name", topic["id"]),
                "topic_pyq_weight":   topic_weight,
                "untested_subtopics": topic_untested,
            })
        untested_by_topic.sort(key=lambda t: -t["topic_pyq_weight"])

        result[sid] = {
            "total_subtopics":   len(all_subs),
            "untested_count":    len(untested),
            "tested_count":      len(tested_list),
            "untested":          untested,         # flat priority order — overall scheduling
            "tested":            tested_list,
            "untested_by_topic": untested_by_topic, # topic-grouped — use for balance rule
        }

    return result


def fetch_user_notes_signals() -> list[dict]:
    """
    Recent parallel session notes (per quiz session), for plan personalisation.
    """
    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            """
            SELECT subtopic_id, confusion, mnemonic, still_weak, updated_at
            FROM session_user_notes
            WHERE user_id='user_1'
            ORDER BY updated_at DESC
            LIMIT 24
            """
        ).fetchall()
        con.close()
    except sqlite3.OperationalError:
        return []

    out: list[dict] = []
    for sub, conf, mnem, weak, upd in rows:
        if not sub:
            continue
        out.append(
            {
                "subtopic_id": sub,
                "confusion_excerpt": (conf or "")[:450],
                "mnemonic_excerpt": (mnem or "")[:220],
                "still_weak": bool(weak),
                "updated_at": upd,
            }
        )
    return out


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {"total_days": 10, "daily_hours": 6, "start_date": date.today().isoformat()}


def days_remaining() -> int:
    config = load_config()
    start_str = config.get("start_date") or date.today().isoformat()
    total = int(config.get("total_days", 10))
    start = date.fromisoformat(start_str)
    elapsed = max(0, (date.today() - start).days)
    return max(1, total - elapsed)


def current_day_number() -> int:
    config = load_config()
    start_str = config.get("start_date") or date.today().isoformat()
    start = date.fromisoformat(start_str)
    elapsed = max(0, (date.today() - start).days)
    return elapsed + 1


def generate_plan(available_hours: float | None = None) -> dict:
    if not PROFILE_PATH.exists():
        print("No prep profile found. Run batch_analyse.py first.")
        return {"message": "No prep profile yet. Complete a diagnostic session and run batch analysis first."}

    try:
        profile = json.loads(PROFILE_PATH.read_text())
    except Exception:
        return {"message": "Prep profile is corrupted. Run batch analysis again to rebuild it."}

    config = load_config()
    if available_hours is None:
        available_hours = float(config.get("daily_hours", 6))

    day_number = current_day_number()
    remaining = days_remaining()
    total_days = int(config.get("total_days", 10))

    subtopic_coverage = compute_subtopic_coverage()
    user_notes_signals = fetch_user_notes_signals()

    prompt_template = PROMPT_PATH.read_text()
    prompt = (
        prompt_template
        .replace("{{prep_profile}}",       json.dumps(profile, indent=2))
        .replace("{{subtopic_coverage}}",  json.dumps(subtopic_coverage, indent=2))
        .replace("{{user_notes_signals}}", json.dumps(user_notes_signals, indent=2))
        .replace("{{day_number}}",         str(day_number))
        .replace("{{days_remaining}}",     str(remaining))
        .replace("{{total_days}}",         str(total_days))
        .replace("{{available_hours}}",    str(available_hours))
        .replace("{{phase}}",              profile.get("phase", "diagnostic"))
    )

    response = client.messages.create(
        model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()

    try:
        start_idx, end_idx = raw.find("{"), raw.rfind("}") + 1
        plan = json.loads(raw[start_idx:end_idx])
    except Exception as e:
        print(f"Plan JSON parse failed: {e}")
        return {"message": "Plan generation failed — Claude returned unexpected format. Try again."}

    plan["generated_at"] = datetime.now(timezone.utc).isoformat()
    plan["day_number"] = day_number
    plan["days_remaining"] = remaining
    plan["total_days"] = total_days

    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(json.dumps(plan, indent=2))
    print(f"✅ Plan generated for Day {day_number}/{total_days}. Sessions: {len(plan.get('sessions', []))}")
    return plan


if __name__ == "__main__":
    import sys
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else None
    generate_plan(hours)
