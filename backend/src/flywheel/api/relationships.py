"""Relationships REST API.

Endpoints (no prefix on router — paths are explicit):

RAPI-01: GET  /relationships/              -- list graduated accounts (partition predicate enforced)
RAPI-02: GET  /relationships/{id}          -- detail with contacts, timeline, cached ai_summary
RAPI-03: PATCH /relationships/{id}/type   -- update relationship_type (validated)
RAPI-04: POST  /relationships/{id}/graduate -- graduate a prospect into relationships

PARTITION CONTRACT: Every query targeting graduated accounts MUST include
`Account.graduated_at.isnot(None)`. The only exception is POST /graduate,
which intentionally targets un-graduated accounts.

AI SUMMARY CONTRACT: GET endpoints return `ai_summary` from the column as-is
(may be NULL). LLM synthesis is NEVER triggered on read.
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Account, AccountContact, ContextEntry

# No prefix — endpoints use full path segments directly
router = APIRouter(tags=["relationships"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_TYPES: frozenset[str] = frozenset({"prospect", "customer", "advisor", "investor"})


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RelationshipListItem(BaseModel):
    id: UUID
    name: str
    domain: str | None
    relationship_type: list[str]
    entity_level: str
    relationship_status: str
    ai_summary: str | None
    signal_count: int
    primary_contact_name: str | None
    last_interaction_at: datetime.datetime | None
    created_at: datetime.datetime


class ContactItem(BaseModel):
    id: UUID
    name: str
    title: str | None
    email: str | None
    linkedin_url: str | None
    role: str | None
    created_at: datetime.datetime


class TimelineItem(BaseModel):
    id: UUID
    source: str
    content: str
    date: datetime.date
    created_at: datetime.datetime


class RelationshipDetail(RelationshipListItem):
    ai_summary_updated_at: datetime.datetime | None
    contacts: list[ContactItem]
    recent_timeline: list[TimelineItem]
    commitments: list  # reserved for future use


class UpdateTypeRequest(BaseModel):
    types: list[str]

    @field_validator("types")
    @classmethod
    def validate_types(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one relationship type required")
        unknown = [t for t in v if t not in ALLOWED_TYPES]
        if unknown:
            allowed_str = ", ".join(sorted(ALLOWED_TYPES))
            raise ValueError(f"Unknown type: {unknown[0]}. Allowed: {allowed_str}")
        return v


class GraduateRequest(BaseModel):
    types: list[str]
    entity_level: str = "company"

    @field_validator("types")
    @classmethod
    def validate_types(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one relationship type required")
        unknown = [t for t in v if t not in ALLOWED_TYPES]
        if unknown:
            allowed_str = ", ".join(sorted(ALLOWED_TYPES))
            raise ValueError(f"Unknown type: {unknown[0]}. Allowed: {allowed_str}")
        return v


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _account_to_list_item(
    account: Account,
    signal_count: int,
    primary_contact_name: str | None,
) -> dict:
    return {
        "id": account.id,
        "name": account.name,
        "domain": account.domain,
        "relationship_type": account.relationship_type or [],
        "entity_level": account.entity_level,
        "relationship_status": account.relationship_status,
        "ai_summary": account.ai_summary,
        "signal_count": signal_count,
        "primary_contact_name": primary_contact_name,
        "last_interaction_at": account.last_interaction_at,
        "created_at": account.created_at,
    }


# ---------------------------------------------------------------------------
# RAPI-01: List graduated accounts
# ---------------------------------------------------------------------------


@router.get("/relationships/")
async def list_relationships(
    type: str | None = Query(default=None, description="Filter by relationship type"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """List graduated accounts. PARTITION PREDICATE: graduated_at IS NOT NULL always applied."""
    # Correlated subquery: primary contact name (earliest created)
    primary_contact_sq = (
        select(AccountContact.name)
        .where(AccountContact.account_id == Account.id)
        .correlate(Account)
        .order_by(AccountContact.created_at.asc())
        .limit(1)
        .scalar_subquery()
    )

    # Correlated subquery: signal count (context entries not deleted)
    signal_count_sq = (
        select(func.count())
        .select_from(ContextEntry)
        .where(
            ContextEntry.account_id == Account.id,
            ContextEntry.deleted_at.is_(None),
        )
        .correlate(Account)
        .scalar_subquery()
    )

    # Base query — PARTITION PREDICATE ALWAYS PRESENT
    base_where = [
        Account.tenant_id == user.tenant_id,
        Account.graduated_at.isnot(None),
    ]

    # Optional type filter
    if type is not None and type in ALLOWED_TYPES:
        base_where.append(Account.relationship_type.any(type))

    # Count query
    count_stmt = (
        select(func.count())
        .select_from(Account)
        .where(*base_where)
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar_one()

    # Data query
    data_stmt = (
        select(
            Account,
            signal_count_sq.label("signal_count"),
            primary_contact_sq.label("primary_contact_name"),
        )
        .where(*base_where)
        .order_by(Account.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(data_stmt)
    rows = result.all()

    items = []
    for row in rows:
        account = row[0]
        sc = row[1] or 0
        pc = row[2]
        items.append(_account_to_list_item(account, sc, pc))

    return {"items": items, "total": total, "offset": offset, "limit": limit}


# ---------------------------------------------------------------------------
# RAPI-02: Relationship detail
# ---------------------------------------------------------------------------


@router.get("/relationships/{id}")
async def get_relationship(
    id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Get relationship detail. Returns cached ai_summary — never calls LLM."""
    # Fetch with contacts eagerly loaded — PARTITION PREDICATE enforced
    result = await db.execute(
        select(Account)
        .where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
            Account.graduated_at.isnot(None),
        )
        .options(selectinload(Account.contacts))
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # Correlated subquery for signal count
    signal_count_result = await db.execute(
        select(func.count())
        .select_from(ContextEntry)
        .where(
            ContextEntry.account_id == id,
            ContextEntry.deleted_at.is_(None),
        )
    )
    signal_count = signal_count_result.scalar_one() or 0

    # Primary contact name (first created)
    primary_contact_name: str | None = None
    if account.contacts:
        sorted_contacts = sorted(account.contacts, key=lambda c: c.created_at)
        primary_contact_name = sorted_contacts[0].name

    # Recent timeline: last 10 context entries
    timeline_result = await db.execute(
        select(ContextEntry)
        .where(
            ContextEntry.account_id == id,
            ContextEntry.deleted_at.is_(None),
        )
        .order_by(ContextEntry.date.desc())
        .limit(10)
    )
    timeline_entries = timeline_result.scalars().all()

    # Serialize contacts
    contacts = [
        {
            "id": c.id,
            "name": c.name,
            "title": c.title,
            "email": c.email,
            "linkedin_url": c.linkedin_url,
            "role": c.role_in_deal,
            "created_at": c.created_at,
        }
        for c in account.contacts
    ]

    # Serialize timeline
    recent_timeline = [
        {
            "id": e.id,
            "source": e.source,
            "content": e.content,
            "date": e.date,
            "created_at": e.created_at,
        }
        for e in timeline_entries
    ]

    return {
        **_account_to_list_item(account, signal_count, primary_contact_name),
        "ai_summary_updated_at": account.ai_summary_updated_at,
        "contacts": contacts,
        "recent_timeline": recent_timeline,
        "commitments": [],
    }


# ---------------------------------------------------------------------------
# RAPI-03: Update relationship type
# ---------------------------------------------------------------------------


@router.patch("/relationships/{id}/type")
async def update_relationship_type(
    id: UUID,
    body: UpdateTypeRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Update relationship_type. Validates non-empty and allowed values. PARTITION PREDICATE enforced."""
    now = datetime.datetime.now(datetime.timezone.utc)

    # Fetch account — PARTITION PREDICATE enforced
    result = await db.execute(
        select(Account).where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
            Account.graduated_at.isnot(None),
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    account.relationship_type = body.types
    account.updated_at = now

    await db.commit()
    await db.refresh(account)

    return {
        "id": account.id,
        "name": account.name,
        "relationship_type": account.relationship_type,
        "updated_at": account.updated_at,
    }


# ---------------------------------------------------------------------------
# RAPI-04: Graduate a prospect into relationships
# ---------------------------------------------------------------------------


@router.post("/relationships/{id}/graduate", status_code=status.HTTP_200_OK)
async def graduate_to_relationship(
    id: UUID,
    body: GraduateRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Graduate an account into the relationships surface.

    NO graduated_at partition predicate here — we're targeting un-graduated accounts.
    Returns 409 if already graduated.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    today = datetime.date.today()

    # Fetch account (no graduated_at filter — intentionally targets un-graduated)
    result = await db.execute(
        select(Account).where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    if account.graduated_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already graduated",
        )

    # Graduate: set timestamp, types, level
    account.graduated_at = now
    account.relationship_type = body.types
    account.entity_level = body.entity_level or "company"
    account.updated_at = now

    # Log ContextEntry for audit trail
    entry = ContextEntry(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        file_name="account-events",
        source="manual:graduate",
        content=(
            f"Account '{account.name}' graduated into relationships "
            f"with types: {', '.join(body.types)}"
        ),
        date=today,
        account_id=account.id,
    )
    db.add(entry)

    await db.commit()
    await db.refresh(account)

    return {
        "id": account.id,
        "name": account.name,
        "domain": account.domain,
        "relationship_type": account.relationship_type,
        "entity_level": account.entity_level,
        "graduated_at": account.graduated_at,
        "updated_at": account.updated_at,
    }
