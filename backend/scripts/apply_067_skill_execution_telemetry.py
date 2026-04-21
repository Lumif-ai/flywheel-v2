"""Create skill_execution_telemetry table — Supabase PgBouncer workaround.

Each DDL statement runs as its own committed transaction because
PgBouncer's transaction-level pooling silently rolls back multi-
statement DDL transactions while committing the alembic_version bump.

Phase 156 — v23.0 In-Context Skill Execution (Telemetry + Migration Cutover).

Usage:
    cd backend && uv run python scripts/apply_067_skill_execution_telemetry.py
"""

import asyncio

from sqlalchemy import text

from flywheel.db.session import get_session_factory


STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS skill_execution_telemetry (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL REFERENCES tenants(id),
        skill_name TEXT NOT NULL,
        execution_path TEXT NOT NULL,
        caller_type TEXT NOT NULL DEFAULT 'mcp',
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_skill_telemetry_created_skill
        ON skill_execution_telemetry (created_at, skill_name)
    """,
]


async def run_migration() -> None:
    factory = get_session_factory()

    # 1) Pre-verify: does the table already exist?
    async with factory() as session:
        before = (
            await session.execute(
                text("SELECT to_regclass('public.skill_execution_telemetry')")
            )
        ).scalar()
        print(f"Before: skill_execution_telemetry exists? -> {before}")

    # 2) Apply each statement in its own transaction
    for stmt in STATEMENTS:
        async with factory() as session:
            await session.execute(text(stmt))
            await session.commit()
        # Collapse whitespace for readable log lines
        compact = " ".join(stmt.split())[:100]
        print(f"OK: {compact}{'...' if len(compact) == 100 else ''}")

    # 3) Post-verify: table exists, count is 0 (or preserved if re-run)
    async with factory() as session:
        count = (
            await session.execute(
                text("SELECT COUNT(*) FROM skill_execution_telemetry")
            )
        ).scalar()
        print(f"After: SELECT COUNT(*) FROM skill_execution_telemetry = {count}")

        indexes = (
            await session.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'skill_execution_telemetry' ORDER BY indexname"
                )
            )
        ).scalars().all()
        print(f"After: indexes on skill_execution_telemetry = {indexes}")

    # 4) Stamp alembic — EXACT string match to migration file's `revision`
    async with factory() as session:
        await session.execute(
            text(
                "UPDATE alembic_version SET version_num = '067_skill_execution_telemetry'"
            )
        )
        await session.commit()
    print("Alembic stamped to 067_skill_execution_telemetry")


if __name__ == "__main__":
    asyncio.run(run_migration())
