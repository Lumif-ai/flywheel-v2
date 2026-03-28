"""Meetings endpoints.

Endpoints:
- POST /meetings/sync  -- pull meetings from Granola, dedup, insert new rows
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.encryption import decrypt_api_key
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Integration, Meeting
from flywheel.services.granola_adapter import RawMeeting, list_meetings

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
    raw_meetings = await list_meetings(api_key, since=integration.last_synced_at)

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

        status = _apply_processing_rules(raw, processing_rules)
        meeting = Meeting(
            tenant_id=user.tenant_id,
            user_id=user.sub,
            provider="granola",
            external_id=raw.external_id,
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
