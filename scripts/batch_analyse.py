"""
End-of-day batch analysis. Called when user clicks "Sync & Plan".

Scoring architecture:
- Numerical scores (subject readiness, overall readiness) are computed deterministically
  in Python using PYQ priority weights and syllabus coverage. Claude does NOT determine
  numbers — only insight text, trend labels, and phase recommendations.
- Untested subtopics are treated as gaps (score 0) until the user proves otherwise.
- Subject readiness = Σ(tested_score × PYQ_weight) / Σ(all_subtopic_weights in subject)
- Overall readiness = Σ(subject_readiness × avg_questions_per_year) / Σ(avg_q_per_year)
"""
from __future__ import annotations
import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, date
import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# priority_scorer lives in the same scripts/ directory
sys.path.insert(0, str(Path(__file__).parent))
from priority_scorer import compute_all_priorities

DB_PATH       = os.getenv("DB_PATH", "data/upsc.db")
PROFILE_PATH  = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "prep_profile.json"
CONFIG_PATH   = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "prep_config.json"
SYLLABUS_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "syllabus.json"
PROMPT_PATH   = Path(__file__).parent.parent / "prompts" / "batch_analysis.txt"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

DEFAULT_WEIGHT = 1.0   # uniform weight for subtopics with no PYQ appearance
MIN_WEIGHT     = 0.5   # floor so every subtopic counts at least a little

# Quiz generation uses short subject IDs; syllabus uses canonical IDs — map them here
SUBJECT_ALIASES: dict[str, str] = {
    "history": "history_amac",
}


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


# ---------------------------------------------------------------------------
# Weighted readiness — deterministic, no LLM involved
# ---------------------------------------------------------------------------

def _build_syllabus_map() -> dict[str, dict]:
    """Returns {subject_id: {all_subtopics: [id,...], avg_questions_per_year: int}}"""
    try:
        syllabus = json.loads(SYLLABUS_PATH.read_text())
    except Exception:
        return {}
    # CSAT excluded — user is not preparing for CSAT
    _EXCLUDED = {"csat"}

    result: dict[str, dict] = {}
    for subject in syllabus.get("subjects", []):
        sid = subject["id"]
        if sid in _EXCLUDED:
            continue
        subtopics: list[str] = []
        for topic in subject.get("topics", []):
            for st in topic.get("subtopics", []):
                subtopics.append(st["id"])
        result[sid] = {
            "all_subtopics": subtopics,
            "avg_questions_per_year": subject.get("avg_questions_per_year", 10),
        }
    return result


def _get_tested_subtopics() -> dict[str, dict[str, float]]:
    """Returns {subject_id: {subtopic_id: score}} from subtopic_scores table."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT subject_id, subtopic_id, score FROM subtopic_scores WHERE user_id='user_1'"
    ).fetchall()
    con.close()
    tested: dict[str, dict[str, float]] = {}
    for row in rows:
        sid = SUBJECT_ALIASES.get(row["subject_id"], row["subject_id"])
        tested.setdefault(sid, {})[row["subtopic_id"]] = row["score"]
    return tested


def compute_weighted_readiness() -> dict:
    """
    Pre-computes authoritative readiness scores before the LLM call.

    For every subject in the syllabus:
      - Each subtopic has a PYQ priority weight (recency-decayed question frequency).
      - Tested subtopics contribute: score × weight.
      - Untested subtopics contribute: 0 (assumed gap — untested = weak).
      - Subject readiness = total weighted score / sum of all weights.
      - Coverage = tested_count / total_subtopic_count.

    Overall readiness = average of subject readiness weighted by avg_questions_per_year.
    """
    syllabus_map = _build_syllabus_map()
    if not syllabus_map:
        return {}

    pyq_weights = compute_all_priorities()
    tested = _get_tested_subtopics()

    subject_readiness: dict[str, dict] = {}

    for sid, info in syllabus_map.items():
        all_subtopics = info["all_subtopics"]
        if not all_subtopics:
            continue

        total_weight   = 0.0
        weighted_score = 0.0
        tested_count   = 0
        all_subtopics_set = set(all_subtopics)
        tested_in_subject = tested.get(sid, {})

        for st_id in all_subtopics:
            w = max(pyq_weights.get(st_id, DEFAULT_WEIGHT), MIN_WEIGHT)
            total_weight += w
            if st_id in tested_in_subject:
                weighted_score += tested_in_subject[st_id] * w
                tested_count += 1
            # untested → score 0, contributes 0 to weighted_score

        # Credit quiz subtopics whose IDs don't match any syllabus subtopic
        # (plan generator uses its own naming e.g. "indus_valley_civilization"
        # while syllabus uses "ivc_sites_features"). Give them average subject weight.
        extra_tested = {st for st in tested_in_subject if st not in all_subtopics_set}
        if extra_tested and all_subtopics:
            avg_w = total_weight / len(all_subtopics)
            for st_id in extra_tested:
                w = max(pyq_weights.get(st_id, avg_w), MIN_WEIGHT)
                total_weight   += w
                weighted_score += tested_in_subject[st_id] * w
                tested_count   += 1

        readiness = (weighted_score / total_weight) if total_weight > 0 else 0.0
        coverage  = tested_count / len(all_subtopics)

        subject_readiness[sid] = {
            "subject_id":         sid,
            "weighted_readiness": round(readiness, 1),
            "coverage_pct":       round(coverage * 100, 1),
            "tested_subtopics":   tested_count,
            "total_subtopics":    len(all_subtopics),
            "tested_scores": {
                st: round(tested[sid][st], 1)
                for st in tested.get(sid, {})
            },
        }

    total_q = sum(
        syllabus_map[sid]["avg_questions_per_year"]
        for sid in subject_readiness
    )
    overall = (
        sum(
            subject_readiness[sid]["weighted_readiness"]
            * syllabus_map[sid]["avg_questions_per_year"]
            for sid in subject_readiness
        ) / max(total_q, 1)
    )

    return {
        "subjects":          subject_readiness,
        "overall_readiness": round(overall, 1),
        "note": (
            "Scores are PYQ-weighted across ALL subtopics. "
            "Untested subtopics score 0. Coverage shows how much of each subject has been tested."
        ),
    }


# ---------------------------------------------------------------------------
# Session data helpers
# ---------------------------------------------------------------------------

def get_unsynced_summaries() -> tuple[list[dict], list[str]]:
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
            answers = con.execute(
                "SELECT subject_id, subtopic_id, is_correct, skipped FROM session_answers "
                "WHERE session_id=?", (s["id"],)
            ).fetchall()
            total   = len(answers)
            correct = sum(1 for a in answers if a["is_correct"] and not a["skipped"])
            summaries.append({
                "session_id":      s["id"],
                "subject_id":      s["subject_id"],
                "session_date":    (s["end_time"] or "")[:10],
                "total_questions": total,
                "correct":         correct,
                "accuracy_pct":    round((correct / max(total, 1)) * 100, 1),
                "note":            "summary_missing_raw_fallback",
            })
    con.close()
    return summaries, session_ids


def get_persistently_weak_subtopics(session_ids: list[str]) -> list[str]:
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
    con.execute(
        f"UPDATE quiz_sessions SET synced=1 WHERE id IN ({placeholders})", session_ids
    )
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Main analysis runner
# ---------------------------------------------------------------------------

def run_analysis() -> dict:
    summaries, session_ids = get_unsynced_summaries()
    if not session_ids:
        print("No unsynced sessions found.")
        return {}

    print(f"Analysing {len(session_ids)} session(s) via summaries...")
    profile = load_profile()

    # Step 1: deterministic weighted readiness (authoritative numbers)
    coverage_report = compute_weighted_readiness()
    print(f"  Weighted overall readiness: {coverage_report.get('overall_readiness', '?')}%")
    for sid, s in coverage_report.get("subjects", {}).items():
        print(f"  {sid}: {s['weighted_readiness']}% "
              f"(coverage {s['coverage_pct']}% — "
              f"{s['tested_subtopics']}/{s['total_subtopics']} subtopics tested)")

    # Step 2: LLM call for insight text only
    persistent_weak = get_persistently_weak_subtopics(session_ids)
    deep_drill      = get_raw_answers_for_subtopics(session_ids, persistent_weak)

    if persistent_weak:
        print(f"  Deep-drill raw data for {len(persistent_weak)} persistently weak subtopic(s)")

    prompt_template = PROMPT_PATH.read_text()
    prompt = (
        prompt_template
        .replace("{{current_profile}}",      json.dumps(profile, indent=2))
        .replace("{{session_summaries}}",    json.dumps(summaries, indent=2))
        .replace("{{deep_drill_subtopics}}", json.dumps(persistent_weak))
        .replace("{{deep_drill_answers}}",   json.dumps(deep_drill, indent=2))
        .replace("{{coverage_report}}",      json.dumps(coverage_report, indent=2))
    )

    response = client.messages.create(
        model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    analysis = json.loads(raw[start:end])

    # Step 3: merge — computed numbers + LLM insight text
    for sid, cov in coverage_report.get("subjects", {}).items():
        existing   = profile["subjects"].get(sid, {})
        claude_sub = next(
            (s for s in analysis.get("subject_updates", []) if s["subject_id"] == sid), {}
        )
        profile["subjects"][sid] = {
            "subject_id":          sid,
            "avg_score":           cov["weighted_readiness"],   # computed, not LLM
            "coverage_pct":        cov["coverage_pct"],
            "tested_subtopics":    cov["tested_subtopics"],
            "total_subtopics":     cov["total_subtopics"],
            "confidence":          claude_sub.get("confidence",          existing.get("confidence",          "unassessed")),
            "trend":               claude_sub.get("trend",               existing.get("trend",               "unknown")),
            "weak_subtopics":      claude_sub.get("weak_subtopics",      existing.get("weak_subtopics",      [])),
            "strong_subtopics":    claude_sub.get("strong_subtopics",    existing.get("strong_subtopics",    [])),
            "weak_question_types": claude_sub.get("weak_question_types", existing.get("weak_question_types", [])),
            "insight":             claude_sub.get("insight",             existing.get("insight",             "")),
        }

    profile["overall_readiness"] = coverage_report.get("overall_readiness", profile["overall_readiness"])
    profile["phase"]             = analysis.get("phase_recommendation", profile["phase"])
    profile["last_analysis"]     = analysis.get("summary", "")
    profile["priority_focus"]    = analysis.get("priority_focus", [])
    profile["time_estimates"]    = analysis.get("time_estimates", {})
    try:
        config = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
        start = date.fromisoformat(config["start_date"])
        profile["day_number"] = (date.today() - start).days + 1
    except Exception:
        profile["day_number"] = profile.get("day_number", 1) + 1

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
