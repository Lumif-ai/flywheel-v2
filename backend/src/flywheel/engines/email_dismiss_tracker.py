"""email_dismiss_tracker.py — Dismiss-based scoring signal for sender feedback.

Queries the email_drafts table for recent dismissals from a specific sender
and returns a scoring signal string suitable for injection into the Haiku
scoring prompt.

Functions:
  get_dismiss_signal(db, tenant_id, sender_email, days, threshold) -> str
    Returns a DISMISS SIGNAL block string if the sender has >= threshold
    dismissals in the past `days` days. Returns empty string otherwise.
    Always returns empty string on any DB error (non-fatal).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_dismiss_signal(
    db: AsyncSession,
    tenant_id: UUID,
    sender_email: str,
    days: int = 30,
    threshold: int = 3,
) -> str:
    """Return a dismiss signal string for injection into the scoring prompt.

    Counts recent (within `days` days) dismissed drafts from `sender_email`
    for the given tenant. If the count is at or above `threshold`, returns a
    DISMISS SIGNAL block that instructs the scorer to score DOWN for this sender.
    Returns empty string if below threshold or on any error.

    Uses make_interval(days => :days) to avoid SQL injection and
    parameterization issues with the interval expression — same pattern
    as _check_daily_scoring_cap in gmail_sync.py but with a named param
    for the interval length.

    Args:
        db: AsyncSession with RLS context already set (caller-owned).
        tenant_id: Tenant UUID.
        sender_email: Full sender email address to look up.
        days: Rolling lookback window in days (default 30).
        threshold: Minimum dismissal count to trigger the signal (default 3).

    Returns:
        Non-empty DISMISS SIGNAL string if threshold reached, else "".
    """
    try:
        result = await db.execute(
            sa_text(
                "SELECT COUNT(*) FROM email_drafts ed "
                "JOIN emails e ON ed.email_id = e.id "
                "WHERE e.tenant_id = :tid "
                "AND e.sender_email = :sender "
                "AND ed.status = 'dismissed' "
                "AND ed.updated_at >= now() - make_interval(days => :days)"
            ).bindparams(tid=tenant_id, sender=sender_email, days=days)
        )
        count = result.scalar_one()

        if count >= threshold:
            return (
                f"\nDISMISS SIGNAL: User has dismissed {count} draft(s) for this sender "
                f"in the past {days} days. Score DOWN: this sender category produces "
                f"drafts the user doesn't want to send."
            )
        return ""

    except Exception as exc:  # noqa: BLE001
        # Non-fatal — scoring must never fail due to dismiss tracker errors
        logger.error(
            "dismiss_tracker: query failed for tenant_id=%s: %s: %s",
            tenant_id,
            type(exc).__name__,
            exc,
        )
        return ""
