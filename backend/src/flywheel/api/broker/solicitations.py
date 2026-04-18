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

from flywheel.api.broker._enforcement import (
    SubsidyDecision,
    raise_endpoint_deprecated,
    require_subsidy_decision,
)
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
) -> list[dict[str, Any]]:
    """List all solicitation drafts for a project.

    Returns a flat array (not wrapped in {"items": [...]}).
    """
    result = await db.execute(
        select(SolicitationDraft, CarrierConfig.carrier_name)
        .outerjoin(CarrierConfig, SolicitationDraft.carrier_config_id == CarrierConfig.id)
        .where(
            SolicitationDraft.broker_project_id == project_id,
            SolicitationDraft.tenant_id == user.tenant_id,
        ).order_by(SolicitationDraft.created_at.desc())
    )
    rows = result.all()
    return [_solicitation_draft_to_dict(row[0], carrier_name=row[1]) for row in rows]


def _solicitation_draft_to_dict(
    d: SolicitationDraft, carrier_name: str | None = None
) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "broker_project_id": str(d.broker_project_id),
        "carrier_config_id": str(d.carrier_config_id),
        "carrier_name": carrier_name,
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
# POST /broker/projects/{project_id}/draft-solicitations — DEPRECATED
# (Phase 150.1 Plan 04)
#
# Flipped to HTTP 410 Gone. Replaced by Pattern 3a pair:
#   POST /api/v1/broker/extract/solicitation-draft
#   POST /api/v1/broker/save/solicitation-draft
# ---------------------------------------------------------------------------


@solicitations_router.post("/projects/{project_id}/draft-solicitations")
async def draft_solicitations_deprecated(project_id: UUID):
    """DEPRECATED (Phase 150.1): returns 410 Gone.

    Use POST /api/v1/broker/extract/solicitation-draft +
    POST /api/v1/broker/save/solicitation-draft (Pattern 3a).
    """
    raise_endpoint_deprecated(operation="solicitation-draft")


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

    # Transition project status to soliciting if still at gaps_identified
    project_result = await db.execute(
        select(BrokerProject).where(BrokerProject.id == draft.broker_project_id)
    )
    project = project_result.scalar_one_or_none()
    if project and project.status == "gaps_identified":
        project.status = "soliciting"

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


# ===========================================================================
# Phase 150.1 Plan 02 — Pattern 3a extract/save endpoint pair for solicitation-draft.
#
# Replaces backend env-var-leak AsyncAnthropic() at solicitation_drafter.py:135.
# Blocker-2 invariant: BOTH endpoints carry require_subsidy_decision.
# ===========================================================================


class ExtractSolicitationDraftBody(BaseModel):
    project_id: UUID
    carrier_config_id: UUID
    api_key: str | None = None  # BYOK per _enforcement.py


class ExtractSolicitationDraftResponse(BaseModel):
    prompt: str
    tool_schema: dict
    documents: list[dict]
    metadata: dict


class SaveSolicitationDraftBody(BaseModel):
    project_id: UUID
    carrier_config_id: UUID
    tool_schema_version: str = "1.0"
    api_key: str | None = None
    subject: str
    body_html: str


@solicitations_router.post(
    "/extract/solicitation-draft",
    response_model=ExtractSolicitationDraftResponse,
)
async def extract_solicitation_draft(
    body: ExtractSolicitationDraftBody,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
    _subsidy: SubsidyDecision = Depends(require_subsidy_decision),
) -> ExtractSolicitationDraftResponse:
    """Return {prompt, tool_schema, documents, metadata} for solicitation drafting."""
    from flywheel.engines.solicitation_drafter import (
        SOLICITATION_TOOL,
        build_solicitation_prompt,
    )

    project_result = await db.execute(
        select(BrokerProject).where(
            BrokerProject.id == body.project_id,
            BrokerProject.tenant_id == user.tenant_id,
            BrokerProject.deleted_at.is_(None),
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    carrier_result = await db.execute(
        select(CarrierConfig).where(
            CarrierConfig.id == body.carrier_config_id,
            CarrierConfig.tenant_id == user.tenant_id,
            CarrierConfig.is_active.is_(True),
        )
    )
    carrier = carrier_result.scalar_one_or_none()
    if carrier is None:
        raise HTTPException(status_code=404, detail="Carrier not found or inactive")

    # Load coverages for prompt rendering.
    cov_result = await db.execute(
        select(ProjectCoverage).where(
            ProjectCoverage.broker_project_id == body.project_id
        )
    )
    coverages_list = [_coverage_to_dict(c) for c in cov_result.scalars().all()]

    # Load primary submissions email (same helper as legacy endpoint).
    contact_emails = await _load_carrier_contacts(
        db, user.tenant_id, [body.carrier_config_id]
    )
    carrier_email = contact_emails.get(body.carrier_config_id)

    project_dict = _project_to_dict(project)
    carrier_dict = _carrier_to_dict(carrier, email=carrier_email)
    language = project.language or "en"

    prompt = build_solicitation_prompt(
        project_dict, carrier_dict, coverages_list, [], language
    )

    return ExtractSolicitationDraftResponse(
        prompt=prompt,
        tool_schema=SOLICITATION_TOOL,
        documents=[],  # solicitation drafting needs no PDFs attached
        metadata={
            "project_id": str(project.id),
            "carrier_config_id": str(carrier.id),
            "carrier_name": carrier.carrier_name,
            "carrier_email": carrier_email,
            "language": language,
            "coverage_count": len(coverages_list),
            "tool_schema_version": "1.0",
        },
    )


@solicitations_router.post("/save/solicitation-draft")
async def save_solicitation_draft(
    body: SaveSolicitationDraftBody,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
    _subsidy: SubsidyDecision = Depends(require_subsidy_decision),  # Blocker-2: MANDATORY
):
    """Persist Claude's solicitation-draft tool_use output."""
    if body.tool_schema_version != "1.0":
        raise HTTPException(
            status_code=400,
            detail=(
                f"tool_schema_version mismatch: got {body.tool_schema_version}, "
                f"expected 1.0"
            ),
        )

    from flywheel.engines.solicitation_drafter import persist_solicitation_draft

    # Verify project and carrier ownership.
    project_result = await db.execute(
        select(BrokerProject).where(
            BrokerProject.id == body.project_id,
            BrokerProject.tenant_id == user.tenant_id,
            BrokerProject.deleted_at.is_(None),
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Look up carrier primary submissions email for sent_to_email field.
    contact_emails = await _load_carrier_contacts(
        db, user.tenant_id, [body.carrier_config_id]
    )
    carrier_email = contact_emails.get(body.carrier_config_id)

    draft = await persist_solicitation_draft(
        db,
        user.tenant_id,
        body.project_id,
        body.carrier_config_id,
        tool_use_output={"subject": body.subject, "body_html": body.body_html},
        sent_to_email=carrier_email,
        created_by_user_id=user.sub,
    )
    await db.commit()
    await db.refresh(draft)

    return {
        "solicitation_draft_id": str(draft.id),
        "project_id": str(body.project_id),
        "carrier_config_id": str(body.carrier_config_id),
        "subject": draft.subject,
        "status": draft.status,
        "sent_to_email": draft.sent_to_email,
    }
