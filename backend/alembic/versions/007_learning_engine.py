"""learning engine: flag columns + suggestion dismissals

Revision ID: 007_learning_engine
Revises: 006_enable_realtime
Create Date: 2026-03-20

Adds flag_reason and flag_related_id columns to context_entries for
contradiction tracking, and creates the suggestion_dismissals table
for dismissal-with-expiry of proactive suggestions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = "007_learning_engine"
down_revision: Union[str, Sequence[str]] = "006_enable_realtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add flag columns to context_entries and create suggestion_dismissals."""

    # --- context_entries: two new nullable columns ---
    op.add_column(
        "context_entries",
        sa.Column("flag_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "context_entries",
        sa.Column(
            "flag_related_id",
            sa.Uuid(),
            sa.ForeignKey("context_entries.id"),
            nullable=True,
        ),
    )

    # --- suggestion_dismissals table ---
    op.create_table(
        "suggestion_dismissals",
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
        sa.Column("suggestion_type", sa.Text(), nullable=False),
        sa.Column("suggestion_key", sa.Text(), nullable=False),
        sa.Column(
            "dismissed_at",
            TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "expires_at",
            TIMESTAMP(timezone=True),
            server_default=sa.text("now() + interval '7 days'"),
        ),
    )

    # Enable RLS with tenant isolation (same pattern as other tables)
    op.execute(
        "ALTER TABLE suggestion_dismissals ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation ON suggestion_dismissals
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    # Composite index for fast dismissal lookups
    op.create_index(
        "idx_suggestion_dismissals_lookup",
        "suggestion_dismissals",
        ["tenant_id", "user_id", "suggestion_type", "suggestion_key"],
    )


def downgrade() -> None:
    """Drop suggestion_dismissals table and flag columns."""
    op.drop_index("idx_suggestion_dismissals_lookup", "suggestion_dismissals")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON suggestion_dismissals")
    op.drop_table("suggestion_dismissals")

    op.drop_column("context_entries", "flag_related_id")
    op.drop_column("context_entries", "flag_reason")
