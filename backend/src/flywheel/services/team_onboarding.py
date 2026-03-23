"""Team onboarding service -- stream listing and joining for new team members.

Provides functions for the invite-accept-to-first-briefing journey:
- List team's existing work streams with entity/entry/member counts
- Join streams by storing selected stream IDs in user settings
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import (
    ContextEntity,
    ContextEntityEntry,
    ContextEntry,
    User,
    WorkStream,
    WorkStreamEntity,
)

logger = logging.getLogger(__name__)


async def get_team_streams_for_join(
    session: AsyncSession, tenant_id: UUID, user_id: UUID
) -> list[dict]:
    """Query all active WorkStreams for the tenant with computed metrics.

    For each stream returns:
    - id, name, description, density_score
    - entity_count: linked WorkStreamEntity rows
    - entry_count: ContextEntry rows linked via entity matches
    - member_count: distinct user_ids who created entries in stream's entities
    - user_joined: whether current user has created entries for this stream
    """
    # Get all active (non-archived) streams for tenant
    stream_stmt = (
        select(WorkStream)
        .where(WorkStream.archived_at.is_(None))
        .order_by(WorkStream.name)
    )
    result = await session.execute(stream_stmt)
    streams = result.scalars().all()

    stream_list: list[dict] = []
    for stream in streams:
        # Count entities linked to this stream
        entity_count_stmt = select(func.count()).select_from(
            WorkStreamEntity
        ).where(WorkStreamEntity.stream_id == stream.id)
        entity_count = (await session.execute(entity_count_stmt)).scalar_one()

        # Get entity IDs for this stream
        entity_ids_stmt = select(WorkStreamEntity.entity_id).where(
            WorkStreamEntity.stream_id == stream.id
        )
        entity_ids_result = await session.execute(entity_ids_stmt)
        entity_ids = [row[0] for row in entity_ids_result.all()]

        entry_count = 0
        member_count = 0
        user_joined = False

        if entity_ids:
            # Count entries linked to stream entities via context_entity_entries
            entry_count_stmt = (
                select(func.count(distinct(ContextEntityEntry.entry_id)))
                .where(ContextEntityEntry.entity_id.in_(entity_ids))
            )
            entry_count = (await session.execute(entry_count_stmt)).scalar_one()

            # Count distinct members who created entries for these entities
            member_stmt = (
                select(func.count(distinct(ContextEntry.user_id)))
                .join(
                    ContextEntityEntry,
                    ContextEntityEntry.entry_id == ContextEntry.id,
                )
                .where(
                    ContextEntityEntry.entity_id.in_(entity_ids),
                    ContextEntry.deleted_at.is_(None),
                )
            )
            member_count = (await session.execute(member_stmt)).scalar_one()

            # Check if current user has entries
            user_entry_stmt = (
                select(func.count())
                .select_from(ContextEntry)
                .join(
                    ContextEntityEntry,
                    ContextEntityEntry.entry_id == ContextEntry.id,
                )
                .where(
                    ContextEntityEntry.entity_id.in_(entity_ids),
                    ContextEntry.user_id == user_id,
                    ContextEntry.deleted_at.is_(None),
                )
            )
            user_entry_count = (await session.execute(user_entry_stmt)).scalar_one()
            user_joined = user_entry_count > 0

        stream_list.append({
            "id": str(stream.id),
            "name": stream.name,
            "description": stream.description or "",
            "density_score": float(stream.density_score),
            "entity_count": entity_count,
            "entry_count": entry_count,
            "member_count": member_count,
            "user_joined": user_joined,
        })

    return stream_list


async def join_streams(
    session: AsyncSession, tenant_id: UUID, user_id: UUID, stream_ids: list[UUID]
) -> list[str]:
    """Join streams by storing selected stream IDs in user settings.

    Verifies each stream belongs to the tenant, then stores the
    stream IDs under User.settings["joined_streams"].

    Returns list of joined stream names.
    """
    joined_names: list[str] = []

    for stream_id in stream_ids:
        stream_stmt = select(WorkStream).where(
            WorkStream.id == stream_id,
            WorkStream.archived_at.is_(None),
        )
        result = await session.execute(stream_stmt)
        stream = result.scalar_one_or_none()

        if stream is None:
            logger.warning(
                "Stream %s not found or archived for tenant %s",
                stream_id, tenant_id,
            )
            continue

        joined_names.append(stream.name)

    # Store joined stream IDs in user settings
    user_stmt = select(User).where(User.id == user_id)
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if user is not None:
        settings = dict(user.settings or {})
        settings["joined_streams"] = [str(sid) for sid in stream_ids]
        user.settings = settings
        await session.flush()

    await session.commit()

    return joined_names
