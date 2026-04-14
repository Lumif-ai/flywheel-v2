"""Broker Schema Modifications 01 — additive column additions.

Adds new nullable columns to 5 existing broker tables:
  - broker_projects: client_id (FK), context_entity_id, created_by_user_id, updated_by_user_id
  - carrier_configs:  context_entity_id, created_by_user_id, updated_by_user_id
  - carrier_quotes:   created_by_user_id, updated_by_user_id
  - project_coverages: updated_at, created_by_user_id, updated_by_user_id
  - submission_documents: updated_at, created_by_user_id

Each DDL statement runs as its own committed transaction to avoid
PgBouncer silently rolling back multi-statement DDL.

After all statements succeed the script stamps alembic to 060_broker_schema_mods_01
via SQLAlchemy UPDATE (alembic CLI targets port 5434 which is unavailable locally).

Usage:
    cd backend && uv run python scripts/broker_schema_mods_01.py
"""

import asyncio
from typing import Union

from sqlalchemy import text

from flywheel.db.session import get_session_factory

# All ADD COLUMN statements use IF NOT EXISTS for idempotency.
# One statement per list element — no compound ALTER TABLE with commas.
STATEMENTS: list[str] = [
    # -------------------------------------------------------------------------
    # broker_projects additions (MOD-01)
    # -------------------------------------------------------------------------
    "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS client_id UUID REFERENCES broker_clients(id) ON DELETE SET NULL",
    "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS context_entity_id UUID",
    "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS created_by_user_id UUID",
    "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS updated_by_user_id UUID",

    # -------------------------------------------------------------------------
    # carrier_configs additions (MOD-03)
    # -------------------------------------------------------------------------
    "ALTER TABLE carrier_configs ADD COLUMN IF NOT EXISTS context_entity_id UUID",
    "ALTER TABLE carrier_configs ADD COLUMN IF NOT EXISTS created_by_user_id UUID",
    "ALTER TABLE carrier_configs ADD COLUMN IF NOT EXISTS updated_by_user_id UUID",

    # -------------------------------------------------------------------------
    # carrier_quotes additions (MOD-02)
    # -------------------------------------------------------------------------
    "ALTER TABLE carrier_quotes ADD COLUMN IF NOT EXISTS created_by_user_id UUID",
    "ALTER TABLE carrier_quotes ADD COLUMN IF NOT EXISTS updated_by_user_id UUID",

    # -------------------------------------------------------------------------
    # project_coverages additions (MOD-04)
    # -------------------------------------------------------------------------
    "ALTER TABLE project_coverages ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()",
    "ALTER TABLE project_coverages ADD COLUMN IF NOT EXISTS created_by_user_id UUID",
    "ALTER TABLE project_coverages ADD COLUMN IF NOT EXISTS updated_by_user_id UUID",

    # -------------------------------------------------------------------------
    # submission_documents additions (MOD-05)
    # -------------------------------------------------------------------------
    "ALTER TABLE submission_documents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()",
    "ALTER TABLE submission_documents ADD COLUMN IF NOT EXISTS created_by_user_id UUID",
]


async def run_migration() -> None:
    factory = get_session_factory()

    for stmt in STATEMENTS:
        async with factory() as session:
            await session.execute(text(stmt))
            await session.commit()
        print(f"OK: {stmt[:80]}...")

    # Stamp alembic via SQLAlchemy UPDATE (alembic CLI targets unavailable port 5434)
    async with factory() as session:
        await session.execute(
            text("UPDATE alembic_version SET version_num = '060_broker_schema_mods_01'")
        )
        await session.commit()
    print("Alembic stamped to 060_broker_schema_mods_01")


if __name__ == "__main__":
    asyncio.run(run_migration())
