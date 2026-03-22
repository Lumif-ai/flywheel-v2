"""Work stream CRUD endpoints with density scoring and entity linking.

8 endpoints:
- GET /streams/                           -- list active streams (paginated)
- POST /streams/                          -- create stream
- GET /streams/{stream_id}                -- get stream detail with entities
- PATCH /streams/{stream_id}              -- update name/description
- POST /streams/{stream_id}/archive       -- archive stream
- POST /streams/{stream_id}/unarchive     -- unarchive stream
- POST /streams/{stream_id}/entities      -- link entity to stream
- DELETE /streams/{stream_id}/entities/{entity_id} -- unlink entity
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import (
    ContextEntity,
    ContextEntityEntry,
    ContextEntry,
    WorkStream,
    WorkStreamEntity,
)

router = APIRouter(prefix="/streams", tags=["streams"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateStreamRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class UpdateStreamRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None


class LinkEntityRequest(BaseModel):
    entity_id: UUID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stream_to_dict(s: WorkStream) -> dict:
    """Serialize a WorkStream ORM object to a JSON-friendly dict."""
    return {
        "id": str(s.id),
        "name": s.name,
        "description": s.description,
        "settings": s.settings,
        "density_score": float(s.density_score) if s.density_score is not None else 0.0,
        "density_details": s.density_details,
        "archived_at": s.archived_at.isoformat() if s.archived_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _entity_to_dict(e: ContextEntity) -> dict:
    """Serialize a ContextEntity for stream detail response."""
    return {
        "id": str(e.id),
        "name": e.name,
        "entity_type": e.entity_type,
        "mention_count": e.mention_count,
    }


def _paginated_response(items: list, total: int, offset: int, limit: int) -> dict:
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


async def _recompute_density(
    stream_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> None:
    """Recompute density score for a work stream based on linked entities.

    Score formula:
    - entity_count * 10: more entities = more coverage
    - entry_count * 2: more entries = deeper knowledge
    - meeting_count * 5: meetings are high-value signals
    - gap_count * -10: entities with < 3 entries are knowledge gaps
    - Clamped to [0, 100]
    """
    # Get all entity IDs linked to this stream
    linked_stmt = select(WorkStreamEntity.entity_id).where(
        WorkStreamEntity.stream_id == stream_id
    )
    result = await db.execute(linked_stmt)
    entity_ids = [row[0] for row in result.all()]

    entity_count = len(entity_ids)

    if entity_count == 0:
        await db.execute(
            update(WorkStream)
            .where(WorkStream.id == stream_id)
            .values(
                density_score=Decimal("0.00"),
                density_details={
                    "entity_count": 0,
                    "entry_count": 0,
                    "meeting_count": 0,
                    "gap_count": 0,
                },
            )
        )
        return

    # Count context entries per entity via context_entity_entries junction
    entry_counts_stmt = (
        select(
            ContextEntityEntry.entity_id,
            func.count(ContextEntityEntry.entry_id).label("cnt"),
        )
        .where(ContextEntityEntry.entity_id.in_(entity_ids))
        .group_by(ContextEntityEntry.entity_id)
    )
    entry_counts_result = await db.execute(entry_counts_stmt)
    entity_entry_counts = {row[0]: row[1] for row in entry_counts_result.all()}

    entry_count = sum(entity_entry_counts.values())

    # Count meeting entries: entries linked to these entities where source contains "meeting"
    if entity_ids:
        meeting_stmt = (
            select(func.count())
            .select_from(ContextEntityEntry)
            .join(ContextEntry, ContextEntry.id == ContextEntityEntry.entry_id)
            .where(
                ContextEntityEntry.entity_id.in_(entity_ids),
                ContextEntry.source.ilike("%meeting%"),
            )
        )
        meeting_result = await db.execute(meeting_stmt)
        meeting_count = meeting_result.scalar() or 0
    else:
        meeting_count = 0

    # Gap count: entities with fewer than 3 entries
    gap_count = sum(
        1 for eid in entity_ids
        if entity_entry_counts.get(eid, 0) < 3
    )

    # Compute score
    raw_score = (entity_count * 10) + (entry_count * 2) + (meeting_count * 5) - (gap_count * 10)
    score = max(0, min(100, raw_score))

    density_details = {
        "entity_count": entity_count,
        "entry_count": entry_count,
        "meeting_count": meeting_count,
        "gap_count": gap_count,
    }

    await db.execute(
        update(WorkStream)
        .where(WorkStream.id == stream_id)
        .values(
            density_score=Decimal(str(score)),
            density_details=density_details,
        )
    )


async def recompute_density_for_entities(
    entity_ids: list[UUID],
    db: AsyncSession,
) -> None:
    """Recompute density for all streams linked to the given entities.

    Called after context writes to keep density scores current.
    """
    if not entity_ids:
        return
    # Find streams linked to any of these entities
    stmt = (
        select(WorkStreamEntity.stream_id)
        .where(WorkStreamEntity.entity_id.in_(entity_ids))
        .distinct()
    )
    result = await db.execute(stmt)
    stream_ids = [row[0] for row in result.all()]
    for sid in stream_ids:
        await _recompute_density(sid, None, db)


async def _get_stream_or_404(
    stream_id: UUID, db: AsyncSession
) -> WorkStream:
    """Fetch a work stream by ID or raise 404."""
    stream = (
        await db.execute(select(WorkStream).where(WorkStream.id == stream_id))
    ).scalar_one_or_none()
    if stream is None:
        raise HTTPException(status_code=404, detail="Work stream not found")
    return stream


async def _check_name_unique(
    name: str, tenant_id: UUID, db: AsyncSession, exclude_id: UUID | None = None
) -> None:
    """Verify stream name is unique among non-archived streams in tenant."""
    stmt = select(WorkStream.id).where(
        WorkStream.tenant_id == tenant_id,
        WorkStream.name == name,
        WorkStream.archived_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(WorkStream.id != exclude_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="A work stream with this name already exists",
        )


# ---------------------------------------------------------------------------
# GET /streams/
# ---------------------------------------------------------------------------


@router.get("/")
async def list_streams(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List active (non-archived) work streams for the tenant."""
    limit = min(limit, 100)

    base = select(WorkStream).where(WorkStream.archived_at.is_(None))

    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    data_stmt = base.order_by(WorkStream.updated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(data_stmt)
    items = result.scalars().all()

    return _paginated_response(
        [_stream_to_dict(s) for s in items], total, offset, limit
    )


# ---------------------------------------------------------------------------
# POST /streams/
# ---------------------------------------------------------------------------


@router.post("/", status_code=201)
async def create_stream(
    body: CreateStreamRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new work stream."""
    await _check_name_unique(body.name, user.tenant_id, db)

    stream = WorkStream(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        name=body.name,
        description=body.description,
    )
    db.add(stream)
    await db.commit()
    await db.refresh(stream)

    return _stream_to_dict(stream)


# ---------------------------------------------------------------------------
# GET /streams/{stream_id}
# ---------------------------------------------------------------------------


@router.get("/{stream_id}")
async def get_stream(
    stream_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get stream detail with linked entities and recent entries."""
    stream = await _get_stream_or_404(stream_id, db)

    # Get linked entities
    entity_stmt = (
        select(ContextEntity)
        .join(WorkStreamEntity, WorkStreamEntity.entity_id == ContextEntity.id)
        .where(WorkStreamEntity.stream_id == stream_id)
        .order_by(ContextEntity.name)
    )
    entity_result = await db.execute(entity_stmt)
    entities = entity_result.scalars().all()

    # Get recent entries linked to stream's entities
    entity_ids = [e.id for e in entities]
    recent_entries = []
    if entity_ids:
        entries_stmt = (
            select(ContextEntry)
            .join(ContextEntityEntry, ContextEntityEntry.entry_id == ContextEntry.id)
            .where(
                ContextEntityEntry.entity_id.in_(entity_ids),
                ContextEntry.deleted_at.is_(None),
            )
            .order_by(ContextEntry.created_at.desc())
            .limit(10)
        )
        entries_result = await db.execute(entries_stmt)
        recent_entries = [
            {
                "id": str(e.id),
                "source": e.source,
                "detail": e.detail,
                "content": e.content[:200],  # Truncate for summary
                "confidence": e.confidence,
                "date": e.date.isoformat() if e.date else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries_result.scalars().all()
        ]

    result = _stream_to_dict(stream)
    result["entities"] = [_entity_to_dict(e) for e in entities]
    result["density"] = stream.density_details
    result["recent_entries"] = recent_entries

    return result


# ---------------------------------------------------------------------------
# PATCH /streams/{stream_id}
# ---------------------------------------------------------------------------


@router.patch("/{stream_id}")
async def update_stream(
    stream_id: UUID,
    body: UpdateStreamRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update stream name and/or description."""
    stream = await _get_stream_or_404(stream_id, db)

    if body.name is not None and body.name != stream.name:
        await _check_name_unique(body.name, user.tenant_id, db, exclude_id=stream_id)
        stream.name = body.name

    if body.description is not None:
        stream.description = body.description

    stream.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    await db.refresh(stream)

    return _stream_to_dict(stream)


# ---------------------------------------------------------------------------
# POST /streams/{stream_id}/archive
# ---------------------------------------------------------------------------


@router.post("/{stream_id}/archive")
async def archive_stream(
    stream_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Archive a work stream (soft delete)."""
    stream = await _get_stream_or_404(stream_id, db)
    stream.archived_at = datetime.datetime.now(datetime.timezone.utc)
    stream.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    return {"archived": True, "id": str(stream_id)}


# ---------------------------------------------------------------------------
# POST /streams/{stream_id}/unarchive
# ---------------------------------------------------------------------------


@router.post("/{stream_id}/unarchive")
async def unarchive_stream(
    stream_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Unarchive a work stream."""
    stream = await _get_stream_or_404(stream_id, db)

    # Check name uniqueness before unarchiving
    await _check_name_unique(stream.name, user.tenant_id, db, exclude_id=stream_id)

    stream.archived_at = None
    stream.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    return {"archived": False, "id": str(stream_id)}


# ---------------------------------------------------------------------------
# POST /streams/{stream_id}/entities
# ---------------------------------------------------------------------------


@router.post("/{stream_id}/entities", status_code=201)
async def link_entity(
    stream_id: UUID,
    body: LinkEntityRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Link a context entity to a work stream. Recomputes density after."""
    stream = await _get_stream_or_404(stream_id, db)

    # Verify entity exists in tenant
    entity = (
        await db.execute(
            select(ContextEntity).where(ContextEntity.id == body.entity_id)
        )
    ).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Check if already linked
    existing = (
        await db.execute(
            select(WorkStreamEntity).where(
                WorkStreamEntity.stream_id == stream_id,
                WorkStreamEntity.entity_id == body.entity_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Entity already linked to this stream")

    link = WorkStreamEntity(
        stream_id=stream_id,
        entity_id=body.entity_id,
        tenant_id=user.tenant_id,
    )
    db.add(link)

    # Recompute density
    await _recompute_density(stream_id, user.tenant_id, db)

    stream.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()

    return {"linked": True, "stream_id": str(stream_id), "entity_id": str(body.entity_id)}


# ---------------------------------------------------------------------------
# DELETE /streams/{stream_id}/entities/{entity_id}
# ---------------------------------------------------------------------------


@router.delete("/{stream_id}/entities/{entity_id}")
async def unlink_entity(
    stream_id: UUID,
    entity_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Unlink a context entity from a work stream. Recomputes density after."""
    stream = await _get_stream_or_404(stream_id, db)

    # Delete the link
    result = await db.execute(
        delete(WorkStreamEntity).where(
            WorkStreamEntity.stream_id == stream_id,
            WorkStreamEntity.entity_id == entity_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Entity not linked to this stream")

    # Recompute density
    await _recompute_density(stream_id, user.tenant_id, db)

    stream.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()

    return {"unlinked": True, "stream_id": str(stream_id), "entity_id": str(entity_id)}
