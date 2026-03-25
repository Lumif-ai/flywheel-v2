"""Background task: delete anonymous Supabase auth users not linked to accounts after 30 days.

Runs daily. Uses the Supabase Admin API to list and delete anonymous users.
Cross-references with local users table to verify they haven't been promoted.

Pattern follows stale_job_cleaner.py: short-lived DB sessions, graceful error handling.
"""

import asyncio
import datetime
import logging

from flywheel.config import settings

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 86400  # 24 hours
ANONYMOUS_MAX_AGE_DAYS = 30


async def anonymous_cleanup_loop():
    """Run anonymous user cleanup once per day."""
    # Wait 60 seconds after startup before first run
    await asyncio.sleep(60)

    while True:
        try:
            await _cleanup_stale_anonymous_users()
        except asyncio.CancelledError:
            logger.info("anonymous_cleanup_stopped")
            return
        except Exception:
            logger.exception("anonymous_cleanup_error")

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


async def _cleanup_stale_anonymous_users():
    """Delete anonymous auth users older than 30 days who haven't promoted."""
    if not settings.supabase_url or not settings.supabase_service_key:
        logger.debug("anonymous_cleanup_skipped reason=no_supabase_config")
        return

    from supabase import create_client

    from flywheel.db.engine import get_engine
    from flywheel.db.models import Profile, UserTenant
    from sqlalchemy import delete as sql_delete, select
    from sqlalchemy.ext.asyncio import AsyncSession

    # Use Supabase Admin API to list anonymous users
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=ANONYMOUS_MAX_AGE_DAYS
    )

    # Get local users to cross-reference
    engine = get_engine()
    deleted_count = 0

    async with AsyncSession(engine) as db:
        # After refactor: Profile has no email/is_anonymous columns.
        # All stale profiles are candidates; Supabase delete is idempotent.
        result = await db.execute(
            select(Profile.id)
            .where(Profile.created_at < cutoff)
        )

        stale_users = result.all()

    for row in stale_users:
        user_id = row[0]
        auth_uid = str(user_id)  # Profile.id IS the Supabase Auth UID
        try:
            # Delete from Supabase Auth (synchronous SDK call)
            await asyncio.to_thread(
                supabase.auth.admin.delete_user, str(auth_uid)
            )
            # Delete local user record (short-lived session per user)
            async with AsyncSession(engine) as db:
                # Remove user_tenant associations first (FK constraint)
                await db.execute(
                    sql_delete(UserTenant).where(UserTenant.user_id == user_id)
                )
                await db.execute(
                    sql_delete(Profile).where(Profile.id == user_id)
                )
                await db.commit()
            deleted_count += 1
        except Exception:
            logger.exception("anonymous_cleanup_delete_failed user_id=%s", user_id)

    if deleted_count > 0:
        logger.info("anonymous_cleanup_complete deleted=%d", deleted_count)
    else:
        logger.debug("anonymous_cleanup_complete deleted=0")
