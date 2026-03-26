"""Add CRM tables: accounts, account_contacts, outreach_activities.

Adds three tenant-scoped CRM tables with full RLS policies and indexes.
Also adds nullable account_id FK column to context_entries for linking
context items to CRM accounts.

Revision ID: 027_crm_tables
Revises: 026_docs_storage_nullable
Create Date: 2026-03-26

DATA-01 -- the database schema foundation for all CRM functionality.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "027_crm_tables"
down_revision: Union[str, None] = "026_docs_storage_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that need RLS in this migration
CRM_TABLES = ["accounts", "account_contacts", "outreach_activities"]


def upgrade() -> None:
    # 1. Create accounts table
    op.create_table(
        "accounts",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'prospect'"), nullable=False),
        sa.Column("fit_score", sa.Numeric(), nullable=True),
        sa.Column("fit_tier", sa.Text(), nullable=True),
        sa.Column("intel", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("last_interaction_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_action_due", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_action_type", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "normalized_name", name="uq_account_tenant_normalized"),
    )
    op.create_index(
        "idx_account_tenant_status",
        "accounts",
        ["tenant_id", "status"],
    )
    op.create_index(
        "idx_account_next_action",
        "accounts",
        ["tenant_id", "next_action_due"],
        postgresql_where=sa.text("next_action_due IS NOT NULL"),
    )

    # 2. Create account_contacts table
    op.create_table(
        "account_contacts",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("role_in_deal", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_contact_account",
        "account_contacts",
        ["account_id"],
    )
    op.create_index(
        "idx_contact_tenant_email",
        "account_contacts",
        ["tenant_id", "email"],
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    # 3. Create outreach_activities table
    op.create_table(
        "outreach_activities",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'sent'"), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["account_contacts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_outreach_account",
        "outreach_activities",
        ["account_id"],
    )
    op.create_index(
        "idx_outreach_tenant_sent",
        "outreach_activities",
        ["tenant_id", sa.text("sent_at DESC")],
    )

    # 4. Add account_id FK to context_entries
    op.add_column(
        "context_entries",
        sa.Column("account_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_context_entry_account",
        "context_entries",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_context_account",
        "context_entries",
        ["account_id"],
        postgresql_where=sa.text("account_id IS NOT NULL"),
    )

    # 5. Enable RLS on all three new CRM tables
    for table in CRM_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_select ON {table}
                FOR SELECT
                USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_insert ON {table}
                FOR INSERT
                WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_update ON {table}
                FOR UPDATE
                USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_delete ON {table}
                FOR DELETE
                USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            """
        )


def downgrade() -> None:
    # 1. Drop account_id column from context_entries
    op.drop_index("idx_context_account", table_name="context_entries")
    op.drop_constraint(
        "fk_context_entry_account", "context_entries", type_="foreignkey"
    )
    op.drop_column("context_entries", "account_id")

    # 2. Drop tables in reverse FK dependency order
    #    (outreach_activities -> account_contacts -> accounts)
    #    RLS policies are dropped automatically with the tables.
    op.drop_index("idx_outreach_tenant_sent", table_name="outreach_activities")
    op.drop_index("idx_outreach_account", table_name="outreach_activities")
    op.drop_table("outreach_activities")

    op.drop_index("idx_contact_tenant_email", table_name="account_contacts")
    op.drop_index("idx_contact_account", table_name="account_contacts")
    op.drop_table("account_contacts")

    op.drop_index("idx_account_next_action", table_name="accounts")
    op.drop_index("idx_account_tenant_status", table_name="accounts")
    op.drop_table("accounts")
