# Phase 67: Tasks UI - Research

**Researched:** 2026-03-29
**Domain:** React frontend feature (Tasks page, Briefing widget, triage system)
**Confidence:** HIGH

## Summary

The Tasks UI builds on a well-established frontend architecture. The codebase follows a consistent `features/` directory pattern (api.ts, hooks/, components/, types/) used by meetings, accounts, pipeline, and other features. The backend Task API is fully built with 7 endpoints, Pydantic schemas, and a state machine -- the frontend needs one backend change (add `deferred` status + `confirmed->done` shortcut) and then a pure React implementation.

The existing component library provides all major primitives: `BrandedCard` (with action/info/warning/complete variants), `Sheet` (right-side panel with @base-ui/react Dialog), `EmptyState`, `Badge`, `Skeleton`, `Button`, and `Sonner` toasts. The design token system (CSS custom properties + TypeScript constants) enforces brand consistency. React Query v5 is the data layer with established mutation patterns (see `useGraduate`, `useSyncMeetings`).

**Primary recommendation:** Follow the meetings feature as the structural template. Build the data layer first (types, api.ts, hooks), then components bottom-up (cards -> sections -> page -> focus mode -> briefing widget). The side panel should use the existing `Sheet` component with `side="right"` and a custom max-width override.

## Standard Stack

### Core (Already in package.json)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | ^19.0.0 | UI framework | Already installed |
| React Router | ^7.13.1 | Routing (`/tasks` route) | Already installed, lazy-load pattern established |
| @tanstack/react-query | ^5.91.2 | Server state management | Already installed, all features use it |
| Zustand | ^5.0.12 | Ephemeral UI state (focus mode index, animation direction) | Already installed |
| Tailwind CSS | ^4.0.0 | Utility styling | Already installed, v4 with `@theme inline` |
| sonner | ^2.0.7 | Toast notifications (undo, errors) | Already installed, used via `toast` import |
| lucide-react | ^0.577.0 | Icons | Already installed |
| date-fns | ^4.1.0 | Date math (grouping, relative time) | Already installed, used in relationships/settings |
| class-variance-authority | ^0.7.1 | Variant-based component styling | Already installed, used in Badge |
| @base-ui/react | ^1.3.0 | Headless UI primitives (Sheet/Dialog) | Already installed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tailwind-merge | ^3.5.0 | Merge Tailwind classes safely | Already used via `cn()` utility |

### No New Dependencies Needed
Everything required is already in the dependency tree. Do NOT add framer-motion, react-spring, or any animation library -- CSS transitions and the existing `animations.ts` patterns are sufficient.

## Architecture Patterns

### Feature Directory Structure
```
frontend/src/features/tasks/
  api.ts              # API functions + query key factory
  types/
    tasks.ts          # TypeScript interfaces matching backend schemas
  hooks/
    useTasks.ts       # useQuery for paginated list with filters
    useTaskSummary.ts # useQuery for status counts + overdue
    useTask.ts        # useQuery for single task detail
    useCreateTask.ts  # useMutation for manual task creation
    useUpdateTask.ts  # useMutation for field updates
    useUpdateTaskStatus.ts  # useMutation for status transitions (optimistic)
  components/
    TasksPage.tsx           # Main page component (route target)
    TriageInbox.tsx          # Triage section with TaskTriageCards
    TaskTriageCard.tsx       # Individual triage card with 3 action buttons
    FocusMode.tsx            # Full-viewport overlay triage
    MyCommitments.tsx        # Grouped list section
    TaskCommitmentCard.tsx   # Individual commitment card
    PromisesToMe.tsx         # Watchlist section
    TaskWatchlistItem.tsx    # Individual watchlist row
    TaskDetailPanel.tsx      # Side panel (wraps Sheet)
    TaskQuickAdd.tsx         # Inline task creation form
    DoneSection.tsx          # Collapsible completed tasks
    TaskStatusBadge.tsx      # Status badge component
    TaskPriorityBadge.tsx    # Priority badge component
    TaskSkillChip.tsx        # Skill suggestion chip with Zap icon
    BriefingTasksWidget.tsx  # Widget for BriefingPage
```

### Pattern 1: Lazy-Loaded Route Registration
**What:** All routes use `lazy()` with `.then((m) => ({ default: m.ComponentName }))` pattern wrapped in `<Suspense fallback={null}>`.
**Example (from routes.tsx):**
```typescript
const TasksPage = lazy(() =>
  import('@/features/tasks/components/TasksPage').then((m) => ({ default: m.TasksPage }))
)
// In Routes:
<Route path="/tasks" element={<Suspense fallback={null}><TasksPage /></Suspense>} />
```

### Pattern 2: Query Key Factory + API Module
**What:** Each feature has an `api.ts` with a `queryKeys` object and typed fetch functions using the `api` utility from `@/lib/api`.
**Example (from meetings/api.ts):**
```typescript
export const queryKeys = {
  tasks: {
    all: ['tasks'] as const,
    list: (filters?: TaskFilters) => ['tasks', 'list', filters] as const,
    summary: ['tasks', 'summary'] as const,
    detail: (id: string) => ['tasks', 'detail', id] as const,
  },
}

export function fetchTasks(filters?: TaskFilters): Promise<TasksListResponse> {
  return api.get<TasksListResponse>('/tasks/', { params: filters as Record<string, unknown> })
}
```

### Pattern 3: Mutation Hook with Cache Invalidation
**What:** Each mutation is a standalone hook using `useMutation` with `useQueryClient` for invalidation. Toast notifications on success/error.
**Example (from pipeline/useGraduate.ts):**
```typescript
export function useUpdateTaskStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch<TaskResponse>(`/tasks/${id}/status`, { status }),
    onMutate: async ({ id, status }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.tasks.all })
      // Snapshot previous value for rollback
      const previous = queryClient.getQueryData(queryKeys.tasks.list())
      // Optimistic update: remove from current list
      // ... update cache ...
      return { previous }
    },
    onError: (_err, _vars, context) => {
      // Rollback on error
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.tasks.list(), context.previous)
      }
      toast.error('Could not update task. Please try again.')
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.summary })
    },
  })
}
```

### Pattern 4: Page Layout
**What:** Pages use `flex-1 overflow-y-auto` with `var(--page-bg)` background, max-width container, and design token spacing.
**Example (from MeetingsPage.tsx):**
```typescript
<div className="flex-1 overflow-y-auto" style={{ background: 'var(--page-bg)' }}>
  <div className="max-w-5xl mx-auto px-6 py-8">
    {/* Page header */}
    {/* Sections */}
  </div>
</div>
```
**Note:** Tasks spec says `960px` max-width (matches `spacing.maxBriefing`). Use `style={{ maxWidth: spacing.maxBriefing }}` or `max-w-[960px]`.

### Pattern 5: Sidebar Navigation Entry
**What:** Add `SidebarMenuItem` with `SidebarMenuButton` wrapping a `NavLink`. Use `isActive` with `location.pathname.startsWith()`.
**Where:** `frontend/src/features/navigation/components/AppSidebar.tsx`, after the Meetings entry (line ~160).
**Icon:** `CheckSquare` from lucide-react (spec says this, needs import added).

### Pattern 6: Sheet for Side Panel
**What:** The existing `Sheet` component from `@base-ui/react` supports `side="right"` with backdrop overlay. Default max-width is `sm` (~384px). For the 480px spec requirement, override with className.
**Example:**
```typescript
<Sheet open={!!selectedTaskId} onOpenChange={(open) => !open && setSelectedTaskId(null)}>
  <SheetContent side="right" className="sm:max-w-[480px] w-full">
    <SheetHeader>
      <SheetTitle>{task.title}</SheetTitle>
    </SheetHeader>
    {/* Detail content */}
  </SheetContent>
</Sheet>
```
**Note:** The spec says desktop should push content left (not overlay). The existing Sheet is overlay-based. Two options: (1) Use Sheet as-is (overlay behavior, simpler), or (2) Build a custom panel that adjusts main content width. Recommendation: **Use Sheet as-is for V1** -- the push behavior is a nice-to-have and adds layout complexity. The Sheet already handles focus trapping, Escape key, backdrop click, and slide animation.

### Pattern 7: BrandedCard Usage
**What:** All cards use `BrandedCard` with appropriate variant. Supports `onClick`, `hoverable`, `variant` props.
```typescript
<BrandedCard variant="action" onClick={() => openDetail(task.id)}>
  {/* Card content */}
</BrandedCard>
```
Variants: `action` (coral left border), `complete` (green), `warning` (amber), `info` (no border).

### Anti-Patterns to Avoid
- **Do NOT use Zustand for task data.** React Query owns all server state. Zustand only for ephemeral UI (focus mode index, which task card is keyboard-focused).
- **Do NOT create custom card wrappers.** Use `BrandedCard` for everything.
- **Do NOT hardcode hex colors.** Always use `var(--brand-coral)`, `var(--error)`, etc. from design tokens.
- **Do NOT use `framer-motion` or animation libraries.** Use CSS transitions and the patterns in `animations.ts`.
- **Do NOT build a custom toast system.** Use `toast` from `sonner` directly.
- **Do NOT use `useEffect` for data fetching.** React Query handles everything.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Toast notifications | Custom toast system | `sonner` (`toast.success()`, `toast.error()`) | Already configured with brand styling in `sonner.tsx` |
| Side panel | Custom slide-in div | `Sheet` from `@/components/ui/sheet` | Handles focus trap, escape, backdrop, animation |
| Loading skeletons | Custom shimmer | `Skeleton` / `ShimmerSkeleton` from `@/components/ui/skeleton` | Already styled with brand shimmer |
| Empty states | Custom empty components | `EmptyState` from `@/components/ui/empty-state` | Consistent icon + title + description + optional CTA |
| Date formatting | Manual date math | `date-fns` (`formatDistanceToNow`, `isAfter`, `isBefore`, `startOfDay`, `startOfWeek`) | Already in deps, handles timezone/locale properly |
| API client | `fetch` directly | `api` from `@/lib/api` | Handles auth token, focus ID header, error parsing |
| Card containers | Custom divs with shadows | `BrandedCard` | Consistent border, shadow, hover, keyboard support |
| Dropdown menus | Custom select | `DropdownMenu` from `@/components/ui/dropdown-menu` | Accessible, keyboard-navigable |

## Common Pitfalls

### Pitfall 1: Stale Triage State After Optimistic Updates
**What goes wrong:** User triages a task (optimistic remove from list), but the server returns an error. The task should reappear but doesn't because the optimistic update wasn't properly rolled back.
**Why it happens:** React Query's optimistic update pattern requires careful snapshot + rollback in `onMutate`/`onError`.
**How to avoid:** Always snapshot the previous query data in `onMutate`, return it as context, and restore it in `onError`. Use `queryClient.cancelQueries` before optimistic update to prevent race conditions.
**Warning signs:** Tasks disappear permanently after a network hiccup.

### Pitfall 2: Focus Mode Keyboard Events Leaking
**What goes wrong:** Arrow key shortcuts in focus mode trigger browser scrolling or other page behavior.
**Why it happens:** Event handlers don't call `preventDefault()` or the listener is attached at the wrong level.
**How to avoid:** In focus mode, attach `keydown` handler to the overlay div (or use `useEffect` on `document`), call `preventDefault()` for handled keys, and remove the listener on cleanup. Gate all page-level shortcuts behind a check: `if (isFocusModeOpen || isDetailPanelOpen || isInputFocused) return`.
**Warning signs:** Page scrolls when pressing arrow keys in focus mode.

### Pitfall 3: Query Key Mismatch Causes Stale Data
**What goes wrong:** Triage inbox shows stale data because the query key for filtered tasks doesn't match what gets invalidated after mutations.
**Why it happens:** Using different filter shapes in query keys vs invalidation calls.
**How to avoid:** Use the `queryKeys` factory consistently. Invalidate the `all` key (`['tasks']`) to catch all filtered variants. Set `staleTime: 30_000` (30s) for tasks since they change frequently during triage.

### Pitfall 4: Date Grouping Off-by-One
**What goes wrong:** A task due "today" appears in the "this week" group, or an overdue task doesn't show as overdue.
**Why it happens:** Comparing UTC timestamps against local timezone dates without proper normalization.
**How to avoid:** Use `date-fns` `startOfDay`, `startOfWeek`, `endOfWeek` with explicit timezone handling. The backend stores `due_date` as `TIMESTAMP WITH TIME ZONE` -- parse it with `new Date()` which respects the timezone, then compare against local day boundaries.

### Pitfall 5: Undo Toast Race Condition
**What goes wrong:** User triages a task, clicks Undo, but the undo calls the wrong previous status because multiple tasks were triaged quickly.
**Why it happens:** The undo callback captures stale closure variables.
**How to avoid:** Pass the task ID and previous status as explicit parameters to the undo function. Use `toast()` with an action button that calls `useUpdateTaskStatus` with the original status value. Each toast is independent.

### Pitfall 6: Sheet Default Width Too Narrow
**What goes wrong:** The TaskDetailPanel appears cramped because Sheet defaults to `sm:max-w-sm` (384px).
**Why it happens:** The Sheet component has a hardcoded default max-width class.
**How to avoid:** Override with `className="sm:max-w-[480px]"` on `SheetContent`. Tailwind v4 supports arbitrary values in brackets.

## Code Examples

### Backend State Machine Extension (TASK-01)
```python
# In backend/src/flywheel/api/tasks.py

VALID_STATUSES = {
    "detected", "in_review", "confirmed", "in_progress",
    "done", "blocked", "dismissed", "deferred",  # ADD deferred
}

VALID_TRANSITIONS: dict[str, set[str]] = {
    "detected":    {"in_review", "confirmed", "dismissed", "deferred"},    # ADD deferred
    "in_review":   {"confirmed", "dismissed", "deferred"},                 # ADD deferred
    "confirmed":   {"in_review", "in_progress", "dismissed", "done"},      # ADD done
    "in_progress": {"done", "blocked", "dismissed"},
    "blocked":     {"in_progress", "dismissed"},
    "done":        set(),
    "dismissed":   {"detected"},
    "deferred":    {"in_review"},                                           # NEW: re-enter triage
}

# In TaskSummaryResponse, add:
class TaskSummaryResponse(BaseModel):
    # ... existing fields ...
    deferred: int = 0  # ADD
```

### TypeScript Types (TASK-03)
```typescript
// frontend/src/features/tasks/types/tasks.ts

export interface Task {
  id: string
  tenant_id: string
  user_id: string
  meeting_id: string | null
  account_id: string | null
  title: string
  description: string | null
  source: string
  task_type: TaskType
  commitment_direction: CommitmentDirection
  suggested_skill: string | null
  skill_context: Record<string, unknown> | null
  trust_level: TrustLevel
  status: TaskStatus
  priority: Priority
  due_date: string | null      // ISO 8601
  completed_at: string | null  // ISO 8601
  metadata: Record<string, unknown> | null
  created_at: string           // ISO 8601
  updated_at: string           // ISO 8601
}

export type TaskStatus = 'detected' | 'in_review' | 'confirmed' | 'in_progress' | 'done' | 'blocked' | 'dismissed' | 'deferred'
export type CommitmentDirection = 'yours' | 'theirs' | 'mutual' | 'signal' | 'speculation'
export type Priority = 'high' | 'medium' | 'low'
export type TaskType = 'followup' | 'deliverable' | 'introduction' | 'research' | 'other'
export type TrustLevel = 'auto' | 'review' | 'confirm'

export const VALID_TRANSITIONS: Record<TaskStatus, TaskStatus[]> = {
  detected:    ['in_review', 'confirmed', 'dismissed', 'deferred'],
  in_review:   ['confirmed', 'dismissed', 'deferred'],
  confirmed:   ['in_review', 'in_progress', 'dismissed', 'done'],
  in_progress: ['done', 'blocked', 'dismissed'],
  blocked:     ['in_progress', 'dismissed'],
  done:        [],
  dismissed:   ['detected'],
  deferred:    ['in_review'],
}

export interface TaskSummary {
  detected: number
  in_review: number
  confirmed: number
  in_progress: number
  done: number
  blocked: number
  dismissed: number
  deferred: number
  overdue: number
}

export interface TasksListResponse {
  tasks: Task[]
  total: number
}

export interface TaskCreate {
  title: string
  description?: string | null
  task_type: TaskType
  commitment_direction?: CommitmentDirection
  suggested_skill?: string | null
  skill_context?: Record<string, unknown> | null
  trust_level?: TrustLevel
  priority?: Priority
  due_date?: string | null
  meeting_id?: string | null
  account_id?: string | null
}

export interface TaskUpdate {
  title?: string | null
  description?: string | null
  priority?: Priority | null
  due_date?: string | null
  suggested_skill?: string | null
  trust_level?: TrustLevel | null
}

export interface TaskFilters {
  offset?: number
  limit?: number
  status?: string
  commitment_direction?: string
  priority?: string
  meeting_id?: string
  account_id?: string
}
```

### API Module Pattern (TASK-02)
```typescript
// frontend/src/features/tasks/api.ts
import { api } from '@/lib/api'
import type { Task, TaskCreate, TaskUpdate, TaskSummary, TasksListResponse, TaskFilters } from './types/tasks'

export const queryKeys = {
  tasks: {
    all: ['tasks'] as const,
    list: (filters?: TaskFilters) => ['tasks', 'list', filters ?? {}] as const,
    summary: ['tasks', 'summary'] as const,
    detail: (id: string) => ['tasks', 'detail', id] as const,
  },
}

export const fetchTasks = (filters?: TaskFilters): Promise<TasksListResponse> =>
  api.get<TasksListResponse>('/tasks/', { params: filters as Record<string, unknown> })

export const fetchTaskSummary = (): Promise<TaskSummary> =>
  api.get<TaskSummary>('/tasks/summary')

export const fetchTask = (id: string): Promise<Task> =>
  api.get<Task>(`/tasks/${id}`)

export const createTask = (body: TaskCreate): Promise<Task> =>
  api.post<Task>('/tasks/', body)

export const updateTask = (id: string, body: TaskUpdate): Promise<Task> =>
  api.patch<Task>(`/tasks/${id}`, body)

export const updateTaskStatus = (id: string, status: string): Promise<Task> =>
  api.patch<Task>(`/tasks/${id}/status`, { status })
```

### Toast with Undo Pattern
```typescript
import { toast } from 'sonner'

// After optimistic status update:
toast('Task confirmed', {
  action: {
    label: 'Undo',
    onClick: () => updateStatus({ id: taskId, status: previousStatus }),
  },
  duration: 5000,
})
```

### Date Grouping Utility
```typescript
import { startOfDay, startOfWeek, endOfWeek, addWeeks, isBefore, isAfter, isEqual } from 'date-fns'
import type { Task } from './tasks'

export interface GroupedTasks {
  overdue: Task[]
  today: Task[]
  thisWeek: Task[]
  nextWeek: Task[]
  later: Task[]
}

export function groupTasksByDueDate(tasks: Task[]): GroupedTasks {
  const now = new Date()
  const todayStart = startOfDay(now)
  const todayEnd = startOfDay(addWeeks(todayStart, 0))  // end of today
  const weekEnd = endOfWeek(now, { weekStartsOn: 1 })
  const nextWeekEnd = endOfWeek(addWeeks(now, 1), { weekStartsOn: 1 })

  const groups: GroupedTasks = { overdue: [], today: [], thisWeek: [], nextWeek: [], later: [] }

  for (const task of tasks) {
    if (!task.due_date) {
      groups.later.push(task)
      continue
    }
    const due = startOfDay(new Date(task.due_date))
    if (isBefore(due, todayStart)) {
      groups.overdue.push(task)
    } else if (isEqual(due, todayStart)) {
      groups.today.push(task)
    } else if (isBefore(due, weekEnd) || isEqual(due, weekEnd)) {
      groups.thisWeek.push(task)
    } else if (isBefore(due, nextWeekEnd) || isEqual(due, nextWeekEnd)) {
      groups.nextWeek.push(task)
    } else {
      groups.later.push(task)
    }
  }
  return groups
}
```

### Staggered Animation Pattern
```typescript
// Using existing animations.ts staggerDelay function
import { staggerDelay, animationClasses } from '@/lib/animations'

{tasks.map((task, index) => (
  <div
    key={task.id}
    className={animationClasses.fadeSlideUp}
    style={{ animationDelay: staggerDelay(index) }}
  >
    <TaskTriageCard task={task} />
  </div>
))}
```

### Skills Execution API (TASK-14)
```typescript
// POST /api/v1/skills/runs
const response = await api.post<{ run_id: string; status: string; stream_url: string }>(
  '/skills/runs',
  {
    skill_name: task.suggested_skill,
    input_text: JSON.stringify(task.skill_context),
  }
)

// SSE stream for progress
const evtSource = new EventSource(`/api/v1/skills/runs/${response.run_id}/stream`)
evtSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  // Handle progress updates
}
```
**Note:** The SSE endpoint requires auth. Use `EventSource` with the auth token passed via query param or build a fetch-based SSE reader, since native `EventSource` doesn't support headers. The existing codebase likely has a pattern for this in meeting processing -- check `useMeetingProcessing.ts`.

## Briefing Widget Integration Point

The BriefingPage renders sections in this order (relevant excerpt):
1. Focus Areas / NextActionCta
2. NudgeCard
3. CalendarNudge
4. PulseSignals (conditional on revenue focus)
5. **Recent Documents** <-- Insert "Next Actions" widget BEFORE this
6. PersonalGapCard

Insert the `BriefingTasksWidget` component between PulseSignals and Recent Documents (around line 502 in BriefingPage.tsx). Wrap it in the same spacing pattern:
```typescript
{/* Next Actions (Tasks widget) */}
<div style={{ marginBottom: spacing.section }}>
  <BriefingTasksWidget />
</div>
```

## Sidebar Navigation Integration Point

In `AppSidebar.tsx`, add after the Meetings `SidebarMenuItem` (line ~160):
```typescript
import { CheckSquare } from 'lucide-react'
// ...
<SidebarMenuItem>
  <SidebarMenuButton
    isActive={location.pathname.startsWith('/tasks')}
    render={<NavLink to="/tasks" />}
    tooltip="Tasks"
  >
    <CheckSquare className="size-4" />
    <span>Tasks</span>
  </SidebarMenuButton>
</SidebarMenuItem>
```

## Backend API Contract Reference

| Endpoint | Method | Request | Response | Notes |
|----------|--------|---------|----------|-------|
| `/tasks/` | GET | `?status=&commitment_direction=&priority=&meeting_id=&account_id=&offset=&limit=` | `{ tasks: Task[], total: number }` | All params optional, max limit=100 |
| `/tasks/summary` | GET | - | `{ detected, in_review, confirmed, in_progress, done, blocked, dismissed, overdue }` | Add `deferred` in TASK-01 |
| `/tasks/{id}` | GET | - | `Task` | 404 if not found |
| `/tasks/` | POST | `TaskCreate` body | `Task` (201) | Source always set to "manual" |
| `/tasks/{id}` | PATCH | `TaskUpdate` body | `Task` | Only title, description, priority, due_date, suggested_skill, trust_level updatable |
| `/tasks/{id}/status` | PATCH | `{ status: string }` | `Task` | 422 if invalid transition |
| `/tasks/{id}` | DELETE | - | 204 | Soft-delete (sets status=dismissed) |

**Note:** The list endpoint accepts only single-value filters (not arrays). To get triage inbox tasks (detected + in_review + deferred), make multiple calls or fetch all and filter client-side. Recommendation: **fetch without status filter and filter client-side** for sections that need multiple statuses, since task volumes are small (8-10/day, ~50 total active).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tailwind v3 (`tailwind.config.js`) | Tailwind v4 (`@theme inline` in CSS) | Dec 2024 | No config file, CSS-native theming |
| shadcn/ui (Radix) | @base-ui/react | Recent | Sheet uses `@base-ui/react/dialog` not Radix Dialog |
| React Router v6 | React Router v7 | 2025 | Import from `react-router` not `react-router-dom` |
| React 18 | React 19 | 2025 | Concurrent features available |

## Open Questions

1. **Push vs Overlay Panel Behavior**
   - What we know: Spec says desktop panel should "push" main content left. Existing Sheet component overlays with backdrop.
   - What's unclear: Whether the push behavior is worth the implementation complexity in V1.
   - Recommendation: **Use Sheet overlay for V1.** It already handles focus trapping, escape, animations. Add push behavior as a future enhancement if users want it.

2. **SSE Auth for Skill Execution**
   - What we know: `EventSource` API doesn't support custom headers. The skills SSE endpoint requires auth.
   - What's unclear: How the existing codebase handles authenticated SSE streams.
   - Recommendation: Check `useMeetingProcessing.ts` for the existing SSE pattern. If it uses fetch-based streaming, follow the same approach.

3. **Multi-Status Filtering**
   - What we know: The backend list endpoint only accepts single `status` filter values. Triage inbox needs detected + in_review + deferred.
   - What's unclear: Whether adding multi-status filter to backend is needed.
   - Recommendation: **Fetch all active tasks (no status filter) and filter client-side.** Volume is small enough (~50 tasks total) that one request is more efficient than three.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/api/tasks.py` -- Full API contract, schemas, state machine, 7 endpoints
- `backend/src/flywheel/db/models.py` lines 1342-1399 -- Task ORM model, all fields, indexes
- `frontend/src/features/meetings/` -- Feature directory pattern reference (api.ts, hooks/, components/, types/)
- `frontend/src/components/ui/sheet.tsx` -- Sheet component implementation (@base-ui/react Dialog)
- `frontend/src/components/ui/branded-card.tsx` -- BrandedCard with 4 variants
- `frontend/src/components/ui/empty-state.tsx` -- EmptyState component API
- `frontend/src/lib/design-tokens.ts` -- All design tokens (spacing, typography, colors)
- `frontend/src/lib/animations.ts` -- Animation patterns (fadeSlideUp, stagger, cardHover)
- `frontend/src/lib/api.ts` -- API client with auth, error handling
- `frontend/src/app/routes.tsx` -- Route registration pattern
- `frontend/src/features/navigation/components/AppSidebar.tsx` -- Sidebar nav pattern
- `frontend/src/features/briefing/components/BriefingPage.tsx` -- Widget integration point
- `frontend/package.json` -- All dependency versions verified
- `frontend/src/index.css` -- Tailwind v4 theme configuration, CSS custom properties
- `backend/src/flywheel/api/skills.py` -- Skills run API (POST /skills/runs, SSE stream)

### Secondary (MEDIUM confidence)
- `.planning/SPEC-tasks-ui.md` -- Full spec with 16 requirements and acceptance criteria
- `.planning/CONCEPT-BRIEF-tasks-ui.md` -- Brainstorm decisions and architectural rationale
- `.planning/DESIGN-BRIEF-tasks-ui.md` -- Visual design specs and component details

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies verified in package.json, all component APIs verified by reading source
- Architecture: HIGH -- feature directory pattern verified across meetings, accounts, pipeline features
- Backend API contract: HIGH -- read complete API source code
- Pitfalls: HIGH -- based on direct codebase analysis (React Query patterns, Sheet defaults, date handling)
- Animation system: HIGH -- read animations.ts source, verified CSS approach
- Skills execution: MEDIUM -- read API source but SSE auth pattern needs verification in existing hooks

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable codebase, unlikely to change architecture)
