"""Learning engine REST endpoints: scoring, contradictions, suggestions, dedup stats, trace analysis.

7 endpoints:
- GET /learning/scores/{file_name}                          -- scored entries with confidence rankings
- GET /learning/contradictions                               -- detected contradictions (optional file filter)
- POST /learning/contradictions/{entry_id}/resolve           -- resolve a contradiction
- GET /learning/suggestions                                  -- proactive suggestions
- POST /learning/suggestions/{suggestion_type}/{suggestion_key}/dismiss -- dismiss a suggestion
- GET /learning/dedup-stats                                  -- dedup event counts per file
- GET /learning/trace-analysis                               -- entry effectiveness from reasoning traces
"""

from __future__ import annotations

import datetime
from enum import Enum
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import ContextEvent
from flywheel.services.learning_engine import (
    analyze_entry_effectiveness,
    detect_contradictions,
    dismiss_suggestion,
    generate_suggestions,
    resolve_contradiction,
    score_entries,
)

router = APIRouter(prefix="/learning", tags=["learning"])


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class ScoredEntry(BaseModel):
    entry_id: UUID
    date: datetime.date | None = None
    source: str | None = None
    detail: str | None = None
    confidence: str | None = None
    evidence_count: int = 1
    composite_score: float = 0.0
    source_diversity: int = 1
    staleness: str = "fresh"
    meets_high_confidence_bar: bool = False


class ScoredEntriesResponse(BaseModel):
    items: list[ScoredEntry]
    file_name: str


class ContradictionEntry(BaseModel):
    id: UUID
    date: datetime.date | None = None
    source: str | None = None
    content_preview: str = ""
    evidence_count: int = 1


class ContradictionPair(BaseModel):
    file_name: str
    topic: str
    entry_a: ContradictionEntry
    entry_b: ContradictionEntry
    similarity: float


class ContradictionsResponse(BaseModel):
    items: list[ContradictionPair]
    count: int


class ResolutionChoice(str, Enum):
    superseded = "superseded"
    dismissed = "dismissed"
    kept = "kept"


class ResolveRequest(BaseModel):
    resolution: ResolutionChoice


class Suggestion(BaseModel):
    type: str
    priority: str
    key: str
    title: str
    detail: str
    work_item_id: str | None = None
    file_name: str | None = None


class SuggestionsResponse(BaseModel):
    items: list[Suggestion]
    count: int


class DedupStats(BaseModel):
    file_name: str
    dedup_count: int


class DedupStatsResponse(BaseModel):
    items: list[DedupStats]
    total_deduped: int


class EntryEffectiveness(BaseModel):
    entry_id: str
    file_name: str
    detail: str | None = None
    confidence: str | None = None
    total_count: int
    success_count: int
    fail_count: int
    success_rate: float


class TraceAnalysisResponse(BaseModel):
    entries: list[EntryEffectiveness]
    total_entries_analyzed: int


# ---------------------------------------------------------------------------
# GET /learning/scores/{file_name}
# ---------------------------------------------------------------------------


@router.get("/scores/{file_name}", response_model=ScoredEntriesResponse)
async def get_scored_entries(
    file_name: str,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Return scored context entries for a file, ranked by composite confidence."""
    scored = await score_entries(db, file_name)
    return ScoredEntriesResponse(items=scored, file_name=file_name)


# ---------------------------------------------------------------------------
# GET /learning/contradictions
# ---------------------------------------------------------------------------


@router.get("/contradictions", response_model=ContradictionsResponse)
async def get_contradictions(
    file_name: str | None = Query(None),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Detect contradictions across context entries, optionally filtered by file."""
    items = await detect_contradictions(db, file_name)
    return ContradictionsResponse(items=items, count=len(items))


# ---------------------------------------------------------------------------
# POST /learning/contradictions/{entry_id}/resolve
# ---------------------------------------------------------------------------


@router.post("/contradictions/{entry_id}/resolve")
async def post_resolve_contradiction(
    entry_id: UUID,
    body: ResolveRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Resolve a detected contradiction by marking the entry."""
    try:
        await resolve_contradiction(db, entry_id, body.resolution.value)
        await db.commit()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entry {entry_id} not found",
        )
    return {"status": "resolved", "entry_id": str(entry_id)}


# ---------------------------------------------------------------------------
# GET /learning/suggestions
# ---------------------------------------------------------------------------


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    limit: int = Query(3, ge=1, le=10),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Return proactive suggestions (meeting prep, stale context alerts)."""
    items = await generate_suggestions(db, user.sub, limit)
    return SuggestionsResponse(items=items, count=len(items))


# ---------------------------------------------------------------------------
# POST /learning/suggestions/{suggestion_type}/{suggestion_key}/dismiss
# ---------------------------------------------------------------------------


@router.post("/suggestions/{suggestion_type}/{suggestion_key}/dismiss")
async def post_dismiss_suggestion(
    suggestion_type: str,
    suggestion_key: str,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Dismiss a suggestion for 7 days."""
    await dismiss_suggestion(db, user.sub, suggestion_type, suggestion_key)
    await db.commit()

    # Calculate the expiry (7 days from now, matching DB default)
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        days=7
    )
    return {
        "status": "dismissed",
        "expires_at": expires_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /learning/dedup-stats
# ---------------------------------------------------------------------------

# Verified from storage.py line 146: event_type = "evidence_incremented"
_DEDUP_EVENT_TYPE = "evidence_incremented"


@router.get("/dedup-stats", response_model=DedupStatsResponse)
async def get_dedup_stats(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Return dedup statistics: how many evidence_incremented events per file."""
    stmt = (
        select(
            ContextEvent.file_name,
            func.count().label("dedup_count"),
        )
        .where(ContextEvent.event_type == _DEDUP_EVENT_TYPE)
        .group_by(ContextEvent.file_name)
        .order_by(func.count().desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = [
        DedupStats(file_name=file_name, dedup_count=dedup_count)
        for file_name, dedup_count in rows
    ]
    total = sum(item.dedup_count for item in items)

    return DedupStatsResponse(items=items, total_deduped=total)


# ---------------------------------------------------------------------------
# GET /learning/trace-analysis
# ---------------------------------------------------------------------------


@router.get("/trace-analysis", response_model=TraceAnalysisResponse)
async def get_trace_analysis(
    file_name: str | None = Query(None, description="Filter by context file name"),
    min_runs: int = Query(3, ge=1, le=100, description="Minimum runs for inclusion"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> TraceAnalysisResponse:
    """Return entry effectiveness rankings based on reasoning trace analysis."""
    results = await analyze_entry_effectiveness(db, file_name, min_runs)
    return TraceAnalysisResponse(
        entries=results,
        total_entries_analyzed=len(results),
    )
