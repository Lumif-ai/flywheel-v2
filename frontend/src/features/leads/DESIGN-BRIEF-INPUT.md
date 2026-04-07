# Leads Pipeline — Frontend Design Brief Input

> For the `/frontend-design` design board. This document contains everything
> needed to produce a DESIGN-BRIEF.md for the leads pipeline feature.

---

## 1. What We're Building

A new **Leads Pipeline** page at `/leads` that shows the GTM outbound funnel.
Leads are pre-relationship prospects being worked through a pipeline:
**scraped → scored → researched → drafted → sent → replied → graduated to account**.

This is separate from the existing Pipeline page (which shows accounts). Leads
represent companies we haven't earned a relationship with yet — they live in
their own tables and graduate to accounts when someone replies.

---

## 2. Data Model

### Lead (company-level)
```
name, domain, purpose[] (sales|fundraising|advisors|partnerships),
fit_score (0-100), fit_tier (Strong Fit → No Fit),
fit_rationale, intel (JSONB), source, campaign,
pipeline_stage (computed = MAX across contacts),
contact_count
```

### LeadContact (person-level, under a lead)
```
name, email, title, linkedin_url, role (decision-maker|champion|influencer),
pipeline_stage (per-contact: scraped → scored → researched → drafted → sent → replied)
```

### LeadMessage (per-contact outreach sequence)
```
step_number (1=connection request, 2=follow-up 1, 3=follow-up 2...),
channel (email|linkedin), status (drafted|sent|delivered|replied|bounced),
subject, body, drafted_at, sent_at, replied_at
```

### Key Relationships
- A lead has 1-N contacts
- Each contact has 1-N messages (outreach sequence)
- A lead's pipeline_stage = MAX stage across all its contacts
- Multiple people at the same company can be at different stages
- Each contact can have messages on multiple channels (email step 1 + linkedin step 1)

---

## 3. API Endpoints (backend is built)

| Method | Path | Returns |
|--------|------|---------|
| GET | /leads/ | `{items: Lead[], total, offset, limit}` — filters: pipeline_stage, fit_tier, purpose, search, campaign |
| GET | /leads/pipeline | `{funnel: {scraped: N, scored: N, ...}, total: N}` |
| GET | /leads/{id} | Lead with nested `contacts[].messages[]` |
| POST | /leads/{id}/graduate | `{graduated: true, account_id, account_name}` |

---

## 4. User Workflows

### Workflow A: View the funnel
1. User navigates to /leads
2. Sees funnel bar at top: scraped (142) → scored (89) → researched (34) → drafted (20) → sent (18) → replied (6)
3. Clicks a stage segment to filter the table below
4. Table shows only leads at that stage

### Workflow B: Drill into a lead
1. User clicks a row in the table
2. Right side panel slides in (440px)
3. Panel shows: company info (name, domain, fit tier, stage, rationale)
4. Below: contacts list — each contact shows name, title, email, linkedin, role, their stage
5. User clicks a contact → accordion expands showing message thread
6. Messages show: Step 1 (connection request) → Step 2 (follow-up 1) → Step 3 (follow-up 2)
7. Each message shows channel icon, status badge, subject, body preview
8. Click message to expand full body + timestamps

### Workflow C: Graduate a lead
1. User clicks "Graduate" button (in table or side panel)
2. Confirmation dialog: "Graduate {name} to a full account?"
3. On confirm: lead disappears from table, account created, toast shows success
4. Funnel counts update

### Workflow D: Filter and search
1. Search bar filters by company name/domain (300ms debounce)
2. Dropdown filters: Stage, Fit Tier, Purpose
3. Active filters shown as chips with X to clear
4. Funnel clicks sync with stage filter dropdown

---

## 5. Existing Patterns to Follow

The app already has a Pipeline page (`/pipeline`) with ag-grid, side panel, filters.
The leads page should feel like a sibling — same visual language, same interaction patterns.

### Design System
- Brand accent: `#E94D35` (coral)
- Font: Inter
- Heading: 28px/700, Body: 15px/400, Caption: 13px
- Card radius: 12px, badge radius: pill (9999px)
- Shadows: `0 1px 3px rgba(0,0,0,0.08)`
- Fit tier badge colors already defined in `design-tokens.ts`:
  - Strong Fit: green (rgba(34,197,94,0.1) / #16a34a)
  - Good Fit: blue (rgba(59,130,246,0.1) / #2563eb)
  - Moderate Fit: amber (rgba(245,158,11,0.1) / #d97706)
  - Weak Fit: red (rgba(239,68,68,0.08) / #dc2626)
  - No Fit: gray (rgba(107,114,128,0.08) / #6b7280)

### ag-grid Theme (from existing pipeline)
```javascript
themeQuartz.withParams({
  backgroundColor: '#FFFFFF',
  foregroundColor: '#121212',
  headerBackgroundColor: '#FAFAFA',
  headerTextColor: '#9CA3AF',
  borderColor: '#F3F4F6',
  accentColor: '#E94D35',
  rowHoverColor: '#FAFAFA',
  fontSize: 13,
  rowHeight: 44,
  headerHeight: 36,
})
```

### Side Panel Pattern (from existing pipeline)
- Fixed right, width 440px
- z-index 40, backdrop at z-30 (semi-transparent)
- Slide-in animation: 200ms cubic-bezier
- Close on X button or backdrop click
- Box shadow: `0 8px 30px rgba(0,0,0,0.12)`

---

## 6. New Visual Elements Needing Design

### A. Pipeline Stage Badges
Need distinct colors for 6 stages. Suggested palette:

| Stage | Meaning | Suggested Color |
|-------|---------|-----------------|
| scraped | Raw company found | Gray (#6b7280) |
| scored | Fit score assigned | Purple (#7c3aed) |
| researched | Deep intel gathered | Blue (#2563eb) |
| drafted | Messages written | Amber (#d97706) |
| sent | Outreach delivered | Sky (#0284c7) |
| replied | Got a response | Green (#16a34a) |

### B. Funnel Visualization
Horizontal segmented bar at top of page. Each segment:
- Width proportional to count
- Colored by stage
- Shows label + count
- Clickable to filter
- Active segment highlighted

### C. Contact Cards (in side panel)
Each contact is a card with:
- Name + title + role badge
- Stage badge (per-contact)
- Email/LinkedIn links with icons
- Expand chevron → reveals message thread

### D. Message Thread (in side panel, under contact)
Expandable message sequence:
- Each message: step number, channel icon (Mail/LinkedIn), status badge, subject
- Collapsed by default
- Expanded: full body text, timestamps (drafted, sent, replied)

### E. Purpose Pills
Small pills showing lead purposes: "sales", "fundraising", "advisors", "partnerships"
- Max 2 visible in table cell + "+N" overflow
- Full list visible in side panel

---

## 7. Page Layout (rough wireframe)

```
┌──────────────────────────────────────────────────────────────┐
│  Leads                                                        │
│                                                              │
│  ┌────┬──────┬──────────┬────────┬──────┬────────┐           │
│  │scra│scored│researched│drafted │ sent │replied │  ← Funnel │
│  │142 │  89  │    34    │   20   │  18  │   6    │           │
│  └────┴──────┴──────────┴────────┴──────┴────────┘           │
│                                                              │
│  [🔍 Search...]  [Stage ▾] [Fit ▾] [Purpose ▾]              │
│                                                              │
│  ┌──────────────────────────────────────────────┬───────────┐│
│  │ Company  │Stage│ Fit  │Con│Purpose │Src│Date│Act│         ││
│  ├──────────┼─────┼──────┼───┼────────┼───┼────┼───│  Side   ││
│  │ Acme Corp│ ●sent│Strong│ 3 │sales   │scr│2d │ ⟶ │  Panel  ││
│  │ acme.com │     │      │   │        │   │    │   │         ││
│  ├──────────┼─────┼──────┼───┼────────┼───┼────┼───│ Company ││
│  │ TechStart│●draf│Good  │ 1 │fund    │mcp│5d │ ⟶ │ info    ││
│  │ tech.io  │     │      │   │        │   │    │   │         ││
│  ├──────────┼─────┼──────┼───┼────────┼───┼────┼───│ Contacts││
│  │ ...      │     │      │   │        │   │    │   │ ├─Jane  ││
│  │          │     │      │   │        │   │    │   │ │ ├msg1 ││
│  │          │     │      │   │        │   │    │   │ │ ├msg2 ││
│  │          │     │      │   │        │   │    │   │ ├─John  ││
│  │          │     │      │   │        │   │    │   │         ││
│  │          │     │      │   │        │   │    │   │[Graduate]││
│  └──────────────────────────────────────────────┴───────────┘│
│                                                              │
│  25 ▾ rows    ← 1-25 of 309 →                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 8. Components to Design

| Component | New/Existing | Notes |
|-----------|-------------|-------|
| LeadsPage | New | Main page orchestrator |
| LeadsFunnel | New | Horizontal segmented funnel bar |
| LeadsFilterBar | New (based on pipeline) | Search + 3 single-select dropdowns |
| LeadSidePanel | New (based on pipeline) | 440px right panel with contacts drill-down |
| ContactCard | New | Expandable contact with message thread |
| MessageThread | New | Outreach sequence visualization |
| StageBadge | New | Colored stage pill (6 stages) |
| PurposePills | New | Purpose tag pills |
| FitTierBadge | Existing | Reuse from pipeline (re-type for Lead) |
| EmptyState | Existing | From component library |
| GraduateButton | New (based on pipeline) | Simple graduate action |

---

## 9. Accessibility Requirements

- Funnel segments: keyboard navigable (arrow keys), role="tablist"
- Table: ag-grid handles keyboard nav natively
- Side panel: focus trap, Escape to close, aria-label
- Contact accordion: aria-expanded, Enter/Space to toggle
- Message expand: aria-expanded, keyboard accessible
- All badges: sufficient contrast (WCAG AA)
- Graduate button: aria-label with company name

---

## 10. States to Design

For each component, define: default, hover, active, focus, disabled, loading, empty, error.

Key states:
- **Funnel loading**: shimmer bar (full width, 56px height)
- **Funnel empty**: all segments show 0, muted colors
- **Table loading**: skeleton grid (header + 8 shimmer rows)
- **Table empty**: EmptyState component
- **Side panel loading**: skeleton (header + 3 contact placeholders)
- **Side panel no contacts**: "No contacts added yet" muted text
- **Message expanded**: full body with timestamps
- **Message collapsed**: one-line summary
- **Graduate button disabled**: if already graduated (opacity 0.5)
