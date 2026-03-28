"""Meetings endpoints.

Endpoints:
- POST /meetings/sync                -- pull meetings from Granola, dedup, insert new rows
- POST /meetings/process-pending     -- batch trigger processing for all pending meetings
- GET  /meetings/                    -- paginated list of meetings (optional status filter)
- GET  /meetings/{id}                -- detail view (owner-only for transcript_url/ai_summary)
- POST /meetings/{id}/process        -- trigger meeting intelligence processing pipeline
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.encryption import decrypt_api_key
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Integration, Meeting, SkillRun
from flywheel.services.granola_adapter import RawMeeting, list_meetings as granola_list_meetings

router = APIRouter(prefix="/meetings", tags=["meetings"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_processing_rules(raw: RawMeeting, rules: dict) -> str:
    """Determine processing_status for a new meeting based on tenant rules.

    Returns "pending" (will be processed) or "skipped" (will not be processed).

    Rules checked (all from Integration.settings["processing_rules"]):
    - skip_internal: skip if ALL attendees have is_external=False
    - min_duration_mins: skip if duration_mins is below threshold
    - skip_domains: skip if ALL attendee emails match any listed domain
    """
    if not rules:
        return "pending"

    attendees = raw.attendees or []

    # skip_internal: skip meetings where no external attendees
    if rules.get("skip_internal"):
        if attendees and all(not a.get("is_external", True) for a in attendees):
            return "skipped"

    # min_duration_mins: skip meetings shorter than threshold
    min_duration = rules.get("min_duration_mins")
    if min_duration is not None and raw.duration_mins is not None:
        if raw.duration_mins < min_duration:
            return "skipped"

    # skip_domains: skip if all attendee emails match any skip domain
    skip_domains = rules.get("skip_domains")
    if skip_domains and isinstance(skip_domains, list) and attendees:
        def matches_any_domain(email: str | None) -> bool:
            if not email:
                return False
            email_lower = email.lower()
            return any(email_lower.endswith(f"@{d.lower()}") for d in skip_domains)

        if all(matches_any_domain(a.get("email")) for a in attendees):
            return "skipped"

    return "pending"


async def _find_matching_scheduled(
    db: AsyncSession,
    tenant_id: UUID,
    raw: RawMeeting,
) -> Meeting | None:
    """Find a scheduled calendar meeting that matches this Granola meeting.

    Fuzzy dedup: matches on time (+/-30 min), title (case-insensitive contains),
    or attendee email overlap. Returns first matching candidate or None.
    """
    if not raw.meeting_date:
        return None

    window_start = raw.meeting_date - timedelta(minutes=30)
    window_end = raw.meeting_date + timedelta(minutes=30)

    result = await db.execute(
        select(Meeting).where(
            and_(
                Meeting.tenant_id == tenant_id,
                Meeting.processing_status == "scheduled",
                Meeting.meeting_date >= window_start,
                Meeting.meeting_date <= window_end,
            )
        )
    )
    candidates = result.scalars().all()

    if not candidates:
        return None

    raw_title = (raw.title or "").lower().strip()
    raw_emails = set()
    if raw.attendees:
        for a in raw.attendees:
            email = a.get("email", "") if isinstance(a, dict) else ""
            if email:
                raw_emails.add(email.lower())

    for candidate in candidates:
        # Title match: case-insensitive contains (either direction)
        cand_title = (candidate.title or "").lower().strip()
        if raw_title and cand_title:
            if raw_title in cand_title or cand_title in raw_title:
                return candidate

        # Attendee overlap: at least one email in common
        if raw_emails and candidate.attendees:
            cand_emails = set()
            for a in candidate.attendees:
                email = a.get("email", "") if isinstance(a, dict) else ""
                if email:
                    cand_emails.add(email.lower())
            if raw_emails & cand_emails:
                return candidate

    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/sync")
async def sync_meetings(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Pull meetings from Granola for the authenticated user.

    Deduplicates by (tenant_id, provider, external_id) — already-seen meetings
    are counted but not re-inserted.

    Processing rules (from Integration.settings["processing_rules"]) filter
    meetings to "skipped" status before any downstream processing.

    Returns:
        synced: count of new meetings inserted with processing_status="pending"
        skipped: count of new meetings inserted with processing_status="skipped"
        already_seen: count of meetings already in DB (not re-inserted)
        total_from_provider: raw count from Granola API
    """
    # 1. Find Granola integration for this user/tenant
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.user_id == user.sub,
            Integration.provider == "granola",
            Integration.status == "connected",
        ).limit(1)
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(
            status_code=400,
            detail="Granola not connected. Add your API key in Settings.",
        )

    # 2. Decrypt API key
    if not integration.credentials_encrypted:
        raise HTTPException(
            status_code=400,
            detail="Granola integration has no stored credentials.",
        )
    api_key = decrypt_api_key(integration.credentials_encrypted)

    # 3. Fetch meetings from Granola (incremental via last_synced_at cursor)
    raw_meetings = await granola_list_meetings(api_key, since=integration.last_synced_at)

    # 4. Dedup: find external_ids already present in the DB
    existing_ids: set[str] = set()
    if raw_meetings:
        fetched_ids = [m.external_id for m in raw_meetings]
        existing_result = await db.execute(
            select(Meeting.external_id).where(
                Meeting.tenant_id == user.tenant_id,
                Meeting.provider == "granola",
                Meeting.external_id.in_(fetched_ids),
            )
        )
        existing_ids = {row[0] for row in existing_result.fetchall()}

    # 5. Insert new meetings with processing rules applied
    synced = 0
    skipped = 0
    processing_rules = (integration.settings or {}).get("processing_rules", {})

    for raw in raw_meetings:
        if raw.external_id in existing_ids:
            continue

        # Fuzzy dedup: check if a scheduled calendar meeting matches
        matched = await _find_matching_scheduled(db, user.tenant_id, raw)
        if matched is not None:
            # Enrich existing scheduled row with Granola data
            matched.granola_note_id = raw.external_id
            matched.ai_summary = raw.ai_summary
            matched.duration_mins = raw.duration_mins
            matched.processing_status = "recorded"
            synced += 1
            continue

        status = _apply_processing_rules(raw, processing_rules)
        meeting = Meeting(
            tenant_id=user.tenant_id,
            user_id=user.sub,
            provider="granola",
            external_id=raw.external_id,
            granola_note_id=raw.external_id,
            title=raw.title,
            meeting_date=raw.meeting_date,
            duration_mins=raw.duration_mins,
            attendees=raw.attendees,
            ai_summary=raw.ai_summary,
            processing_status=status,
        )
        db.add(meeting)

        if status == "pending":
            synced += 1
        else:
            skipped += 1

    # 6. Update sync cursor
    integration.last_synced_at = datetime.now(timezone.utc)

    # 7. Commit and return stats
    await db.commit()

    return {
        "synced": synced,
        "skipped": skipped,
        "already_seen": len(existing_ids),
        "total_from_provider": len(raw_meetings),
    }


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
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return a paginated list of meetings for the authenticated tenant.

    Optionally filter by processing_status. Does NOT include transcript_url
    or ai_summary (those are owner-only — see GET /{id}).

    Returns:
        items: list of meeting metadata dicts
        total: total count (ignoring pagination)
        limit: applied limit
        offset: applied offset
    """
    base_q = select(Meeting).where(
        Meeting.tenant_id == user.tenant_id,
        Meeting.deleted_at.is_(None),
    )
    if status is not None:
        base_q = base_q.where(Meeting.processing_status == status)

    # Count query
    count_q = select(func.count()).select_from(
        select(Meeting.id).where(
            Meeting.tenant_id == user.tenant_id,
            Meeting.deleted_at.is_(None),
            *([Meeting.processing_status == status] if status is not None else []),
        ).subquery()
    )
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Paginated query
    result = await db.execute(
        base_q.order_by(Meeting.meeting_date.desc()).limit(limit).offset(offset)
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
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in meetings
    ]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


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
