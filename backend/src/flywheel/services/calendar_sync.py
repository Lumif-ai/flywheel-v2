"""Calendar sync background service and meeting prep suggestions.

Handles:
- Background sync loop (5-minute interval) polling connected Google Calendar integrations
- Work item upsert from calendar events (timed + all-day, cancellations)
- Incremental sync with 410 GONE recovery (full re-sync)
- Token revocation detection (marks integration disconnected)
- Meeting prep suggestions (external attendees within 48 hours)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from dateutil.parser import isoparse
from googleapiclient.errors import HttpError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import Integration, SuggestionDismissal, WorkItem
from flywheel.db.session import get_session_factory
from flywheel.services.google_calendar import (
    TokenRevokedException,
    get_valid_credentials,
    list_upcoming_events,
)

logger = logging.getLogger(__name__)

SYNC_INTERVAL = 300  # 5 minutes
LOOKAHEAD_DAYS = 14  # sync 2 weeks ahead
SUGGESTION_WINDOW_HOURS = 48


# ---------------------------------------------------------------------------
# Work item upsert
# ---------------------------------------------------------------------------


async def upsert_meeting_work_item(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    event: dict,
) -> None:
    """Create or update a WorkItem from a Google Calendar event.

    Does NOT commit -- caller is responsible for committing the session.
    """
    external_id = f"gcal:{event['id']}"

    # Find existing work item by external_id
    result = await db.execute(
        select(WorkItem).where(
            and_(
                WorkItem.tenant_id == tenant_id,
                WorkItem.external_id == external_id,
            )
        )
    )
    existing = result.scalar_one_or_none()

    # Handle cancelled events
    if event.get("status") == "cancelled":
        if existing is not None:
            existing.status = "cancelled"
        return

    # Parse scheduled_at -- handle both timed and all-day events
    start = event.get("start", {})
    date_time_str = start.get("dateTime")
    date_str = start.get("date")

    if date_time_str:
        scheduled_at = isoparse(date_time_str)
    elif date_str:
        # All-day event: set time to 00:00 UTC
        scheduled_at = datetime.strptime(date_str, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    else:
        scheduled_at = None

    # Extract attendees and check for external attendees
    attendees_raw = event.get("attendees", [])
    attendee_emails = [a.get("email", "") for a in attendees_raw]
    has_external_attendees = any(
        not a.get("self", False) and not a.get("organizer", False)
        for a in attendees_raw
    )

    # Build data dict
    data = {
        "attendees": attendee_emails,
        "has_external_attendees": has_external_attendees,
        "description": event.get("description"),
        "location": event.get("location"),
        "calendar_link": event.get("htmlLink"),
    }

    title = event.get("summary") or "Untitled Meeting"

    if existing is not None:
        # Update existing work item
        existing.title = title
        existing.scheduled_at = scheduled_at
        existing.data = data
        existing.status = "upcoming"  # Re-activate if previously cancelled
    else:
        # Create new work item
        work_item = WorkItem(
            tenant_id=tenant_id,
            user_id=user_id,
            type="meeting",
            title=title,
            status="upcoming",
            data=data,
            source="google-calendar",
            external_id=external_id,
            scheduled_at=scheduled_at,
        )
        db.add(work_item)


# ---------------------------------------------------------------------------
# Calendar sync
# ---------------------------------------------------------------------------


async def sync_calendar(
    db: AsyncSession,
    integration: Integration,
    _retry_count: int = 0,
) -> int:
    """Sync a single Google Calendar integration, upserting work items.

    Returns the number of events processed.

    Raises:
        TokenRevokedException: If the refresh token has been revoked.
    """
    creds = await get_valid_credentials(integration)

    # Get sync token from integration settings
    sync_token = (integration.settings or {}).get("sync_token")

    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=LOOKAHEAD_DAYS)).isoformat()

    try:
        response = await list_upcoming_events(
            creds, time_min, time_max, sync_token
        )
    except HttpError as exc:
        if exc.resp.status == 410 and _retry_count < 1:
            # 410 GONE: sync token expired, clear and do full re-sync
            logger.info(
                "Sync token expired for integration %s, doing full re-sync",
                integration.id,
            )
            settings = dict(integration.settings or {})
            settings["sync_token"] = None
            integration.settings = settings
            return await sync_calendar(db, integration, _retry_count=1)
        raise

    # Upsert each event as a work item
    items = response.get("items", [])
    for event in items:
        await upsert_meeting_work_item(
            db, integration.tenant_id, integration.user_id, event
        )

    # Store next sync token
    next_sync_token = response.get("nextSyncToken")
    if next_sync_token:
        settings = dict(integration.settings or {})
        settings["sync_token"] = next_sync_token
        integration.settings = settings

    # Update last synced timestamp
    integration.last_synced_at = datetime.now(timezone.utc)

    # Commit once after all upserts
    await db.commit()

    return len(items)


# ---------------------------------------------------------------------------
# Background sync loop
# ---------------------------------------------------------------------------


async def calendar_sync_loop() -> None:
    """Infinite loop that syncs all connected Google Calendar integrations.

    Uses short-lived DB sessions per cycle to avoid connection pool exhaustion.
    """
    while True:
        try:
            factory = get_session_factory()

            async with factory() as session:
                # Find all connected Google Calendar integrations
                result = await session.execute(
                    select(Integration).where(
                        and_(
                            Integration.provider == "google-calendar",
                            Integration.status == "connected",
                        )
                    )
                )
                integrations = result.scalars().all()

                for integration in integrations:
                    try:
                        count = await sync_calendar(session, integration)
                        if count > 0:
                            logger.info(
                                "Synced %d events for integration %s",
                                count,
                                integration.id,
                            )
                    except TokenRevokedException:
                        logger.warning(
                            "Token revoked for integration %s, marking disconnected",
                            integration.id,
                        )
                        integration.status = "disconnected"
                        integration.credentials_encrypted = None
                        await session.commit()
                    except Exception:
                        logger.exception(
                            "Error syncing integration %s", integration.id
                        )

        except Exception:
            logger.exception("Error in calendar sync loop iteration")

        await asyncio.sleep(SYNC_INTERVAL)


# ---------------------------------------------------------------------------
# Meeting prep suggestions
# ---------------------------------------------------------------------------


async def get_meeting_prep_suggestions(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
) -> list[dict]:
    """Get meeting prep suggestions for upcoming meetings with external attendees.

    Returns meetings within the next 48 hours that have external attendees
    and haven't been dismissed by the user.
    """
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=SUGGESTION_WINDOW_HOURS)

    # Find upcoming meetings with external attendees in the next 48 hours
    result = await db.execute(
        select(WorkItem).where(
            and_(
                WorkItem.tenant_id == tenant_id,
                WorkItem.type == "meeting",
                WorkItem.status == "upcoming",
                WorkItem.scheduled_at >= now,
                WorkItem.scheduled_at <= window_end,
            )
        )
    )
    meetings = result.scalars().all()

    suggestions = []
    for meeting in meetings:
        # Filter to meetings with external attendees
        if not (meeting.data or {}).get("has_external_attendees", False):
            continue

        # Check if this suggestion has been dismissed
        dismissal_result = await db.execute(
            select(SuggestionDismissal).where(
                and_(
                    SuggestionDismissal.tenant_id == tenant_id,
                    SuggestionDismissal.user_id == user_id,
                    SuggestionDismissal.suggestion_type == "meeting-prep",
                    SuggestionDismissal.suggestion_key == str(meeting.id),
                    SuggestionDismissal.expires_at > now,
                )
            )
        )
        if dismissal_result.scalar_one_or_none() is not None:
            continue

        suggestions.append(
            {
                "type": "meeting-prep",
                "work_item_id": str(meeting.id),
                "title": f"Prepare for {meeting.title}",
                "scheduled_at": meeting.scheduled_at.isoformat()
                if meeting.scheduled_at
                else None,
                "attendees": (meeting.data or {}).get("attendees", []),
            }
        )

    return suggestions
