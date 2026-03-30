# Concept Brief: Tasks UI

> Generated: 2026-03-29
> Mode: Brainstorm (Full Board)
> Rounds: 4
> Active Advisors: Bezos, Chesky, PG, Rams, Ive, Hickey, Vogels, Carmack, Torvalds, Helmer (core) + Tufte (data-dense UI), Christensen (multi-JTBD), Slootman (scope discipline)
> Artifacts Ingested: Task model (backend ORM), Task API, Flywheel ritual engine (Stage 4), existing frontend routes, CRM UX memory

## Problem Statement

Flywheel v4.0 extracts 8-10 tasks per day from meetings — commitments you made, promises others made to you, mutual agreements, and signals. These tasks have rich provenance (meeting source, person, commitment direction, suggested skills for auto-execution) but are currently only visible in the static HTML daily brief. There is no interactive surface for triaging, tracking, or acting on tasks.

The gap: Flywheel can *detect* commitments but gives the founder no place to *manage* them. Tasks accumulate without confirmation, promises from others go untracked, and skill-executable tasks sit dormant.

**Reframe from brainstorm:** This is not a task management page. It's a **commitment accountability system** — tracking what you owe others AND what others owe you, with AI-extracted provenance and one-click execution. The "Promises to Me" watchlist is the novel insight that separates this from every task app.

## Proposed Approach

A unified Tasks page with vertically stacked sections serving three jobs (triage, accountability, execution) in a single scrollable surface. Starts embedded as a Briefing widget, graduates to standalone `/tasks` route as volume grows. Individual user only in V1 — no team view.

The key architectural insight: tasks split into two fundamentally different instruments based on commitment direction, each with distinct UX treatment.

## Key Decisions Made

| Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|----------|-----------------|------------------|-------------------|---------------------|
| Layout | Vertically stacked sections | Glanceable morning check needs all info visible at once | Tufte (don't hide relationships), Rams (information density) | Tabs — hide information, kill glanceability |
| Default view | Grouped list | Dense, scannable, works at low and medium volume | Rams, Hickey, Slootman | Kanban — wastes space at 8-10 tasks/day, encourages management theater |
| Commitment split | Two distinct sections: "My Commitments" + "Promises to Me" | "I love Bezos' idea on commitment tracker from others" | Bezos (unique value), Tufte (different data = different treatment) | Unified list with direction as filter — loses the watchlist insight |
| Provenance richness | Rich from day one | Provenance is the differentiator, not a nice-to-have | Chesky (11-star), Bezos (meeting context is the superpower) | Start minimal, add richness later — misses the 10x moment |
| Triage UX | Dual mode: list (inline actions) + focus (Tinder-style step-through) | "I like the Tinder-like setup. Worth a shot" + "quick inline actions" | Carmack (60-second constraint), Chesky (focus mode delight) | Single mode — loses flexibility between quick checks and morning ritual |
| Triage actions | Three-way: confirm / dismiss / save for later | "Should be able to save for later" — premature decisions are worse than deferred ones | Hickey ("I don't know yet is legitimate"), Rams (exactly three gestures, no more) | Binary confirm/dismiss — forces premature decisions |
| Team view | Individual only, V1 | "Let us do it for individuals now. Can extend to team later" | Vogels (Zone 1 data model constraint), PG (one user, don't overbuild) | Shared visibility, delegated tasks — architecture complexity for no current user |
| Graduation path | Briefing widget → standalone page | Natural volume-driven graduation | Rams (same component, different constraints) | Standalone page only — overbuilds for current volume |
| Skill execution UX | Deferred to frontend design experts | "I'll let front end design experts guide on this" | — | — |

## Advisory Analysis

### Customer Clarity & Unique Value
Bezos and Chesky identified the core differentiator: meeting provenance and commitment direction. Every task app shows orphaned to-do items. Flywheel's tasks carry context — "You told Sarah at Acme you'd send the one-pager by Friday" is enormously more motivating than "Send one-pager: High priority." The "Promises to Me" watchlist is a founder superpower no competitor offers. Chesky's 11-star extension: when you have a meeting coming up with someone who has an outstanding promise, surface it in meeting prep.

### Design & Information Architecture
Rams, Tufte, and Ive converge on the stacked-sections layout. Tabs fragment attention and hide the relationship between incoming detections and active commitments. The page should breathe — dense when you have work, sparse when caught up. Triage inbox collapses as it empties. Done section collapsed by default. "Promises to Me" is visually lighter than "My Commitments" — different data density for different instruments.

### Simplicity & Scope Discipline
PG, Hickey, Slootman, and Carmack enforced constraints. Kanban rejected for encouraging management theater at low volume. Triage must process 8 tasks in under 60 seconds in either mode. Three triage gestures, no more — no "snooze for 2 days" or "set reminder." Team view deferred entirely. The best task view is the one you close fastest.

### Execution & Technical Shape
Carmack and Hickey shaped the component architecture: the Briefing-embedded widget and standalone page should be the same component with different `maxItems` and layout constraints. Build it as a self-contained module from day one. The triage states map cleanly to the existing status workflow with one addition (`deferred` for save-for-later).

### Strategic Defensibility
Helmer flagged skill execution as the moat signal. Tasks with `suggested_skill` can execute themselves — "Draft a one-pager for Acme" isn't a checkbox, it's a button that produces a deliverable. No other task app does this. Combined with meeting provenance and commitment tracking, this creates a compound advantage that's hard to replicate without the full Flywheel data layer.

## Tensions Surfaced

### Tension 1: Richness vs. Minimalism
- **Chesky** argues: lean into provenance, commitment direction, skill execution — make this feel unlike anything else. The data is there, show it.
- **Rams/PG** argue: title, who, when, done/not-done. Everything else is noise until volume justifies it.
- **Why both are right:** Richness is the differentiator but can become clutter. The key is *selective* richness — show provenance (meeting + person) always, but keep card layout clean.
- **User's resolution:** Start rich. "Provenance is the differentiator."
- **User's reasoning:** At 8-10 tasks/day accumulating, volume justifies richness quickly. The meeting context and commitment direction are the reason this isn't just another Todoist.

### Tension 2: Kanban vs. Grouped List
- **Chesky/Christensen** argue: kanban makes workflow stages visual, drag-to-confirm is satisfying, throughput bottlenecks become visible.
- **Rams/Hickey/Slootman** argue: kanban wastes space at low volume, optimizes for status instead of action, encourages task management theater.
- **User's resolution:** Grouped list as default.
- **User's reasoning:** Density and scannability matter more than visual workflow. Kanban can be a future toggle if volume demands it.

### Unresolved Tensions
- **Skill execution visibility:** Should every task with `suggested_skill` show a "Generate" button, or only after confirmation? Where does output appear (inline, side panel, new page)? Deferred to frontend design phase.

## Page Structure

```
┌──────────────────────────────────────────────────┐
│  TASKS                                    [+ Add]│
│                                                  │
│  ┌─ Triage Inbox ──────────────────────────────┐ │
│  │ "3 new from today's meetings"               │ │
│  │                          [Review All →]      │ │
│  │                                              │ │
│  │ ┌─ task card ──────────────────────────────┐ │ │
│  │ │ "Send Acme one-pager"                    │ │ │
│  │ │ From: Call with Sarah · Mar 28           │ │ │
│  │ │ yours · sales-collateral suggested       │ │ │
│  │ │          [Confirm] [Later] [Dismiss]     │ │ │
│  │ └─────────────────────────────────────────┘ │ │
│  │ ┌─ task card ──────────────────────────────┐ │ │
│  │ │ "Schedule follow-up with legal team"     │ │ │
│  │ │ From: Board sync · Mar 28                │ │ │
│  │ │ yours · no skill suggested               │ │ │
│  │ │          [Confirm] [Later] [Dismiss]     │ │ │
│  │ └─────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────┘ │
│                                                  │
│  ┌─ My Commitments ───────────────────────────┐  │
│  │ This Week (3)                              │  │
│  │ ┌─ task card ────────────────────────────┐ │  │
│  │ │ "Draft partnership proposal for Bolt"  │ │  │
│  │ │ From: Intro call · Mar 25  · Due Fri  │ │  │
│  │ │ ● In Progress  ⚡ sales-collateral     │ │  │
│  │ │                          [Generate]    │ │  │
│  │ └───────────────────────────────────────┘ │  │
│  │                                            │  │
│  │ Next Week (2)                              │  │
│  │ [task cards...]                            │  │
│  │                                            │  │
│  │ Later (1)                                  │  │
│  │ [task cards...]                            │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌─ Promises to Me ───────────────────────────┐  │
│  │ ┌─ watchlist item ──────────────────────┐  │  │
│  │ │ Sarah Chen · Acme                     │  │  │
│  │ │ "Send term sheet"        Due: Mar 31  │  │  │
│  │ │ From: Call · Mar 28      ● On track   │  │  │
│  │ └──────────────────────────────────────┘  │  │
│  │ ┌─ watchlist item ──────────────────────┐  │  │
│  │ │ David Park · Bolt                     │  │  │
│  │ │ "Intro to their CTO"    Due: Mar 25  │  │  │
│  │ │ From: Coffee · Mar 20   🔴 Overdue    │  │  │
│  │ │                      [Create Follow-up]│  │  │
│  │ └──────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌─ Done (last 7 days) ─── [collapsed ▸] ─────┐ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘

Focus Mode (triggered by "Review All"):
┌──────────────────────────────────────────────────┐
│  Reviewing 3 of 7                    [Exit ✕]    │
│  ━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░             │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │                                            │  │
│  │  "Send Acme one-pager with Q1 metrics"    │  │
│  │                                            │  │
│  │  Meeting: Call with Sarah Chen · Mar 28    │  │
│  │  Account: Acme Corp                        │  │
│  │  Commitment: Yours                         │  │
│  │  Suggested: ⚡ sales-collateral            │  │
│  │  Context: "Sarah asked for a one-pager     │  │
│  │  focusing on Q1 pipeline results and       │  │
│  │  integration timeline"                     │  │
│  │                                            │  │
│  │  Priority: High  ·  Due: Mar 31            │  │
│  │                                            │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│   ← Dismiss    ↓ Later    Confirm →              │
│                                                  │
│  [Edit before confirming]                        │
└──────────────────────────────────────────────────┘
```

## Triage State Machine

```
                    ┌──────────┐
                    │ detected │  (AI extracts from meeting)
                    └────┬─────┘
                         │
                    ┌────▼─────┐
              ┌─────┤ in_review├─────┐
              │     └────┬─────┘     │
              │          │           │
         ┌────▼───┐ ┌────▼────┐ ┌───▼─────┐
         │dismissed│ │deferred │ │confirmed│
         └────────┘ └────┬────┘ └────┬────┘
                         │           │
                    (next session)   │
                    re-enters   ┌────▼──────┐
                    in_review   │in_progress│
                                └────┬──────┘
                                     │
                                ┌────▼──┐
                                │ done  │
                                └───────┘
```

## "Promises to Me" Lifecycle

```
Detected from meeting (commitment_direction = "theirs" | "mutual")
    │
    ▼
Watchlist item (passive — user monitors, doesn't act)
    │
    ├── Resolved: they delivered → marked complete, logged
    │
    └── Overdue: due date passed, no resolution
            │
            ▼
        Surface "🔴 Overdue" flag
        Offer [Create Follow-up] → generates new "yours" task
        If next meeting with this person scheduled →
            inject into meeting prep: "Still outstanding: [promise]"
```

## Moat Assessment

**Achievable power(s):**
- **Cornered Resource** — Flywheel's meeting transcripts, relationship graph, and context entries are proprietary data no competitor can access
- **Process Power** — the compound loop (meetings → task extraction → skill execution → deliverables → next meeting prep) creates operational advantage that deepens with use

**Moat status:** Emerging

The Tasks UI alone isn't defensible — any app can show a task list. The moat is the *data layer behind it*: AI-extracted provenance, commitment direction classification, and skill execution tied to a rich context store. The "Promises to Me" watchlist that feeds back into meeting prep is the compound loop that strengthens over time.

## Open Questions

- [ ] **Grouping default for "My Commitments":** Due date (this week / next week / later) vs. by account vs. by source meeting. Due date is most actionable — confirm as default with account/meeting as sort alternatives?
- [ ] **Quick-add UX:** Where does "+ Add Task" live — floating button, page header, command palette? Manual tasks lack meeting provenance — how prominent should manual creation be?
- [ ] **Overdue escalation for "Promises to Me":** Auto-create follow-up task when a promise goes stale? Or surface a nudge the user manually converts? Auto risks noise, manual risks forgetting.
- [ ] **Filter bar:** Build filters (by account, priority, source, date range) in V1 or add when volume exceeds ~50 items?
- [ ] **Skill execution UX:** Where does generated output appear — inline expand, side panel, or new page? Deferred to frontend design.
- [ ] **Briefing widget scope:** How many items shown in the embedded widget? Top 3-5 triage items + overdue promises? Or a summary count with click-through?
- [ ] **Keyboard shortcuts:** What key bindings for triage in focus mode? (e.g., → confirm, ← dismiss, ↓ later, e edit)

## Recommendation

**Proceed to /frontend-design.** The concept is strong and differentiated. The strategic shape is clear — three-section stacked layout with dual triage modes and the novel "Promises to Me" watchlist. All major layout and interaction decisions are resolved. The open questions are implementation details best resolved during design exploration.

Suggested sequence:
1. `/frontend-design` — visual design, component specs, responsive behavior, skill execution UX
2. `/spec` — technical specification consuming this brief + design brief
3. `/gsd` — build it

## Artifacts Referenced

- Task ORM model: `/backend/src/flywheel/db/models.py`
- Task API: `/backend/src/flywheel/api/tasks.py`
- Task extraction: `/backend/src/flywheel/engines/flywheel_ritual.py` (Stage 4)
- Frontend routes: `/frontend/src/app/routes.tsx`
- Existing concept briefs: `/Users/sharan/Projects/flywheel-v2/.planning/CONCEPT-BRIEF-*.md`
- CRM UX feedback memory: informed provenance-first design direction
