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
import statistics
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
    """Returns {subject_id: {all_subtopics: [id,...], avg_questions_per_year: int, topics: [...]}}"""
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
        topics_list: list[dict] = []
        for topic in subject.get("topics", []):
            topic_subtopic_ids: list[str] = []
            for st in topic.get("subtopics", []):
                subtopics.append(st["id"])
                topic_subtopic_ids.append(st["id"])
            topics_list.append({
                "id": topic["id"],
                "name": topic.get("name", topic["id"]),
                "subtopics": topic_subtopic_ids,
            })
        result[sid] = {
            "all_subtopics": subtopics,
            "avg_questions_per_year": subject.get("avg_questions_per_year", 10),
            "topics": topics_list,
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


def _get_dimension_scores(con: sqlite3.Connection, subject_id: str) -> dict[str, list[dict]]:
    """
    Returns {subtopic_id: [{dimension_id, score, attempts}, ...]} for a given subject.
    Falls back to empty dict if the table doesn't exist yet (pre-Phase 4 merge).
    """
    try:
        rows = con.execute(
            "SELECT subtopic_id, dimension_id, score, attempts "
            "FROM subtopic_dimension_scores "
            "WHERE user_id='user_1' AND subject_id=?",
            (subject_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        # Table doesn't exist yet — graceful fallback
        return {}
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row["subtopic_id"], []).append({
            "dimension_id": row["dimension_id"],
            "score":        row["score"],
            "attempts":     row["attempts"],
        })
    return result


def _compute_subtopic_dim_coverage(
    subtopic_id: str,
    dim_scores_for_subtopic: list[dict],
    syllabus_dims: list[dict],
) -> tuple[float | None, float | None]:
    """
    Computes (coverage_pct, readiness) for a subtopic using per-dimension scores.

    Returns (None, None) if there are no dimension scores or no syllabus dims for
    this subtopic — callers must fall back to the flat subtopic_scores value.

    coverage_pct reflects which dimensions are still untouched (anti-false-positive):
    a subtopic with 1/3 dimensions tested at 80% will NOT read as 100% coverage.
    """
    if not dim_scores_for_subtopic or not syllabus_dims:
        return None, None

    total_weight = sum(d["final_weight"] for d in syllabus_dims)
    if total_weight == 0:
        return None, None

    score_by_dim = {r["dimension_id"]: r["score"] for r in dim_scores_for_subtopic}
    covered_weight = 0.0
    readiness_sum  = 0.0

    for dim in syllabus_dims:
        score = score_by_dim.get(dim["id"])
        if score is None:
            continue  # untested dimension — 0 contribution
        if score >= 0.75:
            depth = 1.0
        elif score >= 0.45:
            depth = score
        else:
            depth = score * 0.5
        covered_weight += dim["final_weight"] * depth
        readiness_sum  += dim["final_weight"] * score

    coverage_pct = round(covered_weight / total_weight * 100, 1)
    readiness    = round(readiness_sum  / total_weight, 1)
    return coverage_pct, readiness


def _compute_topic_coverage(
    subject_id: str,
    topics: list[dict],
    tested_in_subject: dict[str, float],
    pyq_weights: dict[str, float],
) -> list[dict]:
    """
    Compute topic-level coverage for a single subject.

    For each topic:
      - subtopics_total: number of subtopics in the topic
      - subtopics_tested: how many have been tested
      - readiness: PYQ-weighted score (untested = 0)
      - coverage_pct: percentage of subtopics tested
      - risk_level: high/medium/low based on coverage_pct
      - uncovered_subtopics_count: not yet tested
      - at_risk_subtopics: tested but weak (<0.45) OR untested but high PYQ weight

    Returns a list of topic dicts, skipping topics with 0 subtopics.
    """
    result: list[dict] = []
    for topic in topics:
        topic_subtopics: list[str] = topic["subtopics"]
        subtopics_total = len(topic_subtopics)
        if subtopics_total == 0:
            continue

        # Compute per-subtopic weights for this topic
        topic_weights: dict[str, float] = {
            st_id: max(pyq_weights.get(st_id, DEFAULT_WEIGHT), MIN_WEIGHT)
            for st_id in topic_subtopics
        }

        total_weight   = sum(topic_weights.values())
        weighted_score = 0.0
        subtopics_tested = 0

        for st_id in topic_subtopics:
            if st_id in tested_in_subject:
                weighted_score += tested_in_subject[st_id] * topic_weights[st_id]
                subtopics_tested += 1
            # untested → score 0, contributes 0

        readiness    = (weighted_score / total_weight) if total_weight > 0 else 0.0
        coverage_pct = (subtopics_tested / subtopics_total) * 100

        if coverage_pct < 50:
            risk_level = "high"
        elif coverage_pct < 80:
            risk_level = "medium"
        else:
            risk_level = "low"

        uncovered_subtopics_count = subtopics_total - subtopics_tested

        # Median weight across all subtopics in this topic
        all_weights_in_topic = list(topic_weights.values())
        median_w = statistics.median(all_weights_in_topic) if all_weights_in_topic else MIN_WEIGHT

        at_risk_subtopics: list[str] = []
        for st_id in topic_subtopics:
            if st_id in tested_in_subject:
                if tested_in_subject[st_id] < 0.45:
                    at_risk_subtopics.append(st_id)
            else:
                # Untested — flag if above-median PYQ weight (high priority gap)
                if topic_weights[st_id] > median_w:
                    at_risk_subtopics.append(st_id)

        result.append({
            "id":                       topic["id"],
            "name":                     topic["name"],
            "subtopics_total":          subtopics_total,
            "subtopics_tested":         subtopics_tested,
            "coverage_pct":             round(coverage_pct, 1),
            "readiness":                round(readiness, 1),
            "risk_level":               risk_level,
            "uncovered_subtopics_count": uncovered_subtopics_count,
            "at_risk_subtopics":        at_risk_subtopics,
        })
    return result


def compute_weighted_readiness(
    dim_scores_by_subject: dict[str, dict[str, list[dict]]] | None = None,
    syllabus_dims_map: dict[str, list[dict]] | None = None,
) -> dict:
    """
    Pre-computes authoritative readiness scores before the LLM call.

    For every subject in the syllabus:
      - Each subtopic has a PYQ priority weight (recency-decayed question frequency).
      - If subtopic_dimension_scores rows exist for a subtopic, per-dimension accuracy
        is used to compute readiness (FEATURE-027 Phase 5).
      - If no dimension rows exist yet, falls back to the flat subtopic_scores value
        (prevents all scores dropping to 0 on the first Sync after this merge).
      - Untested subtopics (no flat score AND no dimension rows) contribute 0.
      - Subject readiness = total weighted score / sum of all weights.
      - Coverage = tested_count / total_subtopic_count.

    Overall readiness = average of subject readiness weighted by avg_questions_per_year.
    """
    syllabus_map = _build_syllabus_map()
    if not syllabus_map:
        return {}

    pyq_weights = compute_all_priorities()
    tested = _get_tested_subtopics()

    # Defaults so callers that don't pass these args still get a valid (empty) dict
    if dim_scores_by_subject is None:
        dim_scores_by_subject = {}
    if syllabus_dims_map is None:
        syllabus_dims_map = {}

    subject_readiness: dict[str, dict] = {}

    for sid, info in syllabus_map.items():
        all_subtopics = info["all_subtopics"]
        if not all_subtopics:
            continue

        total_weight   = 0.0
        weighted_score = 0.0
        tested_count   = 0
        all_subtopics_set = set(all_subtopics)
        tested_in_subject  = tested.get(sid, {})
        dim_scores_for_sid = dim_scores_by_subject.get(sid, {})

        for st_id in all_subtopics:
            w = max(pyq_weights.get(st_id, DEFAULT_WEIGHT), MIN_WEIGHT)
            total_weight += w

            # --- dimension-aware readiness (FEATURE-027 Phase 5) ---
            dim_rows   = dim_scores_for_sid.get(st_id, [])
            syllabus_d = syllabus_dims_map.get(st_id, [])
            coverage_pct, dim_readiness = _compute_subtopic_dim_coverage(
                st_id, dim_rows, syllabus_d
            )

            if dim_readiness is not None:
                # Use dimension-computed readiness
                weighted_score += dim_readiness * w
                tested_count   += 1
                print(f"    {st_id}: dim_coverage={coverage_pct}%  readiness={dim_readiness}")
            elif st_id in tested_in_subject:
                # Fallback: use flat subtopic score
                weighted_score += tested_in_subject[st_id] * w
                tested_count   += 1
            # else: untested → score 0, contributes 0 to weighted_score

        # Credit quiz subtopics whose IDs don't match any syllabus subtopic
        # (plan generator uses its own naming e.g. "indus_valley_civilization"
        # while syllabus uses "ivc_sites_features"). Give them average subject weight.
        extra_tested = {st for st in tested_in_subject if st not in all_subtopics_set}
        if extra_tested and all_subtopics:
            avg_w = total_weight / len(all_subtopics)
            for st_id in extra_tested:
                w = max(pyq_weights.get(st_id, avg_w), MIN_WEIGHT)
                total_weight   += w
                # For extra subtopics, dimension data is unlikely; use flat score
                dim_rows   = dim_scores_for_sid.get(st_id, [])
                syllabus_d = syllabus_dims_map.get(st_id, [])
                _, dim_readiness = _compute_subtopic_dim_coverage(st_id, dim_rows, syllabus_d)
                if dim_readiness is not None:
                    weighted_score += dim_readiness * w
                else:
                    weighted_score += tested_in_subject[st_id] * w
                tested_count += 1

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
            "topics": _compute_topic_coverage(
                sid,
                info["topics"],
                tested_in_subject,
                pyq_weights,
            ),
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

    # Build syllabus_dims_map once: {subtopic_id -> list of dimension dicts}
    # Used by the dimension-aware readiness formula (FEATURE-027 Phase 5)
    _syllabus_dims_map: dict[str, list[dict]] = {}
    try:
        _syllabus_raw = json.loads(SYLLABUS_PATH.read_text())
        for _subj in _syllabus_raw.get("subjects", []):
            for _topic in _subj.get("topics", []):
                for _st in _topic.get("subtopics", []):
                    if _st.get("dimensions"):
                        _syllabus_dims_map[_st["id"]] = _st["dimensions"]
    except Exception as _e:
        print(f"  Warning: could not load syllabus dims: {_e}")

    # Fetch per-dimension scores for every subject from the DB
    _dim_scores_by_subject: dict[str, dict[str, list[dict]]] = {}
    try:
        _dim_con = sqlite3.connect(DB_PATH)
        _dim_con.row_factory = sqlite3.Row
        _syllabus_map_for_sids = _build_syllabus_map()
        for _sid in _syllabus_map_for_sids:
            _dim_scores_by_subject[_sid] = _get_dimension_scores(_dim_con, _sid)
        _dim_con.close()
        _total_dim_rows = sum(
            len(rows)
            for st_map in _dim_scores_by_subject.values()
            for rows in st_map.values()
        )
        print(f"  Dimension scores loaded: {_total_dim_rows} row(s) across "
              f"{len(_dim_scores_by_subject)} subject(s)")
    except Exception as _e:
        print(f"  Warning: could not load dimension scores: {_e}")
        _dim_scores_by_subject = {}

    # Step 1: deterministic weighted readiness (authoritative numbers)
    coverage_report = compute_weighted_readiness(
        dim_scores_by_subject=_dim_scores_by_subject,
        syllabus_dims_map=_syllabus_dims_map,
    )
    print(f"  Weighted overall readiness: {coverage_report.get('overall_readiness', '?')}%")
    for sid, s in coverage_report.get("subjects", {}).items():
        print(f"  {sid}: {s['weighted_readiness']}% "
              f"(coverage {s['coverage_pct']}% — "
              f"{s['tested_subtopics']}/{s['total_subtopics']} subtopics tested)")
        for t in s.get("topics", []):
            if t["risk_level"] == "high":
                print(f"    ⚠ topic {t['id']}: {t['coverage_pct']}% covered, risk=high")

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
            "topics":              cov.get("topics", []),       # deterministic, not LLM
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

    # Feedback accumulation reminder — printed when 20+ rows have built up
    try:
        _fb_con = sqlite3.connect(DB_PATH)
        _fb_count = _fb_con.execute(
            "SELECT COUNT(*) FROM content_feedback"
        ).fetchone()[0]
        _fb_con.close()
        if _fb_count >= 20:
            print(
                f"\n⚠️  {_fb_count} feedback items in content_feedback — "
                "consider running: python scripts/apply_feedback.py"
            )
    except Exception:
        # Table doesn't exist yet on older DBs — silently skip
        pass

    return analysis


if __name__ == "__main__":
    run_analysis()
