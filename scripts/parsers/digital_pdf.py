import pdfplumber


def extract_text(filepath: str) -> str:
    text_parts = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n".join(text_parts)


def get_page_text_quality(filepath: str, sample_pages: int = 3) -> float:
    """Returns avg chars per page. Low value (<100) means likely scanned."""
    try:
        with pdfplumber.open(filepath) as pdf:
            pages = pdf.pages[:sample_pages]
            total = sum(len(p.extract_text() or "") for p in pages)
            return total / max(len(pages), 1)
    except Exception:
        return 0.0
