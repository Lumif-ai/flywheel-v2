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
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from flywheel.api.deps import get_current_user, get_db_unscoped, get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload, decode_jwt
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


class MeetingPrepRequest(BaseModel):
    linkedin_url: str = Field(..., min_length=1, max_length=500)
    agenda: str = Field(default="", max_length=2000)
    meeting_type: str = Field(default="discovery", max_length=50)


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
                metadata_=entry.get("metadata") or {},
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
):
    """Start a company crawl and return the run_id for SSE streaming.

    Anonymous users can use this endpoint (no tenant required).
    Creates a SkillRun with skill_name='company-intel' and returns
    JSON with run_id. Frontend connects to /skills/runs/{run_id}/stream
    for SSE events.
    """
    # Validate URL format
    if not _URL_RE.match(body.url):
        raise HTTPException(
            status_code=422,
            detail="Invalid URL: must start with http:// or https://",
        )

    # tenant_id is guaranteed by deps.get_current_user (auto-provisions anonymous users)
    tenant_id = user.tenant_id or user.sub

    # Create SkillRun record
    run = SkillRun(
        tenant_id=tenant_id,
        user_id=user.sub,
        skill_name="company-intel",
        input_text=body.url,
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await db.commit()

    return {"run_id": str(run.id)}


# SSE stream endpoint for crawl events (kept for backward compatibility)
@router.get("/crawl/{run_id}/stream")
async def crawl_stream(
    run_id: str,
    token: str | None = None,
    cred: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
) -> EventSourceResponse:
    """Stream crawl events via SSE for a given run_id.

    Accepts JWT via Authorization header OR ?token= query param
    (EventSource API cannot send custom headers).
    """
    jwt_token = cred.credentials if cred else token
    if not jwt_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = decode_jwt(jwt_token)

    async def event_generator():
        # Yield started event (mapped to 'stage' for useSSE compatibility)
        yield {"event": "stage", "data": json.dumps({"run_id": str(run_id), "stage": "started"})}

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
                    seen_events += 1
                    evt_type = evt.get("event", "")
                    evt_data = evt.get("data", evt)

                    # Discovery events: grouped intelligence items
                    if evt_type == "discovery" and isinstance(evt_data, dict):
                        item_count += 1
                        yield {
                            "event": "text",
                            "data": json.dumps({
                                "category": evt_data.get("category", "company_info"),
                                "icon": evt_data.get("icon", "Building2"),
                                "label": evt_data.get("label", ""),
                                "items": evt_data.get("items", []),
                                "count": item_count,
                            }),
                        }
                    # Stage events: progress updates (shown as status text)
                    elif evt_type == "stage" and isinstance(evt_data, dict):
                        yield {
                            "event": "stage",
                            "data": json.dumps({
                                "stage": evt_data.get("stage", ""),
                                "message": evt_data.get("message", ""),
                            }),
                        }

                if skill_run.status in ("completed", "failed"):
                    yield {
                        "event": "done",
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
# GET /onboarding/run/{run_id}/stream -- generic SSE for onboarding skill runs
# ---------------------------------------------------------------------------


@router.get("/run/{run_id}/stream")
async def onboarding_run_stream(
    run_id: str,
    token: str | None = None,
    cred: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
) -> EventSourceResponse:
    """Stream events for any onboarding skill run (meeting-prep, etc.).

    Same auth pattern as crawl_stream: accepts JWT via header or ?token= query param.
    Passes through all events from events_log as-is, plus rendered_html in done event.
    """
    jwt_token = cred.credentials if cred else token
    if not jwt_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    decode_jwt(jwt_token)

    async def event_generator():
        # Yield an initial event so the SSE connection is established immediately
        yield {"event": "stage", "data": json.dumps({"stage": "queued", "message": "Preparing..."})}

        factory = get_session_factory()
        seen_events = 0

        while True:
            await asyncio.sleep(1)

            session = factory()
            try:
                result = await session.execute(
                    select(SkillRun).where(SkillRun.id == run_id)
                )
                skill_run = result.scalar_one_or_none()
                if skill_run is None:
                    yield {"event": "error", "data": json.dumps({"message": "Run not found"})}
                    return

                events_log = skill_run.events_log or []
                for evt in events_log[seen_events:]:
                    seen_events += 1
                    evt_type = evt.get("event", "stage")
                    evt_data = evt.get("data", evt)
                    yield {"event": evt_type, "data": json.dumps(evt_data)}

                if skill_run.status in ("completed", "failed"):
                    yield {
                        "event": "done",
                        "data": json.dumps({
                            "status": skill_run.status,
                            "rendered_html": skill_run.rendered_html or "",
                            "output": skill_run.output or "",
                            "error": skill_run.error,
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
# POST /onboarding/meeting-prep (authenticated, anonymous allowed)
# ---------------------------------------------------------------------------


@router.post("/meeting-prep")
async def meeting_prep(
    body: MeetingPrepRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Start a meeting prep run and return run_id for SSE streaming.

    Takes a LinkedIn URL and optional agenda. Creates a SkillRun with
    skill_name='meeting-prep' that the job queue worker picks up.
    The input_text is formatted as "LinkedIn: {url}\nAgenda: {agenda}".

    Anonymous users can use this (subsidized).
    """
    tenant_id = user.tenant_id or user.sub

    # Format input for the meeting-prep skill
    input_parts = [f"LinkedIn: {body.linkedin_url.strip()}"]
    if body.agenda.strip():
        input_parts.append(f"Agenda: {body.agenda.strip()}")
    if body.meeting_type:
        input_parts.append(f"Type: {body.meeting_type}")

    run = SkillRun(
        tenant_id=tenant_id,
        user_id=user.sub,
        skill_name="meeting-prep",
        input_text="\n".join(input_parts),
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await db.commit()

    return {"run_id": str(run.id)}


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
