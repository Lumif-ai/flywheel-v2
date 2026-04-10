"""Skill endpoints: listing, run management, SSE streaming, execution history.

Skill metadata is sourced from the skill_definitions table, seeded by the
``flywheel db seed`` CLI command. No filesystem scanning at runtime.

Endpoints:
- GET  /skills                    -- list available skills
- GET  /skills/{name}/prompt      -- retrieve skill system_prompt (MCP tool use)
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
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

import re as _re

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload, decode_jwt
from flywheel.db.models import ContextEntry, SkillDefinition, SkillRun, TenantSkill, WorkItem
from flywheel.db.session import get_session_factory, get_tenant_session
from flywheel.middleware.rate_limit import check_anonymous_run_limit, check_concurrent_run_limit, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class StartRunRequest(BaseModel):
    skill_name: str
    input_text: str | None = None
    input_data: dict | None = None  # Structured input validated against skill's input_schema
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


async def _get_available_skills_db(db: AsyncSession, tenant_id: UUID) -> list[dict[str, Any]]:
    """Query available skills for a tenant.

    Uses tenant_skills as an override/restriction table:
    - If tenant has tenant_skills rows: return only skills where both
      skill_definitions.enabled AND tenant_skills.enabled are True.
    - If tenant has NO tenant_skills rows: return all enabled skill_definitions.
      This is the default for new tenants — all skills available until
      explicitly restricted via tenant_skills.
    """
    # Check if tenant has any tenant_skills overrides
    has_overrides = await db.execute(
        select(TenantSkill.skill_id)
        .where(TenantSkill.tenant_id == tenant_id)
        .limit(1)
    )
    if has_overrides.scalar_one_or_none() is not None:
        # Tenant has explicit skill assignments — use them
        stmt = (
            select(SkillDefinition)
            .join(TenantSkill, TenantSkill.skill_id == SkillDefinition.id)
            .where(
                TenantSkill.tenant_id == tenant_id,
                TenantSkill.enabled == True,  # noqa: E712
                SkillDefinition.enabled == True,  # noqa: E712
            )
            .order_by(SkillDefinition.name.asc())
        )
    else:
        # No overrides — all enabled skills available (default for new tenants)
        stmt = (
            select(SkillDefinition)
            .where(SkillDefinition.enabled == True)  # noqa: E712
            .order_by(SkillDefinition.name.asc())
        )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "name": sd.name,
            "description": sd.description or "",
            "version": sd.version,
            "tags": list(sd.tags) if sd.tags else [],
            "web_tier": sd.web_tier,
            "tier_message": _get_tier_message(sd.web_tier),
            "input_requirements": (sd.parameters or {}).get("input_description", ""),
            "input_schema": (sd.parameters or {}).get("input_schema"),
            "triggers": (sd.parameters or {}).get("triggers", []),
        }
        for sd in rows
    ]


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


def _validate_input_data(data: dict, schema: dict) -> str | None:
    """Validate *data* against a JSON Schema-like *schema*.

    Returns ``None`` on success or a human-readable error string on failure.
    Supports: type, required, properties, format (uuid / uri).

    This is a lightweight validator so that we don't need the ``jsonschema``
    package as an explicit dependency.
    """
    # Top-level type check
    schema_type = schema.get("type")
    if schema_type == "object" and not isinstance(data, dict):
        return f"Expected object, got {type(data).__name__}"

    properties: dict = schema.get("properties", {})
    required: list = schema.get("required", [])

    # Check required fields
    for field in required:
        if field not in data:
            return f"Missing required field: '{field}'"

    # Validate each provided property against its sub-schema
    for field, value in data.items():
        if field not in properties:
            continue  # extra fields are allowed
        prop_schema = properties[field]
        prop_type = prop_schema.get("type")
        if prop_type == "string" and not isinstance(value, str):
            return f"Field '{field}' must be a string"
        if prop_type == "number" and not isinstance(value, (int, float)):
            return f"Field '{field}' must be a number"
        if prop_type == "integer" and not isinstance(value, int):
            return f"Field '{field}' must be an integer"
        if prop_type == "boolean" and not isinstance(value, bool):
            return f"Field '{field}' must be a boolean"
        if prop_type == "array" and not isinstance(value, list):
            return f"Field '{field}' must be an array"

        # Format checks (only for strings)
        fmt = prop_schema.get("format")
        if fmt and isinstance(value, str):
            if fmt == "uuid":
                try:
                    UUID(value)
                except ValueError:
                    return f"Field '{field}' must be a valid UUID"
            elif fmt == "uri":
                if not _re.match(r"^https?://", value):
                    return f"Field '{field}' must be a valid URL (starting with http:// or https://)"

    return None


# ---------------------------------------------------------------------------
# GET /skills -- List available skills
# ---------------------------------------------------------------------------


@router.get("/")
async def list_skills(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Return available skills from DB, scoped to tenant."""
    return {"items": await _get_available_skills_db(db, user.tenant_id)}


# ---------------------------------------------------------------------------
# GET /skills/{skill_name}/prompt -- Retrieve skill system_prompt (MCP)
# ---------------------------------------------------------------------------

ORCHESTRATOR_STUB_TEMPLATE = (
    "This skill executes server-side for security.\n\n"
    "To run this skill:\n"
    "1. Call the `flywheel_run_skill` MCP tool with:\n"
    "   - skill_name: \"{skill_name}\"\n"
    "   - input_text: Pass the user's request/input verbatim\n\n"
    "2. Wait for the result and present it to the user.\n\n"
    "Do NOT attempt to execute this skill's instructions directly."
)


@router.get("/{skill_name}/prompt")
@limiter.limit("10/minute")
async def get_skill_prompt(
    request: Request,
    skill_name: str,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Return the system_prompt for a skill, scoped to tenant.

    Used by MCP tools to fetch the full prompt before executing a skill as Opus.
    Returns 404 if skill is unknown, disabled, or tenant-restricted.
    """
    # Check if tenant has tenant_skills overrides (same logic as _get_available_skills_db)
    has_overrides = await db.execute(
        select(TenantSkill.skill_id)
        .where(TenantSkill.tenant_id == user.tenant_id)
        .limit(1)
    )
    if has_overrides.scalar_one_or_none() is not None:
        # Tenant has explicit skill assignments — use them
        stmt = (
            select(SkillDefinition)
            .join(TenantSkill, TenantSkill.skill_id == SkillDefinition.id)
            .where(
                TenantSkill.tenant_id == user.tenant_id,
                TenantSkill.enabled == True,  # noqa: E712
                SkillDefinition.enabled == True,  # noqa: E712
                SkillDefinition.name == skill_name,
            )
        )
    else:
        # No overrides — all enabled skills available
        stmt = (
            select(SkillDefinition)
            .where(
                SkillDefinition.enabled == True,  # noqa: E712
                SkillDefinition.name == skill_name,
            )
        )
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()

    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' not found or not available for this tenant",
        )

    logger.info(
        "prompt_fetch tenant=%s skill=%s user=%s protected=%s",
        user.tenant_id, skill_name, user.sub, skill.protected,
    )

    if skill.protected:
        return {
            "skill_name": skill.name,
            "system_prompt": ORCHESTRATOR_STUB_TEMPLATE.format(skill_name=skill.name),
            "protected": True,
        }

    return {"skill_name": skill.name, "system_prompt": skill.system_prompt}


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

    # Validate skill exists in DB and is enabled for this tenant.
    # Fetch the full SkillDefinition so we can access parameters for input validation.
    has_overrides = await db.execute(
        select(TenantSkill.skill_id)
        .where(TenantSkill.tenant_id == user.tenant_id)
        .limit(1)
    )
    if has_overrides.scalar_one_or_none() is not None:
        skill_check = await db.execute(
            select(SkillDefinition)
            .join(TenantSkill, TenantSkill.skill_id == SkillDefinition.id)
            .where(
                SkillDefinition.name == body.skill_name,
                SkillDefinition.enabled == True,  # noqa: E712
                TenantSkill.tenant_id == user.tenant_id,
                TenantSkill.enabled == True,  # noqa: E712
            )
        )
    else:
        skill_check = await db.execute(
            select(SkillDefinition)
            .where(
                SkillDefinition.name == body.skill_name,
                SkillDefinition.enabled == True,  # noqa: E712
            )
        )
    skill = skill_check.scalar_one_or_none()
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{body.skill_name}' not found",
        )

    # --- Input validation against skill's input_schema ---
    parameters = skill.parameters or {}
    input_schema = parameters.get("input_schema")
    if input_schema:
        if body.input_data:
            validation_error = _validate_input_data(body.input_data, input_schema)
            if validation_error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid input for skill '{body.skill_name}': {validation_error}",
                )
        elif not body.input_text:
            input_desc = parameters.get(
                "input_description",
                "This skill requires structured input.",
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Skill '{body.skill_name}' requires input: {input_desc}",
            )

    input_text = body.input_text or ""

    # Serialize structured input_data into input_text prefix
    if body.input_data:
        data_context = json.dumps({"input_data": body.input_data})
        input_text = f"{data_context}\n{input_text}" if input_text else data_context

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
    token: str | None = None,
    cred: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
) -> EventSourceResponse:
    """SSE event stream with late-connect replay.

    Accepts JWT via Authorization header OR ?token= query param
    (EventSource API cannot send custom headers).

    CRITICAL: Does NOT use get_tenant_db -- SSE streams are long-lived
    and would hold a DB connection. Instead creates short-lived sessions
    per poll iteration.
    """
    jwt_token = cred.credentials if cred else token
    if not jwt_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = decode_jwt(jwt_token)
    if user.tenant_id is None:
        # Try resolving tenant for authenticated users
        from flywheel.api.deps import _resolve_tenant_for_user
        tenant_id = await _resolve_tenant_for_user(user.sub)
        if tenant_id:
            user.app_metadata["tenant_id"] = str(tenant_id)
        else:
            raise HTTPException(status_code=403, detail="No active tenant")

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
    base = select(SkillRun).where(SkillRun.user_id == user.sub)
    count_q = select(func.count(SkillRun.id)).where(SkillRun.user_id == user.sub)

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
    result = await db.execute(
        select(SkillRun).where(SkillRun.id == run_id, SkillRun.user_id == user.sub)
    )
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
    result = await db.execute(
        select(SkillRun).where(SkillRun.id == run_id, SkillRun.user_id == user.sub)
    )
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
    result = await db.execute(
        select(SkillRun).where(SkillRun.id == run_id, SkillRun.user_id == user.sub)
    )
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
