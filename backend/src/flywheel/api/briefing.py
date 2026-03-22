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
from flywheel.db.models import SuggestionDismissal
from flywheel.services.briefing import assemble_briefing

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
