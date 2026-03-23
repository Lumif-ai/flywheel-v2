"""create skill_definitions and tenant_skills tables with RLS

Revision ID: 018_skill_registry
Revises: 017_context_entry_metadata
Create Date: 2026-03-23

Hand-written migration -- creates the skill registry tables for DB-backed
skill definitions and per-tenant skill access control.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "018_skill_registry"
down_revision: Union[str, Sequence[str]] = "017_context_entry_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    """Create skill_definitions, tenant_skills, RLS policies, and auto-populate."""

    # 1. Create skill_definitions table (global catalog)
    op.create_table(
        "skill_definitions",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "version", sa.Text(), nullable=False, server_default="0.0.0"
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "web_tier",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column(
            "contract_reads",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "contract_writes",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("engine_module", sa.Text(), nullable=True),
        sa.Column(
            "parameters",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("token_budget", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # Indexes on skill_definitions
    op.create_index("idx_skill_defs_name", "skill_definitions", ["name"])
    op.create_index(
        "idx_skill_defs_enabled",
        "skill_definitions",
        ["enabled"],
        postgresql_where=sa.text("enabled = true"),
    )

    # 2. Create tenant_skills junction table
    op.create_table(
        "tenant_skills",
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id"),
            primary_key=True,
        ),
        sa.Column(
            "skill_id",
            sa.Uuid(),
            sa.ForeignKey("skill_definitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "pricing_tier", sa.Text(), server_default="included"
        ),
        sa.Column(
            "activated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # Index on tenant_skills
    op.create_index(
        "idx_ts_tenant_enabled",
        "tenant_skills",
        ["tenant_id"],
        postgresql_where=sa.text("enabled = true"),
    )

    # 3. Enable RLS and create policies on both tables

    # skill_definitions: global catalog -- all can read, only service role can manage
    op.execute("ALTER TABLE skill_definitions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE skill_definitions FORCE ROW LEVEL SECURITY")

    # All authenticated users can read all skill definitions
    op.execute(
        """
        CREATE POLICY skill_defs_read ON skill_definitions
            FOR SELECT USING (true)
        """
    )
    # Only service role (no app.tenant_id set) can insert/update/delete
    op.execute(
        """
        CREATE POLICY skill_defs_manage ON skill_definitions
            FOR ALL USING (current_setting('app.tenant_id', true) IS NULL)
            WITH CHECK (current_setting('app.tenant_id', true) IS NULL)
        """
    )

    # tenant_skills: standard tenant isolation
    op.execute("ALTER TABLE tenant_skills ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_skills FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY tenant_isolation ON tenant_skills
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    # 4. Auto-populate tenant_skills for all existing tenants x all existing skills
    op.execute(
        """
        INSERT INTO tenant_skills (tenant_id, skill_id, enabled, pricing_tier)
        SELECT t.id, sd.id, true, 'included'
        FROM tenants t
        CROSS JOIN skill_definitions sd
        WHERE t.deleted_at IS NULL
        ON CONFLICT DO NOTHING
        """
    )

    # 5. Verify RLS
    verify_rls(["skill_definitions", "tenant_skills"])


def downgrade() -> None:
    """Drop policies, disable RLS, drop tables in correct order."""

    # Drop policies on skill_definitions
    op.execute("DROP POLICY IF EXISTS skill_defs_read ON skill_definitions")
    op.execute("DROP POLICY IF EXISTS skill_defs_manage ON skill_definitions")

    # Drop policy on tenant_skills
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_skills")

    # Disable RLS
    op.execute("ALTER TABLE tenant_skills NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_skills DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE skill_definitions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE skill_definitions DISABLE ROW LEVEL SECURITY")

    # Drop indexes
    op.drop_index("idx_ts_tenant_enabled", table_name="tenant_skills")
    op.drop_index("idx_skill_defs_enabled", table_name="skill_definitions")
    op.drop_index("idx_skill_defs_name", table_name="skill_definitions")

    # Drop tables (tenant_skills first due to FK)
    op.drop_table("tenant_skills")
    op.drop_table("skill_definitions")
