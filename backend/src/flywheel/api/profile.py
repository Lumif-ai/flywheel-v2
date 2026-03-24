"""Company Profile API endpoints.

Endpoints:
- GET  /profile              -- Return tenant company intelligence grouped by category
- PATCH /profile/category/{entry_id} -- Update a category entry's full content
- POST /profile/category     -- Add a new category entry
- POST /profile/upload       -- Link an uploaded file to the company profile
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.context import _FILE_DISPLAY, _split_entry_items
from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import ContextCatalog, ContextEntry, Tenant, UploadedFile

router = APIRouter(prefix="/profile", tags=["profile"])


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


class CompanyProfileResponse(BaseModel):
    company_name: str | None
    domain: str | None
    groups: list[ProfileGroup]
    total_items: int
    last_updated: str | None
    uploaded_files: list[dict]


class UpdateCategoryRequest(BaseModel):
    content: str


class CreateCategoryRequest(BaseModel):
    file_name: str
    content: str
    detail: str | None = None


class LinkFileRequest(BaseModel):
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

    Queries context_entries where source='company-intel-onboarding', groups them
    by file_name, and returns each group with its entry_id for inline editing.
    """
    # Fetch all onboarding intel entries for this tenant (RLS handles scoping)
    entries_result = await db.execute(
        select(ContextEntry).where(
            ContextEntry.deleted_at.is_(None),
            ContextEntry.source == "company-intel-onboarding",
        )
    )
    entries = entries_result.scalars().all()

    # Fetch tenant for company name and domain
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    # Fetch linked files
    files_result = await db.execute(select(UploadedFile))
    all_files = files_result.scalars().all()
    uploaded_files = [
        {
            "id": str(f.id),
            "filename": f.filename,
            "mimetype": f.mimetype,
            "size_bytes": f.size_bytes,
        }
        for f in all_files
        if (f.metadata_ or {}).get("profile_linked") is True
    ]

    # Build groups
    groups: list[ProfileGroup] = []
    total_items = 0
    last_updated_dt: datetime.datetime | None = None

    for entry in entries:
        items = _split_entry_items(entry)
        icon, label = _FILE_DISPLAY.get(
            entry.file_name,
            ("Building2", entry.file_name.replace("-", " ").replace("_", " ").title()),
        )
        groups.append(
            ProfileGroup(
                category=entry.file_name,
                icon=icon,
                label=label,
                items=items,
                entry_id=str(entry.id),
                raw_content=entry.content or "",
                count=len(items),
            )
        )
        total_items += len(items)

        # Track most recent update
        entry_ts = entry.updated_at or entry.created_at
        if entry_ts and (last_updated_dt is None or entry_ts > last_updated_dt):
            last_updated_dt = entry_ts

    return CompanyProfileResponse(
        company_name=tenant.name if tenant else None,
        domain=tenant.domain if tenant else None,
        groups=groups,
        total_items=total_items,
        last_updated=last_updated_dt.isoformat() if last_updated_dt else None,
        uploaded_files=uploaded_files,
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
