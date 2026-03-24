"""Email draft lifecycle REST endpoints.

Endpoints:
- POST /email/drafts/{draft_id}/approve  -- approve and send a draft as threaded reply
- POST /email/drafts/{draft_id}/dismiss  -- dismiss a draft (feeds scoring refinement)
- PUT  /email/drafts/{draft_id}          -- edit draft body before approving
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Email, EmailDraft, Integration
from flywheel.services.gmail_read import (
    get_message_id_header,
    get_valid_credentials,
    send_reply,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/email", tags=["email"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class EditDraftRequest(BaseModel):
    draft_body: str


class DraftResponse(BaseModel):
    id: UUID
    email_id: UUID
    status: str
    message: str


# ---------------------------------------------------------------------------
# POST /email/drafts/{draft_id}/approve
# ---------------------------------------------------------------------------


@router.post("/drafts/{draft_id}/approve", response_model=DraftResponse)
async def approve_draft(
    draft_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> DraftResponse:
    """Approve and send a draft reply as a threaded Gmail reply.

    Sends the draft body (or user_edits if present) as a threaded reply,
    then nulls draft_body (PII minimization) and sets status to 'sent'.
    """
    # Load the draft and verify tenant ownership
    result = await db.execute(
        select(EmailDraft).where(
            and_(
                EmailDraft.id == draft_id,
                EmailDraft.tenant_id == user.tenant_id,
            )
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Draft already {draft.status}",
        )

    if draft.draft_body is None:
        raise HTTPException(
            status_code=400,
            detail="Draft has no body (already sent or nulled)",
        )

    # Load the parent email
    email_result = await db.execute(
        select(Email).where(Email.id == draft.email_id)
    )
    email = email_result.scalar_one_or_none()
    if email is None:
        raise HTTPException(status_code=404, detail="Parent email not found")

    # Load gmail-read integration for this tenant
    intg_result = await db.execute(
        select(Integration).where(
            and_(
                Integration.tenant_id == user.tenant_id,
                Integration.provider == "gmail-read",
                Integration.status == "connected",
            )
        )
    )
    integration = intg_result.scalars().first()
    if integration is None:
        raise HTTPException(
            status_code=400,
            detail="No Gmail read integration connected",
        )

    # Get valid credentials
    creds = await get_valid_credentials(integration)

    # Use user_edits if user edited the draft, otherwise use original draft_body
    reply_body = draft.user_edits if draft.user_edits is not None else draft.draft_body

    # Fetch the Message-ID header on-demand for proper reply threading
    msg_id_header = await get_message_id_header(creds, email.gmail_message_id)
    if msg_id_header is None:
        # Fallback: use gmail_message_id directly (less ideal but functional)
        msg_id_header = email.gmail_message_id

    # Send the reply — do this BEFORE nulling the body so we can retry on failure
    try:
        await send_reply(
            creds,
            to=email.sender_email,
            subject=email.subject or "",
            body_text=reply_body,
            thread_id=email.gmail_thread_id,
            in_reply_to=msg_id_header,
        )
    except Exception as exc:
        # Leave draft in pending state so the user can retry
        logger.error(
            "Gmail send failed for draft_id=%s: %s",
            draft_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Gmail send failed: {exc}",
        ) from exc

    # Success: null body (PII), set status, update timestamp
    draft.draft_body = None
    draft.status = "sent"
    draft.updated_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info("Draft approved and sent: draft_id=%s", draft_id)
    return DraftResponse(
        id=draft.id,
        email_id=draft.email_id,
        status="sent",
        message="Draft sent successfully",
    )


# ---------------------------------------------------------------------------
# POST /email/drafts/{draft_id}/dismiss
# ---------------------------------------------------------------------------


@router.post("/drafts/{draft_id}/dismiss", response_model=DraftResponse)
async def dismiss_draft(
    draft_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> DraftResponse:
    """Dismiss a pending draft. Feeds scoring refinement in Phase 6."""
    result = await db.execute(
        select(EmailDraft).where(
            and_(
                EmailDraft.id == draft_id,
                EmailDraft.tenant_id == user.tenant_id,
            )
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot dismiss a {draft.status} draft",
        )

    draft.status = "dismissed"
    draft.updated_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info("Draft dismissed: draft_id=%s", draft_id)
    return DraftResponse(
        id=draft.id,
        email_id=draft.email_id,
        status="dismissed",
        message="Draft dismissed",
    )


# ---------------------------------------------------------------------------
# PUT /email/drafts/{draft_id}
# ---------------------------------------------------------------------------


@router.put("/drafts/{draft_id}", response_model=DraftResponse)
async def edit_draft(
    draft_id: UUID,
    body: EditDraftRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> DraftResponse:
    """Edit a pending draft body before approving.

    Stores the edited version in user_edits (preserving original draft_body
    for diff analysis in Phase 6). The approve endpoint uses user_edits
    if present.
    """
    result = await db.execute(
        select(EmailDraft).where(
            and_(
                EmailDraft.id == draft_id,
                EmailDraft.tenant_id == user.tenant_id,
            )
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit a {draft.status} draft",
        )

    # Store edited version in user_edits — original draft_body preserved for Phase 6 diff
    draft.user_edits = body.draft_body
    draft.updated_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info("Draft edited: draft_id=%s", draft_id)
    return DraftResponse(
        id=draft.id,
        email_id=draft.email_id,
        status="pending",
        message="Draft updated",
    )
