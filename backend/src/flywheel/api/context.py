"""Context CRUD endpoints: file listing, entry read/write/update/delete, search, batch.

8 endpoints:
- GET /context/files              -- list context files from catalog
- GET /context/files/{name}/entries -- paginated entries with search/filter
- GET /context/files/{name}/stats -- entry count, last updated, unique sources
- POST /context/files/{name}/entries -- append new entry
- POST /context/batch             -- batch append multiple entries atomically
- PATCH /context/entries/{entry_id} -- update entry content/confidence
- DELETE /context/entries/{entry_id} -- soft-delete entry
- GET /context/search             -- cross-file full-text search
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
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


class BatchEntryItem(BaseModel):
    file_name: str
    content: str
    source: str
    detail: str | None = None
    confidence: str = "medium"


class BatchEntriesRequest(BaseModel):
    entries: list[BatchEntryItem] = Field(..., min_length=1, max_length=50)


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
        "focus_id": str(e.focus_id) if e.focus_id else None,
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
    focus_id: str | None = Query(None),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Read paginated context entries for a file with optional filters."""
    limit = min(limit, 100)

    base = select(ContextEntry).where(
        ContextEntry.file_name == file_name,
        ContextEntry.deleted_at.is_(None),
    )

    # Explicit focus filter (user requests entries from one focus only)
    if focus_id is not None:
        from uuid import UUID as _UUID
        base = base.where(ContextEntry.focus_id == _UUID(focus_id))

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
    """Append a new context entry to a file. Auto-tags with active focus from session."""
    # Read focus_id from session config (set by X-Focus-Id header via deps.py)
    fid_result = await db.execute(text("SELECT current_setting('app.focus_id', true)"))
    fid_value = fid_result.scalar()
    focus_id = fid_value if fid_value else None

    new_entry = ContextEntry(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        file_name=file_name,
        source=body.source,
        detail=body.detail,
        confidence=body.confidence,
        content=body.content,
        date=datetime.date.today(),
        focus_id=focus_id,
    )
    db.add(new_entry)
    await db.flush()

    # Graph extraction: extract entities from the new entry (non-blocking)
    extracted_entity_ids: list = []
    try:
        from flywheel.services.entity_extraction import process_entry_for_graph
        extracted_entity_ids = await process_entry_for_graph(db, new_entry, str(user.tenant_id)) or []
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Graph extraction failed for entry %s", new_entry.id, exc_info=True
        )

    # Recompute density for streams linked to extracted entities
    if extracted_entity_ids:
        try:
            from flywheel.api.streams import recompute_density_for_entities
            await recompute_density_for_entities(extracted_entity_ids, db)
        except Exception:
            pass  # Non-blocking: density will catch up on next entity link

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
# POST /context/batch
# ---------------------------------------------------------------------------


@router.post("/batch", status_code=201)
async def batch_entries(
    body: BatchEntriesRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Append multiple context entries atomically. Auto-tags with active focus."""
    today = datetime.date.today()

    # Read focus_id from session config (set by X-Focus-Id header via deps.py)
    fid_result = await db.execute(text("SELECT current_setting('app.focus_id', true)"))
    fid_value = fid_result.scalar()
    focus_id = fid_value if fid_value else None

    # Create all entry objects
    new_entries = []
    for item in body.entries:
        entry = ContextEntry(
            tenant_id=user.tenant_id,
            user_id=user.sub,
            file_name=item.file_name,
            source=item.source,
            detail=item.detail,
            confidence=item.confidence,
            content=item.content,
            date=today,
            focus_id=focus_id,
        )
        new_entries.append(entry)

    db.add_all(new_entries)
    await db.flush()

    # Graph extraction: extract entities from each new entry (non-blocking)
    all_entity_ids: list = []
    for entry in new_entries:
        try:
            from flywheel.services.entity_extraction import process_entry_for_graph
            eids = await process_entry_for_graph(db, entry, str(user.tenant_id)) or []
            all_entity_ids.extend(eids)
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Graph extraction failed for entry %s", entry.id, exc_info=True
            )

    # Recompute density for streams linked to extracted entities
    if all_entity_ids:
        try:
            from flywheel.api.streams import recompute_density_for_entities
            unique_eids = list(set(all_entity_ids))
            await recompute_density_for_entities(unique_eids, db)
        except Exception:
            pass  # Non-blocking: density will catch up on next entity link

    # Upsert catalog status for each unique file_name
    unique_files = {item.file_name for item in body.entries}
    for file_name in unique_files:
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

    # Refresh all entries to get DB-generated fields
    for entry in new_entries:
        await db.refresh(entry)

    return {
        "entries": [_entry_to_dict(e) for e in new_entries],
        "count": len(new_entries),
    }


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
    """Cross-file full-text search across all context entries in the tenant.

    When the user has an active focus, results are re-sorted within each page
    using focus_weight as a secondary factor (ts_rank remains primary).
    V1 limitation: reranking is per-page, not global.
    """
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

    # Focus-aware secondary re-sort within the current page
    active_focus_id_str = None
    try:
        focus_result = await db.execute(
            text("SELECT current_setting('app.focus_id', true)")
        )
        active_focus_id_str = focus_result.scalar()
    except Exception:
        pass

    if active_focus_id_str:
        from uuid import UUID as _UUID
        try:
            active_fid = _UUID(active_focus_id_str)

            def _focus_weight(entry: ContextEntry) -> float:
                if entry.focus_id == active_fid:
                    return 1.0
                if entry.focus_id is None:
                    return 0.8
                return 0.5

            # Stable sort by focus_weight descending preserves ts_rank within groups
            entries = sorted(entries, key=_focus_weight, reverse=True)
        except (ValueError, AttributeError):
            pass  # Invalid UUID in setting, skip reranking

    return _paginated_response(
        [_entry_to_dict(e) for e in entries], total, offset, limit
    )
