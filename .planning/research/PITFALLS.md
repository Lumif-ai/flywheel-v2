# Domain Pitfalls

**Domain:** Unified pipeline schema migration — merging 6 CRM tables into 3 on a live Flywheel V2 system
**Researched:** 2026-04-06
**Confidence:** HIGH (based on direct codebase analysis of all 6 CRM models, 12 API files, 8 engine files, 7 service files, 4 frontend feature directories, 43 Alembic migrations, and Supabase-specific constraints)

---

## Critical Pitfalls

Mistakes that cause data loss, extended downtime, or require rewrites.

### Pitfall 1: Supabase PgBouncer Silently Rolls Back Multi-Statement DDL

**What goes wrong:** Alembic wraps all DDL in a single transaction. PgBouncer (Supabase's connection pooler) commits the `alembic_version` UPDATE but silently rolls back the actual DDL. The migration reports success, `alembic current` shows the new revision, but no tables/columns actually changed. You proceed to deploy code that references non-existent schema.

**Why it happens:** PgBouncer in transaction pooling mode cannot handle multi-statement DDL transactions. Supabase uses PgBouncer by default on the pooled connection string. This is a known, documented issue in this project (see CLAUDE.md and `feedback_supabase_ddl.md`).

**Consequences:** Code deploys referencing `pipeline_entries` table that does not exist. Every API call returns 500. If you deployed the ORM model changes alongside the "migration," rollback requires reverting both code AND manually checking what actually exists in the DB.

**Prevention:**
1. Never run multi-statement DDL through Alembic's standard `upgrade()` path on Supabase pooled connections.
2. For each DDL statement, use a separate `session.execute()` + `session.commit()` via the direct (non-pooled) Supabase connection string, OR paste SQL directly into Supabase SQL Editor.
3. After all DDL succeeds, run `alembic stamp <revision>` to sync Alembic's state.
4. Write the Alembic migration file for documentation and downgrade support, but do NOT rely on `alembic upgrade head` to apply it.

**Detection:** After any migration, verify with a direct SQL query: `SELECT column_name FROM information_schema.columns WHERE table_name = 'pipeline_entries';`. Never trust `alembic current` alone.

**Which phase should address:** Phase 1 (schema migration). Every subsequent phase that adds columns or indexes must follow the same protocol.

---

### Pitfall 2: Data Loss During Table Merge — Orphaned or Duplicated Records

**What goes wrong:** Merging `leads` + `accounts` into `pipeline_entries` loses data because:
- Lead-only fields (`purpose`, `campaign`, `fit_rationale`) have no column in the target table and are silently dropped.
- Duplicate normalized_name entries exist across leads and accounts (same company in both tables, e.g., a lead that was graduated but the lead row was retained with `account_id` FK set).
- The graduation flow in `leads.py:773-905` already copies lead data to accounts during graduation. Merging both rows without checking `Lead.account_id` creates duplicates.

**Why it happens:** The leads and accounts tables evolved independently with different column sets. 15 fields on Lead have no direct counterpart on Account (e.g., `purpose ARRAY(Text)`, `campaign TEXT`, `fit_rationale TEXT`). During migration, the INSERT-SELECT either omits these columns (data loss) or requires a JSONB metadata column to preserve them.

**Consequences:** Lost outreach context. Duplicate pipeline entries for the same company. Broken dedup constraints on the new table.

**Prevention:**
1. Map every column from both source tables to the target schema BEFORE writing migration SQL. Create a column mapping spreadsheet. Fields without a direct target go into `metadata JSONB`.
2. Handle graduated leads explicitly: when `Lead.account_id IS NOT NULL`, merge lead-specific data INTO the corresponding account row (now pipeline_entry), do NOT create a second row.
3. Run the migration on a Supabase branch or local copy first. Compare row counts: `SELECT count(*) FROM pipeline_entries` should equal `(SELECT count(*) FROM accounts) + (SELECT count(*) FROM leads WHERE account_id IS NULL)`.
4. Keep the old tables (renamed with `_legacy` suffix) for 30 days before dropping.

**Detection:** Post-migration audit query: `SELECT normalized_name, tenant_id, count(*) FROM pipeline_entries GROUP BY 1,2 HAVING count(*) > 1;` should return zero rows (unless legitimate duplicates exist across entity types).

**Which phase should address:** Phase 1 (data migration script). Must be the most thoroughly tested plan in the milestone.

---

### Pitfall 3: Contact Deduplication Conflicts When Merging lead_contacts + account_contacts

**What goes wrong:** The same person exists in both `lead_contacts` (linked to a lead) and `account_contacts` (linked to the graduated account). Current graduation code in `leads.py:822-859` already handles this by matching on email, but:
- Some lead_contacts have no email (scraped from LinkedIn with only name + title).
- Name-only matching produces false positives ("John Smith" at two different companies).
- The `lead_contacts` row has `pipeline_stage` (scraped/scored/drafted/sent/replied) while `account_contacts` has `role_in_deal` — different semantic fields.
- `lead_contacts` has a `messages` relationship to `lead_messages`; `account_contacts` links to `outreach_activities`. Merging contacts means re-parenting these child records.

**Why it happens:** The dual-table design was intentional: leads and accounts represent different lifecycle stages. The contact models diverged to serve different purposes. LeadContact tracks outreach progression; AccountContact tracks deal roles.

**Consequences:** Duplicate contacts in the unified table. Lost outreach sequence data if lead_messages are not migrated. Broken FK references from outreach records to the wrong contact ID.

**Prevention:**
1. Dedup strategy: Match by (tenant_id, email) first (high confidence), then (tenant_id, normalized_name, company_normalized_name) as fallback (medium confidence, flag for review).
2. For contacts with no email AND no unique name match, preserve both rows — over-retaining is safer than data loss.
3. Merge child records: for each deduped contact, update `lead_messages.contact_id` and `outreach_activities.contact_id` to point to the surviving unified contact ID.
4. Preserve BOTH `pipeline_stage` and `role_in_deal` as separate columns on the unified contacts table. Do not force one into the other.
5. Add a `source` column tracking origin (`lead_contact`, `account_contact`, `meeting`, `email`).

**Detection:** Post-migration: `SELECT tenant_id, email, count(*) FROM contacts WHERE email IS NOT NULL GROUP BY 1,2 HAVING count(*) > 1;` — review each duplicate.

**Which phase should address:** Phase 1 (data migration). Contact dedup should be a separate, auditable step within the migration script, not buried in a giant INSERT-SELECT.

---

### Pitfall 4: Breaking FK References from Meetings, Tasks, and Context Entries

**What goes wrong:** Three high-traffic tables have `account_id` FK references that must be updated atomically:
- `meetings.account_id` → references `accounts.id` (used by meeting processing, calendar sync, flywheel ritual, meeting prep)
- `tasks.account_id` → references `accounts.id` (used by task extraction, task API, flywheel ritual)
- `context_entries.account_id` → references `accounts.id` (used by 6+ engines and APIs)

If the `accounts` table is renamed/dropped before FK references are updated, all meeting processing, task creation, and context writes fail with FK violation errors.

**Why it happens:** FK constraints are enforced at the DB level. You cannot DROP or RENAME the referenced table while active FKs point to it. The migration must update the FK target before changing the source table.

**Consequences:** Complete system halt. No meetings process. No tasks extract. No context entries write. The daily flywheel ritual fails entirely. This is the highest-blast-radius failure mode.

**Prevention:**
1. Migration order MUST be: (a) Create `pipeline_entries` table, (b) Migrate data from accounts+leads INTO pipeline_entries, (c) Update FK references on meetings/tasks/context_entries to point to pipeline_entries, (d) Drop old FK constraints, (e) Add new FK constraints, (f) ONLY THEN rename/drop old tables.
2. Each step is a separate DDL statement with its own commit (Supabase PgBouncer constraint).
3. Use `ALTER TABLE meetings ADD COLUMN pipeline_entry_id UUID REFERENCES pipeline_entries(id)` first, populate it, verify, THEN drop the old `account_id` column. Never do an in-place rename.
4. During the transition, both columns exist simultaneously. Backend code checks both: `COALESCE(pipeline_entry_id, account_id)`.

**Detection:** Before dropping old columns, verify: `SELECT count(*) FROM meetings WHERE pipeline_entry_id IS NULL AND account_id IS NOT NULL;` should return 0.

**Which phase should address:** Phase 1 (schema migration), with FK update as a distinct, separately-verified step.

---

### Pitfall 5: Breaking MCP Tools and Background Engines During Migration

**What goes wrong:** Multiple backend engines query `accounts`, `leads`, `lead_contacts`, and `account_contacts` directly:
- `meeting_processor_web.py` — joins `AccountContact` to match attendees to accounts (line 173)
- `channel_task_extractor.py` — queries `Account` by normalized_name and `AccountContact` by email to resolve entities (lines 387-402)
- `flywheel_ritual.py` — imports `LeadContact`, `LeadMessage` for lead pipeline stage computation (line 22)
- `skill_executor.py` — queries `Account` by ID for meeting-to-account linking (line 1806)
- `synthesis_engine.py` — queries `Account` and `ContextEntry` for AI summary generation (lines 122, 207)
- `context_store_writer.py` — accepts `account_id` parameter throughout (6 functions)

If the ORM models change before the migration is complete, OR if the migration completes before the code deploys, you get a window where either old code hits new schema or new code hits old schema.

**Why it happens:** This is a live system with background workers (gmail sync, calendar sync, flywheel ritual) that run continuously. There is no maintenance window — the daily user is actively using the system.

**Consequences:** Meeting processing fails silently (no crash, but meetings are not linked to accounts). Task extraction cannot resolve entities. The flywheel ritual produces broken HTML briefings. Context entries are written without account links.

**Prevention:**
1. **Dual-read period:** ORM models support BOTH old and new table names during transition. Use a compatibility layer: `PipelineEntry` model with `__tablename__ = "pipeline_entries"` but also register views or aliases for `accounts` and `leads`.
2. **Feature flag:** Add a `UNIFIED_PIPELINE` feature flag. All engine code checks the flag and uses the appropriate model/table. Roll forward one engine at a time.
3. **API backward compatibility:** Keep old endpoints (`/accounts/*`, `/leads/*`) working during transition by routing to the new unified service layer. Deprecate after all consumers are migrated.
4. **Deploy order:** (a) Deploy migration, (b) Deploy code with dual-read, (c) Verify all engines work, (d) Remove old code paths.

**Detection:** Monitor the flywheel ritual output. If meeting counts drop to zero or account links are missing, the engine-to-schema mismatch has occurred.

**Which phase should address:** Phase 2 (backend migration). This is the riskiest phase and should be split into multiple plans: one per engine.

---

## Moderate Pitfalls

### Pitfall 6: RLS Policy Gaps on New Tables

**What goes wrong:** The current RLS policies are table-specific:
- `accounts` has a custom `visibility_isolation` policy (migration 042) that checks `visibility = 'team' OR owner_id = app.user_id`.
- `leads` has standard `tenant_isolation` policies (migration 040) with separate INSERT/UPDATE/SELECT/DELETE.
- `lead_contacts`, `lead_messages`, `account_contacts`, `outreach_activities` have standard tenant-only isolation.

The unified `pipeline_entries` table needs the MOST restrictive policy from any source table (visibility-aware), but if you create it with only tenant isolation, personal entries become visible to the entire team.

**Why it happens:** Copy-paste from a simpler table's migration. The visibility-aware policy from accounts migration 042 is easy to miss.

**Consequences:** Privacy breach: personal pipeline entries visible to all team members. Depending on data sensitivity, this could expose draft outreach, advisor relationships, or investor conversations.

**Prevention:**
1. The `pipeline_entries` RLS policy MUST include visibility awareness: `(visibility = 'team' OR owner_id = current_setting('app.user_id')::uuid)`.
2. The unified `contacts` table needs tenant isolation only (contacts are always team-visible).
3. The unified `activities` table needs tenant isolation only.
4. Write RLS policies FIRST, before migrating data. Test with a non-owner user.

**Detection:** After migration, connect as a different user and verify: `SET app.tenant_id = '...'; SET app.user_id = '<non-owner-id>'; SELECT * FROM pipeline_entries WHERE visibility = 'personal';` should return zero rows.

**Which phase should address:** Phase 1 (schema creation). RLS is part of table creation, not a follow-up.

---

### Pitfall 7: Frontend State Fragmentation — Three Query Caches Becoming One

**What goes wrong:** The frontend currently maintains separate React Query caches:
- `['leads', params]` — LeadsPage
- `['accounts', params]` — AccountsPage
- `['pipeline', params]` — PipelinePage
- `['lead-detail', id]` — LeadSidePanel
- `['account', id]` — AccountDetailPage
- `['leads-pipeline']` — LeadsFunnel
- `['timeline', accountId, params]` — TimelineFeed

The graduation flow in `useLeadGraduate.ts` and `useGraduate.ts` invalidates BOTH leads and accounts caches. If you replace these with a single `['pipeline-entries', params]` cache, mutations that previously invalidated one list now invalidate the shared list, causing unnecessary re-renders for the entire pipeline.

**Why it happens:** Cache invalidation scope changes when you merge entities. A lead update that previously only invalidated the leads list now invalidates the unified list that includes all pipeline entries.

**Consequences:** Sluggish UI — every mutation causes a full list re-fetch. If the unified list has 500+ entries, this is noticeable. Worse: stale data if you keep old cache keys and the old endpoints are removed.

**Prevention:**
1. Use React Query's `queryKey` factory pattern: `['pipeline-entries', { view: 'leads', ...params }]` so view-specific filters are cache-isolated.
2. Use `queryClient.setQueryData` for optimistic updates on mutations instead of full invalidation.
3. During transition, keep old query hooks working (they call the new API but use renamed keys) and migrate page-by-page.
4. Graduation becomes a simple PATCH to change `stage` — no cross-cache invalidation needed.

**Detection:** Chrome DevTools React Query Devtools extension. Watch for cache keys being invalidated unnecessarily after mutations.

**Which phase should address:** Phase 3 (frontend rebuild). Plan the cache key structure BEFORE building components.

---

### Pitfall 8: Entity Resolution Conflicts — Same Company from Multiple Sources

**What goes wrong:** The same company can enter the system from 5+ sources: GTM scrape (seed_crm.py), meeting processing (attendee domain matching), email context extraction (company mentions), LinkedIn scrape (lead contacts), and manual entry. Each source may use different name variants:
- Seed: "Satguru Ventures Pvt. Ltd."
- Meeting: "Satguru"
- Email: "satguru ventures"
- LinkedIn: "SATGURU VENTURES PVT LTD"

The `normalize_company_name()` function in `utils/normalize.py` handles most suffixes, but edge cases remain:
- "A.I. Solutions" vs "AI Solutions" (periods removed, but the output differs from "ai solutions" vs "a i solutions" — wait, actually periods ARE removed in the normalizer, so both become "ai")
- "The Boston Group" vs "Boston Group" ("the" prefix stripped)
- "McKinsey & Company" vs "McKinsey" (suffix stripped, but "&" handling varies)

**Why it happens:** No authoritative entity registry exists. `normalize_company_name()` is good but not perfect. The `companies` table (global intel cache, line 85-104 of models.py) is keyed on `domain`, not `normalized_name`. Pipeline entries are keyed on `(tenant_id, normalized_name)`. If a meeting creates a pipeline entry before the domain is known, and a later scrape creates another entry with the domain, you get duplicates.

**Consequences:** Duplicate pipeline entries for the same company. Meeting history split across two entries. AI summaries missing data from one of the duplicates.

**Prevention:**
1. Two-pass dedup: normalize_company_name FIRST, then domain match SECOND. If domain matches but name differs, merge into the domain-matched entry.
2. Add a `domain` uniqueness constraint on `pipeline_entries`: `UNIQUE(tenant_id, domain) WHERE domain IS NOT NULL`. This prevents domain-level duplicates.
3. During migration, run a dedup pass: group by `(tenant_id, domain)` and merge entries with matching domains but different normalized names.
4. For meeting processing and email extraction, always check domain first (from attendee email domain), normalized name second.

**Detection:** Periodic audit: `SELECT tenant_id, domain, count(*) FROM pipeline_entries WHERE domain IS NOT NULL GROUP BY 1,2 HAVING count(*) > 1;`

**Which phase should address:** Phase 1 (migration dedup) and Phase 2 (engine updates must use domain-first resolution).

---

### Pitfall 9: The Person-Who-Is-Also-A-Company-Contact Dual-Entity Problem

**What goes wrong:** An advisor like "Laurie" is a person-level entity (entity_type='person' in pipeline_entries) BUT also a contact at a company like "Howden" (a company-level pipeline entry). In the unified schema:
- Laurie has her own row in `pipeline_entries` (type=person, relationship_type includes 'advisor')
- Howden has a row in `pipeline_entries` (type=company, relationship_type includes 'customer')
- Laurie should appear in Howden's contacts panel
- Laurie's own pipeline entry should show her advisory relationship context

If the `contacts` table only links to pipeline_entries via `pipeline_entry_id` (replacing `account_id`), then Laurie-as-advisor and Laurie-as-Howden-contact are two separate records with no link. Updates to one don't flow to the other. The user sees stale data on one of the surfaces.

**Why it happens:** The current schema has no cross-reference between `AccountContact` and `Account` at the person level. The CRM redesign concept brief (line 96-99) explicitly called out this pattern but did not resolve it architecturally.

**Consequences:** Data divergence. The user updates Laurie's email on her advisor page, but Howden's contact panel still shows the old email. Meeting notes tagged to Laurie-as-advisor don't appear on Howden's timeline.

**Prevention:**
1. Add a `person_entry_id UUID REFERENCES pipeline_entries(id)` column on the `contacts` table. When a contact matches a person-type pipeline entry, link them.
2. Person-type pipeline entries get a self-referencing contact row (as specified in STATE.md decision: "contacts table always has rows for person-type entries").
3. When displaying a contact, check if `person_entry_id` is set. If so, pull name/email/title from the pipeline entry (single source of truth), not from the contacts row.
4. Write a sync trigger or application-level hook: when a person pipeline entry is updated, propagate changes to all linked contact rows.

**Detection:** After migration: `SELECT c.id, c.name, pe.name FROM contacts c JOIN pipeline_entries pe ON c.person_entry_id = pe.id WHERE c.name != pe.name;` should return zero rows.

**Which phase should address:** Phase 1 (schema design) and Phase 2 (backend logic for person-entry linking).

---

### Pitfall 10: Performance Regression on Unified Table

**What goes wrong:** Currently:
- `leads` has ~200 rows with GIN index on `purpose` array
- `accounts` has ~20 rows with composite indexes on `(tenant_id, status)`, `(tenant_id, pipeline_stage)`, `(tenant_id, relationship_status)`, and a GIN index on `relationship_type` array

Merging into one `pipeline_entries` table creates ~220 rows (small now, but grows). The current Pipeline grid query in `outreach.py:440-480` joins `Account` with `OutreachActivity`, `AccountContact`, and subqueries for last status and primary contact. This query already has 4 subqueries and 3 joins. On a unified table, the WHERE clause must include `entity_type` filtering, which adds a seq scan if not indexed.

**Why it happens:** Index design for separate tables doesn't transfer to a combined table. The `idx_account_tenant_status` index assumes all rows are accounts. On a unified table, the most common query pattern is `WHERE tenant_id = ? AND entity_type = ?` — this needs a composite index that includes `entity_type`.

**Consequences:** At 200 rows, negligible. At 2,000+ rows (reasonable after a year of use), the pipeline grid query slows noticeably. At 10,000+ rows (unlikely but possible with aggressive scraping), sub-second response time is at risk.

**Prevention:**
1. Every index on `pipeline_entries` should include `entity_type` in the composite: `INDEX idx_pe_tenant_type_stage ON pipeline_entries(tenant_id, entity_type, stage)`.
2. Add partial indexes for common filtered views: `INDEX idx_pe_active ON pipeline_entries(tenant_id, stage) WHERE retired_at IS NULL`.
3. The `last_activity_at` denormalized column (from STATE.md decisions) should have an index: `INDEX idx_pe_activity ON pipeline_entries(tenant_id, last_activity_at DESC) WHERE retired_at IS NULL`.
4. Run `EXPLAIN ANALYZE` on the pipeline grid query BEFORE and AFTER migration. Ensure no seq scans on the unified table.

**Detection:** Add query timing logging to the pipeline API. Alert if P95 exceeds 200ms.

**Which phase should address:** Phase 1 (index design as part of schema creation).

---

## Minor Pitfalls

### Pitfall 11: Alembic Revision Chain Breakage

**What goes wrong:** The current latest revision is `043_fix_context_entries_rls_soft_delete`. Adding a new migration for the unified pipeline must correctly set `down_revision`. If multiple developers (or parallel agent sessions) create migrations simultaneously, the revision chain breaks.

**Prevention:** Always check `alembic heads` before creating a new migration. Use sequential numbering (044, 045, etc.) consistent with the project convention. Create all unified-pipeline migrations in sequence within a single session.

**Which phase should address:** Phase 1.

---

### Pitfall 12: Losing the Graduation History

**What goes wrong:** The current `Lead.graduated_at` and `Lead.account_id` fields record when and where a lead was promoted. In the unified schema, there is no "graduation" — entries just change stage. If the `graduated_at` timestamp is not preserved, the history of when pipeline entries were promoted is lost.

**Prevention:** Preserve `graduated_at` as a column on `pipeline_entries`. Or better: log stage changes as activity records (type='stage_change' as specified in STATE.md decisions) which provides a full audit trail.

**Which phase should address:** Phase 1 (schema design).

---

### Pitfall 13: MCP Tool Descriptions Referencing Old Table Names

**What goes wrong:** MCP tool descriptions and help text may reference "leads" and "accounts" as separate concepts. Users who have built muscle memory around "graduate a lead" will be confused when the concept disappears.

**Prevention:** Update all MCP tool descriptions. Rename `graduate` to `advance_stage` or similar. Add aliases for backward compatibility during transition.

**Which phase should address:** Phase 2 (backend migration) or Phase 4 (cleanup).

---

### Pitfall 14: Seed Script Breaks

**What goes wrong:** `seed_crm.py` directly creates `Account`, `AccountContact`, and `OutreachActivity` ORM instances. After the migration, these models no longer exist or are renamed. Running the seed script on a fresh database fails.

**Prevention:** Update `seed_crm.py` to use the new models immediately after Phase 1. This is a low-effort change but easy to forget.

**Which phase should address:** Phase 1 (schema migration) — update seed script in the same plan.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Severity | Mitigation |
|-------------|---------------|----------|------------|
| Schema creation (DDL) | PgBouncer silent rollback (Pitfall 1) | CRITICAL | Per-statement commits via SQL Editor or direct connection |
| Data migration script | Data loss on merge (Pitfall 2) | CRITICAL | Column mapping, graduated-lead handling, row count verification |
| Data migration script | Contact dedup conflicts (Pitfall 3) | CRITICAL | Email-first matching, preserve-both-on-ambiguity, child record re-parenting |
| FK reference updates | Breaking meetings/tasks/context (Pitfall 4) | CRITICAL | Add new column first, populate, verify, then drop old column |
| Backend engine migration | Engine-to-schema mismatch (Pitfall 5) | CRITICAL | Dual-read period, feature flag, one-engine-at-a-time rollout |
| RLS policy creation | Privacy breach (Pitfall 6) | HIGH | Visibility-aware policy from day one, test with non-owner user |
| Frontend rebuild | Cache fragmentation (Pitfall 7) | MODERATE | QueryKey factory pattern, optimistic updates, page-by-page migration |
| Entity resolution | Duplicate entries (Pitfall 8) | MODERATE | Domain-first resolution, uniqueness constraint on domain |
| Person-as-contact pattern | Data divergence (Pitfall 9) | MODERATE | person_entry_id FK, single source of truth for person data |
| Index design | Query regression (Pitfall 10) | LOW (at current scale) | Composite indexes with entity_type, EXPLAIN ANALYZE verification |
| Alembic management | Chain breakage (Pitfall 11) | LOW | Check `alembic heads` before creating migrations |
| History preservation | Lost graduation timestamps (Pitfall 12) | LOW | Preserve graduated_at or use activity-based stage change log |

## Supabase-Specific Gotchas Summary

1. **PgBouncer DDL transactions** (Pitfall 1): The single most dangerous gotcha. Every DDL statement must be its own commit. Use SQL Editor or direct connection string.
2. **FK to `profiles` table**: Alembic cannot see the `profiles` table (it exists but is invisible to Alembic's connection context). The `pipeline_entries.owner_id` FK must be added via raw SQL, not Alembic's `ForeignKey()`.
3. **RLS policy creation order**: Policies must be created AFTER the table but BEFORE data migration. If data is migrated without RLS, a brief window exists where all data is visible to any authenticated user.
4. **Index creation on large tables**: `CREATE INDEX CONCURRENTLY` is not supported through Alembic and must be run as raw SQL. For the migration of 220 rows this is irrelevant, but worth noting for future index additions.
5. **Trigger functions**: The `last_activity_at` DB trigger (from STATE.md decisions) must be created via raw SQL. Supabase supports triggers but they must be created through the SQL Editor, not through the Alembic pooled connection.

## Sources

- Direct codebase analysis: `db/models.py` (6 CRM table definitions), `api/leads.py` (10 endpoints), `api/accounts.py` (8 endpoints), `api/relationships.py` (8 endpoints), `api/outreach.py` (pipeline grid queries), `api/timeline.py` (FK joins), `api/meetings.py` (account linking), `api/tasks.py` (account FK)
- Engine analysis: `meeting_processor_web.py`, `channel_task_extractor.py`, `flywheel_ritual.py`, `skill_executor.py`, `synthesis_engine.py`, `context_store_writer.py`
- Migration history: 43 Alembic migrations, specifically `040_create_leads_tables.py`, `041_lead_user_scoping.py`, `042_accounts_visibility_rls_and_constraints.py`
- Project decisions: `.planning/STATE.md` (v9.0 design decisions), `.planning/CONCEPT-BRIEF-crm-redesign.md` (dual-entity pattern), `.planning/PROJECT.md` (unified pipeline spec)
- Known constraints: `CLAUDE.md` Supabase DDL workaround, `feedback_supabase_ddl.md`
