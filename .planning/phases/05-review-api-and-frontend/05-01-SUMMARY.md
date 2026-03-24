---
phase: 05-review-api-and-frontend
plan: 01
subsystem: backend-api, frontend-client
tags: [email-api, read-endpoints, gmail-sync, digest, api-client]
dependency_graph:
  requires:
    - backend/src/flywheel/db/models.py (Email, EmailScore, EmailDraft ORM models)
    - backend/src/flywheel/services/gmail_sync.py (sync_gmail function)
    - backend/src/flywheel/db/session.py (get_session_factory, tenant_session)
  provides:
    - GET /api/v1/email/threads (paginated priority-sorted thread summaries)
    - GET /api/v1/email/threads/{thread_id} (full thread detail)
    - POST /api/v1/email/sync (background sync trigger)
    - GET /api/v1/email/digest (today's low-priority summary)
    - frontend api.ts put() method
  affects:
    - frontend/src/features/briefing (Plan 02 inbox UI will consume these endpoints)
tech_stack:
  added: []
  patterns:
    - Single LEFT JOIN query + Python-side grouping (no N+1 per thread)
    - BackgroundTasks inner async function with fresh tenant_session
    - priority_to_tier() helper mapping int|None to tier string
key_files:
  created: []
  modified:
    - backend/src/flywheel/api/email.py
    - frontend/src/lib/api.ts
decisions:
  - Single JOIN with Python grouping avoids N+1: one DB round-trip for thread list
  - BackgroundTasks inner _run_sync() re-loads Integration inside tenant_session to avoid detached instance
  - Thread max_priority computed only over unreplied messages (consistent with scoring intent)
  - digest endpoint uses INNER JOIN (only scored emails are meaningful in digest)
  - is_read at thread level: False if any message is unread (most conservative)
metrics:
  duration: ~5 min
  completed: 2026-03-24
---

# Phase 5 Plan 01: Email Read API Endpoints and API Client put() Summary

**One-liner:** Four email read endpoints (threads list, thread detail, manual sync, digest) added to api/email.py using single JOIN queries with Python-side grouping, plus put() method in frontend api.ts.

## Tasks Completed

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 1 | GET /email/threads and GET /email/threads/{thread_id} | Done | 8031c35 |
| 2 | POST /email/sync, GET /email/digest, api.ts put method | Done | 8031c35 |

## What Was Built

### backend/src/flywheel/api/email.py

Extended with 4 new endpoints prepended before the existing draft lifecycle endpoints:

**GET /email/threads**
- Query params: `priority_min` (optional filter), `offset`, `limit`
- Single `SELECT email, email_score, email_draft LEFT JOIN LEFT JOIN` query ordered by `received_at DESC`
- Python-side grouping by `gmail_thread_id` into a dict
- Max priority computed over unreplied messages only
- Thread `is_read=False` if any message is unread
- Sort: max_priority DESC (None treated as 0), then latest_received_at DESC
- Returns `ThreadListResponse` with `total` before slicing for pagination

**GET /email/threads/{thread_id}**
- Single JOIN query filtered by `gmail_thread_id` AND `tenant_id`
- Builds `MessageDetail` list ordered by `received_at ASC`
- Attaches `MessageScore` per message if score row exists
- Captures first pending `EmailDraft` encountered across thread
- Returns 404 if no emails found for that thread_id

**POST /email/sync**
- Verifies gmail-read integration is connected (400 if not)
- Snapshots `integration_id`, `tenant_id`, `user_id` before background task (avoids ORM detached instance)
- `_run_sync()` inner async function re-loads Integration inside `tenant_session`, calls `sync_gmail()`
- Non-fatal: exceptions logged but don't surface to user
- Returns `SyncResponse(message="Sync triggered", syncing=True)` immediately

**GET /email/digest**
- INNER JOIN on EmailScore (only scored emails)
- Filters: `received_at >= today_start UTC` AND `priority <= 2`
- Groups by `gmail_thread_id`, counts messages per thread
- Returns `DigestResponse` with ISO date string

### frontend/src/lib/api.ts

Added `put` method to the `api` object after `patch`:
```typescript
put: <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
```

### New Pydantic Models Added

- `ThreadSummary`, `ThreadListResponse` — thread list pagination
- `MessageScore`, `MessageDetail`, `DraftDetail`, `ThreadDetailResponse` — thread detail
- `SyncResponse` — background sync trigger
- `DigestThread`, `DigestResponse` — low-priority digest
- `priority_to_tier(p: int | None) -> str` helper

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written with one clarification:

**[Rule 5 - Spec Gap] POST /email/sync inner session pattern**

The plan specified `_run_sync()` using `async with tenant_session(get_session_factory(), ...)` directly, but the integration ORM object would be detached when the background task runs after the request session closes. Implemented a two-step approach: snapshot IDs before the task, reload Integration inside the background `factory()` session. This follows the established `_sync_one_integration` pattern from gmail_sync.py.

The `_run_sync` inner function uses a superuser session to fetch the integration row, then opens a tenant_session to call `sync_gmail()` — consistent with how `email_sync_loop` operates.

## Verification Results

```
All routes: ['/email/threads', '/email/threads/{thread_id}', '/email/sync', '/email/digest',
             '/email/drafts/{draft_id}/approve', '/email/drafts/{draft_id}/dismiss',
             '/email/drafts/{draft_id}']
All assertions passed
```

- `grep -c 'put:' frontend/src/lib/api.ts` → `1`
- Existing approve/dismiss/edit signatures confirmed unchanged

## Self-Check: PASSED

Files exist:
- FOUND: backend/src/flywheel/api/email.py
- FOUND: frontend/src/lib/api.ts

Commits:
- FOUND: 8031c35 — feat(05-01): add email read API endpoints and api.ts put method
