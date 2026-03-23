"""add density_snapshots table for weekly growth tracking

Revision ID: 015_density_snapshots
Revises: 014_meeting_classification
Create Date: 2026-03-23

Hand-written migration -- creates density_snapshots table for tracking
weekly density score history per work stream. Enables week-over-week
growth visualization with source breakdown and change highlights.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "015_density_snapshots"
down_revision: Union[str, Sequence[str]] = "014_meeting_classification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create density_snapshots table with RLS policy."""

    op.create_table(
        "density_snapshots",
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
            "stream_id",
            sa.Uuid(),
            sa.ForeignKey("work_streams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("density_score", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "details",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # Composite index for fast lookups
    op.create_index(
        "idx_ds_stream_week",
        "density_snapshots",
        ["stream_id", "week_start"],
    )

    # Unique constraint: one snapshot per stream per week
    op.create_unique_constraint(
        "uq_ds_stream_week",
        "density_snapshots",
        ["stream_id", "week_start"],
    )

    # RLS policy: tenant_id = current_setting('app.tenant_id')::uuid
    op.execute(
        "ALTER TABLE density_snapshots ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY density_snapshots_tenant_isolation
        ON density_snapshots
        FOR ALL
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    """Drop density_snapshots table."""
    op.execute(
        "DROP POLICY IF EXISTS density_snapshots_tenant_isolation "
        "ON density_snapshots"
    )
    op.drop_constraint("uq_ds_stream_week", "density_snapshots")
    op.drop_index("idx_ds_stream_week", table_name="density_snapshots")
    op.drop_table("density_snapshots")
