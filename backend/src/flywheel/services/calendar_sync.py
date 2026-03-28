"""Calendar sync background service and meeting prep suggestions.

Handles:
- Background sync loop (5-minute interval) polling connected Google Calendar integrations
- Meeting row upsert from calendar events (timed + all-day, cancellations)
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
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import Integration, Meeting, SuggestionDismissal
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
# Meeting row upsert (replaces upsert_meeting_work_item)
# ---------------------------------------------------------------------------


async def upsert_meeting_row(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    event: dict,
) -> None:
    """Create or update a Meeting row from a Google Calendar event.

    Uses calendar_event_id for dedup (not external_id pattern).
    Sets processing_status='scheduled' for new rows.
    Skips update if existing row already has Granola data (richer source).

    Does NOT commit -- caller is responsible for committing the session.
    """
    cal_event_id = event["id"]

    # Find existing meeting by calendar_event_id
    result = await db.execute(
        select(Meeting).where(
            and_(
                Meeting.tenant_id == tenant_id,
                Meeting.calendar_event_id == cal_event_id,
            )
        )
    )
    existing = result.scalar_one_or_none()

    # Handle cancelled events
    if event.get("status") == "cancelled":
        if existing is not None:
            # Do NOT cancel if Granola data is attached (richer source)
            if existing.granola_note_id:
                return
            existing.processing_status = "cancelled"
        return

    # Skip update if existing row has Granola data (richer source wins)
    if existing is not None and existing.granola_note_id:
        return

    # Parse meeting_date -- handle both timed and all-day events
    start = event.get("start", {})
    date_time_str = start.get("dateTime")
    date_str = start.get("date")

    if date_time_str:
        meeting_date = isoparse(date_time_str)
    elif date_str:
        # All-day event: set time to 00:00 UTC
        meeting_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    else:
        meeting_date = datetime.now(timezone.utc)

    # Parse attendees into Meeting-compatible format
    attendees_raw = event.get("attendees", [])
    attendees = [
        {
            "email": a.get("email", ""),
            "name": a.get("displayName", ""),
            "is_external": not a.get("self", False) and not a.get("organizer", False),
        }
        for a in attendees_raw
    ]

    title = event.get("summary") or "Untitled Meeting"

    if existing is not None:
        # Update existing meeting row
        existing.title = title
        existing.meeting_date = meeting_date
        existing.attendees = attendees
        existing.location = event.get("location")
        existing.description = event.get("description")
        existing.processing_status = "scheduled"
    else:
        # Create new meeting row
        meeting = Meeting(
            tenant_id=tenant_id,
            user_id=user_id,
            provider="google-calendar",
            external_id=f"gcal:{cal_event_id}",
            calendar_event_id=cal_event_id,
            title=title,
            meeting_date=meeting_date,
            attendees=attendees,
            location=event.get("location"),
            description=event.get("description"),
            processing_status="scheduled",
        )
        db.add(meeting)


# ---------------------------------------------------------------------------
# Calendar sync
# ---------------------------------------------------------------------------


async def sync_calendar(
    db: AsyncSession,
    integration: Integration,
    _retry_count: int = 0,
) -> int:
    """Sync a single Google Calendar integration, upserting Meeting rows.

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

    # Upsert each event as a Meeting row
    items = response.get("items", [])
    for event in items:
        await upsert_meeting_row(
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
    Sets RLS context (app.tenant_id, app.user_id) before writing Meeting rows
    to satisfy split-visibility RLS policies.
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
                    if not integration.credentials_encrypted:
                        logger.debug("Skipping integration %s — no credentials stored", integration.id)
                        continue
                    try:
                        # Set RLS context for this integration's tenant/user
                        await session.execute(
                            text("SET LOCAL app.tenant_id = :tid"),
                            {"tid": str(integration.tenant_id)},
                        )
                        await session.execute(
                            text("SET LOCAL app.user_id = :uid"),
                            {"uid": str(integration.user_id)},
                        )

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

    Queries the Meeting table for scheduled meetings within the next 48 hours
    that have at least one external attendee and haven't been dismissed.
    """
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=SUGGESTION_WINDOW_HOURS)

    # Find scheduled meetings within the suggestion window
    result = await db.execute(
        select(Meeting).where(
            and_(
                Meeting.tenant_id == tenant_id,
                Meeting.processing_status == "scheduled",
                Meeting.meeting_date >= now,
                Meeting.meeting_date <= window_end,
                Meeting.deleted_at.is_(None),
            )
        )
    )
    meetings = result.scalars().all()

    suggestions = []
    for meeting in meetings:
        # Filter to meetings with at least one external attendee
        has_external = any(
            a.get("is_external", False) for a in (meeting.attendees or [])
        )
        if not has_external:
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
                "meeting_id": str(meeting.id),
                "title": f"Prepare for {meeting.title}",
                "scheduled_at": meeting.meeting_date.isoformat()
                if meeting.meeting_date
                else None,
                "attendees": meeting.attendees,
                "account_id": str(meeting.account_id) if meeting.account_id else None,
            }
        )

    return suggestions
