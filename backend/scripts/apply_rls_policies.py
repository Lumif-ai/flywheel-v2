"""Apply all RLS policies, roles, grants, triggers, and functions to the database.

When the database is set up via Base.metadata.create_all (instead of Alembic migrations),
all op.execute() calls in migration files are skipped. This script applies everything that
create_all misses:

1. PL/pgSQL functions (update_updated_at_column, set_updated_at)
2. app_user role and grants
3. RLS enable/force on all tenant-scoped tables
4. RLS policies on all tenant-scoped tables
5. Triggers (updated_at on context_entries, integrations)

Extracted from migration files: 002, 003, 004, 005, 007, 008, 010, 011, 012, 014, 015, 016.

Usage:
    # From backend directory, with .env loaded:
    python -m scripts.apply_rls_policies
    # Or:
    .venv/bin/python scripts/apply_rls_policies.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL statements extracted from migration files
# ---------------------------------------------------------------------------

# From 003_fts_and_indexes.py: PL/pgSQL function for updated_at triggers
FUNCTIONS_SQL = [
    # update_updated_at_column (used by context_entries trigger in 003)
    """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = now();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """,
    # set_updated_at alias (referenced by integrations trigger in 005)
    # This is a common Supabase convention; create if not exists
    """
    CREATE OR REPLACE FUNCTION set_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = now();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """,
]

# From 003: Trigger on context_entries
# From 005: Trigger on integrations
TRIGGERS_SQL = [
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'set_updated_at'
            AND tgrelid = 'context_entries'::regclass
        ) THEN
            CREATE TRIGGER set_updated_at
                BEFORE UPDATE ON context_entries
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        END IF;
    END $$;
    """,
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'set_integrations_updated_at'
            AND tgrelid = 'integrations'::regclass
        ) THEN
            CREATE TRIGGER set_integrations_updated_at
                BEFORE UPDATE ON integrations
                FOR EACH ROW
                EXECUTE FUNCTION set_updated_at();
        END IF;
    END $$;
    """,
]

# From 003: FTS search_vector column verification
FTS_SQL = [
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'context_entries'
              AND column_name = 'search_vector'
        ) THEN
            EXECUTE 'ALTER TABLE context_entries ADD COLUMN
                search_vector tsvector GENERATED ALWAYS AS (
                    to_tsvector(''english'', coalesce(detail, '''') || '' '' || content)
                ) STORED';
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_context_search
                ON context_entries USING GIN(search_vector)';
        END IF;
    END $$;
    """,
]

# From 002: app_user role creation and grants
ROLE_SQL = [
    """
    DO $$ BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
            CREATE ROLE app_user NOLOGIN;
        END IF;
    END $$;
    """,
    "GRANT USAGE ON SCHEMA public TO app_user",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user",
    "GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_user",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO app_user",
]

# ---------------------------------------------------------------------------
# Tables that need RLS and their policies
# ---------------------------------------------------------------------------

# From 002: Original 9 tenant-scoped tables
TENANT_TABLES_002 = [
    "user_tenants",
    "onboarding_sessions",
    "context_entries",
    "context_catalog",
    "context_events",
    "skill_runs",
    "enrichment_cache",
    "uploaded_files",
    "work_items",
]

# From 004: invites
# From 005: integrations
# From 007: suggestion_dismissals
# From 010: context_entities, context_relationships, context_entity_entries
# From 011: focuses, user_focuses
# From 012: work_streams, work_stream_entities
# From 014: meeting_classifications
# From 015: density_snapshots
# From 016: nudge_interactions

ALL_RLS_TABLES = (
    TENANT_TABLES_002
    + [
        "invites",
        "integrations",
        "suggestion_dismissals",
        "context_entities",
        "context_relationships",
        "context_entity_entries",
        "focuses",
        "user_focuses",
        "work_streams",
        "work_stream_entities",
        "meeting_classifications",
        "density_snapshots",
        "nudge_interactions",
    ]
)


def _enable_rls_sql(tables: list[str]) -> list[str]:
    """Generate ENABLE + FORCE RLS for all tables."""
    stmts = []
    for t in tables:
        stmts.append(f"ALTER TABLE IF EXISTS {t} ENABLE ROW LEVEL SECURITY")
        stmts.append(f"ALTER TABLE IF EXISTS {t} FORCE ROW LEVEL SECURITY")
    return stmts


def _grant_to_app_user_sql(tables: list[str]) -> list[str]:
    """Generate GRANT statements for tables added after migration 002."""
    return [
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {t} TO app_user"
        for t in tables
    ]


def _build_policy_sql() -> list[str]:
    """Build all CREATE POLICY statements from migration definitions.

    Uses DROP IF EXISTS + CREATE to be idempotent.
    """
    stmts: list[str] = []

    def _drop_create(policy_name: str, table: str, sql: str) -> None:
        stmts.append(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        stmts.append(sql)

    # ------------------------------------------------------------------
    # From 002: context_entries (4 policies: read, insert, update, delete)
    # ------------------------------------------------------------------
    _drop_create("context_read", "context_entries", """
        CREATE POLICY context_read ON context_entries
            FOR SELECT
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND deleted_at IS NULL
                AND (
                    visibility IN ('shared', 'team')
                    OR (visibility = 'private'
                        AND user_id = current_setting('app.user_id', true)::uuid)
                )
            )
    """)
    _drop_create("context_insert", "context_entries", """
        CREATE POLICY context_insert ON context_entries
            FOR INSERT
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
    """)
    _drop_create("context_update", "context_entries", """
        CREATE POLICY context_update ON context_entries
            FOR UPDATE
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND deleted_at IS NULL
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
    """)
    _drop_create("context_delete", "context_entries", """
        CREATE POLICY context_delete ON context_entries
            FOR DELETE
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
    """)

    # ------------------------------------------------------------------
    # From 002: Standard tenant_isolation on remaining 8 tables
    # ------------------------------------------------------------------
    standard_002 = [t for t in TENANT_TABLES_002 if t != "context_entries"]
    for table in standard_002:
        _drop_create("tenant_isolation", table, f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
                WITH CHECK (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
        """)

    # ------------------------------------------------------------------
    # From 004: invites (FOR ALL policy)
    # ------------------------------------------------------------------
    _drop_create("invites_tenant_isolation", "invites", """
        CREATE POLICY invites_tenant_isolation ON invites
        FOR ALL
        USING (current_setting('app.tenant_id', true)::uuid = tenant_id)
    """)

    # ------------------------------------------------------------------
    # From 005: integrations (FOR ALL policy)
    # ------------------------------------------------------------------
    _drop_create("integrations_tenant_isolation", "integrations", """
        CREATE POLICY integrations_tenant_isolation ON integrations
        FOR ALL
        USING (current_setting('app.tenant_id', true)::uuid = tenant_id)
    """)

    # ------------------------------------------------------------------
    # From 008 (corrected from 007): suggestion_dismissals
    # ------------------------------------------------------------------
    _drop_create("tenant_isolation", "suggestion_dismissals", """
        CREATE POLICY tenant_isolation ON suggestion_dismissals
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)

    # ------------------------------------------------------------------
    # From 010: 3 graph tables (4 policies each: select, insert, update, delete)
    # ------------------------------------------------------------------
    graph_tables = ["context_entities", "context_relationships", "context_entity_entries"]
    for table in graph_tables:
        for action, clause in [
            ("select", f"FOR SELECT USING (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
            ("insert", f"FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
            ("update", f"FOR UPDATE USING (tenant_id = current_setting('app.tenant_id', true)::uuid) WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
            ("delete", f"FOR DELETE USING (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
        ]:
            _drop_create(f"tenant_isolation_{action}", table,
                         f"CREATE POLICY tenant_isolation_{action} ON {table} {clause}")

    # ------------------------------------------------------------------
    # From 011: 2 focus tables (4 policies each)
    # ------------------------------------------------------------------
    focus_tables = ["focuses", "user_focuses"]
    for table in focus_tables:
        for action, clause in [
            ("select", f"FOR SELECT USING (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
            ("insert", f"FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
            ("update", f"FOR UPDATE USING (tenant_id = current_setting('app.tenant_id', true)::uuid) WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
            ("delete", f"FOR DELETE USING (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
        ]:
            _drop_create(f"tenant_isolation_{action}", table,
                         f"CREATE POLICY tenant_isolation_{action} ON {table} {clause}")

    # ------------------------------------------------------------------
    # From 012: 2 work stream tables (4 policies each)
    # ------------------------------------------------------------------
    ws_tables = ["work_streams", "work_stream_entities"]
    for table in ws_tables:
        for action, clause in [
            ("select", f"FOR SELECT USING (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
            ("insert", f"FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
            ("update", f"FOR UPDATE USING (tenant_id = current_setting('app.tenant_id', true)::uuid) WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
            ("delete", f"FOR DELETE USING (tenant_id = current_setting('app.tenant_id', true)::uuid)"),
        ]:
            _drop_create(f"tenant_isolation_{action}", table,
                         f"CREATE POLICY tenant_isolation_{action} ON {table} {clause}")

    # ------------------------------------------------------------------
    # From 014: meeting_classifications (FOR ALL policy)
    # ------------------------------------------------------------------
    _drop_create("meeting_classifications_tenant_isolation", "meeting_classifications", """
        CREATE POLICY meeting_classifications_tenant_isolation
        ON meeting_classifications
        FOR ALL
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
    """)

    # ------------------------------------------------------------------
    # From 015: density_snapshots (FOR ALL policy)
    # ------------------------------------------------------------------
    _drop_create("density_snapshots_tenant_isolation", "density_snapshots", """
        CREATE POLICY density_snapshots_tenant_isolation
        ON density_snapshots
        FOR ALL
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
    """)

    # ------------------------------------------------------------------
    # From 016: nudge_interactions (FOR ALL policy)
    # ------------------------------------------------------------------
    _drop_create("nudge_interactions_tenant_isolation", "nudge_interactions", """
        CREATE POLICY nudge_interactions_tenant_isolation
        ON nudge_interactions
        FOR ALL
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
    """)

    return stmts


# Tables from 010, 011, 012 that get explicit GRANT after 002's blanket GRANT
EXTRA_GRANT_TABLES = [
    "context_entities", "context_relationships", "context_entity_entries",
    "focuses", "user_focuses",
    "work_streams", "work_stream_entities",
]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

async def apply_all(database_url: str, dry_run: bool = False) -> None:
    """Apply all RLS policies to the database.

    Args:
        database_url: Async Postgres connection URL.
        dry_run: If True, print SQL without executing.
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    all_sql: list[tuple[str, str]] = []

    # Phase 1: Functions
    for sql in FUNCTIONS_SQL:
        all_sql.append(("function", sql))

    # Phase 2: Triggers
    for sql in TRIGGERS_SQL:
        all_sql.append(("trigger", sql))

    # Phase 3: FTS
    for sql in FTS_SQL:
        all_sql.append(("fts", sql))

    # Phase 4: Role and grants
    for sql in ROLE_SQL:
        all_sql.append(("role/grant", sql))

    # Phase 5: Enable RLS on all tables
    for sql in _enable_rls_sql(ALL_RLS_TABLES):
        all_sql.append(("enable-rls", sql))

    # Phase 6: Extra grants for post-002 tables
    for sql in _grant_to_app_user_sql(EXTRA_GRANT_TABLES):
        all_sql.append(("grant", sql))

    # Phase 7: All policies
    for sql in _build_policy_sql():
        all_sql.append(("policy", sql))

    total = len(all_sql)
    print(f"Applying {total} SQL statements...")

    if dry_run:
        for i, (phase, sql) in enumerate(all_sql, 1):
            print(f"\n-- [{i}/{total}] {phase}")
            print(sql.strip())
            print(";")
        print(f"\nDry run complete: {total} statements would be executed.")
        return

    engine = create_async_engine(database_url, echo=False)
    errors = []

    try:
        async with engine.begin() as conn:
            for i, (phase, sql) in enumerate(all_sql, 1):
                try:
                    await conn.execute(text(sql))
                except Exception as e:
                    error_msg = str(e).split("\n")[0]
                    # Skip "table does not exist" errors gracefully
                    if "does not exist" in error_msg or "UndefinedTableError" in error_msg:
                        print(f"  [{i}/{total}] {phase}: SKIPPED (table not found)")
                    else:
                        errors.append((phase, sql.strip()[:80], error_msg))
                        print(f"  [{i}/{total}] {phase}: ERROR - {error_msg}")

        if errors:
            print(f"\nCompleted with {len(errors)} errors:")
            for phase, sql_preview, err in errors:
                print(f"  {phase}: {err}")
                print(f"    SQL: {sql_preview}...")
        else:
            print(f"\nAll {total} statements applied successfully.")

    finally:
        await engine.dispose()


async def verify(database_url: str) -> bool:
    """Verify RLS is enabled and policies exist on key tables."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    engine = create_async_engine(database_url, echo=False)
    ok = True

    try:
        async with engine.begin() as conn:
            # Check RLS enabled
            result = await conn.execute(text("""
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind = 'r'
                ORDER BY c.relname
            """))
            tables = {row[0]: (row[1], row[2]) for row in result}

            print("\nRLS status:")
            for table in ALL_RLS_TABLES:
                if table in tables:
                    enabled, forced = tables[table]
                    status = "OK" if (enabled and forced) else "MISSING"
                    if status == "MISSING":
                        ok = False
                    print(f"  {table}: RLS={'on' if enabled else 'OFF'} FORCE={'on' if forced else 'OFF'} [{status}]")
                else:
                    print(f"  {table}: TABLE NOT FOUND (may not be created yet)")

            # Check policy count
            result = await conn.execute(text("""
                SELECT tablename, COUNT(*) as policy_count
                FROM pg_policies
                WHERE schemaname = 'public'
                GROUP BY tablename
                ORDER BY tablename
            """))
            policies = {row[0]: row[1] for row in result}

            print(f"\nPolicies found: {sum(policies.values())} across {len(policies)} tables")
            for table, count in sorted(policies.items()):
                print(f"  {table}: {count} policies")

            # Check app_user role
            result = await conn.execute(text(
                "SELECT 1 FROM pg_roles WHERE rolname = 'app_user'"
            ))
            has_role = result.scalar() is not None
            print(f"\napp_user role: {'EXISTS' if has_role else 'MISSING'}")
            if not has_role:
                ok = False

    finally:
        await engine.dispose()

    return ok


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Apply all RLS policies to the Flywheel database.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print SQL without executing")
    parser.add_argument("--verify", action="store_true", help="Verify RLS status only")
    parser.add_argument("--database-url", default=None, help="Override database URL")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Get database URL
    db_url = args.database_url
    if db_url is None:
        # Load from backend config
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))
        from flywheel.config import settings
        db_url = settings.database_url

    if args.verify:
        ok = asyncio.run(verify(db_url))
        return 0 if ok else 1

    asyncio.run(apply_all(db_url, dry_run=args.dry_run))

    # Always verify after applying
    if not args.dry_run:
        print("\n--- Verification ---")
        ok = asyncio.run(verify(db_url))
        return 0 if ok else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
