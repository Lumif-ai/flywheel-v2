"""Add saved_views table for persisting user pipeline view configurations.

Revision ID: 049_saved_views
Revises: 048_next_action
Create Date: 2026-04-06
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "049_saved_views"
down_revision: Union[str, None] = "048_next_action"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # NOTE: On Supabase with PgBouncer, run each statement separately via
    # Supabase SQL Editor or a one-off script, then `alembic stamp 049_saved_views`.
    #
    # DDL statements to run individually:
    #
    # 1. CREATE TABLE
    # CREATE TABLE saved_views (
    #     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    #     tenant_id UUID NOT NULL REFERENCES tenants(id),
    #     owner_id UUID,
    #     name TEXT NOT NULL,
    #     filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    #     sort JSONB,
    #     columns JSONB,
    #     is_default BOOLEAN NOT NULL DEFAULT false,
    #     position INTEGER NOT NULL DEFAULT 0,
    #     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    #     updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    # );
    #
    # 2. CREATE INDEX
    # CREATE INDEX idx_saved_views_tenant_owner ON saved_views (tenant_id, owner_id);
    #
    # 3. RLS
    # ALTER TABLE saved_views ENABLE ROW LEVEL SECURITY;
    # ALTER TABLE saved_views FORCE ROW LEVEL SECURITY;
    # CREATE POLICY saved_views_tenant_isolation ON saved_views
    #   USING (tenant_id = current_setting('app.tenant_id')::uuid);
    # GRANT SELECT, INSERT, UPDATE, DELETE ON saved_views TO authenticated;

    op.create_table(
        "saved_views",
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
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "filters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("sort", postgresql.JSONB(), nullable=True),
        sa.Column("columns", postgresql.JSONB(), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_saved_views_tenant_owner",
        "saved_views",
        ["tenant_id", "owner_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_saved_views_tenant_owner", table_name="saved_views")
    op.drop_table("saved_views")
