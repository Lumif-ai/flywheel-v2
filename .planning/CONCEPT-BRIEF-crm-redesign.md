# Concept Brief: CRM Redesign — Intelligence-First Relationship Management

> Generated: 2026-03-27
> Mode: Deep (5 rounds + design advisory)
> Rounds: 5 deliberation rounds + 1 design review round
> Active Advisors: Bezos, Chesky, PG, Rams, Ive, Hickey, Vogels, Carmack, Torvalds, Helmer, Tufte, Christensen, Thiel, Slootman, Thompson, Data Governance + Design Review: Schoger, Norman, Ive, Tufte
> Artifacts Ingested: Lumif.ai screenshots (3), current v2.0 frontend code, backend models, outreach-tracker.csv, context store schema, seed_crm.py

## Problem Statement

The v2.0 CRM shipped as a database viewer — 206 bulk-scraped companies in a plain HTML table. It shows all data equally, treats every company as an "account," and hides the rich intelligence (LinkedIn URLs, email addresses, drafted outreach, meeting transcripts, AI-scored context entries) inside the database where founders can't see it.

The fundamental framing was wrong: "Account" was doing too much work, covering five fundamentally different relationship types with different jobs-to-be-done, different data shapes, and different emotional registers. A founder checking on an advisor relationship and a founder working a sales pipeline are doing completely different jobs.

**What changed from original framing:** The original v2.0 spec treated all companies equally with a single status field. This redesign recognizes that relationship type is the primary dimension — not a status to filter by, but a fundamentally different surface with different layout, different data, and different actions.

## Proposed Approach

Replace the current three pages (Accounts list, Account detail, Pipeline) with **two distinct paradigms, five surfaces**:

### Paradigm 1: Pipeline (Data Grid)
An Airtable-style configurable data grid for the ~200 companies in outreach. Dense, filterable, sortable, with inline actions. This is a **triage cockpit** — scan, filter, act, move on.

### Paradigm 2: Relationships (Intelligence Journal)
A type-aware relationship detail system for the ~15-30 companies/people with real engagement. Each relationship page features an AI-generated narrative summary, chronological timeline, people panel, extracted commitments, and context-aware action buttons. This feels like a **personal relationship journal**, not a CRM.

Five surfaces in the sidebar:
1. **Prospects** — auto-materialized from Pipeline when engagement signals arrive (reply, meeting)
2. **Customers** — companies with active deals/deployments (Satguru, Philips)
3. **Advisors** — individual people who advise you (always person-level, not company-level)
4. **Investors** — VC funds (company-level with multiple contacts) or angel investors (person-level)
5. **Pipeline** — the full outreach grid (200+ companies)

### Key Architectural Insight
The five relationship surfaces share **one detail component** with type-driven rendering. The engineering is not five separate builds — it's one component with five configurations controlling which sections appear, the visual tone, and the AI prompts for suggested actions.

### AI-Native Differentiators
1. **Auto-synthesis** — every relationship page has a living narrative summary computed from context entries, meeting transcripts, outreach history, and email threads. Regenerated on new data, cached otherwise.
2. **Auto-populated pipeline columns** — Pipeline grid columns can be filled by AI extraction from company intel, fit reasoning, meeting notes, and context entries.
3. **Context-aware actions** — action buttons on each relationship page are driven by what the AI knows (e.g., "Draft mockup follow-up" because a meeting transcript mentioned owing a mockup).
4. **Auto-materialization** — prospects are never manually created. They auto-materialize from Pipeline when engagement signals cross a threshold (reply, meeting). The system recognizes a relationship exists.
5. **Graceful degradation** — AI synthesis scales with data density: rich narrative for deep relationships, shorter summary for medium, minimal card for sparse, onboarding prompt for empty.

## Key Decisions Made

| Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|----------|-----------------|------------------|-------------------|---------------------|
| Five separate surfaces | Pipeline + Prospects + Customers + Advisors + Investors as distinct sidebar items | "They serve completely different purposes" — each relationship type has a different JTBD and emotional register | Chesky (different emotions), Christensen (different JTBD) | Two surfaces with type tabs (Slootman/PG recommended, user overrode) |
| Pipeline as Airtable grid | Dense configurable data grid with filters, sorts, column management, inline actions | "Take inspiration from Airtable" — 200+ companies need spreadsheet-density triage, not card layouts | Tufte (data-ink ratio), Rams (progressive disclosure) | Table with fixed columns (v2.0 current) |
| AI synthesis from day one | Build narrative summaries now, accept graceful degradation for sparse data | "We have 8-10 relationships with deep data" — enough to prove the value immediately | Helmer (this IS the moat), Vogels (designed degradation ladder) | Ship UI first, add AI later (Carmack recommended, user overrode) |
| Auto-materialization | Reply/meeting signals promote Pipeline companies to Prospects automatically | "Auto materialize. Everything else lives in pipeline" — no manual account creation for prospects | Thiel (contrarian: CRM that creates itself), Hickey (simple signal-based) | Manual promotion only |
| Advisors are people-first | Advisors linked to individuals, not companies. An advisor can also be a contact at a prospect/customer company | "Laurie advises us but Howden could be a customer" — advisors are personal relationships that may overlap with company relationships | Hickey (separate concerns), Christensen (different JTBD) | All relationships are company-level |
| Investors can be company or person | VC funds = company-level (multiple contacts), angels = person-level | "Sequoia has partners/associates, but an angel is one person" — investors span both entity levels | Pragmatic: matches real-world structure | Force all investors to company-level |
| Multi-type relationships | A person/company can hold multiple relationship types simultaneously | "An advisor can also be an investor" — real relationships don't fit single categories | Hickey (orthogonal dimensions) | Mutually exclusive types |
| Relationships section first in sidebar | Relationships above Pipeline in nav ordering | "Where the magic is" — the intelligence journal is the premium experience, Pipeline is the workhorse | Chesky (lead with magic) | Pipeline first (daily driver argument) |
| Signal layer with badge counts | Badge counts on sidebar items + notification drawer | Missing from v2.0 — "where do signals land?" question revealed no answer | Bezos (where does the founder look first?) | Pulse on Briefing only (v2.0 current) |
| Manual quick-add on every relationship | Notes + file attachments directly on relationship pages | "Should be able to add entries manually too" — hallway conversations and coffee chats need capture | Vogels (system can't know everything) | Skill-generated content only |
| Graduation assigns type | Pipeline → modal: "Move to: Prospect / Customer / Advisor / Investor" | Type assignment happens at the moment of meaningful engagement, not before | Christensen (moment of hire) | Pre-assigned types in Pipeline |
| Cache AI synthesis | Regenerate on new data arrival, serve from cache on page load | Cost-effective while still feeling fresh | Pragmatic: LLM calls per page load too expensive | Real-time generation |
| Scoped accounts | Only actively engaged companies are "relationships" | "We agreed accounts are only for actively engaged ones" — 206 scraped companies are pipeline, not accounts | PG (does anyone want a CRM with 206 entries?), Bezos (working backward) | All seeded companies as accounts |

## Advisory Analysis

### Customer Clarity & Jobs-to-Be-Done
Christensen's JTBD analysis revealed five distinct jobs: triage outreach (Pipeline), nurture engaged prospects (Prospects), manage delivery relationships (Customers), maintain brain trust (Advisors), manage cap table (Investors). Bezos working backward confirmed: the trigger, cadence, and core action differ completely for each. A founder opens Pipeline daily to scan and act; they open an Advisor page when they need help or owe a follow-up. Forcing these into one surface means each job is served poorly.

### Design Philosophy — Two Paradigms
Tufte and Ive split cleanly. Pipeline needs maximum data density — Tufte's principle of high data-ink ratio applied as an Airtable grid with 8-13 columns, inline editing, and row-hover previews. Relationship pages need the opposite — Ive's principle of intentional space, warmth, and hierarchy. The AI summary at top, people with clickable LinkedIn/email, narrative timeline, extracted commitments. Rams mediated: default Pipeline view shows 8 columns (not 13), with progressive disclosure for the rest.

### Strategic Defensibility
Helmer identified two achievable powers: **Cornered Resource** (accumulated context store is data no competitor has) and **Switching Costs** (longer usage = richer synthesis = harder to leave). Thompson added the aggregation lens: Flywheel uniquely aggregates context across meetings, outreach, emails, documents, and skills. Traditional CRMs store records; Flywheel stores understanding that compounds. Thiel's contrarian secret: a CRM that creates itself (auto-materialization) inverts the core CRM pain point of data entry.

### Failure Modes & Resilience
Vogels designed the graceful degradation ladder: rich data → full narrative synthesis; medium data → outreach-focused summary; sparse data → minimal card with the triggering signal; empty → onboarding prompt. This ensures no relationship page ever feels "broken" — it feels proportional to what the system knows. The flywheel effect is visible: more engagement → richer pages → more value → more engagement.

### Execution Scoping
Slootman and PG challenged the five-surface count. User overrode — the emotional differentiation matters. Carmack's pragmatism was applied to the architecture: one detail component with five configurations, not five separate builds. The Pipeline grid is the only truly distinct component. This keeps scope manageable while delivering the full vision.

## Tensions Surfaced

### Tension 1: Five Surfaces vs. Two Surfaces
- **Slootman/PG** argue: Two customers, a few advisors, maybe three investors — five surfaces for ~15 relationships is over-engineering. Ship Pipeline + Relationships, split later.
- **Chesky/Christensen** argue: Different emotional registers require different surfaces. An advisor page that looks like a sales pipeline kills the relationship warmth.
- **Why both are right:** Engineering-wise, it IS one component. UX-wise, five sidebar items with type-specific layouts create the emotional differentiation. The cost is low (same component, different config), the benefit is high (each relationship type feels purpose-built).
- **User's resolution:** Five surfaces. "I feel strongly about 5 surfaces."
- **User's reasoning:** Each serves a completely different purpose and deserves its own space.

### Tension 2: AI Synthesis Now vs. UI First
- **Carmack** argues: Ship the beautiful UI with existing data. AI synthesis can follow in v2.2.
- **Helmer** argues: The AI synthesis IS the product. Without it, you've built a prettier database viewer.
- **Vogels** adds: AI synthesis needs data density. Sparse relationships will feel broken.
- **User's resolution:** Build AI synthesis now with graceful degradation.
- **User's reasoning:** 8-10 relationships already have deep data — enough to prove value. Sparse relationships get simpler views, not broken views.

### Tension 3: People vs. Companies as Primary Entity
- **Current model:** Everything is company-first (Account with contacts).
- **Reality:** Advisors are people-first. An advisor can be at a prospect company. An angel investor is a person, not a company.
- **Resolution:** Two entity levels. Companies (prospects, customers, VC funds) have contacts. People (advisors, angels) ARE the relationship. A person can exist in both contexts — Laurie as advisor AND contact at Howden.
- **User's reasoning:** "Advisors will always be individuals." Investors can be either. Multi-type relationships are real (advisor + investor).

### Unresolved Tensions
- **AI synthesis cost at scale**: Caching solves current scale, but 50+ relationships with frequent updates may need background regeneration jobs.
- **Pipeline column AI-extraction**: Acknowledged as killer feature but may need to be v2.2 scope — user didn't explicitly prioritize.

## Moat Assessment

**Achievable power(s):** Cornered Resource, Switching Costs
**Moat status:** Emerging

The context store accumulates intelligence from every skill run, meeting, email, and document. This data is unique to each tenant — no competitor can replicate it. The AI synthesis layer transforms this data into relationship intelligence that gets richer over time, creating switching costs. The longer a founder uses Flywheel, the more the system knows about every relationship, making the AI summaries, suggested actions, and commitment tracking increasingly valuable and hard to abandon.

## Data Model Changes Required

### New: `relationship_type` on Account (or new Relationship entity)
```
relationship_type: prospect | customer | advisor | investor (array — supports multi-type)
entity_level: company | person
status: active | inactive | churned
stage: (prospect-specific) replied | meeting_scheduled | proposal_sent | negotiating
```

### Separate from current `status` field
Current `status` conflates type and health. Separate into:
- `relationship_type[]` — what kind of relationship (can be multiple)
- `relationship_status` — active | inactive | churned
- `pipeline_stage` — prospect-specific progression

### Person-level relationships
Advisors and angel investors need person-level entries (not company-level). Options:
- A: Account model with `entity_level: person` flag and single contact = self
- B: New Person model separate from Account
- Recommended: Option A for v2.1 (minimal schema change), evolve to B when Laurie-at-Howden dual context is needed

### Quick-add context entries
Every relationship page needs a note/file input that creates a ContextEntry linked to that account/relationship. Already supported by the context_entries.account_id FK — just needs a frontend input component and a simple POST endpoint.

## Pipeline Grid Specification

### Default columns (8 visible)
| Column | Source | Type | Sortable | Filterable |
|--------|--------|------|----------|------------|
| Company | account.name + domain | text + link | ✓ | search |
| Contact | primary contact name | person (avatar) | ✓ | search |
| Email | contact.email | mailto link | | |
| LinkedIn | contact.linkedin_url | icon link | | |
| Fit Tier | account.fit_tier | colored badge | ✓ | multi-select |
| Outreach Status | last outreach status | badge | ✓ | multi-select |
| Last Action | last outreach date | relative date | ✓ | date range |
| Days Stale | computed | number + color | ✓ | range |

### Additional columns (via "+" button)
| Column | Source | Type |
|--------|--------|------|
| Fit Score | account.fit_score | number + bar |
| Industry | intel.industry | tag |
| Title | contact.title | text |
| Channel | last outreach channel | icon |
| Notes | contact.notes | truncated text |
| Source | account.source | text |
| Created | account.created_at | date |

### Grid features
- Column resize, reorder, hide
- Per-column filters with type-aware controls
- Multi-column sort
- Group by (industry, tier, status)
- Row hover → preview card (summary, contact, last action)
- Inline actions: Graduate, Archive, Quick note
- Bulk select + bulk actions
- Saved views as tabs
- Stale row highlighting (>14 days, warm tint)
- New replies float to top with accent indicator

### Graduation flow
"Graduate" action opens modal: "Moving [Company] to Relationships as: [Prospect / Customer / Advisor / Investor]" → type assignment happens here → company disappears from Pipeline, appears in Relationships sidebar with badge count increment.

## Relationship Page Specification

### Shared layout (all five types)
```
Header: [Avatar/Logo] Name, domain, type badges, since date
AI Summary: Living narrative (cached, regenerated on new data)
─────────────────────────────────────────────────────────
| People        | Timeline           | Intelligence     |
| (left panel)  | (center, scroll)   | (right panel)    |
─────────────────────────────────────────────────────────
Commitments: What you owe / What they owe
─────────────────────────────────────────────────────────
Quick Add: [Type a note...] [Attach file] [Save]
─────────────────────────────────────────────────────────
Action Bar: [Context-aware buttons based on type + data]
```

### Type-specific sections

| Section | Prospects | Customers | Advisors | Investors |
|---------|-----------|-----------|----------|-----------|
| AI Summary | ✓ | ✓ | ✓ | ✓ |
| People panel | ✓ (contacts) | ✓ (contacts) | ✓ (just them) | ✓ (partners/angels) |
| Timeline | ✓ | ✓ | ✓ | ✓ |
| Intelligence | ✓ (fit, pain) | ✓ (health) | | |
| Commitments | ✓ | ✓ | ✓ | |
| Outreach sequence | ✓ | | | |
| Meeting highlights | | ✓ | ✓ | ✓ |
| What they help with | | | ✓ | |
| Updates owed | | | | ✓ |
| Health score | | ✓ | | |
| Ask history | | | | ✓ |

### People panel enrichment
Each contact shows:
- Avatar (initials-based or fetched)
- Name (bold), title below
- Email as clickable mailto link
- LinkedIn as clickable icon
- Role badge (champion, blocker, decision-maker)
- Last contacted date

### Timeline enrichment
Each entry shows:
- Type icon: email (envelope), LinkedIn (icon), call (phone), meeting (calendar), note (pen), file (paperclip), context (brain)
- Direction indicator (inbound/outbound)
- Rich preview: email subject + first 2 lines of body, meeting summary, note content
- Source attribution: "From meeting-prep skill" or "Manual note"
- Clickable: opens full content in slide-over

### AI Summary degradation ladder
| Data density | Summary style |
|-------------|---------------|
| Rich (meetings + outreach + context) | Full narrative: relationship history, key topics, commitments, suggested next action |
| Medium (outreach + some context) | Shorter: outreach history focused, contact info, last exchange |
| Sparse (just auto-materialized) | Minimal: the signal that triggered materialization, contact info, single CTA |
| Empty (manually added) | Onboarding: "Add context — paste meeting notes, link emails, or run a research skill" |

## Signal Layer Specification

### Sidebar badge counts
Each relationship section shows a count of items needing attention:
- Prospects (3) — 3 prospects with unread replies or overdue follow-ups
- Customers (1) — 1 customer with a commitment due
- Advisors (0) — all caught up
- Investors (1) — 1 update owed

### Signal types
| Signal | Source | Priority | Surfaces in |
|--------|--------|----------|-------------|
| Reply received | outreach status → replied | High | Prospects badge, notification |
| Follow-up overdue | next_action_due < now | Medium | Any type badge, notification |
| Commitment due | extracted from meeting | Medium | Type badge, relationship page |
| Stale relationship | no activity > N days | Low | Type badge |
| Meeting tomorrow | calendar/context | High | Notification, relationship page |
| New intel available | skill run completed | Low | Relationship page |

## Open Questions

- [ ] Pipeline AI-extracted columns (v2.1 or v2.2?) — user expressed desire but didn't explicitly scope
- [ ] Person model evolution — when does Option A (account with person flag) need to evolve to Option B (separate Person entity)?
- [ ] Avatar/photo sourcing — fetch from LinkedIn? Gravatar? Or initials-only for v2.1?
- [ ] Notification delivery — in-app only, or also Slack/email for high-priority signals?
- [ ] Relationship page refresh cadence — how often does AI summary regenerate? On every new data point, or batched?

## Recommendation

**Proceed to /spec** — the concept is thoroughly validated across 5 rounds with 16 advisors. The two-paradigm architecture (grid + journal) is sound. The type-driven rendering approach keeps engineering scope manageable while delivering five emotionally distinct surfaces. AI synthesis with graceful degradation is the right call given 8-10 relationships already have deep data.

**Suggested milestone structure:**
- Phase A: Data model changes (relationship_type, entity_level, pipeline_stage separation)
- Phase B: Pipeline grid (Airtable-style with full column management)
- Phase C: Relationship detail component (shared, type-driven)
- Phase D: AI synthesis engine (summary generation, commitment extraction, action suggestions)
- Phase E: Signal layer (badge counts, notification drawer)

## Design Specification — Premium UI/UX

> Design advisory by Schoger (visual craft), Norman (usability), Ive (intentional design), Tufte (information design). Based on Lumif.ai reference screenshots and Flywheel design system (Inter, #E94D35 coral, 12px radius).

### Design System Additions

| Token | Current v2.0 | Redesigned | Rationale |
|-------|-------------|------------|-----------|
| Card elevation | `border: 1px solid #E5E7EB` | `box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)` | Two-layer shadow creates premium depth without border clutter (Schoger) |
| Badge style | Solid background fill | `bg-opacity-10` tint with matching text color | Softer, integrated, not "stuck on" (Schoger) |
| Table row height | ~40px | 56px with stacked name+title per cell | Human, breathable, matches Lumif.ai contact density (Schoger) |
| Avatar (list views) | None | 32px circle with initials, coral background for primary contact | Humanizes every row — critical for CRM feel (Schoger) |
| Avatar (detail pages) | None | 48px circle, initials or photo | Prominent on relationship pages (Ive) |
| Page background (Pipeline) | `#FFFFFF` | `#FFFFFF` | Cool, efficient register for data grid (Ive) |
| Page background (Relationships) | `#FFFFFF` | `rgba(233,77,53,0.02)` very subtle warm tint | Warm register for relationship surfaces (Ive) |
| Section separators | `border-bottom: 1px solid` | 32px vertical spacing + subtle background shift | Borders are a last resort (Schoger) |
| Tab navigation | None | Horizontal tabs with 2px coral underline on active | Lumif.ai pattern for detail page sections (Schoger) |
| Status indicators | Colored rectangle badge | 8px colored dot + text label | Subtler, more professional (Schoger) |
| Input fields | Basic 1px border, ~36px height | 44px height, subtle inner shadow, `rounded-xl`, `placeholder: #9CA3AF` | Premium interactive feel (Schoger) |
| Row hover | Background color change | Background highlight + 1px elevation increase + 150ms transition | Feels interactive, not just highlighted (Schoger) |
| All transitions | None | `transition: all 150ms ease-out` on interactive elements | Smooth, intentional — nothing should snap (Ive) |
| Typography hierarchy | Multiple font sizes | 3-4 sizes only (14, 16, 20, 28px), hierarchy via weight (400/500/600) + color (#121212/#6B7280/#9CA3AF) | 6+ hierarchy levels without size proliferation (Schoger) |
| Skeleton loading | Basic gray rectangles | Rounded rectangles with subtle shimmer animation matching card/row shapes | Loading states should preview the layout (Norman) |

### Three Emotional Registers (Ive)

**Pipeline — Focused efficiency:**
- Pure white background, dense grid, minimal decoration
- Accent color only on CTAs and active filters
- The register is a cockpit: clean, powerful, information-dense
- Feels like: Bloomberg terminal meets Airtable

**Prospects & Customers — Warm intelligence:**
- Subtle warm tint background (`rgba(233,77,53,0.02)`)
- Cards with two-layer shadows, generous padding (24px)
- AI summary in a distinct block (slightly different background, left accent border)
- Larger avatars (48px), prominent contact info with action icons
- Feels like: a well-organized dossier — comprehensive but inviting

**Advisors & Investors — Personal warmth:**
- Warmest register — more whitespace, larger name typography
- Meeting history as conversation-style timeline
- "What they help with" / commitments in card-based layout
- No fit scores, no pipeline metrics — people, not deals
- Feels like: a personal journal about people you respect

### AI Context Panel (Per Relationship Page)

Inspired by Lumif.ai's AI assistant sidebar. Every relationship page has a **left-side AI panel** that serves three functions:

**Function 1: Intelligence display**
- AI-generated narrative summary of the relationship
- Updates when new data arrives (cached, regenerated on new context)
- Degradation ladder: rich narrative → shorter summary → minimal card → onboarding prompt

**Function 2: Interactive Q&A**
- Chat-like input at bottom: "Ask about [Name]..."
- User can ask: "When was our last meeting?", "What did they say about pricing?", "Summarize our relationship"
- Responses draw from all linked context entries, meeting transcripts, outreach history

**Function 3: Context capture**
- Same input doubles as note entry: type a note, it gets saved as a ContextEntry linked to this relationship
- Attachment button for files (PDFs, images, documents) — stored and linked
- Each added note/file appears in the timeline immediately
- Placeholder text: "Add a note or ask about [Name]..."

**Panel layout:**
```
┌──────────────────────────┐
│ AI Intelligence           │
│                          │
│ "Satguru is your design  │
│  partner for insurance.  │
│  Last call Mar 15 — they │
│  want PDF export. You    │
│  owe a mockup by Friday."│
│                          │
│ ─────────────────────── │
│                          │
│ Recent notes:            │
│ • Mar 20: Coffee chat,   │
│   mentioned Zurich intro │
│ • Mar 18: Sent mockup v1 │
│                          │
│ ─────────────────────── │
│ [📎] Add a note about    │
│      Satguru...    [Send] │
└──────────────────────────┘
```

### Pipeline Grid Design (Tufte + Schoger)

**Grid chrome:**
- No outer border on the grid. Rows separated by `1px solid rgba(0,0,0,0.06)` — barely visible
- Column headers: `font-weight: 500; color: #6B7280; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em`
- Header row background: `#F9FAFB`
- Aggregate stats in headers: "Fit Score (avg: 72)" or "38 stale"

**Row design:**
- 56px row height
- First column: 32px avatar + company name (600 weight) + domain (400 weight, #9CA3AF) stacked
- Contact column: name + title stacked (same pattern)
- Email: truncated email as mailto link, `#6B7280`, underline on hover only
- LinkedIn: small LinkedIn icon, links to profile, coral on hover
- Fit Tier: translucent badge (`bg-opacity-10`)
- Status: 8px dot + text label
- Last Action: relative date, red text if >14 days
- Days Stale: number with color coding (green <7, amber 7-14, red >14)

**Row interaction:**
- Hover: row background shifts to `rgba(233,77,53,0.03)`, subtle elevation
- Click: navigates to relationship detail page (if graduated) or opens inline preview panel (if still pipeline)
- Row-hover preview: small card appears showing last 3 timeline events as mini-timeline

**Smart features:**
- Stale rows (>14 days): subtle warm background tint permanently, not just on hover
- New replies: float to top with a coral left-border accent for 24 hours
- Pagination: "Showing 1-25 of 206" with page size selector (25/50/100)
- Saved view tabs: "All", "Strong Fit", "Needs Follow-up", "Stale" as horizontal tabs above grid
- Column management: "+" button to add columns from catalog, drag to reorder, right-click header to hide

**Search bar:**
- Above the grid, full-width, 44px height
- Placeholder: "Search companies, contacts, or filter by status..."
- Structured filters: dropdowns for Fit Tier, Outreach Status, Channel, Staleness range
- Natural language search deferred to v2.2 (user decision)

### Relationship Detail Page Design (Ive + Norman + Tufte)

**Page structure:**
```
┌────────────────────────────────────────────────────────────┐
│ ← Prospects                                    [⋮ More]   │
├──────────────┬─────────────────────────────────────────────┤
│              │                                             │
│  AI PANEL    │  MAIN CONTENT AREA                         │
│  (left, 320px)                                            │
│              │  ┌──────────────────────────────────────┐  │
│  [Summary]   │  │ [Logo/Avatar 48px] Company Name      │  │
│              │  │ domain.com · Industry                │  │
│  [Notes]     │  │ [Prospect] [Customer] type badges    │  │
│              │  │ Since March 2026 · 12 interactions   │  │
│  [Input]     │  └──────────────────────────────────────┘  │
│              │                                             │
│              │  [Timeline] [People] [Intel] [Commitments] │
│              │  ─────────────────────────────────────────  │
│              │                                             │
│              │  (Tab content area — scrollable)            │
│              │                                             │
│              │                                             │
├──────────────┴─────────────────────────────────────────────┤
│ [✉ Draft Follow-up] [📅 Schedule] [🔍 Research]           │
└────────────────────────────────────────────────────────────┘
```

**Header card:**
- Company logo or 48px avatar with initials
- Company name in `text-2xl font-semibold`
- Domain as clickable link, industry tag
- Relationship type badges (multiple allowed, clickable to change)
- "Since [date]" + interaction count as metadata line
- Two-layer shadow, 16px padding, 12px radius

**Tab navigation:**
- Horizontal tabs with coral underline on active (2px bottom border)
- Tabs adapt by type:
  - Prospects: Timeline, People, Intelligence, Outreach
  - Customers: Timeline, People, Intelligence, Commitments
  - Advisors: Timeline, Meetings, What They Help With
  - Investors: Timeline, People, Updates Owed, Ask History

**Timeline tab (Tufte principles):**
- Each entry is a single annotated line, directly readable:
  > ✉ **Mar 12 → Lori** Sent pricing proposal · *opened 3x, no reply* · **8d ago**
  > 📞 **Mar 8 ← Lori** Demo call · Positive on data extraction · *45 min* · **12d ago**
  > 📝 **Mar 20** Coffee chat — mentioned Zurich intro · *Manual note* · **7d ago**
- Type icons: ✉ email, 💬 LinkedIn, 📞 call, 📅 meeting, 📝 note, 📎 file, 🧠 context
- Direction: → outbound, ← inbound
- Body preview expandable on click (slide-down, not new page)
- "Load more" at bottom (paginated, 20 per page)

**People tab:**
- Card per contact (not table rows)
- Each card: 48px avatar, name (bold), title, role badge (champion/blocker/influencer)
- Below name: email as mailto link, LinkedIn as icon link, both always visible
- "Last contacted: 8d ago" in caption text
- For person-level relationships (Advisors, angel Investors): single prominent card, no list

**Intelligence tab (Tufte — structured data points, not paragraphs):**
```
● Pain Point     Manual compliance tracking across carriers
● Budget         VP approval needed, Q2 evaluation cycle
● Competition    Spreadsheets only — no incumbent vendor
● Champion       Lori Simpson, Director of Risk
● Blocker        VP Engineering — concerned about integration timeline
● Fit Reasoning  Strong match: insurance vertical, compliance pain, 500+ employees
```
Each is a scannable, labeled data point. Editable on click.

**Commitments tab (Norman — clear ownership):**
```
What You Owe                          What They Owe
─────────────                         ──────────────
☐ Send mockup by Friday (Mar 28)      ☐ Provide test data access
☐ Guidewire timeline estimate          ☐ Intro to VP Engineering
✓ Pricing proposal (sent Mar 12)      ✓ NDA signed (Mar 5)
```
Two-column layout. Overdue items highlighted with warm tint. Completed items gray with strikethrough. Source attribution: "From Mar 15 meeting" as caption.

### Relationship List Pages (Each of the Five Surfaces)

Each surface (Prospects, Customers, Advisors, Investors) shows a **card grid**, not a table:

```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ [🏢] Constellation│ │ [🏢] Satguru     │ │ [👤] Laurie Chen │
│ Energy            │ │ Technologies     │ │                  │
│                   │ │                  │ │ Advisor at Howden │
│ Lori Simpson      │ │ 3 meetings       │ │ Last: Mar 20     │
│ Director, Risk    │ │ Last: Mar 15     │ │                  │
│                   │ │                  │ │ "Go-to-market     │
│ ● Replied 2d ago  │ │ ● Mockup due Fri │ │  strategy,        │
│ Fit: Strong       │ │ Health: Good     │ │  insurance intro"  │
│                   │ │                  │ │                   │
│ [✉] [in] [📅]    │ │ [✉] [in] [📅]   │ │ [✉] [📅]         │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

- 3-column grid on desktop, 2 on tablet, 1 on mobile
- Each card: two-layer shadow, 12px radius, 20px padding
- Company logo or person avatar at top
- Name prominent, key contact or description below
- Most important signal in the middle (type-specific)
- Quick action icons at bottom (email, LinkedIn, schedule)
- Cards sorted by urgency: items needing attention first

### Signal Layer Design

**Sidebar badge counts:**
- Small coral pill badge next to each section name: `Prospects (3)`
- Badge only appears when count > 0
- Badge pulses subtly once when a new signal arrives

**Notification drawer:**
- Triggered by bell icon in top-right header area
- Slide-in panel from right (320px wide)
- Groups signals by urgency: "Needs attention now" / "This week" / "FYI"
- Each signal: one-line description + relative time + link to relationship
- Click a signal → navigates to the relationship page, signal marked as read

### Micro-interactions & Transitions (Ive)

| Interaction | Animation | Duration |
|-------------|-----------|----------|
| Page transition | Fade in + subtle slide up (8px) | 200ms ease-out |
| Card hover | Elevation increase + background tint | 150ms ease-out |
| Tab switch | Content cross-fade, underline slides | 200ms ease-in-out |
| Badge count change | Number scales up briefly (1.2x) then settles | 300ms spring |
| Graduation | Row slides right out of grid, toast appears | 400ms ease-out |
| Timeline entry expand | Slide down, content fades in | 200ms ease-out |
| AI panel note saved | Input clears, new entry slides into notes list from bottom | 250ms ease-out |
| Sidebar section collapse | Smooth height animation | 200ms ease-out |
| Quick action icon hover | Icon color transitions to coral | 100ms linear |
| Notification arrive | Bell icon has single subtle bounce | 400ms spring |

### Empty States (Norman)

Every surface needs a purposeful empty state:

**Pipeline (empty):** "Your pipeline is empty. Run a GTM skill to discover prospects, or import a CSV."

**Prospects (empty):** "No engaged prospects yet. When a pipeline company replies or you schedule a meeting, they'll appear here automatically."

**Customers (empty):** "Add your first customer relationship. [+ Add Customer]" with illustration of a handshake.

**Advisors (empty):** "Track your advisory relationships. Add mentors and advisors who guide your company. [+ Add Advisor]" with warm illustration.

**Investors (empty):** "Manage investor relationships. Add VC funds or angel investors. [+ Add Investor]" with illustration.

Each empty state: centered layout, subtle illustration (line art, not cartoon), warm coral CTA button, explanatory text in `#6B7280`.

### Additional Design Decisions from Advisory

| Decision | Direction | Advisory Source |
|----------|-----------|----------------|
| AI panel is interactive (chat + notes + files) | Not just static summary — users can ask questions AND add context | User decision: "Should be able to add new info/context" |
| Pipeline search starts structured | Dropdown filters for v2.1, semantic/NL search for v2.2 | User decision: "Start with structured first" |
| Borders are a last resort | Use shadows, spacing, and background shifts to separate elements | Schoger: "Borders add visual weight and clutter" |
| Row hover shows preview card | Mini-timeline of last 3 events on pipeline row hover | Tufte: "Small multiples for comparison without clicking" |
| Column headers show aggregates | "Fit Score (avg: 72)" style contextual data in headers | Tufte: "Data-ink ratio — headers should inform, not just label" |
| Relationship type badges are clickable | Click to change type via dropdown — zero-friction correction | Norman: "Users will miscategorize. Make correction effortless" |
| Stale signals show action prompts | "It's been 18 days. Draft a check-in?" not just amber color | Norman: "The system should nudge, not just display" |

## Artifacts Referenced

- Lumif.ai screenshots (3): Campaign list with status cards, sequence builder with AI assistant + live email preview, leads table with contact enrichment (LinkedIn, email, profile links)
- Current v2.0 frontend: AccountsPage.tsx, AccountDetailPage.tsx, PipelinePage.tsx, AppSidebar.tsx
- Backend models: Account, AccountContact, OutreachActivity, ContextEntry, Email, EmailDraft, EmailScore, Document
- GTM stack data: outreach-tracker.csv (300+ contacts), gtm-leads-master.xlsx, pipeline-runs.json
- Context store: 9+ source types, JSONB metadata, account_id FK, full-text search

---
*Concept brief generated after 5-round advisory deliberation with 16 advisors + design review with 4 design advisors.*
*Next step: `/spec` to convert decisions into executable specification, or `/gsd:new-milestone` to plan directly.*
