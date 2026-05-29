# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Do NOT run via `alembic upgrade`. PgBouncer silently rolls back
# multi-statement DDL transactions.
#
# Apply these statements individually in Supabase SQL Editor:
#   ALTER TABLE skill_definitions ALTER COLUMN protected SET DEFAULT false;
#   UPDATE skill_definitions SET protected = false;
#
# Then stamp:
#   cd backend && uv run alembic stamp 062_skill_protected_default_false
# ============================================================

"""Flip skill_definitions.protected default to false (Claude Code as brain)

Phase 95 set protected=true fail-closed, which trapped every skill on the
server-side BYOK execution path. Platform architecture says the opposite:
backend should make no LLM calls when CC is the caller. Flipping default
to false + bulk-setting existing rows restores the intended flow.

Revision ID: 063_skill_protected_default
Revises: 062_broker_schema_mods_03
Create Date: 2026-04-17
"""
from typing import Union

from alembic import op

revision: str = "063_skill_protected_default"
down_revision: Union[str, None] = "062_broker_schema_mods_03"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE skill_definitions ALTER COLUMN protected SET DEFAULT false")
    op.execute("UPDATE skill_definitions SET protected = false")


def downgrade() -> None:
    op.execute("ALTER TABLE skill_definitions ALTER COLUMN protected SET DEFAULT true")
    op.execute("UPDATE skill_definitions SET protected = true")
