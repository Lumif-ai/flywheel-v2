---
phase: 67-tasks-ui
plan: 01
subsystem: api, ui
tags: [react-query, typescript, state-machine, optimistic-updates, date-fns]

requires:
  - phase: none
    provides: existing backend /tasks/ API with 7 endpoints
provides:
  - Backend deferred status and confirmed->done shortcut in task state machine
  - TypeScript type definitions matching backend Pydantic schemas
  - Query key factory and API functions for all task endpoints
  - 6 React Query hooks (useTasks, useTaskSummary, useTask, useCreateTask, useUpdateTask, useUpdateTaskStatus)
  - Optimistic updates with rollback on status transitions
  - Date grouping utility (overdue, today, thisWeek, nextWeek, later)
affects: [67-02, 67-03, 67-04, 67-05, 67-06, 67-07]

tech-stack:
  added: []
  patterns: [query-key-factory, optimistic-cache-update, date-grouping-utility]

key-files:
  created:
    - frontend/src/features/tasks/types/tasks.ts
    - frontend/src/features/tasks/api.ts
    - frontend/src/features/tasks/hooks/useTasks.ts
    - frontend/src/features/tasks/hooks/useTaskSummary.ts
    - frontend/src/features/tasks/hooks/useTask.ts
    - frontend/src/features/tasks/hooks/useCreateTask.ts
    - frontend/src/features/tasks/hooks/useUpdateTask.ts
    - frontend/src/features/tasks/hooks/useUpdateTaskStatus.ts
  modified:
    - backend/src/flywheel/api/tasks.py

key-decisions:
  - "UUIDs typed as string in TypeScript (backend returns JSON-serialized UUIDs)"
  - "30s stale time for task queries (tasks change frequently during triage sessions)"
  - "Optimistic removal from filtered list on status change (task leaves current view)"

patterns-established:
  - "Query key factory: queryKeys.tasks.{all,list,summary,detail} hierarchy"
  - "Optimistic update pattern: cancel -> snapshot -> mutate cache -> rollback on error"

duration: 2min
completed: 2026-03-29
---

# Phase 67 Plan 01: Tasks Data Layer Summary

**Extended backend state machine with deferred status + confirmed->done shortcut, built complete TypeScript types with date grouping, and 6 React Query hooks with optimistic updates**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-29T07:14:56Z
- **Completed:** 2026-03-29T07:17:20Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- Backend state machine extended: deferred status with transitions from detected/in_review, and confirmed->done shortcut for quick completions
- Complete TypeScript type system mirroring all backend Pydantic schemas with enum-like constants
- Date grouping utility classifying tasks into overdue/today/thisWeek/nextWeek/later buckets
- 6 React Query hooks ready for UI consumption, with optimistic updates on status transitions

## Task Commits

Single commit (per-plan strategy):

1. **All tasks** - `363eed8` (feat)

## Files Created/Modified
- `backend/src/flywheel/api/tasks.py` - Added deferred status, transitions, and summary count
- `frontend/src/features/tasks/types/tasks.ts` - All TypeScript interfaces, type aliases, constants, VALID_TRANSITIONS, groupTasksByDueDate utility
- `frontend/src/features/tasks/api.ts` - Query key factory and 6 API functions
- `frontend/src/features/tasks/hooks/useTasks.ts` - Paginated task list query with 30s stale time
- `frontend/src/features/tasks/hooks/useTaskSummary.ts` - Summary counts query
- `frontend/src/features/tasks/hooks/useTask.ts` - Single task detail query (enabled when taskId truthy)
- `frontend/src/features/tasks/hooks/useCreateTask.ts` - Create mutation with success/error toasts
- `frontend/src/features/tasks/hooks/useUpdateTask.ts` - Update mutation with error toast (no success toast for inline edits)
- `frontend/src/features/tasks/hooks/useUpdateTaskStatus.ts` - Status transition mutation with optimistic cache removal and rollback

## Decisions Made
- UUIDs typed as `string` in TypeScript (backend returns JSON-serialized UUIDs)
- 30-second stale time for task queries (tasks change frequently during triage)
- Optimistic update removes task from current filtered list view on status change
- No success toast on useUpdateTask (inline edits are frequent, toast would be noisy)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All types, API functions, and hooks ready for UI components in plans 02-07
- Backend state machine supports full triage workflow including defer/resume cycle
- Feature directory structure established at frontend/src/features/tasks/

## Self-Check: PASSED

All 9 files verified present. Commit 363eed8 verified in git log.

---
*Phase: 67-tasks-ui*
*Completed: 2026-03-29*
