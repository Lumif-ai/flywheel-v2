# Domain Pitfalls

**Domain:** Broker Module Milestone 2 -- Client/contact entities, context store integration, solicitation workflow restructuring, schema migration (6 new tables, 6 modified, 15 columns dropped)
**Researched:** 2026-04-14
**Confidence:** HIGH for codebase-specific pitfalls (direct code analysis of broker.py, models.py, gmail_sync.py, solicitation_drafter.py). HIGH for PgBouncer DDL behavior (proven pattern from broker_migration.py). MEDIUM for PostgreSQL CHECK constraint behavior with existing data (verified against PostgreSQL docs).

---

## Critical Pitfalls

Mistakes that cause data loss, silent failures, or require rollbacks.

### Pitfall 1: PgBouncer Silently Rolls Back Multi-Statement DDL Migrations

**What goes wrong:** Supabase's PgBouncer pooler silently rolls back multi-statement DDL within a single transaction. Alembic wraps all `upgrade()` statements in one transaction. The `alembic_version` row updates successfully (it is the last statement), but all CREATE TABLE / ALTER TABLE / DROP COLUMN statements are rolled back. The migration appears to succeed -- `alembic current` shows the new revision -- but the actual schema is unchanged.

**Why it happens:** PgBouncer in transaction pooling mode assigns connections per-transaction. Multi-statement DDL within a single transaction can exceed PgBouncer's capabilities, causing silent rollback of DDL while allowing the version table update.

**Consequences:** Application crashes with `UndefinedTable` or `UndefinedColumn` errors at runtime. Since `alembic_version` says the migration ran, running `alembic upgrade head` again does nothing. The developer thinks the migration succeeded. Production data operations fail.

**Prevention:**
1. Use the established `broker_migration.py` pattern: each DDL statement runs as its own committed transaction via `async with factory() as session: await session.execute(text(...)); await session.commit()`
2. After all statements succeed, run `alembic stamp <revision>` to sync alembic state
3. Order statements in FK dependency order: parent tables first, then child tables, then indexes, then constraints
4. For this milestone, the order must be: `broker_clients` -> `client_contacts` -> `carrier_contacts` -> `solicitation_drafts` -> `context_links` -> `broker_intel` -> ALTER existing tables -> DROP columns -> CREATE indexes
5. NEVER use Alembic's `upgrade()` directly for DDL changes on Supabase

**Detection:** After running migration, verify with direct SQL: `SELECT column_name FROM information_schema.columns WHERE table_name = 'broker_clients'`. If empty, the migration was silently rolled back.

**Phase:** Must be addressed in the very first phase (schema migration). Every subsequent phase depends on schema being correct.

### Pitfall 2: Dropping carrier_configs.email_address Before Seeding carrier_contacts

**What goes wrong:** The spec calls for moving `email_address` from `carrier_configs` to a new `carrier_contacts` table. If the column is dropped before seeding data into `carrier_contacts`, all carrier email addresses are permanently lost. There are currently 12+ references to `carrier_configs.email_address` across backend (broker.py: 8 refs, gmail_sync.py: 4 refs) and frontend (CarrierForm.tsx: 4 refs, BrokerCarriersPage.tsx: 1 ref, broker.ts types: 4 refs).

**Why it happens:** A developer writes the migration as: create `carrier_contacts` table, drop `email_address` column. This is logically correct but operationally catastrophic -- the seed step is forgotten or fails silently.

**Consequences:** Every carrier loses their email address. Solicitation drafting breaks (`carrier.email_address` returns None). Gmail sync carrier matching breaks (gmail_sync.py line 1130: `CarrierConfig.email_address.isnot(None)` returns no rows). No way to recover without database backup.

**Prevention:**
1. Migration must be THREE separate committed transactions in strict order:
   - Transaction 1: CREATE `carrier_contacts` table
   - Transaction 2: INSERT INTO `carrier_contacts` (SELECT from `carrier_configs` WHERE `email_address` IS NOT NULL) -- seed step
   - Transaction 3: ALTER TABLE `carrier_configs` DROP COLUMN `email_address`
2. Between Transaction 2 and 3, verify seed count: `SELECT COUNT(*) FROM carrier_contacts` must equal `SELECT COUNT(*) FROM carrier_configs WHERE email_address IS NOT NULL`
3. Never drop the column in the same phase as creating the table. Create + seed in phase 1, drop in a later phase after all code references are updated.

**Detection:** After migration, run `SELECT COUNT(*) FROM carrier_contacts WHERE contact_type = 'submission_email'`. If 0 but carriers had email addresses, the seed was skipped.

**Phase:** Schema migration phase. The seed step must be verified BEFORE the drop step executes.

### Pitfall 3: Solicitation Workflow Restructure Breaks CarrierQuote Assumptions

**What goes wrong:** Currently, `draft_solicitations` (broker.py line 1571-1710) creates a `CarrierQuote` row immediately when drafting. The restructure moves quote creation to quote receipt, creating `SolicitationDraft` rows instead during drafting. Any code that assumes "a CarrierQuote exists after solicitation" will break.

**Why it happens:** The current code creates `CarrierQuote` at line 1651-1660 with `status="pending"` and `draft_status="pending"`. Multiple downstream systems depend on this:
- Task generation (broker.py line 314-316): queries `CarrierQuote.draft_status == "pending"` to generate review tasks
- Follow-up detection (broker.py line 474-490): queries `CarrierQuote.draft_status == "sent"` and `CarrierQuote.solicited_at` to find overdue solicitations
- Project status auto-transition (broker.py line 1526-1562): counts CarrierQuotes to determine if all carriers are solicited
- Send endpoint (broker.py line 1815-1868): looks up `CarrierQuote` by ID to send the email
- Portal confirm endpoint (broker.py line 1920-1984): updates `CarrierQuote.draft_status` to track portal submission

**Consequences:** After restructure, the task generation query returns 0 results (no pending CarrierQuotes exist during drafting phase). Follow-up detection stops working. Project status never auto-transitions to "soliciting" because the count logic references CarrierQuotes that do not exist yet.

**Prevention:**
1. Map every query that touches `CarrierQuote.draft_status` or `CarrierQuote.solicited_at` -- there are at least 15 references in broker.py
2. These queries must be rewritten to query `SolicitationDraft` for draft-phase data and `CarrierQuote` for quote-phase data
3. The project status auto-transition logic (line 1526-1562) must count `SolicitationDraft` rows for "all solicited" checks, not `CarrierQuote` rows
4. The send endpoint must update `SolicitationDraft.status` (not `CarrierQuote.draft_status`)
5. Build a compatibility mapping before writing any code:
   - `CarrierQuote.draft_status = "pending"` -> `SolicitationDraft.status = "pending"`
   - `CarrierQuote.draft_status = "sent"` -> `SolicitationDraft.status = "sent"`
   - `CarrierQuote.solicited_at` -> `SolicitationDraft.sent_at`
   - `CarrierQuote.draft_subject/draft_body` -> `SolicitationDraft.draft_subject/draft_body`

**Detection:** After restructure, create a project, draft solicitations, check the tasks endpoint. If no "review draft" tasks appear, the query was not updated.

**Phase:** Solicitation restructure phase. Must update ALL 15+ CarrierQuote.draft_status references simultaneously. Cannot be done incrementally.

### Pitfall 4: CHECK Constraints Fail on Tables with Existing Data

**What goes wrong:** Adding a CHECK constraint (e.g., `CHECK (analysis_status IN ('pending', 'in_progress', 'completed', 'failed'))`) to `broker_projects` fails if ANY existing row has a value not in the allowed list. The ALTER TABLE statement throws an error and the entire migration transaction rolls back.

**Why it happens:** The codebase uses `analysis_status = "completed"` (contract_analyzer.py line 326), but a CHECK constraint might use `'complete'` (without the 'd'). If any existing row has a value like `'error'`, `'analyzing'`, or any other value not in the CHECK list, the constraint cannot be added.

**Consequences:** Migration fails entirely. On Supabase with PgBouncer, this is especially dangerous because the failure may be silent (see Pitfall 1). The developer sees no error, stamps the migration, and the constraint does not exist.

**Prevention:**
1. Before adding any CHECK constraint, query existing values: `SELECT DISTINCT analysis_status FROM broker_projects`
2. Build the CHECK constraint to include ALL existing values, even deprecated ones
3. For `analysis_status`, verify the actual values in code: `contract_analyzer.py` sets `"completed"` (not `"complete"`). The CHECK must include `'completed'`
4. Add CHECK constraints as NOT VALID first, then VALIDATE separately:
   ```sql
   ALTER TABLE broker_projects ADD CONSTRAINT chk_analysis_status
     CHECK (analysis_status IN ('pending', 'in_progress', 'completed', 'failed'))
     NOT VALID;
   ALTER TABLE broker_projects VALIDATE CONSTRAINT chk_analysis_status;
   ```
   The NOT VALID approach adds the constraint for new rows without scanning existing data. The separate VALIDATE step checks existing rows and can be retried.
5. On Supabase, each of these must be a separate committed transaction (see Pitfall 1)

**Detection:** Run the ALTER TABLE manually in Supabase SQL Editor first. If it fails with "check constraint violated", query the offending values before fixing.

**Phase:** Schema migration phase. Validate existing data BEFORE writing migration scripts.

### Pitfall 5: Context Store Entity Creation Failure Breaks Client/Carrier Creation

**What goes wrong:** The spec requires creating a `ContextEntity` row when a `BrokerClient` or `CarrierConfig` is created, plus a `context_link` row to connect them. If the `ContextEntity` INSERT fails (e.g., duplicate name+type violates `uq_entity_tenant_name_type`), the entire transaction should roll back -- but if the rollback is not handled, you get orphaned broker records with no context entity, or orphaned context entities with no broker record.

**Why it happens:** `ContextEntity` has a unique constraint on `(tenant_id, name, entity_type)` (models.py line 553-556). Creating a client named "Acme Corp" as entity_type="company" works the first time. But if "Acme Corp" already exists in context_entities (from email extraction, meeting processing, or manual entry), the INSERT fails with `UniqueViolation`. The broker client creation endpoint must handle this as an upsert-or-link, not a create.

**Consequences:** Three failure modes:
1. Client created, context entity fails -> client exists but has no context intelligence (silent data gap)
2. Context entity created, client fails -> orphaned entity in context store
3. Both succeed but context_link fails -> both records exist but are disconnected

**Prevention:**
1. Use INSERT ... ON CONFLICT (tenant_id, name, entity_type) DO UPDATE SET last_seen_at = now(), mention_count = mention_count + 1 for the context entity
2. Wrap client + entity + link creation in a single database transaction with explicit savepoints
3. If the context entity already exists, reuse its ID for the context_link -- do NOT create a duplicate
4. The lookup should normalize names before matching: "Acme Corp" == "ACME CORP" == "Acme Corporation" (see Pitfall 8 for normalization details)
5. Test the scenario: create a client whose name already exists as a context entity from email extraction

**Detection:** After creating a client, query `context_entities` for a matching row. If none exists, the entity creation silently failed. Query `context_links` for the broker_client_id -- if no row, the link was not created.

**Phase:** Client/contact entity creation phase. The upsert pattern must be designed before any creation endpoint is written.

---

## Moderate Pitfalls

### Pitfall 6: 15 Column Drops Create Ghost References Across Full Stack

**What goes wrong:** Dropping 15 columns from existing tables means every code reference to those columns must be found and removed/redirected. Missing even one reference causes runtime errors (`AttributeError` in Python, `undefined` in TypeScript). The columns span at least two layers: backend (SQLAlchemy model attributes, API serializers, query filters) and frontend (TypeScript types, component props, form fields, grid column definitions).

**Why it happens:** Columns like `carrier_configs.email_address` are referenced in 6 backend files and 4 frontend files (see research above). Other columns being dropped (e.g., `recommendation_subject`, `recommendation_body`, `recommendation_status`, `recommendation_sent_at`, `recommendation_recipient` from `broker_projects`) are referenced in broker.py (15+ lines) and frontend DeliveryPanel.tsx (8+ lines) and broker.ts types (5 fields).

**Prevention:**
1. Before writing any migration, run a full-codebase grep for EVERY column being dropped:
   ```bash
   grep -rn "email_address\|recommendation_subject\|recommendation_body\|recommendation_status\|recommendation_sent_at\|recommendation_recipient\|approval_status" backend/ frontend/src/ --include="*.py" --include="*.ts" --include="*.tsx"
   ```
2. Build a complete reference map: file, line number, usage type (model definition, query, serializer, type definition, component prop, form field, grid column)
3. Update ALL references BEFORE dropping the column. The column drop should be the LAST step, not the first.
4. For `email_address` specifically: backend has 12 references across 3 files, frontend has 9 references across 3 files. Every one must redirect to `carrier_contacts` lookup.

**Detection:** After dropping columns, run the full test suite. Any `AttributeError: 'CarrierConfig' object has no attribute 'email_address'` or TypeScript build errors indicate missed references.

**Phase:** Code update phase must complete BEFORE schema drop phase. Two-phase approach: (1) update all code to use new tables/columns, (2) drop old columns only after code is verified.

### Pitfall 7: Partial Unique Indexes with WHERE Clauses in SQLAlchemy

**What goes wrong:** The spec likely requires partial unique indexes (e.g., unique email per carrier, but only for active contacts: `CREATE UNIQUE INDEX ... ON carrier_contacts(carrier_config_id, email) WHERE deleted_at IS NULL`). SQLAlchemy's `UniqueConstraint` does not support WHERE clauses. If you use `UniqueConstraint` without the WHERE clause, soft-deleted contacts block new contacts with the same email.

**Why it happens:** SQLAlchemy distinguishes between constraints and indexes. `UniqueConstraint` maps to `ALTER TABLE ADD CONSTRAINT` (no WHERE support). `Index(..., unique=True)` maps to `CREATE UNIQUE INDEX` and supports `postgresql_where`. The existing codebase already uses this pattern correctly for `idx_quote_source_dedup` (models.py line 2200-2201), but a developer might not notice the distinction.

**Prevention:**
1. Use `Index("idx_name", "col1", "col2", unique=True, postgresql_where=text("deleted_at IS NULL"))` in `__table_args__`
2. Do NOT use `UniqueConstraint` for any constraint that needs to exclude soft-deleted rows
3. Reference the existing pattern at models.py line 2200: `Index("idx_quote_source_dedup", "source_hash", unique=True, postgresql_where=text("source_hash IS NOT NULL"))`
4. In the migration script (not Alembic), use raw SQL: `CREATE UNIQUE INDEX IF NOT EXISTS ... WHERE deleted_at IS NULL`

**Detection:** Try to create a contact, soft-delete it, then create another contact with the same email. If you get a unique violation, the index is missing the WHERE clause.

**Phase:** Schema migration phase. Define all partial indexes in the migration script, not just in the SQLAlchemy model.

### Pitfall 8: Name Normalization for Dedup Fails on International Legal Suffixes

**What goes wrong:** Client and carrier deduplication requires normalized name matching. "Grupo Cementos de Chihuahua S.A. de C.V." and "GCC SAdeCV" and "Grupo Cementos de Chihuahua" should all match the same entity. Simple lowercasing or stripping punctuation fails on Mexican/Latin American legal suffixes (S.A. de C.V., S. de R.L., S.A.P.I., S.A.B.) which can appear in dozens of formats.

**Why it happens:** The project serves Mexican insurance brokers. Company names include legal entity suffixes that vary wildly: "S.A. de C.V." vs "SA de CV" vs "SADECV" vs "S.A.deC.V." These suffixes are meaningless for dedup purposes but defeat simple string matching.

**Prevention:**
1. Strip known legal suffixes before normalization. Build a suffix list: `S.A. de C.V.`, `S. de R.L.`, `S.A.P.I. de C.V.`, `S.A.B. de C.V.`, `S.C.`, `A.C.`, `Inc.`, `LLC`, `Ltd.`, `Corp.`, `GmbH`
2. Normalize: lowercase, strip punctuation, collapse whitespace, strip suffixes, then compare
3. Store the normalized name as a separate column (`normalized_name`) for index-based lookups
4. The existing `entity_normalization.py` service may already handle some of this -- check before building from scratch
5. Do NOT rely on `LOWER(name)` alone -- it will treat "GCC SA de CV" and "GCC" as different entities

**Detection:** Create two clients with the same company name but different suffix formatting. If both are created as separate entities, normalization is broken.

**Phase:** Client entity creation phase. Normalization logic must be defined before the creation endpoint.

### Pitfall 9: broker.py at 2900 Lines Becomes Unmaintainable with 17 New Endpoints

**What goes wrong:** The current `broker.py` is 2900 lines with approximately 30 endpoints. Adding 17 new endpoints (client CRUD, contact CRUD, context link management, solicitation draft management, intel endpoints) pushes it past 4000+ lines. At this size, developers cannot find endpoints, merge conflicts become constant, and circular import risks increase.

**Why it happens:** The initial broker module was a single-file implementation (common for MVPs). Each subsequent feature adds more endpoints to the same file because "that is where broker things go." Without explicit file-split discipline, the file grows indefinitely.

**Prevention:**
1. Split broker.py into domain-specific routers BEFORE adding new endpoints:
   - `broker_projects.py` -- project CRUD, status transitions
   - `broker_carriers.py` -- carrier config CRUD, contact management
   - `broker_clients.py` -- client CRUD, contact management (NEW)
   - `broker_solicitations.py` -- draft, send, follow-up (RESTRUCTURED)
   - `broker_quotes.py` -- quote receipt, comparison, selection
   - `broker_tasks.py` -- task generation, gate counts
   - `broker_delivery.py` -- recommendation drafting, sending
2. Use a parent router that includes sub-routers: `broker_router.include_router(clients_router, prefix="/clients")`
3. Move shared helpers (`_project_to_dict`, `_carrier_to_dict`, `_coverage_to_dict`) to `broker_helpers.py`
4. The split must happen BEFORE new endpoints are added, not after

**Detection:** `wc -l broker.py` exceeds 3500 lines. More than 3 endpoints share the same helper function. Merge conflicts on broker.py in every PR.

**Phase:** Should be the first or second phase. All subsequent phases benefit from the split.

### Pitfall 10: carrier_pipeline_entry_id FK Blocks pipeline_entries Cleanup

**What goes wrong:** `carrier_configs.carrier_pipeline_entry_id` has a foreign key to `pipeline_entries(id)` (models.py line 1984-1986). If the spec calls for dropping this column or changing the FK target, the FK constraint must be dropped FIRST. Attempting to drop the column without dropping the constraint fails. Attempting to modify `pipeline_entries` while this FK exists also fails.

**Why it happens:** PostgreSQL enforces FK constraints strictly. You cannot DROP a referenced column or TABLE while an FK pointing to it exists. The FK has `ON DELETE SET NULL`, so deleting pipeline entries is safe, but structural changes to `pipeline_entries` are blocked.

**Prevention:**
1. Drop the FK constraint before dropping the column: `ALTER TABLE carrier_configs DROP CONSTRAINT carrier_configs_carrier_pipeline_entry_id_fkey`
2. Then drop the column: `ALTER TABLE carrier_configs DROP COLUMN carrier_pipeline_entry_id`
3. Each statement must be a separate committed transaction (Pitfall 1)
4. If the column is being REPLACED (not just dropped), create the replacement column+FK first, seed data, then drop the old one

**Detection:** Migration script fails with `constraint ... depends on column ...`. Check `pg_constraint` for FK names before writing drop statements.

**Phase:** Schema migration phase, specifically in the column-drop sub-phase.

---

## Minor Pitfalls

### Pitfall 11: RLS Policies Missing on New Tables

**What goes wrong:** Supabase enforces Row Level Security. New tables (`broker_clients`, `client_contacts`, `carrier_contacts`, `solicitation_drafts`, `context_links`, `broker_intel`) need RLS policies or they will return empty result sets when accessed through the Supabase client. The backend uses a service role key that bypasses RLS, but any future direct Supabase access (e.g., Edge Functions, direct client SDK) will fail silently.

**Prevention:** Apply the same RLS policy template used for existing broker tables. Add `ALTER TABLE [table] ENABLE ROW LEVEL SECURITY` and create tenant-scoped policies in the migration script. Do this in the same migration that creates the table.

### Pitfall 12: Frontend Type Definitions Drift from Backend Schema

**What goes wrong:** After dropping columns from the backend and adding new tables, the frontend TypeScript types in `broker.ts` become stale. The types still reference `email_address`, `recommendation_subject`, etc. TypeScript does not error on extra properties in API responses, so the drift is silent until someone tries to READ a dropped field and gets `undefined`.

**Prevention:** Update `frontend/src/features/broker/types/broker.ts` in the same phase that drops backend columns. Add types for new entities (`BrokerClient`, `ClientContact`, `CarrierContact`, `SolicitationDraft`). Remove dropped fields from `CarrierConfig` and `BrokerProject` types.

### Pitfall 13: Gmail Sync Carrier Matching Breaks After email_address Move

**What goes wrong:** `gmail_sync.py` (line 1126-1142) matches incoming emails to carriers by comparing sender domain against `carrier_configs.email_address` domain. After moving email to `carrier_contacts`, this query must JOIN through the new table. If this JOIN is not added, carrier email auto-detection stops working -- incoming quote emails are no longer flagged with `is_carrier_quote: true`.

**Prevention:** Update the gmail_sync query to: `SELECT cc.* FROM carrier_configs cc JOIN carrier_contacts ct ON ct.carrier_config_id = cc.id WHERE ct.email IS NOT NULL AND ct.contact_type = 'submission_email'`. This must happen in the same phase that drops `carrier_configs.email_address`.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Schema migration (new tables) | Pitfall 1: PgBouncer silent rollback | Use broker_migration.py pattern. Each DDL = separate committed transaction. Verify with direct SQL after. |
| Schema migration (data seed) | Pitfall 2: Lost email addresses | Three-step: create table, seed data, verify count, THEN drop column in later phase. |
| Schema migration (CHECK constraints) | Pitfall 4: Existing data violates constraint | Query DISTINCT values before adding. Use NOT VALID + VALIDATE pattern. |
| Schema migration (partial indexes) | Pitfall 7: Soft-delete exclusion | Use Index(..., unique=True, postgresql_where=...) not UniqueConstraint. |
| Schema migration (FK drops) | Pitfall 10: FK blocks column drop | Drop constraint first, then column. Separate transactions. |
| Solicitation restructure | Pitfall 3: 15+ CarrierQuote refs break | Map ALL draft_status/solicited_at refs. Update simultaneously. Cannot be incremental. |
| Client/contact creation | Pitfall 5: Context entity upsert failure | Use ON CONFLICT DO UPDATE. Wrap in single transaction. Handle existing entities. |
| Client/contact creation | Pitfall 8: Mexican legal suffix dedup | Build suffix stripping + normalized_name column. Check entity_normalization.py first. |
| Code updates (pre-drop) | Pitfall 6: Ghost references | Full-codebase grep for every dropped column. Update ALL refs before dropping. |
| Code updates (pre-drop) | Pitfall 13: Gmail sync breaks | Update gmail_sync.py to JOIN carrier_contacts before dropping email_address. |
| Router organization | Pitfall 9: 4000+ line broker.py | Split into domain routers BEFORE adding new endpoints. |
| New table creation | Pitfall 11: Missing RLS | Apply RLS template to every new table in the migration script. |
| Frontend sync | Pitfall 12: Type drift | Update broker.ts types in same phase as backend column drops. |

---

## Sources

- Direct codebase analysis: broker.py (2900 lines), models.py (broker tables at line 1946-2300), gmail_sync.py (line 1120-1160), solicitation_drafter.py, broker_migration.py, entity_normalization.py, contract_analyzer.py (HIGH confidence)
- Existing broker_migration.py pattern for PgBouncer workaround (HIGH confidence -- proven in production)
- PostgreSQL CHECK constraint + NOT VALID documentation (HIGH confidence)
- SQLAlchemy partial index documentation for postgresql_where (HIGH confidence -- existing pattern in codebase at models.py line 2200)
- Mexican corporate entity suffix conventions (MEDIUM confidence -- common knowledge for Latin American business software)
