"""create context graph tables (entities, relationships, entity_entries)

Revision ID: 010_context_graph
Revises: 009_add_reasoning_trace
Create Date: 2026-03-21

Hand-written migration -- creates 3 graph tables layered on top of context_entries.
Includes RLS policies, GIN/B-tree indexes, and unique constraints for entity dedup.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

# revision identifiers, used by Alembic.
revision: str = "010_context_graph"
down_revision: Union[str, Sequence[str]] = "009_add_reasoning_trace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New graph tables that need RLS
GRAPH_TABLES = [
    "context_entities",
    "context_relationships",
    "context_entity_entries",
]


def upgrade() -> None:
    """Create 3 context graph tables with RLS, indexes, and constraints."""

    # -----------------------------------------------------------------------
    # Table 1: context_entities
    # -----------------------------------------------------------------------
    op.create_table(
        "context_entities",
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
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column(
            "aliases",
            ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "metadata",
            JSONB,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "mention_count",
            sa.Integer(),
            server_default=sa.text("1"),
        ),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "name", "entity_type",
            name="uq_entity_tenant_name_type",
        ),
    )

    # Indexes for context_entities
    op.create_index(
        "idx_entities_aliases",
        "context_entities",
        ["aliases"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_entities_tenant_type",
        "context_entities",
        ["tenant_id", "entity_type"],
    )
    op.create_index(
        "idx_entities_tenant_name",
        "context_entities",
        ["tenant_id", "name"],
    )

    # -----------------------------------------------------------------------
    # Table 2: context_relationships
    # -----------------------------------------------------------------------
    op.create_table(
        "context_relationships",
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
            "entity_a_id",
            sa.Uuid(),
            sa.ForeignKey("context_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_b_id",
            sa.Uuid(),
            sa.ForeignKey("context_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relationship", sa.Text(), nullable=False),
        sa.Column(
            "source_entry_id",
            sa.Uuid(),
            sa.ForeignKey("context_entries.id"),
            nullable=True,
        ),
        sa.Column("focus_id", sa.Uuid(), nullable=True),
        sa.Column(
            "directional",
            sa.Boolean(),
            server_default=sa.text("true"),
        ),
        sa.Column(
            "confidence",
            sa.Text(),
            server_default="medium",
        ),
        sa.Column(
            "metadata",
            JSONB,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # Indexes for context_relationships
    op.create_index(
        "idx_relationships_tenant_a",
        "context_relationships",
        ["tenant_id", "entity_a_id"],
    )
    op.create_index(
        "idx_relationships_tenant_b",
        "context_relationships",
        ["tenant_id", "entity_b_id"],
    )

    # -----------------------------------------------------------------------
    # Table 3: context_entity_entries (junction table)
    # -----------------------------------------------------------------------
    op.create_table(
        "context_entity_entries",
        sa.Column(
            "entity_id",
            sa.Uuid(),
            sa.ForeignKey("context_entities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "entry_id",
            sa.Uuid(),
            sa.ForeignKey("context_entries.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "mention_type",
            sa.Text(),
            server_default="explicit",
        ),
    )

    # -----------------------------------------------------------------------
    # RLS: Enable and force on all 3 graph tables
    # -----------------------------------------------------------------------
    for table in GRAPH_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # -----------------------------------------------------------------------
    # RLS: Grant permissions to app_user role
    # -----------------------------------------------------------------------
    for table in GRAPH_TABLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user"
        )

    # -----------------------------------------------------------------------
    # RLS: Create tenant_isolation policies (SELECT/INSERT/UPDATE/DELETE)
    # -----------------------------------------------------------------------
    for table in GRAPH_TABLES:
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
    """Drop RLS policies, disable RLS, revoke grants, drop tables."""

    # Drop policies
    for table in GRAPH_TABLES:
        for action in ["select", "insert", "update", "delete"]:
            op.execute(
                f"DROP POLICY IF EXISTS tenant_isolation_{action} ON {table}"
            )

    # Disable RLS
    for table in GRAPH_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Revoke grants
    for table in GRAPH_TABLES:
        op.execute(
            f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM app_user"
        )

    # Drop tables (reverse order for FK dependencies)
    op.drop_table("context_entity_entries")
    op.drop_table("context_relationships")
    op.drop_table("context_entities")
