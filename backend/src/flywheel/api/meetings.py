"""Meetings endpoints.

Endpoints:
- POST  /meetings/sync                -- pull meetings from Granola, dedup, insert new rows
- POST  /meetings/process-pending     -- batch trigger processing for all pending meetings
- GET   /meetings/                    -- paginated list of meetings (optional status/time filter)
- GET   /meetings/{id}                -- detail view (owner-only for transcript_url/ai_summary)
- PATCH /meetings/{id}                -- partial update (ai_summary, processing_status)
- POST  /meetings/{id}/process        -- trigger meeting intelligence processing pipeline
- POST  /meetings/{id}/prep           -- trigger meeting prep and return stream URL
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Integration, Meeting, PipelineEntry, SkillRun
from flywheel.db.session import get_session_factory
from flywheel.engines.meeting_processor_web import auto_link_meeting_to_pipeline_entry
from flywheel.services.meeting_sync import sync_granola_meetings
from flywheel.services.calendar_sync import sync_calendar

router = APIRouter(prefix="/meetings", tags=["meetings"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class MeetingPatchRequest(BaseModel):
    ai_summary: str | None = None
    processing_status: str | None = None


VALID_PROCESSING_STATUSES = {
    "pending", "processing", "complete", "failed",
    "skipped", "recorded", "scheduled",
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/sync")
async def sync_meetings(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Pull meetings from all connected providers (Google Calendar + Granola).

    Syncs each connected provider independently. Returns combined results.
    Neither provider is required — syncs whichever is connected.
    """
    factory = get_session_factory()
    results: dict = {"providers": []}

    # 1. Google Calendar sync
    cal_integration = (await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.user_id == user.sub,
            Integration.provider == "google-calendar",
            Integration.status == "connected",
        ).limit(1)
    )).scalar_one_or_none()

    if cal_integration:
        try:
            count = await sync_calendar(db, cal_integration)
            results["providers"].append({"provider": "google-calendar", "events": count})
        except Exception as e:
            results["providers"].append({"provider": "google-calendar", "error": str(e)})

    # 2. Granola sync (independent — doesn't fail if not connected)
    try:
        granola_result = await sync_granola_meetings(factory, user.tenant_id, user.sub)
        results["providers"].append({"provider": "granola", **granola_result})
    except HTTPException:
        # Granola not connected — skip silently
        pass
    except Exception as e:
        results["providers"].append({"provider": "granola", "error": str(e)})

    if not results["providers"]:
        raise HTTPException(
            status_code=400,
            detail="No meeting providers connected. Connect Google Calendar or Granola in Settings.",
        )

    return results


@router.post("/process-pending")
async def process_pending_meetings(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Batch trigger meeting intelligence processing for all pending meetings.

    Creates a SkillRun per pending meeting and marks each as "processing".
    The job_queue_loop picks up each run and executes the 7-stage pipeline.

    This is the endpoint the frontend sync button calls.

    Returns:
        queued: count of meetings queued for processing
        run_ids: list of SkillRun UUIDs created
    """
    # Load all pending and recorded meetings for this tenant
    result = await db.execute(
        select(Meeting).where(
            Meeting.tenant_id == user.tenant_id,
            Meeting.processing_status.in_(["pending", "recorded"]),
            Meeting.deleted_at.is_(None),
        )
    )
    pending_meetings = result.scalars().all()

    if not pending_meetings:
        return {"queued": 0, "run_ids": []}

    runs: list[SkillRun] = []
    for meeting in pending_meetings:
        # Mark as processing immediately (race condition guard)
        meeting.processing_status = "processing"

        run = SkillRun(
            tenant_id=user.tenant_id,
            user_id=user.sub,
            skill_name="meeting-processor",
            input_text=str(meeting.id),
            status="pending",
        )
        db.add(run)
        runs.append(run)

    # Flush to populate run IDs, then link back to meetings
    await db.flush()
    for meeting, run in zip(pending_meetings, runs):
        meeting.skill_run_id = run.id

    await db.commit()

    return {
        "queued": len(runs),
        "run_ids": [str(run.id) for run in runs],
    }


@router.get("/")
async def list_meetings(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
    processing_status: str | None = None,
    time: str | None = None,
    show_hidden: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return a paginated list of meetings for the authenticated tenant.

    Optionally filter by processing_status and/or time window:
    - time=upcoming: meeting_date >= now, sorted soonest first (ascending)
    - time=past: meeting_date < now, sorted most recent first (descending)
    - time=None: default descending sort by meeting_date

    Does NOT include transcript_url or ai_summary (those are owner-only — see GET /{id}).

    Returns:
        items: list of meeting metadata dicts
        total: total count (ignoring pagination)
        limit: applied limit
        offset: applied offset
    """
    now = datetime.now(timezone.utc)

    # Build base filters
    filters = [
        Meeting.tenant_id == user.tenant_id,
        Meeting.deleted_at.is_(None),
    ]
    if not show_hidden:
        filters.append(Meeting.hidden.is_(False))
    if processing_status is not None:
        filters.append(Meeting.processing_status == processing_status)

    # Time-based filter
    if time == "upcoming":
        filters.append(Meeting.meeting_date >= now)
        order = Meeting.meeting_date.asc()
    elif time == "past":
        filters.append(Meeting.meeting_date < now)
        order = Meeting.meeting_date.desc()
    else:
        order = Meeting.meeting_date.desc()

    base_q = select(Meeting).where(*filters)

    # Count query (same filters for accurate pagination totals)
    count_q = select(func.count()).select_from(
        select(Meeting.id).where(*filters).subquery()
    )
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Paginated query
    result = await db.execute(
        base_q.order_by(order).limit(limit).offset(offset)
    )
    meetings = result.scalars().all()

    items = [
        {
            "id": str(m.id),
            "title": m.title,
            "meeting_date": m.meeting_date.isoformat() if m.meeting_date else None,
            "duration_mins": m.duration_mins,
            "attendees": m.attendees,
            "meeting_type": m.meeting_type,
            "processing_status": m.processing_status,
            "account_id": str(m.account_id) if m.account_id else None,
            "summary": m.summary,
            "provider": m.provider,
            "location": m.location,
            "calendar_event_id": m.calendar_event_id,
            "recurring_event_id": m.recurring_event_id,
            "hidden": m.hidden,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in meetings
    ]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/{meeting_id}/hide")
async def hide_meeting(
    meeting_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Hide a meeting. If it's part of a recurring series, hide all instances."""
    meeting = (await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.tenant_id == user.tenant_id,
        )
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    count = 0
    if meeting.recurring_event_id:
        # Hide all instances of this recurring series
        result = await db.execute(
            select(Meeting).where(
                Meeting.tenant_id == user.tenant_id,
                Meeting.recurring_event_id == meeting.recurring_event_id,
            )
        )
        for m in result.scalars().all():
            m.hidden = True
            count += 1
    else:
        meeting.hidden = True
        count = 1

    await db.commit()
    return {"hidden": count, "recurring_event_id": meeting.recurring_event_id}


@router.post("/{meeting_id}/unhide")
async def unhide_meeting(
    meeting_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Unhide a meeting and its recurring series."""
    meeting = (await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.tenant_id == user.tenant_id,
        )
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    count = 0
    if meeting.recurring_event_id:
        result = await db.execute(
            select(Meeting).where(
                Meeting.tenant_id == user.tenant_id,
                Meeting.recurring_event_id == meeting.recurring_event_id,
            )
        )
        for m in result.scalars().all():
            m.hidden = False
            count += 1
    else:
        meeting.hidden = False
        count = 1

    await db.commit()
    return {"unhidden": count, "recurring_event_id": meeting.recurring_event_id}


@router.get("/{meeting_id}")
async def get_meeting(
    meeting_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Return full meeting detail, enforcing owner-only access for sensitive fields.

    Owner (meeting.user_id == caller): receives all fields including
    transcript_url and ai_summary.

    Non-owner tenant member: receives metadata only (transcript_url and
    ai_summary omitted per MDE-01 privacy spec).

    Raises:
        404 if meeting not found for this tenant
    """
    result = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.tenant_id == user.tenant_id,
            Meeting.deleted_at.is_(None),
        ).limit(1)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    is_owner = str(meeting.user_id) == str(user.sub)

    data: dict = {
        "id": str(meeting.id),
        "title": meeting.title,
        "meeting_date": meeting.meeting_date.isoformat() if meeting.meeting_date else None,
        "duration_mins": meeting.duration_mins,
        "attendees": meeting.attendees,
        "meeting_type": meeting.meeting_type,
        "processing_status": meeting.processing_status,
        "account_id": str(meeting.account_id) if meeting.account_id else None,
        "summary": meeting.summary,
        "skill_run_id": str(meeting.skill_run_id) if meeting.skill_run_id else None,
        "processed_at": meeting.processed_at.isoformat() if meeting.processed_at else None,
        "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
        "updated_at": meeting.updated_at.isoformat() if meeting.updated_at else None,
    }

    # Owner-only fields (privacy enforcement per MDE-01)
    if is_owner:
        data["transcript_url"] = meeting.transcript_url
        data["ai_summary"] = meeting.ai_summary

    return data


@router.patch("/{meeting_id}")
async def patch_meeting(
    meeting_id: UUID,
    body: MeetingPatchRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Partial update for a meeting record.

    Used by MCP tools to write back AI-generated summaries and update
    processing status after pipeline execution.

    Only updates fields that are explicitly provided (not None).

    Raises:
        404 if meeting not found for this tenant (or soft-deleted)
        422 if processing_status is not a valid value
    """
    result = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.tenant_id == user.tenant_id,
            Meeting.deleted_at.is_(None),
        ).limit(1)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Validate processing_status if provided
    if body.processing_status is not None:
        if body.processing_status not in VALID_PROCESSING_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid processing_status '{body.processing_status}'. "
                    f"Valid values: {sorted(VALID_PROCESSING_STATUSES)}"
                ),
            )
        meeting.processing_status = body.processing_status

    if body.ai_summary is not None:
        meeting.ai_summary = body.ai_summary

    await db.commit()
    await db.refresh(meeting)

    return {
        "id": str(meeting.id),
        "ai_summary": meeting.ai_summary,
        "processing_status": meeting.processing_status,
    }


@router.post("/{meeting_id}/process")
async def process_meeting(
    meeting_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Trigger the meeting intelligence processing pipeline for a meeting.

    Creates a SkillRun for the "meeting-processor" skill. The job_queue_loop
    picks it up and runs the 7-stage pipeline (fetch, store, classify, extract,
    link, write, done).

    Returns:
        run_id: UUID of the created SkillRun
        meeting_id: UUID of the meeting being processed

    Raises:
        404 if meeting not found for this tenant
        409 if meeting is already processing or complete
    """
    # 1. Load meeting by id + tenant_id
    result = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.tenant_id == user.tenant_id,
        ).limit(1)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # 2. Guard against duplicate processing
    if meeting.processing_status in ("processing", "complete"):
        raise HTTPException(
            status_code=409,
            detail=f"Meeting is already in '{meeting.processing_status}' state. "
                   "Only 'pending', 'recorded', 'scheduled', or 'failed' meetings can be reprocessed.",
        )

    # 3. Race condition guard — mark as processing immediately
    meeting.processing_status = "processing"

    # 4. Create SkillRun for the meeting-processor skill
    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name="meeting-processor",
        input_text=str(meeting_id),
        status="pending",
    )
    db.add(run)

    # 5. Flush to get run.id, then link back to meeting
    await db.flush()
    meeting.skill_run_id = run.id

    # 6. Commit
    await db.commit()

    return {"run_id": str(run.id), "meeting_id": str(meeting_id)}


@router.post("/{meeting_id}/prep", status_code=status.HTTP_202_ACCEPTED)
async def prep_meeting(
    meeting_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Trigger meeting prep for a specific meeting and return a stream URL.

    Auto-links the meeting to an account if not already linked (using attendee
    domain matching). Creates a SkillRun for the "meeting-prep" skill with
    Account-ID dispatch prefix.

    Returns:
        run_id: UUID of the created SkillRun
        stream_url: SSE endpoint for real-time prep output

    Raises:
        404 if meeting not found for this tenant
        400 if no account could be linked
    """
    # 1. Load meeting
    result = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.tenant_id == user.tenant_id,
            Meeting.deleted_at.is_(None),
        ).limit(1)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # 2. Resolve account_id — use existing or auto-link
    account_id = meeting.account_id

    if account_id is None:
        # auto_link requires a session factory (opens its own sessions internally)
        linked_id = await auto_link_meeting_to_pipeline_entry(
            get_session_factory(),
            tenant_id=user.tenant_id,
            attendees=meeting.attendees or [],
            user_id=user.sub,
            meeting_title=meeting.title or "",
        )
        if linked_id:
            meeting.pipeline_entry_id = linked_id
            await db.commit()
            await db.refresh(meeting)
            account_id = linked_id

    if account_id is None:
        raise HTTPException(
            status_code=400,
            detail="No account could be linked to this meeting. "
                   "Add attendees with company email addresses.",
        )

    # 3. Load account name for dispatch prefix
    entry_result = await db.execute(
        select(PipelineEntry).where(PipelineEntry.id == account_id).limit(1)
    )
    entry = entry_result.scalar_one_or_none()
    account_name = entry.name if entry else "Unknown"

    # 4. Build input_text with Account-ID dispatch prefix
    input_text = (
        f"Account-ID: {account_id}\n"
        f"Account-Name: {account_name}\n"
        f"Meeting-ID: {meeting_id}"
    )

    # 5. Create SkillRun
    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name="meeting-prep",
        input_text=input_text,
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.commit()

    return {
        "run_id": str(run.id),
        "stream_url": f"/api/v1/skills/runs/{run.id}/stream",
    }
