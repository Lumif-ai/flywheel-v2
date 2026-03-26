---
phase: 52-backend-apis
plan: "03"
subsystem: api
tags: [fastapi, sqlalchemy, crm, timeline, pulse, signals]

requires:
  - phase: 52-01
    provides: Account, AccountContact, OutreachActivity ORM models and accounts router
  - phase: 52-02
    provides: OutreachActivity data and outreach router patterns
  - phase: 50-01
    provides: CRM table migrations (accounts, account_contacts, outreach_activities, context_entries account_id FK)

provides:
  - GET /api/v1/accounts/{account_id}/timeline — unified chronological feed (outreach + context entries) with type discriminator
  - GET /api/v1/pulse/ — prioritized signal feed computing reply_received, followup_overdue, and bump_suggested from live CRM data

affects:
  - frontend timeline view
  - dashboard pulse widget
  - phase 53 (any frontend integration of CRM APIs)

tech-stack:
  added: []
  patterns:
    - "Multi-source merge in Python: fetch both result sets, union as dicts, sort by date DESC, then slice for pagination"
    - "Pulse signals as computed views: 3 independent queries merged at runtime, sorted by priority ASC then created_at DESC"
    - "Subquery pattern for bump_suggested: latest_outreach + replied subqueries joined with outerjoin to filter no-reply prospects"

key-files:
  created:
    - backend/src/flywheel/api/timeline.py
  modified:
    - backend/src/flywheel/main.py

key-decisions:
  - "Timeline v1 includes outreach activities and context entries only — UploadedFile has no account_id FK so documents are deferred with a TODO"
  - "Pulse bump_suggested uses subquery approach: max(sent_at) subquery + replied accounts subquery, outerjoin to find zero-reply prospects"
  - "Router has no prefix — each endpoint carries its own full path (/accounts/{id}/timeline and /pulse/) to avoid ambiguity with the accounts router"

patterns-established:
  - "Python-side merge for timeline: fetch all rows from each source, convert to dicts, sort, paginate — avoids complex UNION ALL across mismatched schemas"
  - "Pulse as on-the-fly computation: no materialized view, always reflects current DB state"

duration: 2min
completed: 2026-03-27
---

# Phase 52 Plan 03: Timeline and Pulse Signals API Summary

**GET /accounts/{id}/timeline merges outreach+context entries chronologically; GET /pulse/ surfaces reply_received, followup_overdue, and bump_suggested signals from live CRM data via subquery computation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-27T~09:21Z
- **Completed:** 2026-03-27T~09:23Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Unified timeline endpoint (API-04) interleaving OutreachActivity and ContextEntry rows sorted by date DESC with `type` discriminator field
- Pulse signals endpoint (API-05) computing 3 signal types from real seeded data: replies in last 7 days, overdue follow-ups, and bump suggestions for stale prospects
- Both endpoints tenant-scoped via `get_tenant_db` dependency, registered at `/api/v1` prefix in main.py

## Task Commits

Plan-level batch commit (commit_strategy: per-plan):

1. **Task 1: Timeline and Pulse Signals API module** — `f320df2` (feat)
2. **Task 2: Register timeline router in main.py** — `f320df2` (feat, same commit)

## Files Created/Modified

- `backend/src/flywheel/api/timeline.py` — New module: GET /accounts/{id}/timeline and GET /pulse/ with all Pydantic response models and query logic
- `backend/src/flywheel/main.py` — Added timeline_router import and `app.include_router(timeline_router, prefix="/api/v1")`

## Decisions Made

- Timeline v1 includes only outreach activities and context entries — UploadedFile has no direct `account_id` FK, so document timeline items are deferred with a TODO comment
- Pulse `bump_suggested` uses a two-subquery approach: one subquery for `max(sent_at)` per account and another for accounts with any `status="replied"` activity; outer join to find zero-reply prospects with stale outreach
- Router declared without a prefix string (tags only) so each endpoint path is self-contained, avoiding ambiguity with the accounts router that already owns `/accounts/` prefix

## Deviations from Plan

None — plan executed exactly as written. The plan explicitly called out the document limitation in v1 and provided the full subquery pattern for bump_suggested.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All 3 backend API plans (52-01, 52-02, 52-03) are complete
- 8 accounts endpoints, 4 outreach endpoints, 2 timeline/pulse endpoints all live at `/api/v1`
- Ready for Phase 53 frontend integration: timeline view, pulse widget, and pipeline board can all hit real API endpoints

---
*Phase: 52-backend-apis*
*Completed: 2026-03-27*
