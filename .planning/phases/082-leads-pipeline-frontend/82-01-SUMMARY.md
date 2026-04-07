---
phase: 082-leads-pipeline-frontend
plan: 01
subsystem: ui
tags: [react, ag-grid, react-query, typescript, leads]

requires:
  - phase: none
    provides: n/a
provides:
  - Lead, LeadContact, LeadMessage, LeadsResponse, PipelineFunnel, LeadParams types
  - fetchLeads, fetchLeadsPipeline, fetchLeadDetail, graduateLead API functions
  - useLeads, useLeadsPipeline, useLeadDetail, useLeadGraduate React Query hooks
  - useLeadsColumns with 8 ag-grid column definitions and localStorage persistence
  - StageBadge, PurposePills, LeadGraduateButton, LeadCompanyCell cell renderers
affects: [82-02, 82-03, leads-page, leads-side-panel]

tech-stack:
  added: []
  patterns: [leads data layer mirroring pipeline feature structure]

key-files:
  created:
    - frontend/src/features/leads/types/lead.ts
    - frontend/src/features/leads/api.ts
    - frontend/src/features/leads/hooks/useLeads.ts
    - frontend/src/features/leads/hooks/useLeadsPipeline.ts
    - frontend/src/features/leads/hooks/useLeadDetail.ts
    - frontend/src/features/leads/hooks/useLeadGraduate.ts
    - frontend/src/features/leads/hooks/useLeadsColumns.ts
    - frontend/src/features/leads/components/cell-renderers/StageBadge.tsx
    - frontend/src/features/leads/components/cell-renderers/PurposePills.tsx
    - frontend/src/features/leads/components/cell-renderers/LeadGraduateButton.tsx
    - frontend/src/features/leads/components/cell-renderers/LeadCompanyCell.tsx
  modified: []

key-decisions:
  - "Inline FitTierBadge in useLeadsColumns.ts typed to Lead (avoids pipeline cross-import)"
  - "LeadGraduateButton uses native button with CSS vars (not shadcn Button) for lighter cell renderer"
  - "StageBadge uses hex color + 1a suffix for 10% opacity background (no rgba conversion needed)"

patterns-established:
  - "Leads feature mirrors pipeline feature structure: types/, api.ts, hooks/, components/cell-renderers/"

duration: 2min
completed: 2026-04-01
---

# Phase 82 Plan 01: Leads Data Layer Summary

**6 TypeScript types, 4 API functions, 4 React Query hooks, 8-column ag-grid definitions with 4 cell renderers for the leads pipeline feature**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-01T07:56:38Z
- **Completed:** 2026-04-01T07:58:39Z
- **Tasks:** 2
- **Files created:** 11

## Accomplishments
- Complete type system matching backend Lead serializers (6 interfaces + STAGE_COLORS + STAGE_ORDER)
- API layer with 4 functions hitting /leads/ endpoints with clean param filtering
- 4 React Query hooks: paginated list with placeholderData, funnel counts, detail (enabled when id set), graduation mutation with toast + invalidation
- 8-column ag-grid definitions with Company (pinned left), Stage, Fit, Contacts, Purpose, Source, Added, and Graduate action (pinned right)
- 4 cell renderers: StageBadge (colored pill with dot), PurposePills (max 2 + overflow), LeadCompanyCell (name + domain), LeadGraduateButton (hidden when graduated, stopPropagation)

## Task Commits

Per-plan commit strategy (single commit for all tasks):

1. **Task 1: Types, API functions, and React Query hooks** - `8b96cec` (feat)
2. **Task 2: Column definitions hook and 4 cell renderers** - `8b96cec` (feat)

## Files Created/Modified
- `frontend/src/features/leads/types/lead.ts` - 6 interfaces, STAGE_COLORS map, STAGE_ORDER array
- `frontend/src/features/leads/api.ts` - fetchLeads, fetchLeadsPipeline, fetchLeadDetail, graduateLead
- `frontend/src/features/leads/hooks/useLeads.ts` - Paginated leads query with placeholderData
- `frontend/src/features/leads/hooks/useLeadsPipeline.ts` - Funnel counts query
- `frontend/src/features/leads/hooks/useLeadDetail.ts` - Detail query, enabled when id set
- `frontend/src/features/leads/hooks/useLeadGraduate.ts` - Graduation mutation with invalidation + toast
- `frontend/src/features/leads/hooks/useLeadsColumns.ts` - 8 column defs, FitTierBadge inline, localStorage persistence
- `frontend/src/features/leads/components/cell-renderers/StageBadge.tsx` - Colored stage pill with 6px dot
- `frontend/src/features/leads/components/cell-renderers/PurposePills.tsx` - Purpose pills with +N overflow
- `frontend/src/features/leads/components/cell-renderers/LeadGraduateButton.tsx` - Graduate action with stopPropagation
- `frontend/src/features/leads/components/cell-renderers/LeadCompanyCell.tsx` - Company name + domain subtitle

## Decisions Made
- Inline FitTierBadge in useLeadsColumns.ts typed to Lead rather than importing from pipeline (avoids cross-feature type coupling)
- LeadGraduateButton uses native HTML button with CSS custom properties instead of shadcn Button for lighter cell renderer weight
- StageBadge uses hex color + `1a` suffix for 10% opacity background instead of rgba conversion

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All data layer and cell renderer components ready for Plan 02 (LeadsPage orchestrator, funnel, filter bar)
- All hooks exported and typed for direct consumption
- Column definitions ready for ag-grid integration

---
*Phase: 082-leads-pipeline-frontend*
*Completed: 2026-04-01*
