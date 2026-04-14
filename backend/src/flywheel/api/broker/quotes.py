"""Broker quote endpoints.

Endpoints:
  GET  /projects/{id}/quotes        -- list quotes for a project
  PUT  /quotes/{id}                 -- manual quote entry
  POST /quotes/{id}/mark-received   -- mark quote received
  POST /quotes/{id}/portal-screenshot -- upload portal screenshot
  POST /quotes/{id}/portal-confirm  -- confirm portal submission
  POST /quotes/{id}/extract         -- trigger async quote extraction
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.broker._shared import validate_transition
from flywheel.api.deps import get_tenant_db, require_module
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import (
    BrokerActivity,
    BrokerProject,
    CarrierQuote,
    Email,
    Integration,
    ProjectCoverage,
    UploadedFile,
)

logger = logging.getLogger(__name__)

quotes_router = APIRouter(tags=["broker"])

_MAX_DOC_SIZE = 25 * 1024 * 1024
_UPLOADS_BUCKET = "uploads"


# ---------------------------------------------------------------------------
# Pydantic request bodies
# ---------------------------------------------------------------------------


class ManualQuoteBody(BaseModel):
    premium: float | None = None
    deductible: float | None = None
    limit_amount: float | None = None
    coinsurance: float | None = None
    term_months: int | None = None
    validity_date: str | None = None
    exclusions: list[str] | None = None
    conditions: list[str] | None = None
    endorsements: list[str] | None = None
    coverage_id: UUID | None = None
    confidence: str | None = None


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------


def _quote_to_dict(quote: CarrierQuote) -> dict[str, Any]:
    """Serialize a CarrierQuote to a JSON-friendly dict.

    NOTE: Removed dropped columns:
      - is_best_price, is_best_coverage, is_recommended
      - draft_subject, draft_body, draft_status
    These fields were moved to BrokerRecommendation and SolicitationDraft tables.
    """
    return {
        "id": str(quote.id),
        "broker_project_id": str(quote.broker_project_id),
        "coverage_id": str(quote.coverage_id) if quote.coverage_id else None,
        "carrier_name": quote.carrier_name,
        "carrier_config_id": str(quote.carrier_config_id) if quote.carrier_config_id else None,
        "carrier_type": quote.carrier_type,
        "premium": float(quote.premium) if quote.premium is not None else None,
        "deductible": float(quote.deductible) if quote.deductible is not None else None,
        "limit_amount": float(quote.limit_amount) if quote.limit_amount is not None else None,
        "coinsurance": float(quote.coinsurance) if quote.coinsurance is not None else None,
        "term_months": quote.term_months,
        "validity_date": quote.validity_date.isoformat() if quote.validity_date else None,
        "exclusions": quote.exclusions or [],
        "conditions": quote.conditions or [],
        "endorsements": quote.endorsements or [],
        "has_critical_exclusion": quote.has_critical_exclusion,
        "critical_exclusion_detail": quote.critical_exclusion_detail,
        "status": quote.status,
        "solicited_at": quote.solicited_at.isoformat() if quote.solicited_at else None,
        "received_at": quote.received_at.isoformat() if quote.received_at else None,
        "confidence": quote.confidence,
        "source": quote.source,
        "is_manual_override": quote.is_manual_override,
        "documents": [],
        "created_at": quote.created_at.isoformat() if quote.created_at else None,
        "updated_at": quote.updated_at.isoformat() if quote.updated_at else None,
    }


# ---------------------------------------------------------------------------
# GET /broker/projects/{project_id}/quotes
# ---------------------------------------------------------------------------


@quotes_router.get("/projects/{project_id}/quotes")
async def list_project_quotes(
    project_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """List all carrier quotes for a project, newest first."""
    result = await db.execute(
        select(BrokerProject).where(
            BrokerProject.id == project_id,
            BrokerProject.tenant_id == user.tenant_id,
            BrokerProject.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    quotes_result = await db.execute(
        select(CarrierQuote)
        .where(
            CarrierQuote.broker_project_id == project_id,
            CarrierQuote.tenant_id == user.tenant_id,
        )
        .order_by(CarrierQuote.created_at.desc())
    )
    quotes = quotes_result.scalars().all()

    return [_quote_to_dict(q) for q in quotes]


# ---------------------------------------------------------------------------
# PUT /broker/quotes/{quote_id}
# ---------------------------------------------------------------------------


@quotes_router.put("/quotes/{quote_id}")
async def update_quote_manual(
    quote_id: UUID,
    body: ManualQuoteBody,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Manual quote entry — update CarrierQuote fields directly."""
    result = await db.execute(
        select(CarrierQuote).where(
            CarrierQuote.id == quote_id,
            CarrierQuote.tenant_id == user.tenant_id,
        )
    )
    quote = result.scalar_one_or_none()
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(quote, field, value)

    quote.source = "manual"
    quote.is_manual_override = True
    quote.status = "extracted"

    activity = BrokerActivity(
        tenant_id=user.tenant_id,
        broker_project_id=quote.broker_project_id,
        activity_type="quote_manual_entry",
        actor_type="user",
        metadata_={"fields_set": list(update_data.keys())},
    )
    db.add(activity)
    await db.commit()
    await db.refresh(quote)

    return _quote_to_dict(quote)


# ---------------------------------------------------------------------------
# POST /broker/quotes/{quote_id}/mark-received
# ---------------------------------------------------------------------------


@quotes_router.post("/quotes/{quote_id}/mark-received")
async def mark_quote_received(
    quote_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Manually mark a quote as received."""
    result = await db.execute(
        select(CarrierQuote).where(
            CarrierQuote.id == quote_id,
            CarrierQuote.tenant_id == user.tenant_id,
        )
    )
    quote = result.scalar_one_or_none()
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")

    quote.status = "received"
    quote.received_at = datetime.now(timezone.utc)

    project_result = await db.execute(
        select(BrokerProject).where(BrokerProject.id == quote.broker_project_id)
    )
    project = project_result.scalar_one()

    all_quotes_result = await db.execute(
        select(CarrierQuote).where(
            CarrierQuote.broker_project_id == project.id
        )
    )
    all_quotes = all_quotes_result.scalars().all()

    all_received = all(
        q.status in ("received", "extracted", "reviewed", "selected")
        for q in all_quotes
    )
    if all_received:
        target_status = "quotes_complete"
    else:
        target_status = "quotes_partial"
    validate_transition(project.status, target_status, client_id=project.client_id)
    project.status = target_status

    activity = BrokerActivity(
        tenant_id=user.tenant_id,
        broker_project_id=project.id,
        activity_type="quote_received",
        actor_type="user",
        description=f"Quote from {quote.carrier_name} manually marked as received",
        metadata_={"carrier_name": quote.carrier_name, "manual": True},
    )
    db.add(activity)
    await db.commit()
    await db.refresh(quote)

    return _quote_to_dict(quote)


# ---------------------------------------------------------------------------
# POST /broker/quotes/{quote_id}/portal-screenshot
# ---------------------------------------------------------------------------


@quotes_router.post("/quotes/{quote_id}/portal-screenshot")
async def portal_screenshot(
    quote_id: UUID,
    screenshot: UploadFile = File(...),
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Upload a portal submission screenshot for review."""
    from flywheel.services.document_storage import upload_file as upload_to_storage
    from uuid import uuid4

    result = await db.execute(
        select(CarrierQuote).where(
            CarrierQuote.id == quote_id,
            CarrierQuote.tenant_id == user.tenant_id,
        )
    )
    quote = result.scalar_one_or_none()
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")

    content = await screenshot.read()
    if len(content) > _MAX_DOC_SIZE:
        raise HTTPException(status_code=413, detail="Screenshot exceeds 25 MB limit")

    file_uuid = uuid4()
    filename = screenshot.filename or "screenshot.png"
    mime_type = screenshot.content_type or "image/png"
    tenant_id_str = str(user.tenant_id)

    try:
        storage_path = await upload_to_storage(
            tenant_id=tenant_id_str,
            file_id=str(file_uuid),
            filename=filename,
            content=content,
            mime_type=mime_type,
        )
        screenshot_url = storage_path
    except Exception:
        screenshot_url = f"local://{tenant_id_str}/{file_uuid}/{filename}"

    metadata = dict(quote.metadata_ or {})
    metadata["screenshot_url"] = screenshot_url
    quote.metadata_ = metadata
    # Store screenshot review status in metadata (no draft_status column)
    metadata["portal_status"] = "review"
    quote.metadata_ = metadata

    await db.commit()

    return {"screenshot_url": screenshot_url, "status": "review"}


# ---------------------------------------------------------------------------
# POST /broker/quotes/{quote_id}/portal-confirm
# ---------------------------------------------------------------------------


@quotes_router.post("/quotes/{quote_id}/portal-confirm")
async def portal_confirm(
    quote_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Confirm a portal submission after screenshot review."""
    result = await db.execute(
        select(CarrierQuote).where(
            CarrierQuote.id == quote_id,
            CarrierQuote.tenant_id == user.tenant_id,
        )
    )
    quote = result.scalar_one_or_none()
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")

    # Check portal_status in metadata (replaces draft_status)
    portal_status = (quote.metadata_ or {}).get("portal_status")
    if portal_status != "review":
        raise HTTPException(
            status_code=409,
            detail="Cannot confirm — screenshot must be uploaded first (portal_status='review')",
        )

    quote.status = "solicited"
    quote.solicited_at = datetime.now(timezone.utc)
    metadata = dict(quote.metadata_ or {})
    metadata["portal_status"] = "confirmed"
    quote.metadata_ = metadata

    activity = BrokerActivity(
        tenant_id=user.tenant_id,
        broker_project_id=quote.broker_project_id,
        activity_type="solicitation_sent",
        actor_type="user",
        metadata_={"method": "portal", "carrier_name": quote.carrier_name},
    )
    db.add(activity)

    await db.commit()
    await db.refresh(quote)

    return {
        "quote_id": str(quote.id),
        "carrier_name": quote.carrier_name,
        "status": quote.status,
        "solicited_at": quote.solicited_at.isoformat() if quote.solicited_at else None,
    }


# ---------------------------------------------------------------------------
# POST /broker/quotes/{quote_id}/extract
# ---------------------------------------------------------------------------


@quotes_router.post("/quotes/{quote_id}/extract", status_code=202)
async def extract_quote_endpoint(
    quote_id: UUID,
    force: bool = Query(False),
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Trigger async PDF extraction for a carrier quote."""
    from flywheel.engines.quote_extractor import extract_quote

    result = await db.execute(
        select(CarrierQuote).where(
            CarrierQuote.id == quote_id,
            CarrierQuote.tenant_id == user.tenant_id,
        )
    )
    quote = result.scalar_one_or_none()
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status in ("extracted", "reviewed") and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Quote already {quote.status}. Use ?force=true to re-extract.",
        )

    pdf_content = None
    if quote.source_document_id:
        pdf_content = await _get_quote_pdf_from_document(db, quote, user.tenant_id)
    elif quote.source_email_id:
        pdf_content = await _get_quote_pdf_from_email(db, quote, user.tenant_id)

    if pdf_content is None:
        raise HTTPException(
            status_code=422,
            detail="No PDF source found for this quote (no source_document_id or source_email_id)",
        )

    cov_result = await db.execute(
        select(ProjectCoverage).where(
            ProjectCoverage.broker_project_id == quote.broker_project_id
        )
    )
    coverages = cov_result.scalars().all()
    coverages_dicts = [
        {
            "id": str(c.id),
            "coverage_type": c.coverage_type,
            "category": c.category,
            "required_limit": float(c.required_limit) if c.required_limit else None,
        }
        for c in coverages
    ]

    tenant_id = user.tenant_id

    async def _run_extraction():
        from flywheel.db.session import get_session_factory
        factory = get_session_factory()
        try:
            async with factory() as session:
                await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
                await extract_quote(
                    session, tenant_id, quote_id, pdf_content, coverages_dicts, force=force
                )
                await session.commit()
        except Exception as exc:
            logger.error("Quote extraction failed for %s: %s", quote_id, exc)

    asyncio.create_task(_run_extraction())

    return {"status": "extracting", "quote_id": str(quote_id)}


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------


async def _get_quote_pdf_from_document(
    db: AsyncSession, quote: CarrierQuote, tenant_id: UUID
) -> bytes | None:
    """Retrieve PDF bytes from UploadedFile via source_document_id."""
    result = await db.execute(
        select(UploadedFile).where(
            UploadedFile.id == quote.source_document_id,
            UploadedFile.tenant_id == tenant_id,
        )
    )
    uploaded_file = result.scalar_one_or_none()
    if not uploaded_file or not uploaded_file.storage_path:
        return None

    import httpx
    from flywheel.config import settings as app_settings

    url = f"{app_settings.supabase_url}/storage/v1/object/{_UPLOADS_BUCKET}/{uploaded_file.storage_path}"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {app_settings.supabase_service_key}"},
        )
        if resp.status_code != 200:
            return None
        return resp.content


async def _get_quote_pdf_from_email(
    db: AsyncSession, quote: CarrierQuote, tenant_id: UUID
) -> bytes | None:
    """Retrieve PDF bytes from the source email's attachment."""
    from flywheel.services.gmail_read import (
        find_pdf_attachments,
        get_attachment,
        get_valid_credentials,
    )

    email_result = await db.execute(
        select(Email).where(
            Email.id == quote.source_email_id,
            Email.tenant_id == tenant_id,
        )
    )
    email_row = email_result.scalar_one_or_none()
    if not email_row:
        return None

    intg_result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.provider == "gmail-read",
            Integration.status == "connected",
        )
    )
    integration = intg_result.scalar_one_or_none()
    if not integration:
        return None

    creds = await get_valid_credentials(integration)

    def _fetch():
        from googleapiclient.discovery import build as _build
        service = _build("gmail", "v1", credentials=creds)
        return (
            service.users()
            .messages()
            .get(userId="me", id=email_row.gmail_message_id, format="full")
            .execute()
        )

    import asyncio as _asyncio
    msg = await _asyncio.to_thread(_fetch)
    pdfs = find_pdf_attachments(msg)
    if not pdfs:
        return None

    return await get_attachment(creds, email_row.gmail_message_id, pdfs[0]["attachment_id"])
