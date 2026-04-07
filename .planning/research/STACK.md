# Technology Stack

**Project:** Unified Pipeline Schema & UI
**Researched:** 2026-04-06

## Recommended Stack

### Principle: Minimal Additions

The existing stack (FastAPI, SQLAlchemy 2.0 async, AG Grid Community v35, React 19, Tailwind v4, Supabase PostgreSQL) already covers 90% of what this milestone needs. The recommendations below are surgical additions, not replacements.

**New packages needed: ZERO (backend and frontend).**
**New database extensions needed: ONE (pg_trgm, enable via Supabase Dashboard).**

---

### 1. Schema Migration (Alembic + Supabase PgBouncer)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Alembic | >=1.14 (existing) | Migration file authoring and version tracking | Already in stack; no change needed |
| Supabase SQL Editor | N/A | Actual DDL execution | PgBouncer silently rolls back multi-statement DDL transactions; each statement must be its own commit |

**Migration strategy for table merging (6 tables -> 3+1):**

Alembic serves as **documentation and version tracking only**. Actual execution goes through Supabase SQL Editor or individual `session.execute()` + `session.commit()` calls. Then `alembic stamp <revision>` to sync state. This is the same pattern used across all 43 existing migrations.

**Required pattern for this milestone:**

```python
# Alembic migration file -- for documentation + downgrade support
def upgrade():
    # Phase 1: Create new tables (do NOT drop old tables yet)
    op.create_table('pipeline_entries', ...)
    op.create_table('pipeline_entry_sources', ...)
    # Unified contacts table (merging lead_contacts + account_contacts)
    op.create_table('contacts', ...)
    # Unified activities table (merging lead_messages + outreach_activities)
    op.create_table('activities', ...)

    # Phase 2: Migrate data
    op.execute("""
        INSERT INTO pipeline_entries (id, tenant_id, name, normalized_name, domain, ...)
        SELECT id, tenant_id, name, normalized_name, domain, ...
        FROM accounts WHERE ...
    """)
    op.execute("""
        INSERT INTO pipeline_entries (id, tenant_id, name, normalized_name, domain, ...)
        SELECT id, tenant_id, name, normalized_name, domain, ...
        FROM leads WHERE ...
    """)
    # ... similar for contacts, activities, sources junction

    # Phase 3: Create indexes, triggers, RLS policies on new tables
    # Phase 4: Drop old tables (separate migration, after app code is updated)

def downgrade():
    # Reverse: recreate old tables from new ones
```

**Critical: CREATE new tables, do NOT RENAME old ones.** Reasons:
- Renaming requires also renaming all sequences, indexes, constraints, and RLS policies
- Supabase RLS policies reference table names by string; renaming silently breaks them
- Fresh tables let you set up clean RLS policies from scratch
- Old tables coexist during migration window for rollback safety
- UUIDs as primary keys mean old IDs carry over to new tables without conflicts

**Execution order (each as separate SQL Editor statement):**
1. CREATE TABLE pipeline_entries
2. CREATE TABLE pipeline_entry_sources
3. CREATE TABLE contacts (unified)
4. CREATE TABLE activities (unified)
5. INSERT INTO pipeline_entries ... (data migration from accounts)
6. INSERT INTO pipeline_entries ... (data migration from leads)
7. INSERT INTO contacts ... (from lead_contacts)
8. INSERT INTO contacts ... (from account_contacts)
9. INSERT INTO activities ... (from lead_messages)
10. INSERT INTO activities ... (from outreach_activities)
11. INSERT INTO pipeline_entry_sources ... (backfill source tracking)
12. CREATE INDEX statements (one per statement)
13. CREATE TRIGGER statements
14. ALTER TABLE ENABLE ROW LEVEL SECURITY + CREATE POLICY statements
15. `alembic stamp <revision>` to sync version state

**Confidence:** HIGH -- matches documented Supabase DDL workaround in CLAUDE.md and pattern used across 43 existing migrations.

---

### 2. AG Grid Airtable-Style UX

| Feature Needed | AG Grid Community Support | Implementation |
|----------------|--------------------------|----------------|
| Inline cell editing | YES - `editable: true` on ColDef | Built-in, no new packages |
| Custom cell editors (dropdowns, tags) | YES - `cellEditor` component prop | Build custom React components |
| Cell editor popups | YES - `cellEditorPopup: true` | Built-in |
| Column resize | YES - already using `resizable: true` | No change |
| Column reorder | YES - already using column move handlers | No change |
| Row click -> side panel | YES - already built | `PipelineSidePanel.tsx` exists |
| Full row editing mode | YES - Community feature | `editType: 'fullRow'` on grid |
| Row selection (single/multi) | YES - built-in | No change |
| Column state persistence | YES - already built | `usePipelineColumns.ts` saves to localStorage |
| Master/Detail (nested grid) | NO - Enterprise only | **Not needed** -- side panel is better UX |

**No new packages needed.** The existing `ag-grid-community@35.2.0` + `ag-grid-react@35.2.0` covers everything required.

**Key implementation patterns for Airtable-style editing:**

```typescript
// 1. Simple dropdown editing (pipeline stage)
{
  headerName: 'Stage',
  field: 'pipeline_stage',
  editable: true,
  cellEditor: 'agSelectCellEditor',  // built-in
  cellEditorParams: {
    values: ['prospect', 'qualified', 'proposal', 'negotiation', 'closed_won', 'closed_lost']
  },
}

// 2. Custom cell editor for complex fields (multi-select tags, rich text)
{
  headerName: 'Tags',
  field: 'relationship_type',
  editable: true,
  cellEditor: TagEditor,         // custom React component
  cellEditorPopup: true,         // renders as popup overlay, not inline
  cellEditorPopupPosition: 'under',
}

// 3. Optimistic update on edit complete
onCellValueChanged={(event) => {
  // Fire mutation via React Query, revert on error
  updatePipelineEntry.mutate({
    id: event.data.id,
    [event.colDef.field]: event.newValue,
  }, {
    onError: () => {
      // Revert: set old value back
      event.node.setDataValue(event.colDef.field!, event.oldValue)
      toast.error('Failed to save')
    }
  })
}}
```

**Row expand pattern:** Keep the existing side panel approach (click row -> 440px slide-in from right). This matches Airtable's actual UX. Master/Detail (Enterprise) renders a nested grid inline, which is wrong for CRM record detail.

**Confidence:** HIGH -- verified against AG Grid v35 Community vs Enterprise feature matrix. Cell editing, custom editors, column operations are all explicitly Community features.

---

### 3. Database Triggers for Denormalized Fields

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL PL/pgSQL triggers | PostgreSQL 15 (Supabase) | Auto-update `last_activity_at`, `contact_count`, `activity_count` on `pipeline_entries` | Guarantees consistency even on direct DB edits or bulk imports |

**Trigger pattern for `last_activity_at`:**

```sql
-- Function: update parent pipeline_entry when activities change
CREATE OR REPLACE FUNCTION fn_update_pipeline_entry_activity_ts()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    UPDATE pipeline_entries
    SET last_activity_at = (
      SELECT MAX(created_at) FROM activities
      WHERE pipeline_entry_id = OLD.pipeline_entry_id
    ), updated_at = NOW()
    WHERE id = OLD.pipeline_entry_id;
    RETURN OLD;
  ELSE
    UPDATE pipeline_entries
    SET last_activity_at = NOW(),
        updated_at = NOW()
    WHERE id = NEW.pipeline_entry_id;
    RETURN NEW;
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER trg_activities_update_pipeline_entry
  AFTER INSERT OR UPDATE OR DELETE ON activities
  FOR EACH ROW
  EXECUTE FUNCTION fn_update_pipeline_entry_activity_ts();
```

**Trigger pattern for `contact_count`:**

```sql
CREATE OR REPLACE FUNCTION fn_update_pipeline_entry_contact_count()
RETURNS TRIGGER AS $$
DECLARE
  target_id UUID;
BEGIN
  target_id := COALESCE(NEW.pipeline_entry_id, OLD.pipeline_entry_id);
  UPDATE pipeline_entries
  SET contact_count = (
    SELECT COUNT(*) FROM contacts WHERE pipeline_entry_id = target_id
  ), updated_at = NOW()
  WHERE id = target_id;
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER trg_contacts_update_pipeline_entry
  AFTER INSERT OR DELETE ON contacts
  FOR EACH ROW
  EXECUTE FUNCTION fn_update_pipeline_entry_contact_count();
```

**Key decisions:**

1. **SECURITY DEFINER** -- triggers must bypass RLS to update the parent table. Without this, the trigger fails if RLS blocks the cross-table UPDATE. Safe because trigger logic is fixed, not user-controlled.

2. **AFTER trigger, not BEFORE** -- the child row (activity/contact) must be committed first, then we update the parent. BEFORE triggers would reference rows that don't yet exist.

3. **FOR EACH ROW** -- the volume per operation is low (one activity insert at a time). FOR EACH STATEMENT with transition tables is more complex and only beneficial for bulk inserts.

4. **Application-layer belt-and-suspenders** -- also compute `last_activity_at` in the API endpoint, so the field works correctly even if triggers are temporarily disabled during schema migrations.

**Confidence:** HIGH -- standard PostgreSQL pattern; Supabase explicitly supports custom triggers with SECURITY DEFINER.

---

### 4. Entity Deduplication for Multi-Source Entries

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pg_trgm` extension | Available in Supabase (enable manually) | Fuzzy company name matching via trigram similarity | Standard approach; runs in DB, no round-trip overhead |
| Application-layer dedup logic | Python/SQLAlchemy | Multi-signal matching pipeline | Orchestrates the 3-tier matching strategy |

**No external dedup library needed.** The matching scope is company names within a single tenant (hundreds to low thousands of records), not probabilistic entity resolution across millions.

**3-tier deduplication strategy:**

| Tier | Signal | Confidence | Action |
|------|--------|------------|--------|
| 1: Exact match | `normalized_name` within tenant | 100% | Auto-merge during data migration, no user confirmation |
| 2: Domain match | Same `domain` (e.g., acme.com) within tenant | 95% | Auto-merge during data migration, log for audit |
| 3: Fuzzy match | `pg_trgm` similarity > 0.6 on `normalized_name` | Variable | Flag as potential duplicate; user confirms in UI |

**Implementation:**

```sql
-- Step 1: Enable pg_trgm (one-time, via Supabase Dashboard > Extensions)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Step 2: GIN index for fast fuzzy lookups
CREATE INDEX idx_pipeline_entry_name_trgm
  ON pipeline_entries USING gin (normalized_name gin_trgm_ops);

-- Step 3: Find Tier 1+2 duplicates during migration
-- (exact name OR same domain)
SELECT a.id AS keep_id, b.id AS merge_id,
       'exact_name' AS match_reason
FROM pipeline_entries a
JOIN pipeline_entries b
  ON a.tenant_id = b.tenant_id
  AND a.normalized_name = b.normalized_name
  AND a.id < b.id;

-- Step 4: Find Tier 3 fuzzy duplicates (post-migration, for user review)
SELECT a.id, b.id,
       similarity(a.normalized_name, b.normalized_name) AS score
FROM pipeline_entries a
JOIN pipeline_entries b
  ON a.tenant_id = b.tenant_id
  AND a.id < b.id
  AND similarity(a.normalized_name, b.normalized_name) > 0.6
WHERE a.domain IS DISTINCT FROM b.domain;  -- skip domain matches (already merged)
```

**Merge strategy:**
- `pipeline_entry_sources` junction table tracks origin: `('accounts', original_id)`, `('leads', original_id)`, `('apollo', import_id)`, etc.
- On merge: keep the record with more data (higher field fill rate), union all sources, re-parent all contacts and activities from the merged record
- Expose "Possible duplicates" badge in the grid + merge UI in the side panel

**The 0.6 threshold** is a well-documented starting point for company name matching. It correctly catches "Acme Corp" vs "Acme Corporation" while avoiding false positives like "Acme" vs "Amazon". May need tuning after initial migration -- expose it as a config value.

**Confidence:** MEDIUM -- pg_trgm is available in Supabase but needs manual enabling. The threshold may need tuning per real data distribution.

---

## What NOT to Add

| Technology | Why Not |
|------------|---------|
| `ag-grid-enterprise` | Master/Detail is not needed; side panel is better UX for CRM records. Saves significant license cost (~$1500+/yr). |
| `dedupe` or `splink` Python libraries | Overkill for tenant-scoped company matching (hundreds of records). pg_trgm + domain matching is sufficient. |
| Real-time sync (liveblocks, yjs) | Not doing collaborative editing. Single-user inline edit with optimistic updates via React Query. |
| Separate migration tool (flyway, dbmate) | Alembic already in stack; just need the PgBouncer single-statement workaround. |
| `react-hook-form` or `formik` | AG Grid's built-in cell editing handles inline forms. Side panel edits use simple controlled components. |
| `react-table` / TanStack Table | AG Grid already in codebase and proven across Pipeline + Leads pages. Switching is a regression. |
| GraphQL / Hasura | REST endpoints with React Query already handle the data fetching. No N+1 problem since pipeline entries are a flat list with JOINed data. |
| Elasticsearch / Meilisearch | Pipeline search is simple column filtering on a few thousand records. PostgreSQL indexes + existing FTS are sufficient. |
| `pgcron` for scheduled dedup | Run dedup on-demand (import events) and during migration. No recurring schedule needed. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Grid editing | AG Grid Community inline edit | AG Grid Enterprise | License cost; Community covers all needed editing features |
| Grid detail | Side panel (existing pattern) | Master/Detail (Enterprise) | Wrong UX pattern -- nested grid vs. record detail panel |
| Grid detail | Side panel (existing pattern) | Full-width expandable row | Breaks table layout; side panel preserves context |
| Fuzzy match | pg_trgm (in-database) | Python rapidfuzz/fuzzywuzzy | Keeps matching in DB, no round-trip, simpler architecture |
| Denorm sync | PostgreSQL triggers | Application-layer only | Triggers guarantee consistency on direct DB edits and bulk imports |
| Denorm sync | PostgreSQL triggers | Materialized views | Overkill; only 2-3 denormalized fields, not aggregate queries |
| Migration execution | SQL Editor + alembic stamp | Direct Alembic execution | PgBouncer constraint makes multi-DDL unreliable |
| Migration approach | CREATE new + migrate data | ALTER TABLE RENAME | Rename breaks RLS policies, sequences, index names |
| Dedup library | pg_trgm + domain match | dedupe (Python) | Probabilistic ER is over-engineered for <10K company records per tenant |

---

## Installation

**No new npm packages needed.** Frontend `package.json` stays exactly as-is.

**No new Python packages needed.** Backend `pyproject.toml` stays exactly as-is.

**One database extension to enable (one-time, via Supabase Dashboard > Database > Extensions):**

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

pg_trgm is pre-installed in Supabase but not enabled by default. Enabling it is a single click in the Dashboard or a single SQL statement.

---

## Version Summary

| Component | Current Version | Change Needed |
|-----------|----------------|---------------|
| ag-grid-community | 35.2.0 | None -- use inline editing features already included |
| ag-grid-react | 35.2.0 | None |
| alembic | >=1.14 | None -- files for documentation, execute via SQL Editor |
| SQLAlchemy | >=2.0 | None -- new async models follow existing patterns |
| PostgreSQL | 15 (Supabase) | Enable pg_trgm extension |
| React Query | 5.91.2 | None -- use for optimistic updates on inline edits |
| Zustand | 5.0.12 | None -- use for side panel state, column preferences |
| React Router | 7.13.1 | None -- existing routing handles profile pages |

---

## Sources

- [AG Grid Community vs Enterprise](https://www.ag-grid.com/javascript-data-grid/community-vs-enterprise/) -- feature matrix confirming cell editing is Community, Master/Detail is Enterprise
- [AG Grid Cell Editing docs](https://www.ag-grid.com/react-data-grid/cell-editing/) -- inline editing API, `editable`, `cellEditor`, `cellEditorPopup`
- [AG Grid Cell Editors](https://www.ag-grid.com/react-data-grid/cell-editors/) -- built-in editors including `agSelectCellEditor`
- [PostgreSQL pg_trgm docs](https://www.postgresql.org/docs/current/fuzzystrmatch.html) -- trigram similarity functions
- [Crunchy Data: Fuzzy Name Matching](https://www.crunchydata.com/blog/fuzzy-name-matching-in-postgresql) -- pg_trgm best practices and threshold recommendations
- [Supabase Extensions docs](https://supabase.com/docs/guides/database/extensions) -- pg_trgm availability in Supabase
- [Supabase Triggers docs](https://supabase.com/docs/guides/database/postgres/triggers) -- trigger support, SECURITY DEFINER pattern
- [PostgreSQL Trigger Functions](https://www.postgresql.org/docs/current/plpgsql-trigger.html) -- PL/pgSQL trigger authoring reference
- [Alembic Operations Reference](https://alembic.sqlalchemy.org/en/latest/ops.html) -- `rename_table`, `create_table`, `execute` operations
- [Pete Graham: Rename Postgres Table with Alembic](https://petegraham.co.uk/rename-postgres-table-with-alembic/) -- why CREATE > RENAME when dealing with sequences/indexes
- Existing codebase: `db/models.py` (6 CRM tables), `PipelinePage.tsx` (AG Grid usage), `PipelineSidePanel.tsx` (side panel pattern), `usePipelineColumns.ts` (column state persistence), `alembic/env.py` (migration config)
