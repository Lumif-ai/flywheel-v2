"""Onboarding endpoints: promotion, subsidy, crawl SSE, stream parsing, and meeting ingest.

Endpoints:
- POST /onboarding/promote          -- promote anonymous user to full account
- GET  /onboarding/subsidy-status   -- remaining anonymous runs
- POST /onboarding/crawl            -- start company crawl, stream SSE with categorized items
- POST /onboarding/parse-streams    -- parse natural language into work streams (anonymous OK)
- POST /onboarding/create-streams   -- batch-create streams with entity seeds (tenant required)
- POST /onboarding/ingest-meetings  -- batch ingest meeting notes (tenant required)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from flywheel.api.deps import get_current_user, get_db_unscoped, get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import (
    ContextEntry,
    OnboardingSession,
    SkillRun,
    Tenant,
    User,
    UserTenant,
)
from flywheel.db.session import get_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

ANONYMOUS_RUN_LIMIT = 3


# ---------------------------------------------------------------------------
# Category detection for crawl items
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "company_info": ["about", "mission", "founded", "headquarters", "history", "overview", "company"],
    "product": ["product", "service", "solution", "platform", "feature", "pricing", "plan"],
    "team": ["team", "leadership", "ceo", "cto", "founder", "executive", "employee", "hire"],
    "market": ["market", "industry", "competitor", "trend", "growth", "opportunity"],
    "technology": ["technology", "stack", "engineering", "api", "infrastructure", "security", "data"],
    "customer": ["customer", "client", "case study", "testimonial", "review", "user"],
    "financial": ["revenue", "funding", "investor", "valuation", "series", "ipo", "financial"],
}

_CATEGORY_ICONS: dict[str, str] = {
    "company_info": "Building2",
    "product": "Package",
    "team": "Users",
    "market": "TrendingUp",
    "technology": "Cpu",
    "customer": "UserCheck",
    "financial": "DollarSign",
}


def _detect_category(content: str) -> str:
    """Detect category from content using keyword matching."""
    content_lower = content.lower()
    scores: dict[str, int] = {}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        scores[category] = sum(1 for kw in keywords if kw in content_lower)
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] > 0 else "company_info"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class PromoteRequest(BaseModel):
    email: str


class PromoteResponse(BaseModel):
    tenant_id: str
    message: str


class SubsidyStatusResponse(BaseModel):
    runs_used: int
    runs_remaining: int
    limit: int


class CrawlRequest(BaseModel):
    url: str


class ParseStreamsRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=2000)


class StreamDef(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    entity_seeds: list[str] = Field(default_factory=list)


class CreateStreamsRequest(BaseModel):
    streams: list[StreamDef] = Field(..., min_length=1, max_length=10)


class MeetingNote(BaseModel):
    content: str = Field(..., min_length=1)
    source: str = "paste"
    title: str | None = None


class IngestMeetingsRequest(BaseModel):
    notes: list[MeetingNote] = Field(..., min_length=1, max_length=50)


# ---------------------------------------------------------------------------
# POST /onboarding/promote (authenticated, anonymous only)
# ---------------------------------------------------------------------------


@router.post("/promote", response_model=PromoteResponse)
async def promote(
    body: PromoteRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Promote an anonymous user to a full account.

    Called after the client has already triggered email confirmation via
    supabase.auth.updateUser({ email }). This endpoint creates the
    tenant, user row, and user_tenants record server-side.
    """
    if not user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already authenticated",
        )

    # Derive tenant name from email domain
    domain = body.email.split("@")[1] if "@" in body.email else "Personal"

    # Create tenant
    tenant = Tenant(name=domain)
    db.add(tenant)
    await db.flush()

    # Create or update user row
    existing_user = (
        await db.execute(select(User).where(User.id == user.sub))
    ).scalar_one_or_none()

    if existing_user is None:
        new_user = User(id=user.sub, email=body.email)
        db.add(new_user)
        await db.flush()
    else:
        existing_user.email = body.email
        await db.flush()

    # Create user_tenants
    ut = UserTenant(
        user_id=user.sub, tenant_id=tenant.id, role="admin", active=True
    )
    db.add(ut)

    # Copy onboarding session data into context_entries for new tenant
    onboarding_rows = (
        await db.execute(
            select(OnboardingSession).where(
                OnboardingSession.user_id == user.sub
            )
        )
    ).scalars().all()

    for session_row in onboarding_rows:
        data = session_row.data or {}
        entries = data.get("context_entries", [])
        for entry in entries:
            ce = ContextEntry(
                tenant_id=tenant.id,
                user_id=user.sub,
                file_name=entry.get("file_name", "onboarding.md"),
                source=entry.get("source", "onboarding"),
                detail=entry.get("detail"),
                content=entry.get("content", ""),
                confidence=entry.get("confidence", "medium"),
            )
            db.add(ce)

    await db.commit()

    return PromoteResponse(
        tenant_id=str(tenant.id),
        message="Account promoted",
    )


# ---------------------------------------------------------------------------
# GET /onboarding/subsidy-status (authenticated, anonymous only)
# ---------------------------------------------------------------------------


@router.get("/subsidy-status", response_model=SubsidyStatusResponse)
async def subsidy_status(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Return remaining subsidized anonymous runs."""
    if not user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not an anonymous user",
        )

    # Count skill runs stored in onboarding_sessions.data
    result = (
        await db.execute(
            select(OnboardingSession.data).where(
                OnboardingSession.user_id == user.sub
            )
        )
    ).scalars().all()

    runs_used = 0
    for data in result:
        if isinstance(data, dict):
            runs_used += len(data.get("skill_runs", []))

    runs_remaining = max(0, ANONYMOUS_RUN_LIMIT - runs_used)

    return SubsidyStatusResponse(
        runs_used=runs_used,
        runs_remaining=runs_remaining,
        limit=ANONYMOUS_RUN_LIMIT,
    )


# ---------------------------------------------------------------------------
# POST /onboarding/crawl (authenticated, anonymous allowed)
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


@router.post("/crawl")
async def crawl(
    body: CrawlRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
) -> EventSourceResponse:
    """Start a company crawl and stream categorized results via SSE.

    Anonymous users can use this endpoint (no tenant required).
    Creates a SkillRun with skill_name='company-intel' and returns
    an SSE stream that polls for events, emitting crawl_item events
    with category, icon, content, and running count.
    """
    # Validate URL format
    if not _URL_RE.match(body.url):
        raise HTTPException(
            status_code=422,
            detail="Invalid URL: must start with http:// or https://",
        )

    # Create SkillRun record
    run = SkillRun(
        tenant_id=user.tenant_id or user.sub,
        user_id=user.sub,
        skill_name="company-intel",
        input_text=body.url,
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await db.commit()

    run_id = run.id

    async def event_generator():
        # Yield started event immediately
        yield {"event": "started", "data": json.dumps({"run_id": str(run_id)})}

        factory = get_session_factory()
        seen_events = 0
        item_count = 0

        while True:
            await asyncio.sleep(1)

            session = factory()
            try:
                result = await session.execute(
                    select(SkillRun).where(SkillRun.id == run_id)
                )
                skill_run = result.scalar_one_or_none()
                if skill_run is None:
                    yield {"event": "error", "data": json.dumps({"message": "Run disappeared"})}
                    return

                # Yield any new events with category enrichment
                events_log = skill_run.events_log or []
                for evt in events_log[seen_events:]:
                    item_count += 1
                    evt_data = evt.get("data", evt)
                    content = ""
                    if isinstance(evt_data, dict):
                        content = evt_data.get("content", evt_data.get("message", ""))
                    elif isinstance(evt_data, str):
                        content = evt_data

                    category = _detect_category(content)
                    icon = _CATEGORY_ICONS.get(category, "Building2")

                    yield {
                        "event": "crawl_item",
                        "data": json.dumps({
                            "category": category,
                            "icon": icon,
                            "content": content,
                            "count": item_count,
                        }),
                    }
                    seen_events += 1

                if skill_run.status in ("completed", "failed"):
                    yield {
                        "event": "crawl_complete",
                        "data": json.dumps({
                            "total_items": item_count,
                            "summary": f"{item_count} entries deposited into your context store",
                        }),
                    }
                    return
            finally:
                await session.close()

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# POST /onboarding/parse-streams (authenticated, anonymous allowed)
# ---------------------------------------------------------------------------


@router.post("/parse-streams")
async def parse_streams(
    body: ParseStreamsRequest,
    user: TokenPayload = Depends(get_current_user),
):
    """Parse natural language work description into 2-4 structured work streams.

    Uses Haiku to extract stream names, descriptions, and entity seeds.
    Anonymous users allowed (no tenant required).
    """
    from flywheel.services.onboarding_streams import parse_work_streams

    streams = await parse_work_streams(body.input)
    return {"streams": streams}


# ---------------------------------------------------------------------------
# POST /onboarding/create-streams (tenant required)
# ---------------------------------------------------------------------------


@router.post("/create-streams", status_code=201)
async def create_streams(
    body: CreateStreamsRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Batch-create work streams with entity seeds.

    Requires an authenticated user with a tenant. Creates WorkStream rows
    plus ContextEntity and WorkStreamEntity records for each seed.
    """
    from flywheel.services.onboarding_streams import create_streams_batch

    streams_data = [s.model_dump() for s in body.streams]
    created = await create_streams_batch(
        streams=streams_data,
        tenant_id=user.tenant_id,
        user_id=user.sub,
        db=db,
    )
    return {"created": created}


# ---------------------------------------------------------------------------
# POST /onboarding/ingest-meetings (tenant required)
# ---------------------------------------------------------------------------


@router.post("/ingest-meetings")
async def ingest_meetings(
    body: IngestMeetingsRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Batch ingest meeting notes into context entries with entity matching.

    Requires an authenticated user with a tenant. Creates context entries
    from each note, matches entities to streams, and returns processing stats.
    """
    from flywheel.services.meeting_ingest import ingest_meeting_notes

    notes_data = [n.model_dump() for n in body.notes]
    result = await ingest_meeting_notes(
        notes=notes_data,
        tenant_id=user.tenant_id,
        user_id=user.sub,
        db=db,
    )
    return result
