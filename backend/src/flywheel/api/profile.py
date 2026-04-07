"""Company Profile API endpoints.

Endpoints:
- GET  /profile              -- Return tenant company intelligence grouped by category
- PATCH /profile/category/{entry_id} -- Update a category entry's full content
- POST /profile/category     -- Add a new category entry
- POST /profile/upload       -- Link an uploaded file to the company profile
- POST /profile/analyze-document -- Route document analysis through the SkillRun engine
- POST /profile/refresh      -- Re-run company intelligence with all available sources
- POST /profile/reset        -- Soft-delete all intel entries then re-run from scratch
"""

from __future__ import annotations

import datetime
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.context import _FILE_DISPLAY, _split_entry_items
from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import ContextCatalog, ContextEntry, SkillRun, Tenant, UploadedFile

router = APIRouter(prefix="/profile", tags=["profile"])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ProfileGroup(BaseModel):
    category: str
    icon: str
    label: str
    items: list[str]
    entry_id: str
    raw_content: str
    count: int


class ProductTab(BaseModel):
    slug: str
    name: str
    icon: str
    sections: list[ProfileGroup]


class CompanyProfileResponse(BaseModel):
    company_name: str | None
    domain: str | None
    groups: list[ProfileGroup]
    product_tabs: list[ProductTab] = []
    total_items: int
    last_updated: str | None
    uploaded_files: list[dict]
    enrichment_status: str | None = None


class UpdateCategoryRequest(BaseModel):
    content: str


class CreateCategoryRequest(BaseModel):
    file_name: str
    content: str
    detail: str | None = None


class LinkFileRequest(BaseModel):
    file_id: str


class AnalyzeDocumentRequest(BaseModel):
    file_id: str


# ---------------------------------------------------------------------------
# GET /profile
# ---------------------------------------------------------------------------


@router.get("", response_model=CompanyProfileResponse)
async def get_company_profile(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> CompanyProfileResponse:
    """Return the tenant's company intelligence grouped by category.

    Sections are ordered for a logical company profile flow:
    About → Products (per-product) → Value Prop → Target Market → Market → Pain Points → Competitive.
    Product modules use `product:*` file_name convention for per-product sections.
    Items within each section are capped at MAX_DISPLAY_ITEMS with full count returned.
    """
    from sqlalchemy import or_

    # Section ordering and display config
    # (file_name_or_prefix, icon, label, max_items)
    SECTION_ORDER = [
        ("positioning", "Building2", "About", 8),
        ("product:", None, None, 0),  # placeholder — expanded dynamically per product
        ("value-mapping", "Target", "Value Proposition", 8),
        ("icp-profiles", "UserCheck", "Target Customers", 8),
        ("market-taxonomy", "TrendingUp", "Market", 0),  # 0 = show all
        ("pain-points", "AlertTriangle", "Pain Points We Solve", 8),
        ("competitive-intel", "Swords", "Competitive Landscape", 5),
    ]

    # Fetch all profile-relevant entries (static files + product:* prefix)
    STATIC_FILES = {
        "positioning", "icp-profiles", "competitive-intel",
        "market-taxonomy", "leadership", "company-details", "tech-stack",
        "value-mapping", "pain-points",
    }

    entries_result = await db.execute(
        select(ContextEntry).where(
            ContextEntry.deleted_at.is_(None),
            ContextEntry.source == "company-intel-onboarding",
            or_(
                ContextEntry.file_name.in_(STATIC_FILES),
                ContextEntry.file_name.like("product:%"),
            ),
        )
    )
    entries = entries_result.scalars().all()

    # Fetch tenant for company name and domain
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    # Fetch linked files — tenant-scoped, deduped by filename
    files_result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.tenant_id == user.tenant_id)
        .order_by(UploadedFile.created_at.desc())
    )
    all_files = files_result.scalars().all()
    seen_filenames: set[str] = set()
    uploaded_files = []
    for f in all_files:
        if (f.metadata_ or {}).get("profile_linked") is True and f.filename not in seen_filenames:
            seen_filenames.add(f.filename)
            uploaded_files.append({
                "id": str(f.id),
                "filename": f.filename,
                "mimetype": f.mimetype,
                "size_bytes": f.size_bytes,
            })

    # Group entries by file_name
    grouped: dict[str, list] = {}
    for entry in entries:
        grouped.setdefault(entry.file_name, []).append(entry)

    # Build groups in section order
    groups: list[ProfileGroup] = []
    total_items = 0
    last_updated_dt: datetime.datetime | None = None
    seen_files: set[str] = set()

    def _build_group(file_name: str, icon: str, label: str, max_items: int) -> ProfileGroup | None:
        nonlocal total_items, last_updated_dt
        file_entries = grouped.get(file_name)
        if not file_entries:
            return None

        seen_files.add(file_name)
        all_items: list[str] = []
        all_raw: list[str] = []
        latest_entry_id = file_entries[0].id

        for entry in file_entries:
            all_items.extend(_split_entry_items(entry))
            all_raw.append(entry.content or "")
            entry_ts = entry.updated_at or entry.created_at
            if entry_ts and (last_updated_dt is None or entry_ts > last_updated_dt):
                last_updated_dt = entry_ts

        display_items = all_items[:max_items] if max_items > 0 else all_items
        total_items += len(all_items)

        return ProfileGroup(
            category=file_name,
            icon=icon,
            label=label,
            items=display_items,
            entry_id=str(latest_entry_id),
            raw_content="\n\n".join(all_raw),
            count=len(all_items),  # full count so frontend can show "N more"
        )

    # --- Build per-product tabs ---
    PRODUCT_SECTION_META = {
        "": ("Package", "Overview"),
        ".icp": ("UserCheck", "Target Customers"),
        ".pain-points": ("AlertTriangle", "Pain Points Solved"),
        ".competitors": ("Swords", "Competitors"),
    }

    # Discover product slugs from file names like product:{slug} and product:{slug}.{section}
    product_slugs: dict[str, dict[str, str]] = {}  # slug -> {suffix -> file_name}
    for fn in sorted(grouped.keys()):
        if fn.startswith("product:"):
            rest = fn[len("product:"):]
            if "." in rest:
                slug, suffix = rest.split(".", 1)
                product_slugs.setdefault(slug, {})[f".{suffix}"] = fn
            else:
                product_slugs.setdefault(rest, {})[""] = fn

    product_tabs: list[ProductTab] = []
    for slug, suffix_map in product_slugs.items():
        tab_sections: list[ProfileGroup] = []
        tab_name = slug.replace("-", " ").title()

        for suffix, (sec_icon, sec_label) in PRODUCT_SECTION_META.items():
            fn = suffix_map.get(suffix)
            if not fn:
                continue
            grp = _build_group(fn, sec_icon, sec_label, 0)
            if grp:
                tab_sections.append(grp)
                # Derive tab name from base entry first line
                if suffix == "" and grp.raw_content:
                    first_line = grp.raw_content.split("\n")[0].strip()
                    if first_line:
                        tab_name = first_line

        if tab_sections:
            product_tabs.append(ProductTab(
                slug=slug,
                name=tab_name,
                icon="Package",
                sections=tab_sections,
            ))

    # Mark all product: files as seen so they don't appear in global groups
    for fn in grouped:
        if fn.startswith("product:"):
            seen_files.add(fn)

    for key, icon, label, max_items in SECTION_ORDER:
        if key == "product:":
            continue  # products are in product_tabs now
        else:
            fallback_icon, fallback_label = _FILE_DISPLAY.get(
                key, ("Building2", key.replace("-", " ").replace("_", " ").title())
            )
            grp = _build_group(key, icon or fallback_icon, label or fallback_label, max_items)
            if grp:
                groups.append(grp)

    # Append any remaining files not in SECTION_ORDER
    for file_name in sorted(grouped.keys()):
        if file_name not in seen_files:
            fallback_icon, fallback_label = _FILE_DISPLAY.get(
                file_name, ("Building2", file_name.replace("-", " ").replace("_", " ").title())
            )
            grp = _build_group(file_name, fallback_icon, fallback_label, 5)
            if grp:
                groups.append(grp)

    return CompanyProfileResponse(
        company_name=tenant.name if tenant else None,
        domain=tenant.domain if tenant else None,
        groups=groups,
        product_tabs=product_tabs,
        total_items=total_items,
        last_updated=last_updated_dt.isoformat() if last_updated_dt else None,
        uploaded_files=uploaded_files,
        enrichment_status=None,
    )


# ---------------------------------------------------------------------------
# PATCH /profile/category/{entry_id}
# ---------------------------------------------------------------------------


@router.patch("/category/{entry_id}")
async def update_category(
    entry_id: UUID,
    body: UpdateCategoryRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Update the full content of a category entry (replaces all items as \\n-joined string)."""
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

    entry.content = body.content
    entry.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    await db.refresh(entry)

    items = _split_entry_items(entry)
    icon, label = _FILE_DISPLAY.get(
        entry.file_name,
        ("Building2", entry.file_name.replace("-", " ").replace("_", " ").title()),
    )

    return {
        "group": {
            "category": entry.file_name,
            "icon": icon,
            "label": label,
            "items": items,
            "entry_id": str(entry.id),
            "raw_content": entry.content or "",
            "count": len(items),
        }
    }


# ---------------------------------------------------------------------------
# POST /profile/category
# ---------------------------------------------------------------------------


@router.post("/category", status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CreateCategoryRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Create a new company intel category entry."""
    new_entry = ContextEntry(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        file_name=body.file_name,
        source="company-intel-onboarding",
        detail=body.detail or body.file_name,
        confidence="verified",
        content=body.content,
        metadata_={},
        date=datetime.date.today(),
    )
    db.add(new_entry)
    await db.flush()

    # Upsert catalog entry
    catalog_stmt = pg_insert(ContextCatalog).values(
        tenant_id=user.tenant_id,
        file_name=body.file_name,
        status="active",
    )
    catalog_stmt = catalog_stmt.on_conflict_do_update(
        index_elements=["tenant_id", "file_name"],
        set_={"status": "active"},
    )
    await db.execute(catalog_stmt)
    await db.commit()
    await db.refresh(new_entry)

    items = _split_entry_items(new_entry)
    icon, label = _FILE_DISPLAY.get(
        body.file_name,
        ("Building2", body.file_name.replace("-", " ").replace("_", " ").title()),
    )

    return {
        "group": {
            "category": new_entry.file_name,
            "icon": icon,
            "label": label,
            "items": items,
            "entry_id": str(new_entry.id),
            "raw_content": new_entry.content or "",
            "count": len(items),
        }
    }


# ---------------------------------------------------------------------------
# POST /profile/upload
# ---------------------------------------------------------------------------


@router.post("/upload")
async def link_profile_upload(
    body: LinkFileRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Link an already-uploaded file to the company profile."""
    try:
        file_uuid = UUID(body.file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file_id format")

    uploaded = (
        await db.execute(
            select(UploadedFile).where(UploadedFile.id == file_uuid)
        )
    ).scalar_one_or_none()

    if uploaded is None:
        raise HTTPException(status_code=404, detail="File not found")

    # Update metadata to flag as profile-linked
    existing_meta = uploaded.metadata_ or {}
    uploaded.metadata_ = {**existing_meta, "profile_linked": True}
    await db.commit()

    return {
        "success": True,
        "file_id": str(uploaded.id),
        "filename": uploaded.filename,
    }


# ---------------------------------------------------------------------------
# POST /profile/analyze-document
# ---------------------------------------------------------------------------


@router.post("/analyze-document")
async def analyze_document(
    body: AnalyzeDocumentRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Analyze an uploaded file through the company-intel skill engine."""
    try:
        file_uuid = UUID(body.file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file_id format")

    uploaded = (await db.execute(
        select(UploadedFile).where(
            UploadedFile.id == file_uuid,
            UploadedFile.tenant_id == user.tenant_id,
        )
    )).scalar_one_or_none()

    if uploaded is None:
        raise HTTPException(status_code=404, detail="File not found")
    if not uploaded.extracted_text or not uploaded.extracted_text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from this file")

    # Ensure file is profile-linked
    existing_meta = uploaded.metadata_ or {}
    if not existing_meta.get("profile_linked"):
        uploaded.metadata_ = {**existing_meta, "profile_linked": True}

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name="company-intel",
        input_text=f"DOCUMENT_FILE:{body.file_id}",
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await db.commit()

    return {"run_id": str(run.id)}


# ---------------------------------------------------------------------------
# POST /profile/refresh
# ---------------------------------------------------------------------------


@router.post("/refresh")
async def refresh_profile(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Re-run company intelligence with all available sources (URL + documents)."""
    # Get tenant for domain/URL
    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )).scalar_one_or_none()

    # Get all profile-linked files for this tenant, ordered deterministically
    all_files = (await db.execute(
        select(UploadedFile)
        .where(UploadedFile.tenant_id == user.tenant_id)
        .order_by(UploadedFile.created_at)
    )).scalars().all()
    linked_files = [
        f for f in all_files
        if (f.metadata_ or {}).get("profile_linked") is True
        and f.extracted_text and f.extracted_text.strip()
    ]

    has_url = tenant and tenant.domain
    has_docs = len(linked_files) > 0

    if not has_url and not has_docs:
        raise HTTPException(
            status_code=400,
            detail="Add a company URL or upload a document to refresh from",
        )

    # Build input_text: URL on first line, then DOCUMENT_FILE:{id} per doc
    input_lines = []
    if has_url:
        input_lines.append(f"https://{tenant.domain}")
    for f in linked_files:
        input_lines.append(f"DOCUMENT_FILE:{str(f.id)}")

    # If no URL but has docs, first line is a DOCUMENT_FILE ref
    # (engine will detect DOCUMENT_FILE prefix and skip crawl)
    input_text = "\n".join(input_lines)

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name="company-intel",
        input_text=input_text,
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await db.commit()

    return {"run_id": str(run.id)}


# ---------------------------------------------------------------------------
# POST /profile/reset
# ---------------------------------------------------------------------------


@router.post("/reset")
async def reset_profile(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Soft-delete all company profile entries and return to blank state."""
    from sqlalchemy import update as sa_update

    result = await db.execute(
        sa_update(ContextEntry)
        .where(
            ContextEntry.tenant_id == user.tenant_id,
            ContextEntry.source == "company-intel-onboarding",
            ContextEntry.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.datetime.now(datetime.timezone.utc))
    )
    await db.commit()
    return {"deleted_count": result.rowcount}
