"""Broker Schema Modifications 03 — Coverage taxonomy table, market context, constraint fixes.

Execution order:
  1. Pre-flight check (alembic version)
  2. CREATE TABLE coverage_types (reference taxonomy)
  3. CREATE indexes on coverage_types (GIN for arrays, B-tree for category)
  4. ADD COLUMN country_code, line_of_business to broker_projects
  5. ADD COLUMN coverage_type_key to project_coverages
  6. Backfill coverage_type_key from existing coverage_type
  7. Fix gap_status CHECK constraint (drop old, backfill values, add new)
  8. Fix category default on project_coverages
  9. Stamp alembic to 062_broker_schema_mods_03

Each DDL statement runs as its own committed transaction to avoid PgBouncer
silently rolling back multi-statement DDL.

Usage:
    cd backend && uv run python scripts/broker_schema_mods_03.py
"""

import asyncio

from sqlalchemy import text

from flywheel.db.session import get_session_factory


# ---------------------------------------------------------------------------
# DDL statements — each runs in its own session/commit
# ---------------------------------------------------------------------------

DDL_STEPS: list[tuple[str, str]] = [
    # 1. Create coverage_types table
    (
        "Create coverage_types table",
        """CREATE TABLE IF NOT EXISTS coverage_types (
            key TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            display_names JSONB NOT NULL DEFAULT '{}'::jsonb,
            aliases JSONB NOT NULL DEFAULT '{}'::jsonb,
            countries TEXT[] NOT NULL DEFAULT '{}'::text[],
            lines_of_business TEXT[] NOT NULL DEFAULT '{}'::text[],
            is_active BOOLEAN NOT NULL DEFAULT true,
            is_verified BOOLEAN NOT NULL DEFAULT true,
            added_by TEXT NOT NULL DEFAULT 'seed',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""",
    ),
    # 2. GIN index on countries
    (
        "Create GIN index on coverage_types.countries",
        "CREATE INDEX IF NOT EXISTS idx_coverage_types_countries ON coverage_types USING GIN (countries)",
    ),
    # 3. GIN index on lines_of_business
    (
        "Create GIN index on coverage_types.lines_of_business",
        "CREATE INDEX IF NOT EXISTS idx_coverage_types_lob ON coverage_types USING GIN (lines_of_business)",
    ),
    # 4. B-tree index on category
    (
        "Create index on coverage_types.category",
        "CREATE INDEX IF NOT EXISTS idx_coverage_types_category ON coverage_types (category)",
    ),
    # 5. Add country_code to broker_projects
    (
        "Add country_code to broker_projects",
        "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS country_code TEXT NOT NULL DEFAULT 'MX'",
    ),
    # 6. Add line_of_business to broker_projects
    (
        "Add line_of_business to broker_projects",
        "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS line_of_business TEXT NOT NULL DEFAULT 'construction'",
    ),
    # 7. Add coverage_type_key to project_coverages
    (
        "Add coverage_type_key to project_coverages",
        "ALTER TABLE project_coverages ADD COLUMN IF NOT EXISTS coverage_type_key TEXT",
    ),
    # 8. Backfill coverage_type_key from coverage_type
    (
        "Backfill coverage_type_key from coverage_type",
        "UPDATE project_coverages SET coverage_type_key = coverage_type WHERE coverage_type_key IS NULL",
    ),
    # 9. Map auto_liability -> auto
    (
        "Backfill coverage_type_key: auto_liability -> auto",
        "UPDATE project_coverages SET coverage_type_key = 'auto' WHERE coverage_type_key = 'auto_liability'",
    ),
    # 10. Map professional_indemnity -> professional_liability
    (
        "Backfill coverage_type_key: professional_indemnity -> professional_liability",
        "UPDATE project_coverages SET coverage_type_key = 'professional_liability' WHERE coverage_type_key = 'professional_indemnity'",
    ),
    # 11. Drop old gap_status constraint BEFORE backfilling new values
    (
        "Drop old gap_status CHECK constraint",
        "ALTER TABLE project_coverages DROP CONSTRAINT IF EXISTS chk_project_coverages_gap_status",
    ),
    # 12. Backfill gap_status: gap -> missing
    (
        "Backfill gap_status: gap -> missing",
        "UPDATE project_coverages SET gap_status = 'missing' WHERE gap_status = 'gap'",
    ),
    # 13. Backfill gap_status: partial -> insufficient
    (
        "Backfill gap_status: partial -> insufficient",
        "UPDATE project_coverages SET gap_status = 'insufficient' WHERE gap_status = 'partial'",
    ),
    # 14. Add new gap_status CHECK constraint
    (
        "Add new gap_status CHECK constraint",
        """ALTER TABLE project_coverages ADD CONSTRAINT chk_project_coverages_gap_status
           CHECK (gap_status IN ('covered', 'missing', 'insufficient', 'unknown'))""",
    ),
    # 15. Fix category default to 'liability'
    (
        "Fix category default to 'liability'",
        "ALTER TABLE project_coverages ALTER COLUMN category SET DEFAULT 'liability'",
    ),
]


# ---------------------------------------------------------------------------
# Pre-flight check
# ---------------------------------------------------------------------------

async def preflight(factory) -> None:
    """Verify alembic version before running mutations."""
    async with factory() as session:
        r = await session.execute(text("SELECT version_num FROM alembic_version"))
        version = r.scalar()
        if version != "061_broker_schema_mods_02":
            raise RuntimeError(
                f"Expected alembic 061_broker_schema_mods_02, got: {version}. "
                "Run broker_schema_mods_02.py first."
            )
    print("Pre-flight check passed.")


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

async def run_migration() -> None:
    factory = get_session_factory()

    # 1. Pre-flight
    await preflight(factory)

    # 2. Execute each DDL step in its own committed transaction
    for label, stmt in DDL_STEPS:
        async with factory() as session:
            await session.execute(text(stmt))
            await session.commit()
        print(f"OK: {label}")

    # 3. Stamp alembic
    async with factory() as session:
        await session.execute(
            text("UPDATE alembic_version SET version_num = '062_broker_schema_mods_03'")
        )
        await session.commit()
    print("Alembic stamped to 062_broker_schema_mods_03")
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(run_migration())
