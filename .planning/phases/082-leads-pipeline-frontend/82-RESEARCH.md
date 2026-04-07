# Phase 82: Leads Pipeline Frontend - Research

**Researched:** 2026-04-01
**Domain:** React frontend — ag-grid data table, side panel, funnel visualization, React Query
**Confidence:** HIGH

## Summary

This is a frontend-only phase building a `/leads` page that is architecturally a sibling to the existing `/pipeline` page. The backend is fully built (10 endpoints at `/api/v1/leads/`), the design brief is complete, and the pipeline feature provides a battle-tested reference implementation for every major pattern: ag-grid with themeQuartz, side panel with slide animation, filter bar with dropdowns, graduation flow with confirmation dialog, pagination, and React Query hooks.

The leads page adds two novel components not present in pipeline: a **horizontal funnel visualization** (LeadsFunnel) and **nested contact accordion with message timeline** (ContactCard + MessageThread in the side panel). Everything else maps directly to existing pipeline patterns with minor adaptations (single-select dropdowns instead of multi-select, StageBadge instead of OutreachStatusCell, PurposePills as a new cell renderer).

**Primary recommendation:** Clone the pipeline feature's file structure and patterns verbatim, then adapt. The design brief specifies every component, column, state, and interaction. Do not invent new patterns — follow pipeline for ag-grid setup, usePipelineColumns for column defs with localStorage persistence, useGraduate for mutation + toast + invalidation, and PipelineSidePanel for the slide-in panel.

## Standard Stack

### Core (already installed in the project)
| Library | Purpose | Why Standard |
|---------|---------|--------------|
| ag-grid-community + ag-grid-react | Data table with sorting, column resize, pinning | Already used in pipeline, themeQuartz configured |
| @tanstack/react-query | Server state, caching, mutation | Already used throughout the app |
| react-router | Routing, URL params, lazy loading | Already used for all routes |
| lucide-react | Icons (Search, X, ChevronDown, ChevronLeft, ChevronRight, Mail, Linkedin, Globe, Users) | Already used everywhere |
| sonner | Toast notifications | Already integrated at `components/ui/sonner.tsx` |

### Reusable from Pipeline
| Component/Pattern | Location | Reuse Strategy |
|-------------------|----------|----------------|
| FitTierBadge | `features/pipeline/components/cell-renderers/FitTierBadge.tsx` | Import directly — same `badges.fitTier` color map from design-tokens. NOTE: Currently typed to `PipelineItem`, needs generic typing or a leads-specific copy |
| CompanyCell pattern | `features/pipeline/components/cell-renderers/CompanyCell.tsx` | Clone and adapt for Lead type (name + domain subtitle) |
| themeQuartz config | `features/pipeline/components/PipelinePage.tsx` lines 21-34 | Extract to shared constant or duplicate (identical config) |
| Column state persistence | `usePipelineColumns.ts` localStorage pattern | Same pattern, different key (`flywheel:leads:columnState`) |
| Graduation mutation | `useGraduate.ts` | New hook, different endpoint (`POST /leads/{id}/graduate`), different invalidation keys |
| Side panel layout | `PipelineSidePanel.tsx` | Same dimensions (440px, z-40), same animation, different content |
| Filter bar structure | `PipelineFilterBar.tsx` | Same search with debounce pattern, but single-select dropdowns (not multi-select checkboxes) |
| Pagination footer | `PipelinePage.tsx` lines 254-306 | Same layout, same page size options |
| EmptyState | `components/ui/empty-state.tsx` | Direct reuse |
| Dialog | `components/ui/dialog.tsx` | Direct reuse for graduation confirmation |
| Button | `components/ui/button.tsx` | Direct reuse |
| ShimmerSkeleton | `components/ui/skeleton.tsx` | Direct reuse |

### No New Dependencies Needed
This phase requires zero new npm packages. Everything is already installed.

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/features/leads/
  api.ts                        # fetchLeads, fetchLeadsPipeline, fetchLeadDetail, graduateLead
  types/
    lead.ts                     # Lead, LeadContact, LeadMessage, LeadsResponse, PipelineFunnel, LeadParams
  hooks/
    useLeads.ts                 # Paginated list query — queryKey: ['leads', params]
    useLeadsPipeline.ts         # Funnel counts query — queryKey: ['leads-pipeline']
    useLeadDetail.ts            # Detail query — queryKey: ['lead-detail', id], enabled when id set
    useLeadGraduate.ts          # Mutation — invalidates ['leads'], ['leads-pipeline'], ['accounts']
    useLeadsColumns.ts          # Column defs + localStorage persistence
  components/
    LeadsPage.tsx               # Page orchestrator (state, hooks, layout)
    LeadsFunnel.tsx             # Horizontal funnel bar (new — no pipeline equivalent)
    LeadsFilterBar.tsx          # Search + 3 single-select dropdowns
    LeadSidePanel.tsx           # Right panel with company info, contacts accordion, graduate button
    ContactCard.tsx             # Expandable contact with message thread
    MessageThread.tsx           # Vertical timeline of outreach messages
    cell-renderers/
      StageBadge.tsx            # Colored stage pill (6 stages)
      PurposePills.tsx          # Purpose tag pills with +N overflow
      LeadGraduateButton.tsx    # Graduate action in table row
      LeadCompanyCell.tsx       # Company name + domain subtitle
```

### Pattern 1: Page Orchestrator (from PipelinePage)
**What:** Single component manages all state (filters, pagination, selected item, graduating ID), renders zones (funnel, filters, table, side panel).
**When to use:** Always for data table pages.
**Key pattern from pipeline:**
```typescript
// State management in LeadsPage — mirrors PipelinePage exactly
const [activeStage, setActiveStage] = useState<string | null>(null)
const [fitTier, setFitTier] = useState<string | null>(null)
const [purpose, setPurpose] = useState<string | null>(null)
const [search, setSearch] = useState('')
const [page, setPage] = useState(0)
const [pageSize, setPageSize] = useState(50)
const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
const [graduatingId, setGraduatingId] = useState<string | null>(null)

// Reset page on filter change — same useEffect pattern
useEffect(() => { setPage(0) }, [activeStage, fitTier, purpose, search, pageSize])
```

### Pattern 2: React Query Hooks (from usePipeline)
**What:** Thin wrapper around useQuery with `placeholderData: (prev) => prev` for smooth pagination.
**Key difference from pipeline:** Leads API uses single-value filters (not arrays), so no comma-join serialization needed.
```typescript
// Source: features/pipeline/hooks/usePipeline.ts
export function useLeads(params: LeadParams) {
  return useQuery({
    queryKey: ['leads', params],
    queryFn: () => fetchLeads(params),
    placeholderData: (prev) => prev,  // keeps previous data while loading next page
  })
}
```

### Pattern 3: Graduation Mutation (from useGraduate)
**What:** useMutation with onSuccess that invalidates related queries and fires toast.
**Key difference:** Leads graduation is simpler — no type selection modal, just confirm/cancel.
```typescript
// Source: features/pipeline/hooks/useGraduate.ts — adapted for leads
export function useLeadGraduate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (leadId: string) => api.post(`/leads/${leadId}/graduate`),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['leads-pipeline'] })
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      toast.success(`${data.account_name} graduated to accounts`)
    },
  })
}
```

### Pattern 4: ag-grid Column Defs with Persistence (from usePipelineColumns)
**What:** Column definitions as a static array, localStorage save/restore of column state.
```typescript
// Source: features/pipeline/hooks/usePipelineColumns.ts
const COLUMN_STATE_KEY = 'flywheel:leads:columnState'
// Same getInitialState() and onColumnStateChanged() pattern
```

### Pattern 5: Side Panel with Backdrop (from PipelinePage + PipelineSidePanel)
**What:** Conditional render of backdrop div + fixed panel, click backdrop or Escape to close.
```typescript
// Source: features/pipeline/components/PipelinePage.tsx lines 312-329
{selectedLead && (
  <>
    <div className="fixed inset-0 z-30" style={{ background: 'rgba(0,0,0,0.2)' }}
         onClick={() => setSelectedLead(null)} />
    <LeadSidePanel lead={selectedLead} onClose={() => setSelectedLead(null)} ... />
  </>
)}
```

### Pattern 6: Row Click with stopPropagation (from GraduateButton)
**What:** Graduate button calls `stopPropagation()` so row click (open panel) is suppressed.
```typescript
// Source: features/pipeline/components/cell-renderers/GraduateButton.tsx
// The graduate button uses context.onGraduate() passed via ag-grid context prop
```

### Anti-Patterns to Avoid
- **Don't use ag-grid built-in pagination:** The project uses custom pagination controls (select + prev/next buttons). ag-grid's built-in pagination looks different and doesn't match the design.
- **Don't use ag-grid built-in filtering:** All filtering is done server-side via API params. ag-grid column filters are disabled.
- **Don't build a custom dropdown from scratch for filters:** The pipeline already has a `FilterDropdown` component. For leads, adapt it to single-select (radio behavior instead of checkbox).
- **Don't put the theme config inline:** The same `themeQuartz.withParams({...})` object is used in pipeline. Either extract to a shared util or duplicate (it's small).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Data table | Custom table with divs | ag-grid with themeQuartz | Column resize, sort, pinning, keyboard nav, row virtualization |
| Toast notifications | Custom toast system | Sonner (already integrated) | Already wired up, consistent with rest of app |
| Confirmation dialog | Custom modal | Dialog component from `components/ui/dialog.tsx` | Focus trap, escape handling, accessible |
| Server state management | useState + useEffect fetch | React Query (useQuery/useMutation) | Caching, deduplication, background refetch, optimistic updates |
| Debounced search | Manual setTimeout | Same pattern as PipelineFilterBar (local state + useEffect with 300ms timeout) | Proven pattern already in codebase |
| Relative time formatting | date-fns or moment | Copy `formatRelativeTime` from `usePipelineColumns.ts` lines 13-27 | Zero dependencies, matches existing format |

## Common Pitfalls

### Pitfall 1: FitTierBadge Type Mismatch
**What goes wrong:** FitTierBadge is typed to `ICellRendererParams<PipelineItem>`. Using it with `Lead` type causes TypeScript errors.
**Why it happens:** The component imports `PipelineItem` type.
**How to avoid:** Either: (a) create a leads-specific copy typed to `Lead`, or (b) make FitTierBadge generic by only accessing `data.fit_tier` which exists on both types. Option (a) is simpler and matches the design brief's recommendation.
**Warning signs:** TypeScript error on `cellRenderer: FitTierBadge` in column defs.

### Pitfall 2: Funnel Click + Stage Dropdown Desync
**What goes wrong:** Clicking a funnel segment doesn't update the Stage dropdown, or vice versa.
**Why it happens:** Two controls share the same `activeStage` state. If they manage their own internal state, they desync.
**How to avoid:** Both components receive `activeStage` and `onStageChange` as props. The funnel is NOT a controlled component with internal state — it's purely presentational + onClick.
**Warning signs:** Clicking funnel shows active border but dropdown still says "All stages".

### Pitfall 3: Pipeline Stage Filter is Computed Server-Side (Python-side)
**What goes wrong:** Filtering by pipeline_stage is slow or returns wrong counts.
**Why it happens:** Pipeline stage is computed from MAX across contacts, not stored as a column. The backend fetches ALL leads and filters in Python when `pipeline_stage` param is set (see `leads.py` lines 331-349).
**How to avoid:** Accept this is a known backend limitation. For small datasets (<10k leads) it's fine. The funnel endpoint (`/leads/pipeline`) is separate and cached independently — don't combine it with the list query.
**Warning signs:** Slow response when filtering by stage on large datasets.

### Pitfall 4: Row Animation on Graduate Conflicts with React Query Refetch
**What goes wrong:** Row slides out, then row reappears briefly, then disappears when query refetches.
**Why it happens:** Graduation mutation triggers invalidation which refetches the list. If the refetch returns before animation completes, the row reappears.
**How to avoid:** Set `graduatingId` state immediately on mutation success (before invalidation). Use `getRowStyle` to apply the slide-out animation. After animation duration (300ms), clear `graduatingId`. Pipeline uses a `setTimeout` for this (line 123-127).
**Warning signs:** Row flickers after graduation.

### Pitfall 5: Side Panel Escape Key Doesn't Close
**What goes wrong:** Pressing Escape while side panel is open does nothing.
**Why it happens:** No `useEffect` listening for keydown events.
**How to avoid:** Add a keydown listener for Escape in the LeadSidePanel (or in LeadsPage when `selectedLead` is set). The design brief specifies focus trap too — implement with `tabindex` management.
**Warning signs:** Panel only closes on backdrop click or X button.

### Pitfall 6: ag-grid AllCommunityModule Not Imported
**What goes wrong:** ag-grid renders nothing or throws errors.
**Why it happens:** ag-grid v33+ requires explicit module registration.
**How to avoid:** Import `AllCommunityModule` from `ag-grid-community` and pass as `modules={[AllCommunityModule]}` prop. This is already done in PipelinePage.
**Warning signs:** Empty grid area, console errors about missing modules.

### Pitfall 7: Leads Route Not Added to Sidebar Navigation
**What goes wrong:** Route works but users can't navigate to it.
**Why it happens:** Only `routes.tsx` is updated, but `AppSidebar.tsx` is forgotten.
**How to avoid:** Add a "Leads" item to the sidebar, ideally in the Pipeline group or as a new "Outbound" group. Use the `Users` icon (from lucide-react, already imported in AppSidebar).
**Warning signs:** Page works at `/leads` but no nav link.

## Code Examples

### TypeScript Types (derived from backend serializers)
```typescript
// Source: backend/src/flywheel/api/leads.py _serialize_lead, _serialize_contact, _serialize_message

export interface Lead {
  id: string
  name: string
  domain: string | null
  purpose: string[]
  fit_score: number | null
  fit_tier: string | null
  fit_rationale: string | null
  intel: Record<string, unknown>
  source: string
  campaign: string | null
  pipeline_stage: string  // computed: max across contacts
  contact_count: number
  account_id: string | null
  graduated_at: string | null
  created_at: string
  updated_at: string
  contacts?: LeadContact[]  // only on detail endpoint
}

export interface LeadContact {
  id: string
  lead_id: string
  name: string
  email: string | null
  title: string | null
  linkedin_url: string | null
  role: string | null
  pipeline_stage: string
  notes: string | null
  created_at: string
  messages?: LeadMessage[]  // only on detail endpoint
}

export interface LeadMessage {
  id: string
  step_number: number
  channel: 'email' | 'linkedin'
  status: 'drafted' | 'sent' | 'delivered' | 'replied' | 'bounced'
  subject: string | null
  body: string | null
  drafted_at: string | null
  sent_at: string | null
  replied_at: string | null
  created_at: string
}

export interface LeadsResponse {
  items: Lead[]
  total: number
  offset: number
  limit: number
}

export interface PipelineFunnel {
  funnel: Record<string, number>  // {scraped: N, scored: N, ...}
  total: number
}

export interface LeadParams {
  offset?: number
  limit?: number
  pipeline_stage?: string
  fit_tier?: string
  purpose?: string
  search?: string
}
```

### API Functions (following pipeline/api.ts pattern)
```typescript
// Source: pattern from features/pipeline/api.ts
import { api } from '@/lib/api'
import type { Lead, LeadsResponse, PipelineFunnel, LeadParams } from './types/lead'

export function fetchLeads(params: LeadParams): Promise<LeadsResponse> {
  const clean: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) clean[k] = v
  }
  return api.get<LeadsResponse>('/leads/', { params: clean })
}

export function fetchLeadsPipeline(): Promise<PipelineFunnel> {
  return api.get<PipelineFunnel>('/leads/pipeline')
}

export function fetchLeadDetail(id: string): Promise<Lead> {
  return api.get<Lead>(`/leads/${id}`)
}

export function graduateLead(id: string): Promise<{ graduated: boolean; account_id: string; account_name: string }> {
  return api.post(`/leads/${id}/graduate`)
}
```

### Stage Colors Map (from design brief)
```typescript
export const STAGE_COLORS: Record<string, string> = {
  scraped: '#6b7280',
  scored: '#7c3aed',
  researched: '#2563eb',
  drafted: '#d97706',
  sent: '#0284c7',
  replied: '#16a34a',
}

export const STAGE_ORDER = ['scraped', 'scored', 'researched', 'drafted', 'sent', 'replied']
```

### ag-grid Theme (identical to pipeline)
```typescript
// Source: features/pipeline/components/PipelinePage.tsx lines 21-34
const leadsTheme = themeQuartz.withParams({
  backgroundColor: '#FFFFFF',
  foregroundColor: '#121212',
  headerBackgroundColor: '#FAFAFA',
  headerTextColor: '#9CA3AF',
  borderColor: '#F3F4F6',
  accentColor: '#E94D35',
  rowHoverColor: '#FAFAFA',
  fontSize: 13,
  rowHeight: 44,
  headerHeight: 36,
  headerFontWeight: 600,
  fontFamily: "'Geist Variable', ui-sans-serif, system-ui, sans-serif",
})
```

### Route Registration (following existing pattern)
```typescript
// In routes.tsx — same lazy-load pattern as PipelinePage
const LeadsPage = lazy(() =>
  import('@/features/leads/components/LeadsPage').then((m) => ({ default: m.LeadsPage }))
)
// Route: <Route path="/leads" element={<Suspense fallback={null}><LeadsPage /></Suspense>} />
```

### Sidebar Nav Item (following pipeline pattern)
```typescript
// In AppSidebar.tsx — add to Pipeline group or create Outbound group
<SidebarMenuItem>
  <SidebarMenuButton
    isActive={location.pathname === '/leads'}
    render={<NavLink to="/leads" />}
    tooltip="Leads"
  >
    <Users className="size-4" />
    <span>Leads</span>
  </SidebarMenuButton>
</SidebarMenuItem>
```

## Key Differences from Pipeline

| Aspect | Pipeline | Leads |
|--------|----------|-------|
| Filter type | Multi-select checkboxes | Single-select dropdowns (radio behavior) |
| Filter values | Arrays (fitTier[], outreachStatus[]) | Single strings (pipeline_stage, fit_tier, purpose) |
| Top visualization | View tabs (all/hot/replied/stale) | Funnel bar with stage counts |
| Side panel content | Single contact + last outreach | Multiple contacts with message threads |
| Graduation flow | Type selection modal (customer/advisor/investor) | Simple confirm/cancel dialog |
| Query invalidation | ['pipeline'], ['relationships'], ['signals'], ['accounts'] | ['leads'], ['leads-pipeline'], ['accounts'] |
| URL params | `?view=` for tabs | `?stage=` for funnel filter |

## Integration Points

### Files to Modify (existing)
1. `frontend/src/app/routes.tsx` — add `/leads` route with lazy import
2. `frontend/src/features/navigation/components/AppSidebar.tsx` — add Leads nav item

### Files to Create (new)
1. `features/leads/api.ts`
2. `features/leads/types/lead.ts`
3. `features/leads/hooks/useLeads.ts`
4. `features/leads/hooks/useLeadsPipeline.ts`
5. `features/leads/hooks/useLeadDetail.ts`
6. `features/leads/hooks/useLeadGraduate.ts`
7. `features/leads/hooks/useLeadsColumns.ts`
8. `features/leads/components/LeadsPage.tsx`
9. `features/leads/components/LeadsFunnel.tsx`
10. `features/leads/components/LeadsFilterBar.tsx`
11. `features/leads/components/LeadSidePanel.tsx`
12. `features/leads/components/ContactCard.tsx`
13. `features/leads/components/MessageThread.tsx`
14. `features/leads/components/cell-renderers/StageBadge.tsx`
15. `features/leads/components/cell-renderers/PurposePills.tsx`
16. `features/leads/components/cell-renderers/LeadGraduateButton.tsx`
17. `features/leads/components/cell-renderers/LeadCompanyCell.tsx`

### Total: 17 new files + 2 modified files

## Open Questions

1. **FitTierBadge reuse vs copy**
   - What we know: The existing FitTierBadge is typed to `PipelineItem`. The design brief says "Reuse existing."
   - What's unclear: Whether to make it generic or create a leads-specific copy.
   - Recommendation: Create a leads-specific copy. It's 42 lines, type safety is worth the duplication. The alternative (moving to shared components) is a bigger refactor.

2. **Sidebar placement for Leads**
   - What we know: Pipeline has its own group below Relationships. Leads is a pre-relationship concept.
   - What's unclear: Whether Leads should be above Pipeline, in the same group, or in a new "Outbound" group.
   - Recommendation: Add Leads immediately above Pipeline in the same sidebar group. They're related concepts (leads graduate to pipeline/accounts).

## Sources

### Primary (HIGH confidence)
- `features/pipeline/` — full reference implementation (PipelinePage, hooks, cell-renderers, types, api)
- `features/leads/DESIGN-BRIEF.md` — complete design specification
- `features/leads/DESIGN-BRIEF-INPUT.md` — requirements with data model and API
- `backend/src/flywheel/api/leads.py` — backend API with serializers, routes, response shapes
- `components/ui/` — existing shared components (Dialog, Button, EmptyState, Skeleton, Sonner)
- `lib/design-tokens.ts` — spacing, typography, colors, badges
- `lib/api.ts` — API client with auth headers
- `app/routes.tsx` — route registration pattern
- `features/navigation/components/AppSidebar.tsx` — sidebar navigation structure

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and used in pipeline
- Architecture: HIGH — exact patterns exist in pipeline feature, file-by-file reference available
- Pitfalls: HIGH — derived from examining actual pipeline code and backend API implementation
- Types: HIGH — derived directly from backend serializer functions in leads.py

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable — no external dependencies, all internal patterns)
