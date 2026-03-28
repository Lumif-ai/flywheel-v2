"""Unify meetings table with dual-source dedup columns.

Adds calendar_event_id, granola_note_id, location, description columns
to support both Google Calendar and Granola as meeting sources with
dedup indexes for each. Replaces idx_meetings_pending with
idx_meetings_processable covering the full lifecycle state machine.

Revision ID: 033_unify_meetings
Revises: 032_create_meetings_table
Create Date: 2026-03-28

UNI-01 -- dual-source dedup columns for unified meeting data layer.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "033_unify_meetings"
down_revision: Union[str, None] = "032_create_meetings_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add dual-source columns
    op.add_column("meetings", sa.Column("calendar_event_id", sa.Text(), nullable=True))
    op.add_column("meetings", sa.Column("granola_note_id", sa.Text(), nullable=True))
    op.add_column("meetings", sa.Column("location", sa.Text(), nullable=True))
    op.add_column("meetings", sa.Column("description", sa.Text(), nullable=True))

    # 2. Partial unique indexes for dual-source dedup
    op.create_index(
        "idx_meetings_calendar_dedup",
        "meetings",
        ["tenant_id", "calendar_event_id"],
        unique=True,
        postgresql_where=sa.text("calendar_event_id IS NOT NULL"),
    )
    op.create_index(
        "idx_meetings_granola_dedup",
        "meetings",
        ["tenant_id", "granola_note_id"],
        unique=True,
        postgresql_where=sa.text("granola_note_id IS NOT NULL"),
    )

    # 3. Replace idx_meetings_pending with idx_meetings_processable
    #    covering the full lifecycle: pending, scheduled, recorded
    op.drop_index("idx_meetings_pending", table_name="meetings")
    op.create_index(
        "idx_meetings_processable",
        "meetings",
        ["tenant_id", "processing_status"],
        postgresql_where=sa.text(
            "processing_status IN ('pending', 'scheduled', 'recorded')"
        ),
    )


def downgrade() -> None:
    # Reverse: drop new indexes and columns, restore old index
    op.drop_index("idx_meetings_processable", table_name="meetings")
    op.create_index(
        "idx_meetings_pending",
        "meetings",
        ["tenant_id", "processing_status"],
        postgresql_where=sa.text("processing_status = 'pending'"),
    )
    op.drop_index("idx_meetings_granola_dedup", table_name="meetings")
    op.drop_index("idx_meetings_calendar_dedup", table_name="meetings")
    op.drop_column("meetings", "description")
    op.drop_column("meetings", "location")
    op.drop_column("meetings", "granola_note_id")
    op.drop_column("meetings", "calendar_event_id")
