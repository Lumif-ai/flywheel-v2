# Requirements: Flywheel v2.1 — CRM Redesign

**Defined:** 2026-03-27
**Core Value:** A founder opens a relationship page and instantly understands the full state — contacts, recent activity, commitments, next actions — without reading raw data or clicking into sub-pages.

## v2.1 Requirements

Requirements for the CRM redesign milestone. Each maps to roadmap phases.

### Data Model

- [ ] **DM-01**: Alembic migration adds `relationship_type text[] NOT NULL DEFAULT '{prospect}'` to accounts with GIN index, preserving all 206 existing accounts as prospects
- [ ] **DM-02**: Alembic migration adds `entity_level text NOT NULL DEFAULT 'company'` to accounts — person-level for advisors and angel investors
- [ ] **DM-03**: Two-phase migration: Phase A adds `relationship_status` and `pipeline_stage` columns, copies data from `status`. Phase B (later) drops old `status` column. Avoids API outage.
- [ ] **DM-04**: Alembic migration adds `ai_summary text` and `ai_summary_updated_at timestamp` to accounts for cached AI synthesis

### Relationship API

- [ ] **RAPI-01**: `GET /api/v1/relationships/` returns relationships filtered by type (prospect/customer/advisor/investor), with signal_count and primary_contact per item — excludes pipeline-only accounts
- [ ] **RAPI-02**: `GET /api/v1/relationships/{id}` returns full detail with contacts, recent timeline, AI summary (cached), commitments, and relationship_type array
- [ ] **RAPI-03**: `PATCH /api/v1/relationships/{id}/type` updates relationship_type array — supports adding/removing types, validates against allowed set, minimum one type
- [ ] **RAPI-04**: `POST /api/v1/relationships/{id}/graduate` promotes from Pipeline with type assignment, sets entity_level for person-type relationships, logs context entry
- [ ] **RAPI-05**: `POST /api/v1/relationships/{id}/notes` creates a ContextEntry linked to the relationship — quick-add notes from the AI panel
- [ ] **RAPI-06**: `POST /api/v1/relationships/{id}/files` uploads and links a file to the relationship — appears in timeline
- [ ] **RAPI-07**: `POST /api/v1/relationships/{id}/synthesize` triggers AI summary regeneration — explicit trigger only (never auto on page load), rate-limited to 1 per 5 minutes, graceful degradation for sparse data
- [ ] **RAPI-08**: `POST /api/v1/relationships/{id}/ask` AI Q&A using existing context entries as RAG context — returns answer with source attribution

### Signal Layer

- [ ] **SIG-01**: `GET /api/v1/signals/` returns signal feed with counts per relationship type for sidebar badges — computed from outreach status changes, next_action_due, and stale relationship detection
- [ ] **SIG-02**: Signal types: reply_received (priority 1), followup_overdue (priority 2), commitment_due (priority 2), stale_relationship (priority 3) — excludes pipeline-only accounts

### Frontend: Pipeline Grid

- [ ] **GRID-01**: Airtable-style data grid replacing current Pipeline table — 8 default columns (Company with avatar, Contact with title, Email mailto, LinkedIn icon, Fit Tier badge, Outreach Status dot, Last Action date, Days Stale colored), 56px rows, column resize/reorder
- [ ] **GRID-02**: Pipeline filter bar with structured filters (Fit Tier multi-select, Outreach Status multi-select, Channel, Staleness range) and text search with 300ms debounce
- [ ] **GRID-03**: Saved view tabs above grid (All, Strong Fit, Needs Follow-up, Stale) — client-side filter presets with coral underline on active
- [ ] **GRID-04**: Graduation flow — "Graduate" button per row opens modal with type selection (Prospect/Customer/Advisor/Investor), calls graduate API, row slides out with animation, sidebar badge increments
- [ ] **GRID-05**: Pipeline pagination with page size selector (25/50/100), stale row warm tint (>14 days), new replies float to top with coral accent

### Frontend: Relationship Surfaces

- [ ] **REL-01**: Sidebar navigation with RELATIONSHIPS section header, four type links (Prospects/Customers/Advisors/Investors) with icons and coral badge counts, Pipeline below — relationships first
- [ ] **REL-02**: Relationship list pages as card grids (3-col desktop, 2-col tablet, 1-col mobile) with type-specific card content, two-layer shadows, sorted by urgency, warm tint background
- [ ] **REL-03**: Relationship detail page with left AI panel (320px) + main content area — header card with avatar, type badges (clickable), tab navigation with type-specific tabs
- [ ] **REL-04**: AI context panel: displays cached AI summary, recent notes, and input for adding notes/asking questions — same input for note capture (saves as ContextEntry) and Q&A (calls ask API)
- [ ] **REL-05**: Timeline tab with directly annotated entries (icon + direction + contact + title + detail + time ago), expandable on click, source attribution, paginated
- [ ] **REL-06**: People tab with contact cards (48px avatar, name, title, email mailto, LinkedIn icon, role badge, last contacted date)
- [ ] **REL-07**: Intelligence tab (Prospects/Customers) with structured labeled data points (Pain, Budget, Competition, Champion, Blocker, Fit Reasoning) — editable on click
- [ ] **REL-08**: Commitments tab with two-column layout (What You Owe / What They Owe), overdue highlighting, source attribution from meetings
- [ ] **REL-09**: Context-aware action bar with type-specific buttons (Prospects: Draft Follow-up/Research/Schedule; Customers: Draft Check-in/Prep Meeting/Research; Advisors: Draft Thank You/Schedule Catch-up/Ask for Intro; Investors: Draft Update/Schedule/Prep Board Deck)

### Frontend: Design System

- [ ] **DS-01**: Design token updates: two-layer card shadows (no borders), translucent badges (bg-opacity-10), 56px row height, avatar component (32px/48px with initials), status dot indicators (8px dot + text), 150ms transitions on all interactive elements
- [ ] **DS-02**: Three emotional registers: Pipeline (cool white, dense, cockpit), Prospects/Customers (warm tint rgba(233,77,53,0.02), generous padding), Advisors/Investors (warmest, more whitespace, personal journal feel)
- [ ] **DS-03**: Empty states for all five surfaces with type-specific illustration, explanatory text, and warm coral CTA button
- [ ] **DS-04**: Skeleton loading states with shimmer animation matching component shapes for grid rows, cards, and detail page sections

---

## v4.0 Requirements — Flywheel OS (Phases A-C)

**Defined:** 2026-03-28
**Core Value:** When a founder says "we'll send a one-pager" in a meeting, that commitment appears in their `/flywheel` task list without any manual entry.
**Spec:** `.planning/SPEC-flywheel-os.md` (reviewed, 16 findings addressed)

### Phase A: Unified Meetings

- [ ] **UNI-01**: Alembic migration 033 adds `calendar_event_id`, `granola_note_id`, `location`, `description` to meetings table. Calendar sync creates Meeting rows with `processing_status='scheduled'` instead of WorkItems.
- [ ] **UNI-02**: Granola sync dedup — fuzzy match by time window (±30min) + title match/attendee overlap against `scheduled` rows. Matched rows enriched with Granola data, status→`'recorded'`.
- [ ] **UNI-03**: Lifecycle status machine: `scheduled` → `recorded` → `processing` → `complete` | `skipped` | `cancelled`. `process-pending` queries both `'pending'` and `'recorded'`.
- [ ] **UNI-04**: `upsert_meeting_row()` replaces `upsert_meeting_work_item()` in calendar_sync.py. Skips rows with `granola_note_id` set.
- [ ] **UNI-05**: Meetings page Upcoming + Past tabs. Backend `GET /meetings/` gains `time=upcoming|past` query param.
- [ ] **UNI-06**: `POST /meetings/{id}/prep` — auto-links account if possible, delegates to account prep engine. Response: `{run_id, stream_url}`.
- [ ] **UNI-08**: `get_meeting_prep_suggestions()` migrated from WorkItem to meetings table queries.

### Phase B: Task Intelligence

- [ ] **TASK-01**: `tasks` table via Alembic with 20 columns, user-level RLS, 3 indexes. ORM model with `source`, `task_type`, `commitment_direction`, `suggested_skill`, `trust_level`, `status` (7 values), `priority`.
- [ ] **TASK-02**: Stage 7 "Task Extraction" in meeting processor. Haiku classifies commitments into 5 categories (your/their/mutual/signal/speculation). Creates Task rows with `suggested_skill`, `skill_context`, `trust_level`, `due_date`. Email tasks always `trust_level='confirm'`.
- [ ] **TASK-03**: Tasks CRUD API at `/api/v1/tasks` — 7 endpoints with response formats, status transition validation, user-scoped.
- [ ] **TASK-04**: Task counts (`tasks_detected`, `tasks_in_review`, `tasks_overdue`) added to `GET /signals/`.

### Phase C: /flywheel CLI Ritual

- [~] **FLY-01**: Superseded by backend-engine rearchitect (SPEC-flywheel-ritual-rearchitect.md). Now ORCH-01/ORCH-06.
- [~] **FLY-02**: Superseded — now Stage 1 of flywheel engine (ORCH-03).
- [~] **FLY-03**: Superseded — now Stage 4 of flywheel engine (ORCH-12).
- [~] **FLY-04**: Superseded — now Stage 3 of flywheel engine (ORCH-05).
- [~] **FLY-05**: Superseded — now Stage 2 of flywheel engine (ORCH-04).
- [~] **FLY-06**: Superseded — auth via MCP JWT session, no FLYWHEEL_API_TOKEN needed.

### Phase A-C: Should Have

- [ ] **UNI-07**: Auto-archive stale calendar events (>7 days, no Granola data) → `processing_status='cancelled'`
- [ ] **TASK-05**: "Their commitments" surface in relationship detail Commitments tab
- [ ] **TASK-06**: Task extraction prompt with 8-10 few-shot examples covering 6 commitment patterns
- [ ] **FLY-07**: Outreach section in `/flywheel` (reads GTM tracker CSV, shows quota)
- [ ] **FLY-08**: "Run all" smart defaults (sync + process + confirm, never outreach)

### Phase A-C: Out of Scope

| Feature | Reason |
|---------|--------|
| Auto-skill execution of detected tasks | Phase E — v4.0 is visibility, not automation |
| Task extraction from emails | Phase F — same pipeline, different source |
| Task extraction from Slack | Deferred — both DMs and channels, later phase |
| Contact discovery (web research for unknowns) | Phase D |
| GTM outreach in /flywheel | Phase G |
| Web UI for /brief and /tasks pages | Phase H |
| Auto-send emails | NEVER — hard constraint from founder |
| Multi-user task assignment | Deferred — Zone 1 only for now |

## Future Requirements

Deferred beyond v2.1/v4.0.

### Pipeline Enhancements
- **GRID-F01**: AI-extracted custom columns (define a column, LLM populates from context)
- **GRID-F02**: Natural language search ("insurance companies that replied last week")
- **GRID-F03**: Pipeline group-by (collapse rows by industry/tier)
- **GRID-F04**: Pipeline column drag-and-drop reorder
- **GRID-F05**: Pipeline bulk select and bulk actions

### Relationship Enhancements
- **REL-F01**: Dual-context linking (Laurie as advisor AND contact at Howden prospect)
- **REL-F02**: Separate Person model (evolve from entity_level flag to dedicated table)
- **REL-F03**: Meeting highlights tab extracted from meeting-processor context entries
- **REL-F04**: Notification drawer (bell icon, slide-in panel, grouped by urgency)
- **REL-F05**: Avatar/photo fetching from LinkedIn or Gravatar

### Integrations
- **INT-F01**: Notification delivery via Slack/email for high-priority signals
- **INT-F02**: Calendar integration for meeting signals
- **INT-F03**: Skill integration for action bar buttons (trigger actual skills, not toast stubs)

## Out of Scope

| Feature | Reason |
|---------|--------|
| General-purpose CRM (deals, forecasting, custom stages) | Intelligence view, not traditional CRM |
| Custom relationship types beyond the four | prospect/customer/advisor/investor covers all current needs |
| Mobile-optimized views | Desktop-first for founders |
| Real-time WebSocket signals | Polling every 60s sufficient at current scale |
| Auto-trigger AI synthesis on page load | Cost runaway risk — explicit triggers only (research finding) |
| Kanban drag-and-drop for Pipeline | Airtable grid is the paradigm, not Kanban |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DM-01 | Phase 54 | ✓ Complete |
| DM-02 | Phase 54 | ✓ Complete |
| DM-03 | Phase 54 | ✓ Complete |
| DM-04 | Phase 54 | ✓ Complete |
| RAPI-01 | Phase 55 | Pending |
| RAPI-02 | Phase 55 | Pending |
| RAPI-03 | Phase 55 | Pending |
| RAPI-04 | Phase 55 | Pending |
| RAPI-05 | Phase 55 | Pending |
| RAPI-06 | Phase 55 | Pending |
| RAPI-07 | Phase 55 | Pending |
| RAPI-08 | Phase 55 | Pending |
| SIG-01 | Phase 55 | Pending |
| SIG-02 | Phase 55 | Pending |
| GRID-01 | Phase 56 | Pending |
| GRID-02 | Phase 56 | Pending |
| GRID-03 | Phase 56 | Pending |
| GRID-04 | Phase 56 | Pending |
| GRID-05 | Phase 56 | Pending |
| DS-01 | Phase 56 | Pending |
| DS-02 | Phase 56 | Pending |
| DS-03 | Phase 56 | Pending |
| DS-04 | Phase 56 | Pending |
| REL-01 | Phase 57 | Pending |
| REL-02 | Phase 57 | Pending |
| REL-03 | Phase 57 | Pending |
| REL-04 | Phase 57 | Pending |
| REL-05 | Phase 57 | Pending |
| REL-06 | Phase 57 | Pending |
| REL-07 | Phase 57 | Pending |
| REL-08 | Phase 57 | Pending |
| REL-09 | Phase 57 | Pending |

| UNI-01 | Phase 64 | Pending |
| UNI-02 | Phase 64 | Pending |
| UNI-03 | Phase 64 | Pending |
| UNI-04 | Phase 64 | Pending |
| UNI-05 | Phase 64 | Pending |
| UNI-06 | Phase 64 | Pending |
| UNI-08 | Phase 64 | Pending |
| TASK-01 | Phase 65 | Pending |
| TASK-02 | Phase 65 | Pending |
| TASK-03 | Phase 65 | Pending |
| TASK-04 | Phase 65 | Pending |
| FLY-01 | Phase 66 | Superseded (Phase 66 rearchitect) |
| FLY-02 | Phase 66 | Superseded (Phase 66 rearchitect) |
| FLY-03 | Phase 66 | Superseded (Phase 66 rearchitect) |
| FLY-04 | Phase 66 | Superseded (Phase 66 rearchitect) |
| FLY-05 | Phase 66 | Superseded (Phase 66 rearchitect) |
| FLY-06 | Phase 66 | Superseded (Phase 66 rearchitect) |

*FLY-01 through FLY-06 superseded by backend-engine rearchitect. See SPEC-flywheel-ritual-rearchitect.md for replacement requirements ORCH-01 through ORCH-12.*

**Coverage:**
- v2.1 requirements: 32 total (all complete)
- v4.0 requirements: 17 Must Have + 5 Should Have = 22 total
- Mapped to phases: 54
- Unmapped: 0

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-28 — v4.0 Flywheel OS requirements added*
