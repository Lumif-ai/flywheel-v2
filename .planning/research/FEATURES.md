# Feature Landscape: Unified Pipeline CRM

**Domain:** AI-native CRM for founders — unified pipeline replacing 3 separate views
**Researched:** 2026-04-06

## Table Stakes

Features users expect from a unified pipeline CRM. Missing = product feels broken or half-baked.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| Single grid showing all entities (leads + accounts + relationships) | This is the entire premise. Attio, Folk, and HubSpot all show companies/people in one surface. Separate views = separate products. | **High** | Requires unified data model or query layer that JOINs `leads`, `accounts`, and their contacts into one result set | AG Grid already used on both Leads and Pipeline pages — reuse the component but unify the data source |
| Continuous stage column (no graduation walls) | Attio and Folk both use a single status/stage field per record. HubSpot uses deal stages that flow continuously. The graduation flow (Lead -> Account -> Relationship) is Flywheel's biggest UX friction — users shouldn't need to "promote" a record to keep working it. | **High** | Needs schema migration: either merge Lead + Account tables, or create a unified view/materialized view. Current `leads.graduated_at` and `accounts.pipeline_stage` + `accounts.relationship_status` are separate progression tracks | This is the hardest backend change. Recommend a single `pipeline_stage` enum that covers the full lifecycle: `scraped -> researched -> contacted -> replied -> meeting_booked -> in_conversation -> proposal -> closed_won -> active_customer -> churned` |
| Side panel for record detail | Every modern CRM (Attio, Folk, Pipedrive, HubSpot) uses click-to-expand side panels. Already built on both Leads and Pipeline pages. | **Low** | Merge `LeadSidePanel` and `PipelineSidePanel` into one `UnifiedSidePanel` that handles both entity types | Existing panels have different data shapes — will need a normalized props interface |
| Full-text search across all records | Attio handles 50k+ contacts with instant search. Users type a name and expect to see every matching company/person regardless of lifecycle stage. | **Medium** | Existing `normalized_name` fields on both tables. Can use pg `ILIKE` or full-text search via `search_vector` on `context_entries` | Search should hit company name, contact name, domain, and notes |
| Filter bar with multi-select facets | Attio, Folk, and Pipedrive all offer combinatorial filters (stage + fit tier + industry + source). Already partially built in `LeadsFilterBar` and `PipelineFilterBar`. | **Medium** | Unify filter state management. Current filters are different per page. | Filter facets: stage, fit tier, relationship type (prospect/customer/advisor/investor), source, last activity recency, owner |
| Column sorting and reordering | Standard spreadsheet behavior. Attio and Clay both allow column drag-to-reorder and click-to-sort. | **Low** | AG Grid supports this natively. Just needs column definitions to enable `sortable: true` and `suppressMovable: false` | Already partially working in existing grids |
| Row click -> side panel -> detail page navigation | Attio: click row = side panel, click "Open" = full page. Folk: same pattern. Two-level progressive disclosure. | **Low** | Side panel already opens on row click. Add a "View full profile" link in the panel header that routes to `/profile/:id` | CompanyProfilePage already exists at `frontend/src/features/profile/` |
| Pagination or virtual scroll for 500+ records | Pipedrive and HubSpot paginate. Attio virtualizes. Both LeadsPage and PipelinePage already have `PAGE_SIZE_OPTIONS = [25, 50, 100]`. | **Low** | AG Grid virtual scrolling is built-in. Keep server-side pagination via existing pattern | Already implemented — just needs unified endpoint |
| Activity recency indicators | Pipedrive shows overdue/due/no-activity badges on pipeline cards. Existing `OutreachDot` and `DaysSinceCell` renderers serve this purpose. | **Low** | Reuse existing cell renderers. `last_interaction_at` exists on Account model. Need to compute equivalent for Leads from `lead_messages.sent_at` | Color-coded dot: green (< 3d), yellow (3-7d), red (> 7d), gray (never) |

## Differentiators

Features that set the product apart. Not expected in a basic CRM but highly valued by founders.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| AI-computed stage suggestions | When a reply comes in or a meeting is booked, suggest (or auto-advance) the stage. No other lightweight CRM does this well. Attio's workflows require manual setup. For founders, the CRM should just know. | **Medium** | Needs signal detection: email reply -> suggest "replied", meeting scheduled -> suggest "meeting_booked". Existing meeting processing and outreach tracking provide the raw signals | Show as a subtle nudge in the side panel: "Acme replied 2h ago — move to Replied?" with one-click accept. Don't auto-advance without user control initially. |
| Unified activity timeline in side panel | Attio's biggest strength: emails, meetings, notes, stage changes — all in one chronological feed per record. Currently split across `outreach_activities`, `meetings`, `context_entries`, and `lead_messages`. | **High** | Must aggregate from 4+ tables. Create a `GET /api/crm/records/:id/timeline` endpoint that unions these sources with a polymorphic shape | This is the single most impactful differentiator. Folk and Pipedrive timelines are basic. Attio's is great. Combine all signal sources into one scrollable feed with type-specific rendering (email card, meeting card, note card, stage-change card) |
| Smart dedup on record creation | When adding a company, detect near-duplicates by normalized name and domain. Show "Did you mean Acme Corp (already in pipeline)?" Clay and Attio both do this. | **Medium** | `normalized_name` and `domain` already indexed with unique constraints. Add a fuzzy match check (Levenshtein or trigram via pg `pg_trgm`) before insert | Prevention > cleanup. Block duplicate creation at the UI level with a merge-or-create dialog |
| Saved views (personal) | Attio's saved views are a core feature: "My hot leads", "Stale accounts", "Investors". Folk has custom views per group. Founders want 3-5 saved filters they toggle between. | **Medium** | New `saved_views` table: `{id, tenant_id, user_id, name, filters: JSONB, sort: JSONB, columns: JSONB, is_default}`. Frontend: tab bar above grid. | Start with personal views only (not shared/team views). The existing `PipelineViewTabs` (all/hot/replied/stale) are hardcoded saved views — make them configurable |
| Inline cell editing (stage, notes, next action) | Attio and Clay both support clicking a cell to edit in-place. More efficient than opening a side panel for a quick stage change. | **Medium** | AG Grid supports `editable: true` on column defs with custom cell editors. Need PATCH endpoint per field. | Only make high-frequency fields inline-editable: stage (dropdown), fit tier (dropdown), next action date (date picker), notes (text). Don't make everything editable — that's a spreadsheet, not a CRM. |
| Multi-source entry with source tagging | Records come from CSV import, manual add, meeting detection, email sync, AI research. Each source should be visible. Attio tags records with source and shows enrichment provenance. | **Low** | `source` field already exists on both Lead and Account. Display as a badge in the grid. Add source to the add-record dialog. | Sources: `manual`, `csv_import`, `meeting_detected`, `email_sync`, `ai_research`, `browser_extension` |
| Keyboard navigation | Attio and Clay both support arrow keys in grid, Enter to open, Escape to close panel. Power users expect this. | **Medium** | AG Grid has built-in keyboard nav. Wire Enter -> open side panel, Escape -> close. Add Cmd+K for quick search. | Low effort, high perceived quality. Ship in v1 of unified view. |
| Quick-add row at bottom of grid | Airtable's "+" row at the bottom. Type a company name, hit Enter, record created with defaults. | **Low** | AG Grid `pinnedBottomRowData` with a custom "Add new" row renderer. On submit, POST to `/api/crm/records` with dedup check. | Much faster than opening a modal. Attio does this. |
| Outreach sequence status as a column | Show "Step 2/4 sent" or "Waiting for reply" inline in the grid. Folk integrates sequences directly in the pipeline view. Currently, sequence state lives in `lead_messages` (step_number, status). | **Medium** | Aggregate sequence progress per contact: `MAX(step_number) WHERE status='sent'` / total steps. Show as a progress indicator cell. | Don't embed full sequence editing in the grid. Show status; click to manage in side panel. |

## Anti-Features

Features to explicitly NOT build. These add complexity without proportional value for a founder-focused CRM.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Kanban board view | Pipedrive's kanban is their identity, but Flywheel is grid-first. Kanban requires a completely different data fetching pattern, drag-drop infrastructure, and doesn't scale past ~50 visible cards. Founders managing 200+ relationships need density, not cards. | Stick with AG Grid table view. Stage progression via inline dropdown or side panel. The filter bar already segments by stage. |
| Custom objects / custom fields (Attio-style) | Attio's object model is powerful but complex. Building a schema-builder is a product unto itself. Founders don't need to define custom objects — they need the one pipeline to work well. | Use JSONB `intel` and `metadata` fields for extensibility. Add specific columns as needed (e.g., `deal_value`, `industry`) rather than a generic field builder. |
| Shared/team saved views with permissions | Team views require role-based visibility, edit permissions, and conflict resolution. For a solo-founder or tiny team, personal views are sufficient. | Ship personal saved views. Add shared views in a future milestone when multi-user is a real use case. |
| Full email compose inside the grid | HubSpot's inline email composer is heavy. Folk's is simpler but still adds significant complexity. | Show email history in the timeline. Link to email compose (existing email feature). Don't embed a rich-text email editor in the CRM grid. |
| Automated sequence execution engine | Building a reliable email sending queue with scheduling, throttling, bounce handling, and deliverability monitoring is a massive undertaking. Clay and HubSpot have dedicated teams for this. | Show sequence templates and drafted messages. Let the user send from their email client (or existing email feature). AI drafts the messages; human sends them. |
| Calendar view of pipeline activities | Attio offers calendar views. Low usage for pipeline management. Founders check their calendar in Google Calendar, not their CRM. | Show "next meeting" as a column in the grid. Link to calendar for scheduling. |
| Real-time collaboration / multiplayer cursors | Attio has multi-user presence indicators. Flywheel is founder-first, often single-user. The engineering cost of real-time sync (WebSockets, conflict resolution) is enormous. | Standard optimistic updates with last-write-wins. Add collaboration features when team size warrants it. |
| Company/contact separation toggle | Some CRMs let you toggle between "show companies" and "show people" as separate grid modes. This recreates the fragmentation we're eliminating. | One grid. Company is the primary row. Contacts are visible in the side panel and as expandable sub-rows (if needed). |

## Feature Dependencies

```
Unified data model ──────────────┬── Single grid view
                                 ├── Unified side panel
                                 ├── Continuous stage progression
                                 └── Full-text search across all records

Single grid view ────────────────┬── Inline cell editing
                                 ├── Column sorting/reordering
                                 ├── Saved views (depends on filter state shape)
                                 ├── Quick-add row
                                 └── Keyboard navigation

Unified side panel ──────────────┬── Activity timeline (aggregated)
                                 └── Outreach sequence status

Activity timeline ───────────────── AI stage suggestions (needs signal data)

Filter bar ──────────────────────── Saved views (serialized filter state)

Dedup check ─────────────────────── Quick-add row (must check before insert)
                                 └── Multi-source entry (merge-or-create on import)
```

## MVP Recommendation

**Phase 1 — Unified Grid (must ship together):**
1. Unified data model / query layer (merges leads + accounts into one result set)
2. Single AG Grid with continuous stage column (no graduation)
3. Merged side panel (handles both legacy entity types)
4. Unified filter bar with stage, fit tier, relationship type, search
5. Keyboard navigation (Enter/Escape/arrow keys)

**Phase 2 — Rich interactions:**
6. Inline cell editing (stage, fit tier, next action)
7. Saved views (personal)
8. Quick-add row with dedup
9. Activity timeline in side panel (aggregated from all sources)

**Phase 3 — AI layer:**
10. AI stage suggestions based on activity signals
11. Smart dedup on all entry points (CSV import, manual add)
12. Outreach sequence status column

**Defer entirely:**
- Kanban view: not needed for density-first founder CRM
- Custom objects: JSONB covers extensibility needs
- Email compose in grid: existing email feature handles this
- Automated sequence sending: draft-and-send-manually is fine for now

## Existing Infrastructure to Leverage

| Existing Component | Reuse Strategy |
|-------------------|----------------|
| AG Grid (both pages) | Unified column definitions, shared theme config (already near-identical between `leadsTheme` and `pipelineTheme`) |
| `PipelineSidePanel` + `LeadSidePanel` | Merge into `UnifiedSidePanel` with normalized data interface |
| `PipelineFilterBar` + `LeadsFilterBar` | Merge into `UnifiedFilterBar` with superset of filter facets |
| `OutreachDot`, `DaysSinceCell`, `FitTierBadge`, `StageBadge` | Reuse directly — these cell renderers work regardless of entity source |
| `CompanyProfilePage` | Already handles full profile view — just needs routing from unified grid |
| `GraduationModal` + `GraduateButton` + `LeadGraduateButton` | **Remove** — graduation is replaced by continuous stage progression |
| `PipelineViewTabs` (all/hot/replied/stale) | Replace with saved views system (these become default saved views) |
| `LeadsFunnel` | Keep as optional collapsible visualization above the grid |
| Backend `Account` + `Lead` models | Create a unified query endpoint that JOINs/UNIONs with consistent shape |
| `lead_messages` + `outreach_activities` + `meetings` | Unified timeline query for side panel |
| `RelationshipListPage` type tabs (prospect/customer/advisor/investor) | Become filter facets in the unified filter bar, not separate pages |

## Sources

- [Attio Help Center - Views](https://attio.com/help/academy/introduction/views) — HIGH confidence
- [Attio Help Center - Filter and sort views](https://attio.com/help/reference/managing-your-data/views/filter-and-sort-views) — HIGH confidence
- [Attio Help Center - Table views](https://attio.com/help/reference/managing-your-data/views/create-and-manage-table-views) — HIGH confidence
- [Attio Workflows](https://attio.com/platform/workflows) — HIGH confidence
- [Attio Chrome Extension](https://attio.com/help/reference/tools-and-extensions/attio-chrome-extension) — HIGH confidence
- [Attio Email and Calendar Syncing](https://attio.com/help/reference/email-calendar/email-and-calendar-syncing) — HIGH confidence
- [Folk CRM - Create views](https://help.folk.app/en/articles/4998224-create-views) — HIGH confidence
- [Folk CRM - Email sequences](https://help.folk.app/en/articles/8744016-send-email-sequences) — HIGH confidence
- [Folk CRM - Best practice email sequences](https://www.folk.app/articles/best-practice-for-sending-email-sequences) — HIGH confidence
- [Pipedrive Pipeline view](https://support.pipedrive.com/en/article/pipeline-view) — HIGH confidence
- [HubSpot Pipeline Management](https://www.hubspot.com/products/crm/pipeline-management) — MEDIUM confidence
- [CRM Deduplication Guide 2025](https://www.rtdynamic.com/blog/crm-deduplication-guide-2025/) — MEDIUM confidence
- [Attio CRM Review 2026 - CRM.org](https://crm.org/news/attio-review) — MEDIUM confidence
- [Folk CRM Review 2026 - hackceleration](https://hackceleration.com/folk-crm-review/) — MEDIUM confidence
- [react-datasheet-grid](https://github.com/nick-keller/react-datasheet-grid) — MEDIUM confidence (implementation patterns)
- [Attio + Clay Integration](https://attio.com/apps/clay) — HIGH confidence (multi-source enrichment patterns)
