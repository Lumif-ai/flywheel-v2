# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply via:
#   cd backend && uv run python scripts/apply_064_skill_assets_table.py
#
# Then stamp (the apply script does this for you):
#   cd backend && uv run alembic stamp 064_skill_assets_table
# ============================================================

"""Create skill_assets table for v22.0 skill bundle storage

Revision ID: 064_skill_assets_table
Revises: 063_skill_protected_default
Create Date: 2026-04-17
"""
from typing import Union

from alembic import op


revision: str = "064_skill_assets_table"
down_revision: Union[str, None] = "063_skill_protected_default"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # One op.execute per DDL statement so the apply script can commit
    # each independently (Supabase PgBouncer rolls back multi-DDL txns).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS skill_assets (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            skill_id          UUID NOT NULL REFERENCES skill_definitions(id) ON DELETE CASCADE,
            bundle            BYTEA NOT NULL,
            bundle_sha256     TEXT NOT NULL,
            bundle_size_bytes INTEGER NOT NULL CHECK (bundle_size_bytes >= 0),
            bundle_format     TEXT NOT NULL DEFAULT 'zip',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_skill_assets_skill_id
            ON skill_assets (skill_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_skill_assets_bundle_sha256
            ON skill_assets (bundle_sha256)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_skill_assets_bundle_sha256")
    op.execute("DROP INDEX IF EXISTS uq_skill_assets_skill_id")
    op.execute("DROP TABLE IF EXISTS skill_assets")
