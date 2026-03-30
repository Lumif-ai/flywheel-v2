"""Add context_extracted_at column and email_context_reviews table.

Adds a nullable context_extracted_at TIMESTAMP to emails (tracks which emails
have been processed by the context extraction pipeline) and creates the
email_context_reviews table for low-confidence extractions pending human review.

Revision ID: 037_context_extraction_pipeline
Revises: 036_voice_profile_expansion
Create Date: 2026-03-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "037_context_extraction_pipeline"
down_revision: Union[str, None] = "036_voice_profile_expansion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add context_extracted_at to emails
    op.add_column(
        "emails",
        sa.Column("context_extracted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # 2. Partial index for efficient "not yet extracted" queries
    op.create_index(
        "idx_emails_context_not_extracted",
        "emails",
        ["tenant_id"],
        postgresql_where=sa.text("context_extracted_at IS NULL"),
    )

    # 3. Create email_context_reviews table
    op.execute("""
        CREATE TABLE email_context_reviews (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            email_id        UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
            user_id         UUID NOT NULL REFERENCES profiles(id),
            extracted_data  JSONB NOT NULL DEFAULT '{}'::jsonb,
            status          TEXT NOT NULL DEFAULT 'pending',
            reviewed_at     TIMESTAMP WITH TIME ZONE,
            created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );

        CREATE INDEX idx_context_reviews_tenant_status
            ON email_context_reviews (tenant_id, status);
    """)

    # 4. Enable RLS and grant permissions
    op.execute("ALTER TABLE email_context_reviews ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE email_context_reviews FORCE ROW LEVEL SECURITY;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON email_context_reviews TO app_user;"
    )

    # 5. Create tenant isolation RLS policies
    for action in ["SELECT", "INSERT", "UPDATE", "DELETE"]:
        clause = "WITH CHECK" if action == "INSERT" else "USING"
        op.execute(f"""
            CREATE POLICY tenant_isolation_{action.lower()} ON email_context_reviews
                FOR {action}
                {clause} (tenant_id = current_setting('app.tenant_id', true)::uuid);
        """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_context_reviews CASCADE;")
    op.drop_index("idx_emails_context_not_extracted", table_name="emails")
    op.drop_column("emails", "context_extracted_at")
