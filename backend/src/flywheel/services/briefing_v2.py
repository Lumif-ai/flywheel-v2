"""Briefing V2 assembly service -- five-section morning standup briefing.

Assembles: narrative_summary, today (meetings + tasks), attention_items,
team_activity, and tasks_today into BriefingV2Response shape.

Plan 01 implements: today section (meetings + tasks), narrative stub,
last_briefing_visit tracking. Plan 02 fills attention, team_activity,
and replaces narrative stub with LLM implementation.

All functions receive an AsyncSession that is already tenant-scoped via RLS.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from datetime import timedelta
from uuid import UUID

import anthropic
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from flywheel.config import settings
from flywheel.db.models import (
    Account,
    Activity,
    ContextEntry,
    Document,
    Email,
    EmailDraft,
    Meeting,
    PipelineEntry,
    Profile,
    SkillRun,
    Task,
)
from flywheel.services.circuit_breaker import anthropic_breaker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def assemble_briefing_v2(
    session: AsyncSession, user_id: str | UUID, tenant_id: str | UUID,
    *, tz: str | None = None,
) -> dict:
    """Assemble the five-section briefing v2 response.

    Returns a dict matching BriefingV2Response schema:
    {narrative_summary, today, attention_items, team_activity, tasks_today}

    Order matters: today + attention + team_activity are built first so their
    counts can be passed to _generate_narrative.
    """
    uid = UUID(str(user_id))
    tid = UUID(str(tenant_id))

    # Track visit (read old timestamp, write new one)
    prev_visit = await _get_and_update_last_visit(session, uid)

    # 1. Build today section (meetings + tasks)
    today_section = await _build_today_section(session, uid, tid, tz=tz)

    # 2. Build attention and team_activity sections
    attention = await _build_attention_section(session, uid, tid)
    team_activity = await _build_team_activity(session, tid, prev_visit)

    # 3. Compute counts for narrative
    attention_count = (
        len(attention["replies"])
        + len(attention["follow_ups"])
        + len(attention["drafts"])
    )
    team_activity_count = sum(g["count"] for g in team_activity)

    # 4. Generate narrative LAST (needs counts from all sections)
    narrative = await _generate_narrative(
        session,
        str(uid),
        str(tid),
        meetings=today_section["meetings"],
        tasks=today_section["tasks"],
        attention_count=attention_count,
        team_activity_count=team_activity_count,
        tz=tz,
    )

    return {
        "narrative_summary": narrative,
        "today": today_section,
        "attention_items": attention,
        "team_activity": team_activity,
        # tasks_today is a CONVENIENCE COPY of today.tasks at the top level.
        # Both contain identical data. This duplication is intentional per API-01.
        "tasks_today": today_section["tasks"],
    }


# ---------------------------------------------------------------------------
# Narrative generation (LLM with circuit breaker + template fallback)
# ---------------------------------------------------------------------------


async def _generate_narrative(
    session: AsyncSession,
    user_id: str,
    tenant_id: str,
    meetings: list,
    tasks: list,
    attention_count: int = 0,
    team_activity_count: int = 0,
    tz: str | None = None,
) -> str:
    """Generate a 2-3 sentence narrative summary using Claude Haiku.

    Gathers real data (names, titles, not just counts) so the LLM can write
    a meaningful, personalized morning brief. Falls back to template string
    on any failure (timeout, API error, circuit breaker open).
    """
    try:
        # 1. Get user's first name
        user_name = "there"
        try:
            stmt = select(Profile.name).where(Profile.id == UUID(user_id))
            result = await session.execute(stmt)
            full_name = result.scalar_one_or_none()
            if full_name:
                user_name = full_name.split()[0]
        except Exception:
            logger.warning("Failed to fetch user name for narrative", exc_info=True)

        # 2. Recent pipeline entries (names, not just count)
        pipeline_names: list[str] = []
        try:
            seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - timedelta(days=7)
            stmt = (
                select(PipelineEntry.name)
                .where(
                    PipelineEntry.owner_id == UUID(user_id),
                    PipelineEntry.created_at > seven_days_ago,
                )
                .order_by(PipelineEntry.created_at.desc())
                .limit(5)
            )
            result = await session.execute(stmt)
            pipeline_names = [r for r in result.scalars().all()]
        except Exception:
            logger.warning("Failed to fetch pipeline names for narrative", exc_info=True)

        # 3. Recent completed skill run names
        skill_names: list[str] = []
        try:
            twenty_four_hours_ago = datetime.datetime.now(datetime.timezone.utc) - timedelta(hours=24)
            stmt = (
                select(func.distinct(SkillRun.skill_name))
                .where(
                    SkillRun.tenant_id == UUID(tenant_id),
                    SkillRun.status == "completed",
                    SkillRun.created_at > twenty_four_hours_ago,
                )
                .limit(5)
            )
            result = await session.execute(stmt)
            skill_names = [r for r in result.scalars().all()]
        except Exception:
            logger.warning("Failed to fetch skill names for narrative", exc_info=True)

        # 4. Build structured facts dict
        # Pre-format meeting times in user's timezone so the LLM doesn't misinterpret ISO offsets
        from zoneinfo import ZoneInfo
        user_tz = datetime.timezone.utc
        if tz:
            try:
                user_tz = ZoneInfo(tz)
            except (KeyError, ValueError):
                pass

        def _format_meeting_time(iso_str: str | None) -> str:
            if not iso_str:
                return "unknown time"
            try:
                dt = datetime.datetime.fromisoformat(iso_str)
                local_dt = dt.astimezone(user_tz)
                return local_dt.strftime("%-I:%M %p")  # e.g. "11:00 AM"
            except (ValueError, TypeError):
                return iso_str

        facts = {
            "user_name": user_name,
            "user_timezone": tz or "UTC",
            "meeting_count": len(meetings),
            "meetings": [
                {
                    "title": m.get("title", "Untitled"),
                    "time": _format_meeting_time(m.get("time")),
                    "company": m.get("company"),
                    "attendees": [
                        a.get("name", a.get("email", ""))
                        for a in (m.get("attendees") or [])[:3]
                    ],
                }
                for m in meetings[:5]
            ],
            "tasks_due": len(tasks),
            "task_titles": [t.get("title", "") for t in tasks[:5]],
            "attention_items": attention_count,
            "team_actions": team_activity_count,
            "recent_pipeline_entries": pipeline_names,
            "recent_skills": skill_names,
        }

        # 5. Check circuit breaker
        if not anthropic_breaker.can_execute():
            return _template_fallback(facts)

        # 6. Call Anthropic Haiku with 5-second timeout
        client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
        try:
            response = await asyncio.wait_for(
                client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=256,
                    system=(
                        "You are a warm, concise chief of staff writing a 2-3 sentence "
                        "morning brief for a startup founder. Reference SPECIFIC details "
                        "from the data: mention meeting titles or company names, task names, "
                        "skill names that ran, or pipeline entries by name. Keep the tone "
                        "encouraging and action-oriented. Do not use bullet points or "
                        "headers -- just flowing prose. Do not greet by name (the UI handles that)."
                    ),
                    messages=[{"role": "user", "content": json.dumps(facts)}],
                ),
                timeout=5.0,
            )
            anthropic_breaker.record_success()
            return response.content[0].text.strip()

        except asyncio.TimeoutError:
            anthropic_breaker.record_failure()
            logger.warning("Narrative LLM call timed out after 5s, using fallback")
            return _template_fallback(facts)

    except Exception:
        anthropic_breaker.record_failure()
        logger.warning("Narrative generation failed, using template fallback", exc_info=True)
        return _template_fallback(facts if "facts" in dir() else {
            "meeting_count": len(meetings),
            "tasks_due": len(tasks),
            "attention_items": attention_count,
            "team_actions": team_activity_count,
            "user_name": "there",
            "recent_pipeline_entries": [],
            "recent_skills": [],
            "meetings": [],
            "task_titles": [],
        })


def _template_fallback(facts: dict) -> str:
    """Simple template string when LLM is unavailable."""
    meeting_count = facts.get("meeting_count", 0)
    tasks_due = facts.get("tasks_due", 0)
    attention_items = facts.get("attention_items", 0)

    parts = []
    if meeting_count:
        parts.append(f"You have {meeting_count} meeting(s) today")
    if tasks_due:
        parts.append(f"{tasks_due} task(s) due")
    if attention_items:
        parts.append(f"{attention_items} item(s) need your attention")

    if not parts:
        return "Your day is clear. A great time to focus on strategic work."

    return ". ".join(parts) + "."


# ---------------------------------------------------------------------------
# Attention items section builder
# ---------------------------------------------------------------------------


async def _build_attention_section(
    session: AsyncSession, user_id: UUID, tenant_id: UUID
) -> dict:
    """Build attention items: replies, follow-ups, and drafts.

    Each sub-list is wrapped in its own try/except so a single query
    failure does not take down the entire section.
    """
    replies = await _build_attention_replies(session, user_id)
    follow_ups = await _build_attention_follow_ups(session, user_id)
    drafts = await _build_attention_drafts(session, user_id)
    return {"replies": replies, "follow_ups": follow_ups, "drafts": drafts}


async def _build_attention_replies(
    session: AsyncSession, user_id: UUID
) -> list[dict]:
    """Inbound email activities on user's pipeline entries from last 7 days."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        stmt = (
            select(Activity)
            .join(PipelineEntry, Activity.pipeline_entry_id == PipelineEntry.id)
            .options(joinedload(Activity.contact))
            .where(
                PipelineEntry.owner_id == user_id,
                Activity.direction == "inbound",
                Activity.type == "email",
                Activity.created_at > seven_days_ago,
            )
            .order_by(Activity.occurred_at.desc())
            .limit(10)
        )

        result = await session.execute(stmt)
        rows = result.unique().scalars().all()

        items = []
        for a in rows:
            contact_name = None
            if a.contact is not None:
                # Contact model should have a name field
                contact_name = getattr(a.contact, "name", None)

            items.append({
                "id": str(a.id),
                "type": "reply",
                "title": a.subject or "Reply received",
                "preview": a.body_preview[:100] if a.body_preview else None,
                "contact_name": contact_name,
                "company_name": None,
            })
        return items

    except Exception:
        logger.warning("Failed to build attention replies", exc_info=True)
        return []


async def _build_attention_follow_ups(
    session: AsyncSession, user_id: UUID
) -> list[dict]:
    """Pipeline entries with no activity in >3 days in outreach stages."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        three_days_ago = now - timedelta(days=3)

        stmt = (
            select(PipelineEntry)
            .where(
                PipelineEntry.owner_id == user_id,
                PipelineEntry.stage.in_(["outreach", "contacted", "engaged"]),
                PipelineEntry.last_activity_at < three_days_ago,
                PipelineEntry.retired_at.is_(None),
            )
            .order_by(PipelineEntry.last_activity_at.asc())
            .limit(10)
        )

        result = await session.execute(stmt)
        rows = result.scalars().all()

        items = []
        for pe in rows:
            days_overdue = (now - pe.last_activity_at).days if pe.last_activity_at else 0
            items.append({
                "id": str(pe.id),
                "type": "follow_up",
                "title": pe.name,
                "preview": None,
                "contact_name": None,
                "company_name": None,
                "days_overdue": days_overdue,
            })
        return items

    except Exception:
        logger.warning("Failed to build attention follow-ups", exc_info=True)
        return []


async def _build_attention_drafts(
    session: AsyncSession, user_id: UUID
) -> list[dict]:
    """Pending email drafts awaiting review."""
    try:
        stmt = (
            select(EmailDraft, Email.subject, Email.sender_name)
            .join(Email, EmailDraft.email_id == Email.id)
            .where(
                Email.user_id == user_id,
                EmailDraft.status == "pending",
            )
            .order_by(EmailDraft.created_at.desc())
            .limit(10)
        )

        result = await session.execute(stmt)
        rows = result.all()

        items = []
        for draft, email_subject, sender_name in rows:
            items.append({
                "id": str(draft.id),
                "type": "draft",
                "title": email_subject or "Draft reply",
                "preview": draft.draft_body[:100] if draft.draft_body else None,
                "contact_name": sender_name,
                "company_name": None,
            })
        return items

    except Exception:
        logger.warning("Failed to build attention drafts", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Team activity section builder
# ---------------------------------------------------------------------------


async def _build_team_activity(
    session: AsyncSession, tenant_id: UUID, last_visit: datetime.datetime | None
) -> list[dict]:
    """Build team activity groups: skill_runs, context_writes, documents.

    Filters by last_visit timestamp. If None, defaults to 24 hours ago.
    Only returns groups with count > 0.
    """
    since = last_visit or (
        datetime.datetime.now(datetime.timezone.utc) - timedelta(hours=24)
    )

    groups: list[dict] = []

    # Skill runs since last visit
    skill_runs_group = await _build_team_skill_runs(session, tenant_id, since)
    if skill_runs_group["count"] > 0:
        groups.append(skill_runs_group)

    # Context writes since last visit
    context_group = await _build_team_context_writes(session, tenant_id, since)
    if context_group["count"] > 0:
        groups.append(context_group)

    # Documents since last visit
    docs_group = await _build_team_documents(session, tenant_id, since)
    if docs_group["count"] > 0:
        groups.append(docs_group)

    return groups


async def _build_team_skill_runs(
    session: AsyncSession, tenant_id: UUID, since: datetime.datetime
) -> dict:
    """Completed skill runs since last visit."""
    try:
        stmt = (
            select(SkillRun)
            .where(
                SkillRun.tenant_id == tenant_id,
                SkillRun.status == "completed",
                SkillRun.created_at > since,
            )
            .order_by(SkillRun.created_at.desc())
        )

        result = await session.execute(stmt)
        runs = result.scalars().all()

        return {
            "type": "skill_runs",
            "count": len(runs),
            "items": [
                {
                    "id": str(r.id),
                    "skill_name": r.skill_name,
                    "created_at": r.created_at.isoformat(),
                }
                for r in runs
            ],
        }

    except Exception:
        logger.warning("Failed to build team skill runs", exc_info=True)
        return {"type": "skill_runs", "count": 0, "items": []}


async def _build_team_context_writes(
    session: AsyncSession, tenant_id: UUID, since: datetime.datetime
) -> dict:
    """Context entries written since last visit."""
    try:
        stmt = (
            select(ContextEntry)
            .where(
                ContextEntry.tenant_id == tenant_id,
                ContextEntry.deleted_at.is_(None),
                ContextEntry.created_at > since,
            )
            .order_by(ContextEntry.created_at.desc())
        )

        result = await session.execute(stmt)
        entries = result.scalars().all()

        return {
            "type": "context_writes",
            "count": len(entries),
            "items": [
                {
                    "id": str(e.id),
                    "file_name": e.file_name,
                    "created_at": e.created_at.isoformat(),
                }
                for e in entries
            ],
        }

    except Exception:
        logger.warning("Failed to build team context writes", exc_info=True)
        return {"type": "context_writes", "count": 0, "items": []}


async def _build_team_documents(
    session: AsyncSession, tenant_id: UUID, since: datetime.datetime
) -> dict:
    """Documents created since last visit."""
    try:
        stmt = (
            select(Document)
            .where(
                Document.tenant_id == tenant_id,
                Document.created_at > since,
            )
            .order_by(Document.created_at.desc())
        )

        result = await session.execute(stmt)
        docs = result.scalars().all()

        return {
            "type": "documents",
            "count": len(docs),
            "items": [
                {
                    "id": str(d.id),
                    "title": d.title,
                    "document_type": d.document_type,
                    "created_at": d.created_at.isoformat(),
                }
                for d in docs
            ],
        }

    except Exception:
        logger.warning("Failed to build team documents", exc_info=True)
        return {"type": "documents", "count": 0, "items": []}


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
    session: AsyncSession, user_id: UUID, tenant_id: UUID,
    *, tz: str | None = None,
) -> dict:
    """Build today section with meetings and tasks for today.

    Returns {"meetings": [...], "tasks": [...]}
    """
    meetings = await _build_meetings(session, user_id, tenant_id, tz=tz)
    tasks = await _build_tasks(session, user_id)
    return {"meetings": meetings, "tasks": tasks}


def _is_internal_meeting(
    attendees: list[dict] | None,
    tenant_domain: str | None,
) -> bool:
    """Return True if all attendees share the tenant's email domain (internal meeting)."""
    if not attendees or not tenant_domain:
        return False
    td = tenant_domain.lower()
    for a in attendees:
        email = (a.get("email") or "").lower()
        if not email:
            continue
        domain = email.rsplit("@", 1)[-1] if "@" in email else ""
        if domain and domain != td:
            return False
    return True


async def _build_meetings(
    session: AsyncSession, user_id: UUID, tenant_id: UUID,
    *, tz: str | None = None,
) -> list[dict]:
    """Query meetings for today with company resolution and prep_status.

    Triggers a calendar sync first to ensure fresh data, then queries
    using the user's timezone to calculate "today" boundaries.
    """
    try:
        from zoneinfo import ZoneInfo

        # Use the user's timezone to determine "today"
        user_tz = datetime.timezone.utc
        if tz:
            try:
                user_tz = ZoneInfo(tz)
            except (KeyError, ValueError):
                logger.warning("Invalid timezone %r, falling back to UTC", tz)

        now_user = datetime.datetime.now(user_tz)
        today_start = now_user.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + datetime.timedelta(days=1)

        # Get tenant domain for internal/external classification
        from flywheel.db.models import Tenant
        tenant_row = (await session.execute(
            select(Tenant.domain).where(Tenant.id == tenant_id)
        )).scalar_one_or_none()
        tenant_domain = tenant_row if tenant_row else None

        stmt = (
            select(Meeting)
            .options(
                joinedload(Meeting.pipeline_entry),
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
            # Company resolution from pipeline_entry
            company: str | None = None
            if m.pipeline_entry is not None:
                company = m.pipeline_entry.name

            # Prep status: "available" if skill_run_id or ai_summary present
            prep_status = (
                "available"
                if (m.skill_run_id is not None or m.ai_summary is not None)
                else "none"
            )

            # Internal classification: use meeting_type if set, else check attendee domains
            mt = m.meeting_type
            is_internal = mt in ("internal", "team-meeting") if mt else _is_internal_meeting(m.attendees, tenant_domain)

            meetings.append({
                "id": str(m.id),
                "title": m.title,
                "time": m.meeting_date.isoformat(),
                "attendees": m.attendees,
                "company": company,
                "prep_status": prep_status,
                "meeting_type": mt,
                "is_internal": is_internal,
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
