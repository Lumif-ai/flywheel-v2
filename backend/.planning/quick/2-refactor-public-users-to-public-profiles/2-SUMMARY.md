---
phase: quick-2
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, supabase, orm, migration]

# Dependency graph
requires:
  - phase: 46-onboarding-resilience
    provides: "users table, FK constraints, tenant-company link"
provides:
  - "profiles table replacing users (lean, no email/is_anonymous)"
  - "Migration 024 with complete DROP CASCADE + CREATE + FK recreation SQL"
  - "Profile ORM model with all FK references updated"
affects: [auth, admin, onboarding, focus, tenant, briefing, skill-executor]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "email and is_anonymous read from JWT TokenPayload, never from DB"
    - "Profile table only holds app-specific data (name, api_key, settings)"

key-files:
  created:
    - alembic/versions/024_users_to_profiles.py
  modified:
    - src/flywheel/db/models.py
    - src/flywheel/auth/anonymous.py
    - src/flywheel/api/auth.py
    - src/flywheel/api/admin.py
    - src/flywheel/api/onboarding.py
    - src/flywheel/api/focus.py
    - src/flywheel/api/tenant.py
    - src/flywheel/api/user.py
    - src/flywheel/api/deps.py
    - src/flywheel/api/briefing.py
    - src/flywheel/services/anonymous_cleanup.py
    - src/flywheel/services/briefing.py
    - src/flywheel/services/nudge_engine.py
    - src/flywheel/services/team_onboarding.py
    - src/flywheel/services/skill_executor.py

key-decisions:
  - "Profile table references auth.users(id) ON DELETE CASCADE -- Supabase manages identity"
  - "email and is_anonymous fields removed from Profile -- read from JWT TokenPayload"
  - "Admin anonymous stats set to 0 with TODO for Supabase Admin API query"
  - "Tenant invite email-based user dedup removed with TODO -- acceptable for empty DB"

patterns-established:
  - "User identity data (email, is_anonymous) comes from JWT, not DB profile"
  - "Profile is lean app-specific storage: name, api_key_encrypted, settings"

# Metrics
duration: 8min
completed: 2026-03-25
---

# Quick Task 2: Refactor public.users to public.profiles Summary

**Replaced public.users with lean public.profiles table, removing email/is_anonymous duplication from Supabase auth.users across 15 files and 1 migration**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-25T00:50:53Z
- **Completed:** 2026-03-25T00:59:38Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments
- Created migration 024 with DROP users CASCADE, CREATE profiles, and all 17 FK constraint recreations
- Renamed User ORM model to Profile, removed email and is_anonymous columns
- Updated all 14 source files importing or using User to use Profile instead
- All Python imports resolve, FastAPI app starts without errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Create migration and update ORM model** - `98d0e0c` (feat)
2. **Task 2: Update all imports and usages across the codebase** - `ee2eccf` (refactor)

## Files Created/Modified
- `alembic/versions/024_users_to_profiles.py` - Migration: DROP users CASCADE, CREATE profiles, recreate FKs
- `src/flywheel/db/models.py` - Profile model replacing User, all ForeignKey("profiles.id")
- `src/flywheel/auth/anonymous.py` - pg_insert(Profile) with just id (no email/is_anonymous)
- `src/flywheel/api/auth.py` - /me returns email from JWT; Profile for api-key ops
- `src/flywheel/api/admin.py` - anonymous_count=0 with TODO for Supabase Admin API
- `src/flywheel/api/onboarding.py` - Profile(id=user.sub) without email in promote
- `src/flywheel/api/focus.py` - Profile in member queries, email=None
- `src/flywheel/api/tenant.py` - Removed email-based user dedup in invite, Profile in members
- `src/flywheel/api/user.py` - Profile for settings/delete operations
- `src/flywheel/api/deps.py` - Updated docstring
- `src/flywheel/api/briefing.py` - Profile.api_key_encrypted for BYOK check
- `src/flywheel/services/anonymous_cleanup.py` - Profile for stale user cleanup
- `src/flywheel/services/briefing.py` - Profile.name, Profile.settings
- `src/flywheel/services/nudge_engine.py` - Profile.created_at for cadence check
- `src/flywheel/services/team_onboarding.py` - Profile for stream join settings
- `src/flywheel/services/skill_executor.py` - Profile.api_key_encrypted for BYOK

## Decisions Made
- Profile table references auth.users(id) ON DELETE CASCADE so Supabase manages identity lifecycle
- email and is_anonymous removed from Profile -- always read from JWT TokenPayload
- Admin dashboard anonymous stats set to 0 with TODO for future Supabase Admin API integration
- Tenant invite email-based user lookup removed (TODO) -- acceptable for empty DB, no data loss risk

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed 5 additional files not in plan's file list**
- **Found during:** Task 2 (comprehensive grep)
- **Issue:** services/briefing.py, services/nudge_engine.py, services/team_onboarding.py, services/skill_executor.py, and api/briefing.py all imported and used User from models but were not listed in the plan's files_modified
- **Fix:** Updated all 5 files: import Profile, replace User.id/User.name/User.settings/User.api_key_encrypted references
- **Files modified:** 5 service/API files
- **Verification:** All imports resolve, no remaining User references in src/flywheel/
- **Committed in:** ee2eccf (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix -- these files would have ImportError at runtime without the update. No scope creep.

## Issues Encountered
None

## User Setup Required

**Migration must be run manually in Supabase SQL Editor.** See migration SQL below.

## Next Phase Readiness
- Backend is ready to run against the new schema once migration is applied
- TODOs remain for email-based queries (admin stats, tenant invite dedup, focus member emails) -- these need Supabase Admin API integration in a future task

---
*Phase: quick-2*
*Completed: 2026-03-25*
