"""link tenants to companies via company_id FK, drop domain unique index

Revision ID: 023_tenant_company_link
Revises: 022_companies_table
Create Date: 2026-03-25

Adds company_id FK (nullable) on tenants pointing to companies.id so the
promote flow can find/create tenants by company rather than by domain.
Drops the Phase 46-01 partial unique index on tenants.domain since domain
now lives on the companies table.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "023_tenant_company_link"
down_revision: Union[str, None] = "022_companies_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add company_id FK to tenants (nullable -- anonymous tenants have no company yet)
    op.add_column("tenants", sa.Column("company_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_tenants_company", "tenants", "companies", ["company_id"], ["id"]
    )
    op.create_index("idx_tenants_company", "tenants", ["company_id"])

    # Drop the Phase 46-01 domain unique index (domain now lives on companies table)
    try:
        op.drop_index("uq_tenants_domain", table_name="tenants")
    except Exception:
        pass  # Index may not exist in some environments


def downgrade() -> None:
    op.drop_index("idx_tenants_company", table_name="tenants")
    op.drop_constraint("fk_tenants_company", "tenants", type_="foreignkey")
    op.drop_column("tenants", "company_id")
