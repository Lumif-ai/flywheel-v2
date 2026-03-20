"""fix suggestion_dismissals RLS policy to use app.tenant_id

Revision ID: 008_fix_dismissal_rls
Revises: 007_learning_engine
Create Date: 2026-03-20

Corrective migration for databases where 007 was already applied with the
wrong config key (app.current_tenant_id). Drops and recreates the
tenant_isolation policy on suggestion_dismissals using app.tenant_id,
matching every other table in the system.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_fix_dismissal_rls"
down_revision: Union[str, Sequence[str]] = "007_learning_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace wrong RLS policy with corrected app.tenant_id version."""
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation ON suggestion_dismissals"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation ON suggestion_dismissals
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    """Restore old (wrong) policy for rollback fidelity."""
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation ON suggestion_dismissals"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation ON suggestion_dismissals
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )
