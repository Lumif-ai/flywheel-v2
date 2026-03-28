"""Create tasks table with user-level RLS.

Adds the tasks table for tracking commitments extracted from meetings.
Tasks are personal (user-level isolation, NOT split-visibility) — each
user sees only their own tasks.

Revision ID: 034_tasks
Revises: 033_unify_meetings
Create Date: 2026-03-28

TASK-01 -- tasks data model foundation for meeting-to-task extraction pipeline.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "034_tasks"
down_revision: Union[str, None] = "033_unify_meetings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create tasks table (20 columns)
    op.create_table(
        "tasks",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("commitment_direction", sa.Text(), nullable=False),
        sa.Column("suggested_skill", sa.Text(), nullable=True),
        sa.Column("skill_context", JSONB(), nullable=True),
        sa.Column("trust_level", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'detected'"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Text(),
            server_default=sa.text("'medium'"),
            nullable=False,
        ),
        sa.Column("due_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(
            ["meeting_id"], ["meetings.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Create indexes
    # Index 1: primary lookup — user's tasks by status
    op.create_index(
        "idx_tasks_user_status",
        "tasks",
        ["tenant_id", "user_id", "status"],
    )
    # Index 2: due date lookup — open tasks with due dates
    op.create_index(
        "idx_tasks_due",
        "tasks",
        ["tenant_id", "user_id", "due_date"],
        postgresql_where=sa.text(
            "due_date IS NOT NULL AND status NOT IN ('done', 'dismissed')"
        ),
    )
    # Index 3: meeting lookup — find tasks for a given meeting
    op.create_index(
        "idx_tasks_meeting",
        "tasks",
        ["meeting_id"],
    )

    # 3. Enable RLS
    op.execute("ALTER TABLE tasks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tasks FORCE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tasks TO app_user")

    # 4. User-level isolation (tasks are personal, NOT split-visibility)
    op.execute("""
        CREATE POLICY tasks_user_isolation ON tasks
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tasks_user_isolation ON tasks")
    op.drop_index("idx_tasks_meeting", table_name="tasks")
    op.drop_index("idx_tasks_due", table_name="tasks")
    op.drop_index("idx_tasks_user_status", table_name="tasks")
    op.drop_table("tasks")
