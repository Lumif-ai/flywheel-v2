"""Learning engine service -- evidence scoring, contradiction detection,
and proactive suggestions.

All functions receive an AsyncSession that is already tenant-scoped via RLS.
This is a read-heavy service layer; it does NOT modify storage.py.
"""

from __future__ import annotations

import difflib
import datetime
from uuid import UUID

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import (
    ContextEntry,
    SkillRun,
    SuggestionDismissal,
    WorkItem,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DECAY_THRESHOLD_DAYS = 90
STALE_THRESHOLD_DAYS = 180
CONTRADICTION_SIM_LOW = 0.2
CONTRADICTION_SIM_HIGH = 0.7


# ---------------------------------------------------------------------------
# 1. Evidence scoring (LEARN-01)
# ---------------------------------------------------------------------------


async def score_entries(
    session: AsyncSession,
    file_name: str,
    today: datetime.date | None = None,
) -> list[dict]:
    """Score context entries by composite confidence metric.

    Composite = evidence_weight * confidence_multiplier * recency_factor * diversity_multiplier

    Returns entries sorted by composite_score descending.
    """
    if today is None:
        today = datetime.date.today()

    # Subquery: source diversity per topic (lower(detail)) within the file
    diversity_sq = (
        select(
            func.lower(ContextEntry.detail).label("topic"),
            func.count(func.distinct(ContextEntry.source)).label("source_diversity"),
        )
        .where(
            and_(
                ContextEntry.file_name == file_name,
                ContextEntry.deleted_at.is_(None),
                ContextEntry.detail.isnot(None),
            )
        )
        .group_by(func.lower(ContextEntry.detail))
        .subquery()
    )

    # Main query: join entries with diversity counts
    stmt = (
        select(ContextEntry, diversity_sq.c.source_diversity)
        .outerjoin(
            diversity_sq,
            func.lower(ContextEntry.detail) == diversity_sq.c.topic,
        )
        .where(
            and_(
                ContextEntry.file_name == file_name,
                ContextEntry.deleted_at.is_(None),
            )
        )
    )

    result = await session.execute(stmt)
    rows = result.all()

    scored: list[dict] = []
    for entry, source_diversity in rows:
        source_diversity = source_diversity or 1

        # Evidence weight: capped at 20
        evidence_weight = min(entry.evidence_count, 20) / 20.0

        # Confidence multiplier
        conf_map = {"high": 1.0, "medium": 0.6, "low": 0.3}
        conf_multiplier = conf_map.get(entry.confidence, 0.6)

        # Recency decay
        days_old = (today - entry.date).days if entry.date else 999
        if days_old < DECAY_THRESHOLD_DAYS:
            recency_factor = 1.0
            staleness = "fresh"
        elif days_old <= STALE_THRESHOLD_DAYS:
            # Linear decay from 1.0 to 0.1 over 90-180 days
            recency_factor = 1.0 - 0.9 * (
                (days_old - DECAY_THRESHOLD_DAYS)
                / (STALE_THRESHOLD_DAYS - DECAY_THRESHOLD_DAYS)
            )
            staleness = "decaying"
        else:
            recency_factor = 0.1
            staleness = "stale"

        # Diversity bonus
        diversity_multiplier = 1.0 if source_diversity >= 2 else 0.7

        composite = (
            evidence_weight * conf_multiplier * recency_factor * diversity_multiplier
        )

        scored.append(
            {
                "entry_id": entry.id,
                "date": entry.date,
                "source": entry.source,
                "detail": entry.detail,
                "confidence": entry.confidence,
                "evidence_count": entry.evidence_count,
                "composite_score": round(composite, 4),
                "source_diversity": source_diversity,
                "staleness": staleness,
                "meets_high_confidence_bar": (
                    source_diversity >= 2
                    and entry.evidence_count >= 3
                    and staleness == "fresh"
                ),
            }
        )

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# 2. Contradiction detection (LEARN-02)
# ---------------------------------------------------------------------------


async def detect_contradictions(
    session: AsyncSession,
    file_name: str | None = None,
) -> list[dict]:
    """Detect potential contradictions: same topic, different content.

    Uses difflib.SequenceMatcher to compare entry content within topic groups.
    Flags pairs with similarity between 0.2 and 0.7 (same topic, different content)
    and within 90 days of each other (temporal proximity filter).
    """
    stmt = select(ContextEntry).where(
        and_(
            ContextEntry.deleted_at.is_(None),
            ContextEntry.flagged.is_(False),
            ContextEntry.detail.isnot(None),
        )
    )
    if file_name is not None:
        stmt = stmt.where(ContextEntry.file_name == file_name)

    result = await session.execute(stmt)
    entries = result.scalars().all()

    # Group by topic key: file_name::lower(detail)
    groups: dict[str, list] = {}
    for entry in entries:
        key = f"{entry.file_name}::{entry.detail.lower()}"
        groups.setdefault(key, []).append(entry)

    contradictions: list[dict] = []
    for topic_key, group_entries in groups.items():
        if len(group_entries) < 2:
            continue

        file_nm, topic = topic_key.split("::", 1)

        # Compare all pairs
        for i in range(len(group_entries)):
            for j in range(i + 1, len(group_entries)):
                a = group_entries[i]
                b = group_entries[j]

                # Temporal proximity filter: only entries within 90 days
                if a.date and b.date:
                    day_diff = abs((a.date - b.date).days)
                    if day_diff > DECAY_THRESHOLD_DAYS:
                        continue

                similarity = difflib.SequenceMatcher(
                    None, a.content, b.content
                ).ratio()

                if CONTRADICTION_SIM_LOW <= similarity <= CONTRADICTION_SIM_HIGH:
                    contradictions.append(
                        {
                            "file_name": file_nm,
                            "topic": topic,
                            "entry_a": {
                                "id": a.id,
                                "date": a.date,
                                "source": a.source,
                                "content_preview": a.content[:200],
                                "evidence_count": a.evidence_count,
                            },
                            "entry_b": {
                                "id": b.id,
                                "date": b.date,
                                "source": b.source,
                                "content_preview": b.content[:200],
                                "evidence_count": b.evidence_count,
                            },
                            "similarity": round(similarity, 4),
                        }
                    )

    return contradictions


# ---------------------------------------------------------------------------
# 3. Proactive suggestions (LEARN-04)
# ---------------------------------------------------------------------------


async def generate_suggestions(
    session: AsyncSession,
    user_id: UUID,
    limit: int = 3,
) -> list[dict]:
    """Generate proactive suggestions: meeting prep and stale context alerts.

    Checks SuggestionDismissal table to exclude recently-dismissed suggestions.
    Returns suggestions sorted by priority (meeting_prep > stale_context).
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    cutoff_48h = now + datetime.timedelta(hours=48)

    # Load active (non-expired) dismissals for this user
    dismiss_stmt = select(SuggestionDismissal).where(
        and_(
            SuggestionDismissal.user_id == user_id,
            SuggestionDismissal.expires_at > now,
        )
    )
    dismiss_result = await session.execute(dismiss_stmt)
    dismissed = {
        (d.suggestion_type, d.suggestion_key)
        for d in dismiss_result.scalars().all()
    }

    suggestions: list[dict] = []

    # --- Meeting prep suggestions ---
    meeting_stmt = select(WorkItem).where(
        and_(
            WorkItem.type == "meeting",
            WorkItem.status == "upcoming",
            WorkItem.scheduled_at.isnot(None),
            WorkItem.scheduled_at <= cutoff_48h,
            WorkItem.scheduled_at >= now,
        )
    )
    meeting_result = await session.execute(meeting_stmt)
    meetings = meeting_result.scalars().all()

    for meeting in meetings:
        suggestion_key = f"meeting:{meeting.id}"
        if ("meeting_prep", suggestion_key) in dismissed:
            continue

        # Check if meeting-prep was already run for this meeting
        prep_stmt = select(func.count()).select_from(SkillRun).where(
            and_(
                SkillRun.skill_name == "meeting-prep",
                or_(
                    SkillRun.input_text.ilike(f"%{meeting.title}%"),
                    SkillRun.input_text.ilike(f"%{meeting.external_id}%")
                    if meeting.external_id
                    else False,
                ),
            )
        )
        prep_result = await session.execute(prep_stmt)
        if prep_result.scalar_one() > 0:
            continue

        suggestions.append(
            {
                "type": "meeting_prep",
                "priority": "high",
                "key": suggestion_key,
                "title": f"Prepare for: {meeting.title}",
                "detail": (
                    f"Meeting scheduled for "
                    f"{meeting.scheduled_at.strftime('%b %d at %H:%M') if meeting.scheduled_at else 'soon'}"
                ),
                "work_item_id": str(meeting.id),
            }
        )

    # --- Stale context suggestions ---
    stale_cutoff = today - datetime.timedelta(days=DECAY_THRESHOLD_DAYS)

    stale_stmt = (
        select(
            ContextEntry.file_name,
            func.count().label("entry_count"),
            func.max(ContextEntry.date).label("newest_date"),
        )
        .where(
            and_(
                ContextEntry.deleted_at.is_(None),
                ContextEntry.date <= stale_cutoff,
                ContextEntry.evidence_count >= 3,
            )
        )
        .group_by(ContextEntry.file_name)
        .having(func.count() >= 2)
    )
    stale_result = await session.execute(stale_stmt)
    stale_groups = stale_result.all()

    for file_name, entry_count, newest_date in stale_groups:
        suggestion_key = f"stale:{file_name}"
        if ("stale_context", suggestion_key) in dismissed:
            continue

        days_stale = (today - newest_date).days if newest_date else 999

        suggestions.append(
            {
                "type": "stale_context",
                "priority": "medium",
                "key": suggestion_key,
                "title": f"Review stale context: {file_name}",
                "detail": (
                    f"{entry_count} entries, newest is {days_stale} days old"
                ),
                "file_name": file_name,
            }
        )

    # Sort by priority (meeting_prep first, then stale_context)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: priority_order.get(s["priority"], 99))

    return suggestions[:limit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def dismiss_suggestion(
    session: AsyncSession,
    user_id: UUID,
    suggestion_type: str,
    suggestion_key: str,
) -> None:
    """Dismiss a suggestion for 7 days (default expiry)."""
    # RLS ensures tenant_id is set via session context
    # We need to get tenant_id from the session context
    tenant_result = await session.execute(
        select(func.current_setting("app.tenant_id", True))
    )
    tenant_id_str = tenant_result.scalar_one_or_none()
    if not tenant_id_str:
        raise ValueError("No tenant context set on session")

    dismissal = SuggestionDismissal(
        tenant_id=UUID(tenant_id_str),
        user_id=user_id,
        suggestion_type=suggestion_type,
        suggestion_key=suggestion_key,
    )
    session.add(dismissal)
    await session.flush()


async def resolve_contradiction(
    session: AsyncSession,
    entry_id: UUID,
    resolution: str,
) -> None:
    """Mark an entry as flagged with a resolution reason."""
    stmt = select(ContextEntry).where(ContextEntry.id == entry_id)
    result = await session.execute(stmt)
    entry = result.scalar_one_or_none()
    if entry is None:
        raise ValueError(f"Entry {entry_id} not found")

    entry.flagged = True
    entry.flag_reason = resolution
    await session.flush()
