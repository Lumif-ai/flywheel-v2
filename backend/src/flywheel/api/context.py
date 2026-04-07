"""Context CRUD endpoints: file listing, entry read/write/update/delete, search, batch.

10 endpoints:
- GET /context/files              -- list context files from catalog
- GET /context/files/{name}/entries -- paginated entries with search/filter
- GET /context/files/{name}/stats -- entry count, last updated, unique sources
- POST /context/files/{name}/entries -- append new entry
- POST /context/batch             -- batch append multiple entries atomically
- PATCH /context/entries/{entry_id} -- update entry content/confidence
- DELETE /context/entries/{entry_id} -- soft-delete entry
- GET /context/search             -- cross-file full-text search
- GET /context/onboarding-cache   -- tenant-scoped onboarding cache check
- POST /context/onboarding-cache/refresh -- trigger background re-crawl
"""

from __future__ import annotations

import datetime
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Company, ContextCatalog, ContextEntry, SkillRun, Tenant
from flywheel.engines.context_store_writer import _write_entry

_ENGINE_SOURCES = frozenset({
    "email-context-engine",
    "ctx-meeting-processor",
    "mcp-manual",
})

router = APIRouter(prefix="/context", tags=["context"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


VALID_CONFIDENCE = {"high", "medium", "low"}


class AppendEntryRequest(BaseModel):
    content: str = Field(..., min_length=10, max_length=4000)
    source: str
    detail: str | None = None
    confidence: str = "medium"
    metadata: dict | None = None

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: str) -> str:
        if v not in VALID_CONFIDENCE:
            raise ValueError(f"confidence must be one of {VALID_CONFIDENCE}")
        return v


class BatchEntryItem(BaseModel):
    file_name: str
    content: str = Field(..., min_length=10, max_length=4000)
    source: str
    detail: str | None = None
    confidence: str = "medium"
    metadata: dict | None = None

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: str) -> str:
        if v not in VALID_CONFIDENCE:
            raise ValueError(f"confidence must be one of {VALID_CONFIDENCE}")
        return v


class BatchEntriesRequest(BaseModel):
    entries: list[BatchEntryItem] = Field(..., min_length=1, max_length=50)


class UpdateEntryRequest(BaseModel):
    content: str | None = Field(None, min_length=10, max_length=4000)
    confidence: str | None = None

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_CONFIDENCE:
            raise ValueError(f"confidence must be one of {VALID_CONFIDENCE}")
        return v


class OnboardingCacheGroup(BaseModel):
    category: str
    icon: str
    label: str
    items: list[str]
    count: int


class OnboardingCacheResponse(BaseModel):
    exists: bool
    entry_count: int = 0
    last_updated: str | None = None
    groups: list[OnboardingCacheGroup] = Field(default_factory=list)


class OnboardingRefreshResponse(BaseModel):
    run_id: str
    message: str


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
        "metadata": e.metadata_ or {},
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
    """Append a new context entry to a file. Auto-tags with active focus from session.

    Engine-sourced writes (source in _ENGINE_SOURCES) are routed through the
    shared _write_entry() helper for identical dedup logic across MCP and
    backend engine paths.
    """
    # Route engine-sourced writes through shared writer for dedup parity
    if body.source in _ENGINE_SOURCES:
        result = await _write_entry(
            db=db,
            tenant_id=user.tenant_id,
            user_id=user.sub,
            file_name=file_name,
            source=body.source,
            detail=body.detail or "",
            content=body.content,
            confidence=body.confidence or "medium",
            entry_date=datetime.date.today(),
        )
        await db.flush()
        await db.commit()
        return {"status": result, "file_name": file_name}

    # Non-engine sources: original direct-insert path
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
        metadata_=body.metadata or {},
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
            metadata_=item.metadata or {},
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

    # Build OR-based tsquery so multi-concept queries match entries
    # containing ANY term, ranked by overlap via ts_rank.
    raw_terms = re.split(r"\s+", q.strip())
    sanitized = [re.sub(r"[^\w]", "", t) for t in raw_terms]
    terms = [t for t in sanitized if t and len(t) > 1]

    if terms:
        ts_query = func.to_tsquery("english", " | ".join(terms))
    else:
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


# ---------------------------------------------------------------------------
# Shared helpers (used by profile.py and other modules)
# ---------------------------------------------------------------------------

_FILE_DISPLAY: dict[str, tuple[str, str]] = {
    "positioning": ("Building2", "Positioning"),
    "product-modules": ("Package", "Product Modules"),
    "icp-profiles": ("UserCheck", "Icp Profiles"),
    "competitive-intel": ("Swords", "Competitive Intel"),
    "market-taxonomy": ("TrendingUp", "Market Taxonomy"),
    "leadership": ("Users", "Leadership"),
    "company-details": ("Info", "Company Details"),
    "tech-stack": ("Cpu", "Tech Stack"),
    "value-mapping": ("Target", "Value Mapping"),
    "pain-points": ("AlertTriangle", "Pain Points"),
}


def _split_entry_items(entry) -> list[str]:
    """Split a context entry's content back into individual display items."""
    content = (getattr(entry, "content", "") or "").strip()
    if not content:
        return []
    return [line.strip() for line in content.split("\n") if line.strip()]


# ---------------------------------------------------------------------------
# GET /context/onboarding-cache — shared companies table lookup
# ---------------------------------------------------------------------------


def _normalize_domain(raw: str) -> str:
    """Normalize a URL or domain string to a bare lowercase domain."""
    import urllib.parse as _urlparse
    _parsed = _urlparse.urlparse(raw if raw.startswith("http") else f"https://{raw}")
    return (_parsed.hostname or raw).removeprefix("www.").lower()


def _build_groups_from_intel(intel: dict) -> list[OnboardingCacheGroup]:
    """Convert a companies.intel JSONB dict into CrawlItem-shaped groups."""
    groups: list[OnboardingCacheGroup] = []

    # Company overview
    overview_items: list[str] = []
    if intel.get("company_name"):
        overview_items.append(intel["company_name"])
    if intel.get("what_they_do"):
        overview_items.append(intel["what_they_do"])
    if intel.get("tagline"):
        overview_items.append(intel["tagline"])
    if intel.get("headquarters"):
        overview_items.append(f"HQ: {intel['headquarters']}")
    if intel.get("founding_year"):
        overview_items.append(f"Founded: {intel['founding_year']}")
    if intel.get("employees"):
        overview_items.append(f"Team size: {intel['employees']}")
    if overview_items:
        groups.append(OnboardingCacheGroup(
            category="company_info", icon="Building2", label="Company",
            items=overview_items, count=len(overview_items),
        ))

    # Products + differentiators + pricing
    product_items: list[str] = []
    for p in (intel.get("products") or [])[:6]:
        product_items.append(p if isinstance(p, str) else p.get("name", str(p)) if isinstance(p, dict) else str(p))
    for d in (intel.get("key_differentiators") or [])[:4]:
        product_items.append(str(d))
    if intel.get("pricing_model"):
        product_items.append(f"Pricing: {intel['pricing_model']}")
    if product_items:
        groups.append(OnboardingCacheGroup(
            category="product", icon="Package", label="Products",
            items=product_items, count=len(product_items),
        ))

    # Customers
    customer_items: list[str] = []
    for c in (intel.get("target_customers") or [])[:6]:
        customer_items.append(c if isinstance(c, str) else c.get("name", str(c)) if isinstance(c, dict) else str(c))
    if customer_items:
        groups.append(OnboardingCacheGroup(
            category="customer", icon="UserCheck", label="Customers",
            items=customer_items, count=len(customer_items),
        ))

    # Competitors
    competitor_items: list[str] = []
    for c in (intel.get("competitors") or [])[:6]:
        competitor_items.append(c if isinstance(c, str) else c.get("name", str(c)) if isinstance(c, dict) else str(c))
    if competitor_items:
        groups.append(OnboardingCacheGroup(
            category="competitive", icon="Swords", label="Competitors",
            items=competitor_items, count=len(competitor_items),
        ))

    # Market (industries + market_position)
    market_items: list[str] = []
    for i in (intel.get("industries") or [])[:6]:
        market_items.append(str(i))
    if intel.get("market_position"):
        market_items.append(str(intel["market_position"]))
    if market_items:
        groups.append(OnboardingCacheGroup(
            category="market", icon="TrendingUp", label="Market",
            items=market_items, count=len(market_items),
        ))

    # Funding
    if intel.get("funding"):
        groups.append(OnboardingCacheGroup(
            category="financial", icon="DollarSign", label="Funding",
            items=[str(intel["funding"])], count=1,
        ))

    # Key people
    people = intel.get("key_people") or []
    if people:
        people_items: list[str] = []
        for p in people[:5]:
            if isinstance(p, dict):
                people_items.append(f"{p.get('name', '?')} — {p.get('title', '?')}")
            else:
                people_items.append(str(p))
        if people_items:
            groups.append(OnboardingCacheGroup(
                category="team", icon="Users", label="Key People",
                items=people_items, count=len(people_items),
            ))

    return groups


@router.get("/onboarding-cache", response_model=OnboardingCacheResponse)
async def onboarding_cache(
    domain: str | None = Query(None),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Cache check for onboarding intel.

    Queries the shared companies table by domain — no tenant involvement.
    Returns groups shaped like CrawlItem so the frontend can consume cache
    hits identically to fresh crawl SSE events.
    """
    if not domain:
        return OnboardingCacheResponse(exists=False)

    normalized = _normalize_domain(domain)

    # Simple lookup — no tenant involvement
    result = await db.execute(
        select(Company).where(Company.domain == normalized)
    )
    company = result.scalar_one_or_none()

    if not company or not company.intel:
        return OnboardingCacheResponse(exists=False)

    groups = _build_groups_from_intel(company.intel)

    if not groups:
        return OnboardingCacheResponse(exists=False)

    return OnboardingCacheResponse(
        exists=True,
        entry_count=sum(len(g.items) for g in groups),
        last_updated=company.crawled_at.isoformat() if company.crawled_at else None,
        groups=groups,
    )


# ---------------------------------------------------------------------------
# POST /context/onboarding-cache/refresh — trigger background re-crawl
# ---------------------------------------------------------------------------


@router.post("/onboarding-cache/refresh", response_model=OnboardingRefreshResponse)
async def onboarding_cache_refresh(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Trigger a background re-crawl using the domain stored on the tenant."""
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    ).scalar_one_or_none()

    if not tenant or not tenant.domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No domain set for this tenant — run onboarding first",
        )

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name="company-intel",
        input_text=f"https://{tenant.domain}",
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await db.commit()

    return OnboardingRefreshResponse(
        run_id=str(run.id),
        message="Refresh started",
    )
