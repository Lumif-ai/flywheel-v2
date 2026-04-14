"""broker_schema_mods_02 — destructive: seed, constraints, drops

Revision ID: 061_broker_schema_mods_02
Revises: 060_broker_schema_mods_01
Create Date: 2026-04-15

NOTE: upgrade() is intentionally empty (pass). The actual migration is
applied by broker_schema_mods_02.py via individual committed transactions
(PgBouncer workaround — multi-statement DDL transactions are silently
rolled back by Supabase's PgBouncer pooler).

The downgrade() re-adds columns and drops CHECK constraints for schema
reversibility. Data loss is acceptable for downgrade (seed data already
consumed in upgrade path).
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "061_broker_schema_mods_02"
down_revision: Union[str, None] = "060_broker_schema_mods_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    # broker_projects — re-add 7 dropped columns
    op.add_column("broker_projects", sa.Column("pipeline_entry_id", postgresql.UUID(), nullable=True))
    op.add_column("broker_projects", sa.Column("recommendation_subject", sa.Text(), nullable=True))
    op.add_column("broker_projects", sa.Column("recommendation_body", sa.Text(), nullable=True))
    op.add_column("broker_projects", sa.Column("recommendation_status", sa.String(50), nullable=True))
    op.add_column("broker_projects", sa.Column("recommendation_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("broker_projects", sa.Column("recommendation_recipient", sa.Text(), nullable=True))
    op.add_column("broker_projects", sa.Column("email_thread_ids", postgresql.ARRAY(sa.Text()), nullable=True))
    # carrier_quotes — re-add 6 dropped columns
    op.add_column("carrier_quotes", sa.Column("draft_subject", sa.Text(), nullable=True))
    op.add_column("carrier_quotes", sa.Column("draft_body", sa.Text(), nullable=True))
    op.add_column("carrier_quotes", sa.Column("draft_status", sa.String(50), nullable=True))
    op.add_column("carrier_quotes", sa.Column("is_best_price", sa.Boolean(), nullable=True))
    op.add_column("carrier_quotes", sa.Column("is_best_coverage", sa.Boolean(), nullable=True))
    op.add_column("carrier_quotes", sa.Column("is_recommended", sa.Boolean(), nullable=True))
    # carrier_configs — re-add 2 dropped columns
    op.add_column("carrier_configs", sa.Column("carrier_pipeline_entry_id", postgresql.UUID(), nullable=True))
    op.add_column("carrier_configs", sa.Column("email_address", sa.Text(), nullable=True))
    # Drop CHECK constraints that were added in upgrade
    op.drop_constraint("chk_broker_projects_status", "broker_projects")
    op.drop_constraint("chk_broker_projects_approval_status", "broker_projects")
    op.drop_constraint("chk_broker_projects_analysis_status", "broker_projects")
    op.drop_constraint("chk_carrier_quotes_status", "carrier_quotes")
    op.drop_constraint("chk_carrier_quotes_confidence", "carrier_quotes")
    op.drop_constraint("chk_project_coverages_gap_status", "project_coverages")
    op.drop_constraint("chk_project_coverages_confidence", "project_coverages")
    op.drop_constraint("chk_project_coverages_source", "project_coverages")
    op.drop_constraint("chk_broker_activities_actor_type", "broker_activities")
    op.drop_constraint("fk_broker_activities_document_id", "broker_activities")
