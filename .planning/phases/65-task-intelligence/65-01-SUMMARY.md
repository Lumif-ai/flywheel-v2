---
phase: 65-task-intelligence
plan: 01
subsystem: database, api
tags: [alembic, sqlalchemy, rls, tasks, signals, postgresql]

requires:
  - phase: 64-unified-meetings
    provides: meetings table (FK target for tasks.meeting_id)
  - phase: 55-relationships-and-signals-apis
    provides: signals endpoint pattern with FILTER clauses and TTL cache
provides:
  - tasks table (migration 034) with 20 columns, 3 indexes, user-level RLS
  - Task ORM model importable from flywheel.db.models
  - task signal counts (tasks_detected, tasks_in_review, tasks_overdue) in GET /signals/
  - user-scoped _task_signals_cache separate from tenant-scoped _signals_cache
affects: [65-02-PLAN, 65-03-PLAN, frontend task surfaces]

tech-stack:
  added: []
  patterns:
    - "User-scoped task signals cache separate from tenant-scoped relationship cache"
    - "Two-layer cache merge in get_signals() — relationship (tenant) + tasks (user)"

key-files:
  created:
    - backend/alembic/versions/034_create_tasks_table.py
  modified:
    - backend/src/flywheel/db/models.py
    - backend/src/flywheel/api/signals.py

key-decisions:
  - "User-level RLS (not split-visibility) for tasks — tasks are personal per research anti-pattern"
  - "Separate _task_signals_cache keyed by tenant_id:user_id — avoids cold cache on every user request if shared with tenant-scoped _signals_cache"
  - "Removed early return in get_signals() — restructured into Step A (relationship)/Step B (task)/Step C (merge) so task counts always run"

patterns-established:
  - "Task table user-level isolation: single policy tasks_user_isolation covers all operations"

duration: 2min
completed: 2026-03-28
---

# Phase 65 Plan 01: Tasks Data Model and Signal Counts Summary

**Tasks table with 20-column migration, user-level RLS, Task ORM model, and 3 task signal counts merged into GET /signals/ via separate user-scoped cache**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-28T12:29:58Z
- **Completed:** 2026-03-28T12:32:24Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Alembic migration 034 creates tasks table with 20 columns, 3 indexes (user_status, due, meeting), and user-level RLS policy
- Task ORM model appended to models.py with all columns, indexes, and relationships matching migration exactly
- Signals endpoint extended with tasks_detected, tasks_in_review, tasks_overdue counts using separate user-scoped cache
- Restructured get_signals() to eliminate early return bypass — task signals always computed regardless of relationship cache state

## Task Commits

Plan committed as single batch (per-plan strategy):

1. **Task 1: Create tasks Alembic migration with user-level RLS** - `751d26f` (feat)
2. **Task 2: Add Task ORM model and extend signals with task counts** - `751d26f` (feat)

## Files Created/Modified
- `backend/alembic/versions/034_create_tasks_table.py` - Tasks table migration with 20 columns, 3 indexes, user-level RLS
- `backend/src/flywheel/db/models.py` - Task ORM model appended after Meeting class
- `backend/src/flywheel/api/signals.py` - Task signal counts, _task_signals_cache, _compute_task_signals, restructured get_signals()

## Decisions Made
- User-level RLS (tasks_user_isolation) not split-visibility — tasks are personal, not team-visible
- Separate _task_signals_cache keyed by tenant_id:user_id to avoid cold cache per-user on the tenant-scoped relationship cache
- Removed early return pattern in get_signals() — restructured into three steps (A: relationship cache, B: task cache, C: merge) so task counts are never skipped

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Task table and ORM model ready for Plan 02 (meeting processor Stage 7 task extraction)
- Task signal counts ready for Plan 03 (Tasks CRUD API) — new tasks will immediately appear in sidebar badge counts
- No blockers

---
*Phase: 65-task-intelligence*
*Completed: 2026-03-28*
