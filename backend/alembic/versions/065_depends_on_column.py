# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply via:
#   cd backend && uv run python scripts/apply_065_depends_on_column.py
#
# Then stamp (the apply script does this for you):
#   cd backend && uv run alembic stamp 065_depends_on_column
# ============================================================

"""Add depends_on ARRAY(Text) column to skill_definitions for v22.0 fanout

Revision ID: 065_depends_on_column
Revises: 064_skill_assets_table
Create Date: 2026-04-18
"""
from typing import Union

from alembic import op


revision: str = "065_depends_on_column"
down_revision: Union[str, None] = "064_skill_assets_table"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Additive column (Phase 150 Plan 01 backing for MCP fanout).
    # ARRAY(Text) not JSONB — avoids the "never .append on a JSONB-bound list"
    # SQLAlchemy mutation gotcha memorialized in saved user memory.
    op.execute(
        "ALTER TABLE skill_definitions "
        "ADD COLUMN IF NOT EXISTS depends_on TEXT[] NOT NULL DEFAULT '{}'::text[]"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE skill_definitions DROP COLUMN IF EXISTS depends_on")
