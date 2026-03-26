"""add metadata JSONB column to uploaded_files

Revision ID: 025_uploaded_files_metadata
Revises: 024_users_to_profiles
Create Date: 2026-03-25

Adds a metadata JSONB column to uploaded_files for storing profile_linked
flag and other per-file metadata.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "025_uploaded_files_metadata"
down_revision = "024_users_to_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='uploaded_files' AND column_name='metadata'"
        )
    )
    if result.fetchone() is None:
        op.add_column(
            "uploaded_files",
            sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("uploaded_files", "metadata")
