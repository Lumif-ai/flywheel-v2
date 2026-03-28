"""Create meetings table with split-visibility RLS.

Adds the meetings table as a first-class entity in the CRM data model.
Supports meeting ingestion from external sources (Granola, Fathom, etc.)
or manual upload.

Privacy model:
- tenant_read policy: all tenant members can SELECT meetings metadata
- owner_write policy: only the user who created a meeting can INSERT/UPDATE/DELETE

Revision ID: 032_create_meetings_table
Revises: 031_user_level_rls
Create Date: 2026-03-28

MDE-01 -- meeting table schema foundation for all meeting ingestion functionality.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "032_create_meetings_table"
down_revision: Union[str, None] = "031_user_level_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create meetings table
    op.create_table(
        "meetings",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("meeting_date", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("duration_mins", sa.Integer(), nullable=True),
        sa.Column("attendees", JSONB(), nullable=True),
        sa.Column("transcript_url", sa.Text(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("summary", JSONB(), nullable=True),
        sa.Column("meeting_type", sa.Text(), nullable=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            nullable=True,
        ),
        sa.Column(
            "skill_run_id",
            sa.Uuid(),
            nullable=True,
        ),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "processing_status",
            sa.Text(),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["skill_run_id"], ["skill_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Create partial indexes
    # Dedup: unique on (tenant_id, provider, external_id) WHERE external_id IS NOT NULL
    op.create_index(
        "idx_meetings_dedup",
        "meetings",
        ["tenant_id", "provider", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    # Account lookup ordered by date
    op.create_index(
        "idx_meetings_account",
        "meetings",
        ["account_id", sa.text("meeting_date DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Per-user meeting history
    op.create_index(
        "idx_meetings_user",
        "meetings",
        ["tenant_id", "user_id", sa.text("meeting_date DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Processing queue
    op.create_index(
        "idx_meetings_pending",
        "meetings",
        ["tenant_id", "processing_status"],
        postgresql_where=sa.text("processing_status = 'pending'"),
    )

    # 3. Enable RLS
    op.execute("ALTER TABLE meetings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE meetings FORCE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON meetings TO app_user")

    # 4. Split-visibility RLS policies
    # Policy A: All tenant members can read meeting metadata (SELECT only)
    op.execute("""
        CREATE POLICY meetings_tenant_read ON meetings
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    # Policy B: Only the owning user can write their own meetings (INSERT/UPDATE/DELETE)
    op.execute("""
        CREATE POLICY meetings_owner_write ON meetings
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            )
    """)


def downgrade() -> None:
    # Drop policies explicitly (though dropping the table would do it too)
    op.execute("DROP POLICY IF EXISTS meetings_tenant_read ON meetings")
    op.execute("DROP POLICY IF EXISTS meetings_owner_write ON meetings")
    op.drop_index("idx_meetings_pending", table_name="meetings")
    op.drop_index("idx_meetings_user", table_name="meetings")
    op.drop_index("idx_meetings_account", table_name="meetings")
    op.drop_index("idx_meetings_dedup", table_name="meetings")
    op.drop_table("meetings")
