"""Auto-provision Supabase users into application tables.

When a user authenticates via Supabase (anonymous sign-in or OAuth), they exist
in Supabase Auth but NOT in our profiles/tenants/user_tenants tables. This
module creates those rows on first API call so every endpoint "just works"
without per-endpoint FK workarounds.

Uses INSERT ... ON CONFLICT DO NOTHING for atomic, race-free provisioning.
Multiple concurrent requests can safely call these functions — the database
handles idempotency natively.

Called from deps.get_current_user (anonymous) and deps.require_tenant
(authenticated).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import Profile, Tenant, UserTenant
from flywheel.db.session import get_session_factory

logger = logging.getLogger(__name__)

# Cache of already-provisioned user IDs (per process lifetime)
_provisioned: set[UUID] = set()


async def ensure_provisioned(user_id: UUID, is_anonymous: bool) -> UUID | None:
    """Ensure Profile + Tenant + UserTenant rows exist for an anonymous user.

    Returns the tenant_id if provisioned, None if user is not anonymous.
    Idempotent — uses INSERT ON CONFLICT DO NOTHING so concurrent requests
    never race. The database handles deduplication atomically.
    """
    if not is_anonymous:
        return None

    if user_id in _provisioned:
        return user_id  # Already provisioned this process lifetime

    factory = get_session_factory()
    async with factory() as session:
        # Atomic upserts — ON CONFLICT DO NOTHING means:
        # - If row exists: skip silently
        # - If row doesn't exist: insert
        # No race condition possible.
        await session.execute(
            pg_insert(Tenant)
            .values(id=user_id, name="Anonymous Workspace")
            .on_conflict_do_nothing(index_elements=["id"])
        )

        await session.execute(
            pg_insert(Profile)
            .values(id=user_id)
            .on_conflict_do_nothing(index_elements=["id"])
        )

        await session.execute(
            pg_insert(UserTenant)
            .values(user_id=user_id, tenant_id=user_id, role="admin", active=True)
            .on_conflict_do_nothing(index_elements=["user_id", "tenant_id"])
        )

        await session.commit()
        _provisioned.add(user_id)

    return user_id


async def ensure_authenticated_provisioned(
    user_id: UUID, email: str | None
) -> tuple[str | None, str]:
    """Ensure Profile + Tenant + UserTenant rows exist for an authenticated user.

    Called from require_tenant() as a self-healing fallback when promote-oauth
    or /auth/me provisioning was missed (e.g., OAuth callback error, direct
    login without onboarding).

    Returns (tenant_id, role) if provisioned, (None, "member") if no email
    is available to derive a tenant name.

    Idempotent — uses INSERT ON CONFLICT DO NOTHING so concurrent requests
    never race.
    """
    if email is None:
        return None, "member"

    if user_id in _provisioned:
        # Already provisioned this process — but we need to return the tenant_id.
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(UserTenant.tenant_id, UserTenant.role).where(
                    UserTenant.user_id == user_id,
                    UserTenant.active == True,  # noqa: E712
                ).limit(1)
            )
            row = result.first()
            if row:
                return str(row.tenant_id), row.role or "admin"
        return None, "member"

    domain = email.split("@")[1] if "@" in email else "Personal"

    factory = get_session_factory()
    async with factory() as session:
        # Check if user already has ANY tenant membership (active or not).
        # This handles partial provisioning where profile/tenant exist but
        # the _provisioned cache missed it (e.g., different process).
        existing_ut = await session.execute(
            select(UserTenant.tenant_id, UserTenant.role).where(
                UserTenant.user_id == user_id,
            ).limit(1)
        )
        existing_row = existing_ut.first()
        if existing_row:
            _provisioned.add(user_id)
            return str(existing_row.tenant_id), existing_row.role or "admin"

        # Ensure profile exists
        await session.execute(
            pg_insert(Profile)
            .values(id=user_id)
            .on_conflict_do_nothing(index_elements=["id"])
        )

        # Create a new tenant named after email domain
        new_tenant = Tenant(name=domain)
        session.add(new_tenant)
        await session.flush()
        tenant_id = new_tenant.id

        # Create user_tenant link. Use ON CONFLICT on the PK (user_id, tenant_id)
        # to handle races. The partial unique index idx_one_active_tenant(user_id)
        # WHERE active=true is safe here because we checked for existing rows above.
        await session.execute(
            pg_insert(UserTenant)
            .values(
                user_id=user_id,
                tenant_id=tenant_id,
                role="admin",
                active=True,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "tenant_id"])
        )

        await session.commit()
        _provisioned.add(user_id)
        logger.info(
            "Auto-provisioned authenticated user %s → tenant %s (%s)",
            user_id, tenant_id, domain,
        )

    return str(tenant_id), "admin"
