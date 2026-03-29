"""Add email_id FK and resolution metadata columns to tasks table.

Adds 4 columns (email_id, resolved_by, resolution_source_id, resolution_note)
and 2 indexes (idx_tasks_email, idx_tasks_source) to the tasks table.

email_id FK enables idempotency checks (no duplicate tasks per email).
Resolution columns are schema prep for the commitment ledger (Layer B).

Revision ID: 035_email_task_fields
Revises: 034_tasks
Create Date: 2026-03-29

ETL-05 -- schema foundation for email-to-task extraction pipeline.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "035_email_task_fields"
down_revision: Union[str, None] = "034_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns
    op.add_column(
        "tasks",
        sa.Column(
            "email_id",
            postgresql.UUID(),
            sa.ForeignKey("emails.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column("resolved_by", sa.Text(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("resolution_source_id", postgresql.UUID(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )

    # 2. Add indexes
    op.create_index("idx_tasks_email", "tasks", ["email_id"])
    op.create_index(
        "idx_tasks_source", "tasks", ["tenant_id", "user_id", "source"]
    )


def downgrade() -> None:
    # Drop indexes first, then columns
    op.drop_index("idx_tasks_source", table_name="tasks")
    op.drop_index("idx_tasks_email", table_name="tasks")
    op.drop_column("tasks", "resolution_note")
    op.drop_column("tasks", "resolution_source_id")
    op.drop_column("tasks", "resolved_by")
    op.drop_column("tasks", "email_id")
