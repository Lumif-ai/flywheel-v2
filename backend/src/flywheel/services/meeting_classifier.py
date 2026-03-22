"""Meeting classification service with three-tier confidence hierarchy.

Signal hierarchy:
1. Internal-only check (LOW) -- no external attendees -> suppress
2. Entity match (HIGH) -- attendee matches ContextEntity linked to a WorkStream
3. Domain pattern (HIGH) -- 3+ user classifications from same email domain
4. Fallback (MEDIUM) -- unknown external attendees -> show one-tap picker

Pattern learning: after 3+ user classifications from the same domain,
future meetings from that domain auto-classify to the most common stream.
"""

from __future__ import annotations

import logging
from collections import Counter
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import (
    ContextEntity,
    MeetingClassification,
    Tenant,
    WorkItem,
    WorkStream,
    WorkStreamEntity,
)

logger = logging.getLogger(__name__)

DOMAIN_LEARNING_THRESHOLD = 3


def _extract_domains(attendee_emails: list[str]) -> list[str]:
    """Extract unique email domains from attendee list."""
    domains: list[str] = []
    for email in attendee_emails:
        if "@" in email:
            domain = email.split("@", 1)[1].lower()
            if domain not in domains:
                domains.append(domain)
    return domains


async def classify_meeting(
    session: AsyncSession,
    tenant_id: UUID,
    work_item: WorkItem,
) -> dict:
    """Classify a meeting work item by confidence level.

    Returns:
        {confidence: "high"|"medium"|"low", stream_id: UUID|None,
         reason: str, source: str}
    """
    data = work_item.data or {}

    # ---------------------------------------------------------------
    # 1. Internal-only check (LOW)
    # ---------------------------------------------------------------
    if not data.get("has_external_attendees", False):
        return {
            "confidence": "low",
            "stream_id": None,
            "reason": "Internal meeting",
            "source": "suppressed",
        }

    attendee_emails = data.get("attendees", [])
    domains = _extract_domains(attendee_emails)

    # ---------------------------------------------------------------
    # 2. Entity match check (HIGH)
    # ---------------------------------------------------------------
    if attendee_emails:
        # Match attendee names/aliases against ContextEntity linked to streams
        from sqlalchemy import or_

        name_conditions = []
        for email in attendee_emails:
            local_part = email.split("@")[0] if "@" in email else email
            # Match entity name containing the email local part (first.last style)
            name_conditions.append(
                ContextEntity.name.ilike(f"%{local_part}%")
            )
            # Also try matching the full email as an alias
            name_conditions.append(
                ContextEntity.aliases.any(email)
            )

        if name_conditions:
            entity_stream_stmt = (
                select(
                    ContextEntity.name,
                    WorkStreamEntity.stream_id,
                )
                .join(
                    WorkStreamEntity,
                    WorkStreamEntity.entity_id == ContextEntity.id,
                )
                .where(
                    and_(
                        ContextEntity.tenant_id == tenant_id,
                        or_(*name_conditions),
                    )
                )
                .limit(1)
            )

            result = await session.execute(entity_stream_stmt)
            row = result.first()

            if row:
                entity_name, stream_id = row
                return {
                    "confidence": "high",
                    "stream_id": str(stream_id),
                    "reason": f"Known entity: {entity_name}",
                    "source": "auto_entity",
                }

    # ---------------------------------------------------------------
    # 3. Domain pattern check (HIGH)
    # ---------------------------------------------------------------
    if domains:
        for domain in domains:
            # Count user classifications for this domain
            count_stmt = (
                select(func.count())
                .select_from(MeetingClassification)
                .where(
                    and_(
                        MeetingClassification.tenant_id == tenant_id,
                        MeetingClassification.email_domain == domain,
                        MeetingClassification.source == "user_classified",
                    )
                )
            )
            count_result = await session.execute(count_stmt)
            classification_count = count_result.scalar_one()

            if classification_count >= DOMAIN_LEARNING_THRESHOLD:
                # Find most common stream for this domain
                stream_stmt = (
                    select(
                        MeetingClassification.stream_id,
                        func.count().label("cnt"),
                    )
                    .where(
                        and_(
                            MeetingClassification.tenant_id == tenant_id,
                            MeetingClassification.email_domain == domain,
                            MeetingClassification.source == "user_classified",
                            MeetingClassification.stream_id.isnot(None),
                        )
                    )
                    .group_by(MeetingClassification.stream_id)
                    .order_by(func.count().desc())
                    .limit(1)
                )
                stream_result = await session.execute(stream_stmt)
                stream_row = stream_result.first()

                if stream_row:
                    learned_stream_id = stream_row[0]
                    # Fetch stream name for the reason string
                    name_stmt = select(WorkStream.name).where(
                        WorkStream.id == learned_stream_id
                    )
                    name_result = await session.execute(name_stmt)
                    stream_name = name_result.scalar_one_or_none() or "Unknown"

                    return {
                        "confidence": "high",
                        "stream_id": str(learned_stream_id),
                        "reason": f"Learned pattern: {domain} -> {stream_name}",
                        "source": "auto_domain",
                    }

    # ---------------------------------------------------------------
    # 4. Fallback (MEDIUM)
    # ---------------------------------------------------------------
    domain_str = ", ".join(domains) if domains else "unknown"
    return {
        "confidence": "medium",
        "stream_id": None,
        "reason": f"Unknown external: {domain_str}",
        "source": "unknown",
    }


async def record_classification(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    work_item_id: UUID,
    stream_id: UUID,
    email_domain: str | None,
) -> None:
    """Record a user's meeting classification decision.

    Creates a MeetingClassification row with source='user_classified'.
    """
    classification = MeetingClassification(
        tenant_id=tenant_id,
        user_id=user_id,
        work_item_id=work_item_id,
        stream_id=stream_id,
        email_domain=email_domain,
        confidence="high",
        source="user_classified",
    )
    session.add(classification)
    await session.flush()


async def get_domain_rules(
    session: AsyncSession, tenant_id: UUID
) -> list[dict]:
    """Return learned domain rules (domains with 3+ classifications).

    Returns list of {domain, stream_id, stream_name, classification_count}.
    """
    stmt = (
        select(
            MeetingClassification.email_domain,
            MeetingClassification.stream_id,
            func.count().label("cnt"),
        )
        .where(
            and_(
                MeetingClassification.tenant_id == tenant_id,
                MeetingClassification.source == "user_classified",
                MeetingClassification.email_domain.isnot(None),
                MeetingClassification.stream_id.isnot(None),
            )
        )
        .group_by(
            MeetingClassification.email_domain,
            MeetingClassification.stream_id,
        )
        .having(func.count() >= DOMAIN_LEARNING_THRESHOLD)
    )

    result = await session.execute(stmt)
    rows = result.all()

    rules: list[dict] = []
    for email_domain, stream_id, count in rows:
        # Fetch stream name
        name_result = await session.execute(
            select(WorkStream.name).where(WorkStream.id == stream_id)
        )
        stream_name = name_result.scalar_one_or_none() or "Unknown"

        rules.append({
            "domain": email_domain,
            "stream_id": str(stream_id),
            "stream_name": stream_name,
            "classification_count": count,
        })

    return rules
