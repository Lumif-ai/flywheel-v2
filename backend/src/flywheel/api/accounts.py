"""Accounts and Contacts REST API — Legacy endpoints backed by unified pipeline_entries.

8 endpoints (response shapes preserved from pre-migration):
- GET    /accounts/                          -- paginated, filterable, searchable, sortable list
- GET    /accounts/{account_id}             -- full detail with contacts + timeline preview
- POST   /accounts/                          -- create account (PipelineEntry)
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
from flywheel.db.models import Activity, Contact, ContextEntry, PipelineEntry
from flywheel.utils.normalize import normalize_company_name

router = APIRouter(prefix="/accounts", tags=["accounts"])

# ---------------------------------------------------------------------------
# Stage mapping: unified stages -> old account status
# ---------------------------------------------------------------------------

_STAGE_TO_STATUS = {
    "identified": "prospect",
    "contacted": "engaged",
    "engaged": "engaged",
    "qualified": "engaged",
    "committed": "engaged",
    "closed": "engaged",
}


# ---------------------------------------------------------------------------
# Request / Response models (unchanged contracts)
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
    relationship_status: str | None = None
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
    source: str = "manual"


class UpdateContactRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    title: str | None = None
    role_in_deal: str | None = None
    linkedin_url: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Serialization helpers — map PipelineEntry/Contact to old response shapes
# ---------------------------------------------------------------------------


def _pipeline_to_account_list_item(entry: PipelineEntry, contact_count: int) -> dict:
    """Serialize a PipelineEntry to AccountListItem dict shape."""
    return {
        "id": str(entry.id),
        "name": entry.name,
        "domain": entry.domain,
        "status": _STAGE_TO_STATUS.get(entry.stage, "prospect"),
        "fit_score": float(entry.fit_score) if entry.fit_score is not None else None,
        "fit_tier": entry.fit_tier,
        "contact_count": contact_count,
        "last_interaction_at": entry.last_activity_at.isoformat() if entry.last_activity_at else None,
        "next_action_due": None,  # dropped field
        "next_action_type": None,  # dropped field
        "source": entry.source,
        "relationship_type": entry.relationship_type,
        "entity_level": entry.entity_type,
        "relationship_status": (entry.relationship_type[0] if entry.relationship_type else None),
        "pipeline_stage": entry.stage,
        "visibility": "team",  # hardcoded, field dropped
        "owner_id": str(entry.owner_id) if entry.owner_id else None,
    }


def _pipeline_to_account_detail(
    entry: PipelineEntry, contacts: list, timeline: list
) -> dict:
    """Serialize a PipelineEntry to AccountDetail dict shape."""
    base = _pipeline_to_account_list_item(entry, len(contacts))
    return {
        **base,
        "intel": entry.intel or {},
        "contacts": contacts,
        "recent_timeline": timeline,
        "ai_summary": entry.ai_summary,
        "ai_summary_updated_at": None,  # field not on PipelineEntry
    }


def _contact_to_account_contact(c: Contact) -> dict:
    """Serialize a Contact to the old AccountContact response shape."""
    return {
        "id": str(c.id),
        "name": c.name,
        "email": c.email,
        "title": c.title,
        "role_in_deal": c.role,  # Contact.role maps to old role_in_deal
        "linkedin_url": c.linkedin_url,
        "notes": c.notes,
        "source": "manual",  # Contact has no source field; default
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
    "name": PipelineEntry.name,
    "fit_score": PipelineEntry.fit_score,
    "last_interaction_at": PipelineEntry.last_activity_at,
    "next_action_due": PipelineEntry.created_at,  # fallback (field dropped)
    "created_at": PipelineEntry.created_at,
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
    sort_col = _SORT_COLUMNS.get(sort_by, PipelineEntry.created_at)
    order_expr = sort_col.desc() if sort_dir.lower() != "asc" else sort_col.asc()

    # Base query — exclude retired entries
    base = select(PipelineEntry).where(PipelineEntry.retired_at.is_(None))

    # Map old status filter to stage
    if status is not None:
        # Reverse map: prospect -> identified, engaged -> contacted/engaged/qualified/committed/closed
        if status == "prospect":
            base = base.where(PipelineEntry.stage == "identified")
        elif status == "engaged":
            base = base.where(PipelineEntry.stage.in_(["contacted", "engaged", "qualified", "committed", "closed"]))
        else:
            # Try direct stage match as fallback
            base = base.where(PipelineEntry.stage == status)

    if search is not None:
        pattern = f"%{search}%"
        base = base.where(
            PipelineEntry.name.ilike(pattern) | PipelineEntry.domain.ilike(pattern)
        )

    # Count total matching rows
    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch page with contact counts via correlated subquery
    contact_count_subq = (
        select(func.count())
        .where(Contact.pipeline_entry_id == PipelineEntry.id)
        .correlate(PipelineEntry)
        .scalar_subquery()
    )

    data_stmt = (
        select(PipelineEntry, contact_count_subq.label("contact_count"))
        .where(PipelineEntry.retired_at.is_(None))
        .order_by(order_expr)
        .offset(offset)
        .limit(limit)
    )

    # Re-apply filters to data query
    if status is not None:
        if status == "prospect":
            data_stmt = data_stmt.where(PipelineEntry.stage == "identified")
        elif status == "engaged":
            data_stmt = data_stmt.where(PipelineEntry.stage.in_(["contacted", "engaged", "qualified", "committed", "closed"]))
        else:
            data_stmt = data_stmt.where(PipelineEntry.stage == status)
    if search is not None:
        pattern = f"%{search}%"
        data_stmt = data_stmt.where(
            PipelineEntry.name.ilike(pattern) | PipelineEntry.domain.ilike(pattern)
        )

    result = await db.execute(data_stmt)
    rows = result.all()

    items = [_pipeline_to_account_list_item(row[0], row[1] or 0) for row in rows]

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
        select(PipelineEntry)
        .where(PipelineEntry.id == account_id)
        .options(selectinload(PipelineEntry.contacts))
    )
    entry = result.scalar_one_or_none()

    if entry is None:
        raise HTTPException(status_code=404, detail="Account not found")

    contacts = [_contact_to_account_contact(c) for c in entry.contacts]

    # Build timeline: Activities + ContextEntries, merge+sort in Python
    timeline_entries: list[dict] = []

    # 1. Activities (replaces OutreachActivity)
    activity_result = await db.execute(
        select(Activity)
        .where(Activity.pipeline_entry_id == account_id)
        .order_by(Activity.occurred_at.desc(), Activity.created_at.desc())
        .limit(10)
    )
    for act in activity_result.scalars().all():
        entry_date = act.occurred_at or act.created_at
        timeline_entries.append({
            "id": str(act.id),
            "type": "outreach" if act.type == "message" else act.type,
            "title": act.subject or f"{act.channel or act.type} {act.direction or ''}".strip(),
            "date": entry_date.isoformat() if entry_date else None,
            "summary": act.body_preview,
            "channel": act.channel,
            "direction": act.direction,
        })

    # 2. Context entries linked to this pipeline entry
    context_result = await db.execute(
        select(ContextEntry)
        .where(
            ContextEntry.pipeline_entry_id == account_id,
            ContextEntry.deleted_at.is_(None),
        )
        .order_by(ContextEntry.created_at.desc())
        .limit(10)
    )
    for ce in context_result.scalars().all():
        timeline_entries.append({
            "id": str(ce.id),
            "type": "context",
            "title": ce.detail or ce.file_name,
            "date": ce.created_at.isoformat() if ce.created_at else None,
            "summary": ce.content[:200] if ce.content else None,
            "file_name": ce.file_name,
        })

    # Sort merged timeline by date descending, take top 10
    def _sort_key(item: dict):
        d = item.get("date")
        if d is None:
            return ""
        return d

    timeline_entries.sort(key=_sort_key, reverse=True)
    recent_timeline = timeline_entries[:10]

    return _pipeline_to_account_detail(entry, contacts, recent_timeline)


# ---------------------------------------------------------------------------
# POST /accounts/
# ---------------------------------------------------------------------------


@router.post("/", status_code=201)
async def create_account(
    body: CreateAccountRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new account (PipelineEntry) with normalized_name for dedup."""
    normalized_name = normalize_company_name(body.name)

    # Map old status to stage
    stage_map = {"prospect": "identified", "engaged": "engaged"}
    stage = stage_map.get(body.status, "identified")

    new_entry = PipelineEntry(
        tenant_id=user.tenant_id,
        name=body.name,
        normalized_name=normalized_name,
        domain=body.domain,
        stage=stage,
        fit_score=body.fit_score,
        fit_tier=body.fit_tier,
        intel=body.intel or {},
        source=body.source,
    )
    db.add(new_entry)
    await db.flush()
    await db.refresh(new_entry)
    await db.commit()

    return _pipeline_to_account_list_item(new_entry, 0)


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
        select(PipelineEntry).where(PipelineEntry.id == account_id)
    )
    entry = result.scalar_one_or_none()

    if entry is None:
        raise HTTPException(status_code=404, detail="Account not found")

    if body.name is not None:
        entry.name = body.name
        entry.normalized_name = normalize_company_name(body.name)
    if body.domain is not None:
        entry.domain = body.domain
    if body.status is not None:
        # Map old status to stage
        stage_map = {"prospect": "identified", "engaged": "engaged"}
        entry.stage = stage_map.get(body.status, body.status)
    if body.relationship_status is not None:
        entry.relationship_type = [body.relationship_status]
    if body.fit_score is not None:
        entry.fit_score = body.fit_score
    if body.fit_tier is not None:
        entry.fit_tier = body.fit_tier
    if body.intel is not None:
        entry.intel = body.intel
    # next_action_due / next_action_type are dropped — silently ignored

    entry.updated_at = datetime.datetime.now(datetime.timezone.utc)

    await db.commit()
    await db.refresh(entry)

    # Get contact count for response
    cc_result = await db.execute(
        select(func.count()).where(Contact.pipeline_entry_id == account_id)
    )
    contact_count = cc_result.scalar() or 0

    return _pipeline_to_account_list_item(entry, contact_count)


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
    # Verify entry exists
    acc_result = await db.execute(
        select(PipelineEntry.id).where(PipelineEntry.id == account_id)
    )
    if acc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Account not found")

    result = await db.execute(
        select(Contact)
        .where(Contact.pipeline_entry_id == account_id)
        .order_by(Contact.created_at.asc())
    )
    contacts = result.scalars().all()

    return {"items": [_contact_to_account_contact(c) for c in contacts]}


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
    # Verify entry exists
    acc_result = await db.execute(
        select(PipelineEntry.id).where(PipelineEntry.id == account_id)
    )
    if acc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Account not found")

    new_contact = Contact(
        tenant_id=user.tenant_id,
        pipeline_entry_id=account_id,
        name=body.name,
        email=body.email,
        title=body.title,
        role=body.role_in_deal,  # old role_in_deal maps to Contact.role
        linkedin_url=body.linkedin_url,
        notes=body.notes,
    )
    db.add(new_contact)
    await db.flush()
    await db.refresh(new_contact)
    await db.commit()

    return _contact_to_account_contact(new_contact)


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
        select(Contact).where(
            Contact.id == contact_id,
            Contact.pipeline_entry_id == account_id,
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
        contact.role = body.role_in_deal  # old role_in_deal maps to Contact.role
    if body.linkedin_url is not None:
        contact.linkedin_url = body.linkedin_url
    if body.notes is not None:
        contact.notes = body.notes

    contact.updated_at = datetime.datetime.now(datetime.timezone.utc)

    await db.commit()
    await db.refresh(contact)

    return _contact_to_account_contact(contact)


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
        select(Contact).where(
            Contact.id == contact_id,
            Contact.pipeline_entry_id == account_id,
        )
    )
    contact = result.scalar_one_or_none()

    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    await db.delete(contact)
    await db.commit()

    return {"deleted": True, "id": str(contact_id)}
