"""Add 6 voice profile expansion columns.

Adds formality_level, greeting_style, question_style, paragraph_pattern,
emoji_usage, and avg_sentences to email_voice_profiles.

These columns capture richer writing-style signals used by the voice extraction,
drafting, and incremental learning engines (Phase 70).

Revision ID: 036_voice_profile_expansion
Revises: 035_email_task_fields
Create Date: 2026-03-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "036_voice_profile_expansion"
down_revision: Union[str, None] = "035_email_task_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_voice_profiles",
        sa.Column(
            "formality_level",
            sa.Text(),
            server_default="conversational",
            nullable=True,
        ),
    )
    op.add_column(
        "email_voice_profiles",
        sa.Column(
            "greeting_style",
            sa.Text(),
            server_default="Hi {name},",
            nullable=True,
        ),
    )
    op.add_column(
        "email_voice_profiles",
        sa.Column(
            "question_style",
            sa.Text(),
            server_default="direct",
            nullable=True,
        ),
    )
    op.add_column(
        "email_voice_profiles",
        sa.Column(
            "paragraph_pattern",
            sa.Text(),
            server_default="short single-line",
            nullable=True,
        ),
    )
    op.add_column(
        "email_voice_profiles",
        sa.Column(
            "emoji_usage",
            sa.Text(),
            server_default="never",
            nullable=True,
        ),
    )
    op.add_column(
        "email_voice_profiles",
        sa.Column(
            "avg_sentences",
            sa.Integer(),
            server_default="3",
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("email_voice_profiles", "avg_sentences")
    op.drop_column("email_voice_profiles", "emoji_usage")
    op.drop_column("email_voice_profiles", "paragraph_pattern")
    op.drop_column("email_voice_profiles", "question_style")
    op.drop_column("email_voice_profiles", "greeting_style")
    op.drop_column("email_voice_profiles", "formality_level")
