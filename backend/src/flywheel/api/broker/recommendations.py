"""Broker recommendation endpoints.

Endpoints:
  POST /projects/{id}/draft-recommendation      -- create BrokerRecommendation row
  PUT  /recommendations/{id}                    -- edit draft before sending
  POST /recommendations/{id}/approve-send       -- send recommendation email + save Document
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.broker._shared import validate_transition
from flywheel.api.deps import get_tenant_db, require_module
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import (
    BrokerActivity,
    BrokerProject,
    BrokerRecommendation,
    CarrierQuote,
    Document,
    ProjectCoverage,
)
from flywheel.services.email_dispatch import send_email_as_user

logger = logging.getLogger(__name__)

recommendations_router = APIRouter(tags=["broker"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class DraftRecommendationBody(BaseModel):
    recipient_email: str | None = None


class EditRecommendationBody(BaseModel):
    subject: str | None = None
    body: str | None = None
    recipient_email: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coverage_to_dict(c: ProjectCoverage) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "coverage_type": c.coverage_type,
        "category": c.category,
        "display_name": c.display_name,
        "required_limit": float(c.required_limit) if c.required_limit is not None else None,
        "gap_status": c.gap_status,
        "gap_notes": c.gap_notes,
    }


def _quote_to_dict(q: CarrierQuote) -> dict[str, Any]:
    return {
        "id": str(q.id),
        "carrier_name": q.carrier_name,
        "carrier_type": q.carrier_type,
        "premium": float(q.premium) if q.premium is not None else None,
        "deductible": float(q.deductible) if q.deductible is not None else None,
        "limit_amount": float(q.limit_amount) if q.limit_amount is not None else None,
        "status": q.status,
        "has_critical_exclusion": q.has_critical_exclusion,
        "critical_exclusion_detail": q.critical_exclusion_detail,
    }


# ---------------------------------------------------------------------------
# POST /broker/projects/{project_id}/draft-recommendation
# ---------------------------------------------------------------------------


@recommendations_router.post("/projects/{project_id}/draft-recommendation")
async def draft_recommendation(
    project_id: UUID,
    body: DraftRecommendationBody | None = None,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Generate an AI recommendation and create a BrokerRecommendation row.

    Requires project status 'quotes_complete'. Transitions project to 'recommended'.
    """
    from flywheel.engines.quote_comparator import compare_quotes, summarize_comparison
    from flywheel.engines.recommendation_drafter import draft_recommendation_email

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

    # Status gate: must be transitioning to 'recommended'
    validate_transition(project.status, "recommended", client_id=project.client_id)

    # Load coverages and quotes
    cov_result = await db.execute(
        select(ProjectCoverage).where(ProjectCoverage.broker_project_id == project_id)
    )
    coverages = cov_result.scalars().all()
    coverage_dicts = [_coverage_to_dict(c) for c in coverages]

    quote_result = await db.execute(
        select(CarrierQuote).where(
            CarrierQuote.broker_project_id == project_id,
            CarrierQuote.status.in_(("extracted", "reviewed", "selected")),
        )
    )
    quotes = quote_result.scalars().all()
    quote_dicts = [_quote_to_dict(q) for q in quotes]

    project_dict = {
        "id": str(project.id),
        "name": project.name,
        "project_type": project.project_type,
        "description": project.description,
        "contract_value": float(project.contract_value) if project.contract_value is not None else None,
        "currency": project.currency,
        "location": project.location,
        "language": project.language,
        "status": project.status,
    }

    language = project.language or "en"
    comparison = compare_quotes(coverage_dicts, quote_dicts)
    summary = summarize_comparison(comparison)
    draft_result = await draft_recommendation_email(
        project_dict, comparison, summary, language
    )

    recipient = (body.recipient_email if body else None)

    # Create BrokerRecommendation row (status='draft')
    recommendation = BrokerRecommendation(
        tenant_id=user.tenant_id,
        broker_project_id=project_id,
        subject=draft_result["subject"],
        body=draft_result["body_html"],
        recipient_email=recipient,
        status="draft",
        created_by_user_id=user.sub,
    )
    db.add(recommendation)

    # Transition project status
    project.status = "recommended"
    project.updated_at = datetime.now(timezone.utc)

    activity = BrokerActivity(
        tenant_id=user.tenant_id,
        broker_project_id=project.id,
        activity_type="recommendation_drafted",
        actor_type="system",
        description=f"AI recommendation drafted for {project.name}",
        metadata_={"recipient": recipient},
    )
    db.add(activity)
    await db.commit()
    await db.refresh(recommendation)

    return {
        "recommendation_id": str(recommendation.id),
        "subject": recommendation.subject,
        "body_html": recommendation.body,
        "recipient": recipient,
        "status": recommendation.status,
    }


# ---------------------------------------------------------------------------
# PUT /broker/recommendations/{recommendation_id}  -- edit draft
# ---------------------------------------------------------------------------


@recommendations_router.put("/recommendations/{recommendation_id}")
async def edit_recommendation(
    recommendation_id: UUID,
    body: EditRecommendationBody,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Edit a recommendation draft before sending."""
    result = await db.execute(
        select(BrokerRecommendation).where(
            BrokerRecommendation.id == recommendation_id,
            BrokerRecommendation.tenant_id == user.tenant_id,
        )
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if rec.status in ("sent", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot edit recommendation with status '{rec.status}'",
        )

    if body.subject is not None:
        rec.subject = body.subject
    if body.body is not None:
        rec.body = body.body
    if body.recipient_email is not None:
        rec.recipient_email = body.recipient_email
    rec.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(rec)

    return {
        "recommendation_id": str(rec.id),
        "subject": rec.subject,
        "body_html": rec.body,
        "recipient": rec.recipient_email,
        "status": rec.status,
    }


# ---------------------------------------------------------------------------
# POST /broker/recommendations/{recommendation_id}/approve-send
# ---------------------------------------------------------------------------


@recommendations_router.post("/recommendations/{recommendation_id}/approve-send")
async def approve_send_recommendation(
    recommendation_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Approve and send recommendation email, save to document library.

    Transitions recommendation status: draft -> approved -> sent (in one step).
    Transitions project status: recommended -> delivered.
    """
    result = await db.execute(
        select(BrokerRecommendation).where(
            BrokerRecommendation.id == recommendation_id,
            BrokerRecommendation.tenant_id == user.tenant_id,
        )
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if rec.status not in ("draft", "approved"):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot send recommendation with status '{rec.status}'",
        )

    if not rec.recipient_email:
        raise HTTPException(
            status_code=422,
            detail="No recipient email set. Edit the recommendation to add a recipient.",
        )

    # Load project for status transition
    project_result = await db.execute(
        select(BrokerProject).where(
            BrokerProject.id == rec.broker_project_id,
            BrokerProject.deleted_at.is_(None),
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Associated project not found")

    email_result = await send_email_as_user(
        db=db,
        tenant_id=user.tenant_id,
        to=rec.recipient_email,
        subject=rec.subject or "Insurance Recommendation",
        body_html=rec.body,
    )

    now = datetime.now(timezone.utc)

    # Update recommendation status
    rec.status = "sent"
    rec.sent_at = now
    rec.approved_by_user_id = user.sub
    rec.approved_at = now
    rec.updated_at = now

    # Transition project to delivered
    validate_transition(project.status, "delivered", client_id=project.client_id)
    project.status = "delivered"
    project.updated_at = now

    # Save recommendation to document library
    doc = Document(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        title=f"Recommendation - {project.name}",
        document_type="broker-recommendation",
        module="broker",
        tags=["broker", "recommendation", project.project_type or "insurance"],
        metadata_={
            "broker_project_id": str(project.id),
            "broker_recommendation_id": str(rec.id),
            "sent_to": rec.recipient_email,
            "sent_at": now.isoformat(),
        },
    )
    db.add(doc)
    await db.flush()

    activity = BrokerActivity(
        tenant_id=user.tenant_id,
        broker_project_id=project.id,
        activity_type="recommendation_sent",
        actor_type="user",
        description=f"Recommendation sent to {rec.recipient_email}",
        metadata_={
            "recipient": rec.recipient_email,
            "document_id": str(doc.id),
            "email_provider": email_result.get("provider") if isinstance(email_result, dict) else None,
        },
    )
    db.add(activity)
    await db.commit()

    return {
        "status": "sent",
        "sent_at": now.isoformat(),
        "document_id": str(doc.id),
        "recommendation_id": str(rec.id),
    }
