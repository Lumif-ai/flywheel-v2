"""Add next_action_date and next_action_note to pipeline_entries.

Revision ID: 048_next_action
Revises: 047_legacy_rename
Create Date: 2026-04-06
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "048_next_action"
down_revision: Union[str, None] = "047_legacy_rename"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # NOTE: On Supabase with PgBouncer, run each ALTER TABLE as a separate
    # commit or via Supabase SQL Editor, then `alembic stamp 048_next_action`.
    op.add_column(
        "pipeline_entries",
        sa.Column("next_action_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "pipeline_entries",
        sa.Column("next_action_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pipeline_entries", "next_action_note")
    op.drop_column("pipeline_entries", "next_action_date")
