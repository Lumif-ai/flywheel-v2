"""create documents table with RLS

Revision ID: 019_documents
Revises: 018_skill_registry
Create Date: 2026-03-24

Hand-written migration -- creates the documents table for persistent,
shareable document artifacts produced by skill runs.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "019_documents"
down_revision: Union[str, None] = "018_skill_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE documents (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            user_id         UUID NOT NULL REFERENCES users(id),
            title           TEXT NOT NULL,
            document_type   VARCHAR(50) NOT NULL,
            mime_type       VARCHAR(100) NOT NULL DEFAULT 'text/html',
            storage_path    TEXT NOT NULL,
            file_size_bytes INTEGER,
            skill_run_id    UUID REFERENCES skill_runs(id) ON DELETE SET NULL,
            share_token     VARCHAR(64) UNIQUE,
            metadata        JSONB DEFAULT '{}',
            created_at      TIMESTAMPTZ DEFAULT now(),
            updated_at      TIMESTAMPTZ DEFAULT now(),
            deleted_at      TIMESTAMPTZ
        );
    """)

    # Indexes
    op.execute("""
        CREATE INDEX idx_documents_tenant
            ON documents (tenant_id);
    """)
    op.execute("""
        CREATE INDEX idx_documents_type
            ON documents (tenant_id, document_type);
    """)
    op.execute("""
        CREATE INDEX idx_documents_share
            ON documents (share_token)
            WHERE share_token IS NOT NULL;
    """)
    op.execute("""
        CREATE INDEX idx_documents_metadata
            ON documents USING GIN (metadata);
    """)

    # RLS
    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY documents_tenant_isolation ON documents
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS documents_tenant_isolation ON documents;")
    op.execute("DROP TABLE IF EXISTS documents;")
