import re
from typing import Any

CHUNK_SIZE_WORDS = 375   # ≈500 tokens
OVERLAP_WORDS = 38       # ≈50 tokens


def chunk_text(text: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text).strip()
    if not text:
        return []

    words = text.split()
    if len(words) < 50:
        return [{"text": text, "metadata": {**metadata, "chunk_index": 0, "total_chunks": 1}}]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE_WORDS, len(words))
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - OVERLAP_WORDS

    return [
        {"text": c, "metadata": {**metadata, "chunk_index": i, "total_chunks": len(chunks)}}
        for i, c in enumerate(chunks)
    ]
