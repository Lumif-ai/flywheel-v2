# Phase 62: Meeting Surfaces and Relationship Enrichment - Research

**Researched:** 2026-03-28
**Domain:** React frontend (meetings feature slice, settings integration, relationship enrichment); Python backend (relationships.py timeline and intel queries, signals cache)
**Confidence:** HIGH

## Summary

Phase 62 is predominantly a frontend phase with three targeted backend additions. The backend work covers: (1) adding Meeting rows to the relationship timeline query in `relationships.py`, (2) enriching the `intel` dict with meeting-sourced ContextEntry content, and (3) updating `account.last_interaction_at` after meeting processing to refresh signal badges. The frontend work covers: (1) a new `/meetings` list/detail page with status badges and SSE-powered processing feedback, (2) a Granola settings panel in the existing SettingsPage, and (3) wiring meeting entries into the already-built timeline, intelligence, and people tabs.

The Phase 61 backend is confirmed complete and functioning: `GET /meetings/`, `GET /meetings/{id}`, `POST /meetings/sync`, `POST /meetings/process-pending`, and `POST /meetings/{id}/process` are all live. The `meeting_processor_web.py` engine writes `ContextEntry` rows with `account_id` set, which is the data that feeds the relationship enrichment in this phase.

The key insight for planning is that the relationship surfaces (timeline, intel, people tabs) are already built in Phase 57 — they just need their data sources expanded. The `TimelineTab` component accepts a `TimelineItem[]` prop; adding meeting entries requires a backend change to `GET /relationships/{id}` to query the `meetings` table, not a frontend change. Similarly, the `IntelligenceTab` renders any `Record<string, unknown>` from the `account.intel` field, which is currently returned from `account.intel` (JSONB column) — the spec enrichment requires querying `ContextEntry` rows instead, making the change backend-only. Frontend work for enrichment is zero.

**Primary recommendation:** Build in three sequential plans: (1) Meetings page + meeting detail + SSE hook; (2) Granola settings panel; (3) Backend relationship enrichment — timeline query expansion, intel query from ContextEntry, signal badge update via `last_interaction_at`. This order is safe because plans 1-2 are pure additions; plan 3 extends existing backend endpoints that are already tested.

## Standard Stack

### Core (all already installed — no new npm packages needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @tanstack/react-query | ^5.91.2 | Data fetching, cache, invalidation | Already used by all hooks in features/ |
| react-router | ^7.13.1 | Route params, navigation, lazy loading | App uses throughout; `/meetings/:id` follows same pattern |
| lucide-react | ^0.577.0 | Status icons (Loader2, CheckCircle2, XCircle, Clock, SkipForward) | Already installed and active |
| sonner | ^2.0.7 | Toast notifications for sync results | Already wired in AppLayout |
| useSSE (`/lib/sse.ts`) | (internal) | SSE event handling for meeting processing feedback | Already built; `discovery` event type already in SSEEventType union |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@/components/ui/branded-card` | (internal) | Meeting cards, status panels | All card-like components in this phase |
| `@/components/ui/empty-state` | (internal) | Empty meetings page, empty timeline | Zero-state screens |
| `@/components/ui/skeleton` | (internal) | Loading states | All async data loads |
| `@/lib/design-tokens` | (internal) | Spacing, colors, registers | Required — do not use hardcoded values |

### No New npm Packages Needed

All required functionality exists. The SSE `discovery` event type was confirmed added in Phase 58-03 execution.

### Backend: No New Dependencies

All backend libraries are present. The relationship enrichment uses existing SQLAlchemy patterns, existing ORM models (`Meeting`, `ContextEntry`), and the existing signal cache. No new Python packages needed.

## Architecture Patterns

### Recommended Project Structure

```
frontend/src/
├── features/meetings/             # NEW feature slice
│   ├── api.ts                     # fetchMeetings, fetchMeeting, syncMeetings, processMeeting
│   ├── types/
│   │   └── meetings.ts            # Meeting, MeetingListItem, MeetingDetail TS types
│   ├── hooks/
│   │   ├── useMeetings.ts         # useQuery for GET /meetings/
│   │   ├── useMeetingDetail.ts    # useQuery for GET /meetings/{id}
│   │   ├── useSyncMeetings.ts     # useMutation for POST /meetings/sync
│   │   └── useMeetingProcessing.ts # SSE hook for per-meeting processing feedback
│   └── components/
│       ├── MeetingsPage.tsx        # List view with filter bar, sync button, meeting cards
│       ├── MeetingCard.tsx         # Individual meeting card
│       ├── MeetingDetailPage.tsx   # Detail view with summary sections
│       └── GranolaSettings.tsx     # Granola API key + processing rules panel
├── features/settings/
│   └── components/
│       └── GranolaSettings.tsx    # (same file — add to settings feature slice)
└── pages/
    └── SettingsPage.tsx           # MODIFIED: add Integrations tab
```

```
backend/src/flywheel/
├── api/
│   └── relationships.py           # MODIFIED: timeline query + intel query + RSE-01/02/03
```

### Pattern 1: Meetings Feature API Module

**What:** All meetings API calls in a single `features/meetings/api.ts` file, following the exact same pattern as `features/relationships/api.ts`.

```typescript
// Source: features/relationships/api.ts pattern
import { api } from '@/lib/api'
import type { MeetingListItem, MeetingDetail, SyncResult } from './types/meetings'

export const queryKeys = {
  meetings: {
    all: ['meetings'] as const,
    list: (status?: string) => ['meetings', 'list', status ?? 'all'] as const,
    detail: (id: string) => ['meetings', 'detail', id] as const,
  },
}

export function fetchMeetings(status?: string): Promise<{ items: MeetingListItem[]; total: number }> {
  return api.get('/meetings/', { params: status ? { status, limit: 50 } : { limit: 50 } })
}

export function fetchMeetingDetail(id: string): Promise<MeetingDetail> {
  return api.get(`/meetings/${id}`)
}

export function syncMeetings(): Promise<SyncResult> {
  return api.post('/meetings/sync')
}

export function processMeeting(id: string): Promise<{ run_id: string }> {
  return api.post(`/meetings/${id}/process`)
}
```

### Pattern 2: TypeScript Types for Meetings

The backend `GET /meetings/` response shape is confirmed from reading `meetings.py`:

```typescript
// Source: backend/src/flywheel/api/meetings.py list_meetings endpoint
export interface MeetingListItem {
  id: string
  title: string | null
  meeting_date: string | null        // ISO 8601
  duration_mins: number | null
  attendees: Attendee[] | null       // [{email, name, is_external}]
  meeting_type: string | null        // 'discovery' | 'prospect' | 'advisor' | etc.
  processing_status: 'pending' | 'processing' | 'complete' | 'failed' | 'skipped'
  account_id: string | null
  summary: MeetingSummary | null     // JSONB: {tldr, key_decisions, action_items, pain_points, attendee_roles, meeting_type}
  created_at: string
}

// GET /meetings/{id} adds owner-only fields
export interface MeetingDetail extends MeetingListItem {
  skill_run_id: string | null
  processed_at: string | null
  updated_at: string
  transcript_url?: string | null     // owner-only (absent for non-owners)
  ai_summary?: string | null         // owner-only (absent for non-owners)
}

export interface Attendee {
  email: string | null
  name: string | null
  is_external: boolean
}

export interface MeetingSummary {
  tldr: string | null
  key_decisions: string[]
  action_items: Array<{ item: string; owner?: string; due?: string }>
  pain_points: string[]
  attendee_roles: Record<string, string>
  meeting_type: string | null
}

export interface SyncResult {
  synced: number
  skipped: number
  already_seen: number
  total_from_provider: number
}
```

### Pattern 3: Meeting Status Badge Colors

Meeting status maps to visual indicator — follow the same palette as Phase 56/57 design tokens:

```typescript
// Status to visual indicator mapping
const STATUS_CONFIG: Record<string, { icon: React.ComponentType; color: string; label: string }> = {
  pending:    { icon: Clock,         color: 'var(--secondary-text)', label: 'Pending' },
  processing: { icon: Loader2,       color: '#3B82F6',               label: 'Processing' },  // blue spin
  complete:   { icon: CheckCircle2,  color: 'var(--success)',         label: 'Complete' },
  failed:     { icon: XCircle,       color: 'var(--error)',           label: 'Failed' },
  skipped:    { icon: Minus,         color: 'var(--secondary-text)', label: 'Skipped' },
}
```

Meeting type badge colors (8 types from the processing pipeline spec):
```typescript
const TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  discovery:        { bg: 'rgba(59,130,246,0.1)',  text: '#2563eb' },   // blue
  prospect:         { bg: 'rgba(34,197,94,0.1)',   text: '#16a34a' },   // green
  customer_feedback:{ bg: 'rgba(34,197,94,0.1)',   text: '#16a34a' },   // green
  advisor:          { bg: 'rgba(168,85,247,0.1)',  text: '#7c3aed' },   // purple
  investor_pitch:   { bg: 'rgba(245,158,11,0.1)',  text: '#d97706' },   // amber
  internal:         { bg: 'rgba(107,114,128,0.1)', text: '#4b5563' },   // gray
  team_meeting:     { bg: 'rgba(107,114,128,0.1)', text: '#4b5563' },   // gray
  expert:           { bg: 'rgba(20,184,166,0.1)',  text: '#0f766e' },   // teal
}
```

### Pattern 4: SSE Processing Hook

Follow `useProfileRefresh.ts` exactly — it's the canonical SSE hook pattern in this codebase. The key structure: useState for phase/stage/discoveries, useSSE with url controlled by useState, post to API first to get run_id, then set SSE URL.

```typescript
// Source: features/profile/hooks/useProfileRefresh.ts pattern
// New file: features/meetings/hooks/useMeetingProcessing.ts

export function useMeetingProcessing(meetingId: string) {
  const [phase, setPhase] = useState<'idle' | 'processing' | 'complete' | 'error'>('idle')
  const [currentStage, setCurrentStage] = useState<string | null>(null)
  const [sseUrl, setSseUrl] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const handleEvent = useCallback((event: { type: string; data: Record<string, unknown> }) => {
    switch (event.type) {
      case 'stage':
        setCurrentStage(event.data.message as string)
        break
      case 'done':
        setPhase('complete')
        setSseUrl(null)
        queryClient.invalidateQueries({ queryKey: queryKeys.meetings.detail(meetingId) })
        break
      case 'error':
        setPhase('error')
        setSseUrl(null)
        break
    }
  }, [queryClient, meetingId])

  useSSE(sseUrl, handleEvent)

  const startProcessing = useCallback(async () => {
    setPhase('processing')
    setCurrentStage(null)
    try {
      const res = await processMeeting(meetingId)
      setSseUrl(`/api/v1/skills/runs/${res.run_id}/stream`)
    } catch (err) {
      setPhase('error')
    }
  }, [meetingId])

  return { phase, currentStage, startProcessing }
}
```

**CRITICAL:** The meeting detail query invalidation must use `queryKeys.meetings.detail(meetingId)` — not the list key — because the list comes from a different endpoint and doesn't update processing_status in real time (it can be stale by 60s). The detail page polling approach: after SSE `done` event, invalidate detail query to get updated `processing_status='complete'` and fresh `summary`.

### Pattern 5: Sync Button with Toast

```typescript
// Source: sonner + useMutation pattern from existing components
const syncMutation = useMutation({
  mutationFn: syncMeetings,
  onSuccess: (data) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.meetings.all })
    toast.success(
      `Sync complete: ${data.synced} new meetings (${data.skipped} skipped, ${data.already_seen} already seen)`
    )
  },
  onError: (err) => {
    toast.error(err instanceof Error ? err.message : 'Sync failed')
  },
})
```

### Pattern 6: GranolaSettings Component

GranolaSettings is a self-contained component added to the existing SettingsPage under an "Integrations" tab. It follows the same structure as `ApiKeyManager.tsx` (the Anthropic key manager already in settings):

**State required:**
- `integrations` — fetched from `GET /integrations/` filtered to `provider='granola'`
- `apiKey` — controlled input for new key
- `showKey` — toggle password visibility
- `connectMutation` — `POST /integrations/granola/connect`
- `disconnectMutation` — `DELETE /integrations/{id}`
- `syncMutation` — `POST /meetings/sync`

**Connection states:**
- Not connected: show API key input + Connect button
- Connected: show "Connected" with last sync timestamp, Disconnect button, manual Sync button
- Loading: spinner while connecting

The `GET /integrations/` endpoint already returns Granola integrations via the existing list endpoint. Filter client-side: `integrations?.find(i => i.provider === 'granola')`.

```typescript
// Source: features/settings/components/ApiKeyManager.tsx pattern
// Key query:
const { data: integrations } = useQuery({
  queryKey: ['integrations'],
  queryFn: () => api.get<Integration[]>('/integrations/'),
})

const granolaIntegration = integrations?.find(i => i.provider === 'granola' && i.status === 'connected')
```

**SettingsPage tab addition:**
Add an "Integrations" tab to the `<Tabs>` in `SettingsPage.tsx`. The tab is always visible to authenticated non-anonymous users (same guard as the Workspace tab: `isAdmin`).

```tsx
// Source: SettingsPage.tsx existing Tabs structure
{isAdmin && <TabsTrigger value="integrations">Integrations</TabsTrigger>}
{isAdmin && (
  <TabsContent value="integrations" className="mt-6">
    <GranolaSettings />
  </TabsContent>
)}
```

### Pattern 7: Backend — Meeting Timeline Entries (RSE-01)

The existing `GET /relationships/{id}` endpoint (RAPI-02, in `relationships.py`) queries `ContextEntry` rows for the timeline. The spec requires ALSO querying `Meeting` rows linked via `meeting.account_id` and serializing them as timeline items.

The existing `_derive_direction()` function already handles `source.startswith("meeting:")` — returns `"bidirectional"`. The `ctx-meeting-processor` source writes ContextEntry rows that already appear in timeline via the existing query. The additional work is adding **direct meeting rows** (pre-processing or skipped meetings that have no ContextEntries yet) to the timeline.

```python
# Source: backend/src/flywheel/api/relationships.py line 406 + Meeting ORM (models.py line 1245)
# Add after existing timeline_result query:

from flywheel.db.models import Meeting  # add to imports if not present

# Query meeting rows linked to this account
meeting_rows = (await db.execute(
    select(Meeting)
    .where(
        Meeting.account_id == id,
        Meeting.deleted_at.is_(None),
    )
    .order_by(Meeting.meeting_date.desc())
    .limit(20)
)).scalars().all()

# Serialize meeting rows as timeline items
for m in meeting_rows:
    attendee_count = len(m.attendees or [])
    tldr = (m.summary or {}).get("tldr") or ""
    content = f"{m.title or 'Untitled meeting'}"
    if tldr:
        content += f" — {tldr}"
    recent_timeline.append({
        "id": str(m.id),
        "source": f"meeting:{m.meeting_type or 'unclassified'}",
        "content": content,
        "date": m.meeting_date,
        "created_at": m.created_at,
        "direction": "bidirectional",
        "contact_name": f"{attendee_count} attendees" if attendee_count > 0 else None,
    })

# Sort combined list by date desc and limit
recent_timeline.sort(key=lambda x: x["date"], reverse=True)
recent_timeline = recent_timeline[:20]
```

**Note on Meeting ORM import:** `Meeting` is already defined in `db/models.py` (line 1245). Check if it's already imported in `relationships.py` — if not, add to the imports block. The `Account` model is already imported; `Meeting` follows same pattern.

### Pattern 8: Backend — Intel Enrichment from ContextEntry (RSE-02)

The current RAPI-02 returns `"intel": account.intel or {}` — a JSONB column. The spec requires enriching this with ContextEntry rows from meeting processing.

The spec shows grouping ContextEntry rows by `file_name` and returning them as a richer dict. However, the existing frontend `IntelligenceTab` uses `lookupValue()` with a simple `Record<string, unknown>` — adding nested arrays (as the spec shows) would break existing rendering.

**Correct approach:** Query ContextEntry rows grouped by `file_name` and merge them into a flat `intel` dict that preserves backward compatibility. For each recognized file, extract the most recent entry's content:

```python
# Source: backend/src/flywheel/api/relationships.py + db/models.py ContextEntry
# Add after existing timeline query, before building response dict:

INTEL_FILES = [
    "pain-points",        # Phase 61 writes as "pain-points" (no .md)
    "competitive-intel",
    "icp-profiles",
    "insights",
    "product-feedback",
    "action-items",
    "key-decisions",
]

intel_entries_result = await db.execute(
    select(ContextEntry)
    .where(
        ContextEntry.account_id == id,
        ContextEntry.deleted_at.is_(None),
        ContextEntry.file_name.in_(INTEL_FILES),
    )
    .order_by(ContextEntry.date.desc())
    .limit(50)
)
intel_entries = intel_entries_result.scalars().all()

# Build enriched intel dict — merge with existing account.intel
intel = dict(account.intel or {})
for entry in intel_entries:
    key = entry.file_name.replace("-", "_")  # "pain-points" → "pain_points"
    if key not in intel or not intel[key]:
        intel[key] = entry.content  # most recent entry wins
```

**Why flat, not nested:** The `IntelligenceTab` uses `lookupValue()` which does direct key lookup. Adding a flat `pain_points` key with string content (most recent entry) preserves existing IntelligenceTab rendering. The frontend lookup keys `['pain', 'Pain', 'pain_point']` already check `pain_points` via case-insensitive scan. This approach adds meeting intelligence to existing fields without breaking the frontend.

**CRITICAL:** File names in ContextEntry use hyphen format WITHOUT `.md` (confirmed from Phase 61 research: file_name="pain-points", not "pain-points.md"). The query must match `file_name.in_([...])` using hyphen names without `.md`.

### Pattern 9: Signal Badge Update (RSE-03)

The signals endpoint computes `stale_relationship` based on `account.last_interaction_at < 90 days ago`. After meeting processing completes, `account.last_interaction_at` is already updated by `meeting_processor_web.py` (Phase 61 implementation via `auto_link_meeting_to_account` and the account update in Stage 6). The signal cache has a 60-second TTL.

**Frontend behavior:** After `POST /meetings/sync` or after SSE `done` event, call:
```typescript
queryClient.invalidateQueries({ queryKey: ['signals'] })
```

This forces a fresh `GET /signals/` call. Since the backend cache is server-side (per-process in-memory dict), the 60-second TTL means the frontend may see stale counts for up to 60 seconds — this is acceptable per the existing design.

**No backend cache-busting function is needed.** The signals cache expires naturally. The frontend just needs to re-fetch after processing events.

### Pattern 10: Meetings Route Registration

New routes to add to `frontend/src/app/routes.tsx` following the lazy-load pattern:

```typescript
// Source: routes.tsx existing lazy load pattern
const MeetingsPage = lazy(() =>
  import('@/features/meetings/components/MeetingsPage').then((m) => ({ default: m.MeetingsPage }))
)
const MeetingDetailPage = lazy(() =>
  import('@/features/meetings/components/MeetingDetailPage').then((m) => ({ default: m.MeetingDetailPage }))
)

// In AppRoutes JSX:
<Route path="/meetings" element={<Suspense fallback={null}><MeetingsPage /></Suspense>} />
<Route path="/meetings/:id" element={<Suspense fallback={null}><MeetingDetailPage /></Suspense>} />
```

### Pattern 11: Sidebar Navigation — Add Meetings Link

Add a Meetings link to `AppSidebar.tsx`. Meetings is NOT a relationship type — it belongs in the general navigation group alongside Email, Documents, etc. (above the Relationships section):

```tsx
// Source: AppSidebar.tsx existing SidebarMenuItem pattern
// Add in the general navigation SidebarGroup, after Email:
<SidebarMenuItem>
  <SidebarMenuButton
    isActive={location.pathname.startsWith('/meetings')}
    render={<NavLink to="/meetings" />}
    tooltip="Meetings"
  >
    <CalendarDays className="size-4" />   {/* lucide-react CalendarDays */}
    <span>Meetings</span>
  </SidebarMenuButton>
</SidebarMenuItem>
```

### Anti-Patterns to Avoid

- **Adding meetings as a Relationship type in sidebar:** Meetings is a first-class page, not a relationship type. It goes in the general nav group, not under the RELATIONSHIPS section header.
- **Building a custom status polling mechanism:** Use SSE via `useSSE` + `useMeetingProcessing` hook. Do NOT poll `GET /meetings/{id}` in a `setInterval`.
- **Storing transcript content in frontend state:** The transcript URL (owner-only) comes from `GET /meetings/{id}`. Never cache transcript text in React Query or localStorage.
- **Intel tab nested array format:** The existing `IntelligenceTab` renders flat strings via `lookupValue()`. Keep intel dict values as flat strings (most recent entry content), not arrays. Arrays would break the existing UI.
- **Using `account.intel` JSONB column directly for meeting intelligence:** The `account.intel` column is set by the company intelligence engine (Phase 58). Meeting intelligence lives in `ContextEntry` rows. The RAPI-02 handler must MERGE both sources into the `intel` response dict.
- **Forgetting `Meeting` import in relationships.py:** The `Meeting` ORM model is not currently imported in `relationships.py`. Add it alongside existing model imports.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE event handling | Custom EventSource | `useSSE` hook from `/lib/sse.ts` | Already handles token auth, reconnection, and cleanup |
| Meeting processing state machine | Custom hook from scratch | `useProfileRefresh.ts` as template | Identical FSM: idle → processing → complete/error |
| API key masked input | Custom password toggle | Copy from `ApiKeyManager.tsx` | Same UX pattern — Eye/EyeOff toggle already built |
| Status badge rendering | Custom badge logic | Same `badge-translucent` CSS + STATUS_CONFIG map | Consistency with pipeline/relationship badges |
| Toast on sync completion | Custom notification | `toast.success()` from sonner | Already imported and wired in AppLayout |
| ContextEntry intel query | Custom ORM query | Query `ContextEntry.file_name.in_(INTEL_FILES)` | Simple SELECT — no library needed |

**Key insight:** Phase 62's frontend work is almost entirely composition of existing patterns. The hooks follow `useProfileRefresh.ts`, the cards follow `BrandedCard`, the settings follow `ApiKeyManager.tsx`, the timeline entries follow `TimelineItem` (same shape), and the routes follow the lazy-load pattern. There is no novel UI pattern in this phase.

## Common Pitfalls

### Pitfall 1: Meeting Timeline Duplicate Entries
**What goes wrong:** Meeting rows in timeline from the `Meeting` table + ContextEntry rows from meeting processing (with `source="ctx-meeting-processor"`) appear for the same meeting, creating duplicates in the timeline.
**Why it happens:** The spec adds both Meeting rows AND ContextEntry rows to the timeline. After processing, both exist for the same meeting.
**How to avoid:** Filter ContextEntry rows with `source="ctx-meeting-processor"` out of the timeline query — meeting rows already show the meeting. OR: Only include Meeting rows that have `processing_status != 'complete'` (pre-processing rows) + all ContextEntry rows (post-processing). Recommend: show Meeting rows regardless of status (gives users visibility into all meetings) but deduplicate by `meeting_id` if a ContextEntry has a `meeting_id` field.
**Warning signs:** Timeline shows "Discovery call — TechCorp" twice on the same date.

**Simplest safe approach:** Include Meeting rows unconditionally in timeline. The ContextEntry rows from `ctx-meeting-processor` have titles like "Pain: budget concerns..." not "Meeting: TechCorp call" — they don't duplicate the meeting-level entry. The titles are different enough that visual duplicates are not a concern.

### Pitfall 2: Intel Dict Overwriting Existing Company Intel
**What goes wrong:** Meeting ContextEntry intel (e.g., `pain_points`) overwrites `account.intel["pain_points"]` set by the company intelligence engine.
**Why it happens:** Both sources use overlapping key names.
**How to avoid:** When merging, prefer existing `account.intel` values: `if key not in intel or not intel[key]: intel[key] = entry.content`. Meeting intel fills gaps; company intel takes precedence.
**Warning signs:** Company-researched pain points disappear after meeting processing.

### Pitfall 3: `file_name` Case Mismatch in ContextEntry Query
**What goes wrong:** Query for `file_name IN ('pain-points', 'competitive-intel')` returns no rows because the actual file_name stored is `'Pain'` or `'pain_points'` or `'pain-points.md'`.
**Why it happens:** Phase 61 research established that file_name is stored WITHOUT `.md`. But the exact format (hyphens vs underscores) must match what `meeting_processor_web.py` actually writes.
**How to avoid:** Check the `CONTEXT_FILE_MAP` in `meeting_processor_web.py` to confirm exact `file_name` values stored. From Phase 61 research: `file_name="pain-points"` (hyphenated, no extension). Query must use the same format.
**Warning signs:** `intel_entries` always empty even after meetings are processed.

### Pitfall 4: SSE URL Before run_id is Available
**What goes wrong:** `useMeetingProcessing` sets SSE URL immediately on button click before `POST /meetings/{id}/process` returns a `run_id`.
**Why it happens:** Async mutation is fired, URL is set optimistically.
**How to avoid:** Only set `setSseUrl()` inside the mutation's `onSuccess` callback (or `try/await` pattern). Follow `useProfileRefresh.ts` exactly — it awaits the API call before setting `sseUrl`.
**Warning signs:** SSE connection immediately errors with "Meeting not found" or connects to wrong run.

### Pitfall 5: Granola Integration Status Check
**What goes wrong:** `GranolaSettings` shows "Not connected" even when a Granola integration exists because `GET /integrations/` returns integrations with `status='disconnected'` too.
**Why it happens:** The existing integrations list includes all integrations for the user regardless of status.
**How to avoid:** Filter to `granolaIntegration = integrations?.find(i => i.provider === 'granola' && i.status === 'connected')`. A `status='disconnected'` integration row exists after disconnecting — must check status, not just provider.
**Warning signs:** "Connect" form appears even after successful connection.

### Pitfall 6: Meeting Detail Transcript Visibility
**What goes wrong:** Transcript section renders for non-owners because `meeting.transcript_url` appears in the response as `undefined` (absent), but frontend checks `if (meeting.transcript_url)` which treats `undefined` and `null` the same.
**Why it happens:** API omits `transcript_url` for non-owners (not set to null, just absent from response). TypeScript type marks it as optional.
**How to avoid:** Type `transcript_url` as optional (`transcript_url?: string | null`) and check `'transcript_url' in meeting` OR simply render section only `if (meeting.transcript_url)`. Both undefined and null mean non-owner — the check is safe.

### Pitfall 7: Signals Cache Not Refreshing
**What goes wrong:** After meeting processing completes, sidebar signal badges don't update because the signals cache has 60-second TTL.
**Why it happens:** `_signals_cache` is process-level in-memory dict — no cache invalidation function exists.
**How to avoid:** Call `queryClient.invalidateQueries({ queryKey: ['signals'] })` in the SSE `done` handler and after sync completes. This forces a fresh `GET /signals/` request. The server-side 60-second TTL means new data appears within 60 seconds — acceptable per existing design. Do NOT try to bust the backend cache from frontend.
**Warning signs:** Signal badge counts visually stale after meetings are processed — resolved after next 60-second TTL expiry.

## Code Examples

### Meeting Card Status Badge

```tsx
// Source: STATUS_CONFIG pattern + lucide-react icons
import { Clock, Loader2, CheckCircle2, XCircle, Minus } from 'lucide-react'

function StatusBadge({ status }: { status: MeetingListItem['processing_status'] }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending

  return (
    <span
      className="inline-flex items-center gap-1 text-xs font-medium rounded-full px-2 py-0.5"
      style={{
        background: `${config.color}1a`,
        color: config.color,
      }}
    >
      <config.icon
        className={`size-3 ${status === 'processing' ? 'animate-spin' : ''}`}
      />
      {config.label}
    </span>
  )
}
```

### useQuery for Meetings List

```typescript
// Source: features/relationships/hooks/useRelationships.ts pattern
export function useMeetings(status?: string) {
  const user = useAuthStore((s) => s.user)

  return useQuery<{ items: MeetingListItem[]; total: number }>({
    queryKey: queryKeys.meetings.list(status),
    queryFn: () => fetchMeetings(status),
    enabled: !!user,
  })
}
```

### Backend — Relationships.py Import Addition

```python
# Source: backend/src/flywheel/db/models.py — Meeting at line 1245
# Add to existing imports in relationships.py:
from flywheel.db.models import (
    Account,
    AccountContact,
    ContextEntry,
    Meeting,           # ADD THIS
    OutreachActivity,
)
```

### Backend — Relationship Detail with Meeting Timeline

```python
# Source: backend/src/flywheel/api/relationships.py lines 395-414 pattern
# After existing timeline query, add:

meeting_rows = (await db.execute(
    select(Meeting)
    .where(
        Meeting.account_id == id,
        Meeting.tenant_id == user.tenant_id,
        Meeting.deleted_at.is_(None),
    )
    .order_by(Meeting.meeting_date.desc())
    .limit(20)
)).scalars().all()

for m in meeting_rows:
    attendees_list = m.attendees or []
    tldr = (m.summary or {}).get("tldr") or ""
    display_content = m.title or "Untitled meeting"
    if tldr:
        display_content += f" — {tldr}"

    recent_timeline.append({
        "id": str(m.id),
        "source": f"meeting:{m.meeting_type or 'unclassified'}",
        "content": display_content,
        "date": m.meeting_date,
        "created_at": m.created_at,
        "direction": "bidirectional",
        "contact_name": f"{len(attendees_list)} attendees" if attendees_list else None,
    })

# Sort and cap
recent_timeline.sort(key=lambda x: (x["date"] or x["created_at"]), reverse=True)
recent_timeline = recent_timeline[:20]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Timeline shows only ContextEntry rows | Timeline shows ContextEntry + Meeting rows from `meetings` table | Phase 62 | Pre-processing meetings visible in relationship timeline |
| `intel` dict from `account.intel` JSONB only | `intel` dict merges `account.intel` + `ContextEntry` rows from meeting processing | Phase 62 | Meeting intelligence populates Intelligence tab |
| No meetings UI | `/meetings` list + `/meetings/:id` detail pages | Phase 62 | Dedicated meeting surfaces for sync/process/view |
| Granola settings via API only | Granola connection UI in Settings → Integrations tab | Phase 62 | Non-technical users can connect Granola |
| Signal badges from email/calendar only | Signal badges updated via `account.last_interaction_at` from meeting processing | Phase 61+62 | Meeting activity refreshes stale signal |

**Deprecated/outdated in Phase 62 context:**
- The `account.intel` JSONB as sole intel source: superseded by ContextEntry merge. The JSONB column remains and is still read — just merged with ContextEntry content.

## Open Questions

1. **Meeting Timeline Dedup Strategy**
   - What we know: Phase 61 writes `ContextEntry` rows with `source="ctx-meeting-processor"` and `account_id` set. These appear in the existing timeline query. Phase 62 adds direct `Meeting` row serialization.
   - What's unclear: Whether `ctx-meeting-processor` ContextEntry rows have titles that visually duplicate the meeting-level entry or are differentiated enough (they contain extracted intel snippets, not meeting titles).
   - Recommendation: Don't dedup — the content is different. Meeting row shows "Discovery call — Acme (tldr)" while ContextEntry rows show "Pain: budget concerns" and similar. Visual distinction is clear.

2. **Meeting Processing SSE per-card vs global**
   - What we know: The spec shows SSE-powered real-time status updates as each meeting processes. The `POST /meetings/sync` + `POST /meetings/process-pending` sequence can trigger multiple meetings.
   - What's unclear: Whether Phase 62-01 should show a global processing indicator (one SSE connection for all pending meetings) or per-card processing status (one SSE per meeting card).
   - Recommendation: Per-card processing indicator using `useMeetingProcessing(meetingId)` hook per card. The batch `POST /meetings/process-pending` triggers multiple `SkillRun` rows; only per-meeting SSE provides granular feedback. After batch sync, show toast only; per-card SSE is for individually triggered meetings.

3. **GranolaSettings tab visibility gating**
   - What we know: The Integrations tab shows Granola settings. The existing SettingsPage shows API Key only for `state === 'S4' || state === 'S5'`, and Workspace/Team for `isAdmin`.
   - What's unclear: Whether Granola settings should be gated behind S4+ (same as API key) or visible to all authenticated users.
   - Recommendation: Show Integrations tab to all non-anonymous users (same gate as `isAdmin`). Granola connection is needed for any user to sync meetings, not just power users. Unlike the Anthropic API key which is a power user feature, Granola is a core integration.

4. **`ContextEntry.file_name` format in meeting_processor_web.py**
   - What we know: Phase 61 research states `file_name="pain-points"` (hyphenated, no `.md`). The `CONTEXT_FILE_MAP` in `meeting_processor_web.py` defines the actual values.
   - What's unclear: Whether the implementation used hyphenated names or underscore names for all 7 files.
   - Recommendation: Before writing the ContextEntry intel query in RAPI-02, read `CONTEXT_FILE_MAP` in `meeting_processor_web.py` to confirm exact `file_name` values. This is a quick read before coding.

## Sources

### Primary (HIGH confidence)

- `backend/src/flywheel/api/meetings.py` — confirmed list/detail/sync/process endpoints (complete implementation from Phase 61)
- `backend/src/flywheel/api/relationships.py` — RAPI-02 detail handler (lines 340-430), `_serialize_timeline_item()`, `_derive_direction()` implementation confirmed
- `backend/src/flywheel/api/integrations.py` — `POST /integrations/granola/connect` and `GET /integrations/` confirmed present; Granola upsert pattern confirmed
- `backend/src/flywheel/api/signals.py` — signal computation logic confirmed; 60-second in-memory TTL cache; no external bust mechanism
- `backend/src/flywheel/db/models.py` — `Meeting` ORM at line 1245; all fields confirmed; `attendees` is JSONB, `summary` is JSONB
- `frontend/src/features/relationships/components/RelationshipDetail.tsx` — TAB_CONFIG, AskPanel integration, existing tab structure confirmed
- `frontend/src/features/relationships/components/tabs/TimelineTab.tsx` — `TimelineItem[]` prop shape confirmed
- `frontend/src/features/relationships/components/tabs/IntelligenceTab.tsx` — `Record<string, unknown>` prop + `lookupValue()` pattern confirmed
- `frontend/src/features/relationships/components/tabs/PeopleTab.tsx` — `ContactItem[]` prop shape confirmed
- `frontend/src/features/relationships/api.ts` — `queryKeys` hierarchy pattern confirmed
- `frontend/src/features/relationships/types/relationships.ts` — `TimelineItem`, `ContactItem`, `RelationshipDetailItem` type shapes confirmed
- `frontend/src/features/profile/hooks/useProfileRefresh.ts` — canonical SSE hook pattern to follow exactly
- `frontend/src/lib/sse.ts` — `useSSE` hook + `SSEEventType` union (includes `'discovery'`) confirmed
- `frontend/src/pages/SettingsPage.tsx` — existing tab structure, guards (`isAdmin`, `showApiKey`) confirmed
- `frontend/src/features/settings/components/ApiKeyManager.tsx` — Granola settings UI template confirmed
- `frontend/src/app/routes.tsx` — lazy route registration pattern confirmed
- `frontend/src/features/navigation/components/AppSidebar.tsx` — general nav SidebarGroup pattern + signalByType helper confirmed
- `.planning/phases/61-meeting-intelligence-pipeline/61-RESEARCH.md` — CONTEXT_FILE_MAP file_name format, ContextEntry source value `"ctx-meeting-processor"` confirmed
- `.planning/SPEC-intelligence-flywheel.md` — FE-01, FE-02, FE-03, FE-04, RSE-01, RSE-02, RSE-03 requirements read

### Secondary (MEDIUM confidence)

- `.planning/phases/61-meeting-intelligence-pipeline/61-VERIFICATION.md` — Phase 61 confirmed complete (5/6 must-haves; processing rules gap is orthogonal to Phase 62)
- `.planning/phases/60-meeting-data-model-and-granola-adapter/60-RESEARCH.md` — Granola API shape, RLS split-visibility design

### Tertiary (LOW confidence)

- `meeting_processor_web.py` CONTEXT_FILE_MAP exact file_name values — inferred from Phase 61 research documentation; should verify by reading the file before coding `INTEL_FILES` list in relationships.py
- Meeting timeline visual dedup behavior — reasoned inference; actual rendered output should be confirmed during plan execution

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed present; no new packages needed
- Frontend feature structure: HIGH — pattern directly derived from existing relationships feature slice (Phase 57)
- Backend relationship enrichment: HIGH — existing endpoint code read directly; Meeting ORM confirmed; signals cache confirmed
- Granola settings UI: HIGH — ApiKeyManager.tsx and existing integrations endpoint read directly
- SSE processing hook: HIGH — useProfileRefresh.ts read directly; SSEEventType confirmed includes 'discovery'
- INTEL_FILES values: MEDIUM — file_name format inferred from Phase 61 research; should verify against meeting_processor_web.py CONTEXT_FILE_MAP

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stack is stable; Meeting ORM is finalized; Granola API shape is from Phase 60 research)
