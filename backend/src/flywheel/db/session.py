"""Async session factory - active when FLYWHEEL_BACKEND=postgres.

Provides:
- get_session_factory(): Lazy singleton async_sessionmaker
- get_db(): FastAPI dependency yielding a plain session
- get_tenant_session(): Creates a session with RLS tenant/user context
- tenant_session(): Async context manager for tenant-scoped sessions
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flywheel.db.engine import get_engine

_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazy singleton session factory -- avoids crash when Postgres is unavailable."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a database session, auto-closes on exit."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_tenant_session(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    user_id: str,
) -> AsyncSession:
    """Create a new AsyncSession with RLS tenant/user context.

    Sets session-level config variables that RLS policies read:
    - app.tenant_id: tenant isolation
    - app.user_id: visibility (private entries)

    Then downgrades to app_user role so RLS policies are enforced.
    """
    session = session_factory()
    await session.execute(text("SELECT set_config('app.tenant_id', :tid, false)"), {"tid": tenant_id})
    await session.execute(text("SELECT set_config('app.user_id', :uid, false)"), {"uid": user_id})
    await session.execute(text("SET ROLE app_user"))
    return session


@asynccontextmanager
async def tenant_session(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    user_id: str,
) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for tenant-scoped sessions with cleanup."""
    session = await get_tenant_session(session_factory, tenant_id, user_id)
    try:
        yield session
    finally:
        await session.close()
