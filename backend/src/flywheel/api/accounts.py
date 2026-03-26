"""Accounts and Contacts REST API — API-01 and API-02.

8 endpoints:
- GET    /accounts/                          -- paginated, filterable, searchable, sortable list
- GET    /accounts/{account_id}             -- full detail with contacts + timeline preview
- POST   /accounts/                          -- create account with normalized_name dedup
- PATCH  /accounts/{account_id}             -- update account fields
- GET    /accounts/{account_id}/contacts    -- list contacts for an account
- POST   /accounts/{account_id}/contacts    -- create a contact under an account
- PATCH  /accounts/{account_id}/contacts/{contact_id}  -- update a contact
- DELETE /accounts/{account_id}/contacts/{contact_id}  -- remove a contact
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Account, AccountContact, ContextEntry, OutreachActivity
from flywheel.utils.normalize import normalize_company_name

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class AccountListItem(BaseModel):
    id: str
    name: str
    domain: str | None
    status: str
    fit_score: float | None
    fit_tier: str | None
    contact_count: int
    last_interaction_at: str | None
    next_action_due: str | None
    next_action_type: str | None
    source: str


class AccountDetail(AccountListItem):
    intel: dict
    contacts: list[dict]
    recent_timeline: list[dict]


class CreateAccountRequest(BaseModel):
    name: str
    domain: str | None = None
    status: str = "prospect"
    fit_score: float | None = None
    fit_tier: str | None = None
    intel: dict | None = None
    source: str


class UpdateAccountRequest(BaseModel):
    name: str | None = None
    domain: str | None = None
    status: str | None = None
    fit_score: float | None = None
    fit_tier: str | None = None
    intel: dict | None = None
    next_action_due: str | None = None
    next_action_type: str | None = None


class ContactResponse(BaseModel):
    id: str
    name: str
    email: str | None
    title: str | None
    role_in_deal: str | None
    linkedin_url: str | None
    notes: str | None
    source: str
    created_at: str | None


class CreateContactRequest(BaseModel):
    name: str
    email: str | None = None
    title: str | None = None
    role_in_deal: str | None = None
    linkedin_url: str | None = None
    notes: str | None = None
    source: str


class UpdateContactRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    title: str | None = None
    role_in_deal: str | None = None
    linkedin_url: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _account_to_list_item(a: Account, contact_count: int) -> dict:
    """Serialize an Account ORM object to AccountListItem dict shape."""
    return {
        "id": str(a.id),
        "name": a.name,
        "domain": a.domain,
        "status": a.status,
        "fit_score": float(a.fit_score) if a.fit_score is not None else None,
        "fit_tier": a.fit_tier,
        "contact_count": contact_count,
        "last_interaction_at": a.last_interaction_at.isoformat() if a.last_interaction_at else None,
        "next_action_due": a.next_action_due.isoformat() if a.next_action_due else None,
        "next_action_type": a.next_action_type,
        "source": a.source,
    }


def _account_to_detail(a: Account, contacts: list, timeline: list) -> dict:
    """Serialize an Account ORM object to AccountDetail dict shape."""
    base = _account_to_list_item(a, len(contacts))
    return {
        **base,
        "intel": a.intel or {},
        "contacts": contacts,
        "recent_timeline": timeline,
    }


def _contact_to_dict(c: AccountContact) -> dict:
    """Serialize an AccountContact ORM object to ContactResponse dict shape."""
    return {
        "id": str(c.id),
        "name": c.name,
        "email": c.email,
        "title": c.title,
        "role_in_deal": c.role_in_deal,
        "linkedin_url": c.linkedin_url,
        "notes": c.notes,
        "source": c.source,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _paginated_response(items: list, total: int, offset: int, limit: int) -> dict:
    """Build a standard paginated response envelope."""
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


# ---------------------------------------------------------------------------
# GET /accounts/
# ---------------------------------------------------------------------------


_SORT_COLUMNS = {
    "name": Account.name,
    "fit_score": Account.fit_score,
    "last_interaction_at": Account.last_interaction_at,
    "next_action_due": Account.next_action_due,
    "created_at": Account.created_at,
}


@router.get("/")
async def list_accounts(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Paginated, filterable, searchable, sortable list of accounts."""
    limit = min(limit, 100)

    # Validate sort_by
    sort_col = _SORT_COLUMNS.get(sort_by, Account.created_at)
    order_expr = sort_col.desc() if sort_dir.lower() != "asc" else sort_col.asc()

    # Base query
    base = select(Account)

    if status is not None:
        base = base.where(Account.status == status)

    if search is not None:
        pattern = f"%{search}%"
        base = base.where(
            Account.name.ilike(pattern) | Account.domain.ilike(pattern)
        )

    # Count total matching rows
    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch page with contact counts via correlated subquery
    contact_count_subq = (
        select(func.count())
        .where(AccountContact.account_id == Account.id)
        .correlate(Account)
        .scalar_subquery()
    )

    data_stmt = (
        select(Account, contact_count_subq.label("contact_count"))
        .order_by(order_expr)
        .offset(offset)
        .limit(limit)
    )

    if status is not None:
        data_stmt = data_stmt.where(Account.status == status)
    if search is not None:
        pattern = f"%{search}%"
        data_stmt = data_stmt.where(
            Account.name.ilike(pattern) | Account.domain.ilike(pattern)
        )

    result = await db.execute(data_stmt)
    rows = result.all()

    items = [_account_to_list_item(row[0], row[1] or 0) for row in rows]

    return _paginated_response(items, total, offset, limit)


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}
# ---------------------------------------------------------------------------


@router.get("/{account_id}")
async def get_account(
    account_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Full account detail with contacts and recent timeline entries."""
    result = await db.execute(
        select(Account)
        .where(Account.id == account_id)
        .options(selectinload(Account.contacts))
    )
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    contacts = [_contact_to_dict(c) for c in account.contacts]

    # Build timeline: 3 separate queries, merge+sort in Python
    timeline_entries: list[dict] = []

    # 1. Outreach activities
    outreach_result = await db.execute(
        select(OutreachActivity)
        .where(OutreachActivity.account_id == account_id)
        .order_by(OutreachActivity.sent_at.desc().nulls_last(), OutreachActivity.created_at.desc())
        .limit(10)
    )
    for act in outreach_result.scalars().all():
        entry_date = act.sent_at or act.created_at
        timeline_entries.append({
            "id": str(act.id),
            "type": "outreach",
            "title": act.subject or f"{act.channel} {act.direction}",
            "date": entry_date.isoformat() if entry_date else None,
            "summary": act.body_preview,
            "channel": act.channel,
            "direction": act.direction,
        })

    # 2. Context entries linked to this account
    context_result = await db.execute(
        select(ContextEntry)
        .where(
            ContextEntry.account_id == account_id,
            ContextEntry.deleted_at.is_(None),
        )
        .order_by(ContextEntry.created_at.desc())
        .limit(10)
    )
    for entry in context_result.scalars().all():
        timeline_entries.append({
            "id": str(entry.id),
            "type": "context",
            "title": entry.detail or entry.file_name,
            "date": entry.created_at.isoformat() if entry.created_at else None,
            "summary": entry.content[:200] if entry.content else None,
            "file_name": entry.file_name,
        })

    # Sort merged timeline by date descending, take top 10
    def _sort_key(item: dict):
        d = item.get("date")
        if d is None:
            return ""
        return d

    timeline_entries.sort(key=_sort_key, reverse=True)
    recent_timeline = timeline_entries[:10]

    return _account_to_detail(account, contacts, recent_timeline)


# ---------------------------------------------------------------------------
# POST /accounts/
# ---------------------------------------------------------------------------


@router.post("/", status_code=201)
async def create_account(
    body: CreateAccountRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new account with normalized_name for dedup."""
    normalized_name = normalize_company_name(body.name)

    new_account = Account(
        tenant_id=user.tenant_id,
        name=body.name,
        normalized_name=normalized_name,
        domain=body.domain,
        status=body.status,
        fit_score=body.fit_score,
        fit_tier=body.fit_tier,
        intel=body.intel or {},
        source=body.source,
    )
    db.add(new_account)
    await db.flush()
    await db.refresh(new_account)
    await db.commit()

    return _account_to_list_item(new_account, 0)


# ---------------------------------------------------------------------------
# PATCH /accounts/{account_id}
# ---------------------------------------------------------------------------


@router.patch("/{account_id}")
async def update_account(
    account_id: UUID,
    body: UpdateAccountRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update account fields. Recomputes normalized_name if name changes."""
    result = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    if body.name is not None:
        account.name = body.name
        account.normalized_name = normalize_company_name(body.name)
    if body.domain is not None:
        account.domain = body.domain
    if body.status is not None:
        account.status = body.status
    if body.fit_score is not None:
        account.fit_score = body.fit_score
    if body.fit_tier is not None:
        account.fit_tier = body.fit_tier
    if body.intel is not None:
        account.intel = body.intel
    if body.next_action_due is not None:
        # Accept ISO string or None
        account.next_action_due = datetime.datetime.fromisoformat(body.next_action_due)
    if body.next_action_type is not None:
        account.next_action_type = body.next_action_type

    account.updated_at = datetime.datetime.now(datetime.timezone.utc)

    await db.commit()
    await db.refresh(account)

    # Get contact count for response
    cc_result = await db.execute(
        select(func.count()).where(AccountContact.account_id == account_id)
    )
    contact_count = cc_result.scalar() or 0

    return _account_to_list_item(account, contact_count)


# ---------------------------------------------------------------------------
# GET /accounts/{account_id}/contacts
# ---------------------------------------------------------------------------


@router.get("/{account_id}/contacts")
async def list_contacts(
    account_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all contacts for an account."""
    # Verify account exists
    acc_result = await db.execute(
        select(Account.id).where(Account.id == account_id)
    )
    if acc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Account not found")

    result = await db.execute(
        select(AccountContact)
        .where(AccountContact.account_id == account_id)
        .order_by(AccountContact.created_at.asc())
    )
    contacts = result.scalars().all()

    return {"items": [_contact_to_dict(c) for c in contacts]}


# ---------------------------------------------------------------------------
# POST /accounts/{account_id}/contacts
# ---------------------------------------------------------------------------


@router.post("/{account_id}/contacts", status_code=201)
async def create_contact(
    account_id: UUID,
    body: CreateContactRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a contact under an account."""
    # Verify account exists
    acc_result = await db.execute(
        select(Account.id).where(Account.id == account_id)
    )
    if acc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Account not found")

    new_contact = AccountContact(
        tenant_id=user.tenant_id,
        account_id=account_id,
        name=body.name,
        email=body.email,
        title=body.title,
        role_in_deal=body.role_in_deal,
        linkedin_url=body.linkedin_url,
        notes=body.notes,
        source=body.source,
    )
    db.add(new_contact)
    await db.flush()
    await db.refresh(new_contact)
    await db.commit()

    return _contact_to_dict(new_contact)


# ---------------------------------------------------------------------------
# PATCH /accounts/{account_id}/contacts/{contact_id}
# ---------------------------------------------------------------------------


@router.patch("/{account_id}/contacts/{contact_id}")
async def update_contact(
    account_id: UUID,
    contact_id: UUID,
    body: UpdateContactRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a contact. Verifies the contact belongs to the given account."""
    result = await db.execute(
        select(AccountContact).where(
            AccountContact.id == contact_id,
            AccountContact.account_id == account_id,
        )
    )
    contact = result.scalar_one_or_none()

    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    if body.name is not None:
        contact.name = body.name
    if body.email is not None:
        contact.email = body.email
    if body.title is not None:
        contact.title = body.title
    if body.role_in_deal is not None:
        contact.role_in_deal = body.role_in_deal
    if body.linkedin_url is not None:
        contact.linkedin_url = body.linkedin_url
    if body.notes is not None:
        contact.notes = body.notes

    contact.updated_at = datetime.datetime.now(datetime.timezone.utc)

    await db.commit()
    await db.refresh(contact)

    return _contact_to_dict(contact)


# ---------------------------------------------------------------------------
# DELETE /accounts/{account_id}/contacts/{contact_id}
# ---------------------------------------------------------------------------


@router.delete("/{account_id}/contacts/{contact_id}", status_code=200)
async def delete_contact(
    account_id: UUID,
    contact_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Hard-delete a contact from an account."""
    result = await db.execute(
        select(AccountContact).where(
            AccountContact.id == contact_id,
            AccountContact.account_id == account_id,
        )
    )
    contact = result.scalar_one_or_none()

    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    await db.delete(contact)
    await db.commit()

    return {"deleted": True, "id": str(contact_id)}
