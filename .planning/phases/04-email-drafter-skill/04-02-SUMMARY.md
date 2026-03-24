---
phase: 04-email-drafter-skill
plan: 02
subsystem: api
tags: [email, gmail, draft-lifecycle, sync-wiring, rest-api]

# Dependency graph
requires:
  - phase: 04-email-drafter-skill
    plan: 01
    provides: draft_email() engine; EmailDraft ORM model; voice profile injection
  - phase: 03-email-scorer-skill
    provides: EmailScore with priority + suggested_action fields; scorer patterns
  - phase: 01-data-layer-and-gmail-foundation
    provides: gmail_read.get_valid_credentials(); Email.gmail_message_id, gmail_thread_id
provides:
  - _draft_important_emails() wired into both full sync and incremental sync paths
  - send_reply() for threaded Gmail replies with In-Reply-To/References headers
  - get_message_id_header() for on-demand Message-ID fetch at approval time
  - Draft lifecycle REST API: approve, dismiss, edit (3 endpoints)
  - gmail-read provider routing in email_dispatch.py
affects:
  - Phase 5 (frontend): draft list display, approve/dismiss/edit UI actions
  - Phase 6 (scoring refinement): dismissed drafts feed reinforcement learning

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Draft wiring after scoring: same non-fatal try/except block as scoring in sync loop"
    - "LEFT JOIN IS NULL idempotency guard — prevents duplicate drafts across sync cycles"
    - "send_reply() uses MIME In-Reply-To + References headers for proper Gmail thread reply"
    - "Draft approve: send first, null body after — allows retry on send failure"
    - "user_edits field preserves original draft_body for Phase 6 diff analysis"

key-files:
  created:
    - backend/src/flywheel/api/email.py
  modified:
    - backend/src/flywheel/services/gmail_sync.py
    - backend/src/flywheel/services/gmail_read.py
    - backend/src/flywheel/services/email_dispatch.py
    - backend/src/flywheel/main.py

key-decisions:
  - "Draft after scoring not concurrent: ensures EmailScore rows exist before LEFT JOIN IS NULL query"
  - "send first, null body after: draft_body nulled only on successful Gmail send (allows retry)"
  - "user_edits stores edits separately: original draft_body preserved for Phase 6 diff analysis"
  - "get_message_id_header on-demand at approval time: no schema change, no Message-ID storage"
  - "gmail-read dispatch is safety net: dedicated approve endpoint handles real draft sends"

# Metrics
duration: 5min
completed: 2026-03-24
---

# Phase 4 Plan 02: Sync Loop Wiring + Draft Lifecycle API Summary

**Drafting wired into sync pipeline via _draft_important_emails() with LEFT JOIN IS NULL idempotency guard; threaded Gmail reply via MIME In-Reply-To headers; 3-endpoint REST API for approve/dismiss/edit**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-24T13:42:00Z
- **Completed:** 2026-03-24T13:47:10Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `_draft_important_emails()` to `gmail_sync.py`: queries EmailScore rows with `priority >= 3` AND `suggested_action = 'draft_reply'`, LEFT JOIN IS NULL guard prevents duplicate drafts, calls `draft_email()` per qualifying email. Non-fatal — individual failures logged but never block the sync loop.
- Wired `_draft_important_emails()` into both sync paths: after scoring block in `_full_sync()` and `sync_gmail()` (incremental). Each wiring uses the same non-fatal try/except pattern as scoring.
- Added `send_reply()` to `gmail_read.py`: constructs MIME message with `In-Reply-To` and `References` headers for proper Gmail thread reply (not orphaned as new thread).
- Added `get_message_id_header()` to `gmail_read.py`: lightweight metadata-format API call to fetch `Message-ID` header on-demand at approval time. No schema change required.
- Added `gmail-read` provider routing to `email_dispatch.py`: provider filter includes `gmail-read`; new routing block handles general dispatch via gmail-read integration as safety net.
- Created `api/email.py` with 3 endpoints: approve (send as threaded reply, null body, set status=sent), dismiss (set status=dismissed), edit (store in user_edits, preserve draft_body for Phase 6).
- Registered `email_router` in `main.py` at `/api/v1/email/*`.

## Task Commits

All changes committed per-plan (single commit strategy):

1. **Tasks 1+2: sync wiring + draft lifecycle API** - `408b8fa` (feat)

## Files Created/Modified

- `backend/src/flywheel/api/email.py` — Draft lifecycle endpoints: approve, dismiss, edit with tenant RLS + proper status guards
- `backend/src/flywheel/services/gmail_sync.py` — `_draft_important_emails()` + wiring in `_full_sync` and `sync_gmail`; added imports for `draft_email`, `EmailDraft`
- `backend/src/flywheel/services/gmail_read.py` — `send_reply()` + `get_message_id_header()`
- `backend/src/flywheel/services/email_dispatch.py` — `gmail-read` in provider filter + routing case
- `backend/src/flywheel/main.py` — `email_router` import + `include_router` registration

## Decisions Made

- **Draft after scoring, not concurrent:** `_draft_important_emails()` is called AFTER `_score_new_emails()` completes its commit. This ensures EmailScore rows exist before the LEFT JOIN IS NULL query, which guards against duplicates while enabling proper priority filtering.
- **send first, null body after:** In the approve endpoint, Gmail send is called before `draft_body = None`. If send fails, the draft remains in `pending` status with body intact — user can retry. Nulling only happens on confirmed success.
- **user_edits for edits:** The edit endpoint stores changes in `user_edits`, not `draft_body`. This preserves the original AI-generated draft for Phase 6 analysis of user edit patterns.
- **get_message_id_header on-demand:** Rather than storing Message-ID during sync (requiring a schema change), it's fetched on-demand at approval time via a lightweight metadata API call.
- **gmail-read dispatch as safety net:** The approve endpoint in `api/email.py` uses `send_reply()` directly for proper threading. The `email_dispatch.py` gmail-read routing is a safety net for general-purpose dispatch — not the primary path for draft approval.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Verification uses `.venv/bin/python` (standard pattern for this backend — `python` command not available).

## User Setup Required

None.

## Next Phase Readiness

- Draft pipeline is complete end-to-end: sync → score → draft (auto) → approve/dismiss/edit (manual)
- Phase 5 (frontend) can now implement the draft inbox UI: list pending drafts, show draft body, trigger approve/dismiss/edit via the 3 new endpoints
- Phase 6 (scoring refinement) will read `dismissed` drafts and `user_edits` vs `draft_body` diff for reinforcement signals

---
*Phase: 04-email-drafter-skill*
*Completed: 2026-03-24*

## Self-Check: PASSED

- FOUND: backend/src/flywheel/api/email.py
- FOUND: backend/src/flywheel/services/gmail_sync.py (_draft_important_emails: 3 occurrences)
- FOUND: backend/src/flywheel/services/gmail_read.py (send_reply, get_message_id_header)
- FOUND: backend/src/flywheel/services/email_dispatch.py (gmail-read provider)
- FOUND: backend/src/flywheel/main.py (email_router registered)
- FOUND: .planning/phases/04-email-drafter-skill/04-02-SUMMARY.md
- FOUND commit: 408b8fa feat(04-02): wire draft engine into sync loop and add draft lifecycle API
