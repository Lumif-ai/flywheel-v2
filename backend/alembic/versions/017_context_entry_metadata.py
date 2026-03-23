"""add metadata JSONB column to context_entries

Revision ID: 017_context_entry_metadata
Revises: 016_nudge_interactions
Create Date: 2026-03-23

Hand-written migration -- adds a metadata JSONB column to context_entries
for arbitrary structured metadata (source URLs, classification tags, provenance).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "017_context_entry_metadata"
down_revision: Union[str, Sequence[str]] = "016_nudge_interactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add metadata JSONB column with empty-object default."""
    op.add_column(
        "context_entries",
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove metadata column."""
    op.drop_column("context_entries", "metadata")
