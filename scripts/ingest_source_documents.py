#!/usr/bin/env python3
"""
Ingest an official communication document (RBI circular/press release, PIB release,
gazette notification, ...) into source_documents. Implements PLAN-009 section 1.D
(.knowledge/plans/PLAN-009.md), grounding material for the bucket-C generation pipeline.

Hard-coded, code-enforced source allowlist (not just documented): rbi.org.in and any
subdomain, pib.gov.in and any subdomain, and any .gov.in domain. This is the direct
structural fix for BUG-035's root cause -- a scraper pointed at an unofficial
coaching-site aggregator. A URL outside the allowlist is rejected, not silently skipped.

Real-world fetch constraint discovered while building this (documented, not hidden):
RBI's direct PDF links (rbidocs.rbi.org.in/.../*.PDF) sit behind a bot-protection
CAPTCHA that blocks both a plain `requests` fetch and a browser-driven fetch. RBI's own
HTML press-release pages (rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=...) are
NOT protected and fetch cleanly. For a URL that resists a direct fetch, pass
--text-file with text already extracted by some other means (e.g. a browser-based
fetch) -- the allowlist and sanity checks still apply to the ORIGINAL --url, so this is
not a bypass of provenance tracking, only of the fetch mechanism.

De-dupe: content_hash (sha256 of the normalized extracted text) is UNIQUE. Re-ingesting
identical content is a no-op that reports the existing row, never a duplicate insert.

Sanity gate (rejects obvious non-content before it ever reaches the DB): text shorter
than 200 characters, or containing a bot-protection/CAPTCHA marker, is refused outright
-- storing a CAPTCHA page as if it were a real circular is exactly the class of mistake
BUG-035 was.

Usage:
    python scripts/ingest_source_documents.py --url <url> --exam-source rbi_grade_b \
        --doc-type rbi_press_release [--title "..."] [--publish-date 2026-08-05] \
        [--text-file path/to/already-extracted.txt]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import os

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "upsc.db"))
DOC_STORE_DIR = Path(__file__).parent.parent / "data" / "source_documents"

ALLOWED_EXACT_OR_SUBDOMAIN = ("rbi.org.in", "pib.gov.in")
ALLOWED_SUFFIX = (".gov.in",)

BOT_PROTECTION_MARKERS = (
    "captcha",
    "verify you are human",
    "checking your browser",
    "access denied",
    "cloudflare",
    "are you a robot",
    "javascript must be enabled",
    "javascript is either disabled",
    "enable javascript",
    "please enable javascript",
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) NyayaRecall-SourceIngest/1.0"
)


class RejectedURL(Exception):
    pass


class RejectedContent(Exception):
    pass


def check_allowlist(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        raise RejectedURL(f"Could not parse a hostname from URL: {url}")

    for allowed in ALLOWED_EXACT_OR_SUBDOMAIN:
        if host == allowed or host.endswith("." + allowed):
            return
    for suffix in ALLOWED_SUFFIX:
        if host.endswith(suffix):
            return

    raise RejectedURL(
        f"Host '{host}' is not on the official-source allowlist "
        f"(rbi.org.in, pib.gov.in, or any *.gov.in domain). Refusing to ingest. "
        f"This is the BUG-035 prevention gate -- do not add a new domain here without "
        f"confirming it is an official government/regulator source."
    )


def fetch_via_requests(url: str) -> str:
    import requests

    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")

    if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
        import pdfplumber

        text_parts = []
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def sanity_check(text: str) -> None:
    stripped = text.strip()
    if len(stripped) < 200:
        raise RejectedContent(
            f"Extracted text is only {len(stripped)} characters -- too short to be "
            f"real document content. Refusing to store. If this URL needs a "
            f"browser-based fetch to get past bot protection, use --text-file with "
            f"text extracted some other way."
        )
    lowered = stripped.lower()
    for marker in BOT_PROTECTION_MARKERS:
        if marker in lowered:
            raise RejectedContent(
                f"Extracted text contains the bot-protection marker '{marker}' -- this "
                f"looks like a CAPTCHA/challenge page, not real document content. "
                f"Refusing to store. Use --text-file with text extracted a different way."
            )


def content_hash_of(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def find_existing_by_hash(con: sqlite3.Connection, content_hash: str) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM source_documents WHERE content_hash = ?", (content_hash,)
    ).fetchone()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="Source URL (checked against the allowlist regardless of --text-file)")
    parser.add_argument("--exam-source", required=True, help="e.g. rbi_grade_b, vision_ias")
    parser.add_argument("--doc-type", required=True, help="e.g. rbi_press_release, rbi_circular, pib_release, gazette_notification")
    parser.add_argument("--title", default=None, help="Document title (defaults to a placeholder derived from the URL if omitted)")
    parser.add_argument("--publish-date", default=None, help="YYYY-MM-DD, optional")
    parser.add_argument("--text-file", default=None, help="Use pre-extracted text from this file instead of fetching --url directly")
    args = parser.parse_args()

    try:
        check_allowlist(args.url)
    except RejectedURL as e:
        print(f"REJECTED (allowlist): {e}", file=sys.stderr)
        return 1

    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8")
    else:
        try:
            text = fetch_via_requests(args.url)
        except Exception as e:
            print(f"FETCH FAILED: {e}", file=sys.stderr)
            print(
                "If this is a bot-protected endpoint (known issue: rbidocs.rbi.org.in "
                "direct PDF links), extract the text some other way and re-run with "
                "--text-file.",
                file=sys.stderr,
            )
            return 1

    try:
        sanity_check(text)
    except RejectedContent as e:
        print(f"REJECTED (content sanity check): {e}", file=sys.stderr)
        return 1

    chash = content_hash_of(text)

    con = get_conn()
    existing = find_existing_by_hash(con, chash)
    if existing:
        print(f"Already ingested: id={existing['id']}, title={existing['title']!r} (content_hash matches, no-op).")
        con.close()
        return 0

    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    title = args.title or f"[untitled] {urlparse(args.url).path.rsplit('/', 1)[-1]}"
    ingested_at = datetime.now(timezone.utc).isoformat()

    DOC_STORE_DIR.mkdir(parents=True, exist_ok=True)
    text_path = DOC_STORE_DIR / f"{doc_id}.txt"
    text_path.write_text(text, encoding="utf-8")

    con.execute(
        """INSERT INTO source_documents
           (id, doc_type, title, source_url, publish_date, ingested_at, exam_source, raw_text_ref, content_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (doc_id, args.doc_type, title, args.url, args.publish_date, ingested_at,
         args.exam_source, str(text_path.relative_to(Path(__file__).parent.parent)), chash),
    )
    con.commit()
    con.close()

    print(f"Ingested: id={doc_id}")
    print(f"  title: {title}")
    print(f"  exam_source: {args.exam_source}  doc_type: {args.doc_type}")
    print(f"  raw_text_ref: {text_path.relative_to(Path(__file__).parent.parent)}")
    print(f"  content_hash: {chash}")
    print(f"  text length: {len(text)} chars")
    print(f"  snippet: {text[:300].strip()!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
