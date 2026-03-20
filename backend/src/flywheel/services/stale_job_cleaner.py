"""Periodic cleanup of stuck running jobs and re-queuing of waiting_for_api jobs.

Runs as a background task alongside the job queue worker:
1. Resets stale running jobs (locked > 10min) to pending if retriable.
2. Marks exhausted stale jobs as failed.
3. Re-queues waiting_for_api jobs when the circuit breaker recovers.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, update

from flywheel.db.models import SkillRun
from flywheel.db.session import get_session_factory
from flywheel.services.circuit_breaker import anthropic_breaker

logger = logging.getLogger(__name__)

STALE_THRESHOLD = timedelta(minutes=10)
CLEANUP_INTERVAL = 60  # seconds


async def cleanup_stale_jobs() -> None:
    """Infinite loop that cleans up stuck jobs every CLEANUP_INTERVAL seconds.

    Three operations per cycle:
    1. Retriable stale jobs (running, locked > 10min, attempts < max) -> pending
    2. Exhausted stale jobs (running, locked > 10min, attempts >= max) -> failed
    3. Waiting-for-API jobs -> pending (only when circuit breaker can execute)
    """
    while True:
        try:
            factory = get_session_factory()
            cutoff = datetime.now(timezone.utc) - STALE_THRESHOLD

            async with factory() as session:
                # 1. Reset retriable stale jobs to pending
                result_retriable = await session.execute(
                    update(SkillRun)
                    .where(
                        and_(
                            SkillRun.status == "running",
                            SkillRun.locked_at < cutoff,
                            SkillRun.attempts < SkillRun.max_attempts,
                        )
                    )
                    .values(
                        status="pending",
                        locked_at=None,
                        locked_by=None,
                    )
                )
                retriable_count = result_retriable.rowcount

                # 2. Mark exhausted stale jobs as failed
                result_exhausted = await session.execute(
                    update(SkillRun)
                    .where(
                        and_(
                            SkillRun.status == "running",
                            SkillRun.locked_at < cutoff,
                            SkillRun.attempts >= SkillRun.max_attempts,
                        )
                    )
                    .values(
                        status="failed",
                        error="Max attempts exceeded (stale job)",
                    )
                )
                exhausted_count = result_exhausted.rowcount

                # 3. Re-queue waiting_for_api jobs when circuit breaker recovers
                waiting_count = 0
                if anthropic_breaker.can_execute():
                    result_waiting = await session.execute(
                        update(SkillRun)
                        .where(SkillRun.status == "waiting_for_api")
                        .values(
                            status="pending",
                            locked_at=None,
                            locked_by=None,
                        )
                    )
                    waiting_count = result_waiting.rowcount

                await session.commit()

            # Log only when work was done
            if retriable_count > 0:
                logger.info(
                    "Reset %d stale retriable job(s) to pending", retriable_count
                )
            if exhausted_count > 0:
                logger.info(
                    "Marked %d exhausted stale job(s) as failed", exhausted_count
                )
            if waiting_count > 0:
                logger.info(
                    "Re-queued %d waiting_for_api job(s) after circuit breaker recovery",
                    waiting_count,
                )

        except Exception:
            logger.exception("Error during stale job cleanup")

        await asyncio.sleep(CLEANUP_INTERVAL)
