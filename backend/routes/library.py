"""Serve indexed source files from UPSC_CONTENT_PATH (read-only, path-validated)."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()


def _content_root() -> Path:
    return Path(os.getenv("UPSC_CONTENT_PATH", "/Users/rahulsingh/Desktop/UPSC/Prelims")).expanduser().resolve()


@router.get("/file")
def get_library_file(rel: str):
    """
    rel: path relative to UPSC_CONTENT_PATH (POSIX-style, e.g. Geography/NCERT_XI.pdf).
    Used by session notes links built from Chroma chunk metadata.
    """
    if not rel or not rel.strip():
        raise HTTPException(status_code=400, detail="rel required")
    decoded = unquote(rel).strip().lstrip("/")
    if ".." in Path(decoded).parts:
        raise HTTPException(status_code=400, detail="invalid path")

    root = _content_root()
    target = (root / decoded).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="path outside content root")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")

    return FileResponse(path=target, filename=target.name)
