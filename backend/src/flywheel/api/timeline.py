"""Account Timeline and Pulse Signals REST API — API-04 and API-05.

2 endpoints:
- GET /accounts/{account_id}/timeline  -- unified chronological feed (outreach + context)
- GET /pulse/                          -- prioritized actionable signal feed
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Account, ContextEntry, OutreachActivity

router = APIRouter(tags=["timeline"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TimelineItem(BaseModel):
    id: str
    type: str  # "outreach" | "context"
    date: str | None
    title: str
    summary: str | None
    # Outreach-specific
    status: str | None = None
    channel: str | None = None
    direction: str | None = None
    # Context-specific
    source: str | None = None
    confidence: str | None = None


class TimelineResponse(BaseModel):
    items: list[TimelineItem]
    total: int
    offset: int
    limit: int
    has_more: bool


class PulseSignal(BaseModel):
    id: str
    type: str  # "reply_received" | "followup_overdue" | "bump_suggested"
    priority: int
    account_id: str
    account_name: str
    title: str
    detail: str
    created_at: str


class PulseResponse(BaseModel):
    items: list[PulseSignal]
    total: int


# ---------------------------------------------------------------------------
# Helper: build timeline item dicts
# ---------------------------------------------------------------------------


def _outreach_to_item(row: OutreachActivity) -> dict:
    title = row.subject or f"{row.channel} {row.direction}"
    date_val = row.sent_at or row.created_at
    return {
        "id": str(row.id),
        "type": "outreach",
        "date": date_val.isoformat() if date_val else None,
        "title": title,
        "summary": row.body_preview,
        "status": row.status,
        "channel": row.channel,
        "direction": row.direction,
        "source": None,
        "confidence": None,
    }


def _context_to_item(row: ContextEntry) -> dict:
    date_val = row.created_at
    return {
        "id": str(row.id),
        "type": "context",
        "date": date_val.isoformat() if date_val else None,
        "title": row.file_name,
        "summary": row.content[:200] if row.content else None,
        "status": None,
        "channel": None,
        "direction": None,
        "source": row.source,
        "confidence": row.confidence,
    }


# ---------------------------------------------------------------------------
# Endpoint 1: GET /accounts/{account_id}/timeline  (API-04)
# ---------------------------------------------------------------------------


@router.get(
    "/accounts/{account_id}/timeline",
    response_model=TimelineResponse,
    summary="Unified chronological timeline for an account",
)
async def get_account_timeline(
    account_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> TimelineResponse:
    """Return a unified chronological feed for an account.

    Interleaves outreach activities and context entries sorted by date DESC.
    Documents are excluded in v1 (no direct account_id FK on uploaded_files).
    """
    tenant_id = user.tenant_id

    # Verify the account belongs to this tenant
    account_check = await db.execute(
        select(Account.id).where(
            Account.id == account_id,
            Account.tenant_id == tenant_id,
        )
    )
    if account_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Fetch all outreach activities for this account
    outreach_rows = (
        await db.execute(
            select(OutreachActivity).where(
                OutreachActivity.account_id == account_id,
                OutreachActivity.tenant_id == tenant_id,
            )
        )
    ).scalars().all()

    # Fetch all context entries for this account (non-deleted)
    context_rows = (
        await db.execute(
            select(ContextEntry).where(
                ContextEntry.account_id == account_id,
                ContextEntry.tenant_id == tenant_id,
                ContextEntry.deleted_at.is_(None),
            )
        )
    ).scalars().all()

    # Map to unified dicts
    items: list[dict] = []
    for row in outreach_rows:
        items.append(_outreach_to_item(row))
    for row in context_rows:
        items.append(_context_to_item(row))

    # Sort by date DESC (None dates go last)
    def _sort_key(item: dict) -> tuple:
        d = item["date"]
        if d is None:
            return (0, "")
        return (1, d)

    items.sort(key=_sort_key, reverse=True)

    total = len(items)
    page = items[offset : offset + limit]

    return TimelineResponse(
        items=[TimelineItem(**i) for i in page],
        total=total,
        offset=offset,
        limit=limit,
        has_more=(offset + limit) < total,
    )


# ---------------------------------------------------------------------------
# Endpoint 2: GET /pulse/  (API-05)
# ---------------------------------------------------------------------------


@router.get(
    "/pulse/",
    response_model=PulseResponse,
    summary="Prioritized pulse signals computed from live CRM data",
)
async def get_pulse(
    limit: int = Query(20, ge=1, le=50),
    type: str | None = Query(None, description="Filter to a specific signal type"),
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> PulseResponse:
    """Compute and return prioritized actionable signals.

    Signal types (in priority order):
    1. reply_received  — outreach with status='replied' in the last 7 days
    2. followup_overdue — accounts with next_action_due in the past
    3. bump_suggested  — prospect accounts with no reply and stale outreach (>14 days)
    """
    tenant_id = user.tenant_id
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff_7d = now - datetime.timedelta(days=7)
    cutoff_14d = now - datetime.timedelta(days=14)

    signals: list[dict] = []

    # -------------------------------------------------------------------------
    # Signal 1: reply_received (priority 1)
    # -------------------------------------------------------------------------
    if type is None or type == "reply_received":
        reply_rows = (
            await db.execute(
                select(OutreachActivity, Account)
                .join(Account, OutreachActivity.account_id == Account.id)
                .where(
                    OutreachActivity.tenant_id == tenant_id,
                    OutreachActivity.status == "replied",
                    OutreachActivity.created_at >= cutoff_7d,
                )
                .order_by(OutreachActivity.created_at.desc())
            )
        ).all()

        for oa, acct in reply_rows:
            signals.append(
                {
                    "id": f"reply_{oa.id}",
                    "type": "reply_received",
                    "priority": 1,
                    "account_id": str(acct.id),
                    "account_name": acct.name,
                    "title": f"{acct.name} replied",
                    "detail": oa.subject or oa.channel,
                    "created_at": oa.created_at.isoformat(),
                }
            )

    # -------------------------------------------------------------------------
    # Signal 2: followup_overdue (priority 2)
    # -------------------------------------------------------------------------
    if type is None or type == "followup_overdue":
        overdue_rows = (
            await db.execute(
                select(Account).where(
                    Account.tenant_id == tenant_id,
                    Account.next_action_due.isnot(None),
                    Account.next_action_due < now,
                    Account.status.in_(["prospect", "engaged"]),
                )
                .order_by(Account.next_action_due.asc())
            )
        ).scalars().all()

        for acct in overdue_rows:
            signals.append(
                {
                    "id": f"overdue_{acct.id}",
                    "type": "followup_overdue",
                    "priority": 2,
                    "account_id": str(acct.id),
                    "account_name": acct.name,
                    "title": f"Follow-up overdue: {acct.name}",
                    "detail": acct.next_action_type or "Follow up needed",
                    "created_at": acct.next_action_due.isoformat(),
                }
            )

    # -------------------------------------------------------------------------
    # Signal 3: bump_suggested (priority 3)
    # -------------------------------------------------------------------------
    if type is None or type == "bump_suggested":
        # Subquery: latest sent_at per account
        latest_outreach = (
            select(
                OutreachActivity.account_id,
                func.max(OutreachActivity.sent_at).label("latest_sent"),
            )
            .where(OutreachActivity.tenant_id == tenant_id)
            .group_by(OutreachActivity.account_id)
            .subquery()
        )

        # Subquery: accounts that have received at least one reply
        replied = (
            select(OutreachActivity.account_id)
            .where(
                OutreachActivity.tenant_id == tenant_id,
                OutreachActivity.status == "replied",
            )
            .distinct()
            .subquery()
        )

        bump_rows = (
            await db.execute(
                select(Account, latest_outreach.c.latest_sent)
                .join(latest_outreach, Account.id == latest_outreach.c.account_id)
                .outerjoin(replied, Account.id == replied.c.account_id)
                .where(
                    Account.tenant_id == tenant_id,
                    Account.status == "prospect",
                    replied.c.account_id.is_(None),
                    latest_outreach.c.latest_sent < cutoff_14d,
                )
                .order_by(latest_outreach.c.latest_sent.asc())
            )
        ).all()

        for acct, latest_sent in bump_rows:
            days_since = (now - latest_sent.replace(tzinfo=datetime.timezone.utc)).days
            signals.append(
                {
                    "id": f"bump_{acct.id}",
                    "type": "bump_suggested",
                    "priority": 3,
                    "account_id": str(acct.id),
                    "account_name": acct.name,
                    "title": f"Bump {acct.name}?",
                    "detail": f"No activity in {days_since} days",
                    "created_at": latest_sent.isoformat(),
                }
            )

    # Sort by priority ASC, then created_at DESC within same priority
    # Negate created_at string doesn't work directly, so use tuple with inverted flag
    signals.sort(key=lambda s: (s["priority"], s["created_at"]), reverse=False)
    # Stable secondary sort: for each priority group, sort created_at descending.
    # Since Python sort is stable, sort by created_at DESC first, then by priority ASC.
    signals.sort(key=lambda s: s["created_at"], reverse=True)
    signals.sort(key=lambda s: s["priority"])

    total = len(signals)
    page = signals[:limit]

    return PulseResponse(
        items=[PulseSignal(**s) for s in page],
        total=total,
    )
