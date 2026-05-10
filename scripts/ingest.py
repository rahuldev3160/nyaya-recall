"""
Main ingestion orchestrator.
Run: python scripts/ingest.py
Re-runs skip already-processed files via ingestion_log.json.
"""
import os
import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime, timezone
from tqdm import tqdm
import chromadb
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from parsers.digital_pdf import extract_text as extract_digital, get_page_text_quality
from parsers.scanned_pdf import extract_text as extract_scanned
from parsers.handwritten_pdf import extract_text as extract_handwritten
from parsers.docx_parser import extract_text as extract_docx
from parsers.pages_converter import extract_text as extract_pages
from parsers.html_parser import extract_text as extract_html
from parsers.textclipping_parser import extract_text as extract_textclipping
from chunker import chunk_text
from embedder import embed_texts

CONTENT_PATH = Path(os.getenv("UPSC_CONTENT_PATH", "/Users/rahulsingh/Desktop/UPSC/Prelims"))
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", "vector_store"))
LOG_PATH = Path(__file__).parent / "ingestion_log.json"

SKIP_DIRS = {"Prelims PYQs"}
SKIP_EXTS = {".ds_store", ".svg"}
HANDWRITTEN_KEYWORDS = {"handwritten", "self notes", "self_notes", "goodnotes", "notability"}

FOLDER_SUBJECT_MAP = {
    "Polity": "polity",
    "Ancient, Medieval, Art & Culture": "history_amac",
    "Modern History": "modern_history",
    "Geography": "geography",
    "Mapping": "geography",
    "Economy": "economy",
    "Environment": "environment",
    "Science and Tech": "science_tech",
    "Current Affairs": "current_affairs",
    "International Relations & Governance": "ir_governance",
    "CSAT": "csat",
}


def load_log() -> dict:
    if LOG_PATH.exists():
        with open(LOG_PATH) as f:
            return json.load(f)
    return {}


def save_log(log: dict) -> None:
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)


def file_hash(path: Path) -> str:
    stat = path.stat()
    return hashlib.sha256(f"{path}:{stat.st_size}:{stat.st_mtime}".encode()).hexdigest()[:16]


def detect_parser(path: Path) -> str:
    name_lower = path.name.lower()
    suffix = path.suffix.lower()

    if suffix == ".docx":
        return "docx"
    if suffix == ".pages":
        return "pages"
    if suffix == ".html" or suffix == ".htm":
        return "html"
    if suffix == ".textclipping":
        return "textclipping"
    if suffix == ".pdf":
        if any(kw in name_lower for kw in HANDWRITTEN_KEYWORDS):
            return "handwritten_pdf"
        quality = get_page_text_quality(str(path))
        if quality < 100:
            return "scanned_pdf"
        return "digital_pdf"
    return "unknown"


def extract(path: Path, parser: str) -> str:
    if parser == "digital_pdf":
        return extract_digital(str(path))
    if parser == "scanned_pdf":
        return extract_scanned(str(path))
    if parser == "handwritten_pdf":
        return extract_handwritten(str(path))
    if parser == "docx":
        return extract_docx(str(path))
    if parser == "pages":
        return extract_pages(str(path))
    if parser == "html":
        return extract_html(str(path))
    if parser == "textclipping":
        return extract_textclipping(str(path))
    return ""


def get_subject(path: Path) -> str:
    for part in path.parts:
        if part in FOLDER_SUBJECT_MAP:
            return FOLDER_SUBJECT_MAP[part]
    return "general"


def ingest_file(path: Path, collection: chromadb.Collection, log: dict) -> bool:
    fhash = file_hash(path)
    if fhash in log:
        return False  # already processed

    suffix = path.suffix.lower()
    if suffix in SKIP_EXTS:
        return False

    parser = detect_parser(path)
    if parser == "unknown":
        return False

    subject_id = get_subject(path)
    source_label = path.name

    try:
        text = extract(path, parser)
    except Exception as e:
        print(f"  ⚠ Failed to parse {path.name}: {e}")
        log[fhash] = {"file": str(path), "status": "failed", "error": str(e),
                      "processed_at": datetime.now(timezone.utc).isoformat()}
        return False

    if not text.strip():
        log[fhash] = {"file": str(path), "status": "empty",
                      "processed_at": datetime.now(timezone.utc).isoformat()}
        return False

    metadata = {"subject_id": subject_id, "source_file": source_label,
                 "parser": parser, "file_path": str(path)}
    chunks = chunk_text(text, metadata)

    if not chunks:
        return False

    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)

    ids = [f"{fhash}_{i}" for i in range(len(chunks))]
    metas = [c["metadata"] for c in chunks]

    collection.add(documents=texts, embeddings=embeddings.tolist(), metadatas=metas, ids=ids)

    log[fhash] = {"file": str(path), "status": "ok", "chunks": len(chunks),
                  "subject": subject_id, "parser": parser,
                  "processed_at": datetime.now(timezone.utc).isoformat()}
    return True


def main():
    print(f"Content path: {CONTENT_PATH}")
    print(f"Vector store: {CHROMA_PATH}\n")

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection("upsc_content")

    log = load_log()
    all_files = []

    for root, dirs, files in os.walk(CONTENT_PATH):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if not fname.startswith("."):
                all_files.append(Path(root) / fname)

    new_count = 0
    for path in tqdm(all_files, desc="Ingesting files"):
        added = ingest_file(path, collection, log)
        if added:
            new_count += 1
            save_log(log)  # save after each file (resume-safe)

    save_log(log)
    total = collection.count()
    print(f"\n✅ Done. New files: {new_count}. Total chunks in store: {total}")


if __name__ == "__main__":
    main()
