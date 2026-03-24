---
phase: 02-sync-worker-and-voice-profile
plan: 01
subsystem: api
tags: [gmail, sync, asyncio, postgresql, background-worker, historyId, upsert]

# Dependency graph
requires:
  - phase: 01-data-layer-and-gmail-foundation
    provides: Email ORM model, gmail-read Integration row with history_id slot, gmail_read.py functions (get_history, list_message_headers, get_message_headers, get_profile, get_valid_credentials, TokenRevokedException)

provides:
  - email_sync_loop() background worker in gmail_sync.py
  - sync_gmail() incremental historyId sync with 404 fallback
  - _full_sync() profile-first historyId capture before pagination
  - upsert_email() with pg_insert ON CONFLICT DO UPDATE
  - email_sync_loop registered in main.py lifespan alongside calendar_sync_task

affects:
  - 02-02 (voice profile builder — shares gmail-read credentials and gmail_read.py)
  - 03-email-scoring (reads Email rows created by this sync worker)
  - 04-draft-generation (reads Email rows + integration credentials)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "historyId sync with 404 fallback: check history_id is None → full sync; 404 error → clear history_id, recurse once with _retry_count=1"
    - "get_profile() before pagination: capture historyId checkpoint before list_message_headers loop to prevent missed messages during pagination"
    - "Concurrent per-integration sync: asyncio.wait_for per integration + asyncio.gather(return_exceptions=True) for multi-user safety"
    - "Tenant session reload: re-query Integration inside tenant_session to avoid detached-instance errors from outer superuser session"
    - "Caller-commits pattern: upsert_email does not commit — caller commits once after batch"

key-files:
  created:
    - backend/src/flywheel/services/gmail_sync.py
  modified:
    - backend/src/flywheel/main.py

key-decisions:
  - "historyId captured from get_profile() BEFORE pagination in _full_sync to prevent missing messages that arrive mid-sync"
  - "email_sync_loop uses asyncio.wait_for(60s) per integration + gather(return_exceptions=True) matching GMAIL-08 concurrent polling requirement"
  - "Integration row re-loaded inside tenant_session to avoid SQLAlchemy DetachedInstanceError from crossing session boundaries"
  - "Zero PII in log output — only integration.id, message_id, thread_id, counts logged"

patterns-established:
  - "Background sync loop pattern: outer try/except swallows iteration errors, inner per-integration exceptions logged but loop never crashes"
  - "Upsert pattern: pg_insert(Model).on_conflict_do_update(constraint=...) for idempotent sync"

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 2 Plan 01: Gmail Sync Worker Summary

**Gmail inbox sync background worker using historyId incremental sync, 404 full-sync fallback, and concurrent per-integration polling via asyncio.gather**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-24T10:51:01Z
- **Completed:** 2026-03-24T10:53:19Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `gmail_sync.py` with the full email sync pipeline: `email_sync_loop`, `sync_gmail`, `_full_sync`, `upsert_email`, and `_parse_email_date`
- Incremental historyId sync detects new INBOX messages via Gmail history.list, falls back to full re-sync on HTTP 404 (stale historyId) with a recursion guard
- Full sync captures historyId from `get_profile()` BEFORE the pagination loop, preventing messages from being missed if they arrive mid-sync
- Concurrent multi-user polling: each integration wrapped in `asyncio.wait_for(60s)` and gathered with `return_exceptions=True`, satisfying the GMAIL-08 concurrent polling requirement
- Registered `email_sync_loop` in `main.py` lifespan with declaration, `asyncio.create_task`, and cancellation — exactly matching the `calendar_sync_task` pattern

## Task Commits

Both tasks committed atomically in a single plan commit:

1. **Task 1: Create gmail_sync.py** - `6e57ab9` (feat)
2. **Task 2: Register email_sync_loop in main.py** - `6e57ab9` (feat)

## Files Created/Modified

- `backend/src/flywheel/services/gmail_sync.py` — Full email sync pipeline: sync loop, incremental sync, full sync, upsert
- `backend/src/flywheel/main.py` — Added `gmail_sync_task` declaration, import, create_task, and cancellation

## Decisions Made

- Integration row is re-loaded inside `tenant_session` (not passed across session boundary) — avoids SQLAlchemy `DetachedInstanceError` since the outer superuser session and inner tenant session are different transactions
- `get_profile()` called before pagination in `_full_sync` — if messages arrive during the pagination loop, the pre-captured historyId ensures they appear in the next incremental sync rather than being silently skipped
- PII compliance enforced by convention: zero references to subject, snippet, sender_email, or msg dict in any logger call

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — venv was at `backend/.venv/` (not root `.venv/`), discovered during verification, adjusted path immediately.

## User Setup Required

None — no external service configuration required. The worker auto-starts on app boot and connects to whatever `gmail-read` integrations exist in the database.

## Next Phase Readiness

- Email rows will populate within 5 minutes of a user completing the Gmail OAuth grant (Phase 1, Plan 02)
- `gmail_sync.py` exports `email_sync_loop` for main.py and `sync_gmail`/`upsert_email` for any future direct-call use
- Phase 2 Plan 02 (voice profile builder) can now use the same `gmail_read.py` credentials infrastructure and `gmail-read` Integration rows

---
*Phase: 02-sync-worker-and-voice-profile*
*Completed: 2026-03-24*

## Self-Check: PASSED

- `backend/src/flywheel/services/gmail_sync.py` — FOUND
- `backend/src/flywheel/main.py` — FOUND
- `.planning/phases/02-sync-worker-and-voice-profile/02-01-SUMMARY.md` — FOUND
- Commit `6e57ab9` — FOUND
