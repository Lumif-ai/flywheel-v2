"""Onboarding endpoints: anonymous promotion and subsidy tracking.

Endpoints:
- POST /onboarding/promote          -- promote anonymous user to full account
- GET  /onboarding/subsidy-status   -- remaining anonymous runs
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_current_user, get_db_unscoped
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import (
    ContextEntry,
    OnboardingSession,
    Tenant,
    User,
    UserTenant,
)

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
