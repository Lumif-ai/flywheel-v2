---
phase: 52-backend-apis
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, crm, outreach, pipeline, graduation, auto-graduation]

# Dependency graph
requires:
  - phase: 50-data-model-and-utilities
    provides: Account, AccountContact, OutreachActivity, ContextEntry ORM models
  - phase: 52-backend-apis/52-01
    provides: accounts router (sibling plan in same phase)
provides:
  - GET/POST /api/v1/accounts/{id}/outreach — outreach activity CRUD
  - PATCH /api/v1/outreach/{id} — update outreach with AUTO-01 graduation trigger
  - GET /api/v1/pipeline/ — prospect accounts sorted by fit_score with outreach stats
  - POST /api/v1/accounts/{id}/graduate — manual graduation endpoint
affects: [frontend CRM views, pipeline surface, account detail page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - No-prefix router with explicit path segments for multi-group endpoints
    - Shared _graduate_account() helper called by both auto and manual graduation paths
    - Subquery + window function (row_number) to avoid N+1 on pipeline outreach stats
    - AUTO-01 graduation triggered in both POST create and PATCH update when status=replied

key-files:
  created:
    - backend/src/flywheel/api/outreach.py
  modified:
    - backend/src/flywheel/main.py

key-decisions:
  - "Router has no prefix — endpoints use full explicit paths to span two URL groups (/accounts/{id}/outreach and /outreach/{id})"
  - "_graduate_account() shared helper ensures consistent graduation logic (status change + ContextEntry log) for both auto and manual paths"
  - "Pipeline query uses subquery + row_number window function to fetch last outreach status without N+1"
  - "db.flush() called before _graduate_account in POST /outreach so activity.id is populated for the ContextEntry content string"

patterns-established:
  - "No-prefix router pattern: when a router spans multiple URL groups, set no prefix on router and use full paths on decorators"
  - "Shared business logic helper pattern: extract multi-caller logic into async helper that takes db+user, called before commit"

# Metrics
duration: 2min
completed: 2026-03-26
---

# Phase 52, Plan 02: Outreach, Pipeline, and Graduation API Summary

**5-endpoint FastAPI router for outreach CRUD, pipeline view with outreach stats, and AUTO-01 auto-graduation from prospect to engaged on 'replied' status**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-26T16:57:26Z
- **Completed:** 2026-03-26T16:58:50Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Outreach CRUD (list, create, PATCH) with tenant-scoped RLS via get_tenant_db
- AUTO-01 auto-graduation implemented in both POST /outreach (create) and PATCH /outreach/{id} (update) — when status becomes "replied" and account is a prospect, account.status becomes "engaged" and a ContextEntry is logged
- Pipeline endpoint uses subquery + row_number window function for outreach stats (outreach_count, last_outreach_status, days_since_last_outreach) — no N+1
- Manual graduation endpoint with 400 guard for non-prospect accounts
- Both graduation paths (auto/manual) share _graduate_account() helper for consistent behavior

## Task Commits

Both tasks included in one plan-level commit:

1. **Task 1: Outreach, Pipeline, and Graduation API module** - `9df1119` (feat)
2. **Task 2: Register outreach router in main.py** - `9df1119` (feat)

## Files Created/Modified
- `backend/src/flywheel/api/outreach.py` — Full outreach router: 5 endpoints, Pydantic models, serialization helpers, _graduate_account() shared helper
- `backend/src/flywheel/main.py` — Added outreach_router import and include_router call

## Decisions Made
- No prefix on router: the outreach router spans two URL groups (/accounts/{id}/outreach and /outreach/{id}), so setting prefix on the router itself would break one group. Explicit full paths on each decorator is cleaner.
- Shared _graduate_account() helper: graduation logic (set status, set updated_at, create ContextEntry) is identical between auto and manual paths — extracted to avoid drift.
- Pipeline uses row_number() window function in a subquery to get the most-recent outreach status per account without N+1 queries.
- db.flush() before _graduate_account in POST create: needed to ensure activity.id is populated for the ContextEntry content string before we log it.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- Outreach API is complete and registered; ready for frontend CRM views
- Pipeline endpoint ready for the pipeline surface (triage JTBD)
- Graduate endpoint ready for both manual UI action and future automation triggers

---
*Phase: 52-backend-apis*
*Completed: 2026-03-26*
