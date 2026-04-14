# Architecture Patterns: Broker Frontend MVP

**Domain:** Insurance broker workflow management (on existing React + Vite + Tailwind v4 app)
**Researched:** 2026-04-14
**Confidence:** HIGH (all recommendations derived from reading the actual codebase)

---

## 1. Shared Module Toolkit Extraction

### Problem

ag-grid infrastructure is currently embedded in `features/pipeline/`: the theme config, 13 cell renderers, column state persistence hooks, and grid-related utilities. The broker module needs grids (projects table, carriers table) but must not import from `features/pipeline/` -- that creates a coupling where broker depends on GTM code.

### Recommended Architecture

Create `src/shared/grid/` as the extraction target. This is a new top-level directory alongside `src/lib/` and `src/components/`.

```
src/
  shared/
    grid/
      theme.ts                    # pipelineTheme extracted + renamed to flywheelGridTheme
      hooks/
        useColumnPersistence.ts   # generic version of usePipelineColumns' persist logic
      cell-renderers/
        DateCell.tsx              # generic -- used by both pipeline and broker
        StatusPill.tsx            # generic pill renderer (parameterized colors)
        ExpandToggleCell.tsx      # generic expand/collapse
        CurrencyCell.tsx          # NEW -- broker needs currency formatting
      index.ts                   # barrel export
```

### Extraction Order (safe sequence)

This order ensures GTM never breaks at any intermediate step:

**Step 1: Copy theme to shared, re-export from pipeline.**
- Copy `pipelineTheme` from `PipelinePage.tsx` lines 34-47 into `src/shared/grid/theme.ts` as `flywheelGridTheme`.
- In `PipelinePage.tsx`, replace the inline theme with `import { flywheelGridTheme } from '@/shared/grid/theme'`.
- GTM works identically. Zero behavior change.

**Step 2: Extract generic cell renderers.**
- Copy `DateCell.tsx`, `ExpandToggleCell.tsx` to `src/shared/grid/cell-renderers/`.
- These two are fully generic (no pipeline-specific types in their interfaces).
- Update pipeline imports to point to `@/shared/grid/cell-renderers/DateCell`.
- Remove originals from pipeline.
- `StatusPill.tsx` is NEW -- a parameterized version that accepts `colorMap` prop, unlike `StagePill.tsx` which hardcodes pipeline stages.

**Step 3: Extract column persistence hook.**
- The pattern in `usePipelineColumns.ts` (lines 132-159) is: read from localStorage, apply on grid ready, save on column change.
- Extract to `useColumnPersistence(storageKey: string)` that returns `{ restoreColumnState, onColumnStateChanged, gridApiRef }`.
- `usePipelineColumns` becomes a thin wrapper: calls `useColumnPersistence('pipeline-col-state')` + defines pipeline-specific `columnDefs`.

**Step 4: Broker uses shared.**
- Broker grids import from `@/shared/grid/` directly.
- Broker defines its own column defs in `features/broker/hooks/useProjectColumns.ts`.

### What stays in pipeline (do NOT extract)

These are pipeline-domain-specific and should NOT move to shared:
- `NameCell.tsx` (renders company name + domain icon -- GTM concept)
- `ContactCell.tsx` (renders contact avatar + name -- GTM concept)
- `StagePill.tsx` (hardcoded pipeline stages)
- `FitTierBadge.tsx` (hardcoded fit tiers)
- `ChannelsCell.tsx`, `ChannelIconsCell.tsx` (GTM channel concept)
- `AiInsightCell.tsx` (pipeline AI summary)
- `OutreachStatusCell.tsx` (GTM outreach concept)
- `ContactStatusPill.tsx` (GTM contact statuses)
- `DatePickerEditor.tsx` (inline editing -- broker doesn't need inline grid editing in MVP)

### GTM Non-Breakage Contract

The extraction is safe because:
1. **Copy-first**: shared versions are copies, not moves. Pipeline imports update after verification.
2. **No interface changes**: `flywheelGridTheme` is identical to `pipelineTheme` (same params object).
3. **Barrel exports**: `@/shared/grid` barrel means pipeline can switch imports in one line per file.
4. **Feature flag isolation**: broker code is gated by `useFeatureFlag('broker')` and `BrokerGuard`. Even if shared code has a bug, GTM-only tenants never render broker components.

---

## 2. Comparison Matrix Architecture

### Why NOT ag-grid for the Comparison Matrix

The spec requires:
- Two-row cells (premium top, limit+deductible bottom)
- Sticky first column (coverage names) during horizontal scroll
- Sticky header row during vertical scroll
- Sticky total premium row at bottom
- Conditional cell backgrounds (red/amber/green/blue)
- Carrier selection checkboxes in column headers
- "Show differences only" toggle that hides rows
- Insurance/surety tabs with different column counts

ag-grid CAN do all of this, but the cost is high:
- Two-row cells require custom `cellRenderer` with forced row height -- already done in the existing `ComparisonMatrix.tsx` but as a plain table.
- Sticky rows/columns in ag-grid require Enterprise license (`pinnedBottomRowData` is Community, but combined with sticky headers and custom cell backgrounds creates complexity).
- The matrix is read-only (no editing, no sorting, no column reorder) -- ag-grid's value-add is in interactive grids.
- The existing `ComparisonMatrix.tsx` (188 lines) already renders the correct structure as a plain HTML table.

**Recommendation: Enhance the existing HTML table approach.** Use CSS `position: sticky` for frozen column/row behavior. This is simpler, lighter, and matches the spec better.

### Component Architecture

```
features/broker/components/comparison/
  ComparisonView.tsx          # Orchestrator: tabs + alerts + export button + toggles
  ComparisonMatrix.tsx        # Single matrix (receives coverages + carriers for one tab)
  ComparisonCell.tsx          # Two-row cell with conditional styling
  CriticalAlertBox.tsx        # Alert box above tabs
  ComparisonToolbar.tsx       # Export button + highlight toggle + differences toggle
  useComparisonState.ts       # Toggle state, carrier selection, filtered rows
```

### Sticky Column/Row Implementation

```css
/* First column sticky */
.comparison-matrix td:first-child,
.comparison-matrix th:first-child {
  position: sticky;
  left: 0;
  z-index: 2;
  background: inherit; /* prevent transparency on scroll */
}

/* Header row sticky */
.comparison-matrix thead th {
  position: sticky;
  top: 0;
  z-index: 3; /* above sticky column */
}

/* Corner cell (first-col + header) needs highest z-index */
.comparison-matrix thead th:first-child {
  z-index: 4;
}

/* Total premium row sticky at bottom */
.comparison-matrix tfoot td {
  position: sticky;
  bottom: 0;
  z-index: 2;
}
```

The matrix container needs `overflow: auto; max-height: calc(100dvh - 280px);` to enable both scrolls.

### Two-Row Cell Component

```typescript
interface ComparisonCellProps {
  premium: number | null
  limit: number | null
  deductible: number | null
  status: 'normal' | 'excluded' | 'insufficient' | 'best_price' | 'best_coverage' | 'critical'
  highlightBest: boolean  // controlled by toggle
  currency: string
}

function ComparisonCell({ premium, limit, deductible, status, highlightBest, currency }: ComparisonCellProps) {
  // Status drives background color (always visible)
  // highlightBest drives text color (only when toggle is on)
  const bg = {
    normal: 'bg-white',
    excluded: 'bg-red-50',
    insufficient: 'bg-amber-50',
    critical: 'bg-red-50 border-l-4 border-red-500',
    best_price: highlightBest ? 'bg-white' : 'bg-white',  // text color, not bg
    best_coverage: highlightBest ? 'bg-white' : 'bg-white',
  }[status]

  if (status === 'excluded') {
    return <td className={bg}><span className="text-red-600 font-bold text-sm">EXCLUDED</span></td>
  }

  return (
    <td className={`px-3 py-2 min-w-[140px] ${bg}`}>
      <div className="text-sm font-semibold">{formatCurrency(premium, currency)}</div>
      <div className="text-xs text-muted-foreground">
        Limit: {formatCurrency(limit, currency)} . Ded: {formatCurrency(deductible, currency)}
      </div>
    </td>
  )
}
```

### Data Flow

The existing `useComparison(projectId)` hook (in `useBrokerQuotes.ts`) already fetches `/broker/projects/:id/comparison` and returns `ComparisonMatrix` type with `coverages[]` containing `quotes[]` per coverage. The data structure already supports the matrix layout.

For the insurance/surety split: filter `coverages` by `category` field. The backend already populates `category` as `'insurance'` or `'surety'` on each `ComparisonCoverage`.

---

## 3. Persistent Gate Strip

### Problem

The gate strip ("Review: 3 | Approve: 1 | Export: 2") must appear on EVERY broker route, above the main content. It needs its own data fetch (gate counts from a dashboard endpoint) and must not re-mount or flicker on route transitions.

### Recommended Pattern: Layout-Level Component

Place the gate strip in the layout layer, not in individual pages. The app already has a layout architecture:

```
AppLayout
  -> AppShell
       -> AppSidebar (persistent)
       -> SidebarInset
            -> main
                 -> GateStrip (NEW -- persistent for broker)
                 -> AppRoutes (page content)
       -> AuthenticatedAlerts (persistent)
```

### Implementation

**Option A (Recommended): Conditional wrapper inside AppShell.**

In `layout.tsx`, add the gate strip inside the `SidebarInset > main` block, gated on the broker feature flag:

```typescript
// In AppShell's desktop return:
<SidebarInset>
  <main className="flex-1 overflow-auto">
    <BrokerGateStrip />  {/* renders null if not broker tenant */}
    <AppRoutes />
  </main>
</SidebarInset>
```

`BrokerGateStrip` internally checks `useFeatureFlag('broker')` and returns `null` for GTM tenants. This means:
- Zero impact on GTM (component renders nothing).
- No route-level coordination needed.
- Single data fetch shared across all broker pages.

**Option B (Rejected): Per-page import.** Each broker page would import `<GateStrip />`. This causes:
- Repeated code in 4+ pages.
- Component unmounts/remounts on navigation (flash of loading).
- Data refetch on every route change.

### GateStrip Component

```
features/broker/components/GateStrip.tsx
```

```typescript
function BrokerGateStrip() {
  const brokerEnabled = useFeatureFlag('broker')
  if (!brokerEnabled) return null

  const { data: gateCounts } = useGateCounts()  // NEW hook
  // Renders: Review: N | Approve: N | Export: N
  // Each count is a link to /broker/projects?gate=review (filtered)
  // Uses React Query with staleTime: 60_000 (refresh every minute)
}
```

### Navigation Behavior

Each gate count links to `/broker/projects?gate=review` (or `approve` or `export`). The projects page reads the `gate` query param and pre-filters to show only projects at that gate. This avoids a "jump to oldest" behavior that could be confusing -- instead, the broker sees all pending items for that gate.

### New Backend Endpoint

```
GET /broker/gate-counts -> { review: number, approve: number, export: number }
```

This is a lightweight aggregation query. It runs a COUNT on `broker_projects` grouped by status buckets:
- review: status IN ('analyzing', 'gaps_identified') AND approval_status = 'draft'
- approve: status IN ('gaps_identified') AND approval_status = 'approved' (carriers matched, no solicitations sent)
- export: status IN ('quotes_partial', 'quotes_complete')

### New Hook

```typescript
// features/broker/hooks/useGateCounts.ts
export function useGateCounts() {
  return useQuery({
    queryKey: ['broker', 'gate-counts'],
    queryFn: () => api.get<GateCounts>('/broker/gate-counts'),
    staleTime: 60_000,  // 1 minute -- not real-time, but frequent enough
    refetchInterval: 60_000,  // auto-refresh while tab is active
  })
}
```

---

## 4. Tab Routing with URL State

### Problem

The project detail page (`/broker/projects/:id`) needs tabs (Overview, Coverage, Carriers, Quotes, Compare). The active tab must be reflected in the URL so that:
- Deep links work (gate strip links to `/broker/projects/123?tab=compare`)
- Browser back/forward works
- Refreshing preserves tab state

### Recommended Pattern: `?tab=` Query Parameter

This is the same pattern already used successfully in `PipelinePage.tsx` for URL-synced state (lines 50-192). Use `useSearchParams` from react-router-dom.

### Why NOT path-based routing (`/broker/projects/:id/coverage`)

- The project detail is a single page with a sidebar (right 1/3) that stays constant across tabs. Path-based routing would require either a layout route or repeated sidebar rendering.
- The existing `BrokerProjectDetail.tsx` already has the 2/3 + 1/3 layout. Tabs are content within the 2/3 section.
- `?tab=` is simpler and matches the existing PipelinePage URL-sync pattern.

### Implementation

```typescript
// In BrokerProjectDetail.tsx
const [searchParams, setSearchParams] = useSearchParams()
const activeTab = (searchParams.get('tab') as TabName) ?? 'overview'

const handleTabChange = (tab: TabName) => {
  setSearchParams(prev => {
    const next = new URLSearchParams(prev)
    if (tab === 'overview') next.delete('tab')  // default doesn't need param
    else next.set('tab', tab)
    return next
  }, { replace: true })  // replace: true so tab changes don't pollute history
}
```

### Tab Definitions

```typescript
type TabName = 'overview' | 'coverage' | 'carriers' | 'quotes' | 'compare'

const TABS: { value: TabName; label: string; gateLabel?: string }[] = [
  { value: 'overview', label: 'Overview' },
  { value: 'coverage', label: 'Coverage', gateLabel: 'Gate 1' },
  { value: 'carriers', label: 'Carriers', gateLabel: 'Gate 2' },
  { value: 'quotes', label: 'Quotes' },
  { value: 'compare', label: 'Compare', gateLabel: 'Gate 3' },
]
```

### Rendering with Base UI Tabs

The existing `tabs.tsx` component wraps `@base-ui/react/tabs`. Use it with controlled value:

```typescript
<Tabs value={activeTab} onValueChange={handleTabChange}>
  <TabsList variant="line">
    {TABS.map(tab => (
      <TabsTrigger key={tab.value} value={tab.value}>
        {tab.label}
        {tab.gateLabel && <Badge variant="outline" className="ml-1 text-[10px]">{tab.gateLabel}</Badge>}
      </TabsTrigger>
    ))}
  </TabsList>
  <TabsContent value="overview"><OverviewTab project={project} /></TabsContent>
  <TabsContent value="coverage"><CoverageTab project={project} /></TabsContent>
  <TabsContent value="carriers"><CarriersTab projectId={project.id} /></TabsContent>
  <TabsContent value="quotes"><QuotesTab projectId={project.id} /></TabsContent>
  <TabsContent value="compare"><CompareTab projectId={project.id} currency={project.currency} /></TabsContent>
</Tabs>
```

### Step Indicator

The step indicator sits above the tabs. It reads project status to determine which steps are complete:

```typescript
function StepIndicator({ project }: { project: BrokerProjectDetail }) {
  const steps = [
    { label: 'Extract', done: project.analysis_status === 'completed' },
    { label: 'Review', done: project.approval_status === 'approved' },
    { label: 'Solicit', done: ['soliciting','quotes_partial','quotes_complete','bound'].includes(project.status) },
    { label: 'Compare', done: ['quotes_complete','recommended','delivered','bound'].includes(project.status) },
    { label: 'Deliver', done: ['delivered','bound'].includes(project.status) },
  ]
  // Render horizontal dots + labels with grey/amber/green states
}
```

---

## 5. Excel Export Architecture

### Backend Streaming vs In-Memory

**Recommendation: Backend in-memory generation with streaming response.**

The comparison matrix for 50 coverage lines x 10 carriers is ~500 cells. Even with formatting, the .xlsx will be < 500KB. In-memory generation with `openpyxl` is appropriate.

Use a streaming response (`StreamingResponse` in FastAPI) to avoid holding the full file in memory during transfer, but the generation itself is in-memory.

```python
# Backend endpoint
@router.get("/broker/projects/{project_id}/export-comparison")
async def export_comparison(project_id: str, ...):
    wb = build_comparison_workbook(project_id)  # openpyxl Workbook
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=comparison-{project_id[:8]}.xlsx"}
    )
```

### Frontend Download Trigger

```typescript
// features/broker/hooks/useExportComparison.ts
export function useExportComparison(projectId: string) {
  const { mutate, isPending } = useMutation({
    mutationFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(`/api/v1/broker/projects/${projectId}/export-comparison`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('Export failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `comparison-${projectId.slice(0, 8)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    },
  })
  return { exportComparison: mutate, isExporting: isPending }
}
```

This bypasses the normal `api.get()` helper because it needs to handle a binary blob response, not JSON.

---

## 6. New Backend Endpoint Wiring

### Existing Pattern

All broker API calls go through `features/broker/api.ts` which uses the shared `api` helper from `@/lib/api`. Each function is a thin wrapper: `api.get<ResponseType>('/broker/endpoint')`. Hooks in `features/broker/hooks/` wrap these with React Query.

### New Endpoints to Wire

| Endpoint | API Function | Hook | Used By |
|----------|-------------|------|---------|
| `GET /broker/gate-counts` | `fetchGateCounts()` | `useGateCounts()` | GateStrip |
| `GET /broker/dashboard-tasks` | `fetchDashboardTasks()` | `useDashboardTasks()` | BrokerDashboard |
| `GET /broker/projects/:id/export-comparison` | raw fetch (blob) | `useExportComparison()` | ComparisonView |
| `POST /broker/projects/:id/approve` | `approveProject()` | `useApproveProject()` | CoverageTab |

### Wiring Pattern (consistent with existing code)

1. Add type to `features/broker/types/broker.ts`
2. Add API function to `features/broker/api.ts`
3. Add hook to `features/broker/hooks/`
4. Import hook in component

No new patterns needed -- follow the exact same structure as the existing 15 broker hooks.

---

## 7. Component Boundaries

### New Components

| Component | Location | Responsibility | Data Source |
|-----------|----------|----------------|-------------|
| `BrokerGateStrip` | `features/broker/components/GateStrip.tsx` | Persistent gate counts bar | `useGateCounts()` |
| `ComparisonView` | `features/broker/components/comparison/ComparisonView.tsx` | Orchestrates tabs + alerts + toolbar | `useComparison()` |
| `ComparisonMatrix` | `features/broker/components/comparison/ComparisonMatrix.tsx` | Single coverage-vs-carrier table | Props from parent |
| `ComparisonCell` | `features/broker/components/comparison/ComparisonCell.tsx` | Two-row cell with conditional bg | Props |
| `CriticalAlertBox` | `features/broker/components/comparison/CriticalAlertBox.tsx` | Exclusion warnings | Props |
| `ComparisonToolbar` | `features/broker/components/comparison/ComparisonToolbar.tsx` | Export + toggles | Props + `useExportComparison()` |
| `StepIndicator` | `features/broker/components/StepIndicator.tsx` | Horizontal progress dots | Props (project status) |
| `OverviewTab` | `features/broker/components/tabs/OverviewTab.tsx` | Client info + docs + activity | Props (project) |
| `CoverageTab` | `features/broker/components/tabs/CoverageTab.tsx` | Coverage table + gaps + approve | Props + mutations |
| `CarriersTab` | `features/broker/components/tabs/CarriersTab.tsx` | Carrier matches + solicitations | Hooks |
| `QuotesTab` | `features/broker/components/tabs/QuotesTab.tsx` | Quote tracking per carrier | Hooks |
| `CompareTab` | `features/broker/components/tabs/CompareTab.tsx` | Wraps ComparisonView | Hooks |
| `DashboardTaskList` | `features/broker/components/DashboardTaskList.tsx` | Prioritized action items | `useDashboardTasks()` |
| `ProjectsTable` | `features/broker/components/ProjectsTable.tsx` | Full projects list with filters | `useBrokerProjects()` |

### Modified Components

| Component | Change | Risk |
|-----------|--------|------|
| `layout.tsx` | Add `<BrokerGateStrip />` inside `<main>` | LOW -- renders null for GTM |
| `BrokerProjectDetail.tsx` | Rewrite from single-page to tabbed layout | MEDIUM -- existing component replaced |
| `BrokerDashboard.tsx` | Redesign from KPI cards to task list + table | MEDIUM -- existing component replaced |
| `ComparisonMatrix.tsx` | Move to `comparison/` subfolder, enhance | MEDIUM -- substantial enhancement |
| `PipelinePage.tsx` | Update ag-grid theme import to shared | LOW -- import path change only |
| `usePipelineColumns.ts` | Extract persistence to shared hook | LOW -- behavior identical |

---

## 8. Data Flow Diagram

```
                    +--------------------------------------------------+
                    |                   AppShell                        |
                    |  +-----------------------------------------------+
                    |  | BrokerGateStrip (useGateCounts)                |
                    |  |   Review: 3  |  Approve: 1  |  Export: 2      |
                    |  +-----------------------------------------------+
                    |  +-----------------------------------------------+
                    |  | AppRoutes -> /broker/projects/:id              |
                    |  |  +------------------------------------------+ |
                    |  |  | BrokerProjectDetail                      | |
                    |  |  |  +-----------+ +------------------+      | |
                    |  |  |  | StepBar   | |  Sidebar (1/3)   |      | |
                    |  |  |  +-----------+ |  Project Info     |      | |
                    |  |  |  | Tab Bar   | |  Activity Log     |      | |
                    |  |  |  | ?tab=X    | |                   |      | |
                    |  |  |  +-----------+ |                   |      | |
                    |  |  |  | Tab Panel | |                   |      | |
                    |  |  |  | (2/3)     | |                   |      | |
                    |  |  |  +-----------+ +------------------+      | |
                    |  |  +------------------------------------------+ |
                    |  +-----------------------------------------------+
                    +--------------------------------------------------+
```

---

## 9. Recommended Build Order

Build order is driven by two constraints: (a) dependency chains and (b) GTM safety.

| Order | What | Why This Order | Depends On |
|-------|------|----------------|------------|
| 1 | Shared grid toolkit extraction | Foundation for all grids; validates GTM does not break | Nothing |
| 2 | Gate strip + `useGateCounts` hook | Layout-level change that touches `layout.tsx` -- do early before other changes accumulate | Backend endpoint |
| 3 | Tab routing in `BrokerProjectDetail` | Structural change that all tab content hangs off of | Nothing |
| 4 | Tab content: Coverage, Carriers, Quotes (repackage existing components) | Move existing components into tab structure | Step 3 |
| 5 | Dashboard redesign (task list + table) | New data source, but self-contained | Backend endpoint |
| 6 | Comparison matrix enhancement (sticky, two-row, tabs, toggles) | Most complex component; build last with stable foundation | Step 3 (tab routing) |
| 7 | Excel export | Simple once comparison data is available | Step 6 + backend endpoint |
| 8 | Projects list page | Table with filters -- uses shared grid toolkit | Step 1 |

### Parallelizable Work

Steps 2 + 3 can run in parallel (no dependency).
Steps 4 + 5 can run in parallel (no dependency).
Step 6 blocks on Step 3 but not on Steps 4 or 5.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Importing from `features/pipeline/` in broker code
**What:** Broker components importing cell renderers or hooks from pipeline feature.
**Why bad:** Creates cross-feature coupling. Changes to pipeline can break broker.
**Instead:** Extract to `shared/grid/` or duplicate if the component is small and diverging.

### Anti-Pattern 2: ag-grid for read-only display tables
**What:** Using ag-grid for the comparison matrix or simple list views.
**Why bad:** ag-grid adds bundle weight and complexity for tables that don't need editing, sorting, or column reorder. The comparison matrix needs sticky positioning that is simpler with CSS than ag-grid config.
**Instead:** Use HTML `<table>` with CSS sticky for comparison. Use ag-grid only for interactive data grids (projects table if it needs inline editing later).

### Anti-Pattern 3: Path-based tab routing for detail pages
**What:** `/broker/projects/:id/coverage`, `/broker/projects/:id/carriers`, etc.
**Why bad:** The sidebar (1/3 width) is shared across all tabs and contains its own data. Path routing forces either nested routes with a layout or repeated sidebar imports. It also creates unnecessary full-page transitions between tabs.
**Instead:** `?tab=coverage` query param with `replace: true` on `setSearchParams`.

### Anti-Pattern 4: Gate strip as a per-page component
**What:** Each broker page imports and renders `<GateStrip />`.
**Why bad:** Unmounts/remounts on navigation causing loading flash. Data refetches on every route change. Easy to forget in a new page.
**Instead:** Single instance in `layout.tsx` that reads feature flag and renders null for non-broker tenants.

---

## Sources

- Codebase analysis: `frontend/src/features/pipeline/` (ag-grid usage, theme, hooks)
- Codebase analysis: `frontend/src/features/broker/` (existing components, API, types)
- Codebase analysis: `frontend/src/app/layout.tsx` (AppShell architecture)
- Codebase analysis: `frontend/src/app/routes.tsx` (BrokerGuard, route structure)
- Codebase analysis: `frontend/src/lib/feature-flags.ts` (tenant feature flag system)
- Spec: `SPEC-BROKER-FRONTEND-MVP.md` (gate strip, comparison matrix, tab routing requirements)
- Confidence: HIGH -- all recommendations based on reading actual production code
