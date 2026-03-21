"""Message schema constants and response helpers for the agent protocol."""

from __future__ import annotations

COMMAND_TYPES: frozenset[str] = frozenset(
    {"navigate", "click", "type", "extract", "screenshot"}
)


def make_response(request_id: str, content: str = "", **extra) -> dict:
    """Build a success response dict."""
    return {"request_id": request_id, "status": "ok", "content": content, **extra}


def make_error_response(request_id: str, error: str) -> dict:
    """Build an error response dict."""
    return {"request_id": request_id, "status": "error", "error": error}
