# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply in Supabase SQL Editor:
#   ALTER TABLE pipeline_entries
#     ADD COLUMN ai_summary_updated_at TIMESTAMPTZ;
#
# Then stamp:
#   cd backend && alembic stamp 055_add_ai_summary_updated_at
# ============================================================

"""Add ai_summary_updated_at to pipeline_entries

Revision ID: 055_add_ai_summary_updated_at
Revises: 054_library_data_cleanup
Create Date: 2026-04-09
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "055_add_ai_summary_updated_at"
down_revision: Union[str, None] = "054_library_data_cleanup"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "pipeline_entries",
        sa.Column("ai_summary_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pipeline_entries", "ai_summary_updated_at")
