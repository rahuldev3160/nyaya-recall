"""Thin HTTP client for nyaya-core's local API (see nyaya-core/src/api/, bound to
127.0.0.1 only — same-machine only, matches this repo's own local-first design).

Every call fails loudly (raises NyayaCoreUnavailableError) rather than returning an
empty/stub result — 100% of PFRDA/EPFO content lives in nyaya-core, none in this repo's
own upsc.db, so there is no safe local fallback to silently degrade to (matches
nyaya-core's own DECIDE-10: "insufficient grounding is a signal, never a silent
fallback"). Uses stdlib urllib only — no new dependency for a handful of JSON GET/POSTs.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

NYAYA_CORE_API_URL = os.getenv("NYAYA_CORE_API_URL", "http://127.0.0.1:8420")
TIMEOUT_SECONDS = 10


class NyayaCoreUnavailableError(RuntimeError):
    """nyaya-core's API couldn't be reached at all (connection refused, timeout) — there
    is no local fallback for PFRDA/EPFO content, so callers should surface this as a
    clear service-down error (502), never silently degrade."""


class NyayaCoreClientError(RuntimeError):
    """nyaya-core responded but rejected the request (4xx) — a real client error (e.g.
    unknown question_id), not a service-availability problem. Callers should propagate
    `status_code`/the message as-is, not mask it as "unavailable."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"nyaya-core {status_code}: {detail}")


def _request(method: str, path: str, params: Optional[dict] = None, json_body: Optional[dict] = None) -> Any:
    url = f"{NYAYA_CORE_API_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})

    data = json.dumps(json_body).encode() if json_body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            detail = body
        raise NyayaCoreClientError(exc.code, detail) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise NyayaCoreUnavailableError(
            f"Could not reach nyaya-core's API at {NYAYA_CORE_API_URL} ({exc}). "
            "Start it with: .venv/bin/python -m src.api.main (from the nyaya-core repo)."
        ) from exc


def get_exams() -> list[dict]:
    return _request("GET", "/exams")


def get_topics(exam_id: str, paper_id: Optional[str] = None) -> list[dict]:
    return _request("GET", "/topics", {"exam_id": exam_id, "paper_id": paper_id})


def get_papers(exam_id: str) -> list[dict]:
    return _request("GET", "/papers", {"exam_id": exam_id})


def get_pyq(
    exam_id: str,
    paper_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    question_format: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    return _request(
        "GET",
        "/pyq",
        {
            "exam_id": exam_id,
            "paper_id": paper_id,
            "topic_id": topic_id,
            "question_format": question_format,
            "status": status,
            "limit": limit,
        },
    )


def search(query: str, exam_id: str, paper_id: Optional[str] = None, topic_id: Optional[str] = None, k: int = 8) -> dict:
    return _request("GET", "/search", {"q": query, "exam_id": exam_id, "paper_id": paper_id, "topic_id": topic_id, "k": k})


def post_attempt(question_id: str, chosen_option: str) -> dict:
    return _request("POST", "/attempt", json_body={"question_id": question_id, "chosen_option": chosen_option})


def get_attempted_question_ids(exam_id: str) -> list[str]:
    return _request("GET", "/attempts", {"exam_id": exam_id})
