---
phase: 68-email-to-tasks
plan: 03
subsystem: api, ui
tags: [fastapi, html-brief, email-tasks, pydantic]

requires:
  - phase: 68-02
    provides: "channel_task_extractor with tasks_detail list in summary dict"
provides:
  - "Detected Tasks section in daily brief HTML with source badges, priority dots, duplicate labels"
  - "GET /tasks/?source=email filter for email-sourced tasks"
  - "email_id, resolved_by, resolution_source_id, resolution_note fields in TaskResponse and TaskUpdate"
affects: [tasks-ui, email-to-tasks-frontend]

tech-stack:
  added: []
  patterns:
    - "_render_*_section pattern extended for detected tasks"
    - "resolved_by validator pattern (enum constraint via field_validator)"

key-files:
  created: []
  modified:
    - backend/src/flywheel/engines/flywheel_ritual.py
    - backend/src/flywheel/api/tasks.py

key-decisions:
  - "Detected Tasks section placed between Processing and Prep sections (Section 2.5)"
  - "Source badge uses pill-style with color-coded backgrounds (email=blue, slack=green, other=gray)"
  - "resolved_by validates against {user, system} enum set"

patterns-established:
  - "Channel task rendering: consumes tasks_detail from extractor summary directly"
  - "Resolution fields: resolved_by + resolution_source_id + resolution_note triplet for task provenance"

duration: 2min
completed: 2026-03-30
---

# Phase 68 Plan 03: Brief Integration + Task API Summary

**Detected Tasks section in daily brief with color-coded source badges and priority indicators, plus source filter and resolution fields on Task API**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-29T15:58:48Z
- **Completed:** 2026-03-30T00:01:03Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added _render_detected_tasks_section to daily brief with source badges, priority dots, duplicate labels, first-run message, and empty state
- Added source query filter to GET /tasks/ endpoint
- Added email_id, resolved_by, resolution_source_id, resolution_note to TaskResponse and TaskUpdate with validator

## Task Commits

Single plan-level commit (per-plan strategy):

1. **All tasks** - `379d271` (feat)

## Files Created/Modified
- `backend/src/flywheel/engines/flywheel_ritual.py` - Added _render_detected_tasks_section() and inserted call in _compose_daily_brief between Processing and Prep sections
- `backend/src/flywheel/api/tasks.py` - Added source filter to list_tasks, email_id + resolution fields to TaskResponse/TaskUpdate, resolved_by validator, update handler for resolution fields

## Decisions Made
- Detected Tasks section placed as Section 2.5 between Processing Summary and Meeting Prep
- Source badge color scheme: email=#3B82F6 (blue), slack=#22C55E (green), other=#6B7280 (gray)
- Priority indicator: high=red dot (#E94D35), medium=amber dot (#F97316), low=no dot
- resolved_by field validated to only accept "user" or "system"

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Email-to-tasks pipeline complete (phases 68-01 through 68-03)
- Daily brief renders extracted tasks with full visual treatment
- Task API exposes all new fields for frontend consumption
- Ready for frontend integration (tasks-ui can filter by source=email and display resolution metadata)

---
*Phase: 68-email-to-tasks*
*Completed: 2026-03-30*
