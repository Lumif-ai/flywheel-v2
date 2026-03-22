"""create work_streams and work_stream_entities tables

Revision ID: 012_work_stream_tables
Revises: 011_focus_tables
Create Date: 2026-03-22

Hand-written migration -- creates work_streams and work_stream_entities tables
for the v3.0 work stream organizing principle. Includes RLS policies and grants
following the pattern from migration 011.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "012_work_stream_tables"
down_revision: Union[str, Sequence[str]] = "011_focus_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New tables that need RLS
WORK_STREAM_TABLES = [
    "work_streams",
    "work_stream_entities",
]


def upgrade() -> None:
    """Create work_streams and work_stream_entities tables with RLS."""

    # -----------------------------------------------------------------------
    # Table 1: work_streams
    # -----------------------------------------------------------------------
    op.create_table(
        "work_streams",
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
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
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
            "density_score",
            sa.Numeric(5, 2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.Column(
            "density_details",
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
    )

    # Indexes for work_streams
    op.create_index(
        "idx_streams_tenant",
        "work_streams",
        ["tenant_id"],
    )
    op.create_index(
        "idx_streams_tenant_active",
        "work_streams",
        ["tenant_id"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    # Partial unique: name must be unique per tenant among non-archived streams
    op.create_index(
        "uq_stream_tenant_name",
        "work_streams",
        ["tenant_id", "name"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    # -----------------------------------------------------------------------
    # Table 2: work_stream_entities (junction)
    # -----------------------------------------------------------------------
    op.create_table(
        "work_stream_entities",
        sa.Column(
            "stream_id",
            sa.Uuid(),
            sa.ForeignKey("work_streams.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "entity_id",
            sa.Uuid(),
            sa.ForeignKey("context_entities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "linked_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Indexes for work_stream_entities
    op.create_index(
        "idx_wse_tenant",
        "work_stream_entities",
        ["tenant_id"],
    )
    op.create_index(
        "idx_wse_entity",
        "work_stream_entities",
        ["entity_id"],
    )

    # -----------------------------------------------------------------------
    # RLS: Enable and force on both new tables
    # -----------------------------------------------------------------------
    for table in WORK_STREAM_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # -----------------------------------------------------------------------
    # RLS: Grant permissions to app_user role
    # -----------------------------------------------------------------------
    for table in WORK_STREAM_TABLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user"
        )

    # -----------------------------------------------------------------------
    # RLS: Create tenant_isolation policies (SELECT/INSERT/UPDATE/DELETE)
    # -----------------------------------------------------------------------
    for table in WORK_STREAM_TABLES:
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
    """Drop work_stream_entities and work_streams tables (reverse order)."""

    # Drop RLS policies on work stream tables
    for table in WORK_STREAM_TABLES:
        for action in ["select", "insert", "update", "delete"]:
            op.execute(
                f"DROP POLICY IF EXISTS tenant_isolation_{action} ON {table}"
            )

    # Disable RLS
    for table in WORK_STREAM_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Revoke grants
    for table in WORK_STREAM_TABLES:
        op.execute(
            f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM app_user"
        )

    # Drop tables (reverse order for FK dependencies)
    op.drop_index("idx_wse_entity", table_name="work_stream_entities")
    op.drop_index("idx_wse_tenant", table_name="work_stream_entities")
    op.drop_table("work_stream_entities")
    op.drop_index("uq_stream_tenant_name", table_name="work_streams")
    op.drop_index("idx_streams_tenant_active", table_name="work_streams")
    op.drop_index("idx_streams_tenant", table_name="work_streams")
    op.drop_table("work_streams")
