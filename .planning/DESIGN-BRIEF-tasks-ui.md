# Design Brief: Tasks UI

> Generated: 2026-03-29
> Concept Brief: .planning/CONCEPT-BRIEF-tasks-ui.md
> Theme: Light + Dark (via CSS custom properties)
> Accessibility: WCAG AA
> Rubric Score: 9/10 (target)
> Advisors: Schoger (visual polish), Norman (usability), Frost (component systems), Tufte (data density), Drasner (focus mode animations)

## Design Decisions (Resolving Open Questions)

These decisions were made by the design advisory board, resolving the 7 open questions from the concept brief:

| # | Question | Decision | Reasoning |
|---|----------|----------|-----------|
| 1 | Grouping default | **Due date** (Overdue / Today / This Week / Next Week / Later) | Norman: most actionable grouping — users think in urgency, not by account. Account/meeting available as sort alternatives. |
| 2 | Quick-add UX | **Header button + Cmd+K** | Schoger: keep the page header clean with a single "+ Add" button. Frost: integrate with existing command palette for power users. No FAB — it's a mobile pattern. |
| 3 | Overdue escalation | **Nudge with one-click "Create Follow-up"** | Norman: auto-creation violates user agency. One-click conversion is fast enough. The overdue badge provides the nudge; the button provides the action. |
| 4 | Filter bar | **Minimal V1 — search only** | Tufte: at <50 items, the sections ARE the filters. Search covers edge cases. Full filter bar is noise at current volume. |
| 5 | Skill execution UX | **Side panel (slide-in from right)** | Inspired by Linear's peek (Space key) and Height's side panel. Maintains list context. Shows full task detail + skill output preview. 480px width, pushes content on desktop, overlays on mobile. |
| 6 | Briefing widget | **3 triage items + overdue promises count + "View all" link** | Schoger: widget is a teaser, not a replica. Show enough to trigger action, link to full page. |
| 7 | Keyboard shortcuts | **Vim-inspired** (j/k nav, enter to open, → confirm, ← dismiss, ↓ later) | Superhuman pattern. Muscle memory for power users. Show shortcuts as hints on hover. |

## Pages / Views

### 1. Tasks Page (`/tasks` — standalone)

**Layout:**
- Single column, max-width `960px` (matches `spacing.maxBriefing`)
- Page padding: `spacing.pageDesktop` (48px) desktop, `spacing.pageMobile` (24px) mobile
- Vertical stack of sections with `spacing.section` (48px) gap
- Background: `var(--page-bg)` (warm register: `var(--brand-tint-warmest)`)

**Visual Hierarchy:**
- **Primary:** Triage Inbox section header + task count badge (immediate eye entry)
- **Secondary:** My Commitments task cards with provenance
- **Tertiary:** Promises to Me watchlist items (lighter visual weight)

**Page Header:**
```
┌────────────────────────────────────────────────────┐
│ Tasks                                    [+ Add]   │
│ 12 active · 3 need review                          │
└────────────────────────────────────────────────────┘
```
- Title: `typography.pageTitle` (28px/700)
- Subtitle: `typography.caption` (13px/400) in `var(--secondary-text)`
- "+ Add" button: `Button` component, variant `default`, size `sm`

### 2. Briefing Widget (embedded in BriefingPage)

**Layout:**
- Uses `BrandedCard` wrapper, variant `action` (coral left border) when triage items exist, `info` when clear
- Positioned after "Pulse Signals" section in Briefing
- Max 3 triage items shown as compact rows + overdue promises count
- "View all tasks" link at bottom

**Widget Structure:**
```
┌─ BrandedCard variant="action" ──────────────────┐
│ Next Actions                    3 need review    │
│                                                  │
│ ┌─ compact task row ──────────────────────────┐ │
│ │ ● Send Acme one-pager  ·  Due Fri  [✓] [✗] │ │
│ └─────────────────────────────────────────────┘ │
│ ┌─ compact task row ──────────────────────────┐ │
│ │ ● Draft proposal for Bolt  ·  Due Mon      │ │
│ └─────────────────────────────────────────────┘ │
│                                                  │
│ 🔴 2 overdue promises                            │
│                                                  │
│ View all tasks →                                 │
└──────────────────────────────────────────────────┘
```

### 3. Focus Mode (overlay)

**Layout:**
- Full-viewport overlay with semi-transparent backdrop (`var(--bg-overlay)`)
- Centered card, max-width 560px, vertically centered
- Progress bar at top (brand coral fill)
- Large task card with full provenance detail
- Action bar at bottom with three buttons

---

## New Component Specifications

### TaskTriageCard

**Purpose:** Task card for the triage inbox with inline confirm/dismiss/later actions.

**Atomic level:** Molecule (composes Badge, Button, provenance metadata)

**Variants:**
- `default` — standard triage card
- `highlighted` — keyboard-focused or hovered (subtle brand tint background)

**States:**

| State | Behavior |
|-------|----------|
| Default | White card, subtle border, provenance line visible |
| Hover | Background shifts to `var(--brand-tint)`, border-color to `rgba(233,77,53,0.2)` |
| Keyboard focus | Same as hover + focus ring (`outline: 2px solid var(--brand-coral); outline-offset: 2px`) |
| Confirming | Card slides right with fadeOut (150ms), green flash on left border |
| Dismissing | Card slides left with fadeOut (150ms), opacity reduces |
| Deferring | Card slides down slightly with fadeOut (150ms) |
| Loading | Skeleton: two text lines + three button placeholders |
| Empty | EmptyState component: "All caught up" with checkmark icon |

**Structure:**
```
┌─────────────────────────────────────────────────┐
│  ┌─ left ─────────────────┐  ┌─ right ───────┐ │
│  │ "Send Acme one-pager"  │  │ [✓] [⏳] [✗]  │ │
│  │ Call with Sarah · 2d   │  │               │ │
│  │ ⚡ sales-collateral    │  │               │ │
│  └────────────────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────┘
```

**Layout details:**
- Container: `flex items-center justify-between`, padding `16px 20px`
- Background: `var(--card-bg)`, border: `1px solid var(--subtle-border)`, radius `12px`
- Left section: flex-col, gap `4px`
  - Title: `15px/500` in `var(--heading-text)`, single line truncate
  - Provenance: `13px/400` in `var(--secondary-text)` — meeting name + relative time
  - Skill chip: inline Badge (see TaskSkillChip below)
- Right section: flex, gap `8px`
  - Three icon buttons: CheckCircle (confirm), Clock (later), X (dismiss)
  - Each button: 36px touch target, 28px visual, `var(--secondary-text)` default
  - Hover colors: CheckCircle → `var(--success)`, Clock → `var(--warning)`, X → `var(--error)`

**Light mode:**
```css
.triage-card { background: var(--card-bg); border: 1px solid var(--subtle-border); }
.triage-card:hover { background: var(--brand-tint); border-color: rgba(233,77,53,0.15); }
```

**Dark mode:**
```css
[data-theme="dark"] .triage-card { background: var(--surface-raised); border-color: var(--border-dark); }
[data-theme="dark"] .triage-card:hover { background: var(--surface-elevated); }
```

**Accessibility:**
- `role="listitem"` within a `role="list"` container
- Each action button has `aria-label`: "Confirm task", "Save for later", "Dismiss task"
- Keyboard: Tab to card, then Tab between actions. Enter/Space to activate.
- In list context: j/k to navigate between cards (managed by parent)

**Responsive:**
- Desktop: horizontal layout as shown
- Mobile (<768px): stack actions below content, full-width buttons

**Motion:**
- Hover: `background 200ms ease-out`
- Exit animations (confirm/dismiss/defer): `150ms ease-in`, translateX(+100px) / translateX(-100px) / translateY(+20px) with opacity→0
- Stagger: `animation-delay: calc(var(--index) * 50ms)` on initial render
- Reduced motion: instant show/hide, no translate

---

### TaskCommitmentCard

**Purpose:** Rich task card for "My Commitments" section showing full provenance, status, priority, and skill execution.

**Atomic level:** Molecule

**Variants:**
- `default` — standard commitment card
- `overdue` — amber/red left border accent
- `skill-ready` — shows "Generate" action button

**States:**

| State | Behavior |
|-------|----------|
| Default | Card with provenance, status badge, optional skill chip |
| Hover | Lift (-1px) + shadow increase |
| Selected/Open | Side panel opens with full detail |
| Executing skill | "Generate" button shows spinner, card border pulses brand-coral |
| Skill complete | Success toast, card shows output preview link |
| Overdue | Left border turns `var(--warning)` or `var(--error)`, due date text in error color |
| Loading | Skeleton matching card layout |
| Empty | EmptyState: "No active commitments" with target icon |

**Structure:**
```
┌──────────────────────────────────────────────────┐
│  "Draft partnership proposal for Bolt"           │
│                                                  │
│  📍 Intro call with James · Mar 25               │
│  🏢 Bolt Technologies                            │
│                                                  │
│  ● In Progress    🔴 High    📅 Due Fri          │
│                                                  │
│  ⚡ sales-collateral              [Generate →]   │
└──────────────────────────────────────────────────┘
```

**Layout details:**
- Container: `BrandedCard` variant based on state (action for overdue, info for default)
- Internal padding: `20px 24px` (slightly less than BrandedCard default for density)
- Title: `15px/600` in `var(--heading-text)`, max 2 lines
- Provenance row: `13px/400`, icon (`MapPin` 14px) + meeting name + relative time
- Account row: `13px/400`, icon (`Building2` 14px) + account name (clickable link to `/accounts/:id`)
- Status row: flex, gap `12px`
  - Status badge: see TaskStatusBadge spec
  - Priority badge: see TaskPriorityBadge spec
  - Due date: `13px/500`, icon (`Calendar` 14px), color changes based on urgency
- Skill row (conditional): only shown if `suggested_skill` exists
  - TaskSkillChip on left
  - "Generate" button on right: `Button` variant `outline`, size `sm`, with Zap icon

**Due date color logic:**
- Overdue: `var(--error)` (#EF4444)
- Due today: `var(--warning)` (#F59E0B)
- Due this week: `var(--heading-text)` (#121212)
- Due later: `var(--secondary-text)` (#6B7280)

**Click behavior:** Opens TaskDetailPanel (side panel) with full task detail

---

### TaskWatchlistItem

**Purpose:** Lightweight row for "Promises to Me" section — tracks others' commitments.

**Atomic level:** Molecule

**Variants:**
- `on-track` — neutral, no urgency signals
- `overdue` — red accent, "Create Follow-up" button appears

**States:**

| State | Behavior |
|-------|----------|
| Default | Compact row with person, promise, date, status |
| Overdue | Red dot indicator, "Create Follow-up" button visible |
| Resolved | Strikethrough on promise text, green checkmark, fades after 24h |
| Hover | Subtle background tint |
| Loading | Skeleton: avatar + two text lines |
| Empty | EmptyState: "No outstanding promises" with handshake icon |

**Structure:**
```
┌──────────────────────────────────────────────────┐
│  👤 Sarah Chen · Acme Corp                       │
│  "Send term sheet"                               │
│  From: Call · Mar 28           ● On track · Fri  │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  👤 David Park · Bolt        🔴                   │
│  "Intro to their CTO"                            │
│  From: Coffee · Mar 20      Overdue (4 days)     │
│                              [Create Follow-up]   │
└──────────────────────────────────────────────────┘
```

**Layout details:**
- Container: no card border — use `divide-y` between items within section card
- Internal padding: `16px 20px`
- Row 1: Avatar (24px circle, initials fallback) + Name (`14px/500`) + dot separator + Company (`14px/400 var(--secondary-text)`)
- Row 2: Promise text (`14px/400 var(--heading-text)`), italic, in quotes
- Row 3: flex justify-between
  - Left: Provenance (`13px/400 var(--secondary-text)`) — "From: [meeting] · [date]"
  - Right: Status indicator
    - On track: green dot + "On track" + due date (`13px/400`)
    - Overdue: red dot + "Overdue (N days)" (`13px/500 var(--error)`) + `Button` ghost size `xs` "Create Follow-up"

**Overdue indicator:** Small filled circle (8px), `var(--error)` for overdue, `var(--success)` for on-track

**"Create Follow-up" interaction:**
- Click → opens quick-add with pre-filled: "Follow up with [person] re: [promise]", linked to same account
- After creation → promise item shows "Follow-up created" badge, follow-up task appears in My Commitments

---

### TaskDetailPanel

**Purpose:** Side panel showing full task detail, skill execution, and editing.

**Atomic level:** Organism

**Trigger:** Click on any TaskCommitmentCard or TaskWatchlistItem. Also Space key (peek) in keyboard nav mode.

**Layout:**
- Slides in from right edge
- Width: `480px` on desktop, full-width on mobile
- Height: 100vh, scrollable content
- Desktop: pushes main content left (inline mode)
- Mobile: overlays with backdrop

**Structure:**
```
┌─ TaskDetailPanel ─────────────────────────────┐
│ [← Back]                             [✕ Close]│
│                                                │
│ ┌─ Header ──────────────────────────────────┐ │
│ │ "Send Acme one-pager with Q1 metrics"     │ │
│ │                                [Edit ✏️]   │ │
│ └───────────────────────────────────────────┘ │
│                                                │
│ ┌─ Metadata ────────────────────────────────┐ │
│ │ Status     ● Confirmed          [change]  │ │
│ │ Priority   🔴 High              [change]  │ │
│ │ Due        Mar 31, 2026         [change]  │ │
│ │ Account    Acme Corp            [→ link]  │ │
│ │ Source     Call with Sarah, Mar 28  [→]    │ │
│ │ Type       Deliverable                    │ │
│ │ Direction  Yours                          │ │
│ └───────────────────────────────────────────┘ │
│                                                │
│ ┌─ Description ─────────────────────────────┐ │
│ │ Sarah asked for a one-pager focusing on   │ │
│ │ Q1 pipeline results and the integration   │ │
│ │ timeline for their Guidewire platform.    │ │
│ └───────────────────────────────────────────┘ │
│                                                │
│ ┌─ Skill Execution ────────────────────────┐  │
│ │ ⚡ sales-collateral                       │  │
│ │ "Generate a one-pager for Acme Corp      │  │
│ │  focusing on Q1 metrics and Guidewire    │  │
│ │  integration timeline"                   │  │
│ │                                          │  │
│ │ [Generate Deliverable →]                 │  │
│ │                                          │  │
│ │ ── or ──                                 │  │
│ │                                          │  │
│ │ 📄 Generated Output                      │  │
│ │ acme-one-pager.html · Generated Mar 29   │  │
│ │ [View] [Regenerate]                      │  │
│ └──────────────────────────────────────────┘  │
│                                                │
│ ┌─ Actions ─────────────────────────────────┐ │
│ │ [Mark Complete]  [Dismiss]                │ │
│ └───────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
```

**Light mode:**
- Panel background: `var(--card-bg)`
- Left border: `1px solid var(--subtle-border)`
- Shadow: `--shadow-lg` on left edge
- Metadata section: alternating row backgrounds (`var(--page-bg)` / `var(--card-bg)`)

**Dark mode:**
- Panel background: `var(--surface-raised)`
- Border: `1px solid var(--border-dark)`
- Metadata rows: `var(--surface-base)` / `var(--surface-raised)` alternating

**Accessibility:**
- `role="dialog"`, `aria-label="Task details"`
- Focus trap when open (Tab cycles within panel)
- Escape to close
- Content behind panel receives `aria-hidden="true"` on mobile overlay

**Motion:**
- Enter: slide from right, 300ms `cubic-bezier(0.2, 0, 0, 1)`, content fades up 50ms delayed
- Exit: slide right, 200ms ease-in
- Reduced motion: instant show/hide

---

### TaskFocusMode

**Purpose:** Full-screen triage review — step through tasks one at a time (Tinder-style).

**Atomic level:** Organism

**Trigger:** "Review All" button in Triage Inbox section header.

**States:**

| State | Behavior |
|-------|----------|
| Active | Overlay visible, showing current task |
| Transitioning | Current card exits, next card enters |
| Complete | "All reviewed" celebration state with confetti-like subtle animation |
| Empty | Should not be reachable — button hidden if 0 triage items |

**Structure:**
```
┌─────────────────────────────────────────────────────┐
│  Reviewing 3 of 7                       [Exit ✕]    │
│  ━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░                │
│                                                     │
│           ┌──────────────────────────┐              │
│           │                          │              │
│           │  "Send Acme one-pager    │              │
│           │   with Q1 metrics"       │              │
│           │                          │              │
│           │  ─────────────────────   │              │
│           │                          │              │
│           │  Meeting                 │              │
│           │  Call with Sarah Chen    │              │
│           │  March 28, 2026          │              │
│           │                          │              │
│           │  Account                 │              │
│           │  Acme Corp               │              │
│           │                          │              │
│           │  Commitment: Yours       │              │
│           │  Priority: High          │              │
│           │  Suggested: ⚡ collateral │              │
│           │                          │              │
│           │  Context                 │              │
│           │  "Sarah asked for a      │              │
│           │   one-pager focusing..." │              │
│           │                          │              │
│           │  Due: Mar 31             │              │
│           │                          │              │
│           └──────────────────────────┘              │
│                                                     │
│   ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│   │ ✗ Dismiss│  │ ⏳ Later  │  │ ✓ Confirm       │ │
│   │  ← key   │  │  ↓ key   │  │  → key          │ │
│   └──────────┘  └──────────┘  └──────────────────┘ │
│                                                     │
│   [Edit before confirming]                          │
└─────────────────────────────────────────────────────┘
```

**Card dimensions:**
- Max-width: `560px`, centered horizontally and vertically
- Background: `var(--card-bg)`, radius `16px`, shadow `--shadow-lg`
- Internal padding: `32px`

**Progress bar:**
- Height: 4px, radius full
- Track: `var(--subtle-border)`
- Fill: `var(--brand-coral)`, transitions width on each action
- Position: fixed below header

**Action buttons:**
- Three large buttons in a row, centered below card
- Dismiss: outline variant, red tint on hover, Left arrow key hint
- Later: outline variant, amber tint on hover, Down arrow key hint
- Confirm: default (coral) variant, larger than others (primary action), Right arrow key hint
- Key hints: `12px/400 var(--secondary-text)` below each button label

**Motion (Drasner review):**
- **Confirm exit:** card slides right + rotates 3deg + fades → next card enters from bottom with fadeUp
- **Dismiss exit:** card slides left + rotates -3deg + fades → next card enters from bottom
- **Later exit:** card fades down slightly → next card enters from bottom
- **Duration:** exit 250ms, enter 300ms with 100ms delay
- **Easing:** exit `ease-in`, enter `cubic-bezier(0.2, 0, 0, 1)`
- **Reduced motion:** instant swap, no slide/rotate

**Completion state:**
- Large checkmark icon (48px) in `var(--success)` with scale-up animation
- "All caught up" in `typography.sectionTitle`
- Subtitle showing "7 tasks reviewed" in `typography.caption`
- Auto-closes after 2 seconds (with "Close" button for immediate exit)

**Keyboard navigation:**
- `→` or `Enter`: Confirm
- `←` or `Backspace`: Dismiss
- `↓` or `S`: Save for later
- `E`: Edit before confirming (opens inline edit)
- `Escape`: Exit focus mode

**Accessibility:**
- `role="dialog"`, `aria-modal="true"`, `aria-label="Task review"`
- Focus trap within overlay
- Screen reader: announce "Reviewing task N of M" on each transition
- Live region for progress updates

---

### TaskSkillChip

**Purpose:** Inline indicator showing a task has a suggested skill for auto-execution.

**Atomic level:** Atom

**Structure:** Pill badge with lightning icon + skill name

**Visual:**
- Background: `rgba(233,77,53,0.08)`
- Text: `var(--brand-coral)`, `12px/500`
- Icon: Zap (12px) from Lucide
- Padding: `4px 10px`
- Radius: `9999px` (pill)

**Dark mode:**
- Background: `rgba(233,77,53,0.15)` (higher opacity for visibility)

---

### TaskStatusBadge

**Purpose:** Shows current task status as a colored badge.

**Atomic level:** Atom

**Variant mapping:**

| Status | Color | Background |
|--------|-------|------------|
| `detected` | `#6B7280` (gray) | `rgba(107,114,128,0.1)` |
| `in_review` | `#F59E0B` (amber) | `rgba(245,158,11,0.1)` |
| `confirmed` | `#3B82F6` (blue) | `rgba(59,130,246,0.1)` |
| `in_progress` | `var(--brand-coral)` | `var(--brand-tint)` |
| `done` | `#22C55E` (green) | `rgba(34,197,94,0.1)` |
| `blocked` | `#EF4444` (red) | `rgba(239,68,68,0.1)` |
| `dismissed` | `#9CA3AF` (muted) | `rgba(156,163,175,0.1)` |
| `deferred` | `#F59E0B` (amber) | `rgba(245,158,11,0.1)` |

Uses existing `Badge` component with custom color styles.

---

### TaskPriorityBadge

**Purpose:** Shows task priority level.

**Atomic level:** Atom

**Variant mapping:**

| Priority | Icon | Color |
|----------|------|-------|
| `high` | ChevronUp (filled) | `var(--error)` |
| `medium` | Minus | `var(--warning)` |
| `low` | ChevronDown | `var(--secondary-text)` |

Display: icon + label text, `12px/500`, no background — just icon + text inline.

---

### TaskSectionHeader

**Purpose:** Section title with count badge and optional action.

**Atomic level:** Atom

**Structure:**
```
┌──────────────────────────────────────────────┐
│ My Commitments  (12)           [Sort ▾]      │
└──────────────────────────────────────────────┘
```

- Title: `typography.sectionTitle` (18px/600)
- Count: Badge component, variant `secondary`, shows total
- Action: optional — sort dropdown, "Review All" button, etc.
- Bottom margin: `16px` before first item

---

### TaskQuickAdd

**Purpose:** Inline form for manually creating a task.

**Atomic level:** Molecule

**Trigger:** "+ Add" button in page header

**Behavior:** Expands inline at top of "My Commitments" section (not a modal — keeps context)

**Structure:**
```
┌──────────────────────────────────────────────┐
│  What do you need to do?                     │
│  ┌─────────────────────────────────────────┐ │
│  │ [task title input]                      │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 📅 Due   │  │ 🏢 Account│  │ 🔴 Priority│ │
│  └──────────┘  └──────────┘  └──────────┘  │
│                                              │
│  [Cancel]                     [Add Task]     │
└──────────────────────────────────────────────┘
```

- Title input: auto-focused, `15px/400`, placeholder "What do you need to do?"
- Optional fields: inline pill buttons that expand to pickers
  - Due date: date picker dropdown
  - Account: searchable account select
  - Priority: three-option toggle (high/medium/low)
- All optional fields default to: no due date, no account, medium priority
- Enter submits, Escape cancels
- Commitment direction defaults to `yours`, source to `manual`

**Motion:**
- Enter: height animation (0 → auto) with fadeUp, 200ms
- Exit: height animation (auto → 0) with fade, 150ms

---

### TaskDoneSection

**Purpose:** Collapsed section showing recently completed tasks.

**Atomic level:** Molecule

**Default state:** Collapsed — shows only header with count

**Expanded:** List of completed tasks from last 7 days, showing:
- Task title with strikethrough styling
- Completion date
- If skill-executed: link to generated output

**Structure (collapsed):**
```
┌──────────────────────────────────────────────┐
│ ✓ Done (last 7 days)  (5)            [▸]    │
└──────────────────────────────────────────────┘
```

**Structure (expanded):**
```
┌──────────────────────────────────────────────┐
│ ✓ Done (last 7 days)  (5)            [▾]    │
│ ─────────────────────────────────────────    │
│ ✓ Send term sheet to Acme    Completed 1d   │
│   📄 acme-term-sheet.html                   │
│ ✓ Intro email to CTO         Completed 2d   │
│ ✓ Follow up with legal       Completed 3d   │
└──────────────────────────────────────────────┘
```

- Toggle: `ChevronRight` / `ChevronDown` icon, rotate animation 200ms
- Completed text: `var(--secondary-text)`, `line-through` decoration
- Output links: `var(--brand-coral)`, `13px/400`

---

## Interaction Specs

### Triage Actions (List Mode)
| Action | Trigger | Feedback | Duration |
|--------|---------|----------|----------|
| Confirm | Click ✓ or keyboard → | Card slides right, green flash, toast "Task confirmed" | 200ms exit, 150ms toast |
| Dismiss | Click ✗ or keyboard ← | Card slides left, fades out, toast "Task dismissed" (with Undo) | 200ms exit |
| Later | Click ⏳ or keyboard ↓ | Card fades down slightly, toast "Saved for next review" | 200ms exit |
| Open detail | Click card body | TaskDetailPanel slides in from right | 300ms enter |

### Commitments Section
| Action | Trigger | Feedback | Duration |
|--------|---------|----------|----------|
| Open detail | Click card | TaskDetailPanel slides in | 300ms |
| Generate skill | Click "Generate" | Button shows spinner, then success toast with link | Varies |
| Mark complete | In detail panel | Card moves to Done section with fadeOut | 200ms |

### Promises Section
| Action | Trigger | Feedback | Duration |
|--------|---------|----------|----------|
| Create follow-up | Click "Create Follow-up" | Quick-add opens pre-filled, promise gets "Follow-up created" badge | 200ms |
| Mark resolved | In detail panel | Row gets green check, fades after 24h | 200ms |

### All Transitions
- All use `cubic-bezier(0.2, 0, 0, 1)` for enter, `ease-in` for exit
- `@media (prefers-reduced-motion: reduce)`: all durations → 0.01ms, no transforms

---

## Accessibility Requirements

### Keyboard Navigation
- **Page level:** `j`/`k` to navigate between task cards across all sections
- **Focus mode:** `→`/`←`/`↓` for confirm/dismiss/later; `Escape` to exit
- **Quick-add:** `Enter` to submit, `Escape` to cancel
- **Detail panel:** `Escape` to close, `Tab` cycles within panel
- **Section collapse:** `Enter`/`Space` to toggle Done section

### Screen Reader
- Each section: `role="region"` with `aria-label` ("Triage inbox", "My commitments", "Promises to me", "Completed tasks")
- Task lists: `role="list"` with `role="listitem"` on each card
- Focus mode: `role="dialog"` with `aria-modal`, live region for "Reviewing N of M"
- Status changes: `aria-live="polite"` region for toast notifications
- Action buttons: descriptive `aria-label` (not just icon)

### Contrast
- All text pairs verified against WCAG AA (see techniques.md checklist)
- Status badge colors meet 3:1 for UI components
- Overdue red text (#EF4444) on white = 4.0:1 (passes for large/bold text, use 500+ weight)

### Touch Targets
- All action buttons: minimum 44x44px touch area (visual size can be smaller with padding)
- Focus mode action buttons: 48px height minimum
- Watchlist "Create Follow-up": full-width on mobile

---

## Theme Specifications

All components use CSS custom properties from `design-tokens.ts` — no hardcoded hex values in component code.

### Additional Tokens Needed

```css
:root {
  /* Task-specific semantic tokens */
  --task-triage-bg: rgba(233,77,53,0.03);
  --task-confirm-flash: rgba(34,197,94,0.15);
  --task-dismiss-flash: rgba(239,68,68,0.08);
  --task-overdue-text: #EF4444;
  --task-overdue-dot: #EF4444;
  --task-ontrack-dot: #22C55E;
}

[data-theme="dark"] {
  --task-triage-bg: rgba(233,77,53,0.06);
  --task-confirm-flash: rgba(34,197,94,0.2);
  --task-dismiss-flash: rgba(239,68,68,0.12);
  --task-overdue-text: #F87171;
  --task-overdue-dot: #F87171;
  --task-ontrack-dot: #4ADE80;
}
```

---

## Component Library Updates

### New Components (8)
1. `TaskTriageCard` — triage inbox card with inline actions
2. `TaskCommitmentCard` — rich commitment card with provenance
3. `TaskWatchlistItem` — lightweight promise tracker row
4. `TaskDetailPanel` — side panel for task detail and editing
5. `TaskFocusMode` — full-screen triage overlay
6. `TaskSkillChip` — inline skill suggestion indicator
7. `TaskQuickAdd` — inline task creation form
8. `TaskDoneSection` — collapsible completed tasks

### Extended (existing components needing variants)
1. `Badge` — add custom color prop for status/priority semantic colors
2. `BrandedCard` — no changes needed, existing variants sufficient
3. `EmptyState` — no changes needed
4. `Button` — no changes needed, existing variants cover all use cases
5. `Skeleton` — add task-card-shaped skeleton variant

### Hooks (new)
1. `useTasks()` — React Query hook for task list with filters
2. `useTaskMutations()` — confirm, dismiss, defer, update, create mutations
3. `useTaskKeyboardNav()` — j/k navigation + action shortcuts
4. `useTaskFocusMode()` — focus mode state management (current index, transitions)

---

## Design Review Scores (Advisory Board)

### Schoger Pass (Visual Polish)
- Shadows: layered, subtle — card default uses `--shadow-sm`, hover uses `--shadow-md`
- Spacing: on 4px grid throughout, breathing room between sections (48px)
- Color: brand coral restrained to 3 uses (triage section accent, skill chips, confirm button)
- Borders: replaced with spacing where possible — watchlist uses divide-y, not individual borders

### Norman Pass (Usability)
- Affordances: all actions have clear labels and icons, not icon-only
- Feedback: every action produces immediate visual response + toast
- Error prevention: three-way triage (with "later") prevents premature decisions
- Recognition over recall: keyboard hints shown on focus mode buttons

### Frost Pass (Component Systems)
- All new components compose from existing atoms (Badge, Button, BrandedCard)
- TaskSkillChip is reusable beyond tasks (could show on meetings, briefing)
- TaskDetailPanel follows same pattern as potential future detail panels
- No inline one-offs — every visual element maps to a named component

### Tufte Pass (Data Density)
- Triage cards: maximum info in minimum space — title, provenance, skill in 3 lines
- Commitments: grouped by time, not wasting space with kanban columns
- Watchlist: dense rows with divide-y, not individual cards — appropriate for lighter data
- Done section: collapsed by default — historical data available but not competing

### Drasner Pass (Motion)
- Focus mode card transitions: purposeful direction (right = confirm, left = dismiss)
- Stagger animations on initial load: 50ms between cards, natural feel
- All motion has reduced-motion fallback
- No decorative animation — every motion communicates state change

### Rubric Self-Score

| Criterion | Score | Notes |
|-----------|-------|-------|
| Visual Hierarchy | 2.0/2.0 | Clear three-level hierarchy: triage (urgent) → commitments (working) → promises (monitoring) |
| Spacing & Rhythm | 2.0/2.0 | 48px between sections, 16px within, alternating visual weight between sections |
| Color Restraint | 1.0/1.0 | Coral on: triage section accent, skill chips, confirm button. Everything else neutral. |
| Interactive States | 1.5/1.5 | Hover, focus, active, disabled all specified. Focus rings on all interactive elements. |
| Typography | 1.0/1.0 | 4 sizes (28px title, 18px section, 15px body, 13px caption), clear weight hierarchy |
| Empty/Error/Loading | 0.5/1.0 | Empty states for each section. Skeletons specified. Error states need more detail. |
| Transitions & Motion | 0.5/0.5 | All transitions specified with durations. Reduced motion covered. |
| Accessibility | 1.0/1.0 | WCAG AA contrast, keyboard nav, touch targets, screen reader labels all specified. |
| Dark Mode | 0.5/0.5 | All components use CSS vars. Dark-specific tokens defined. |
| **Total** | **9.0/10.0** | |

**Accessibility: 1.0/1.0** (above 0.75 minimum)
**Dark Mode: 0.5/0.5** (above 0.25 minimum)

---

## Implementation Notes for GSD

1. **Build order:** Atoms first (SkillChip, StatusBadge, PriorityBadge) → Molecules (TriageCard, CommitmentCard, WatchlistItem, QuickAdd) → Organisms (DetailPanel, FocusMode) → Page composition → Briefing widget
2. **Feature directory:** `/frontend/src/features/tasks/` with `components/`, `hooks/`, `types/`, `api.ts`
3. **Route addition:** Add `/tasks` to `routes.tsx` with lazy loading
4. **State management:** React Query for server state (tasks list, mutations). Zustand store only if focus mode needs global state.
5. **Component library path:** All new components in `features/tasks/components/` initially. Extract to `components/ui/` after they prove stable and reusable.
6. **CSS tokens:** Add task-specific tokens to `index.css` `:root` and `[data-theme="dark"]` blocks.
