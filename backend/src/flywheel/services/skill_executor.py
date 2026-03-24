"""Skill execution -- async tool_use loop (web) and sync gateway bridge (CLI).

Skill metadata (system_prompt, engine_module, web_tier) is sourced from the
skill_definitions table, seeded by ``flywheel db seed``. No filesystem
scanning or hardcoded skill sets in the runtime path.

Web execution uses AsyncAnthropic with a tool_use loop through the tool
registry. CLI/Slack execution still uses the sync execution_gateway via
_execute_with_api_key(). Both paths share BYOK key decryption, event
streaming, cost calculation, and HTML rendering.

Public API:
    execute_run(run) -> None
    _execute_with_tools(...) -> tuple[str, dict, list]
    _append_event_atomic(factory, run_id, event_dict) -> None
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text as sa_text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from flywheel.db.models import (
    ContextEntry, Focus, SkillDefinition, SkillRun, Tenant, User, UserFocus,
)
from flywheel.db.session import get_session_factory
from sqlalchemy import select

from flywheel.services.circuit_breaker import anthropic_breaker
from flywheel.services.cost_tracker import calculate_cost

logger = logging.getLogger(__name__)

# Markers in tool results that indicate a browser step was skipped
AGENT_SKIP_MARKERS = ["AGENT_NOT_CONNECTED", "AGENT_TIMEOUT"]

# Thread lock for env var manipulation during execute_skill calls.
# The execution_gateway reads ANTHROPIC_API_KEY from os.environ, so we
# must set it before calling execute_skill and restore it after.
_env_lock = threading.Lock()

async def _load_skill_from_db(
    factory: async_sessionmaker[AsyncSession],
    skill_name: str,
) -> dict | None:
    """Load skill metadata from the skill_definitions table.

    Queries SkillDefinition where name == skill_name and enabled == True.
    Returns a dict with keys: system_prompt, contract, engine_module,
    parameters, web_tier, token_budget. Returns None if not found.

    This is the single source of truth for skill metadata at execution time,
    replacing filesystem-based SKILL.md parsing and hardcoded sets.
    """
    async with factory() as session:
        result = await session.execute(
            select(SkillDefinition).where(
                SkillDefinition.name == skill_name,
                SkillDefinition.enabled.is_(True),
            )
        )
        row = result.scalar_one_or_none()

    if row is None:
        return None

    return {
        "system_prompt": row.system_prompt,
        "contract": {
            "reads": list(row.contract_reads) if row.contract_reads else [],
            "writes": list(row.contract_writes) if row.contract_writes else [],
        },
        "engine_module": row.engine_module,
        "parameters": row.parameters or {},
        "web_tier": row.web_tier,
        "token_budget": row.token_budget,
    }


def merge_settings(tenant_settings: dict | None, focus_settings: dict | None) -> dict:
    """Shallow merge: focus settings override tenant defaults key-by-key.

    Always merge at read time, never persist merged results.
    """
    if not focus_settings:
        return dict(tenant_settings) if tenant_settings else {}
    return {**(tenant_settings or {}), **focus_settings}


async def get_merged_settings(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    focus_id: UUID | None,
) -> dict:
    """Query tenant and focus settings, return shallow-merged result.

    If focus_id is None, returns tenant settings only.
    """
    async with factory() as session:
        tenant_result = await session.execute(
            select(Tenant.settings).where(Tenant.id == tenant_id)
        )
        tenant_settings = tenant_result.scalar_one_or_none() or {}

        focus_settings = None
        if focus_id is not None:
            focus_result = await session.execute(
                select(Focus.settings).where(Focus.id == focus_id)
            )
            focus_settings = focus_result.scalar_one_or_none()

    return merge_settings(tenant_settings, focus_settings)


async def resolve_weighted_context(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    active_focus_id: UUID | None,
    file_names: list[str],
) -> list[tuple[ContextEntry, float]]:
    """Query context entries for given files with focus-based weighting.

    Weighting rules:
    - active_focus_id is None -> all entries weight 1.0
    - entry.focus_id == active_focus_id -> weight 1.0
    - entry.focus_id is None -> weight 0.8 (global/unscoped)
    - entry.focus_id != active_focus_id -> weight 0.5
    - If focus is archived, entries from it get weight 0.5 regardless

    Returns entries sorted by (composite_score * focus_weight) descending.
    CRITICAL: Never filters out entries -- only sort order changes.
    """
    async with factory() as session:
        await session.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )

        result = await session.execute(
            select(ContextEntry)
            .where(
                ContextEntry.tenant_id == tenant_id,
                ContextEntry.file_name.in_(file_names),
                ContextEntry.deleted_at.is_(None),
            )
        )
        rows = result.scalars().all()

        if not rows:
            return []

        # Look up archived focuses to apply weight penalty
        archived_focus_ids: set[UUID] = set()
        if active_focus_id is not None:
            focus_ids_in_rows = {r.focus_id for r in rows if r.focus_id is not None}
            if focus_ids_in_rows:
                archived_result = await session.execute(
                    select(Focus.id).where(
                        Focus.id.in_(focus_ids_in_rows),
                        Focus.archived_at.is_not(None),
                    )
                )
                archived_focus_ids = set(archived_result.scalars().all())

    # Apply weighting
    weighted: list[tuple[ContextEntry, float]] = []
    for entry in rows:
        if active_focus_id is None:
            weight = 1.0
        elif entry.focus_id is not None and entry.focus_id in archived_focus_ids:
            weight = 0.5
        elif entry.focus_id == active_focus_id:
            weight = 1.0
        elif entry.focus_id is None:
            weight = 0.8
        else:
            weight = 0.5

        composite_score = getattr(entry, "composite_score", None) or 0.5
        weighted.append((entry, composite_score * weight))

    # Sort by weighted score descending
    weighted.sort(key=lambda x: x[1], reverse=True)
    return weighted


async def _get_user_active_focus(
    factory: async_sessionmaker[AsyncSession],
    user_id: UUID,
    tenant_id: UUID,
) -> UUID | None:
    """Get the user's active focus_id for the given tenant, or None."""
    async with factory() as session:
        result = await session.execute(
            select(UserFocus.focus_id).where(
                UserFocus.user_id == user_id,
                UserFocus.tenant_id == tenant_id,
                UserFocus.active.is_(True),
            )
        )
        return result.scalar_one_or_none()


async def _build_attribution(
    tenant_id: UUID, user_id: UUID, skill_name: str
) -> dict:
    """Build attribution data from recent context entries for the tenant.

    Queries the most recent non-deleted ContextEntry rows to show users
    which prior context informed a skill run. Returns a structured dict
    with entry counts, files consulted, and source breakdown.

    This function must NEVER raise -- attribution is informational and
    must not block skill execution results.
    """
    try:
        factory = get_session_factory()
        async with factory() as session:
            # Set tenant RLS context
            await session.execute(
                sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )

            # Query up to 50 most recent non-deleted entries
            result = await session.execute(
                select(ContextEntry)
                .where(
                    ContextEntry.tenant_id == tenant_id,
                    ContextEntry.deleted_at.is_(None),
                )
                .order_by(ContextEntry.updated_at.desc())
                .limit(50)
            )
            rows = result.scalars().all()

            if not rows:
                return {
                    "entry_count": 0,
                    "files_consulted": [],
                    "sources": [],
                    "entries_read": [],
                }

            return {
                "entry_count": len(rows),
                "files_consulted": list(set(r.file_name for r in rows)),
                "sources": list(set(r.source for r in rows if r.source)),
                "entries_read": [
                    {
                        "id": str(r.id),
                        "file": r.file_name,
                        "source": r.source,
                        "focus_id": str(r.focus_id) if r.focus_id else None,
                    }
                    for r in rows[:20]  # Cap detail at 20
                ],
            }
    except Exception as exc:
        logger.warning("Attribution building failed: %s", exc)
        return {
            "entry_count": 0,
            "files_consulted": [],
            "sources": [],
            "entries_read": [],
        }


async def _build_reasoning_trace(
    tenant_id: UUID,
    user_id: UUID,
    skill_name: str,
    gateway_attribution: dict,
    events_log: list,
    execution_mode: str,
    tool_calls: list | None = None,
) -> dict:
    """Build a reasoning trace capturing context consumed and routing decision.

    Assembles entry-level detail from ContextEntry rows for each file the
    gateway reported reading, plus the orchestrator's routing decision from
    the run's events_log. Optionally includes tool_calls made during the run.

    This function must NEVER raise -- reasoning trace is informational and
    must not block skill execution results.

    Args:
        tenant_id: Tenant UUID for RLS scoping.
        user_id: User UUID (unused currently, reserved for user-scoped traces).
        skill_name: Name of the skill that was executed.
        gateway_attribution: File-level attribution dict from execution gateway
            (e.g. {filename: {entry_count, chars_read}}).
        events_log: Current events_log list from the SkillRun record.
        execution_mode: Execution mode string (e.g. "llm", "template").
        tool_calls: Optional list of tool call records from _execute_with_tools.

    Returns:
        Structured trace dict with version, routing, context_consumed,
        files_read, tool_calls, and captured_at. On failure returns minimal error dict.
    """
    try:
        # Extract routing decision from events_log
        routing_data: dict = {}
        for event in (events_log or []):
            if isinstance(event, dict) and event.get("event") == "routing":
                routing_data = event.get("data", {})
                break

        routing = {
            "intent_action": routing_data.get("action", "direct"),
            "intent_confidence": routing_data.get("confidence"),
            "skill_name": skill_name,
            "execution_mode": execution_mode,
        }

        # Query entry-level detail for files the gateway actually read
        context_consumed: list[dict] = []
        files_with_entries = [
            fname for fname, info in (gateway_attribution or {}).items()
            if isinstance(info, dict) and info.get("entry_count", 0) > 0
        ]

        if files_with_entries:
            factory = get_session_factory()
            async with factory() as session:
                # Set tenant RLS context
                await session.execute(
                    sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
                )

                result = await session.execute(
                    select(ContextEntry)
                    .where(
                        ContextEntry.tenant_id == tenant_id,
                        ContextEntry.file_name.in_(files_with_entries),
                        ContextEntry.deleted_at.is_(None),
                    )
                    .order_by(ContextEntry.date.desc())
                    .limit(50)
                )
                rows = result.scalars().all()

                context_consumed = [
                    {
                        "entry_id": str(entry.id),
                        "file_name": entry.file_name,
                        "source": entry.source,
                        "detail": entry.detail,
                        "confidence": entry.confidence,
                        "evidence_count": entry.evidence_count,
                        "date": entry.date.isoformat() if entry.date else None,
                    }
                    for entry in rows
                ]

        return {
            "version": 1,
            "routing": routing,
            "context_consumed": context_consumed,
            "files_read": gateway_attribution or {},
            "tool_calls": tool_calls or [],
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning("Reasoning trace building failed: %s", exc)
        return {"version": 1, "error": str(exc)}


def _build_tool_attribution(tool_calls: list) -> dict:
    """Build file-level attribution dict from tool call records.

    Maps context_read tool calls to a file-level attribution dict compatible
    with the existing attribution format: {filename: {entry_count, chars_read}}.

    Args:
        tool_calls: List of tool call records from _execute_with_tools.

    Returns:
        Attribution dict keyed by context file name.
    """
    attribution: dict = {}
    for call in (tool_calls or []):
        if call.get("tool") == "context_read":
            # Parse filename from input summary
            input_str = call.get("input", "")
            # input is str repr of dict like "{'file': 'company-intel'}"
            try:
                # Try to extract file name from the input string
                if "'file'" in input_str or '"file"' in input_str:
                    import re
                    match = re.search(r"['\"]file['\"]:\s*['\"]([^'\"]+)['\"]", input_str)
                    if match:
                        filename = match.group(1)
                        if filename not in attribution:
                            attribution[filename] = {"entry_count": 0, "chars_read": 0}
                        attribution[filename]["entry_count"] += 1
                        attribution[filename]["chars_read"] += call.get("result_length", 0)
            except Exception:
                pass
    return attribution


async def execute_run(run: SkillRun) -> None:
    """Execute a skill run and update the database with results.

    This is the main entry point called by the job queue worker after
    claiming a pending run. It:
    1. Emits a 'started' event
    2. Decrypts the user's BYOK API key
    3. Runs execute_skill in a thread (gateway is sync)
    4. Updates the SkillRun record with results
    5. Emits 'done' or 'error' events

    Args:
        run: The SkillRun ORM instance (detached from session).
    """
    factory = get_session_factory()
    start_time = time.time()

    try:
        # Circuit breaker check -- if API is down, set to waiting_for_api
        if not anthropic_breaker.can_execute():
            async with factory() as session:
                await session.execute(
                    update(SkillRun)
                    .where(SkillRun.id == run.id)
                    .values(status="waiting_for_api")
                )
                await session.commit()
            logger.info("Run %s deferred: circuit breaker is open", run.id)
            return

        # Emit "started" event
        await _append_event_atomic(factory, run.id, {
            "event": "stage",
            "data": {"stage": "started", "message": f"Running {run.skill_name}..."},
        })

        # Retrieve and decrypt user's BYOK API key
        api_key = await _get_user_api_key(factory, run.user_id)
        if api_key is None:
            # Fall back to subsidy key for onboarding skills and background engine skills
            from flywheel.config import settings
            if run.skill_name in ("company-intel", "meeting-prep", "email-scorer") and settings.flywheel_subsidy_api_key:
                api_key = settings.flywheel_subsidy_api_key
            else:
                raise ValueError(
                    "No API key configured. Please add your Anthropic API key in Settings."
                )

        # Look up user's active focus before creating RunContext
        active_focus_id = await _get_user_active_focus(
            factory, run.user_id, run.tenant_id
        )

        # Create tool registry and run context for web execution path
        from flywheel.tools import create_registry
        from flywheel.tools.registry import RunContext
        from flywheel.tools.budget import RunBudget
        from flywheel.services.agent_manager import agent_manager

        registry = create_registry()

        # Check agent connection for browser tool availability
        agent_connected = agent_manager.is_connected(run.user_id) if run.user_id else False

        # Load skill metadata from DB (RT-02/RT-03: DB is runtime source of truth)
        skill_meta = await _load_skill_from_db(factory, run.skill_name)
        if skill_meta is None:
            logger.warning(
                "Run %s: skill '%s' not found in DB, falling back to filesystem",
                run.id, run.skill_name,
            )

        # Tier check: use DB web_tier (seeded from SKILL.md frontmatter)
        skill_web_tier = skill_meta["web_tier"] if skill_meta else None
        if skill_web_tier == 3 and not agent_connected:
            raise ValueError(
                "This skill requires the local agent for browser automation. "
                "Start the agent with: flywheel agent start"
            )

        run_context = RunContext(
            tenant_id=run.tenant_id,
            user_id=run.user_id,
            run_id=run.id,
            budget=RunBudget(),
            session_factory=factory,
            focus_id=active_focus_id,
        )

        # Merge tenant + focus settings (available for system prompt context)
        merged_settings = await get_merged_settings(
            factory, run.tenant_id, active_focus_id
        )
        logger.info(
            "Run %s: active_focus=%s, merged_settings_keys=%s, agent_connected=%s, skill_from_db=%s",
            run.id,
            active_focus_id,
            list(merged_settings.keys()) if merged_settings else [],
            agent_connected,
            skill_meta is not None,
        )

        try:
            # Engine dispatch (RT-03): check engine_module from DB,
            # with fallback for company-intel which has a dedicated Python engine
            # and must work even before skill_definitions is seeded.
            has_engine = bool(skill_meta and skill_meta["engine_module"])
            is_company_intel = run.skill_name == "company-intel"
            is_meeting_prep = run.skill_name == "meeting-prep"
            is_email_scorer = run.skill_name == "email-scorer"
            if has_engine or is_company_intel or is_meeting_prep or is_email_scorer:
                if is_company_intel:
                    output, token_usage, tool_calls = await _execute_company_intel(
                        api_key=api_key,
                        input_text=run.input_text or "",
                        factory=factory,
                        run_id=run.id,
                        tenant_id=run.tenant_id,
                        user_id=run.user_id,
                    )
                elif is_meeting_prep:
                    output, token_usage, tool_calls = await _execute_meeting_prep(
                        api_key=api_key,
                        input_text=run.input_text or "",
                        factory=factory,
                        run_id=run.id,
                        tenant_id=run.tenant_id,
                        user_id=run.user_id,
                    )
                elif is_email_scorer:
                    # Email scorer is primarily called directly from gmail_sync.py
                    # (bypassing execute_run). This dispatch exists for observability
                    # and manual re-scoring via the skill execution UI.
                    # Direct scoring is handled by gmail_sync._score_new_emails().
                    from flywheel.engines.email_scorer import score_email  # noqa: F401
                    output = "Email scorer engine registered. Direct scoring is handled by gmail_sync.py."
                    token_usage = 0
                    tool_calls = []
                else:
                    engine_mod = skill_meta["engine_module"] if skill_meta else None
                    raise ValueError(
                        f"Engine skill '{run.skill_name}' (engine_module={engine_mod}) "
                        f"has no engine dispatch"
                    )
            else:
                # Resolve system_prompt: prefer DB, fall back to filesystem
                db_system_prompt = skill_meta["system_prompt"] if skill_meta else None

                output, token_usage, tool_calls = await _execute_with_tools(
                    api_key=api_key,
                    skill_name=run.skill_name,
                    input_text=run.input_text or "",
                    registry=registry,
                    context=run_context,
                    factory=factory,
                    run_id=run.id,
                    agent_connected=agent_connected,
                    system_prompt_override=db_system_prompt,
                )
            anthropic_breaker.record_success()
        except Exception as exec_err:
            # Check if this is an Anthropic API error for circuit breaker tracking
            try:
                import anthropic as anthropic_mod
                if isinstance(exec_err, anthropic_mod.APIError):
                    anthropic_breaker.record_failure()
            except ImportError:
                pass
            raise

        duration_ms = int((time.time() - start_time) * 1000)
        cost = calculate_cost(token_usage)

        # Add agent status note to output for Tier 2 skills that ran without agent
        browser_tool_names = registry.get_browser_tool_names()
        if browser_tool_names and not agent_connected:
            output += (
                "\n\nNote: Some browser-based capabilities were unavailable "
                "(local agent not connected)."
            )

        # Build attribution from tool calls (context_read calls -> file-level attribution)
        tool_attribution = _build_tool_attribution(tool_calls)

        # Render HTML output
        rendered_html = None
        if is_meeting_prep:
            # Meeting-prep engine returns HTML directly as output
            rendered_html = output
        else:
            try:
                from flywheel.engines.output_renderer import render_output
                rendered_html = render_output(
                    run.skill_name, output, tool_attribution
                )
            except Exception as e:
                logger.warning("Output rendering failed for %s: %s", run.skill_name, e)

        # Update run record with results
        total_tokens = (
            (token_usage or {}).get("input_tokens", 0)
            + (token_usage or {}).get("output_tokens", 0)
        )
        tool_snapshot = registry.snapshot_tools(run.skill_name)
        async with factory() as session:
            await session.execute(
                update(SkillRun)
                .where(SkillRun.id == run.id)
                .values(
                    status="completed",
                    output=output,
                    rendered_html=rendered_html,
                    tokens_used=total_tokens,
                    cost_estimate=cost,
                    duration_ms=duration_ms,
                    attribution=tool_attribution,
                )
            )
            await session.commit()

        # Create document artifact
        if rendered_html:
            try:
                from flywheel.services.document_storage import (
                    upload_document, _generate_title, _extract_document_metadata
                )
                from flywheel.db.models import Document
                doc_metadata = _extract_document_metadata(
                    run.skill_name, run.input_text, output
                )
                doc_title = _generate_title(
                    run.skill_name, run.input_text, doc_metadata
                )
                doc_id = str(uuid4())
                storage_path = await upload_document(
                    tenant_id=str(run.tenant_id),
                    document_type=run.skill_name,
                    document_id=doc_id,
                    content=rendered_html.encode("utf-8"),
                )
                async with factory() as session:
                    doc = Document(
                        id=doc_id,
                        tenant_id=run.tenant_id,
                        user_id=run.user_id,
                        title=doc_title,
                        document_type=run.skill_name,
                        storage_path=storage_path,
                        file_size_bytes=len(rendered_html.encode("utf-8")),
                        skill_run_id=run.id,
                        metadata_=doc_metadata,
                    )
                    session.add(doc)
                    await session.commit()
                logger.info("Document created for run %s: %s", run.id, doc_title)
            except Exception as doc_err:
                logger.warning("Document creation failed for run %s: %s", run.id, doc_err)

        # Build attribution from context entries (post-completion, per Pitfall 4)
        try:
            db_attribution = await _build_attribution(
                run.tenant_id, run.user_id, run.skill_name
            )
            if db_attribution.get("entry_count", 0) > 0:
                merged = {**tool_attribution, **db_attribution}
                async with factory() as session:
                    await session.execute(
                        update(SkillRun)
                        .where(SkillRun.id == run.id)
                        .values(attribution=merged)
                    )
                    await session.commit()
        except Exception as attr_err:
            logger.warning(
                "Attribution enrichment failed for run %s: %s", run.id, attr_err
            )

        # Log budget summary as event
        await _append_event_atomic(factory, run.id, {
            "event": "budget",
            "data": run_context.budget.summary(),
        })

        # Build reasoning trace (post-completion, entry-level detail + tool calls)
        try:
            async with factory() as session:
                events_result = await session.execute(
                    select(SkillRun.events_log).where(SkillRun.id == run.id)
                )
                current_events = events_result.scalar_one_or_none() or []

            trace = await _build_reasoning_trace(
                run.tenant_id,
                run.user_id,
                run.skill_name,
                tool_attribution,
                current_events,
                "llm",
                tool_calls=tool_calls,
            )
            # Include tool snapshot for version safety auditing
            trace["tools_snapshot"] = tool_snapshot
            trace["agent_connected"] = agent_connected
            async with factory() as session:
                await session.execute(
                    update(SkillRun)
                    .where(SkillRun.id == run.id)
                    .values(reasoning_trace=trace)
                )
                await session.commit()
        except Exception as trace_err:
            logger.warning("Reasoning trace failed for run %s: %s", run.id, trace_err)

        # Emit "done" event with cost data (rendered_html omitted to avoid bloating events_log)
        await _append_event_atomic(factory, run.id, {
            "event": "done",
            "data": {
                "status": "completed",
                "duration_ms": duration_ms,
                "run_id": str(run.id),
                "tokens_used": total_tokens,
                "cost_estimate": float(cost) if cost else None,
            },
        })

        logger.info(
            "Run %s completed (skill=%s, duration=%dms, cost=$%.4f)",
            run.id, run.skill_name, duration_ms, cost or 0,
        )

    except Exception as e:
        # Mark as failed
        duration_ms = int((time.time() - start_time) * 1000)
        async with factory() as session:
            await session.execute(
                update(SkillRun)
                .where(SkillRun.id == run.id)
                .values(status="failed", error=str(e), duration_ms=duration_ms)
            )
            await session.commit()

        await _append_event_atomic(factory, run.id, {
            "event": "error",
            "data": {"message": str(e)},
        })

        logger.error("Run %s failed (skill=%s): %s", run.id, run.skill_name, e)


async def _execute_company_intel(
    api_key: str,
    input_text: str,
    factory: async_sessionmaker,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None = None,
) -> tuple[str, dict, list]:
    """Execute the company-intel engine directly, bypassing the LLM tool-use loop.

    The company-intel skill has a dedicated Python engine that handles crawling,
    LLM structuring, web enrichment, and context store writes. This avoids the
    need for a SKILL.md file and the generic tool-use loop.

    Args:
        api_key: Anthropic API key (BYOK or subsidy).
        input_text: Company URL to crawl.
        factory: Session factory for event logging and context writes.
        run_id: SkillRun UUID for event logging.
        tenant_id: Tenant UUID for context store writes.

    Returns:
        Tuple of (output_text, token_usage_dict, tool_calls_list).
    """
    from flywheel.engines.company_intel import (
        crawl_company,
        structure_intelligence,
        enrich_with_web_research,
    )
    from flywheel.storage import append_entry as async_append_entry

    url = input_text.strip()
    output_parts = []
    tool_calls = []

    # Stage 1: Crawl the website
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "crawling", "message": f"Crawling {url}..."},
    })

    crawl_result = await crawl_company(url)
    pages_crawled = crawl_result.get("pages_crawled", 0)
    tool_calls.append({"tool": "crawl_company", "input": url, "result_length": pages_crawled})

    if not crawl_result.get("success"):
        output_parts.append(f"Could not crawl {url}. No pages returned content.")
        return "\n\n".join(output_parts), {}, tool_calls

    # Save domain to tenant EARLY so cache lookups work for concurrent users.
    # Must happen before structure_intelligence (which is the expensive step).
    import urllib.parse as _urlparse_early
    _parsed_early = _urlparse_early.urlparse(url if url.startswith("http") else f"https://{url}")
    _early_domain = (_parsed_early.hostname or url).removeprefix("www.").lower()
    try:
        async with factory() as _dsess:
            await _dsess.execute(
                sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            # Only set domain if tenant doesn't already have one
            await _dsess.execute(
                sa_text(
                    "UPDATE tenants SET domain = :d WHERE id = :tid AND domain IS NULL"
                ),
                {"d": _early_domain, "tid": str(tenant_id)},
            )
            await _dsess.commit()
    except Exception as _early_err:
        # IntegrityError from unique constraint is fine -- another tenant already
        # owns this domain (handled at promote time).  Log and continue.
        logger.debug("Early domain save skipped or failed: %s", _early_err)

    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {
            "stage": "crawled",
            "message": f"Crawled {pages_crawled} pages",
        },
    })

    # Combine raw page text for structuring
    raw_text = "\n\n---\n\n".join(
        f"[{path}]\n{text}" for path, text in crawl_result["raw_pages"].items()
    )

    # Stage 2: Structure with LLM
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "structuring", "message": "Analyzing company information..."},
    })

    intelligence = await asyncio.to_thread(
        structure_intelligence, raw_text, "website-crawl", api_key=api_key
    )

    tool_calls.append({"tool": "structure_intelligence", "input": "raw_text", "result_length": len(str(intelligence))})

    if not intelligence.get("structured"):
        await _append_event_atomic(factory, run_id, {
            "event": "crawl_error",
            "data": {
                "error": "Unable to analyze company website. The AI service may be temporarily unavailable.",
                "retryable": True,
            },
        })
        output_parts.append(f"Crawled {pages_crawled} pages but could not structure the data.")
        return "\n\n".join(output_parts), {}, tool_calls

    company_name = intelligence.get("company_name", url)
    intelligence["_source_url"] = url

    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "structured", "message": f"Identified: {company_name}"},
    })

    # Stage 3: Enrich with web research
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "enriching", "message": "Researching company online..."},
    })

    enriched = await asyncio.to_thread(
        enrich_with_web_research, company_name, intelligence, api_key=api_key
    )

    tool_calls.append({"tool": "enrich_with_web_research", "input": company_name, "result_length": len(str(enriched))})

    # Helper to build grouped discovery events from an intelligence dict
    def _build_discoveries(data: dict) -> list[dict]:
        """Build grouped discovery events — one per category with items list."""
        groups: list[dict] = []

        # Company overview
        overview_items = []
        if data.get("company_name"):
            overview_items.append(data["company_name"])
        if data.get("what_they_do"):
            overview_items.append(data["what_they_do"])
        if data.get("headquarters"):
            overview_items.append(f"HQ: {data['headquarters']}")
        if data.get("founding_year"):
            overview_items.append(f"Founded: {data['founding_year']}")
        if data.get("employees"):
            overview_items.append(f"Team size: {data['employees']}")
        if overview_items:
            groups.append({"category": "company_info", "icon": "Building2",
                           "label": "Company", "items": overview_items})

        # Products
        products = data.get("products") or []
        if products:
            items = []
            for p in products[:6]:
                items.append(p if isinstance(p, str) else p.get("name", str(p)) if isinstance(p, dict) else str(p))
            groups.append({"category": "product", "icon": "Package",
                           "label": "Products", "items": items})

        # Target customers / ICP
        customers = data.get("target_customers") or []
        if customers:
            items = []
            for c in customers[:6]:
                items.append(c if isinstance(c, str) else c.get("name", str(c)) if isinstance(c, dict) else str(c))
            groups.append({"category": "customer", "icon": "UserCheck",
                           "label": "Ideal Customers", "items": items})

        # Industries
        industries = data.get("industries") or []
        if industries:
            items = [str(i) for i in industries[:6]]
            groups.append({"category": "market", "icon": "TrendingUp",
                           "label": "Industries", "items": items})

        # Competitors
        competitors = data.get("competitors") or []
        if competitors:
            items = []
            for c in competitors[:6]:
                items.append(c if isinstance(c, str) else c.get("name", str(c)) if isinstance(c, dict) else str(c))
            groups.append({"category": "competitive", "icon": "Swords",
                           "label": "Competitors", "items": items})

        # Differentiators
        diffs = data.get("key_differentiators") or []
        if diffs:
            items = [str(d) for d in diffs[:4]]
            groups.append({"category": "technology", "icon": "Cpu",
                           "label": "Differentiators", "items": items})

        # Funding
        if data.get("funding"):
            groups.append({"category": "financial", "icon": "DollarSign",
                           "label": "Funding", "items": [str(data["funding"])]})

        # Key people (from enrichment)
        people = data.get("key_people") or []
        if people:
            items = []
            for p in people[:5]:
                if isinstance(p, dict):
                    items.append(f"{p.get('name', '?')} — {p.get('title', '?')}")
                else:
                    items.append(str(p))
            groups.append({"category": "team", "icon": "Users",
                           "label": "Key People", "items": items})

        return groups

    # Emit structured discoveries immediately (don't wait for enrichment)
    structured_groups = _build_discoveries(intelligence)
    discovery_count = 0
    for group in structured_groups:
        discovery_count += 1
        await _append_event_atomic(factory, run_id, {
            "event": "discovery",
            "data": {
                "category": group["category"],
                "icon": group["icon"],
                "label": group["label"],
                "items": group["items"],
                "count": discovery_count,
            },
        })

    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "enriched", "message": "Web research complete"},
    })

    # Emit enrichment-only discoveries (key_people, funding, headquarters etc.
    # that weren't in the structured output)
    enrichment_groups = _build_discoveries(enriched)
    # Only emit groups that are new or have more items than structured
    structured_labels = {g["label"] for g in structured_groups}
    for group in enrichment_groups:
        if group["label"] not in structured_labels:
            discovery_count += 1
            await _append_event_atomic(factory, run_id, {
                "event": "discovery",
                "data": {
                    "category": group["category"],
                    "icon": group["icon"],
                    "label": group["label"],
                    "items": group["items"],
                    "count": discovery_count,
                },
            })

    # Stage 4a: Upsert into shared companies table (cache for all tenants)
    import urllib.parse as _urlparse_co
    _parsed_co = _urlparse_co.urlparse(url if url.startswith("http") else f"https://{url}")
    _co_domain = (_parsed_co.hostname or url).removeprefix("www.").lower()

    # Merge intelligence + enrichment for the cached intel dict
    _merged_intel = {**intelligence, **enriched}
    _merged_intel.pop("_source_url", None)  # keep source_url out of shared cache

    try:
        from flywheel.db.models import Company
        from sqlalchemy.dialects.postgresql import insert as _pg_insert

        async with factory() as _co_sess:
            _co_stmt = _pg_insert(Company).values(
                domain=_co_domain,
                name=_merged_intel.get("company_name"),
                intel=_merged_intel,
                crawled_at=datetime.now(timezone.utc),
            ).on_conflict_do_update(
                index_elements=["domain"],
                set_={
                    "name": _merged_intel.get("company_name"),
                    "intel": _merged_intel,
                    "crawled_at": datetime.now(timezone.utc),
                },
            )
            await _co_sess.execute(_co_stmt)
            await _co_sess.commit()
        logger.info("Upserted companies cache for domain=%s", _co_domain)
    except Exception as _co_err:
        logger.error("Companies table upsert failed for %s: %s", _co_domain, _co_err)

    # Stage 4b: Write to context store (async, tenant-scoped)
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "writing", "message": "Saving company intelligence..."},
    })

    from flywheel.engines.company_intel import (
        _build_positioning_content,
        _build_list_content,
    )
    from datetime import date as date_type

    today = date_type.today().isoformat()
    source = "company-intel-onboarding"
    write_results = {}

    section_map = {
        "positioning.md": _build_positioning_content(enriched),
        "icp-profiles.md": _build_list_content(
            enriched.get("target_customers", []), "target-customer-profiles"
        ),
        "competitive-intel.md": _build_list_content(
            enriched.get("competitors", []), "competitive-landscape"
        ),
        "product-modules.md": _build_list_content(
            enriched.get("products", []), "product-inventory"
        ),
        "market-taxonomy.md": _build_list_content(
            enriched.get("industries", []), "industry-verticals"
        ),
    }

    # Domain was already saved early (before structure_intelligence).
    # Re-derive for metadata use only -- no DB write needed here.
    import urllib.parse as _urlparse
    _parsed = _urlparse.urlparse(url if url.startswith("http") else f"https://{url}")
    company_domain = (_parsed.hostname or url).removeprefix("www.").lower()

    files_written = 0
    for filename, (content_lines, detail) in section_map.items():
        if not content_lines:
            continue

        entry = {
            "detail": detail,
            "confidence": "medium",
            "content": content_lines,
            "metadata": {"source_url": url},
        }

        try:
            async with factory() as session:
                # Set tenant + user context for RLS and NOT NULL constraint
                await session.execute(
                    sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
                )
                _uid = str(user_id) if user_id else str(tenant_id)
                await session.execute(
                    sa_text("SELECT set_config('app.user_id', :uid, true)"),
                    {"uid": _uid},
                )
                await async_append_entry(
                    session=session,
                    file=filename.replace(".md", ""),
                    entry=entry,
                    source=source,
                )
                await session.commit()
            write_results[filename] = "OK"
            files_written += 1
        except Exception as e:
            write_results[filename] = f"ERROR: {e}"
            logger.error("Context write failed for %s: %s", filename, e)

    tool_calls.append({"tool": "write_context", "input": str(list(section_map.keys())), "result_length": files_written})

    # Build output summary
    output_parts.append(f"# Company Intelligence: {company_name}")
    output_parts.append(f"\nCrawled {pages_crawled} pages from {url}")

    if enriched.get("what_they_do"):
        output_parts.append(f"\n**What they do:** {enriched['what_they_do']}")
    if enriched.get("products"):
        output_parts.append(f"\n**Products:** {', '.join(str(p) for p in enriched['products'])}")
    if enriched.get("target_customers"):
        output_parts.append(f"\n**Target customers:** {', '.join(str(c) for c in enriched['target_customers'])}")
    if enriched.get("competitors"):
        output_parts.append(f"\n**Competitors:** {', '.join(str(c) for c in enriched['competitors'])}")
    if enriched.get("industries"):
        output_parts.append(f"\n**Industries:** {', '.join(str(i) for i in enriched['industries'])}")
    if enriched.get("key_differentiators"):
        output_parts.append(f"\n**Key differentiators:** {', '.join(str(d) for d in enriched['key_differentiators'])}")
    if enriched.get("key_people"):
        people = enriched["key_people"]
        if isinstance(people, list) and people:
            people_strs = []
            for p in people:
                if isinstance(p, dict):
                    people_strs.append(f"{p.get('name', '?')} ({p.get('title', '?')})")
                else:
                    people_strs.append(str(p))
            output_parts.append(f"\n**Key people:** {', '.join(people_strs)}")
    if enriched.get("funding"):
        output_parts.append(f"\n**Funding:** {enriched['funding']}")
    if enriched.get("headquarters"):
        output_parts.append(f"\n**Headquarters:** {enriched['headquarters']}")

    output_parts.append(f"\n\nWrote intelligence to {files_written} context files.")

    # Surface any write errors in output
    failed_writes = {k: v for k, v in write_results.items() if v != "OK"}
    if failed_writes:
        output_parts.append("\nNote: Some context writes failed:")
        for fname, err in failed_writes.items():
            output_parts.append(f"  - {fname}: {err}")
            logger.error("Context write failed for %s: %s", fname, err)

    # Token usage is approximate (sync client doesn't easily return counts)
    token_usage = {"input_tokens": 0, "output_tokens": 0, "model": "claude-sonnet-4-20250514"}

    return "\n".join(output_parts), token_usage, tool_calls


async def _execute_meeting_prep(
    api_key: str,
    input_text: str,
    factory: async_sessionmaker,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None = None,
) -> tuple[str, dict, list]:
    """Execute the meeting-prep engine: research person + company, generate HTML briefing.

    Parses LinkedIn URL and agenda from input_text, runs parallel web_search
    research for the person and their company, generates a polished HTML briefing
    via LLM, and writes contact info to the context store.

    Args:
        api_key: Anthropic API key (BYOK or subsidy).
        input_text: Formatted as "LinkedIn: {url}\\nAgenda: {agenda}\\nType: {type}".
        factory: Session factory for event logging and context writes.
        run_id: SkillRun UUID for event logging.
        tenant_id: Tenant UUID for context store writes.

    Returns:
        Tuple of (html_output, token_usage_dict, tool_calls_list).
    """
    import re
    import anthropic

    tool_calls = []
    total_input_tokens = 0
    total_output_tokens = 0

    # ------------------------------------------------------------------
    # Stage 1: Parse input
    # ------------------------------------------------------------------
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "parsing", "message": "Preparing research..."},
    })

    # Extract fields from formatted input
    linkedin_url = ""
    agenda = ""
    meeting_type = "discovery"
    company_name = ""

    for line in input_text.strip().split("\n"):
        if line.startswith("LinkedIn:"):
            linkedin_url = line.split(":", 1)[1].strip()
        elif line.startswith("Agenda:"):
            agenda = line.split(":", 1)[1].strip()
        elif line.startswith("Type:"):
            meeting_type = line.split(":", 1)[1].strip()
        elif line.startswith("Company:"):
            company_name = line.split(":", 1)[1].strip()

    # Extract person name from LinkedIn URL slug (e.g. /in/cheok-yen-kwan -> Cheok Yen Kwan)
    person_name = "the contact"
    slug_match = re.search(r"/in/([^/?]+)", linkedin_url)
    if slug_match:
        slug = slug_match.group(1)
        person_name = slug.replace("-", " ").title()

    logger.info(
        "Meeting prep: person=%s, url=%s, agenda=%s, type=%s, company=%s",
        person_name, linkedin_url, agenda, meeting_type, company_name,
    )

    # ------------------------------------------------------------------
    # Stage 1b: Check context store for existing knowledge (the flywheel)
    # ------------------------------------------------------------------
    existing_contact = ""
    existing_company_intel = ""
    existing_meetings = ""
    try:
        from flywheel.storage import read_context, query_context
        _uid = str(user_id) if user_id else str(tenant_id)
        async with factory() as session:
            await session.execute(
                sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            await session.execute(
                sa_text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": _uid},
            )
            # Search for this person in contacts
            contacts = await query_context(session, "contacts", search=person_name)
            if contacts:
                existing_contact = "\n".join(
                    f"- {e.get('content', '')[:200]}" for e in contacts[:2]
                )
                logger.info("Meeting prep: found existing contact data for %s", person_name)

            # Search for company intel
            if company_name:
                positioning = await query_context(session, "positioning", search=company_name)
                if positioning:
                    existing_company_intel = "\n".join(
                        f"- {e.get('content', '')[:200]}" for e in positioning[:2]
                    )

            # Search for prior meetings with this person
            meetings = await query_context(session, "meeting-history", search=person_name)
            if meetings:
                existing_meetings = "\n".join(
                    f"- {e.get('content', '')[:200]}" for e in meetings[:3]
                )
                logger.info("Meeting prep: found %d prior meetings with %s", len(meetings), person_name)
    except Exception as e:
        logger.warning("Context lookup failed (proceeding with fresh research): %s", e)

    # ------------------------------------------------------------------
    # Stage 2 & 3: Research person + company via web_search
    # ------------------------------------------------------------------
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "researching", "message": f"Researching {person_name}..."},
    })

    # Helper to run a sync Anthropic web_search call in a thread
    def _research_person() -> tuple[dict, dict]:
        """Web search for person info. Returns (person_data, usage).

        Uses the full LinkedIn URL as the primary search query for accurate
        disambiguation (prevents wrong-person matches for common names).
        Falls back to name-only search if no LinkedIn URL is available.
        Tracks research_source confidence: linkedin_indexed or name_search.
        """
        try:
            client = anthropic.Anthropic(api_key=api_key)

            # Build the search prompt with LinkedIn URL as primary identifier
            if linkedin_url:
                company_hint = (
                    f"\nThey work at {company_name}. " if company_name else ""
                )
                search_prompt = (
                    f"Research the person at this LinkedIn profile: {linkedin_url}\n"
                    f"Find information about them from Google-indexed sources that "
                    f"reference this LinkedIn URL or the person it belongs to.\n"
                    f"Their name appears to be: {person_name}\n"
                    f"{company_hint}\n"
                    f"IMPORTANT: Use the LinkedIn URL as the primary search query to "
                    f"find the EXACT right person. Do NOT rely on name alone — common "
                    f"names match multiple people. Search for the URL itself, and also "
                    f"search for the person's name combined with any company/role info "
                    f"found from the URL-based search.\n\n"
                    f"Do NOT try to fetch LinkedIn directly — it blocks automated access. "
                    f"Instead search Google for cached/indexed LinkedIn data, news articles, "
                    f"conference talks, blog posts, and other sources that reference this "
                    f"specific profile URL.\n\n"
                )
                research_source = "linkedin_indexed"
            else:
                company_hint = (
                    f" at {company_name}" if company_name else ""
                )
                search_prompt = (
                    f"Research this person for a meeting briefing: {person_name}"
                    f"{company_hint}.\n\n"
                    f"Search Google for information about them — their role, company, "
                    f"background from news articles, conference talks, blog posts, etc.\n\n"
                )
                research_source = "name_search"

            search_prompt += (
                f"After researching, return ONLY a JSON object (no markdown fencing) with:\n"
                f"- name: string (their full name)\n"
                f"- title: string (current job title)\n"
                f"- company: string (current company name)\n"
                f"- location: string or null\n"
                f"- summary: string (2-3 sentence professional summary)\n"
                f"- education: list of strings (degrees/schools) or empty list\n"
                f"- experience_highlights: list of strings (notable career highlights)\n"
                f"- interests: list of strings (professional interests, topics they speak/write about)\n"
                f"- mutual_context: string or null (anything relevant for building rapport)\n"
            )

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5,
                }],
                messages=[{
                    "role": "user",
                    "content": search_prompt,
                }],
            )

            # Extract text from response
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)

            full_text = "\n".join(text_parts).strip()

            # Parse JSON from response
            import json as _json
            json_match = re.search(r'\{[\s\S]*\}', full_text)
            person_data = {}
            if json_match:
                try:
                    person_data = _json.loads(json_match.group())
                except _json.JSONDecodeError:
                    person_data = {"name": person_name, "raw_text": full_text}
            else:
                person_data = {"name": person_name, "raw_text": full_text}

            # Track research source confidence
            person_data["research_source"] = research_source

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            return person_data, usage
        except Exception:
            logger.exception("_research_person failed")
            return {"name": person_name, "research_source": "name_search"}, {"input_tokens": 0, "output_tokens": 0}

    def _research_company(co_name: str) -> tuple[dict, dict]:
        """Web search for company info. Returns (company_data, usage)."""
        if not co_name:
            return {}, {"input_tokens": 0, "output_tokens": 0}

        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 3,
                }],
                messages=[{
                    "role": "user",
                    "content": (
                        f"Research the company '{co_name}' for a meeting briefing.\n\n"
                        f"Search for: what they do, key products/services, industry, "
                        f"company size, recent news, funding, competitors.\n\n"
                        f"Return ONLY a JSON object (no markdown fencing) with:\n"
                        f"- company_name: string\n"
                        f"- what_they_do: string (1-2 sentence summary)\n"
                        f"- products: list of strings\n"
                        f"- industry: string\n"
                        f"- size: string (e.g. '50-200 employees')\n"
                        f"- recent_news: list of strings (2-3 recent headlines)\n"
                        f"- competitors: list of strings\n"
                        f"- headquarters: string or null\n"
                    ),
                }],
            )

            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)

            full_text = "\n".join(text_parts).strip()

            import json as _json
            json_match = re.search(r'\{[\s\S]*\}', full_text)
            company_data = {}
            if json_match:
                try:
                    company_data = _json.loads(json_match.group())
                except _json.JSONDecodeError:
                    company_data = {"company_name": co_name, "raw_text": full_text}
            else:
                company_data = {"company_name": co_name, "raw_text": full_text}

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            return company_data, usage
        except Exception:
            logger.exception("_research_company failed for %s", co_name)
            return {"company_name": co_name}, {"input_tokens": 0, "output_tokens": 0}

    # Run person research first (we need company name for company research)
    person_data, person_usage = await asyncio.to_thread(_research_person)
    total_input_tokens += person_usage.get("input_tokens", 0)
    total_output_tokens += person_usage.get("output_tokens", 0)
    tool_calls.append({
        "tool": "web_search_person",
        "input": linkedin_url,
        "result_length": len(str(person_data)),
    })

    # Extract company name from person research
    company_name = person_data.get("company", "")
    person_name = person_data.get("name", person_name)

    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {
            "stage": "person_researched",
            "message": f"Found: {person_name}" + (f" at {company_name}" if company_name else ""),
        },
    })

    # Now research the company (if we have a name)
    if company_name:
        await _append_event_atomic(factory, run_id, {
            "event": "stage",
            "data": {"stage": "researching_company", "message": f"Researching {company_name}..."},
        })

        company_data, company_usage = await asyncio.to_thread(
            _research_company, company_name
        )
        total_input_tokens += company_usage.get("input_tokens", 0)
        total_output_tokens += company_usage.get("output_tokens", 0)
        tool_calls.append({
            "tool": "web_search_company",
            "input": company_name,
            "result_length": len(str(company_data)),
        })
    else:
        company_data = {}

    # ------------------------------------------------------------------
    # Stage 4: Generate HTML briefing via LLM
    # ------------------------------------------------------------------
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "generating", "message": "Generating briefing..."},
    })

    # Pre-load tenant context asynchronously (before entering sync thread)
    _tenant_context_preloaded = ""
    try:
        ctx_files = ["positioning", "icp-profiles", "competitive-intel",
                     "product-modules", "market-taxonomy"]
        ctx_parts = []
        for cf in ctx_files:
            try:
                async with factory() as _s:
                    await _s.execute(
                        sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                        {"tid": str(tenant_id)},
                    )
                    from sqlalchemy import select as _sel
                    from flywheel.db.models import ContextEntry as _CE
                    _rows = (await _s.execute(
                        _sel(_CE.content).where(
                            _CE.tenant_id == tenant_id,
                            _CE.file_name == cf,
                            _CE.deleted_at.is_(None),
                        ).limit(5)
                    )).scalars().all()
                    if _rows:
                        ctx_parts.append(f"### {cf}\n" + "\n".join(
                            r[:500] if isinstance(r, str) else str(r)[:500] for r in _rows
                        ))
            except Exception:
                continue
        if ctx_parts:
            _tenant_context_preloaded = "\n\n".join(ctx_parts)
    except Exception:
        pass

    def _generate_briefing() -> tuple[str, dict]:
        """Generate HTML briefing using the meeting-prep SKILL.md prompt.

        Loads the full SKILL.md system prompt (from DB or filesystem) and
        provides pre-collected research as context. Instructs Claude to skip
        Steps 0-5 (research, already done by engine) and execute Steps 6-8
        (hypothesis, questions, HTML briefing).
        """
        try:
            client = anthropic.Anthropic(api_key=api_key)

            today_str = datetime.now().strftime("%B %d, %Y")

            # Load the meeting-prep SKILL.md system prompt
            # Try DB first (skill_definitions), fall back to filesystem
            skill_prompt = None
            try:
                import asyncio as _aio
                _meta = _aio.get_event_loop().run_until_complete(
                    _load_skill_from_db(factory, "meeting-prep")
                )
                if _meta and _meta.get("system_prompt"):
                    skill_prompt = _meta["system_prompt"]
            except Exception:
                pass

            if not skill_prompt:
                # Fall back to reading SKILL.md from filesystem
                skill_md_path = Path(__file__).resolve().parents[4] / "skills" / "meeting-prep" / "SKILL.md"
                if skill_md_path.exists():
                    raw = skill_md_path.read_text()
                    # Strip YAML frontmatter
                    if raw.startswith("---"):
                        end = raw.find("---", 3)
                        if end != -1:
                            skill_prompt = raw[end + 3:].strip()
                        else:
                            skill_prompt = raw
                    else:
                        skill_prompt = raw

            if not skill_prompt:
                skill_prompt = "You are a meeting preparation specialist."

            # Use pre-loaded tenant context (loaded async before thread)
            tenant_context = _tenant_context_preloaded

            # Build system prompt: focused on intel briefing (no questions)
            system_prompt = (
                f"{skill_prompt}\n\n"
                "---\n\n"
                "IMPORTANT OVERRIDE FOR THIS EXECUTION:\n\n"
                "Steps 0-5 (research) have ALREADY been completed by the engine.\n\n"
                "Your job: Generate a **business intelligence briefing** as HTML.\n\n"
                "CRITICAL CONTENT RULES:\n"
                "- DO NOT include 'Suggested Questions' or 'Question' sections\n"
                "- DO NOT include objection prep sections\n"
                "- FOCUS on business-relevant intelligence that helps the user "
                "understand this person and their company in the context of "
                "the user's OWN business\n"
                "- If tenant context is provided below, cross-reference: how does "
                "the contact's company relate to the tenant's business? Are they "
                "a potential customer, partner, competitor?\n"
                "- Include: partnership announcements, marketing spend/budgets, "
                "technology investments, relevant industry news\n"
                "- Include: other key people in the contact's team/department "
                "(if found in research)\n"
                "- Make every piece of intel actionable and specific\n\n"
                "BRIEFING SECTIONS (in this order):\n"
                "1. Header — person name, title, company, meeting date\n"
                "2. About [Person] — role, background, career highlights\n"
                "3. About [Company] — what they do, size, industry position\n"
                "4. Business Relevance — how this company relates to YOUR business "
                "(cross-reference tenant context), relevant spend, partnerships, "
                "competitor usage\n"
                "5. Key Team Members — other people in relevant roles at the company\n"
                "6. Recent News & Signals — industry-relevant announcements, "
                "funding, partnerships, regulatory changes\n"
                "7. Talking Points — 3-4 specific, non-intrusive conversation starters "
                "based on the intel\n\n"
                "Output ONLY the HTML. No markdown fencing, no explanation.\n\n"
                "HTML constraints: ONLY inline styles, no external CSS, no <style> blocks.\n"
                "Design tokens:\n"
                "- Font: Inter, -apple-system, sans-serif\n"
                "- Max width: 720px, centered, padding 48px 24px\n"
                "- Brand accent: #E94D35 (warm coral)\n"
                "- Headings: #121212, Body: #374151, Secondary: #6B7280\n"
                "- Sections separated by hr with border-top: 1px solid #E5E7EB\n"
            )

            import json as _json
            user_content = (
                f"Generate a business intelligence briefing for a **{meeting_type}** "
                f"call on {today_str}.\n\n"
                f"## Pre-Collected Research Data\n\n"
                f"### Person Research\n"
                f"```json\n{_json.dumps(person_data, indent=2, default=str)}\n```\n\n"
                f"### Company Research\n"
                f"```json\n{_json.dumps(company_data, indent=2, default=str)}\n```\n\n"
            )
            if tenant_context:
                user_content += (
                    f"## Our Business Context (tenant's own data)\n"
                    f"Use this to cross-reference and show business relevance:\n\n"
                    f"{tenant_context}\n\n"
                )
            if agenda:
                user_content += f"### Meeting Agenda\n{agenda}\n\n"

            # Add prior interaction context (the flywheel payoff)
            if existing_contact or existing_meetings:
                user_content += "## Prior Knowledge (from previous interactions)\n\n"
                if existing_contact:
                    user_content += f"### What we already knew about this person\n{existing_contact}\n\n"
                if existing_meetings:
                    user_content += f"### Previous meetings/interactions\n{existing_meetings}\n\n"
                user_content += (
                    "IMPORTANT: Reference prior interactions in the briefing. "
                    "Show what's NEW since the last meeting vs what we already knew. "
                    "This demonstrates compounding intelligence.\n\n"
                )

            # Add research confidence warning for name-only fallback
            research_source = person_data.get("research_source", "linkedin_indexed")
            if research_source == "name_search":
                user_content += (
                    "## IMPORTANT: Research Confidence Warning\n"
                    "LinkedIn profile could not be accessed or was not provided. "
                    "Research is based on web search by name only — there is a risk "
                    "of wrong-person matches for common names.\n\n"
                    "You MUST include a visible warning banner at the TOP of the "
                    "briefing HTML (after the header), styled as:\n"
                    '`<div style="background: #FEF3C7; border: 1px solid #F59E0B; '
                    "border-radius: 8px; padding: 12px 16px; margin-bottom: 24px; "
                    'font-size: 14px; color: #92400E;">`\n'
                    "with text: 'Note: LinkedIn profile could not be accessed directly. "
                    "This briefing is based on web search by name — please verify the "
                    "person details are correct.'\n\n"
                )

            user_content += (
                f"### Meeting Details\n"
                f"- Person: {person_name}\n"
                f"- Company: {company_name or 'Unknown'}\n"
                f"- LinkedIn: {linkedin_url}\n"
                f"- Meeting type: {meeting_type}\n"
                f"- Research source: {research_source}\n\n"
                "Generate the HTML briefing now. Focus on business intelligence, "
                "NOT interview questions."
            )

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )

            html = ""
            for block in response.content:
                if hasattr(block, "text"):
                    html += block.text

            # Strip markdown fencing if present
            html = html.strip()
            if html.startswith("```html"):
                html = html[7:]
            if html.startswith("```"):
                html = html[3:]
            if html.endswith("```"):
                html = html[:-3]
            html = html.strip()

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            return html, usage
        except Exception:
            logger.exception("_generate_briefing failed")
            raise

    html_briefing, briefing_usage = await asyncio.to_thread(_generate_briefing)
    total_input_tokens += briefing_usage.get("input_tokens", 0)
    total_output_tokens += briefing_usage.get("output_tokens", 0)
    tool_calls.append({
        "tool": "generate_briefing",
        "input": "person + company research",
        "result_length": len(html_briefing),
    })

    # ------------------------------------------------------------------
    # Stage 5: Write ALL research to context store (the flywheel)
    #
    # Every meeting prep compounds intelligence:
    # 1. contacts       — person details (deduped by name)
    # 2. meeting-history — what we prepped for, when, with whom
    # 3. Company intel   — positioning, competitors, products (if new)
    # 4. relationship-intel — how this person connects to our business
    # ------------------------------------------------------------------
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "writing", "message": "Saving to context store..."},
    })

    from flywheel.storage import append_entry as async_append_entry

    _uid = str(user_id) if user_id else str(tenant_id)
    files_written = 0

    async def _write_entry(file: str, detail: str, content_lines: list[str], source: str = "meeting-prep") -> bool:
        """Write a single context entry with proper RLS context. Returns True on success."""
        nonlocal files_written
        if not content_lines:
            return False
        try:
            async with factory() as session:
                await session.execute(
                    sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
                )
                await session.execute(
                    sa_text("SELECT set_config('app.user_id', :uid, true)"),
                    {"uid": _uid},
                )
                await async_append_entry(
                    session=session,
                    file=file,
                    entry={"detail": detail, "confidence": "medium", "content": content_lines},
                    source=source,
                )
                await session.commit()
            files_written += 1
            return True
        except Exception as e:
            logger.error("Context write failed for %s/%s: %s", file, detail, e)
            return False

    # --- 1. Contact card (deduped by person name) ---
    contact_lines = []
    if person_data.get("name"):
        contact_lines.append(f"Name: {person_data['name']}")
    if person_data.get("title"):
        contact_lines.append(f"Title: {person_data['title']}")
    if person_data.get("company"):
        contact_lines.append(f"Company: {person_data['company']}")
    if person_data.get("location"):
        contact_lines.append(f"Location: {person_data['location']}")
    if linkedin_url:
        contact_lines.append(f"LinkedIn: {linkedin_url}")
    if person_data.get("summary"):
        contact_lines.append(f"Summary: {person_data['summary']}")
    if person_data.get("education"):
        for edu in person_data["education"][:3]:
            contact_lines.append(f"Education: {edu}")
    if person_data.get("experience_highlights"):
        for exp in person_data["experience_highlights"][:3]:
            contact_lines.append(f"Experience: {exp}")
    if person_data.get("interests"):
        contact_lines.append(f"Interests: {', '.join(person_data['interests'][:5])}")

    pname = person_data.get("name", "unknown")
    await _write_entry("contacts", f"{pname}", contact_lines)

    # --- 2. Meeting history (every prep is a compounding event) ---
    from datetime import datetime as _dt
    meeting_lines = [
        f"Date: {_dt.now().strftime('%Y-%m-%d')}",
        f"Type: {meeting_type}",
        f"Contact: {pname}",
    ]
    if person_data.get("company"):
        meeting_lines.append(f"Company: {person_data['company']}")
    if agenda:
        meeting_lines.append(f"Agenda: {agenda}")
    if linkedin_url:
        meeting_lines.append(f"LinkedIn: {linkedin_url}")
    meeting_lines.append("Status: prepared")

    await _write_entry(
        "meeting-history",
        f"{pname} — {meeting_type} — {_dt.now().strftime('%Y-%m-%d')}",
        meeting_lines,
    )

    # --- 3. Company intel (only if we researched the company) ---
    if company_data and company_data.get("company_name"):
        co = company_data

        # Positioning
        pos_lines = []
        if co.get("company_name"):
            pos_lines.append(f"Company: {co['company_name']}")
        if co.get("what_they_do"):
            pos_lines.append(f"Description: {co['what_they_do']}")
        if co.get("industry"):
            pos_lines.append(f"Industry: {co['industry']}")
        if co.get("size"):
            pos_lines.append(f"Size: {co['size']}")
        if co.get("headquarters"):
            pos_lines.append(f"Headquarters: {co['headquarters']}")
        await _write_entry(
            "positioning",
            f"{co['company_name']} — from meeting-prep",
            pos_lines,
            source="meeting-prep",
        )

        # Competitors
        competitors = co.get("competitors", [])
        if competitors:
            await _write_entry(
                "competitive-intel",
                f"{co['company_name']} competitors",
                [str(c) for c in competitors[:6]],
                source="meeting-prep",
            )

        # Products
        products = co.get("products", [])
        if products:
            await _write_entry(
                "product-modules",
                f"{co['company_name']} products",
                [str(p) for p in products[:6]],
                source="meeting-prep",
            )

        # Recent news (high-value signal for future preps)
        news = co.get("recent_news", [])
        if news:
            news_lines = []
            for n in news[:5]:
                if isinstance(n, dict):
                    news_lines.append(f"{n.get('title', '')} ({n.get('date', '')})")
                else:
                    news_lines.append(str(n))
            await _write_entry(
                "market-signals",
                f"{co['company_name']} — recent news",
                news_lines,
                source="meeting-prep",
            )

    # --- 4. Relationship intel (how this person connects to our business) ---
    rel_lines = []
    if person_data.get("mutual_context"):
        rel_lines.append(f"Mutual context: {person_data['mutual_context']}")
    if agenda:
        rel_lines.append(f"Discussion topic: {agenda}")
    if meeting_type:
        rel_lines.append(f"Relationship stage: {meeting_type}")
    if person_data.get("interests"):
        rel_lines.append(f"Their interests: {', '.join(person_data['interests'][:5])}")

    if rel_lines:
        await _write_entry(
            "relationship-intel",
            f"{pname} — relationship context",
            rel_lines,
        )

    tool_calls.append({
        "tool": "write_context",
        "input": f"{files_written} context files",
        "result_length": files_written,
    })

    logger.info("Meeting prep wrote %d context files for %s", files_written, pname)

    # ------------------------------------------------------------------
    # Stage 6: Return HTML briefing
    # ------------------------------------------------------------------
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "complete", "message": "Briefing ready"},
    })

    token_usage = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "model": "claude-sonnet-4-20250514",
    }

    return html_briefing, token_usage, tool_calls


def _append_skipped_steps_note(
    output_text: str,
    tool_calls_made: list[dict],
    agent_connected: bool,
) -> str:
    """Deterministically scan tool results for skipped browser steps.

    After the tool loop completes, this function checks all tool call records
    for AGENT_NOT_CONNECTED or AGENT_TIMEOUT markers and appends a structured
    note to the output. Also adds a note when browser tools were excluded
    because the agent was not connected.

    This is NOT optional and does NOT rely on Claude choosing to summarize
    skipped steps. It guarantees the must-have truth that skipped steps are
    noted in output by engineered behavior, not LLM judgment.
    """
    skipped_steps = []
    for call in tool_calls_made:
        tool_name = call.get("tool", "unknown")
        result_snippet = call.get("result_snippet", "")
        # Check if the tool result contains AGENT_NOT_CONNECTED or AGENT_TIMEOUT
        # markers returned by browser_tools handlers when the agent disconnects
        if any(marker in result_snippet for marker in AGENT_SKIP_MARKERS):
            skipped_steps.append(tool_name)

    # Also check: if browser tools exist in registry but were excluded
    # (agent not connected), note the reduced capability
    if not agent_connected and not skipped_steps:
        # No skipped steps to report (browser tools were excluded from tool
        # list entirely, so Claude never tried to call them). Add a note
        # about reduced capability only if the output doesn't already mention it.
        return output_text

    if skipped_steps:
        unique_skipped = list(dict.fromkeys(skipped_steps))  # preserve order, dedupe
        skip_note = (
            f"\n\n---\nSkipped browser steps (agent unavailable): "
            f"{', '.join(unique_skipped)}"
        )
        output_text += skip_note

    return output_text


async def _execute_with_tools(
    api_key: str,
    skill_name: str,
    input_text: str,
    registry: "ToolRegistry",
    context: "RunContext",
    factory: async_sessionmaker,
    run_id: UUID,
    max_iterations: int = 25,
    agent_connected: bool = False,
    system_prompt_override: str | None = None,
) -> tuple[str, dict, list]:
    """Execute a skill using AsyncAnthropic with the tool registry.

    This is the web execution path that bypasses the sync execution_gateway.
    It directly calls the Anthropic API with tool definitions from the
    registry and routes tool_use responses back through the registry.

    Args:
        api_key: Decrypted BYOK API key.
        skill_name: Name of the skill to execute.
        input_text: User's input text.
        registry: Tool registry with all available tools.
        context: Run context with budget, tenant, session factory.
        factory: Session factory for event logging.
        run_id: SkillRun UUID for event logging.
        max_iterations: Maximum tool_use loop iterations (default 25).
        agent_connected: Whether the user's local agent is connected.
        system_prompt_override: If provided (from DB), use this instead of
            parsing SKILL.md from the filesystem. Enables RT-02.

    Returns:
        Tuple of (output_text, token_usage_dict, tool_calls_list).
    """
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Build system prompt: prefer DB override (RT-02), fall back to SKILL.md
    # TODO: Remove filesystem fallback after confirming all skills are seeded
    if system_prompt_override:
        system_prompt = system_prompt_override
    else:
        logger.warning(
            "Run %s: no DB system_prompt for '%s', falling back to SKILL.md",
            run_id, skill_name,
        )
        _skills_engines_dir = str(
            Path(__file__).resolve().parents[4] / "skills" / "_shared" / "engines"
        )
        if _skills_engines_dir not in sys.path:
            sys.path.insert(0, _skills_engines_dir)
        from skill_converter import convert_skill

        spec = convert_skill(skill_name)
        system_prompt = spec.system_prompt

    # Snapshot tool definitions for version safety
    # When agent is not connected, exclude browser tools so Claude never
    # sees them and won't attempt to call them (Tier 2 graceful degradation)
    tool_defs = registry.get_anthropic_tools(
        skill_name=skill_name,
        exclude_browser=not agent_connected,
    )

    # Replace any custom web_search tool with Anthropic's server-side built-in.
    # The built-in is resolved by the API — no Tavily dependency, no local handler.
    # Gives every skill web research without requiring a local browser agent.
    tool_defs = [t for t in tool_defs if t.get("name") != "web_search"]
    tool_defs.append({
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 5,
    })

    # Initial message
    messages = [{"role": "user", "content": input_text}]

    # Cumulative token tracking
    total_input_tokens = 0
    total_output_tokens = 0
    tool_calls_made: list[dict] = []

    for _iteration in range(max_iterations):
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=tool_defs,
            messages=messages,
        )

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        if response.stop_reason == "end_turn":
            # Extract text from content blocks
            output_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    output_parts.append(block.text)
            output_text = "\n".join(output_parts) if output_parts else ""

            # Post-loop: deterministic skipped-step scanning
            output_text = _append_skipped_steps_note(output_text, tool_calls_made, agent_connected)

            token_usage = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "model": "claude-sonnet-4-20250514",
            }
            return output_text, token_usage, tool_calls_made

        if response.stop_reason == "tool_use":
            # Build assistant message content and tool results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    # Emit SSE event for real-time progress
                    await _append_event_atomic(factory, run_id, {
                        "event": "stage",
                        "data": {
                            "stage": "tool_call",
                            "tool": block.name,
                            "message": f"Using {block.name}...",
                        },
                    })

                    # Execute tool through registry
                    result = await registry.execute(block.name, block.input, context)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

                    # Track for reasoning trace and skipped-step detection
                    input_summary = str(block.input)
                    if len(input_summary) > 200:
                        input_summary = input_summary[:200] + "..."
                    # Store result snippet for AGENT_SKIP_MARKERS detection
                    result_snippet = result[:300] if isinstance(result, str) else str(result)[:300]
                    tool_calls_made.append({
                        "tool": block.name,
                        "input": input_summary,
                        "result_length": len(result),
                        "result_snippet": result_snippet,
                    })

            # Append assistant response + tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason -- return what we have
            output_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    output_parts.append(block.text)
            output_text = "\n".join(output_parts) if output_parts else ""
            output_text = _append_skipped_steps_note(output_text, tool_calls_made, agent_connected)
            token_usage = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "model": "claude-sonnet-4-20250514",
            }
            return output_text, token_usage, tool_calls_made

    # Max iterations exceeded
    output_text = _append_skipped_steps_note(
        "Skill exceeded maximum iterations", tool_calls_made, agent_connected
    )
    token_usage = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "model": "claude-sonnet-4-20250514",
    }
    return output_text, token_usage, tool_calls_made


# Legacy sync path -- used by CLI gateway (execution_gateway.py). Web uses _execute_with_tools().
def _execute_with_api_key(
    api_key: str, skill_name: str, input_text: str, user_id: str
):
    """Execute skill with BYOK key set in environment (thread-safe).

    The execution_gateway reads ANTHROPIC_API_KEY from os.environ.
    We acquire a lock, set the key, execute, and restore the original value.
    """
    from flywheel.engines.execution_gateway import execute_skill

    with _env_lock:
        original_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = api_key
        try:
            return execute_skill(
                skill_name=skill_name,
                input_text=input_text,
                user_id=user_id,
                force_llm=True,
            )
        finally:
            if original_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = original_key
            else:
                os.environ.pop("ANTHROPIC_API_KEY", None)


async def _get_user_api_key(
    factory: async_sessionmaker[AsyncSession],
    user_id: UUID | None,
) -> str | None:
    """Retrieve and decrypt the user's BYOK API key.

    Args:
        factory: Session factory for DB access.
        user_id: The user's UUID.

    Returns:
        Decrypted API key string, or None if user has no key.
    """
    if user_id is None:
        return None

    from sqlalchemy import select

    async with factory() as session:
        result = await session.execute(
            select(User.api_key_encrypted).where(User.id == user_id)
        )
        encrypted = result.scalar_one_or_none()

    if encrypted is None:
        return None

    from flywheel.auth.encryption import decrypt_api_key
    return decrypt_api_key(encrypted)


async def _append_event_atomic(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    event_dict: dict,
) -> None:
    """Append an event to the run's events_log JSONB array atomically.

    Uses PostgreSQL's || operator for atomic array concatenation,
    avoiding the read-modify-write race condition.

    Args:
        factory: Session factory for DB access.
        run_id: The SkillRun UUID.
        event_dict: Event dict to append (must be JSON-serializable).
    """
    async with factory() as session:
        await session.execute(
            sa_text("""
                UPDATE skill_runs
                SET events_log = events_log || CAST(:event AS jsonb)
                WHERE id = :run_id
            """),
            {"run_id": str(run_id), "event": json.dumps([event_dict])},
        )
        await session.commit()
