# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# Alembic's multi-statement DDL transactions are silently rolled
# back by PgBouncer. This migration file exists for documentation
# and downgrade support ONLY.
#
# To apply: Run EACH statement separately in Supabase SQL Editor
# (Dashboard > SQL Editor), then run:
#   cd backend && alembic stamp 053_library_redesign_schema
#
# Phase 1 — Schema (additive, safe):
#   ALTER TABLE documents ADD COLUMN tags TEXT[] NOT NULL DEFAULT '{}';
#   ALTER TABLE documents ADD COLUMN account_id UUID REFERENCES pipeline_entries(id) ON DELETE SET NULL;
#   ALTER TABLE documents ADD COLUMN module TEXT NOT NULL DEFAULT 'crm';
#
# Phase 2 — Indexes (run AFTER columns exist):
#   CREATE INDEX idx_documents_tags ON documents USING GIN (tags);
#   CREATE INDEX idx_documents_account ON documents (tenant_id, account_id);
#
# Phase 3 — Dedup indexes (run AFTER data cleanup migration 054):
#   CREATE UNIQUE INDEX idx_documents_dedup ON documents (tenant_id, document_type, title, account_id)
#     WHERE account_id IS NOT NULL AND deleted_at IS NULL;
#   CREATE UNIQUE INDEX idx_documents_dedup_no_account ON documents (tenant_id, document_type, title)
#     WHERE account_id IS NULL AND deleted_at IS NULL;
#
# Then: cd backend && alembic stamp 053_library_redesign_schema
# ============================================================

"""Library redesign: add tags, account_id, module columns and indexes.

Revision ID: 053_library_redesign_schema
Revises: 052_add_last_briefing_visit
Create Date: 2026-04-08
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "053_library_redesign_schema"
down_revision: Union[str, None] = "052_add_last_briefing_visit"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Add columns
    op.add_column(
        "documents",
        sa.Column("tags", ARRAY(sa.Text), nullable=False, server_default="{}"),
    )
    op.add_column(
        "documents",
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("pipeline_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("module", sa.Text, nullable=False, server_default="crm"),
    )
    # Indexes
    op.create_index(
        "idx_documents_tags", "documents", ["tags"], postgresql_using="gin"
    )
    op.create_index(
        "idx_documents_account", "documents", ["tenant_id", "account_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_documents_account", table_name="documents")
    op.drop_index("idx_documents_tags", table_name="documents")
    op.drop_column("documents", "module")
    op.drop_column("documents", "account_id")
    op.drop_column("documents", "tags")
