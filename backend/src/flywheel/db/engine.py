"""Async database engine - active when FLYWHEEL_BACKEND=postgres.

Lazy initialization: engine is only created when explicitly requested.
Includes pool event hooks to prevent session config leakage between
requests AND ``before_cursor_execute`` / ``after_cursor_execute``
listeners that feed per-request DB-roundtrip counters consumed by
:mod:`flywheel.middleware.timing`.
"""

import time

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine

from flywheel.config import settings
from flywheel.middleware.timing import db_count_cv, db_total_ns_cv

_engine = None

# Module-level flag so we only register the cursor-execute listeners
# once per process, even if get_engine() is ever called twice. Event
# listeners accumulate on each ``event.listen`` call; without this
# guard, a second attach would double-count every query.
_timing_hooks_installed = False


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


def _db_before_execute(conn, cursor, statement, parameters, context, executemany):
    """Stamp a start timestamp on the SQLAlchemy ``ExecutionContext``.

    Paired with :func:`_db_after_execute`, this lets us compute
    per-query wall time without needing to thread timing through every
    call site. The attribute name is prefixed with ``_flywheel_`` to
    avoid colliding with any internal SQLAlchemy context state.
    """
    context._flywheel_query_start_ns = time.perf_counter_ns()


def _db_after_execute(conn, cursor, statement, parameters, context, executemany):
    """Increment the per-request DB counters for the completed query.

    Reads the timestamp stamped by :func:`_db_before_execute`, computes
    the elapsed nanoseconds, and folds both the count and the total
    into the ``db_count_cv`` / ``db_total_ns_cv`` ContextVars. Those
    vars are read (and logged) by :class:`flywheel.middleware.timing.TimingMiddleware`
    in its ``finally`` block when the request completes.

    If ``_flywheel_query_start_ns`` is missing (e.g. the before-hook
    raised or was skipped), we short-circuit — better to under-count
    than to log garbage elapsed values.
    """
    start = getattr(context, "_flywheel_query_start_ns", None)
    if start is None:
        return
    elapsed_ns = time.perf_counter_ns() - start
    db_count_cv.set(db_count_cv.get() + 1)
    db_total_ns_cv.set(db_total_ns_cv.get() + elapsed_ns)


def get_engine():
    """Get or create the async database engine."""
    global _engine, _timing_hooks_installed
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=10,
            pool_recycle=3600,
        )
        # Register pool checkout hook to clear stale session config
        event.listen(
            _engine.sync_engine, "checkout", _reset_connection_config
        )
        # Register cursor execute hooks that feed the per-request DB
        # counters consumed by TimingMiddleware. Attach on
        # ``sync_engine`` because cursor events are only emitted on the
        # underlying sync engine of an AsyncEngine.
        if not _timing_hooks_installed:
            event.listen(
                _engine.sync_engine, "before_cursor_execute", _db_before_execute
            )
            event.listen(
                _engine.sync_engine, "after_cursor_execute", _db_after_execute
            )
            _timing_hooks_installed = True
    return _engine


async def dispose_engine():
    """Dispose the engine and release all connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
