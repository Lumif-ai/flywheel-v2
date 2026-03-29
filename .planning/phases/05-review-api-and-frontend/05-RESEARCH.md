# Phase 5: Review API and Frontend - Research

**Researched:** 2026-03-24
**Domain:** FastAPI list/detail endpoints + React virtual scrolling + in-app alerts + Zustand store
**Confidence:** HIGH (codebase directly examined; external libraries verified via Context7/official docs)

---

## Summary

Phase 5 builds the Email inbox: a prioritized thread list, per-thread score detail, and one-tap approve/edit/dismiss
for drafts. The backend already has the three draft lifecycle endpoints (approve/dismiss/edit) in `api/email.py`.
What is new is (a) the read-side API — GET threads, GET thread detail, GET digest, POST manual sync — and (b) the
entire frontend: EmailPage, ThreadList with virtual scrolling, ThreadCard, DraftReview, Zustand store, React Query
hooks, and in-app critical-email alerts.

The frontend stack is already decided: React 19, TanStack Query v5, Zustand v5, Tailwind v4 (via `@tailwindcss/vite`),
Lucide icons, and the project's own `BrandedCard` / `design-tokens` system. Nothing in this phase requires a new UI
framework. Virtual scrolling requires adding `@tanstack/react-virtual`. In-app alerts are best served by Sonner
(shadcn's blessed toast library for v4 projects), which is not yet installed. The `@tailwindcss/typography` concern
flagged in STATE.md is a non-issue: the plugin supports Tailwind v4 via `@plugin "@tailwindcss/typography"` in CSS —
no JavaScript config needed. The project does not currently use this plugin at all, so no migration is required.

On the backend, thread grouping must be done in Python, not SQL, because the data model is message-level (emails
table) and thread priority is a read-time MAX query (`get_thread_priority()` in `gmail_sync.py`). The GET threads
endpoint must group emails by `gmail_thread_id`, compute thread priority per group, and return a sorted, paginated
list of thread summaries. Offset-based pagination is appropriate for this inbox (not cursor-based) because threads
are sorted by priority tier first, then recency, and the list is bounded by the inbox size.

**Primary recommendation:** Build the backend list/detail endpoints with manual grouping in Python + SQLAlchemy
async queries; use `@tanstack/react-virtual` for thread list virtualization; use Sonner for in-app alerts; follow
the existing `useBriefing` / `BrandedCard` patterns exactly.

---

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@tanstack/react-query` | 5.91.2 | Server state, caching, mutations | Already used throughout; `useBriefing` is the template |
| `zustand` | 5.0.12 | Client-only UI state (selected thread, expanded panel) | Already used for `useUIStore`, `useAuthStore` |
| `tailwindcss` | 4.2.2 | Utility CSS | Project standard; v4 via `@tailwindcss/vite` |
| `lucide-react` | 0.577.0 | Icons | Already the icon library; use `Mail`, `AlertCircle`, `CheckCircle2`, `Clock`, `ChevronRight` |
| FastAPI + SQLAlchemy async | existing | Backend API + DB queries | All existing API routes use this stack |

### New Dependencies Required
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `@tanstack/react-virtual` | ^3.x (latest v3) | Virtual scrolling for ThreadList | Only option that's headless, works with any DOM structure, zero config overhead. UI-05 requires it for 500+ threads. |
| `sonner` | ^1.x | In-app toasts for critical-email alerts (UI-04) | shadcn's recommended toast library for v4 projects; `shadcn add sonner` generates the themed `Toaster` wrapper |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@tanstack/react-virtual` | `react-window` | react-window requires fixed-size containers and is harder to integrate with the existing flex layout; TanStack Virtual is headless |
| `sonner` | Custom `Toast` component (already exists) | The existing `Toast` component is stateless and can only show one message at a time; it has no queue, no priority ordering, and no "dismiss" button — not suitable for persistent critical alerts |
| Offset pagination | Cursor/keyset | Cursor is faster at scale but the inbox is bounded (~500-2000 emails max) and priority-tier ordering makes cursor pagination complex; offset is fine here |

**Installation:**
```bash
# In frontend/
npm install @tanstack/react-virtual
npx shadcn@latest add sonner

# @tailwindcss/typography — only install if prose classes are needed for reasoning text rendering
# npm install -D @tailwindcss/typography  (and add @plugin "@tailwindcss/typography"; to index.css)
```

---

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/features/email/
├── components/
│   ├── EmailPage.tsx          # page shell: title bar, sync button, priority tier headers
│   ├── ThreadList.tsx         # useVirtualizer wrapper — the scroll container
│   ├── ThreadCard.tsx         # single thread row rendered inside virtualizer
│   ├── ThreadDetail.tsx       # slide-in panel or route: messages + scores + drafts
│   ├── DraftReview.tsx        # approve/edit/dismiss UI for a single draft
│   ├── DigestView.tsx         # daily digest of low-priority auto-filed emails
│   └── CriticalEmailAlert.tsx # Sonner toast trigger for priority-5 emails
├── hooks/
│   ├── useEmailThreads.ts     # useQuery: GET /email/threads
│   ├── useThreadDetail.ts     # useQuery: GET /email/threads/:threadId
│   ├── useDraftActions.ts     # useMutation: approve / dismiss / edit
│   ├── useDailyDigest.ts      # useQuery: GET /email/digest
│   └── useManualSync.ts       # useMutation: POST /email/sync
├── store/
│   └── emailStore.ts          # Zustand: selectedThreadId, detailOpen, alertDismissed
└── types/
    └── email.ts               # TypeScript interfaces: Thread, Message, Score, Draft
```

```
backend/src/flywheel/api/email.py  # extend existing file — add new routers here
```

### Pattern 1: Backend — Thread Grouping Query

The emails table is message-level, not thread-level. There is no `threads` table. Thread grouping is done in Python.

**What:** Query all emails for the tenant sorted by received_at DESC. Group by `gmail_thread_id`. For each thread
group, call (or inline) the `get_thread_priority()` logic to compute MAX(score) for unhandled messages.
Return one `ThreadSummary` per unique thread.

**When to use:** GET /email/threads endpoint.

**Example:**
```python
# Source: codebase gmail_sync.py lines 357-387; FastAPI async pattern from existing api/*.py
from sqlalchemy import select, func, text as sa_text
from flywheel.db.models import Email, EmailScore, EmailDraft

async def get_thread_list(
    db: AsyncSession,
    tenant_id: UUID,
    priority_min: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[ThreadSummary]:
    """
    Step 1: Fetch all emails with their scores in one query using a LEFT JOIN.
    Step 2: Group in Python by gmail_thread_id.
    Step 3: Compute thread priority as MAX(score.priority) where is_replied=False.
    Step 4: Sort by thread priority DESC, then most-recent received_at DESC.
    Step 5: Slice with offset/limit.
    """
    # Single query: emails + their scores + any pending drafts
    result = await db.execute(
        select(Email, EmailScore, EmailDraft)
        .outerjoin(EmailScore, EmailScore.email_id == Email.id)
        .outerjoin(
            EmailDraft,
            (EmailDraft.email_id == Email.id) & (EmailDraft.status == "pending"),
        )
        .where(Email.tenant_id == tenant_id)
        .order_by(Email.received_at.desc())
    )
    rows = result.all()
    # Group + compute in Python — see Architecture Pattern 2 for grouping logic
```

### Pattern 2: Backend — Thread Priority Computation (inline, no extra query)

Rather than calling `get_thread_priority()` per thread (N+1 queries), inline the MAX computation during Python
grouping after a single JOIN query.

```python
from collections import defaultdict
from dataclasses import dataclass, field

@dataclass
class ThreadAccumulator:
    thread_id: str
    subject: str | None
    sender_name: str | None
    sender_email: str
    latest_received_at: datetime
    messages: list[Email] = field(default_factory=list)
    max_priority: int | None = None
    has_pending_draft: bool = False
    draft_id: UUID | None = None

threads: dict[str, ThreadAccumulator] = {}
for email, score, draft in rows:
    tid = email.gmail_thread_id
    if tid not in threads:
        threads[tid] = ThreadAccumulator(
            thread_id=tid,
            subject=email.subject,
            sender_name=email.sender_name,
            sender_email=email.sender_email,
            latest_received_at=email.received_at,
        )
    acc = threads[tid]
    acc.messages.append(email)
    acc.latest_received_at = max(acc.latest_received_at, email.received_at)
    if score and not email.is_replied:
        acc.max_priority = max(acc.max_priority or 0, score.priority)
    if draft and draft.status == "pending":
        acc.has_pending_draft = True
        acc.draft_id = draft.id

# Sort: priority DESC (None last), then recency DESC
sorted_threads = sorted(
    threads.values(),
    key=lambda t: (-(t.max_priority or 0), -t.latest_received_at.timestamp()),
)
# Slice for pagination
page = sorted_threads[offset : offset + limit]
```

### Pattern 3: Frontend — useVirtualizer for ThreadList

**What:** Virtual scrolling that renders only ~10-20 DOM nodes regardless of how many threads exist.

**When to use:** ThreadList.tsx — the scrollable container for all threads.

```typescript
// Source: https://tanstack.com/virtual/latest/docs/framework/react/examples/fixed
import { useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'

interface ThreadListProps {
  threads: Thread[]
  onSelectThread: (threadId: string) => void
  selectedThreadId: string | null
}

export function ThreadList({ threads, onSelectThread, selectedThreadId }: ThreadListProps) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: threads.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,   // ThreadCard height in px — measure and set accurately
    overscan: 5,
    useFlushSync: false,      // React 19: suppress flushSync console warnings
  })

  return (
    <div
      ref={parentRef}
      className="overflow-auto flex-1"
      style={{ height: '100%' }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          position: 'relative',
          width: '100%',
        }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => (
          <div
            key={virtualRow.index}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualRow.size}px`,
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            <ThreadCard
              thread={threads[virtualRow.index]}
              isSelected={threads[virtualRow.index].thread_id === selectedThreadId}
              onSelect={onSelectThread}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
```

**Critical:** The scroll container must have a fixed height (not `height: auto`). It must be the element with
`overflow: auto`, not a parent. If the container grows with content, virtualization never activates.

### Pattern 4: Frontend — Zustand Email Store

```typescript
// Source: existing pattern from /frontend/src/stores/ui.ts
import { create } from 'zustand'

interface EmailState {
  selectedThreadId: string | null
  detailOpen: boolean
  alertDismissedIds: Set<string>   // priority-5 thread IDs already alerted
  selectThread: (id: string | null) => void
  closeDetail: () => void
  dismissAlert: (threadId: string) => void
}

export const useEmailStore = create<EmailState>((set) => ({
  selectedThreadId: null,
  detailOpen: false,
  alertDismissedIds: new Set(),
  selectThread: (id) => set({ selectedThreadId: id, detailOpen: !!id }),
  closeDetail: () => set({ detailOpen: false, selectedThreadId: null }),
  dismissAlert: (threadId) =>
    set((s) => ({
      alertDismissedIds: new Set([...s.alertDismissedIds, threadId]),
    })),
}))
```

### Pattern 5: Frontend — React Query Hooks

Follow the exact pattern from `useBriefing.ts`:

```typescript
// Source: /frontend/src/features/briefing/hooks/useBriefing.ts (project pattern)
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

// GET /email/threads
export function useEmailThreads(params?: { priority_min?: number; offset?: number; limit?: number }) {
  return useQuery({
    queryKey: ['email-threads', params],
    queryFn: () => api.get<ThreadListResponse>('/email/threads', { params }),
    staleTime: 30_000,
  })
}

// POST approve — optimistic update
export function useApproveDraft() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (draftId: string) =>
      api.post<DraftActionResponse>(`/email/drafts/${draftId}/approve`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['email-threads'] })
      qc.invalidateQueries({ queryKey: ['thread-detail'] })
    },
  })
}
```

**Note:** The `api` client in `/frontend/src/lib/api.ts` is missing a `put` method. Add it:
```typescript
put: <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
```

### Pattern 6: In-App Alert for Priority-5 Emails (Sonner)

```typescript
// Source: https://ui.shadcn.com/docs/components/radix/sonner
// In app/layout.tsx — add once to root
import { Toaster } from "@/components/ui/sonner"
// <Toaster position="top-right" />

// In CriticalEmailAlert.tsx — triggered when threads data arrives
import { toast } from "sonner"
import { useEffect } from "react"
import { useEmailStore } from '../store/emailStore'

export function CriticalEmailAlert({ threads }: { threads: Thread[] }) {
  const { alertDismissedIds, dismissAlert } = useEmailStore()

  useEffect(() => {
    const criticalThreads = threads.filter(
      (t) => t.max_priority === 5 && !alertDismissedIds.has(t.thread_id)
    )
    criticalThreads.forEach((thread) => {
      toast.warning(`Critical email: ${thread.subject ?? thread.sender_email}`, {
        id: thread.thread_id,          // deduplicate toasts
        duration: Infinity,            // stays until dismissed
        onDismiss: () => dismissAlert(thread.thread_id),
        action: {
          label: 'View',
          onClick: () => { /* navigate to /email?thread=... */ },
        },
      })
      dismissAlert(thread.thread_id)  // mark as alerted so re-renders don't re-toast
    })
  }, [threads, alertDismissedIds, dismissAlert])

  return null
}
```

### Pattern 7: Priority Tier Group Headers

The thread list groups threads by priority tier (5 = critical, 4 = high, 3 = medium, 1-2 = low). Group headers
are rendered as non-virtual rows inserted between tier boundaries.

**Implementation approach:** Flatten threads into a `FlatItem[]` array where each item is either a `{type: 'header', tier: number}` or `{type: 'thread', thread: Thread}`. Pass this flat array to useVirtualizer with `count: flatItems.length`. Each virtual row checks `flatItems[index].type` to render the right component. Header rows have a different `estimateSize` (40px vs 80px for thread cards).

For variable item heights (header vs thread), use `measureElement` callback or just provide an accurate `estimateSize` per-index:
```typescript
estimateSize: (index) => flatItems[index].type === 'header' ? 40 : 80,
```

### Anti-Patterns to Avoid

- **Thread grouping in SQL with GROUP BY:** The `emails` table has no stored `thread_priority` column (by design, SCORE-07). A SQL GROUP BY + subquery for MAX priority is possible but complex; Python grouping after a JOIN is simpler and performs adequately for inbox scale.
- **N+1 thread priority queries:** Do NOT call `get_thread_priority()` once per thread in a loop. Inline the MAX computation during Python grouping as shown in Pattern 2.
- **Virtual list with `height: auto` container:** useVirtualizer requires the scroll element to have a fixed or constrained height. An auto-height container means `getTotalSize()` always equals visible content height — no virtualization occurs.
- **Storing `alertDismissedIds` in Zustand with a plain array:** Use `Set<string>` for O(1) lookup. Serialize to/from localStorage if persistence across page loads is needed (not required for MVP).
- **Calling `toast()` on every re-render:** Always gate on `alertDismissedIds` before firing and immediately mark as alerted in the same effect pass.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Virtual scrolling | Custom windowed list with manual DOM management | `@tanstack/react-virtual` useVirtualizer | Scroll math, resize observation, overscan, dynamic sizing — all solved. Custom implementations miss edge cases (resize, scroll restoration, keyboard nav). |
| Toast notification system | Extend existing one-shot `Toast` component | Sonner via `shadcn add sonner` | The existing `Toast` cannot queue, deduplicate (by `id`), show `action` buttons, or persist until dismissed. Sonner handles all of these. |
| Thread grouping library | Custom groupBy utility | Python `collections.defaultdict` | Standard library, zero deps, readable. |
| Pagination | Custom cursor encoding | Offset/limit query params | Inbox size is bounded; offset is simple and correct for this use case. |

**Key insight:** The existing `Toast` component in the project is intentionally minimal (3-second auto-dismiss, no
queue, no actions). It is not a notification system — it is a feedback flash. Sonner fills the gap for persistent,
actionable alerts.

---

## Common Pitfalls

### Pitfall 1: N+1 Priority Queries
**What goes wrong:** Calling `get_thread_priority(db, tenant_id, thread_id)` once per thread in a Python loop
causes O(N) database round-trips for an N-thread inbox.
**Why it happens:** `get_thread_priority()` is a convenience function designed for Phase 4's sync loop (one call
per newly synced thread). It was never intended as a bulk read operation.
**How to avoid:** Use a single JOIN query (Email LEFT JOIN EmailScore) and compute MAX priority in Python grouping.
**Warning signs:** Response time scales linearly with inbox size.

### Pitfall 2: Virtual List Container Height
**What goes wrong:** ThreadList renders all threads in the DOM; virtual scrolling appears to do nothing.
**Why it happens:** The scroll container has `height: auto` or is inside a flex container without `flex: 1` and
explicit height. `useVirtualizer` reports `getTotalSize()` equal to actual content height — the container never
clips content.
**How to avoid:** Ensure the scroll container element has a fixed or flex-constrained height (`flex: 1`, `min-h-0`
on the parent chain) and `overflow: auto`.
**Warning signs:** DevTools shows 500+ `<div>` elements for a 500-thread inbox.

### Pitfall 3: Sonner Toast Deduplication
**What goes wrong:** Every time the `useEmailThreads` query refetches (every 30s), critical email alerts re-fire.
**Why it happens:** `useEffect` runs on every `threads` reference change; `toast()` is called again.
**How to avoid:** Use `toast()` with a stable `id: thread.thread_id`. Sonner silently deduplicates calls with the
same ID — it will not show a second toast if one with that ID is already visible. Combine with `alertDismissedIds`
in Zustand to suppress re-alerting after the user has dismissed.
**Warning signs:** Multiple toasts stacking for the same email on each poll cycle.

### Pitfall 4: Missing `put` Method on API Client
**What goes wrong:** The PUT /email/drafts/:id endpoint (edit draft) returns a runtime error when called from the
frontend because `api.put` does not exist.
**Why it happens:** The `api` client in `lib/api.ts` only defines `get`, `post`, `patch`, `delete` — no `put`.
**How to avoid:** Add `put` to the api client before building `useDraftActions.ts`.
**Warning signs:** `api.put is not a function` at runtime.

### Pitfall 5: Tailwind v4 Typography Plugin Confusion
**What goes wrong:** Developer adds `@tailwindcss/typography` but tries to configure it via `tailwind.config.js`,
which Tailwind v4 no longer reads. The plugin appears to not work.
**Why it happens:** Tailwind v4 uses CSS-first configuration. Plugins are registered via `@plugin` in CSS, not in
a JS config file.
**How to avoid:** If typography plugin is needed (e.g., for rendering email reasoning text as prose), add:
```css
/* in index.css, after @import "tailwindcss"; */
@plugin "@tailwindcss/typography";
```
No JS config file needed. The existing project does NOT use this plugin — assess whether it's actually needed
before adding it.
**Warning signs:** `prose` class has no effect; Tailwind generates no typography utilities.

### Pitfall 6: Thread Detail — Missing Context Refs Links
**What goes wrong:** `context_refs` field on EmailScore exists as JSONB but its structure is not defined in the
existing codebase. Rendering context reference links may require fetching context entries by ID.
**Why it happens:** The `context_refs` column is declared as `JSONB` with `server_default="'[]'::jsonb"` —
the shape of each ref object was left unspecified in Phase 3/4.
**How to avoid:** Inspect actual scored emails' `context_refs` values before building the UI. The likely shape is
`[{"entry_id": "...", "file_name": "...", "content_preview": "..."}]`. Confirm and type accordingly.
**Warning signs:** `context_refs.map(...)` fails because shape is wrong.

---

## Code Examples

Verified patterns from official sources and codebase:

### Backend: GET /email/threads Response Shape
```python
# Pydantic models for the new endpoints
class ThreadSummary(BaseModel):
    thread_id: str                  # gmail_thread_id
    subject: str | None
    sender_name: str | None
    sender_email: str
    latest_received_at: datetime
    message_count: int
    max_priority: int | None        # 1-5, None if unscored
    priority_tier: str              # "critical" | "high" | "medium" | "low" | "unscored"
    has_pending_draft: bool
    draft_id: str | None            # UUID of pending draft, if any
    is_read: bool

class ThreadListResponse(BaseModel):
    threads: list[ThreadSummary]
    total: int                      # total thread count (for pagination UI)
    offset: int
    limit: int

def priority_to_tier(p: int | None) -> str:
    if p is None: return "unscored"
    if p == 5: return "critical"
    if p == 4: return "high"
    if p == 3: return "medium"
    return "low"
```

### Backend: GET /email/threads/:threadId Detail Shape
```python
class MessageScore(BaseModel):
    priority: int
    category: str
    reasoning: str | None
    suggested_action: str | None
    context_refs: list[dict]

class MessageDetail(BaseModel):
    id: str
    gmail_message_id: str
    sender_email: str
    sender_name: str | None
    subject: str | None
    snippet: str | None
    received_at: datetime
    is_read: bool
    is_replied: bool
    score: MessageScore | None

class DraftDetail(BaseModel):
    id: str
    status: str                     # "pending" | "sent" | "dismissed"
    draft_body: str | None          # None after send (PII minimization)
    user_edits: str | None

class ThreadDetailResponse(BaseModel):
    thread_id: str
    subject: str | None
    messages: list[MessageDetail]
    draft: DraftDetail | None       # the pending draft for this thread, if any
    max_priority: int | None
    priority_tier: str
```

### Backend: POST /email/sync (manual trigger)
```python
# Source: existing pattern from api/integrations.py POST /{id}/sync
@router.post("/sync", response_model=SyncResponse)
async def trigger_gmail_sync(
    background_tasks: BackgroundTasks,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> SyncResponse:
    """Trigger a manual Gmail sync for the current user's gmail-read integration."""
    intg_result = await db.execute(
        select(Integration).where(
            and_(
                Integration.tenant_id == user.tenant_id,
                Integration.provider == "gmail-read",
                Integration.status == "connected",
            )
        )
    )
    integration = intg_result.scalars().first()
    if integration is None:
        raise HTTPException(status_code=400, detail="No Gmail read integration connected")

    # Run sync as background task — return immediately
    async def _run_sync():
        from flywheel.services.gmail_sync import sync_gmail
        async with get_tenant_session(user.tenant_id) as sync_db:
            await sync_gmail(sync_db, integration)

    background_tasks.add_task(_run_sync)
    return SyncResponse(message="Sync triggered", syncing=True)
```

### Frontend: TypeScript Interfaces
```typescript
// frontend/src/features/email/types/email.ts
export interface Thread {
  thread_id: string
  subject: string | null
  sender_name: string | null
  sender_email: string
  latest_received_at: string    // ISO 8601
  message_count: number
  max_priority: number | null
  priority_tier: 'critical' | 'high' | 'medium' | 'low' | 'unscored'
  has_pending_draft: boolean
  draft_id: string | null
  is_read: boolean
}

export interface ThreadListResponse {
  threads: Thread[]
  total: number
  offset: number
  limit: number
}

export interface Score {
  priority: number
  category: string
  reasoning: string | null
  suggested_action: string | null
  context_refs: Array<{ entry_id: string; file_name: string; content_preview?: string }>
}

export interface Message {
  id: string
  gmail_message_id: string
  sender_email: string
  sender_name: string | null
  subject: string | null
  snippet: string | null
  received_at: string
  is_read: boolean
  is_replied: boolean
  score: Score | null
}

export interface Draft {
  id: string
  status: 'pending' | 'sent' | 'dismissed'
  draft_body: string | null
  user_edits: string | null
}

export interface ThreadDetailResponse {
  thread_id: string
  subject: string | null
  messages: Message[]
  draft: Draft | null
  max_priority: number | null
  priority_tier: string
}
```

### Frontend: Priority Badge Component Pattern
```typescript
// Inline pattern — follow existing design-tokens approach
const TIER_COLORS: Record<string, string> = {
  critical: '#E94D35',
  high: '#F97316',
  medium: '#F59E0B',
  low: '#6B7280',
  unscored: '#9CA3AF',
}

function PriorityBadge({ tier, priority }: { tier: string; priority: number | null }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 8px',
        borderRadius: '9999px',
        fontSize: '12px',
        fontWeight: '600',
        color: TIER_COLORS[tier] ?? '#9CA3AF',
        backgroundColor: `${TIER_COLORS[tier] ?? '#9CA3AF'}18`,  // 10% opacity
      }}
    >
      P{priority ?? '?'}
    </span>
  )
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `react-window` (fixed-size lists) | `@tanstack/react-virtual` (headless) | No fixed-container requirement; works with any DOM structure |
| `react-toastify` / `notistack` | Sonner | Smaller bundle, matches shadcn theming, React 19 compatible |
| Tailwind plugin via JS config | `@plugin` in CSS (`index.css`) | Tailwind v4 — no JS config file at all |
| `useMutation` then manual `setState` | `useMutation` + `queryClient.invalidateQueries` | React Query handles server state; no manual state sync needed |

**Deprecated/outdated in this project's context:**
- `tailwind.config.js`: Tailwind v4 does not read it; configuration is CSS-first
- The existing one-shot `Toast` component: adequate for feedback flashes, not for persistent alerts

---

## Open Questions

1. **`context_refs` shape in EmailScore**
   - What we know: Declared as JSONB, default `[]`. Phase 3/4 scorer may populate it.
   - What's unclear: Exact keys in each ref object (entry_id? file_name? snippet?).
   - Recommendation: Before building ThreadDetail, query the DB for any existing `email_scores.context_refs`
     values. If the column is empty (no emails scored yet), define the shape in the scorer output and document
     it in the Pydantic response model.

2. **GET /email/digest — what is "daily digest"?**
   - What we know: UI-05 requires "daily digest of low-priority emails that were auto-filed/archived".
   - What's unclear: Are priority 1-2 emails auto-archived, or is this a separate workflow? Is the digest
     an aggregation by day, or a snapshot of today's low-priority emails?
   - Recommendation: Define digest as "today's emails with priority 1-2, grouped by category". Simple
     SELECT with date filter and priority <= 2. No separate archival workflow needed for Phase 5.

3. **Thread detail — slide-in panel vs separate route?**
   - What we know: No decision made. Both patterns exist in the app (sheets, modals, separate pages).
   - Recommendation: Use a slide-in panel (Sheet component from `/components/ui/sheet.tsx`) rather than a
     separate route. This keeps the thread list visible and active, which is the standard inbox UX pattern.
     The selected thread ID lives in Zustand (`emailStore.selectedThreadId`).

4. **Manual sync — `BackgroundTasks` vs direct async call?**
   - What we know: The sync loop (`email_sync_loop`) runs as a background asyncio task in main.py. Manual
     sync should trigger one cycle of `sync_gmail` immediately without waiting for the loop.
   - What's unclear: Whether calling `sync_gmail` from a FastAPI `BackgroundTasks` callback will have
     database session conflicts with the loop task.
   - Recommendation: Use FastAPI `BackgroundTasks` and create a fresh tenant session inside the task
     (same pattern as `_sync_for_tenant` in `gmail_sync.py`). The loop task and manual sync operate on
     separate sessions so no conflict occurs.

---

## Sources

### Primary (HIGH confidence)
- `/Users/sharan/Projects/flywheel-v2/frontend/package.json` — exact installed versions
- `/Users/sharan/Projects/flywheel-v2/frontend/src/lib/api.ts` — API client shape (missing `put`)
- `/Users/sharan/Projects/flywheel-v2/frontend/src/features/briefing/hooks/useBriefing.ts` — React Query pattern
- `/Users/sharan/Projects/flywheel-v2/frontend/src/stores/ui.ts` — Zustand store pattern
- `/Users/sharan/Projects/flywheel-v2/frontend/src/app/routes.tsx` — routing pattern (lazy imports)
- `/Users/sharan/Projects/flywheel-v2/frontend/src/app/layout.tsx` — where Toaster must be mounted
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/email.py` — existing endpoints (approve/dismiss/edit)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/db/models.py` — Email, EmailScore, EmailDraft schemas
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/services/gmail_sync.py:357-387` — get_thread_priority()
- https://tanstack.com/virtual/latest/docs/framework/react/examples/fixed — useVirtualizer fixed example (verified)
- https://github.com/tailwindlabs/tailwindcss-typography — v4 `@plugin` syntax (verified)

### Secondary (MEDIUM confidence)
- https://ui.shadcn.com/docs/components/radix/sonner — Sonner integration for shadcn (official shadcn docs)
- https://ui.shadcn.com/docs/tailwind-v4 — shadcn v4 changes (official)

### Tertiary (LOW confidence)
- WebSearch results on FastAPI pagination patterns — consistent with existing codebase patterns, but not verified against a specific official source

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed from installed node_modules; codebase patterns examined directly
- Architecture patterns: HIGH — based on existing briefing/hooks pattern which is established and working
- Virtual scrolling: HIGH — useVirtualizer API verified from official TanStack docs
- Sonner/alerts: HIGH — shadcn official docs confirmed integration approach
- Pitfalls: HIGH — N+1 query and virtual list height issues confirmed from codebase inspection; toast deduplication from official Sonner API
- Tailwind typography: HIGH — verified from official tailwindcss-typography GitHub README

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable libraries; Tailwind v4 is moving but the `@plugin` pattern is stable)
