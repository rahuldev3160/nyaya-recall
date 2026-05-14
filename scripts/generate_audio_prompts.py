#!/usr/bin/env python3
"""
Generate audio prompt pipeline for NotebookLM.

Produces prompt_pipeline.md — ready-to-paste prompts ordered by exam priority.
Each prompt directs two hosts to explore a topic group through specific dimensions.

Usage:
  python generate_audio_prompts.py
  python generate_audio_prompts.py --no-llm
  python generate_audio_prompts.py --subject environment
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

DB_PATH      = Path(os.getenv("DB_PATH", str(ROOT / "data/upsc.db")))
PROFILE_PATH = ROOT / "data" / "prep_profile.json"
SYLLABUS_PATH = ROOT / "data" / "syllabus.json"
VS_PATH      = os.getenv("VECTOR_STORE_PATH", str(ROOT / "vector_store"))
OUTPUT_PATH  = ROOT / "exports" / "audio" / "prompt_pipeline.md"

USER_ID = "user_1"

CA_SOURCE_KEYWORDS = ["current affair", "pt365", "saarthi", "flash note", "ca_", " news"]

SUBJECT_DISPLAY_ORDER = [
    "polity", "economy", "environment", "science_tech",
    "geography", "modern_history", "ir_governance", "current_affairs",
    "history_amac",
]

# Short codes for subject prefixes
SUBJECT_CODES = {
    "polity": "POL", "economy": "ECO", "environment": "ENV",
    "science_tech": "SCI", "geography": "GEO", "modern_history": "MHI",
    "ir_governance": "IRG", "current_affairs": "CA", "history_amac": "HIS",
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_syllabus() -> dict:
    return json.loads(SYLLABUS_PATH.read_text()) if SYLLABUS_PATH.exists() else {"subjects": []}


def load_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text()) if PROFILE_PATH.exists() else {}


def get_subtopic_scores(db: sqlite3.Connection, subject_id: str) -> dict[str, dict]:
    rows = db.execute(
        "SELECT subtopic_id, score, total_attempts FROM subtopic_scores "
        "WHERE user_id=? AND subject_id=?",
        (USER_ID, subject_id),
    ).fetchall()
    return {r["subtopic_id"]: dict(r) for r in rows}


def get_pyq_counts_for_subject(db: sqlite3.Connection, subject_id: str) -> dict[str, int]:
    rows = db.execute(
        "SELECT subtopic_id, COUNT(*) as n FROM pyq_questions "
        "WHERE subject_id=? GROUP BY subtopic_id",
        (subject_id,),
    ).fetchall()
    return {r["subtopic_id"]: r["n"] for r in rows}


def get_sample_pyqs(db: sqlite3.Connection, subtopic_ids: list[str], subject_id: str) -> list[dict]:
    """Get up to 4 sample PYQ questions for a topic group."""
    pyqs: list[dict] = []
    for stid in subtopic_ids:
        rows = db.execute(
            "SELECT question_text, year FROM pyq_questions "
            "WHERE subtopic_id=? ORDER BY year DESC LIMIT 2",
            (stid,),
        ).fetchall()
        pyqs.extend(dict(r) for r in rows)
    # Fallback: keyword search within subject if no direct matches
    if not pyqs:
        st_names = subtopic_ids  # use ids as keyword seeds
        for stid in subtopic_ids[:2]:
            kws = stid.replace("_", " ").split()[:2]
            for kw in kws:
                rows = db.execute(
                    "SELECT question_text, year FROM pyq_questions "
                    "WHERE subject_id=? AND question_text LIKE ? LIMIT 2",
                    (subject_id, f"%{kw}%"),
                ).fetchall()
                pyqs.extend(dict(r) for r in rows)
    return pyqs[:4]


def subject_has_ca(subject_id: str) -> bool:
    """Check if subject has current affairs / recent-update chunks in ChromaDB."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=VS_PATH)
        col = client.get_collection("upsc_content")
        r = col.get(
            limit=5000,
            where={"subject_id": subject_id},
            include=["metadatas"],
        )
        for m in r["metadatas"]:
            src = m.get("source_file", "").lower()
            if any(kw in src for kw in CA_SOURCE_KEYWORDS):
                return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Priority computation
# ---------------------------------------------------------------------------

def compute_group_priority(
    subtopics: list[dict],
    scores: dict[str, dict],
    pyq_counts: dict[str, int],
    priority_focus: set[str],
    subject_avg_q: int,
    total_subtopics: int,
) -> float:
    """
    Priority = sum over subtopics of:
      - If PYQ match: pyq_count × (1 − score) × focus_multiplier
      - If no PYQ match: subject_avg_q/total_subtopics × (1 − score) × focus_multiplier
    Focus multiplier: 2.0 if subtopic is in priority_focus, else 1.0
    """
    subject_baseline = subject_avg_q / max(total_subtopics, 1)
    total = 0.0
    for st in subtopics:
        sid = st["id"]
        sc = scores.get(sid, {}).get("score", None)
        gap_factor = 1 - (sc or 0) / 100  # untested = full gap (1.0)
        pyq_n = pyq_counts.get(sid, 0)
        base = pyq_n if pyq_n > 0 else subject_baseline
        focus = 2.0 if sid in priority_focus else 1.0
        total += base * gap_factor * focus
    return round(total, 2)


def priority_label(score: float) -> str:
    if score >= 12:
        return "CRITICAL"
    elif score >= 6:
        return "HIGH"
    elif score >= 3:
        return "MEDIUM"
    else:
        return "LOW"


# ---------------------------------------------------------------------------
# LLM dimension generation
# ---------------------------------------------------------------------------

def haiku_dimensions(
    subject_name: str,
    topic_name: str,
    subtopics: list[dict],
    pyqs: list[dict],
    has_ca: bool,
    api_key: str,
) -> str:
    import anthropic

    subtopic_names = " | ".join(st["name"] for st in subtopics)

    pyq_block = ""
    if pyqs:
        pyq_block = "\nSample past exam questions on this topic:\n"
        for p in pyqs[:4]:
            pyq_block += f"- [{p['year']}] {p['question_text'][:130].strip()}\n"

    ca_note = (
        "\nNote: Current affairs sources (2024–25 updates) are uploaded in this notebook — "
        "include one dimension about recent developments or policy updates relevant to this topic."
        if has_ca else ""
    )

    prompt = (
        f"You are designing a revision podcast episode for a UPSC Prelims 2026 aspirant.\n\n"
        f"Subject: {subject_name}\n"
        f"Topic area: {topic_name}\n"
        f"Subtopics to cover: {subtopic_names}\n"
        f"{pyq_block}{ca_note}\n\n"
        f"Write exactly 3–4 bullet points — specific dimensions for two hosts to explore in conversation.\n\n"
        f"Rules:\n"
        f"- Each bullet is 1–2 sentences describing a CONCRETE angle, not a generic instruction\n"
        f"- Bad: 'Discuss biodiversity hotspots' — Good: 'Explore what makes a region a biodiversity hotspot — "
        f"the 2 criteria (endemism threshold + habitat loss), India's 4 hotspots, and why the Western Ghats "
        f"is different from the Eastern Himalayas'\n"
        f"- Ground each dimension in what UPSC actually tests based on the sample questions\n"
        f"- No quiz formats, no MCQ simulations, no 'quiz each other'\n"
        f"- The result should feel like two knowledgeable people having a focused conversation\n\n"
        f"Output ONLY the bullet points. No intro, no headers."
    )

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def basic_dimensions(topic_name: str, subtopics: list[dict]) -> str:
    names = [st["name"] for st in subtopics]
    lines = [
        f"- The core concepts behind {names[0]} — definitions, mechanisms, and what makes it exam-relevant",
    ]
    if len(names) > 1:
        lines.append(
            f"- Key distinctions between {' and '.join(names[:2])} — what's commonly confused and why"
        )
    lines.append(
        "- India-specific facts: names, dates, classifications, and examples that appear in Prelims"
    )
    lines.append(
        "- Recent policy or current affairs connections — what's changed or been in news lately"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

TONE_INSTRUCTION = (
    "Tone: two hosts who genuinely know this topic, exploring it together in conversation. "
    "Not a lecture, not a quiz. The right depth for revision — clear concepts, "
    "memorable examples, exam-relevant facts. Target 12–15 minutes."
)


def build_prompt_text(subtopic_names: str, dimensions: str) -> str:
    return (
        f"Explore {subtopic_names} with your listeners preparing for UPSC Prelims 2026.\n\n"
        f"Cover these specific angles:\n{dimensions}\n\n"
        f"{TONE_INSTRUCTION}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="Skip Haiku calls, use basic dimensions")
    parser.add_argument("--subject", default=None, help="Generate only for one subject")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    use_llm = not args.no_llm and bool(api_key)

    db = db_conn()
    syllabus = load_syllabus()
    profile = load_profile()
    priority_focus = set(profile.get("priority_focus", []))
    today = date.today().isoformat()

    # Filter subjects — always exclude CSAT (separate system, separate paper)
    all_subjects = [s for s in syllabus.get("subjects", []) if s["id"] != "csat"]
    if args.subject:
        all_subjects = [s for s in all_subjects if s["id"] == args.subject]

    # Pre-compute CA availability per subject (one ChromaDB scan per subject)
    print("Scanning sources...")
    ca_map: dict[str, bool] = {}
    for subj in all_subjects:
        ca_map[subj["id"]] = subject_has_ca(subj["id"])

    # Build topic groups
    groups: list[dict] = []
    for subj in all_subjects:
        subject_id  = subj["id"]
        subject_name = subj.get("name", subject_id)
        avg_q       = subj.get("avg_questions_per_year", 10)
        scores      = get_subtopic_scores(db, subject_id)
        pyq_counts  = get_pyq_counts_for_subject(db, subject_id)
        total_st    = sum(len(t.get("subtopics", [])) for t in subj.get("topics", []))
        has_ca      = ca_map[subject_id]
        prefix      = SUBJECT_CODES.get(subject_id, subject_id[:3].upper())

        for t_idx, topic in enumerate(subj.get("topics", []), 1):
            subtopics = [
                {"id": st["id"], "name": st["name"]}
                for st in topic.get("subtopics", [])
            ]
            if not subtopics:
                continue

            priority = compute_group_priority(
                subtopics, scores, pyq_counts, priority_focus, avg_q, total_st
            )
            pyqs = get_sample_pyqs(db, [s["id"] for s in subtopics], subject_id)

            groups.append({
                "subject_id":   subject_id,
                "subject_name": subject_name,
                "topic_name":   topic.get("name", ""),
                "subtopics":    subtopics,
                "priority":     priority,
                "label":        priority_label(priority),
                "pyqs":         pyqs,
                "has_ca":       has_ca,
                "code":         f"{prefix}-{t_idx:02d}",
            })

    # Assign global ranks (sorted by priority descending)
    groups.sort(key=lambda g: -g["priority"])
    for i, g in enumerate(groups, 1):
        g["global_rank"] = i

    # Generate dimensions
    total = len(groups)
    print(f"Generating dimensions for {total} topic groups {'(Haiku)' if use_llm else '(basic, no LLM)'}...")

    for i, g in enumerate(groups, 1):
        label_str = f"[{i}/{total}] {g['code']} — {g['topic_name']}"
        if use_llm:
            print(f"  {label_str}")
            try:
                g["dimensions"] = haiku_dimensions(
                    g["subject_name"], g["topic_name"], g["subtopics"],
                    g["pyqs"], g["has_ca"], api_key,
                )
            except Exception as e:
                print(f"    ⚠ Haiku failed ({e}), using basic")
                g["dimensions"] = basic_dimensions(g["topic_name"], g["subtopics"])
        else:
            g["dimensions"] = basic_dimensions(g["topic_name"], g["subtopics"])

    # ---------------------------------------------------------------------------
    # Build output document
    # ---------------------------------------------------------------------------

    lines: list[str] = [
        f"# Audio Prompt Pipeline — UPSC Prelims 2026",
        f"Generated: {today}  |  {total} prompts across {len(set(g['subject_id'] for g in groups))} subjects",
        f"",
        f"> **How to use:** Copy each prompt block → open the correct NotebookLM notebook",
        f"> → Audio Overview → Customize → paste → Generate.",
        f"> Work top-to-bottom within each subject. The subject order here reflects exam weight.",
        f"",
        f"---",
        f"",
        f"## Top 15 globally — highest priority",
        f"",
        f"| # | Code | Topic | Subject | Priority |",
        f"|---|------|-------|---------|----------|",
    ]
    for g in groups[:15]:
        lines.append(
            f"| {g['global_rank']} | `{g['code']}` | {g['topic_name']} | {g['subject_name']} | **{g['label']}** |"
        )

    lines += ["", "---", ""]

    # Output by subject (ordered by subject priority, within subject by topic priority)
    by_subject: dict[str, list[dict]] = defaultdict(list)
    for g in groups:
        by_subject[g["subject_id"]].append(g)

    # Subject order: by their top prompt's global rank
    subject_top_rank = {
        sid: min(g["global_rank"] for g in gs)
        for sid, gs in by_subject.items()
    }
    ordered_subjects = sorted(by_subject.keys(), key=lambda s: subject_top_rank[s])

    subject_total_time: dict[str, int] = {}
    for sid, gs in by_subject.items():
        subject_total_time[sid] = len(gs) * 13  # avg 13 min

    for sid in ordered_subjects:
        gs = sorted(by_subject[sid], key=lambda g: g["global_rank"])
        subject_name = gs[0]["subject_name"]
        est_min = subject_total_time[sid]

        lines += [
            f"## {subject_name} — {len(gs)} audio{'s' if len(gs) > 1 else ''}  (~{est_min} min total)",
            f"",
        ]

        for g in gs:
            subtopic_names = " + ".join(st["name"] for st in g["subtopics"])
            prompt_text = build_prompt_text(subtopic_names, g["dimensions"])

            lines += [
                f"### `{g['code']}` — {g['topic_name']}",
                f"**Global rank:** #{g['global_rank']}  |  **Priority:** {g['label']}  |  **Target:** 12–15 min",
                f"**Subtopics:** {subtopic_names}",
                f"",
                f"```",
                prompt_text,
                f"```",
                f"",
                f"---",
                f"",
            ]

    # Summary table
    lines += [
        f"## Summary",
        f"",
        f"| Subject | Audios | Est. time | Notebook name |",
        f"|---------|--------|-----------|---------------|",
    ]
    for sid in ordered_subjects:
        gs = by_subject[sid]
        name = gs[0]["subject_name"]
        lines.append(
            f"| {name} | {len(gs)} | ~{subject_total_time[sid]} min | {name} |"
        )

    total_min = sum(subject_total_time.values())
    total_hr = total_min // 60
    lines += [
        f"",
        f"**Total: {total} prompts — ~{total_min} minutes (~{total_hr} hours) of audio**",
        f"",
        f"*Generated by UPSC AI Prep System on {today}*",
    ]

    content = "\n".join(lines)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content, encoding="utf-8")

    print(f"\n✅  {OUTPUT_PATH}")
    print(f"    {total} prompts  |  ~{total_min} min (~{total_hr}h) of audio")
    print(f"\nTop 5:")
    for g in groups[:5]:
        print(f"  #{g['global_rank']} [{g['label']}] {g['subject_name']} — {g['topic_name']}")


if __name__ == "__main__":
    main()
