"""HTTP-backed context_utils -- routes all context operations through the Flywheel API.

Provides the same 7-function API surface as storage_backend.py but sends
requests over HTTP to a hosted Flywheel API instead of accessing files or
Postgres directly.  Designed for ``FLYWHEEL_BACKEND=remote``.
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import httpx

from flywheel_cli.auth import get_token
from flywheel_cli.config import get_api_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level HTTP client singleton
# ---------------------------------------------------------------------------

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """Return (or create) the module-level httpx client."""
    global _client
    if _client is None:
        _client = httpx.Client(timeout=30.0)
    return _client


def _auth_headers() -> dict[str, str]:
    """Return Authorization header with current access token."""
    return {"Authorization": f"Bearer {get_token()}"}


def _api(path: str) -> str:
    """Build a full API URL for the given path."""
    return f"{get_api_url()}/api/v1{path}"


def _handle_response(resp: httpx.Response) -> httpx.Response:
    """Raise a helpful RuntimeError on HTTP or connection errors."""
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Try to extract a message from the JSON body
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(
            f"Flywheel API error ({resp.status_code}): {detail}"
        ) from exc
    return resp


# ---------------------------------------------------------------------------
# v1-compatible text formatting
# ---------------------------------------------------------------------------

# Entry header regex (same as v1 context_utils.py)
_ENTRY_HEADER_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2})\s*\|\s*source:\s*([^|\]]+?)(?:\s*\|\s*(.+?))?\]"
)


def _format_as_v1_text(entries: list[dict]) -> str:
    """Format a list of API entry dicts into v1-compatible markdown text.

    Each entry dict is expected to have: date, source, detail (optional),
    confidence, evidence_count, content.
    """
    if not entries:
        return ""

    blocks: list[str] = []
    for e in entries:
        date = e.get("date", "")
        # If date is a full ISO timestamp, take just the date part
        if date and "T" in date:
            date = date.split("T")[0]
        source = e.get("source", "unknown")
        detail = e.get("detail", "")
        confidence = e.get("confidence", "medium")
        evidence = e.get("evidence_count", 1)
        content = e.get("content", "")

        # Build header
        header_parts = [date, f"source: {source}"]
        if detail:
            header_parts.append(detail)
        header = f"[{' | '.join(header_parts)}]"

        # Build metadata line
        meta = f"confidence: {confidence} | evidence: {evidence}"

        # Build content lines
        content_lines = content.rstrip("\n") if content else ""

        block = f"{header} {meta}\n{content_lines}"
        blocks.append(block)

    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# v1-compatible entry parsing (local, no HTTP)
# ---------------------------------------------------------------------------


def parse_context_file(text: str) -> list[dict]:
    """Parse v1-format markdown text into a list of entry dicts.

    This is a pure local operation -- no HTTP call.  Mirrors the regex-based
    parser from v1 context_utils.py.
    """
    if not text or not text.strip():
        return []

    entries: list[dict] = []
    header_matches = list(_ENTRY_HEADER_RE.finditer(text))
    if not header_matches:
        return []

    for i, match in enumerate(header_matches):
        header_end = match.end()
        body_end = header_matches[i + 1].start() if i + 1 < len(header_matches) else len(text)
        body = text[header_end:body_end]

        date_str = match.group(1)
        source = match.group(2).strip()
        detail = match.group(3).strip() if match.group(3) else ""

        # Parse metadata and content from body
        evidence_count = 1
        confidence = "medium"
        content_lines: list[str] = []

        # Check for inline metadata on the header line remainder
        first_line_rest = body.split("\n", 1)
        first_line = first_line_rest[0].strip() if first_line_rest else ""
        remaining = first_line_rest[1] if len(first_line_rest) > 1 else ""

        # Try to parse confidence/evidence from first line (inline metadata)
        inline_meta = re.match(
            r"\s*confidence:\s*(\w+)\s*\|\s*evidence:\s*(\d+)", first_line
        )
        if inline_meta:
            confidence = inline_meta.group(1).lower()
            evidence_count = int(inline_meta.group(2))
            body_to_parse = remaining
        else:
            body_to_parse = body

        for line in body_to_parse.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            ev_match = re.match(r"evidence_count:\s*(\d+)", stripped)
            if ev_match:
                evidence_count = int(ev_match.group(1))
                continue

            conf_match = re.match(r"confidence:\s*(\w+)", stripped)
            if conf_match:
                confidence = conf_match.group(1).lower()
                continue

            content_lines.append(line.rstrip())

        entries.append({
            "date": date_str,
            "source": source,
            "detail": detail,
            "confidence": confidence,
            "evidence_count": evidence_count,
            "content": "\n".join(content_lines),
        })

    return entries


# ---------------------------------------------------------------------------
# Public API (7 functions)
# ---------------------------------------------------------------------------


def read_context(file: str, **kwargs: Any) -> str:
    """Read all entries from a context file, returning v1-format markdown text.

    Paginates automatically if the server returns ``has_more=True``.
    """
    client = _get_client()
    all_entries: list[dict] = []
    offset = 0
    limit = 100

    try:
        while True:
            resp = _handle_response(
                client.get(
                    _api(f"/context/files/{file}/entries"),
                    params={"offset": offset, "limit": limit, **kwargs},
                    headers=_auth_headers(),
                )
            )
            data = resp.json()
            items = data.get("items", [])
            all_entries.extend(items)

            if not data.get("has_more", False):
                break
            offset += limit

    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Cannot connect to Flywheel API at {get_api_url()}. Is the server running?"
        ) from exc

    return _format_as_v1_text(all_entries)


def append_entry(file: str, entry: dict, source: str, **kwargs: Any) -> dict:
    """Append a single entry to a context file via the API."""
    client = _get_client()
    body = {
        "content": entry["content"],
        "source": source,
        "detail": entry.get("detail"),
        "confidence": entry.get("confidence", "medium"),
    }
    try:
        resp = _handle_response(
            client.post(
                _api(f"/context/files/{file}/entries"),
                json=body,
                headers=_auth_headers(),
            )
        )
        return resp.json()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Cannot connect to Flywheel API at {get_api_url()}. Is the server running?"
        ) from exc


def query_context(file: str, search: str | None = None, **kwargs: Any) -> list:
    """Query entries from a context file with optional search/filter params."""
    client = _get_client()
    params: dict[str, Any] = {**kwargs}
    if search:
        params["search"] = search

    try:
        resp = _handle_response(
            client.get(
                _api(f"/context/files/{file}/entries"),
                params=params,
                headers=_auth_headers(),
            )
        )
        return resp.json().get("items", [])
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Cannot connect to Flywheel API at {get_api_url()}. Is the server running?"
        ) from exc


class _BatchOperation:
    """Accumulates entries and sends them in a single POST on exit."""

    def __init__(self, source: str) -> None:
        self.source = source
        self._entries: list[dict] = []

    def append_entry(self, file: str, entry: dict) -> None:
        """Stage an entry for batch submission."""
        self._entries.append({
            "file_name": file,
            "content": entry["content"],
            "source": self.source,
            "detail": entry.get("detail"),
            "confidence": entry.get("confidence", "medium"),
        })

    def _send(self) -> None:
        """Send all accumulated entries in one request."""
        if not self._entries:
            return

        client = _get_client()
        try:
            _handle_response(
                client.post(
                    _api("/context/batch"),
                    json={"entries": self._entries},
                    headers=_auth_headers(),
                )
            )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to Flywheel API at {get_api_url()}. Is the server running?"
            ) from exc


@contextmanager
def batch_context(source: str):
    """Context manager that batches append_entry calls into a single POST.

    Usage::

        with batch_context("my-skill") as batch:
            batch.append_entry("companies.md", {"content": "- Acme Corp"})
            batch.append_entry("contacts.md", {"content": "- Jane Doe"})
        # Single POST to /context/batch on exit
    """
    batch = _BatchOperation(source)
    try:
        yield batch
    except Exception:
        # On exception, do NOT send the batch
        raise
    else:
        batch._send()


def list_context_files() -> list:
    """List all context files available for the current tenant."""
    client = _get_client()
    try:
        resp = _handle_response(
            client.get(
                _api("/context/files"),
                headers=_auth_headers(),
            )
        )
        return resp.json().get("items", [])
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Cannot connect to Flywheel API at {get_api_url()}. Is the server running?"
        ) from exc


def log_event(event_type: str, data: dict | None = None, **kwargs: Any) -> None:
    """Fire-and-forget event logging. Never raises."""
    try:
        client = _get_client()
        client.post(
            _api("/events"),
            json={"event_type": event_type, "data": data or {}},
            headers=_auth_headers(),
        )
    except Exception:
        logger.debug("log_event failed for %s (silently ignored)", event_type)
