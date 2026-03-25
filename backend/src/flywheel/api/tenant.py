"""Tenant management endpoints: CRUD, invites, members.

Admin-only endpoints:
- PATCH /tenants/current     -- update tenant settings
- DELETE /tenants/current    -- soft-delete tenant (30-day grace)
- POST /tenants/invite       -- invite team member by email
- DELETE /tenants/members/{user_id} -- remove member

Authenticated endpoints:
- GET /tenants/current       -- get current tenant details
- POST /tenants/invite/accept -- accept an invite token
- GET /tenants/members       -- list members + pending invites
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import logging
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import (
    get_current_user,
    get_db_unscoped,
    get_tenant_db,
    require_admin,
    require_tenant,
)
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import (
    ContextEntry,
    Invite,
    Profile,
    SkillRun,
    Tenant,
    UserTenant,
    WorkItem,
)
from flywheel.services.data_export import (
    estimate_export_size,
    generate_export_zip,
    SIZE_THRESHOLD,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

DEFAULT_MEMBER_LIMIT = 10


class TenantUpdateRequest(BaseModel):
    name: str | None = None
    domain: str | None = None
    settings: dict | None = None


class InviteRequest(BaseModel):
    email: str
    role: str = "member"


class AcceptInviteRequest(BaseModel):
    token: str


class TenantResponse(BaseModel):
    id: str
    name: str
    domain: str | None
    settings: dict
    trial_expires_at: str | None
    created_at: str
    member_count: int


class InviteResponse(BaseModel):
    invite_id: str
    email: str
    expires_at: str | None
    invite_token: str | None = None


class AcceptInviteResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    role: str


class MemberItem(BaseModel):
    user_id: str | None = None
    email: str
    name: str | None = None
    role: str
    joined_at: str | None = None
    status: str = "active"
    expires_at: str | None = None


class DeleteTenantResponse(BaseModel):
    deleted_at: str
    grace_period_ends: str


class TenantListItem(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    member_limit: int


# ---------------------------------------------------------------------------
# GET /tenants (list all tenants for current user)
# ---------------------------------------------------------------------------


@router.get("", response_model=list[TenantListItem])
async def list_tenants(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """List all tenants the authenticated user belongs to.

    Returns tenant info in the shape the frontend TenantSwitcher expects:
    id, name, slug, plan, member_limit.
    """
    result = await db.execute(
        select(Tenant, UserTenant.role)
        .join(UserTenant, UserTenant.tenant_id == Tenant.id)
        .where(UserTenant.user_id == user.sub)
        .where(Tenant.deleted_at.is_(None))
    )
    items = []
    for tenant, role in result.all():
        settings = tenant.settings or {}
        items.append(
            TenantListItem(
                id=str(tenant.id),
                name=tenant.name,
                slug=settings.get("slug", tenant.name.lower().replace(" ", "-")),
                plan=settings.get("plan", "free"),
                member_limit=settings.get("member_limit", DEFAULT_MEMBER_LIMIT),
            )
        )
    return items


# ---------------------------------------------------------------------------
# GET /tenants/current
# ---------------------------------------------------------------------------


@router.get("/current", response_model=TenantResponse)
async def get_current_tenant(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Return current tenant details with member count."""
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    ).scalar_one_or_none()

    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    member_count_result = await db.execute(
        select(func.count()).select_from(UserTenant).where(
            UserTenant.tenant_id == user.tenant_id
        )
    )
    member_count = member_count_result.scalar() or 0

    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        domain=tenant.domain,
        settings=tenant.settings or {},
        trial_expires_at=tenant.trial_expires_at.isoformat() if tenant.trial_expires_at else None,
        created_at=tenant.created_at.isoformat(),
        member_count=member_count,
    )


# ---------------------------------------------------------------------------
# PATCH /tenants/current (admin only)
# ---------------------------------------------------------------------------


@router.patch("/current", response_model=TenantResponse)
async def update_tenant(
    body: TenantUpdateRequest,
    user: TokenPayload = Depends(require_admin),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Update tenant settings. Admin only."""
    values: dict = {}
    if body.name is not None:
        values["name"] = body.name
    if body.domain is not None:
        values["domain"] = body.domain
    if body.settings is not None:
        values["settings"] = body.settings

    if values:
        await db.execute(
            update(Tenant).where(Tenant.id == user.tenant_id).values(**values)
        )
        await db.commit()

    # Re-fetch and return
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    ).scalar_one_or_none()

    member_count_result = await db.execute(
        select(func.count()).select_from(UserTenant).where(
            UserTenant.tenant_id == user.tenant_id
        )
    )
    member_count = member_count_result.scalar() or 0

    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        domain=tenant.domain,
        settings=tenant.settings or {},
        trial_expires_at=tenant.trial_expires_at.isoformat() if tenant.trial_expires_at else None,
        created_at=tenant.created_at.isoformat(),
        member_count=member_count,
    )


# ---------------------------------------------------------------------------
# DELETE /tenants/current (admin only)
# ---------------------------------------------------------------------------


@router.delete("/current", response_model=DeleteTenantResponse)
async def delete_tenant(
    user: TokenPayload = Depends(require_admin),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Soft-delete tenant with 30-day grace period. Admin only."""
    # Check if user is last admin -- must transfer first
    admin_count_result = await db.execute(
        select(func.count()).select_from(UserTenant).where(
            UserTenant.tenant_id == user.tenant_id,
            UserTenant.role == "admin",
        )
    )
    admin_count = admin_count_result.scalar() or 0

    if admin_count <= 1:
        # Check total member count -- if solo admin with other members, block
        member_count_result = await db.execute(
            select(func.count()).select_from(UserTenant).where(
                UserTenant.tenant_id == user.tenant_id,
            )
        )
        member_count = member_count_result.scalar() or 0
        if member_count > 1:
            raise HTTPException(
                status_code=400,
                detail="Transfer admin role before deleting tenant",
            )

    now = datetime.datetime.now(datetime.timezone.utc)
    grace_period_ends = now + datetime.timedelta(days=30)

    await db.execute(
        update(Tenant).where(Tenant.id == user.tenant_id).values(deleted_at=now)
    )
    await db.commit()

    return DeleteTenantResponse(
        deleted_at=now.isoformat(),
        grace_period_ends=grace_period_ends.isoformat(),
    )


# ---------------------------------------------------------------------------
# POST /tenants/invite (admin only)
# ---------------------------------------------------------------------------


@router.post("/invite", response_model=InviteResponse)
async def invite_member(
    body: InviteRequest,
    user: TokenPayload = Depends(require_admin),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Invite a team member by email. Admin only."""
    # Check member limit
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    ).scalar_one_or_none()

    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    member_limit = (tenant.settings or {}).get("member_limit", DEFAULT_MEMBER_LIMIT)

    member_count_result = await db.execute(
        select(func.count()).select_from(UserTenant).where(
            UserTenant.tenant_id == user.tenant_id
        )
    )
    member_count = member_count_result.scalar() or 0

    if member_count >= member_limit:
        raise HTTPException(status_code=403, detail="Member limit reached")

    # Check for existing pending invite
    existing_invite = (
        await db.execute(
            select(Invite).where(
                Invite.tenant_id == user.tenant_id,
                Invite.email == body.email,
                Invite.accepted_at.is_(None),
                Invite.expires_at > func.now(),
            )
        )
    ).scalar_one_or_none()

    if existing_invite is not None:
        raise HTTPException(status_code=409, detail="Invite already sent")

    # TODO: Profile table has no email column. To check if an invited user
    # already has an account, query auth.users via Supabase Admin API.
    # For now, always create an invite token (dedup skipped).

    # Generate token, store hash
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    invite = Invite(
        tenant_id=user.tenant_id,
        invited_by=user.sub,
        email=body.email,
        role=body.role,
        token_hash=token_hash,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    logger.info("invite_created tenant=%s email=%s", user.tenant_id, body.email)

    # Fire-and-forget invite email (fails gracefully, never blocks response)
    from flywheel.config import settings
    from flywheel.services.email import send_invite_email

    invite_url = f"{settings.frontend_url}/invite?token={token}"
    asyncio.create_task(send_invite_email(body.email, invite_url, tenant.name))

    return InviteResponse(
        invite_id=str(invite.id),
        email=body.email,
        expires_at=invite.expires_at.isoformat() if invite.expires_at else None,
        invite_token=token,  # Still returned as fallback (shareable link)
    )


# ---------------------------------------------------------------------------
# POST /tenants/invite/accept (authenticated)
# ---------------------------------------------------------------------------


@router.post("/invite/accept", response_model=AcceptInviteResponse)
async def accept_invite(
    body: AcceptInviteRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Accept an invite by providing the invite token."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()

    invite = (
        await db.execute(
            select(Invite).where(
                Invite.token_hash == token_hash,
                Invite.accepted_at.is_(None),
                Invite.expires_at > func.now(),
            )
        )
    ).scalar_one_or_none()

    if invite is None:
        raise HTTPException(status_code=404, detail="Invalid or expired invite")

    # Race condition guard: re-check member limit
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == invite.tenant_id))
    ).scalar_one_or_none()

    member_limit = (tenant.settings or {}).get("member_limit", DEFAULT_MEMBER_LIMIT)
    member_count_result = await db.execute(
        select(func.count()).select_from(UserTenant).where(
            UserTenant.tenant_id == invite.tenant_id
        )
    )
    member_count = member_count_result.scalar() or 0

    if member_count >= member_limit:
        raise HTTPException(status_code=403, detail="Member limit reached")

    # Create user_tenants row
    ut = UserTenant(
        user_id=user.sub,
        tenant_id=invite.tenant_id,
        role=invite.role,
        active=False,  # user keeps current tenant active
    )
    db.add(ut)

    # Mark invite as accepted
    invite.accepted_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()

    return AcceptInviteResponse(
        tenant_id=str(invite.tenant_id),
        tenant_name=tenant.name,
        role=invite.role,
    )


# ---------------------------------------------------------------------------
# GET /tenants/members
# ---------------------------------------------------------------------------


@router.get("/members", response_model=list[MemberItem])
async def list_members(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """List tenant members and pending invites."""
    # Active members
    members_result = await db.execute(
        select(UserTenant, Profile)
        .join(Profile, Profile.id == UserTenant.user_id)
        .where(UserTenant.tenant_id == user.tenant_id)
    )
    members = []
    for ut, p in members_result.all():
        members.append(
            MemberItem(
                user_id=str(p.id),
                email=None,  # TODO: email lives in auth.users, fetch via Supabase Admin API if needed
                name=p.name,
                role=ut.role,
                joined_at=ut.joined_at.isoformat() if ut.joined_at else None,
                status="active",
            )
        )

    # Pending invites
    invites_result = await db.execute(
        select(Invite).where(
            Invite.tenant_id == user.tenant_id,
            Invite.accepted_at.is_(None),
            Invite.expires_at > func.now(),
        )
    )
    for inv in invites_result.scalars().all():
        members.append(
            MemberItem(
                email=inv.email,
                role=inv.role,
                status="pending",
                expires_at=inv.expires_at.isoformat() if inv.expires_at else None,
            )
        )

    return members


# ---------------------------------------------------------------------------
# DELETE /tenants/members/{user_id} (admin only)
# ---------------------------------------------------------------------------


@router.delete("/members/{user_id}", status_code=204)
async def remove_member(
    user_id: UUID,
    user: TokenPayload = Depends(require_admin),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Remove a member from the tenant. Admin only."""
    if user_id == user.sub:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    # Check if target is last admin
    target_ut = (
        await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == user_id,
                UserTenant.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()

    if target_ut is None:
        raise HTTPException(status_code=404, detail="Member not found")

    if target_ut.role == "admin":
        admin_count_result = await db.execute(
            select(func.count()).select_from(UserTenant).where(
                UserTenant.tenant_id == user.tenant_id,
                UserTenant.role == "admin",
            )
        )
        admin_count = admin_count_result.scalar() or 0
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove last admin")

    await db.execute(
        delete(UserTenant).where(
            UserTenant.user_id == user_id,
            UserTenant.tenant_id == user.tenant_id,
        )
    )
    await db.commit()


# ---------------------------------------------------------------------------
# GET /tenants/export (admin only)
# ---------------------------------------------------------------------------


@router.get("/export")
async def export_tenant_data(
    user: TokenPayload = Depends(require_admin),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Export all tenant data as a ZIP of JSON files.

    Streams a ZIP download for datasets under 100MB.
    Returns 413 for larger datasets (async export not yet implemented).
    """
    estimated_size = await estimate_export_size(user.tenant_id, db)

    if estimated_size >= SIZE_THRESHOLD:
        raise HTTPException(
            status_code=413,
            detail={
                "message": "Dataset too large for sync export. Async export with email notification is not yet available.",
                "estimated_size_mb": round(estimated_size / 1_000_000, 1),
                "threshold_mb": SIZE_THRESHOLD / 1_000_000,
            },
        )

    # Sync path: generate and stream ZIP directly
    zip_buffer = await generate_export_zip(user.tenant_id, db)
    filename = f"flywheel-export-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
