"""
PYQ extraction and classification pipeline.
Processes year-wise PDFs + Microthemes compilation.
Classifies each question using Claude Haiku → stores in SQLite.
Run once: python scripts/ingest_pyq.py
"""
from __future__ import annotations
import os
import json
import hashlib
import sqlite3
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from tqdm import tqdm
import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from parsers.digital_pdf import extract_text as extract_digital, get_page_text_quality
from parsers.scanned_pdf import extract_text as extract_scanned

DB_PATH = os.getenv("DB_PATH", "data/upsc.db")
PYQ_PATH = Path(os.getenv("UPSC_CONTENT_PATH", "/Users/rahulsingh/Desktop/UPSC/Prelims")) / "Prelims PYQs"
CLASSIFY_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "pyq_classify.txt"
LOG_PATH = Path(__file__).parent / "pyq_ingestion_log.json"

YEAR_PATTERN = re.compile(r"\b(20\d{2}|19\d{2})\b")
YEARWISE_PATTERN = re.compile(r"(?:^|_)(\d{4})(?:_|\.pdf$)", re.IGNORECASE)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_log() -> dict:
    return json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else {}


def save_log(log: dict):
    LOG_PATH.write_text(json.dumps(log, indent=2))


def question_hash(text: str, year: int) -> str:
    return hashlib.sha256(f"{year}:{text[:200]}".encode()).hexdigest()[:20]


def detect_year_from_filename(path: Path) -> int | None:
    m = YEARWISE_PATTERN.search(path.name)
    if m:
        return int(m.group(1))
    return None


def clean_bilingual_text(text: str) -> str:
    """Remove lines that are predominantly non-ASCII (Hindi OCR garbage) keeping English."""
    cleaned = []
    for line in text.split("\n"):
        if not line.strip():
            cleaned.append("")
            continue
        ascii_chars = sum(1 for c in line if ord(c) < 128)
        ratio = ascii_chars / len(line)
        if ratio >= 0.6:  # keep lines that are ≥60% ASCII
            cleaned.append(line)
    return "\n".join(cleaned)


Q_NUMBER_RE = re.compile(r"^(?:Q\.?\s*)?(\d{1,3})[\.\)]\s")


def extract_q_number(block: str) -> int | None:
    """Extract the leading question number from a question block, if present."""
    m = Q_NUMBER_RE.match(block.strip())
    if m:
        return int(m.group(1))
    return None


def extract_questions_from_text(text: str) -> list[str]:
    """Split raw PDF text into individual question blocks."""
    text = clean_bilingual_text(text)

    # Match numbered questions: "1.", "2.", ... with flexible spacing
    blocks = re.split(r"\n\s*(?=(?:Q\.?\s*)?\b\d{1,3}[\.\)]\s)", text)
    questions = []
    for block in blocks:
        block = block.strip()
        has_options = any(opt in block for opt in ["(a)", "(A)", "(b)", "(B)", "(c)", "(C)"])
        if len(block) > 60 and has_options:
            questions.append(block)

    # Fallback: accumulate chunks until we have a full question with all 4 options
    if len(questions) < 5:
        chunks = re.split(r"\n{2,}", text)
        current = []
        for chunk in chunks:
            current.append(chunk)
            combined = "\n".join(current)
            has_a = any(o in combined for o in ["(a)", "(A)"])
            has_d = any(o in combined for o in ["(d)", "(D)"])
            if has_a and has_d and len(combined) > 80:
                questions.append(combined.strip())
                current = []

    return questions[:150]


def extract_questions_via_ai(path: str, year: int) -> list[str]:
    """Page-by-page Claude Haiku extraction for bilingual/garbled scanned papers."""
    from pdf2image import convert_from_path as cfp
    import pytesseract

    print(f"  Using page-by-page AI extraction for {Path(path).name}...")
    try:
        images = cfp(path, dpi=250)
    except Exception as e:
        print(f"  pdf2image failed: {e}")
        return []

    all_questions = []
    # Process 2 pages at a time to give Claude enough context per question
    for i in range(0, len(images), 2):
        page_text = "\n\n--- PAGE BREAK ---\n\n".join(
            pytesseract.image_to_string(img) for img in images[i:i+2]
        )
        if not page_text.strip() or len(page_text) < 100:
            continue
        try:
            resp = client.messages.create(
                model=os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001"),
                max_tokens=3000,
                messages=[{"role": "user", "content": (
                    f"This is OCR text from pages {i+1}-{i+2} of the UPSC Prelims {year} GS Paper 1. "
                    "The scan may be bilingual (Hindi+English) or have OCR noise. "
                    "Extract every complete English MCQ question you can find. "
                    "Each question has a stem and options (a)(b)(c)(d). "
                    "Return ONLY a JSON array of strings, each string being one complete question block "
                    "(stem + all options). Example: [\"1. Which of the following...\\n(a) X\\n(b) Y\\n(c) Z\\n(d) W\"]. "
                    "If no questions found, return [].\n\n"
                    + page_text
                )}]
            )
            raw = resp.content[0].text.strip()
            start, end = raw.find("["), raw.rfind("]") + 1
            if start >= 0 and end > start:
                import json as _json
                blocks = _json.loads(raw[start:end])
                all_questions.extend(b for b in blocks if isinstance(b, str) and len(b) > 60)
        except Exception as e:
            continue

    # Deduplicate
    seen, unique = set(), []
    for q in all_questions:
        key = q[:80]
        if key not in seen:
            seen.add(key)
            unique.append(q)
    print(f"  AI extraction found {len(unique)} questions")
    return unique[:150]


def classify_batch(questions: list[str], year: int) -> list[dict]:
    """Send up to 20 questions to Claude Haiku for classification."""
    prompt_template = CLASSIFY_PROMPT_PATH.read_text()
    batch_text = "\n\n---\n\n".join(
        f"Q{i+1} (Year: {year}):\n{q}" for i, q in enumerate(questions)
    )
    prompt = prompt_template.replace("{{QUESTIONS}}", batch_text)

    response = client.messages.create(
        model=os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        return json.loads(raw[start:end])
    except Exception:
        return []


def _has_q_number_column(cur: sqlite3.Cursor) -> bool:
    cur.execute("PRAGMA table_info(pyq_questions)")
    return any(row[1] == "q_number" for row in cur.fetchall())


def store_questions(classified: list[dict], source_file: str, year: int):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    use_q_number = _has_q_number_column(cur)
    inserted = 0
    for q in classified:
        if not q or not (q.get("question_text") or "").strip():
            continue
        qhash = question_hash(q.get("question_text") or "", year)
        q_number = extract_q_number(q.get("question_text") or "")
        try:
            if use_q_number:
                cur.execute("""
                    INSERT OR IGNORE INTO pyq_questions
                    (year, q_number, question_text, option_a, option_b, option_c, option_d,
                     correct_answer, subject_id, topic_id, subtopic_id, concepts, source_file, question_hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    year, q_number,
                    q.get("question_text") or "",
                    q.get("option_a"), q.get("option_b"),
                    q.get("option_c"), q.get("option_d"),
                    q.get("correct_answer"),
                    q.get("subject_id"), q.get("topic_id"), q.get("subtopic_id"),
                    json.dumps(q.get("concepts", [])),
                    source_file, qhash
                ))
            else:
                cur.execute("""
                    INSERT OR IGNORE INTO pyq_questions
                    (year, question_text, option_a, option_b, option_c, option_d,
                     correct_answer, subject_id, topic_id, subtopic_id, concepts, source_file, question_hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    year,
                    q.get("question_text") or "",
                    q.get("option_a"), q.get("option_b"),
                    q.get("option_c"), q.get("option_d"),
                    q.get("correct_answer"),
                    q.get("subject_id"), q.get("topic_id"), q.get("subtopic_id"),
                    json.dumps(q.get("concepts", [])),
                    source_file, qhash
                ))
            inserted += 1
        except Exception:
            pass
    con.commit()
    con.close()
    return inserted


def process_file(path: Path, year: int | None, log: dict) -> int:
    fkey = f"{path.name}:{year}"
    if fkey in log:
        return 0

    quality = get_page_text_quality(str(path))
    text = extract_digital(str(path)) if quality >= 100 else extract_scanned(str(path))

    if not text.strip():
        log[fkey] = "empty"
        return 0

    # If year unknown (compilation), try to detect from text context
    questions_raw = extract_questions_from_text(text)
    # Fallback to AI extraction for bilingual/garbled papers
    if len(questions_raw) < 10:
        print(f"  Regex found only {len(questions_raw)} Qs, switching to AI extraction...")
        questions_raw = extract_questions_via_ai(str(path), year or 0)
    if not questions_raw:
        log[fkey] = "no_questions_found"
        return 0

    total_inserted = 0
    batch_size = 20
    for i in range(0, len(questions_raw), batch_size):
        batch = questions_raw[i:i + batch_size]
        classified = classify_batch(batch, year or 0)
        if classified:
            total_inserted += store_questions(classified, path.name, year or 0)

    log[fkey] = {"inserted": total_inserted, "processed_at": datetime.now(timezone.utc).isoformat()}
    return total_inserted


def main():
    from db_init import init_db
    init_db()

    log = load_log()
    total = 0

    # Tier 1: year-wise PDFs
    yearwise = sorted(PYQ_PATH.glob("*.pdf"))
    yearwise = [f for f in yearwise if YEARWISE_PATTERN.search(f.name)]
    print(f"Found {len(yearwise)} year-wise PYQ files")

    for path in tqdm(yearwise, desc="Year-wise PYQs"):
        year = detect_year_from_filename(path)
        if not year:
            continue
        n = process_file(path, year, log)
        total += n
        save_log(log)

    # Tier 2: Microthemes compilation (2009-2025)
    compilation = PYQ_PATH / "Microthemes_PYQs _2009-2025.pdf"
    if compilation.exists():
        print("\nProcessing Microthemes compilation (2009-2025)...")
        n = process_file(compilation, None, log)
        total += n
        save_log(log)

    print(f"\n✅ PYQ ingestion complete. Total questions stored: {total}")


if __name__ == "__main__":
    main()
