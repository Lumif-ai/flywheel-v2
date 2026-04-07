"""Verify migration counts and rename old tables to *_legacy.

Runs three verification assertions BEFORE renaming:
1. Pipeline entry count == accounts + non-graduated leads
2. Contact count == account_contacts + non-graduated lead_contacts
3. Zero orphan meetings/tasks/context_entries with account_id but no pipeline_entry_id

Then renames 6 tables to *_legacy and 2 unique indexes.

PgBouncer NOTE: Each DDL RENAME is a separate op.execute() call.
When applying via Supabase SQL Editor, run each DDL statement separately.

Revision ID: 047_legacy_rename
Revises: 046_fk_retarget_
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "047_legacy_rename"
down_revision: Union[str, None] = "046_fk_retarget_"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # Part 1: Verification queries (DML — safe to batch)
    # ---------------------------------------------------------------
    conn = op.get_bind()

    # Verification 1: Pipeline entry count
    counts = conn.execute(text("""
        SELECT
            (SELECT count(*) FROM accounts) AS account_count,
            (SELECT count(*) FROM leads WHERE graduated_at IS NULL) AS non_grad_lead_count,
            (SELECT count(*) FROM pipeline_entries) AS pipeline_count
    """)).fetchone()
    expected = counts.account_count + counts.non_grad_lead_count
    assert counts.pipeline_count == expected, (
        f"Pipeline entry count mismatch: expected {expected} "
        f"(accounts={counts.account_count} + leads={counts.non_grad_lead_count}), "
        f"got {counts.pipeline_count}"
    )

    # Verification 2: Contact count
    contacts_result = conn.execute(text("""
        SELECT
            (SELECT count(*) FROM account_contacts) AS ac_count,
            (SELECT count(*) FROM lead_contacts lc
             JOIN leads l ON lc.lead_id = l.id
             WHERE l.graduated_at IS NULL) AS lc_count,
            (SELECT count(*) FROM contacts) AS unified_count
    """)).fetchone()
    expected_contacts = contacts_result.ac_count + contacts_result.lc_count
    assert contacts_result.unified_count == expected_contacts, (
        f"Contact count mismatch: expected {expected_contacts} "
        f"(account_contacts={contacts_result.ac_count} + lead_contacts={contacts_result.lc_count}), "
        f"got {contacts_result.unified_count}"
    )

    # Verification 3: FK retarget completeness
    orphans = conn.execute(text("""
        SELECT
            (SELECT count(*) FROM meetings WHERE account_id IS NOT NULL AND pipeline_entry_id IS NULL) AS orphan_meetings,
            (SELECT count(*) FROM tasks WHERE account_id IS NOT NULL AND pipeline_entry_id IS NULL) AS orphan_tasks,
            (SELECT count(*) FROM context_entries WHERE account_id IS NOT NULL AND pipeline_entry_id IS NULL) AS orphan_context
    """)).fetchone()
    assert orphans.orphan_meetings == 0, (
        f"Found {orphans.orphan_meetings} meetings with account_id but no pipeline_entry_id"
    )
    assert orphans.orphan_tasks == 0, (
        f"Found {orphans.orphan_tasks} tasks with account_id but no pipeline_entry_id"
    )
    assert orphans.orphan_context == 0, (
        f"Found {orphans.orphan_context} context_entries with account_id but no pipeline_entry_id"
    )

    print(
        f"VERIFICATION PASSED: {counts.pipeline_count} pipeline entries, "
        f"{contacts_result.unified_count} contacts, 0 orphans"
    )

    # ---------------------------------------------------------------
    # Part 2: Legacy renames (DDL — each its own op.execute)
    # ---------------------------------------------------------------

    # Table renames
    op.execute(text("ALTER TABLE leads RENAME TO leads_legacy"))
    op.execute(text("ALTER TABLE accounts RENAME TO accounts_legacy"))
    op.execute(text("ALTER TABLE lead_contacts RENAME TO lead_contacts_legacy"))
    op.execute(text("ALTER TABLE account_contacts RENAME TO account_contacts_legacy"))
    op.execute(text("ALTER TABLE lead_messages RENAME TO lead_messages_legacy"))
    op.execute(text("ALTER TABLE outreach_activities RENAME TO outreach_activities_legacy"))

    # Index renames to avoid naming conflicts
    op.execute(text(
        "ALTER INDEX IF EXISTS uq_lead_tenant_owner_normalized "
        "RENAME TO uq_lead_legacy_tenant_owner_normalized"
    ))
    op.execute(text(
        "ALTER INDEX IF EXISTS uq_account_tenant_normalized "
        "RENAME TO uq_account_legacy_tenant_normalized"
    ))


def downgrade() -> None:
    # Reverse index renames first
    op.execute(text(
        "ALTER INDEX IF EXISTS uq_account_legacy_tenant_normalized "
        "RENAME TO uq_account_tenant_normalized"
    ))
    op.execute(text(
        "ALTER INDEX IF EXISTS uq_lead_legacy_tenant_owner_normalized "
        "RENAME TO uq_lead_tenant_owner_normalized"
    ))

    # Reverse table renames
    op.execute(text("ALTER TABLE outreach_activities_legacy RENAME TO outreach_activities"))
    op.execute(text("ALTER TABLE lead_messages_legacy RENAME TO lead_messages"))
    op.execute(text("ALTER TABLE account_contacts_legacy RENAME TO account_contacts"))
    op.execute(text("ALTER TABLE lead_contacts_legacy RENAME TO lead_contacts"))
    op.execute(text("ALTER TABLE accounts_legacy RENAME TO accounts"))
    op.execute(text("ALTER TABLE leads_legacy RENAME TO leads"))
