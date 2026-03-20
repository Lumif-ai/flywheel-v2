"""enable RLS policies on all tenant-scoped tables

Revision ID: 002_rls
Revises: 5e96a39d5776
Create Date: 2026-03-20

Hand-written migration -- RLS and policies are not supported by Alembic autogenerate.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_rls"
down_revision: Union[str, Sequence[str], None] = "5e96a39d5776"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 9 tenant-scoped tables that need RLS
TENANT_TABLES = [
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


def verify_rls(tables: list[str]) -> None:
    """Verify RLS is enabled on all specified tables."""
    for table in tables:
        op.execute(
            f"DO $$ BEGIN "
            f"IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='{table}' AND relrowsecurity) "
            f"THEN RAISE EXCEPTION 'RLS not enabled on table: {table}'; "
            f"END IF; END $$;"
        )


def upgrade() -> None:
    """Enable RLS on all tenant-scoped tables and create policies."""

    # 1. Create app_user role (idempotent)
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user NOLOGIN;
            END IF;
        END $$;
        """
    )

    # 2. Grant permissions to app_user
    op.execute("GRANT USAGE ON SCHEMA public TO app_user")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user"
    )
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_user")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE ON SEQUENCES TO app_user"
    )

    # 3. Enable and force RLS on all tenant-scoped tables
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # 4. Create RLS policies

    # context_entries: most complex -- visibility + soft delete
    op.execute(
        """
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
        """
    )
    op.execute(
        """
        CREATE POLICY context_insert ON context_entries
            FOR INSERT
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )
    op.execute(
        """
        CREATE POLICY context_update ON context_entries
            FOR UPDATE
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND deleted_at IS NULL
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )
    op.execute(
        """
        CREATE POLICY context_delete ON context_entries
            FOR DELETE
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )

    # All other tenant-scoped tables: standard tenant isolation policy
    standard_tables = [t for t in TENANT_TABLES if t != "context_entries"]
    for table in standard_tables:
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
                WITH CHECK (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
            """
        )

    # 5. Verify RLS
    verify_rls(TENANT_TABLES)


def downgrade() -> None:
    """Remove all RLS policies, disable RLS, revoke grants, drop app_user role."""

    # Drop policies on context_entries
    for policy in ["context_read", "context_insert", "context_update", "context_delete"]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON context_entries")

    # Drop standard policies on other tables
    standard_tables = [t for t in TENANT_TABLES if t != "context_entries"]
    for table in standard_tables:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    # Disable RLS on all tables
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Revoke grants
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM app_user"
    )
    op.execute("REVOKE USAGE ON ALL SEQUENCES IN SCHEMA public FROM app_user")
    op.execute("REVOKE USAGE ON SCHEMA public FROM app_user")

    # Drop role
    op.execute(
        """
        DO $$ BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
                DROP ROLE app_user;
            END IF;
        END $$;
        """
    )
