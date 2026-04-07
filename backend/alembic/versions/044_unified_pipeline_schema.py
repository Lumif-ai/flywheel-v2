"""Create unified pipeline schema: pipeline_entries, contacts, activities, pipeline_entry_sources.

Replaces the separate leads + accounts model with a single pipeline_entries table
where entity_type ('company' | 'person') distinguishes record types. Contacts,
activities, and provenance sources are tracked in dedicated child tables.

Includes:
- pg_trgm extension for fuzzy name search
- SECURITY DEFINER trigger to denormalize last_activity_at
- RLS policies on all four new tables
- GIN indexes for array and trigram columns

Revision ID: 044_unified_pipeline
Revises: 043_ctx_rls_softdel
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "044_unified_pipeline"
down_revision: Union[str, None] = "043_ctx_rls_softdel"
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
    # ── Step 1: pg_trgm extension for fuzzy name search ──
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # ── Step 2: pipeline_entries table ──
    op.execute("""
        CREATE TABLE pipeline_entries (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            owner_id            UUID,
            entity_type         TEXT NOT NULL DEFAULT 'company',
            name                TEXT NOT NULL,
            normalized_name     TEXT NOT NULL,
            domain              TEXT,
            stage               TEXT NOT NULL DEFAULT 'identified',
            fit_score           NUMERIC,
            fit_tier            TEXT,
            fit_rationale       TEXT,
            relationship_type   TEXT[] NOT NULL DEFAULT '{prospect}'::text[],
            source              TEXT NOT NULL,
            channels            TEXT[] NOT NULL DEFAULT '{}'::text[],
            intel               JSONB NOT NULL DEFAULT '{}'::jsonb,
            ai_summary          TEXT,
            company_cache_id    UUID REFERENCES companies(id),
            context_entity_id   UUID,
            referred_by         UUID,
            last_activity_at    TIMESTAMPTZ,
            stale_notified_at   TIMESTAMPTZ,
            retired_at          TIMESTAMPTZ,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_pipeline_tenant_owner_normalized
                UNIQUE (tenant_id, owner_id, normalized_name),
            CONSTRAINT chk_entity_type
                CHECK (entity_type IN ('company', 'person'))
        );
    """)

    # ── Step 3: Self-referencing FK ──
    op.execute("""
        ALTER TABLE pipeline_entries
            ADD CONSTRAINT fk_pipeline_referred_by
            FOREIGN KEY (referred_by) REFERENCES pipeline_entries(id) ON DELETE SET NULL;
    """)

    # ── Step 4: context_entity FK ──
    op.execute("""
        ALTER TABLE pipeline_entries
            ADD CONSTRAINT fk_pipeline_context_entity
            FOREIGN KEY (context_entity_id) REFERENCES context_entities(id) ON DELETE SET NULL;
    """)

    # ── Step 5: pipeline_entries indexes ──
    op.execute("CREATE INDEX idx_pipeline_tenant_stage ON pipeline_entries (tenant_id, stage);")
    op.execute("CREATE INDEX idx_pipeline_tenant_fit ON pipeline_entries (tenant_id, fit_tier);")
    op.execute("CREATE INDEX idx_pipeline_relationship_type ON pipeline_entries USING GIN (relationship_type);")
    op.execute("CREATE INDEX idx_pipeline_entries_name_trgm ON pipeline_entries USING GIN (normalized_name gin_trgm_ops);")

    _enable_rls("pipeline_entries")

    # ── Step 6: contacts table ──
    op.execute("""
        CREATE TABLE contacts (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            pipeline_entry_id   UUID REFERENCES pipeline_entries(id) ON DELETE CASCADE,
            name                TEXT NOT NULL,
            email               TEXT,
            title               TEXT,
            role                TEXT,
            linkedin_url        TEXT,
            phone               TEXT,
            notes               TEXT,
            is_primary          BOOLEAN NOT NULL DEFAULT false,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # ── Step 7: contacts indexes ──
    op.execute("CREATE INDEX idx_contacts_pipeline_entry ON contacts (pipeline_entry_id);")
    op.execute("CREATE INDEX idx_contacts_tenant_email ON contacts (tenant_id, email) WHERE email IS NOT NULL;")
    op.execute("CREATE UNIQUE INDEX uq_contacts_primary ON contacts (pipeline_entry_id) WHERE is_primary = true;")

    _enable_rls("contacts")

    # ── Step 8: activities table ──
    op.execute("""
        CREATE TABLE activities (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            pipeline_entry_id   UUID NOT NULL REFERENCES pipeline_entries(id) ON DELETE CASCADE,
            contact_id          UUID REFERENCES contacts(id) ON DELETE SET NULL,
            type                TEXT NOT NULL,
            channel             TEXT,
            direction           TEXT,
            status              TEXT NOT NULL DEFAULT 'completed',
            subject             TEXT,
            body_preview        TEXT,
            metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
            occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_activity_type
                CHECK (type IN ('email', 'meeting', 'call', 'linkedin_message',
                                'note', 'stage_change', 'enrichment', 'task'))
        );
    """)

    # ── Step 9: activities indexes ──
    op.execute("CREATE INDEX idx_activities_pipeline_entry ON activities (pipeline_entry_id);")
    op.execute("CREATE INDEX idx_activities_tenant_type ON activities (tenant_id, type);")
    op.execute("CREATE INDEX idx_activities_occurred ON activities (pipeline_entry_id, occurred_at DESC);")

    _enable_rls("activities")

    # ── Step 10: pipeline_entry_sources table ──
    op.execute("""
        CREATE TABLE pipeline_entry_sources (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            pipeline_entry_id   UUID NOT NULL REFERENCES pipeline_entries(id) ON DELETE CASCADE,
            source_type         TEXT NOT NULL,
            source_ref_id       UUID,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_source_type
                CHECK (source_type IN ('manual', 'meeting', 'email', 'gtm_scrape',
                                       'import', 'referral'))
        );
    """)

    # ── Step 11: pipeline_entry_sources indexes ──
    op.execute("CREATE INDEX idx_pes_pipeline_entry ON pipeline_entry_sources (pipeline_entry_id);")
    op.execute("CREATE INDEX idx_pes_source_ref ON pipeline_entry_sources (source_type, source_ref_id) WHERE source_ref_id IS NOT NULL;")

    _enable_rls("pipeline_entry_sources")

    # ── Step 12: SECURITY DEFINER trigger function ──
    op.execute("""
        CREATE OR REPLACE FUNCTION update_pipeline_entry_last_activity()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        BEGIN
            UPDATE pipeline_entries
            SET last_activity_at = GREATEST(
                last_activity_at,
                COALESCE(NEW.occurred_at, NEW.created_at)
            )
            WHERE id = NEW.pipeline_entry_id;
            RETURN NEW;
        END;
        $$;
    """)

    # ── Step 13: Attach trigger to activities table ──
    op.execute("""
        CREATE TRIGGER trg_activities_update_last_activity
            AFTER INSERT ON activities
            FOR EACH ROW
            EXECUTE FUNCTION update_pipeline_entry_last_activity();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_activities_update_last_activity ON activities;")
    op.execute("DROP FUNCTION IF EXISTS update_pipeline_entry_last_activity();")
    op.execute("DROP TABLE IF EXISTS pipeline_entry_sources CASCADE;")
    op.execute("DROP TABLE IF EXISTS activities CASCADE;")
    op.execute("DROP TABLE IF EXISTS contacts CASCADE;")
    op.execute("DROP TABLE IF EXISTS pipeline_entries CASCADE;")
    # Do NOT drop pg_trgm extension -- other things may use it.
