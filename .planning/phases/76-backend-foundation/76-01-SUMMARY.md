---
phase: 76-backend-foundation
plan: 01
subsystem: api
tags: [fastapi, mcp, skills, meetings, tenant-scoping]

# Dependency graph
requires: []
provides:
  - "GET /skills/{name}/prompt endpoint for MCP tool skill prompt retrieval"
  - "PATCH /meetings/{id} endpoint for MCP tool meeting summary writeback"
affects: [77-mcp-tools, 78-mcp-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tenant-scoped skill lookup reused from _get_available_skills_db pattern"
    - "PATCH with explicit-field-only update pattern (None = skip)"

key-files:
  created: []
  modified:
    - "backend/src/flywheel/api/skills.py"
    - "backend/src/flywheel/api/meetings.py"

key-decisions:
  - "Reused _get_available_skills_db tenant-scoping logic inline rather than refactoring to shared helper"
  - "VALID_PROCESSING_STATUSES as module-level set for validation consistency"

patterns-established:
  - "MCP-facing endpoints follow same require_tenant + get_tenant_db pattern as UI endpoints"
  - "PATCH endpoints only update explicitly provided fields (not None)"

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 76 Plan 01: Skill Prompt & Meeting PATCH Endpoints Summary

**GET /skills/{name}/prompt and PATCH /meetings/{id} endpoints for MCP tool integration -- tenant-scoped skill prompt retrieval and meeting summary writeback**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T16:59:57Z
- **Completed:** 2026-03-30T17:01:34Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- GET /skills/{name}/prompt returns system_prompt for enabled skills with full tenant-scoping (TenantSkill overrides respected)
- PATCH /meetings/{id} accepts ai_summary and processing_status, validates status against known set, persists to meeting record
- Both endpoints use existing require_tenant + get_tenant_db dependency injection -- no new auth patterns

## Task Commits

Per-plan commit (all tasks in one):

1. **Task 1: GET /skills/{name}/prompt** + **Task 2: PATCH /meetings/{id}** - `6ba0da8` (feat)

## Files Created/Modified
- `backend/src/flywheel/api/skills.py` - Added GET /{skill_name}/prompt endpoint with tenant-scoped skill lookup
- `backend/src/flywheel/api/meetings.py` - Added MeetingPatchRequest model, VALID_PROCESSING_STATUSES set, PATCH /{meeting_id} endpoint

## Decisions Made
- Reused the _get_available_skills_db tenant-scoping logic inline in the new prompt endpoint rather than extracting a shared helper -- keeps the pattern explicit and avoids refactoring existing code
- Used a module-level VALID_PROCESSING_STATUSES set rather than an Enum to stay consistent with the string-based processing_status field in the Meeting model

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both endpoints ready for MCP tool consumption in Phase 77
- No new router registration needed -- endpoints added to existing routers
- No new dependencies added

---
*Phase: 76-backend-foundation*
*Completed: 2026-03-30*
