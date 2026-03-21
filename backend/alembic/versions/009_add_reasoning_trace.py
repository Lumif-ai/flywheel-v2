"""add reasoning_trace JSONB column to skill_runs

Revision ID: 009_add_reasoning_trace
Revises: 008_fix_dismissal_rls
Create Date: 2026-03-21

Adds a nullable reasoning_trace JSONB column to skill_runs for capturing
entry-level context consumption data and orchestrator routing decisions.
Includes a partial GIN index for efficient JSONB containment queries.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "009_add_reasoning_trace"
down_revision: Union[str, Sequence[str]] = "008_fix_dismissal_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add reasoning_trace JSONB column and partial GIN index."""

    op.add_column(
        "skill_runs",
        sa.Column("reasoning_trace", JSONB, nullable=True),
    )

    # Partial GIN index for efficient containment queries by the learning engine.
    # Only indexes rows where reasoning_trace IS NOT NULL (no wasted index space
    # on legacy rows).
    op.execute(
        """
        CREATE INDEX idx_runs_reasoning_trace
        ON skill_runs USING gin (reasoning_trace)
        WHERE reasoning_trace IS NOT NULL
        """
    )


def downgrade() -> None:
    """Drop the GIN index then the reasoning_trace column."""
    op.execute("DROP INDEX IF EXISTS idx_runs_reasoning_trace")
    op.drop_column("skill_runs", "reasoning_trace")
