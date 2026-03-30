---
phase: 71-voice-settings-ui
plan: 01
subsystem: api
tags: [fastapi, pydantic, voice-profile, sqlalchemy, background-tasks]

requires:
  - phase: 70-voice-profile-expansion
    provides: EmailVoiceProfile model with 10 fields
provides:
  - GET /email/voice-profile endpoint returning full profile or null
  - PATCH /email/voice-profile endpoint updating tone and sign_off only
  - POST /email/voice-profile/reset endpoint with background re-extraction
affects: [71-02 voice settings UI, frontend voice profile integration]

tech-stack:
  added: []
  patterns: [voice profile CRUD via existing email router, read-only enforcement via restricted Pydantic model]

key-files:
  created: []
  modified: [backend/src/flywheel/api/email.py]

key-decisions:
  - "All three voice profile endpoints added to existing email.py router (no new router file)"
  - "VoiceProfilePatch restricts updates to tone and sign_off only -- 8 fields remain read-only"
  - "Reset endpoint follows trigger_sync background task pattern with tenant_session for RLS"

patterns-established:
  - "Read-only field enforcement: Pydantic model with only updatable fields, exclude_none=True for partial updates"
  - "Background re-extraction: delete row then trigger voice_profile_init in background task"

duration: 2min
completed: 2026-03-30
---

# Phase 71 Plan 01: Voice Profile API Endpoints Summary

**Three REST endpoints (GET, PATCH, POST reset) for voice profile CRUD with background re-extraction on reset**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T00:29:45Z
- **Completed:** 2026-03-30T00:32:17Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- GET /email/voice-profile returns full 10-field profile with samples_analyzed and updated_at, or null when no profile exists
- PATCH /email/voice-profile updates only tone and sign_off (8 fields enforced read-only via VoiceProfilePatch model), returns 404 when no profile
- POST /email/voice-profile/reset deletes profile, verifies Gmail integration, triggers background voice_profile_init re-extraction

## Task Commits

Per-plan commit (all tasks in one commit):

1. **Task 1: Add Pydantic models and GET/PATCH voice profile endpoints** - `358b2eb` (feat)
2. **Task 2: Add POST voice-profile/reset endpoint with background re-extraction** - `358b2eb` (feat)

## Files Created/Modified
- `backend/src/flywheel/api/email.py` - Added VoiceProfileResponse, VoiceProfilePatch models; GET, PATCH, POST reset endpoints; imports for EmailVoiceProfile, voice_profile_init, delete, update

## Decisions Made
None - followed plan as specified.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Voice profile API layer complete, ready for Plan 02 (Voice Profile Settings UI)
- All three endpoints follow existing auth patterns (require_tenant, get_tenant_db)
- Background re-extraction uses proven tenant_session pattern from trigger_sync

---
*Phase: 71-voice-settings-ui*
*Completed: 2026-03-30*
