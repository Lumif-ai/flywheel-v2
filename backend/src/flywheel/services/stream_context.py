"""Work stream context loader for chat orchestration.

Resolves a stream_id to contextual information that helps the orchestrator
make better routing decisions. For example, if the user is in a "Q2 Pipeline"
stream, the orchestrator knows to bias toward sales-related skills.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import ContextEntity, WorkStream, WorkStreamEntity


async def load_stream_context(
    stream_id: str,
    tenant_id: UUID,
    db: AsyncSession,
) -> str | None:
    """Load work stream context for the orchestrator.

    Queries the work_streams table and joins through work_stream_entities to
    build a context string describing the stream and its linked entities.

    Args:
        stream_id: The work stream identifier (UUID string) from the frontend.
        tenant_id: The tenant UUID for data isolation.
        db: Async database session (tenant-scoped).

    Returns:
        A context string describing the work stream, or None if not found.
    """
    try:
        sid = UUID(stream_id)
    except (ValueError, AttributeError):
        return None

    # Fetch the work stream
    result = await db.execute(
        select(WorkStream).where(
            WorkStream.id == sid,
            WorkStream.tenant_id == tenant_id,
            WorkStream.archived_at.is_(None),
        )
    )
    stream = result.scalar_one_or_none()
    if stream is None:
        return None

    # Fetch linked entities
    entity_result = await db.execute(
        select(ContextEntity)
        .join(WorkStreamEntity, WorkStreamEntity.entity_id == ContextEntity.id)
        .where(WorkStreamEntity.stream_id == sid)
        .order_by(ContextEntity.name)
    )
    entities = entity_result.scalars().all()

    # Build context string
    parts = [f"Work stream: {stream.name}."]

    if stream.description:
        parts.append(f"Description: {stream.description}.")

    if entities:
        entity_strs = [f"{e.name} ({e.entity_type})" for e in entities]
        parts.append(f"Key entities: {', '.join(entity_strs)}.")

    return " ".join(parts)
