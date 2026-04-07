"""Add user-scoped leads, sender email tracking, and account visibility.

- leads: add owner_id (NOT NULL), replace tenant-only RLS with user-level RLS
- lead_contacts: replace tenant-only RLS with FK-based user isolation
- lead_messages: replace tenant-only RLS with FK-based user isolation, add from_email
- outreach_activities: add from_email
- accounts: add owner_id (nullable) + visibility (default 'team') scaffolding

Revision ID: 041_lead_user_scoping
Revises: 040_create_leads_tables
Create Date: 2026-04-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "041_lead_user_scoping"
down_revision: Union[str, None] = "040_create_leads_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Leads: add owner_id ──────────────────────────────────────────
    op.execute("""
        ALTER TABLE leads ADD COLUMN owner_id UUID;
    """)
    # Backfill existing leads (if any) with the first active user in their tenant
    op.execute("""
        UPDATE leads SET owner_id = (
            SELECT ut.user_id FROM user_tenants ut
            WHERE ut.tenant_id = leads.tenant_id AND ut.active = true
            LIMIT 1
        );
    """)
    op.execute("ALTER TABLE leads ALTER COLUMN owner_id SET NOT NULL;")

    # Replace unique constraint: (tenant, name) → (tenant, owner, name)
    op.execute("ALTER TABLE leads DROP CONSTRAINT uq_lead_tenant_normalized;")
    op.execute("""
        ALTER TABLE leads ADD CONSTRAINT uq_lead_tenant_owner_normalized
            UNIQUE (tenant_id, owner_id, normalized_name);
    """)

    # Add owner index for filtered queries
    op.execute("CREATE INDEX idx_lead_owner ON leads (tenant_id, owner_id);")

    # Replace tenant-only RLS with user-level RLS on leads
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON leads;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON leads;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON leads;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON leads;")
    op.execute("""
        CREATE POLICY user_isolation ON leads
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND owner_id = current_setting('app.user_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND owner_id = current_setting('app.user_id', true)::uuid
            );
    """)

    # ── 2. Lead contacts: FK-based user isolation ───────────────────────
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON lead_contacts;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON lead_contacts;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON lead_contacts;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON lead_contacts;")
    op.execute("""
        CREATE POLICY user_isolation ON lead_contacts
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND lead_id IN (
                    SELECT id FROM leads
                    WHERE owner_id = current_setting('app.user_id', true)::uuid
                )
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND lead_id IN (
                    SELECT id FROM leads
                    WHERE owner_id = current_setting('app.user_id', true)::uuid
                )
            );
    """)

    # ── 3. Lead messages: FK-based user isolation + from_email ──────────
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON lead_messages;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON lead_messages;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON lead_messages;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON lead_messages;")
    op.execute("""
        CREATE POLICY user_isolation ON lead_messages
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND contact_id IN (
                    SELECT lc.id FROM lead_contacts lc
                    JOIN leads l ON l.id = lc.lead_id
                    WHERE l.owner_id = current_setting('app.user_id', true)::uuid
                )
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND contact_id IN (
                    SELECT lc.id FROM lead_contacts lc
                    JOIN leads l ON l.id = lc.lead_id
                    WHERE l.owner_id = current_setting('app.user_id', true)::uuid
                )
            );
    """)

    # Add from_email to lead_messages
    op.execute("ALTER TABLE lead_messages ADD COLUMN from_email TEXT;")

    # ── 4. Outreach activities: add from_email ──────────────────────────
    op.execute("ALTER TABLE outreach_activities ADD COLUMN from_email TEXT;")

    # ── 5. Accounts: visibility scaffolding ─────────────────────────────
    op.execute("ALTER TABLE accounts ADD COLUMN owner_id UUID;")
    op.execute("ALTER TABLE accounts ADD COLUMN visibility TEXT NOT NULL DEFAULT 'team';")
    op.execute(
        "CREATE INDEX idx_account_tenant_visibility ON accounts (tenant_id, visibility);"
    )


def downgrade() -> None:
    # ── Accounts ──
    op.execute("DROP INDEX IF EXISTS idx_account_tenant_visibility;")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS visibility;")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS owner_id;")

    # ── Outreach activities ──
    op.execute("ALTER TABLE outreach_activities DROP COLUMN IF EXISTS from_email;")

    # ── Lead messages: restore tenant-only RLS, drop from_email ──
    op.execute("ALTER TABLE lead_messages DROP COLUMN IF EXISTS from_email;")
    op.execute("DROP POLICY IF EXISTS user_isolation ON lead_messages;")
    for action in ["SELECT", "INSERT", "UPDATE", "DELETE"]:
        if action == "INSERT":
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON lead_messages
                    FOR {action}
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)
        elif action == "UPDATE":
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON lead_messages
                    FOR {action}
                    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)
        else:
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON lead_messages
                    FOR {action}
                    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)

    # ── Lead contacts: restore tenant-only RLS ──
    op.execute("DROP POLICY IF EXISTS user_isolation ON lead_contacts;")
    for action in ["SELECT", "INSERT", "UPDATE", "DELETE"]:
        if action == "INSERT":
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON lead_contacts
                    FOR {action}
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)
        elif action == "UPDATE":
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON lead_contacts
                    FOR {action}
                    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)
        else:
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON lead_contacts
                    FOR {action}
                    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)

    # ── Leads: restore tenant-only RLS, drop owner_id ──
    op.execute("DROP POLICY IF EXISTS user_isolation ON leads;")
    for action in ["SELECT", "INSERT", "UPDATE", "DELETE"]:
        if action == "INSERT":
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON leads
                    FOR {action}
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)
        elif action == "UPDATE":
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON leads
                    FOR {action}
                    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)
        else:
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON leads
                    FOR {action}
                    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)

    op.execute("DROP INDEX IF EXISTS idx_lead_owner;")
    op.execute("ALTER TABLE leads DROP CONSTRAINT IF EXISTS uq_lead_tenant_owner_normalized;")
    op.execute("""
        ALTER TABLE leads ADD CONSTRAINT uq_lead_tenant_normalized
            UNIQUE (tenant_id, normalized_name);
    """)
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS owner_id;")
