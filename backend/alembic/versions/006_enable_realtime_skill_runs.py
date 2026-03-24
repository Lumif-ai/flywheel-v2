"""enable realtime for skill_runs table

Revision ID: 006_enable_realtime
Revises: 005_add_integrations
Create Date: 2026-03-20

Adds the skill_runs table to the Supabase Realtime publication so that
frontend clients can subscribe to status changes for background completion
notifications. Wrapped in try/except for local dev where the publication
may not exist.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '006_enable_realtime'
down_revision: Union[str, Sequence[str]] = '005_add_integrations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add skill_runs to the supabase_realtime publication."""
    # Use DO block to safely skip when publication doesn't exist (local dev)
    op.execute("""
        DO $$
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE skill_runs;
        EXCEPTION WHEN undefined_object THEN
            NULL;
        END $$;
    """)


def downgrade() -> None:
    """Remove skill_runs from the supabase_realtime publication."""
    op.execute("""
        DO $$
        BEGIN
            ALTER PUBLICATION supabase_realtime DROP TABLE skill_runs;
        EXCEPTION WHEN undefined_object THEN
            NULL;
        END $$;
    """)
