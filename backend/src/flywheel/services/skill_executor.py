"""Skill execution -- async tool_use loop (web) and sync gateway bridge (CLI).

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
from uuid import UUID

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

# ---------------------------------------------------------------------------
# Skill Browser Tiers:
# - Tier 1: Cloud-only skills. No browser tools needed. Always available.
# - Tier 2: Skills that benefit from browser but work without.
#   When agent not connected: browser tools excluded from tool list,
#   skill runs with reduced capability + note in output.
# - Tier 3: Skills that REQUIRE browser automation to function.
#   When agent not connected: execution blocked with clear error message.
#
# Classification is by skill name in TIER_3_SKILLS set.
# All other skills with browser tool usage are implicitly Tier 2.
# Skills that never use browser tools are implicitly Tier 1.
# ---------------------------------------------------------------------------
TIER_3_SKILLS: set[str] = {"gtm-web-scraper", "dogfood-tester"}

# Skills with dedicated Python engines that bypass the LLM tool-use loop.
# These run their own crawl/structure/write logic directly.
ENGINE_SKILLS: set[str] = {"company-intel"}

# Markers in tool results that indicate a browser step was skipped
AGENT_SKIP_MARKERS = ["AGENT_NOT_CONNECTED", "AGENT_TIMEOUT"]

# Thread lock for env var manipulation during execute_skill calls.
# The execution_gateway reads ANTHROPIC_API_KEY from os.environ, so we
# must set it before calling execute_skill and restore it after.
_env_lock = threading.Lock()

# Path to the engines directory (v1 execution gateway location)
_ENGINES_DIR = Path(__file__).resolve().parents[3] / "engines"


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
            # Fall back to subsidy key for onboarding skills (anonymous users)
            from flywheel.config import settings
            if run.skill_name in ("company-intel",) and settings.flywheel_subsidy_api_key:
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

        # Tier 3 skills require the agent -- fail fast if not connected
        if run.skill_name in TIER_3_SKILLS and not agent_connected:
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
            "Run %s: active_focus=%s, merged_settings_keys=%s, agent_connected=%s",
            run.id,
            active_focus_id,
            list(merged_settings.keys()) if merged_settings else [],
            agent_connected,
        )

        try:
            # Engine dispatch: skills with dedicated Python engines bypass
            # the generic LLM tool-use loop (and don't need SKILL.md files)
            if run.skill_name in ENGINE_SKILLS:
                if run.skill_name == "company-intel":
                    output, token_usage, tool_calls = await _execute_company_intel(
                        api_key=api_key,
                        input_text=run.input_text or "",
                        factory=factory,
                        run_id=run.id,
                        tenant_id=run.tenant_id,
                    )
                else:
                    raise ValueError(f"Engine skill '{run.skill_name}' has no engine dispatch")
            else:
                output, token_usage, tool_calls = await _execute_with_tools(
                    api_key=api_key,
                    skill_name=run.skill_name,
                    input_text=run.input_text or "",
                    registry=registry,
                    context=run_context,
                    factory=factory,
                    run_id=run.id,
                    agent_connected=agent_connected,
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

    # Set API key for sync Anthropic client used by structure_intelligence
    original_key = os.environ.get("ANTHROPIC_API_KEY")
    os.environ["ANTHROPIC_API_KEY"] = api_key
    try:
        intelligence = await asyncio.to_thread(
            structure_intelligence, raw_text, "website-crawl"
        )
    finally:
        if original_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = original_key
        else:
            os.environ.pop("ANTHROPIC_API_KEY", None)

    tool_calls.append({"tool": "structure_intelligence", "input": "raw_text", "result_length": len(str(intelligence))})

    if not intelligence.get("structured"):
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

    os.environ["ANTHROPIC_API_KEY"] = api_key
    try:
        enriched = await asyncio.to_thread(
            enrich_with_web_research, company_name, intelligence
        )
    finally:
        if original_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = original_key
        else:
            os.environ.pop("ANTHROPIC_API_KEY", None)

    tool_calls.append({"tool": "enrich_with_web_research", "input": company_name, "result_length": len(str(enriched))})

    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "enriched", "message": "Web research complete"},
    })

    # Stage 4: Write to context store (async, tenant-scoped)
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

    files_written = 0
    for filename, (content_lines, detail) in section_map.items():
        if not content_lines:
            continue

        entry = {
            "detail": detail,
            "confidence": "medium",
            "content": content_lines,
        }

        try:
            async with factory() as session:
                # Set tenant context for RLS
                await session.execute(
                    sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
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
            logger.warning("Context write failed for %s: %s", filename, e)

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

    # Token usage is approximate (sync client doesn't easily return counts)
    token_usage = {"input_tokens": 0, "output_tokens": 0, "model": "claude-sonnet-4-20250514"}

    return "\n".join(output_parts), token_usage, tool_calls


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

    Returns:
        Tuple of (output_text, token_usage_dict, tool_calls_list).
    """
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Build system prompt from SKILL.md
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
