# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply via Supabase SQL Editor or a single-statement apply script,
# then stamp:
#   cd backend && uv run alembic stamp 067_skill_execution_telemetry
# ============================================================

"""Create skill_execution_telemetry table

Revision ID: 067_skill_execution_telemetry
Revises: 066_cc_executable
Create Date: 2026-04-21
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "067_skill_execution_telemetry"
down_revision: Union[str, None] = "066_cc_executable"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS skill_execution_telemetry (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            skill_name TEXT NOT NULL,
            execution_path TEXT NOT NULL,
            caller_type TEXT NOT NULL DEFAULT 'mcp',
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_skill_telemetry_created_skill
            ON skill_execution_telemetry (created_at, skill_name)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_skill_telemetry_created_skill")
    op.execute("DROP TABLE IF EXISTS skill_execution_telemetry")
