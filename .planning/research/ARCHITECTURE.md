# Architecture Patterns: Library Redesign

**Domain:** Document library with tags, filtering, dedup, pagination
**Researched:** 2026-04-08
**Confidence:** HIGH (based on direct codebase analysis)

## Current Architecture Snapshot

### Backend Layer
```
cli/flywheel_mcp/server.py          -- MCP tool: flywheel_save_document()
  -> cli/flywheel_mcp/api_client.py -- HTTP client: POST /api/v1/documents/from-content
    -> backend/.../api/documents.py  -- FastAPI router: create_from_content()
      -> backend/.../db/models.py    -- Document + SkillRun ORM models
```

### Frontend Layer
```
frontend/src/app/routes.tsx          -- /documents, /documents/:id routes
  -> features/documents/components/DocumentLibrary.tsx  -- main list page
  -> features/documents/components/DocumentViewer.tsx   -- detail page
  -> features/documents/api.ts                          -- fetchDocuments(), fetchDocument()
  -> features/documents/utils.ts                        -- type styles, title cleaning
```

### Database (current Document table)
```sql
documents (
  id UUID PK,
  tenant_id UUID FK -> tenants.id,     -- RLS-scoped
  user_id UUID FK -> profiles.id,
  title TEXT,
  document_type TEXT,                   -- "meeting-prep", "company-intel", etc.
  mime_type TEXT DEFAULT 'text/html',
  storage_path TEXT,                    -- legacy: Supabase Storage path
  file_size_bytes INT,
  skill_run_id UUID FK -> skill_runs.id,
  share_token TEXT UNIQUE,
  metadata JSONB DEFAULT '{}',          -- {companies: [], contacts: [], tags: []}
  created_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ                -- soft delete
)
```

---

## Recommended Architecture for Library Redesign

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Alembic migration 053** | Add tags[], account_id, module, updated_at columns + GIN index + partial unique index | PostgreSQL via Supabase SQL Editor |
| **Document ORM model** | SQLAlchemy model with new columns mapped | API layer, DB |
| **documents.py API router** | 3 new endpoints + modify list endpoint for cursor pagination + tag filters | Frontend via HTTP, DB via SQLAlchemy |
| **MCP tool (server.py)** | Extended save_document with account_id, tags params | Backend API via HTTP |
| **api_client.py** | HTTP client with new params for save_document | MCP tool layer |
| **DocumentLibrary.tsx** | Tag filter bar, cursor pagination, updated query params | Backend API, URL state |
| **TagFilterBar.tsx (NEW)** | Interactive tag chips with counts, contextual updates | DocumentLibrary parent |
| **documents/api.ts** | New fetch functions: tags-with-counts, cursor-paginated list | Backend API |

### New vs Modified Components

#### NEW files to create:

| File | Purpose |
|------|---------|
| `backend/alembic/versions/053_library_tags_dedup.py` | Migration: tags[], account_id FK, module, updated_at, GIN index, partial unique index |
| `frontend/src/features/documents/components/TagFilterBar.tsx` | Tag chip filter bar with counts |
| `frontend/src/features/documents/hooks/useDocumentFilters.ts` | Filter state management + URL sync |

#### MODIFIED files:

| File | Changes |
|------|---------|
| `backend/src/flywheel/db/models.py` | Add `tags`, `account_id`, `module`, `updated_at` to Document class; add indexes |
| `backend/src/flywheel/api/documents.py` | Add 3 new endpoints; refactor list_documents for cursor pagination + tag/account filtering; modify create_from_content for dedup + tags |
| `cli/flywheel_mcp/server.py` | Add `tags` and `account_id` params to `flywheel_save_document()` |
| `cli/flywheel_mcp/api_client.py` | Add `tags` and `account_id` to `save_document()` method payload |
| `frontend/src/features/documents/api.ts` | Add `DocumentListItem.tags`, `DocumentListItem.account_id`; new `fetchTags()`, cursor-based `fetchDocuments()` |
| `frontend/src/features/documents/components/DocumentLibrary.tsx` | Replace offset pagination with cursor; add TagFilterBar; wire filter state to query |
| `frontend/src/features/documents/components/DocumentRow.tsx` | Display tag pills on each row |
| `frontend/src/features/documents/components/DocumentGridCard.tsx` | Display tag pills on each card |

#### UNCHANGED files (verified no changes needed):

| File | Reason |
|------|--------|
| `frontend/src/app/routes.tsx` | Routes /documents and /documents/:id already exist |
| `backend/src/flywheel/main.py` | documents_router already registered at /api/v1 |
| `backend/src/flywheel/api/deps.py` | RLS dependency chain unchanged |
| `frontend/src/features/documents/components/DocumentViewer.tsx` | Detail page not in this milestone scope |
| `frontend/src/features/documents/components/SharedDocumentPage.tsx` | Public share unaffected |
| `frontend/src/features/documents/utils.ts` | Type styles already complete from design brief |

---

## Data Flow: Document Creation (Skill -> Library)

### Happy Path

```
1. Skill execution in Claude Code
   |
   v
2. flywheel_save_document(title, content, skill_name, account_id?, tags?)
   [cli/flywheel_mcp/server.py:524]
   |
   v
3. client.save_document(title, skill_name, markdown_content, metadata={account_id, tags})
   [cli/flywheel_mcp/api_client.py:173]
   |  POST /api/v1/documents/from-content
   v
4. create_from_content() -- ENHANCED
   [backend/src/flywheel/api/documents.py:180]
   |
   |-- a. Account resolution (NEW)
   |     If account_id provided: validate FK exists in pipeline_entries
   |     If not: attempt fuzzy match from metadata.companies[0]
   |
   |-- b. Auto-tagging (NEW)
   |     Merge explicit tags[] with auto-derived tags:
   |     - skill_name -> tag (e.g. "meeting-prep")
   |     - account domain -> tag if resolvable
   |
   |-- c. Title dedup check (NEW)
   |     ON CONFLICT (tenant_id, document_type, title)
   |     WHERE deleted_at IS NULL
   |     DO UPDATE SET skill_run_id, updated_at, tags (merged)
   |
   |-- d. Create SkillRun (existing)
   |     SkillRun(status="completed", ...)
   |
   |-- e. Create/Update Document
   |     Document(tags=merged_tags, account_id=resolved_id, ...)
   |
   v
5. Response: {document_id, skill_run_id, is_update: bool}
```

### Error Cases

| Error | Where | Handling |
|-------|-------|----------|
| Invalid account_id | Step 4a | Log warning, proceed without account link (don't fail the save) |
| Account not found by name | Step 4a | Set account_id = NULL, save normally |
| Tag array too long (>20) | Step 4b | Truncate to first 20, log warning |
| Dedup conflict race condition | Step 4c | Use ON CONFLICT with partial unique index; let Postgres resolve |
| Markdown rendering fails | Step 4d | Save raw markdown in output, set rendered_html = NULL |
| Database commit fails | Step 4e | Return 500, MCP tool reports error string to Claude |

### Dedup Strategy

Use a **partial unique index** rather than application-level SELECT-then-INSERT:

```sql
CREATE UNIQUE INDEX idx_documents_dedup
ON documents (tenant_id, document_type, title)
WHERE deleted_at IS NULL;
```

The API uses SQLAlchemy's `on_conflict_do_update` or a raw `INSERT ... ON CONFLICT ... DO UPDATE SET`:
- Updates `skill_run_id` to latest run
- Updates `updated_at` to now()
- Merges tags (union of old + new via `array_cat` + `array_distinct`)
- Preserves original `created_at`

This is safe under PgBouncer because the UNIQUE index constraint is enforced at the Postgres level regardless of transaction mode.

**Important note on SkillRun ordering:** The SkillRun must be created BEFORE the Document upsert because the Document FK references skill_run_id. On conflict (dedup hit), the old SkillRun is orphaned. This is acceptable -- orphaned SkillRuns are harmless rows. Alternatively, the old skill_run_id can be preserved and a new version linked via metadata.

**Critical Supabase note:** The DDL migration (CREATE INDEX) must be run via Supabase SQL Editor or individual commits, NOT through Alembic multi-statement transaction. See the Supabase DDL workaround in project memory.

---

## Data Flow: Tag-Filtered Document List

```
1. User clicks tag "meeting-prep" in TagFilterBar
   |
   v
2. useDocumentFilters hook updates URL params
   ?tags=meeting-prep&cursor=...
   |
   v
3. fetchDocuments({ tags: ["meeting-prep"], cursor: "2026-04-08T..." })
   [frontend/src/features/documents/api.ts]
   |  GET /documents/?tags=meeting-prep&cursor=2026-04-08T...
   v
4. list_documents() -- ENHANCED
   [backend/src/flywheel/api/documents.py]
   |
   |-- a. Base query: WHERE deleted_at IS NULL
   |-- b. Tag filter: WHERE tags @> ARRAY['meeting-prep']::text[]  (GIN index hit)
   |-- c. Type filter: WHERE document_type = :type (if set)
   |-- d. Search filter: WHERE title ILIKE '%query%' (if set)
   |-- e. Cursor: WHERE created_at < :cursor
   |-- f. ORDER BY created_at DESC LIMIT 51 (fetch N+1 for has_more)
   |
   v
5. Response: {documents: [...50], next_cursor: "iso-datetime", has_more: true}
```

### Cursor Pagination Design

Replace the current offset-based pagination (`offset` + `limit` params) with cursor-based.

**Why:** Offset pagination breaks when new documents are inserted between page loads (user sees duplicates or misses items). With skills creating documents asynchronously, this is a real scenario. Cursor pagination is stable.

**Implementation:**
- Cursor = `created_at` ISO timestamp of last item on current page
- Query: `WHERE created_at < :cursor ORDER BY created_at DESC LIMIT :limit+1`
- If result has `limit+1` rows, `has_more = true`, pop the extra row, cursor = last row's `created_at`
- First page: no cursor param (returns newest documents)
- **Edge case:** Two documents with identical `created_at` could cause cursor to skip one. Mitigate with compound cursor `(created_at, id)` -- `WHERE (created_at, id) < (:cursor_ts, :cursor_id)`. This uses the existing primary key index.

**Backward compatibility:** Keep `offset` param working (deprecated) for any existing callers. If both `offset` and `cursor` are provided, `cursor` wins.

---

## Data Flow: Tags with Counts

```
1. DocumentLibrary mounts or filters change
   |
   v
2. fetchTags({ document_type?: "meeting-prep" })
   |  GET /documents/tags?document_type=meeting-prep
   v
3. NEW endpoint: get_document_tags()
   |
   |  SELECT unnest(tags) AS tag, count(*) AS count
   |  FROM documents
   |  WHERE deleted_at IS NULL
   |    AND (:document_type IS NULL OR document_type = :document_type)
   |  GROUP BY tag
   |  ORDER BY count DESC
   |  LIMIT 50
   |
   v
4. Response: [{tag: "meeting-prep", count: 12}, {tag: "acme-corp", count: 5}, ...]
```

**Contextual behavior:** When a type tab is active, tag counts reflect only that type. When "All" is active, counts are global. This requires refetching tags when the type tab changes -- handled by including `activeType` in the React Query key.

---

## New API Endpoints Summary

### 1. GET /documents/tags
Returns distinct tags with counts for the current tenant.

```typescript
// Request
GET /api/v1/documents/tags?document_type=meeting-prep

// Response 200
{
  tags: [
    { tag: "meeting-prep", count: 12 },
    { tag: "acme-corp", count: 5 }
  ]
}
```

**CRITICAL: Must be registered BEFORE `/{document_id}` route** to avoid FastAPI path conflict. FastAPI matches routes in registration order. If `/{document_id}` comes first, a request to `/documents/tags` would try to parse "tags" as a UUID and return 422. The existing code already follows this pattern (see `documents.py` line 8 docstring).

### 2. GET /documents/counts-by-type
Returns document counts grouped by type (replaces client-side counting from the current DocumentLibrary lines 101-116).

```typescript
// Request
GET /api/v1/documents/counts-by-type

// Response 200
{
  counts: [
    { document_type: "meeting-prep", count: 15 },
    { document_type: "company-intel", count: 8 }
  ],
  total: 42
}
```

### 3. PATCH /documents/{document_id}/tags
Add or remove tags on an existing document.

```typescript
// Request
PATCH /api/v1/documents/{document_id}/tags
{ add: ["important"], remove: ["draft"] }

// Response 200
{ tags: ["meeting-prep", "important"] }
```

### Modified: GET /documents/
Extended with cursor and tag filter params.

```typescript
// Request params (new params marked)
GET /api/v1/documents/?document_type=meeting-prep&tags=acme-corp&cursor=2026-04-07T12:00:00Z&limit=50&search=acme

// Response (new fields marked)
{
  documents: [...],
  total: 42,
  next_cursor: "2026-04-07T10:30:00Z",   // NEW
  has_more: true                           // NEW
}
```

### Modified: POST /documents/from-content
Extended request body.

```typescript
// Request body (new fields marked)
{
  title: "Meeting Prep: Acme Corp",
  skill_name: "meeting-prep",
  markdown_content: "...",
  metadata: { companies: ["Acme Corp"] },
  tags: ["meeting-prep", "acme-corp"],     // NEW - explicit tags
  account_id: "uuid-or-null",             // NEW - link to pipeline entry
  module: "meeting-prep"                   // NEW - categorization
}

// Response (new field marked)
{
  document_id: "uuid",
  skill_run_id: "uuid",
  is_update: false                         // NEW - true if dedup matched
}
```

---

## Schema Changes (Migration 053)

```sql
-- Run each statement individually via Supabase SQL Editor
-- (PgBouncer silently rolls back multi-statement DDL transactions)

-- 1. Add new columns
ALTER TABLE documents ADD COLUMN tags TEXT[] DEFAULT '{}';
ALTER TABLE documents ADD COLUMN account_id UUID REFERENCES pipeline_entries(id) ON DELETE SET NULL;
ALTER TABLE documents ADD COLUMN module TEXT;
ALTER TABLE documents ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now();

-- 2. GIN index for tag array queries (WHERE tags @> ARRAY['tag'])
CREATE INDEX idx_documents_tags ON documents USING GIN (tags);

-- 3. Composite index for filtered + sorted queries
CREATE INDEX idx_documents_tenant_created ON documents (tenant_id, created_at DESC)
WHERE deleted_at IS NULL;

-- 4. Partial unique index for dedup (ON CONFLICT target)
CREATE UNIQUE INDEX idx_documents_dedup ON documents (tenant_id, document_type, title)
WHERE deleted_at IS NULL;

-- 5. Account FK index for join queries
CREATE INDEX idx_documents_account ON documents (account_id)
WHERE account_id IS NOT NULL;

-- 6. Backfill tags from existing metadata.tags (if any exist)
UPDATE documents
SET tags = ARRAY(SELECT jsonb_array_elements_text(metadata->'tags'))
WHERE metadata ? 'tags' AND jsonb_array_length(metadata->'tags') > 0;

-- 7. Backfill updated_at from created_at for existing rows
UPDATE documents SET updated_at = created_at WHERE updated_at IS NULL;

-- 8. Stamp alembic
-- alembic stamp 053
```

### ORM Model Changes

```python
# In backend/src/flywheel/db/models.py, Document class additions:

tags: Mapped[list[str]] = mapped_column(
    ARRAY(Text), server_default=text("'{}'::text[]")
)
account_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("pipeline_entries.id", ondelete="SET NULL"), nullable=True
)
module: Mapped[str | None] = mapped_column(Text, nullable=True)
updated_at: Mapped[datetime.datetime] = mapped_column(
    TIMESTAMP(timezone=True), server_default=text("now()")
)
```

Add to `__table_args__`:
```python
Index("idx_documents_tags", "tags", postgresql_using="gin"),
Index(
    "idx_documents_tenant_created",
    "tenant_id", "created_at",
    postgresql_where=text("deleted_at IS NULL"),
),
Index(
    "idx_documents_dedup",
    "tenant_id", "document_type", "title",
    unique=True,
    postgresql_where=text("deleted_at IS NULL"),
),
Index(
    "idx_documents_account",
    "account_id",
    postgresql_where=text("account_id IS NOT NULL"),
),
```

---

## Frontend Architecture

### State Management Pattern

Follow the existing pattern from PipelineFilterBar: local component state + URL search params, no global store needed.

```
DocumentLibrary (page component)
  |
  |-- useDocumentFilters() hook (NEW)
  |     Manages: activeType, activeTags[], cursor, searchQuery
  |     Syncs to: URL search params (?type=meeting-prep&tags=acme)
  |     Returns: { filters, setType, toggleTag, clearTags, setCursor }
  |
  |-- useQuery(['documents', filters])
  |     queryFn: fetchDocuments(filters)
  |     Keyed on full filter state for proper React Query cache invalidation
  |
  |-- useQuery(['document-tags', activeType])
  |     queryFn: fetchTags({ document_type: activeType })
  |     Refetches when type tab changes (activeType in key)
  |
  |-- useQuery(['document-counts'])
  |     queryFn: fetchCountsByType()
  |     For tab counts -- fetched once, staleTime: 60s
  |
  +-- TagFilterBar (NEW component)
  |     Props: tags[], activeTags[], onToggle, onClear
  |     Renders: horizontal scrollable chip bar with counts
  |     Pattern: similar to PipelineFilterBar multi-select dropdown
  |
  +-- DocumentRow / DocumentGridCard (MODIFIED)
        Now receive and display tags[] as small pills
```

### Query Key Strategy

```typescript
// Documents list -- refetches on any filter change
['documents', { type, tags, cursor, search }]

// Tags with counts -- refetches only when type tab changes
['document-tags', type]

// Type counts -- fetched once on mount, cached for 60s
['document-counts']
```

### Tag Filter Interaction Flow

1. User clicks type tab -> refetch tags for that type, reset tag selection, reset cursor
2. User clicks tag chip -> toggle in activeTags[], refetch documents from first page
3. User clicks "Clear" on tag bar -> empty activeTags[], refetch documents
4. Active tags rendered as filled pills (brand tint bg), inactive as outlined (subtle border)
5. Tag counts update based on current type filter (not current tag selection -- avoids confusing zero-count tags)

### URL State Sync

```
/documents?type=meeting-prep&tags=acme-corp,important&search=q2
```

The `useDocumentFilters` hook reads initial state from URL params on mount and writes back on every change. This enables:
- Shareable filtered views (copy URL)
- Browser back/forward navigation through filter states
- Bookmarkable saved searches

Pattern reference: the existing PipelineFilterBar does NOT sync to URL. The library should be better -- follow the approach from React Router's `useSearchParams`.

---

## Patterns to Follow

### Pattern 1: FastAPI Route Ordering (Critical)
The existing documents.py has a specific route ordering comment (line 8). New `/documents/tags` and `/documents/counts-by-type` endpoints MUST be registered before `/{document_id}` to prevent FastAPI treating "tags" as a UUID.

```python
# Correct order in the router:
@router.get("/")                    # List (existing)
@router.get("/tags")                # NEW - must come before /{id}
@router.get("/counts-by-type")      # NEW - must come before /{id}
@router.get("/shared/{share_token}")# Existing
@router.post("/from-content")       # Existing (modified)
@router.get("/{document_id}/content") # Existing
@router.get("/{document_id}")       # Existing - catch-all UUID param last
@router.post("/{document_id}/share") # Existing
@router.patch("/{document_id}/tags") # NEW - under /{id} namespace
```

### Pattern 2: RLS-Scoped Queries
All document queries go through `get_tenant_db` dependency which sets `app.tenant_id` in the Postgres session via `get_tenant_session()`. The RLS policy automatically filters by tenant. The existing code also adds explicit `WHERE tenant_id` clauses as defense-in-depth -- follow this same pattern in new queries.

### Pattern 3: Supabase DDL Migrations
Write the Alembic migration file for documentation and downgrade support, but apply DDL via individual SQL statements in Supabase SQL Editor. Then `alembic stamp` to sync version. This is documented in project CLAUDE.md and memory.

### Pattern 4: React Query Cache Keys
Follow the existing pattern from `usePipeline.ts`: query keys are arrays with filter objects. When filters change, React Query automatically refetches. Invalidate the document list on tag CRUD operations.

### Pattern 5: Pydantic Response Models
The existing documents.py defines explicit Pydantic response models (DocumentListItem, DocumentDetail, DocumentListResponse). New response fields (tags, next_cursor, has_more) must be added to these models. New endpoints need their own response models (TagCount, TagListResponse, TypeCount, TypeCountResponse).

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Tags in JSONB metadata
**What:** Storing tags inside the existing `metadata` JSONB column (where some already live).
**Why bad:** Cannot use GIN index for array containment (`@>`). Requires `jsonb_array_elements_text()` for every query -- much slower than native array `@>` with GIN. No type safety. Existing metadata.tags values are inconsistent strings vs arrays.
**Instead:** Dedicated `TEXT[]` column with GIN index. Backfill from metadata.tags during migration.

### Anti-Pattern 2: Client-Side Tag Counting
**What:** Fetching all documents and counting tags in JavaScript (the current DocumentLibrary does this for type tabs at lines 101-116).
**Why bad:** Doesn't scale past ~200 docs. With tags, the combinatorial explosion makes it worse. Also means the first page load fetches ALL documents just to build tab counts.
**Instead:** Dedicated `/documents/tags` and `/documents/counts-by-type` server endpoints. Lightweight queries that return only aggregates.

### Anti-Pattern 3: ON CONFLICT on Primary Key for Dedup
**What:** Using the document UUID as the conflict target.
**Why bad:** Different skill runs for the same report generate different UUIDs. The second run creates a duplicate. Dedup should match on semantic identity: (tenant_id, document_type, title).
**Instead:** Partial unique index on (tenant_id, document_type, title) WHERE deleted_at IS NULL.

### Anti-Pattern 4: Eager Account Resolution Blocking Save
**What:** Making account resolution a required step that blocks document save on failure.
**Why bad:** If account lookup fails (name mismatch, account not yet in pipeline, pipeline_entries table empty for new tenants), the entire document save fails. Skills should NEVER lose their output.
**Instead:** Account resolution is best-effort. Save document regardless. Log a warning if resolution fails. Document can be linked to an account later via tag or manual edit.

### Anti-Pattern 5: Separate Tag Table with Join
**What:** Creating a `document_tags` junction table (document_id, tag) instead of a TEXT[] column.
**Why bad:** Overkill for this use case. Tags are simple strings, not entities with their own metadata. A junction table means JOINs on every document query, more complex mutations, and more migration DDL. PostgreSQL native arrays with GIN are purpose-built for this pattern.
**Instead:** TEXT[] column with GIN index. Simpler schema, simpler queries, same performance.

---

## Suggested Build Order

Dependencies flow: **Schema -> ORM -> API -> MCP Tool -> Frontend**

### Plan 01: Backend Foundation (must be first)

```
Step 1: Migration 053 (schema changes via SQL Editor)
  |  No dependencies. Creates columns + indexes.
  v
Step 2: ORM model updates (models.py)
  |  Depends on: Step 1 (columns must exist in DB)
  v
Step 3: New endpoints (tags, counts-by-type)
  |  Depends on: Step 2 (model must have tags column mapped)
  |  Register BEFORE /{document_id} route.
  v
Step 4: Modify list_documents for cursor pagination + tag/search filters
  |  Depends on: Step 2 (GIN index for tag queries)
  v
Step 5: Modify create_from_content for dedup + tags + account_id
  |  Depends on: Step 2 (dedup index), Step 3 (tag infrastructure)
  v
Step 6: Add PATCH /{document_id}/tags endpoint
  |  Depends on: Step 2
```

### Plan 02: Frontend (requires backend endpoints)

```
Step 1: api.ts updates (new types, new fetch functions, cursor support)
  |  Depends on: Backend Plan 01 complete
  v
Step 2: useDocumentFilters hook (filter state + URL sync)
  |  Depends on: Step 1 (API types for filter params)
  v
Step 3: TagFilterBar component
  |  Depends on: Step 1 (fetchTags API), Step 2 (filter state)
  v
Step 4: DocumentLibrary rewrite (cursor pagination, tags, server-side counts)
  |  Depends on: Steps 1-3 all complete
  v
Step 5: DocumentRow + DocumentGridCard tag pills
  |  Can run in parallel with Step 4
```

### Plan 03: Skill Ecosystem (requires backend API changes)

```
Step 1: api_client.py (add tags, account_id to save_document payload)
  |  Depends on: Backend Plan 01 Step 5
  v
Step 2: server.py MCP tool (expose tags, account_id params to Claude)
  |  Depends on: Step 1
  v
Step 3: Update skill CLAUDE.md instructions (tell skills to pass tags)
  |  Depends on: Step 2
```

### Parallelization Opportunities

- Frontend Step 5 (tag pills in rows/cards) can parallel with Step 4 (library rewrite)
- Plan 03 (skill ecosystem) can start after Backend Step 5, even if Frontend isn't done
- Backend Steps 3 and 6 can parallel (different functions in same file, no shared state)
- Backend Step 4 and Step 5 are independent (list endpoint vs create endpoint)

---

## Scalability Considerations

| Concern | At 100 docs | At 1K docs | At 10K docs |
|---------|-------------|------------|-------------|
| Tag query (`@>` with GIN) | <1ms | <10ms | <50ms |
| List with cursor pagination | Instant | Instant | Instant (B-tree on created_at) |
| Tag counts (`unnest` + `GROUP BY`) | <1ms | ~20ms | ~100ms -- consider materialized view |
| Dedup check (unique index) | Instant | Instant | Instant (B-tree) |
| Type counts (`GROUP BY document_type`) | <1ms | ~10ms | ~30ms, cache with staleTime: 60s |

At 10K+ documents, the `unnest(tags) + GROUP BY` for tag counts may slow down. If that happens, a materialized view refreshed on document write is the standard PostgreSQL answer. Not needed for initial implementation -- premature optimization.

---

## Sources

- Direct codebase analysis of all referenced files (HIGH confidence):
  - `backend/src/flywheel/api/documents.py` -- current 5 endpoints, route ordering
  - `backend/src/flywheel/db/models.py` -- Document class at line 891, Account class at line 1159
  - `backend/src/flywheel/api/deps.py` -- RLS tenant scoping chain
  - `backend/src/flywheel/db/session.py` -- get_tenant_session RLS implementation
  - `cli/flywheel_mcp/server.py` -- flywheel_save_document at line 524
  - `cli/flywheel_mcp/api_client.py` -- save_document at line 173
  - `frontend/src/features/documents/` -- all components, api.ts, utils.ts
  - `frontend/src/features/pipeline/components/PipelineFilterBar.tsx` -- filter pattern reference
  - `frontend/src/app/routes.tsx` -- routing structure
- PostgreSQL GIN index documentation for array containment queries
- Supabase PgBouncer DDL limitation (documented in project CLAUDE.md)
