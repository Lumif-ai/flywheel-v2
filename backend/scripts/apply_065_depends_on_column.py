"""Add depends_on ARRAY(Text) column to skill_definitions — Supabase PgBouncer workaround.

Each DDL statement runs as its own committed transaction because
PgBouncer's transaction-level pooling silently rolls back multi-
statement DDL transactions while committing the alembic_version bump.

Phase 150 Plan 01 — v22.0 Skill Platform Consolidation.

Usage:
    cd backend && uv run python scripts/apply_065_depends_on_column.py

The column is ARRAY(Text) (NOT JSONB) — avoids the "never .append on a
JSONB-bound list" SQLAlchemy mutation gotcha (saved user memory); also
matches the existing shape of SkillDefinition.tags / contract_reads /
contract_writes so readers don't context-switch on list representation.

DEFAULT '{}'::text[] ensures existing rows carry an empty array on
backfill, so NOT NULL is safe to declare in the same statement.
"""

import asyncio

from sqlalchemy import text

from flywheel.db.session import get_session_factory


STATEMENTS: list[str] = [
    "ALTER TABLE skill_definitions "
    "ADD COLUMN IF NOT EXISTS depends_on TEXT[] NOT NULL DEFAULT '{}'::text[]",
]


async def run_migration() -> None:
    factory = get_session_factory()

    # 1) Pre-verify: does the column already exist?
    async with factory() as session:
        before = (
            await session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='skill_definitions' AND column_name='depends_on'"
                )
            )
        ).scalar()
        print(f"Before: skill_definitions.depends_on exists? -> {before}")

    # 2) Apply each statement in its own transaction
    for stmt in STATEMENTS:
        async with factory() as session:
            await session.execute(text(stmt))
            await session.commit()
        compact = " ".join(stmt.split())[:100]
        print(f"OK: {compact}{'...' if len(compact) == 100 else ''}")

    # 3) Post-verify: column exists; existing rows default to empty array
    async with factory() as session:
        after = (
            await session.execute(
                text(
                    "SELECT column_name, data_type, udt_name, is_nullable, column_default "
                    "FROM information_schema.columns "
                    "WHERE table_name='skill_definitions' AND column_name='depends_on'"
                )
            )
        ).first()
        print(f"After: skill_definitions.depends_on metadata = {after}")

        null_count = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM skill_definitions WHERE depends_on IS NULL"
                )
            )
        ).scalar()
        print(f"After: rows with NULL depends_on = {null_count} (should be 0)")

    # 4) Stamp alembic — EXACT string match to migration file's `revision`
    async with factory() as session:
        await session.execute(
            text("UPDATE alembic_version SET version_num = '065_depends_on_column'")
        )
        await session.commit()
    print("Alembic stamped to 065_depends_on_column")


if __name__ == "__main__":
    asyncio.run(run_migration())
