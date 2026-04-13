# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply each statement individually in Supabase SQL Editor:
#   ALTER TABLE carrier_quotes ADD COLUMN IF NOT EXISTS draft_subject TEXT;
#   ALTER TABLE carrier_quotes ADD COLUMN IF NOT EXISTS draft_body TEXT;
#   ALTER TABLE carrier_quotes ADD COLUMN IF NOT EXISTS draft_status TEXT;
#
# Then stamp:
#   cd backend && uv run alembic stamp 057_carrier_quote_draft_columns
# ============================================================

"""Add solicitation draft columns to carrier_quotes

Revision ID: 057_carrier_quote_draft_columns
Revises: 056_broker_tables
Create Date: 2026-04-11
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "057_carrier_quote_draft_columns"
down_revision: Union[str, None] = "056_broker_tables"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("carrier_quotes", sa.Column("draft_subject", sa.Text(), nullable=True))
    op.add_column("carrier_quotes", sa.Column("draft_body", sa.Text(), nullable=True))
    op.add_column("carrier_quotes", sa.Column("draft_status", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("carrier_quotes", "draft_status")
    op.drop_column("carrier_quotes", "draft_body")
    op.drop_column("carrier_quotes", "draft_subject")
