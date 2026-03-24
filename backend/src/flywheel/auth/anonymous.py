"""Auto-provision anonymous Supabase users into application tables.

When a user authenticates via Supabase anonymous sign-in, they exist in
Supabase Auth but NOT in our users/tenants/user_tenants tables. This module
creates those rows on first API call so every endpoint "just works" for
anonymous users without per-endpoint FK workarounds.

Uses INSERT ... ON CONFLICT DO NOTHING for atomic, race-free provisioning.
Multiple concurrent requests can safely call ensure_provisioned — the database
handles idempotency natively.

Called from deps.get_current_user after JWT decode.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import Tenant, User, UserTenant
from flywheel.db.session import get_session_factory

logger = logging.getLogger(__name__)

# Cache of already-provisioned user IDs (per process lifetime)
_provisioned: set[UUID] = set()


async def ensure_provisioned(user_id: UUID, is_anonymous: bool) -> UUID | None:
    """Ensure User + Tenant + UserTenant rows exist for an anonymous user.

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
            pg_insert(User)
            .values(id=user_id, email=None, is_anonymous=True)
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
