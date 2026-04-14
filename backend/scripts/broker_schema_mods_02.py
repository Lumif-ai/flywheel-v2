"""Broker Schema Modifications 02 — seed, constraints, and destructive drops.

Execution order (critical — do not reorder):
  1. Pre-flight checks (alembic version, bad analysis_status values, orphaned document_ids)
  2. Seed carrier_configs.email_address -> carrier_contacts (role='submissions', is_primary=true)
  3. Verify seed (abort if dest count < source count — data loss prevention gate)
  4. CHECK constraints on broker_projects, carrier_quotes, project_coverages, broker_activities
  5. broker_activities FK on document_id (NOT VALID then VALIDATE — VALIDATE is non-fatal)
  6. Drop obsolete columns from broker_projects (7), carrier_quotes (6), carrier_configs (2)
     NOTE: carrier_configs.email_address dropped LAST to preserve seed source data until verified
  7. Stamp alembic to 061_broker_schema_mods_02

Each DDL statement runs as its own committed transaction to avoid PgBouncer
silently rolling back multi-statement DDL.

Alembic stamp applied via SQLAlchemy UPDATE (alembic CLI targets port 5434, unavailable locally).

Usage:
    cd backend && uv run python scripts/broker_schema_mods_02.py
"""

import asyncio

from sqlalchemy import text

from flywheel.db.session import get_session_factory

# ---------------------------------------------------------------------------
# Seed statement: carrier_configs.email_address -> carrier_contacts
# ---------------------------------------------------------------------------

SEED_STATEMENT = """INSERT INTO carrier_contacts (
    tenant_id, carrier_config_id, name, email, role, is_primary, created_at, updated_at
)
SELECT
    tenant_id,
    id AS carrier_config_id,
    carrier_name AS name,
    email_address AS email,
    'submissions' AS role,
    true AS is_primary,
    now() AS created_at,
    now() AS updated_at
FROM carrier_configs
WHERE email_address IS NOT NULL
ON CONFLICT (carrier_config_id, email) DO NOTHING"""

# ---------------------------------------------------------------------------
# CHECK constraints (DROP IF EXISTS + ADD — idempotent)
# ---------------------------------------------------------------------------

CHECK_STATEMENTS: list[str] = [
    # broker_projects.status (adds binding, bound states)
    "ALTER TABLE broker_projects DROP CONSTRAINT IF EXISTS chk_broker_projects_status",
    """ALTER TABLE broker_projects ADD CONSTRAINT chk_broker_projects_status
       CHECK (status IN ('new_request','analyzing','analysis_failed','gaps_identified',
                         'soliciting','quotes_partial','quotes_complete','recommended',
                         'delivered','binding','bound','cancelled'))""",
    # broker_projects.approval_status
    "ALTER TABLE broker_projects DROP CONSTRAINT IF EXISTS chk_broker_projects_approval_status",
    """ALTER TABLE broker_projects ADD CONSTRAINT chk_broker_projects_approval_status
       CHECK (approval_status IN ('draft','pending','approved','rejected'))""",
    # broker_projects.analysis_status — NOTE: 'completed' not 'complete'
    "ALTER TABLE broker_projects DROP CONSTRAINT IF EXISTS chk_broker_projects_analysis_status",
    """ALTER TABLE broker_projects ADD CONSTRAINT chk_broker_projects_analysis_status
       CHECK (analysis_status IN ('pending','running','completed','failed'))""",
    # carrier_quotes.status
    "ALTER TABLE carrier_quotes DROP CONSTRAINT IF EXISTS chk_carrier_quotes_status",
    """ALTER TABLE carrier_quotes ADD CONSTRAINT chk_carrier_quotes_status
       CHECK (status IN ('pending','solicited','received','selected','rejected','expired'))""",
    # carrier_quotes.confidence
    "ALTER TABLE carrier_quotes DROP CONSTRAINT IF EXISTS chk_carrier_quotes_confidence",
    """ALTER TABLE carrier_quotes ADD CONSTRAINT chk_carrier_quotes_confidence
       CHECK (confidence IN ('high','medium','low'))""",
    # project_coverages.gap_status
    "ALTER TABLE project_coverages DROP CONSTRAINT IF EXISTS chk_project_coverages_gap_status",
    """ALTER TABLE project_coverages ADD CONSTRAINT chk_project_coverages_gap_status
       CHECK (gap_status IN ('covered','gap','unknown','partial'))""",
    # project_coverages.confidence
    "ALTER TABLE project_coverages DROP CONSTRAINT IF EXISTS chk_project_coverages_confidence",
    """ALTER TABLE project_coverages ADD CONSTRAINT chk_project_coverages_confidence
       CHECK (confidence IN ('high','medium','low'))""",
    # project_coverages.source
    "ALTER TABLE project_coverages DROP CONSTRAINT IF EXISTS chk_project_coverages_source",
    """ALTER TABLE project_coverages ADD CONSTRAINT chk_project_coverages_source
       CHECK (source IN ('ai_extraction','manual','import'))""",
    # broker_activities.actor_type (MOD-06)
    "ALTER TABLE broker_activities DROP CONSTRAINT IF EXISTS chk_broker_activities_actor_type",
    """ALTER TABLE broker_activities ADD CONSTRAINT chk_broker_activities_actor_type
       CHECK (actor_type IN ('system','user','automation'))""",
]

# ---------------------------------------------------------------------------
# broker_activities FK on document_id (NOT VALID + VALIDATE pattern)
# ---------------------------------------------------------------------------

ACTIVITY_FK_STATEMENTS: list[str] = [
    # Drop existing FK if it exists (idempotency)
    "ALTER TABLE broker_activities DROP CONSTRAINT IF EXISTS fk_broker_activities_document_id",
    # Add FK NOT VALID (avoids full table lock, tolerates orphaned rows)
    """ALTER TABLE broker_activities ADD CONSTRAINT fk_broker_activities_document_id
       FOREIGN KEY (document_id) REFERENCES uploaded_files(id) ON DELETE SET NULL
       NOT VALID""",
    # Validate the constraint (fails if orphans exist — acceptable, log and continue)
    "ALTER TABLE broker_activities VALIDATE CONSTRAINT fk_broker_activities_document_id",
]

# ---------------------------------------------------------------------------
# DROP obsolete columns
# CRITICAL: carrier_configs.email_address is dropped LAST (seed source data)
# ---------------------------------------------------------------------------

DROP_STATEMENTS: list[str] = [
    # broker_projects — 7 columns (MOD-01 drops)
    "ALTER TABLE broker_projects DROP COLUMN IF EXISTS pipeline_entry_id",
    "ALTER TABLE broker_projects DROP COLUMN IF EXISTS recommendation_subject",
    "ALTER TABLE broker_projects DROP COLUMN IF EXISTS recommendation_body",
    "ALTER TABLE broker_projects DROP COLUMN IF EXISTS recommendation_status",
    "ALTER TABLE broker_projects DROP COLUMN IF EXISTS recommendation_sent_at",
    "ALTER TABLE broker_projects DROP COLUMN IF EXISTS recommendation_recipient",
    "ALTER TABLE broker_projects DROP COLUMN IF EXISTS email_thread_ids",
    # carrier_quotes — 6 columns (MOD-02 drops)
    "ALTER TABLE carrier_quotes DROP COLUMN IF EXISTS draft_subject",
    "ALTER TABLE carrier_quotes DROP COLUMN IF EXISTS draft_body",
    "ALTER TABLE carrier_quotes DROP COLUMN IF EXISTS draft_status",
    "ALTER TABLE carrier_quotes DROP COLUMN IF EXISTS is_best_price",
    "ALTER TABLE carrier_quotes DROP COLUMN IF EXISTS is_best_coverage",
    "ALTER TABLE carrier_quotes DROP COLUMN IF EXISTS is_recommended",
    # carrier_configs — 2 columns (carrier_pipeline_entry_id first, email_address LAST)
    "ALTER TABLE carrier_configs DROP COLUMN IF EXISTS carrier_pipeline_entry_id",
    "ALTER TABLE carrier_configs DROP COLUMN IF EXISTS email_address",
]


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

async def preflight(factory) -> None:
    """Verify preconditions before running any mutations."""
    async with factory() as session:
        # 1. Verify alembic version
        r = await session.execute(text("SELECT version_num FROM alembic_version"))
        version = r.scalar()
        if version != "060_broker_schema_mods_01":
            raise RuntimeError(
                f"Expected alembic 060_broker_schema_mods_01, got: {version}. "
                "Run Plan 01 (broker_schema_mods_01.py) first."
            )

        # 2. Check for non-conforming analysis_status values
        r2 = await session.execute(text(
            "SELECT DISTINCT analysis_status FROM broker_projects WHERE analysis_status IS NOT NULL"
        ))
        statuses = [row[0] for row in r2.fetchall()]
        bad = [s for s in statuses if s not in ('pending', 'running', 'completed', 'failed')]
        if bad:
            print(f"WARNING: broker_projects.analysis_status has non-conforming values: {bad}")
            print("These rows will violate the CHECK constraint. Fix data before proceeding.")
            raise RuntimeError(f"Non-conforming analysis_status values: {bad}")

        # 3. Check for orphaned document_ids in broker_activities
        r3 = await session.execute(text(
            "SELECT count(*) FROM broker_activities WHERE document_id IS NOT NULL "
            "AND document_id NOT IN (SELECT id FROM uploaded_files)"
        ))
        orphan_count = r3.scalar()
        if orphan_count and orphan_count > 0:
            print(f"WARNING: {orphan_count} broker_activities rows have orphaned document_id values.")
            print("Using NOT VALID constraint to allow partial migration. Run VALIDATE CONSTRAINT after cleanup.")

    print("Pre-flight checks passed.")


# ---------------------------------------------------------------------------
# Seed verification gate (abort before drops if seed incomplete)
# ---------------------------------------------------------------------------

async def verify_seed(factory) -> None:
    """Abort migration if carrier_contacts seed count < carrier_configs email count."""
    async with factory() as session:
        r = await session.execute(text(
            "SELECT COUNT(*) FROM carrier_configs WHERE email_address IS NOT NULL"
        ))
        source_count = r.scalar()
        r2 = await session.execute(text(
            "SELECT COUNT(*) FROM carrier_contacts WHERE role = 'submissions' AND is_primary = true"
        ))
        dest_count = r2.scalar()

    print(
        f"Seed check — source (carrier_configs with email): {source_count}, "
        f"dest (carrier_contacts submissions): {dest_count}"
    )
    if source_count and source_count > 0 and dest_count < source_count:
        raise RuntimeError(
            f"Seed incomplete: {dest_count} carrier_contacts rows < {source_count} source rows. "
            "Aborting before column drop."
        )
    print("Seed verified OK.")


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

async def run_migration() -> None:
    factory = get_session_factory()

    # 1. Pre-flight
    await preflight(factory)

    # 2. Seed carrier emails into carrier_contacts
    async with factory() as session:
        await session.execute(text(SEED_STATEMENT))
        await session.commit()
    print("OK: Carrier email seed complete")

    # 3. Verify seed BEFORE any drops (data loss prevention gate)
    await verify_seed(factory)

    # 4. CHECK constraints — each as own committed transaction
    for stmt in CHECK_STATEMENTS:
        async with factory() as session:
            await session.execute(text(stmt))
            await session.commit()
        print(f"OK: {stmt.strip()[:80]}...")

    # 5. broker_activities FK (NOT VALID + VALIDATE; VALIDATE errors are logged, not fatal)
    for stmt in ACTIVITY_FK_STATEMENTS:
        try:
            async with factory() as session:
                await session.execute(text(stmt))
                await session.commit()
            print(f"OK: {stmt.strip()[:80]}...")
        except Exception as e:
            if "VALIDATE" in stmt.upper():
                print(
                    f"WARNING: FK validation failed (orphaned document_ids may exist): {e}"
                )
                print(
                    "The NOT VALID constraint is still in place. "
                    "Clean orphans and re-run VALIDATE manually."
                )
            else:
                raise

    # 6. Drop obsolete columns — each as own committed transaction
    for stmt in DROP_STATEMENTS:
        async with factory() as session:
            await session.execute(text(stmt))
            await session.commit()
        print(f"OK: {stmt.strip()[:80]}...")

    # 7. Stamp alembic via SQLAlchemy UPDATE (CLI targets unavailable port 5434)
    async with factory() as session:
        await session.execute(
            text("UPDATE alembic_version SET version_num = '061_broker_schema_mods_02'")
        )
        await session.commit()
    print("Alembic stamped to 061_broker_schema_mods_02")
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(run_migration())
