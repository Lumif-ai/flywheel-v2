"""Document endpoints: list, detail, share, public access, create-from-content, tags.

Documents are persistent artifacts created by skill runs (e.g. meeting prep
briefings, company intel reports). This router provides CRUD-like access
plus a public share mechanism via token-based URLs.

Endpoints (ordered to prevent FastAPI path conflicts):
- GET  /documents                       -- filtered, paginated list for current tenant
- GET  /documents/tags                  -- unique tags with counts (scoped to filters)
- GET  /documents/counts-by-type        -- doc counts per type (scoped to filters)
- GET  /documents/shared/{share_token}  -- public access (no auth)
- POST /documents/from-content          -- create document from raw markdown (with dedup)
- GET  /documents/{document_id}         -- single document detail + signed URL
- GET  /documents/{document_id}/content -- serve HTML content
- DELETE /documents/{document_id}        -- soft delete (set deleted_at)
- PATCH /documents/{document_id}/tags   -- add/remove tags on a document
- POST /documents/{document_id}/share   -- generate or return share token
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, and_, text
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Document, SkillRun, PipelineEntry
from flywheel.services.document_storage import get_document_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

# ---------------------------------------------------------------------------
# Tag validation constants
# ---------------------------------------------------------------------------

TAG_MAX_PER_DOCUMENT = 20
TAG_MAX_PER_TENANT = 200
TAG_MAX_CHARS = 50
TAG_MIN_CHARS = 2
TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")

DEDUP_WINDOW_HOURS = 1


def validate_tag(tag: str) -> str:
    """Normalize and validate a single tag. Returns normalized tag or raises ValueError."""
    tag = tag.strip().lower()
    if len(tag) < TAG_MIN_CHARS:
        raise ValueError(f"Tag '{tag}' is too short (min {TAG_MIN_CHARS} chars)")
    if len(tag) > TAG_MAX_CHARS:
        raise ValueError(f"Tag '{tag}' is too long (max {TAG_MAX_CHARS} chars)")
    if not TAG_PATTERN.match(tag):
        raise ValueError(
            f"Tag '{tag}' contains invalid characters (lowercase alphanumeric and hyphens only)"
        )
    return tag


def validate_tags(tags: list[str]) -> list[str]:
    """Validate and normalize a list of tags."""
    if len(tags) > TAG_MAX_PER_DOCUMENT:
        raise ValueError(
            f"Too many tags ({len(tags)}), max {TAG_MAX_PER_DOCUMENT} per document"
        )
    return list(dict.fromkeys(validate_tag(t) for t in tags))  # dedup preserving order


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
    tags: list[str] = []
    account_id: str | None = None
    account_name: str | None = None


class DocumentDetail(DocumentListItem):
    content_url: str
    output: str | None = None
    rendered_html: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]
    total: int
    next_cursor: str | None = None


class TagCountItem(BaseModel):
    tag: str
    count: int


class TypeCountItem(BaseModel):
    document_type: str
    count: int


class ShareResponse(BaseModel):
    share_token: str
    share_url: str


class TagUpdateRequest(BaseModel):
    add: list[str] = []
    remove: list[str] = []


class TagUpdateResponse(BaseModel):
    tags: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_to_list_item(doc: Document, account_name: str | None = None) -> DocumentListItem:
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
        tags=doc.tags or [],
        account_id=str(doc.account_id) if doc.account_id else None,
        account_name=account_name,
    )


def _apply_filters(
    stmt,
    document_type: str | None = None,
    account_id: UUID | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
):
    """Apply common filters to a document query."""
    stmt = stmt.where(Document.deleted_at.is_(None))
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    if account_id:
        stmt = stmt.where(Document.account_id == account_id)
    if tags:
        # AND logic: document must have ALL specified tags
        for tag in tags:
            stmt = stmt.where(Document.tags.any(tag))
    if search:
        stmt = stmt.where(Document.title.ilike(f"%{search}%"))
    return stmt


# ---------------------------------------------------------------------------
# GET /documents -- Filtered, paginated list for current tenant
# ---------------------------------------------------------------------------


@router.get("/")
async def list_documents(
    document_type: str | None = None,
    account_id: UUID | None = None,
    tags: list[str] | None = Query(None),
    search: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentListResponse:
    """Return filtered, cursor-paginated list of documents for the current tenant."""
    base = select(Document)
    base = _apply_filters(base, document_type, account_id, tags, search)

    # Count (for total)
    count_q = select(func.count(Document.id))
    count_q = _apply_filters(count_q, document_type, account_id, tags, search)
    total = (await db.execute(count_q)).scalar() or 0

    # Cursor-based pagination: cursor is "created_at|id"
    if cursor:
        try:
            parts = cursor.split("|", 1)
            cursor_ts = datetime.fromisoformat(parts[0])
            cursor_id = UUID(parts[1])
            base = base.where(
                (Document.created_at < cursor_ts)
                | (
                    (Document.created_at == cursor_ts)
                    & (Document.id < cursor_id)
                )
            )
        except (ValueError, IndexError):
            pass  # Invalid cursor, ignore and start from beginning

    base = base.order_by(Document.created_at.desc(), Document.id.desc()).limit(limit + 1)
    rows = (await db.execute(base)).scalars().all()

    # Determine next cursor
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    # Batch-fetch account names for documents that have account_id
    account_ids = {doc.account_id for doc in rows if doc.account_id}
    account_names: dict[UUID, str] = {}
    if account_ids:
        acct_result = await db.execute(
            select(PipelineEntry.id, PipelineEntry.name).where(
                PipelineEntry.id.in_(account_ids)
            )
        )
        account_names = {row.id: row.name for row in acct_result.all()}

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"

    return DocumentListResponse(
        documents=[
            _doc_to_list_item(doc, account_names.get(doc.account_id))
            for doc in rows
        ],
        total=total,
        next_cursor=next_cursor,
    )


# ---------------------------------------------------------------------------
# GET /documents/tags -- Unique tags with counts (scoped to filters)
# ---------------------------------------------------------------------------


@router.get("/tags")
async def list_tags(
    document_type: str | None = None,
    account_id: UUID | None = None,
    search: str | None = None,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[TagCountItem]:
    """Return unique tags with counts, scoped to active filters."""
    # Unnest tags array and count occurrences
    unnested = (
        select(
            func.unnest(Document.tags).label("tag"),
            Document.id,
        )
        .where(Document.deleted_at.is_(None))
    )
    if document_type:
        unnested = unnested.where(Document.document_type == document_type)
    if account_id:
        unnested = unnested.where(Document.account_id == account_id)
    if search:
        unnested = unnested.where(Document.title.ilike(f"%{search}%"))

    unnested_sub = unnested.subquery()
    stmt = (
        select(
            unnested_sub.c.tag,
            func.count().label("count"),
        )
        .group_by(unnested_sub.c.tag)
        .order_by(func.count().desc())
    )
    result = await db.execute(stmt)
    return [TagCountItem(tag=row.tag, count=row.count) for row in result.all()]


# ---------------------------------------------------------------------------
# GET /documents/counts-by-type -- Doc counts per type (scoped to filters)
# ---------------------------------------------------------------------------


@router.get("/counts-by-type")
async def counts_by_type(
    account_id: UUID | None = None,
    tags: list[str] | None = Query(None),
    search: str | None = None,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[TypeCountItem]:
    """Return document counts per type, scoped to active filters."""
    stmt = (
        select(
            Document.document_type,
            func.count(Document.id).label("count"),
        )
        .where(Document.deleted_at.is_(None))
    )
    if account_id:
        stmt = stmt.where(Document.account_id == account_id)
    if tags:
        for tag in tags:
            stmt = stmt.where(Document.tags.any(tag))
    if search:
        stmt = stmt.where(Document.title.ilike(f"%{search}%"))
    stmt = stmt.group_by(Document.document_type).order_by(func.count(Document.id).desc())
    result = await db.execute(stmt)
    return [TypeCountItem(document_type=row.document_type, count=row.count) for row in result.all()]


# ---------------------------------------------------------------------------
# GET /documents/shared/{share_token} -- Public access (no auth)
# ---------------------------------------------------------------------------


@router.get("/shared/{share_token}")
async def get_shared_document(
    share_token: str,
) -> DocumentDetail:
    """Return document metadata and signed content URL for a shared document."""
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

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Database unavailable",
    )


# ---------------------------------------------------------------------------
# POST /documents/from-content -- Create document from raw markdown (with dedup)
# ---------------------------------------------------------------------------


class FromContentRequest(BaseModel):
    title: str
    skill_name: str
    markdown_content: str
    metadata: dict = {}
    # v12.0 optional fields — backward compatible
    account_id: str | None = None
    tags: list[str] = []


@router.post("/from-content", status_code=201)
async def create_from_content(
    body: FromContentRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Create a completed SkillRun and linked Document from raw markdown.

    Supports dedup: if a document with the same title + type + account exists
    within the last hour, updates it instead of creating a new one.
    """
    from flywheel.engines.output_renderer import render_output

    rendered_html = render_output(body.skill_name, body.markdown_content)

    # Validate tags if provided
    validated_tags: list[str] = []
    if body.tags:
        try:
            validated_tags = validate_tags(body.tags)
        except ValueError as e:
            logger.warning(
                "Tag validation failure: skill=%s tenant=%s error=%s",
                body.skill_name, user.tenant_id, str(e),
            )
            raise HTTPException(status_code=422, detail=str(e))

    # Resolve account_id
    resolved_account_id: UUID | None = None
    if body.account_id:
        try:
            resolved_account_id = UUID(body.account_id)
            # Verify account exists
            acct = await db.execute(
                select(PipelineEntry.id).where(PipelineEntry.id == resolved_account_id)
            )
            if acct.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Account {body.account_id} not found",
                )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid account_id: {body.account_id}",
            )

    # Also check metadata for account_id (backward compat)
    if not resolved_account_id and body.metadata.get("account_id"):
        try:
            resolved_account_id = UUID(body.metadata["account_id"])
        except (ValueError, TypeError):
            pass

    # Dedup check: same title + type + account within DEDUP_WINDOW_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_WINDOW_HOURS)
    dedup_q = (
        select(Document)
        .where(
            Document.title == body.title,
            Document.document_type == body.skill_name,
            Document.deleted_at.is_(None),
            Document.created_at >= cutoff,
        )
    )
    if resolved_account_id:
        dedup_q = dedup_q.where(Document.account_id == resolved_account_id)
    else:
        dedup_q = dedup_q.where(Document.account_id.is_(None))

    existing = (await db.execute(dedup_q)).scalar_one_or_none()

    if existing:
        # Update existing document
        logger.info(
            "dedup_match: existing_doc=%s new_title=%s window=%dm",
            existing.id, body.title, DEDUP_WINDOW_HOURS * 60,
        )
        # Update the linked skill run
        if existing.skill_run_id:
            run_result = await db.execute(
                select(SkillRun).where(SkillRun.id == existing.skill_run_id)
            )
            run = run_result.scalar_one_or_none()
            if run:
                run.output = body.markdown_content
                run.rendered_html = rendered_html
                run.input_text = body.markdown_content[:200]
        existing.file_size_bytes = len(rendered_html.encode("utf-8"))
        existing.metadata_ = body.metadata
        existing.updated_at = datetime.now(timezone.utc)
        if validated_tags:
            existing.tags = validated_tags
        if resolved_account_id:
            existing.account_id = resolved_account_id
        await db.commit()
        return {"document_id": str(existing.id), "skill_run_id": str(existing.skill_run_id), "dedup": True}

    # Create new skill run + document
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
        tags=validated_tags,
        account_id=resolved_account_id,
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
    """Serve document HTML content from the linked skill run."""
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

    if doc.skill_run_id:
        run_result = await db.execute(
            select(SkillRun.rendered_html).where(SkillRun.id == doc.skill_run_id)
        )
        html = run_result.scalar_one_or_none()
        if html:
            return HTMLResponse(content=html)

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
    """Return document metadata plus content URL."""
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

    if doc.storage_path:
        content_url = await get_document_url(doc.storage_path)
    else:
        content_url = f"/api/v1/documents/{doc.id}/content"

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

    # Fetch account name
    account_name = None
    if doc.account_id:
        acct_result = await db.execute(
            select(PipelineEntry.name).where(PipelineEntry.id == doc.account_id)
        )
        account_name = acct_result.scalar_one_or_none()

    item = _doc_to_list_item(doc, account_name)
    return DocumentDetail(
        **item.model_dump(),
        content_url=content_url,
        output=run_output,
        rendered_html=run_html,
    )


# ---------------------------------------------------------------------------
# GET /documents/{document_id}/export -- Export as PDF or DOCX
# ---------------------------------------------------------------------------


@router.get("/{document_id}/export")
async def export_document(
    document_id: UUID,
    format: str = Query(..., pattern="^(pdf|docx)$"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> StreamingResponse:
    """Export document as PDF or DOCX for download."""
    import io

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

    # Fetch linked SkillRun content
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

    if not run_output and not run_html:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document has no exportable content",
        )

    from flywheel.services.document_export import export_as_pdf, export_as_docx

    safe_title = re.sub(r"[^\w\s\-]", "", doc.title or "document").strip().replace(" ", "_")[:60]

    try:
        if format == "pdf":
            content = await asyncio.to_thread(export_as_pdf, doc.document_type, run_output, run_html)
            return StreamingResponse(
                io.BytesIO(content),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_title}.pdf"',
                },
            )
        else:
            content = await asyncio.to_thread(export_as_docx, doc.document_type, run_output, run_html)
            return StreamingResponse(
                io.BytesIO(content),
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_title}.docx"',
                },
            )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Export failed for document %s format=%s", document_id, format)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {e}",
        )


# ---------------------------------------------------------------------------
# PATCH /documents/{document_id}/tags -- Add/remove tags
# ---------------------------------------------------------------------------


@router.patch("/{document_id}/tags")
async def update_document_tags(
    document_id: UUID,
    body: TagUpdateRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> TagUpdateResponse:
    """Add or remove tags on a document with validation."""
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

    current_tags = list(doc.tags or [])

    # Remove tags
    if body.remove:
        remove_normalized = {t.strip().lower() for t in body.remove}
        current_tags = [t for t in current_tags if t not in remove_normalized]

    # Add tags
    if body.add:
        try:
            new_tags = [validate_tag(t) for t in body.add]
        except ValueError as e:
            logger.warning(
                "Tag validation failure: doc=%s tenant=%s error=%s",
                document_id, user.tenant_id, str(e),
            )
            raise HTTPException(status_code=422, detail=str(e))
        for tag in new_tags:
            if tag not in current_tags:
                current_tags.append(tag)

    # Check per-document limit
    if len(current_tags) > TAG_MAX_PER_DOCUMENT:
        raise HTTPException(
            status_code=422,
            detail=f"Too many tags ({len(current_tags)}), max {TAG_MAX_PER_DOCUMENT}",
        )

    # Check per-tenant limit
    tenant_tag_count = (
        await db.execute(
            select(func.count(func.distinct(func.unnest(Document.tags)))).where(
                Document.deleted_at.is_(None)
            )
        )
    ).scalar() or 0
    new_unique = len(set(current_tags) - set(doc.tags or []))
    if tenant_tag_count + new_unique > TAG_MAX_PER_TENANT:
        raise HTTPException(
            status_code=422,
            detail=f"Too many unique tags for tenant (max {TAG_MAX_PER_TENANT})",
        )

    doc.tags = current_tags
    doc.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return TagUpdateResponse(tags=doc.tags)


# ---------------------------------------------------------------------------
# DELETE /documents/{document_id} -- Soft delete
# ---------------------------------------------------------------------------


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    """Soft-delete a document by setting deleted_at timestamp."""
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

    doc.deleted_at = datetime.now(timezone.utc)
    await db.commit()


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
