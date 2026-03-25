"""Briefing REST endpoint -- proactive morning intelligence.

Endpoints:
- GET /briefing  -- assembled briefing with greeting, cards, knowledge health, nudge
- POST /briefing/dismiss  -- dismiss a card for 7 days
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from sqlalchemy import select

from flywheel.db.models import (
    ContextEntry,
    Profile,
    SuggestionDismissal,
    Tenant,
    WorkItem,
    WorkStream,
)
from flywheel.services.briefing import assemble_briefing
from flywheel.services.meeting_classifier import (
    get_domain_rules,
    record_classification,
)
from flywheel.services.nudge_engine import record_nudge_action

router = APIRouter(prefix="/briefing", tags=["briefing"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class BriefingCard(BaseModel):
    type: str  # "meeting" | "meeting_prep" | "stale_context"
    priority: str  # "high" | "medium" | "low"
    sort_order: int
    title: str
    detail: str
    scheduled_at: datetime.datetime | None = None
    entity_matches: list[dict] | None = None
    work_item_id: str | None = None
    suggestion_key: str | None = None
    file_name: str | None = None
    days_stale: int | None = None
    entry_count: int | None = None
    reason: str | None = None
    source_attribution: list[dict] | None = None
    auto_classified: bool = False
    change_option: bool = False
    stream_id: str | None = None
    classification_confidence: str | None = None


class ClassifyMeetingRequest(BaseModel):
    work_item_id: str
    stream_id: str


class ClassifyMeetingResponse(BaseModel):
    classified: bool
    stream_name: str


class DismissRequest(BaseModel):
    card_type: str
    suggestion_key: str
    feedback: str = "not_relevant"  # "not_relevant" | "already_handled"


class DismissResponse(BaseModel):
    dismissed: bool


class KnowledgeHealth(BaseModel):
    total_streams: int
    avg_density: float
    total_entries: int
    total_entities: int
    health_level: str  # "strong" | "growing" | "early"


class NudgeResponse(BaseModel):
    type: str  # "calendar_meeting_prep" | "integration_connect" | "knowledge_gap" | "context_enrichment"
    key: str
    title: str
    body: str
    provider: str | None = None
    action_url: str | None = None
    action_label: str | None = None
    stream_id: str | None = None
    stream_name: str | None = None
    entity_id: str | None = None
    entity_name: str | None = None
    has_research_action: bool = False
    # Calendar meeting prep fields
    action_type: str | None = None
    action_payload: dict | None = None


class FirstVisitData(BaseModel):
    briefing_html: str | None = None
    intel_summary: dict | None = None
    primary_priority: str = "grow_revenue"


class BriefingResponse(BaseModel):
    greeting: str
    cards: list[BriefingCard]
    card_count: int
    knowledge_health: KnowledgeHealth
    nudge: NudgeResponse | None = None
    is_first_visit: bool = False
    first_visit: FirstVisitData | None = None


class NudgeDismissRequest(BaseModel):
    nudge_type: str
    nudge_key: str


class NudgeDismissResponse(BaseModel):
    dismissed: bool


class NudgeSubmitRequest(BaseModel):
    nudge_key: str
    stream_id: str
    text: str  # The user's inline text input


class NudgeSubmitResponse(BaseModel):
    submitted: bool
    entry_id: str


class NudgeResearchRequest(BaseModel):
    nudge_key: str
    entity_id: str
    entity_name: str


class NudgeResearchResponse(BaseModel):
    triggered: bool
    work_item_id: str


# ---------------------------------------------------------------------------
# GET /briefing
# ---------------------------------------------------------------------------


@router.get("", response_model=BriefingResponse)
async def get_briefing(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Return the assembled briefing for the authenticated user.

    Includes time-based greeting, up to 10 prioritized cards
    (meetings > suggestions > stale context), knowledge health
    metrics from work stream density, and nudge placeholder.
    """
    import logging
    _log = logging.getLogger("flywheel.briefing.debug")
    _log.warning("BRIEFING DEBUG: tenant=%s user=%s", user.tenant_id, user.sub)
    result = await assemble_briefing(db, user.sub, user.tenant_id)
    _log.warning("BRIEFING DEBUG: is_first_visit=%s, first_visit=%s",
                 result.get("is_first_visit"), "present" if result.get("first_visit") else "None")
    return result


# ---------------------------------------------------------------------------
# POST /briefing/dismiss
# ---------------------------------------------------------------------------


@router.post("/dismiss", response_model=DismissResponse)
async def dismiss_card(
    body: DismissRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Dismiss a briefing card for 7 days.

    Creates a SuggestionDismissal row that prevents the card
    from appearing in subsequent briefing calls until expired.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    dismissal = SuggestionDismissal(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        suggestion_type=body.card_type,
        suggestion_key=body.suggestion_key,
        dismissed_at=now,
        expires_at=now + datetime.timedelta(days=7),
    )
    db.add(dismissal)
    await db.commit()
    return DismissResponse(dismissed=True)


# ---------------------------------------------------------------------------
# POST /briefing/classify-meeting
# ---------------------------------------------------------------------------


@router.post("/classify-meeting", response_model=ClassifyMeetingResponse)
async def classify_meeting_endpoint(
    body: ClassifyMeetingRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Classify a meeting by assigning it to a work stream.

    Records the user's classification decision. After 3+ classifications
    from the same email domain, future meetings auto-classify via pattern learning.
    """
    from uuid import UUID as _UUID

    work_item_id = _UUID(body.work_item_id)
    stream_id = _UUID(body.stream_id)

    # Fetch work item to extract email domain
    result = await db.execute(
        select(WorkItem).where(WorkItem.id == work_item_id)
    )
    work_item = result.scalar_one_or_none()

    email_domain: str | None = None
    if work_item:
        attendees = (work_item.data or {}).get("attendees", [])
        # Extract first external domain
        for email in attendees:
            if "@" in email:
                email_domain = email.split("@", 1)[1].lower()
                break

    # Record the classification
    await record_classification(
        session=db,
        tenant_id=user.tenant_id,
        user_id=user.sub,
        work_item_id=work_item_id,
        stream_id=stream_id,
        email_domain=email_domain,
    )

    # Update the work item's classification data
    if work_item:
        # Fetch stream name
        stream_result = await db.execute(
            select(WorkStream.name).where(WorkStream.id == stream_id)
        )
        stream_name = stream_result.scalar_one_or_none() or "Unknown"

        updated_data = dict(work_item.data or {})
        updated_data["classification"] = {
            "confidence": "high",
            "stream_id": str(stream_id),
            "reason": f"User classified -> {stream_name}",
            "source": "user_classified",
        }
        work_item.data = updated_data

    # Check if domain now has 3+ classifications -> update tenant rules
    if email_domain:
        domain_rules = await get_domain_rules(db, user.tenant_id)
        if domain_rules:
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.id == user.tenant_id)
            )
            tenant = tenant_result.scalar_one_or_none()
            if tenant:
                settings = dict(tenant.settings or {})
                settings["classification_rules"] = domain_rules
                tenant.settings = settings

    await db.commit()

    # Fetch stream name for response
    stream_name_result = await db.execute(
        select(WorkStream.name).where(WorkStream.id == stream_id)
    )
    final_stream_name = stream_name_result.scalar_one_or_none() or "Unknown"

    return ClassifyMeetingResponse(
        classified=True,
        stream_name=final_stream_name,
    )


# ---------------------------------------------------------------------------
# POST /briefing/nudge/dismiss
# ---------------------------------------------------------------------------


@router.post("/nudge/dismiss", response_model=NudgeDismissResponse)
async def dismiss_nudge(
    body: NudgeDismissRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Dismiss a nudge for 7 days.

    Creates a SuggestionDismissal with type='nudge' and records a
    nudge_interaction with action='dismissed'. The nudge will not
    resurface until the dismissal expires.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    # Create 7-day dismissal
    dismissal = SuggestionDismissal(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        suggestion_type="nudge",
        suggestion_key=body.nudge_key,
        dismissed_at=now,
        expires_at=now + datetime.timedelta(days=7),
    )
    db.add(dismissal)

    # Record nudge interaction
    await record_nudge_action(
        db, user.tenant_id, user.sub,
        body.nudge_type, body.nudge_key, "dismissed",
    )

    await db.commit()
    return NudgeDismissResponse(dismissed=True)


# ---------------------------------------------------------------------------
# POST /briefing/nudge/submit
# ---------------------------------------------------------------------------


@router.post("/nudge/submit", response_model=NudgeSubmitResponse)
async def submit_nudge(
    body: NudgeSubmitRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Submit inline text for a knowledge gap nudge.

    Creates a ContextEntry from the user's text input and records
    the nudge interaction as completed.
    """
    from uuid import UUID as _UUID

    stream_id = _UUID(body.stream_id)

    # Fetch stream name for detail field
    stream_result = await db.execute(
        select(WorkStream.name).where(WorkStream.id == stream_id)
    )
    stream_name = stream_result.scalar_one_or_none() or "knowledge-gaps"

    # Create context entry from user's text
    entry = ContextEntry(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        file_name="knowledge-gaps",
        source="user-nudge",
        detail=stream_name,
        confidence="medium",
        content=body.text,
        metadata_={},
    )
    db.add(entry)
    await db.flush()  # Get entry.id

    # Record nudge interaction as completed
    await record_nudge_action(
        db, user.tenant_id, user.sub,
        "knowledge_gap", body.nudge_key, "completed",
        data={"entry_id": str(entry.id)},
    )

    await db.commit()
    return NudgeSubmitResponse(submitted=True, entry_id=str(entry.id))


# ---------------------------------------------------------------------------
# POST /briefing/nudge/research
# ---------------------------------------------------------------------------


@router.post("/nudge/research", response_model=NudgeResearchResponse)
async def trigger_research(
    body: NudgeResearchRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Trigger background research for a context enrichment nudge.

    Requires the user to have a BYOK API key configured. Creates a
    WorkItem with type='nudge_research' for the job queue worker.
    """
    from fastapi import HTTPException

    # Check if user has BYOK API key
    user_result = await db.execute(
        select(Profile.api_key_encrypted).where(Profile.id == user.sub)
    )
    api_key = user_result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=400,
            detail="API key required for research. Add one in Settings.",
        )

    # Create work item for job queue
    work_item = WorkItem(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        type="nudge_research",
        title=f"Research {body.entity_name}",
        status="pending",
        source="nudge",
        data={
            "entity_id": body.entity_id,
            "entity_name": body.entity_name,
            "nudge_key": body.nudge_key,
        },
    )
    db.add(work_item)
    await db.flush()  # Get work_item.id

    # Record nudge interaction as completed
    await record_nudge_action(
        db, user.tenant_id, user.sub,
        "context_enrichment", body.nudge_key, "completed",
        data={"work_item_id": str(work_item.id)},
    )

    await db.commit()
    return NudgeResearchResponse(
        triggered=True, work_item_id=str(work_item.id)
    )
