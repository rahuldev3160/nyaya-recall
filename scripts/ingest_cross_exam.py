#!/usr/bin/env python3
"""
Ingest CDS/NDA/CAPF/CISF PYQs into the question_bank table.

Pipeline:
  1. Extract text from PDF via pdfplumber (digital) or OCR (scanned)
  2. Chunk text into ~4-page segments
  3. Send each chunk to Haiku for MCQ extraction + UPSC taxonomy classification
  4. Filter out `out_of_scope` questions (NDA Maths, CDS English, etc.)
  5. INSERT OR IGNORE into question_bank (dedup via question_hash)

Usage:
    cd scripts
    python ingest_cross_exam.py --exam cds --year 2024 --pdf /path/to/cds_2024_gk.pdf
    python ingest_cross_exam.py --exam nda --year 2023 --pdf /path/to/nda_2023_gat.pdf --paper I
    python ingest_cross_exam.py --exam capf --year 2022 --pdf /path/to/capf_2022.pdf
    python ingest_cross_exam.py --exam cds --year 2024 --pdf /path/to/ --batch  # all PDFs in dir
    python ingest_cross_exam.py --dry-run --exam cds --year 2024 --pdf file.pdf  # no DB write

Supported exam values: cds, nda, capf, cisf, cms
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber not installed. Run: pip install pdfplumber")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic not installed. Run: pip install anthropic")
    sys.exit(1)

DB_PATH     = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "cross_exam_classify.txt"
LOG_PATH    = Path(__file__).parent / "cross_exam_ingestion_log.json"
CACHE_DIR   = Path(__file__).parent.parent / "cache" / "cross_exam_classify"

MODEL      = "claude-haiku-4-5-20251001"
MAX_TOKENS = 4096
PAGES_PER_CHUNK = 4

VALID_EXAMS   = {"cds", "nda", "capf", "cisf", "cms", "geoscientist"}
OUT_OF_SCOPE  = "out_of_scope"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def question_hash(question_text: str, exam: str, year: int) -> str:
    key = f"{exam}:{year}:{question_text[:200]}"
    return hashlib.sha256(key.encode()).hexdigest()[:24]


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def clean_bilingual_text(text: str) -> str:
    """Remove lines that are predominantly non-ASCII (Hindi OCR) keeping English."""
    lines = []
    for line in text.split("\n"):
        if not line.strip():
            lines.append("")
            continue
        ascii_chars = sum(1 for c in line if ord(c) < 128)
        if ascii_chars / len(line) >= 0.55:
            lines.append(line)
    return "\n".join(lines)


def extract_pdf_text(pdf_path: Path) -> list[str]:
    """Return list of page texts."""
    pages: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(clean_bilingual_text(text))
    except Exception as e:
        print(f"  WARNING: pdfplumber failed ({e}). Trying OCR fallback.")
        try:
            from parsers.scanned_pdf import extract_text as ocr_extract
            pages = ocr_extract(str(pdf_path))
        except Exception as e2:
            print(f"  ERROR: OCR also failed ({e2}). Skipping file.")
            return []
    return pages


def chunk_pages(pages: list[str], chunk_size: int = PAGES_PER_CHUNK) -> list[str]:
    chunks = []
    for i in range(0, len(pages), chunk_size):
        chunk = "\n".join(pages[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# Claude extraction
# ---------------------------------------------------------------------------

def classify_chunk(
    chunk: str,
    template: str,
    exam: str,
    year: int,
    paper: str | None,
    cache_key: str,
) -> list[dict]:
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    paper_suffix = f" Paper {paper}" if paper else ""
    prompt = (
        template
        .replace("{{exam}}", exam.upper())
        .replace("{{year}}", str(year))
        .replace("{{paper_suffix}}", paper_suffix)
        .replace("{{TEXT}}", chunk[:8000])  # hard limit to avoid token overrun
    )

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if isinstance(data, list):
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data))
            return data
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e} — skipping chunk")
    except anthropic.APIError as e:
        print(f"  API error: {e} — retrying in 5s")
        time.sleep(5)
    return []


# ---------------------------------------------------------------------------
# DB insertion
# ---------------------------------------------------------------------------

def insert_questions(
    con: sqlite3.Connection,
    questions: list[dict],
    exam: str,
    year: int,
    paper: str | None,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    inserted = skipped_scope = skipped_dup = 0

    for q in questions:
        subject_id = q.get("subject_id", "")
        if subject_id == OUT_OF_SCOPE:
            skipped_scope += 1
            continue

        question_text = (q.get("question_text") or "").strip()
        if not question_text or len(question_text) < 10:
            continue

        qhash = question_hash(question_text, exam, year)
        qid   = str(uuid.uuid4())

        option_a = (q.get("option_a") or "").strip()
        option_b = (q.get("option_b") or "").strip()
        option_c = (q.get("option_c") or "").strip()
        option_d = (q.get("option_d") or "").strip()
        if not all([option_a, option_b, option_c, option_d]):
            continue  # incomplete options — skip

        correct_answer = (q.get("correct_answer") or "").strip().lower() or None
        topic_id       = (q.get("topic_id") or "").strip() or "general"
        subtopic_id    = (q.get("subtopic_id") or "").strip() or topic_id
        question_type  = q.get("question_type") or "direct"
        difficulty     = q.get("difficulty") or "medium"

        if dry_run:
            print(f"  [DRY RUN] Would insert: {exam.upper()} {year} | {subject_id} | {question_text[:60]}…")
            inserted += 1
            continue

        try:
            con.execute(
                """
                INSERT OR IGNORE INTO question_bank
                    (id, question_hash, question_text,
                     option_a, option_b, option_c, option_d,
                     correct_answer, answer_source, exam_source, year, paper,
                     subject_id, topic_id, subtopic_id,
                     question_type, upsc_relevance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    qid, qhash, question_text,
                    option_a, option_b, option_c, option_d,
                    correct_answer,
                    "official_key" if correct_answer else "ai_inferred",
                    exam, year, paper,
                    subject_id, topic_id, subtopic_id,
                    question_type,
                    0.9 if exam in ("cds", "capf") else 0.75,  # CDS/CAPF closer to CS Prelims
                ),
            )
            if con.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
            else:
                skipped_dup += 1
        except sqlite3.Error as e:
            print(f"  DB error: {e}")

    if not dry_run and inserted:
        con.commit()

    return inserted, skipped_scope, skipped_dup


# ---------------------------------------------------------------------------
# Log helpers
# ---------------------------------------------------------------------------

def load_log() -> dict:
    return json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else {}


def save_log(log: dict) -> None:
    LOG_PATH.write_text(json.dumps(log, indent=2))


def log_key(pdf_path: Path, exam: str, year: int, paper: str | None) -> str:
    return f"{exam}:{year}:{paper or 'gk'}:{pdf_path.stem}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_file(
    pdf_path: Path,
    exam: str,
    year: int,
    paper: str | None,
    template: str,
    dry_run: bool,
    force: bool,
) -> None:
    log = load_log()
    lk  = log_key(pdf_path, exam, year, paper)

    if lk in log and not force:
        print(f"  Already ingested (use --force to re-run): {lk}")
        return

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing: {pdf_path.name}")

    pages = extract_pdf_text(pdf_path)
    if not pages:
        print("  ERROR: No text extracted.")
        return
    print(f"  {len(pages)} pages extracted")

    chunks = chunk_pages(pages)
    print(f"  {len(chunks)} chunks of ≤{PAGES_PER_CHUNK} pages")

    con = get_conn()
    total_inserted = total_scope = total_dup = 0

    for i, chunk in enumerate(chunks):
        cache_key = hashlib.sha256(f"{lk}:chunk{i}:{chunk[:100]}".encode()).hexdigest()[:16]
        questions = classify_chunk(chunk, template, exam, year, paper, cache_key)
        print(f"  Chunk {i+1}/{len(chunks)}: {len(questions)} questions extracted")

        ins, scope, dup = insert_questions(con, questions, exam, year, paper, dry_run)
        total_inserted += ins
        total_scope    += scope
        total_dup      += dup

    con.close()

    print(f"  Summary: inserted={total_inserted} out_of_scope={total_scope} duplicates={total_dup}")

    if not dry_run:
        log[lk] = {
            "pdf": str(pdf_path),
            "exam": exam,
            "year": year,
            "paper": paper,
            "inserted": total_inserted,
            "out_of_scope": total_scope,
            "duplicates": total_dup,
        }
        save_log(log)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest cross-exam PYQs into question_bank.")
    parser.add_argument("--exam",  required=True, choices=sorted(VALID_EXAMS), help="Exam identifier")
    parser.add_argument("--year",  required=True, type=int, help="Exam year")
    parser.add_argument("--pdf",   required=True, help="Path to PDF file (or directory with --batch)")
    parser.add_argument("--paper", help="Paper identifier (e.g. I, II, GK) — for exams with multiple papers")
    parser.add_argument("--batch", action="store_true", help="Process all PDFs in the given directory")
    parser.add_argument("--dry-run", action="store_true", help="Parse and classify but do NOT write to DB")
    parser.add_argument("--force",   action="store_true", help="Re-process files already in the log")
    args = parser.parse_args()

    if not PROMPT_PATH.exists():
        print(f"ERROR: Prompt not found: {PROMPT_PATH}")
        return 1

    template = PROMPT_PATH.read_text()
    pdf_target = Path(args.pdf)

    if args.batch:
        if not pdf_target.is_dir():
            print("ERROR: --batch requires a directory path")
            return 1
        pdfs = sorted(pdf_target.glob("*.pdf"))
        if not pdfs:
            print(f"No PDFs found in: {pdf_target}")
            return 1
        print(f"Found {len(pdfs)} PDFs to process")
        for pdf in pdfs:
            process_file(pdf, args.exam, args.year, args.paper, template, args.dry_run, args.force)
    else:
        if not pdf_target.exists():
            print(f"ERROR: File not found: {pdf_target}")
            return 1
        process_file(pdf_target, args.exam, args.year, args.paper, template, args.dry_run, args.force)

    return 0


if __name__ == "__main__":
    sys.exit(main())
