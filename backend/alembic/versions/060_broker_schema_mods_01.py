# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply via:
#   cd backend && uv run python scripts/broker_schema_mods_01.py
#
# Alembic stamp is applied by the script itself via SQLAlchemy UPDATE.
# ============================================================

"""Add columns to 5 existing broker tables (additive schema modifications)

Revision ID: 060_broker_schema_mods_01
Revises: 059_broker_data_model_tables
Create Date: 2026-04-15
"""
from typing import Union

from alembic import op

revision: str = "060_broker_schema_mods_01"
down_revision: Union[str, None] = "059_broker_data_model_tables"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Applied via broker_schema_mods_01.py (PgBouncer DDL workaround)
    pass


def downgrade() -> None:
    # broker_projects
    op.drop_column("broker_projects", "updated_by_user_id")
    op.drop_column("broker_projects", "created_by_user_id")
    op.drop_column("broker_projects", "context_entity_id")
    op.drop_column("broker_projects", "client_id")
    # carrier_configs
    op.drop_column("carrier_configs", "updated_by_user_id")
    op.drop_column("carrier_configs", "created_by_user_id")
    op.drop_column("carrier_configs", "context_entity_id")
    # carrier_quotes
    op.drop_column("carrier_quotes", "updated_by_user_id")
    op.drop_column("carrier_quotes", "created_by_user_id")
    # project_coverages
    op.drop_column("project_coverages", "updated_by_user_id")
    op.drop_column("project_coverages", "created_by_user_id")
    op.drop_column("project_coverages", "updated_at")
    # submission_documents
    op.drop_column("submission_documents", "created_by_user_id")
    op.drop_column("submission_documents", "updated_at")
