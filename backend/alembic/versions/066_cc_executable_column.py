# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply via Supabase SQL Editor or a single-statement apply script,
# then stamp:
#   cd backend && uv run alembic stamp 066_cc_executable
# ============================================================

"""Add cc_executable column to skill_definitions

Revision ID: 066_cc_executable
Revises: 065_depends_on_column
Create Date: 2026-04-21
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "066_cc_executable"
down_revision: Union[str, None] = "065_depends_on_column"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE skill_definitions "
        "ADD COLUMN IF NOT EXISTS cc_executable BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE skill_definitions DROP COLUMN IF EXISTS cc_executable")
