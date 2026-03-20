"""add integrations table

Revision ID: 005_add_integrations
Revises: 004_add_invites
Create Date: 2026-03-20

Adds the integrations table for external service connections (Google Calendar,
etc.). Enables RLS for tenant isolation. Includes updated_at trigger.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_add_integrations'
down_revision: Union[str, Sequence[str]] = '004_add_invites'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create integrations table with RLS and updated_at trigger."""
    op.create_table(
        'integrations',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), server_default='connected', nullable=False),
        sa.Column('credentials_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('settings', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('last_synced_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Enable RLS
    op.execute("ALTER TABLE integrations ENABLE ROW LEVEL SECURITY")

    # RLS policy: tenant members can manage their tenant's integrations
    op.execute("""
        CREATE POLICY integrations_tenant_isolation ON integrations
        FOR ALL
        USING (current_setting('app.tenant_id', true)::uuid = tenant_id)
    """)

    # updated_at trigger (same PL/pgSQL function pattern as Phase 16 migrations)
    op.execute("""
        CREATE TRIGGER set_integrations_updated_at
        BEFORE UPDATE ON integrations
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at()
    """)

    # Verify RLS is enabled
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='integrations' AND relrowsecurity) "
        "THEN RAISE EXCEPTION 'RLS not enabled on table: integrations'; "
        "END IF; END $$;"
    )


def downgrade() -> None:
    """Drop integrations table and associated objects."""
    op.execute("DROP TRIGGER IF EXISTS set_integrations_updated_at ON integrations")
    op.execute("DROP POLICY IF EXISTS integrations_tenant_isolation ON integrations")
    op.drop_table('integrations')
