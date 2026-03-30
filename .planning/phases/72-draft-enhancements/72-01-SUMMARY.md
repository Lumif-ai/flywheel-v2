---
phase: 72-draft-enhancements
plan: 01
subsystem: api
tags: [email, drafting, voice-profile, regeneration, claude-api]

# Dependency graph
requires:
  - phase: 70-voice-profile-overhaul
    provides: 10-field EmailVoiceProfile with extraction and updating
  - phase: 71-voice-settings-ui
    provides: Voice profile CRUD endpoints in email.py
provides:
  - Voice snapshot persistence in draft context_used JSONB
  - POST /email/drafts/{draft_id}/regenerate endpoint with quick actions and custom instructions
  - Reusable _generate_draft_body helper for draft generation
  - QUICK_ACTION_OVERRIDES constant (shorter, longer, more_casual, more_formal)
affects: [72-02-PLAN, frontend-draft-ui, email-thread-detail]

# Tech tracking
tech-stack:
  added: []
  patterns: [voice-snapshot-in-context-used, one-time-override-without-profile-mutation]

key-files:
  created: []
  modified:
    - backend/src/flywheel/engines/email_drafter.py
    - backend/src/flywheel/api/email.py

key-decisions:
  - "Voice snapshot stored as {type: voice_snapshot, ...fields} entry in context_used JSONB array"
  - "Regeneration merges overrides into a copy of the current voice profile — persistent profile never mutated"
  - "Extracted _generate_draft_body helper to avoid code duplication between draft_email and regenerate_draft_with_overrides"

patterns-established:
  - "Voice snapshot pattern: all 10 voice fields stored alongside context_refs in context_used for audit and display"
  - "One-time override pattern: merge dict overrides into profile copy, generate, discard — no side effects"

# Metrics
duration: 3min
completed: 2026-03-30
---

# Phase 72 Plan 01: Voice Snapshot & Draft Regeneration Summary

**Voice snapshot persistence in draft pipeline + POST /drafts/{draft_id}/regenerate endpoint with 4 quick actions and custom instructions**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T02:29:40Z
- **Completed:** 2026-03-30T02:32:19Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Every new draft now stores a voice_snapshot dict (all 10 voice profile fields) inside context_used JSONB
- POST /email/drafts/{draft_id}/regenerate endpoint accepts quick actions (shorter, longer, more_casual, more_formal) or free-form custom_instructions
- Regeneration re-drafts via Claude with merged voice overrides without touching the persistent EmailVoiceProfile
- Thread detail API response includes voice_snapshot for each draft (None for legacy drafts)
- Extracted core drafting logic into reusable _generate_draft_body helper

## Task Commits

Per-plan commit strategy (single commit for all tasks):

1. **Task 1: Store voice snapshot in context_used during draft creation** - `c44686b` (feat)
2. **Task 2: Add POST /email/drafts/{draft_id}/regenerate endpoint** - `c44686b` (feat)

## Files Created/Modified
- `backend/src/flywheel/engines/email_drafter.py` - Added QUICK_ACTION_OVERRIDES, VOICE_SNAPSHOT_FIELDS, _generate_draft_body helper, _build_voice_snapshot helper, regenerate_draft_with_overrides function; refactored draft_email to use shared helper and store voice snapshot
- `backend/src/flywheel/api/email.py` - Added RegenerateRequest/RegenerateDraftResponse models, regenerate_draft endpoint, voice_snapshot field on DraftDetail, voice_snapshot extraction in thread detail

## Decisions Made
- Voice snapshot stored as `{type: "voice_snapshot", ...fields}` entry in context_used JSONB array -- consistent with existing context_ref pattern and easily filterable
- Regeneration merges overrides into a copy of the current voice profile -- persistent profile never mutated
- Extracted _generate_draft_body helper to share drafting logic between draft_email and regenerate_draft_with_overrides

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Regeneration endpoint ready for frontend integration
- Voice snapshot available in thread detail for UI display
- 72-02 can build on this foundation for frontend draft enhancement UI

---
*Phase: 72-draft-enhancements*
*Completed: 2026-03-30*
