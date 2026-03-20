"""Test configuration for flywheel v2 backend.

Sets up sys.path and module aliasing so v1 tests work unchanged.
The v1 tests use `import context_utils` directly, but in v2 the module
lives at `flywheel.context_utils`. We add a sys.modules alias so both
import paths resolve to the same module.

Also provides async Postgres fixtures for storage.py tests when
Docker Postgres is available (port 5434).
"""

import os
import sys
import uuid

import pytest

# Ensure FLYWHEEL_BACKEND is set to flatfile for tests
os.environ.setdefault("FLYWHEEL_BACKEND", "flatfile")

# Add the flywheel package's parent to sys.path so `import flywheel` works
_src_dir = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.abspath(_src_dir))

# Import the real module and alias it so `import context_utils` works
import flywheel.context_utils  # noqa: E402

sys.modules["context_utils"] = flywheel.context_utils


# ---------------------------------------------------------------------------
# Async Postgres fixtures for storage.py tests
# ---------------------------------------------------------------------------

_PG_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://flywheel:flywheel@localhost:5434/flywheel",
)

# Fixed test UUIDs (deterministic per session via namespace)
_NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")
TENANT_A_ID = str(uuid.uuid5(_NAMESPACE, "tenant-a"))
TENANT_B_ID = str(uuid.uuid5(_NAMESPACE, "tenant-b"))
USER_A_ID = str(uuid.uuid5(_NAMESPACE, "user-a"))
USER_B_ID = str(uuid.uuid5(_NAMESPACE, "user-b"))


@pytest.fixture
def tenant_ids():
    """Fixed UUIDs for Tenant A and Tenant B."""
    return {"a": TENANT_A_ID, "b": TENANT_B_ID}


@pytest.fixture
def user_ids():
    """Fixed UUIDs for User A (Tenant A) and User B (Tenant B)."""
    return {"a": USER_A_ID, "b": USER_B_ID}


@pytest.fixture
def pg_engine():
    """Function-scoped async engine for Postgres tests."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_PG_URL, echo=False)
    return engine


@pytest.fixture
def pg_session_factory(pg_engine):
    """Function-scoped async_sessionmaker."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    return async_sessionmaker(
        bind=pg_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest.fixture
async def pg_seed(pg_session_factory):
    """Seed tenants and users via superuser connection (bypasses RLS).

    Runs per-test. Creates test data, yields, then cleans up.
    """
    from sqlalchemy import text as sa_text

    async with pg_session_factory() as session:
        # Insert test tenants
        for tid, name in [(TENANT_A_ID, "Test Tenant A"), (TENANT_B_ID, "Test Tenant B")]:
            await session.execute(
                sa_text(
                    "INSERT INTO tenants (id, name) VALUES (:id, :name) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid, "name": name},
            )
        # Insert test users
        for uid, email, name in [
            (USER_A_ID, f"usera-{USER_A_ID[:8]}@test.com", "User A"),
            (USER_B_ID, f"userb-{USER_B_ID[:8]}@test.com", "User B"),
        ]:
            await session.execute(
                sa_text(
                    "INSERT INTO users (id, email, name) VALUES (:id, :email, :name) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": uid, "email": email, "name": name},
            )
        # Insert user_tenants mappings
        for uid, tid in [(USER_A_ID, TENANT_A_ID), (USER_B_ID, TENANT_B_ID)]:
            await session.execute(
                sa_text(
                    "INSERT INTO user_tenants (user_id, tenant_id, role, active) "
                    "VALUES (:uid, :tid, 'admin', true) ON CONFLICT DO NOTHING"
                ),
                {"uid": uid, "tid": tid},
            )
        await session.commit()

    yield

    # Cleanup: delete all test data (superuser, no RLS)
    async with pg_session_factory() as session:
        for table in [
            "context_events",
            "context_entries",
            "context_catalog",
            "enrichment_cache",
        ]:
            await session.execute(
                sa_text(f"DELETE FROM {table} WHERE tenant_id IN (:a, :b)"),
                {"a": TENANT_A_ID, "b": TENANT_B_ID},
            )
        await session.commit()


@pytest.fixture
async def admin_session(pg_session_factory, pg_seed):
    """Superuser session that bypasses RLS -- for verification queries."""
    from sqlalchemy import text as sa_text

    async with pg_session_factory() as session:
        # Ensure we run as superuser (not app_user from connection pool reuse)
        await session.execute(sa_text("RESET ROLE"))
        yield session


@pytest.fixture
async def tenant_a_session(pg_session_factory, pg_seed):
    """AsyncSession with RLS context for Tenant A / User A."""
    from flywheel.db.session import get_tenant_session

    session = await get_tenant_session(pg_session_factory, TENANT_A_ID, USER_A_ID)
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
async def tenant_b_session(pg_session_factory, pg_seed):
    """AsyncSession with RLS context for Tenant B / User B."""
    from flywheel.db.session import get_tenant_session

    session = await get_tenant_session(pg_session_factory, TENANT_B_ID, USER_B_ID)
    try:
        yield session
    finally:
        await session.close()
