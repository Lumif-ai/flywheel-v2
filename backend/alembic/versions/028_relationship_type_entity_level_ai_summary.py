"""Add relationship_type, entity_level, ai_summary columns to accounts.

Adds four columns to the accounts table to support relationship surface
categorization, entity-level filtering, and AI synthesis.

Revision ID: 028_relationship_type_entity_level_ai_summary
Revises: 027_crm_tables
Create Date: 2026-03-27

DM-01 -- relationship_type text[] with GIN index (multi-label per account)
DM-02 -- entity_level text (company | person) with default 'company'
DM-04 -- ai_summary text nullable + ai_summary_updated_at timestamptz nullable
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers, used by Alembic.
revision: str = "028_acct_ext"
down_revision: Union[str, None] = "027_crm_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DM-01: relationship_type text[] — multi-label, NOT NULL, default {prospect}
    # GIN index ships in the same migration per architecture decision.
    op.add_column(
        "accounts",
        sa.Column(
            "relationship_type",
            ARRAY(sa.Text()),
            server_default=sa.text("'{prospect}'::text[]"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_account_relationship_type",
        "accounts",
        ["relationship_type"],
        postgresql_using="gin",
    )

    # DM-02: entity_level text — 'company' | 'person', NOT NULL, default 'company'
    op.add_column(
        "accounts",
        sa.Column(
            "entity_level",
            sa.Text(),
            server_default=sa.text("'company'"),
            nullable=False,
        ),
    )

    # DM-04: ai_summary + ai_summary_updated_at — nullable, set only by AI synthesis
    op.add_column(
        "accounts",
        sa.Column("ai_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "ai_summary_updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("accounts", "ai_summary_updated_at")
    op.drop_column("accounts", "ai_summary")
    op.drop_column("accounts", "entity_level")
    op.drop_index("idx_account_relationship_type", table_name="accounts")
    op.drop_column("accounts", "relationship_type")
