# Feature Landscape — v2.1 CRM Redesign

**Domain:** Intelligence-first founder CRM (relationship type segmentation, AI synthesis, configurable pipeline grid, commitment tracking, signal layer)
**Researched:** 2026-03-27
**Confidence:** MEDIUM — sources include Attio, Folk, Notion CRM patterns, Zoho Signals, TanStack Table docs. Most architectural claims verified. UX pattern claims are MEDIUM confidence (WebSearch + practitioner consensus).

---

## Context: What Already Exists vs What's New

The v2.0 CRM shipped flat account tables, basic pipeline triage, and REST APIs. v2.1 builds intelligence surfaces on top of that data. Nothing in this document requires rebuilding what works — it only extends it.

| Already Shipped (v2.0) | Status |
|------------------------|--------|
| Accounts list + detail page | Done |
| Pipeline page (table + Graduate button) | Done |
| Pulse signals on Briefing page | Done |
| REST APIs: accounts, contacts, outreach, timeline, pulse | Done |
| Sidebar with Accounts + Pipeline links | Done |

---

## Table Stakes

Features users expect. Missing = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| Separate list pages per relationship type (Prospects, Customers, Advisors, Investors) | Every CRM since Salesforce 2005 segments contacts. Attio, Folk, HubSpot all do this. Users cannot mentally manage Advisors and Prospects in a single table — the context and actions are completely different. | Medium | DM-01 `relationship_type[]` migration, API-01 |
| Click-through to relationship detail | Navigation to detail is non-negotiable. No CRM ships a list-only view. | Low | Existing account detail page — reuse and extend |
| Primary contact visible on list card | Folk, Attio, and Notion CRM templates all surface the lead contact inline. Users cannot remember which card is which without a name. | Low | API-01 `primary_contact` field |
| AI summary on detail page (cached, not on-demand) | Nutshell, Attio, and Folk all ship cached relationship summaries. Users expect synthesis; reading raw timeline is too slow. | Medium | DM-04 `ai_summary` + `ai_summary_updated_at` columns, API-07 synthesize |
| Graceful degradation when AI summary is empty | Attio shows enrichment data when AI context is thin. Folk shows a limited-data research note. Industry consensus: never show a blank panel — display a shorter template-based summary or a "not enough data yet" state instead. | Low | API-07 threshold logic (fewer than 3 data points triggers template summary not LLM call) |
| Note capture on any relationship (quick-add) | Every personal CRM (Dex, Nimble, Folk) has a quick note field. It's the primary data input for founder users. | Low | API-05 quick-add note, context entry system (already built) |
| Timeline showing all interaction history | Core CRM table stakes since Salesforce. Users orient by recency. | Low | API already ships unified timeline; FE-09 is the new renderer |
| Sidebar navigation with relationship type sections | HubSpot, Attio, and Pipedrive all have persistent type-based navigation. Founders context-switch constantly between investor mode and customer mode. | Low | FE-06 sidebar redesign |
| Graduate-to-relationship flow from Pipeline | Users need an explicit promotion action — this is the "graduation ceremony" of a prospect becoming a real relationship. | Low | API-04 graduate endpoint (already designed) |
| Configurable Pipeline columns (show/hide) | Airtable-style column management. Any power user of CRMs expects this. TanStack Table supports it natively with column visibility state. | Medium | FE-01 Pipeline grid |
| Signal count badges on sidebar | Zoho CRM Signals, HubSpot notification dots, Intercom badge counts — users need to know where attention is needed without opening every page. | Medium | API-09 signals endpoint, FE-06 |

---

## Differentiators

Features that set this product apart from standard CRMs. Not expected, but create meaningful value and justify adoption over commodity alternatives.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-type account (one entity = Advisor + Investor simultaneously) | Attio supports this and it is their primary differentiator for startup use cases. For a founder, their lead investor IS also their advisor. No other lightweight CRM does this cleanly — most require separate records or a single forced type. | Medium | DM-01 text array not enum; type badge chips with PATCH API-03 |
| Interactive AI panel — Q&A about a relationship | Asking "what did we discuss last about pricing?" is impossible in legacy CRMs. RAG over account context is founder-specific and high value. Folk offers "draft follow-up from thread" but not open Q&A. | High | API-08 ask endpoint; requires quality RAG implementation with source attribution |
| Two-paradigm layout: Pipeline as data grid, Relationships as intelligence journals | No single CRM separates these cleanly. Airtable feels clinical for investor journals; Notion feels too freeform for outreach triage. The design decision to have two distinct visual modes is the conceptual differentiator. | High | FE-01 (grid) and FE-07/FE-08 (cards and detail) must look and feel different from each other |
| Commitment tracking — "What You Owe / What They Owe" | This is the founder's primary cognitive burden after a meeting. Meeting notes contain commitments but no tool extracts and surfaces them bidirectionally. Closest competitor is OnePageCRM's "next action" concept, but that is unidirectional and not commitment-specific. | Medium | FE-12 Commitments tab; API-02 commitments field |
| Type-specific tab sets per relationship (Advisor tabs differ from Investor tabs differ from Prospect tabs) | Folk and Attio use the same record layout for all contact types. Flywheel's type-driven rendering is a meaningful UX improvement — advisors have "What They Help With", investors have "Updates Owed", prospects have "Outreach". | Medium | FE-08 tab config map; shared RelationshipDetail component with four configurations |
| Signal layer with priority tiers (reply_received above followup_overdue above commitment_due above stale) | Zoho's Signals are limited to email-open events. Flywheel's signal taxonomy is relationship-aware and multi-source — it covers outreach staleness, commitment deadlines, and inbound replies in a single feed. | Medium | API-09 signal computation; signal types map to founder job-to-be-done |
| File attachment on relationship (PDF, contract, deck) | Neither Attio nor Folk have native file attachment to contact records. Supabase Storage already exists in this codebase — it is low-cost to add but high value for founder workflows (investor deck attached to investor record, NDA attached to customer). | Medium | API-06, Supabase Storage (already in stack) |
| Stale relationship detection with ambient visual tint | "Losing touch" detection exists in Dex and Nimble but is limited to notification reminders. Flywheel's grid shows staleness inline (colored number and row background tint) making it ambient and glanceable rather than disruptive. | Low | `days_since_last_outreach` computed field plus CSS class on row |
| AI-generated type-specific action prompts (Advisor gets "Draft Thank You", Investor gets "Draft Update") | The action bar adapting to relationship type signals the system understands who this person is. No commodity CRM does type-aware action suggestions. The stubs in v2.1 set the surface for v3 skill triggers. | Low | FE-13 type-to-button config map; most buttons are stubs in v2.1 with "Coming soon" toasts |

---

## Anti-Features

Features to explicitly avoid. Building these would dilute focus, add maintenance cost, or conflict with existing design decisions already recorded in PROJECT.md.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Custom pipeline stages | Out of scope per PROJECT.md. Stages are fixed by design. Adding configurability requires a settings page, migration strategy, and validation logic that does not add founder value. | Document the 5 fixed stages clearly in UI. |
| Kanban drag-and-drop for Pipeline | Out of scope per PROJECT.md. Adds complex drag state, mobile incompatibility, and conflicts with the "data grid" paradigm. | Provide inline status dropdown per row if needed in a future patch. |
| Bulk outreach sending from Pipeline UI | Out of scope per PROJECT.md. Creates compliance risk and undermines the founder ethos of intentional, skill-generated outreach. | Keep outreach generated by skills only. |
| AI-auto-populate commitments from NLP extraction (v2.1) | High complexity, high error rate. NLP commitment extraction from freeform meeting notes is a standalone ML problem. Wrong commitments displayed as facts erode trust faster than the feature delivers value. | Extract commitments from context entries with `source = "commitment"` — manual capture first, NLP deferred to v3. |
| Free-text contact creation from UI | Conflicts with no-manual-entry design principle from PROJECT.md. Contacts are created by skills and seed CLI. Adding forms opens data hygiene debt with duplicates and normalization issues. | If quick-add is needed, call the existing contact API with minimal fields. Defer to v3. |
| Kanban board view for relationship types (e.g., Advisors as Kanban) | Relationships are not a pipeline — they are persistent and do not move through stages. A board view implies stage progression, which is conceptually wrong for advisor/investor relationships. | Card grid for relationships, table grid for pipeline. The two-paradigm design is a stated principle. |
| Mobile-responsive layout | Out of scope per PROJECT.md. Responsive work doubles CSS complexity. This is a daily-use desktop tool for founders. | Use minimum widths, defer mobile to a dedicated milestone. |
| Slack and email notification delivery for signals | Out of scope. In-app badges and Briefing page cover signal surfacing for v2.1 without delivery infrastructure. | Ship in-app first, notification delivery is v3. |
| Account merge and dedup UI | Out of scope per PROJECT.md. Normalization handles this at seed time via CLI. UI dedup adds complex conflict resolution UI. | Run normalization CLI when duplicates appear. |
| Server-side saved views (persisted to DB) | Overengineered for v2.1. The 4 predefined filter tabs (All, Strong Fit, Needs Follow-up, Stale) cover 90% of pipeline triage needs without requiring a views table, API, and settings UI. | Client-side filter presets. Add server persistence when users explicitly request custom views. |

---

## Feature Dependencies

Build order constraints — features downstream of others must wait.

```
DM-01 (relationship_type[] column)
  → API-01 (relationships list filtered by type)
    → FE-07 (relationship list pages — 4 surfaces)
    → FE-06 (sidebar badge counts)
  → API-03 (type update)
    → FE-08 type badges (clickable)
  → API-04 (graduate with type assignment)
    → FE-04 (graduation modal)

DM-02 (entity_level column)
  → FE-10 (People tab — person-level = single prominent card, not grid)

DM-03 (relationship_status + pipeline_stage rename)
  → API-01 (relationship list filters on relationship_status)
  → API-10 (pipeline filters on pipeline_stage)
  → FE-01 (Pipeline grid uses pipeline_stage not old status)

DM-04 (ai_summary + ai_summary_updated_at columns)
  → API-07 (synthesize endpoint)
    → FE-08 AI panel (cached summary display)
  → API-08 (ask endpoint)
    → FE-08 AI panel (Q&A mode — question detection)

API-05 (quick-add note)
  → FE-08 AI panel note input
    → FE-09 Timeline (optimistic update, new entry at top)

API-06 (file upload)
  → FE-08 AI panel attachment button
    → FE-09 Timeline file-type entries

API-09 (signals)
  → FE-06 sidebar badge counts
  → FE-07 card signal indicator
  → FE-08 signal banner on detail page

Existing (already built):
  - Timeline API → API-07 synthesize and API-08 ask both consume this data
  - Context store → AI endpoints read from it; note quick-add writes to it
  - Accounts API Graduate endpoint → API-04 extends it with type parameter
  - Supabase Storage → API-06 file upload uses the existing storage pattern
```

---

## MVP Recommendation

Given the target user (founder managing 15 deep relationships plus 200 outreach pipeline), the minimum shipping set for v2.1:

**Prioritize — cannot ship without:**
1. DM-01 to DM-03 data model migrations (all other features block on this)
2. API-01 and API-02 relationship list and detail with primary_contact and signal_count
3. FE-06 sidebar with 5 surfaces and badge counts
4. FE-07 relationship card list pages (4 type surfaces)
5. FE-08 relationship detail with AI panel and type-driven tabs
6. FE-01 Pipeline grid (Airtable-style) with column show/hide and filter tabs
7. FE-04 graduation flow with type selection modal
8. API-07 synthesize and API-08 ask endpoints with graceful degradation
9. FE-12 Commitments tab (the founder pain point v2.0 does not address at all)

**Defer to patch or v2.2:**
- File attachments (API-06 and attachment button in FE-08) — note capture is higher value per effort; files add Supabase storage wiring that should not block the main surfaces
- Action bar skill triggers (FE-13 stubs are fine for v2.1 — "Coming soon" toasts are acceptable)
- Signal computation beyond `stale_relationship` type — reply_received and commitment_due require richer event wiring that can ship as a follow-on
- Column drag-to-reorder — show/hide is sufficient for v2.1; drag-reorder is polish

---

## Complexity Assessment by Feature Area

| Feature Area | Complexity | Risk | Notes |
|-------------|------------|------|-------|
| Data model migrations (DM-01 to DM-04) | Low | Low | Additive columns only; existing data gets safe defaults |
| Relationships API (API-01 to API-10) | Medium | Low | Follows established FastAPI patterns already in codebase |
| Pipeline grid (FE-01 to FE-05) | Medium | Medium | TanStack Table v8 handles column state; saved-view tabs are client-side only |
| Relationship list pages (FE-07) | Low | Low | Card grid with type-config map; mostly CSS and one API call |
| Relationship detail (FE-08 to FE-12) | High | Medium | Multi-tab, AI panel, Q&A detection, optimistic updates — most complex FE component |
| AI synthesis (API-07, AI panel display) | Medium | Medium | Prompt engineering and graceful degradation logic; LLM latency needs streaming or spinner |
| AI Q&A (API-08) | High | Medium | RAG quality determines usefulness; source attribution adds implementation complexity |
| Signal layer (API-09 and sidebar badges) | Medium | Low | Signal computation is rule-based (not ML); badge polling or React Query invalidation needed |
| Commitment tracking (FE-12) | Medium | Low | Two-column layout with context entry storage is straightforward; display is harder than storage |
| Premium design system | Low | Low | Design tokens already defined in project constraints; mostly Tailwind utility classes |

---

## Sources

- Attio multi-type custom objects and relationship intelligence: [Attio CRM Review 2025 — Stacksync](https://www.stacksync.com/blog/attio-crm-2025-review-features-pros-cons-pricing), [Attio CRM Review 2026 — Authencio](https://www.authencio.com/blog/attio-crm-review-features-pricing-customization-alternatives), [Attio vs Folk 2025 — popi.ai](https://popi.ai/compare/crm-software/attio-vs-folk-crm/)
- Folk Magic Fields and AI enrichment: [Folk CRM AI Features — folk.app](https://www.folk.app/articles/folk-crm-ai-features)
- AI relationship summaries (Nutshell timeline summarization): [AI-Powered CRM 2025 — usemotion.com](https://www.usemotion.com/blog/ai-crm)
- Saved views and column config patterns (Airtable): [Getting Started with Airtable Views](https://support.airtable.com/docs/getting-started-with-airtable-views)
- TanStack Table column sizing and state persistence: [Column Sizing Guide — TanStack Table](https://tanstack.com/table/v8/docs/guide/column-sizing)
- Zoho CRM Signals (real-time notification system): [Signals — Zoho CRM Help](https://help.zoho.com/portal/en/kb/crm/experience-center/salessignals/articles/signals-an-overview)
- AI graceful degradation patterns: [Graceful Degradation — MOTA AI on Medium](https://medium.com/@mota_ai/building-ai-that-never-goes-down-the-graceful-degradation-playbook-d7428dc34ca3)
- Stale contact detection patterns: [CRM Health Score — Medium](https://medium.com/@williamflaiz/your-crm-health-score-is-hiding-a-2m-problem-heres-the-scorecard-that-exposes-it-4a1ee8c4452d)
- Personal CRM losing-touch detection: [Personal CRM Guide 2025 — folk.app](https://www.folk.app/articles/personal-crm-guide)
- Segmentation best practices for founders and VCs: [Essential CRM Features for Private Equity — 4Degrees](https://www.4degrees.ai/blog/essential-crm-features-for-private-equity-firms-in-2025-streamline-deal-flow-relationships-and-data-driven-decisions)
