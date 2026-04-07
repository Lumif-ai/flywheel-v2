"""Leads API — Legacy endpoints backed by unified pipeline_entries.

10 endpoints (response shapes preserved from pre-migration):
- POST   /leads/                                -- upsert lead by normalized name
- GET    /leads/                                 -- list leads with filters
- GET    /leads/pipeline                         -- funnel counts by stage (BEFORE /{lead_id})
- GET    /leads/{lead_id}                        -- lead detail with contacts + messages
- PATCH  /leads/{lead_id}                        -- update lead fields
- POST   /leads/{lead_id}/contacts               -- add contact to lead
- PATCH  /leads/contacts/{contact_id}            -- update contact
- POST   /leads/contacts/{contact_id}/messages   -- create activity (message)
- PATCH  /leads/messages/{message_id}            -- update activity (message)
- POST   /leads/{lead_id}/graduate               -- no-op (unified pipeline)
"""

from __future__ import annotations

import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Activity, Contact, PipelineEntry
from flywheel.utils.normalize import normalize_company_name

router = APIRouter(prefix="/leads", tags=["leads"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STAGE_ORDER = ["identified", "contacted", "engaged", "qualified", "committed", "closed"]
_STAGE_INDEX = {s: i for i, s in enumerate(STAGE_ORDER)}

VALID_CHANNELS = {"email", "linkedin"}
VALID_STATUSES = {"drafted", "sent", "delivered", "replied", "bounced"}
VALID_PURPOSES = {"sales", "fundraising", "advisors", "partnerships"}


def _parse_timestamp(value: str | None) -> datetime.datetime | None:
    """Parse an ISO timestamp string, returning None on invalid input."""
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Invalid timestamp format: {value!r}. Use ISO 8601.",
        )


# ---------------------------------------------------------------------------
# Request / Response models (unchanged contracts)
# ---------------------------------------------------------------------------


class UpsertLeadRequest(BaseModel):
    name: str
    domain: str | None = None
    purpose: list[str] | None = None
    fit_score: float | None = None
    fit_tier: str | None = None
    fit_rationale: str | None = None
    intel: dict | None = None
    source: str = "mcp"
    campaign: str | None = None


class UpdateLeadRequest(BaseModel):
    name: str | None = None
    domain: str | None = None
    purpose: list[str] | None = None
    fit_score: float | None = None
    fit_tier: str | None = None
    fit_rationale: str | None = None
    intel: dict | None = None
    campaign: str | None = None


class AddContactRequest(BaseModel):
    name: str
    email: str | None = None
    title: str | None = None
    linkedin_url: str | None = None
    role: str | None = None
    notes: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v else None


class UpdateContactRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    title: str | None = None
    linkedin_url: str | None = None
    role: str | None = None
    pipeline_stage: str | None = None
    notes: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v else None


class CreateMessageRequest(BaseModel):
    step_number: int
    channel: Literal["email", "linkedin"]
    status: Literal["drafted", "sent", "delivered", "replied", "bounced"] = "drafted"
    subject: str | None = None
    body: str | None = None
    from_email: str | None = None
    drafted_at: str | None = None
    sent_at: str | None = None
    metadata: dict | None = None

    @field_validator("step_number")
    @classmethod
    def positive_step(cls, v: int) -> int:
        if v < 1:
            raise ValueError("step_number must be >= 1")
        return v


class UpdateMessageRequest(BaseModel):
    status: Literal["drafted", "sent", "delivered", "replied", "bounced"] | None = None
    subject: str | None = None
    body: str | None = None
    from_email: str | None = None
    sent_at: str | None = None
    replied_at: str | None = None


# ---------------------------------------------------------------------------
# Serializers — map PipelineEntry/Contact/Activity to old response shapes
# ---------------------------------------------------------------------------


def _pipeline_to_lead_response(
    entry: PipelineEntry,
    contact_count: int,
    include_contacts: bool = False,
) -> dict:
    """Map a PipelineEntry to the old Lead response shape."""
    data = {
        "id": str(entry.id),
        "name": entry.name,
        "domain": entry.domain,
        "purpose": entry.relationship_type or ["sales"],
        "fit_score": float(entry.fit_score) if entry.fit_score is not None else None,
        "fit_tier": entry.fit_tier,
        "fit_rationale": entry.fit_rationale,
        "intel": entry.intel or {},
        "source": entry.source,
        "campaign": None,  # dropped field
        "account_id": None,  # no longer relevant
        "graduated_at": None,  # no longer relevant
        "pipeline_stage": entry.stage,
        "contact_count": contact_count,
        "created_at": entry.created_at.isoformat(),
        "owner_id": str(entry.owner_id) if entry.owner_id else None,
        "updated_at": entry.updated_at.isoformat(),
    }
    if include_contacts and entry.contacts:
        data["contacts"] = [
            _contact_to_lead_contact(c, include_messages=True) for c in entry.contacts
        ]
    elif include_contacts:
        data["contacts"] = []
    return data


def _contact_to_lead_contact(
    contact: Contact, include_messages: bool = False
) -> dict:
    """Map a Contact to the old LeadContact response shape."""
    data = {
        "id": str(contact.id),
        "lead_id": str(contact.pipeline_entry_id) if contact.pipeline_entry_id else None,
        "name": contact.name,
        "email": contact.email,
        "title": contact.title,
        "linkedin_url": contact.linkedin_url,
        "role": contact.role,
        "pipeline_stage": None,  # contacts no longer have individual stages
        "notes": contact.notes,
        "created_at": contact.created_at.isoformat(),
    }
    if include_messages:
        # Messages are now Activities — fetch from pipeline_entry.activities
        # filtered by contact_id. We only include if contacts were eagerly loaded
        # with their activities. For the detail endpoint this is handled separately.
        data["messages"] = []
    return data


def _activity_to_message(act: Activity) -> dict:
    """Map an Activity (type=message) to the old LeadMessage response shape."""
    meta = act.metadata_ or {}
    return {
        "id": str(act.id),
        "step_number": meta.get("step_number", 1),
        "channel": act.channel or "email",
        "status": act.status,
        "subject": act.subject,
        "body": act.body_preview,
        "from_email": meta.get("from_email"),
        "drafted_at": meta.get("drafted_at"),
        "sent_at": meta.get("sent_at"),
        "replied_at": meta.get("replied_at"),
        "metadata": {k: v for k, v in meta.items() if k not in {
            "step_number", "from_email", "drafted_at", "sent_at", "replied_at",
        }},
        "created_at": act.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# 1. POST /leads/ — Upsert lead
# ---------------------------------------------------------------------------


@router.post("/")
async def upsert_lead(
    body: UpsertLeadRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Create or update a lead by normalized company name."""
    now = datetime.datetime.now(datetime.timezone.utc)
    norm = normalize_company_name(body.name)
    if not norm:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid company name")

    result = await db.execute(
        select(PipelineEntry)
        .options(selectinload(PipelineEntry.contacts))
        .where(
            PipelineEntry.tenant_id == user.tenant_id,
            PipelineEntry.owner_id == user.sub,
            PipelineEntry.normalized_name == norm,
        )
    )
    entry = result.scalar_one_or_none()

    if entry:
        # Merge fields
        if body.domain and not entry.domain:
            entry.domain = body.domain
        if body.purpose:
            existing = set(entry.relationship_type or [])
            entry.relationship_type = list(existing | set(body.purpose))
        if body.fit_score is not None and (entry.fit_score is None or body.fit_score > float(entry.fit_score)):
            entry.fit_score = body.fit_score
        if body.fit_tier:
            entry.fit_tier = body.fit_tier
        if body.fit_rationale:
            entry.fit_rationale = body.fit_rationale
        if body.intel:
            merged = {**(entry.intel or {}), **body.intel}
            entry.intel = merged
        entry.updated_at = now
    else:
        entry = PipelineEntry(
            tenant_id=user.tenant_id,
            owner_id=user.sub,
            name=body.name,
            normalized_name=norm,
            domain=body.domain,
            relationship_type=body.purpose or ["sales"],
            fit_score=body.fit_score,
            fit_tier=body.fit_tier,
            fit_rationale=body.fit_rationale,
            intel=body.intel or {},
            source=body.source,
            stage="identified",
        )
        db.add(entry)

    await db.flush()
    await db.refresh(entry, ["contacts"])
    await db.commit()
    contact_count = len(entry.contacts) if entry.contacts else 0
    return _pipeline_to_lead_response(entry, contact_count)


# ---------------------------------------------------------------------------
# 2. GET /leads/ — List leads
# ---------------------------------------------------------------------------


@router.get("/")
async def list_leads(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    pipeline_stage: str | None = Query(default=None),
    fit_tier: str | None = Query(default=None),
    purpose: str | None = Query(default=None),
    search: str | None = Query(default=None),
    campaign: str | None = Query(default=None),
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """List leads with optional filters."""
    # Base query — exclude retired entries
    base = select(PipelineEntry).where(PipelineEntry.retired_at.is_(None))

    if pipeline_stage:
        base = base.where(PipelineEntry.stage == pipeline_stage)
    if fit_tier:
        base = base.where(PipelineEntry.fit_tier == fit_tier)
    if purpose:
        base = base.where(PipelineEntry.relationship_type.contains([purpose]))
    if search:
        pattern = f"%{search}%"
        base = base.where(
            PipelineEntry.name.ilike(pattern) | PipelineEntry.domain.ilike(pattern)
        )
    # campaign filter is a no-op now (field dropped), but we accept it silently

    # Count
    count_stmt = select(func.count()).select_from(base.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar_one()

    # Contact count correlated subquery
    contact_count_subq = (
        select(func.count())
        .where(Contact.pipeline_entry_id == PipelineEntry.id)
        .correlate(PipelineEntry)
        .scalar_subquery()
    )

    data_stmt = (
        select(PipelineEntry, contact_count_subq.label("contact_count"))
        .where(PipelineEntry.retired_at.is_(None))
        .order_by(PipelineEntry.fit_score.desc().nulls_last(), PipelineEntry.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    if pipeline_stage:
        data_stmt = data_stmt.where(PipelineEntry.stage == pipeline_stage)
    if fit_tier:
        data_stmt = data_stmt.where(PipelineEntry.fit_tier == fit_tier)
    if purpose:
        data_stmt = data_stmt.where(PipelineEntry.relationship_type.contains([purpose]))
    if search:
        pattern = f"%{search}%"
        data_stmt = data_stmt.where(
            PipelineEntry.name.ilike(pattern) | PipelineEntry.domain.ilike(pattern)
        )

    result = await db.execute(data_stmt)
    rows = result.all()
    items = [_pipeline_to_lead_response(row[0], row[1] or 0) for row in rows]

    return {"items": items, "total": total, "offset": offset, "limit": limit}


# ---------------------------------------------------------------------------
# 3. GET /leads/pipeline — Funnel counts (BEFORE /{lead_id} to avoid route conflict)
# ---------------------------------------------------------------------------


@router.get("/pipeline")
async def get_pipeline_funnel(
    purpose: str | None = Query(default=None),
    campaign: str | None = Query(default=None),
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Return counts per pipeline stage for funnel visualization."""
    base = select(PipelineEntry.stage, func.count().label("cnt")).where(
        PipelineEntry.retired_at.is_(None)
    )
    if purpose:
        base = base.where(PipelineEntry.relationship_type.contains([purpose]))
    # campaign filter is a no-op now

    base = base.group_by(PipelineEntry.stage)
    result = await db.execute(base)
    rows = result.all()

    counts = {s: 0 for s in STAGE_ORDER}
    total = 0
    for stage_val, cnt in rows:
        if stage_val in counts:
            counts[stage_val] = cnt
        total += cnt

    return {"funnel": counts, "total": total}


# ---------------------------------------------------------------------------
# 4. GET /leads/{lead_id} — Lead detail
# ---------------------------------------------------------------------------


@router.get("/{lead_id}")
async def get_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Get lead with contacts and their message sequences."""
    result = await db.execute(
        select(PipelineEntry)
        .options(
            selectinload(PipelineEntry.contacts),
            selectinload(PipelineEntry.activities),
        )
        .where(PipelineEntry.id == lead_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")

    contact_count = len(entry.contacts) if entry.contacts else 0
    data = _pipeline_to_lead_response(entry, contact_count, include_contacts=True)

    # Attach messages (activities of type=message) to each contact
    message_activities = [a for a in (entry.activities or []) if a.type == "message"]
    # Group by contact_id
    messages_by_contact: dict[UUID | None, list[dict]] = {}
    for act in message_activities:
        cid = act.contact_id
        if cid not in messages_by_contact:
            messages_by_contact[cid] = []
        messages_by_contact[cid].append(_activity_to_message(act))

    for contact_data in data.get("contacts", []):
        cid_str = contact_data.get("id")
        if cid_str:
            try:
                cid = UUID(cid_str)
            except (ValueError, TypeError):
                cid = None
            msgs = messages_by_contact.get(cid, [])
            contact_data["messages"] = sorted(
                msgs, key=lambda m: (m["step_number"], m["channel"])
            )

    return data


# ---------------------------------------------------------------------------
# 5. PATCH /leads/{lead_id} — Update lead
# ---------------------------------------------------------------------------


@router.patch("/{lead_id}")
async def update_lead(
    lead_id: UUID,
    body: UpdateLeadRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Update lead fields."""
    result = await db.execute(
        select(PipelineEntry)
        .options(selectinload(PipelineEntry.contacts))
        .where(PipelineEntry.id == lead_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")

    if body.name is not None:
        entry.name = body.name
        entry.normalized_name = normalize_company_name(body.name)
    if body.domain is not None:
        entry.domain = body.domain
    if body.purpose is not None:
        entry.relationship_type = body.purpose
    if body.fit_score is not None:
        entry.fit_score = body.fit_score
    if body.fit_tier is not None:
        entry.fit_tier = body.fit_tier
    if body.fit_rationale is not None:
        entry.fit_rationale = body.fit_rationale
    if body.intel:
        entry.intel = {**(entry.intel or {}), **body.intel}
    # campaign is a no-op (field dropped)
    entry.updated_at = datetime.datetime.now(datetime.timezone.utc)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A lead with that name already exists",
        )
    await db.refresh(entry, ["contacts"])
    contact_count = len(entry.contacts) if entry.contacts else 0
    return _pipeline_to_lead_response(entry, contact_count)


# ---------------------------------------------------------------------------
# 6. POST /leads/{lead_id}/contacts — Add contact
# ---------------------------------------------------------------------------


@router.post("/{lead_id}/contacts", status_code=status.HTTP_201_CREATED)
async def add_contact(
    lead_id: UUID,
    body: AddContactRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Add a contact to a lead. Deduplicates by email (case-insensitive)."""
    result = await db.execute(
        select(PipelineEntry).where(PipelineEntry.id == lead_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")

    # Dedup by email (already lowercased by validator)
    if body.email:
        existing = await db.execute(
            select(Contact).where(
                Contact.pipeline_entry_id == lead_id,
                func.lower(Contact.email) == body.email,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Contact with email {body.email} already exists on this lead",
            )

    contact = Contact(
        tenant_id=user.tenant_id,
        pipeline_entry_id=lead_id,
        name=body.name,
        email=body.email,
        title=body.title,
        linkedin_url=body.linkedin_url,
        role=body.role,
        notes=body.notes,
    )
    db.add(contact)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Duplicate contact")
    await db.refresh(contact)
    return _contact_to_lead_contact(contact)


# ---------------------------------------------------------------------------
# 7. PATCH /leads/contacts/{contact_id} — Update contact
# ---------------------------------------------------------------------------


@router.patch("/contacts/{contact_id}")
async def update_contact(
    contact_id: UUID,
    body: UpdateContactRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Update a lead contact's fields."""
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")

    for field in ["name", "email", "title", "linkedin_url", "role", "notes"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(contact, field, val)

    # pipeline_stage is accepted but no longer stored on Contact
    # (stage is at the PipelineEntry level now)

    contact.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    await db.refresh(contact)
    return _contact_to_lead_contact(contact)


# ---------------------------------------------------------------------------
# 8. POST /leads/contacts/{contact_id}/messages — Create message (Activity)
# ---------------------------------------------------------------------------


@router.post("/contacts/{contact_id}/messages", status_code=status.HTTP_201_CREATED)
async def create_message(
    contact_id: UUID,
    body: CreateMessageRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Create or upsert an outreach message for a contact (stored as Activity)."""
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")

    if not contact.pipeline_entry_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Contact is not linked to a pipeline entry")

    now = datetime.datetime.now(datetime.timezone.utc)

    # Upsert by step_number + channel (stored in metadata)
    existing_result = await db.execute(
        select(Activity).where(
            Activity.pipeline_entry_id == contact.pipeline_entry_id,
            Activity.contact_id == contact_id,
            Activity.type == "message",
            Activity.channel == body.channel,
            Activity.metadata_["step_number"].as_integer() == body.step_number,
        )
    )
    act = existing_result.scalar_one_or_none()

    if act:
        if body.subject is not None:
            act.subject = body.subject
        if body.body is not None:
            act.body_preview = body.body if body.body else None
        if body.status:
            act.status = body.status
        meta = dict(act.metadata_ or {})
        if body.sent_at:
            meta["sent_at"] = _parse_timestamp(body.sent_at).isoformat() if body.sent_at else None
        if body.from_email is not None:
            meta["from_email"] = body.from_email
        if body.metadata is not None:
            meta.update(body.metadata)
        act.metadata_ = meta
    else:
        meta = {
            "step_number": body.step_number,
            "from_email": body.from_email,
            "drafted_at": now.isoformat() if body.status == "drafted" else (
                _parse_timestamp(body.drafted_at).isoformat() if body.drafted_at else None
            ),
            "sent_at": _parse_timestamp(body.sent_at).isoformat() if body.sent_at else None,
            **(body.metadata or {}),
        }
        act = Activity(
            tenant_id=user.tenant_id,
            pipeline_entry_id=contact.pipeline_entry_id,
            contact_id=contact_id,
            type="message",
            channel=body.channel,
            direction="outbound",
            status=body.status,
            subject=body.subject,
            body_preview=body.body if body.body else None,
            metadata_=meta,
        )
        db.add(act)

    await db.flush()
    await db.commit()
    await db.refresh(act)
    return _activity_to_message(act)


# ---------------------------------------------------------------------------
# 9. PATCH /leads/messages/{message_id} — Update message (Activity)
# ---------------------------------------------------------------------------


@router.patch("/messages/{message_id}")
async def update_message(
    message_id: UUID,
    body: UpdateMessageRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Update message (activity) status."""
    result = await db.execute(
        select(Activity).where(Activity.id == message_id, Activity.type == "message")
    )
    act = result.scalar_one_or_none()
    if not act:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    meta = dict(act.metadata_ or {})

    if body.subject is not None:
        act.subject = body.subject
    if body.body is not None:
        act.body_preview = body.body if body.body else None
    if body.from_email is not None:
        meta["from_email"] = body.from_email
    if body.sent_at:
        meta["sent_at"] = _parse_timestamp(body.sent_at).isoformat()
    if body.replied_at:
        meta["replied_at"] = _parse_timestamp(body.replied_at).isoformat()

    if body.status:
        act.status = body.status
        if body.status == "sent" and not meta.get("sent_at"):
            meta["sent_at"] = now.isoformat()
        if body.status == "replied" and not meta.get("replied_at"):
            meta["replied_at"] = now.isoformat()

    act.metadata_ = meta
    await db.commit()
    await db.refresh(act)
    return _activity_to_message(act)


# ---------------------------------------------------------------------------
# 10. POST /leads/{lead_id}/graduate — No-op (unified pipeline)
# ---------------------------------------------------------------------------


@router.post("/{lead_id}/graduate")
async def graduate_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """No-op in unified pipeline. Returns the entry data with an explanatory message."""
    result = await db.execute(
        select(PipelineEntry).where(PipelineEntry.id == lead_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")

    return {
        "graduated": False,
        "message": "Graduation is no longer needed. All entries are in a unified pipeline.",
        "lead_id": str(entry.id),
        "account_id": None,
        "account_name": None,
        "pipeline_entry_id": str(entry.id),
        "stage": entry.stage,
    }
