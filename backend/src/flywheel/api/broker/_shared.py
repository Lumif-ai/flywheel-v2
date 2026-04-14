"""Shared constants and helpers for broker sub-routers."""
from __future__ import annotations

from fastapi import HTTPException

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new_request": {"analyzing", "cancelled"},
    "analyzing": {"analysis_failed", "gaps_identified", "cancelled"},
    "analysis_failed": {"analyzing", "cancelled"},
    "gaps_identified": {"soliciting", "cancelled"},
    "soliciting": {"quotes_partial", "quotes_complete", "cancelled"},
    "quotes_partial": {"quotes_complete", "cancelled"},
    "quotes_complete": {"recommended", "cancelled"},
    "recommended": {"delivered", "cancelled"},
    "delivered": {"binding", "cancelled"},
    "binding": {"bound", "cancelled"},
    "bound": set(),     # terminal
    "cancelled": set(), # terminal
}

# States that require a client_id to be set on the project
REQUIRES_CLIENT_STATES: set[str] = {
    "gaps_identified", "soliciting", "quotes_partial",
    "quotes_complete", "recommended", "delivered",
    "binding", "bound",
}


def validate_transition(current: str, target: str, client_id=None) -> None:
    """Raise HTTPException(409/422) if status transition is not allowed.

    Also raises 422 if target is in REQUIRES_CLIENT_STATES and client_id is None.
    """
    if target in REQUIRES_CLIENT_STATES and client_id is None:
        raise HTTPException(
            status_code=422,
            detail="client_id required before advancing past 'analyzing'",
        )
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Invalid status transition: '{current}' -> '{target}'. "
                f"Allowed: {sorted(allowed) if allowed else 'none (terminal state)'}"
            ),
        )
