# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Alembic's multi-statement DDL transactions are silently rolled
# back by PgBouncer. This migration file exists for documentation
# and downgrade support ONLY.
#
# To apply: Run the ALTER TABLE statement directly in Supabase
# SQL Editor (Dashboard > SQL Editor), then run:
#   cd backend && alembic stamp 052_add_last_briefing_visit
#
# Alternatively, apply via session.execute + session.commit:
#   async with factory() as session:
#       await session.execute(text("ALTER TABLE profiles ADD COLUMN last_briefing_visit TIMESTAMPTZ"))
#       await session.commit()
#   Then: alembic stamp 052_add_last_briefing_visit
# ============================================================

"""Add last_briefing_visit column to profiles.

Revision ID: 052_add_last_briefing_visit
Revises: 051_create_waitlist_table
Create Date: 2026-04-08
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "052_add_last_briefing_visit"
down_revision: Union[str, None] = "051_create_waitlist_table"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("last_briefing_visit", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "last_briefing_visit")
