# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply each statement individually in Supabase SQL Editor:
#   ALTER TABLE broker_projects ADD COLUMN IF NOT EXISTS approval_status TEXT DEFAULT 'draft';
#   CREATE INDEX IF NOT EXISTS ix_broker_projects_tenant_status_approval ON broker_projects (tenant_id, status, approval_status);
#
# Then stamp:
#   cd backend && uv run alembic stamp 058_add_approval_status
# ============================================================

"""Add approval_status column and composite index to broker_projects

Revision ID: 058_add_approval_status
Revises: 057_carrier_quote_draft_columns
Create Date: 2026-04-14
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "058_add_approval_status"
down_revision: Union[str, None] = "057_carrier_quote_draft_columns"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("broker_projects", sa.Column("approval_status", sa.Text(), server_default="draft"))
    op.create_index(
        "ix_broker_projects_tenant_status_approval",
        "broker_projects",
        ["tenant_id", "status", "approval_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_broker_projects_tenant_status_approval", table_name="broker_projects")
    op.drop_column("broker_projects", "approval_status")
