"""Broker module DDL migration — Supabase PgBouncer workaround.

Each DDL statement runs as its own committed transaction to avoid
PgBouncer silently rolling back multi-statement DDL.

Usage:
    cd backend && uv run python scripts/broker_migration.py

After success, stamp alembic:
    cd backend && uv run alembic stamp 056_broker_tables
"""

import asyncio

from sqlalchemy import text

from flywheel.db.session import get_session_factory

# All DDL statements in FK dependency order.
# Each statement is executed and committed individually.
STATEMENTS: list[str] = [
    # -------------------------------------------------------------------------
    # 1. carrier_configs
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS carrier_configs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL REFERENCES tenants(id),
        carrier_name TEXT NOT NULL,
        carrier_type TEXT DEFAULT 'insurance',
        carrier_code TEXT,
        logo_url TEXT,
        submission_method TEXT DEFAULT 'email',
        portal_url TEXT,
        portal_limit NUMERIC,
        portal_credentials BYTEA,
        carrier_pipeline_entry_id UUID REFERENCES pipeline_entries(id) ON DELETE SET NULL,
        coverage_types TEXT[] DEFAULT '{}',
        regions TEXT[] DEFAULT '{}',
        min_project_value NUMERIC,
        max_project_value NUMERIC,
        avg_response_days NUMERIC,
        avg_premium_ratio NUMERIC,
        total_quotes INTEGER DEFAULT 0,
        total_selected INTEGER DEFAULT 0,
        notes TEXT,
        is_active BOOLEAN DEFAULT true,
        email_address TEXT,
        import_source TEXT DEFAULT 'manual',
        external_id TEXT,
        external_ref TEXT,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(tenant_id, carrier_name, carrier_type)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_carrier_config_tenant
       ON carrier_configs(tenant_id) WHERE is_active = true""",

    # -------------------------------------------------------------------------
    # 2. broker_projects
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS broker_projects (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL REFERENCES tenants(id),
        pipeline_entry_id UUID REFERENCES pipeline_entries(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        project_type TEXT DEFAULT 'construction',
        description TEXT,
        contract_value NUMERIC,
        currency TEXT DEFAULT 'MXN',
        start_date DATE,
        end_date DATE,
        location TEXT,
        distance_km NUMERIC,
        language TEXT DEFAULT 'en',
        status TEXT DEFAULT 'new_request',
        source_email_id UUID,
        source_document_id UUID REFERENCES uploaded_files(id),
        email_thread_ids TEXT[] DEFAULT '{}',
        analysis_status TEXT DEFAULT 'pending',
        analysis_completed_at TIMESTAMPTZ,
        critical_findings JSONB DEFAULT '[]',
        import_source TEXT DEFAULT 'manual',
        external_id TEXT,
        external_ref TEXT,
        metadata JSONB DEFAULT '{}',
        deleted_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    )""",
    """CREATE INDEX IF NOT EXISTS idx_broker_project_tenant_status
       ON broker_projects(tenant_id, status) WHERE deleted_at IS NULL""",
    """CREATE INDEX IF NOT EXISTS idx_broker_project_pipeline
       ON broker_projects(pipeline_entry_id) WHERE pipeline_entry_id IS NOT NULL""",

    # -------------------------------------------------------------------------
    # 3. project_coverages
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS project_coverages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL REFERENCES tenants(id),
        broker_project_id UUID NOT NULL REFERENCES broker_projects(id) ON DELETE CASCADE,
        coverage_type TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'insurance',
        display_name TEXT,
        language TEXT DEFAULT 'en',
        required_limit NUMERIC,
        required_deductible NUMERIC,
        required_terms TEXT,
        contract_clause TEXT,
        current_limit NUMERIC,
        current_carrier TEXT,
        current_policy_number TEXT,
        current_expiry DATE,
        gap_status TEXT DEFAULT 'unknown',
        gap_amount NUMERIC,
        gap_notes TEXT,
        source TEXT DEFAULT 'ai_extraction',
        source_document_id UUID REFERENCES uploaded_files(id),
        source_page INTEGER,
        source_section TEXT,
        source_excerpt TEXT,
        confidence TEXT DEFAULT 'high',
        is_manual_override BOOLEAN DEFAULT false,
        import_source TEXT DEFAULT 'manual',
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT now()
    )""",
    """CREATE INDEX IF NOT EXISTS idx_coverage_project
       ON project_coverages(broker_project_id)""",
    """CREATE INDEX IF NOT EXISTS idx_coverage_tenant_category
       ON project_coverages(tenant_id, category)""",

    # -------------------------------------------------------------------------
    # 4. carrier_quotes
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS carrier_quotes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL REFERENCES tenants(id),
        broker_project_id UUID NOT NULL REFERENCES broker_projects(id) ON DELETE CASCADE,
        coverage_id UUID REFERENCES project_coverages(id) ON DELETE SET NULL,
        carrier_config_id UUID REFERENCES carrier_configs(id) ON DELETE SET NULL,
        carrier_name TEXT NOT NULL,
        carrier_type TEXT DEFAULT 'insurance',
        premium NUMERIC,
        deductible NUMERIC,
        limit_amount NUMERIC,
        coinsurance NUMERIC,
        term_months INTEGER,
        validity_date DATE,
        exclusions TEXT[] DEFAULT '{}',
        conditions TEXT[] DEFAULT '{}',
        endorsements TEXT[] DEFAULT '{}',
        terms_detail JSONB DEFAULT '{}',
        is_best_price BOOLEAN DEFAULT false,
        is_best_coverage BOOLEAN DEFAULT false,
        is_recommended BOOLEAN DEFAULT false,
        has_critical_exclusion BOOLEAN DEFAULT false,
        critical_exclusion_detail TEXT,
        status TEXT DEFAULT 'pending',
        solicited_at TIMESTAMPTZ,
        received_at TIMESTAMPTZ,
        selected_at TIMESTAMPTZ,
        source TEXT DEFAULT 'ai_extraction',
        source_document_id UUID REFERENCES uploaded_files(id),
        source_page INTEGER,
        source_section TEXT,
        source_excerpt TEXT,
        source_email_id UUID,
        source_hash TEXT,
        confidence TEXT DEFAULT 'high',
        is_manual_override BOOLEAN DEFAULT false,
        import_source TEXT DEFAULT 'manual',
        language TEXT DEFAULT 'en',
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    )""",
    """CREATE INDEX IF NOT EXISTS idx_quote_project
       ON carrier_quotes(broker_project_id)""",
    """CREATE INDEX IF NOT EXISTS idx_quote_coverage
       ON carrier_quotes(coverage_id)""",
    """CREATE INDEX IF NOT EXISTS idx_quote_tenant_status
       ON carrier_quotes(tenant_id, status)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_quote_source_dedup
       ON carrier_quotes(source_hash) WHERE source_hash IS NOT NULL""",

    # -------------------------------------------------------------------------
    # 5. submission_documents
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS submission_documents (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL REFERENCES tenants(id),
        carrier_quote_id UUID NOT NULL REFERENCES carrier_quotes(id) ON DELETE CASCADE,
        uploaded_file_id UUID NOT NULL REFERENCES uploaded_files(id),
        document_type TEXT NOT NULL,
        display_name TEXT,
        included BOOLEAN DEFAULT true,
        import_source TEXT DEFAULT 'manual',
        created_at TIMESTAMPTZ DEFAULT now()
    )""",
    """CREATE INDEX IF NOT EXISTS idx_submission_doc_quote
       ON submission_documents(carrier_quote_id)""",

    # -------------------------------------------------------------------------
    # 6. broker_activities
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS broker_activities (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL REFERENCES tenants(id),
        broker_project_id UUID NOT NULL REFERENCES broker_projects(id) ON DELETE CASCADE,
        activity_type TEXT NOT NULL,
        description TEXT,
        carrier_name TEXT,
        coverage_type TEXT,
        actor_type TEXT DEFAULT 'system',
        user_id UUID,
        email_id UUID,
        document_id UUID,
        carrier_quote_id UUID REFERENCES carrier_quotes(id) ON DELETE SET NULL,
        import_source TEXT DEFAULT 'manual',
        metadata JSONB DEFAULT '{}',
        occurred_at TIMESTAMPTZ DEFAULT now(),
        created_at TIMESTAMPTZ DEFAULT now()
    )""",
    """CREATE INDEX IF NOT EXISTS idx_broker_activity_project
       ON broker_activities(broker_project_id, occurred_at DESC)""",
    """CREATE INDEX IF NOT EXISTS idx_broker_activity_tenant
       ON broker_activities(tenant_id, occurred_at DESC)""",
]

# RLS policies for all 6 broker tables
BROKER_TABLES = [
    "carrier_configs",
    "broker_projects",
    "project_coverages",
    "carrier_quotes",
    "submission_documents",
    "broker_activities",
]


def _rls_statements(table: str) -> list[str]:
    """Generate RLS enablement statements for a broker table."""
    setting = "current_setting('app.tenant_id', true)::uuid"
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user",
        (
            f"CREATE POLICY tenant_isolation_select ON {table} "
            f"FOR SELECT USING (tenant_id = {setting})"
        ),
        (
            f"CREATE POLICY tenant_isolation_insert ON {table} "
            f"FOR INSERT WITH CHECK (tenant_id = {setting})"
        ),
        (
            f"CREATE POLICY tenant_isolation_update ON {table} "
            f"FOR UPDATE USING (tenant_id = {setting}) "
            f"WITH CHECK (tenant_id = {setting})"
        ),
        (
            f"CREATE POLICY tenant_isolation_delete ON {table} "
            f"FOR DELETE USING (tenant_id = {setting})"
        ),
    ]


async def run_migration() -> None:
    factory = get_session_factory()

    # DDL statements
    for stmt in STATEMENTS:
        async with factory() as session:
            await session.execute(text(stmt))
            await session.commit()
        print(f"OK: {stmt.strip()[:80]}...")

    # RLS policies
    for table in BROKER_TABLES:
        for rls_stmt in _rls_statements(table):
            async with factory() as session:
                await session.execute(text(rls_stmt))
                await session.commit()
            print(f"OK: {rls_stmt[:80]}...")

    print("\nAll DDL applied. Run: alembic stamp 056_broker_tables")


# ---------------------------------------------------------------------------
# Phase 117: Recommendation delivery columns
# ---------------------------------------------------------------------------

RECOMMENDATION_COLUMNS: list[str] = [
    "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS recommendation_subject text",
    "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS recommendation_body text",
    "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS recommendation_status text",
    "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS recommendation_sent_at timestamptz",
    "ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS recommendation_recipient text",
]


async def run_recommendation_migration() -> None:
    """Add recommendation delivery columns to broker_projects."""
    factory = get_session_factory()

    for stmt in RECOMMENDATION_COLUMNS:
        async with factory() as session:
            await session.execute(text(stmt))
            await session.commit()
        print(f"OK: {stmt}")

    print("\nRecommendation columns added.")


if __name__ == "__main__":
    asyncio.run(run_migration())
