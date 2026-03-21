"""create focus tables (focuses, user_focuses) and add focus_id FKs

Revision ID: 011_focus_tables
Revises: 010_context_graph
Create Date: 2026-03-21

Hand-written migration -- creates focuses and user_focuses tables, adds focus_id FK
to context_entries, and adds FK constraint to existing context_relationships.focus_id.
Includes RLS policies and grants following the pattern from migration 010.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "011_focus_tables"
down_revision: Union[str, Sequence[str]] = "010_context_graph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New tables that need RLS
FOCUS_TABLES = [
    "focuses",
    "user_focuses",
]


def upgrade() -> None:
    """Create focuses and user_focuses tables, add focus_id FK to context_entries,
    add FK constraint to context_relationships.focus_id. Enable RLS on new tables."""

    # -----------------------------------------------------------------------
    # Table 1: focuses
    # -----------------------------------------------------------------------
    op.create_table(
        "focuses",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "settings",
            JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "archived_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id", "name",
            name="uq_focus_tenant_name",
        ),
    )

    # Index for focuses
    op.create_index(
        "idx_focuses_tenant",
        "focuses",
        ["tenant_id"],
    )

    # -----------------------------------------------------------------------
    # Table 2: user_focuses
    # -----------------------------------------------------------------------
    op.create_table(
        "user_focuses",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            primary_key=True,
        ),
        sa.Column(
            "focus_id",
            sa.Uuid(),
            sa.ForeignKey("focuses.id"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "joined_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Partial unique index: one active focus per user per tenant
    op.create_index(
        "idx_one_active_focus",
        "user_focuses",
        ["user_id", "tenant_id"],
        unique=True,
        postgresql_where=sa.text("active = true"),
    )

    # -----------------------------------------------------------------------
    # Add focus_id FK to context_entries
    # -----------------------------------------------------------------------
    op.add_column(
        "context_entries",
        sa.Column(
            "focus_id",
            sa.Uuid(),
            sa.ForeignKey("focuses.id"),
            nullable=True,
        ),
    )

    # Index for focus-scoped queries on context_entries
    op.create_index(
        "idx_context_focus",
        "context_entries",
        ["tenant_id", "focus_id"],
    )

    # -----------------------------------------------------------------------
    # Add FK constraint to existing context_relationships.focus_id
    # -----------------------------------------------------------------------
    op.execute(
        "ALTER TABLE context_relationships "
        "ADD CONSTRAINT fk_relationships_focus "
        "FOREIGN KEY (focus_id) REFERENCES focuses(id)"
    )

    # -----------------------------------------------------------------------
    # RLS: Enable and force on both new tables
    # -----------------------------------------------------------------------
    for table in FOCUS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # -----------------------------------------------------------------------
    # RLS: Grant permissions to app_user role
    # -----------------------------------------------------------------------
    for table in FOCUS_TABLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user"
        )

    # -----------------------------------------------------------------------
    # RLS: Create tenant_isolation policies (SELECT/INSERT/UPDATE/DELETE)
    # -----------------------------------------------------------------------
    for table in FOCUS_TABLES:
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_select ON {table}
                FOR SELECT
                USING (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_insert ON {table}
                FOR INSERT
                WITH CHECK (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_update ON {table}
                FOR UPDATE
                USING (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
                WITH CHECK (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_delete ON {table}
                FOR DELETE
                USING (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
            """
        )


def downgrade() -> None:
    """Drop FK on context_relationships.focus_id, drop focus_id column from
    context_entries, drop user_focuses table, drop focuses table (reverse order)."""

    # Drop FK constraint on context_relationships.focus_id
    op.execute(
        "ALTER TABLE context_relationships "
        "DROP CONSTRAINT IF EXISTS fk_relationships_focus"
    )

    # Drop focus_id column and index from context_entries
    op.drop_index("idx_context_focus", table_name="context_entries")
    op.drop_column("context_entries", "focus_id")

    # Drop RLS policies on focus tables
    for table in FOCUS_TABLES:
        for action in ["select", "insert", "update", "delete"]:
            op.execute(
                f"DROP POLICY IF EXISTS tenant_isolation_{action} ON {table}"
            )

    # Disable RLS
    for table in FOCUS_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Revoke grants
    for table in FOCUS_TABLES:
        op.execute(
            f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM app_user"
        )

    # Drop tables (reverse order for FK dependencies)
    op.drop_index("idx_one_active_focus", table_name="user_focuses")
    op.drop_table("user_focuses")
    op.drop_index("idx_focuses_tenant", table_name="focuses")
    op.drop_table("focuses")
