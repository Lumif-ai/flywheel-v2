"""Add raw token column to invites table for copy-link functionality.

Revision ID: 038_add_invite_token_column
Revises: 037_context_extraction_pipeline
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa

revision = "038_add_invite_token_column"
down_revision = "037_context_extraction_pipeline"


def upgrade() -> None:
    op.add_column("invites", sa.Column("token", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("invites", "token")
