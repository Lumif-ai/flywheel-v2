"""Replace tenant-only RLS policies with user-level RLS on 7 tables.

Upgrades RLS enforcement on emails, email_scores, email_drafts,
email_voice_profiles, integrations, work_items, and skill_runs from
tenant-only isolation to user-level isolation. Users within the same
tenant can no longer see each other's personal data.

Session variable app.user_id is already set on every request by the
existing get_tenant_session() helper. These policies simply check it.

Revision ID: 031_user_level_rls
Revises: 030_grad_at
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "031_user_level_rls"
down_revision: Union[str, None] = "030_grad_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # Pattern 1 — Direct user_id (emails, email_voice_profiles)
    # These tables have user_id UUID NOT NULL.
    # Drop 4 per-operation tenant_isolation_* policies, create single
    # user_isolation policy that checks both tenant_id and user_id.
    # -----------------------------------------------------------------------

    # emails
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON emails;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON emails;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON emails;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON emails;")
    op.execute("""
        CREATE POLICY user_isolation ON emails
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            );
    """)

    # email_voice_profiles
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_select ON email_voice_profiles;"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_insert ON email_voice_profiles;"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_update ON email_voice_profiles;"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_delete ON email_voice_profiles;"
    )
    op.execute("""
        CREATE POLICY user_isolation ON email_voice_profiles
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            );
    """)

    # -----------------------------------------------------------------------
    # Pattern 1 continued — integrations (single policy, different name)
    # integrations uses policy name "integrations_tenant_isolation" (not
    # the generic "tenant_isolation" name used by work_items / skill_runs).
    # -----------------------------------------------------------------------

    # integrations
    op.execute(
        "DROP POLICY IF EXISTS integrations_tenant_isolation ON integrations;"
    )
    op.execute("""
        CREATE POLICY user_isolation ON integrations
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            );
    """)

    # -----------------------------------------------------------------------
    # Pattern 2 — Nullable user_id (work_items, skill_runs)
    # user_id is UUID (nullable). Rows with user_id IS NULL are treated as
    # tenant-shared (system-generated). Rows with a user_id are private to
    # that user.
    # -----------------------------------------------------------------------

    # work_items
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON work_items;")
    op.execute("""
        CREATE POLICY user_isolation ON work_items
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND (
                    user_id IS NULL
                    OR user_id = current_setting('app.user_id', true)::uuid
                )
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND (
                    user_id IS NULL
                    OR user_id = current_setting('app.user_id', true)::uuid
                )
            );
    """)

    # skill_runs
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON skill_runs;")
    op.execute("""
        CREATE POLICY user_isolation ON skill_runs
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND (
                    user_id IS NULL
                    OR user_id = current_setting('app.user_id', true)::uuid
                )
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND (
                    user_id IS NULL
                    OR user_id = current_setting('app.user_id', true)::uuid
                )
            );
    """)

    # -----------------------------------------------------------------------
    # Pattern 3 — Subquery via FK (email_scores, email_drafts)
    # These tables do NOT have a user_id column. Ownership is enforced by
    # checking that the parent email row belongs to the current user via a
    # subquery: email_id IN (SELECT id FROM emails WHERE user_id = ...).
    # -----------------------------------------------------------------------

    # email_scores
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON email_scores;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON email_scores;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON email_scores;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON email_scores;")
    op.execute("""
        CREATE POLICY user_isolation ON email_scores
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND email_id IN (
                    SELECT id FROM emails
                    WHERE user_id = current_setting('app.user_id', true)::uuid
                )
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND email_id IN (
                    SELECT id FROM emails
                    WHERE user_id = current_setting('app.user_id', true)::uuid
                )
            );
    """)

    # email_drafts
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON email_drafts;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON email_drafts;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON email_drafts;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON email_drafts;")
    op.execute("""
        CREATE POLICY user_isolation ON email_drafts
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND email_id IN (
                    SELECT id FROM emails
                    WHERE user_id = current_setting('app.user_id', true)::uuid
                )
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND email_id IN (
                    SELECT id FROM emails
                    WHERE user_id = current_setting('app.user_id', true)::uuid
                )
            );
    """)


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Restore original policies from migrations 020_email_models.py and
    # 005_add_integrations_table.py / 002_enable_rls_policies.py.
    # -----------------------------------------------------------------------

    # --- emails: restore 4 per-operation tenant_isolation_* policies ---
    op.execute("DROP POLICY IF EXISTS user_isolation ON emails;")
    op.execute("""
        CREATE POLICY tenant_isolation_select ON emails
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON emails
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON emails
            FOR UPDATE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON emails
            FOR DELETE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)

    # --- email_scores: restore 4 per-operation tenant_isolation_* policies ---
    op.execute("DROP POLICY IF EXISTS user_isolation ON email_scores;")
    op.execute("""
        CREATE POLICY tenant_isolation_select ON email_scores
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON email_scores
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON email_scores
            FOR UPDATE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON email_scores
            FOR DELETE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)

    # --- email_drafts: restore 4 per-operation tenant_isolation_* policies ---
    op.execute("DROP POLICY IF EXISTS user_isolation ON email_drafts;")
    op.execute("""
        CREATE POLICY tenant_isolation_select ON email_drafts
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON email_drafts
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON email_drafts
            FOR UPDATE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON email_drafts
            FOR DELETE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)

    # --- email_voice_profiles: restore 4 per-operation policies ---
    op.execute("DROP POLICY IF EXISTS user_isolation ON email_voice_profiles;")
    op.execute("""
        CREATE POLICY tenant_isolation_select ON email_voice_profiles
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_insert ON email_voice_profiles
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_update ON email_voice_profiles
            FOR UPDATE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_delete ON email_voice_profiles
            FOR DELETE
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
    """)

    # --- integrations: restore original "integrations_tenant_isolation" policy ---
    op.execute("DROP POLICY IF EXISTS user_isolation ON integrations;")
    op.execute("""
        CREATE POLICY integrations_tenant_isolation ON integrations
            FOR ALL
            USING (current_setting('app.tenant_id', true)::uuid = tenant_id)
            WITH CHECK (current_setting('app.tenant_id', true)::uuid = tenant_id);
    """)

    # --- work_items: restore single tenant_isolation policy ---
    op.execute("DROP POLICY IF EXISTS user_isolation ON work_items;")
    op.execute("""
        CREATE POLICY tenant_isolation ON work_items
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            );
    """)

    # --- skill_runs: restore single tenant_isolation policy ---
    op.execute("DROP POLICY IF EXISTS user_isolation ON skill_runs;")
    op.execute("""
        CREATE POLICY tenant_isolation ON skill_runs
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            );
    """)
