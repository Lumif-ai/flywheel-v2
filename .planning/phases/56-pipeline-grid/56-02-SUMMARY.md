---
phase: 56-pipeline-grid
plan: 02
subsystem: ui
tags: [ag-grid, react, typescript, pipeline, data-grid, localStorage]

# Dependency graph
requires:
  - phase: 56-01
    provides: design tokens (badges.fitTier, badge-translucent CSS class, ShimmerSkeleton, EmptyState, registers)
  - phase: 55-01
    provides: AccountContact model with name/title/email/linkedin_url fields

provides:
  - AG Grid Community v35.2 pipeline page replacing HTML table
  - 9-column grid: Company (avatar+name+domain), Contact (name+title), Email (mailto), LinkedIn (icon), Fit Tier (translucent badge), Outreach (dot), Last Action (relative time), Days Stale (color-coded), Graduate (action button pinned right)
  - Cell renderer components: CompanyCell, ContactCell, FitTierBadge, OutreachDot, GraduateButton, DaysSinceCell
  - usePipelineColumns hook with localStorage column state persistence
  - Backend pipeline endpoint extended with primary contact LEFT JOIN (no N+1)
  - GraduateButton reads context.onGraduate — wired to stub, Plan 03 adds modal

affects:
  - 56-03 (graduation modal — wires context.onGraduate from this plan's GraduateButton)

# Tech tracking
tech-stack:
  added:
    - ag-grid-community v35.2 (programmatic theme API, AllCommunityModule)
    - ag-grid-react v35.2 (AgGridReact component)
  patterns:
    - themeQuartz.withParams() for AG Grid theming via CSS custom properties (no CSS imports)
    - Cell renderers as standalone React components receiving ICellRendererParams<PipelineItem>
    - GraduateButton reads onGraduate from AG Grid context prop — decoupled action injection
    - localStorage column state persistence via getColumnState()/setItem on resize/move/visible events
    - PRIMARY CONTACT via DISTINCT ON subquery — first contact by created_at, no N+1

key-files:
  created:
    - frontend/src/features/pipeline/components/cell-renderers/CompanyCell.tsx
    - frontend/src/features/pipeline/components/cell-renderers/ContactCell.tsx
    - frontend/src/features/pipeline/components/cell-renderers/FitTierBadge.tsx
    - frontend/src/features/pipeline/components/cell-renderers/OutreachDot.tsx
    - frontend/src/features/pipeline/components/cell-renderers/GraduateButton.tsx
    - frontend/src/features/pipeline/components/cell-renderers/DaysSinceCell.tsx
    - frontend/src/features/pipeline/hooks/usePipelineColumns.ts
  modified:
    - frontend/src/features/pipeline/components/PipelinePage.tsx
    - frontend/src/features/pipeline/types/pipeline.ts
    - backend/src/flywheel/api/outreach.py

key-decisions:
  - "AG Grid Email/LinkedIn columns use string cellRenderer (HTML return) not React component — avoids overhead for simple anchor rendering"
  - "fit_tier filter moved to backend query (not just client-side) for accurate total count"
  - "outreach_status filter now properly applied at SQL level in pipeline endpoint"
  - "DaysSinceCell is its own file (not inline) for Plan 03 reuse potential"
  - "GraduateButton wraps content in flex h-full div to vertically center in 56px row"

patterns-established:
  - "Cell renderers: always wrap content in flex items-center h-full for 56px row vertical centering"
  - "AG Grid context injection pattern: PipelinePage passes onGraduate via context prop; GraduateButton reads via props.context.onGraduate"
  - "localStorage key format: flywheel:{page}:{stateType}"

# Metrics
duration: 15min
completed: 2026-03-27
---

# Phase 56 Plan 02: AG Grid Pipeline Page Summary

**AG Grid Community v35 pipeline replacing HTML table — 9 columns with React cell renderers, themeQuartz CSS variable theming, and localStorage column state persistence; backend extended with primary contact LEFT JOIN subquery**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-27T00:00:00Z
- **Completed:** 2026-03-27T00:15:00Z
- **Tasks:** 2/2
- **Files modified:** 12

## Accomplishments

- Replaced HTML table pipeline with AG Grid Community v35 — resize, reorder, virtualize out of the box
- Created 6 focused cell renderer components (CompanyCell with avatar initials, ContactCell, FitTierBadge using badge-translucent + design token colors, OutreachDot 8px status dot, GraduateButton with context injection, DaysSinceCell color-coded)
- Extended backend GET /pipeline/ with primary contact subquery (DISTINCT ON, no N+1) and query-level fit_tier/outreach_status filters
- Column state (width, order, visibility) persists across navigations via localStorage key `flywheel:pipeline:columnState`
- Shimmer skeleton loading state (8 rows × column layout) and EmptyState component wired

## Task Commits

Both tasks committed together (commit_strategy: per-plan):

1. **Task 1: Install AG Grid, extend backend, update types** - `2b19462` (feat)
2. **Task 2: Cell renderers, usePipelineColumns hook, PipelinePage rewrite** - `2b19462` (feat)

## Files Created/Modified

- `frontend/src/features/pipeline/components/cell-renderers/CompanyCell.tsx` - Avatar initials + company name + domain
- `frontend/src/features/pipeline/components/cell-renderers/ContactCell.tsx` - primary_contact_name + title
- `frontend/src/features/pipeline/components/cell-renderers/FitTierBadge.tsx` - badge-translucent + badges.fitTier tokens
- `frontend/src/features/pipeline/components/cell-renderers/OutreachDot.tsx` - 8px colored circle + status label
- `frontend/src/features/pipeline/components/cell-renderers/GraduateButton.tsx` - Ghost button reading props.context.onGraduate
- `frontend/src/features/pipeline/components/cell-renderers/DaysSinceCell.tsx` - Color-coded days (green/amber/red)
- `frontend/src/features/pipeline/hooks/usePipelineColumns.ts` - 9 ColDef array + localStorage persistence hook
- `frontend/src/features/pipeline/components/PipelinePage.tsx` - Rewritten with AgGridReact + themeQuartz + shimmer/empty states
- `frontend/src/features/pipeline/types/pipeline.ts` - Added 4 primary_contact_* fields + search to PipelineParams
- `backend/src/flywheel/api/outreach.py` - PipelineItem extended; primary_contact subquery + LEFT JOIN; fit_tier/outreach_status query params
- `frontend/package.json` - ag-grid-community, ag-grid-react added
- `frontend/package-lock.json` - lockfile updated

## Decisions Made

- AG Grid Email and LinkedIn columns use string-returning cellRenderer (HTML) rather than React components — straightforward anchor tags don't justify React component overhead
- fit_tier and outreach_status filters applied at SQL level (not client-side post-fetch) so the total count is accurate when filters are active
- Graduate column uses `suppressMovable: true` in addition to `pinned: 'right'` to prevent accidental reordering
- No CSS imports from ag-grid-community/styles/ — programmatic theme API only (prevents Tailwind v4 CSS conflict)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added fit_tier and outreach_status as proper query params to backend endpoint**
- **Found during:** Task 1 (backend extension)
- **Issue:** Original pipeline endpoint had no filter params; frontend was sending them but backend silently ignored them; filter state existed in UI but had no effect on results
- **Fix:** Added `fit_tier` and `outreach_status` Query params to `get_pipeline()`, applied to WHERE clause, also corrected total count query to respect fit_tier filter
- **Files modified:** backend/src/flywheel/api/outreach.py
- **Verification:** Import check passes; filters now correctly restrict results
- **Committed in:** 2b19462

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for filter functionality to actually work. No scope creep — the frontend had filter UI but backend was ignoring params.

## Issues Encountered

None — plan executed cleanly. TypeScript compiled with zero errors on first check.

## Self-Check: PASSED

- `frontend/src/features/pipeline/components/cell-renderers/CompanyCell.tsx` — EXISTS
- `frontend/src/features/pipeline/components/cell-renderers/GraduateButton.tsx` — EXISTS
- `frontend/src/features/pipeline/hooks/usePipelineColumns.ts` — EXISTS
- `frontend/src/features/pipeline/components/PipelinePage.tsx` — EXISTS (AgGridReact, themeQuartz confirmed)
- Commit `2b19462` — EXISTS (verified via git log)
- `grep ag-grid frontend/package.json` — MATCHES (ag-grid-community, ag-grid-react v35.2)
- `grep primary_contact backend/src/flywheel/api/outreach.py` — MATCHES

## Next Phase Readiness

- Plan 03 (graduation modal + filter bar) can wire `context.onGraduate` to modal opener — GraduateButton is ready
- All 9 columns render; Plan 03 upgrades filter selects to proper filter bar with search
- Grid state persistence tested conceptually — localStorage read/write on column events

---
*Phase: 56-pipeline-grid*
*Completed: 2026-03-27*
