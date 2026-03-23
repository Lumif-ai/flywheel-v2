"""add nudge_interactions table for tracking nudge lifecycle

Revision ID: 016_nudge_interactions
Revises: 015_density_snapshots
Create Date: 2026-03-23

Hand-written migration -- creates nudge_interactions table for tracking
which nudges were shown, dismissed, completed, or skipped per user.
Enables progressive nudge cadence and 7-day dismissal suppression.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "016_nudge_interactions"
down_revision: Union[str, Sequence[str]] = "015_density_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create nudge_interactions table with RLS policy."""

    op.create_table(
        "nudge_interactions",
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
        sa.Column("nudge_type", sa.Text(), nullable=False),
        sa.Column("nudge_key", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column(
            "data",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # Composite indexes for fast lookups
    op.create_index(
        "idx_ni_tenant_user",
        "nudge_interactions",
        ["tenant_id", "user_id"],
    )

    op.create_index(
        "idx_ni_tenant_type",
        "nudge_interactions",
        ["tenant_id", "nudge_type", sa.text("created_at DESC")],
    )

    # RLS policy: tenant_id = current_setting('app.tenant_id')::uuid
    op.execute(
        "ALTER TABLE nudge_interactions ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY nudge_interactions_tenant_isolation
        ON nudge_interactions
        FOR ALL
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    """Drop nudge_interactions table."""
    op.execute(
        "DROP POLICY IF EXISTS nudge_interactions_tenant_isolation "
        "ON nudge_interactions"
    )
    op.drop_index("idx_ni_tenant_type", table_name="nudge_interactions")
    op.drop_index("idx_ni_tenant_user", table_name="nudge_interactions")
    op.drop_table("nudge_interactions")
