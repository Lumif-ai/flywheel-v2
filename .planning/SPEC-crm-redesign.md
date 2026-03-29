# CRM Redesign — Specification

> Status: Draft
> Created: 2026-03-27
> Source: CONCEPT-BRIEF-crm-redesign.md (5-round advisory + design review)

## Overview

Replace the v2.0 flat accounts table with an intelligence-first CRM: a configurable Pipeline data grid for 200+ outreach companies, and four relationship surfaces (Prospects, Customers, Advisors, Investors) that render type-specific layouts with AI synthesis, interactive context panels, and premium design. Every surface shares one detail component with type-driven rendering.

## Core Value

The ONE thing that cannot fail: **a founder opens a relationship page and instantly understands the full state of that relationship** — who the contacts are, what happened recently, what's owed, and what to do next — without reading raw data or clicking into sub-pages.

## Users & Entry Points

| User Type | Entry Point | Primary Goal |
|-----------|-------------|--------------|
| Founder (daily) | Sidebar → Pipeline | Triage outreach: filter, act, graduate |
| Founder (relationship) | Sidebar → Prospects/Customers/Advisors/Investors | Deep-dive a specific relationship: review, prep, follow up |
| Founder (signal) | Notification badge / Briefing pulse | Respond to something that needs attention now |

## Requirements

### Must Have

#### Data Model

- **DM-01**: Add `relationship_type` column to `accounts` table — PostgreSQL text array (`text[]`), default `'{prospect}'`, allowing multiple simultaneous types from: `prospect`, `customer`, `advisor`, `investor`
  - **Acceptance Criteria:**
    - [ ] Alembic migration adds `relationship_type text[] NOT NULL DEFAULT '{prospect}'` to accounts
    - [ ] Existing 206 accounts get `'{prospect}'` as default during migration
    - [ ] An account can hold `'{advisor,investor}'` — multi-type verified by inserting and reading back
    - [ ] RLS policies unchanged — column doesn't affect tenant isolation

- **DM-02**: Add `entity_level` column to `accounts` table — text, values `company` | `person`, default `company`
  - **Acceptance Criteria:**
    - [ ] Alembic migration adds `entity_level text NOT NULL DEFAULT 'company'`
    - [ ] Person-level accounts (advisors, angel investors) set `entity_level = 'person'`
    - [ ] For `entity_level = 'person'`, a single AccountContact exists where the contact IS the relationship (self-contact pattern)

- **DM-03**: Add `relationship_status` column — text, values `active` | `inactive` | `churned`, default `active`. Rename existing `status` to `pipeline_stage` for prospect-specific progression
  - **Acceptance Criteria:**
    - [ ] Migration adds `relationship_status text NOT NULL DEFAULT 'active'`
    - [ ] Migration renames `status` to `pipeline_stage`
    - [ ] Existing accounts: `status='prospect'` → `pipeline_stage='prospect'`, `status='engaged'` → `pipeline_stage='engaged'`
    - [ ] All API responses updated to use new column names
    - [ ] Pipeline grid filters on `pipeline_stage`; Relationship surfaces filter on `relationship_type` + `relationship_status`

- **DM-04**: Add `ai_summary` and `ai_summary_updated_at` columns to `accounts` — text (nullable) and timestamp (nullable) for cached AI synthesis
  - **Acceptance Criteria:**
    - [ ] Migration adds both columns, nullable, default NULL
    - [ ] `ai_summary` stores the generated narrative text
    - [ ] `ai_summary_updated_at` records when the summary was last regenerated
    - [ ] Summary is NULL for all existing accounts (generated on first page load or background job)

#### Backend API

- **API-01**: `GET /api/v1/relationships/` — list relationships (not pipeline), filtered by `relationship_type`
  - **Request:** `?type=prospect&type=customer` (array filter), `?status=active`, `?search=`, `?limit=50&offset=0`
  - **Response:** `{ items: [RelationshipListItem], total: int, offset: int, limit: int }`
  - **RelationshipListItem:** `{ id, name, domain, entity_level, relationship_type: string[], relationship_status, fit_score, fit_tier, contact_count, last_interaction_at, next_action_due, next_action_type, ai_summary_preview: string|null (first 200 chars), signal_count: int, primary_contact: { name, email, title, linkedin_url } | null }`
  - **Acceptance Criteria:**
    - [ ] `GET /api/v1/relationships/?type=advisor` returns only accounts where `'advisor' = ANY(relationship_type)`
    - [ ] `GET /api/v1/relationships/?type=prospect&status=active` returns active prospects only
    - [ ] Response includes `signal_count` (number of attention-needing signals for this account)
    - [ ] Response includes `primary_contact` (first contact by created_at, or self for person-level)
    - [ ] Response excludes accounts where ALL relationship_types are `['prospect']` and `pipeline_stage` is not `engaged` — those stay in Pipeline only

- **API-02**: `GET /api/v1/relationships/{id}` — full relationship detail with AI synthesis
  - **Response:** `{ ...RelationshipListItem, intel, contacts: [ContactResponse], recent_timeline: [TimelineItem], ai_summary: string|null, ai_summary_updated_at: string|null, commitments: [Commitment], relationship_type: string[] }`
  - **Acceptance Criteria:**
    - [ ] Returns full AI summary (from cache) or null if not yet generated
    - [ ] `recent_timeline` merges outreach + context entries + manual notes, sorted chronologically, limit 20
    - [ ] `commitments` extracted from context entries where `source` contains `meeting` and content contains action items (or from a dedicated commitments field)
    - [ ] Contacts include email, linkedin_url, title, role_in_deal — all visible

- **API-03**: `PATCH /api/v1/relationships/{id}/type` — update relationship types
  - **Request:** `{ relationship_type: string[] }` e.g., `["advisor", "investor"]`
  - **Response:** Updated relationship object
  - **Acceptance Criteria:**
    - [ ] Can add a type: `["prospect"]` → `["prospect", "customer"]`
    - [ ] Can remove a type: `["advisor", "investor"]` → `["advisor"]`
    - [ ] Cannot set empty array — at least one type required (400 error)
    - [ ] Validates values against allowed set (400 if invalid type)

- **API-04**: `POST /api/v1/relationships/{id}/graduate` — graduate from Pipeline to Relationship
  - **Request:** `{ relationship_type: string }` — the type to assign (prospect, customer, advisor, investor)
  - **Response:** Updated account with new `relationship_type` array including the assigned type
  - **Acceptance Criteria:**
    - [ ] Adds the requested type to `relationship_type` array (does not replace)
    - [ ] Sets `relationship_status = 'active'`
    - [ ] Creates a ContextEntry with source `"manual:graduation"` documenting the promotion
    - [ ] If type is `advisor` or `investor` (person-level), sets `entity_level = 'person'`
    - [ ] Returns 409 if account already has this relationship type

- **API-05**: `POST /api/v1/relationships/{id}/notes` — quick-add note to a relationship
  - **Request:** `{ content: string, source?: string }` (source defaults to `"manual:note"`)
  - **Response:** Created ContextEntry
  - **Acceptance Criteria:**
    - [ ] Creates a ContextEntry with `account_id` set to the relationship ID
    - [ ] `file_name` set to `"account-notes"`
    - [ ] `detail` auto-generated as first 100 chars of content
    - [ ] Appears immediately in the relationship's timeline
    - [ ] Returns 201 with the created entry

- **API-06**: `POST /api/v1/relationships/{id}/files` — attach file to a relationship
  - **Request:** multipart form with file upload
  - **Response:** Created file record linked to account
  - **Acceptance Criteria:**
    - [ ] File stored via existing Supabase storage pattern
    - [ ] ContextEntry created with `source = "manual:file"` and file reference in metadata
    - [ ] File appears in the relationship timeline as a file-type entry
    - [ ] Accepts PDF, PNG, JPG, DOCX (max 10MB)
    - [ ] Returns 413 if file too large, 415 if unsupported type

- **API-07**: `POST /api/v1/relationships/{id}/synthesize` — trigger AI summary regeneration
  - **Response:** `{ ai_summary: string, updated_at: string }`
  - **Acceptance Criteria:**
    - [ ] Gathers all context entries, outreach activities, and contacts for this account
    - [ ] Sends to LLM with a type-aware prompt (different prompts for prospect vs advisor)
    - [ ] Stores result in `accounts.ai_summary` and `accounts.ai_summary_updated_at`
    - [ ] Returns the generated summary
    - [ ] Degradation: if <3 data points, returns a shorter template-based summary (no LLM call)
    - [ ] Rate-limited: max 1 regeneration per account per 5 minutes (429 if exceeded)

- **API-08**: `POST /api/v1/relationships/{id}/ask` — AI Q&A about a relationship
  - **Request:** `{ question: string }`
  - **Response:** `{ answer: string, sources: [{ id, type, title }] }`
  - **Acceptance Criteria:**
    - [ ] Gathers all context for the account as RAG context
    - [ ] Sends question + context to LLM
    - [ ] Returns answer with source attribution (which context entries were used)
    - [ ] Returns 400 if question is empty
    - [ ] Timeout: 30 seconds max, returns 504 if exceeded

- **API-09**: `GET /api/v1/signals/` — unified signal feed with counts per relationship type
  - **Response:** `{ items: [Signal], counts: { prospect: int, customer: int, advisor: int, investor: int }, total: int }`
  - **Signal:** `{ id, type, priority, account_id, account_name, relationship_type: string[], title, detail, created_at }`
  - **Signal types:** `reply_received` (priority 1), `followup_overdue` (priority 2), `commitment_due` (priority 2), `stale_relationship` (priority 3)
  - **Acceptance Criteria:**
    - [ ] `counts` returns the number of attention-needing signals per relationship type (for sidebar badges)
    - [ ] Signals are computed in real-time from: outreach status changes, next_action_due dates, context entry analysis
    - [ ] `?type=prospect` filters to prospect-only signals
    - [ ] Signals for Pipeline-only accounts (not graduated) are excluded

- **API-10**: Update existing `GET /api/v1/pipeline/` to return enriched PipelineItem
  - **PipelineItem additions:** `primary_contact: { name, email, title, linkedin_url } | null`, `days_since_last_outreach: int | null`
  - **Acceptance Criteria:**
    - [ ] Pipeline returns only accounts where `relationship_type = '{prospect}'` AND `relationship_status != 'active'` (not yet graduated to a relationship surface)
    - [ ] OR: Pipeline returns accounts where `pipeline_stage IN ('prospect', 'sent', 'awaiting')` — not yet engaged
    - [ ] Each item includes primary contact details for inline display
    - [ ] Graduated accounts no longer appear in Pipeline

#### Frontend — Pipeline Grid

- **FE-01**: Replace current PipelinePage with Airtable-style configurable data grid
  - **Acceptance Criteria:**
    - [ ] Grid shows 8 default columns: Company (avatar+name+domain), Contact (name+title), Email (mailto link), LinkedIn (icon link), Fit Tier (translucent badge), Outreach Status (dot+label), Last Action (relative date), Days Stale (colored number)
    - [ ] Column headers are uppercase, 13px, #6B7280, with aggregate stats where applicable
    - [ ] Rows are 56px height with stacked name+domain in first column
    - [ ] Row hover: background shifts to `rgba(233,77,53,0.03)` with subtle elevation, 150ms transition
    - [ ] Row click: opens inline preview panel showing last 3 timeline events
    - [ ] "+" button in header area to add additional columns (Fit Score, Industry, Title, Channel, Notes, Source, Created)
    - [ ] Column resize by dragging header borders
    - [ ] Column reorder by dragging headers
    - [ ] Stale rows (>14 days) have permanent warm background tint
    - [ ] New replies float to top with coral left-border accent for 24 hours

- **FE-02**: Pipeline filter and search bar
  - **Acceptance Criteria:**
    - [ ] Full-width search bar above grid, 44px height, rounded-xl, subtle inner shadow
    - [ ] Placeholder: "Search companies, contacts, or filter by status..."
    - [ ] Text search filters by company name and contact name (300ms debounce)
    - [ ] Dropdown filters for: Fit Tier (multi-select checkboxes), Outreach Status (multi-select), Channel, Staleness range
    - [ ] Active filters shown as removable tags below the search bar
    - [ ] Filters reset offset to 0

- **FE-03**: Pipeline saved views
  - **Acceptance Criteria:**
    - [ ] Horizontal tab bar above the grid: "All", "Strong Fit", "Needs Follow-up", "Stale"
    - [ ] Each tab applies a predefined filter set
    - [ ] Active tab has coral underline (2px)
    - [ ] "Strong Fit": `fit_tier IN ('Strong Fit', 'Good Fit')`
    - [ ] "Needs Follow-up": `last_outreach_status = 'sent' AND days_stale > 7`
    - [ ] "Stale": `days_stale > 14`
    - [ ] Views are client-side filter presets (no server-side saved views in v2.1)

- **FE-04**: Pipeline graduation flow
  - **Acceptance Criteria:**
    - [ ] "Graduate" button visible on each row (inline action)
    - [ ] Click opens modal: "Moving [Company] to Relationships as:" with radio buttons for Prospect, Customer, Advisor, Investor
    - [ ] Confirm calls `POST /api/v1/relationships/{id}/graduate` with selected type
    - [ ] On success: row slides right out of grid (400ms animation), toast: "Moved to [Type]"
    - [ ] Sidebar badge count for the target type increments
    - [ ] React Query invalidates both `pipeline` and `relationships` caches

- **FE-05**: Pipeline pagination
  - **Acceptance Criteria:**
    - [ ] "Showing 1-25 of 206" text below grid
    - [ ] Page size selector: 25, 50, 100
    - [ ] Previous/Next buttons, disabled at boundaries
    - [ ] Page changes use `keepPreviousData` for smooth transition

#### Frontend — Relationship Surfaces

- **FE-06**: Sidebar navigation with five surfaces and badge counts
  - **Acceptance Criteria:**
    - [ ] Sidebar structure (top to bottom): Briefing, Company Profile, Library, **[RELATIONSHIPS section header]**, Prospects, Customers, Advisors, Investors, **[separator]**, Pipeline, **[separator]**, Email, Streams, Settings
    - [ ] Relationship items use icons: Prospects (Target), Customers (Handshake), Advisors (Brain), Investors (Landmark)
    - [ ] Pipeline uses TrendingUp icon
    - [ ] Each relationship item shows coral pill badge with signal count (hidden when 0)
    - [ ] Badge pulses once (300ms spring animation) when count increases
    - [ ] Active route highlights correctly for each surface
    - [ ] Relationship section label "RELATIONSHIPS" is uppercase, 11px, #9CA3AF, non-clickable

- **FE-07**: Relationship list page (shared for all four types)
  - **Acceptance Criteria:**
    - [ ] Card grid layout: 3 columns on desktop (>1024px), 2 on tablet, 1 on mobile
    - [ ] Each card: 12px radius, two-layer shadow, 20px padding, no border
    - [ ] Card content: 48px avatar/logo at top, name (20px, 600 weight), key metadata, signal indicator, quick action icons at bottom
    - [ ] Type-specific card content:
      - Prospects: primary contact, replied signal, fit tier badge
      - Customers: meeting count, health indicator, last interaction
      - Advisors: "What they help with" preview, last meeting date
      - Investors: fund name, partner name, updates owed count
    - [ ] Cards sorted by urgency: items with signals first, then by last_interaction_at desc
    - [ ] Click card → navigates to `/relationships/{id}`
    - [ ] Quick action icons: email (mailto), LinkedIn (external link), schedule (toast: "Coming soon")
    - [ ] Page background: `rgba(233,77,53,0.02)` warm tint
    - [ ] Empty state per type with illustration, explanatory text, and CTA button

- **FE-08**: Relationship detail page with AI panel and type-driven tabs
  - **Acceptance Criteria:**
    - [ ] Layout: 320px left AI panel + main content area
    - [ ] Back link: "← [Type]" navigates to the list page for that type
    - [ ] Header card: 48px avatar, name (28px, 600), domain link, type badges (clickable to change), "Since [date] · [N] interactions"
    - [ ] Header has two-layer shadow, 16px padding, 12px radius
    - [ ] AI panel (left): shows cached AI summary at top, recent notes in middle, input at bottom
    - [ ] AI panel input: "Add a note or ask about [Name]..." with attachment button and send button
    - [ ] Typing a note and pressing Send: creates context entry via API-05, appears in timeline
    - [ ] Attaching a file: uploads via API-06, appears in timeline
    - [ ] Asking a question (prefixed with "?" or detected as question): calls API-08, shows answer inline
    - [ ] Tab navigation below header with coral underline on active tab
    - [ ] Tabs adapt by type:
      - Prospects: Timeline, People, Intelligence, Outreach
      - Customers: Timeline, People, Intelligence, Commitments
      - Advisors: Timeline, Meetings, What They Help With
      - Investors: Timeline, People, Updates Owed, Ask History
    - [ ] Tab switch: content cross-fades, underline slides (200ms)
    - [ ] All transitions: 150ms ease-out minimum

- **FE-09**: Timeline tab
  - **Acceptance Criteria:**
    - [ ] Each entry is a single directly-annotated line: `[icon] [date → contact] [title] · [detail] · [time ago]`
    - [ ] Icons by type: envelope (email), LinkedIn icon, phone (call), calendar (meeting), pencil (note), paperclip (file), brain (context)
    - [ ] Direction shown as → (outbound) or ← (inbound)
    - [ ] Click entry to expand: body preview slides down (200ms), showing full content
    - [ ] Source attribution on each entry: "From meeting-prep skill" or "Manual note"
    - [ ] Paginated: 20 per page, "Load more" button at bottom
    - [ ] New entries (added via AI panel) appear at top immediately (optimistic update)

- **FE-10**: People tab
  - **Acceptance Criteria:**
    - [ ] Card per contact (not table): 48px avatar, name (600 weight), title (400, #6B7280)
    - [ ] Email displayed as clickable mailto link, always visible
    - [ ] LinkedIn displayed as clickable icon, always visible (coral on hover)
    - [ ] Role badge (champion/blocker/influencer/decision-maker) as translucent badge
    - [ ] "Last contacted: [relative date]" in caption
    - [ ] For person-level entities (Advisors, angel Investors): single prominent card, no grid
    - [ ] For company-level: card grid, 2 columns

- **FE-11**: Intelligence tab (Prospects & Customers only)
  - **Acceptance Criteria:**
    - [ ] Structured data points, not paragraphs: `● [Label]  [Value]`
    - [ ] Default fields: Pain Point, Budget, Competition, Champion, Blocker, Fit Reasoning
    - [ ] Values sourced from `account.intel` JSONB + extracted from context entries
    - [ ] Each value is editable on click (inline text input, saves to intel JSONB via PATCH)
    - [ ] Empty fields show "—" with "Click to add" hint on hover

- **FE-12**: Commitments tab (Prospects & Customers)
  - **Acceptance Criteria:**
    - [ ] Two-column layout: "What You Owe" (left) and "What They Owe" (right)
    - [ ] Each commitment: checkbox, description, due date, source ("From [date] meeting")
    - [ ] Overdue items: warm tint background
    - [ ] Completed items: gray text with strikethrough
    - [ ] Can add new commitment manually (inline input at bottom of each column)
    - [ ] Commitments stored as context entries with `source = "commitment"` and structured metadata

- **FE-13**: Action bar (bottom of detail page)
  - **Acceptance Criteria:**
    - [ ] Three context-aware buttons in a row, type-specific:
      - Prospects: "Draft Follow-up", "Research", "Schedule"
      - Customers: "Draft Check-in", "Prep Meeting", "Research"
      - Advisors: "Draft Thank You", "Schedule Catch-up", "Ask for Intro"
      - Investors: "Draft Update", "Schedule", "Prep Board Deck"
    - [ ] Buttons use outline variant, icons from Lucide
    - [ ] For v2.1: buttons show toast "Coming soon — this will trigger [skill name]"
    - [ ] Button labels are context-aware where possible (e.g., if a commitment is overdue: "Draft Mockup Follow-up" instead of generic "Draft Follow-up")

#### Frontend — Signal Layer

- **FE-14**: Sidebar badge counts
  - **Acceptance Criteria:**
    - [ ] `GET /api/v1/signals/` called on app mount, polled every 60 seconds
    - [ ] Badge appears as coral pill next to each relationship type label
    - [ ] Badge hidden when count is 0
    - [ ] Badge animates (scale 1→1.2→1, 300ms spring) when count changes
    - [ ] Counts sourced from `signals.counts` response field

#### Frontend — Design System

- **FE-15**: Design system token updates
  - **Acceptance Criteria:**
    - [ ] Card elevation: `box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)` — no border
    - [ ] Badge style: `bg-opacity-10` tint with matching text color (not solid fill)
    - [ ] Avatar component: 32px (list) / 48px (detail) circle with initials, first letter of name, coral background for primary
    - [ ] Row height: 56px in Pipeline grid with stacked name+subtitle
    - [ ] All transitions: `transition: all 150ms ease-out` on interactive elements
    - [ ] Typography: 4 sizes only (14, 16, 20, 28px), hierarchy via weight (400/500/600) + color (#121212/#6B7280/#9CA3AF)
    - [ ] Skeleton loading: shimmer animation matching component shapes
    - [ ] Status indicators: 8px colored dot + text label (not solid badge)

### Should Have

- **SH-01**: Pipeline column reorder via drag-and-drop
- **SH-02**: Pipeline bulk select and bulk actions (graduate multiple, archive multiple)
- **SH-03**: Pipeline row-hover preview card (mini-timeline of last 3 events)
- **SH-04**: Pipeline column hide via right-click context menu
- **SH-05**: Notification drawer (bell icon, slide-in panel, grouped by urgency)
- **SH-06**: AI summary auto-regeneration on new data (background trigger, not just manual)
- **SH-07**: Meeting highlights tab for Advisors/Investors (extracted from meeting-processor context entries)
- **SH-08**: Relationship creation flow for Advisors/Investors (manual add with name, email, type)

### Won't Have (v2.1)

- AI-extracted pipeline columns (custom column with LLM extraction) — v2.2
- Natural language search in Pipeline ("show me insurance companies that replied") — v2.2
- Notification delivery via Slack/email — v2.2
- Pipeline group-by (collapse rows by industry/tier) — v2.2
- Avatar/photo fetching from LinkedIn or Gravatar — initials only for v2.1
- Separate Person model (Option B) — using account with `entity_level` flag for v2.1
- Calendar integration for meeting signals — v2.2

## Edge Cases & Error States

| Scenario | Expected Behavior |
|----------|-------------------|
| Account has `relationship_type = ['advisor', 'investor']` | Appears in BOTH sidebar sections. Detail page shows both type badges. Tabs show union of both type's tabs. |
| Advisor is also a contact at a Prospect company | Two separate account entries: one person-level (advisor), one company-level (prospect) with the person as a contact. They are NOT linked in v2.1 (Laurie-at-Howden dual context deferred). |
| User graduates a Pipeline company as "Advisor" | `entity_level` changes to `person`. Prompt: "Who is the advisor? [Name, Email]" to create the self-contact. |
| AI summary requested but account has 0 context entries | Returns template: "No context available yet. Add notes, run a research skill, or connect email to build intelligence." |
| AI summary requested but account has 1-2 entries | Returns short template-based summary (no LLM call): "[Name] — [entity_level]. [N] interactions. Last: [date]. [First context entry detail]." |
| User tries to set empty `relationship_type` array | 400 error: "At least one relationship type required" |
| Pipeline shows 0 results after all companies graduated | Empty state: "Pipeline is clear. All companies have been moved to Relationships." |
| Quick-add note with empty content | 400 error: "Note content cannot be empty" |
| File upload exceeds 10MB | 413 error: "File too large. Maximum size is 10MB." |
| AI Q&A times out (>30s) | 504 error in API. Frontend shows: "Couldn't generate an answer. Try a simpler question or check back later." |
| Signal count is stale (polled every 60s) | Acceptable — counts may lag by up to 60 seconds. Badge updates on next poll. |
| Account has relationship_type=['prospect'] but pipeline_stage='engaged' | This IS a graduated prospect — shows in Prospects relationship surface, not in Pipeline |
| Migration runs on existing 206 accounts | All get `relationship_type='{prospect}'`, `entity_level='company'`, `relationship_status='active'`, `pipeline_stage` = old `status` value |

## Constraints

- **Existing stack**: FastAPI + PostgreSQL + SQLAlchemy 2.0 (async) backend, React + Vite + Tailwind + shadcn/ui frontend
- **No manual data entry for Pipeline**: Pipeline companies come from skills/seed. Only graduation promotes them.
- **Company-first for Prospects/Customers**: Contacts belong to accounts. No standalone contact view.
- **Person-first for Advisors/Angels**: The account IS the person. Single self-contact.
- **Tenant isolation**: All queries scoped by tenant_id. RLS on all tables.
- **Design system**: Inter font, #E94D35 coral accent, 12px radius, warm tints. See CONCEPT-BRIEF Design Specification section for full token table.
- **AI synthesis caching**: Summary stored in DB, regenerated on explicit trigger or new data. No LLM call on every page load.

## Anti-Requirements

- This is NOT a general-purpose CRM with deal stages, forecasting, or revenue tracking
- This does NOT replace the Pipeline for outreach management — Pipeline remains the triage surface
- This does NOT support custom relationship types beyond the four (prospect, customer, advisor, investor)
- This does NOT auto-link person-level advisors to their company-level prospect entries (v2.2)
- This does NOT send emails or LinkedIn messages — actions trigger skills or show "coming soon" toasts

## Open Questions

- [ ] **Commitment extraction**: How are commitments extracted from meeting transcripts? Manual only for v2.1, or attempt regex/LLM extraction from context entries with `source = 'meeting-processor'`?
- [ ] **AI summary prompt templates**: What's the prompt structure for each relationship type? Need 4 prompt templates (prospect, customer, advisor, investor) with different emphasis.
- [ ] **Pipeline filter persistence**: Should active filters persist across page navigations (URL params vs local state)?
- [ ] **Dual relationship display**: When a person appears in both Advisors and Investors, should clicking them from Advisors show advisor-focused tabs and from Investors show investor-focused tabs? Or always show all tabs?

## Component Tree

```
AppSidebar (modified)
├── SidebarGroup: Main
│   ├── Briefing
│   ├── Company Profile
│   └── Library
├── SidebarGroup: Relationships (NEW)
│   ├── RelationshipNavItem (Prospects, icon=Target, badge=signal_count)
│   ├── RelationshipNavItem (Customers, icon=Handshake, badge=signal_count)
│   ├── RelationshipNavItem (Advisors, icon=Brain, badge=signal_count)
│   └── RelationshipNavItem (Investors, icon=Landmark, badge=signal_count)
├── SidebarGroup: Pipeline
│   └── PipelineNavItem (icon=TrendingUp)
├── SidebarGroup: Tools
│   ├── Email
│   └── Streams

Routes:
├── /pipeline → PipelinePage (NEW — replaces current)
├── /prospects → RelationshipListPage (type=prospect)
├── /customers → RelationshipListPage (type=customer)
├── /advisors → RelationshipListPage (type=advisor)
├── /investors → RelationshipListPage (type=investor)
├── /relationships/:id → RelationshipDetailPage (shared)
└── /accounts → Redirect to /prospects (backwards compat)

features/pipeline/ (NEW — full rewrite)
├── types/pipeline.ts
├── api.ts
├── hooks/usePipeline.ts
├── hooks/useGraduate.ts
├── components/
│   ├── PipelinePage.tsx
│   ├── PipelineGrid.tsx (the data grid)
│   ├── PipelineRow.tsx
│   ├── PipelineFilters.tsx
│   ├── PipelineViewTabs.tsx
│   ├── GraduationModal.tsx
│   └── PipelinePreviewCard.tsx (hover preview)

features/relationships/ (NEW)
├── types/relationships.ts
├── api.ts
├── hooks/
│   ├── useRelationships.ts (list by type)
│   ├── useRelationshipDetail.ts
│   ├── useTimeline.ts
│   ├── useSignals.ts
│   ├── useSynthesis.ts
│   ├── useAsk.ts
│   ├── useAddNote.ts
│   └── useAddFile.ts
├── components/
│   ├── RelationshipListPage.tsx (shared, type-parameterized)
│   ├── RelationshipCard.tsx (list card, type-aware)
│   ├── RelationshipDetailPage.tsx (shared detail, type-aware)
│   ├── AIPanel.tsx (left panel: summary + notes + input)
│   ├── RelationshipHeader.tsx
│   ├── RelationshipTabs.tsx (type-driven tab config)
│   ├── tabs/
│   │   ├── TimelineTab.tsx
│   │   ├── PeopleTab.tsx
│   │   ├── IntelligenceTab.tsx
│   │   ├── CommitmentsTab.tsx
│   │   ├── OutreachTab.tsx
│   │   ├── MeetingsTab.tsx
│   │   ├── WhatTheyHelpWithTab.tsx
│   │   ├── UpdatesOwedTab.tsx
│   │   └── AskHistoryTab.tsx
│   ├── ActionBar.tsx (type-aware buttons)
│   ├── TypeBadges.tsx (clickable multi-type badges)
│   └── EmptyState.tsx (type-specific)

components/ui/ (additions)
├── Avatar.tsx (enhanced — initials, sizes, coral background)
├── DataGrid.tsx (generic configurable grid component)
├── BadgeDot.tsx (8px dot + text status indicator)
├── SignalBadge.tsx (coral pill for sidebar counts)
```

## Artifacts Referenced

- `.planning/CONCEPT-BRIEF-crm-redesign.md` — 5-round advisory + design review
- Lumif.ai screenshots (3) — campaign cards, sequence builder, leads table
- Current backend: `backend/src/flywheel/db/models.py` (Account, AccountContact, OutreachActivity, ContextEntry)
- Current API: `backend/src/flywheel/api/accounts.py`, `outreach.py`, `timeline.py`, `context.py`
- Current frontend: `frontend/src/features/accounts/`, `pipeline/`, `navigation/`

## Gaps Found During Generation

1. **Commitment storage**: The concept brief mentions a "Commitments" tab but the current schema has no dedicated commitment entity. Commitments will need to be stored as context entries with `source = "commitment"` and structured metadata `{ owner: "you"|"them", description, due_date, completed, source_meeting_date }`. This is functional but may need a dedicated table in v2.2 for better querying.

2. **AI Q&A cost**: The `/ask` endpoint triggers an LLM call on every question. No caching strategy defined for Q&A (unlike synthesis which is cached). For v2.1, accept per-question LLM calls. Monitor cost.

3. **Signal computation**: Signals are described as real-time computed, but computing them on every `GET /signals/` request requires scanning outreach tables and context entries. For v2.1, this is acceptable at current scale (~200 accounts). If scale grows, consider materialized views or a background signal computation job.

4. **Migration backward compatibility**: Renaming `status` → `pipeline_stage` will break the existing v2.0 Pipeline frontend and API until both are updated. The migration and API update must be deployed together. Consider a two-phase migration: add new columns first, then remove old ones.

---
*Spec generated from CONCEPT-BRIEF-crm-redesign.md. Self-reviewed with 7 structural lenses.*
*Next step: `/gsd:new-milestone` to plan execution phases.*
