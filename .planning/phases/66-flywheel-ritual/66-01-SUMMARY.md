---
phase: 66-flywheel-ritual
plan: 01
subsystem: api, engine
tags: [meeting-sync, skill-executor, engine-dispatch, flywheel-ritual]

# Dependency graph
requires:
  - phase: 60-meeting-data-model-and-granola-adapter
    provides: Granola adapter, Meeting model, Integration model
  - phase: 61-meeting-intelligence-pipeline
    provides: meeting_processor_web, post-classification rules
provides:
  - Shared sync_granola_meetings() function callable by both API and engine
  - Flywheel engine dispatch wiring in skill_executor.py
  - Clean backend-engine SKILL.md (engine: flywheel_ritual)
  - Updated REQUIREMENTS.md traceability for FLY-01 through FLY-06
affects: [66-02, 66-03, 66-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [shared-function-extraction, engine-dispatch-wiring]

key-files:
  created:
    - backend/src/flywheel/services/meeting_sync.py
  modified:
    - backend/src/flywheel/api/meetings.py
    - backend/src/flywheel/services/skill_executor.py
    - skills/flywheel/SKILL.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "sync_granola_meetings opens its own session via factory() with RLS context — fully self-contained"
  - "_find_matching_scheduled kept as module-level function taking explicit session param (not nested)"
  - "HTTPException raised from inside sync function for API compatibility (caller is always an endpoint or engine)"

patterns-established:
  - "Shared sync function pattern: extract from endpoint, accept async_sessionmaker, set RLS internally"

# Metrics
duration: 4min
completed: 2026-03-29
---

# Phase 66 Plan 01: Foundation Wiring Summary

**Shared sync_granola_meetings() extracted to meeting_sync.py, flywheel engine dispatch wired in skill_executor.py, SKILL.md replaced with backend-engine definition**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-29T00:20:05Z
- **Completed:** 2026-03-29T00:24:30Z
- **Tasks:** 3
- **Files modified:** 5 (+ 1 created, 1 deleted)

## Accomplishments
- Extracted sync logic from meetings.py into reusable meeting_sync.py with async_sessionmaker pattern
- Replaced curl-based SKILL.md with clean engine: flywheel_ritual definition, deleted api-reference.md
- Wired flywheel dispatch in skill_executor.py (dispatch, subsidy allowlist, HTML rendering path)
- Updated REQUIREMENTS.md FLY-01 through FLY-06 as superseded with ORCH cross-references

## Task Commits

Per-plan commit strategy (single commit for all tasks):

1. **Task 1: Extract sync logic into shared meeting_sync.py** - `6a0c9bd`
2. **Task 2: Replace SKILL.md, delete api-reference.md, wire dispatch** - `6a0c9bd`
3. **Task 3: Update REQUIREMENTS.md** - `6a0c9bd`

## Files Created/Modified
- `backend/src/flywheel/services/meeting_sync.py` - Shared sync_granola_meetings() with RLS-aware session management
- `backend/src/flywheel/api/meetings.py` - Refactored POST /sync to delegate to shared function
- `backend/src/flywheel/services/skill_executor.py` - Flywheel dispatch, subsidy allowlist, HTML rendering
- `skills/flywheel/SKILL.md` - Backend-engine skill definition (engine: flywheel_ritual, web_tier: 1)
- `skills/flywheel/references/api-reference.md` - Deleted (no longer needed)
- `.planning/REQUIREMENTS.md` - FLY-01 through FLY-06 marked superseded

## Decisions Made
- sync_granola_meetings opens its own session via factory() with RLS context — fully self-contained for both API and engine use
- _find_matching_scheduled kept as module-level function taking explicit session param (not nested inside sync function)
- HTTPException raised from inside sync function for API compatibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- sync_granola_meetings() ready for flywheel engine Stage 1 (Plan 02/03)
- skill_executor.py dispatch ready — expects flywheel.engines.flywheel_ritual.execute_flywheel_ritual (Plan 02 creates this)
- SKILL.md ready for seed.py to read engine: flywheel_ritual frontmatter

## Self-Check: PASSED

- meeting_sync.py: FOUND
- SKILL.md: FOUND
- api-reference.md: CONFIRMED DELETED
- Commit 6a0c9bd: FOUND

---
*Phase: 66-flywheel-ritual*
*Completed: 2026-03-29*
