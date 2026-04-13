# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply via:
#   cd backend && uv run python scripts/broker_migration.py
#
# Then stamp:
#   cd backend && uv run alembic stamp 056_broker_tables
# ============================================================

"""Add 6 broker module tables

Revision ID: 056_broker_tables
Revises: 055_add_ai_summary_updated_at
Create Date: 2026-04-11
"""
from typing import Union

from alembic import op

revision: str = "056_broker_tables"
down_revision: Union[str, None] = "055_add_ai_summary_updated_at"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Applied via broker_migration.py (PgBouncer DDL workaround)
    pass


def downgrade() -> None:
    op.drop_table("broker_activities")
    op.drop_table("submission_documents")
    op.drop_table("carrier_quotes")
    op.drop_table("project_coverages")
    op.drop_table("broker_projects")
    op.drop_table("carrier_configs")
