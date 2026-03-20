"""Postgres job queue worker using FOR UPDATE SKIP LOCKED.

Background daemon that polls the skill_runs table for pending jobs,
atomically claims one, and dispatches to skill_executor for execution.
Runs as a system process -- does NOT use RLS (no SET ROLE app_user).

Public API:
    claim_next_job(session) -> SkillRun | None
    job_queue_loop() -> None  (runs forever as asyncio task)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import SkillRun
from flywheel.db.session import get_session_factory

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds


async def claim_next_job(session: AsyncSession) -> SkillRun | None:
    """Atomically claim the next pending job using FOR UPDATE SKIP LOCKED.

    Queries for the oldest pending run that is scheduled to run now and has
    not exceeded its retry limit. Uses SKIP LOCKED so multiple workers can
    safely compete for jobs without blocking each other.

    Args:
        session: An async DB session (NOT tenant-scoped -- worker is system-level).

    Returns:
        The claimed SkillRun with status set to 'running', or None if no jobs available.
    """
    result = await session.execute(
        select(SkillRun)
        .where(SkillRun.status == "pending")
        .where(SkillRun.scheduled_for <= datetime.now(timezone.utc))
        .where(SkillRun.attempts < SkillRun.max_attempts)
        .order_by(SkillRun.scheduled_for)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    run = result.scalar_one_or_none()
    if run:
        run.status = "running"
        run.locked_at = datetime.now(timezone.utc)
        run.locked_by = "worker-1"
        run.attempts += 1
        await session.commit()
    return run


async def job_queue_loop() -> None:
    """Main worker loop -- polls every POLL_INTERVAL seconds.

    Uses get_session_factory() for short-lived sessions (no RLS).
    On each iteration: try to claim a job. If claimed, execute it.
    If no job available, sleep and retry.

    This function runs forever and should be started as an asyncio task
    in the FastAPI lifespan manager.
    """
    factory = get_session_factory()
    logger.info("Job queue worker started (poll interval: %ds)", POLL_INTERVAL)

    while True:
        try:
            async with factory() as session:
                run = await claim_next_job(session)

            if run:
                logger.info(
                    "Claimed job %s (skill=%s, attempt=%d)",
                    run.id, run.skill_name, run.attempts,
                )
                # Import here to avoid circular imports at module load time
                from flywheel.services.skill_executor import execute_run

                await execute_run(run)
            else:
                await asyncio.sleep(POLL_INTERVAL)
        except Exception:
            logger.exception("Job queue error")
            await asyncio.sleep(POLL_INTERVAL)
