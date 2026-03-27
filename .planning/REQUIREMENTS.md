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

## Future Requirements

Deferred beyond v2.1.

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
| DM-01 | — | Pending |
| DM-02 | — | Pending |
| DM-03 | — | Pending |
| DM-04 | — | Pending |
| RAPI-01 | — | Pending |
| RAPI-02 | — | Pending |
| RAPI-03 | — | Pending |
| RAPI-04 | — | Pending |
| RAPI-05 | — | Pending |
| RAPI-06 | — | Pending |
| RAPI-07 | — | Pending |
| RAPI-08 | — | Pending |
| SIG-01 | — | Pending |
| SIG-02 | — | Pending |
| GRID-01 | — | Pending |
| GRID-02 | — | Pending |
| GRID-03 | — | Pending |
| GRID-04 | — | Pending |
| GRID-05 | — | Pending |
| REL-01 | — | Pending |
| REL-02 | — | Pending |
| REL-03 | — | Pending |
| REL-04 | — | Pending |
| REL-05 | — | Pending |
| REL-06 | — | Pending |
| REL-07 | — | Pending |
| REL-08 | — | Pending |
| REL-09 | — | Pending |
| DS-01 | — | Pending |
| DS-02 | — | Pending |
| DS-03 | — | Pending |
| DS-04 | — | Pending |

**Coverage:**
- v2.1 requirements: 32 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 32

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-27 — initial definition from SPEC-crm-redesign.md + research*
