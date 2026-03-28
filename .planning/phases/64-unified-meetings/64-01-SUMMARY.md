---
phase: 64-unified-meetings
plan: 01
subsystem: database, api
tags: [alembic, sqlalchemy, meetings, dedup, calendar-sync, granola, rls, lifecycle]

requires:
  - phase: 60-meeting-data-model-and-granola-adapter
    provides: Meeting table (032), Granola adapter, split-visibility RLS
  - phase: 61-meeting-intelligence-pipeline
    provides: Meeting processing pipeline, classify_meeting, auto_link
provides:
  - Migration 033 adding calendar_event_id, granola_note_id, location, description columns
  - Dual-source dedup indexes (calendar + granola)
  - Calendar sync writing Meeting rows with status=scheduled
  - Granola fuzzy dedup matching scheduled calendar events
  - Lifecycle state machine (scheduled -> recorded -> processing -> complete)
  - RLS context setting in calendar sync loop
affects: [64-02-PLAN, 64-03-PLAN, meetings-api, meeting-prep]

tech-stack:
  added: []
  patterns: [dual-source-dedup, fuzzy-time-match, lifecycle-state-machine, rls-context-in-background-loop]

key-files:
  created:
    - backend/alembic/versions/033_unify_meetings_table.py
  modified:
    - backend/src/flywheel/db/models.py
    - backend/src/flywheel/services/calendar_sync.py
    - backend/src/flywheel/api/meetings.py

key-decisions:
  - "calendar_event_id used for dedup (not external_id prefix pattern) -- cleaner partial unique index"
  - "Granola data wins over calendar data -- skip update if existing row has granola_note_id"
  - "Fuzzy dedup uses OR of title-contains and attendee-overlap (not AND) -- maximizes match rate"
  - "get_meeting_prep_suggestions kept on WorkItem for now -- Plan 02 migrates it"

patterns-established:
  - "Dual-source dedup: partial unique indexes on source-specific ID columns (calendar_event_id, granola_note_id)"
  - "Fuzzy time match: +/-30 min window with title contains OR attendee email overlap"
  - "RLS context in background loops: SET LOCAL app.tenant_id/user_id before writing to RLS-protected tables"
  - "Lifecycle state machine: scheduled (calendar) -> recorded (granola match) -> processing -> complete"

duration: 3min
completed: 2026-03-28
---

# Phase 64 Plan 01: Unified Meetings Data Layer Summary

**Migration 033 with dual-source dedup columns, calendar sync rewriting to Meeting table with scheduled status, Granola fuzzy dedup matching against calendar events, and lifecycle state machine**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-28T12:25:47Z
- **Completed:** 2026-03-28T12:29:12Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Migration 033 adds calendar_event_id, granola_note_id, location, description columns with dual-source dedup indexes
- Calendar sync now writes Meeting rows (not WorkItems) with processing_status='scheduled' and sets RLS context in sync loop
- Granola sync fuzzy-matches incoming meetings against scheduled calendar events (+/-30 min window, title/attendee overlap) and enriches to 'recorded' status
- process-pending queries both 'pending' and 'recorded' statuses for the lifecycle state machine

## Task Commits

Single plan-level commit (per-plan strategy):

1. **All tasks** - `6d1cab2` (feat: migration 033 + calendar sync rewrite + Granola fuzzy dedup)

## Files Created/Modified
- `backend/alembic/versions/033_unify_meetings_table.py` - Migration adding 4 columns, 2 dedup indexes, replacing pending index with processable
- `backend/src/flywheel/db/models.py` - Meeting model with calendar_event_id, granola_note_id, location, description + updated __table_args__
- `backend/src/flywheel/services/calendar_sync.py` - upsert_meeting_row replacing upsert_meeting_work_item, RLS context in sync loop
- `backend/src/flywheel/api/meetings.py` - _find_matching_scheduled fuzzy dedup, process-pending querying pending+recorded

## Decisions Made
- calendar_event_id used for dedup (not external_id prefix pattern) -- cleaner partial unique index, avoids string prefix matching
- Granola data wins over calendar data -- if existing Meeting row has granola_note_id set, calendar sync skips update (richer source preserved)
- Fuzzy dedup uses OR of title-contains and attendee-overlap (not AND) -- maximizes match rate between calendar and Granola sources
- get_meeting_prep_suggestions kept on WorkItem for now -- Plan 02 migrates it to query Meeting table

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Migration 033 ready to apply (alembic head is 033_unify_meetings)
- Plan 02 can now add time param to list endpoint, prep endpoint, and migrate suggestions
- Plan 03 can build frontend Upcoming/Past tabs against the updated Meeting model
- get_meeting_prep_suggestions still uses WorkItem -- Plan 02 will migrate

---
*Phase: 64-unified-meetings*
*Completed: 2026-03-28*
