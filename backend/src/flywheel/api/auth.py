"""Auth endpoints: magic link, anonymous sign-in, token refresh, user profile, BYOK API key, lifecycle.

Public endpoints (no auth):
- POST /auth/magic-link  -- send magic link email via Supabase
- POST /auth/anonymous   -- create anonymous session
- POST /auth/refresh     -- exchange refresh_token for new tokens

Authenticated endpoints:
- GET  /auth/me           -- user profile with has_api_key flag
- GET  /auth/lifecycle    -- user lifecycle state (S1-S5) with signals
- POST /auth/api-key      -- validate + encrypt + store BYOK key
- DELETE /auth/api-key    -- remove stored key
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_current_user, get_db_unscoped, require_tenant
from flywheel.auth.encryption import encrypt_api_key
from flywheel.auth.jwt import TokenPayload
from flywheel.auth.supabase_client import get_supabase_admin
from flywheel.config import settings
from flywheel.db.models import ContextEntry, Integration, Profile, SkillRun, Tenant, UserTenant
from flywheel.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MagicLinkRequest(BaseModel):
    email: str
    redirect_to: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class APIKeyRequest(BaseModel):
    api_key: str


class UserProfile(BaseModel):
    user_id: str
    email: str | None
    name: str | None
    is_anonymous: bool
    has_api_key: bool
    active_tenant: dict | None = None  # { id, name, role }


class LifecycleResponse(BaseModel):
    state: str  # S1 | S2 | S3 | S4 | S5
    is_anonymous: bool
    has_api_key: bool
    run_count: int
    run_limit: int = 3
    has_calendar: bool
    has_email: bool
    is_first_visit: bool


# ---------------------------------------------------------------------------
# Lifecycle state computation
# ---------------------------------------------------------------------------

_ONBOARDING_SKILLS = ("company-intel", "meeting-prep")


def compute_lifecycle_state(
    is_anonymous: bool, has_api_key: bool, run_count: int
) -> str:
    """Determine user lifecycle state (S1-S5) from signals.

    S1 = First Magic (anonymous, <= 1 run)
    S2 = Signup Moment (anonymous, > 1 run -- approaching gate)
    S3 = Exploring (authenticated, < 3 runs, no API key)
    S4 = Power Threshold (authenticated, >= 3 runs, no API key)
    S5 = Power User (authenticated, has API key)
    """
    if is_anonymous:
        return "S1" if run_count <= 1 else "S2"
    if has_api_key:
        return "S5"
    return "S3" if run_count < 3 else "S4"


# ---------------------------------------------------------------------------
# POST /auth/magic-link (public)
# ---------------------------------------------------------------------------


@router.post("/magic-link")
@limiter.limit("3/hour")
async def magic_link(request: Request, body: MagicLinkRequest):
    """Send a magic link email. Never reveals whether email exists."""
    if not _EMAIL_RE.match(body.email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email format",
        )

    logger.info("magic_link_requested email=%s", body.email)

    try:
        supabase = await get_supabase_admin()
        options: dict = {}
        if body.redirect_to:
            options["email_redirect_to"] = body.redirect_to
        await supabase.auth.sign_in_with_otp(
            {"email": body.email, "options": options}
        )
    except Exception:
        # Swallow errors to avoid leaking whether the email exists
        logger.exception("magic_link_error email=%s", body.email)

    # Supabase handles magic link email delivery via its built-in mailer.
    # To use Resend instead, configure Supabase SMTP settings to point to Resend's
    # SMTP relay (smtp.resend.com) in the Supabase Dashboard -> Auth -> SMTP Settings.

    # Always return success -- do NOT reveal whether email exists
    return {"message": "Magic link sent"}


# ---------------------------------------------------------------------------
# POST /auth/anonymous (public)
# ---------------------------------------------------------------------------


@router.post("/anonymous")
async def anonymous():
    """Create an anonymous Supabase session (no credentials required)."""
    supabase = await get_supabase_admin()
    result = await supabase.auth.sign_in_anonymously()

    session = result.session
    user = result.user

    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "user": {
            "id": str(user.id),
            "is_anonymous": user.is_anonymous,
        },
    }


# ---------------------------------------------------------------------------
# POST /auth/refresh (public -- refresh_token IS the credential)
# ---------------------------------------------------------------------------


@router.post("/refresh")
@limiter.limit(settings.rate_limit_default)
async def refresh_token(request: Request, body: RefreshTokenRequest):
    """Exchange a valid refresh_token for new access + refresh tokens."""
    url = f"{settings.supabase_url}/auth/v1/token?grant_type=refresh_token"
    headers = {
        "apikey": settings.supabase_service_key,
        "content-type": "application/json",
    }
    payload = {"refresh_token": body.refresh_token}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
        except httpx.HTTPError:
            logger.exception("refresh_token_error")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not reach auth provider",
            )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    data = resp.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": data["expires_at"],
    }


# ---------------------------------------------------------------------------
# GET /auth/me (authenticated)
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserProfile)
async def me(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Return current user profile. Auto-creates user + tenant on first login."""
    row = (await db.execute(select(Profile).where(Profile.id == user.sub))).scalar_one_or_none()

    if row is None and user.email:
        # First login after magic link -- create profile + tenant + user_tenants
        domain = user.email.split("@")[1] if "@" in user.email else "Personal"
        tenant = Tenant(name=domain)
        db.add(tenant)
        await db.flush()

        new_profile = Profile(id=user.sub)
        db.add(new_profile)
        await db.flush()

        ut = UserTenant(user_id=user.sub, tenant_id=tenant.id, role="admin", active=True)
        db.add(ut)
        await db.commit()
        await db.refresh(new_profile)
        row = new_profile

        # Build active_tenant from what we just created
        active_tenant = {"id": str(tenant.id), "name": tenant.name, "role": "admin"}
    else:
        # Lookup active tenant
        active_tenant = None
        if row is not None:
            ut_row = (
                await db.execute(
                    select(UserTenant, Tenant)
                    .join(Tenant, Tenant.id == UserTenant.tenant_id)
                    .where(UserTenant.user_id == user.sub, UserTenant.active.is_(True))
                )
            ).first()
            if ut_row:
                ut_obj, tenant_obj = ut_row
                active_tenant = {
                    "id": str(tenant_obj.id),
                    "name": tenant_obj.name,
                    "role": ut_obj.role,
                }

    if row is None:
        # Anonymous user with no user record yet
        return UserProfile(
            user_id=str(user.sub),
            email=user.email,
            name=None,
            is_anonymous=user.is_anonymous,
            has_api_key=False,
            active_tenant=None,
        )

    return UserProfile(
        user_id=str(row.id),
        email=user.email,  # email from JWT, not DB profile
        name=row.name,
        is_anonymous=user.is_anonymous,
        has_api_key=row.api_key_encrypted is not None,
        active_tenant=active_tenant,
    )


# ---------------------------------------------------------------------------
# GET /auth/lifecycle (authenticated -- user lifecycle state)
# ---------------------------------------------------------------------------


@router.get("/lifecycle", response_model=LifecycleResponse)
async def lifecycle(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Return the user's lifecycle state (S1-S5) with supporting signals.

    Works for both anonymous and authenticated users. Uses lifetime run count
    (total completed skill runs ever). Monthly reset may be added later via
    billing_period_start on the Tenant model.
    """
    # --- has_api_key ---
    profile_row = (
        await db.execute(
            select(Profile.api_key_encrypted).where(Profile.id == user.sub)
        )
    ).scalar_one_or_none()
    has_api_key = profile_row is not None

    # --- run_count (lifetime completed runs for tenant) ---
    run_count = 0
    if user.tenant_id is not None:
        run_count_result = await db.execute(
            select(func.count()).select_from(SkillRun).where(
                SkillRun.tenant_id == user.tenant_id,
                SkillRun.status == "completed",
            )
        )
        run_count = run_count_result.scalar_one()

    # --- has_calendar / has_email ---
    has_calendar = False
    has_email = False
    if user.tenant_id is not None:
        cal_result = await db.execute(
            select(Integration.id).where(
                Integration.tenant_id == user.tenant_id,
                Integration.provider.in_(("google-calendar",)),
                Integration.status == "connected",
                Integration.credentials_encrypted.isnot(None),
            ).limit(1)
        )
        has_calendar = cal_result.scalar_one_or_none() is not None

        email_result = await db.execute(
            select(Integration.id).where(
                Integration.tenant_id == user.tenant_id,
                Integration.provider.in_(("gmail-read", "microsoft-outlook")),
                Integration.status == "connected",
                Integration.credentials_encrypted.isnot(None),
            ).limit(1)
        )
        has_email = email_result.scalar_one_or_none() is not None

    # --- is_first_visit (reuses briefing.py heuristic) ---
    # First visit = has onboarding intel AND no completed non-onboarding skill runs
    is_first_visit = False
    if user.tenant_id is not None:
        intel_count_result = await db.execute(
            select(func.count()).select_from(
                select(ContextEntry).where(
                    ContextEntry.tenant_id == user.tenant_id,
                    ContextEntry.source == "company-intel-onboarding",
                    ContextEntry.deleted_at.is_(None),
                ).subquery()
            )
        )
        has_onboarding_intel = (intel_count_result.scalar() or 0) > 0

        if has_onboarding_intel:
            non_onboarding_result = await db.execute(
                select(func.count()).select_from(
                    select(SkillRun).where(
                        SkillRun.tenant_id == user.tenant_id,
                        SkillRun.status == "completed",
                        SkillRun.skill_name.notin_(_ONBOARDING_SKILLS),
                    ).subquery()
                )
            )
            non_onboarding_runs = non_onboarding_result.scalar() or 0
            is_first_visit = non_onboarding_runs == 0

    state = compute_lifecycle_state(user.is_anonymous, has_api_key, run_count)

    return LifecycleResponse(
        state=state,
        is_anonymous=user.is_anonymous,
        has_api_key=has_api_key,
        run_count=run_count,
        run_limit=3,
        has_calendar=has_calendar,
        has_email=has_email,
        is_first_visit=is_first_visit,
    )


# ---------------------------------------------------------------------------
# GET /auth/api-key (authenticated -- check if user has a stored key)
# ---------------------------------------------------------------------------


@router.get("/api-key")
async def get_api_key_status(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Check whether the authenticated user has a stored API key."""
    result = await db.execute(
        select(Profile.api_key_encrypted).where(Profile.id == user.sub)
    )
    encrypted = result.scalar_one_or_none()
    return {"has_api_key": encrypted is not None}


# ---------------------------------------------------------------------------
# POST /auth/api-key (authenticated, requires tenant)
# ---------------------------------------------------------------------------


@router.post("/api-key")
async def store_api_key(
    body: APIKeyRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Validate an Anthropic API key, encrypt, and store it."""
    # Validate the key via Anthropic test call
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": body.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-20250514",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
                timeout=10.0,
            )
        except httpx.HTTPError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not reach Anthropic API to validate key",
            )

    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key",
        )

    encrypted = encrypt_api_key(body.api_key)
    await db.execute(
        update(Profile).where(Profile.id == user.sub).values(api_key_encrypted=encrypted)
    )
    await db.commit()

    return {"has_api_key": True}


# ---------------------------------------------------------------------------
# DELETE /auth/api-key (authenticated, requires tenant)
# ---------------------------------------------------------------------------


@router.delete("/api-key")
async def delete_api_key(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Remove stored API key."""
    await db.execute(
        update(Profile).where(Profile.id == user.sub).values(api_key_encrypted=None)
    )
    await db.commit()

    return {"has_api_key": False}
