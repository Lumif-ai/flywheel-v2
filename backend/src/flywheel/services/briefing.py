"""Briefing assembly service -- proactive morning intelligence.

Assembles greeting, prioritized cards (meetings, suggestions, stale context),
knowledge health metrics, and nudge placeholder into a structured briefing response.

All functions receive an AsyncSession that is already tenant-scoped via RLS.
"""

from __future__ import annotations

import datetime
import logging
from uuid import UUID

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import (
    ContextEntity,
    ContextEntry,
    SuggestionDismissal,
    User,
    WorkItem,
    WorkStream,
)
from flywheel.services.learning_engine import generate_suggestions

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CARDS = 10
MAX_STALE_CARDS = 5
STALE_THRESHOLD_DAYS = 90


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def assemble_briefing(session: AsyncSession, user_id: UUID) -> dict:
    """Assemble the briefing for a user: greeting, cards, knowledge health, nudge.

    Returns a dict matching the BriefingResponse schema:
    {greeting, cards[], card_count, knowledge_health, nudge}
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()

    # Build all sections
    greeting = await _build_greeting(session, user_id, now)
    meeting_cards = await _build_meeting_cards(session, now)
    suggestion_cards = await _build_suggestion_cards(session, user_id)
    stale_cards = await _build_stale_cards(session, today, suggestion_cards)
    knowledge_health = await _build_knowledge_health(session)

    # Merge and sort: meetings (100) < suggestions (200) < stale (300+)
    all_cards = meeting_cards + suggestion_cards + stale_cards
    all_cards.sort(key=lambda c: c["sort_order"])

    # Truncate to max
    cards = all_cards[:MAX_CARDS]

    return {
        "greeting": greeting,
        "cards": cards,
        "card_count": len(cards),
        "knowledge_health": knowledge_health,
        "nudge": None,  # Phase 37 will implement nudge engine with priority ranking
    }


# ---------------------------------------------------------------------------
# Greeting
# ---------------------------------------------------------------------------


async def _build_greeting(
    session: AsyncSession, user_id: UUID, now: datetime.datetime
) -> str:
    """Time-based greeting, optionally with user's name."""
    hour = now.hour
    if 5 <= hour < 12:
        greeting = "Good morning"
    elif 12 <= hour < 17:
        greeting = "Good afternoon"
    elif 17 <= hour < 21:
        greeting = "Good evening"
    else:
        greeting = "Hello"

    # Try to append user name
    try:
        stmt = select(User.name).where(User.id == user_id)
        result = await session.execute(stmt)
        name = result.scalar_one_or_none()
        if name:
            greeting = f"{greeting}, {name}"
    except Exception:
        logger.debug("Could not fetch user name for greeting", exc_info=True)

    return greeting


# ---------------------------------------------------------------------------
# Meeting cards (priority 1, sort_order 100)
# ---------------------------------------------------------------------------


async def _build_meeting_cards(
    session: AsyncSession, now: datetime.datetime
) -> list[dict]:
    """Build cards for upcoming meetings in the next 48 hours."""
    cutoff_48h = now + datetime.timedelta(hours=48)

    stmt = (
        select(WorkItem)
        .where(
            and_(
                WorkItem.type == "meeting",
                WorkItem.status == "upcoming",
                WorkItem.scheduled_at.isnot(None),
                WorkItem.scheduled_at >= now,
                WorkItem.scheduled_at <= cutoff_48h,
            )
        )
        .order_by(WorkItem.scheduled_at.asc())
    )

    result = await session.execute(stmt)
    meetings = result.scalars().all()

    cards: list[dict] = []
    for meeting in meetings:
        # Check for linked entities by matching meeting title words
        entity_matches = await _find_entity_matches(session, meeting.title)

        detail = (
            f"Scheduled for "
            f"{meeting.scheduled_at.strftime('%b %d at %H:%M') if meeting.scheduled_at else 'soon'}"
        )

        cards.append(
            {
                "type": "meeting",
                "priority": "high",
                "sort_order": 100,
                "title": meeting.title,
                "detail": detail,
                "scheduled_at": meeting.scheduled_at.isoformat()
                if meeting.scheduled_at
                else None,
                "entity_matches": entity_matches,
                "work_item_id": str(meeting.id),
            }
        )

    return cards


async def _find_entity_matches(
    session: AsyncSession, title: str
) -> list[dict]:
    """Search ContextEntity by name matching meeting title words."""
    if not title:
        return []

    # Extract words >= 3 chars (skip short words like "the", "and")
    words = [w for w in title.split() if len(w) >= 3]
    if not words:
        return []

    # Build OR conditions for each word
    conditions = [ContextEntity.name.ilike(f"%{word}%") for word in words]

    stmt = select(ContextEntity).where(
        and_(
            # At least one word matches
            *[],  # placeholder
        )
    )
    # Use or_ for matching any word
    from sqlalchemy import or_

    stmt = (
        select(
            ContextEntity.name,
            ContextEntity.entity_type,
        )
        .where(or_(*conditions))
        .limit(10)
    )

    try:
        result = await session.execute(stmt)
        rows = result.all()

        matches = []
        for name, entity_type in rows:
            # Count entries linked to this entity (simplified -- just use mention_count)
            matches.append(
                {
                    "name": name,
                    "type": entity_type,
                }
            )
        return matches
    except Exception:
        logger.debug("Entity match lookup failed", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Suggestion cards (priority 2, sort_order 200)
# ---------------------------------------------------------------------------


async def _build_suggestion_cards(
    session: AsyncSession, user_id: UUID
) -> list[dict]:
    """Build cards from learning engine suggestions."""
    try:
        suggestions = await generate_suggestions(session, user_id, limit=5)
    except Exception:
        logger.warning("Failed to generate suggestions for briefing", exc_info=True)
        return []

    cards: list[dict] = []
    for s in suggestions:
        card: dict = {
            "type": s["type"],
            "priority": s["priority"],
            "sort_order": 200,
            "title": s["title"],
            "detail": s["detail"],
            "suggestion_key": s["key"],
        }
        if s.get("work_item_id"):
            card["work_item_id"] = s["work_item_id"]
        if s.get("file_name"):
            card["file_name"] = s["file_name"]
        cards.append(card)

    return cards


# ---------------------------------------------------------------------------
# Stale context cards (priority 3, sort_order 300+)
# ---------------------------------------------------------------------------


async def _build_stale_cards(
    session: AsyncSession,
    today: datetime.date,
    suggestion_cards: list[dict],
) -> list[dict]:
    """Build cards for stale context entries (>90 days old)."""
    stale_cutoff = today - datetime.timedelta(days=STALE_THRESHOLD_DAYS)

    # Files already covered by suggestion cards (avoid duplicates)
    suggestion_files = {
        c.get("file_name") for c in suggestion_cards if c.get("file_name")
    }

    # Query stale entries grouped by file
    stmt = (
        select(
            ContextEntry.file_name,
            func.count().label("entry_count"),
            func.max(ContextEntry.date).label("newest_date"),
        )
        .where(
            and_(
                ContextEntry.deleted_at.is_(None),
                ContextEntry.date <= stale_cutoff,
            )
        )
        .group_by(ContextEntry.file_name)
        .order_by(func.max(ContextEntry.date).asc())
    )

    result = await session.execute(stmt)
    stale_groups = result.all()

    # Load dismissed stale suggestions
    now = datetime.datetime.now(datetime.timezone.utc)
    dismiss_stmt = select(SuggestionDismissal.suggestion_key).where(
        and_(
            SuggestionDismissal.suggestion_type == "stale_context",
            SuggestionDismissal.expires_at > now,
        )
    )
    dismiss_result = await session.execute(dismiss_stmt)
    dismissed_keys = {row[0] for row in dismiss_result.all()}

    cards: list[dict] = []
    for file_name, entry_count, newest_date in stale_groups:
        if file_name in suggestion_files:
            continue

        suggestion_key = f"stale:{file_name}"
        if suggestion_key in dismissed_keys:
            continue

        days_stale = (today - newest_date).days if newest_date else 999

        cards.append(
            {
                "type": "stale_context",
                "priority": "low",
                "sort_order": 300 + days_stale,
                "title": f"Stale: {file_name}",
                "detail": f"{entry_count} entries, last updated {days_stale} days ago",
                "file_name": file_name,
                "days_stale": days_stale,
                "entry_count": entry_count,
            }
        )

        if len(cards) >= MAX_STALE_CARDS:
            break

    return cards


# ---------------------------------------------------------------------------
# Knowledge health
# ---------------------------------------------------------------------------


async def _build_knowledge_health(session: AsyncSession) -> dict:
    """Compute knowledge health metrics from active work streams."""
    # Active (non-archived) work streams
    stream_stmt = (
        select(
            func.count().label("total_streams"),
            func.coalesce(func.avg(WorkStream.density_score), 0).label("avg_density"),
        )
        .where(WorkStream.archived_at.is_(None))
    )

    stream_result = await session.execute(stream_stmt)
    stream_row = stream_result.one()

    total_streams = stream_row.total_streams
    avg_density = float(stream_row.avg_density)

    # Total context entries (non-deleted)
    entry_stmt = select(func.count()).select_from(ContextEntry).where(
        ContextEntry.deleted_at.is_(None)
    )
    entry_result = await session.execute(entry_stmt)
    total_entries = entry_result.scalar_one()

    # Total context entities
    entity_stmt = select(func.count()).select_from(ContextEntity)
    entity_result = await session.execute(entity_stmt)
    total_entities = entity_result.scalar_one()

    # Health level
    if avg_density >= 70:
        health_level = "strong"
    elif avg_density >= 30:
        health_level = "growing"
    else:
        health_level = "early"

    return {
        "total_streams": total_streams,
        "avg_density": round(avg_density, 2),
        "total_entries": total_entries,
        "total_entities": total_entities,
        "health_level": health_level,
    }
