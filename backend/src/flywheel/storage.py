"""Async Postgres storage layer implementing the 4-function context API.

All functions are async and expect an AsyncSession with tenant context
already configured via db.session.get_tenant_session().

API surface matches v1 context_utils.py:
- read_context(session, file) -> str
- append_entry(session, file, entry, source) -> str
- query_context(session, file, **filters) -> list[dict]
- batch_context(session, source) -> AsyncContextManager[BatchOperation]

Plus enrichment cache:
- get_cached_enrichment(session, tenant_id, query_text) -> dict | None
- set_cached_enrichment(session, tenant_id, query_text, results) -> None
"""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any
from collections.abc import AsyncGenerator

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import (
    ContextCatalog,
    ContextEntry,
    ContextEvent,
    EnrichmentCache,
)

# Confidence hierarchy for min_confidence filtering
_CONFIDENCE_LEVELS = {"low": 0, "medium": 1, "high": 2}


def _format_entry(entry: ContextEntry) -> str:
    """Format a ContextEntry row to match v1 output format.

    Format: [YYYY-MM-DD | source: {source} | {detail}] confidence: {confidence} | evidence: {evidence_count}
    - content line 1
    - content line 2
    """
    date_str = entry.date.isoformat() if isinstance(entry.date, date) else str(entry.date)
    detail_part = f" | {entry.detail}" if entry.detail else ""
    header = (
        f"[{date_str} | source: {entry.source}{detail_part}] "
        f"confidence: {entry.confidence} | evidence: {entry.evidence_count}"
    )
    # Content is stored as a single string; each line should be prefixed with "- "
    content_lines = entry.content.strip().split("\n")
    formatted_lines = []
    for line in content_lines:
        stripped = line.strip()
        if stripped:
            # If line already starts with "- ", keep it; otherwise add prefix
            if stripped.startswith("- "):
                formatted_lines.append(stripped)
            else:
                formatted_lines.append(f"- {stripped}")
    body = "\n".join(formatted_lines)
    return f"{header}\n{body}"


async def read_context(session: AsyncSession, file: str) -> str:
    """Read all context entries for a file, formatted as v1 output.

    RLS automatically filters by tenant_id and excludes deleted/private-not-owned.
    Returns empty string if no entries.
    """
    stmt = (
        select(ContextEntry)
        .where(ContextEntry.file_name == file)
        .where(ContextEntry.deleted_at.is_(None))
        .order_by(ContextEntry.date.asc(), ContextEntry.created_at.asc())
    )
    result = await session.execute(stmt)
    entries = result.scalars().all()

    if not entries:
        return ""

    return "\n\n".join(_format_entry(e) for e in entries)


async def append_entry(
    session: AsyncSession,
    file: str,
    entry: dict[str, Any],
    source: str,
    focus_id: str | None = None,
) -> str:
    """Append a context entry, with evidence deduplication.

    Args:
        session: Tenant-scoped AsyncSession
        file: Context file name (e.g., "company-intel")
        entry: Dict with keys: detail, confidence (optional), content (str or list)
        source: Source identifier (e.g., "skill-name")
        focus_id: Optional focus UUID string. If not provided, reads from session config.

    Returns:
        Formatted entry string matching v1 output format.
    """
    detail = entry.get("detail")
    confidence = entry.get("confidence", "medium")
    metadata = entry.get("metadata") or {}
    content_raw = entry.get("content", "")
    if isinstance(content_raw, list):
        content = "\n".join(content_raw)
    else:
        content = str(content_raw)

    # Normalize detail for dedup comparison
    normalized_detail = (detail or "").strip().lower()

    # Get tenant_id and user_id from session config
    tid_result = await session.execute(text("SELECT current_setting('app.tenant_id', true)"))
    tenant_id = tid_result.scalar()
    uid_result = await session.execute(text("SELECT current_setting('app.user_id', true)"))
    user_id = uid_result.scalar()

    # Resolve focus_id: explicit param > session config > None
    if not focus_id:
        fid_result = await session.execute(text("SELECT current_setting('app.focus_id', true)"))
        fid_value = fid_result.scalar()
        focus_id = fid_value if fid_value else None

    # Evidence dedup: check for existing entry with same tenant+file+source+detail
    # Explicit tenant_id filter required because superuser roles bypass RLS
    dedup_filters = [
        ContextEntry.file_name == file,
        ContextEntry.source == source,
        ContextEntry.deleted_at.is_(None),
        func.lower(func.coalesce(ContextEntry.detail, "")) == normalized_detail,
    ]
    if tenant_id:
        from uuid import UUID as _UUID
        dedup_filters.append(ContextEntry.tenant_id == _UUID(tenant_id))
    dedup_stmt = (
        select(ContextEntry)
        .where(*dedup_filters)
        .with_for_update()
    )
    dedup_result = await session.execute(dedup_stmt)
    existing = dedup_result.scalar_one_or_none()

    event_type: str

    if existing is not None:
        # Increment evidence count and update content if different
        existing.evidence_count += 1
        if existing.content.strip() != content.strip():
            existing.content = content
        if metadata:
            existing.metadata_ = {**(existing.metadata_ or {}), **metadata}
        await session.flush()
        result_entry = existing
        event_type = "evidence_incremented"
    else:
        # Insert new entry
        new_entry = ContextEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            file_name=file,
            source=source,
            detail=detail,
            confidence=confidence,
            content=content,
            metadata_=metadata,
            date=date.today(),
            focus_id=focus_id,
        )
        session.add(new_entry)
        await session.flush()
        result_entry = new_entry
        event_type = "entry_added"

    # Upsert context_catalog: set status='active' if was 'empty'
    catalog_stmt = pg_insert(ContextCatalog).values(
        tenant_id=tenant_id,
        file_name=file,
        status="active",
    )
    catalog_stmt = catalog_stmt.on_conflict_do_update(
        index_elements=["tenant_id", "file_name"],
        set_={"status": "active"},
    )
    await session.execute(catalog_stmt)

    # Log event
    event = ContextEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=event_type,
        file_name=file,
        entry_id=result_entry.id,
        detail=detail,
    )
    session.add(event)
    await session.flush()

    # Graph extraction: extract entities from the new/updated entry (non-blocking)
    try:
        from flywheel.services.entity_extraction import process_entry_for_graph
        await process_entry_for_graph(session, result_entry, tenant_id)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Graph extraction failed for entry %s", result_entry.id, exc_info=True
        )

    return _format_entry(result_entry)


async def query_context(
    session: AsyncSession,
    file: str,
    *,
    since: str | date | None = None,
    source: str | None = None,
    keyword: str | None = None,
    search: str | None = None,
    min_confidence: str | None = None,
) -> list[dict[str, Any]]:
    """Query context entries with filters.

    Args:
        session: Tenant-scoped AsyncSession
        file: Context file name
        since: Filter entries on or after this date (str or date)
        source: Partial case-insensitive source match
        keyword: Partial case-insensitive content match
        search: Full-text search using tsvector
        min_confidence: Minimum confidence level (low/medium/high)

    Returns:
        List of dicts with entry data.
    """
    stmt = (
        select(ContextEntry)
        .where(ContextEntry.file_name == file)
        .where(ContextEntry.deleted_at.is_(None))
    )

    if since is not None:
        if isinstance(since, str):
            since_date = date.fromisoformat(since)
        else:
            since_date = since
        stmt = stmt.where(ContextEntry.date >= since_date)

    if source is not None:
        stmt = stmt.where(ContextEntry.source.ilike(f"%{source}%"))

    if keyword is not None:
        stmt = stmt.where(ContextEntry.content.ilike(f"%{keyword}%"))

    if min_confidence is not None:
        min_level = _CONFIDENCE_LEVELS.get(min_confidence.lower(), 0)
        allowed = [k for k, v in _CONFIDENCE_LEVELS.items() if v >= min_level]
        stmt = stmt.where(ContextEntry.confidence.in_(allowed))

    if search is not None:
        ts_query = func.plainto_tsquery("english", search)
        stmt = stmt.where(ContextEntry.search_vector.op("@@")(ts_query))
        stmt = stmt.order_by(func.ts_rank(ContextEntry.search_vector, ts_query).desc())
    else:
        stmt = stmt.order_by(ContextEntry.date.asc(), ContextEntry.created_at.asc())

    result = await session.execute(stmt)
    entries = result.scalars().all()

    return [
        {
            "id": str(entry.id),
            "date": entry.date.isoformat() if isinstance(entry.date, date) else str(entry.date),
            "source": entry.source,
            "detail": entry.detail,
            "confidence": entry.confidence,
            "evidence_count": entry.evidence_count,
            "content": entry.content,
            "visibility": entry.visibility,
            "focus_id": str(entry.focus_id) if entry.focus_id else None,
        }
        for entry in entries
    ]


class BatchOperation:
    """Queues context writes for atomic execution within a single transaction."""

    def __init__(self, session: AsyncSession, source: str) -> None:
        self._session = session
        self._source = source
        self._queue: list[tuple[str, dict[str, Any]]] = []

    def append_entry(self, file: str, entry: dict[str, Any]) -> None:
        """Queue a write for later execution."""
        self._queue.append((file, entry))

    async def _execute(self) -> None:
        """Execute all queued writes in the current transaction."""
        for file, entry in self._queue:
            await append_entry(self._session, file, entry, self._source)


@asynccontextmanager
async def batch_context(
    session: AsyncSession,
    source: str,
) -> AsyncGenerator[BatchOperation, None]:
    """Async context manager for atomic batch writes.

    All queued writes execute in the same session transaction.
    On exception, the session rolls back naturally (SQLAlchemy behavior).
    """
    batch = BatchOperation(session, source)
    yield batch
    # Execute all queued writes on successful exit
    await batch._execute()


async def get_cached_enrichment(
    session: AsyncSession,
    tenant_id: str,
    query_text: str,
) -> dict[str, Any] | None:
    """Retrieve cached enrichment results within 24h TTL.

    Args:
        session: AsyncSession (can be admin or tenant-scoped)
        tenant_id: Tenant UUID string
        query_text: The query text to look up

    Returns:
        Cached results dict, or None if not found / expired.
    """
    query_hash = hashlib.sha256(query_text.strip().lower().encode()).hexdigest()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    stmt = (
        select(EnrichmentCache)
        .where(
            EnrichmentCache.tenant_id == tenant_id,
            EnrichmentCache.query_hash == query_hash,
            EnrichmentCache.created_at > cutoff,
        )
    )
    result = await session.execute(stmt)
    cached = result.scalar_one_or_none()

    if cached is None:
        return None

    return cached.results


async def set_cached_enrichment(
    session: AsyncSession,
    tenant_id: str,
    query_text: str,
    results: dict[str, Any],
) -> None:
    """Store enrichment results with SHA256 dedup and 24h TTL.

    Uses upsert: if same tenant+hash exists, update results and reset created_at.
    """
    normalized = query_text.strip().lower()
    query_hash = hashlib.sha256(normalized.encode()).hexdigest()

    stmt = pg_insert(EnrichmentCache).values(
        tenant_id=tenant_id,
        query_hash=query_hash,
        query_text=normalized,
        results=results,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_enrichment_tenant_hash",
        set_={
            "results": results,
            "query_text": normalized,
            "created_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.flush()


async def list_context_files(session: AsyncSession) -> list[str]:
    """List distinct context file names for the current tenant.

    RLS automatically filters by tenant_id.

    Returns:
        List of file name strings.
    """
    stmt = (
        select(ContextEntry.file_name)
        .where(ContextEntry.deleted_at.is_(None))
        .distinct()
        .order_by(ContextEntry.file_name)
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def log_event(
    session: AsyncSession,
    event_type: str,
    file_name: str,
    agent_id: str,
    detail: str = "",
) -> None:
    """Log an event to the context_events table.

    Args:
        session: Tenant-scoped AsyncSession.
        event_type: Type of event (e.g., 'entry_added', 'contract_violation').
        file_name: Context file associated with the event.
        agent_id: Agent or user that triggered the event.
        detail: Optional detail string.
    """
    tid_result = await session.execute(text("SELECT current_setting('app.tenant_id', true)"))
    tenant_id = tid_result.scalar()
    uid_result = await session.execute(text("SELECT current_setting('app.user_id', true)"))
    user_id = uid_result.scalar()

    event = ContextEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=event_type,
        file_name=file_name,
        detail=detail,
    )
    session.add(event)
    await session.flush()


async def backfill_graph_for_entries(
    session: AsyncSession,
    tenant_id: str,
    batch_size: int = 100,
) -> dict:
    """Backfill graph data for all existing context entries in a tenant.

    Processes entries in batches. Returns stats dict with counts.

    Args:
        session: Tenant-scoped AsyncSession.
        tenant_id: Tenant UUID string.
        batch_size: Not currently used for chunking but reserved for future use.

    Returns:
        Dict with processed, errors, and total counts.
    """
    import logging

    from flywheel.services.entity_extraction import process_entry_for_graph

    stmt = (
        select(ContextEntry)
        .where(ContextEntry.deleted_at.is_(None))
        .order_by(ContextEntry.created_at.asc())
    )
    result = await session.execute(stmt)
    entries = result.scalars().all()

    processed = 0
    errors = 0
    for entry in entries:
        try:
            await process_entry_for_graph(session, entry, tenant_id)
            processed += 1
        except Exception:
            errors += 1
            logging.getLogger(__name__).warning(
                "Backfill failed for entry %s", entry.id, exc_info=True
            )

    return {"processed": processed, "errors": errors, "total": len(entries)}
