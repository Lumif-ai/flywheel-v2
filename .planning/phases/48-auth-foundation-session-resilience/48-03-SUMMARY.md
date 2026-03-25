---
phase: 48-auth-foundation-session-resilience
plan: 03
subsystem: auth, api
tags: [supabase, oauth, data-migration, anonymous-auth, tenant-scoping]

# Dependency graph
requires:
  - phase: 48-01
    provides: "useOAuthSignIn hook with flywheel-prev-anon-id localStorage capture"
  - phase: 48-02
    provides: "AuthCallback metadata refresh with getUser after promote-oauth"
provides:
  - "POST /onboarding/claim-anonymous-data endpoint for orphaned anonymous data recovery"
  - "AuthCallback claim flow after promote-oauth"
affects: [onboarding, session-management]

# Tech tracking
tech-stack:
  added: []
  patterns: [atomic-data-migration, non-fatal-claim-flow, anonymous-tenant-safety-check]

key-files:
  created: []
  modified:
    - backend/src/flywheel/api/onboarding.py
    - frontend/src/app/AuthCallback.tsx

key-decisions:
  - "Only tenants named 'Anonymous Workspace' with no other linked users can be claimed -- prevents arbitrary tenant takeover"
  - "Data migration uses SQLAlchemy update() bulk operations in single transaction -- atomic or nothing"
  - "Claim failure is non-fatal in AuthCallback -- user gets new account without prior data rather than being blocked"
  - "localStorage cleanup in finally block -- always removes flywheel-prev-anon-id regardless of claim success/failure"

patterns-established:
  - "Anonymous data claim pattern: store anon ID before OAuth, attempt claim after promote, clean up always"
  - "Cross-tenant migration pattern: get_db_unscoped for operations spanning tenant boundaries"

# Metrics
duration: 3min
completed: 2026-03-25
---

# Phase 48 Plan 03: Anonymous Data Claim Endpoint Summary

**Atomic data migration endpoint for orphaned anonymous sessions when OAuth creates a new user, with AuthCallback integration**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-25T09:34:16Z
- **Completed:** 2026-03-25T09:37:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added POST /onboarding/claim-anonymous-data endpoint that atomically migrates ContextEntry, SkillRun, OnboardingSession, Document, and WorkStream from orphaned anonymous tenants
- Security: validates tenant is named "Anonymous Workspace" and has no other linked users before allowing claim
- Cleanup removes old UserTenant, Profile, and Tenant rows after migration
- AuthCallback calls claim endpoint after promote-oauth when flywheel-prev-anon-id exists and differs from current user ID

## Task Commits

Single commit per per-plan strategy:

1. **Task 1 + Task 2** - `da2861a` (feat)

## Files Created/Modified
- `backend/src/flywheel/api/onboarding.py` - Added ClaimAnonymousDataRequest model and claim_anonymous_data endpoint with atomic migration + cleanup
- `frontend/src/app/AuthCallback.tsx` - Added claim flow after promote-oauth with non-fatal error handling and localStorage cleanup

## Decisions Made
- Only "Anonymous Workspace" tenants claimable -- name check prevents claiming arbitrary tenants via spoofed IDs
- Bulk UPDATE per model rather than row-by-row -- efficient for potentially many context entries
- OnboardingSession migrated by tenant_id (consistent with other models) rather than user_id alone
- get_db_unscoped used since claim crosses tenant boundaries (old tenant -> new tenant)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Complete auth foundation: OAuth hook (Plan 01), metadata extraction (Plan 02), and data claim (Plan 03) all wired
- Anonymous-to-authenticated flow is now lossless: session data survives even when linkIdentity fails
- flywheel-prev-anon-id lifecycle complete: stored before OAuth (Plan 01), consumed after OAuth (Plan 03)

## Self-Check: PASSED

All 2 source files verified present. Commit da2861a verified in git log.

---
*Phase: 48-auth-foundation-session-resilience*
*Completed: 2026-03-25*
