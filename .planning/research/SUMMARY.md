# Project Research Summary

**Project:** Unified Pipeline Schema & UI
**Domain:** CRM schema migration + AG Grid UX overhaul on live FastAPI + Supabase system
**Researched:** 2026-04-06
**Confidence:** HIGH

## Executive Summary

This milestone replaces Flywheel's fragmented 6-table CRM (leads, lead_contacts, lead_messages, accounts, account_contacts, outreach_activities) with a unified 3-table schema (pipeline_companies, pipeline_contacts, pipeline_activities) and rebuilds the frontend as a single Airtable-style AG Grid view. Every major CRM in this space — Attio, Folk, Pipedrive — centers on a single company-first grid with continuous stage progression. Flywheel's current graduation wall (lead → account promotion) is its biggest UX friction point, and this milestone eliminates it entirely.

The recommended approach is strictly incremental: create new tables first (additive, nothing breaks), migrate data with explicit dedup handling, introduce a new `/pipeline/` API namespace alongside old endpoints as thin wrappers, then migrate the frontend feature by feature. The existing stack requires zero new packages — AG Grid Community 35.2.0 already supports inline cell editing, and pg_trgm (one-time Supabase extension enable) handles fuzzy company name matching. The only significant technical constraint is Supabase's PgBouncer, which silently rolls back multi-statement DDL transactions; every DDL statement must be its own commit via SQL Editor or direct connection.

The highest risks are data integrity during migration (graduated leads exist in both tables; contacts with no email are hard to dedup) and breaking FK references from meetings, tasks, and context_entries to the old `accounts` table. Both are preventable with explicit migration sequencing and a dual-read period where old API endpoints are thin wrappers over the new service layer. The daily dogfooding constraint — this is a live, actively-used system — makes incremental migration non-optional.

---

## Key Findings

### Recommended Stack

Zero new packages required on either frontend or backend. The entire milestone runs on the existing stack: FastAPI + SQLAlchemy 2.0 async (backend), AG Grid Community 35.2.0 + React 19 + React Query 5.91.2 (frontend), and Supabase PostgreSQL 15. The only infrastructure addition is enabling the `pg_trgm` PostgreSQL extension (pre-installed in Supabase, disabled by default) via one SQL statement in the Dashboard. PostgreSQL PL/pgSQL triggers handle denormalized field sync (`last_activity_at`, `contact_count`) with SECURITY DEFINER to bypass RLS on cross-table updates.

**Core technologies:**
- **Alembic (existing):** Migration file authoring and version tracking only — actual DDL runs via SQL Editor due to PgBouncer constraint
- **AG Grid Community 35.2.0 (existing):** Inline cell editing (`editable`, `cellEditor`, `cellEditorPopup`), column operations — all Community features, no Enterprise needed
- **pg_trgm (enable only):** Fuzzy company name matching with trigram similarity; 0.6 threshold for near-duplicate detection
- **PostgreSQL triggers (new SQL):** Auto-update `last_activity_at`, `contact_count`, `activity_count` on `pipeline_companies` for consistency across direct DB edits and bulk imports
- **React Query (existing):** Optimistic updates on inline cell edits with revert-on-error pattern

### Expected Features

Research benchmarked against Attio, Folk, Pipedrive, and HubSpot. The CRM market has converged on company-first grids with continuous stage progression — any fragmentation into separate views is a UX regression.

**Must have (table stakes):**
- Single grid showing all entity types — the entire premise; missing = product feels broken
- Continuous stage column with no graduation wall — biggest current friction point
- Merged side panel handling all entity types — click-to-expand is expected in every modern CRM
- Full-text search across all records (name, domain, contact name, notes)
- Filter bar with multi-select facets (stage, fit tier, relationship type, source, last activity)
- Column sorting and reordering — standard spreadsheet behavior
- Row click → side panel → full profile navigation (two-level progressive disclosure)

**Should have (differentiators):**
- Inline cell editing for high-frequency fields (stage dropdown, fit tier, next action date)
- Saved views (personal) — Attio's most-cited feature; hardcoded tabs become configurable
- Quick-add row with dedup check at bottom of grid (Airtable pattern)
- Unified activity timeline in side panel aggregating emails, meetings, notes, stage changes
- AI-computed stage suggestions based on email replies and meeting bookings
- Keyboard navigation (arrow keys, Enter to open, Escape to close, Cmd+K search)

**Defer to v2+:**
- Kanban board view — wrong data density for 200+ relationship management
- Custom objects / field builder — JSONB covers extensibility needs adequately
- Shared/team saved views with permissions — personal views sufficient for solo-founder use case
- Full email compose inside grid — existing email feature handles this
- Real-time collaboration / multiplayer — engineering cost is enormous for single-user value

### Architecture Approach

The migration strategy is incremental with a compatibility view layer. New tables are created alongside old tables (additive Phase 1), data migrated with deterministic UUID preservation for accounts (so FK references to meetings/tasks/context_entries need only constraint retargeting, not data migration), compatibility views provide old table names during transition, and old API endpoints become thin wrappers calling `pipeline_service.py`. Frontend rebuilds feature-by-feature against the new `/pipeline/` namespace. Old tables and deprecated wrappers drop only after all consumers are verified migrated.

**Major components:**
1. `pipeline_companies` table — single source of truth for all company entities; absorbs leads + accounts
2. `pipeline_contacts` table — unified persons; absorbs lead_contacts + account_contacts; `person_entry_id` FK handles advisor dual-entity pattern
3. `pipeline_activities` table — unified touchpoints; absorbs lead_messages + outreach_activities
4. `pipeline_stages` reference table — stage definitions, ordering, display config
5. Compatibility views (`accounts_compat`, `leads_compat`) — old API code reads these during transition window
6. `api/pipeline.py` (new) — unified CRUD replacing leads.py, accounts.py, outreach.py, relationships.py
7. `services/pipeline_service.py` (new) — business logic for stage transitions, dedup, scoring; called by API and MCP tools
8. `features/pipeline/` (rebuilt) — unified AG Grid + side panel + filter bar; replaces 4 frontend feature directories

### Critical Pitfalls

1. **Supabase PgBouncer silently rolls back multi-statement DDL** — Never run `alembic upgrade head` for DDL on Supabase. Execute each statement via SQL Editor or direct connection string with individual commits. Use `alembic stamp <revision>` after execution to sync state. Verify schema with direct SQL after every migration step.

2. **Data loss during table merge — graduated leads exist in both tables** — When `Lead.account_id IS NOT NULL`, the lead was graduated; merge its data INTO the corresponding accounts row, do NOT create a second pipeline_companies row. Map all 15 lead-only fields (purpose, campaign, fit_rationale, etc.) to target columns or JSONB metadata before writing migration SQL. Verify: `(count accounts) + (count leads WHERE account_id IS NULL)` must equal `count pipeline_companies`.

3. **Breaking FK references from meetings, tasks, context_entries** — These three tables have `account_id` FKs to the `accounts` table. Migration order must be: create new tables → migrate data (preserving account UUIDs) → retarget FK constraints to `pipeline_companies` → ONLY THEN rename/drop old tables. Add `pipeline_company_id` column first, populate it, verify completeness, then drop `account_id`.

4. **Breaking background engines during migration** — `meeting_processor_web.py`, `channel_task_extractor.py`, `flywheel_ritual.py`, `skill_executor.py`, and `synthesis_engine.py` all query `accounts`/`leads` directly. Use a `UNIFIED_PIPELINE` feature flag and dual-read period. Migrate one engine at a time. Deploy order: (a) migration, (b) code with dual-read, (c) verify engines, (d) remove old paths.

5. **RLS policy gaps — privacy breach on new tables** — The unified `pipeline_companies` table needs visibility-aware RLS (matching accounts migration 042): `visibility = 'team' OR owner_id = current_setting('app.user_id')::uuid`. Create RLS policies BEFORE migrating data to prevent even a brief window of unrestricted visibility.

---

## Implications for Roadmap

Based on dependency analysis and pitfall severity, the research points to a clear 4-phase structure:

### Phase 1: Schema Foundation
**Rationale:** All subsequent work depends on the new tables existing. This must be the most carefully executed phase — errors here (data loss, broken FKs, RLS gaps) have the highest blast radius. The Supabase PgBouncer constraint makes every DDL statement a deliberate, individually-verified operation.
**Delivers:** New tables (`pipeline_companies`, `pipeline_contacts`, `pipeline_activities`, `pipeline_stages`) with correct RLS, indexes, triggers, and compatibility views. Data migrated from all 6 source tables. FK references retargeted on meetings, tasks, context_entries. Old tables preserved as `_legacy` for 30 days.
**Addresses:** Unified data model, continuous stage column (schema level), dedup infrastructure (pg_trgm enabled, domain uniqueness constraint)
**Avoids:** Pitfalls 1 (PgBouncer), 2 (data loss), 3 (contact dedup), 4 (FK references), 6 (RLS gaps), 10 (index design), 11 (Alembic chain), 12 (graduation history)

### Phase 2: Backend Service Layer + API
**Rationale:** Frontend cannot be built until the API returns a stable, unified shape. Old endpoints must continue working for background engines during this phase. This phase is itself incremental: new `/pipeline/` namespace first, then one-engine-at-a-time migration of background workers.
**Delivers:** `api/pipeline.py` with full CRUD for companies/contacts/activities/stages. `services/pipeline_service.py` with stage transitions, dedup logic, and entity resolution. Old endpoints as thin wrappers. `UNIFIED_PIPELINE` feature flag. Background engines (meeting processor, task extractor, flywheel ritual, synthesis engine) migrated to new models.
**Uses:** SQLAlchemy 2.0 async patterns (existing), pg_trgm fuzzy matching, PostgreSQL triggers
**Implements:** `pipeline_service.py` architecture, compatibility view layer, dual-write period
**Avoids:** Pitfall 5 (engine-to-schema mismatch), Pitfall 8 (entity resolution), Pitfall 9 (person-as-contact), Pitfall 13 (MCP tool descriptions)

### Phase 3: Frontend Rebuild — Unified Grid
**Rationale:** With a stable API, the frontend can be rebuilt against the new data shape. The research is explicit: rebuild, don't adapt. The existing leads/, accounts/, relationships/ feature directories each have incompatible data shapes and cell renderers. A single unified `features/pipeline/` view is less work than adapting 4 diverged views.
**Delivers:** Single AG Grid view replacing leads/accounts/relationships/pipeline pages. Unified side panel. Unified filter bar. Continuous stage column with inline dropdown editing. Column sorting/reordering. Keyboard navigation. React Query cache with queryKey factory pattern.
**Uses:** AG Grid Community inline editing (`editable`, `agSelectCellEditor`, `cellEditorPopup`), optimistic updates via React Query, Zustand for side panel state
**Implements:** Unified grid architecture; side panel merge pattern; cache invalidation design
**Avoids:** Pitfall 7 (frontend cache fragmentation), Anti-pattern 4 (simultaneous front/back changes)

### Phase 4: Rich Interactions + AI Layer
**Rationale:** These features depend on Phase 3's grid being stable and Phase 2's activity data being unified. AI stage suggestions require the unified activity timeline. Saved views require the filter state shape to be finalized.
**Delivers:** Saved views (personal, configurable). Quick-add row with dedup dialog. Unified activity timeline in side panel. AI stage suggestions as subtle nudges. Outreach sequence status column. Smart dedup on all entry points.
**Implements:** `saved_views` table + tab bar UI. `GET /api/pipeline/companies/:id/timeline` aggregation endpoint. Stage suggestion signal detection.

### Phase Ordering Rationale

- Phase 1 before everything: no code change is safe until new tables exist with correct RLS and FK references are retargeted
- Phase 2 before Phase 3: frontend must have a stable API contract; building UI against shifting schema compounds bugs
- Phase 3 before Phase 4: saved views, quick-add, and AI suggestions all depend on the grid's filter state shape and query key design being finalized
- This ordering minimizes the blast radius of the highest-severity pitfalls (1-5) by addressing them all before touching the frontend

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Schema):** Contact dedup strategy for name-only matches needs explicit decision rules before migration SQL is written. The person-type entity pattern (person rows in pipeline_companies vs separate table) needs an architectural decision before schema is finalized.
- **Phase 2 (Backend):** Engine-by-engine migration is complex enough that meeting processor, task extractor, flywheel ritual, and synthesis engine each deserve their own research pass. Context entity bridging strategy (pipeline_companies ↔ context_entities via `context_entity_id` FK) needs implementation design.

Phases with standard patterns (skip research):
- **Phase 3 (Frontend):** AG Grid inline editing is well-documented with code examples in STACK.md. React Query optimistic update pattern is standard. The design decision (rebuild vs adapt) is resolved — rebuild.
- **Phase 4 (Rich Interactions):** Saved views pattern is standard (JSONB column + tab UI). Timeline aggregation is a union query — well-understood pattern.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified against AG Grid v35 Community vs Enterprise matrix; Supabase DDL pattern confirmed against 43 existing migrations; pg_trgm availability confirmed in Supabase docs |
| Features | HIGH | Benchmarked against Attio, Folk, Pipedrive, HubSpot help docs; feature recommendations grounded in competitive research |
| Architecture | HIGH | Based on direct codebase analysis of all ORM models, API files, engine files, and migrations; not external sources |
| Pitfalls | HIGH | Based on direct codebase analysis of 6 CRM models, 12 API files, 8 engine files, 43 migrations, and known Supabase constraints from project memory |

**Overall confidence:** HIGH

### Gaps to Address

- **Contact dedup threshold for name-only matches:** Email-first strategy is clear, but name-only matching needs a decision — auto-merge on (tenant_id, normalized_name, company_normalized_name) or always flag for review. Recommendation: flag for review during migration; auto-link going forward on email match only.
- **pg_trgm similarity threshold:** The 0.6 threshold is a starting point, not validated against this tenant's data. Expose as a config value and tune post-migration.
- **Person-type entity design:** ARCHITECTURE.md references `entity_type = 'person'` rows in `pipeline_companies`. This needs a schema decision in Phase 1 planning: discriminator column on pipeline_companies vs separate pipeline_people table.
- **Compatibility view naming conflict:** Cannot name a view `accounts` while the `accounts` table exists. The rename of the old table to `accounts_old` must be the first DDL step and requires verifying no consumer breaks on that rename alone.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase: `db/models.py`, all `api/*.py` files, `engines/`, `alembic/versions/` (43 migrations) — architecture and pitfall analysis
- [AG Grid Community vs Enterprise feature matrix](https://www.ag-grid.com/javascript-data-grid/community-vs-enterprise/) — confirmed inline editing is Community
- [AG Grid Cell Editing docs](https://www.ag-grid.com/react-data-grid/cell-editing/) — implementation patterns
- [Supabase Triggers docs](https://supabase.com/docs/guides/database/postgres/triggers) — SECURITY DEFINER pattern
- Project memory: `CLAUDE.md` Supabase DDL workaround, `feedback_supabase_ddl.md`
- [Attio Help Center](https://attio.com/help/) — views, filters, table views, workflows
- [Folk CRM Help](https://help.folk.app/) — views, email sequences

### Secondary (MEDIUM confidence)
- [Crunchy Data: Fuzzy Name Matching in PostgreSQL](https://www.crunchydata.com/blog/fuzzy-name-matching-in-postgresql) — pg_trgm threshold recommendations
- [Pipedrive Pipeline View](https://support.pipedrive.com/en/article/pipeline-view) — UX pattern reference
- [HubSpot Pipeline Management](https://www.hubspot.com/products/crm/pipeline-management) — feature benchmarking
- [CRM Deduplication Guide 2025](https://www.rtdynamic.com/blog/crm-deduplication-guide-2025/) — dedup strategy patterns

### Tertiary (LOW confidence)
- [Folk CRM Review 2026](https://hackceleration.com/folk-crm-review/) — UX pattern comparisons, needs validation against direct Folk usage

---
*Research completed: 2026-04-06*
*Ready for roadmap: yes*
