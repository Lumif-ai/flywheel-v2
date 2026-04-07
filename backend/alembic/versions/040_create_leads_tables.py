"""Create leads, lead_contacts, and lead_messages tables for GTM pipeline.

Three tables handle the pre-relationship GTM pipeline:
- leads: company-level prospects (scraped, scored, researched)
- lead_contacts: people at those companies (each with own pipeline stage)
- lead_messages: outreach sequence per contact (connection request, follow-ups)

On reply, leads graduate to the existing accounts/account_contacts/outreach_activities tables.

Revision ID: 040_create_leads_tables
Revises: 039_normalize_fit_tier_values
Create Date: 2026-04-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "040_create_leads_tables"
down_revision: Union[str, None] = "039_normalize_fit_tier_values"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(table: str) -> None:
    """Enable RLS, grant permissions, and create tenant isolation policies."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user;")
    for action in ["SELECT", "INSERT", "UPDATE", "DELETE"]:
        if action == "INSERT":
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON {table}
                    FOR {action}
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)
        elif action == "UPDATE":
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON {table}
                    FOR {action}
                    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)
        else:
            op.execute(f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON {table}
                    FOR {action}
                    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """)


def upgrade() -> None:
    # ── 1. leads table ──
    op.execute("""
        CREATE TABLE leads (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            name            TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            domain          TEXT,
            purpose         TEXT[] NOT NULL DEFAULT '{sales}'::text[],
            fit_score       NUMERIC,
            fit_tier        TEXT,
            fit_rationale   TEXT,
            intel           JSONB NOT NULL DEFAULT '{}'::jsonb,
            source          TEXT NOT NULL,
            campaign        TEXT,
            account_id      UUID REFERENCES accounts(id) ON DELETE SET NULL,
            graduated_at    TIMESTAMP WITH TIME ZONE,
            created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),

            CONSTRAINT uq_lead_tenant_normalized UNIQUE (tenant_id, normalized_name)
        );
    """)
    op.execute("CREATE INDEX idx_lead_tenant_purpose ON leads USING GIN (purpose);")
    op.execute("CREATE INDEX idx_lead_tenant_fit ON leads (tenant_id, fit_tier);")
    op.execute("""
        CREATE INDEX idx_lead_graduated
            ON leads (graduated_at)
            WHERE graduated_at IS NOT NULL;
    """)
    op.execute("""
        CREATE INDEX idx_lead_tenant_campaign
            ON leads (tenant_id, campaign)
            WHERE campaign IS NOT NULL;
    """)
    _enable_rls("leads")

    # ── 2. lead_contacts table ──
    op.execute("""
        CREATE TABLE lead_contacts (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            lead_id         UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            name            TEXT NOT NULL,
            email           TEXT,
            title           TEXT,
            linkedin_url    TEXT,
            role            TEXT,
            pipeline_stage  TEXT NOT NULL DEFAULT 'scraped',
            notes           TEXT,
            created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX idx_lead_contact_lead ON lead_contacts (lead_id);")
    op.execute("CREATE INDEX idx_lead_contact_tenant_stage ON lead_contacts (tenant_id, pipeline_stage);")
    op.execute("""
        CREATE UNIQUE INDEX uq_lead_contact_email
            ON lead_contacts (tenant_id, lead_id, email)
            WHERE email IS NOT NULL;
    """)
    _enable_rls("lead_contacts")

    # ── 3. lead_messages table ──
    op.execute("""
        CREATE TABLE lead_messages (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            contact_id      UUID NOT NULL REFERENCES lead_contacts(id) ON DELETE CASCADE,
            step_number     INTEGER NOT NULL,
            channel         TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'drafted',
            subject         TEXT,
            body            TEXT,
            drafted_at      TIMESTAMP WITH TIME ZONE,
            sent_at         TIMESTAMP WITH TIME ZONE,
            replied_at      TIMESTAMP WITH TIME ZONE,
            metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),

            CONSTRAINT uq_lead_message_step UNIQUE (contact_id, step_number, channel)
        );
    """)
    op.execute("CREATE INDEX idx_lead_message_contact ON lead_messages (contact_id);")
    op.execute("CREATE INDEX idx_lead_message_tenant_status ON lead_messages (tenant_id, status);")
    _enable_rls("lead_messages")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lead_messages CASCADE;")
    op.execute("DROP TABLE IF EXISTS lead_contacts CASCADE;")
    op.execute("DROP TABLE IF EXISTS leads CASCADE;")
