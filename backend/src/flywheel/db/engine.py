"""Async database engine - active when FLYWHEEL_BACKEND=postgres.

Lazy initialization: engine is only created when explicitly requested.
"""

from sqlalchemy.ext.asyncio import create_async_engine

from flywheel.config import settings

_engine = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
    return _engine


async def dispose_engine():
    """Dispose the engine and release all connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
