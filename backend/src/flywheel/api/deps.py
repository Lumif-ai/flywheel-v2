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

from flywheel.auth.jwt import TokenPayload, decode_jwt
from flywheel.auth.anonymous import ensure_provisioned
from flywheel.db.session import get_db, get_session_factory, get_tenant_session

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> TokenPayload:
    """Extract and validate the JWT from the Authorization header.

    For anonymous Supabase users, auto-provisions User + Tenant + UserTenant
    rows on first API call so downstream endpoints don't hit FK violations.
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
