"""Retarget FK references from accounts to pipeline_entries.

Adds pipeline_entry_id column to meetings, tasks, and context_entries,
populates from existing account_id (UUID-preserved, so direct copy),
and creates indexes.

PgBouncer NOTE: When applying via Supabase SQL Editor, run each DDL
statement as a separate execution. DML (UPDATE) can share a transaction
with adjacent DML but NOT with DDL.

Revision ID: 046_fk_retarget_
Revises: 045_data_mig_pipe
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "046_fk_retarget_"
down_revision: Union[str, None] = "045_data_mig_pipe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Meetings FK retarget ────────────────────────────────────────

    # DDL 1: Add column (separate execution for PgBouncer)
    op.execute(text(
        "ALTER TABLE meetings "
        "ADD COLUMN pipeline_entry_id UUID "
        "REFERENCES pipeline_entries(id) ON DELETE SET NULL"
    ))

    # DML: Populate from account_id (UUID preserved, so direct copy)
    op.execute(text(
        "UPDATE meetings SET pipeline_entry_id = account_id "
        "WHERE account_id IS NOT NULL"
    ))

    # DDL 2: Create index (separate execution for PgBouncer)
    op.execute(text(
        "CREATE INDEX idx_meetings_pipeline_entry "
        "ON meetings (pipeline_entry_id, meeting_date DESC) "
        "WHERE deleted_at IS NULL"
    ))

    # ── Tasks FK retarget ───────────────────────────────────────────

    # DDL 3: Add column (separate execution for PgBouncer)
    op.execute(text(
        "ALTER TABLE tasks "
        "ADD COLUMN pipeline_entry_id UUID "
        "REFERENCES pipeline_entries(id) ON DELETE SET NULL"
    ))

    # DML: Populate from account_id
    op.execute(text(
        "UPDATE tasks SET pipeline_entry_id = account_id "
        "WHERE account_id IS NOT NULL"
    ))

    # DDL 4: Create index (separate execution for PgBouncer)
    op.execute(text(
        "CREATE INDEX idx_tasks_pipeline_entry "
        "ON tasks (pipeline_entry_id)"
    ))

    # ── Context entries FK retarget ─────────────────────────────────

    # DDL 5: Add column (separate execution for PgBouncer)
    op.execute(text(
        "ALTER TABLE context_entries "
        "ADD COLUMN pipeline_entry_id UUID "
        "REFERENCES pipeline_entries(id) ON DELETE SET NULL"
    ))

    # DML: Populate from account_id
    op.execute(text(
        "UPDATE context_entries SET pipeline_entry_id = account_id "
        "WHERE account_id IS NOT NULL"
    ))

    # DDL 6: Create index (separate execution for PgBouncer)
    op.execute(text(
        "CREATE INDEX idx_context_entries_pipeline_entry "
        "ON context_entries (pipeline_entry_id)"
    ))


def downgrade() -> None:
    # Reverse in order — each DDL as separate execution for PgBouncer

    # Context entries
    op.execute(text("DROP INDEX IF EXISTS idx_context_entries_pipeline_entry"))
    op.execute(text(
        "ALTER TABLE context_entries DROP COLUMN IF EXISTS pipeline_entry_id"
    ))

    # Tasks
    op.execute(text("DROP INDEX IF EXISTS idx_tasks_pipeline_entry"))
    op.execute(text(
        "ALTER TABLE tasks DROP COLUMN IF EXISTS pipeline_entry_id"
    ))

    # Meetings
    op.execute(text("DROP INDEX IF EXISTS idx_meetings_pipeline_entry"))
    op.execute(text(
        "ALTER TABLE meetings DROP COLUMN IF EXISTS pipeline_entry_id"
    ))
