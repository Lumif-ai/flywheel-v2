"""Briefing REST endpoint -- proactive morning intelligence.

1 endpoint:
- GET /briefing  -- assembled briefing with greeting, cards, knowledge health, nudge
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.services.briefing import assemble_briefing

router = APIRouter(prefix="/briefing", tags=["briefing"])


# ---------------------------------------------------------------------------
# Pydantic response models
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
