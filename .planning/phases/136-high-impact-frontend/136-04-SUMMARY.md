---
phase: 136-high-impact-frontend
plan: 04
subsystem: ui
tags: [ag-grid, comparison-matrix, typescript, broker, frontend, comp-requirements]

# Dependency graph
requires:
  - phase: 136-03
    provides: ag-grid spike with ComparisonCellRenderer, fullWidthRow section headers, pinned total row, spike decision approved:ag-grid
  - phase: 136-01
    provides: ComparisonQuoteCell optional flags (is_recommended/is_best_price/is_best_coverage) in broker.ts

provides:
  - Complete comparison matrix satisfying all COMP-01 through COMP-08 requirements
  - CriticalExclusionAlert per-quote carrier detail listing
  - AI Insight card with template narrative (client-side, no new endpoint)
  - Partial comparison amber banner
  - Interactive/PDF view mode toggle in toolbar
  - Expandable coverage group sections (Insurance/Surety collapse)
  - Recommended carrier column header badge

affects:
  - 136-05 (final phase plans build on complete comparison matrix)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CarrierHeaderWithBadge: IHeaderParams + isRecommended param for coral badge in colDef headerComponent"
    - "CarrierCellRenderer: unified renderer — handles data cells AND pinned bottom row via props.node.rowPinned check"
    - "Expandable sections: useState<Set<string>> collapsedSections + filter on allRowsWithSections (section header rows always included)"
    - "viewMode prop: 'interactive' | 'pdf' threaded from ComparisonView → ComparisonTabs → ComparisonGrid"
    - "PdfPrintView: static HTML table with recommended coral border, used when viewMode=pdf"
    - "deriveInsightText: vote-count across is_recommended flags to generate template recommendation string"

key-files:
  created: []
  modified:
    - frontend/src/features/broker/components/comparison/ComparisonGrid.tsx
    - frontend/src/features/broker/components/comparison/ComparisonView.tsx
    - frontend/src/features/broker/components/comparison/CriticalExclusionAlert.tsx
    - frontend/src/features/broker/components/comparison/ComparisonToolbar.tsx
    - frontend/src/features/broker/components/comparison/ComparisonTabs.tsx
    - frontend/src/features/broker/api.ts

key-decisions:
  - "CarrierCellRenderer replaces TotalsCellRenderer — checks props.node.rowPinned==='bottom' internally; pinnedBottomRowCellRenderer prop does not exist in this ag-grid version"
  - "PDF mode renders PdfPrintView (static HTML table) rather than ag-grid print styles — simpler, reliable across browsers"
  - "AI Insight shown only when recommendation data available (hides 'Insufficient data' variant to avoid noise)"
  - "viewMode flows ComparisonView → ComparisonTabs → ComparisonGrid as optional prop with default 'interactive'"
  - "Expandable groups use pure client-side filter on rowData — no ag-grid grouping API needed"

# Metrics
duration: 30min
completed: 2026-04-15
---

# Phase 136 Plan 04: Complete Comparison Matrix Summary

**Full comparison matrix with all COMP-01 through COMP-08 requirements: recommended carrier badge, expandable coverage groups, AI Insight card, critical exclusion alert, partial banner, Interactive/PDF toggle, and stable pinned totals**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-04-15T13:39:15Z
- **Completed:** 2026-04-15T14:10:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

### Task 1: ComparisonGrid — recommended badge, expandable groups, pinned totals (COMP-01, 02, 06, 07, 08)

- **COMP-06 Recommended carrier header badge:** `CarrierHeaderWithBadge` headerComponent renders coral "Recommended" pill for the winning carrier; passed via `headerComponentParams.isRecommended`. Column also keeps `borderLeft: '3px solid #E94D35'` cellStyle.
- **COMP-02 Expandable coverage groups:** `useState<Set<string>>` tracks collapsed section labels. `toggleSection` callback passed through `context` to `SectionHeaderRenderer`. Rows with a `_section` matching a collapsed label are filtered out. Section header rows always remain visible. ChevronRight/ChevronDown icons indicate state.
- **COMP-07 Stable pinned totals:** `pinnedBottomRowData` computed from the full `coverages` array — never the filtered `rowData` — so totals remain correct when groups are collapsed.
- **COMP-08 PDF mode:** `PdfPrintView` renders a static HTML table with coral recommended-carrier borders and a `<tfoot>` total row. Active when `viewMode='pdf'`.
- **Renderer consolidation:** `CarrierCellRenderer` replaces the old `ComparisonCellRenderer` + `TotalsCellRenderer` pair. It checks `props.node.rowPinned === 'bottom'` to switch between totals and data rendering — the `pinnedBottomRowCellRenderer` grid prop does not exist in this ag-grid version.

### Task 2: ComparisonView + CriticalExclusionAlert + ComparisonToolbar (COMP-03, 04, 05, 08)

- **COMP-03 CriticalExclusionAlert:** Refactored to `flatMap` across all coverage quotes producing `{ coverage, carrier, detail }` items. Renders red card with exact spec styling (`rgba(239,68,68,0.06)` bg, `rgba(239,68,68,0.4)` border) listing each carrier–coverage pair.
- **COMP-04 AI Insight card:** `deriveInsightText()` in ComparisonView tallies `is_recommended` votes per carrier and generates `"{top} is recommended for {N} of {total} coverages — lowest premium without critical exclusions."` Renders coral accent card with `Sparkles` icon. Hidden when no recommendation data is available (avoids showing the fallback message as noise).
- **COMP-05 Partial comparison banner:** Amber `bg-amber-50 border-amber-200` banner with `Info` icon shown when `data.partial === true`.
- **COMP-08 Interactive/PDF toggle:** `ViewModeToggle` segmented control added to `ComparisonToolbar`. In PDF mode, Export Excel button replaced with Print button (`window.print()`). `viewMode` state lives in `ComparisonView`, threaded down through `ComparisonTabs` → `ComparisonGrid`.
- **Render order in ComparisonView:** Toolbar → Partial banner → CriticalExclusionAlert → AI Insight card → ComparisonGrid (via ComparisonTabs).

## Task Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 + 2 | Complete comparison matrix COMP-01–COMP-08 | fe1d79f |

## Files Created/Modified

- `frontend/src/features/broker/components/comparison/ComparisonGrid.tsx` — expandable groups, recommended header badge, unified cell renderer, PDF print view, viewMode prop
- `frontend/src/features/broker/components/comparison/ComparisonView.tsx` — AI Insight card, partial banner, viewMode state, toolbar wiring
- `frontend/src/features/broker/components/comparison/CriticalExclusionAlert.tsx` — refactored to per-quote flatMap with exact spec styling
- `frontend/src/features/broker/components/comparison/ComparisonToolbar.tsx` — Interactive/PDF ViewModeToggle, Print button for PDF mode
- `frontend/src/features/broker/components/comparison/ComparisonTabs.tsx` — viewMode prop added and passed to ComparisonGrid instances
- `frontend/src/features/broker/api.ts` — pre-existing missing import fixed (CreateProjectPayload)

## Decisions Made

- `CarrierCellRenderer` unified renderer replaces separate `TotalsCellRenderer` — `pinnedBottomRowCellRenderer` is not a valid AgGridReact prop in this version; `props.node.rowPinned === 'bottom'` is the correct detection mechanism
- PDF mode uses a static `PdfPrintView` component (plain HTML table) rather than ag-grid print mode — simpler, no print CSS needed, recommended carrier styling applied consistently
- AI Insight card hidden (not shown with fallback message) when no `is_recommended` data — avoids confusing "Insufficient data" text for brokers viewing older quotes
- `viewMode` as optional prop with default `'interactive'` throughout the chain — no breaking change to existing callers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `pinnedBottomRowCellRenderer` prop does not exist in ag-grid React API**
- **Found during:** Task 1 build
- **Issue:** Plan specified `pinnedBottomRowCellRenderer` as an AgGridReact prop, but this property is not in the ag-grid-react type definitions for this version. Build failed with `Property 'pinnedBottomRowCellRenderer' does not exist`.
- **Fix:** Unified `CarrierCellRenderer` checks `props.node.rowPinned === 'bottom'` internally to switch rendering. Removed the separate `TotalsCellRenderer`. Clean pattern — one renderer handles both cases.
- **Files modified:** `ComparisonGrid.tsx`
- **Committed in:** fe1d79f

**2. [Rule 3 - Blocking] Pre-existing `CreateProjectPayload` missing from api.ts import**
- **Found during:** Task 2 build (clean build check)
- **Issue:** `api.ts` line 63 uses `CreateProjectPayload` type which is defined in `broker.ts` but was not imported. Pre-existing error confirmed by git stash test. Blocked clean build.
- **Fix:** Added `CreateProjectPayload` to the import list in api.ts.
- **Files modified:** `frontend/src/features/broker/api.ts`
- **Committed in:** fe1d79f

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking build issues)
**Impact on plan:** Both were essential for achieving the "clean build" success criterion. Neither changed plan logic or architecture.

## Verification Results

1. COMP-01: ComparisonCellRenderer (via `CarrierCellRenderer`) shows premium + limit/deductible in two rows — confirmed in renderer code
2. COMP-02: SectionHeaderRenderer with `ChevronRight/Down` icon, `collapsedSections` filter on `rowData` — expandable groups implemented
3. COMP-03: CriticalExclusionAlert flatMaps per-quote critical exclusions, red card with spec-exact styling — confirmed
4. COMP-04: `deriveInsightText()` generates template narrative from `is_recommended` votes — AI Insight card renders with coral styling
5. COMP-05: Partial banner on `data.partial === true` — amber InfoCard implemented
6. COMP-06: `CarrierHeaderWithBadge` with coral "Recommended" pill + `borderLeft: '3px solid #E94D35'` cellStyle — confirmed
7. COMP-07: `pinnedBottomRowData` computed from full `coverages` array — stable across collapse toggles
8. COMP-08: `ViewModeToggle` segmented control in toolbar, `PdfPrintView` static table in PDF mode
9. Build: `npm run build` — clean build (✓ built in 2.57s), no TypeScript errors

## Self-Check: PASSED

- `frontend/src/features/broker/components/comparison/ComparisonGrid.tsx` — exists, 309 lines
- `frontend/src/features/broker/components/comparison/ComparisonView.tsx` — exists, 130 lines
- `frontend/src/features/broker/components/comparison/CriticalExclusionAlert.tsx` — exists, 42 lines
- `frontend/src/features/broker/components/comparison/ComparisonToolbar.tsx` — exists, 117 lines
- `frontend/src/features/broker/components/comparison/ComparisonTabs.tsx` — exists, updated
- Commit fe1d79f — confirmed in git log

---
*Phase: 136-high-impact-frontend*
*Completed: 2026-04-15*
