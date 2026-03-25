"""rename public.users to public.profiles, drop email + is_anonymous columns

Revision ID: 024_users_to_profiles
Revises: 023_tenant_company_link
Create Date: 2026-03-25

The public.users table duplicates email and is_anonymous from Supabase
auth.users. Replace it with a lean profiles table that only holds
app-specific data (name, api_key_encrypted, settings) and references
auth.users(id) via FK.

Because the DB is completely empty, this migration uses DROP TABLE CASCADE
to remove all FK constraints, then recreates them pointing to profiles.
"""

revision = "024_users_to_profiles"
down_revision = "023_tenant_company_link"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    # 1. Drop the users table and cascade all FK constraints
    op.execute("DROP TABLE IF EXISTS public.users CASCADE")

    # 2. Create the lean profiles table
    op.execute("""
        CREATE TABLE public.profiles (
            id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
            name TEXT,
            api_key_encrypted BYTEA,
            settings JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # 3. Create index on created_at
    op.execute("CREATE INDEX idx_profiles_created_at ON public.profiles(created_at)")

    # 4. Recreate all FK constraints that previously pointed to users(id)
    op.execute("ALTER TABLE public.user_tenants ADD CONSTRAINT fk_user_tenants_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.onboarding_sessions ADD CONSTRAINT fk_onboarding_sessions_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.invites ADD CONSTRAINT fk_invites_invited_by FOREIGN KEY (invited_by) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.context_entries ADD CONSTRAINT fk_context_entries_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.skill_runs ADD CONSTRAINT fk_skill_runs_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.uploaded_files ADD CONSTRAINT fk_uploaded_files_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.integrations ADD CONSTRAINT fk_integrations_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.work_items ADD CONSTRAINT fk_work_items_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.focuses ADD CONSTRAINT fk_focuses_created_by FOREIGN KEY (created_by) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.user_focuses ADD CONSTRAINT fk_user_focuses_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.suggestion_dismissals ADD CONSTRAINT fk_suggestion_dismissals_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.work_streams ADD CONSTRAINT fk_work_streams_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.nudge_interactions ADD CONSTRAINT fk_nudge_interactions_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.meeting_classifications ADD CONSTRAINT fk_meeting_classifications_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.documents ADD CONSTRAINT fk_documents_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.emails ADD CONSTRAINT fk_emails_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")
    op.execute("ALTER TABLE public.email_voice_profiles ADD CONSTRAINT fk_email_voice_profiles_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id)")


def downgrade() -> None:
    # Drop profiles and recreate original users table
    op.execute("DROP TABLE IF EXISTS public.profiles CASCADE")

    op.execute("""
        CREATE TABLE public.users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT UNIQUE,
            name TEXT,
            is_anonymous BOOLEAN DEFAULT false,
            api_key_encrypted BYTEA,
            settings JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # Recreate original FK constraints pointing to users(id)
    op.execute("ALTER TABLE public.user_tenants ADD CONSTRAINT fk_user_tenants_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.onboarding_sessions ADD CONSTRAINT fk_onboarding_sessions_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.invites ADD CONSTRAINT fk_invites_invited_by FOREIGN KEY (invited_by) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.context_entries ADD CONSTRAINT fk_context_entries_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.skill_runs ADD CONSTRAINT fk_skill_runs_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.uploaded_files ADD CONSTRAINT fk_uploaded_files_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.integrations ADD CONSTRAINT fk_integrations_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.work_items ADD CONSTRAINT fk_work_items_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.focuses ADD CONSTRAINT fk_focuses_created_by FOREIGN KEY (created_by) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.user_focuses ADD CONSTRAINT fk_user_focuses_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.suggestion_dismissals ADD CONSTRAINT fk_suggestion_dismissals_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.work_streams ADD CONSTRAINT fk_work_streams_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.nudge_interactions ADD CONSTRAINT fk_nudge_interactions_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.meeting_classifications ADD CONSTRAINT fk_meeting_classifications_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.documents ADD CONSTRAINT fk_documents_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.emails ADD CONSTRAINT fk_emails_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
    op.execute("ALTER TABLE public.email_voice_profiles ADD CONSTRAINT fk_email_voice_profiles_user_id FOREIGN KEY (user_id) REFERENCES public.users(id)")
