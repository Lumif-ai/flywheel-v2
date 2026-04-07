"""Add protected boolean column to skill_definitions.

NOTE: Due to Supabase PgBouncer DDL rollback issue, apply these statements
individually via Supabase SQL Editor, then run:
    alembic stamp 050_add_skill_protected

Revision ID: 050_add_skill_protected
Revises: 049_saved_views
Create Date: 2026-04-07
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "050_add_skill_protected"
down_revision: Union[str, None] = "049_saved_views"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # NOTE: On Supabase with PgBouncer, run each statement separately via
    # Supabase SQL Editor or a one-off script, then `alembic stamp 050_add_skill_protected`.
    #
    # DDL statements to run individually:
    #
    # 1. Add protected column (default TRUE = fail closed)
    # ALTER TABLE skill_definitions ADD COLUMN protected BOOLEAN NOT NULL DEFAULT TRUE;
    #
    # 2. Partial index for efficient lookup of protected skills
    # CREATE INDEX idx_skill_defs_protected ON skill_definitions (protected) WHERE protected = true;

    op.add_column(
        "skill_definitions",
        sa.Column(
            "protected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index(
        "idx_skill_defs_protected",
        "skill_definitions",
        ["protected"],
        postgresql_where=sa.text("protected = true"),
    )


def downgrade() -> None:
    op.drop_index("idx_skill_defs_protected", table_name="skill_definitions")
    op.drop_column("skill_definitions", "protected")
