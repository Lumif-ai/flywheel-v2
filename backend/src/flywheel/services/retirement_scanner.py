"""Background task: flag stale pipeline entries and retire inactive ones.

Runs hourly. Entries with no activity for 60 days get stale_notified_at set.
Entries stale for 30 additional days (90 total) get retired_at set.
If activity occurs after stale flagging, the stale flag is cleared.

Pattern follows anonymous_cleanup.py: async loop with try/except, graceful shutdown.
"""

import asyncio
import logging

from sqlalchemy import text, update

from flywheel.db.models import PipelineEntry
from flywheel.db.session import get_session_factory

logger = logging.getLogger(__name__)

SCAN_INTERVAL = 3600  # 1 hour
STALE_DAYS = 60
RETIRE_DAYS_AFTER_STALE = 30


async def retirement_scanner_loop():
    """Run retirement scanning once per hour."""
    # Wait 90 seconds after startup before first run
    await asyncio.sleep(90)

    while True:
        try:
            await _scan_and_retire()
        except asyncio.CancelledError:
            logger.info("retirement_scanner_stopped")
            return
        except Exception:
            logger.exception("retirement_scanner_error")

        await asyncio.sleep(SCAN_INTERVAL)


async def _scan_and_retire():
    """Execute the four retirement operations in a single session."""
    factory = get_session_factory()

    async with factory() as session:
        # 1. Flag stale: entries with last_activity_at older than 60 days
        result_stale = await session.execute(
            update(PipelineEntry)
            .where(
                PipelineEntry.last_activity_at.is_not(None),
                PipelineEntry.last_activity_at < text(f"NOW() - interval '{STALE_DAYS} days'"),
                PipelineEntry.stale_notified_at.is_(None),
                PipelineEntry.retired_at.is_(None),
            )
            .values(stale_notified_at=text("NOW()"))
        )
        if result_stale.rowcount > 0:
            logger.info("retirement_scanner_flagged_stale count=%d", result_stale.rowcount)

        # 2. Flag no-activity stale: entries with NULL last_activity_at and created > 60 days ago
        result_no_activity = await session.execute(
            update(PipelineEntry)
            .where(
                PipelineEntry.last_activity_at.is_(None),
                PipelineEntry.created_at < text(f"NOW() - interval '{STALE_DAYS} days'"),
                PipelineEntry.stale_notified_at.is_(None),
                PipelineEntry.retired_at.is_(None),
            )
            .values(stale_notified_at=text("NOW()"))
        )
        if result_no_activity.rowcount > 0:
            logger.info("retirement_scanner_flagged_no_activity count=%d", result_no_activity.rowcount)

        # 3. Clear stale: activity happened after stale flag was set
        result_clear = await session.execute(
            update(PipelineEntry)
            .where(
                PipelineEntry.stale_notified_at.is_not(None),
                PipelineEntry.retired_at.is_(None),
                PipelineEntry.last_activity_at > PipelineEntry.stale_notified_at,
            )
            .values(stale_notified_at=None)
        )
        if result_clear.rowcount > 0:
            logger.info("retirement_scanner_cleared_stale count=%d", result_clear.rowcount)

        # 4. Retire: stale for 30+ days
        result_retire = await session.execute(
            update(PipelineEntry)
            .where(
                PipelineEntry.stale_notified_at.is_not(None),
                PipelineEntry.stale_notified_at < text(f"NOW() - interval '{RETIRE_DAYS_AFTER_STALE} days'"),
                PipelineEntry.retired_at.is_(None),
            )
            .values(retired_at=text("NOW()"))
        )
        if result_retire.rowcount > 0:
            logger.info("retirement_scanner_retired count=%d", result_retire.rowcount)

        await session.commit()
