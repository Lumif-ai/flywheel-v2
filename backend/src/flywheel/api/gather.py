"""Data-gathering endpoints for MCP tool consumption.

Three read-only, LLM-free endpoints that compose existing DB queries and the
crawl_company() function into structured JSON for downstream MCP tools.

Endpoints:
- GET /gather/company-data       -- crawl a company website
- GET /gather/meeting-context/{id} -- meeting metadata + linked entities
- GET /gather/briefing-sources   -- recent meetings, pipeline, tasks, outreach
"""

from __future__ import annotations

import datetime
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import (
    ContextEntry,
    LeadContact,
    LeadMessage,
    Meeting,
    PipelineEntry,
    Task,
)
from flywheel.engines.company_intel import crawl_company

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gather", tags=["gather"])


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _cap_response(data: dict, max_chars: int) -> dict:
    """Enforce a character cap on the JSON-serialised response.

    Strategy: progressively pop the last item from each list field until the
    serialised size is under *max_chars*.  Always keeps at least one item per
    list so the response is never empty.
    """
    serialised = json.dumps(data, default=str)
    total_chars = len(serialised)

    if total_chars <= max_chars:
        data["total_chars"] = total_chars
        data["truncated"] = False
        data["max_chars"] = max_chars
        return data

    # Identify list fields eligible for trimming (exclude meta keys)
    meta_keys = {"total_chars", "truncated", "max_chars"}
    list_keys = [k for k, v in data.items() if isinstance(v, list) and k not in meta_keys]

    # Progressive trim: cycle through lists popping last items
    truncated = False
    while True:
        serialised = json.dumps(data, default=str)
        if len(serialised) <= max_chars:
            break

        # Try to pop from the longest list first
        trimmed_any = False
        for key in sorted(list_keys, key=lambda k: len(data[k]), reverse=True):
            if len(data[key]) > 1:
                data[key].pop()
                trimmed_any = True
                truncated = True
                break

        if not trimmed_any:
            # All lists are at length 1; truncate string fields as last resort
            for key in ("ai_summary", "content"):
                if key in data and isinstance(data[key], str) and len(data[key]) > 200:
                    data[key] = data[key][:200] + "... [truncated]"
                    truncated = True
            # Also try nested dicts (meeting sub-dict)
            if "meeting" in data and isinstance(data["meeting"], dict):
                m = data["meeting"]
                if "ai_summary" in m and isinstance(m["ai_summary"], str) and len(m["ai_summary"]) > 200:
                    m["ai_summary"] = m["ai_summary"][:200] + "... [truncated]"
                    truncated = True
            break

    serialised = json.dumps(data, default=str)
    data["total_chars"] = len(serialised)
    data["truncated"] = truncated
    data["max_chars"] = max_chars
    return data


# ---------------------------------------------------------------------------
# GET /gather/company-data
# ---------------------------------------------------------------------------


@router.get("/company-data")
async def get_company_data(
    url: str,
    max_chars: int = Query(default=16384, ge=100, le=100_000),
    user: TokenPayload = Depends(require_tenant),
):
    """Crawl a company website and return structured page content."""
    try:
        crawl_result = await crawl_company(url)
    except Exception as exc:
        logger.warning("crawl_company failed for %s: %s", url, exc)
        return {
            "url": url,
            "pages_crawled": 0,
            "success": False,
            "content": f"Crawl failed: {exc}",
            "total_chars": 0,
            "truncated": False,
            "max_chars": max_chars,
        }

    raw_pages: dict = crawl_result.get("raw_pages", {})
    pages_crawled = crawl_result.get("pages_crawled", len(raw_pages))
    success = crawl_result.get("success", bool(raw_pages))

    # Flatten pages into a single string with path separators
    parts = []
    for path, text in raw_pages.items():
        parts.append(f"--- {path} ---\n{text}")
    combined = "\n\n".join(parts)

    total_chars = len(combined)
    truncated = False
    if len(combined) > max_chars:
        combined = combined[:max_chars]
        truncated = True

    return {
        "url": url,
        "pages_crawled": pages_crawled,
        "success": success,
        "content": combined,
        "total_chars": total_chars,
        "truncated": truncated,
        "max_chars": max_chars,
    }


# ---------------------------------------------------------------------------
# GET /gather/meeting-context/{meeting_id}
# ---------------------------------------------------------------------------


@router.get("/meeting-context/{meeting_id}")
async def get_meeting_context(
    meeting_id: UUID,
    max_chars: int = Query(default=16384, ge=100, le=100_000),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Return meeting metadata, linked pipeline entry, and context entries."""
    # Fetch meeting with tenant scope
    result = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.tenant_id == user.tenant_id,
            Meeting.deleted_at.is_(None),
        )
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    # Owner check: only the meeting owner sees ai_summary
    is_owner = str(meeting.user_id) == str(user.sub)
    ai_summary = meeting.ai_summary if is_owner else None

    meeting_data = {
        "id": str(meeting.id),
        "title": meeting.title,
        "meeting_date": str(meeting.meeting_date) if meeting.meeting_date else None,
        "attendees": meeting.attendees,
        "meeting_type": meeting.meeting_type,
        "ai_summary": ai_summary,
        "duration_mins": meeting.duration_mins,
    }

    # Linked pipeline entry
    pipeline_data = None
    if meeting.pipeline_entry_id:
        pe_result = await db.execute(
            select(PipelineEntry).where(
                PipelineEntry.id == meeting.pipeline_entry_id,
                PipelineEntry.tenant_id == user.tenant_id,
            )
        )
        pe = pe_result.scalar_one_or_none()
        if pe:
            pipeline_data = {
                "id": str(pe.id),
                "name": pe.name,
                "stage": pe.stage,
                "domain": pe.domain,
                "entity_type": pe.entity_type,
            }

    # Context entries related to this meeting
    context_entries = []
    if meeting.title:
        ctx_result = await db.execute(
            select(ContextEntry).where(
                ContextEntry.tenant_id == user.tenant_id,
                ContextEntry.source == "ctx-meeting-processor",
                ContextEntry.content.ilike(f"%{meeting.title}%"),
                ContextEntry.deleted_at.is_(None),
            ).limit(5)
        )
        for entry in ctx_result.scalars().all():
            context_entries.append({
                "id": str(entry.id),
                "file_name": entry.file_name,
                "content": entry.content,
                "date": str(entry.date) if entry.date else None,
            })

    response = {
        "meeting": meeting_data,
        "pipeline_entry": pipeline_data,
        "context_entries": context_entries,
    }
    return _cap_response(response, max_chars)


# ---------------------------------------------------------------------------
# GET /gather/briefing-sources
# ---------------------------------------------------------------------------


@router.get("/briefing-sources")
async def get_briefing_sources(
    max_chars: int = Query(default=16384, ge=100, le=100_000),
    days: int = Query(default=7, ge=1, le=90),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Return recent meetings, pipeline changes, tasks, and outreach due."""
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=days)

    # Recent meetings (user-scoped, non-deleted)
    meetings_result = await db.execute(
        select(Meeting).where(
            Meeting.tenant_id == user.tenant_id,
            Meeting.user_id == user.sub,
            Meeting.deleted_at.is_(None),
            Meeting.meeting_date >= cutoff,
        ).order_by(Meeting.meeting_date.desc()).limit(20)
    )
    meetings = [
        {
            "id": str(m.id),
            "title": m.title,
            "meeting_date": str(m.meeting_date) if m.meeting_date else None,
            "meeting_type": m.meeting_type,
            "attendees": m.attendees,
        }
        for m in meetings_result.scalars().all()
    ]

    # Pipeline entries with recent activity
    pipeline_result = await db.execute(
        select(PipelineEntry).where(
            PipelineEntry.tenant_id == user.tenant_id,
            PipelineEntry.updated_at >= cutoff,
        ).limit(20)
    )
    pipeline_entries = [
        {
            "id": str(pe.id),
            "name": pe.name,
            "stage": pe.stage,
            "domain": pe.domain,
            "entity_type": pe.entity_type,
        }
        for pe in pipeline_result.scalars().all()
    ]

    # Active tasks (user-scoped)
    tasks_result = await db.execute(
        select(Task).where(
            Task.tenant_id == user.tenant_id,
            Task.user_id == user.sub,
            Task.status.in_(["detected", "in_review", "confirmed", "deferred"]),
        ).limit(30)
    )
    tasks = [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_date": str(t.due_date) if t.due_date else None,
            "source": t.source,
        }
        for t in tasks_result.scalars().all()
    ]

    # Outreach due (drafted messages, join contact for name)
    # Note: LeadMessage has no send_after field; we filter on status='drafted'
    outreach_result = await db.execute(
        select(LeadMessage, LeadContact).join(
            LeadContact, LeadMessage.contact_id == LeadContact.id
        ).where(
            LeadMessage.tenant_id == user.tenant_id,
            LeadMessage.status == "drafted",
        ).limit(10)
    )
    outreach_due = [
        {
            "id": str(msg.id),
            "contact_name": contact.name,
            "contact_email": contact.email,
            "subject": msg.subject,
            "channel": msg.channel,
            "step_number": msg.step_number,
        }
        for msg, contact in outreach_result.all()
    ]

    response = {
        "meetings": meetings,
        "pipeline_entries": pipeline_entries,
        "tasks": tasks,
        "outreach_due": outreach_due,
    }
    return _cap_response(response, max_chars)
