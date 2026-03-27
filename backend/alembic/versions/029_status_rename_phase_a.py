"""Phase A of DM-03: add relationship_status and pipeline_stage columns.

This is Phase A of a two-phase zero-downtime rename of the status column.
Phase A (this migration): add the two new columns as nullable, copy data from
status, then set NOT NULL. The old status column is intentionally left alive
so existing v2.0 API code reading account.status continues to work without
any changes.

Phase B (deferred until after stable deploy): drop the status column once all
API consumers have been migrated to read relationship_status / pipeline_stage.

DM-03 spec: relationship_status and pipeline_stage both default-copy from status
so there is zero semantic loss during the transition window.

Revision ID: 029_status_phase_a
Revises: 028_acct_ext
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "029_status_phase_a"
down_revision: Union[str, None] = "028_acct_ext"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add new columns as nullable so existing rows are unaffected.
    op.add_column("accounts", sa.Column("relationship_status", sa.Text(), nullable=True))
    op.add_column("accounts", sa.Column("pipeline_stage", sa.Text(), nullable=True))

    # Step 2: Copy data from the existing status column to both new columns.
    # After this UPDATE every row has a non-NULL value, making Step 3 safe.
    op.execute(
        sa.text("UPDATE accounts SET relationship_status = status, pipeline_stage = status")
    )

    # Step 3: Set NOT NULL now that all rows have values.
    op.alter_column("accounts", "relationship_status", nullable=False)
    op.alter_column("accounts", "pipeline_stage", nullable=False)

    # Step 4: Add composite indexes (tenant_id + new column) for query performance.
    # Mirrors the existing idx_account_tenant_status pattern.
    op.create_index(
        "idx_account_relationship_status",
        "accounts",
        ["tenant_id", "relationship_status"],
    )
    op.create_index(
        "idx_account_pipeline_stage",
        "accounts",
        ["tenant_id", "pipeline_stage"],
    )


def downgrade() -> None:
    op.drop_index("idx_account_pipeline_stage", table_name="accounts")
    op.drop_index("idx_account_relationship_status", table_name="accounts")
    op.drop_column("accounts", "pipeline_stage")
    op.drop_column("accounts", "relationship_status")
