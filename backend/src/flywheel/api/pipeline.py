"""Pipeline REST API — unified pipeline CRUD endpoints.

17 endpoints:
- GET    /pipeline/check-dedup                        -- fuzzy dedup check
- GET    /pipeline/search                             -- cross-table search
- GET    /pipeline/contacts/                          -- flat contact list with next_step
- GET    /pipeline/                                   -- paginated list
- POST   /pipeline/                                   -- create with dedup
- GET    /pipeline/{entry_id}                         -- full detail
- PATCH  /pipeline/{entry_id}                         -- update with stage tracking
- GET    /pipeline/{entry_id}/timeline                -- merged timeline
- POST   /pipeline/{entry_id}/retire                  -- retire entry
- POST   /pipeline/{entry_id}/reactivate              -- reactivate entry
- GET    /pipeline/{entry_id}/contacts                -- list contacts
- POST   /pipeline/{entry_id}/contacts                -- create contact
- PATCH  /pipeline/{entry_id}/contacts/{contact_id}   -- update contact
- DELETE /pipeline/{entry_id}/contacts/{contact_id}   -- delete contact
- GET    /pipeline/{entry_id}/activities               -- list activities
- POST   /pipeline/{entry_id}/activities               -- create activity
- PATCH  /pipeline/{entry_id}/activities/{activity_id} -- update activity
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.services.pipeline_service import (
    CreateActivityRequest,
    CreateContactRequest,
    CreatePipelineRequest,
    PipelineService,
    UpdateActivityRequest,
    UpdateContactRequest,
    UpdatePipelineRequest,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_entry_list(
    entry,
    contact_count: int,
    primary_contact: dict | None,
    outreach_summary: dict | None = None,
) -> dict:
    """Serialize a PipelineEntry ORM object to list-item dict shape."""
    return {
        "id": str(entry.id),
        "name": entry.name,
        "domain": entry.domain,
        "entity_type": entry.entity_type,
        "stage": entry.stage,
        "fit_score": float(entry.fit_score) if entry.fit_score is not None else None,
        "fit_tier": entry.fit_tier,
        "relationship_type": entry.relationship_type or [],
        "source": entry.source,
        "channels": entry.channels or [],
        "ai_summary": entry.ai_summary,
        "next_action_date": (
            entry.next_action_date.isoformat() if entry.next_action_date else None
        ),
        "next_action_note": entry.next_action_note,
        "last_activity_at": (
            entry.last_activity_at.isoformat() if entry.last_activity_at else None
        ),
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "stale_notified_at": entry.stale_notified_at.isoformat() if entry.stale_notified_at else None,
        "retired_at": entry.retired_at.isoformat() if entry.retired_at else None,
        "contact_count": contact_count,
        "primary_contact": primary_contact,
        "outreach_summary": outreach_summary,
    }


def _serialize_entry_detail(entry) -> dict:
    """Serialize a PipelineEntry ORM object to full detail dict shape."""
    contacts = [_serialize_contact(c) for c in (entry.contacts or [])]
    activities = [
        _serialize_activity(a)
        for a in (getattr(entry, "_recent_activities", None) or [])
    ]
    sources = [_serialize_source(s) for s in (entry.sources or [])]

    # Primary contact
    primary_contact = None
    for c in entry.contacts or []:
        if c.is_primary:
            primary_contact = {
                "name": c.name,
                "email": c.email,
                "title": c.title,
            }
            break

    return {
        "id": str(entry.id),
        "name": entry.name,
        "domain": entry.domain,
        "entity_type": entry.entity_type,
        "stage": entry.stage,
        "fit_score": float(entry.fit_score) if entry.fit_score is not None else None,
        "fit_tier": entry.fit_tier,
        "fit_rationale": entry.fit_rationale,
        "relationship_type": entry.relationship_type or [],
        "source": entry.source,
        "channels": entry.channels or [],
        "last_activity_at": (
            entry.last_activity_at.isoformat() if entry.last_activity_at else None
        ),
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "stale_notified_at": entry.stale_notified_at.isoformat() if entry.stale_notified_at else None,
        "retired_at": entry.retired_at.isoformat() if entry.retired_at else None,
        "contact_count": len(contacts),
        "primary_contact": primary_contact,
        "intel": entry.intel or {},
        "ai_summary": entry.ai_summary,
        "contacts": contacts,
        "recent_activities": activities,
        "sources": sources,
    }


def _serialize_contact(contact) -> dict:
    """Serialize a Contact ORM object."""
    return {
        "id": str(contact.id),
        "name": contact.name,
        "email": contact.email,
        "title": contact.title,
        "role": contact.role,
        "linkedin_url": contact.linkedin_url,
        "phone": contact.phone,
        "notes": contact.notes,
        "is_primary": contact.is_primary,
        "created_at": (
            contact.created_at.isoformat() if contact.created_at else None
        ),
    }


def _serialize_activity(activity) -> dict:
    """Serialize an Activity ORM object."""
    return {
        "id": str(activity.id),
        "type": activity.type,
        "channel": activity.channel,
        "direction": activity.direction,
        "status": activity.status,
        "subject": activity.subject,
        "body_preview": activity.body_preview,
        "metadata": activity.metadata_ or {},
        "contact_id": str(activity.contact_id) if activity.contact_id else None,
        "occurred_at": (
            activity.occurred_at.isoformat() if activity.occurred_at else None
        ),
        "created_at": (
            activity.created_at.isoformat() if activity.created_at else None
        ),
    }


def _serialize_source(source) -> dict:
    """Serialize a PipelineEntrySource ORM object."""
    return {
        "id": str(source.id),
        "source_type": source.source_type,
        "source_ref_id": str(source.source_ref_id) if source.source_ref_id else None,
        "created_at": (
            source.created_at.isoformat() if source.created_at else None
        ),
    }


# ---------------------------------------------------------------------------
# CRITICAL: Fixed routes MUST come before parameterized routes
# ---------------------------------------------------------------------------


# GET /pipeline/check-dedup — API-12
@router.get("/check-dedup")
async def check_dedup(
    name: str = Query(..., description="Company/person name to check"),
    domain: str | None = Query(None, description="Domain to match"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Check for potential duplicate pipeline entries."""
    service = PipelineService(db, user)
    matches = await service.check_dedup(name, domain)
    return {"matches": [m.model_dump() for m in matches]}


# ---------------------------------------------------------------------------
# GET /pipeline/search — API-08
# ---------------------------------------------------------------------------


@router.get("/search")
async def search_entries(
    q: str = Query(..., description="Search query"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Search pipeline entries across name, domain, contact names, and notes."""
    service = PipelineService(db, user)
    entries, total = await service.search_entries(q, offset, limit)

    items = [
        _serialize_entry_list(entry, cc, pc)
        for entry, cc, pc in entries
    ]

    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


# ---------------------------------------------------------------------------
# GET /pipeline/contacts/ — flat contact list
# ---------------------------------------------------------------------------


def _serialize_contact_flat(row: dict) -> dict:
    """Serialize a flat contact dict from list_contacts_flat."""
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row.get("email"),
        "title": row.get("title"),
        "linkedin_url": row.get("linkedin_url"),
        "phone": row.get("phone"),
        "is_primary": row.get("is_primary", False),
        "company_name": row.get("company_name"),
        "company_domain": row.get("company_domain"),
        "pipeline_entry_id": row["pipeline_entry_id"],
        "channels": row.get("channels", []),
        "source": row.get("source"),
        "campaign": row.get("campaign"),
        "latest_activity": row.get("latest_activity"),
        "next_step": row.get("next_step", "Ready to send"),
        "created_at": row.get("created_at"),
    }


@router.get("/contacts/")
async def list_contacts_flat(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("name"),
    sort_dir: str = Query("asc"),
    company: str | None = Query(None),
    status: str | None = Query(None),
    channel: str | None = Query(None),
    variant: str | None = Query(None),
    step_number: int | None = Query(None),
    include_retired: bool = Query(False),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Flat contact list with parent company, latest outreach activity, and AI-computed next_step."""
    filters: dict = {}
    if company is not None:
        filters["company"] = company
    if status is not None:
        filters["status"] = status
    if channel is not None:
        filters["channel"] = channel
    if variant is not None:
        filters["variant"] = variant
    if step_number is not None:
        filters["step_number"] = step_number

    service = PipelineService(db, user)
    contacts, total = await service.list_contacts_flat(
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
        filters=filters,
        include_retired=include_retired,
    )

    return {
        "items": [_serialize_contact_flat(c) for c in contacts],
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


# ---------------------------------------------------------------------------
# GET /pipeline/ — API-01
# ---------------------------------------------------------------------------


@router.get("/")
async def list_entries(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    entity_type: str | None = Query(None),
    stage: str | None = Query(None, description="Comma-separated stages"),
    fit_tier: str | None = Query(None, description="Comma-separated fit tiers"),
    source: str | None = Query(None),
    relationship_type: str | None = Query(None, description="Comma-separated relationship types"),
    view: str | None = Query(None, description="View filter: needs_action, replied, stale"),
    include_retired: bool = Query(False, description="Include retired entries in results"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Paginated, filterable, searchable, sortable pipeline list."""
    limit = min(limit, 100)

    # Parse comma-separated filters
    filters: dict = {}
    if entity_type:
        filters["entity_type"] = entity_type
    if stage:
        filters["stage"] = [s.strip() for s in stage.split(",")]
    if fit_tier:
        filters["fit_tier"] = [t.strip() for t in fit_tier.split(",")]
    if source:
        filters["source"] = source
    if relationship_type:
        filters["relationship_type"] = [r.strip() for r in relationship_type.split(",")]

    service = PipelineService(db, user)
    entries, total = await service.list_entries(
        filters=filters,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
        search=search,
        view=view,
        include_retired=include_retired,
    )

    items = [
        _serialize_entry_list(entry, cc, pc, outreach_summary)
        for entry, cc, pc, outreach_summary in entries
    ]

    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


# ---------------------------------------------------------------------------
# GET /pipeline/{entry_id} — API-02
# ---------------------------------------------------------------------------


@router.get("/{entry_id}")
async def get_entry(
    entry_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Full pipeline entry detail with contacts, activities, sources."""
    service = PipelineService(db, user)
    entry = await service.get_entry(entry_id)
    return _serialize_entry_detail(entry)


# ---------------------------------------------------------------------------
# POST /pipeline/ — API-03
# ---------------------------------------------------------------------------


@router.post("/", status_code=201)
async def create_entry(
    body: CreatePipelineRequest,
    response: Response,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a pipeline entry with dedup check and person auto-contact."""
    service = PipelineService(db, user)
    entry, was_dedup = await service.create_entry(body)

    if was_dedup:
        response.status_code = status.HTTP_200_OK
        return {
            "entry": _serialize_entry_detail(entry),
            "dedup_matched": True,
        }

    return {
        "entry": _serialize_entry_detail(entry),
        "dedup_matched": False,
    }


# ---------------------------------------------------------------------------
# PATCH /pipeline/{entry_id} — API-04, API-11
# ---------------------------------------------------------------------------


@router.patch("/{entry_id}")
async def update_entry(
    entry_id: UUID,
    body: UpdatePipelineRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update pipeline entry fields with stage change tracking."""
    service = PipelineService(db, user)
    entry = await service.update_entry(entry_id, body)

    # Reload with relationships for full response
    entry = await service.get_entry(entry_id)
    return _serialize_entry_detail(entry)


# ---------------------------------------------------------------------------
# GET /pipeline/{entry_id}/timeline — API-05
# ---------------------------------------------------------------------------


@router.get("/{entry_id}/timeline")
async def get_timeline(
    entry_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Unified timeline merging activities, meetings, and context entries."""
    service = PipelineService(db, user)
    items, total = await service.get_timeline(entry_id, offset, limit)

    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


# ---------------------------------------------------------------------------
# POST /pipeline/{entry_id}/retire — Retire entry
# ---------------------------------------------------------------------------


@router.post("/{entry_id}/retire")
async def retire_entry(
    entry_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Manually retire a pipeline entry."""
    service = PipelineService(db, user)
    entry = await service.retire_entry(entry_id)
    entry = await service.get_entry(entry_id)
    return _serialize_entry_detail(entry)


# ---------------------------------------------------------------------------
# POST /pipeline/{entry_id}/reactivate — Reactivate entry
# ---------------------------------------------------------------------------


@router.post("/{entry_id}/reactivate")
async def reactivate_entry(
    entry_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Reactivate a retired pipeline entry."""
    service = PipelineService(db, user)
    entry = await service.reactivate_entry(entry_id)
    entry = await service.get_entry(entry_id)
    return _serialize_entry_detail(entry)


# ---------------------------------------------------------------------------
# Contacts CRUD — API-06
# ---------------------------------------------------------------------------


@router.get("/{entry_id}/contacts")
async def list_contacts(
    entry_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all contacts for a pipeline entry."""
    service = PipelineService(db, user)
    contacts = await service.list_contacts(entry_id)
    return {"contacts": [_serialize_contact(c) for c in contacts]}


@router.post("/{entry_id}/contacts", status_code=201)
async def create_contact(
    entry_id: UUID,
    body: CreateContactRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a contact under a pipeline entry."""
    service = PipelineService(db, user)
    contact = await service.create_contact(entry_id, body)
    return _serialize_contact(contact)


@router.patch("/{entry_id}/contacts/{contact_id}")
async def update_contact(
    entry_id: UUID,
    contact_id: UUID,
    body: UpdateContactRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a contact."""
    service = PipelineService(db, user)
    contact = await service.update_contact(entry_id, contact_id, body)
    return _serialize_contact(contact)


@router.delete("/{entry_id}/contacts/{contact_id}", status_code=204)
async def delete_contact(
    entry_id: UUID,
    contact_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a contact."""
    service = PipelineService(db, user)
    await service.delete_contact(entry_id, contact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Activities CRUD — API-07
# ---------------------------------------------------------------------------


@router.get("/{entry_id}/activities")
async def list_activities(
    entry_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    contact_id: UUID | None = Query(None, description="Filter activities by contact"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List activities for a pipeline entry, paginated."""
    service = PipelineService(db, user)
    activities, total = await service.list_activities(
        entry_id, offset, limit, contact_id=contact_id
    )

    return {
        "items": [_serialize_activity(a) for a in activities],
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


@router.post("/{entry_id}/activities", status_code=201)
async def create_activity(
    entry_id: UUID,
    body: CreateActivityRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create an activity under a pipeline entry."""
    service = PipelineService(db, user)
    activity = await service.create_activity(entry_id, body)
    return _serialize_activity(activity)


@router.patch("/{entry_id}/activities/{activity_id}")
async def update_activity(
    entry_id: UUID,
    activity_id: UUID,
    body: UpdateActivityRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update an activity."""
    service = PipelineService(db, user)
    activity = await service.update_activity(entry_id, activity_id, body)
    return _serialize_activity(activity)
