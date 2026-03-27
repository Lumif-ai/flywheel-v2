"""Outreach Activities, Pipeline, and Graduation REST API.

Endpoints (no prefix on router — paths are explicit per group):

Outreach CRUD (API-03):
- GET  /accounts/{account_id}/outreach   -- list outreach for an account
- POST /accounts/{account_id}/outreach   -- create outreach activity
- PATCH /outreach/{outreach_id}          -- update outreach activity (auto-graduation on replied)

Pipeline view:
- GET /pipeline/                         -- prospect accounts sorted by fit_score

Graduation:
- POST /accounts/{account_id}/graduate   -- manually graduate prospect to engaged

AUTO-01: When outreach status is set to 'replied', the parent account auto-graduates
from 'prospect' to 'engaged' and a ContextEntry is logged.
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Account, AccountContact, ContextEntry, OutreachActivity

# No prefix — endpoints use full path segments directly
router = APIRouter(tags=["outreach"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class OutreachResponse(BaseModel):
    id: UUID
    account_id: UUID
    contact_id: UUID | None
    channel: str
    direction: str
    status: str
    subject: str | None
    body_preview: str | None
    sent_at: datetime.datetime | None
    metadata: dict
    created_at: datetime.datetime


class CreateOutreachRequest(BaseModel):
    channel: str
    direction: str
    status: str = "sent"
    subject: str | None = None
    body_preview: str | None = None
    sent_at: datetime.datetime | None = None
    contact_id: UUID | None = None
    metadata: dict | None = None


class UpdateOutreachRequest(BaseModel):
    status: str | None = None
    subject: str | None = None
    body_preview: str | None = None
    sent_at: datetime.datetime | None = None
    contact_id: UUID | None = None
    metadata: dict | None = None


class PipelineItem(BaseModel):
    id: UUID
    name: str
    domain: str | None
    fit_score: float | None
    fit_tier: str | None
    status: str
    last_interaction_at: datetime.datetime | None
    outreach_count: int
    last_outreach_status: str | None
    days_since_last_outreach: int | None
    created_at: datetime.datetime
    primary_contact_name: str | None = None
    primary_contact_title: str | None = None
    primary_contact_email: str | None = None
    primary_contact_linkedin: str | None = None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _outreach_to_dict(o: OutreachActivity) -> dict:
    return {
        "id": o.id,
        "account_id": o.account_id,
        "contact_id": o.contact_id,
        "channel": o.channel,
        "direction": o.direction,
        "status": o.status,
        "subject": o.subject,
        "body_preview": o.body_preview,
        "sent_at": o.sent_at,
        "metadata": o.metadata_,
        "created_at": o.created_at,
    }


def _account_to_dict(a: Account) -> dict:
    return {
        "id": a.id,
        "tenant_id": a.tenant_id,
        "name": a.name,
        "normalized_name": a.normalized_name,
        "domain": a.domain,
        "status": a.status,
        "fit_score": float(a.fit_score) if a.fit_score is not None else None,
        "fit_tier": a.fit_tier,
        "intel": a.intel,
        "source": a.source,
        "last_interaction_at": a.last_interaction_at,
        "next_action_due": a.next_action_due,
        "next_action_type": a.next_action_type,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


# ---------------------------------------------------------------------------
# Shared business logic
# ---------------------------------------------------------------------------


async def _graduate_account(
    db: AsyncSession,
    account: Account,
    user: TokenPayload,
    source_label: str,
    outreach_id: UUID | None = None,
) -> None:
    """Graduate a prospect account to engaged and log a ContextEntry.

    Called by both PATCH /outreach/{id} (source_label='auto:graduation') and
    POST /accounts/{id}/graduate (source_label='manual:graduation').

    Assumes the caller has already verified account.status == 'prospect'.
    The caller is responsible for committing after this function returns.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    today = datetime.date.today()

    account.status = "engaged"
    account.graduated_at = now
    account.updated_at = now

    if outreach_id is not None:
        content = (
            f"Account '{account.name}' auto-graduated from prospect to engaged "
            f"after reply received on outreach {outreach_id}"
        )
    else:
        content = (
            f"Account '{account.name}' manually graduated from prospect to engaged"
        )

    entry = ContextEntry(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        file_name="account-events",
        source=source_label,
        content=content,
        date=today,
        account_id=account.id,
    )
    db.add(entry)


# ---------------------------------------------------------------------------
# Outreach CRUD (API-03)
# ---------------------------------------------------------------------------


@router.get("/accounts/{account_id}/outreach")
async def list_outreach(
    account_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """List outreach activities for an account."""
    # Verify account exists
    account_row = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    account = account_row.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Fetch outreach activities ordered by sent_at DESC
    result = await db.execute(
        select(OutreachActivity)
        .where(OutreachActivity.account_id == account_id)
        .order_by(OutreachActivity.sent_at.desc().nulls_last())
        .offset(offset)
        .limit(limit)
    )
    activities = result.scalars().all()

    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(OutreachActivity).where(
            OutreachActivity.account_id == account_id
        )
    )
    total = count_result.scalar_one()

    return {
        "items": [_outreach_to_dict(a) for a in activities],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.post("/accounts/{account_id}/outreach", status_code=status.HTTP_201_CREATED)
async def create_outreach(
    account_id: UUID,
    body: CreateOutreachRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Create an outreach activity for an account."""
    now = datetime.datetime.now(datetime.timezone.utc)

    # Verify account exists
    account_row = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    account = account_row.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # If contact_id provided, verify it belongs to this account
    if body.contact_id is not None:
        contact_row = await db.execute(
            select(AccountContact).where(
                AccountContact.id == body.contact_id,
                AccountContact.account_id == account_id,
            )
        )
        if contact_row.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact does not belong to this account",
            )

    sent_at = body.sent_at or now

    activity = OutreachActivity(
        tenant_id=user.tenant_id,
        account_id=account_id,
        contact_id=body.contact_id,
        channel=body.channel,
        direction=body.direction,
        status=body.status,
        subject=body.subject,
        body_preview=body.body_preview,
        sent_at=sent_at,
        metadata_=body.metadata or {},
    )
    db.add(activity)

    # Update last_interaction_at if sent_at is more recent
    if account.last_interaction_at is None or sent_at > account.last_interaction_at:
        account.last_interaction_at = sent_at
        account.updated_at = now

    # AUTO-01: auto-graduate if status is replied
    if body.status == "replied" and account.status == "prospect":
        await db.flush()  # ensure activity.id is populated
        await _graduate_account(db, account, user, "auto:graduation", outreach_id=activity.id)

    await db.commit()
    await db.refresh(activity)
    return _outreach_to_dict(activity)


@router.patch("/outreach/{outreach_id}")
async def update_outreach(
    outreach_id: UUID,
    body: UpdateOutreachRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Update an outreach activity. AUTO-01: setting status to 'replied' auto-graduates account."""
    # Fetch outreach activity
    result = await db.execute(
        select(OutreachActivity).where(OutreachActivity.id == outreach_id)
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach not found")

    # Apply non-None fields
    if body.status is not None:
        activity.status = body.status
    if body.subject is not None:
        activity.subject = body.subject
    if body.body_preview is not None:
        activity.body_preview = body.body_preview
    if body.sent_at is not None:
        activity.sent_at = body.sent_at
    if body.contact_id is not None:
        activity.contact_id = body.contact_id
    if body.metadata is not None:
        activity.metadata_ = body.metadata

    # AUTO-01: if status is being updated to 'replied', check parent account
    if body.status == "replied":
        account_result = await db.execute(
            select(Account).where(Account.id == activity.account_id)
        )
        account = account_result.scalar_one_or_none()
        if account is not None and account.status == "prospect":
            await _graduate_account(db, account, user, "auto:graduation", outreach_id=outreach_id)

    await db.commit()
    await db.refresh(activity)
    return _outreach_to_dict(activity)


# ---------------------------------------------------------------------------
# Pipeline view
# ---------------------------------------------------------------------------


@router.get("/pipeline/")
async def get_pipeline(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    fit_tier: list[str] | None = Query(default=None),
    outreach_status: list[str] | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Cross-account pipeline view: prospect accounts sorted by fit_score with outreach stats."""
    now = datetime.datetime.now(datetime.timezone.utc)

    # Expand comma-separated values in list params
    # Supports both repeated params (?fit_tier=A&fit_tier=B) and comma-separated (?fit_tier=A,B)
    def _expand(values: list[str]) -> list[str]:
        expanded: list[str] = []
        for v in values:
            expanded.extend(v.split(","))
        return expanded

    fit_tier_expanded = _expand(fit_tier) if fit_tier is not None else None
    outreach_status_expanded = _expand(outreach_status) if outreach_status is not None else None

    # Subquery: outreach stats per account (avoids N+1)
    # Computes: count, last sent_at, status of most-recent outreach
    outreach_stats = (
        select(
            OutreachActivity.account_id.label("account_id"),
            func.count(OutreachActivity.id).label("outreach_count"),
            func.max(OutreachActivity.sent_at).label("last_sent_at"),
        )
        .group_by(OutreachActivity.account_id)
        .subquery("outreach_stats")
    )

    # Subquery: status of the most recent outreach per account
    # Uses a lateral-style approach: rank by sent_at and pick rank=1
    ranked_outreach = (
        select(
            OutreachActivity.account_id.label("account_id"),
            OutreachActivity.status.label("last_status"),
            func.row_number()
            .over(
                partition_by=OutreachActivity.account_id,
                order_by=OutreachActivity.sent_at.desc().nulls_last(),
            )
            .label("rn"),
        )
        .subquery("ranked_outreach")
    )

    last_status_sq = (
        select(
            ranked_outreach.c.account_id,
            ranked_outreach.c.last_status,
        )
        .where(ranked_outreach.c.rn == 1)
        .subquery("last_status_sq")
    )

    # Primary contact subquery (first contact per account, avoids N+1)
    primary_contact_sq = (
        select(
            AccountContact.account_id,
            AccountContact.name.label("contact_name"),
            AccountContact.title.label("contact_title"),
            AccountContact.email.label("contact_email"),
            AccountContact.linkedin_url.label("contact_linkedin"),
        )
        .distinct(AccountContact.account_id)
        .order_by(AccountContact.account_id, AccountContact.created_at.asc())
        .subquery("primary_contact")
    )

    # Main query: prospects only, left join outreach stats and primary contact
    stmt = (
        select(
            Account,
            func.coalesce(outreach_stats.c.outreach_count, 0).label("outreach_count"),
            outreach_stats.c.last_sent_at.label("last_sent_at"),
            last_status_sq.c.last_status.label("last_outreach_status"),
            primary_contact_sq.c.contact_name.label("primary_contact_name"),
            primary_contact_sq.c.contact_title.label("primary_contact_title"),
            primary_contact_sq.c.contact_email.label("primary_contact_email"),
            primary_contact_sq.c.contact_linkedin.label("primary_contact_linkedin"),
        )
        .outerjoin(outreach_stats, outreach_stats.c.account_id == Account.id)
        .outerjoin(last_status_sq, last_status_sq.c.account_id == Account.id)
        .outerjoin(primary_contact_sq, primary_contact_sq.c.account_id == Account.id)
        .where(Account.status == "prospect")
        .order_by(Account.fit_score.desc().nulls_last())
        .offset(offset)
        .limit(limit)
    )

    if fit_tier_expanded is not None:
        stmt = stmt.where(Account.fit_tier.in_(fit_tier_expanded))
    if outreach_status_expanded is not None:
        stmt = stmt.where(last_status_sq.c.last_status.in_(outreach_status_expanded))
    if search is not None:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Account.name.ilike(pattern) | Account.domain.ilike(pattern)
        )

    result = await db.execute(stmt)
    rows = result.all()

    # Count total prospects (with same filters applied for accurate pagination)
    count_stmt = (
        select(func.count())
        .select_from(Account)
        .outerjoin(last_status_sq, last_status_sq.c.account_id == Account.id)
        .where(Account.status == "prospect")
    )
    if fit_tier_expanded is not None:
        count_stmt = count_stmt.where(Account.fit_tier.in_(fit_tier_expanded))
    if outreach_status_expanded is not None:
        count_stmt = count_stmt.where(last_status_sq.c.last_status.in_(outreach_status_expanded))
    if search is not None:
        pattern = f"%{search}%"
        count_stmt = count_stmt.where(
            Account.name.ilike(pattern) | Account.domain.ilike(pattern)
        )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar_one()

    items = []
    for row in rows:
        account = row[0]
        outreach_count = row[1] or 0
        last_sent_at = row[2]
        last_outreach_status = row[3]
        primary_contact_name = row[4]
        primary_contact_title = row[5]
        primary_contact_email = row[6]
        primary_contact_linkedin = row[7]

        # Compute days_since_last_outreach
        if last_sent_at is not None:
            # Ensure timezone-aware comparison
            if last_sent_at.tzinfo is None:
                last_sent_at = last_sent_at.replace(tzinfo=datetime.timezone.utc)
            delta = now - last_sent_at
            days_since = delta.days
        else:
            days_since = None

        items.append(
            PipelineItem(
                id=account.id,
                name=account.name,
                domain=account.domain,
                fit_score=float(account.fit_score) if account.fit_score is not None else None,
                fit_tier=account.fit_tier,
                status=account.status,
                last_interaction_at=account.last_interaction_at,
                outreach_count=int(outreach_count),
                last_outreach_status=last_outreach_status,
                days_since_last_outreach=days_since,
                created_at=account.created_at,
                primary_contact_name=primary_contact_name,
                primary_contact_title=primary_contact_title,
                primary_contact_email=primary_contact_email,
                primary_contact_linkedin=primary_contact_linkedin,
            )
        )

    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# Manual graduation
# ---------------------------------------------------------------------------


@router.post("/accounts/{account_id}/graduate")
async def graduate_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Manually graduate an account from prospect to engaged."""
    result = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if account.status != "prospect":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is not a prospect",
        )

    await _graduate_account(db, account, user, "manual:graduation")
    await db.commit()
    await db.refresh(account)
    return _account_to_dict(account)
