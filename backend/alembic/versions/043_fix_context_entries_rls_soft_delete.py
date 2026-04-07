"""Remove deleted_at IS NULL from context_entries RLS policies.

The SELECT and UPDATE policies included deleted_at IS NULL, which made
soft-delete operations impossible under RLS (the updated row with
deleted_at set to a timestamp would fail the policy check). All app-layer
queries already filter deleted_at IS NULL explicitly, so removing it from
RLS doesn't change read behavior.

Revision ID: 043_fix_context_entries_rls_soft_delete
Revises: 042_accounts_visibility_rls_and_constraints
Create Date: 2026-04-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "043_ctx_rls_softdel"
down_revision: Union[str, None] = "042_acct_vis_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop and recreate SELECT policy without deleted_at filter
    op.execute("DROP POLICY IF EXISTS context_read ON context_entries;")
    op.execute("""
        CREATE POLICY context_read ON context_entries
            FOR SELECT
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND (
                    visibility IN ('shared', 'team')
                    OR (visibility = 'private'
                        AND user_id = current_setting('app.user_id', true)::uuid)
                )
            )
    """)

    # Drop and recreate UPDATE policy without deleted_at filter in USING
    op.execute("DROP POLICY IF EXISTS context_update ON context_entries;")
    op.execute("""
        CREATE POLICY context_update ON context_entries
            FOR UPDATE
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
    """)


def downgrade() -> None:
    # Restore original policies with deleted_at IS NULL
    op.execute("DROP POLICY IF EXISTS context_read ON context_entries;")
    op.execute("""
        CREATE POLICY context_read ON context_entries
            FOR SELECT
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND deleted_at IS NULL
                AND (
                    visibility IN ('shared', 'team')
                    OR (visibility = 'private'
                        AND user_id = current_setting('app.user_id', true)::uuid)
                )
            )
    """)

    op.execute("DROP POLICY IF EXISTS context_update ON context_entries;")
    op.execute("""
        CREATE POLICY context_update ON context_entries
            FOR UPDATE
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND deleted_at IS NULL
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
    """)
