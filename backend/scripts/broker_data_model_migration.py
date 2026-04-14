"""Broker Data Model v2 DDL migration — Supabase PgBouncer workaround.

Each DDL statement runs as its own committed transaction to avoid
PgBouncer silently rolling back multi-statement DDL.

Usage:
    cd backend && uv run python scripts/broker_data_model_migration.py

After success, stamp alembic:
    cd backend && uv run alembic stamp 059_broker_data_model_tables
"""

import asyncio
from typing import Union

from sqlalchemy import text

from flywheel.db.session import get_session_factory

# All DDL statements in FK dependency order.
# Each statement is executed and committed individually.
STATEMENTS: list[str] = [
    # -------------------------------------------------------------------------
    # 1. broker_clients
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS broker_clients (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id         UUID NOT NULL REFERENCES tenants(id),
        name              TEXT NOT NULL,
        normalized_name   TEXT NOT NULL,
        legal_name        TEXT,
        domain            TEXT,
        tax_id            TEXT,
        industry          TEXT,
        location          TEXT,
        notes             TEXT,
        context_entity_id UUID,
        metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_broker_client_tenant_name UNIQUE (tenant_id, normalized_name)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_broker_client_tenant
       ON broker_clients (tenant_id)""",

    # -------------------------------------------------------------------------
    # 2. broker_client_contacts
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS broker_client_contacts (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id         UUID NOT NULL REFERENCES tenants(id),
        broker_client_id  UUID NOT NULL REFERENCES broker_clients(id) ON DELETE CASCADE,
        name              TEXT NOT NULL,
        email             TEXT,
        phone             TEXT,
        title             TEXT,
        role              TEXT NOT NULL DEFAULT 'primary'
                          CHECK (role IN ('primary', 'billing', 'technical', 'legal', 'executive')),
        is_primary        BOOLEAN NOT NULL DEFAULT false,
        notes             TEXT,
        created_by_user_id UUID,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_broker_client_contact_email UNIQUE (broker_client_id, email)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_broker_client_contact_client
       ON broker_client_contacts (broker_client_id)""",

    # -------------------------------------------------------------------------
    # 3. carrier_contacts
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS carrier_contacts (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id         UUID NOT NULL REFERENCES tenants(id),
        carrier_config_id UUID NOT NULL REFERENCES carrier_configs(id) ON DELETE CASCADE,
        name              TEXT NOT NULL,
        email             TEXT,
        phone             TEXT,
        title             TEXT,
        role              TEXT NOT NULL DEFAULT 'submissions'
                          CHECK (role IN ('submissions', 'account_manager', 'underwriter', 'claims', 'billing')),
        is_primary        BOOLEAN NOT NULL DEFAULT false,
        notes             TEXT,
        created_by_user_id UUID,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_carrier_contact_email UNIQUE (carrier_config_id, email)
    )""",
    """CREATE INDEX IF NOT EXISTS idx_carrier_contact_carrier
       ON carrier_contacts (carrier_config_id)""",

    # -------------------------------------------------------------------------
    # 4. broker_recommendations
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS broker_recommendations (
        id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id             UUID NOT NULL REFERENCES tenants(id),
        broker_project_id     UUID NOT NULL REFERENCES broker_projects(id) ON DELETE CASCADE,
        subject               TEXT NOT NULL,
        body                  TEXT NOT NULL,
        recipient_email       TEXT,
        status                TEXT NOT NULL DEFAULT 'draft'
                              CHECK (status IN ('draft', 'approved', 'sent', 'failed')),
        created_by_user_id    UUID,
        approved_by_user_id   UUID,
        approved_at           TIMESTAMPTZ,
        sent_at               TIMESTAMPTZ,
        metadata              JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    """CREATE INDEX IF NOT EXISTS idx_broker_recommendation_project
       ON broker_recommendations (broker_project_id)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_broker_recommendation_approved
       ON broker_recommendations (broker_project_id) WHERE status = 'approved'""",

    # -------------------------------------------------------------------------
    # 5. solicitation_drafts
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS solicitation_drafts (
        id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id             UUID NOT NULL REFERENCES tenants(id),
        broker_project_id     UUID NOT NULL REFERENCES broker_projects(id) ON DELETE CASCADE,
        carrier_config_id     UUID NOT NULL REFERENCES carrier_configs(id) ON DELETE CASCADE,
        carrier_quote_id      UUID REFERENCES carrier_quotes(id) ON DELETE SET NULL,
        subject               TEXT,
        body                  TEXT,
        status                TEXT NOT NULL DEFAULT 'draft'
                              CHECK (status IN ('draft', 'pending', 'approved', 'sent', 'bounced')),
        sent_to_email         TEXT,
        created_by_user_id    UUID,
        approved_by_user_id   UUID,
        approved_at           TIMESTAMPTZ,
        sent_at               TIMESTAMPTZ,
        created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    """CREATE INDEX IF NOT EXISTS idx_solicitation_draft_project
       ON solicitation_drafts (broker_project_id)""",
    """CREATE INDEX IF NOT EXISTS idx_solicitation_draft_carrier
       ON solicitation_drafts (carrier_config_id)""",
    """CREATE INDEX IF NOT EXISTS idx_solicitation_draft_status
       ON solicitation_drafts (tenant_id, status) WHERE status IN ('draft', 'pending')""",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_solicitation_draft_active
       ON solicitation_drafts (broker_project_id, carrier_config_id)
       WHERE status IN ('draft', 'pending', 'approved')""",

    # -------------------------------------------------------------------------
    # 6. broker_project_emails
    # -------------------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS broker_project_emails (
        id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id             UUID NOT NULL REFERENCES tenants(id),
        broker_project_id     UUID NOT NULL REFERENCES broker_projects(id) ON DELETE CASCADE,
        thread_id             TEXT NOT NULL,
        direction             TEXT CHECK (direction IN ('inbound', 'outbound')),
        received_at           TIMESTAMPTZ,
        created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    """CREATE INDEX IF NOT EXISTS idx_broker_project_email_project
       ON broker_project_emails (broker_project_id)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_broker_project_email_thread
       ON broker_project_emails (broker_project_id, thread_id)""",
]

# New tables added in this migration (used for RLS — handled in plan 02)
NEW_TABLES: list[str] = [
    "broker_clients",
    "broker_client_contacts",
    "carrier_contacts",
    "broker_recommendations",
    "solicitation_drafts",
    "broker_project_emails",
]


async def run_migration() -> None:
    factory = get_session_factory()

    # DDL statements only — RLS handled in broker_data_model_rls.py (plan 02)
    for stmt in STATEMENTS:
        async with factory() as session:
            await session.execute(text(stmt))
            await session.commit()
        print(f"OK: {stmt.strip()[:80]}...")

    print("\nAll DDL applied. Run: alembic stamp 059_broker_data_model_tables")


if __name__ == "__main__":
    asyncio.run(run_migration())
