---
phase: 60-meeting-data-model-and-granola-adapter
plan: 02
subsystem: api
tags: [granola, integration, httpx, encryption, aes-256-gcm, api-adapter]

# Dependency graph
requires:
  - phase: 59-team-privacy-foundation
    provides: user.sub pattern for user_id, encrypt_api_key from flywheel.auth.encryption

provides:
  - GranolaAdapter service with test_connection, list_meetings, get_meeting_content
  - POST /integrations/granola/connect endpoint with API key validation and encrypted storage
  - Upsert Integration row on reconnect (no duplicate rows)

affects:
  - 60-03 (meetings sync endpoint uses GranolaAdapter.list_meetings and decrypt_api_key)
  - Phase 61+ (processing pipeline uses get_meeting_content for full transcript ingestion)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Non-OAuth API-key integration pattern (simpler than OAuth — no state/CSRF, direct key validation)
    - Adapter reconciliation against real API shape vs spec assumptions

key-files:
  created:
    - backend/src/flywheel/services/granola_adapter.py
  modified:
    - backend/src/flywheel/api/integrations.py

key-decisions:
  - "GRANOLA_API_BASE = https://public-api.granola.ai/v1 — real URL, NOT https://api.granola.ai/v1 as spec assumed"
  - "test_connection validates key via GET /v1/notes?page_size=1 — no /v1/me endpoint exists"
  - "list_meetings reads 'notes' key from response, not 'meetings'"
  - "duration_mins computed from calendar_event.start_time/end_time (not a direct API field)"
  - "Upsert pattern on reconnect: clear last_synced_at to force full re-sync from scratch"
  - "connect endpoint does NOT store last_sync_cursor in settings — Integration.last_synced_at column serves as cursor"
  - "user.sub (not user.id) for user_id per Phase 59 decision"

patterns-established:
  - "Non-OAuth integration pattern: validate key -> encrypt -> upsert Integration row; no pending state needed"
  - "Adapter reconciliation: spec API shape vs real API documented in RESEARCH.md and comments"

# Metrics
duration: 2min
completed: 2026-03-28
---

# Phase 60 Plan 02: Granola Adapter and Connect Endpoint Summary

**httpx async adapter for real Granola API (/v1/notes) with AES-256-GCM API key storage via POST /integrations/granola/connect upsert endpoint**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-28T00:45:03Z
- **Completed:** 2026-03-28T00:47:21Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `granola_adapter.py` with three async functions matching the real Granola API shape (verified against docs.granola.ai OpenAPI spec): `test_connection` (validates key via `/v1/notes?page_size=1`), `list_meetings` (paginates `/v1/notes` with `created_after` cursor), `get_meeting_content` (single call to `/v1/notes/{id}?include=transcript`)
- Added `POST /integrations/granola/connect` endpoint to `integrations.py` — validates API key, encrypts with AES-256-GCM (`encrypt_api_key`), upserts Integration row (updates on reconnect, creates on first connect)
- Added "granola" to `_PROVIDER_DISPLAY` map for UI display

## Task Commits

1. **Task 1: Granola adapter service + Task 2: Connect endpoint** — `e0fe408` (feat: per-plan batch commit)

## Files Created/Modified
- `backend/src/flywheel/services/granola_adapter.py` — Granola async adapter: GRANOLA_API_BASE, RawMeeting/MeetingContent dataclasses, test_connection/list_meetings/get_meeting_content async functions
- `backend/src/flywheel/api/integrations.py` — Added POST /integrations/granola/connect, imported encrypt_api_key, added "granola" to _PROVIDER_DISPLAY

## Decisions Made
- Used real Granola API base URL `https://public-api.granola.ai/v1` (spec assumed `api.granola.ai`)
- `test_connection` calls `GET /v1/notes?page_size=1` since `/v1/me` does not exist
- `list_meetings` reads `notes` key (not `meetings`) and maps `item["created_at"]` to `meeting_date`
- `item.get("summary_text")` maps to `ai_summary` (spec assumed field name was wrong)
- Upsert on reconnect clears `last_synced_at = None` to force full re-sync from scratch
- `settings={"processing_rules": {}}` only — no `last_sync_cursor` in settings, Integration.last_synced_at column serves as cursor

## Deviations from Plan

None - plan executed exactly as written. The adapter was built using the correct real API shape from 60-RESEARCH.md as specified.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 03 (meetings sync endpoint) can now import `list_meetings` from `granola_adapter.py` and `decrypt_api_key` from `flywheel.auth.encryption`
- Connect endpoint is fully functional for API key ingestion; users can link their Granola account
- All three adapter functions are ready for Phase 61+ processing pipeline (`get_meeting_content` for transcript ingestion)

## Self-Check: PASSED
- granola_adapter.py: FOUND
- 60-02-SUMMARY.md: FOUND
- Commit e0fe408: FOUND

---
*Phase: 60-meeting-data-model-and-granola-adapter*
*Completed: 2026-03-28*
