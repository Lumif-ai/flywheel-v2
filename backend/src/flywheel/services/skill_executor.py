"""Skill execution bridge -- async job queue to sync execution_gateway.

Bridges the async job queue worker to the synchronous execution_gateway.
Handles BYOK key decryption, env var management (thread-safe), event
streaming to events_log, cost calculation, and HTML rendering.

Public API:
    execute_run(run) -> None
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
from pathlib import Path
from uuid import UUID

from sqlalchemy import text as sa_text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from flywheel.db.models import ContextEntry, SkillRun, User
from flywheel.db.session import get_session_factory
from sqlalchemy import select

from flywheel.services.circuit_breaker import anthropic_breaker
from flywheel.services.cost_tracker import calculate_cost

logger = logging.getLogger(__name__)

# Thread lock for env var manipulation during execute_skill calls.
# The execution_gateway reads ANTHROPIC_API_KEY from os.environ, so we
# must set it before calling execute_skill and restore it after.
_env_lock = threading.Lock()

# Path to the engines directory (v1 execution gateway location)
_ENGINES_DIR = Path(__file__).resolve().parents[3] / "engines"


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
                    {"id": str(r.id), "file": r.file_name, "source": r.source}
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
            raise ValueError(
                "No API key configured. Please add your Anthropic API key in Settings."
            )

        # Ensure engines directory is on sys.path for execution_gateway imports
        engines_str = str(_ENGINES_DIR)
        if engines_str not in sys.path:
            sys.path.insert(0, engines_str)

        from flywheel.engines.execution_gateway import execute_skill

        # Thread-safe env var manipulation: set BYOK key, execute, restore
        try:
            result = await asyncio.to_thread(
                _execute_with_api_key, api_key, run.skill_name, run.input_text or "", str(run.user_id)
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
        cost = calculate_cost(result.token_usage)

        # Render HTML output
        rendered_html = None
        try:
            from flywheel.engines.output_renderer import render_output
            rendered_html = render_output(
                run.skill_name, result.output, result.context_attribution
            )
        except Exception as e:
            logger.warning("Output rendering failed for %s: %s", run.skill_name, e)

        # Update run record with results
        total_tokens = (
            (result.token_usage or {}).get("input_tokens", 0)
            + (result.token_usage or {}).get("output_tokens", 0)
        )
        async with factory() as session:
            await session.execute(
                update(SkillRun)
                .where(SkillRun.id == run.id)
                .values(
                    status="completed",
                    output=result.output,
                    rendered_html=rendered_html,
                    tokens_used=total_tokens,
                    cost_estimate=cost,
                    duration_ms=duration_ms,
                    attribution=result.context_attribution or {},
                )
            )
            await session.commit()

        # Build attribution from context entries (post-completion, per Pitfall 4)
        try:
            db_attribution = await _build_attribution(
                run.tenant_id, run.user_id, run.skill_name
            )
            if db_attribution.get("entry_count", 0) > 0:
                # Merge DB attribution with any gateway-provided attribution
                merged = {**(result.context_attribution or {}), **db_attribution}
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
                SET events_log = events_log || :event::jsonb
                WHERE id = :run_id
            """),
            {"run_id": str(run_id), "event": json.dumps([event_dict])},
        )
        await session.commit()
