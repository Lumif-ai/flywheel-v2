"""Context CRUD endpoints: file listing, entry read/write/update/delete, search.

7 endpoints:
- GET /context/files              -- list context files from catalog
- GET /context/files/{name}/entries -- paginated entries with search/filter
- GET /context/files/{name}/stats -- entry count, last updated, unique sources
- POST /context/files/{name}/entries -- append new entry
- PATCH /context/entries/{entry_id} -- update entry content/confidence
- DELETE /context/entries/{entry_id} -- soft-delete entry
- GET /context/search             -- cross-file full-text search
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import ContextCatalog, ContextEntry

router = APIRouter(prefix="/context", tags=["context"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class AppendEntryRequest(BaseModel):
    content: str
    source: str
    detail: str | None = None
    confidence: str = "medium"


class UpdateEntryRequest(BaseModel):
    content: str | None = None
    confidence: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry_to_dict(e: ContextEntry) -> dict:
    """Serialize a ContextEntry ORM object to a JSON-friendly dict."""
    return {
        "id": str(e.id),
        "file_name": e.file_name,
        "date": e.date.isoformat() if e.date else None,
        "source": e.source,
        "detail": e.detail,
        "confidence": e.confidence,
        "evidence_count": e.evidence_count,
        "content": e.content,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def _paginated_response(items: list, total: int, offset: int, limit: int) -> dict:
    """Build a standard paginated response envelope."""
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


# ---------------------------------------------------------------------------
# GET /context/files
# ---------------------------------------------------------------------------


@router.get("/files")
async def list_context_files(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all context files for the current tenant."""
    result = await db.execute(select(ContextCatalog))
    catalogs = result.scalars().all()
    return {
        "items": [
            {
                "file_name": c.file_name,
                "description": c.description,
                "tags": c.tags,
                "status": c.status,
            }
            for c in catalogs
        ]
    }


# ---------------------------------------------------------------------------
# GET /context/files/{file_name}/entries
# ---------------------------------------------------------------------------


@router.get("/files/{file_name}/entries")
async def read_entries(
    file_name: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str | None = Query(None),
    source: str | None = Query(None),
    min_confidence: str | None = Query(None),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Read paginated context entries for a file with optional filters."""
    limit = min(limit, 100)

    base = select(ContextEntry).where(
        ContextEntry.file_name == file_name,
        ContextEntry.deleted_at.is_(None),
    )

    if source is not None:
        base = base.where(ContextEntry.source.ilike(f"%{source}%"))

    if min_confidence is not None:
        confidence_levels = {"low": 0, "medium": 1, "high": 2}
        min_level = confidence_levels.get(min_confidence.lower(), 0)
        allowed = [k for k, v in confidence_levels.items() if v >= min_level]
        base = base.where(ContextEntry.confidence.in_(allowed))

    if search is not None:
        ts_query = func.plainto_tsquery("english", search)
        base = base.where(ContextEntry.search_vector.op("@@")(ts_query))

    # Count total
    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch page
    if search is not None:
        ts_query = func.plainto_tsquery("english", search)
        data_stmt = base.order_by(
            func.ts_rank(ContextEntry.search_vector, ts_query).desc()
        )
    else:
        data_stmt = base.order_by(
            ContextEntry.date.asc(), ContextEntry.created_at.asc()
        )

    data_stmt = data_stmt.offset(offset).limit(limit)
    result = await db.execute(data_stmt)
    entries = result.scalars().all()

    return _paginated_response(
        [_entry_to_dict(e) for e in entries], total, offset, limit
    )


# ---------------------------------------------------------------------------
# GET /context/files/{file_name}/stats
# ---------------------------------------------------------------------------


@router.get("/files/{file_name}/stats")
async def file_stats(
    file_name: str,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Return stats for a context file: entry count, last updated, unique sources."""
    base = select(ContextEntry).where(
        ContextEntry.file_name == file_name,
        ContextEntry.deleted_at.is_(None),
    )

    count_result = await db.execute(
        select(func.count()).select_from(base.subquery())
    )
    entry_count = count_result.scalar() or 0

    last_updated_result = await db.execute(
        select(func.max(ContextEntry.updated_at)).where(
            ContextEntry.file_name == file_name,
            ContextEntry.deleted_at.is_(None),
        )
    )
    last_updated = last_updated_result.scalar()

    sources_result = await db.execute(
        select(func.array_agg(func.distinct(ContextEntry.source))).where(
            ContextEntry.file_name == file_name,
            ContextEntry.deleted_at.is_(None),
        )
    )
    sources = sources_result.scalar() or []

    return {
        "entry_count": entry_count,
        "last_updated": last_updated.isoformat() if last_updated else None,
        "sources": sources,
    }


# ---------------------------------------------------------------------------
# POST /context/files/{file_name}/entries
# ---------------------------------------------------------------------------


@router.post("/files/{file_name}/entries", status_code=201)
async def append_entry(
    file_name: str,
    body: AppendEntryRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Append a new context entry to a file."""
    new_entry = ContextEntry(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        file_name=file_name,
        source=body.source,
        detail=body.detail,
        confidence=body.confidence,
        content=body.content,
        date=datetime.date.today(),
    )
    db.add(new_entry)
    await db.flush()

    # Upsert catalog status to active
    catalog_stmt = pg_insert(ContextCatalog).values(
        tenant_id=user.tenant_id,
        file_name=file_name,
        status="active",
    )
    catalog_stmt = catalog_stmt.on_conflict_do_update(
        index_elements=["tenant_id", "file_name"],
        set_={"status": "active"},
    )
    await db.execute(catalog_stmt)
    await db.commit()
    await db.refresh(new_entry)

    return {"entry": _entry_to_dict(new_entry)}


# ---------------------------------------------------------------------------
# PATCH /context/entries/{entry_id}
# ---------------------------------------------------------------------------


@router.patch("/entries/{entry_id}")
async def update_entry(
    entry_id: UUID,
    body: UpdateEntryRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update an existing context entry's content and/or confidence."""
    entry = (
        await db.execute(
            select(ContextEntry).where(
                ContextEntry.id == entry_id,
                ContextEntry.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    if body.content is not None:
        entry.content = body.content
    if body.confidence is not None:
        entry.confidence = body.confidence

    await db.commit()
    await db.refresh(entry)

    return {"entry": _entry_to_dict(entry)}


# ---------------------------------------------------------------------------
# DELETE /context/entries/{entry_id}
# ---------------------------------------------------------------------------


@router.delete("/entries/{entry_id}", status_code=200)
async def delete_entry(
    entry_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Soft-delete a context entry."""
    entry = (
        await db.execute(
            select(ContextEntry).where(
                ContextEntry.id == entry_id,
                ContextEntry.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    entry.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()

    return {"deleted": True, "id": str(entry_id)}


# ---------------------------------------------------------------------------
# GET /context/search
# ---------------------------------------------------------------------------


@router.get("/search")
async def search_entries(
    q: str = Query(..., min_length=1),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Cross-file full-text search across all context entries in the tenant."""
    limit = min(limit, 100)
    ts_query = func.plainto_tsquery("english", q)

    base = select(ContextEntry).where(
        ContextEntry.deleted_at.is_(None),
        ContextEntry.search_vector.op("@@")(ts_query),
    )

    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    data_stmt = (
        base.order_by(func.ts_rank(ContextEntry.search_vector, ts_query).desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(data_stmt)
    entries = result.scalars().all()

    return _paginated_response(
        [_entry_to_dict(e) for e in entries], total, offset, limit
    )
