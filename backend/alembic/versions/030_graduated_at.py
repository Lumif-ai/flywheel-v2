"""Add graduated_at column to accounts for relationship partition predicate.

Relationships surface requires graduated_at IS NOT NULL to distinguish
graduated accounts from pipeline prospects. This migration adds the column
with a partial index for efficient filtered queries.

Revision ID: 030_grad_at
Revises: 029_status_phase_a
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "030_grad_at"
down_revision: Union[str, None] = "029_status_phase_a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("graduated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_account_graduated_at",
        "accounts",
        ["graduated_at"],
        postgresql_where=sa.text("graduated_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_account_graduated_at",
        table_name="accounts",
        postgresql_where=sa.text("graduated_at IS NOT NULL"),
    )
    op.drop_column("accounts", "graduated_at")
