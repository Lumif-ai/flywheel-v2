# ============================================================
# SUPABASE PGBOUNCER DDL WORKAROUND
# ============================================================
# This migration handles data cleanup for the library redesign.
# Run in Supabase SQL Editor, then stamp.
#
# Step 1 — Clean bad titles (UUID-prefixed, raw URLs):
#   UPDATE documents
#   SET title = CASE
#     WHEN title LIKE 'DOCUMENT_FILE:%' THEN
#       COALESCE(
#         INITCAP(REPLACE(document_type, '-', ' ')) || ': ' ||
#         COALESCE(metadata->>'company_name', 'Document'),
#         'Untitled Document'
#       )
#     WHEN title LIKE 'http%://%' THEN
#       COALESCE(
#         INITCAP(REPLACE(document_type, '-', ' ')) || ': ' ||
#         COALESCE(metadata->>'company_name', 'Document'),
#         'Untitled Document'
#       )
#     ELSE title
#   END,
#   updated_at = now()
#   WHERE title LIKE 'DOCUMENT_FILE:%' OR title LIKE 'http%://%';
#
# Step 2 — Merge duplicates (keep newest, soft-delete others):
#   WITH ranked AS (
#     SELECT id,
#       ROW_NUMBER() OVER (
#         PARTITION BY tenant_id, document_type, title
#         ORDER BY created_at DESC
#       ) AS rn
#     FROM documents
#     WHERE deleted_at IS NULL
#   )
#   UPDATE documents
#   SET deleted_at = now(), updated_at = now()
#   FROM ranked
#   WHERE documents.id = ranked.id AND ranked.rn > 1;
#
# Step 3 — Backfill account_id from metadata:
#   UPDATE documents d
#   SET account_id = pe.id, updated_at = now()
#   FROM pipeline_entries pe
#   WHERE d.metadata->>'account_id' IS NOT NULL
#     AND pe.id = (d.metadata->>'account_id')::uuid
#     AND d.account_id IS NULL
#     AND d.deleted_at IS NULL;
#
# Step 4 — Add dedup indexes (AFTER cleanup):
#   CREATE UNIQUE INDEX idx_documents_dedup
#     ON documents (tenant_id, document_type, title, account_id)
#     WHERE account_id IS NOT NULL AND deleted_at IS NULL;
#   CREATE UNIQUE INDEX idx_documents_dedup_no_account
#     ON documents (tenant_id, document_type, title)
#     WHERE account_id IS NULL AND deleted_at IS NULL;
#
# Then: cd backend && alembic stamp 054_library_data_cleanup
# ============================================================

"""Library data cleanup: fix titles, merge dupes, backfill account_id, add dedup indexes.

Revision ID: 054_library_data_cleanup
Revises: 053_library_redesign_schema
Create Date: 2026-04-08
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "054_library_data_cleanup"
down_revision: Union[str, None] = "053_library_redesign_schema"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Data cleanup is done via SQL Editor (see header comments).
    # Dedup indexes added after cleanup.
    op.create_index(
        "idx_documents_dedup",
        "documents",
        ["tenant_id", "document_type", "title", "account_id"],
        unique=True,
        postgresql_where=sa.text(
            "account_id IS NOT NULL AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "idx_documents_dedup_no_account",
        "documents",
        ["tenant_id", "document_type", "title"],
        unique=True,
        postgresql_where=sa.text(
            "account_id IS NULL AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("idx_documents_dedup_no_account", table_name="documents")
    op.drop_index("idx_documents_dedup", table_name="documents")
