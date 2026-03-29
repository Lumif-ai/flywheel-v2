"""Flywheel ritual engine -- Stages 1-4: Granola sync, meeting processing, meeting prep, task execution.

The core orchestrator that sequences sync, process, prep, and execute stages.
Stage 5 (HTML brief) is added in Plan 04.

Public API:
    execute_flywheel_ritual(factory, run_id, tenant_id, user_id, api_key)
        -> tuple[str, dict, list]
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from uuid import UUID

import anthropic
from sqlalchemy import func, or_, select, update
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flywheel.db.models import Meeting, SkillRun, Task
from flywheel.services.meeting_sync import sync_granola_meetings
from flywheel.services.skill_executor import (
    _append_event_atomic,
    _execute_account_meeting_prep,
    _execute_meeting_prep,
    _execute_meeting_processor,
    _execute_with_tools,
    _load_skill_from_db,
    preload_tenant_context,
)

logger = logging.getLogger("flywheel.engines.flywheel_ritual")


async def execute_flywheel_ritual(
    factory: async_sessionmaker,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None,
    api_key: str | None = None,
) -> tuple[str, dict, list]:
    """Orchestrate the flywheel ritual: sync, process, prep.

    Returns (html_output, token_usage, tool_calls) matching the standard
    engine signature used by skill_executor dispatch.
    """
    total_token_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
    all_tool_calls: list = []

    # Collect outputs for brief (Plan 04 will use these)
    stage_results: dict = {
        "sync": None,
        "processed": [],
        "prepped": [],
        "tasks": [],  # Stage 4 in Plan 03
    }

    # --- Stage 1: Granola Sync ---
    await _stage_1_sync(factory, run_id, tenant_id, user_id, stage_results)

    # --- Stage 2: Process Unprocessed Meetings ---
    await _stage_2_process(
        factory, run_id, tenant_id, user_id, api_key,
        total_token_usage, all_tool_calls, stage_results,
    )

    # --- Stage 3: Prep Today's Meetings ---
    await _stage_3_prep(
        factory, run_id, tenant_id, user_id, api_key,
        total_token_usage, all_tool_calls, stage_results,
    )

    # --- Stage 4: Execute Pending Tasks (ORCH-12) ---
    await _stage_4_execute(
        factory, run_id, tenant_id, user_id, api_key,
        total_token_usage, all_tool_calls, stage_results,
    )

    # --- Stage 5: Compose HTML Brief (Plan 04 adds this) ---
    # For now, return a placeholder
    html_output = "<div>Flywheel ritual complete. HTML brief coming in Plan 04.</div>"

    return html_output, total_token_usage, all_tool_calls


# ---------------------------------------------------------------------------
# Stage 1 -- Granola Sync (ORCH-03)
# ---------------------------------------------------------------------------


async def _stage_1_sync(
    factory: async_sessionmaker,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None,
    stage_results: dict,
) -> None:
    """Sync meetings from Granola. Non-fatal on failure."""
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "syncing", "message": "Syncing from Granola..."},
    })

    try:
        sync_stats = await sync_granola_meetings(factory, tenant_id, user_id)
        stage_results["sync"] = sync_stats
        await _append_event_atomic(factory, run_id, {
            "event": "stage",
            "data": {
                "stage": "syncing",
                "message": (
                    f"Synced {sync_stats['synced']} new meetings "
                    f"({sync_stats['skipped']} skipped, "
                    f"{sync_stats['already_seen']} already seen)"
                ),
            },
        })
    except Exception as e:
        # No Granola integration or API failure -- NOT fatal, continue to Stage 2
        logger.warning("Stage 1 sync failed: %s", e)
        stage_results["sync"] = {
            "synced": 0, "skipped": 0, "already_seen": 0, "error": str(e),
        }
        await _append_event_atomic(factory, run_id, {
            "event": "stage",
            "data": {"stage": "syncing", "message": f"Sync skipped: {e}"},
        })


# ---------------------------------------------------------------------------
# Stage 2 -- Process Unprocessed Meetings (ORCH-04)
# ---------------------------------------------------------------------------


async def _stage_2_process(
    factory: async_sessionmaker,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None,
    api_key: str | None,
    total_token_usage: dict,
    all_tool_calls: list,
    stage_results: dict,
) -> None:
    """Process ALL meetings with unprocessed status (no caps)."""
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "processing", "message": "Checking for unprocessed meetings..."},
    })

    # Query ALL meetings with unprocessed status (no caps per spec)
    async with factory() as session:
        await _set_rls_context(session, tenant_id, user_id)
        result = await session.execute(
            select(Meeting).where(
                Meeting.tenant_id == tenant_id,
                Meeting.processing_status.in_(["pending", "recorded"]),
            ).order_by(Meeting.meeting_date.desc())
        )
        unprocessed = result.scalars().all()

    total_to_process = len(unprocessed)
    processed_count = 0
    process_failures = 0

    for meeting in unprocessed:
        try:
            await _append_event_atomic(factory, run_id, {
                "event": "stage",
                "data": {
                    "stage": "processing",
                    "message": f"Processing: {meeting.title}...",
                },
            })
            output, usage, calls = await _execute_meeting_processor(
                factory=factory,
                run_id=run_id,
                tenant_id=tenant_id,
                user_id=user_id,
                meeting_id=meeting.id,
                api_key=api_key,
            )
            _accumulate_usage(total_token_usage, usage)
            all_tool_calls.extend(calls or [])
            processed_count += 1
            stage_results["processed"].append({
                "meeting_id": str(meeting.id),
                "title": meeting.title,
                "output": output,
                "success": True,
            })
        except Exception as e:
            logger.error(
                "Stage 2 failed for meeting %s (%s): %s",
                meeting.id, meeting.title, e,
            )
            process_failures += 1
            stage_results["processed"].append({
                "meeting_id": str(meeting.id),
                "title": meeting.title,
                "error": str(e),
                "success": False,
            })
            await _append_event_atomic(factory, run_id, {
                "event": "stage",
                "data": {
                    "stage": "processing",
                    "message": f"Failed: {meeting.title} -- {e}",
                },
            })

    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {
            "stage": "processing",
            "message": (
                f"Processed {processed_count}/{total_to_process} meetings. "
                f"{process_failures} failed."
            ),
        },
    })


# ---------------------------------------------------------------------------
# Stage 3 -- Prep Today's Meetings (ORCH-05)
# ---------------------------------------------------------------------------


async def _stage_3_prep(
    factory: async_sessionmaker,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None,
    api_key: str | None,
    total_token_usage: dict,
    all_tool_calls: list,
    stage_results: dict,
) -> None:
    """Prep ALL today's unprepped external meetings."""
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "prepping", "message": "Checking today's meetings for prep..."},
    })

    # Query today's meetings (external only -- NULL meeting_type treated as external)
    today = date.today()
    async with factory() as session:
        await _set_rls_context(session, tenant_id, user_id)
        result = await session.execute(
            select(Meeting).where(
                Meeting.tenant_id == tenant_id,
                func.date(Meeting.meeting_date) == today,
                or_(
                    Meeting.meeting_type != "internal",
                    Meeting.meeting_type.is_(None),
                ),
            )
        )
        todays_meetings = result.scalars().all()

    # Determine which meetings still need prep
    unprepped = await _filter_unprepped(factory, tenant_id, todays_meetings)

    total_to_prep = len(unprepped)
    prepped_count = 0
    prep_failures = 0

    for meeting in unprepped:
        try:
            await _append_event_atomic(factory, run_id, {
                "event": "stage",
                "data": {
                    "stage": "prepping",
                    "message": f"Preparing brief for: {meeting.title}...",
                },
            })

            if meeting.account_id:
                # Account-scoped prep
                output, usage, calls = await _execute_account_meeting_prep(
                    api_key=api_key,
                    input_text=f"Account-ID:{meeting.account_id}",
                    factory=factory,
                    run_id=run_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            else:
                # Standard prep -- construct input_text per ORCH-05
                attendee_names = []
                if meeting.attendees:
                    for a in (meeting.attendees if isinstance(meeting.attendees, list) else []):
                        name = a.get("name") or a.get("email", "Unknown")
                        attendee_names.append(name)
                input_text = (
                    f"Meeting: {meeting.title}\n"
                    f"Date: {meeting.meeting_date}\n"
                    f"Attendees: {', '.join(attendee_names) if attendee_names else 'Unknown'}\n"
                    f"Type: {meeting.meeting_type or 'discovery'}"
                )
                output, usage, calls = await _execute_meeting_prep(
                    api_key=api_key,
                    input_text=input_text,
                    factory=factory,
                    run_id=run_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )

            _accumulate_usage(total_token_usage, usage)
            all_tool_calls.extend(calls or [])
            prepped_count += 1
            stage_results["prepped"].append({
                "meeting_id": str(meeting.id),
                "title": meeting.title,
                "account_id": str(meeting.account_id) if meeting.account_id else None,
                "output": output,
                "success": True,
            })
        except Exception as e:
            logger.error(
                "Stage 3 prep failed for meeting %s (%s): %s",
                meeting.id, meeting.title, e,
            )
            prep_failures += 1
            stage_results["prepped"].append({
                "meeting_id": str(meeting.id),
                "title": meeting.title,
                "error": str(e),
                "success": False,
            })
            await _append_event_atomic(factory, run_id, {
                "event": "stage",
                "data": {
                    "stage": "prepping",
                    "message": f"Prep failed: {meeting.title} -- {e}",
                },
            })

    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {
            "stage": "prepping",
            "message": f"Prepared {prepped_count}/{total_to_prep} meeting briefs.",
        },
    })


# ---------------------------------------------------------------------------
# Stage 4 -- Execute Pending Tasks (ORCH-12)
# ---------------------------------------------------------------------------


async def _stage_4_execute(
    factory: async_sessionmaker,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None,
    api_key: str | None,
    total_token_usage: dict,
    all_tool_calls: list,
    stage_results: dict,
) -> None:
    """Execute confirmed tasks that have a suggested_skill.

    For each task: gather context, formulate input via LLM (Haiku),
    invoke the target skill, store the deliverable, and transition
    the task to ``in_review``.  Individual failures are logged and
    skipped -- they never block other tasks.
    """
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "executing", "message": "Checking for confirmed tasks..."},
    })

    # Query confirmed tasks with a suggested skill
    async with factory() as session:
        await _set_rls_context(session, tenant_id, user_id)
        result = await session.execute(
            select(Task).where(
                Task.tenant_id == tenant_id,
                Task.user_id == user_id,
                Task.status == "confirmed",
                Task.suggested_skill.isnot(None),
            )
        )
        executable_tasks = result.scalars().all()

    total_tasks = len(executable_tasks)
    executed_count = 0
    task_failures = 0

    for task in executable_tasks:
        try:
            await _append_event_atomic(factory, run_id, {
                "event": "stage",
                "data": {
                    "stage": "executing",
                    "message": f"Executing task: {task.title} via {task.suggested_skill}...",
                },
            })

            # Step 1: Gather context for input formulation
            context_parts: list[str] = []
            context_parts.append(f"Task: {task.title}")
            if task.description:
                context_parts.append(f"Description: {task.description}")
            if task.skill_context:
                # skill_context is JSONB with additional context from extraction
                context_parts.append(f"Context: {json.dumps(task.skill_context)}")

            # Load tenant context (all context entries for the tenant)
            if task.account_id:
                try:
                    tenant_context = await preload_tenant_context(factory, tenant_id)
                    if tenant_context:
                        context_parts.append(f"Account Intelligence:\n{tenant_context}")
                except Exception as ctx_err:
                    logger.warning(
                        "Failed to load tenant context for task %s: %s",
                        task.id, ctx_err,
                    )

            # Load meeting summary if task has meeting_id
            if task.meeting_id:
                try:
                    async with factory() as session:
                        await _set_rls_context(session, tenant_id, user_id)
                        mtg_result = await session.execute(
                            select(Meeting.title, Meeting.ai_summary).where(
                                Meeting.id == task.meeting_id,
                            )
                        )
                        mtg_row = mtg_result.first()
                        if mtg_row:
                            context_parts.append(f"Meeting: {mtg_row.title}")
                            if mtg_row.ai_summary:
                                context_parts.append(
                                    f"Meeting Summary: {mtg_row.ai_summary}"
                                )
                except Exception as mtg_err:
                    logger.warning(
                        "Failed to load meeting context for task %s: %s",
                        task.id, mtg_err,
                    )

            # Step 2: Formulate input_text using LLM (Haiku -- cheap and fast)
            formulation_prompt = (
                f"You are formulating the input for the '{task.suggested_skill}' skill.\n\n"
                f"Based on the following task and context, write a clear, actionable input "
                f"that the skill can use to produce a high-quality deliverable.\n\n"
                + "\n".join(context_parts)
                + "\n\n"
                f"Write the input_text for the '{task.suggested_skill}' skill. "
                f"Be specific, include relevant names, dates, and context. "
                f"Return ONLY the input text, no explanation."
            )

            client = anthropic.AsyncAnthropic(api_key=api_key)
            formulation_response = await client.messages.create(
                model="claude-haiku-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": formulation_prompt}],
            )
            formulated_input = formulation_response.content[0].text
            total_token_usage["input_tokens"] += formulation_response.usage.input_tokens
            total_token_usage["output_tokens"] += formulation_response.usage.output_tokens

            # Step 3: Invoke the target skill
            if task.suggested_skill == "meeting-prep" and task.account_id:
                output, usage, calls = await _execute_account_meeting_prep(
                    api_key=api_key,
                    input_text=f"Account-ID:{task.account_id}",
                    factory=factory,
                    run_id=run_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            elif task.suggested_skill == "meeting-prep":
                output, usage, calls = await _execute_meeting_prep(
                    api_key=api_key,
                    input_text=formulated_input,
                    factory=factory,
                    run_id=run_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            else:
                # Generic skill invocation via _execute_with_tools
                from flywheel.tools import create_registry
                from flywheel.tools.budget import RunBudget
                from flywheel.tools.registry import RunContext

                registry = create_registry()
                run_context = RunContext(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    run_id=run_id,
                    budget=RunBudget(),
                    session_factory=factory,
                    focus_id=None,
                )
                skill_meta = await _load_skill_from_db(factory, task.suggested_skill)
                system_prompt = skill_meta["system_prompt"] if skill_meta else None

                if system_prompt is None:
                    logger.warning(
                        "Skill '%s' not found in DB, skipping task %s",
                        task.suggested_skill, task.id,
                    )
                    raise ValueError(
                        f"Skill '{task.suggested_skill}' not found in skill_definitions"
                    )

                output, usage, calls = await _execute_with_tools(
                    api_key=api_key,
                    skill_name=task.suggested_skill,
                    input_text=formulated_input,
                    registry=registry,
                    context=run_context,
                    factory=factory,
                    run_id=run_id,
                    agent_connected=False,
                    system_prompt_override=system_prompt,
                )

            _accumulate_usage(total_token_usage, usage)
            all_tool_calls.extend(calls or [])

            # Step 4: Update task status -- confirmed -> in_review (per spec ORCH-12)
            async with factory() as session:
                await _set_rls_context(session, tenant_id, user_id)
                await session.execute(
                    update(Task).where(Task.id == task.id).values(
                        status="in_review",
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

            executed_count += 1
            stage_results["tasks"].append({
                "task_id": str(task.id),
                "title": task.title,
                "suggested_skill": task.suggested_skill,
                "output": output,
                "trust_level": task.trust_level,
                "success": True,
            })
        except Exception as e:
            logger.error(
                "Stage 4 failed for task %s (%s): %s", task.id, task.title, e,
            )
            task_failures += 1
            stage_results["tasks"].append({
                "task_id": str(task.id),
                "title": task.title,
                "suggested_skill": task.suggested_skill,
                "error": str(e),
                "success": False,
            })
            await _append_event_atomic(factory, run_id, {
                "event": "stage",
                "data": {
                    "stage": "executing",
                    "message": f"Task failed: {task.title} -- {e}",
                },
            })

    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {
            "stage": "executing",
            "message": (
                f"Executed {executed_count}/{total_tasks} tasks. "
                f"{task_failures} failed."
            ),
        },
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _set_rls_context(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID | None,
) -> None:
    """Set RLS context variables for a session."""
    await session.execute(
        sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    if user_id:
        await session.execute(
            sa_text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )


async def _filter_unprepped(
    factory: async_sessionmaker,
    tenant_id: UUID,
    meetings: list,
) -> list:
    """Return meetings that do NOT already have a completed meeting-prep run.

    IMPORTANT: If meeting.title is None/empty, skip the skill_runs query
    and treat as unprepped. ``contains("")`` would match ALL completed preps,
    causing every meeting to appear "already prepped".
    """
    unprepped = []
    for meeting in meetings:
        if not meeting.title:
            # No title -- can't match against skill_runs, treat as unprepped
            unprepped.append(meeting)
            continue

        async with factory() as session:
            await _set_rls_context(session, tenant_id, None)
            existing_prep = await session.execute(
                select(SkillRun.id).where(
                    SkillRun.tenant_id == tenant_id,
                    SkillRun.skill_name.in_(["meeting-prep"]),
                    SkillRun.status == "completed",
                    SkillRun.input_text.contains(meeting.title),
                ).limit(1)
            )
            if existing_prep.scalar_one_or_none() is None:
                unprepped.append(meeting)

    return unprepped


def _accumulate_usage(total: dict, usage: dict | None) -> None:
    """Add sub-engine token usage into running totals."""
    if not usage:
        return
    total["input_tokens"] += usage.get("input_tokens", 0)
    total["output_tokens"] += usage.get("output_tokens", 0)
