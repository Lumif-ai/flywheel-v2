---
phase: 68-email-to-tasks
plan: 01
subsystem: database
tags: [alembic, postgres, sqlalchemy, migration, tasks, email]

requires:
  - phase: 67-tasks-ui
    provides: Tasks table (034 migration) and Task ORM model
provides:
  - email_id FK on tasks table for idempotent email-to-task extraction
  - Resolution metadata columns (resolved_by, resolution_source_id, resolution_note)
  - idx_tasks_email and idx_tasks_source composite indexes
affects: [68-02, 68-03, email-to-tasks pipeline, commitment ledger]

tech-stack:
  added: []
  patterns: [add_column migration pattern for extending existing tables]

key-files:
  created:
    - backend/alembic/versions/035_add_email_task_fields.py
  modified:
    - backend/src/flywheel/db/models.py

key-decisions:
  - "resolution_source_id has no FK (polymorphic reference to email or meeting)"
  - "All new columns nullable for backwards-compatibility with existing tasks"

patterns-established:
  - "Incremental migration pattern: add_column + create_index for extending tables"

duration: 3min
completed: 2026-03-29
---

# Phase 68 Plan 01: Email Task Schema Foundation Summary

**Alembic migration 035 adding email_id FK and resolution columns to tasks table, with ORM model update and two new indexes**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-29T15:50:27Z
- **Completed:** 2026-03-29T15:53:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Alembic migration 035 adds 4 nullable columns (email_id, resolved_by, resolution_source_id, resolution_note) to tasks table
- Two new indexes: idx_tasks_email for idempotency lookups, idx_tasks_source for source-filtered queries
- Task ORM model updated with new columns, indexes in __table_args__, and email relationship

## Task Commits

All tasks committed in single plan-level commit:

1. **Task 1: Create Alembic migration** - `d3363bc` (feat)
2. **Task 2: Update Task ORM model** - `d3363bc` (feat)

## Files Created/Modified
- `backend/alembic/versions/035_add_email_task_fields.py` - Migration adding email_id FK, resolution columns, and 2 indexes
- `backend/src/flywheel/db/models.py` - Task class updated with 4 new columns, 2 indexes, email relationship

## Decisions Made
- resolution_source_id intentionally has no FK constraint (polymorphic reference to email or meeting)
- All 4 new columns are nullable for full backwards-compatibility with existing task rows

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. Migration must be run against the database (`alembic upgrade head`) before email-to-task extraction can begin.

## Next Phase Readiness
- Schema foundation complete for email-to-task extraction pipeline
- email_id FK enables NOT EXISTS idempotency checks in 68-02
- Resolution columns ready for Layer B commitment ledger
- No blockers for 68-02 (extraction ritual)

---
*Phase: 68-email-to-tasks*
*Completed: 2026-03-29*
