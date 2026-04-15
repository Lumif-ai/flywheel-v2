---
phase: 136-high-impact-frontend
plan: "02"
subsystem: broker-frontend
tags: [ag-grid, coverage, gap-analysis, urgency-banner, cell-renderers]
dependency_graph:
  requires:
    - "frontend/src/shared/grid/cell-renderers (CurrencyCell, ClauseLink)"
    - "frontend/src/shared/grid/theme (gridTheme, GRID_SHADOW, GRID_BORDER_RADIUS)"
    - "frontend/src/features/broker/types/broker (ProjectCoverage, BrokerProject.start_date)"
  provides:
    - "frontend/src/features/broker/components/GapCoverageGrid.tsx"
    - "frontend/src/features/broker/components/tabs/CoverageTab.tsx (updated)"
  affects:
    - "Coverage tab on all broker project detail pages"
tech_stack:
  added: []
  patterns:
    - "ag-grid isFullWidthRow + fullWidthCellRenderer for Community-compatible section headers"
    - "Union type (ProjectCoverage | SectionHeaderRow) with type guard for mixed row data"
    - "getRowStyle for gap_status row coloring (red/amber tints)"
    - "gap_amount ?? required_limit fallback for missing coverages"
key_files:
  created:
    - "frontend/src/features/broker/components/GapCoverageGrid.tsx"
  modified:
    - "frontend/src/features/broker/components/tabs/CoverageTab.tsx"
    - "frontend/src/shared/grid/cell-renderers/ClauseLink.tsx"
decisions:
  - "Used union type GridRow = ProjectCoverage | SectionHeaderRow with isSectionHeader() type guard — avoids unsafe casts throughout the component"
  - "domLayout=normal (not autoHeight) to prevent re-render storms as documented in plan"
  - "Dynamic height capped at 600px via Math.min(rowData.length * 44 + 36, 600)"
  - "ClauseLink color updated from blue (#3B82F6) to coral (#E94D35) per brand accent spec"
  - "Removed useCoverageMutation from CoverageTab (grid is read-only; old editable columns removed)"
metrics:
  duration: "~20 minutes"
  completed: "2026-04-15"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 136 Plan 02: GapCoverageGrid ag-grid with section headers, row coloring, and urgency banner

**One-liner:** ag-grid coverage table with fullWidthRow Insurance/Surety headers, red/amber gap row tinting, GapAmountCell with gap_amount??required_limit fallback, and urgency banner when project starts within 30 days.

## Tasks Completed

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | GapCoverageGrid ag-grid component | Done | 7a7919e |
| 2 | CoverageTab urgency banner + grid integration | Done | 7a7919e |

## What Was Built

### GapCoverageGrid.tsx (new, 221 lines)
- `GridRow = ProjectCoverage | SectionHeaderRow` union type with `isSectionHeader()` type guard
- `rowData` built via `useMemo`: Insurance section header → insurance rows → Surety section header → surety rows
- `isFullWidthRow` + `fullWidthCellRenderer={SectionHeaderRenderer}` for Community-compatible section header rows
- 6 columns: Coverage (valueGetter skips section-header), Required Limit (CurrencyCell), Current Limit (CurrencyCell), Gap Amount (inline GapAmountCell in red for missing/insufficient), Contract Clause (ClauseLink in coral), Status (inline GapStatusCell badge)
- `getRowStyle`: section-header → gray bg, missing → `rgba(239,68,68,0.06)`, insufficient → `rgba(245,158,11,0.06)`
- `GapAmountCell`: uses `gap_amount ?? required_limit` for missing; `gap_amount ?? (required_limit - current_limit)` for insufficient
- Dynamic height `Math.min(rowData.length * 44 + 36, 600)`, `domLayout="normal"`

### CoverageTab.tsx (updated)
- Replaced dual AgGridReact Insurance/Surety grid sections with single `<GapCoverageGrid coverages={coverages} />`
- Added urgency banner: `daysUntilStart = Math.ceil((start_date - now) / 86400000)`, shows when `<= 30`
- Banner uses coral-tinted background with `AlertTriangle` icon; copy adapts for past-start and future-start dates
- Removed old `columnDefs`, `ConfidenceDot`, `onCellValueChanged`, `insuranceCoverages`/`suretyCoverages` memos
- Kept `useApproveProject` and "Approve Project" button

### ClauseLink.tsx (updated)
- Color changed from `#3B82F6` (blue) to `#E94D35` (coral) per brand accent

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Brand Alignment] Updated ClauseLink to coral**
- **Found during:** Task 1 implementation
- **Issue:** ClauseLink used `#3B82F6` (blue) but must_haves.truths required "coral ClauseLink" per brand accent
- **Fix:** Changed color from `#3B82F6` to `#E94D35` in `ClauseLink.tsx`
- **Files modified:** `frontend/src/shared/grid/cell-renderers/ClauseLink.tsx`
- **Commit:** 7a7919e

### TypeScript Fixes Applied

- `getRowStyle` return type required `border: 'none' as const` to satisfy ag-grid's `RowStyle` index signature (no `undefined` values)
- `isFullWidthRow` cast `params.rowNode.data as SectionHeaderRow | undefined` to access `._type` safely
- Union type `GridRow` with `isSectionHeader()` guard used throughout to avoid `as any` casts

## Self-Check

- [x] `frontend/src/features/broker/components/GapCoverageGrid.tsx` — created, 221 lines
- [x] `frontend/src/features/broker/components/tabs/CoverageTab.tsx` — updated with GapCoverageGrid + urgency banner
- [x] `frontend/src/shared/grid/cell-renderers/ClauseLink.tsx` — coral color
- [x] Commit 7a7919e exists
- [x] `npx tsc --noEmit` — zero errors
- [x] min_lines: 100 — satisfied (221 lines)
- [x] key_links: GapCoverageGrid imported in CoverageTab, CurrencyCell+ClauseLink imported in GapCoverageGrid

## Self-Check: PASSED
