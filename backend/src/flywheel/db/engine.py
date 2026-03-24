"""Async database engine - active when FLYWHEEL_BACKEND=postgres.

Lazy initialization: engine is only created when explicitly requested.
Includes pool event hooks to prevent session config leakage between requests.
"""

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine

from flywheel.config import settings

_engine = None


def _reset_connection_config(dbapi_connection, connection_record, connection_proxy):
    """Reset app.* session config on connection checkout from pool.

    Prevents tenant_id/user_id/focus_id from leaking between requests
    when connections are reused from the pool.

    Args:
        dbapi_connection: The raw DBAPI connection being checked out.
        connection_record: The _ConnectionRecord managing this connection.
        connection_proxy: The _ConnectionFairy proxy for this checkout.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("SELECT set_config('app.tenant_id', '', false)")
    cursor.execute("SELECT set_config('app.user_id', '', false)")
    cursor.execute("SELECT set_config('app.focus_id', '', false)")
    cursor.execute("RESET ROLE")
    cursor.close()


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
        # Register pool checkout hook to clear stale session config
        event.listen(
            _engine.sync_engine, "checkout", _reset_connection_config
        )
    return _engine


async def dispose_engine():
    """Dispose the engine and release all connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
