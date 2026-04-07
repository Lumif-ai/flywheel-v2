---
phase: quick-2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - alembic/versions/024_users_to_profiles.py
  - src/flywheel/db/models.py
  - src/flywheel/auth/anonymous.py
  - src/flywheel/api/deps.py
  - src/flywheel/api/auth.py
  - src/flywheel/api/admin.py
  - src/flywheel/api/onboarding.py
  - src/flywheel/api/focus.py
  - src/flywheel/api/tenant.py
  - src/flywheel/api/user.py
  - src/flywheel/api/chat.py
  - src/flywheel/api/skills.py
  - src/flywheel/services/anonymous_cleanup.py
autonomous: true

must_haves:
  truths:
    - "public.users table no longer exists; public.profiles table exists with correct schema"
    - "All ForeignKey references across all tables point to profiles(id) not users(id)"
    - "No code references User model or users table — all use Profile and profiles"
    - "email and is_anonymous are read from JWT TokenPayload, never from DB profile row"
    - "App starts without import errors"
  artifacts:
    - path: "alembic/versions/024_users_to_profiles.py"
      provides: "Migration SQL: DROP users CASCADE, CREATE profiles, recreate all FK constraints"
    - path: "src/flywheel/db/models.py"
      provides: "Profile model replacing User"
      contains: "class Profile"
    - path: "src/flywheel/auth/anonymous.py"
      provides: "Updated provisioning using Profile model"
      contains: "pg_insert(Profile)"
  key_links:
    - from: "src/flywheel/db/models.py"
      to: "all API files"
      via: "import Profile"
      pattern: "from flywheel\\.db\\.models import.*Profile"
    - from: "src/flywheel/api/auth.py"
      to: "TokenPayload"
      via: "user.email and user.is_anonymous from JWT, not DB"
      pattern: "user\\.email|user\\.is_anonymous"
---

<objective>
Refactor public.users to public.profiles across the entire flywheel-v2 backend.

Purpose: The public.users table duplicates email and is_anonymous from Supabase auth.users. Replacing it with a lean profiles table that only holds app-specific data (name, api_key, settings) and references auth.users(id) via FK.

Output: Migration file, updated ORM model, and all imports/usages across the codebase updated.
</objective>

<execution_context>
@/Users/sharan/.claude/get-shit-done/workflows/execute-plan.md
@/Users/sharan/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/flywheel/db/models.py
@src/flywheel/auth/anonymous.py
@src/flywheel/auth/jwt.py
@src/flywheel/api/auth.py
@src/flywheel/api/admin.py
@src/flywheel/api/onboarding.py
@src/flywheel/api/focus.py
@src/flywheel/api/tenant.py
@src/flywheel/api/user.py
@src/flywheel/services/anonymous_cleanup.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create migration and update ORM model</name>
  <files>
    alembic/versions/024_users_to_profiles.py
    src/flywheel/db/models.py
  </files>
  <action>
1. Create alembic migration `024_users_to_profiles.py` with revision chain from 023.

   The upgrade SQL must (in order):
   a. DROP TABLE public.users CASCADE — this cascades all FK constraints referencing users(id) across ALL tables (user_tenants, onboarding_sessions, invites, context_entries, skill_runs, uploaded_files, integrations, work_items, focuses, user_focuses, suggestion_dismissals, work_streams, nudge_interactions, meeting_classifications, documents, emails, email_voice_profiles).
   b. CREATE TABLE public.profiles (id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE, name TEXT, api_key_encrypted BYTEA, settings JSONB DEFAULT '{}', created_at TIMESTAMPTZ DEFAULT now()).
   c. CREATE INDEX idx_profiles_created_at ON public.profiles(created_at).
   d. Recreate ALL foreign key constraints that previously pointed to users(id), now pointing to profiles(id). Every table with a user_id column needs: ALTER TABLE {table} ADD CONSTRAINT fk_{table}_user_id FOREIGN KEY (user_id) REFERENCES public.profiles(id). Tables: user_tenants, onboarding_sessions, invites (invited_by), context_entries, skill_runs, uploaded_files, integrations, work_items, focuses (created_by), user_focuses, suggestion_dismissals, work_streams, nudge_interactions, meeting_classifications, documents, emails, email_voice_profiles.

   The downgrade SQL must reverse this (CREATE TABLE users with original schema, DROP profiles, recreate original FKs). Since DB is empty, this is safe.

   IMPORTANT: Write this as standard alembic op.execute() with raw SQL strings. The user will copy the SQL to run in Supabase SQL Editor.

2. Update models.py:
   - Rename `class User(Base)` to `class Profile(Base)`
   - Change `__tablename__ = "users"` to `__tablename__ = "profiles"`
   - Remove `email` column (Mapped[str | None] with unique=True)
   - Remove `is_anonymous` column (Mapped[bool])
   - Keep: id, name, api_key_encrypted, settings, created_at
   - Update the module docstring to say "profiles" instead of "users"
   - Update ALL ForeignKey("users.id") references throughout the ENTIRE file to ForeignKey("profiles.id") — there are ~18 of these across UserTenant, OnboardingSession, Invite, ContextEntry, SkillRun, UploadedFile, Integration, WorkItem, Focus, UserFocus, SuggestionDismissal, WorkStream, NudgeInteraction, MeetingClassification, Document, Email, EmailVoiceProfile.
  </action>
  <verify>
    Run: `cd /Users/sharan/Projects/flywheel-v2/backend && python3 -c "from flywheel.db.models import Profile, Tenant, UserTenant; print('Model import OK'); print(Profile.__tablename__); assert Profile.__tablename__ == 'profiles'; assert not hasattr(Profile, 'email'); assert not hasattr(Profile, 'is_anonymous'); print('All assertions pass')"`

    Also verify no remaining "users" FK references: `grep -n 'ForeignKey("users' src/flywheel/db/models.py` should return nothing.
  </verify>
  <done>
    Profile model exists with tablename "profiles", no email/is_anonymous columns. All ForeignKey references in models.py point to "profiles.id". Migration file exists with correct up/down SQL.
  </done>
</task>

<task type="auto">
  <name>Task 2: Update all imports and usages across the codebase</name>
  <files>
    src/flywheel/auth/anonymous.py
    src/flywheel/api/auth.py
    src/flywheel/api/admin.py
    src/flywheel/api/onboarding.py
    src/flywheel/api/focus.py
    src/flywheel/api/tenant.py
    src/flywheel/api/user.py
    src/flywheel/api/chat.py
    src/flywheel/api/skills.py
    src/flywheel/api/deps.py
    src/flywheel/services/anonymous_cleanup.py
  </files>
  <action>
**Import renames (all files):**
Every `from flywheel.db.models import ... User ...` becomes `... Profile ...`. Files:
- anonymous.py: `User` -> `Profile`
- auth.py: `User` -> `Profile`
- admin.py: `User` -> `Profile`
- onboarding.py: `User` -> `Profile`
- focus.py: `User` -> `Profile` (also `UserFocus`)
- tenant.py: references `User` in joins
- user.py: `User` -> `Profile`
- anonymous_cleanup.py: `User` -> `Profile`

**anonymous.py changes:**
- Change `pg_insert(User)` to `pg_insert(Profile)`
- Remove `email=None, is_anonymous=True` from the values dict
- Just insert `id=user_id` (the minimal profile row)

**auth.py (/me endpoint) changes:**
- `select(User)` -> `select(Profile)`
- `User.id` -> `Profile.id`
- Line 188: `User(id=user.sub, email=user.email)` -> `Profile(id=user.sub)` (no email on Profile)
- Line 232: `email=row.email` -> `email=user.email` (read from JWT token, not DB row)
- Line 223: `email=user.email` is already correct (reads from JWT)
- Line 234: `is_anonymous=user.is_anonymous` is already correct (reads from JWT)

**admin.py changes:**
- Replace `User` with `Profile` in all selects and counts
- The `is_anonymous` detection logic uses `hasattr(User, "is_anonymous")` — since Profile won't have this field, the `hasattr` check will be False. The fallback path uses `User.email.is_(None)` which also won't work since Profile has no email.
- REPLACE the entire anonymous-count logic: instead of querying the Profile table, query via Supabase auth or just remove the anonymous counting (set anonymous_count = 0 with a TODO comment). The admin stats endpoint can't determine anonymity from profiles table alone. Set `anonymous_count = 0` and `total_anonymous_ever = 0` and `anonymous_with_runs = 0` with a comment: `# TODO: query auth.users via Supabase Admin API for anonymous user stats`.

**onboarding.py changes:**
- `User` -> `Profile`
- Line 260: `User(id=user.sub, email=body.email)` -> `Profile(id=user.sub)` (no email column)
- Line 264: `existing_user.email = body.email` -> remove this line entirely (email lives in auth.users, not profiles)
- `user.is_anonymous` checks are fine — they read from JWT TokenPayload

**focus.py changes:**
- `User` -> `Profile`
- Lines 188 and 415: `"email": u.email` -> `"email": None` with a comment `# TODO: email lives in auth.users, fetch via Supabase Admin API if needed`
- The join `User.id` -> `Profile.id` in all queries

**tenant.py changes:**
- `User` -> `Profile` in imports and all query references
- Line 343: `User.email == body.email` -> This query checks if a user exists by email for invite dedup. Since Profile has no email, this lookup needs to go through Supabase. For now: REMOVE this check and add a TODO comment. The invite will proceed without dedup (acceptable for empty DB).
- Line 492: `email=u.email` -> `email=None` with TODO comment (same as focus.py — email not in profiles)

**anonymous_cleanup.py changes:**
- `User` -> `Profile`
- The `hasattr(User, "is_anonymous")` block and `User.email.is_(None)` fallback both break. Replace with: query `Profile.id` joined with `Profile.created_at < cutoff` (all profiles without a corresponding non-anonymous auth user are candidates). Simplify to just select all profiles older than cutoff and let the Supabase Admin API call handle the actual anonymity check. Comment: `# After refactor: all stale profiles are candidates; Supabase delete is idempotent`.

**chat.py and skills.py:**
- These files reference `user.is_anonymous` which comes from TokenPayload (JWT), NOT from the DB model. Verify no `User` import exists. If `User` is imported, change to `Profile`.
- `check_anonymous_run_limit(user.sub, user.is_anonymous, db)` — user here is TokenPayload, this is fine.

**IMPORTANT:** After all changes, do a comprehensive grep for any remaining `User` references from models import and fix them. Run: `grep -rn "from flywheel.db.models import.*User[^TF]" src/` and `grep -rn "User\." src/flywheel/ | grep -v "UserTenant\|UserFocus\|user_id\|user\.\|#"` to catch stragglers.
  </action>
  <verify>
    1. `cd /Users/sharan/Projects/flywheel-v2/backend && python3 -c "from flywheel.db.models import Profile; from flywheel.auth.anonymous import ensure_provisioned; from flywheel.api.auth import router; from flywheel.api.admin import router; from flywheel.api.onboarding import router; from flywheel.api.focus import router; from flywheel.api.tenant import router; print('All imports OK')"` — no ImportError
    2. `grep -rn 'from flywheel.db.models import.*\bUser\b' src/flywheel/` — should return ZERO matches (UserTenant and UserFocus are fine)
    3. `grep -rn 'ForeignKey("users' src/flywheel/` — should return ZERO matches
    4. `grep -rn '\bUser\b' src/flywheel/db/models.py | grep -v UserTenant | grep -v UserFocus | grep -v '# '` — should return ZERO matches for standalone `User` class
  </verify>
  <done>
    All files import Profile instead of User. No code reads email or is_anonymous from the Profile model. anonymous.py inserts minimal profile rows. auth.py reads email/is_anonymous from JWT. Admin stats gracefully handle missing anonymity data. App starts without import errors.
  </done>
</task>

</tasks>

<verification>
1. All model imports resolve: `python3 -c "from flywheel.db import models; print(dir(models))"` shows Profile, not User
2. No stale references: `grep -rn '\bclass User\b\|"users"\|ForeignKey("users' src/flywheel/` returns nothing
3. Migration SQL is syntactically valid (manual review)
4. FastAPI app starts: `cd /Users/sharan/Projects/flywheel-v2/backend && timeout 5 python3 -c "from flywheel.main import app; print('App created OK')"` (may fail on DB connection but should not fail on import)
</verification>

<success_criteria>
- Profile model exists at models.py with tablename "profiles", columns: id, name, api_key_encrypted, settings, created_at
- Zero references to `class User`, `ForeignKey("users.id")`, or `import User` from models remain in src/flywheel/
- Migration 024 exists with complete SQL for DROP users CASCADE + CREATE profiles + all FK recreation
- anonymous.py provisions with just id (no email/is_anonymous)
- auth.py /me endpoint returns email from JWT token, not from DB profile row
- All Python imports resolve without errors
</success_criteria>

<output>
After completion, create `.planning/quick/2-refactor-public-users-to-public-profiles/2-SUMMARY.md`
</output>
