from __future__ import annotations
from sentence_transformers import SentenceTransformer
import numpy as np
import torch

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        _model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
    return _model


def embed_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    return get_model().encode(texts, batch_size=batch_size, show_progress_bar=False)
