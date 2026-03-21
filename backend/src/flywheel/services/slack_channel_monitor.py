"""Slack channel keyword monitoring for competitive intelligence.

Ported from v1's watcher_slack_channels.py to async multi-tenant v2 architecture.
Receives real-time message events via Slack Events API (not polling).

Handles:
- Keyword matching (case-insensitive substring, configurable per-tenant)
- Daily cap enforcement per-tenant (default 50)
- Intelligence extraction and structuring
- Storage as tenant-scoped context entries

Public API:
    DEFAULT_KEYWORDS: list[str]
    process_channel_message(event, db) -> None
    check_daily_cap(db, tenant_id) -> bool
    extract_intelligence(text, keywords) -> dict
    matches_keywords(text, keywords) -> list[str]
"""

from __future__ import annotations

import datetime
import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import ContextEntry, Integration

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default keywords (ported from v1 watcher_slack_channels.py)
# ---------------------------------------------------------------------------

DEFAULT_KEYWORDS: list[str] = [
    "competitor",
    "alternative to",
    "switching from",
    "better than",
    "compared to",
    "versus",
    "replaced",
    "moving to",
    "tried",
]

# Default daily cap per-tenant (overridable via Integration settings)
DEFAULT_DAILY_CAP = 50

# Maximum content length stored per intelligence entry
MAX_CONTENT_LENGTH = 2000


# ---------------------------------------------------------------------------
# Keyword matching
# ---------------------------------------------------------------------------


def matches_keywords(text: str, keywords: list[str]) -> list[str]:
    """Case-insensitive substring matching against keyword list.

    Ported from v1's _matches_keywords but returns the matched keywords
    instead of a boolean, for richer intelligence extraction.

    Args:
        text: Message text to search.
        keywords: List of keyword strings to match.

    Returns:
        List of keywords that matched (may be empty).
    """
    if not text:
        return []

    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


# ---------------------------------------------------------------------------
# Intelligence extraction
# ---------------------------------------------------------------------------


def extract_intelligence(text: str, keywords: list[str]) -> dict:
    """Structure a raw Slack message into a competitive intelligence entry.

    This is a lightweight extraction (no LLM call). The full enrichment
    happens downstream when the context entry is processed by the
    learning engine.

    Args:
        text: The Slack message text.
        keywords: List of keywords that triggered this extraction.

    Returns:
        Dict with structured intelligence fields.
    """
    return {
        "matched_keywords": keywords,
        "content": text[:MAX_CONTENT_LENGTH],
        "source": "slack-channel-monitor",
        "confidence": "medium",  # channel chatter, not verified
    }


# ---------------------------------------------------------------------------
# Daily cap enforcement
# ---------------------------------------------------------------------------


async def check_daily_cap(db: AsyncSession, tenant_id: UUID) -> bool:
    """Check if a tenant is under their daily Slack monitoring cap.

    Counts today's context entries with source='slack-channel-monitor'
    for the given tenant. Compares against the daily_cap from Integration
    settings (default 50).

    Args:
        db: Async database session.
        tenant_id: Tenant UUID.

    Returns:
        True if under cap (more captures allowed), False if cap exceeded.
    """
    today = datetime.date.today()

    # Count today's Slack-sourced entries
    result = await db.execute(
        select(func.count(ContextEntry.id)).where(
            ContextEntry.tenant_id == tenant_id,
            ContextEntry.source == "slack-channel-monitor",
            ContextEntry.date == today,
        )
    )
    count = result.scalar() or 0

    # Look up per-tenant cap from Integration settings
    cap = DEFAULT_DAILY_CAP
    int_result = await db.execute(
        select(Integration).where(
            Integration.provider == "slack",
            Integration.status == "connected",
            Integration.tenant_id == tenant_id,
        )
    )
    integration = int_result.scalar_one_or_none()
    if integration and integration.settings:
        cap = integration.settings.get("daily_cap", DEFAULT_DAILY_CAP)

    if count >= cap:
        logger.info(
            "Daily cap reached for tenant %s (%d/%d)",
            tenant_id, count, cap,
        )
        return False

    return True


# ---------------------------------------------------------------------------
# Channel message processor (main entry point)
# ---------------------------------------------------------------------------


async def process_channel_message(event: dict, db: AsyncSession) -> None:
    """Process an incoming Slack channel message for competitive intelligence.

    Called by slack_events.process_slack_event for message-type events.
    Applies filtering gates in order:
    1. Resolve tenant from team_id
    2. Check if channel is in monitored channels list
    3. Match text against keywords
    4. Enforce daily cap
    5. Extract and store intelligence

    Args:
        event: Slack message event dict with keys:
            team_id (from parent payload), channel, text, user, ts.
        db: Async database session.
    """
    team_id = event.get("team_id", "")
    channel = event.get("channel", "")
    text = event.get("text", "")

    if not text or not team_id:
        return

    # Gate 1: Resolve tenant from team_id
    result = await db.execute(
        select(Integration).where(
            Integration.provider == "slack",
            Integration.status == "connected",
        )
    )
    integrations = result.scalars().all()

    integration = None
    for intg in integrations:
        if intg.settings and intg.settings.get("team_id") == team_id:
            integration = intg
            break

    if integration is None:
        logger.debug("No Slack integration found for team %s", team_id)
        return

    tenant_id = integration.tenant_id
    settings = integration.settings or {}

    # Gate 2: Channel must be in monitored channels list
    monitored_channels = settings.get("monitored_channels", [])
    if monitored_channels and channel not in monitored_channels:
        return

    # Gate 3: Text must match keywords
    keywords = settings.get("keywords", DEFAULT_KEYWORDS)
    matched = matches_keywords(text, keywords)
    if not matched:
        return

    # Gate 4: Daily cap not exceeded
    under_cap = await check_daily_cap(db, tenant_id)
    if not under_cap:
        return

    # All gates passed -- extract intelligence and store
    intel = extract_intelligence(text, matched)

    logger.info(
        "Slack intel captured: tenant=%s channel=%s keywords=%s",
        tenant_id, channel, matched,
    )

    # Store as a context entry
    entry = ContextEntry(
        tenant_id=tenant_id,
        user_id=integration.user_id,
        file_name="competitive-intel.md",
        source="slack-channel-monitor",
        detail=f"Slack #{channel} | keywords: {', '.join(matched)}",
        confidence="medium",
        content=intel["content"],
    )
    db.add(entry)
    await db.commit()
