"""FastAPI authentication and database dependencies.

Dependency chain::

    get_current_user  (decodes JWT, returns TokenPayload)
      -> require_tenant  (asserts tenant_id is set)
        -> require_admin  (asserts role == "admin")

    get_tenant_db  (bridges JWT identity to RLS-scoped session)
    get_db_unscoped  (plain session, no RLS -- for account-level ops)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from flywheel.auth.jwt import TokenPayload, decode_jwt
from flywheel.auth.anonymous import ensure_provisioned
from flywheel.db.models import UserTenant
from flywheel.db.session import get_db, get_session_factory, get_tenant_session

_bearer = HTTPBearer(auto_error=False)

# Cache resolved tenant IDs for authenticated users (per process lifetime)
_user_tenant_cache: dict[str, str] = {}


async def _resolve_tenant_for_user(user_id) -> str | None:
    """Look up tenant_id from user_tenants for an authenticated user."""
    uid = str(user_id)
    if uid in _user_tenant_cache:
        return _user_tenant_cache[uid]

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(UserTenant.tenant_id).where(
                UserTenant.user_id == user_id,
                UserTenant.active == True,
            ).limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            tid = str(row)
            _user_tenant_cache[uid] = tid
            return tid
    return None


async def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> TokenPayload:
    """Extract and validate the JWT from the Authorization header.

    For anonymous Supabase users, auto-provisions Profile + Tenant + UserTenant
    rows on first API call so downstream endpoints don't hit FK violations.

    For authenticated users without tenant_id in JWT (e.g., freshly OAuth'd),
    looks up their tenant from user_tenants table.
    """
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = decode_jwt(cred.credentials)

    # Auto-provision anonymous users into app tables
    if token.is_anonymous:
        tenant_id = await ensure_provisioned(token.sub, is_anonymous=True)
        if tenant_id and token.tenant_id is None:
            # Patch app_metadata so downstream sees the tenant
            token.app_metadata["tenant_id"] = str(tenant_id)
    elif token.tenant_id is None:
        # Authenticated user without tenant_id in JWT (post-OAuth).
        # Look up their tenant from the DB.
        tenant_id = await _resolve_tenant_for_user(token.sub)
        if tenant_id:
            token.app_metadata["tenant_id"] = str(tenant_id)

    return token


async def require_tenant(
    user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """Require the user to have an active tenant."""
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active tenant",
        )
    return user


async def require_admin(
    user: TokenPayload = Depends(require_tenant),
) -> TokenPayload:
    """Require the user to be a tenant admin."""
    if user.tenant_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def get_tenant_db(
    request: Request,
    user: TokenPayload = Depends(require_tenant),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a tenant-scoped AsyncSession with RLS context set.

    Reads X-Focus-Id header to propagate active focus into session config.
    """
    focus_id = request.headers.get("x-focus-id")
    factory = get_session_factory()
    session = await get_tenant_session(
        factory,
        tenant_id=str(user.tenant_id),
        user_id=str(user.sub),
        focus_id=focus_id,
    )
    try:
        yield session
    finally:
        await session.close()


async def get_db_unscoped() -> AsyncGenerator[AsyncSession, None]:
    """Yield a plain session without tenant scope (account-level ops)."""
    async for session in get_db():
        yield session
