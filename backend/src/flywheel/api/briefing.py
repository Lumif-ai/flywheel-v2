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

from flywheel.db.models import SuggestionDismissal, Tenant, WorkItem
from flywheel.services.briefing import assemble_briefing
from flywheel.services.meeting_classifier import (
    get_domain_rules,
    record_classification,
)

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


class BriefingResponse(BaseModel):
    greeting: str
    cards: list[BriefingCard]
    card_count: int
    knowledge_health: KnowledgeHealth
    nudge: dict | None = None


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
    result = await assemble_briefing(db, user.sub)
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
    from flywheel.db.models import WorkStream

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
