"""Briefing V2 assembly service -- five-section morning standup briefing.

Assembles: narrative_summary, today (meetings + tasks), attention_items,
team_activity, and tasks_today into BriefingV2Response shape.

Plan 01 implements: today section (meetings + tasks), narrative stub,
last_briefing_visit tracking. Plan 02 fills attention, team_activity,
and replaces narrative stub with LLM implementation.

All functions receive an AsyncSession that is already tenant-scoped via RLS.
"""

from __future__ import annotations

import datetime
import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from flywheel.db.models import (
    Account,
    Meeting,
    PipelineEntry,
    Profile,
    Task,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def assemble_briefing_v2(
    session: AsyncSession, user_id: str | UUID, tenant_id: str | UUID
) -> dict:
    """Assemble the five-section briefing v2 response.

    Returns a dict matching BriefingV2Response schema:
    {narrative_summary, today, attention_items, team_activity, tasks_today}
    """
    uid = UUID(str(user_id))
    tid = UUID(str(tenant_id))

    # Track visit (read old timestamp, write new one)
    _prev_visit = await _get_and_update_last_visit(session, uid)

    # Build today section (meetings + tasks)
    today_section = await _build_today_section(session, uid, tid)

    # Narrative stub (Plan 02 replaces with LLM)
    narrative = await _generate_narrative(
        session, str(uid), str(tid),
        meetings=today_section["meetings"],
        tasks=today_section["tasks"],
        attention_count=0,  # Plan 02 wires real count
        team_activity_count=0,  # Plan 02 wires real count
    )

    return {
        "narrative_summary": narrative,
        "today": today_section,
        "attention_items": {
            "replies": [],
            "follow_ups": [],
            "drafts": [],
        },
        "team_activity": [],
        # tasks_today is a CONVENIENCE COPY of today.tasks at the top level.
        # Both contain identical data. This duplication is intentional per API-01.
        "tasks_today": today_section["tasks"],
    }


# ---------------------------------------------------------------------------
# Narrative stub (Plan 02 replaces implementation)
# ---------------------------------------------------------------------------


async def _generate_narrative(
    session: AsyncSession,
    user_id: str,
    tenant_id: str,
    meetings: list,
    tasks: list,
    attention_count: int = 0,
    team_activity_count: int = 0,
) -> str:
    """Stub: returns placeholder. Plan 02 replaces with LLM implementation."""
    return "Good morning. Your briefing is being prepared."


# ---------------------------------------------------------------------------
# Last-visit tracking
# ---------------------------------------------------------------------------


async def _get_and_update_last_visit(
    session: AsyncSession, user_id: UUID
) -> datetime.datetime | None:
    """Read last_briefing_visit then update to now().

    Returns the OLD value (read before update -- order matters for team_activity).
    Wraps in try/except for graceful degradation.
    """
    try:
        # Read current value
        stmt = select(Profile.last_briefing_visit).where(Profile.id == user_id)
        result = await session.execute(stmt)
        prev_visit = result.scalar_one_or_none()

        # Update to now
        now = datetime.datetime.now(datetime.timezone.utc)
        update_stmt = (
            update(Profile)
            .where(Profile.id == user_id)
            .values(last_briefing_visit=now)
        )
        await session.execute(update_stmt)
        await session.flush()

        return prev_visit
    except Exception:
        logger.warning("Failed to read/update last_briefing_visit", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Today section builder (meetings + tasks)
# ---------------------------------------------------------------------------


async def _build_today_section(
    session: AsyncSession, user_id: UUID, tenant_id: UUID
) -> dict:
    """Build today section with meetings and tasks for today.

    Returns {"meetings": [...], "tasks": [...]}
    """
    meetings = await _build_meetings(session, user_id, tenant_id)
    tasks = await _build_tasks(session, user_id)
    return {"meetings": meetings, "tasks": tasks}


async def _build_meetings(
    session: AsyncSession, user_id: UUID, tenant_id: UUID
) -> list[dict]:
    """Query meetings for today with company resolution and prep_status."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + datetime.timedelta(days=1)

        stmt = (
            select(Meeting)
            .options(
                joinedload(Meeting.pipeline_entry),
                joinedload(Meeting.account),
            )
            .where(
                Meeting.tenant_id == tenant_id,
                Meeting.user_id == user_id,
                Meeting.meeting_date >= today_start,
                Meeting.meeting_date < today_end,
                Meeting.deleted_at.is_(None),
            )
            .order_by(Meeting.meeting_date.asc())
        )

        result = await session.execute(stmt)
        rows = result.unique().scalars().all()

        meetings = []
        for m in rows:
            # Company resolution: pipeline_entry > account > None
            company: str | None = None
            if m.pipeline_entry is not None:
                company = m.pipeline_entry.name
            elif m.account is not None:
                company = m.account.name

            # Prep status: "available" if skill_run_id or ai_summary present
            prep_status = (
                "available"
                if (m.skill_run_id is not None or m.ai_summary is not None)
                else "none"
            )

            meetings.append({
                "id": str(m.id),
                "title": m.title,
                "time": m.meeting_date.isoformat(),
                "attendees": m.attendees,
                "company": company,
                "prep_status": prep_status,
            })

        return meetings

    except Exception:
        logger.warning("Failed to build meetings for today section", exc_info=True)
        return []


async def _build_tasks(
    session: AsyncSession, user_id: UUID
) -> list[dict]:
    """Query tasks due today (or overdue) that are not done/dismissed."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        today_end = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)

        stmt = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.due_date <= today_end,
                Task.status.notin_(["done", "dismissed"]),
            )
            .order_by(Task.due_date.asc())
        )

        result = await session.execute(stmt)
        rows = result.scalars().all()

        tasks = []
        for t in rows:
            tasks.append({
                "id": str(t.id),
                "title": t.title,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "source": t.source or "manual",
                "status": t.status,
            })

        return tasks

    except Exception:
        logger.warning("Failed to build tasks for today section", exc_info=True)
        return []
