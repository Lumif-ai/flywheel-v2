"""add meeting_classifications table for pattern learning

Revision ID: 014_meeting_classification
Revises: 013_sub_threads
Create Date: 2026-03-23

Hand-written migration -- creates meeting_classifications table for tracking
user classification decisions and enabling domain-based pattern learning.
After 3+ classifications from the same email domain, future meetings auto-classify.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "014_meeting_classification"
down_revision: Union[str, Sequence[str]] = "013_sub_threads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create meeting_classifications table with RLS policy."""

    op.create_table(
        "meeting_classifications",
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
        sa.Column(
            "work_item_id",
            sa.Uuid(),
            sa.ForeignKey("work_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stream_id",
            sa.Uuid(),
            sa.ForeignKey("work_streams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email_domain", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # Index for fast domain pattern lookups
    op.create_index(
        "idx_mc_tenant_domain",
        "meeting_classifications",
        ["tenant_id", "email_domain"],
    )

    # RLS policy: tenant_id = current_setting('app.tenant_id')::uuid
    op.execute(
        "ALTER TABLE meeting_classifications ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY meeting_classifications_tenant_isolation
        ON meeting_classifications
        FOR ALL
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    """Drop meeting_classifications table."""
    op.execute(
        "DROP POLICY IF EXISTS meeting_classifications_tenant_isolation "
        "ON meeting_classifications"
    )
    op.drop_index("idx_mc_tenant_domain", table_name="meeting_classifications")
    op.drop_table("meeting_classifications")
