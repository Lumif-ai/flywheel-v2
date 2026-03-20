"""User account endpoints: tenant list, switch tenant, delete account.

Authenticated endpoints:
- GET    /user/tenants        -- list all tenants for current user
- POST   /user/switch-tenant  -- switch active tenant
- DELETE /user/account        -- soft-delete account (30-day grace)
"""

from __future__ import annotations

import datetime
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_current_user, get_db_unscoped
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import SkillRun, Tenant, User, UserTenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["user"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class TenantListItem(BaseModel):
    tenant_id: str
    tenant_name: str
    role: str
    active: bool
    joined_at: str | None = None


class SwitchTenantRequest(BaseModel):
    tenant_id: UUID


class SwitchTenantResponse(BaseModel):
    tenant_id: str
    action: str


class DeleteAccountResponse(BaseModel):
    message: str
    deletion_date: str


# ---------------------------------------------------------------------------
# GET /user/tenants
# ---------------------------------------------------------------------------


@router.get("/tenants", response_model=list[TenantListItem])
async def list_user_tenants(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """List all tenants the user belongs to."""
    result = await db.execute(
        select(UserTenant, Tenant)
        .join(Tenant, Tenant.id == UserTenant.tenant_id)
        .where(UserTenant.user_id == user.sub)
    )
    items = []
    for ut, t in result.all():
        items.append(
            TenantListItem(
                tenant_id=str(t.id),
                tenant_name=t.name,
                role=ut.role,
                active=ut.active,
                joined_at=ut.joined_at.isoformat() if ut.joined_at else None,
            )
        )
    return items


# ---------------------------------------------------------------------------
# POST /user/switch-tenant
# ---------------------------------------------------------------------------


@router.post("/switch-tenant", response_model=SwitchTenantResponse)
async def switch_tenant(
    body: SwitchTenantRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Switch the user's active tenant.

    Uses an UNSCOPED session because this modifies cross-tenant state.
    Client must call supabase.auth.refreshSession() after to get
    a new JWT with the updated tenant_id from the Custom Access Token Hook.
    """
    # Verify user is a member of the target tenant
    membership = (
        await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == user.sub,
                UserTenant.tenant_id == body.tenant_id,
            )
        )
    ).scalar_one_or_none()

    if membership is None:
        raise HTTPException(status_code=404, detail="Not a member of this tenant")

    # Deactivate current active tenant
    await db.execute(
        update(UserTenant)
        .where(UserTenant.user_id == user.sub, UserTenant.active.is_(True))
        .values(active=False)
    )

    # Activate new tenant
    await db.execute(
        update(UserTenant)
        .where(
            UserTenant.user_id == user.sub,
            UserTenant.tenant_id == body.tenant_id,
        )
        .values(active=True)
    )
    await db.commit()

    return SwitchTenantResponse(
        tenant_id=str(body.tenant_id),
        action="refresh_token_required",
    )


# ---------------------------------------------------------------------------
# DELETE /user/account
# ---------------------------------------------------------------------------


@router.delete("/account", response_model=DeleteAccountResponse)
async def delete_account(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Soft-delete user account with 30-day grace period.

    Steps:
    a. Cancel pending/running skill_runs
    b. Set deleting_at flag in user.settings
    c. Remove from all tenant memberships
    d. Wipe api_key_encrypted
    """
    # Check if user is last admin of any tenant
    admin_tenants = (
        await db.execute(
            select(UserTenant, Tenant)
            .join(Tenant, Tenant.id == UserTenant.tenant_id)
            .where(
                UserTenant.user_id == user.sub,
                UserTenant.role == "admin",
            )
        )
    ).all()

    blocking_tenants = []
    for ut, t in admin_tenants:
        admin_count_result = await db.execute(
            select(func.count()).select_from(UserTenant).where(
                UserTenant.tenant_id == ut.tenant_id,
                UserTenant.role == "admin",
            )
        )
        admin_count = admin_count_result.scalar() or 0
        if admin_count <= 1:
            blocking_tenants.append(t.name)

    if blocking_tenants:
        tenant_names = ", ".join(blocking_tenants)
        raise HTTPException(
            status_code=400,
            detail=f"Transfer admin role for {tenant_names} before deleting account",
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    deletion_date = now + datetime.timedelta(days=30)

    # a. Cancel pending/running skill_runs
    await db.execute(
        update(SkillRun)
        .where(
            SkillRun.user_id == user.sub,
            SkillRun.status.in_(["pending", "running"]),
        )
        .values(status="cancelled")
    )

    # b. Set deleting_at flag in user.settings
    user_row = (
        await db.execute(select(User).where(User.id == user.sub))
    ).scalar_one_or_none()

    if user_row is not None:
        new_settings = dict(user_row.settings or {})
        new_settings["deleting_at"] = now.isoformat()
        new_settings["deletion_scheduled"] = deletion_date.isoformat()
        await db.execute(
            update(User).where(User.id == user.sub).values(
                settings=new_settings,
                api_key_encrypted=None,  # d. Wipe API key
            )
        )

    # c. Remove from all tenant memberships
    await db.execute(
        delete(UserTenant).where(UserTenant.user_id == user.sub)
    )

    await db.commit()

    # Note: Actual hard-delete is a background job (Phase 25)
    return DeleteAccountResponse(
        message="Account scheduled for deletion",
        deletion_date=deletion_date.isoformat(),
    )
