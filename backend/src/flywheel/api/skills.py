"""Skill endpoints: listing, run management, SSE streaming, execution history.

Endpoints:
- GET  /skills                    -- list available skills
- POST /skills/runs               -- start a skill run
- GET  /skills/runs               -- paginated execution history
- GET  /skills/runs/{run_id}      -- single run detail
- GET  /skills/runs/{run_id}/stream -- SSE event stream with late-connect replay
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import ContextEntry, SkillRun, WorkItem
from flywheel.db.session import get_session_factory, get_tenant_session
from flywheel.middleware.rate_limit import check_anonymous_run_limit, check_concurrent_run_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])

# Directory where skill definitions live (relative to project root)
SKILLS_DIR = Path(__file__).resolve().parents[4] / "skills"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class StartRunRequest(BaseModel):
    skill_name: str
    input_text: str | None = None
    work_item_id: UUID | None = None


class StartRunResponse(BaseModel):
    run_id: str
    status: str
    stream_url: str


class AttributionEntry(BaseModel):
    id: str
    file: str
    source: str | None = None


class AttributionResponse(BaseModel):
    entry_count: int = 0
    files_consulted: list[str] = []
    sources: list[str] = []
    entries_read: list[dict] = []
    status: str = "available"
    reason: str | None = None


class TraceEntry(BaseModel):
    entry_id: str
    file_name: str
    source: str | None = None
    detail: str | None = None
    confidence: str | None = None
    evidence_count: int = 1
    date: str | None = None
    still_exists: bool = True
    updated_since_capture: bool = False


class RoutingDecision(BaseModel):
    intent_action: str = "direct"
    intent_confidence: float | None = None
    skill_name: str
    execution_mode: str


class ReasoningTraceResponse(BaseModel):
    version: int = 1
    routing: RoutingDecision | None = None
    context_consumed: list[TraceEntry] = []
    files_read: dict = {}
    captured_at: str | None = None
    status: str = "available"
    reason: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tier_message(tier: int) -> str | None:
    """Return human-readable tier gate message for the frontend.

    Tier 1: Full functionality on web -- no message needed.
    Tier 2: Partial functionality -- inform user of reduced capability.
    Tier 3: Requires local agent -- block execution on web.
    """
    if tier == 3:
        return "Requires local agent. Install the Flywheel CLI and run 'flywheel agent start' to use this skill."
    if tier == 2:
        return "Works on web with reduced capability. Connect your local agent for deeper research."
    return None  # Tier 1: no message needed, full functionality


def _parse_skill_frontmatter(skill_dir: Path) -> dict[str, Any] | None:
    """Parse SKILL.md YAML frontmatter from a skill directory."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return None
        end = text.index("---", 3)
        fm = yaml.safe_load(text[3:end])
        if not isinstance(fm, dict):
            return None
        web_tier = fm.get("web_tier", 1)
        return {
            "name": fm.get("name", skill_dir.name),
            "description": fm.get("description", ""),
            "version": fm.get("version", "0.0.0"),
            "tags": fm.get("tags", []),
            "web_tier": web_tier,
            "tier_message": _get_tier_message(web_tier),
        }
    except Exception:
        logger.debug("Failed to parse SKILL.md in %s", skill_dir)
        return None


def _get_available_skills() -> list[dict[str, Any]]:
    """Scan the skills directory and return parsed metadata."""
    if not SKILLS_DIR.is_dir():
        return []
    skills = []
    for child in sorted(SKILLS_DIR.iterdir()):
        if child.is_dir():
            meta = _parse_skill_frontmatter(child)
            if meta is not None:
                skills.append(meta)
    return skills


def _run_to_dict(run: SkillRun, *, detail: bool = False) -> dict[str, Any]:
    """Serialize a SkillRun to a response dict."""
    d: dict[str, Any] = {
        "id": str(run.id),
        "skill_name": run.skill_name,
        "status": run.status,
        "input_text": (run.input_text[:200] if run.input_text and len(run.input_text) > 200 else run.input_text),
        "tokens_used": run.tokens_used,
        "cost_estimate": float(run.cost_estimate) if run.cost_estimate is not None else None,
        "duration_ms": run.duration_ms,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "error": run.error,
    }
    if detail:
        d["input_text"] = run.input_text  # full text
        d["output"] = run.output
        d["rendered_html"] = run.rendered_html
        d["attribution"] = run.attribution
        d["events_log"] = run.events_log
    return d


# ---------------------------------------------------------------------------
# GET /skills -- List available skills
# ---------------------------------------------------------------------------


@router.get("/")
async def list_skills(
    user: TokenPayload = Depends(require_tenant),
) -> dict[str, Any]:
    """Return available skills with metadata parsed from SKILL.md files."""
    return {"items": _get_available_skills()}


# ---------------------------------------------------------------------------
# POST /skills/runs -- Start a skill run
# ---------------------------------------------------------------------------


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def start_run(
    body: StartRunRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> StartRunResponse:
    """Create a SkillRun record and return a run_id.

    NOTE: Actual execution is Phase 20. This just creates the pending record.
    """
    # Rate limit checks
    await check_anonymous_run_limit(user.sub, user.is_anonymous, db)
    await check_concurrent_run_limit(user.sub, db)

    # Validate skill exists
    available = [s["name"] for s in _get_available_skills()]
    if body.skill_name not in available:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{body.skill_name}' not found",
        )

    input_text = body.input_text or ""

    # If work_item_id provided, verify it exists and include its data
    if body.work_item_id:
        result = await db.execute(
            select(WorkItem).where(WorkItem.id == body.work_item_id)
        )
        work_item = result.scalar_one_or_none()
        if work_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work item not found",
            )
        # Prepend work item context to input
        wi_context = json.dumps({"work_item": {"title": work_item.title, "type": work_item.type, "data": work_item.data}})
        input_text = f"{wi_context}\n{input_text}" if input_text else wi_context

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name=body.skill_name,
        input_text=input_text or None,
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await db.commit()

    return StartRunResponse(
        run_id=str(run.id),
        status="pending",
        stream_url=f"/api/v1/skills/runs/{run.id}/stream",
    )


# ---------------------------------------------------------------------------
# GET /skills/runs/{run_id}/stream -- SSE event stream
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}/stream")
async def stream_run(
    run_id: UUID,
    user: TokenPayload = Depends(require_tenant),
) -> EventSourceResponse:
    """SSE event stream with late-connect replay.

    CRITICAL: Does NOT use get_tenant_db -- SSE streams are long-lived
    and would hold a DB connection. Instead creates short-lived sessions
    per poll iteration.
    """

    async def event_generator():
        factory = get_session_factory()
        seen_events = 0

        # Initial load -- replay stored events
        session = await get_tenant_session(factory, str(user.tenant_id), str(user.sub))
        try:
            result = await session.execute(select(SkillRun).where(SkillRun.id == run_id))
            run = result.scalar_one_or_none()
            if run is None:
                yield {"event": "error", "data": json.dumps({"message": "Run not found"})}
                return

            # Replay all stored events (late-connect support)
            events_log = run.events_log or []
            for evt in events_log:
                yield {"event": evt.get("event", "message"), "data": json.dumps(evt.get("data", evt))}
                seen_events += 1

            # If already done, send done event with output data and return
            if run.status in ("completed", "failed"):
                done_data: dict[str, Any] = {
                    "status": run.status,
                    "run_id": str(run_id),
                    "tokens_used": run.tokens_used,
                    "cost_estimate": float(run.cost_estimate) if run.cost_estimate else None,
                    "rendered_html": run.rendered_html or "",
                }
                yield {"event": "done", "data": json.dumps(done_data)}
                return

            current_status = run.status
        finally:
            await session.close()

        # Poll loop for in-progress runs
        while current_status not in ("completed", "failed"):
            await asyncio.sleep(1)

            session = await get_tenant_session(factory, str(user.tenant_id), str(user.sub))
            try:
                result = await session.execute(select(SkillRun).where(SkillRun.id == run_id))
                run = result.scalar_one_or_none()
                if run is None:
                    yield {"event": "error", "data": json.dumps({"message": "Run disappeared"})}
                    return

                # Yield any new events
                events_log = run.events_log or []
                for evt in events_log[seen_events:]:
                    yield {"event": evt.get("event", "message"), "data": json.dumps(evt.get("data", evt))}
                    seen_events += 1

                current_status = run.status
            finally:
                await session.close()

        # Fetch final run state for output data
        session = await get_tenant_session(factory, str(user.tenant_id), str(user.sub))
        try:
            result = await session.execute(select(SkillRun).where(SkillRun.id == run_id))
            final_run = result.scalar_one_or_none()
            done_payload: dict[str, Any] = {
                "status": current_status,
                "run_id": str(run_id),
            }
            if final_run:
                done_payload["tokens_used"] = final_run.tokens_used
                done_payload["cost_estimate"] = float(final_run.cost_estimate) if final_run.cost_estimate else None
                done_payload["rendered_html"] = final_run.rendered_html or ""
        finally:
            await session.close()
        yield {"event": "done", "data": json.dumps(done_payload)}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# GET /skills/runs -- Paginated execution history
# ---------------------------------------------------------------------------


@router.get("/runs")
async def list_runs(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    skill_name: str | None = None,
    run_status: str | None = Query(None, alias="status"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Paginated execution history with optional filters."""
    base = select(SkillRun)
    count_q = select(func.count(SkillRun.id))

    if skill_name:
        base = base.where(SkillRun.skill_name == skill_name)
        count_q = count_q.where(SkillRun.skill_name == skill_name)
    if run_status:
        base = base.where(SkillRun.status == run_status)
        count_q = count_q.where(SkillRun.status == run_status)

    total = (await db.execute(count_q)).scalar() or 0
    runs = (
        await db.execute(
            base.order_by(SkillRun.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    return {
        "items": [_run_to_dict(r) for r in runs],
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


# ---------------------------------------------------------------------------
# GET /skills/runs/{run_id} -- Single run detail
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}")
async def get_run(
    run_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Return full run object including output and events_log."""
    result = await db.execute(select(SkillRun).where(SkillRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    return _run_to_dict(run, detail=True)


# ---------------------------------------------------------------------------
# GET /skills/runs/{run_id}/attribution -- Attribution detail for a run
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}/attribution", response_model=AttributionResponse)
async def get_run_attribution(
    run_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> AttributionResponse:
    """Return attribution data showing which context entries informed a skill run."""
    result = await db.execute(select(SkillRun).where(SkillRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    # If run is still in progress, attribution hasn't been computed yet
    if run.status in ("pending", "running", "waiting_for_api"):
        return AttributionResponse(
            status="pending",
            reason="Attribution is computed after run completion",
        )

    # If run completed but has no attribution data
    attribution = run.attribution
    if not attribution or not attribution.get("entry_count"):
        return AttributionResponse(
            status="unavailable",
            reason=(
                "Run completed before attribution tracking was enabled "
                "or attribution data was not collected"
            ),
        )

    return AttributionResponse(
        entry_count=attribution.get("entry_count", 0),
        files_consulted=attribution.get("files_consulted", []),
        sources=attribution.get("sources", []),
        entries_read=attribution.get("entries_read", []),
        status="available",
    )


# ---------------------------------------------------------------------------
# GET /skills/runs/{run_id}/trace -- Reasoning trace ("What informed this?")
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}/trace", response_model=ReasoningTraceResponse)
async def get_run_trace(
    run_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> ReasoningTraceResponse:
    """Return the reasoning trace for a run: routing decision, context consumed, files read."""
    result = await db.execute(select(SkillRun).where(SkillRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    # Pending/running runs don't have traces yet
    if run.status in ("pending", "running", "waiting_for_api"):
        return ReasoningTraceResponse(
            status="pending",
            reason="Trace is computed after run completion",
        )

    # Old runs without trace data
    trace = run.reasoning_trace
    if not trace:
        return ReasoningTraceResponse(
            status="unavailable",
            reason="Run completed before reasoning trace tracking was enabled",
        )

    # Build routing decision
    routing = None
    if trace.get("routing"):
        routing_data = trace["routing"]
        routing = RoutingDecision(
            intent_action=routing_data.get("intent_action", "direct"),
            intent_confidence=routing_data.get("intent_confidence"),
            skill_name=routing_data.get("skill_name", ""),
            execution_mode=routing_data.get("execution_mode", ""),
        )

    # Build context consumed entries with liveness check
    raw_entries = trace.get("context_consumed", [])
    entry_ids: list[UUID] = []
    for e in raw_entries:
        try:
            entry_ids.append(UUID(e["entry_id"]))
        except (KeyError, ValueError):
            pass

    # Batch liveness query: fetch all referenced entries in one query
    liveness_map: dict[str, tuple[bool, bool]] = {}  # entry_id -> (exists, updated_since)
    captured_at_str = trace.get("captured_at")
    try:
        if entry_ids:
            liveness_result = await db.execute(
                select(
                    ContextEntry.id,
                    ContextEntry.deleted_at,
                    ContextEntry.updated_at,
                ).where(ContextEntry.id.in_(entry_ids))
            )
            liveness_rows = liveness_result.all()

            found_ids: set[str] = set()
            for row_id, deleted_at, updated_at in liveness_rows:
                eid = str(row_id)
                found_ids.add(eid)
                exists = deleted_at is None
                updated_since = False
                if captured_at_str and updated_at:
                    try:
                        captured_dt = datetime.datetime.fromisoformat(captured_at_str)
                        if updated_at.tzinfo is None:
                            updated_at = updated_at.replace(tzinfo=datetime.timezone.utc)
                        if captured_dt.tzinfo is None:
                            captured_dt = captured_dt.replace(tzinfo=datetime.timezone.utc)
                        updated_since = updated_at > captured_dt
                    except (ValueError, TypeError):
                        pass
                liveness_map[eid] = (exists, updated_since)

            # Mark missing entries
            for eid_uuid in entry_ids:
                eid_str = str(eid_uuid)
                if eid_str not in found_ids:
                    liveness_map[eid_str] = (False, False)
    except Exception:
        # Graceful degradation: liveness check failed, use optimistic defaults
        logger.warning("Liveness check failed for run %s, using defaults", run_id)

    context_consumed: list[TraceEntry] = []
    for e in raw_entries:
        eid = e.get("entry_id", "")
        exists, updated = liveness_map.get(eid, (True, False))
        context_consumed.append(
            TraceEntry(
                entry_id=eid,
                file_name=e.get("file_name", ""),
                source=e.get("source"),
                detail=e.get("detail"),
                confidence=e.get("confidence"),
                evidence_count=e.get("evidence_count", 1),
                date=e.get("date"),
                still_exists=exists,
                updated_since_capture=updated,
            )
        )

    return ReasoningTraceResponse(
        version=trace.get("version", 1),
        routing=routing,
        context_consumed=context_consumed,
        files_read=trace.get("files_read", {}),
        captured_at=captured_at_str,
        status="available",
    )
