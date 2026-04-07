"""Add accounts visibility RLS policy and lead_messages step_number CHECK.

- accounts: add RLS policy that enforces visibility (team=all, personal=owner only)
- lead_messages: add CHECK constraint step_number >= 1

Revision ID: 042_accounts_visibility_rls_and_constraints
Revises: 041_lead_user_scoping
Create Date: 2026-04-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "042_acct_vis_rls"
down_revision: Union[str, None] = "041_lead_user_scoping"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Accounts: visibility-aware RLS policy ───────────────────────
    # Enable RLS if not already (idempotent)
    op.execute("ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;")

    # Drop any existing tenant-only policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON accounts;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON accounts;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON accounts;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON accounts;")
    op.execute("DROP POLICY IF EXISTS visibility_isolation ON accounts;")

    # New policy: tenant members see team accounts + their own personal accounts
    op.execute("""
        CREATE POLICY visibility_isolation ON accounts
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND (
                    visibility = 'team'
                    OR owner_id = current_setting('app.user_id', true)::uuid
                )
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND (
                    visibility = 'team'
                    OR owner_id = current_setting('app.user_id', true)::uuid
                )
            );
    """)

    # ── 2. Lead messages: CHECK constraint on step_number ──────────────
    op.execute("""
        ALTER TABLE lead_messages
            ADD CONSTRAINT chk_lead_message_step_positive
            CHECK (step_number >= 1);
    """)


def downgrade() -> None:
    # ── Lead messages ──
    op.execute(
        "ALTER TABLE lead_messages DROP CONSTRAINT IF EXISTS chk_lead_message_step_positive;"
    )

    # ── Accounts: remove visibility RLS, restore basic tenant isolation ──
    op.execute("DROP POLICY IF EXISTS visibility_isolation ON accounts;")
    op.execute("""
        CREATE POLICY tenant_isolation_select ON accounts
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON accounts
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON accounts
            FOR UPDATE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON accounts
            FOR DELETE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
