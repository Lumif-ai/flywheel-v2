"""Auth endpoints: magic link, anonymous sign-in, user profile, BYOK API key.

Public endpoints (no auth):
- POST /auth/magic-link  -- send magic link email via Supabase
- POST /auth/anonymous   -- create anonymous session

Authenticated endpoints:
- GET  /auth/me           -- user profile with has_api_key flag
- POST /auth/api-key      -- validate + encrypt + store BYOK key
- DELETE /auth/api-key    -- remove stored key
"""

from __future__ import annotations

import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_current_user, get_db_unscoped, require_tenant
from flywheel.auth.encryption import encrypt_api_key
from flywheel.auth.jwt import TokenPayload
from flywheel.auth.supabase_client import get_supabase_admin
from flywheel.db.models import Tenant, User, UserTenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MagicLinkRequest(BaseModel):
    email: str
    redirect_to: str | None = None


class APIKeyRequest(BaseModel):
    api_key: str


class UserProfile(BaseModel):
    user_id: str
    email: str | None
    name: str | None
    is_anonymous: bool
    has_api_key: bool
    active_tenant: dict | None = None  # { id, name, role }


# ---------------------------------------------------------------------------
# POST /auth/magic-link (public)
# ---------------------------------------------------------------------------


@router.post("/magic-link")
async def magic_link(body: MagicLinkRequest):
    """Send a magic link email. Never reveals whether email exists."""
    if not _EMAIL_RE.match(body.email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email format",
        )

    # TODO: Rate limit to 3/hr/email (Phase 18 AUTH-09)
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
# GET /auth/me (authenticated)
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserProfile)
async def me(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Return current user profile. Auto-creates user + tenant on first login."""
    row = (await db.execute(select(User).where(User.id == user.sub))).scalar_one_or_none()

    if row is None and user.email:
        # First login after magic link -- create user + tenant + user_tenants
        domain = user.email.split("@")[1] if "@" in user.email else "Personal"
        tenant = Tenant(name=domain)
        db.add(tenant)
        await db.flush()

        new_user = User(id=user.sub, email=user.email)
        db.add(new_user)
        await db.flush()

        ut = UserTenant(user_id=user.sub, tenant_id=tenant.id, role="admin", active=True)
        db.add(ut)
        await db.commit()
        await db.refresh(new_user)
        row = new_user

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
        email=row.email,
        name=row.name,
        is_anonymous=user.is_anonymous,
        has_api_key=row.api_key_encrypted is not None,
        active_tenant=active_tenant,
    )


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
        update(User).where(User.id == user.sub).values(api_key_encrypted=encrypted)
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
        update(User).where(User.id == user.sub).values(api_key_encrypted=None)
    )
    await db.commit()

    return {"has_api_key": False}
