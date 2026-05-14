#!/usr/bin/env python3
"""
Generate personalised audio revision documents for NotebookLM upload.

Usage:
  python generate_audio_brief.py --type subject --subject environment
  python generate_audio_brief.py --type daily
  python generate_audio_brief.py --type weak --subtopic fiscal_policy_budget
  python generate_audio_brief.py --type subject --subject polity --no-llm
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from textwrap import dedent

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

DB_PATH       = Path(os.getenv("DB_PATH", str(ROOT / "data/upsc.db")))
PROFILE_PATH  = ROOT / "data" / "prep_profile.json"
CONFIG_PATH   = ROOT / "data" / "prep_config.json"
PLAN_PATH     = ROOT / "data" / "study_plan.json"
SYLLABUS_PATH = ROOT / "data" / "syllabus.json"
OUTPUT_DIR    = ROOT / "exports" / "audio"
VS_PATH       = os.getenv("VECTOR_STORE_PATH", str(ROOT / "vector_store"))

USER_ID = "user_1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def chroma_collection():
    import chromadb
    client = chromadb.PersistentClient(path=VS_PATH)
    return client.get_collection("upsc_content")


def load_syllabus() -> dict:
    return json.loads(SYLLABUS_PATH.read_text()) if SYLLABUS_PATH.exists() else {"subjects": []}


def subtopic_display_names(syllabus: dict) -> dict[str, str]:
    """Returns {subtopic_id: display_name}"""
    names: dict[str, str] = {}
    for subj in syllabus.get("subjects", []):
        for topic in subj.get("topics", []):
            for st in topic.get("subtopics", []):
                names[st["id"]] = st["name"]
    return names


def subject_display_name(syllabus: dict, subject_id: str) -> str:
    for subj in syllabus.get("subjects", []):
        if subj["id"] == subject_id:
            return subj.get("name", subject_id)
    return subject_id


def fetch_pyqs(db: sqlite3.Connection, subject_id: str | None = None,
               subtopic_id: str | None = None, limit: int = 200) -> list[dict]:
    if subtopic_id:
        rows = db.execute(
            "SELECT * FROM pyq_questions WHERE subtopic_id = ? ORDER BY year DESC LIMIT ?",
            (subtopic_id, limit)
        ).fetchall()
    elif subject_id:
        rows = db.execute(
            "SELECT * FROM pyq_questions WHERE subject_id = ? ORDER BY year DESC LIMIT ?",
            (subject_id, limit)
        ).fetchall()
    else:
        rows = []
    return [dict(r) for r in rows]


def fetch_subtopic_scores(db: sqlite3.Connection, subject_id: str) -> dict[str, dict]:
    rows = db.execute(
        "SELECT subtopic_id, score, total_attempts, correct_count FROM subtopic_scores "
        "WHERE user_id = ? AND subject_id = ?",
        (USER_ID, subject_id)
    ).fetchall()
    return {r["subtopic_id"]: dict(r) for r in rows}


def fetch_chroma_chunks(query: str, subject_id: str, n: int = 4) -> list[str]:
    try:
        col = chroma_collection()
        results = col.query(
            query_texts=[query],
            n_results=n,
            where={"subject_id": subject_id}
        )
        docs = results.get("documents", [[]])[0]
        # Filter out scanned-PDF garbage (short or non-ASCII dominated)
        clean = []
        for doc in docs:
            ascii_ratio = sum(1 for c in doc if ord(c) < 128) / max(len(doc), 1)
            if len(doc) > 100 and ascii_ratio > 0.7:
                clean.append(doc.strip())
        return clean[:n]
    except Exception:
        return []


def haiku_synthesis(prompt: str, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()


def write_output(content: str, filename: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / filename
    out.write_text(content, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Subject Overview Builder
# ---------------------------------------------------------------------------

class SubjectOverviewBuilder:
    def __init__(self, subject_id: str, no_llm: bool = False):
        self.subject_id = subject_id
        self.no_llm = no_llm
        self.db = db_conn()
        self.syllabus = load_syllabus()
        self.display_names = subtopic_display_names(self.syllabus)
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")

    def build(self) -> tuple[str, str]:
        subject_name = subject_display_name(self.syllabus, self.subject_id)
        today = date.today().isoformat()

        # Scores
        scores = fetch_subtopic_scores(self.db, self.subject_id)

        # PYQ counts by subtopic
        pyq_rows = self.db.execute(
            "SELECT subtopic_id, COUNT(*) as n FROM pyq_questions "
            "WHERE subject_id = ? GROUP BY subtopic_id",
            (self.subject_id,)
        ).fetchall()
        pyq_counts: dict[str, int] = {r["subtopic_id"]: r["n"] for r in pyq_rows}
        total_pyqs = sum(pyq_counts.values())

        # All subtopics from syllabus for this subject
        all_subtopics: list[dict] = []
        for subj in self.syllabus.get("subjects", []):
            if subj["id"] == self.subject_id:
                for topic in subj.get("topics", []):
                    for st in topic.get("subtopics", []):
                        sid = st["id"]
                        sc = scores.get(sid, {})
                        pyq_n = pyq_counts.get(sid, 0)
                        score_val = sc.get("score", None)
                        attempts = sc.get("total_attempts", 0)
                        gap = pyq_n * (1 - (score_val or 0) / 100) if pyq_n else 0
                        all_subtopics.append({
                            "id": sid,
                            "name": st["name"],
                            "topic": topic["name"],
                            "score": score_val,
                            "attempts": attempts,
                            "pyq_count": pyq_n,
                            "gap_score": gap,
                        })

        # Rank by gap score
        tested_weak = [s for s in all_subtopics if s["score"] is not None and s["score"] < 60]
        tested_strong = [s for s in all_subtopics if s["score"] is not None and s["score"] >= 60]
        untested = [s for s in all_subtopics if s["score"] is None]

        top_risk = sorted(
            tested_weak + untested,
            key=lambda x: x["gap_score"],
            reverse=True
        )[:6]

        # Build sections for each top-risk subtopic
        sections: list[str] = []
        for i, st in enumerate(top_risk, 1):
            chunks = fetch_chroma_chunks(
                f"{st['name']} {self.subject_id} UPSC",
                self.subject_id,
                n=3
            )
            pyqs = fetch_pyqs(self.db, subtopic_id=st["id"], limit=4)

            # Fallback: search by subject if no subtopic PYQs
            if not pyqs:
                pyqs = [p for p in fetch_pyqs(self.db, subject_id=self.subject_id, limit=100)
                        if any(kw in p["question_text"].lower()
                               for kw in st["name"].lower().split()[:3])][:3]

            score_str = f"{st['score']:.0f}%" if st["score"] is not None else "Not yet tested"
            risk_label = "CRITICAL" if st["gap_score"] > 5 else "HIGH" if st["gap_score"] > 2 else "MEDIUM"

            concept_text = ""
            if chunks:
                concept_text = "\n\n### Core concepts from your study notes\n"
                concept_text += "\n\n".join(f"> {c[:600]}" for c in chunks[:2])
            elif not self.no_llm and self.api_key:
                synth = haiku_synthesis(
                    f"In 4 bullet points, summarise the key UPSC-testable facts about "
                    f"'{st['name']}' in Indian context. Be specific — dates, names, numbers. "
                    f"Focus on what appears in Prelims MCQs.",
                    self.api_key
                )
                concept_text = f"\n\n### Key facts (AI synthesised)\n{synth}"

            pyq_text = ""
            if pyqs:
                pyq_text = f"\n\n### Past exam questions ({len(pyqs)} shown)\n"
                for p in pyqs[:4]:
                    q = p["question_text"].strip()
                    opts = "  ".join(filter(None, [
                        f"(a) {p.get('option_a','')}" if p.get('option_a') else "",
                        f"(b) {p.get('option_b','')}" if p.get('option_b') else "",
                        f"(c) {p.get('option_c','')}" if p.get('option_c') else "",
                        f"(d) {p.get('option_d','')}" if p.get('option_d') else "",
                    ]))
                    ans = p.get("correct_answer", "")
                    yr = p.get("year", "")
                    pyq_text += f"\n**{yr} Prelims**\nQ: {q}\n{opts}\n**Answer: {ans}**\n"

            sections.append(dedent(f"""
## {i}. {st['name']}
**Topic:** {st['topic']}  |  **Your score:** {score_str}  |  **PYQ appearances:** {st['pyq_count']}  |  **Risk:** {risk_label}
{concept_text}
{pyq_text}

---"""))

        # Table for all subtopics
        table_rows = ""
        for st in sorted(all_subtopics, key=lambda x: -x["gap_score"]):
            score_str = f"{st['score']:.0f}%" if st["score"] is not None else "Untested"
            risk = "🔴 CRITICAL" if st["gap_score"] > 5 else "🟡 HIGH" if st["gap_score"] > 2 else "🟢 OK" if (st["score"] or 0) >= 60 else "⚪ Unknown"
            table_rows += f"| {st['name']} | {score_str} | {st['attempts']} | {st['pyq_count']} | {risk} |\n"

        # Stats
        tested_count = len(scores)
        total_count = len(all_subtopics)
        avg_score = sum(s["score"] for s in scores.values()) / max(len(scores), 1) if scores else 0

        strong_list = "\n".join(
            f"- {s['name']}: {s['score']:.0f}% ({s['pyq_count']} PYQs)"
            for s in sorted(tested_strong, key=lambda x: -x["score"])
        ) or "None yet"

        untested_list = "\n".join(
            f"- {s['name']} — {s['pyq_count']} PYQs in past exams"
            for s in sorted(untested, key=lambda x: -x["pyq_count"])
        ) or "All subtopics tested!"

        content = dedent(f"""
# Subject Overview: {subject_name}
## UPSC Prelims Revision — {today}

> This is a personalised revision document for **{subject_name}**.
> Use this to listen to an Audio Overview in NotebookLM — upload this file, then click "Generate Audio Overview".
>
> **Your coverage:** {tested_count} of {total_count} subtopics tested  |  **Average score:** {avg_score:.0f}%
> **Total PYQ exposure:** {total_pyqs} questions across this subject (2009–2025)
> **Focus of this document:** Your weakest and untested subtopics — highest exam risk first.

---

## Your score map — all subtopics

| Subtopic | Your Score | Attempts | PYQ Count | Risk |
|----------|-----------|----------|-----------|------|
{table_rows}

---

## Deep focus: Your 6 highest-risk areas

These are the subtopics where your readiness gap is largest — calculated as:
**Risk score = PYQ appearances × (1 − your score)**. Highest first.
{"".join(sections)}

## What you've already mastered ✅

{strong_list}

---

## Untested subtopics — you have not been quizzed on these yet

These are gaps the system has not yet measured. Treat as priority for tomorrow's sessions.

{untested_list}

---

## Quick-fire recall prompts

Use these to test yourself mentally while listening:

1. Name three types of ecosystems found in India and their defining features.
2. What is the difference between in-situ and ex-situ conservation? Give two examples of each.
3. Which Indian wetlands are Ramsar sites? What criteria qualifies a wetland?
4. What is the greenhouse effect? Name the top 3 greenhouse gases by warming potential.
5. What is the Paris Agreement's temperature target? What does India's NDC commit to?
6. What distinguishes a Biosphere Reserve from a National Park?
7. Name three Project Tiger reserves in India and their states.
8. What is the Montreal Protocol? What substances does it control?
9. Define biogeochemical cycle. Which nutrient cycle has no atmospheric phase?
10. What is ecological succession? Give an example of primary vs secondary succession.

---

*Document generated by UPSC AI Prep System on {today}. Upload to notebooklm.google.com → Audio Overview.*
        """).strip()

        filename = f"audio_subject_{self.subject_id}_{today}.md"
        return content, filename


# ---------------------------------------------------------------------------
# Daily Brief Builder (lightweight version)
# ---------------------------------------------------------------------------

class DailyBriefBuilder:
    def __init__(self, no_llm: bool = False):
        self.no_llm = no_llm
        self.db = db_conn()
        self.syllabus = load_syllabus()
        self.display_names = subtopic_display_names(self.syllabus)
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")

    def build(self) -> tuple[str, str]:
        today = date.today().isoformat()

        # Load today's plan
        plan: dict = {}
        if PLAN_PATH.exists():
            try:
                plan = json.loads(PLAN_PATH.read_text())
            except Exception:
                pass

        sessions = plan.get("sessions", plan.get("today", []))
        if not sessions:
            return "# No study plan found for today. Run Sync & Plan first.", f"audio_brief_{today}.md"

        # Gather subtopics from today's plan
        planned: list[dict] = []
        for s in sessions:
            for st_id in s.get("subtopics", [s.get("subtopic_id", "")]):
                if not st_id:
                    continue
                subject_id = s.get("subject_id", s.get("subject", ""))
                pyq_count = self.db.execute(
                    "SELECT COUNT(*) FROM pyq_questions WHERE subtopic_id = ?", (st_id,)
                ).fetchone()[0]
                sc = self.db.execute(
                    "SELECT score, total_attempts FROM subtopic_scores WHERE user_id=? AND subtopic_id=?",
                    (USER_ID, st_id)
                ).fetchone()
                score = sc["score"] if sc else 0
                planned.append({
                    "subtopic_id": st_id,
                    "subject_id": subject_id,
                    "name": self.display_names.get(st_id, st_id.replace("_", " ").title()),
                    "subject_name": subject_display_name(self.syllabus, subject_id),
                    "score": score,
                    "pyq_count": pyq_count,
                    "priority": pyq_count * (1 - score / 100),
                    "duration": s.get("duration_min", 30),
                })

        planned = sorted(planned, key=lambda x: -x["priority"])[:7]

        sections: list[str] = []
        for i, st in enumerate(planned, 1):
            chunks = fetch_chroma_chunks(
                f"{st['name']} UPSC exam", st["subject_id"], n=2
            )
            pyqs = fetch_pyqs(self.db, subtopic_id=st["subtopic_id"], limit=3)
            score_str = f"{st['score']:.0f}%"
            priority_label = "CRITICAL" if st["priority"] > 8 else "HIGH" if st["priority"] > 3 else "MEDIUM"

            concept_text = ""
            if chunks:
                concept_text = "\n### Key concepts\n" + "\n\n".join(f"> {c[:500]}" for c in chunks[:1])

            pyq_text = ""
            if pyqs:
                pyq_text = "\n### Real exam questions\n"
                for p in pyqs[:2]:
                    opts = "  ".join(filter(None, [
                        f"(a) {p.get('option_a','')}" if p.get('option_a') else "",
                        f"(b) {p.get('option_b','')}" if p.get('option_b') else "",
                    ]))
                    pyq_text += f"\n**{p.get('year')} Prelims:** {p['question_text'][:200]}\n{opts}\n**Answer: {p.get('correct_answer')}**\n"

            sections.append(dedent(f"""
## {i}. {st['name']} — {st['subject_name']}
**Your score:** {score_str}  |  **PYQ count:** {st['pyq_count']}  |  **Priority:** {priority_label}
{concept_text}
{pyq_text}
---"""))

        # Session table
        session_table = "| Session | Subject | Subtopic | Duration | Score |\n|---|---|---|---|---|\n"
        for i, st in enumerate(planned, 1):
            session_table += f"| {i} | {st['subject_name']} | {st['name']} | {st['duration']} min | {st['score']:.0f}% |\n"

        content = dedent(f"""
# UPSC Prelims Daily Brief — {today}
## Today's Priority Revision

> Personalised revision for today's planned sessions. Upload to NotebookLM → Audio Overview.
> Topics ordered by exam risk: highest PYQ frequency × your current gap = top of list.

---
{"".join(sections)}

## Today's Study Plan at a Glance

{session_table}

---

*Upload this file to notebooklm.google.com, then click "Audio Overview" to generate a 10–15 minute podcast.*
        """).strip()

        filename = f"audio_brief_{today}.md"
        return content, filename


# ---------------------------------------------------------------------------
# Weak Topic Deep-Dive Builder
# ---------------------------------------------------------------------------

class WeakTopicBuilder:
    def __init__(self, subtopic_id: str, no_llm: bool = False):
        self.subtopic_id = subtopic_id
        self.no_llm = no_llm
        self.db = db_conn()
        self.syllabus = load_syllabus()
        self.display_names = subtopic_display_names(self.syllabus)
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")

    def _find_subject(self) -> str:
        for subj in self.syllabus.get("subjects", []):
            for topic in subj.get("topics", []):
                for st in topic.get("subtopics", []):
                    if st["id"] == self.subtopic_id:
                        return subj["id"]
        return "unknown"

    def build(self) -> tuple[str, str]:
        today = date.today().isoformat()
        subject_id = self._find_subject()
        name = self.display_names.get(self.subtopic_id, self.subtopic_id.replace("_", " ").title())
        subject_name = subject_display_name(self.syllabus, subject_id)

        sc = self.db.execute(
            "SELECT score, total_attempts, correct_count FROM subtopic_scores "
            "WHERE user_id=? AND subtopic_id=?", (USER_ID, self.subtopic_id)
        ).fetchone()

        score = sc["score"] if sc else 0
        attempts = sc["total_attempts"] if sc else 0
        correct = sc["correct_count"] if sc else 0

        # Wrong answers from quiz history
        wrong = self.db.execute(
            "SELECT sa.question_text, sa.user_answer, sa.correct_answer "
            "FROM session_answers sa "
            "WHERE sa.subtopic_id=? AND sa.is_correct=0 AND sa.user_id=? "
            "ORDER BY sa.created_at DESC LIMIT 10",
            (self.subtopic_id, USER_ID)
        ).fetchall()

        # All PYQs
        pyqs = fetch_pyqs(self.db, subtopic_id=self.subtopic_id, limit=50)

        # ChromaDB
        chunks = fetch_chroma_chunks(f"{name} {subject_name} UPSC Prelims", subject_id, n=5)

        wrong_section = ""
        if wrong:
            wrong_section = "\n## Questions you got wrong\n"
            for w in wrong:
                wrong_section += f"\nQ: {w['question_text']}\nYour answer: {w['user_answer']}  |  Correct: {w['correct_answer']}\n"

        concepts_section = ""
        if chunks:
            concepts_section = "\n## Core concepts from your study notes\n"
            for c in chunks[:4]:
                concepts_section += f"\n{c[:800]}\n\n---\n"

        pyq_section = ""
        if pyqs:
            pyq_section = f"\n## All past exam questions — {len(pyqs)} questions (2009–2025)\n"
            for p in pyqs:
                opts = "\n".join(filter(None, [
                    f"(a) {p.get('option_a','')}" if p.get('option_a') else "",
                    f"(b) {p.get('option_b','')}" if p.get('option_b') else "",
                    f"(c) {p.get('option_c','')}" if p.get('option_c') else "",
                    f"(d) {p.get('option_d','')}" if p.get('option_d') else "",
                ]))
                pyq_section += f"\n**{p.get('year')} Prelims**\nQ: {p['question_text']}\n{opts}\n**Answer: {p.get('correct_answer')}**\n"

        examiner_section = ""
        if not self.no_llm and self.api_key and pyqs:
            q_texts = "\n".join(p["question_text"][:150] for p in pyqs[:15])
            examiner_section = "\n## What the UPSC examiner tests on this topic\n"
            examiner_section += haiku_synthesis(
                f"You are a UPSC expert. Analyse these {len(pyqs)} past exam questions on '{name}' "
                f"and write 3 paragraphs:\n1. What specific aspects of the topic appear most\n"
                f"2. What question patterns/traps to watch for\n3. The 3 most important facts to memorise\n\n"
                f"Questions:\n{q_texts}",
                self.api_key
            )

        content = dedent(f"""
# Deep Dive: {name}
## Subject: {subject_name}

> Personalised deep-dive for **{name}**.
> Your score: **{score:.0f}%** across **{attempts}** attempts ({correct} correct).
> Upload to NotebookLM → Audio Overview for a focused 15–20 minute revision podcast.

---

## Your performance summary

| Metric | Value |
|--------|-------|
| Score | {score:.0f}% |
| Total attempts | {attempts} |
| Correct | {correct} |
| PYQ questions on this topic | {len(pyqs)} |
{wrong_section}
---
{concepts_section}
{examiner_section}
{pyq_section}

---

*Upload to notebooklm.google.com → Audio Overview*
        """).strip()

        filename = f"audio_deep_dive_{self.subtopic_id}_{today}.md"
        return content, filename


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True, choices=["daily", "weak", "subject"])
    parser.add_argument("--subtopic", default=None)
    parser.add_argument("--subject", default=None)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    global OUTPUT_DIR
    if args.output:
        OUTPUT_DIR = Path(args.output)

    if args.type == "subject":
        if not args.subject:
            print("Error: --subject required for --type subject")
            sys.exit(1)
        builder = SubjectOverviewBuilder(args.subject, no_llm=args.no_llm)
    elif args.type == "weak":
        if not args.subtopic:
            print("Error: --subtopic required for --type weak")
            sys.exit(1)
        builder = WeakTopicBuilder(args.subtopic, no_llm=args.no_llm)
    else:
        builder = DailyBriefBuilder(no_llm=args.no_llm)

    print(f"Generating {args.type} document...")
    content, filename = builder.build()

    out_path = write_output(content, filename)
    words = len(content.split())
    print(f"✅ Generated: {out_path}")
    print(f"   Words: {words:,}")
    print(f"\nNext steps:")
    print(f"  1. Open: {out_path}")
    print(f"  2. Go to: notebooklm.google.com")
    print(f"  3. Create notebook → + Source → Upload → select this file")
    print(f"  4. Click 'Audio Overview' → Generate → wait ~8 min → download & listen")


if __name__ == "__main__":
    main()
