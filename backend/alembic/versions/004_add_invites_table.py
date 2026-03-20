"""add invites table

Revision ID: 004_add_invites
Revises: 003
Create Date: 2026-03-20

Adds the invites table for team invite flow with SHA-256 token hashing
and 7-day default expiry. Enables RLS for tenant isolation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_add_invites'
down_revision: Union[str, Sequence[str]] = '003_fts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create invites table with RLS."""
    op.create_table(
        'invites',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('invited_by', sa.Uuid(), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('role', sa.Text(), server_default='member', nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('accepted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('expires_at', postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text("now() + interval '7 days'"), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Enable RLS
    op.execute("ALTER TABLE invites ENABLE ROW LEVEL SECURITY")

    # RLS policy: tenant members can see invites for their tenant
    op.execute("""
        CREATE POLICY invites_tenant_isolation ON invites
        FOR ALL
        USING (current_setting('app.tenant_id', true)::uuid = tenant_id)
    """)

    # Verify RLS is enabled
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='invites' AND relrowsecurity) "
        "THEN RAISE EXCEPTION 'RLS not enabled on table: invites'; "
        "END IF; END $$;"
    )


def downgrade() -> None:
    """Drop invites table."""
    op.execute("DROP POLICY IF EXISTS invites_tenant_isolation ON invites")
    op.drop_table('invites')
