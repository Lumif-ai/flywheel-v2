# Phase 56: Pipeline Grid - Research

**Researched:** 2026-03-27
**Domain:** AG Grid React, Tailwind v4 CSS variable theming, design system tokens, frontend filter/sort patterns
**Confidence:** HIGH

## Summary

Phase 56 is a medium-complexity frontend phase. It has three independent vertical slices: design
system token expansion (Plan 01), AG Grid integration for the pipeline data grid (Plan 02), and
filter bar + saved views + graduation flow (Plan 03). The only genuinely new library is AG Grid
— everything else (React Query, Zustand, Tailwind v4, base-ui components) already exists and
follows established patterns in the codebase.

The most important technical discovery is the AG Grid theming approach. AG Grid v35 uses a
programmatic `themeQuartz.withParams()` API that injects CSS directly into the DOM. Critically,
color parameters accept `var(--css-variable)` syntax, which means AG Grid can reference the
app's existing Tailwind v4 CSS custom properties (`--card-bg`, `--brand-coral`, `--subtle-border`,
etc.) directly. No separate CSS file import needed — the Vite `@tailwindcss/vite` plugin does not
conflict with AG Grid's style injection because they target different mechanisms.

The second important discovery is the backend gap. The `GET /pipeline/` endpoint (`outreach.py`)
currently supports neither `fit_tier` nor `outreach_status` query params (the frontend sends them
but they are silently ignored), and `fit_score` has no database index despite the endpoint
ordering by it. Plan 03 depends on Plan 01 of this phase fixing those gaps, or it can add a
migration for the index and extend the endpoint as part of its own work.

**Primary recommendation:** Use `ag-grid-community` v35 (Community edition, MIT license). Theme it
via `themeQuartz.withParams()` referencing the app's existing CSS custom properties. Persist
column state in `localStorage` via the `onColumnStateChanged` grid event. Do NOT use Enterprise
edition — all required features (resize, reorder, visibility, custom cell renderers, pagination,
virtualization) are in Community.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ag-grid-community | ^35.2.0 | Data grid engine, column state, events | MIT license, all required features included; v35 has modern programmatic theme API |
| ag-grid-react | ^35.2.0 | React wrapper for AG Grid (`<AgGridReact>`) | Paired 1:1 with ag-grid-community; same version required |
| @tanstack/react-query | ^5.91.2 | Already installed; data fetching + cache invalidation | Existing pattern in all feature hooks |
| zustand | ^5.0.12 | Already installed; UI state if needed across components | Existing store pattern (ui.ts) |
| react-router | ^7.13.1 | Already installed; URL query params for saved view tabs | Existing routing pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | ^0.577.0 | Icons for column visibility toggle, filter chips | Already installed |
| sonner | ^2.0.7 | Toast notifications on graduation success/error | Already installed; used in useGraduate |
| class-variance-authority | ^0.7.1 | Badge variant system for translucent fit-tier badges | Already installed |
| tw-animate-css | ^1.4.0 | Row slide-out animation on graduation | Already installed; keyframe animations |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ag-grid-community | @tanstack/react-table | TanStack Table requires building all UI manually; AG Grid provides resize/reorder/column visibility out of the box — this is the right call for Airtable-style requirements |
| ag-grid-community | react-virtualized + custom table | Hand-rolling column resize + reorder + localStorage is exactly the "don't hand-roll" trap; AG Grid handles all of it |
| themeQuartz.withParams() | AG Grid CSS class overrides | withParams() is the current (v33+) API — class overrides are the legacy pre-v33 approach and will break in future versions |

**Installation:**
```bash
npm install ag-grid-community ag-grid-react
```

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
├── features/
│   └── pipeline/
│       ├── api.ts                    # extend fetchPipeline with fit_tier/outreach_status params
│       ├── components/
│       │   ├── PipelinePage.tsx      # replace HTML table with AgGridReact
│       │   ├── PipelineFilterBar.tsx # fit tier multi-select, outreach status, text search
│       │   ├── PipelineViewTabs.tsx  # All / Hot / Stale / Replied tabs
│       │   ├── GraduationModal.tsx   # type-selection dialog
│       │   └── cell-renderers/
│       │       ├── CompanyCell.tsx   # avatar + company name
│       │       ├── ContactCell.tsx   # contact name + title
│       │       ├── FitTierBadge.tsx  # translucent badge per tier
│       │       └── OutreachDot.tsx   # 8px status dot
│       ├── hooks/
│       │   ├── usePipeline.ts        # existing, extend params
│       │   ├── useGraduate.ts        # extend with types[] + invalidation
│       │   └── usePipelineColumns.ts # column defs, localStorage restore
│       └── types/
│           └── pipeline.ts           # extend PipelineItem with contact fields
├── components/ui/
│   ├── avatar.tsx                    # extend with 32px/48px size variant
│   ├── skeleton.tsx                  # add shimmer variant via animate-shimmer
│   └── empty-state.tsx              # NEW: EmptyState component
└── index.css                         # add card shadow tokens, status dot tokens
```

### Pattern 1: AG Grid Theme via CSS Custom Properties

**What:** `themeQuartz.withParams()` accepts `var(--css-variable)` expressions for color
parameters, allowing the grid to inherit from the app's existing Tailwind v4 design tokens.

**When to use:** Always — do not import separate AG Grid CSS files. Use the programmatic API.

```typescript
// Source: https://www.ag-grid.com/javascript-data-grid/theming-colors/
import { themeQuartz } from 'ag-grid-community'

export const pipelineTheme = themeQuartz.withParams({
  backgroundColor: 'var(--card-bg)',
  foregroundColor: 'var(--heading-text)',
  headerBackgroundColor: 'var(--card-bg)',
  headerTextColor: 'var(--secondary-text)',
  rowHoverColor: 'rgba(0,0,0,0.02)',
  accentColor: 'var(--brand-coral)',
  borderColor: 'var(--subtle-border)',
  fontSize: 14,
  rowHeight: 56,
  headerHeight: 40,
  fontFamily: 'var(--font-sans)',
})
```

### Pattern 2: Column State Persistence in localStorage

**What:** Save/restore column widths, order, and visibility using AG Grid's column state API.

**When to use:** In `usePipelineColumns.ts` hook — capture on `onColumnStateChanged`, restore on
grid ready via `initialState` prop (avoids flicker vs. `applyColumnState` in `onGridReady`).

```typescript
// Source: https://www.ag-grid.com/react-data-grid/column-state/
const LS_KEY = 'flywheel:pipeline:columnState'

// Save
const onColumnStateChanged = useCallback(() => {
  if (gridApiRef.current) {
    const state = gridApiRef.current.getColumnState()
    localStorage.setItem(LS_KEY, JSON.stringify(state))
  }
}, [])

// Restore — pass to <AgGridReact initialState={...}>
const savedState = useMemo(() => {
  const raw = localStorage.getItem(LS_KEY)
  if (!raw) return undefined
  try {
    return { columnState: JSON.parse(raw) }
  } catch {
    return undefined
  }
}, [])
```

### Pattern 3: Debounced Filter State (existing codebase pattern)

**What:** `useEffect` + `setTimeout(300ms)` on search input before updating query params.
Matches the pattern already used in `AccountsPage.tsx`.

```typescript
// Source: frontend/src/features/accounts/components/AccountsPage.tsx
useEffect(() => {
  const timer = setTimeout(() => {
    setDebouncedSearch(searchInput)
    setOffset(0)
  }, 300)
  return () => clearTimeout(timer)
}, [searchInput])
```

### Pattern 4: URL Query Params for Saved View Tabs

**What:** Tabs persist active view in URL `?view=hot` so refreshing or sharing preserves context.

**When to use:** `GRID-04` requires tabs to persist in URL query params.

```typescript
import { useSearchParams } from 'react-router'

const [searchParams, setSearchParams] = useSearchParams()
const activeView = searchParams.get('view') ?? 'all'

// Each tab calls setSearchParams({ view: 'hot' })
// "Hot" view: fitTier filter = 'Strong'
// "Stale" view: computed client-side — filter rows where days_stale > 14
// "Replied" view: outreach_status filter = 'replied'
```

### Pattern 5: Graduate Mutation with Cache Invalidation

**What:** Graduate endpoint requires `types[]` array and sets `graduated_at`. Invalidation must
hit pipeline + relationships + any signals queries.

**When to use:** In `useGraduate.ts` — extend the current implementation to:
1. Accept a `GraduatePayload` (`{ id, types, entity_level }`)
2. Call `POST /relationships/{id}/graduate` (NOT the old `POST /accounts/{id}/graduate`)
3. Invalidate `['pipeline']`, `['relationships']`, and `['signals']` query keys

```typescript
// Source: backend/src/flywheel/api/relationships.py lines 431-496
// GraduateRequest: { types: string[], entity_level?: string }
// Endpoint: POST /relationships/{id}/graduate
// Returns: { id, name, domain, relationship_type, entity_level, graduated_at, updated_at }
```

**Note:** The old `POST /accounts/{account_id}/graduate` endpoint in `outreach.py` does NOT set
`graduated_at`. Phase 56 Plan 03 must update `useGraduate.ts` to call the relationships endpoint
(`/relationships/{id}/graduate`) instead.

### Pattern 6: Stale Row Tint (CSS in AG Grid)

**What:** Rows where `days_stale > 14` render with warm tint background. Apply via
`getRowStyle` prop on `<AgGridReact>`.

```typescript
const getRowStyle = (params: RowStyleParams) => {
  if ((params.data?.days_since_last_outreach ?? 0) > 14) {
    return { background: 'var(--brand-tint)' } // rgba(233,77,53,0.04)
  }
  return undefined
}
```

### Pattern 7: Skeleton Shimmer (existing CSS, new component)

**What:** The app already has `animate-shimmer` keyframe in `index.css`. A shimmer skeleton
component wraps the class and adds dimensions.

```typescript
// index.css already defines:
// @keyframes shimmer { ... }
// .animate-shimmer { background: linear-gradient(...); animation: shimmer 1.5s ... }

function ShimmerSkeleton({ className }: { className?: string }) {
  return <div className={cn('animate-shimmer rounded-md', className)} />
}
```

### Anti-Patterns to Avoid

- **Using `onGridReady` to call `applyColumnState()`:** Causes a visible flicker — the grid
  renders default column widths, then jumps. Use `initialState` prop instead.
- **Importing `ag-grid-community/styles/ag-grid.css`:** The legacy CSS import approach conflicts
  with the v33+ programmatic theme API. Use `themeQuartz.withParams()` only.
- **Calling `POST /accounts/{id}/graduate` for graduation:** This endpoint exists in `outreach.py`
  but does NOT set `graduated_at`. Always use `POST /relationships/{id}/graduate`.
- **Client-side-only filtering:** The "Stale" saved view can be computed client-side (filter rows
  already loaded), but fit_tier and outreach_status filters MUST be server-side once the backend
  is fixed, otherwise the pagination counts will be wrong.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Column resize handle | Custom mouse-drag logic | AG Grid built-in `resizable: true` on colDef | Handles touch, keyboard, min/max width edge cases |
| Column reorder | Drag-and-drop implementation | AG Grid built-in `movable: true` on colDef | Handles auto-scroll at edge of viewport |
| Column visibility toggle | Custom checkbox panel | AG Grid `hide` in column state + custom header button calling `gridApi.setColumnsVisible()` | State syncs automatically to getColumnState() |
| Row virtualization | Windowing with react-virtual | AG Grid built-in (rows not in DOM are not rendered) | Already handles overscan, keyboard nav, scrollTo |
| Debounce hook | Custom useDebounce | `useEffect` + `setTimeout` (existing codebase pattern) | Consistent with AccountsPage.tsx, no new dependency |
| Slide-out animation | Framer Motion | `tw-animate-css` + CSS `transition`/`transform` (already installed) | Phase already has `tw-animate-css`; no Framer needed |

**Key insight:** AG Grid Community provides everything needed for an Airtable-style grid. The
primary risk is theming — using the pre-v33 CSS approach (global class overrides) instead of
`themeQuartz.withParams()` will cause maintenance pain as AG Grid upgrades.

## Common Pitfalls

### Pitfall 1: AG Grid CSS Conflicts with Tailwind v4 Vite Plugin

**What goes wrong:** If you import `ag-grid-community/styles/ag-grid.css` as a static CSS file,
Tailwind v4's `@tailwindcss/vite` plugin processes it through PostCSS, causing `@layer` conflicts
and stripping AG Grid's internal cascade rules.

**Why it happens:** AG Grid v33+ switched from static CSS files to dynamic style injection. The
old CSS files still exist in the package but are legacy — they target the old pre-v33 class-based
theme architecture.

**How to avoid:** Do not import any CSS from `ag-grid-community/styles/`. Use only:
```typescript
import { themeQuartz } from 'ag-grid-community'
const theme = themeQuartz.withParams({ ... })
// Pass theme prop to <AgGridReact theme={theme} />
```
**Warning signs:** Grid renders without row lines, or rows have incorrect colors that ignore
your withParams values.

### Pitfall 2: Grid Height Must Be Fixed

**What goes wrong:** AG Grid renders as zero height if its container does not have an explicit
pixel height or `height: 100%` with a parent that has a defined height.

**Why it happens:** AG Grid uses the container height to compute how many rows to render
(virtualization). Without a fixed height, it calculates 0 visible rows.

**How to avoid:** Wrap `<AgGridReact>` in a `div` with explicit height:
```tsx
<div style={{ height: 'calc(100vh - 240px)', width: '100%' }}>
  <AgGridReact ... />
</div>
```
Or use a fixed pixel height (e.g., `height: 600px` for a shorter grid).
**Warning signs:** Grid container renders but no rows are visible; no error in console.

### Pitfall 3: Backend Pipeline Endpoint Ignores fit_tier and outreach_status

**What goes wrong:** The frontend already sends `fit_tier` and `outreach_status` query params to
`GET /pipeline/`, but the backend (`outreach.py` lines 341–413) does not read or apply them. All
rows are returned regardless of filter values.

**Why it happens:** These query params were added to `PipelineParams` types and the API call, but
the corresponding `Query(...)` parameters and `.where()` clauses were never added to the FastAPI
endpoint.

**How to avoid:** Plan 03 (or whichever plan handles the filter bar) must add to `outreach.py`:
```python
fit_tier: str | None = Query(None),
outreach_status: str | None = Query(None),
# ...
if fit_tier is not None:
    stmt = stmt.where(Account.fit_tier == fit_tier)
if outreach_status is not None:
    stmt = stmt.where(last_status_sq.c.last_status == outreach_status)
```
**Warning signs:** Filter chips show active state but row count doesn't change.

### Pitfall 4: fit_score Has No Database Index

**What goes wrong:** `GET /pipeline/` orders by `Account.fit_score DESC NULLS LAST`. With 206
accounts today this is a seq scan (fast enough), but the index is missing and will cause slow
query under load.

**Why it happens:** No migration has created `idx_account_fit_score`. The existing account table
indexes are on `tenant_id+status`, `relationship_status`, `pipeline_stage`, and `graduated_at`.

**How to avoid:** Add a migration that creates the index. In Plan 02 or Plan 03:
```python
op.create_index(
    "idx_account_tenant_fit_score",
    "accounts",
    ["tenant_id", "fit_score"],
    postgresql_where=sa.text("fit_score IS NOT NULL"),
)
```
**Warning signs:** Pipeline page becomes slow with >1000 accounts; PostgreSQL EXPLAIN shows Seq Scan.

### Pitfall 5: Graduate Flow Uses Wrong Endpoint

**What goes wrong:** The current `useGraduate.ts` calls `POST /accounts/{id}/graduate` (in
`outreach.py`). This endpoint sets `account.status = 'engaged'` but does NOT set `graduated_at`.
The relationships surface uses `graduated_at IS NOT NULL` as its partition predicate.

**Why it happens:** The old graduation endpoint predates Phase 55's `graduated_at` column design.

**How to avoid:** Plan 03 must update `useGraduate.ts` to call
`POST /relationships/{id}/graduate` (defined in `relationships.py`). This endpoint:
- Sets `graduated_at = now` (satisfies partition predicate)
- Sets `relationship_type = body.types[]`
- Returns the full graduated account object

**Warning signs:** Account graduates and disappears from pipeline, but the relationships page
shows 0 items (because `graduated_at` is still NULL, failing the IS NOT NULL predicate).

### Pitfall 6: Saved View Tab State Lost on Navigation

**What goes wrong:** User is on the "Stale" tab, navigates to account detail, returns, and finds
the "All" tab active.

**Why it happens:** React component state does not persist across unmount/remount.

**How to avoid:** Persist active tab in URL query params:
```typescript
const [searchParams, setSearchParams] = useSearchParams()
const activeView = (searchParams.get('view') as ViewKey) ?? 'all'
```
**Warning signs:** Tab resets on browser back navigation.

## Code Examples

Verified patterns from official sources and codebase:

### AG Grid Minimal Setup (React, Community, Programmatic Theme)
```typescript
// Source: https://www.ag-grid.com/react-data-grid/getting-started/
// Source: https://www.ag-grid.com/javascript-data-grid/theming-colors/
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, themeQuartz } from 'ag-grid-community'
import type { ColDef, GridReadyEvent } from 'ag-grid-community'

const pipelineTheme = themeQuartz.withParams({
  backgroundColor: 'var(--card-bg)',
  foregroundColor: 'var(--body-text)',
  headerBackgroundColor: 'var(--card-bg)',
  headerTextColor: 'var(--secondary-text)',
  borderColor: 'var(--subtle-border)',
  accentColor: 'var(--brand-coral)',
  rowHoverColor: 'rgba(0,0,0,0.02)',
  fontSize: 14,
  rowHeight: 56,
  headerHeight: 40,
  fontFamily: "'Geist Variable', ui-sans-serif, system-ui, sans-serif",
})

const colDefs: ColDef[] = [
  { field: 'name', headerName: 'Company', cellRenderer: CompanyCell, minWidth: 200 },
  { field: 'contact', headerName: 'Contact', cellRenderer: ContactCell, minWidth: 160 },
  { field: 'fit_tier', headerName: 'Fit Tier', cellRenderer: FitTierBadge, width: 120 },
  { field: 'last_outreach_status', headerName: 'Outreach', cellRenderer: OutreachDot, width: 120 },
  { field: 'last_interaction_at', headerName: 'Last Action', valueFormatter: formatRelativeTime, width: 140 },
  { field: 'days_since_last_outreach', headerName: 'Days Stale', width: 100 },
  { field: 'actions', headerName: '', cellRenderer: GraduateButton, width: 100, sortable: false },
]

export function PipelineGrid({ rowData }: { rowData: PipelineItem[] }) {
  const gridApiRef = useRef<GridApi>(null)

  const savedInitialState = useMemo(() => {
    const raw = localStorage.getItem('flywheel:pipeline:columnState')
    if (!raw) return undefined
    try { return { columnState: JSON.parse(raw) } } catch { return undefined }
  }, [])

  const onColumnStateChanged = useCallback(() => {
    const state = gridApiRef.current?.getColumnState()
    if (state) localStorage.setItem('flywheel:pipeline:columnState', JSON.stringify(state))
  }, [])

  return (
    <div style={{ height: 'calc(100vh - 220px)', width: '100%' }}>
      <AgGridReact
        modules={[AllCommunityModule]}
        theme={pipelineTheme}
        rowData={rowData}
        columnDefs={colDefs}
        initialState={savedInitialState}
        onColumnResized={onColumnStateChanged}
        onColumnMoved={onColumnStateChanged}
        onColumnVisible={onColumnStateChanged}
        getRowStyle={(p) =>
          (p.data?.days_since_last_outreach ?? 0) > 14
            ? { background: 'var(--brand-tint)' }
            : undefined
        }
        onGridReady={(e: GridReadyEvent) => { gridApiRef.current = e.api }}
      />
    </div>
  )
}
```

### Avatar Component Extension (32px / 48px sizes)
```typescript
// Source: frontend/src/components/ui/avatar.tsx (existing)
// Extension needed: size="md" (32px) and size="lg" (48px) with initials fallback
// Existing sizes: sm=24px, default=32px, lg=40px
// Required by DS-02: 32px and 48px
// Current "default" is already 32px (size-8 = 32px)
// Add size="xl" at 48px via data-[size=xl]:size-12

function CompanyCell({ value, data }: { value: string; data: PipelineItem }) {
  const initial = (data.name ?? '?')[0].toUpperCase()
  return (
    <div className="flex items-center gap-2">
      <Avatar size="default"> {/* 32px */}
        <AvatarFallback style={{ background: 'var(--brand-light)', color: 'var(--brand-coral)' }}>
          {initial}
        </AvatarFallback>
      </Avatar>
      <div>
        <div style={{ fontWeight: 500, color: 'var(--heading-text)' }}>{data.name}</div>
        {data.domain && <div style={{ fontSize: 12, color: 'var(--secondary-text)' }}>{data.domain}</div>}
      </div>
    </div>
  )
}
```

### Translucent Badge (DS-01 requirement)
```typescript
// opacity-10 background + full-opacity text
// Existing badge.tsx uses CVA variants — add "translucent" variant or use inline style

const FIT_TIER_PALETTE: Record<string, { bg: string; text: string }> = {
  strong:    { bg: 'rgba(34,197,94,0.10)',  text: '#16a34a' },
  good:      { bg: 'rgba(59,130,246,0.10)', text: '#2563eb' },
  fair:      { bg: 'rgba(245,158,11,0.10)', text: '#d97706' },
  weak:      { bg: 'rgba(239,68,68,0.10)',  text: '#dc2626' },
}

function FitTierBadge({ value }: { value: string | null }) {
  if (!value) return <span style={{ color: 'var(--secondary-text)' }}>—</span>
  const key = value.toLowerCase()
  const p = FIT_TIER_PALETTE[key] ?? FIT_TIER_PALETTE.fair
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 8px', borderRadius: '9999px',
      background: p.bg, color: p.text,
      fontSize: 12, fontWeight: 500,
    }}>
      {value}
    </span>
  )
}
```

### Status Dot (DS-01 requirement)
```typescript
// 8px colored circle for outreach status
const STATUS_COLORS: Record<string, string> = {
  sent:     '#3B82F6',   // blue
  opened:   '#F97316',   // orange
  replied:  '#22C55E',   // green
  bounced:  '#EF4444',   // red
}

function OutreachDot({ value }: { value: string | null }) {
  const color = value ? (STATUS_COLORS[value] ?? '#6B7280') : '#D1D5DB'
  return (
    <div className="flex items-center gap-2">
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
      <span style={{ fontSize: 13, color: 'var(--secondary-text)', textTransform: 'capitalize' }}>
        {value ?? 'None'}
      </span>
    </div>
  )
}
```

### GraduationModal (type selection)
```typescript
// Backend GraduateRequest: { types: string[], entity_level?: string }
// Source: backend/src/flywheel/api/relationships.py lines 112-128
// ALLOWED_TYPES = {"prospect", "customer", "advisor", "investor"}

function GraduationModal({ accountId, onClose }: { accountId: string; onClose: () => void }) {
  const [selected, setSelected] = useState<string[]>([])
  const graduate = useGraduate()

  const types = ['customer', 'advisor', 'investor'] // prospect excluded — graduating out of prospect

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <h2>Graduate to Relationship</h2>
        {types.map((t) => (
          <label key={t}>
            <input
              type="checkbox"
              checked={selected.includes(t)}
              onChange={() => setSelected((prev) =>
                prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
              )}
            />
            {t}
          </label>
        ))}
        <Button
          disabled={selected.length === 0 || graduate.isPending}
          onClick={() => graduate.mutate({ id: accountId, types: selected })}
        >
          Graduate
        </Button>
      </DialogContent>
    </Dialog>
  )
}
```

### Backend Filter Fix (Plan 03 prerequisite)
```python
# Source: backend/src/flywheel/api/outreach.py — get_pipeline() needs these additions
@router.get("/pipeline/")
async def get_pipeline(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    fit_tier: str | None = Query(None),          # ADD
    outreach_status: str | None = Query(None),   # ADD
    search: str | None = Query(None),            # ADD (for text search requirement)
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    # ... after .where(Account.status == "prospect") ...
    if fit_tier is not None:
        stmt = stmt.where(Account.fit_tier == fit_tier)
    if outreach_status is not None:
        stmt = stmt.where(last_status_sq.c.last_status == outreach_status)
    if search is not None:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Account.name.ilike(pattern) | Account.domain.ilike(pattern)
        )
    # Also update the count query to apply same filters
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| AG Grid CSS class overrides (`ag-theme-alpine`) | `themeQuartz.withParams()` programmatic API | AG Grid v33 (2023) | Must use new API; old CSS imports break with v33+ |
| `onGridReady` + `applyColumnState()` for localStorage restore | `initialState` prop on `<AgGridReact>` | AG Grid v31 | Prevents flicker — grid initializes with correct widths |
| `columnApi` (separate from `gridApi`) | Single unified `gridApi` | AG Grid v30 | No `columnApi` reference needed; all state via `gridApi` |
| `AgGridProvider` wrapper | Direct `<AgGridReact modules={[AllCommunityModule]}>` | AG Grid v33+ | Can pass modules directly; Provider is optional helper |
| `POST /accounts/{id}/graduate` (outreach.py) | `POST /relationships/{id}/graduate` (relationships.py) | Phase 55 | Must update `useGraduate.ts` to use new endpoint |

**Deprecated/outdated:**
- `ag-grid-community/styles/ag-grid.css` and `ag-grid-community/styles/ag-theme-*.css`: Legacy
  static CSS files; do not import in v33+.
- `columnApi`: Removed in v30; all column methods now on `gridApi`.
- `POST /accounts/{account_id}/graduate`: Does not set `graduated_at`; will be superseded by
  Phase 56 Plan 03 updating the hook.

## Open Questions

1. **Spike recommendation: AG Grid theming with Tailwind v4 Vite plugin**
   - What we know: `themeQuartz.withParams()` supports `var(--css-variable)` syntax; Tailwind v4
     uses `@tailwindcss/vite` plugin for CSS processing; the two mechanisms are orthogonal.
   - What's unclear: Whether `@tailwindcss/vite` post-processes `<style>` tags injected by AG
     Grid into the DOM at runtime (it should not, since Vite processes build-time CSS, not runtime
     injected styles — but this has not been tested in this codebase).
   - Recommendation: The phase brief already flags this — budget the 1-hour spike in Plan 02 task
     01 before the rest of the grid work. If the spike fails, fallback is using AG Grid's own
     `--ag-*` CSS variables in a scoped stylesheet: `[data-ag-theme] { --ag-background-color: var(--card-bg); }`.

2. **Contact data on pipeline rows**
   - What we know: `GET /pipeline/` currently returns only Account fields; `AccountContact` is a
     separate table joined via `account.contacts` relationship. The grid columns require
     "Contact + title" and "Email" from the primary contact.
   - What's unclear: Whether Plan 02 should extend the pipeline endpoint to LEFT JOIN the primary
     contact, or whether each grid row fetches contact data lazily.
   - Recommendation: Extend the pipeline endpoint to return `primary_contact_name`,
     `primary_contact_title`, `primary_contact_email`, and `primary_contact_linkedin` via a
     LEFT JOIN LATERAL (same pattern used in `get_pipeline_badges` in relationships.py). Lazy
     per-row fetches would cause N+1 queries.

3. **Saved view "Stale" — client-side vs server-side**
   - What we know: "Stale" is defined as `days_since_last_outreach > 14`. This is already
     computed by the pipeline endpoint as `days_since_last_outreach` on each row.
   - What's unclear: Should the "Stale" view filter server-side (add `stale=true` param to
     endpoint that applies a WHERE clause) or client-side (filter rows already loaded in AG Grid)?
   - Recommendation: Client-side filtering is correct here because: (a) the data for staleness
     is already in each row, (b) pagination would be wrong if we filter client-side but the count
     reflects all records. If "Stale" view needs accurate pagination, it must be server-side. Given
     206 accounts and 25/50/100 page sizes, client-side filtering across all loaded rows is
     acceptable for the initial implementation.

## Sources

### Primary (HIGH confidence)
- [AG Grid React Theming](https://www.ag-grid.com/react-data-grid/theming/) — programmatic API overview
- [AG Grid Theme Colors & CSS Variables](https://www.ag-grid.com/javascript-data-grid/theming-colors/) — `var(--css-variable)` in withParams
- [AG Grid Column State](https://www.ag-grid.com/react-data-grid/column-state/) — `getColumnState`/`applyColumnState`/`initialState`
- [AG Grid Community vs Enterprise](https://www.ag-grid.com/react-data-grid/community-vs-enterprise/) — confirmed all required features in Community edition
- [AG Grid Theme Parameters](https://www.ag-grid.com/react-data-grid/theming-parameters/) — `rowHeight`, `headerHeight`, `backgroundColor`, `fontFamily` params
- `backend/src/flywheel/api/outreach.py` — confirmed no `fit_tier`/`outreach_status` params in pipeline endpoint
- `backend/src/flywheel/api/relationships.py` lines 431-496 — confirmed `GraduateRequest` model and correct endpoint
- `backend/src/flywheel/db/models.py` — confirmed no `idx_account_fit_score` index
- `frontend/src/index.css` — confirmed existing CSS custom properties, `animate-shimmer` keyframe

### Secondary (MEDIUM confidence)
- [AG Grid npm page](https://www.npmjs.com/package/ag-grid-react) — confirmed v35.2.0 as latest version (2026-03-27)
- [AG Grid Community vs Enterprise — Oreate AI](https://www.oreateai.com/blog/unpacking-ag-grid-pricing-community-vs-enterprise-and-what-you-get/fa237a579496851d44caae6461a8e445) — cross-verified feature list
- [Medium: Persisting AG Grid State](https://medium.com/@jwag/persisting-state-for-ag-grid-saving-column-order-filters-and-sort-options-e62f18332ebd) — `onColumnStateChanged` + localStorage pattern

### Tertiary (LOW confidence)
- [AG Grid GitHub Issue #7373](https://github.com/ag-grid/ag-grid/issues/7373) — flicker with `applyColumnState` in `onGridReady` vs `initialState` prop

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — AG Grid v35.2.0 current version confirmed from npm; Community features
  confirmed from official docs; all other libraries already in package.json
- Architecture: HIGH — patterns derived from existing codebase conventions + official AG Grid API
  docs; backend gaps confirmed by reading source code directly
- Pitfalls: HIGH for backend gaps (confirmed by reading code); MEDIUM for AG Grid/Tailwind v4
  interaction (inferred from mechanism analysis, not live-tested — spike recommended)

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (AG Grid releases frequently; check for v36 before planning)
