"""Async session factory - active when FLYWHEEL_BACKEND=postgres."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flywheel.db.engine import get_engine

AsyncSessionLocal = async_sessionmaker(
    bind=get_engine(),
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a database session, auto-closes on exit."""
    async with AsyncSessionLocal() as session:
        yield session
