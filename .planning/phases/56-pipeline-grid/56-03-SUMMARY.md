---
phase: 56-pipeline-grid
plan: 03
subsystem: ui
tags: [react, ag-grid, fastapi, multi-select, pagination, modal, graduation]

# Dependency graph
requires:
  - phase: 56-02
    provides: AG Grid pipeline with 9 columns, GraduateButton cell renderer using context.onGraduate stub
  - phase: 55-01
    provides: POST /relationships/{id}/graduate endpoint accepting types[] and entity_level

provides:
  - Multi-select filter bar (Fit Tier: Excellent/Strong/Good/Fair/Weak; Outreach Status: Sent/Opened/Replied/Bounced) with 300ms debounced search
  - Saved view tabs (All, Hot, Stale, Replied) with URL ?view= persistence
  - Stale row warm-tint background (days_since_last_outreach > 14)
  - Replied rows float to top with coral left border
  - Page size selector (25/50/100) with server-side offset pagination
  - GraduationModal with Customer/Advisor/Investor checkboxes and entity_level auto-detection
  - Backend GET /pipeline/ accepting fit_tier[], outreach_status[], search as multi-value list params with IN() clauses on both data and count queries
  - useGraduate hook calling POST /relationships/{id}/graduate with types[] array, invalidating pipeline+relationships+signals+accounts

affects: [57-relationship-detail, phase-57]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Multi-select checkbox dropdown (Popover-less) using click-outside ref pattern
    - View tab URL persistence using useSearchParams from react-router
    - Comma-separated array serialization for query params (frontend splits/backend splits)
    - Client-side stale filter via items.filter on already-loaded data (Stale tab)
    - Entity level auto-detection: only advisor/investor => person, otherwise company
    - AG Grid postSortRows for replied-float-to-top behavior
    - AG Grid getRowStyle for per-row dynamic styling (stale tint, slide-out animation, reply border)

key-files:
  created:
    - frontend/src/features/pipeline/components/PipelineFilterBar.tsx
    - frontend/src/features/pipeline/components/PipelineViewTabs.tsx
    - frontend/src/features/pipeline/components/GraduationModal.tsx
  modified:
    - backend/src/flywheel/api/outreach.py
    - frontend/src/features/pipeline/api.ts
    - frontend/src/features/pipeline/types/pipeline.ts
    - frontend/src/features/pipeline/hooks/useGraduate.ts
    - frontend/src/features/pipeline/components/PipelinePage.tsx

key-decisions:
  - "Comma-separated array param serialization: frontend sends fit_tier=Excellent,Strong as single param; backend _expand() splits on commas — avoids axios repeated-param encoding issues"
  - "Stale tab uses client-side filter (items.filter on already-loaded data) — days_since_last_outreach already present in each row, no extra server call"
  - "Entity level auto-detection in GraduationModal: if all selected types are advisor/investor (no customer), set entity_level=person; else company"
  - "Count query for pagination applies same fit_tier, outreach_status, search filters with LEFT JOIN on last_status_sq subquery — prevents pagination count mismatch"
  - "Stale row and replied row styles use getRowStyle (not CSS classes) to avoid AG Grid class-name conflicts with Tailwind v4"
  - "postSortRows pushes replied rows to top for All/Hot/Stale views; no re-sort in Replied tab (already server-filtered)"

patterns-established:
  - "MultiSelect: controlled dropdown with useRef click-outside, accentColor var(--brand-coral) for checkboxes"
  - "View tabs: PipelineViewTabs sets ?view= URL param; PipelinePage reads it to derive server filter params"

# Metrics
duration: 5min
completed: 2026-03-27
---

# Phase 56 Plan 03: Pipeline Filters, Tabs, Graduation Modal Summary

**Multi-select filter bar (Excellent/Strong/Good/Fair/Weak tiers; outreach statuses), All/Hot/Stale/Replied URL-persisted view tabs, stale/replied row visual signals, 25/50/100 page size pagination, and GraduationModal calling POST /relationships/{id}/graduate with Customer/Advisor/Investor type selection**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-27T11:16:58Z
- **Completed:** 2026-03-27T11:21:58Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Backend GET /pipeline/ now accepts fit_tier and outreach_status as list[str] params with IN() clauses applied to both data and count queries (accurate pagination counts), plus search text filter on name/domain
- Frontend filter bar renders multi-select checkbox dropdowns (not single-value selects) with click-outside close, active selection count display, and 300ms debounced search input
- View tabs (All/Hot/Stale/Replied) persist active tab in ?view= URL param; Hot sets fitTier server param, Replied sets outreachStatus, Stale applies client-side filter on days_since_last_outreach
- Stale rows (>14 days) render with var(--brand-tint-warmest) background; replied rows float to top with coral left border via AG Grid postSortRows + getRowStyle
- Page size selector (25/50/100) drives server-side offset pagination with prev/next controls and "Showing X-Y of Z" display
- GraduationModal connects GraduateButton context stub from Plan 02 — Customer/Advisor/Investor card checkboxes, entity_level auto-detection (person if only advisor/investor), calls POST /relationships/{id}/graduate, invalidates pipeline+relationships+signals+accounts cache

## Task Commits

Per-plan commit strategy (single commit for all task work):

1. **All tasks — filter bar, view tabs, modal, backend** - `6058a54` (feat)

## Files Created/Modified
- `backend/src/flywheel/api/outreach.py` - fit_tier/outreach_status/search as list[str] params with IN() on data+count queries
- `frontend/src/features/pipeline/api.ts` - GraduatePayload calling /relationships/{id}/graduate; comma-separated array serialization
- `frontend/src/features/pipeline/types/pipeline.ts` - fit_tier/outreach_status now string[] arrays
- `frontend/src/features/pipeline/hooks/useGraduate.ts` - accepts GraduatePayload, invalidates pipeline+relationships+signals+accounts
- `frontend/src/features/pipeline/components/PipelineFilterBar.tsx` - CREATED: MultiSelect checkbox dropdowns + debounced search
- `frontend/src/features/pipeline/components/PipelineViewTabs.tsx` - CREATED: All/Hot/Stale/Replied URL-persisted tabs
- `frontend/src/features/pipeline/components/GraduationModal.tsx` - CREATED: Customer/Advisor/Investor dialog calling useGraduate
- `frontend/src/features/pipeline/components/PipelinePage.tsx` - wire all: view tabs, filter bar, modal, row styles, pagination

## Decisions Made
- Comma-separated array param serialization: frontend sends `fit_tier=Excellent,Strong` as single param; backend `_expand()` splits on commas. This avoids axios repeated-param encoding complexity.
- Stale tab uses client-side filter on already-loaded items — `days_since_last_outreach` already in each row, no extra round trip needed.
- Entity level auto-detection in modal: all selected types are advisor/investor => `entity_level: 'person'`, otherwise `'company'`.
- Count query JOIN: added LEFT JOIN on `last_status_sq` subquery to count query so outreach_status filter applies correctly and pagination totals stay accurate.

## Deviations from Plan

None — plan executed exactly as written. The backend count query already needed the outreach_status filter fix which was explicitly called out in the plan spec.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- Pipeline is fully interactive: all GRID-01 through GRID-05 requirements met
- Phase 57 can begin RelationshipDetail surface — graduation from Pipeline now calls the correct /relationships/{id}/graduate endpoint; sidebar badge counts deferred to Phase 57
- queryKeys invalidation pattern established: graduation invalidates pipeline + relationships + signals + accounts simultaneously

---
*Phase: 56-pipeline-grid*
*Completed: 2026-03-27*
