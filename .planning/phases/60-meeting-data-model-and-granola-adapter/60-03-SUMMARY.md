---
phase: 60-meeting-data-model-and-granola-adapter
plan: 03
subsystem: api
tags: [fastapi, granola, meetings, sync, dedup, aes-gcm]

requires:
  - phase: 60-01
    provides: Meeting ORM model with idx_meetings_dedup partial unique index
  - phase: 60-02
    provides: granola_adapter.list_meetings(), granola_adapter.RawMeeting, POST /integrations/granola/connect

provides:
  - POST /api/v1/meetings/sync endpoint with full Granola dedup pipeline
  - _apply_processing_rules() helper for skip_internal / min_duration_mins / skip_domains rules
  - meetings_router registered in main.py

affects: [phase-61-meeting-processing, phase-62-meeting-crm-link]

tech-stack:
  added: []
  patterns:
    - "Incremental sync cursor: Integration.last_synced_at used as created_after param"
    - "Dedup via SELECT external_id IN (fetched_ids) before insert — avoids unique index conflict"
    - "Processing rules from Integration.settings['processing_rules'] dict — tenant-configurable"

key-files:
  created:
    - backend/src/flywheel/api/meetings.py
  modified:
    - backend/src/flywheel/main.py

key-decisions:
  - "Processing rules read from integration.settings['processing_rules'] (not a separate config model) — keeps it tenant-scoped without new table"
  - "already_seen count uses len(existing_ids) not a separate query — set built during dedup step"
  - "synced/skipped counts tracked during insert loop — no extra DB query needed post-insert"
  - "user.sub (not user.id) used for user_id — consistent with Phase 59 decision"

patterns-established:
  - "Sync endpoints: fetch -> dedup -> insert -> update cursor -> return stats"
  - "_apply_processing_rules() returns 'pending' or 'skipped' only (exhaustive)"

duration: 1min
completed: 2026-03-28
---

# Phase 60 Plan 03: Meetings Sync Endpoint Summary

**POST /api/v1/meetings/sync endpoint pulling from Granola with external_id dedup, processing rules (skip_internal/min_duration/skip_domains), and last_synced_at cursor update**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-28T00:49:54Z
- **Completed:** 2026-03-28T00:51:23Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `meetings.py` API router with `POST /sync` endpoint implementing full Granola sync pipeline
- Dedup logic queries existing external_ids before insert — avoids unique index violations, counts already_seen correctly
- `_apply_processing_rules()` helper supports three configurable rule types: skip_internal, min_duration_mins, skip_domains
- Registered `meetings_router` in `main.py` at `/api/v1` prefix — route accessible at `POST /api/v1/meetings/sync`

## Task Commits

1. **Task 1: Meetings sync endpoint** + **Task 2: Register meetings router** - `86c0d9f` (feat — per-plan batch commit)

## Files Created/Modified

- `backend/src/flywheel/api/meetings.py` - POST /meetings/sync endpoint with dedup pipeline and processing rules helper
- `backend/src/flywheel/main.py` - Added meetings_router import and include_router call

## Decisions Made

- Processing rules sourced from `integration.settings["processing_rules"]` dict — avoids a separate config table; tenant can configure via settings JSONB column already on Integration model
- `already_seen` count computed as `len(existing_ids)` — the set is already built during the dedup step, no extra DB query needed
- Sync stats returned immediately after commit — no async background processing at this stage (Phase 61 handles that)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `POST /api/v1/meetings/sync` is live and complete — Granola data flows into the meetings table
- Phase 61 can now read meetings WHERE processing_status='pending' via idx_meetings_pending partial index
- `get_meeting_content()` in granola_adapter.py ready for transcript fetch in Phase 61
- CRM linking (account_id population) is the Phase 62 concern — meeting rows are inserted with account_id=NULL for now

---
*Phase: 60-meeting-data-model-and-granola-adapter*
*Completed: 2026-03-28*
