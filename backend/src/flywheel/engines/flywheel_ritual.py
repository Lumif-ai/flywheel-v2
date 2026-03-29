"""Flywheel ritual engine -- Stages 1-3: Granola sync, meeting processing, meeting prep.

The core orchestrator that sequences sync, process, and prep stages.
Stage 4 (task execution) and Stage 5 (HTML brief) are added in Plans 03 and 04.

Public API:
    execute_flywheel_ritual(factory, run_id, tenant_id, user_id, api_key)
        -> tuple[str, dict, list]
"""

from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flywheel.db.models import Meeting, SkillRun
from flywheel.services.meeting_sync import sync_granola_meetings
from flywheel.services.skill_executor import (
    _append_event_atomic,
    _execute_account_meeting_prep,
    _execute_meeting_prep,
    _execute_meeting_processor,
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

    # --- Stage 4: Task Execution (Plan 03 adds this) ---

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
