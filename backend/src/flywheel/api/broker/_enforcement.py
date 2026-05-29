"""Phase 150.1 CC-as-Brain subsidy enforcement — FastAPI dependency + SubsidyDecision.

This module implements the four-cell truth table from `150.1-CONTEXT.md` at the
FastAPI boundary for every new extract/save endpoint shipping in Plans 02-03.
The single allowlist constant lives in `flywheel.config.settings.subsidy_allowed_skills`
(single source of truth, git-tracked, deploy-required to change).

Four-cell truth table (from CONTEXT.md):

    | skill allowlisted? | api_key in request body? | Behavior |
    |--------------------|--------------------------|----------|
    | Yes                | No                       | Use subsidy key       |
    | Yes                | Yes                      | Use caller's key (BYOK) |
    | No                 | No                       | **HTTP 403**          |
    | No                 | Yes                      | Use caller's key (BYOK) |

BYOK MECHANISM (chosen by Task 1 POC on 2026-04-18):
    BODY-BASED `api_key` FIELD.

    Per Plan 01 Task 1 POC (150.1-01-AUDIT.md Section 3) on pinned stack
    fastapi=0.135.1, starlette=0.52.1:
    - FastAPI caches `await request.json()` on first read via `request._body`,
      so a dependency reading the body does NOT consume the stream for a
      downstream Pydantic body parameter. Body-double-read is safe.
    - Empty / non-JSON bodies raise `JSONDecodeError`; this module wraps the
      read in `try/except Exception` to degrade gracefully (treat as "no key").

    Consumer contract (locked for Plans 02/03):
    - Caller identification header: `X-Flywheel-Skill: <skill-name>` — set by
      every skill; missing header is treated as "non-allowlisted" per CONTEXT.
    - BYOK payload shape: JSON body field `api_key: str | None = None`.
    - Plan 02 save-endpoint Pydantic models MUST include `api_key: str | None = None`.
    - Plan 03 `api_client.py` MUST put `api_key` in the JSON body, NOT a header.

    If a future Starlette/FastAPI upgrade ever breaks body-double-read semantics,
    flip to header-based `X-Flywheel-BYOK-Key: <key>` by reading a second
    `Header()` arg instead of reading the body. Rerun the Plan 01 POC first.

403 body shape (locked by CONTEXT.md):
    {
      "error": "subsidy_not_allowed",
      "skill": "<skill-name or None>",
      "hint": "Pass api_key in request body or use the Pattern 3a /extract/{operation} endpoint"
    }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from flywheel.config import settings

logger = logging.getLogger(__name__)


def raise_endpoint_deprecated(*, operation: str) -> None:
    """Raise HTTP 410 Gone with the Phase 150.1 Pattern 3a migration hint.

    Called by every legacy broker endpoint handler that was flipped to 410
    in Plan 04. Emits a structured deprecation log line for monitoring +
    a machine-actionable body so Claude-in-conversation can auto-route to
    the new /extract/{op} + /save/{op} endpoints.

    Args:
        operation: The Pattern 3a operation name (e.g., "contract-analysis",
            "quote-extraction", "solicitation-draft", "recommendation-draft").

    Raises:
        HTTPException(410): Always.
    """
    logger.warning(
        "deprecated_endpoint_called",
        extra={"operation": operation, "migrated_in": "150.1"},
    )
    raise HTTPException(
        status_code=410,
        detail={
            "error": "endpoint_deprecated",
            "operation": operation,
            "replacement": (
                f"/api/v1/broker/extract/{operation} + "
                f"/api/v1/broker/save/{operation}"
            ),
            "migrated_in": "150.1",
            "reason": (
                "Backend no longer runs LLM calls for broker flows. Use "
                "Pattern 3a: extract prompt + tool_schema, run inference in "
                "Claude-in-conversation, save result."
            ),
        },
    )


@dataclass(frozen=True)
class SubsidyDecision:
    """Typed result of the subsidy-enforcement dependency.

    Attributes:
        skill_name: Value of the X-Flywheel-Skill header (None if absent).
        caller_api_key: BYOK key from request body `api_key` field (None if absent).
        effective_api_key: Key engines should use. Non-None post-dependency —
            either caller's BYOK or the subsidy key for allowlisted skills.
        was_subsidized: True iff `effective_api_key` came from the subsidy pool.
    """

    skill_name: str | None
    caller_api_key: str | None
    effective_api_key: str | None
    was_subsidized: bool


async def require_subsidy_decision(
    request: Request,
    x_flywheel_skill: str | None = Header(None, alias="x-flywheel-skill"),
) -> SubsidyDecision:
    """FastAPI dependency — enforce the CC-as-Brain subsidy allowlist.

    Reads the `X-Flywheel-Skill` header (caller identification) and the JSON
    body `api_key` field (BYOK). Implements the 4-cell truth table declared in
    the module docstring.

    Raises:
        HTTPException(403): Skill is not allowlisted AND no BYOK key provided.
            Response body matches the CONTEXT-locked shape.
    """
    # Body-double-read is safe on fastapi>=0.135 / starlette>=0.52 — FastAPI
    # caches `request._body` so the downstream Pydantic body parse sees the
    # same payload. Any parse failure → treat as "no BYOK" (degrade gracefully).
    body_api_key: str | None = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            ak = body.get("api_key")
            if isinstance(ak, str) and ak.strip():
                body_api_key = ak.strip()
    except Exception:
        pass  # empty body / non-JSON / not-a-dict — treat as no BYOK

    allowlisted = (
        x_flywheel_skill in settings.subsidy_allowed_skills
        if x_flywheel_skill
        else False
    )

    # Cell 2 & Cell 4: caller supplied a key — always honor it (BYOK wins).
    if body_api_key:
        return SubsidyDecision(
            skill_name=x_flywheel_skill,
            caller_api_key=body_api_key,
            effective_api_key=body_api_key,
            was_subsidized=False,
        )

    # Cell 1: allowlisted skill + no BYOK + subsidy key configured → use subsidy.
    if allowlisted and settings.flywheel_subsidy_api_key:
        return SubsidyDecision(
            skill_name=x_flywheel_skill,
            caller_api_key=None,
            effective_api_key=settings.flywheel_subsidy_api_key,
            was_subsidized=True,
        )

    # Cell 3 (+ fail-closed sub-case: allowlisted but subsidy key unset): 403.
    raise HTTPException(
        status_code=403,
        detail={
            "error": "subsidy_not_allowed",
            "skill": x_flywheel_skill,
            "hint": "Pass api_key in request body or use the Pattern 3a /extract/{operation} endpoint",
        },
    )


__all__ = [
    "SubsidyDecision",
    "require_subsidy_decision",
    "raise_endpoint_deprecated",
]
