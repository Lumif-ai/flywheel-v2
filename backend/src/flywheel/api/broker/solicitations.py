"""Broker solicitation draft endpoints.

Endpoints:
  GET  /projects/{id}/solicitation-drafts  -- list drafts for a project (API-10)
  POST /projects/{id}/draft-solicitations  -- batch create SolicitationDraft rows
  PUT  /solicitation-drafts/{id}           -- edit a draft before sending
  POST /solicitation-drafts/{id}/approve   -- approve without sending (WRK-03)
  POST /solicitation-drafts/{id}/approve-send -- send the draft email
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
    CarrierConfig,
    CarrierContact,
    ProjectCoverage,
    SolicitationDraft,
)
from flywheel.engines.solicitation_drafter import draft_solicitation_email
from flywheel.services.email_dispatch import send_email_as_user

logger = logging.getLogger(__name__)

solicitations_router = APIRouter(tags=["broker"])

_EMAIL_RE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class DraftSolicitationsBody(BaseModel):
    carrier_config_ids: list[UUID]


class EditSolicitationDraftBody(BaseModel):
    subject: str | None = None
    body: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_carrier_contacts(
    db: AsyncSession,
    tenant_id: UUID,
    carrier_config_ids: list[UUID],
) -> dict[UUID, str | None]:
    """Batch load primary submissions emails to avoid N+1 queries."""
    result = await db.execute(
        select(CarrierContact.carrier_config_id, CarrierContact.email).where(
            CarrierContact.carrier_config_id.in_(carrier_config_ids),
            CarrierContact.is_primary.is_(True),
            CarrierContact.role == "submissions",
            CarrierContact.email.is_not(None),
        )
    )
    return {row.carrier_config_id: row.email for row in result}


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


def _project_to_dict(p: BrokerProject) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "name": p.name,
        "project_type": p.project_type,
        "description": p.description,
        "contract_value": float(p.contract_value) if p.contract_value is not None else None,
        "currency": p.currency,
        "location": p.location,
        "language": p.language,
        "status": p.status,
    }


def _carrier_to_dict(c: CarrierConfig, email: str | None = None) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "carrier_name": c.carrier_name,
        "carrier_type": c.carrier_type,
        "submission_method": c.submission_method,
        "portal_url": c.portal_url,
        "email_address": email,  # from carrier_contacts, not carrier_configs
        "coverage_types": c.coverage_types or [],
        "regions": c.regions or [],
    }


# ---------------------------------------------------------------------------
# GET /broker/projects/{project_id}/solicitation-drafts  (API-10)
# ---------------------------------------------------------------------------


@solicitations_router.get("/projects/{project_id}/solicitation-drafts")
async def list_solicitation_drafts(
    project_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """List all solicitation drafts for a project."""
    result = await db.execute(
        select(SolicitationDraft).where(
            SolicitationDraft.broker_project_id == project_id,
            SolicitationDraft.tenant_id == user.tenant_id,
        ).order_by(SolicitationDraft.created_at.desc())
    )
    drafts = result.scalars().all()
    return {"items": [_solicitation_draft_to_dict(d) for d in drafts]}


def _solicitation_draft_to_dict(d: SolicitationDraft) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "broker_project_id": str(d.broker_project_id),
        "carrier_config_id": str(d.carrier_config_id),
        "carrier_quote_id": str(d.carrier_quote_id) if d.carrier_quote_id else None,
        "subject": d.subject,
        "body": d.body,
        "status": d.status,
        "sent_to_email": d.sent_to_email,
        "approved_at": d.approved_at.isoformat() if d.approved_at else None,
        "sent_at": d.sent_at.isoformat() if d.sent_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


# ---------------------------------------------------------------------------
# POST /broker/projects/{project_id}/draft-solicitations
# ---------------------------------------------------------------------------


@solicitations_router.post("/projects/{project_id}/draft-solicitations")
async def draft_solicitations(
    project_id: UUID,
    body: DraftSolicitationsBody,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Batch-draft solicitation emails — creates SolicitationDraft rows."""
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

    # Load coverages
    cov_result = await db.execute(
        select(ProjectCoverage).where(
            ProjectCoverage.broker_project_id == project_id
        )
    )
    coverages_list = [_coverage_to_dict(c) for c in cov_result.scalars().all()]

    # Batch load carrier contacts (avoids N+1)
    contact_emails = await _load_carrier_contacts(
        db, user.tenant_id, body.carrier_config_ids
    )

    drafts: list[dict] = []
    portal_submissions: list[dict] = []
    skipped: list[dict] = []

    for carrier_config_id in body.carrier_config_ids:
        carrier_result = await db.execute(
            select(CarrierConfig).where(
                CarrierConfig.id == carrier_config_id,
                CarrierConfig.tenant_id == user.tenant_id,
                CarrierConfig.is_active.is_(True),
            )
        )
        carrier = carrier_result.scalar_one_or_none()
        if carrier is None:
            skipped.append({
                "carrier_config_id": str(carrier_config_id),
                "reason": "Carrier not found or inactive",
            })
            continue

        method = carrier.submission_method or "email"
        carrier_email = contact_emails.get(carrier_config_id)

        # Email track
        if method in ("email", "both"):
            if not carrier_email or not _EMAIL_RE.match(carrier_email):
                skipped.append({
                    "carrier_config_id": str(carrier_config_id),
                    "carrier_name": carrier.carrier_name,
                    "reason": "No primary submissions contact email configured",
                })
                if method == "email":
                    continue
            else:
                # Check for existing active draft (unique partial index guard)
                existing_result = await db.execute(
                    select(SolicitationDraft).where(
                        SolicitationDraft.broker_project_id == project_id,
                        SolicitationDraft.carrier_config_id == carrier_config_id,
                        SolicitationDraft.status.in_(["draft", "pending", "approved"]),
                    )
                )
                existing_draft = existing_result.scalar_one_or_none()

                if existing_draft:
                    # Return existing draft rather than creating duplicate
                    drafts.append({
                        "solicitation_draft_id": str(existing_draft.id),
                        "carrier_name": carrier.carrier_name,
                        "carrier_config_id": str(carrier_config_id),
                        "submission_method": method,
                        "subject": existing_draft.subject,
                        "body": existing_draft.body,
                        "status": existing_draft.status,
                        "reused": True,
                    })
                    continue

                # Create SolicitationDraft (not CarrierQuote)
                draft = SolicitationDraft(
                    tenant_id=user.tenant_id,
                    broker_project_id=project_id,
                    carrier_config_id=carrier_config_id,
                    status="draft",
                    sent_to_email=carrier_email,
                    created_by_user_id=user.sub,
                )
                db.add(draft)
                await db.flush()

                # Generate AI draft
                project_dict = _project_to_dict(project)
                carrier_dict = _carrier_to_dict(carrier, email=carrier_email)
                language = project.language or "en"

                try:
                    ai_result = await draft_solicitation_email(
                        project_dict, carrier_dict, coverages_list, [], language
                    )
                    draft.subject = ai_result.get("subject", "")
                    draft.body = ai_result.get("body_html", "")
                    draft.status = "pending"
                except Exception as exc:
                    logger.warning(
                        "AI draft failed for carrier %s: %s", carrier.carrier_name, exc
                    )
                    draft.subject = ""
                    draft.body = ""
                    draft.status = "draft"

                drafts.append({
                    "solicitation_draft_id": str(draft.id),
                    "carrier_name": carrier.carrier_name,
                    "carrier_config_id": str(carrier_config_id),
                    "submission_method": method,
                    "subject": draft.subject,
                    "body": draft.body,
                    "status": draft.status,
                    "documents": [],
                })

        # Portal track
        if method in ("portal", "both"):
            portal_draft = SolicitationDraft(
                tenant_id=user.tenant_id,
                broker_project_id=project_id,
                carrier_config_id=carrier_config_id,
                status="draft",
                created_by_user_id=user.sub,
            )
            db.add(portal_draft)
            await db.flush()

            portal_submissions.append({
                "solicitation_draft_id": str(portal_draft.id),
                "carrier_name": carrier.carrier_name,
                "carrier_config_id": str(carrier_config_id),
                "submission_method": method,
                "portal_url": carrier.portal_url,
                "documents": [],
            })

    await db.commit()

    activity = BrokerActivity(
        tenant_id=user.tenant_id,
        broker_project_id=project_id,
        activity_type="solicitations_drafted",
        actor_type="user",
        metadata_={
            "email_count": len(drafts),
            "portal_count": len(portal_submissions),
            "skipped_count": len(skipped),
        },
    )
    db.add(activity)
    await db.commit()

    return {
        "drafts": drafts,
        "portal_submissions": portal_submissions,
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# PUT /broker/solicitation-drafts/{draft_id}  -- edit draft
# ---------------------------------------------------------------------------


@solicitations_router.put("/solicitation-drafts/{draft_id}")
async def edit_solicitation_draft(
    draft_id: UUID,
    body: EditSolicitationDraftBody,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Edit a solicitation draft subject/body before sending."""
    result = await db.execute(
        select(SolicitationDraft).where(
            SolicitationDraft.id == draft_id,
            SolicitationDraft.tenant_id == user.tenant_id,
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Solicitation draft not found")

    if draft.status in ("sent", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot edit draft with status '{draft.status}'",
        )

    if body.subject is not None:
        draft.subject = body.subject
    if body.body is not None:
        draft.body = body.body
    draft.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(draft)

    return {
        "solicitation_draft_id": str(draft.id),
        "subject": draft.subject,
        "body": draft.body,
        "status": draft.status,
    }


# ---------------------------------------------------------------------------
# POST /broker/solicitation-drafts/{draft_id}/approve  (WRK-03)
# ---------------------------------------------------------------------------


@solicitations_router.post("/solicitation-drafts/{draft_id}/approve")
async def approve_solicitation(
    draft_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Approve a solicitation draft without sending. Sets status to 'approved'."""
    result = await db.execute(
        select(SolicitationDraft).where(
            SolicitationDraft.id == draft_id,
            SolicitationDraft.tenant_id == user.tenant_id,
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Solicitation draft not found")
    if draft.status not in ("draft", "pending"):
        raise HTTPException(status_code=409, detail=f"Cannot approve draft in status '{draft.status}'")
    draft.status = "approved"
    draft.approved_by_user_id = user.sub  # TokenPayload.sub is the user UUID
    draft.approved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": str(draft.id), "status": draft.status, "approved_at": draft.approved_at.isoformat()}


# ---------------------------------------------------------------------------
# POST /broker/solicitation-drafts/{draft_id}/approve-send
# ---------------------------------------------------------------------------


@solicitations_router.post("/solicitation-drafts/{draft_id}/approve-send")
async def approve_send_solicitation(
    draft_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Approve a solicitation draft and send via email_dispatch.

    Body is preserved after send (not nulled) per WRK-08 PII retention requirement.
    """
    result = await db.execute(
        select(SolicitationDraft).where(
            SolicitationDraft.id == draft_id,
            SolicitationDraft.tenant_id == user.tenant_id,
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Solicitation draft not found")

    if draft.status not in ("pending", "approved"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot send draft with status '{draft.status}' — only 'pending' or 'approved' drafts can be sent",
        )

    if not draft.sent_to_email:
        raise HTTPException(
            status_code=422,
            detail="No email address configured for this solicitation draft",
        )

    await send_email_as_user(
        db,
        user.tenant_id,
        to=draft.sent_to_email,
        subject=draft.subject or "",
        body_html=draft.body or "",
    )

    now = datetime.now(timezone.utc)
    draft.status = "sent"
    draft.sent_at = now
    draft.approved_by_user_id = user.sub
    draft.approved_at = draft.approved_at or now
    draft.updated_at = now
    # NOTE: draft.body is intentionally NOT cleared (WRK-08 PII retention)

    activity = BrokerActivity(
        tenant_id=user.tenant_id,
        broker_project_id=draft.broker_project_id,
        activity_type="solicitation_sent",
        actor_type="user",
        metadata_={"method": "email", "to": draft.sent_to_email, "draft_id": str(draft.id)},
    )
    db.add(activity)
    await db.commit()

    return {
        "solicitation_draft_id": str(draft.id),
        "status": draft.status,
        "sent_at": now.isoformat(),
        "sent_to": draft.sent_to_email,
    }
