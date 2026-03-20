"""Onboarding endpoints: anonymous promotion, subsidy tracking, and crawl SSE.

Endpoints:
- POST /onboarding/promote          -- promote anonymous user to full account
- GET  /onboarding/subsidy-status   -- remaining anonymous runs
- POST /onboarding/crawl            -- start company crawl, stream SSE results
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from flywheel.api.deps import get_current_user, get_db_unscoped
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import (
    ContextEntry,
    OnboardingSession,
    SkillRun,
    Tenant,
    User,
    UserTenant,
)
from flywheel.db.session import get_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

ANONYMOUS_RUN_LIMIT = 3


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class PromoteRequest(BaseModel):
    email: str


class PromoteResponse(BaseModel):
    tenant_id: str
    message: str


class SubsidyStatusResponse(BaseModel):
    runs_used: int
    runs_remaining: int
    limit: int


class CrawlRequest(BaseModel):
    url: str


# ---------------------------------------------------------------------------
# POST /onboarding/promote (authenticated, anonymous only)
# ---------------------------------------------------------------------------


@router.post("/promote", response_model=PromoteResponse)
async def promote(
    body: PromoteRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Promote an anonymous user to a full account.

    Called after the client has already triggered email confirmation via
    supabase.auth.updateUser({ email }). This endpoint creates the
    tenant, user row, and user_tenants record server-side.
    """
    if not user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already authenticated",
        )

    # Derive tenant name from email domain
    domain = body.email.split("@")[1] if "@" in body.email else "Personal"

    # Create tenant
    tenant = Tenant(name=domain)
    db.add(tenant)
    await db.flush()

    # Create or update user row
    existing_user = (
        await db.execute(select(User).where(User.id == user.sub))
    ).scalar_one_or_none()

    if existing_user is None:
        new_user = User(id=user.sub, email=body.email)
        db.add(new_user)
        await db.flush()
    else:
        existing_user.email = body.email
        await db.flush()

    # Create user_tenants
    ut = UserTenant(
        user_id=user.sub, tenant_id=tenant.id, role="admin", active=True
    )
    db.add(ut)

    # Copy onboarding session data into context_entries for new tenant
    onboarding_rows = (
        await db.execute(
            select(OnboardingSession).where(
                OnboardingSession.user_id == user.sub
            )
        )
    ).scalars().all()

    for session_row in onboarding_rows:
        data = session_row.data or {}
        entries = data.get("context_entries", [])
        for entry in entries:
            ce = ContextEntry(
                tenant_id=tenant.id,
                user_id=user.sub,
                file_name=entry.get("file_name", "onboarding.md"),
                source=entry.get("source", "onboarding"),
                detail=entry.get("detail"),
                content=entry.get("content", ""),
                confidence=entry.get("confidence", "medium"),
            )
            db.add(ce)

    await db.commit()

    return PromoteResponse(
        tenant_id=str(tenant.id),
        message="Account promoted",
    )


# ---------------------------------------------------------------------------
# GET /onboarding/subsidy-status (authenticated, anonymous only)
# ---------------------------------------------------------------------------


@router.get("/subsidy-status", response_model=SubsidyStatusResponse)
async def subsidy_status(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Return remaining subsidized anonymous runs."""
    if not user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not an anonymous user",
        )

    # Count skill runs stored in onboarding_sessions.data
    result = (
        await db.execute(
            select(OnboardingSession.data).where(
                OnboardingSession.user_id == user.sub
            )
        )
    ).scalars().all()

    runs_used = 0
    for data in result:
        if isinstance(data, dict):
            runs_used += len(data.get("skill_runs", []))

    runs_remaining = max(0, ANONYMOUS_RUN_LIMIT - runs_used)

    return SubsidyStatusResponse(
        runs_used=runs_used,
        runs_remaining=runs_remaining,
        limit=ANONYMOUS_RUN_LIMIT,
    )


# ---------------------------------------------------------------------------
# POST /onboarding/crawl (authenticated, anonymous allowed)
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


@router.post("/crawl")
async def crawl(
    body: CrawlRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
) -> EventSourceResponse:
    """Start a company crawl and stream results via SSE.

    Anonymous users can use this endpoint (no tenant required).
    Creates a SkillRun with skill_name='company-intel' and returns
    an SSE stream that polls for events.

    NOTE: Actual crawl execution is Phase 20. The SSE endpoint is ready
    to stream events once the job queue processes the run.
    """
    # Validate URL format
    if not _URL_RE.match(body.url):
        raise HTTPException(
            status_code=422,
            detail="Invalid URL: must start with http:// or https://",
        )

    # Create SkillRun record
    # For anonymous users, tenant_id may be None -- use a sentinel or skip
    run = SkillRun(
        tenant_id=user.tenant_id or user.sub,  # fallback to user_id for anonymous
        user_id=user.sub,
        skill_name="company-intel",
        input_text=body.url,
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await db.commit()

    run_id = run.id

    async def event_generator():
        # Yield started event immediately
        yield {"event": "started", "data": json.dumps({"run_id": str(run_id)})}

        factory = get_session_factory()
        seen_events = 0

        while True:
            await asyncio.sleep(1)

            session = factory()
            try:
                result = await session.execute(
                    select(SkillRun).where(SkillRun.id == run_id)
                )
                skill_run = result.scalar_one_or_none()
                if skill_run is None:
                    yield {"event": "error", "data": json.dumps({"message": "Run disappeared"})}
                    return

                # Yield any new events
                events_log = skill_run.events_log or []
                for evt in events_log[seen_events:]:
                    yield {
                        "event": evt.get("event", "message"),
                        "data": json.dumps(evt.get("data", evt)),
                    }
                    seen_events += 1

                if skill_run.status in ("completed", "failed"):
                    yield {"event": "done", "data": json.dumps({"status": skill_run.status})}
                    return
            finally:
                await session.close()

    return EventSourceResponse(event_generator())
