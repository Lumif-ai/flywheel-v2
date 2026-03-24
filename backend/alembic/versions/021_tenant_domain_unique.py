"""add partial unique index on tenants.domain

Revision ID: 021_tenant_domain_unique
Revises: 020_email_models
Create Date: 2026-03-24

Adds a partial unique index so that non-NULL tenant domains are unique.
Anonymous tenants (domain IS NULL) are unaffected -- NULLs are distinct
in Postgres unique indexes.  This prevents two promoted tenants from
sharing the same company domain.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers
revision: str = "021_tenant_domain_unique"
down_revision: Union[str, None] = "020_email_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial unique index: only non-NULL domains must be unique.
    # NULL domains (anonymous tenants) are allowed to coexist.
    op.execute("""
        CREATE UNIQUE INDEX uq_tenants_domain
            ON tenants (domain)
            WHERE domain IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_tenants_domain;")
