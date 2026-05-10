"""Cache AI-generated explanations by hash. Never regenerate the same content."""
from __future__ import annotations
import json
import hashlib
import os
from pathlib import Path

CACHE_PATH = os.getenv("CACHE_PATH", "cache/explanations.json")


def _load() -> dict:
    path = Path(CACHE_PATH)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _save(data: dict) -> None:
    Path(CACHE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def make_key(question_text: str, subtopic_id: str) -> str:
    raw = f"{subtopic_id}::{question_text[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get(question_text: str, subtopic_id: str) -> str | None:
    return _load().get(make_key(question_text, subtopic_id))


def set(question_text: str, subtopic_id: str, explanation: str) -> None:
    data = _load()
    data[make_key(question_text, subtopic_id)] = explanation
    _save(data)
