"""Flip skill_definitions.protected default to false and bulk-update rows.

Phase 95 set protected=true fail-closed, which trapped every skill on the
server-side BYOK execution path. Platform architecture says: backend makes
NO LLM calls when CC is the caller. Flipping restores "CC as brain".

Each statement runs as its own committed transaction (Supabase PgBouncer
silently rolls back multi-statement DDL otherwise).

Usage:
    cd backend && uv run python scripts/apply_062_skill_protected_default.py
"""

import asyncio

from sqlalchemy import text

from flywheel.db.session import get_session_factory


async def run_migration() -> None:
    factory = get_session_factory()

    # 1) Show current state before touching anything
    async with factory() as session:
        before = (await session.execute(
            text("SELECT protected, COUNT(*) FROM skill_definitions GROUP BY protected")
        )).all()
        print(f"Before: {before}")

    # 2) Flip default
    async with factory() as session:
        await session.execute(
            text("ALTER TABLE skill_definitions ALTER COLUMN protected SET DEFAULT false")
        )
        await session.commit()
    print("OK: default flipped to false")

    # 3) Bulk update existing rows
    async with factory() as session:
        result = await session.execute(
            text("UPDATE skill_definitions SET protected = false WHERE protected = true")
        )
        await session.commit()
        print(f"OK: updated rows={result.rowcount}")

    # 4) Verify
    async with factory() as session:
        after = (await session.execute(
            text("SELECT protected, COUNT(*) FROM skill_definitions GROUP BY protected")
        )).all()
        print(f"After: {after}")

    # 5) Stamp alembic
    async with factory() as session:
        await session.execute(
            text("UPDATE alembic_version SET version_num = '062_skill_protected_default_false'")
        )
        await session.commit()
    print("Alembic stamped to 062_skill_protected_default_false")


if __name__ == "__main__":
    asyncio.run(run_migration())
