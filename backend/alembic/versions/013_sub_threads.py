"""add parent_id to work_streams for sub-thread support

Revision ID: 013_sub_threads
Revises: 012_work_stream_tables
Create Date: 2026-03-23

Hand-written migration -- adds parent_id self-referential FK to work_streams
for hierarchical sub-thread organization. Sub-threads are WorkStreams whose
parent_id is non-null, limited to 1 level of nesting.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "013_sub_threads"
down_revision: Union[str, Sequence[str]] = "012_work_stream_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add parent_id column to work_streams with self-referential FK."""

    # Add nullable parent_id column
    op.add_column(
        "work_streams",
        sa.Column(
            "parent_id",
            sa.Uuid(),
            sa.ForeignKey("work_streams.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # Index for querying children of a parent stream
    op.create_index(
        "idx_streams_parent",
        "work_streams",
        ["parent_id"],
    )


def downgrade() -> None:
    """Remove parent_id column from work_streams."""
    op.drop_index("idx_streams_parent", table_name="work_streams")
    op.drop_column("work_streams", "parent_id")
