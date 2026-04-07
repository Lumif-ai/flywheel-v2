"""Shared Granola meeting sync logic.

Extracted from meetings.py so both the API endpoint and the flywheel engine
can call sync_granola_meetings() with an async_sessionmaker.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flywheel.auth.encryption import decrypt_api_key
from flywheel.db.models import Integration, Meeting
from flywheel.services.granola_adapter import (
    RawMeeting,
    list_meetings as granola_list_meetings,
)


# ---------------------------------------------------------------------------
# Helpers (pure or session-scoped)
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
    session: AsyncSession,
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

    result = await session.execute(
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
    raw_emails: set[str] = set()
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
            cand_emails: set[str] = set()
            for a in candidate.attendees:
                email = a.get("email", "") if isinstance(a, dict) else ""
                if email:
                    cand_emails.add(email.lower())
            if raw_emails & cand_emails:
                return candidate

    return None


# ---------------------------------------------------------------------------
# Main shared function
# ---------------------------------------------------------------------------


async def sync_granola_meetings(
    factory: async_sessionmaker,
    tenant_id: UUID,
    user_id: UUID,
) -> dict:
    """Pull meetings from Granola for a user, dedup, and insert new rows.

    Opens its own session via `factory()`, sets RLS context, runs the full
    sync logic, and returns stats.

    Returns:
        {"synced": int, "skipped": int, "already_seen": int, "total_from_provider": int}
    """
    async with factory() as session:
        # Set RLS context
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )

        # 1. Find Granola integration for this user/tenant
        result = await session.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.user_id == user_id,
                Integration.provider == "granola",
                Integration.status == "connected",
            ).limit(1)
        )
        integration = result.scalar_one_or_none()
        if integration is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="Granola not connected. Add your API key in Settings.",
            )

        # 2. Decrypt API key
        if not integration.credentials_encrypted:
            from fastapi import HTTPException
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
            existing_result = await session.execute(
                select(Meeting.external_id).where(
                    Meeting.tenant_id == tenant_id,
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
            if not raw.external_id:
                skipped += 1
                continue
            if raw.external_id in existing_ids:
                continue

            # Fuzzy dedup: check if a scheduled calendar meeting matches
            matched = await _find_matching_scheduled(session, tenant_id, raw)
            if matched is not None:
                # Enrich existing scheduled row with Granola data
                matched.granola_note_id = raw.external_id
                matched.ai_summary = raw.ai_summary
                matched.duration_mins = raw.duration_mins
                matched.processing_status = "recorded"
                synced += 1
                continue

            processing_status = _apply_processing_rules(raw, processing_rules)
            meeting = Meeting(
                tenant_id=tenant_id,
                user_id=user_id,
                provider="granola",
                external_id=raw.external_id,
                granola_note_id=raw.external_id,
                title=raw.title,
                meeting_date=raw.meeting_date,
                duration_mins=raw.duration_mins,
                attendees=raw.attendees,
                ai_summary=raw.ai_summary,
                processing_status=processing_status,
            )
            session.add(meeting)

            if processing_status == "pending":
                synced += 1
            else:
                skipped += 1

        # 6. Update sync cursor
        integration.last_synced_at = datetime.now(timezone.utc)

        # 7. Commit and return stats
        await session.commit()

        return {
            "synced": synced,
            "skipped": skipped,
            "already_seen": len(existing_ids),
            "total_from_provider": len(raw_meetings),
        }
