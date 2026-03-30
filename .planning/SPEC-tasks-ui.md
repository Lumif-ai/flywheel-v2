# Tasks UI — Specification

> Status: Execution-Ready
> Created: 2026-03-29
> Last updated: 2026-03-29
> Concept Brief: .planning/CONCEPT-BRIEF-tasks-ui.md
> Design Brief: .planning/DESIGN-BRIEF-tasks-ui.md

## Overview

Build a frontend Tasks page and Briefing widget for Flywheel's commitment accountability system. The backend (Task model, API, extraction pipeline) is complete — this spec covers the React frontend that surfaces extracted tasks for triage, tracks active commitments, and monitors promises others have made. The page serves three jobs in a single scrollable surface: triage inbox (review AI-extracted tasks), accountability dashboard (track what you owe), and execution cockpit (run skills to generate deliverables).

## Core Value

**Morning triage in under 60 seconds.** A founder opens the Tasks page, reviews 8-10 AI-extracted commitments from yesterday's meetings, confirms/dismisses/defers each one, and knows exactly what they owe and what others owe them — without typing anything.

## Users & Entry Points

| User Type | Entry Point | Primary Goal |
|-----------|-------------|--------------|
| Founder (morning ritual) | Briefing widget → `/tasks` | Triage today's extracted tasks, check overdue items |
| Founder (during day) | Sidebar nav → `/tasks` | Quick status check, mark tasks done, run skill execution |
| Founder (post-meeting) | Briefing widget or `/tasks` directly | Review newly extracted commitments from just-processed meeting |

## Requirements

### Must Have

#### Backend Extension

- **TASK-01**: Add `deferred` status to the task state machine
  - Add `"deferred"` to `VALID_STATUSES`
  - Add transitions: `"in_review" → "deferred"`, `"detected" → "deferred"`, `"deferred" → "in_review"` (re-enters triage on next session)
  - Add `"done"` to `VALID_TRANSITIONS["confirmed"]` (skip `in_progress` for quick completions)
  - Add `"deferred"` count to `TaskSummaryResponse`
  - **Acceptance Criteria:**
    - [ ] `PATCH /tasks/{id}/status` accepts `{"status": "deferred"}` from `detected` or `in_review`
    - [ ] `PATCH /tasks/{id}/status` accepts `{"status": "in_review"}` from `deferred`
    - [ ] `GET /tasks/summary` returns `deferred` count
    - [ ] `PATCH /tasks/{id}/status` accepts `{"status": "done"}` from `confirmed` (skip in_progress)
    - [ ] Invalid transitions (e.g., `confirmed → deferred`) return 422

#### Frontend — Data Layer

- **TASK-02**: React Query hooks for task API
  - `useTasks(filters)` — paginated list with filters for status, commitment_direction, priority, meeting_id, account_id
  - `useTaskSummary()` — status counts + overdue count
  - `useTask(taskId)` — single task detail
  - `useCreateTask()` — mutation for manual task creation
  - `useUpdateTask()` — mutation for field updates (title, description, priority, due_date, suggested_skill, trust_level)
  - `useUpdateTaskStatus()` — mutation for status transitions with optimistic updates
  - Query keys: `['tasks', filters]`, `['tasks', 'summary']`, `['tasks', taskId]`
  - Cache invalidation: all task mutations invalidate `['tasks']` and `['tasks', 'summary']`
  - **Acceptance Criteria:**
    - [ ] `useTasks({ status: 'detected' })` returns only detected tasks, ordered by created_at DESC
    - [ ] `useUpdateTaskStatus()` optimistically removes task from triage list before server confirms
    - [ ] Network error on mutation shows toast with error message and reverts optimistic update
    - [ ] Stale time: 30 seconds (tasks change frequently during triage)

- **TASK-03**: Task type definitions
  - TypeScript interfaces matching backend schemas: `Task`, `TaskCreate`, `TaskUpdate`, `TaskSummary`
  - Enum constants: `TASK_STATUSES`, `COMMITMENT_DIRECTIONS`, `PRIORITIES`, `TASK_TYPES`, `TRUST_LEVELS`
  - Status transition map (mirrors backend `VALID_TRANSITIONS`) for client-side validation
  - Grouping utility: `groupTasksByDueDate(tasks)` → `{ overdue, today, thisWeek, nextWeek, later }`
  - **Acceptance Criteria:**
    - [ ] All TypeScript types match backend Pydantic schemas exactly (field names, types, optionality)
    - [ ] `groupTasksByDueDate` correctly classifies: overdue (due_date < today), today (due_date = today), this week (due_date within current week), next week, later
    - [ ] Tasks with no due_date go into the "later" group

#### Frontend — Page & Routing

- **TASK-04**: Tasks page at `/tasks` route
  - Add lazy-loaded route in `routes.tsx` following existing pattern
  - Feature directory: `frontend/src/features/tasks/` with `components/`, `hooks/`, `types/`, `api.ts`
  - Page layout: single column, max-width `960px`, page padding from `spacing.pageDesktop`
  - Background: warm register (`var(--brand-tint-warmest)`)
  - Page header: "Tasks" title (`typography.pageTitle`) + summary line ("12 active · 3 need review") + "+ Add" button
  - Four vertically stacked sections with `spacing.section` (48px) gap:
    1. Triage Inbox
    2. My Commitments
    3. Promises to Me
    4. Done (collapsed)
  - Sidebar navigation: add "Tasks" entry with `CheckSquare` icon from Lucide, positioned after "Meetings"
  - **Acceptance Criteria:**
    - [ ] Navigating to `/tasks` renders the Tasks page with all four sections
    - [ ] Page loads with skeleton placeholders while data fetches, then renders real data
    - [ ] Page header shows accurate count from `useTaskSummary()` — active = confirmed + in_progress + in_review, need review = detected + deferred
    - [ ] Empty page (no tasks) shows EmptyState: "No tasks yet" with description "Tasks will appear here after your meetings are processed" and no CTA (tasks are auto-generated)

#### Frontend — Triage Inbox Section

- **TASK-05**: Triage Inbox with inline actions
  - Section shows tasks with `status` in `['detected', 'in_review', 'deferred']`
  - Section header: "Triage Inbox" + count badge + "Review All →" button (opens focus mode)
  - Section collapses (height → 0 with animation) when empty, showing "All caught up" inline message
  - Each task rendered as `TaskTriageCard` with:
    - Title (15px/500, single line truncate)
    - Provenance line: meeting name + relative time ("Call with Sarah · 2d ago"). If no meeting (manual), show "Manual task"
    - Skill chip (if `suggested_skill` exists): `TaskSkillChip` with Zap icon + skill name
    - Three action buttons: Confirm (CheckCircle), Later (Clock), Dismiss (X)
  - **Action behaviors:**
    - Confirm: calls `useUpdateTaskStatus(id, 'confirmed')`, card exits right with slide animation
    - Later: calls `useUpdateTaskStatus(id, 'deferred')`, card exits down
    - Dismiss: calls `useUpdateTaskStatus(id, 'dismissed')`, card exits left
  - Undo: dismiss/confirm/defer actions show toast with "Undo" button for 5 seconds. Undo reverts status to previous value.
  - **Acceptance Criteria:**
    - [ ] Triage inbox shows exactly the tasks with status detected, in_review, or deferred
    - [ ] Clicking Confirm transitions task to `confirmed` and removes it from triage with rightward slide animation (150ms)
    - [ ] Clicking Dismiss transitions task to `dismissed` and removes it with leftward slide animation
    - [ ] Clicking Later transitions task to `deferred` and removes it with downward fade
    - [ ] Toast with "Undo" appears after each action. Clicking "Undo" reverts the status transition.
    - [ ] When all triage tasks are processed, section shows "All caught up" with a checkmark icon
    - [ ] Tasks are ordered by: priority (high first), then created_at (newest first)

- **TASK-06**: Focus Mode (Tinder-style triage)
  - Triggered by "Review All" button in Triage Inbox header
  - Full-viewport overlay with semi-transparent backdrop
  - Progress bar at top: brand coral fill, width proportional to (reviewed / total)
  - Centered card (max-width 560px) showing full task detail:
    - Title (20px/600)
    - Meeting name and date
    - Account name (if linked)
    - Commitment direction badge
    - Suggested skill chip (if exists)
    - Description/context (if exists)
    - Priority and due date
  - Bottom action bar: three buttons — Dismiss (←), Later (↓), Confirm (→)
  - Keyboard hints shown below each button label ("← key", "↓ key", "→ key")
  - "Edit before confirming" link below action bar — opens inline edit for title, priority, due date
  - **Card transitions:**
    - Confirm: card slides right + rotates 3deg + fades, next card enters from bottom (fadeUp)
    - Dismiss: card slides left + rotates -3deg + fades, next card enters from bottom
    - Later: card fades down, next card enters from bottom
    - Exit: 250ms ease-in, Enter: 300ms cubic-bezier(0.2, 0, 0, 1) with 100ms delay
  - Completion state: large checkmark icon (48px, green) + "All caught up" + "N tasks reviewed" + auto-close after 2s
  - **Keyboard shortcuts:**
    - `→` or `Enter`: Confirm
    - `←` or `Backspace`: Dismiss
    - `↓` or `S`: Save for later
    - `E`: Edit before confirming
    - `Escape`: Exit focus mode
  - **Acceptance Criteria:**
    - [ ] "Review All" button opens focus mode overlay with first triage task displayed
    - [ ] Progress bar advances after each action (e.g., 1/7 → 2/7)
    - [ ] Arrow keys trigger corresponding triage actions
    - [ ] Card transition animations play on each action (reduced to instant swap with `prefers-reduced-motion`)
    - [ ] Pressing E opens inline edit fields for title, priority, due date within the card
    - [ ] After all tasks reviewed, completion state shows for 2 seconds then auto-closes
    - [ ] Escape exits focus mode at any point, returning to Tasks page with current triage state preserved
    - [ ] Focus is trapped within overlay (Tab cycles within, not outside)
    - [ ] Screen reader announces "Reviewing task N of M" on each transition via `aria-live` region

#### Frontend — My Commitments Section

- **TASK-07**: My Commitments grouped list
  - Shows tasks with `commitment_direction = 'yours'` AND `status` in `['confirmed', 'in_progress', 'blocked']`
  - Grouped by due date: Overdue, Today, This Week, Next Week, Later (no due date)
  - Group headers: uppercase label (`12px/600`) with count in parentheses
  - Empty groups hidden (don't show "This Week (0)")
  - Each task rendered as `TaskCommitmentCard`:
    - Title (15px/600, max 2 lines)
    - Provenance: MapPin icon + meeting name + relative time
    - Account: Building2 icon + account name (clickable → `/accounts/:id`)
    - Status row: `TaskStatusBadge` + `TaskPriorityBadge` + due date with Calendar icon
    - Skill row (conditional): `TaskSkillChip` + "Generate →" button (if `suggested_skill` exists and `status = 'confirmed'`)
  - Click on card body opens `TaskDetailPanel` (side panel)
  - Due date color: overdue = `var(--error)`, today = `var(--warning)`, this week = `var(--heading-text)`, later = `var(--secondary-text)`
  - **Acceptance Criteria:**
    - [ ] Section shows only `yours` commitment tasks in active statuses
    - [ ] Tasks are correctly grouped by due date with proper date math (uses start of day, respects local timezone)
    - [ ] Overdue group header and due dates shown in red (`var(--error)`)
    - [ ] Clicking account name navigates to `/accounts/:id`
    - [ ] "Generate" button only appears on confirmed tasks with `suggested_skill` set
    - [ ] Clicking task card opens side panel with full detail
    - [ ] Empty section shows EmptyState: "No active commitments" with Target icon

#### Frontend — Promises to Me Section

- **TASK-08**: Promises to Me watchlist
  - Shows tasks with `commitment_direction` in `['theirs', 'mutual']` AND `status` NOT in `['done', 'dismissed']`
  - Section header: "Promises to Me" + count badge
  - Each item rendered as `TaskWatchlistItem`:
    - Row 1: Avatar (24px, initials) + person/meeting name + dot + company/account name
    - Row 2: Promise text (task title) in italics, quoted
    - Row 3: provenance ("From: [meeting] · [date]") + status indicator
    - Status indicator: green dot + "On track" + due date, OR red dot + "Overdue (N days)" + "Create Follow-up" button
  - Items separated by `divide-y` (not individual cards — lighter visual weight)
  - Overdue items sorted to top of section
  - "Create Follow-up" click: opens TaskQuickAdd pre-filled with "Follow up with [person] re: [promise]", linked to same account_id
  - After follow-up created: promise item shows "Follow-up created" badge inline
  - **Acceptance Criteria:**
    - [ ] Section shows only `theirs` and `mutual` commitment tasks in active statuses
    - [ ] Overdue items (due_date < now) display red dot, "Overdue (N days)" text, and "Create Follow-up" button
    - [ ] On-track items (due_date >= now or no due_date) display green dot and "On track"
    - [ ] "Create Follow-up" opens quick-add with pre-filled title, account_id, and commitment_direction = "yours"
    - [ ] After follow-up task is created, the original promise item shows "Follow-up created" badge
    - [ ] Items without a linked meeting show "Manual" as provenance source
    - [ ] Empty section shows EmptyState: "No outstanding promises" with Handshake icon

#### Frontend — Task Detail Panel

- **TASK-09**: Slide-in side panel for task detail
  - Triggered by clicking any task card (commitment or watchlist)
  - Slides from right edge, 480px width on desktop, full-width on mobile
  - Desktop: pushes main content left (panel is inline, not overlay)
  - Mobile (<768px): overlays with backdrop, full-width
  - Panel sections:
    - Header: task title (18px/600, editable on click) + close button
    - Metadata grid: Status (with change dropdown), Priority (toggle), Due date (date picker), Account (link), Source meeting (link), Task type, Commitment direction
    - Description: editable text area (auto-save on blur, 500ms debounce)
    - Skill Execution (conditional): skill name + context preview + "Generate Deliverable" button OR generated output with "View" / "Regenerate" links
    - Actions: "Mark Complete" (primary) + "Dismiss" (ghost/destructive)
  - Metadata changes: each field updates via `useUpdateTask()` or `useUpdateTaskStatus()` immediately (no save button)
  - "Mark Complete" transitions to `done`, panel closes, toast confirms
  - **Acceptance Criteria:**
    - [ ] Panel opens from right with 300ms slide animation
    - [ ] Panel closes on Escape key, close button, or clicking outside (mobile)
    - [ ] Editing title: click → inline input → Enter/blur saves → shows updated title
    - [ ] Changing status: dropdown shows only valid transitions from current status (client-side transition map)
    - [ ] Changing priority: three-option toggle (high/medium/low), updates immediately
    - [ ] Changing due date: date picker, updates immediately
    - [ ] "Mark Complete" is disabled if current status doesn't allow `done` transition (e.g., still `confirmed`, needs `in_progress` first — or allow direct `confirmed → done` by adding this transition)
    - [ ] "Generate Deliverable" button shows loading spinner during execution, then shows output link on success
    - [ ] Focus is trapped within panel when open on mobile (overlay mode)
    - [ ] Panel preserves scroll position of main content when opening/closing

#### Frontend — Quick Add

- **TASK-10**: Inline task creation
  - Triggered by "+ Add" button in page header
  - Expands inline at top of "My Commitments" section (not a modal)
  - Fields:
    - Title input (auto-focused, placeholder "What do you need to do?", required)
    - Optional pill buttons expanding to pickers: Due date (Calendar), Account (Building2 searchable select), Priority (three-toggle)
  - Defaults: commitment_direction = "yours", source = "manual", task_type = "other", priority = "medium", trust_level = "review", status = "detected"
  - Enter submits (if title non-empty), Escape cancels and collapses
  - After creation: task appears in Triage Inbox (since status = detected), quick-add collapses, toast "Task created"
  - **Acceptance Criteria:**
    - [ ] "+ Add" expands inline form with height animation (200ms)
    - [ ] Title input is auto-focused immediately
    - [ ] Pressing Enter with non-empty title creates task via `useCreateTask()` and collapses form
    - [ ] Pressing Enter with empty title does nothing (no empty tasks)
    - [ ] Pressing Escape collapses form without creating
    - [ ] Account picker searches accounts by name (uses existing accounts API)
    - [ ] Created task appears in Triage Inbox immediately (optimistic update)

#### Frontend — Briefing Widget

- **TASK-11**: Tasks widget embedded in BriefingPage
  - Position: after "Pulse Signals" section (or after "Your Focus Areas" if no Pulse Signals)
  - Wrapper: `BrandedCard` with variant `action` (coral left border) when triage items exist, `info` when clear
  - Content:
    - Section title: "Next Actions" + triage count badge (if > 0)
    - Up to 3 triage items as compact rows: dot indicator + title (truncated) + due date + compact confirm/dismiss buttons
    - If overdue promises exist: "🔴 N overdue promises" line
    - Footer: "View all tasks →" link navigating to `/tasks`
  - Widget uses same `useTasks` and `useTaskSummary` hooks as full page
  - Compact triage actions work the same (confirm/dismiss inline, no "later" in widget)
  - **Acceptance Criteria:**
    - [ ] Widget renders in Briefing page between Pulse Signals and Recent Documents
    - [ ] Shows max 3 triage items; if more exist, shows "+N more" text
    - [ ] Confirm/dismiss actions on compact rows update task status and re-fetch
    - [ ] "View all tasks →" navigates to `/tasks`
    - [ ] Widget shows `BrandedCard variant="action"` when triage count > 0, `variant="info"` when 0
    - [ ] When no tasks at all (summary all zeros), widget is hidden entirely
    - [ ] Overdue promises count appears even if no triage items (different data)

#### Frontend — Done Section

- **TASK-12**: Collapsible completed tasks section
  - Shows tasks with `status = 'done'` from last 7 days
  - Default state: collapsed — shows only header with count and chevron
  - Click header to expand/collapse with height animation (200ms)
  - Expanded rows: strikethrough title + relative completion time + output link (if skill-generated)
  - **Acceptance Criteria:**
    - [ ] Section defaults to collapsed, showing "Done (last 7 days) (N)" with ChevronRight icon
    - [ ] Click toggles expanded state, ChevronRight rotates to ChevronDown (200ms)
    - [ ] Expanded section shows completed tasks ordered by completed_at DESC
    - [ ] Tasks older than 7 days are excluded from the query
    - [ ] Each completed task shows strikethrough title and "Completed [relative time]"

#### Frontend — Keyboard Navigation

- **TASK-13**: Page-level keyboard shortcuts
  - `j` / `k`: navigate between task cards across all sections (moves focus ring)
  - `Enter` or `Space`: open detail panel for focused card
  - Focus mode shortcuts (documented in TASK-06)
  - Shortcuts disabled when: input/textarea is focused, detail panel is open (panel has its own key handling), focus mode is active
  - **Acceptance Criteria:**
    - [ ] Pressing `j` moves focus to next task card, `k` to previous
    - [ ] Focus wraps: `j` on last card does nothing, `k` on first card does nothing
    - [ ] Focused card shows visible focus ring (`outline: 2px solid var(--brand-coral)`)
    - [ ] Pressing Enter on focused card opens TaskDetailPanel
    - [ ] Keyboard shortcuts don't fire when typing in input fields

### Should Have

- **TASK-14**: Skill execution in detail panel
  - "Generate Deliverable" button in TaskDetailPanel calls `POST /api/v1/skills/runs` with `{ skill_name: task.suggested_skill, input_text: JSON.stringify(task.skill_context) }`
  - Connects to SSE stream at `GET /skills/runs/{run_id}/stream` for real-time progress
  - Shows loading state (spinner on button, "Generating..." text, optionally stream progress events)
  - On success (stream complete): shows output link/preview inline
  - On failure: shows error message with retry button
  - **Acceptance Criteria:**
    - [ ] "Generate" button visible on tasks with `suggested_skill` and status `confirmed` or `in_progress`
    - [ ] Click triggers skill execution API call
    - [ ] Loading state shows spinner for duration of execution
    - [ ] Success shows link to generated output
    - [ ] Failure shows error toast with "Retry" option

- **TASK-15**: Search within tasks page
  - Search input in page header (right of "+ Add" button)
  - Filters all visible sections by task title (client-side filter)
  - Debounced: 300ms delay before filtering
  - Clear button (X) resets search
  - **Acceptance Criteria:**
    - [ ] Typing in search filters all visible tasks by title substring match (case-insensitive)
    - [ ] Filter applies across all sections (triage, commitments, promises, done)
    - [ ] Clearing search restores all tasks
    - [ ] Empty search result shows "No tasks matching '[query]'" per section

- **TASK-16**: Staggered entrance animations
  - On initial page load, task cards animate in with staggered fadeUp (50ms delay between cards)
  - On section re-render (after triage action), remaining cards re-animate
  - Respects `prefers-reduced-motion`: no animation
  - **Acceptance Criteria:**
    - [ ] Cards fade-slide-up on initial render with 50ms stagger
    - [ ] `prefers-reduced-motion: reduce` disables all animations
    - [ ] Re-rendering after triage action doesn't re-animate existing cards (only new positions)

### Won't Have (this version)

- Team/shared task views — Reason: tasks are Zone 1 (user-private RLS), data model doesn't support shared visibility yet
- Kanban board view — Reason: grouped list is better at current volume (8-10/day); kanban as future toggle
- Recurring tasks — Reason: no backend support; tasks are one-time commitments
- Task dependencies — Reason: overcomplicates for a single-founder tool
- Calendar view of tasks — Reason: meetings page already covers time-based view
- Drag-and-drop reordering — Reason: tasks have priority and due date for ordering; manual reorder adds complexity without clear value
- Email/Slack notifications for overdue tasks — Reason: the daily brief already surfaces overdue items
- Bulk actions (select multiple, batch confirm) — Reason: focus mode handles sequential review; batch operations can be added when volume exceeds 20+ triage items
- Mobile swipe gestures in list mode — Reason: button actions work on mobile; swipe can be added post-launch if mobile usage is significant

## Edge Cases & Error States

| Scenario | Expected Behavior |
|----------|-------------------|
| Task with no meeting_id (manual) | Provenance line shows "Manual task" instead of meeting name |
| Task with no account_id | Account row hidden in card and detail panel |
| Task with no due_date | Grouped under "Later" in My Commitments; no due date shown; cannot be overdue |
| Task with due_date in past but status = done | Not shown as overdue (filtered out by status) |
| Task with commitment_direction = "signal" or "speculation" | Not shown in My Commitments or Promises to Me; visible only in Triage Inbox for review |
| Status transition fails (422) | Toast: "Couldn't update task: [server message]". Revert optimistic update. |
| Network error on any mutation | Toast: "Network error. Please try again." Revert optimistic update. |
| Tasks API returns empty list | Each section shows its empty state component |
| User has 0 meetings processed (no tasks ever) | Page shows single full-page EmptyState: "No tasks yet. Tasks will appear after your meetings are processed." No sections rendered. |
| Focus mode with 1 task | Works normally — shows single card, completes immediately after one action |
| Focus mode interrupted (user navigates away) | Mode closes, triage state preserved (already persisted to server) |
| Concurrent triage (two tabs) | React Query refetch on focus handles stale data; worst case is a 404 on already-triaged task — handle gracefully (skip to next) |
| Very long task title (100+ chars) | Truncate with ellipsis in card view (single line); show full title in detail panel |
| Task with skill_context but no suggested_skill | Don't show skill chip or generate button |
| "Create Follow-up" for promise with no account | Follow-up task created without account_id |
| Detail panel open when task is triaged from another section | Panel closes with toast "This task was updated" |

## Constraints

- **Existing backend API is the contract.** Frontend must work with current `/tasks/` endpoints. Only backend change is adding `deferred` status (TASK-01). No new endpoints.
- **Design tokens mandatory.** All colors via `var()` from design-tokens.ts. No hardcoded hex in component code. Enforced by existing pre-commit hook.
- **React Query for all server state.** No Zustand stores for task data. Zustand only if focus mode needs ephemeral UI state (current index, animation direction).
- **Feature directory convention.** All new code in `frontend/src/features/tasks/`. Follows existing pattern from briefing, meetings, accounts features.
- **BrandedCard for card containers.** Use existing component, don't create new card wrappers.
- **60-second triage constraint.** The morning triage flow (either list or focus mode) must enable processing 8 tasks in under 60 seconds. This means: no confirmation dialogs, no multi-step flows, one click per action.

## Anti-Requirements

- This is NOT a project management tool. No subtasks, no dependencies, no Gantt charts, no sprint planning.
- This is NOT a team collaboration tool. No task assignment, no comments, no @mentions, no shared views.
- This does NOT replace the daily brief. The brief is the push summary; the Tasks page is the pull interface for managing commitments.
- This does NOT auto-execute skills. The "Generate" button requires explicit user click. Trust level enforcement is a backend concern.
- This does NOT show all historical tasks. Done section shows last 7 days only. Full history is out of scope.

## Open Questions

All resolved:

1. **`confirmed → done` shortcut:** **Yes.** Add `"done"` to `VALID_TRANSITIONS["confirmed"]` so tasks can skip `in_progress` for quick completions (included in TASK-01). Detail panel "Mark Complete" works from both `confirmed` and `in_progress`.

2. **Skill execution backend:** **Exists.** `POST /api/v1/skills/runs` accepts `{ skill_name, input_text }` and returns `{ run_id, status, stream_url }`. SSE stream at `GET /skills/runs/{run_id}/stream` for real-time progress. TASK-14 wires "Generate Deliverable" to this endpoint, passing `suggested_skill` as `skill_name` and JSON-serialized `skill_context` as `input_text`.

3. **Promise resolution flow:** **Yes, simplified.** "Promises to Me" items get a two-action treatment: "Resolved" (transitions to `done`) and "Not delivered → Follow up" (creates follow-up task in My Commitments). No full status workflow on watchlist items.

## Artifacts Referenced

- **CONCEPT-BRIEF.md**: Brainstorm decisions — layout (stacked sections), triage (dual mode with 3 gestures), commitment split, provenance richness, individual-only V1
- **DESIGN-BRIEF.md**: Component specs — TaskTriageCard, TaskCommitmentCard, TaskWatchlistItem, TaskDetailPanel, TaskFocusMode, TaskSkillChip, TaskQuickAdd, TaskDoneSection. Visual hierarchy, motion specs, accessibility requirements, dark mode tokens, rubric score 9/10.
- **Backend Task model**: `backend/src/flywheel/db/models.py` lines 1342-1409 — Task ORM with all fields, indexes, RLS
- **Backend Task API**: `backend/src/flywheel/api/tasks.py` — 6 endpoints, Pydantic schemas, state machine
- **Frontend design tokens**: `frontend/src/lib/design-tokens.ts` — spacing, typography, colors, shadows
- **Frontend BrandedCard**: `frontend/src/components/ui/branded-card.tsx` — card wrapper with variants
- **Frontend animations**: `frontend/src/lib/animations.ts` — fadeSlideUp, stagger, cardHover patterns
- **Frontend routes**: `frontend/src/app/routes.tsx` — lazy loading pattern for new route

---

## Gaps Found During Generation

1. **[Minor | friction]** The backend `source` field accepts any string, but the frontend assumes a known set ("meeting", "manual", "email", "system"). If the backend sends an unknown source value, the provenance display should fallback to "Task" rather than showing a raw string.

2. **[Minor | friction]** `TaskUpdate` schema doesn't allow updating `account_id` or `meeting_id`. If the user wants to link/unlink a task to an account from the detail panel, a backend schema change is needed. Current spec works around this by making account a read-only display in the panel.

3. **[Minor | hygiene]** The backend `metadata_` field (note trailing underscore, aliased to `metadata` in response) contains skill execution outputs in practice. The spec assumes this but doesn't formally define the metadata structure for skill outputs. This could cause issues when rendering "Generated Output" in the detail panel.

4. **[Major | functional]** The "Create Follow-up" flow for overdue promises creates a new task, but there's no backend field linking the follow-up task back to the original promise task. The "Follow-up created" badge on the promise item would need to be tracked client-side (fragile) or via a new `parent_task_id` field (backend change). Recommendation: track client-side for V1, add `parent_task_id` if the pattern proves valuable.

5. **[Minor | friction]** Focus mode "Edit before confirming" allows editing title, priority, and due date — but `TaskUpdate` doesn't include `task_type` or `commitment_direction`. If the AI misclassifies a task's commitment direction (e.g., marks "theirs" as "yours"), the user can't fix it from focus mode. Consider adding `commitment_direction` and `task_type` to `TaskUpdate`.
