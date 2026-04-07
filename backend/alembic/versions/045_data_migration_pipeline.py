"""Migrate data from leads/accounts into unified pipeline tables.

Populates pipeline_entries, contacts, activities, and pipeline_entry_sources
from the old leads, accounts, lead_contacts, account_contacts,
lead_messages, and outreach_activities tables. Preserves UUIDs for
FK retargeting in Plan 02.

All operations are pure DML (INSERT/UPDATE) so PgBouncer transaction
batching works fine — no DDL statements.

Revision ID: 045_data_mig_pipe
Revises: 044_unified_pipeline
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "045_data_mig_pipe"
down_revision: Union[str, None] = "044_unified_pipeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Pre-check: UUID collision guard ──────────────────────────────
    # If any non-graduated lead shares an id with an account, the INSERT
    # into pipeline_entries would violate the PK.  Fail loudly.
    conn = op.get_bind()
    collision_rows = conn.execute(
        text(
            "SELECT l.id FROM leads l "
            "JOIN accounts a ON l.id = a.id "
            "WHERE l.graduated_at IS NULL"
        )
    ).fetchall()
    if collision_rows:
        ids = ", ".join(str(r[0]) for r in collision_rows)
        raise RuntimeError(
            f"UUID collision detected between non-graduated leads and accounts: {ids}. "
            "These must be resolved before running the data migration."
        )

    # ── Step 1: Migrate accounts -> pipeline_entries ─────────────────
    op.execute(
        text("""
            INSERT INTO pipeline_entries (
                id, tenant_id, owner_id, entity_type, name, normalized_name, domain,
                stage, fit_score, fit_tier, relationship_type, source, intel,
                ai_summary, last_activity_at, created_at, updated_at
            )
            SELECT
                a.id,
                a.tenant_id,
                a.owner_id,
                COALESCE(a.entity_level, 'company'),
                a.name,
                a.normalized_name,
                a.domain,
                CASE a.pipeline_stage
                    WHEN 'prospect' THEN 'identified'
                    WHEN 'identified' THEN 'identified'
                    WHEN 'qualified' THEN 'qualified'
                    WHEN 'engaged' THEN 'engaged'
                    WHEN 'replied' THEN 'engaged'
                    WHEN 'customer' THEN 'customer'
                    WHEN 'churned' THEN 'churned'
                    ELSE 'identified'
                END,
                a.fit_score,
                a.fit_tier,
                a.relationship_type,
                a.source,
                a.intel,
                a.ai_summary,
                a.last_interaction_at,
                a.created_at,
                a.updated_at
            FROM accounts a
        """)
    )

    # ── Step 2: Migrate non-graduated leads -> pipeline_entries ──────
    op.execute(
        text("""
            INSERT INTO pipeline_entries (
                id, tenant_id, owner_id, entity_type, name, normalized_name, domain,
                stage, fit_score, fit_tier, fit_rationale, relationship_type, source,
                intel, created_at, updated_at
            )
            SELECT
                l.id,
                l.tenant_id,
                l.owner_id,
                'company',
                l.name,
                l.normalized_name,
                l.domain,
                COALESCE(
                    (SELECT CASE MAX(
                        CASE lc.pipeline_stage
                            WHEN 'replied' THEN 6
                            WHEN 'sent' THEN 5
                            WHEN 'drafted' THEN 4
                            WHEN 'researched' THEN 3
                            WHEN 'scored' THEN 2
                            WHEN 'scraped' THEN 1
                            ELSE 0
                        END
                    )
                        WHEN 6 THEN 'engaged'
                        WHEN 5 THEN 'engaged'
                        WHEN 4 THEN 'qualified'
                        WHEN 3 THEN 'qualified'
                        WHEN 2 THEN 'qualified'
                        WHEN 1 THEN 'identified'
                        ELSE 'identified'
                    END
                    FROM lead_contacts lc WHERE lc.lead_id = l.id),
                    'identified'
                ),
                l.fit_score,
                l.fit_tier,
                l.fit_rationale,
                '{prospect}',
                l.source,
                CASE
                    WHEN l.purpose IS NOT NULL AND l.campaign IS NOT NULL THEN
                        l.intel || jsonb_build_object('legacy_purpose', l.purpose, 'campaign', l.campaign)
                    WHEN l.purpose IS NOT NULL THEN
                        l.intel || jsonb_build_object('legacy_purpose', l.purpose)
                    WHEN l.campaign IS NOT NULL THEN
                        l.intel || jsonb_build_object('campaign', l.campaign)
                    ELSE l.intel
                END,
                l.created_at,
                l.updated_at
            FROM leads l
            WHERE l.graduated_at IS NULL
        """)
    )

    # ── Step 3: Enrich graduated-lead data into account pipeline entries
    op.execute(
        text("""
            UPDATE pipeline_entries pe
            SET
                intel = pe.intel || l.intel ||
                    CASE
                        WHEN l.purpose IS NOT NULL THEN jsonb_build_object('legacy_purpose', l.purpose)
                        ELSE '{}'::jsonb
                    END ||
                    CASE
                        WHEN l.campaign IS NOT NULL THEN jsonb_build_object('campaign', l.campaign)
                        ELSE '{}'::jsonb
                    END,
                fit_rationale = COALESCE(pe.fit_rationale, l.fit_rationale),
                fit_score = GREATEST(pe.fit_score, l.fit_score),
                created_at = LEAST(pe.created_at, l.created_at)
            FROM leads l
            WHERE l.account_id = pe.id
              AND l.graduated_at IS NOT NULL
        """)
    )

    # ── Step 4: Migrate account_contacts -> contacts ─────────────────
    op.execute(
        text("""
            INSERT INTO contacts (
                id, tenant_id, pipeline_entry_id, name, email, title, role,
                linkedin_url, notes, is_primary, created_at, updated_at
            )
            SELECT
                ac.id,
                ac.tenant_id,
                ac.account_id,
                ac.name,
                ac.email,
                ac.title,
                ac.role_in_deal,
                ac.linkedin_url,
                ac.notes,
                false,
                ac.created_at,
                ac.updated_at
            FROM account_contacts ac
        """)
    )

    # ── Step 5: Migrate lead_contacts -> contacts (non-graduated only)
    op.execute(
        text("""
            INSERT INTO contacts (
                id, tenant_id, pipeline_entry_id, name, email, title, role,
                linkedin_url, notes, is_primary, created_at, updated_at
            )
            SELECT
                lc.id,
                lc.tenant_id,
                lc.lead_id,
                lc.name,
                lc.email,
                lc.title,
                lc.role,
                lc.linkedin_url,
                lc.notes,
                false,
                lc.created_at,
                lc.updated_at
            FROM lead_contacts lc
            JOIN leads l ON lc.lead_id = l.id
            WHERE l.graduated_at IS NULL
        """)
    )

    # ── Step 6: Migrate outreach_activities -> activities ─────────────
    op.execute(
        text("""
            INSERT INTO activities (
                id, tenant_id, pipeline_entry_id, contact_id, type, channel,
                direction, status, subject, body_preview, metadata, occurred_at,
                created_at
            )
            SELECT
                oa.id,
                oa.tenant_id,
                oa.account_id,
                oa.contact_id,
                CASE
                    WHEN oa.channel = 'email' THEN 'email'
                    WHEN oa.channel = 'linkedin' THEN 'linkedin_message'
                    WHEN oa.channel = 'call' THEN 'call'
                    ELSE 'email'
                END,
                oa.channel,
                oa.direction,
                oa.status,
                oa.subject,
                oa.body_preview,
                oa.metadata || CASE
                    WHEN oa.from_email IS NOT NULL
                    THEN jsonb_build_object('from_email', oa.from_email)
                    ELSE '{}'::jsonb
                END,
                COALESCE(oa.sent_at, oa.created_at),
                oa.created_at
            FROM outreach_activities oa
        """)
    )

    # ── Step 7a: Migrate lead_messages -> activities (non-graduated) ──
    op.execute(
        text("""
            INSERT INTO activities (
                id, tenant_id, pipeline_entry_id, contact_id, type, channel,
                direction, status, subject, body_preview, metadata, occurred_at,
                created_at
            )
            SELECT
                lm.id,
                lm.tenant_id,
                l.id,
                lm.contact_id,
                CASE
                    WHEN lm.channel = 'linkedin' THEN 'linkedin_message'
                    ELSE 'email'
                END,
                lm.channel,
                'outbound',
                lm.status,
                lm.subject,
                LEFT(lm.body, 500),
                lm.metadata || jsonb_build_object(
                    'step_number', lm.step_number,
                    'from_email', lm.from_email,
                    'drafted_at', lm.drafted_at,
                    'sent_at', lm.sent_at,
                    'replied_at', lm.replied_at
                ),
                COALESCE(lm.sent_at, lm.drafted_at, lm.created_at),
                lm.created_at
            FROM lead_messages lm
            JOIN lead_contacts lc ON lm.contact_id = lc.id
            JOIN leads l ON lc.lead_id = l.id
            WHERE l.graduated_at IS NULL
        """)
    )

    # ── Step 7b: Graduated lead draft messages (not copied during graduation)
    op.execute(
        text("""
            INSERT INTO activities (
                id, tenant_id, pipeline_entry_id, contact_id, type, channel,
                direction, status, subject, body_preview, metadata, occurred_at,
                created_at
            )
            SELECT
                lm.id,
                lm.tenant_id,
                l.account_id,
                NULL,
                CASE
                    WHEN lm.channel = 'linkedin' THEN 'linkedin_message'
                    ELSE 'email'
                END,
                lm.channel,
                'outbound',
                lm.status,
                lm.subject,
                LEFT(lm.body, 500),
                lm.metadata || jsonb_build_object(
                    'step_number', lm.step_number,
                    'from_email', lm.from_email,
                    'drafted_at', lm.drafted_at,
                    'legacy_source', 'lead_message_draft'
                ),
                COALESCE(lm.drafted_at, lm.created_at),
                lm.created_at
            FROM lead_messages lm
            JOIN lead_contacts lc ON lm.contact_id = lc.id
            JOIN leads l ON lc.lead_id = l.id
            WHERE l.graduated_at IS NOT NULL
              AND lm.status = 'drafted'
        """)
    )

    # ── Step 8: Create pipeline_entry_sources rows ───────────────────
    op.execute(
        text("""
            INSERT INTO pipeline_entry_sources (tenant_id, pipeline_entry_id, source_type, created_at)
            SELECT
                pe.tenant_id,
                pe.id,
                CASE
                    WHEN pe.source ILIKE '%scrape%' OR pe.source ILIKE '%gtm%' THEN 'gtm_scrape'
                    WHEN pe.source ILIKE '%meeting%' THEN 'meeting'
                    WHEN pe.source ILIKE '%email%' THEN 'email'
                    WHEN pe.source ILIKE '%import%' THEN 'import'
                    ELSE 'manual'
                END,
                pe.created_at
            FROM pipeline_entries pe
        """)
    )

    # ── Step 9: Derive channels array from activities ────────────────
    op.execute(
        text("""
            UPDATE pipeline_entries pe
            SET channels = sub.channels
            FROM (
                SELECT pipeline_entry_id, array_agg(DISTINCT channel) AS channels
                FROM activities
                WHERE channel IS NOT NULL
                GROUP BY pipeline_entry_id
            ) sub
            WHERE sub.pipeline_entry_id = pe.id
        """)
    )


def downgrade() -> None:
    # Reverse order: clear child tables first, then pipeline_entries
    op.execute(text("DELETE FROM pipeline_entry_sources"))
    op.execute(text("DELETE FROM activities"))
    op.execute(text("DELETE FROM contacts"))
    op.execute(text("DELETE FROM pipeline_entries"))
