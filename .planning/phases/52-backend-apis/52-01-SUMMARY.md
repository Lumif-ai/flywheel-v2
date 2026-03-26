---
phase: 52-backend-apis
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, accounts, contacts, crm, pagination]

requires:
  - phase: 50-data-model-and-utilities
    provides: Account, AccountContact, OutreachActivity ORM models and normalize_company_name utility

provides:
  - GET/POST /api/v1/accounts/ — paginated, filterable, searchable, sortable account list + create
  - GET/PATCH /api/v1/accounts/{id} — full account detail with contacts and 3-source timeline + update
  - GET/POST /api/v1/accounts/{id}/contacts — list and create contacts
  - PATCH/DELETE /api/v1/accounts/{id}/contacts/{cid} — update and delete contacts

affects:
  - 53-crm-frontend
  - phase-52-plan-02
  - phase-52-plan-03

tech-stack:
  added: []
  patterns:
    - "Correlated subquery for contact_count in list endpoint (avoids N+1 loads)"
    - "3-source timeline: outreach_activities + context_entries + future UploadedFile, merged+sorted in Python"
    - "ILIKE search across name and domain columns"
    - "Same _paginated_response + serialization helper pattern as context.py"

key-files:
  created:
    - backend/src/flywheel/api/accounts.py
  modified:
    - backend/src/flywheel/main.py

key-decisions:
  - "Correlated subquery for contact_count in list query rather than left join — avoids changing the base query shape needed for count query"
  - "3-source timeline (outreach, context_entries, uploaded_files) merged in Python — simpler than UNION ALL with mismatched column shapes"
  - "next_action_due in UpdateAccountRequest accepts ISO string and parses to datetime — avoids forcing frontend to use complex date type"

patterns-established:
  - "Serialization helpers: _account_to_list_item, _account_to_detail, _contact_to_dict keep endpoint code clean"
  - "_paginated_response helper reused from context.py pattern"

duration: 2min
completed: 2026-03-26
---

# Phase 52 Plan 01: Accounts and Contacts REST API Summary

**FastAPI router with 8 endpoints covering full CRUD for accounts and contacts, with pagination, ILIKE search, multi-column sort, contact count via correlated subquery, and 3-source timeline merge**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-26T16:57:29Z
- **Completed:** 2026-03-26T16:59:08Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `accounts.py` with 8 endpoints: list (paginated/filtered/sorted), detail (eager contacts + timeline), create (normalized_name), update, list contacts, create contact, update contact, delete contact
- Contact count in list endpoint uses correlated subquery — one DB round-trip, no N+1
- Timeline preview fetches from outreach_activities and context_entries separately, merges and sorts in Python (top 10 by date DESC)
- Registered `accounts_router` in `main.py` at `/api/v1` prefix alongside existing routers

## Task Commits

Plan committed as one batch (commit_strategy = per-plan):

1. **Task 1: Accounts and Contacts REST API module** + **Task 2: Register accounts router in main.py** — `950950b` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/accounts.py` — New: 8-endpoint accounts/contacts router with Pydantic models, serialization helpers, and timeline merge logic
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/main.py` — Modified: added import + `app.include_router(accounts_router, prefix="/api/v1")`

## Decisions Made

- Correlated subquery for `contact_count` in list endpoint rather than left join — left join changes the query shape in a way that complicates the count subquery; correlated subquery is clean and performant at the expected row counts
- Timeline fetched via 3 separate queries (outreach_activities, context_entries, uploaded_files pending) merged in Python — avoids UNION ALL complexity with different column shapes; the 10-row limit makes Python merge negligible
- `next_action_due` accepted as ISO string in `UpdateAccountRequest` — simplifies frontend: send a date string, not a datetime object

## Deviations from Plan

None — plan executed exactly as written. The `outreach_router` already existed in `main.py` (added by a parallel change); added accounts_router after it.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All 8 account/contact endpoints available at `/api/v1/accounts/...`
- Phase 52-02 (Activities API) and 52-03 (Timeline/Search API) can now build on the same account_id FK patterns
- Phase 53 (CRM frontend) has the complete REST surface needed for accounts list and account detail pages

---
*Phase: 52-backend-apis*
*Completed: 2026-03-26*
