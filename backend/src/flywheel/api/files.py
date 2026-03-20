"""File upload, listing, and metadata endpoints.

Endpoints:
- POST /files/upload    -- Upload a file with text extraction
- GET  /files/          -- List uploaded files (paginated)
- GET  /files/{file_id} -- Get file metadata including extracted text
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import UploadedFile
from flywheel.services.file_extraction import (
    ALLOWED_MIMETYPES,
    MAX_FILE_SIZE,
    extract_text,
    validate_upload,
)

router = APIRouter(prefix="/files", tags=["files"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file_to_dict(f: UploadedFile, *, include_text: bool = False) -> dict[str, Any]:
    """Serialize an UploadedFile to a JSON-friendly dict."""
    d: dict[str, Any] = {
        "id": str(f.id),
        "filename": f.filename,
        "mimetype": f.mimetype,
        "size_bytes": f.size_bytes,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }
    if include_text:
        d["extracted_text"] = f.extracted_text
        d["extracted_text_length"] = len(f.extracted_text) if f.extracted_text else 0
        d["storage_path"] = f.storage_path
    return d


# ---------------------------------------------------------------------------
# POST /files/upload
# ---------------------------------------------------------------------------


@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Upload a file, extract text, and store metadata."""
    # Read content
    content = await file.read()
    size = len(content)

    # Validate
    try:
        mimetype = validate_upload(file.filename or "unknown", file.content_type, size)
    except ValueError as e:
        error_msg = str(e)
        if "too large" in error_msg.lower():
            raise HTTPException(status_code=413, detail=error_msg)
        raise HTTPException(status_code=415, detail=error_msg)

    # Extract text
    extracted = await extract_text(content, mimetype)

    # Storage path (local placeholder -- Supabase Storage in Phase 25)
    file_uuid = uuid4()
    storage_path = f"local://{user.tenant_id}/{file_uuid}/{file.filename}"

    # Create DB record
    uploaded = UploadedFile(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        filename=file.filename or "unknown",
        mimetype=mimetype,
        size_bytes=size,
        extracted_text=extracted,
        storage_path=storage_path,
    )
    db.add(uploaded)
    await db.commit()
    await db.refresh(uploaded)

    return {
        "id": str(uploaded.id),
        "filename": uploaded.filename,
        "mimetype": uploaded.mimetype,
        "size_bytes": uploaded.size_bytes,
        "extracted_text_length": len(extracted) if extracted else 0,
        "created_at": uploaded.created_at.isoformat() if uploaded.created_at else None,
    }


# ---------------------------------------------------------------------------
# GET /files/ -- List uploaded files
# ---------------------------------------------------------------------------


@router.get("/")
async def list_files(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """List uploaded files with pagination. Does not include extracted_text."""
    count_q = select(func.count(UploadedFile.id))
    total = (await db.execute(count_q)).scalar() or 0

    files = (
        await db.execute(
            select(UploadedFile)
            .order_by(UploadedFile.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    return {
        "items": [_file_to_dict(f) for f in files],
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


# ---------------------------------------------------------------------------
# GET /files/{file_id} -- File detail with extracted text
# ---------------------------------------------------------------------------


@router.get("/{file_id}")
async def get_file(
    file_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Get file metadata including full extracted text."""
    result = await db.execute(
        select(UploadedFile).where(UploadedFile.id == file_id)
    )
    uploaded = result.scalar_one_or_none()
    if uploaded is None:
        raise HTTPException(status_code=404, detail="File not found")

    return _file_to_dict(uploaded, include_text=True)
