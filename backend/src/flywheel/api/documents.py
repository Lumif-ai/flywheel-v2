"""Document endpoints: list, detail, share, public access, create-from-content.

Documents are persistent artifacts created by skill runs (e.g. meeting prep
briefings, company intel reports). This router provides CRUD-like access
plus a public share mechanism via token-based URLs.

Endpoints (ordered to prevent FastAPI path conflicts):
- GET  /documents                       -- paginated list for current tenant
- GET  /documents/shared/{share_token}  -- public access (no auth)
- POST /documents/from-content          -- create document from raw markdown
- GET  /documents/{document_id}         -- single document detail + signed URL
- POST /documents/{document_id}/share   -- generate or return share token
"""

from __future__ import annotations

import secrets
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Document, SkillRun
from flywheel.services.document_storage import get_document_url

router = APIRouter(prefix="/documents", tags=["documents"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class DocumentListItem(BaseModel):
    id: str
    title: str
    document_type: str
    mime_type: str
    file_size_bytes: int | None
    metadata: dict
    created_at: str
    skill_run_id: str | None


class DocumentDetail(DocumentListItem):
    content_url: str
    output: str | None = None
    rendered_html: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]
    total: int


class ShareResponse(BaseModel):
    share_token: str
    share_url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_to_list_item(doc: Document) -> DocumentListItem:
    """Serialize a Document ORM instance to a list response item."""
    return DocumentListItem(
        id=str(doc.id),
        title=doc.title,
        document_type=doc.document_type,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        metadata=doc.metadata_ or {},
        created_at=doc.created_at.isoformat() if doc.created_at else "",
        skill_run_id=str(doc.skill_run_id) if doc.skill_run_id else None,
    )


# ---------------------------------------------------------------------------
# GET /documents -- Paginated list for current tenant
# ---------------------------------------------------------------------------


@router.get("/")
async def list_documents(
    document_type: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentListResponse:
    """Return paginated list of documents for the current tenant."""
    base = select(Document).where(Document.deleted_at.is_(None))
    count_q = select(func.count(Document.id)).where(Document.deleted_at.is_(None))

    if document_type:
        base = base.where(Document.document_type == document_type)
        count_q = count_q.where(Document.document_type == document_type)

    total = (await db.execute(count_q)).scalar() or 0

    rows = (
        await db.execute(
            base.order_by(Document.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    return DocumentListResponse(
        documents=[_doc_to_list_item(doc) for doc in rows],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /documents/shared/{share_token} -- Public access (no auth)
# ---------------------------------------------------------------------------


@router.get("/shared/{share_token}")
async def get_shared_document(
    share_token: str,
) -> DocumentDetail:
    """Return document metadata and signed content URL for a shared document.

    This endpoint is public -- no authentication required.
    Uses an unscoped DB session since there is no tenant context.
    """
    from flywheel.api.deps import get_db_unscoped

    async for db in get_db_unscoped():
        result = await db.execute(
            select(Document).where(
                Document.share_token == share_token,
                Document.deleted_at.is_(None),
            )
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shared document not found",
            )

        if doc.storage_path:
            content_url = await get_document_url(doc.storage_path)
        else:
            content_url = f"/api/v1/documents/{doc.id}/content"
        item = _doc_to_list_item(doc)
        return DocumentDetail(
            **item.model_dump(),
            content_url=content_url,
        )

    # Should not reach here, but satisfy type checker
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Database unavailable",
    )


# ---------------------------------------------------------------------------
# POST /documents/from-content -- Create document from raw markdown
# ---------------------------------------------------------------------------


class FromContentRequest(BaseModel):
    title: str
    skill_name: str
    markdown_content: str
    metadata: dict = {}


@router.post("/from-content", status_code=201)
async def create_from_content(
    body: FromContentRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Create a completed SkillRun and linked Document from raw markdown.

    Used by MCP tools to save skill output as documents. The SkillRun is
    created with status=completed and attempts=max_attempts so the job queue
    never picks it up. The markdown is rendered to sanitized HTML via the
    output rendering pipeline.
    """
    from flywheel.engines.output_renderer import render_output

    rendered_html = render_output(body.skill_name, body.markdown_content)

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name=body.skill_name,
        input_text=body.markdown_content[:200],
        output=body.markdown_content,
        rendered_html=rendered_html,
        status="completed",
        attempts=3,
        max_attempts=3,
    )
    db.add(run)
    await db.flush()

    doc = Document(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        title=body.title,
        document_type=body.skill_name,
        storage_path=None,
        file_size_bytes=len(rendered_html.encode("utf-8")),
        skill_run_id=run.id,
        metadata_=body.metadata,
    )
    db.add(doc)
    await db.commit()

    return {"document_id": str(doc.id), "skill_run_id": str(run.id)}


# ---------------------------------------------------------------------------
# GET /documents/{document_id}/content -- Serve HTML from skill_runs
# ---------------------------------------------------------------------------


@router.get("/{document_id}/content", response_class=HTMLResponse)
async def get_document_content(
    document_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> HTMLResponse:
    """Serve document HTML content from the linked skill run.

    Primary content source: skill_runs.rendered_html (via skill_run_id FK).
    Fallback: Supabase Storage (if storage_path exists — legacy docs).
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.deleted_at.is_(None),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Primary: serve from linked skill run
    if doc.skill_run_id:
        run_result = await db.execute(
            select(SkillRun.rendered_html).where(SkillRun.id == doc.skill_run_id)
        )
        html = run_result.scalar_one_or_none()
        if html:
            return HTMLResponse(content=html)

    # Fallback: legacy docs with storage_path
    if doc.storage_path:
        import httpx
        try:
            signed_url = await get_document_url(doc.storage_path)
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(signed_url)
                resp.raise_for_status()
                return HTMLResponse(content=resp.text)
        except Exception:
            pass

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Document content not available",
    )


# ---------------------------------------------------------------------------
# GET /documents/{document_id} -- Single document detail
# ---------------------------------------------------------------------------


@router.get("/{document_id}")
async def get_document(
    document_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentDetail:
    """Return document metadata plus content URL.

    Points to /documents/{id}/content for HTML serving.
    Falls back to signed Storage URL for legacy docs.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.deleted_at.is_(None),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # New docs: content served from /documents/{id}/content
    # Legacy docs with storage_path: use signed URL
    if doc.storage_path:
        content_url = await get_document_url(doc.storage_path)
    else:
        content_url = f"/api/v1/documents/{doc.id}/content"

    # Fetch skill run output for native frontend rendering
    run_output: str | None = None
    run_html: str | None = None
    if doc.skill_run_id:
        run_result = await db.execute(
            select(SkillRun.output, SkillRun.rendered_html).where(
                SkillRun.id == doc.skill_run_id
            )
        )
        run_row = run_result.one_or_none()
        if run_row:
            run_output, run_html = run_row

    item = _doc_to_list_item(doc)
    return DocumentDetail(
        **item.model_dump(),
        content_url=content_url,
        output=run_output,
        rendered_html=run_html,
    )


# ---------------------------------------------------------------------------
# POST /documents/{document_id}/share -- Generate share token
# ---------------------------------------------------------------------------


@router.post("/{document_id}/share")
async def share_document(
    document_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> ShareResponse:
    """Generate or return existing share token for a document."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.deleted_at.is_(None),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if not doc.share_token:
        doc.share_token = secrets.token_urlsafe(32)
        await db.flush()
        await db.commit()
        await db.refresh(doc)

    return ShareResponse(
        share_token=doc.share_token,
        share_url=f"/d/{doc.share_token}",
    )
