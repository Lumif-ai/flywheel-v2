"""add shared companies table for cross-tenant cache

Revision ID: 022_companies_table
Revises: 021_tenant_domain_unique
Create Date: 2026-03-25

Creates a global (non-tenant-scoped) companies table with a unique domain
constraint. Stores structured intel as JSONB so cache lookups are a simple
domain query with zero tenant involvement.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "022_companies_table"
down_revision: Union[str, None] = "021_tenant_domain_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("intel", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("crawled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_companies_domain", "companies", ["domain"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_companies_domain", table_name="companies")
    op.drop_table("companies")
