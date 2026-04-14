# Technology Stack

**Project:** Broker Frontend MVP
**Researched:** 2026-04-14
**Overall confidence:** HIGH

## Verdict: No New Dependencies Needed

The existing stack covers every requirement for the broker frontend MVP. No new npm packages. No new Python packages. This is a pure build-out using what is already installed and proven in the codebase.

---

## Existing Stack (Confirmed Installed and Used)

### Core Framework (No Changes)
| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| React | ^19.0.0 | UI framework | Installed, used everywhere |
| Vite | ^6.0.0 | Build tool | Installed |
| TypeScript | ^5.5.0 | Type safety | Installed |
| Tailwind CSS | ^4.0.0 | Styling | Installed, all components use it |
| react-router | ^7.13.1 | Routing + URL params | Installed, `useSearchParams` already used in PipelinePage |

### Data Layer (No Changes)
| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| @tanstack/react-query | ^5.91.2 | Server state | Installed, all broker hooks use it |
| zustand | ^5.0.12 | Client state | Installed, used for app state |

### Grid (No Changes)
| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| ag-grid-community | ^35.2.0 | Data grids | Installed, PipelinePage + LeadsPage use it |
| ag-grid-react | ^35.2.0 | React wrapper | Installed |

### UI Components (No Changes)
| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| shadcn/ui | ^4.1.0 | Component primitives | 27 components installed: badge, button, dialog, tabs, tooltip, skeleton, etc. |
| lucide-react | ^0.577.0 | Icons | Installed |
| sonner | ^2.0.7 | Toast notifications | Installed |
| date-fns | ^4.1.0 | Date formatting | Installed, used in DateCell renderer |
| clsx + tailwind-merge | latest | Class merging | Installed |

### Backend (No Changes)
| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| FastAPI | existing | API server | StreamingResponse pattern already used in documents.py and tenant.py |
| openpyxl | system-wide | Excel generation | Installed, spec calls for .xlsx export |

---

## Feature-to-Stack Mapping

Every broker frontend feature maps to existing dependencies:

### 1. Shared ag-grid Toolkit Extraction
**Stack:** ag-grid-community ^35.2.0 (themeQuartz), existing cell renderers
**What exists:** `pipelineTheme` in PipelinePage.tsx (lines 34-47), 11 cell renderers in `features/pipeline/components/cell-renderers/`, column state persistence in usePipelineColumns.
**What to do:** Extract to `lib/grid-theme.ts` and `components/grid/cell-renderers/`. Pure refactor, no new deps.
**Confidence:** HIGH -- code is right there, just needs to move.

### 2. Comparison Matrix (Custom Table)
**Stack:** Native HTML `<table>` + Tailwind CSS `sticky` classes
**Why NOT ag-grid:** Spec explicitly calls this out (section 2.5). Two-row cells, cross-row color analysis, carrier checkboxes in headers, sticky columns/rows -- all fight ag-grid's cell model. The existing `ComparisonMatrix.tsx` already uses a plain `<table>`. The new version extends it with `position: sticky` (already used in 7 other files in the codebase including ThreadList, BriefingPage, RelationshipTable).
**What to do:** Build with `<table>` + Tailwind. CSS `sticky` is well-supported. No library needed.
**Confidence:** HIGH -- standard CSS pattern already proven in this codebase.

### 3. Tab Routing with URL Query Params
**Stack:** react-router ^7.13.1 `useSearchParams`
**What exists:** PipelinePage already uses `useSearchParams` for view state. The pattern is proven.
**What to do:** `?tab=overview|coverage|carriers|quotes|compare` using same pattern. No new deps.
**Confidence:** HIGH -- exact same pattern as PipelinePage.

### 4. Step Indicator Component
**Stack:** Tailwind CSS + lucide-react icons
**What to do:** Custom component with colored dots and connecting lines. Pure CSS + existing icon library. No stepper library needed -- the spec is simple (5 fixed steps, 3 color states).
**Confidence:** HIGH -- trivial UI component, ~50 lines.

### 5. Critical Exclusion Alert UI
**Stack:** Tailwind CSS (existing alert patterns)
**What exists:** ComparisonMatrix.tsx already renders yellow alert boxes (lines 144-159). The new CriticalExclusionAlert is the same pattern with red styling and richer content.
**What to do:** Build as a standalone component. Uses AlertTriangle from lucide-react (already imported in ComparisonMatrix).
**Confidence:** HIGH -- extending existing pattern.

### 6. Excel Export from Frontend
**Stack:** Browser `fetch` + `Blob` + `URL.createObjectURL`
**Backend:** FastAPI `StreamingResponse` (already used in documents.py line 638+ and tenant.py line 650 for file downloads)
**What to do:** Frontend triggers POST, receives binary .xlsx, creates download link via standard browser API. Backend uses openpyxl (system-wide) to generate the formatted workbook with two sheets, color fills, and merged cells.
**Confidence:** HIGH -- StreamingResponse download pattern already exists twice in the codebase.

### 7. Dashboard Task List
**Stack:** React components + React Query
**What to do:** Fetch from new endpoint, render as card list. Uses existing Badge, Button from shadcn/ui.
**Confidence:** HIGH -- standard data fetching + rendering.

### 8. Gate Strip (Persistent Banner)
**Stack:** React component + React Query with 30s polling
**What exists:** React Query `refetchInterval` option is the standard pattern.
**What to do:** Small component that polls gate-counts endpoint. Renders above page content via layout wrapper.
**Confidence:** HIGH -- trivial component.

### 9. Coverage Grid with Inline Editing
**Stack:** ag-grid-community ^35.2.0 (editable cells are a community feature)
**What exists:** ag-grid `editable: true` on column defs is a community feature. DatePickerEditor already exists in pipeline cell-renderers.
**What to do:** Set `editable: true` on coverage_type and required_limit columns. Use `onCellValueChanged` to trigger mutation. No enterprise features needed.
**Confidence:** HIGH -- ag-grid community supports inline editing.

---

## Alternatives Considered and Rejected

| Feature | Considered | Why Rejected |
|---------|-----------|--------------|
| Comparison matrix | ag-grid-enterprise (pivot, grouping) | License cost ($900+/dev), overkill for 5-10 columns. Custom table matches spec exactly. ag-grid community doesn't support the two-row cell layout needed. |
| Comparison matrix | @tanstack/react-table | Adds dependency for something a plain `<table>` handles. Matrix is max ~20 rows x 10 columns -- not a performance concern. |
| Step indicator | react-step-progress-bar, @mui/stepper | External dependency for ~50 lines of Tailwind CSS. Step indicator has exactly 5 fixed steps with 3 color states. No dynamic step generation needed. |
| Excel export | SheetJS (xlsx) client-side | Backend already has openpyxl + StreamingResponse. Server-side gives better formatting control (cell fills, borders, merged cells for two-row layout). Client-side adds 500KB+ dependency for no benefit. |
| Excel export | FileSaver.js | Browser native `Blob` + `URL.createObjectURL` + `a.click()` does the same thing in 5 lines. No dependency needed. |
| Tab component | @radix-ui/react-tabs standalone | shadcn/ui tabs.tsx is already installed (wraps Radix under the hood). Already in the project at `components/ui/tabs.tsx`. |
| Virtualized comparison | @tanstack/react-virtual | Matrix is max ~20 rows x 10 columns. Virtualization adds complexity for zero performance benefit. react-virtual is installed but only used in email ThreadList for 1000+ item lists. |
| Form library | react-hook-form, formik | Existing codebase uses controlled components + React Query mutations. Adding a form library just for broker breaks consistency. Inline ag-grid editing doesn't use form libraries anyway. |

---

## What NOT to Add

| Package | Why Not |
|---------|---------|
| Any charting library | No charts in broker MVP spec |
| Any drag-and-drop library | No DnD in broker MVP spec |
| Any rich text editor | Solicitation emails use plain textarea (existing EmailApproval.tsx) |
| Any PDF viewer | PDFs download via existing document endpoint |
| Any form library | Existing controlled component pattern is consistent across codebase |
| Any animation library | Existing tw-animate-css covers transitions |
| ag-grid-enterprise | License cost, none of the enterprise features (row grouping, pivot, etc.) are needed. Inline editing is a community feature. |
| Any CSS-in-JS library | Tailwind handles everything including sticky positioning |

---

## Installation

```bash
# Nothing to install. All dependencies are already in package.json and pyproject.toml.
# Zero new npm packages.
# Zero new Python packages.
```

---

## Key Integration Points

### ag-grid Shared Toolkit (Extract, Don't Add)

The pipeline module has everything broker needs. Extract these to shared locations:

| Current Location | Target Location | What |
|-----------------|----------------|------|
| `PipelinePage.tsx` lines 34-47 | `lib/grid-theme.ts` | `flywheelGridTheme` (rename from `pipelineTheme`) |
| `pipeline/components/cell-renderers/DateCell.tsx` | `components/grid/cell-renderers/DateCell.tsx` | Generic date renderer (uses date-fns) |
| `pipeline/components/cell-renderers/ExpandToggleCell.tsx` | `components/grid/cell-renderers/ExpandToggleCell.tsx` | Chevron toggle |
| `pipeline/components/cell-renderers/DatePickerEditor.tsx` | `components/grid/cell-renderers/DatePickerEditor.tsx` | Inline date editor |
| `usePipelineColumns.ts` column state logic | `hooks/useGridColumnState.ts` | localStorage persistence |

Pipeline-specific renderers (ContactCell, ChannelsCell, NextStepCell, etc.) stay in `features/pipeline/`.

### Excel Export Backend Pattern

Follow the existing StreamingResponse pattern from `documents.py`:

```python
# Already used in backend -- same pattern for Excel export
from fastapi.responses import StreamingResponse
from io import BytesIO
import openpyxl

# Build workbook, write to BytesIO, return as StreamingResponse
# Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

### Frontend File Download Pattern

Standard browser download -- no library needed:

```typescript
const response = await fetch(`/api/v1/broker/projects/${id}/export-comparison`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ carrier_ids: selectedIds }),
})
const blob = await response.blob()
const url = URL.createObjectURL(blob)
const a = document.createElement('a')
a.href = url
a.download = `comparison-${projectName}-${date}.xlsx`
a.click()
URL.revokeObjectURL(url)
```

---

## Sources

- `frontend/package.json` -- direct inspection of all installed dependencies (HIGH confidence)
- `PipelinePage.tsx` lines 1-50 -- ag-grid theme config, useSearchParams usage, AllCommunityModule import (HIGH confidence)
- `ComparisonMatrix.tsx` -- existing plain HTML table pattern for quote comparison (HIGH confidence)
- `backend/src/flywheel/api/documents.py` lines 638-690 -- StreamingResponse file download pattern (HIGH confidence)
- `backend/src/flywheel/api/tenant.py` line 650 -- additional StreamingResponse usage (HIGH confidence)
- `features/pipeline/components/cell-renderers/` -- 11 existing cell renderers, 4 generic enough to extract (HIGH confidence)
- `components/ui/` directory -- 27 shadcn/ui components installed including tabs.tsx (HIGH confidence)
- 7 frontend files using CSS `sticky` positioning -- confirms pattern is established (HIGH confidence)
- ag-grid community docs -- inline cell editing is a community (free) feature (HIGH confidence)
