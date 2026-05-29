"""Create skill_assets table — Supabase PgBouncer workaround.

Each DDL statement runs as its own committed transaction because
PgBouncer's transaction-level pooling silently rolls back multi-
statement DDL transactions while committing the alembic_version bump.

Phase 146 — v22.0 Skill Platform Consolidation.

Usage:
    cd backend && uv run python scripts/apply_064_skill_assets_table.py
"""

import asyncio

from sqlalchemy import text

from flywheel.db.session import get_session_factory


STATEMENTS: list[str] = [
    # Defensive: ensure pgcrypto is available for gen_random_uuid().
    # Supabase has it pre-enabled (41 in-repo gen_random_uuid() uses,
    # zero explicit CREATE EXTENSION statements), but local Docker
    # Postgres (port 5434) may not — IF NOT EXISTS makes it a no-op.
    "CREATE EXTENSION IF NOT EXISTS pgcrypto",
    """
    CREATE TABLE IF NOT EXISTS skill_assets (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        skill_id          UUID NOT NULL REFERENCES skill_definitions(id) ON DELETE CASCADE,
        bundle            BYTEA NOT NULL,
        bundle_sha256     TEXT NOT NULL,
        bundle_size_bytes INTEGER NOT NULL CHECK (bundle_size_bytes >= 0),
        bundle_format     TEXT NOT NULL DEFAULT 'zip',
        created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_skill_assets_skill_id ON skill_assets (skill_id)",
    "CREATE INDEX IF NOT EXISTS idx_skill_assets_bundle_sha256 ON skill_assets (bundle_sha256)",
]


async def run_migration() -> None:
    factory = get_session_factory()

    # 1) Pre-verify: does the table already exist?
    async with factory() as session:
        before = (
            await session.execute(text("SELECT to_regclass('public.skill_assets')"))
        ).scalar()
        print(f"Before: skill_assets exists? -> {before}")

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
            await session.execute(text("SELECT COUNT(*) FROM skill_assets"))
        ).scalar()
        print(f"After: SELECT COUNT(*) FROM skill_assets = {count}")

        indexes = (
            await session.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'skill_assets' ORDER BY indexname"
                )
            )
        ).scalars().all()
        print(f"After: indexes on skill_assets = {indexes}")

    # 4) Stamp alembic — EXACT string match to migration file's `revision`
    async with factory() as session:
        await session.execute(
            text("UPDATE alembic_version SET version_num = '064_skill_assets_table'")
        )
        await session.commit()
    print("Alembic stamped to 064_skill_assets_table")


if __name__ == "__main__":
    asyncio.run(run_migration())
