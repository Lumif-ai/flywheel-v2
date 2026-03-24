---
phase: 01-data-layer-and-gmail-foundation
plan: 02
subsystem: gmail-read-service
tags: [gmail, oauth, read, integrations, email-sync]
dependency_graph:
  requires: []
  provides:
    - gmail_read.py OAuth flow functions
    - gmail_read.py message operations (6 API functions)
    - /gmail-read/authorize endpoint
    - /gmail-read/callback endpoint
    - google_gmail_read_redirect_uri config setting
  affects:
    - Phase 2 sync worker (depends on list_message_headers, get_history, get_profile)
    - Phase 3 scorer (depends on list_sent_messages for voice profile)
    - Phase 4 drafter (depends on get_message_body for context assembly)
tech_stack:
  added:
    - google-auth-oauthlib Flow (gmail-read OAuth grant)
    - googleapiclient gmail v1 API (list, get, history, getProfile)
  patterns:
    - asyncio.to_thread for all blocking Google API calls
    - AES-256-GCM credential encryption via flywheel.auth.encryption
    - Separate OAuth grant per provider (no scope merging)
key_files:
  created:
    - backend/src/flywheel/services/gmail_read.py
  modified:
    - backend/src/flywheel/api/integrations.py
    - backend/src/flywheel/config.py
decisions:
  - "No include_granted_scopes on gmail-read grant — isolates read credential from send-only gmail"
  - "Pre-allocate history_id=None in pending Integration row — Phase 2 sync worker expects this slot"
  - "Three scopes (readonly+modify+send) on single grant — avoids second OAuth prompt for draft approval"
metrics:
  duration_minutes: 3
  completed_date: "2026-03-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 1 Plan 02: Gmail Read Service Summary

**One-liner:** New gmail_read.py service provides isolated Gmail read OAuth grant (3 scopes: readonly+modify+send) with 6 API operations and two new /gmail-read/authorize and /gmail-read/callback endpoints using provider="gmail-read".

## What Was Built

### gmail_read.py — Standalone Gmail Read Service

New service at `backend/src/flywheel/services/gmail_read.py` that is architecturally separate from the existing send-only `google_gmail.py`.

Key design decisions embedded in the code:
- Uses `settings.google_gmail_read_redirect_uri` (not `google_gmail_redirect_uri`) to keep OAuth callbacks isolated
- No `include_granted_scopes` in authorization URL — prevents scope merging with the send-only grant
- Three scopes (`gmail.readonly`, `gmail.modify`, `gmail.send`) so Phase 4 draft approval reuses this same credential
- `TokenRevokedException` defined locally to avoid coupling to `google_gmail.py`

Six Gmail API operations implemented:
1. `list_message_headers` — paginated inbox listing (ids+threadIds only, no content)
2. `get_message_headers` — metadata fetch (From/To/Subject/Date only)
3. `get_message_body` — on-demand full body fetch (Phase 4 drafter use only)
4. `list_sent_messages` — SENT label listing for voice profile extraction
5. `get_history` — incremental sync via historyId (Phase 2 sync worker)
6. `get_profile` — emailAddress + historyId capture for sync initialization

All API calls use `asyncio.to_thread`. No email content (subject, snippet, body) appears in any log statement — only message_id, thread_id, and operation name are logged.

### config.py — New Redirect URI Setting

Added `google_gmail_read_redirect_uri` after the existing `google_gmail_redirect_uri`:
```
google_gmail_read_redirect_uri: str = "http://localhost:5173/api/v1/integrations/gmail-read/callback"
```

### integrations.py — Two New Endpoints

- `GET /gmail-read/authorize` — Creates `Integration(provider="gmail-read", status="pending", settings={"oauth_state": state, "history_id": None})` and returns auth URL
- `GET /gmail-read/callback` — Queries only `provider="gmail-read"` rows, exchanges code, stores encrypted credentials, sets `status="connected"`
- Added `"gmail-read": "Gmail (Read)"` to `_PROVIDER_DISPLAY`
- Both endpoints strictly use `provider="gmail-read"` — never touch `provider="gmail"` rows

## Verification Results

All 6 plan checks passed:
1. `from flywheel.services.gmail_read import generate_gmail_read_auth_url` — OK
2. `from flywheel.api.integrations import router` — OK (no import errors)
3. `grep -c 'provider.*gmail-read' integrations.py` — 6 matches (> 3 required)
4. `grep -c 'include_granted_scopes' gmail_read.py` — 3 matches, all in comments/docstrings explaining why it is NOT used (zero in code)
5. No logger calls containing snippet/subject/body content confirmed
6. `google_gmail_read_redirect_uri` confirmed in config.py

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 17e16f3 | feat(01-02): create gmail_read.py service with OAuth and message operations |
| Task 2 | ac96e6c | feat(01-02): add gmail-read OAuth endpoints and config setting |

## Self-Check: PASSED

All files exist and all commits verified:
- FOUND: backend/src/flywheel/services/gmail_read.py
- FOUND: backend/src/flywheel/api/integrations.py
- FOUND: backend/src/flywheel/config.py
- FOUND commit: 17e16f3 (Task 1)
- FOUND commit: ac96e6c (Task 2)
