# Architecture Patterns: Unified Pipeline Schema Migration

**Domain:** Schema refactor -- merging 6 CRM tables into 3+1 within a live FastAPI + Supabase system
**Researched:** 2026-04-06
**Overall confidence:** HIGH (based on direct codebase analysis, not external sources)

---

## Current State Analysis

### Tables Being Merged

**Source tables (6):**
1. `leads` -- pre-relationship prospects (scraped/scored/researched/drafted/sent/replied)
2. `lead_contacts` -- people at lead companies
3. `lead_messages` -- outreach sequence per lead contact
4. `accounts` -- post-graduation companies (prospect/engaged/customer/advisor/investor)
5. `account_contacts` -- people at account companies
6. `outreach_activities` -- touchpoints on accounts

**Target tables (3+1):**
1. `pipeline_companies` -- unified company entity (replaces leads + accounts)
2. `pipeline_contacts` -- unified person entity (replaces lead_contacts + account_contacts)
3. `pipeline_activities` -- unified touchpoint/message entity (replaces lead_messages + outreach_activities)
4. `pipeline_stages` -- reference table for stage definitions and ordering

### FK Dependencies on Current Tables

| Table | FK to `accounts` | FK to `leads` | Notes |
|-------|-------------------|---------------|-------|
| `meetings` | `account_id` | -- | Critical: meeting-to-company link |
| `tasks` | `account_id` | -- | Critical: task-to-company link |
| `context_entries` | `account_id` | -- | Many rows, used for intel aggregation |
| `outreach_activities` | `account_id`, `contact_id` | -- | Being replaced |
| `account_contacts` | `account_id` | -- | Being replaced |
| `lead_contacts` | -- | `lead_id` | Being replaced |
| `lead_messages` | -- | `contact_id` (lead_contacts) | Being replaced |
| `email_scores` | -- | -- | `sender_entity_id` FK to context_entities, not accounts |
| `leads` | `account_id` | -- | Self-reference for graduated leads |

### API Surface Being Changed

| File | Endpoints | Imports from models | Must change |
|------|-----------|---------------------|-------------|
| `api/leads.py` | 10 endpoints under `/leads/` | Lead, LeadContact, LeadMessage, Account, AccountContact, OutreachActivity | YES - replace entirely |
| `api/accounts.py` | 8 endpoints under `/accounts/` | Account, AccountContact, ContextEntry, OutreachActivity | YES - replace entirely |
| `api/relationships.py` | 8 endpoints (no prefix) | Account, AccountContact, ContextEntry, Meeting, SkillRun | YES - replace entirely |
| `api/outreach.py` | 5 endpoints under `/accounts/` and `/pipeline/` | Account, AccountContact, OutreachActivity, ContextEntry | YES - replace entirely |
| `api/meetings.py` | 7 endpoints under `/meetings/` | Account, Meeting, SkillRun | PARTIAL - update FK references |
| `api/tasks.py` | 7 endpoints under `/tasks/` | Task | PARTIAL - Task model has account_id |
| `api/context.py` | 10 endpoints under `/context/` | ContextEntry (has account_id) | PARTIAL - update FK references |
| `api/timeline.py` | unknown | likely Account | CHECK |
| `api/signals.py` | unknown | likely Account | CHECK |

### Frontend Surface Being Changed

| Feature dir | Components | API calls | Must change |
|-------------|------------|-----------|-------------|
| `features/pipeline/` | PipelinePage, PipelineFilterBar, PipelineSidePanel, PipelineViewTabs, GraduationModal, cell-renderers | `/pipeline/`, `/relationships/{id}/graduate` | YES - rebuild |
| `features/leads/` | LeadsPage, LeadSidePanel, LeadsFilterBar, LeadsFunnel, ContactCard, MessageThread, cell-renderers | `/leads/*` | YES - replace with unified |
| `features/accounts/` | AccountsPage, AccountDetailPage, ActionBar, ContactsPanel, IntelSidebar, TimelineFeed | `/accounts/*` | YES - replace with unified |
| `features/relationships/` | RelationshipListPage, RelationshipDetail, RelationshipTable, RelationshipCard, tabs, etc. | `/relationships/*` | YES - replace with unified |
| `features/meetings/` | unknown | `/meetings/*` | PARTIAL - update company references |
| `features/tasks/` | unknown | `/tasks/*` | PARTIAL - update company references |

---

## Recommended Architecture

### Migration Strategy: Incremental with Compatibility Views

**Use incremental migration, NOT big bang.** Rationale:

1. **Supabase PgBouncer constraint** -- multi-statement DDL transactions silently roll back. Each DDL statement must be its own commit. A big-bang migration with 20+ DDL statements is extremely fragile.
2. **Active daily dogfooding** -- the founder uses this daily. Zero-downtime is not optional.
3. **25K LOC backend, 15K LOC frontend** -- too many consumers to update atomically.

**The approach: Create new tables first, then migrate data, then create compatibility views over old table names, then update consumers incrementally, then drop views.**

```
Phase 1: Create new tables (additive only, nothing breaks)
    |
Phase 2: Data migration + dual-write layer
    |
Phase 3: API migration (new /pipeline/ namespace + old endpoints become thin wrappers)
    |
Phase 4: Frontend migration (feature by feature)
    |
Phase 5: Cleanup (drop old tables, remove compatibility layer)
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `pipeline_companies` table | Single source of truth for all company entities | meetings, tasks, context_entries via FK |
| `pipeline_contacts` table | Single source of truth for all people | pipeline_companies via FK |
| `pipeline_activities` table | All outreach/messages unified | pipeline_contacts, pipeline_companies via FK |
| `pipeline_stages` ref table | Stage definitions, ordering, display config | pipeline_companies (stage FK) |
| Compatibility views | `accounts` and `leads` as views over `pipeline_companies` | Old API code reads from views during transition |
| `api/pipeline.py` (new) | Unified CRUD for companies, contacts, activities | Replaces leads.py, accounts.py, outreach.py, relationships.py |
| `services/pipeline_service.py` (new) | Business logic: stage transitions, graduation, scoring | Called by API and MCP tools |
| Frontend `features/pipeline/` | Unified grid + detail views | New API namespace |

### Data Flow

```
[MCP Tools / Skills] --> [pipeline_service.py] --> [pipeline_companies/contacts/activities]
                                                         |
[meetings.py] --> FK to pipeline_companies.id            |
[tasks.py]    --> FK to pipeline_companies.id            |
[context.py]  --> FK to pipeline_companies.id            |
                                                         |
[Compatibility views] <-- reads during transition -------+
     |
[Old API endpoints] (thin wrappers, deprecated)
```

---

## Migration Strategy Detail

### Phase 1: New Tables (Additive)

Create `pipeline_companies`, `pipeline_contacts`, `pipeline_activities`, `pipeline_stages` alongside existing tables. No FKs to old tables, no drops.

**pipeline_companies schema:**
```sql
CREATE TABLE pipeline_companies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    owner_id        UUID REFERENCES profiles(id),
    visibility      TEXT DEFAULT 'team',
    name            TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    domain          TEXT,
    -- Unified stage replaces leads.purpose + accounts.status + accounts.pipeline_stage
    stage           TEXT NOT NULL DEFAULT 'prospect',
    -- Preserves relationship semantics from accounts
    relationship_type   TEXT[] DEFAULT '{prospect}'::text[],
    entity_level        TEXT DEFAULT 'company',
    relationship_status TEXT DEFAULT 'active',
    -- Scoring
    fit_score       NUMERIC,
    fit_tier        TEXT,
    fit_rationale   TEXT,
    -- Intel
    intel           JSONB NOT NULL DEFAULT '{}'::jsonb,
    ai_summary      TEXT,
    ai_summary_updated_at TIMESTAMP WITH TIME ZONE,
    -- Source tracking
    source          TEXT NOT NULL,
    campaign        TEXT,
    purpose         TEXT[] DEFAULT '{sales}'::text[],
    -- Lifecycle timestamps
    graduated_at    TIMESTAMP WITH TIME ZONE,
    last_interaction_at TIMESTAMP WITH TIME ZONE,
    next_action_due TIMESTAMP WITH TIME ZONE,
    next_action_type TEXT,
    -- Standard
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT uq_pipeline_co_tenant_normalized UNIQUE (tenant_id, normalized_name)
);
```

Key design decisions:
- **`stage` column** replaces the multi-table lifecycle. Values: `scraped`, `scored`, `researched`, `prospecting`, `outreach`, `engaged`, `customer`, `churned`, `lost`.
- **`purpose` array preserved** from leads for campaign tracking.
- **`graduated_at` preserved** as a lifecycle marker but no longer triggers a table move.
- **`owner_id` nullable** -- team-visible companies may not have an owner (accounts didn't require one).

**Supabase DDL execution approach:**
```python
# Each statement as its own commit via session.execute + session.commit
# Then alembic stamp to sync revision
# OR paste into Supabase SQL Editor statement by statement
```

### Phase 2: Data Migration + Dual Write

1. **Migrate existing data** into new tables with deterministic ID mapping:
   - `accounts` rows --> `pipeline_companies` (preserve UUIDs so FK references survive)
   - `leads` rows --> `pipeline_companies` (new UUIDs, store mapping in temp table)
   - Handle name collisions: same company in both `leads` and `accounts` --> merge into single `pipeline_companies` row, keep the `accounts` UUID.
   
2. **Create compatibility views:**
   ```sql
   CREATE VIEW accounts_compat AS
   SELECT id, tenant_id, owner_id, visibility, name, normalized_name, domain,
          stage AS status, fit_score, fit_tier, intel, source,
          relationship_type, entity_level, ai_summary, ai_summary_updated_at,
          graduated_at, relationship_status, stage AS pipeline_stage,
          last_interaction_at, next_action_due, next_action_type,
          created_at, updated_at
   FROM pipeline_companies
   WHERE graduated_at IS NOT NULL OR stage NOT IN ('scraped', 'scored', 'researched');
   ```
   
   Note: Cannot name the view `accounts` while the table still exists. Use `accounts_compat` during transition, or drop the old table first (risky). Better approach: rename old table to `accounts_old`, create view as `accounts`.

3. **Update FKs on meetings, tasks, context_entries** to point to `pipeline_companies.id`:
   - Since we preserve account UUIDs, the FK column values don't change -- only the constraint target changes.
   - For leads that had no account_id in meetings/tasks, this is a no-op.

4. **Dual-write layer** in `pipeline_service.py`: writes to new tables, the views handle reads from old API code.

### Phase 3: API Migration

**Use a new `/pipeline/` namespace. Do NOT try to modify existing endpoints in-place.**

Rationale:
- Existing `/leads/`, `/accounts/`, `/relationships/` have different response shapes.
- A unified API can return a consistent shape with a `stage` field.
- Old endpoints become thin wrappers that call `pipeline_service.py` and reshape responses.
- Frontend can migrate feature-by-feature to the new API.

**New endpoint structure:**
```
POST   /pipeline/companies/                -- create/upsert company
GET    /pipeline/companies/                -- list with filters (stage, type, search, sort)
GET    /pipeline/companies/{id}            -- detail with contacts, activities, intel
PATCH  /pipeline/companies/{id}            -- update fields
POST   /pipeline/companies/{id}/advance    -- advance stage (replaces graduate)

POST   /pipeline/companies/{id}/contacts   -- add contact
PATCH  /pipeline/contacts/{id}             -- update contact
DELETE /pipeline/contacts/{id}             -- remove contact

POST   /pipeline/companies/{id}/activities -- create activity
PATCH  /pipeline/activities/{id}           -- update activity
GET    /pipeline/companies/{id}/activities -- list activities

GET    /pipeline/stages                    -- stage definitions + counts (funnel)
GET    /pipeline/industries                -- distinct industries for filtering
```

**Old endpoints kept as deprecated wrappers:**
```python
# api/accounts.py becomes:
@router.get("/accounts/")
async def list_accounts(...):
    """DEPRECATED: Use /pipeline/companies/?stage=engaged,customer"""
    return await pipeline_service.list_companies(
        filters={"stage": ["engaged", "customer", ...]},
        response_shape="account",  # reshape for backward compat
    )
```

### Phase 4: Frontend Migration

**Rebuild, don't adapt.** The existing AG Grid components in leads/, accounts/, relationships/ each have their own column definitions, cell renderers, filter bars, and side panels. Trying to make them work with the new data shape would be more work than building a single unified pipeline view.

**Migration order:**
1. `features/pipeline/` -- already exists as a thin wrapper. Rebuild as the primary view.
2. `features/relationships/` -- relationship detail page becomes the company detail page.
3. `features/leads/` -- leads-specific views (funnel, message thread) fold into pipeline.
4. `features/accounts/` -- accounts page becomes a filtered view of pipeline.
5. `features/meetings/` -- update company reference display.
6. `features/tasks/` -- update company reference display.

### Phase 5: Cleanup

- Drop compatibility views
- Drop old tables (`leads`, `lead_contacts`, `lead_messages`, `accounts`, `account_contacts`, `outreach_activities`)
- Remove deprecated API endpoints
- Remove old frontend feature directories

---

## RLS Policy Design for New Tables

Use the identical pattern from `040_create_leads_tables.py` (proven working):

```sql
-- For each new table:
ALTER TABLE pipeline_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_companies FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON pipeline_companies TO app_user;

-- Four policies per table:
CREATE POLICY tenant_isolation_select ON pipeline_companies
    FOR SELECT USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_insert ON pipeline_companies
    FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_update ON pipeline_companies
    FOR UPDATE
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_delete ON pipeline_companies
    FOR DELETE USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

**Important: RLS on views.** PostgreSQL applies RLS on the underlying table, not the view. So the compatibility views will automatically inherit RLS from `pipeline_companies`. No extra policy needed on views.

**Caveat:** Views cannot have their own RLS policies. If the old code does `SET app.tenant_id` before queries (which it does via `get_tenant_db`), this works transparently.

---

## MCP Tool Updates

The 10+ registered MCP tools and their impact:

| Tool | Current behavior | Change needed |
|------|-----------------|---------------|
| `context_read` | Reads context_entries by file_name | NO CHANGE -- context_entries unchanged |
| `context_write` | Writes to context_entries with optional account_id | MINOR -- rename `account_id` param to `company_id`, add alias |
| `context_query` | Full-text search on context_entries | NO CHANGE |
| `web_search` | Tavily search | NO CHANGE |
| `web_fetch` | URL fetch | NO CHANGE |
| `file_read` | Reads tenant files | NO CHANGE |
| `file_write` | Writes tenant files | NO CHANGE |
| `python_execute` | Sandbox execution | NO CHANGE |
| `browser_*` (5 tools) | Browser automation | NO CHANGE |

**Only `context_write` needs updating** because it accepts an `account_id` parameter. The fix is trivial: rename to `company_id` in the schema, map internally to `pipeline_companies.id`.

However, **skills that reference accounts/leads by name** in their prompts or context file conventions will need prompt updates. This is a content change, not a code change. Affected services:
- `engines/meeting_processor_web.py` (writes to account-linked context entries via `auto_link_meeting_to_account`)
- `engines/company_intel.py` (enriches account intel)
- Any GTM pipeline skill (creates leads, not pipeline_companies)

---

## Context Entity Bridging Strategy

### The Overlap Problem

`context_entities` (knowledge graph) and `pipeline_companies` (CRM) both represent companies:
- `context_entities` with `entity_type = 'company'` stores mention-based knowledge graph nodes
- `pipeline_companies` stores CRM lifecycle data

These MUST be linked, not merged, because:
1. Context entities also include people, products, technologies -- not just companies.
2. A context entity is mention-driven (auto-created from meeting transcripts), while a pipeline company is intentionally tracked.
3. The knowledge graph has relationships (entity_a <--> entity_b), which CRM companies don't.

### Bridging Approach

Add a `context_entity_id` FK to `pipeline_companies`:

```sql
ALTER TABLE pipeline_companies
    ADD COLUMN context_entity_id UUID REFERENCES context_entities(id) ON DELETE SET NULL;
CREATE INDEX idx_pipeline_co_entity ON pipeline_companies (context_entity_id)
    WHERE context_entity_id IS NOT NULL;
```

**Auto-linking logic** (in `pipeline_service.py`):
```python
async def link_company_to_entity(company_id, session):
    """Find or create a context_entity for this pipeline company."""
    company = await session.get(PipelineCompany, company_id)
    entity = await session.execute(
        select(ContextEntity).where(
            ContextEntity.tenant_id == company.tenant_id,
            ContextEntity.entity_type == 'company',
            func.lower(ContextEntity.name) == company.normalized_name,
        )
    )
    # Link if found, create if not
```

This preserves the graph's independence while enabling rich queries like:
- "Show me the knowledge graph around Acme Corp" (traverse from pipeline_company.context_entity_id)
- "Which pipeline companies are connected to this person?" (join through context_relationships)

### Migration of Existing Links

`context_entries.account_id` already links context to accounts. Since we preserve account UUIDs in `pipeline_companies`, this FK just needs its constraint retargeted:

```sql
ALTER TABLE context_entries DROP CONSTRAINT context_entries_account_id_fkey;
ALTER TABLE context_entries ADD CONSTRAINT context_entries_company_id_fkey
    FOREIGN KEY (account_id) REFERENCES pipeline_companies(id) ON DELETE SET NULL;
-- Optionally rename the column later during API migration:
ALTER TABLE context_entries RENAME COLUMN account_id TO company_id;
```

---

## Meeting and Task FK Migration

### Strategy: Preserve UUIDs, Retarget Constraints

Since `pipeline_companies` will contain all former `accounts` rows with the **same UUIDs**, the FK migration is a constraint swap, not a data migration.

**For `meetings.account_id`:**
```sql
ALTER TABLE meetings DROP CONSTRAINT meetings_account_id_fkey;
ALTER TABLE meetings ADD CONSTRAINT meetings_company_id_fkey
    FOREIGN KEY (account_id) REFERENCES pipeline_companies(id) ON DELETE SET NULL;
-- Rename column later during API migration phase:
ALTER TABLE meetings RENAME COLUMN account_id TO company_id;
```

**For `tasks.account_id`:**
```sql
ALTER TABLE tasks DROP CONSTRAINT tasks_account_id_fkey;
ALTER TABLE tasks ADD CONSTRAINT tasks_company_id_fkey
    FOREIGN KEY (account_id) REFERENCES pipeline_companies(id) ON DELETE SET NULL;
ALTER TABLE tasks RENAME COLUMN account_id TO company_id;
```

**Column rename consideration:** Renaming `account_id` to `company_id` across meetings, tasks, and context_entries improves clarity but requires updating every ORM model and API that references these columns. Do this in Phase 3 (API migration) when those files are already being rewritten.

### Meetings API Impact

`api/meetings.py` imports `Account` and `Meeting`. Changes needed:
1. Replace `Account` import with `PipelineCompany`
2. Update `auto_link_meeting_to_account` function to `auto_link_meeting_to_company`
3. Update response serialization to use company name/domain

### Tasks API Impact

`api/tasks.py` imports `Task` only. The `Task` model has `account_id` FK. Changes:
1. Update `Task` model to reference `pipeline_companies`
2. Update any response that includes account info

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Big-Bang Table Swap
**What:** Drop old tables and create new ones in a single migration.
**Why bad:** On Supabase PgBouncer, multi-DDL transactions silently roll back. A 20-statement migration will appear to succeed but actually do nothing. Also blocks the founder from using the app during migration.
**Instead:** Additive-only migrations. Create new tables, migrate data, swap FKs, then drop old tables in separate migrations.

### Anti-Pattern 2: In-Place Column Renames on Live Tables
**What:** `ALTER TABLE accounts RENAME TO pipeline_companies` while the app is running.
**Why bad:** Every running query against `accounts` immediately breaks. ORM models become invalid.
**Instead:** Create new table, copy data, create view with old name, migrate consumers, drop view.

### Anti-Pattern 3: Shared Mutable Service Layer Too Early
**What:** Creating `pipeline_service.py` before the new tables exist, trying to abstract over both old and new.
**Why bad:** The service layer becomes a translation mess. Two different data shapes, two different stage models, conditional logic everywhere.
**Instead:** Create new tables first. Then write `pipeline_service.py` that ONLY talks to new tables. Old endpoints call the service and reshape output.

### Anti-Pattern 4: Migrating Frontend and Backend Simultaneously
**What:** Updating AG Grid column definitions while the API response shape is still changing.
**Why bad:** Frontend and backend changes compound. A bug could be in either layer. Debugging is painful.
**Instead:** Backend first (new API namespace), verify with curl/httpie, then frontend.

### Anti-Pattern 5: Deleting Old Endpoints Before Frontend Migrates
**What:** Removing `/leads/` and `/accounts/` endpoints before all frontend code is updated.
**Why bad:** Hard-to-catch 404s in production. Features silently break.
**Instead:** Keep old endpoints as deprecated wrappers. Add `X-Deprecated: true` header. Remove only after frontend is fully migrated and tested.

---

## Scalability Considerations

| Concern | Current (100s of records) | At 10K companies | At 100K companies |
|---------|---------------------------|-------------------|---------------------|
| Pipeline grid load | Fine with full table scan | Need cursor pagination + server-side sort | Need virtual scrolling + search index |
| Stage transition | Single UPDATE | Fine | Fine (single row) |
| Funnel counts | COUNT(*) GROUP BY | Add materialized view | Materialized view + background refresh |
| Company detail | 3-4 JOINs | Fine with indexes | Fine with indexes |
| Data migration | Minutes | 10-15 minutes | Background job with progress |

At current scale (100s of records), none of these are concerns. The architecture supports growth without redesign.

---

## Suggested Build Order

Based on dependency analysis:

```
1. pipeline_companies + pipeline_contacts + pipeline_activities tables (no deps)
   |
2. Data migration script (depends on new tables)
   |
3. pipeline_service.py business logic (depends on new tables + data)
   |
4. Retarget meetings.account_id + tasks.account_id FKs (depends on data migration)
   |
5. New /pipeline/ API endpoints (depends on service layer)
   |
6. Deprecated wrappers for old endpoints (depends on new API)
   |
7. Frontend pipeline rebuild (depends on new API being stable)
   |
8. Frontend meetings/tasks updates (depends on FK retargeting)
   |
9. Cleanup: drop old tables, remove wrappers (depends on all consumers migrated)
```

Steps 1-3 can be one phase. Steps 4-6 can be one phase. Steps 7-8 can be one phase. Step 9 is a separate phase.

---

## Sources

- Direct codebase analysis of `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/db/models.py` (all ORM models)
- Direct analysis of all API files in `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/`
- Direct analysis of MCP tools in `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/tools/`
- Direct analysis of frontend feature directories
- RLS pattern from `/Users/sharan/Projects/flywheel-v2/backend/alembic/versions/040_create_leads_tables.py`
- Supabase PgBouncer constraint from project memory (CLAUDE.md)
- PostgreSQL documentation: RLS on views inherits from base tables (HIGH confidence, well-documented behavior)
