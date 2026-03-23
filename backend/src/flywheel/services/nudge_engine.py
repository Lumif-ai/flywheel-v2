"""Nudge engine -- priority-ranked daily nudge selection.

Selects at most one nudge per day for a user, ranked by priority:
1. Integration connect (Calendar day 2, Gmail day 5, Slack day 7)
2. Knowledge gap (streams with lowest density)
3. Context enrichment (entities with lowest mention count)

Cadence: daily for first 14 days, weekly after (or after all integrations connected).
Dismissed nudges do not resurface for 7 days (via SuggestionDismissal).
"""

from __future__ import annotations

import datetime
import logging
from uuid import UUID

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import (
    ContextEntity,
    Integration,
    NudgeInteraction,
    SuggestionDismissal,
    User,
    WorkStream,
    WorkStreamEntity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Progressive integration connect sequence: (provider, display_name, min_account_age_days)
INTEGRATION_SEQUENCE = [
    ("google-calendar", "Google Calendar", 2),
    ("gmail", "Gmail", 5),
    ("slack", "Slack", 7),
]

DAILY_CADENCE_DAYS = 14
WEEKLY_CADENCE_INTERVAL = 7
GAP_NUDGE_COOLDOWN_DAYS = 3
ENRICHMENT_NUDGE_COOLDOWN_DAYS = 5


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def select_nudge(
    session: AsyncSession, user_id: UUID, tenant_id: UUID
) -> dict | None:
    """Select at most one nudge for the user today.

    Returns a nudge dict or None if no nudge should be shown.
    Priority: integration_connect > knowledge_gap > context_enrichment.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. Compute account age
    user_stmt = select(User.created_at).where(User.id == user_id)
    user_result = await session.execute(user_stmt)
    user_created = user_result.scalar_one_or_none()
    if user_created is None:
        return None

    account_age_days = (now - user_created).days

    # 2. Check connected integrations count
    connected_stmt = select(func.count()).select_from(Integration).where(
        and_(
            Integration.tenant_id == tenant_id,
            Integration.user_id == user_id,
            Integration.status == "connected",
        )
    )
    connected_result = await session.execute(connected_stmt)
    connected_count = connected_result.scalar_one()

    all_integrations_connected = connected_count >= len(INTEGRATION_SEQUENCE)

    # 3. Check cadence: daily for first 14 days, weekly after
    if account_age_days > DAILY_CADENCE_DAYS or all_integrations_connected:
        # Weekly cadence: check if any nudge shown in last 7 days
        weekly_stmt = select(func.count()).select_from(NudgeInteraction).where(
            and_(
                NudgeInteraction.user_id == user_id,
                NudgeInteraction.tenant_id == tenant_id,
                NudgeInteraction.action == "shown",
                NudgeInteraction.created_at >= now - datetime.timedelta(days=WEEKLY_CADENCE_INTERVAL),
            )
        )
        weekly_result = await session.execute(weekly_stmt)
        if weekly_result.scalar_one() > 0:
            return None

    # 4. Check if already shown today
    today_stmt = select(func.count()).select_from(NudgeInteraction).where(
        and_(
            NudgeInteraction.user_id == user_id,
            NudgeInteraction.tenant_id == tenant_id,
            NudgeInteraction.action == "shown",
            NudgeInteraction.created_at >= today_midnight,
        )
    )
    today_result = await session.execute(today_stmt)
    if today_result.scalar_one() > 0:
        return None

    # Priority 1: Integration connect nudges
    nudge = await _select_integration_nudge(
        session, user_id, tenant_id, account_age_days, now
    )
    if nudge:
        await record_nudge_action(
            session, tenant_id, user_id,
            nudge["type"], nudge["key"], "shown",
        )
        return nudge

    # Priority 2: Knowledge gap nudges
    nudge = await _select_gap_nudge(session, user_id, tenant_id, now)
    if nudge:
        await record_nudge_action(
            session, tenant_id, user_id,
            nudge["type"], nudge["key"], "shown",
        )
        return nudge

    # Priority 3: Context enrichment nudges
    nudge = await _select_enrichment_nudge(session, user_id, tenant_id, now)
    if nudge:
        await record_nudge_action(
            session, tenant_id, user_id,
            nudge["type"], nudge["key"], "shown",
        )
        return nudge

    return None


# ---------------------------------------------------------------------------
# Priority 1: Integration connect nudges
# ---------------------------------------------------------------------------


async def _select_integration_nudge(
    session: AsyncSession,
    user_id: UUID,
    tenant_id: UUID,
    account_age_days: int,
    now: datetime.datetime,
) -> dict | None:
    """Select an integration connect nudge based on progressive day sequence."""

    # Query connected integrations for this user
    connected_stmt = select(Integration.provider).where(
        and_(
            Integration.tenant_id == tenant_id,
            Integration.user_id == user_id,
            Integration.status == "connected",
        )
    )
    connected_result = await session.execute(connected_stmt)
    connected_providers = {row[0] for row in connected_result.all()}

    # Load active dismissals for nudge type
    dismiss_stmt = select(SuggestionDismissal.suggestion_key).where(
        and_(
            SuggestionDismissal.tenant_id == tenant_id,
            SuggestionDismissal.user_id == user_id,
            SuggestionDismissal.suggestion_type == "nudge",
            SuggestionDismissal.expires_at > now,
        )
    )
    dismiss_result = await session.execute(dismiss_stmt)
    dismissed_keys = {row[0] for row in dismiss_result.all()}

    for provider, display_name, min_day in INTEGRATION_SEQUENCE:
        if account_age_days < min_day:
            continue
        if provider in connected_providers:
            continue

        nudge_key = f"connect:{provider}"
        if nudge_key in dismissed_keys:
            continue

        # Build dynamic impact text
        impact_text = await _build_integration_impact(
            session, tenant_id, provider, display_name
        )

        return {
            "type": "integration_connect",
            "key": nudge_key,
            "provider": provider,
            "title": f"Connect {display_name}",
            "body": impact_text,
            "action_url": "/settings",
            "action_label": "Connect",
        }

    return None


async def _build_integration_impact(
    session: AsyncSession,
    tenant_id: UUID,
    provider: str,
    display_name: str,
) -> str:
    """Build dynamic impact text for integration connect nudges."""
    if provider == "google-calendar":
        stream_count_stmt = select(func.count()).select_from(WorkStream).where(
            and_(
                WorkStream.tenant_id == tenant_id,
                WorkStream.archived_at.is_(None),
            )
        )
        result = await session.execute(stream_count_stmt)
        count = result.scalar_one()
        return f"Connect {display_name} -- auto-detect meetings with your {count} active streams"

    elif provider == "gmail":
        entity_count_stmt = select(func.count()).select_from(ContextEntity).where(
            ContextEntity.tenant_id == tenant_id
        )
        result = await session.execute(entity_count_stmt)
        count = result.scalar_one()
        return f"Connect {display_name} -- surface email threads about your {count} tracked entities"

    elif provider == "slack":
        return f"Connect {display_name} -- capture team conversations that mention your work streams"

    return f"Connect {display_name} to enhance your briefing"


# ---------------------------------------------------------------------------
# Priority 2: Knowledge gap nudges
# ---------------------------------------------------------------------------


async def _select_gap_nudge(
    session: AsyncSession,
    user_id: UUID,
    tenant_id: UUID,
    now: datetime.datetime,
) -> dict | None:
    """Select a knowledge gap nudge targeting streams with lowest density."""

    # Get streams with some data, ordered by density_score ASC
    stream_stmt = (
        select(WorkStream)
        .where(
            and_(
                WorkStream.tenant_id == tenant_id,
                WorkStream.archived_at.is_(None),
                WorkStream.density_score > 0,
            )
        )
        .order_by(WorkStream.density_score.asc())
        .limit(5)
    )
    stream_result = await session.execute(stream_stmt)
    streams = stream_result.scalars().all()

    if not streams:
        return None

    # Check which streams were recently nudged
    cooldown_cutoff = now - datetime.timedelta(days=GAP_NUDGE_COOLDOWN_DAYS)
    recent_stmt = select(NudgeInteraction.nudge_key).where(
        and_(
            NudgeInteraction.tenant_id == tenant_id,
            NudgeInteraction.user_id == user_id,
            NudgeInteraction.nudge_type == "knowledge_gap",
            NudgeInteraction.action == "shown",
            NudgeInteraction.created_at >= cooldown_cutoff,
        )
    )
    recent_result = await session.execute(recent_stmt)
    recently_nudged_keys = {row[0] for row in recent_result.all()}

    for stream in streams:
        nudge_key = f"gap:{stream.id}"
        if nudge_key in recently_nudged_keys:
            continue

        # Extract gap dimensions from density_details
        details = stream.density_details or {}
        gap_dimensions = details.get("gap_dimensions", [])

        if not gap_dimensions:
            # Infer gaps from dimension counts
            gap_dimensions = []
            dim_counts = details.get("dimensions", {})
            thresholds = {"entities": 3, "context": 10, "meetings": 3, "people": 2}
            for dim, threshold in thresholds.items():
                if dim_counts.get(dim, 0) < threshold:
                    gap_dimensions.append(dim)

        gap_label = gap_dimensions[0] if gap_dimensions else "context"

        # Try to find an entity linked to this stream for targeted nudge
        entity_stmt = (
            select(WorkStreamEntity.entity_id)
            .where(WorkStreamEntity.stream_id == stream.id)
            .limit(1)
        )
        entity_result = await session.execute(entity_stmt)
        first_entity_id = entity_result.scalar_one_or_none()

        nudge: dict = {
            "type": "knowledge_gap",
            "key": nudge_key,
            "stream_id": str(stream.id),
            "stream_name": stream.name,
            "title": f"Fill a gap in {stream.name}",
            "body": f"Your {stream.name} stream is missing {gap_label} context. Add a quick note to boost density.",
        }
        if first_entity_id:
            nudge["entity_id"] = str(first_entity_id)

        return nudge

    return None


# ---------------------------------------------------------------------------
# Priority 3: Context enrichment nudges
# ---------------------------------------------------------------------------


async def _select_enrichment_nudge(
    session: AsyncSession,
    user_id: UUID,
    tenant_id: UUID,
    now: datetime.datetime,
) -> dict | None:
    """Select a context enrichment nudge targeting low-mention entities."""

    # Entities linked to active streams with lowest mention_count
    entity_stmt = (
        select(ContextEntity)
        .join(
            WorkStreamEntity,
            WorkStreamEntity.entity_id == ContextEntity.id,
        )
        .join(
            WorkStream,
            and_(
                WorkStream.id == WorkStreamEntity.stream_id,
                WorkStream.archived_at.is_(None),
            ),
        )
        .where(ContextEntity.tenant_id == tenant_id)
        .order_by(ContextEntity.mention_count.asc())
        .limit(10)
    )
    entity_result = await session.execute(entity_stmt)
    entities = entity_result.scalars().all()

    if not entities:
        return None

    # Check which entities were recently nudged
    cooldown_cutoff = now - datetime.timedelta(days=ENRICHMENT_NUDGE_COOLDOWN_DAYS)
    recent_stmt = select(NudgeInteraction.nudge_key).where(
        and_(
            NudgeInteraction.tenant_id == tenant_id,
            NudgeInteraction.user_id == user_id,
            NudgeInteraction.nudge_type == "context_enrichment",
            NudgeInteraction.action == "shown",
            NudgeInteraction.created_at >= cooldown_cutoff,
        )
    )
    recent_result = await session.execute(recent_stmt)
    recently_nudged_keys = {row[0] for row in recent_result.all()}

    for entity in entities:
        nudge_key = f"enrich:{entity.id}"
        if nudge_key in recently_nudged_keys:
            continue

        return {
            "type": "context_enrichment",
            "key": nudge_key,
            "entity_id": str(entity.id),
            "entity_name": entity.name,
            "title": f"Tell us more about {entity.name}",
            "body": f"Adding context about {entity.name} helps your briefing. Type a note, or let us research for you.",
            "has_research_action": True,
        }

    return None


# ---------------------------------------------------------------------------
# Helper: record nudge interaction
# ---------------------------------------------------------------------------


async def record_nudge_action(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    nudge_type: str,
    nudge_key: str,
    action: str,
    data: dict | None = None,
) -> NudgeInteraction:
    """Record a nudge interaction (shown, dismissed, completed, skipped)."""
    interaction = NudgeInteraction(
        tenant_id=tenant_id,
        user_id=user_id,
        nudge_type=nudge_type,
        nudge_key=nudge_key,
        action=action,
        data=data or {},
    )
    session.add(interaction)
    await session.flush()
    return interaction
