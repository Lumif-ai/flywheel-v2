# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply via:
#   cd backend && uv run python scripts/broker_data_model_migration.py
#
# Then stamp:
#   cd backend && uv run alembic stamp 059_broker_data_model_tables
# ============================================================

"""Add 6 broker data model v2 tables

Revision ID: 059_broker_data_model_tables
Revises: 058_add_approval_status
Create Date: 2026-04-14
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "059_broker_data_model_tables"
down_revision: Union[str, None] = "058_add_approval_status"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Applied via broker_data_model_migration.py (PgBouncer DDL workaround)
    pass


def downgrade() -> None:
    op.drop_table("broker_project_emails")
    op.drop_table("solicitation_drafts")
    op.drop_table("broker_recommendations")
    op.drop_table("carrier_contacts")
    op.drop_table("broker_client_contacts")
    op.drop_table("broker_clients")
