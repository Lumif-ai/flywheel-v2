---
phase: 136-high-impact-frontend
plan: 01
subsystem: ui
tags: [react, ag-grid, tanstack-query, broker, dashboard]

# Dependency graph
requires:
  - phase: 133-backend-new-endpoints
    provides: /broker/dashboard-stats endpoint with total_projects, projects_needing_action, total_premium, projects_by_status
provides:
  - MetricCard component (reusable KPI card with optional coral accent border)
  - useDashboardStats hook querying ['broker-dashboard-stats']
  - BrokerDashboard with 4 live KPI cards + Needs Attention filter badge
  - ProjectPipelineGrid with Premium col, Days Since Update col, coral row borders for action-needed statuses
affects: [136-02, 136-03, 136-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - MetricCard pattern: generic KPI card with label/value/sub/accent props
    - filterAttention pattern: parent manages filter state, passes computed status param to useBrokerProjects
    - getRowStyle pattern: ag-grid row highlight via borderLeft for status-based visual priority

key-files:
  created:
    - frontend/src/features/broker/components/MetricCard.tsx
    - frontend/src/features/broker/hooks/useDashboardStats.ts
  modified:
    - backend/src/flywheel/api/broker/projects.py
    - frontend/src/features/broker/types/broker.ts
    - frontend/src/features/broker/api.ts
    - frontend/src/features/broker/components/BrokerDashboard.tsx
    - frontend/src/features/broker/components/ProjectPipelineGrid.tsx

key-decisions:
  - "Filter state managed in BrokerDashboard (not grid) — passes computed status string to useBrokerProjects, keeps grid dumb"
  - "Needs Attention filter resets offset to 0 on toggle to avoid empty page bug"
  - "Days Since Update uses valueGetter (not field) so no extra DB column needed"

patterns-established:
  - "MetricCard with accent=true adds 3px coral left border matching brand palette"
  - "ACTION_STATUSES constant shared between getRowStyle and BrokerDashboard filter"

# Metrics
duration: 20min
completed: 2026-04-15
---

# Phase 136 Plan 01: Dashboard KPI Cards + Pipeline Enhancements Summary

**4 live MetricCards wired to /broker/dashboard-stats, coral row borders for action-needed projects, Premium + Days Since Update columns in pipeline grid, and Needs Attention filter badge**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-15T00:00:00Z
- **Completed:** 2026-04-15T00:20:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Wired BrokerDashboard to real /broker/dashboard-stats data via useDashboardStats hook
- Added 4 MetricCards: Total Projects, Needs Attention (coral accent when > 0), Total Premium (compact currency format), Quotes Complete
- Pipeline grid now shows Premium (CurrencyCell) and Days Since Update (DaysCell, valueGetter) columns
- Action-needed rows (new_request, analysis_failed, gaps_identified) highlighted with 3px coral left border via getRowStyle
- "Needs Attention" toggle badge filters grid to action-needed rows only; resets pagination on toggle
- Backend _project_to_dict now serializes start_date field

## Task Commits

1. **Task 1: Backend patch + type/api/hook layer** - `a3c73b5` (feat)
2. **Task 2: MetricCard + BrokerDashboard + pipeline grid** - `a3c73b5` (feat)

**Plan commit:** `a3c73b5` (per-plan strategy — single commit)

## Files Created/Modified
- `backend/src/flywheel/api/broker/projects.py` - Added start_date serialization to _project_to_dict
- `frontend/src/features/broker/types/broker.ts` - Added start_date to BrokerProject, added DashboardStats interface
- `frontend/src/features/broker/api.ts` - Added DashboardStats import, fetchDashboardStats() function
- `frontend/src/features/broker/hooks/useDashboardStats.ts` - New hook, query key ['broker-dashboard-stats'], staleTime 60s
- `frontend/src/features/broker/components/MetricCard.tsx` - New reusable KPI card component
- `frontend/src/features/broker/components/BrokerDashboard.tsx` - 4 MetricCards, filterAttention state, Needs Attention badge
- `frontend/src/features/broker/components/ProjectPipelineGrid.tsx` - CurrencyCell/DaysCell cols, getRowStyle, ACTION_STATUSES constant

## Decisions Made
- Filter state (filterAttention) managed in BrokerDashboard, not the grid — keeps ProjectPipelineGrid a dumb display component
- Needs Attention toggle resets offset to 0 to prevent empty page on filtered result set
- Days Since Update uses valueGetter computing from updated_at — no new DB column, no extra endpoint

## Deviations from Plan
None — plan executed exactly as written.

## Issues Encountered
Pre-existing TypeScript errors in GapCoverageGrid.tsx and api.ts (CreateProjectPayload not imported) were present before this plan and are not introduced by these changes. Verified via git stash comparison.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- MetricCard is reusable — other dashboard panels can adopt it
- useDashboardStats hook ready for other consumers
- filterAttention pattern established for other filter badges
- 136-02, 136-03, 136-04 can proceed in parallel

---
*Phase: 136-high-impact-frontend*
*Completed: 2026-04-15*
