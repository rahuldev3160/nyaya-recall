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

_PROJECT_PATH   = Path(os.getenv("PROJECT_PATH", "."))
_LEGACY_PROFILE = _PROJECT_PATH / "data" / "prep_profile.json"
_LEGACY_PLAN    = _PROJECT_PATH / "data" / "study_plan.json"
_LEGACY_CONFIG  = _PROJECT_PATH / "data" / "prep_config.json"
SYLLABUS_PATH   = _PROJECT_PATH / "data" / "syllabus.json"
PROMPT_PATH     = Path(__file__).parent.parent / "prompts" / "plan_generation.txt"
from db_helper import get_conn, DB_PATH


def _profile_path(user_id: str = "user_1") -> Path:
    return _PROJECT_PATH / "data" / "profiles" / user_id / "prep_profile.json"


def _plan_path(user_id: str = "user_1") -> Path:
    return _PROJECT_PATH / "data" / "profiles" / user_id / "study_plan.json"


def _user_plan_path(user_id: str = "user_1") -> Path:
    return _PROJECT_PATH / "data" / "profiles" / user_id / "study_plan_user.json"


def _config_path(user_id: str = "user_1") -> Path:
    return _PROJECT_PATH / "data" / "profiles" / user_id / "prep_config.json"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _get_todays_completed_subtopics() -> dict[str, dict[str, float]]:
    """
    Returns {subject_id: {subtopic_id: score}} for quiz sessions completed today
    that may not yet be in subtopic_scores (unsynced).
    Score is computed from today's session_answers (% correct, 0–100).
    """
    result: dict[str, dict[str, float]] = {}
    try:
        con = get_conn()
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


def compute_subtopic_coverage(user_id: str = "user_1") -> dict:
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

    # tested_map: {subject_id: {subtopic_id: {"score": float, "attempts": int}}}
    tested_map: dict[str, dict[str, dict]] = {}
    try:
        con = get_conn()
        rows = con.execute(
            "SELECT subject_id, subtopic_id, score, total_attempts FROM subtopic_scores WHERE user_id=?",
            (user_id,),
        ).fetchall()
        con.close()
        for subj_id, st_id, sc, attempts in rows:
            if st_id:
                tested_map.setdefault(subj_id, {})[st_id] = {"score": sc, "attempts": attempts or 0}
    except Exception:
        pass

    # Merge today's completed sessions (may not be in subtopic_scores yet if unsynced)
    todays_done = _get_todays_completed_subtopics()
    for subj_id, st_scores in todays_done.items():
        for st_id, score in st_scores.items():
            if st_id not in tested_map.get(subj_id, {}):
                tested_map.setdefault(subj_id, {})[st_id] = {"score": score, "attempts": 1}

    # CSAT excluded — user is not preparing for CSAT
    _EXCLUDED_SUBJECTS = {"csat"}

    # Shallow-tested threshold: < 3 attempts means the score is unreliable.
    # These subtopics are not "untested" but should be re-tested before the exam.
    _SHALLOW_ATTEMPTS = 3

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
            [
                {
                    "id": st,
                    "score": round(info["score"], 1),
                    "attempts": info["attempts"],
                    "pyq_weight": round(weights.get(st, 1.0), 2),
                }
                for st, info in tested_in_subj.items()
            ],
            key=lambda x: -x["pyq_weight"],
        )

        # Shallow-tested: in subtopic_scores but < 3 attempts — score is unreliable,
        # these should be re-tested like untested subtopics, especially in late sprint.
        needs_retest = sorted(
            [
                {"id": st, "score": round(info["score"], 1), "attempts": info["attempts"], "pyq_weight": round(weights.get(st, 1.0), 2)}
                for st, info in tested_in_subj.items()
                if info["attempts"] < _SHALLOW_ATTEMPTS
            ],
            key=lambda x: (-x["pyq_weight"], x["score"]),  # high PYQ weight + low score first
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
            "needs_retest_count": len(needs_retest),
            "untested":          untested,          # flat priority order — overall scheduling
            "tested":            tested_list,
            "needs_retest":      needs_retest,       # shallow-tested (< 3 attempts) — re-test priority
            "untested_by_topic": untested_by_topic,  # topic-grouped — use for balance rule
        }

    return result


def fetch_user_notes_signals(user_id: str = "user_1") -> list[dict]:
    """
    Recent per-session and per-question notes, for plan personalisation.

    Sources (additive — both are read, legacy table preserved for backward compat):
    1. session_user_notes — original session-level notes blob
    2. question_notes (ISSUE-017) — per-question notes, only rows with still_weak=1
    """
    con = get_conn()
    out: list[dict] = []

    # Source 1: legacy session-level notes
    try:
        rows = con.execute(
            """
            SELECT subtopic_id, confusion, mnemonic, still_weak, updated_at
            FROM session_user_notes
            WHERE user_id=?
            ORDER BY updated_at DESC
            LIMIT 24
            """,
            (user_id,),
        ).fetchall()
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
                    "source": "session_user_notes",
                }
            )
    except sqlite3.OperationalError:
        pass

    # Source 2: per-question notes flagged still_weak (ISSUE-017 question_notes table)
    try:
        qrows = con.execute(
            """
            SELECT subtopic_id, note_text, updated_at
            FROM question_notes
            WHERE user_id=? AND still_weak=1
            ORDER BY updated_at DESC
            LIMIT 24
            """,
            (user_id,),
        ).fetchall()
        for sub, note, upd in qrows:
            if not sub:
                continue
            out.append(
                {
                    "subtopic_id": sub,
                    "confusion_excerpt": (note or "")[:450],
                    "mnemonic_excerpt": "",
                    "still_weak": True,
                    "updated_at": upd,
                    "source": "question_notes",
                }
            )
    except sqlite3.OperationalError:
        pass

    con.close()
    return out


def load_config(user_id: str = "user_1") -> dict:
    path = _config_path(user_id)
    if not path.exists() and user_id == "user_1" and _LEGACY_CONFIG.exists():
        import shutil
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_LEGACY_CONFIG, path)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {"total_days": 10, "daily_hours": 6, "start_date": date.today().isoformat()}


def days_remaining(user_id: str = "user_1") -> int:
    config = load_config(user_id)
    start_str = config.get("start_date") or date.today().isoformat()
    total = int(config.get("total_days", 10))
    start = date.fromisoformat(start_str)
    elapsed = max(0, (date.today() - start).days)
    return max(1, total - elapsed)


def current_day_number(user_id: str = "user_1") -> int:
    config = load_config(user_id)
    start_str = config.get("start_date") or date.today().isoformat()
    start = date.fromisoformat(start_str)
    elapsed = max(0, (date.today() - start).days)
    return elapsed + 1


def generate_plan(available_hours: float | None = None, user_id: str = "user_1") -> dict:
    profile_path = _profile_path(user_id)
    if not profile_path.exists() and user_id == "user_1" and _LEGACY_PROFILE.exists():
        import shutil
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_LEGACY_PROFILE, profile_path)

    if not profile_path.exists():
        print("No prep profile found. Run batch_analyse.py first.")
        return {"message": "No prep profile yet. Complete a diagnostic session and run batch analysis first."}

    try:
        profile = json.loads(profile_path.read_text())
    except Exception:
        return {"message": "Prep profile is corrupted. Run batch analysis again to rebuild it."}

    last_updated = profile.get("last_updated")
    if last_updated:
        try:
            age_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(last_updated)).total_seconds() / 3600
            if age_hours > 12:
                print(f"⚠️  WARNING: prep_profile.json is {age_hours:.0f}h old. Run batch_analyse.py first for an accurate plan.")
        except Exception:
            pass

    config = load_config(user_id)
    if available_hours is None:
        available_hours = float(config.get("daily_hours", 6))

    day_number = current_day_number(user_id)
    remaining = days_remaining(user_id)
    total_days = int(config.get("total_days", 10))

    subtopic_coverage = compute_subtopic_coverage(user_id)
    user_notes_signals = fetch_user_notes_signals(user_id)

    # Strip topics[] from profile — planner gets topic data via subtopic_coverage instead,
    # and sending both doubles the token cost for no benefit.
    slim_profile = {
        k: (
            {sid: {fk: fv for fk, fv in sdata.items() if fk != "topics"} for sid, sdata in v.items()}
            if k == "subjects" else v
        )
        for k, v in profile.items()
    }

    prompt_template = PROMPT_PATH.read_text()
    prompt = (
        prompt_template
        .replace("{{prep_profile}}",       json.dumps(slim_profile, indent=2))
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
        max_tokens=8192,
        betas=["output-128k-2025-02-19"],
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

    # Deterministic rule enforcement: validate and auto-fix Claude's output.
    try:
        from plan_validator import validate_and_fix
        plan = validate_and_fix(plan, available_hours, subtopic_coverage)
        corr = plan.get("validation", {}).get("corrections", [])
        warn = plan.get("validation", {}).get("warnings", [])
        if corr:
            print(f"  ✅ Validator auto-fixed {len(corr)} rule violation(s):")
            for c in corr: print(f"     - {c}")
        if warn:
            print(f"  ⚠️  Validator warnings ({len(warn)}):")
            for w in warn: print(f"     - {w}")
    except Exception as e:
        print(f"  ⚠️  Plan validator skipped: {e}")

    # Safety filter: strip any CSAT sessions Claude may have included.
    # CSAT is a completely separate system with its own flow at /csat.
    sessions_before = plan.get("sessions", [])
    sessions_after = [s for s in sessions_before if s.get("subject_id", "").lower() != "csat"]
    if len(sessions_after) < len(sessions_before):
        removed = len(sessions_before) - len(sessions_after)
        print(f"  ⚠ Stripped {removed} CSAT session(s) from plan — CSAT is a separate system.")
        plan["sessions"] = sessions_after

    plan_p = _plan_path(user_id)
    plan_p.parent.mkdir(parents=True, exist_ok=True)
    plan_p.write_text(json.dumps(plan, indent=2))
    # Clear any user-edited plan so the fresh AI plan takes over
    user_plan_p = _user_plan_path(user_id)
    if user_plan_p.exists():
        user_plan_p.unlink()
        print("🗑️  Cleared user-edited plan — fresh AI plan is now active.")
    print(f"✅ Plan generated for Day {day_number}/{total_days}. Sessions: {len(plan.get('sessions', []))}")
    return plan


if __name__ == "__main__":
    import sys
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else None
    generate_plan(hours)
