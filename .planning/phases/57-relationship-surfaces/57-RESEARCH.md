# Phase 57: Relationship Surfaces - Research

**Researched:** 2026-03-27
**Domain:** React frontend — card-grid list pages, shared detail page with type-driven tabs, AI panel, sidebar badge counts
**Confidence:** HIGH

## Summary

Phase 57 is a pure frontend phase with no new backend work. All five backend APIs that power this phase
exist and are verified working: `GET /relationships/` (list, type-filtered), `GET /relationships/{id}`
(detail), `POST /relationships/{id}/notes`, `POST /relationships/{id}/synthesize`, and
`POST /relationships/{id}/ask`. The signals endpoint (`GET /signals/`) returns per-type badge counts
that the sidebar will display. No new npm packages are required — every library needed is already
installed and in active use.

The key architectural decision that shapes all five plans is the `fromType` URL parameter pattern.
A single `RelationshipDetail` page is shared across all four relationship types. The page reads
`?fromType=prospect|customer|advisor|investor` from the URL to (a) configure which tabs appear
and (b) control the back-link. Prospects and Customers show an Intelligence tab; Advisors and
Investors do not. This type-config-map pattern should be a single authoritative constant in
`RelationshipDetail.tsx`, not spread across multiple files.

The AI context panel (Plan 57-05) is the highest-complexity component. It combines three distinct
behaviors behind one input: idle note capture (saves as ContextEntry via RAPI-05), question
answering (calls RAPI-08 ask API), and synthesis trigger (calls RAPI-07 with rate-limit awareness).
The dual-mode input requires an intent heuristic — most simply, questions ending in `?` go to ask;
everything else becomes a note. Source citations from the ask response must render inline. This
component should be built as its own focused unit with explicit state machine logic.

The codebase already has strong conventions that Phase 57 must follow exactly: `useQuery` hooks in
`features/{name}/hooks/`, API calls in `features/{name}/api.ts`, design tokens from
`lib/design-tokens.ts`, CSS variables from `index.css`, lazy-loaded pages via `React.lazy` +
`Suspense` in `app/routes.tsx`, and `queryClient.invalidateQueries()` with the existing key
hierarchy `['pipeline', 'relationships', 'signals', 'accounts']`.

**Primary recommendation:** Build as five sequential plans: sidebar first (badge counts drive
navigation UX), then list pages, then the shared detail skeleton (layout + header + tab navigation),
then the tab content bodies (Timeline, People, Intelligence, Commitments, action bar), and finally
the AI panel (most complex, isolated last to avoid blocking the detail page).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @tanstack/react-query | ^5.91.2 | Data fetching, cache, invalidation | Already in use for all hooks; query key hierarchy established |
| react-router | ^7.13.1 | URL params, navigation, lazy loading | App uses react-router throughout; `useParams`, `useSearchParams`, `Link` |
| lucide-react | ^0.577.0 | Type icons (Users, TrendingUp, Briefcase, DollarSign, etc.) | Already installed; all icon needs covered |
| sonner | ^2.0.7 | Toast notifications for action bar stubs + note save feedback | Already installed and wired in AppLayout |
| zustand | ^5.0.12 | Global UI state if needed (panel open/close) | Already installed; prefer local state unless cross-component |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @base-ui/react | (installed) | Tabs primitive (`TabsPrimitive`) | `tabs.tsx` wraps this; use existing `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent` |
| class-variance-authority | ^0.7.1 | Badge variants | Already installed; `badge-translucent` CSS class established in 56-01 |
| tw-animate-css | ^1.4.0 | Card hover transitions | `transition-interactive` utility established in 56-01 |

### No New Packages Needed
All required functionality exists. Do NOT add new npm dependencies for this phase.

**Installation:** None required.

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
├── features/
│   └── relationships/            # NEW feature slice
│       ├── api.ts                # fetchRelationships, fetchRelationshipDetail, createNote, synthesize, ask
│       ├── hooks/
│       │   ├── useRelationships.ts    # useQuery wrapping fetchRelationships({type})
│       │   ├── useRelationshipDetail.ts
│       │   ├── useSignals.ts          # useQuery wrapping GET /signals/
│       │   ├── useCreateNote.ts       # useMutation for RAPI-05
│       │   ├── useSynthesize.ts       # useMutation for RAPI-07 (rate-limit aware)
│       │   └── useAsk.ts              # useMutation for RAPI-08
│       ├── types/
│       │   └── relationships.ts       # TS types matching backend Pydantic schemas
│       └── components/
│           ├── RelationshipListPage.tsx    # Card grid (3/2/1 col), urgency sort, empty state
│           ├── RelationshipCard.tsx        # Individual card — type-specific content
│           ├── RelationshipDetail.tsx      # Shared detail: left AI panel + tab area
│           ├── RelationshipHeader.tsx      # Avatar, name, type badges
│           ├── tabs/
│           │   ├── TimelineTab.tsx         # Annotated entries, paginated
│           │   ├── PeopleTab.tsx           # 48px contact cards
│           │   ├── IntelligenceTab.tsx     # Prospects/Customers only — editable data points
│           │   └── CommitmentsTab.tsx      # Two-column, overdue highlight
│           └── AskPanel.tsx               # Left panel: summary + note/Q&A input
├── features/navigation/
│   └── components/AppSidebar.tsx      # MODIFIED: add RELATIONSHIPS section header + badge links
└── app/
    └── routes.tsx                     # MODIFIED: add 5 new lazy routes
```

### Pattern 1: Query Key Factory
**What:** All relationship queries use a consistent key hierarchy so `invalidateQueries` works.
**When to use:** Every `useQuery` in the relationships feature must use these keys exactly.

```typescript
// Source: frontend/src/features/pipeline/hooks/useGraduate.ts (invalidation pattern)
// Extended to relationships surface

export const queryKeys = {
  relationships: {
    all: ['relationships'] as const,
    list: (type: string) => ['relationships', 'list', type] as const,
    detail: (id: string) => ['relationships', id] as const,
  },
  signals: {
    all: ['signals'] as const,
  },
} as const
```

The graduation hook already invalidates `['relationships']` and `['signals']` — any query whose key
starts with these prefixes will be invalidated automatically when graduation occurs.

### Pattern 2: Card Grid Layout (3-col / 2-col / 1-col responsive)
**What:** CSS grid with Tailwind responsive breakpoints. Warm tint background via register system.
**When to use:** `RelationshipListPage.tsx` and `RelationshipCard.tsx`.

```typescript
// Source: lib/design-tokens.ts — registers.relationship pattern
// Page wrapper applies warm register background

<div
  style={{ background: registers.relationship.background }}   // var(--brand-tint-warm)
  className="min-h-dvh"
>
  <div
    className="mx-auto w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
    style={{ maxWidth: spacing.maxGrid, padding: `${spacing.section} ${spacing.pageDesktop}` }}
  >
    {items.map(item => <RelationshipCard key={item.id} item={item} />)}
  </div>
</div>
```

### Pattern 3: RelationshipCard — Two-Layer Shadow + Urgency Border
**What:** Cards use `BrandedCard` component or equivalent inline shadow. Urgency is expressed via
left border color (`cardBorderColors.action` for overdue/high-signal, `transparent` for normal).
**When to use:** Each card in the grid.

```typescript
// Source: frontend/src/components/ui/branded-card.tsx — card shadow and border pattern
// Source: lib/design-tokens.ts — cardBorderColors

const urgencyVariant = (item: RelationshipListItem): CardVariant => {
  if (item.signal_count > 0) return 'action'   // coral left border
  return 'info'                                 // no left border
}
```

### Pattern 4: Type-Driven Tab Configuration Map
**What:** A static config object maps `RelationshipType` to which tabs appear. This prevents
if/else chains spread across components.
**When to use:** `RelationshipDetail.tsx` — read `fromType` from URL, look up tab config.

```typescript
// Pattern derived from Phase 57 architectural decision (fromType param)

type RelationshipType = 'prospect' | 'customer' | 'advisor' | 'investor'

interface TabConfig {
  key: string
  label: string
}

const TAB_CONFIG: Record<RelationshipType, TabConfig[]> = {
  prospect: [
    { key: 'timeline', label: 'Timeline' },
    { key: 'people', label: 'People' },
    { key: 'intelligence', label: 'Intelligence' },
    { key: 'commitments', label: 'Commitments' },
  ],
  customer: [
    { key: 'timeline', label: 'Timeline' },
    { key: 'people', label: 'People' },
    { key: 'intelligence', label: 'Intelligence' },
    { key: 'commitments', label: 'Commitments' },
  ],
  advisor: [
    { key: 'timeline', label: 'Timeline' },
    { key: 'people', label: 'People' },
    { key: 'commitments', label: 'Commitments' },
  ],
  investor: [
    { key: 'timeline', label: 'Timeline' },
    { key: 'people', label: 'People' },
    { key: 'commitments', label: 'Commitments' },
  ],
}
```

### Pattern 5: AskPanel Dual-Mode Input State Machine
**What:** Single `<textarea>` drives three behaviors: idle (note capture), Q&A question, and
synthesis request. State must be explicit — do not use boolean flags.
**When to use:** `AskPanel.tsx` only.

```typescript
// Pattern: explicit state enum prevents ambiguous boolean flag combinations

type PanelMode = 'idle' | 'asking' | 'saving_note' | 'synthesizing'

const [mode, setMode] = useState<PanelMode>('idle')
const [inputValue, setInputValue] = useState('')
const [lastAnswer, setLastAnswer] = useState<AskResponse | null>(null)

// Intent heuristic — questions (ending with ?) → ask; everything else → note
const isQuestion = (text: string) => text.trim().endsWith('?')

function handleSubmit() {
  const trimmed = inputValue.trim()
  if (!trimmed) return
  if (isQuestion(trimmed)) {
    setMode('asking')
    askMutation.mutate({ question: trimmed }, { onSettled: () => setMode('idle') })
  } else {
    setMode('saving_note')
    noteMutation.mutate({ content: trimmed }, { onSettled: () => setMode('idle') })
  }
  setInputValue('')
}
```

### Pattern 6: Sidebar RELATIONSHIPS Section Header + Badge Links
**What:** Insert a new `SidebarGroup` with a `SidebarGroupLabel` ("RELATIONSHIPS") and four
`SidebarMenuItem` entries for Prospects/Customers/Advisors/Investors, each with a coral badge
from `GET /signals/`. Pipeline moves below this group.
**When to use:** `AppSidebar.tsx` only.

```typescript
// Source: AppSidebar.tsx — existing SidebarGroup/SidebarMenuItem pattern
// Source: signals.py — TypeBadge.total_signals drives badge number

// badge count display
{badge > 0 && (
  <span
    className="badge-translucent ml-auto"
    style={{
      background: 'rgba(233,77,53,0.1)',
      color: 'var(--brand-coral)',
    }}
  >
    {badge}
  </span>
)}
```

### Pattern 7: Route Registration (Lazy-Loaded)
**What:** All new pages follow the lazy import + Suspense pattern in `routes.tsx`.
**When to use:** All five new page routes in Phase 57.

```typescript
// Source: frontend/src/app/routes.tsx — lazy loading pattern

const RelationshipListPage = lazy(() =>
  import('@/features/relationships/components/RelationshipListPage').then(
    (m) => ({ default: m.RelationshipListPage })
  )
)

// Routes:
// /relationships/prospects
// /relationships/customers
// /relationships/advisors
// /relationships/investors
// /relationships/:id   (shared detail, ?fromType= param)
```

### Pattern 8: Existing Tabs Component Usage
**What:** `tabs.tsx` wraps `@base-ui/react/tabs` — use `variant="line"` for underline-style tabs
matching the PipelineViewTabs aesthetic.
**When to use:** Detail page tab navigation.

```typescript
// Source: frontend/src/components/ui/tabs.tsx — line variant

<Tabs defaultValue="timeline">
  <TabsList variant="line">
    {tabs.map(tab => (
      <TabsTrigger key={tab.key} value={tab.key}>{tab.label}</TabsTrigger>
    ))}
  </TabsList>
  <TabsContent value="timeline"><TimelineTab ... /></TabsContent>
  {hasIntelligence && <TabsContent value="intelligence"><IntelligenceTab ... /></TabsContent>}
  ...
</Tabs>
```

### Pattern 9: Type-Specific Action Bar Buttons
**What:** Static config map of `RelationshipType → ActionConfig[]`. All buttons show `toast.info`
stubs initially — no backend calls.
**When to use:** Action bar rendered at bottom of detail page, outside the tab panel.

```typescript
// Source: frontend/src/features/accounts/components/ActionBar.tsx — toast stub pattern

const ACTION_CONFIG: Record<RelationshipType, ActionConfig[]> = {
  prospect:  [
    { label: 'Draft Follow-up', icon: Send },
    { label: 'Research', icon: Search },
    { label: 'Schedule', icon: Calendar },
  ],
  customer:  [{ label: 'Draft Check-in', icon: Send }, { label: 'Prep Meeting', icon: Briefcase }, { label: 'Research', icon: Search }],
  advisor:   [{ label: 'Draft Thank You', icon: Send }, { label: 'Schedule Catch-up', icon: Calendar }, { label: 'Ask for Intro', icon: Users }],
  investor:  [{ label: 'Draft Update', icon: Send }, { label: 'Schedule', icon: Calendar }, { label: 'Prep Board Deck', icon: Briefcase }],
}
```

### Anti-Patterns to Avoid
- **Per-type page files:** Do not create four separate list pages or four separate detail pages. One `RelationshipListPage` receives `type` from URL params; one `RelationshipDetail` uses the tab config map.
- **Auto-triggering synthesis on detail page load:** `GET /relationships/{id}` returns `ai_summary` from the column (may be NULL). Never call POST /synthesize on mount. Synthesize only on explicit user button press.
- **Passing `fromType` through component props instead of URL:** The type context must be in the URL so browser back/forward and deep links work. Read it via `useSearchParams` or `useParams`.
- **Querying signals on every render:** `useSignals` should have `staleTime: 60_000` minimum. Sidebar badge counts do not need realtime precision.
- **Using the AG Grid Tabs component:** The detail page uses the existing `tabs.tsx` wrapping `@base-ui/react/tabs`. AG Grid is only for the pipeline grid (Phase 56) — do not import it in Phase 57.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tab navigation with keyboard | Custom button-based tabs | `tabs.tsx` (`Tabs`/`TabsList`/`TabsTrigger`/`TabsContent`) | Already wraps @base-ui/react/tabs with accessible keyboard nav and aria-selected |
| Toast feedback | Custom alert component | `sonner` via `toast.success()` / `toast.error()` | Already wired in AppLayout Toaster; consistent across app |
| Contact avatar fallback | Custom initials renderer | `Avatar` + `AvatarFallback` from `components/ui/avatar.tsx` | Already supports `size="xl"` (48px) added in Phase 56-01 |
| Loading skeletons | Custom shimmer div | `ShimmerSkeleton` from `components/ui/skeleton.tsx` | Added in Phase 56-01 for consistent shimmer pattern |
| Empty state | Inline empty div | `EmptyState` from `components/ui/empty-state.tsx` | Added in Phase 56-01 with icon + title + description + CTA |
| Rate limit error display | Custom error component | Check `error.code === 429` from `ApiError` and show retry-after message | `ApiError` class in `lib/api.ts` has `code` field |
| Relative time formatting | Custom date library | Inline `formatRelativeTime` function | Pattern already in `AccountsPage.tsx` — copy the function |

**Key insight:** The entire design system (tokens, components, shadows, animations) was established in Phase 56-01 specifically for Phase 57 to inherit. Do not re-introduce any of those patterns from scratch.

## Common Pitfalls

### Pitfall 1: fromType URL Param Not Propagated on Card Click
**What goes wrong:** Clicking a relationship card navigates to `/relationships/:id` without `?fromType=`, so the detail page renders with no tabs and no back-link.
**Why it happens:** `navigate(id)` called without passing search params.
**How to avoid:** Card click must use `navigate(\`/relationships/\${item.id}?fromType=\${type}\`)` where `type` is the current list page type.
**Warning signs:** Detail page shows fallback/empty tab list; back button goes to wrong page.

### Pitfall 2: Intelligence Tab Visible for Advisors/Investors
**What goes wrong:** The tab config lookup fails silently and shows Intelligence tab for all types.
**Why it happens:** Using `relationship_type[0]` from the API response as `fromType` instead of the URL param. The API returns an array (e.g., `["advisor", "investor"]`), not a single canonical type.
**How to avoid:** Always derive `fromType` from the URL param, not from `account.relationship_type`. The URL param is the navigational context; the array field is data.
**Warning signs:** Intelligence tab appears for advisor/investor detail pages.

### Pitfall 3: Signals Query Firing on Unauthenticated Routes
**What goes wrong:** `useSignals` fires before auth is established, returning 401 errors in the sidebar.
**Why it happens:** `AppSidebar` is rendered inside `AppShell`, but the signals query doesn't check auth state.
**How to avoid:** Add `enabled: !!user` to the `useSignals` query options, same as other tenant-dependent queries. Check `useAuthStore` for the token.
**Warning signs:** Console shows 401 errors on /onboarding or /auth routes.

### Pitfall 4: Note vs Question Input Ambiguity
**What goes wrong:** The AI panel submits every input as a question, or every input as a note, because the intent heuristic is missing or inverted.
**Why it happens:** Input intent detection not implemented; defaults to one behavior.
**How to avoid:** Implement the question heuristic (ends with `?`) explicitly. Display a UI hint below the input: "End with ? to ask, otherwise saves as note."
**Warning signs:** Plain text inputs trigger the ask endpoint; questions get saved as notes.

### Pitfall 5: Synthesis Rate Limit Not Surfaced to User
**What goes wrong:** User clicks "Refresh AI Summary", gets a silent failure or unhandled error.
**Why it happens:** `ApiError` with code 429 is thrown from the API client but not caught in `useSynthesize`.
**How to avoid:** In `useSynthesize` mutation's `onError` handler, check `error.code === 429` and show a specific toast: "AI summary was refreshed recently. Try again in a few minutes."
**Warning signs:** Synthesis button appears to do nothing on second click within 5 minutes.

### Pitfall 6: Card Grid Background Does Not Apply on List Pages
**What goes wrong:** Relationship list pages show `--page-bg` (cool white) instead of `--brand-tint-warm` (warm tint), indistinguishable from Pipeline.
**Why it happens:** The page container lacks the register background style.
**How to avoid:** Every relationship list page wrapper must use `style={{ background: registers.relationship.background }}` from `lib/design-tokens.ts`.
**Warning signs:** Pipeline page and Prospects page look identical in background color.

### Pitfall 7: Stale Signal Counts in Sidebar After Graduation
**What goes wrong:** After graduating an account, the sidebar still shows old badge counts.
**Why it happens:** `useGraduate` already invalidates `['signals']` — but `useSignals` might have a very long `staleTime`.
**How to avoid:** Keep `staleTime` at the default 30s for signals (already set in QueryClient defaultOptions). No explicit `staleTime` override in `useSignals` unless needed.
**Warning signs:** Sidebar badge counts don't update after graduation actions.

## Code Examples

### Fetching Relationship List
```typescript
// Source: backend/src/flywheel/api/relationships.py — RAPI-01 response shape
// api.ts pattern matches pipeline/api.ts

import { api } from '@/lib/api'

export interface RelationshipListItem {
  id: string
  name: string
  domain: string | null
  relationship_type: string[]
  entity_level: string
  relationship_status: string
  ai_summary: string | null
  signal_count: number
  primary_contact_name: string | null
  last_interaction_at: string | null
  created_at: string
}

export function fetchRelationships(type: string): Promise<{ items: RelationshipListItem[]; total: number }> {
  return api.get('/relationships/', { params: { type, limit: 100 } as Record<string, unknown> })
}
```

### Fetching Signals for Sidebar Badges
```typescript
// Source: backend/src/flywheel/api/signals.py — SignalsResponse shape

export interface TypeBadge {
  type: string
  label: string
  total_signals: number
  counts: {
    reply_received: number
    followup_overdue: number
    commitment_due: number
    stale_relationship: number
  }
}

export interface SignalsResponse {
  types: TypeBadge[]
  total: number
}

export function fetchSignals(): Promise<SignalsResponse> {
  return api.get('/signals/')
}

// Hook
export function useSignals() {
  const user = useAuthStore((s) => s.user)
  return useQuery({
    queryKey: queryKeys.signals.all,
    queryFn: fetchSignals,
    enabled: !!user,
    staleTime: 30_000,
  })
}
```

### Ask API Call with Source Attribution
```typescript
// Source: backend/src/flywheel/api/relationships.py — AskResponse shape

export interface AskResponse {
  answer: string
  sources: Array<{ source: string; content: string; date: string }>
  insufficient_context: boolean
}

export function askRelationship(id: string, question: string): Promise<AskResponse> {
  return api.post(`/relationships/${id}/ask`, { question })
}
```

### Route Registration (New Pages)
```typescript
// Source: frontend/src/app/routes.tsx — lazy loading pattern

const RelationshipListPage = lazy(() =>
  import('@/features/relationships/components/RelationshipListPage').then(
    (m) => ({ default: m.RelationshipListPage })
  )
)
const RelationshipDetail = lazy(() =>
  import('@/features/relationships/components/RelationshipDetail').then(
    (m) => ({ default: m.RelationshipDetail })
  )
)

// In AppRoutes:
<Route path="/relationships/prospects"  element={<Suspense fallback={null}><RelationshipListPage type="prospect" /></Suspense>} />
<Route path="/relationships/customers"  element={<Suspense fallback={null}><RelationshipListPage type="customer" /></Suspense>} />
<Route path="/relationships/advisors"   element={<Suspense fallback={null}><RelationshipListPage type="advisor" /></Suspense>} />
<Route path="/relationships/investors"  element={<Suspense fallback={null}><RelationshipListPage type="investor" /></Suspense>} />
<Route path="/relationships/:id"        element={<Suspense fallback={null}><RelationshipDetail /></Suspense>} />
```

### Sidebar RELATIONSHIPS Section
```typescript
// Source: frontend/src/features/navigation/components/AppSidebar.tsx — SidebarGroup pattern

import { Users, TrendingUp, Briefcase, DollarSign } from 'lucide-react'
import { useSignals } from '@/features/relationships/hooks/useSignals'

// Inside AppSidebar — add BEFORE the Pipeline SidebarMenuItem
const { data: signals } = useSignals()
const signalByType = (type: string) =>
  signals?.types.find((t) => t.type === type)?.total_signals ?? 0

// SidebarGroup with label:
<SidebarGroup>
  <SidebarGroupLabel style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--secondary-text)' }}>
    Relationships
  </SidebarGroupLabel>
  <SidebarGroupContent>
    <SidebarMenu>
      {[
        { type: 'prospect', label: 'Prospects', icon: Users, path: '/relationships/prospects' },
        { type: 'customer', label: 'Customers', icon: TrendingUp, path: '/relationships/customers' },
        { type: 'advisor', label: 'Advisors', icon: Briefcase, path: '/relationships/advisors' },
        { type: 'investor', label: 'Investors', icon: DollarSign, path: '/relationships/investors' },
      ].map(({ type, label, icon: Icon, path }) => {
        const badge = signalByType(type)
        return (
          <SidebarMenuItem key={type}>
            <SidebarMenuButton
              isActive={location.pathname.startsWith(path)}
              render={<NavLink to={path} />}
              tooltip={label}
            >
              <Icon className="size-4" />
              <span>{label}</span>
              {badge > 0 && (
                <span
                  className="badge-translucent ml-auto"
                  style={{ background: 'rgba(233,77,53,0.1)', color: 'var(--brand-coral)' }}
                >
                  {badge}
                </span>
              )}
            </SidebarMenuButton>
          </SidebarMenuItem>
        )
      })}
    </SidebarMenu>
  </SidebarGroupContent>
</SidebarGroup>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Accounts page as generic table | Relationship surfaces as typed card grids | Phase 57 | Type-aware UI; warm register background |
| No AI panel on detail pages | Left AI panel (320px) with synthesis + Q&A | Phase 57 | RAPI-07/08 now surfaced in UI |
| Pipeline sidebar item only | RELATIONSHIPS section header + 4 typed links + Pipeline below | Phase 57 | Sidebar reorg — Pipeline moves down |
| HTML table for accounts list | Card grid with BrandedCard | Phase 57 | Urgency-driven left border coloring |

**Deprecated/outdated:**
- `AccountsPage.tsx` and `AccountDetailPage.tsx`: These old `/accounts` routes will coexist until explicitly replaced. Do not remove them in Phase 57 — focus on the new `/relationships/*` routes only.

## Open Questions

1. **Commitments data source**
   - What we know: `RelationshipDetail.commitments` returns `[]` (reserved for future use per `relationships.py` line 94)
   - What's unclear: The Commitments tab spec requires two-column "What You Owe / What They Owe" with overdue highlighting — but there is no backend data yet
   - Recommendation: Render the two-column layout with an empty state ("No commitments tracked yet") — do not add a TODO spinner. The tab should exist but gracefully handle empty data.

2. **Intelligence tab data source**
   - What we know: `account.intel` is a `Record<string, unknown>` JSON field; the existing `IntelSidebar.tsx` shows generic key-value pairs
   - What's unclear: The Intelligence tab requires specific labeled fields (Pain, Budget, Competition, Champion, Blocker, Fit Reasoning) — these may not exist as structured keys in `account.intel`
   - Recommendation: Map known intel keys to labels; show a graceful placeholder for missing fields. Make fields editable via RAPI-03 (type update) or a future notes endpoint — scope editability as "click to add a note" for this phase.

3. **Detail page layout on mobile**
   - What we know: The spec requires a fixed 320px left AI panel + main area
   - What's unclear: 320px left panel is unusable on mobile (< 768px)
   - Recommendation: On mobile, collapse the AI panel below the tab area (stack vertically). Use `flex-col lg:flex-row` on the main layout container.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/api/relationships.py` — all RAPI endpoints, request/response schemas, partition contracts
- `backend/src/flywheel/api/signals.py` — SIG-01 endpoint, TypeBadge/SignalsResponse schemas, signal taxonomy
- `frontend/src/features/navigation/components/AppSidebar.tsx` — SidebarGroup/SidebarMenuItem/SidebarMenuButton pattern
- `frontend/src/features/accounts/components/AccountDetailPage.tsx` — detail page layout baseline
- `frontend/src/features/accounts/components/AccountsPage.tsx` — list page baseline
- `frontend/src/features/pipeline/hooks/useGraduate.ts` — query invalidation key pattern
- `frontend/src/components/ui/tabs.tsx` — Tabs primitive (line variant)
- `frontend/src/components/ui/branded-card.tsx` — card shadow + left border pattern
- `frontend/src/components/ui/avatar.tsx` — Avatar with xl (48px) size variant
- `frontend/src/components/ui/empty-state.tsx` — EmptyState component
- `frontend/src/lib/design-tokens.ts` — registers, shadows, badges, colors tokens
- `frontend/src/index.css` — CSS custom properties for brand-tint-warm, card-shadow, badge-translucent
- `frontend/src/app/routes.tsx` — lazy import + Suspense route registration pattern
- `.planning/phases/56-pipeline-grid/56-01-SUMMARY.md` — design system decisions (badge-translucent, registers, xl avatar)
- `.planning/phases/56-pipeline-grid/56-03-SUMMARY.md` — GraduationModal, useGraduate, entity-level auto-detection
- `.planning/phases/55-relationships-and-signals-apis/55-RESEARCH.md` — backend API architecture

### Secondary (MEDIUM confidence)
- Phase 57 prior decisions in roadmap: `fromType` URL param, query key factory, AI synthesis never auto-triggered, badge-translucent inline style pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in package.json and in active use
- Architecture: HIGH — backend APIs and existing component patterns verified from source code
- Pitfalls: HIGH — derived from code inspection of existing patterns and Phase 56 execution decisions
- Commitments tab: LOW — backend returns `[]`; UI spec exists but no backend data yet

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable — no fast-moving library upgrades anticipated)
