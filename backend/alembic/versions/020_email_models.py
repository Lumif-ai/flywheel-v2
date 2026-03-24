"""create email copilot tables with RLS

Revision ID: 020_email_models
Revises: 019_documents
Create Date: 2026-03-24

Hand-written migration -- creates 4 email copilot tables with RLS, indexes,
unique constraints, grants, per-operation policies, and updated_at triggers.

Tables: emails, email_scores, email_drafts, email_voice_profiles

Note: No body column on emails -- email body is fetched on-demand for PII minimization.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers
revision: str = "020_email_models"
down_revision: Union[str, None] = "019_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that get updated_at triggers
UPDATED_AT_TABLES = ["email_drafts", "email_voice_profiles"]

# All four tables (creation order matters for FK dependencies)
EMAIL_TABLES = ["emails", "email_scores", "email_drafts", "email_voice_profiles"]


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # Table 1: emails
    # Synced Gmail message metadata. No body stored.
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE emails (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            user_id             UUID NOT NULL REFERENCES users(id),
            gmail_message_id    TEXT NOT NULL,
            gmail_thread_id     TEXT NOT NULL,
            sender_email        TEXT NOT NULL,
            sender_name         TEXT,
            subject             TEXT,
            snippet             TEXT,
            received_at         TIMESTAMPTZ NOT NULL,
            labels              TEXT[] NOT NULL DEFAULT '{}'::text[],
            is_read             BOOLEAN NOT NULL DEFAULT false,
            is_replied          BOOLEAN NOT NULL DEFAULT false,
            synced_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_email_tenant_message UNIQUE (tenant_id, gmail_message_id)
        );
    """)

    op.execute("""
        CREATE INDEX idx_emails_tenant_received
            ON emails (tenant_id, received_at DESC);
    """)
    op.execute("""
        CREATE INDEX idx_emails_tenant_user
            ON emails (tenant_id, user_id);
    """)
    op.execute("""
        CREATE INDEX idx_emails_thread
            ON emails (tenant_id, gmail_thread_id);
    """)

    op.execute("ALTER TABLE emails ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE emails FORCE ROW LEVEL SECURITY;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON emails TO app_user;")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON emails
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON emails
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON emails
            FOR UPDATE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON emails
            FOR DELETE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)

    # -----------------------------------------------------------------------
    # Table 2: email_scores
    # AI-generated priority score and category for a synced email.
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE email_scores (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            email_id            UUID NOT NULL REFERENCES emails(id),
            priority            INTEGER NOT NULL,
            category            TEXT NOT NULL,
            suggested_action    TEXT,
            reasoning           TEXT,
            context_refs        JSONB NOT NULL DEFAULT '[]'::jsonb,
            sender_entity_id    UUID REFERENCES context_entities(id),
            scored_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_email_score_email UNIQUE (email_id)
        );
    """)

    op.execute("""
        CREATE INDEX idx_email_scores_tenant_priority
            ON email_scores (tenant_id, priority DESC);
    """)

    op.execute("ALTER TABLE email_scores ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE email_scores FORCE ROW LEVEL SECURITY;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON email_scores TO app_user;")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON email_scores
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON email_scores
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON email_scores
            FOR UPDATE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON email_scores
            FOR DELETE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)

    # -----------------------------------------------------------------------
    # Table 3: email_drafts
    # AI-generated reply draft. draft_body nulled after send for PII minimization.
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE email_drafts (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            email_id        UUID NOT NULL REFERENCES emails(id),
            draft_body      TEXT,
            status          TEXT NOT NULL DEFAULT 'pending',
            context_used    JSONB NOT NULL DEFAULT '[]'::jsonb,
            user_edits      TEXT,
            visible_after   TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX idx_email_drafts_tenant_status
            ON email_drafts (tenant_id, status);
    """)

    op.execute("ALTER TABLE email_drafts ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE email_drafts FORCE ROW LEVEL SECURITY;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON email_drafts TO app_user;")

    op.execute("""
        CREATE POLICY tenant_isolation_select ON email_drafts
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON email_drafts
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON email_drafts
            FOR UPDATE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON email_drafts
            FOR DELETE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)

    op.execute("""
        CREATE TRIGGER set_updated_at
            BEFORE UPDATE ON email_drafts
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    # -----------------------------------------------------------------------
    # Table 4: email_voice_profiles
    # Learned writing style for a user. One profile per user per tenant.
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE email_voice_profiles (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            user_id             UUID NOT NULL REFERENCES users(id),
            tone                TEXT,
            avg_length          INTEGER,
            sign_off            TEXT,
            phrases             JSONB NOT NULL DEFAULT '[]'::jsonb,
            samples_analyzed    INTEGER NOT NULL DEFAULT 0,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_voice_profile_tenant_user UNIQUE (tenant_id, user_id)
        );
    """)

    op.execute("ALTER TABLE email_voice_profiles ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE email_voice_profiles FORCE ROW LEVEL SECURITY;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON email_voice_profiles TO app_user;"
    )

    op.execute("""
        CREATE POLICY tenant_isolation_select ON email_voice_profiles
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON email_voice_profiles
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON email_voice_profiles
            FOR UPDATE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON email_voice_profiles
            FOR DELETE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)

    op.execute("""
        CREATE TRIGGER set_updated_at
            BEFORE UPDATE ON email_voice_profiles
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    # -----------------------------------------------------------------------
    # Verification: assert RLS is enabled on all four tables
    # -----------------------------------------------------------------------
    op.execute("""
        DO $$
        DECLARE
            t TEXT;
            rls_ok BOOLEAN;
        BEGIN
            FOREACH t IN ARRAY ARRAY['emails', 'email_scores', 'email_drafts', 'email_voice_profiles']
            LOOP
                SELECT relrowsecurity INTO rls_ok
                FROM pg_class
                WHERE relname = t;

                IF NOT rls_ok THEN
                    RAISE EXCEPTION 'RLS not enabled on table: %', t;
                END IF;
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.execute("DROP TABLE IF EXISTS email_voice_profiles;")
    op.execute("DROP TABLE IF EXISTS email_drafts;")
    op.execute("DROP TABLE IF EXISTS email_scores;")
    op.execute("DROP TABLE IF EXISTS emails;")
