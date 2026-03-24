"""Email REST endpoints.

Read endpoints:
- GET  /email/threads                    -- paginated thread summaries sorted by priority
- GET  /email/threads/{thread_id}        -- full thread detail with messages, scores, draft
- POST /email/sync                       -- trigger background Gmail sync
- GET  /email/digest                     -- today's low-priority email summary

Draft lifecycle endpoints:
- POST /email/drafts/{draft_id}/approve  -- approve and send a draft as threaded reply
- POST /email/drafts/{draft_id}/dismiss  -- dismiss a draft (feeds scoring refinement)
- PUT  /email/drafts/{draft_id}          -- edit draft body before approving
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Email, EmailDraft, EmailScore, Integration
from flywheel.db.session import get_session_factory, tenant_session
from flywheel.services.gmail_read import (
    get_message_id_header,
    get_valid_credentials,
    send_reply,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/email", tags=["email"])


# ---------------------------------------------------------------------------
# Pydantic models — read endpoints
# ---------------------------------------------------------------------------


def priority_to_tier(p: int | None) -> str:
    """Map numeric priority to human-readable tier string."""
    if p is None:
        return "unscored"
    if p >= 5:
        return "critical"
    if p >= 4:
        return "high"
    if p >= 3:
        return "medium"
    return "low"


class ThreadSummary(BaseModel):
    thread_id: str
    subject: str | None
    sender_name: str | None
    sender_email: str
    latest_received_at: datetime
    message_count: int
    max_priority: int | None
    priority_tier: str
    has_pending_draft: bool
    draft_id: str | None
    is_read: bool


class ThreadListResponse(BaseModel):
    threads: list[ThreadSummary]
    total: int
    offset: int
    limit: int


class MessageScore(BaseModel):
    priority: int
    category: str
    reasoning: str | None
    suggested_action: str | None
    context_refs: list[dict]


class MessageDetail(BaseModel):
    id: str
    gmail_message_id: str
    sender_email: str
    sender_name: str | None
    subject: str | None
    snippet: str | None
    received_at: datetime
    is_read: bool
    is_replied: bool
    score: MessageScore | None


class DraftDetail(BaseModel):
    id: str
    status: str
    draft_body: str | None
    user_edits: str | None


class ThreadDetailResponse(BaseModel):
    thread_id: str
    subject: str | None
    messages: list[MessageDetail]
    draft: DraftDetail | None
    max_priority: int | None
    priority_tier: str


class SyncResponse(BaseModel):
    message: str
    syncing: bool


class DigestThread(BaseModel):
    thread_id: str
    subject: str | None
    sender_email: str
    category: str | None
    priority: int | None
    message_count: int


class DigestResponse(BaseModel):
    date: str
    threads: list[DigestThread]
    total: int


# ---------------------------------------------------------------------------
# Pydantic models — draft lifecycle
# ---------------------------------------------------------------------------


class EditDraftRequest(BaseModel):
    draft_body: str


class DraftResponse(BaseModel):
    id: UUID
    email_id: UUID
    status: str
    message: str


# ---------------------------------------------------------------------------
# GET /email/threads
# ---------------------------------------------------------------------------


@router.get("/threads", response_model=ThreadListResponse)
async def list_threads(
    priority_min: int | None = Query(default=None, ge=1, le=5),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> ThreadListResponse:
    """Return paginated thread summaries sorted by priority tier then recency.

    Uses a single LEFT JOIN query over emails+scores+pending-drafts then groups
    in Python — no N+1 queries.
    """
    # Single JOIN query — pull all emails with their scores and pending drafts
    stmt = (
        select(Email, EmailScore, EmailDraft)
        .outerjoin(EmailScore, EmailScore.email_id == Email.id)
        .outerjoin(
            EmailDraft,
            and_(
                EmailDraft.email_id == Email.id,
                EmailDraft.status == "pending",
            ),
        )
        .where(Email.tenant_id == user.tenant_id)
        .order_by(Email.received_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Group by gmail_thread_id in Python
    threads: dict[str, dict] = {}
    for email, score, draft in rows:
        tid = email.gmail_thread_id
        if tid not in threads:
            threads[tid] = {
                "thread_id": tid,
                "subject": email.subject,
                "sender_name": email.sender_name,
                "sender_email": email.sender_email,
                "latest_received_at": email.received_at,
                "message_count": 0,
                "max_priority": None,
                "has_pending_draft": False,
                "draft_id": None,
                "is_read": email.is_read,
            }

        t = threads[tid]
        t["message_count"] += 1

        # Track latest message metadata
        if email.received_at > t["latest_received_at"]:
            t["latest_received_at"] = email.received_at
            t["subject"] = email.subject
            t["sender_name"] = email.sender_name
            t["sender_email"] = email.sender_email

        # Max priority across unreplied messages
        if score is not None and not email.is_replied:
            current_max = t["max_priority"]
            if current_max is None or score.priority > current_max:
                t["max_priority"] = score.priority

        # Pending draft
        if draft is not None:
            t["has_pending_draft"] = True
            t["draft_id"] = str(draft.id)

        # Thread is unread if any message is unread
        if not email.is_read:
            t["is_read"] = False

    # Apply priority_min filter
    thread_list = list(threads.values())
    if priority_min is not None:
        thread_list = [
            t for t in thread_list
            if t["max_priority"] is not None and t["max_priority"] >= priority_min
        ]

    # Sort: max_priority DESC (None=0), then latest_received_at DESC
    thread_list.sort(
        key=lambda t: (t["max_priority"] or 0, t["latest_received_at"]),
        reverse=True,
    )

    total = len(thread_list)
    page = thread_list[offset: offset + limit]

    return ThreadListResponse(
        threads=[
            ThreadSummary(
                priority_tier=priority_to_tier(t["max_priority"]),
                **t,
            )
            for t in page
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# GET /email/threads/{thread_id}
# ---------------------------------------------------------------------------


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(
    thread_id: str,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> ThreadDetailResponse:
    """Return full thread detail: all messages with scores and pending draft."""
    stmt = (
        select(Email, EmailScore, EmailDraft)
        .outerjoin(EmailScore, EmailScore.email_id == Email.id)
        .outerjoin(
            EmailDraft,
            and_(
                EmailDraft.email_id == Email.id,
                EmailDraft.status == "pending",
            ),
        )
        .where(
            and_(
                Email.gmail_thread_id == thread_id,
                Email.tenant_id == user.tenant_id,
            )
        )
        .order_by(Email.received_at.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages: list[MessageDetail] = []
    pending_draft: DraftDetail | None = None
    max_priority: int | None = None
    thread_subject: str | None = None

    for email, score, draft in rows:
        # Build MessageScore if score exists
        msg_score: MessageScore | None = None
        if score is not None:
            msg_score = MessageScore(
                priority=score.priority,
                category=score.category,
                reasoning=score.reasoning,
                suggested_action=score.suggested_action,
                context_refs=score.context_refs or [],
            )
            # Track max priority for unreplied messages
            if not email.is_replied:
                if max_priority is None or score.priority > max_priority:
                    max_priority = score.priority

        messages.append(
            MessageDetail(
                id=str(email.id),
                gmail_message_id=email.gmail_message_id,
                sender_email=email.sender_email,
                sender_name=email.sender_name,
                subject=email.subject,
                snippet=email.snippet,
                received_at=email.received_at,
                is_read=email.is_read,
                is_replied=email.is_replied,
                score=msg_score,
            )
        )

        # Capture pending draft (at most one per thread)
        if draft is not None and pending_draft is None:
            pending_draft = DraftDetail(
                id=str(draft.id),
                status=draft.status,
                draft_body=draft.draft_body,
                user_edits=draft.user_edits,
            )

        # Subject from most recent message
        thread_subject = email.subject

    return ThreadDetailResponse(
        thread_id=thread_id,
        subject=thread_subject,
        messages=messages,
        draft=pending_draft,
        max_priority=max_priority,
        priority_tier=priority_to_tier(max_priority),
    )


# ---------------------------------------------------------------------------
# POST /email/sync
# ---------------------------------------------------------------------------


@router.post("/sync", response_model=SyncResponse)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> SyncResponse:
    """Trigger a background Gmail sync for the current tenant.

    Returns immediately — sync runs in the background.
    """
    # Verify the tenant has a connected gmail-read integration
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

    # Snapshot IDs needed by background task (avoid detached instance issues)
    integration_id = integration.id
    tenant_id = str(user.tenant_id)
    user_id = str(user.id)

    async def _run_sync() -> None:
        from flywheel.services.gmail_sync import sync_gmail  # noqa: PLC0415

        factory = get_session_factory()
        async with factory() as superuser_db:
            intg_row_result = await superuser_db.execute(
                select(Integration).where(Integration.id == integration_id)
            )
            intg_row = intg_row_result.scalar_one_or_none()
            if intg_row is None:
                logger.warning("Sync: integration %s not found", integration_id)
                return

        async with tenant_session(factory, tenant_id, user_id) as sync_db:
            # Re-load inside tenant session
            fresh_result = await sync_db.execute(
                select(Integration).where(Integration.id == integration_id)
            )
            fresh_intg = fresh_result.scalar_one_or_none()
            if fresh_intg is None:
                logger.warning("Sync: integration %s not in tenant session", integration_id)
                return
            try:
                await sync_gmail(sync_db, fresh_intg)
            except Exception as exc:  # noqa: BLE001
                logger.error("Background sync failed for tenant=%s: %s", tenant_id, exc)

    background_tasks.add_task(_run_sync)
    return SyncResponse(message="Sync triggered", syncing=True)


# ---------------------------------------------------------------------------
# GET /email/digest
# ---------------------------------------------------------------------------


@router.get("/digest", response_model=DigestResponse)
async def get_digest(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> DigestResponse:
    """Return today's low-priority email summary (priority <= 2).

    Groups by gmail_thread_id, one entry per thread.
    """
    from datetime import date  # noqa: PLC0415

    today_start = datetime.combine(date.today(), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    stmt = (
        select(Email, EmailScore)
        .join(EmailScore, EmailScore.email_id == Email.id)
        .where(
            and_(
                Email.tenant_id == user.tenant_id,
                Email.received_at >= today_start,
                EmailScore.priority <= 2,
            )
        )
        .order_by(Email.received_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Group by thread
    threads: dict[str, dict] = {}
    for email, score in rows:
        tid = email.gmail_thread_id
        if tid not in threads:
            threads[tid] = {
                "thread_id": tid,
                "subject": email.subject,
                "sender_email": email.sender_email,
                "category": score.category,
                "priority": score.priority,
                "message_count": 0,
            }
        threads[tid]["message_count"] += 1

    digest_threads = [DigestThread(**t) for t in threads.values()]

    return DigestResponse(
        date=date.today().isoformat(),
        threads=digest_threads,
        total=len(digest_threads),
    )


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
