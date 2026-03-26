"""Make documents.storage_path nullable.

Documents now serve content from skill_runs.rendered_html via the
GET /documents/{id}/content endpoint. Storage path is only needed
for legacy docs uploaded to Supabase Storage.

Revision ID: 026
"""

from alembic import op


revision = "026_docs_storage_nullable"
down_revision = "025_uploaded_files_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("documents", "storage_path", nullable=True)


def downgrade() -> None:
    # Backfill NULLs before restoring NOT NULL
    op.execute("UPDATE documents SET storage_path = '' WHERE storage_path IS NULL")
    op.alter_column("documents", "storage_path", nullable=False)
