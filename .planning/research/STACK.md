# Technology Stack: Library Redesign

**Project:** Flywheel V2 - Library Redesign (Tags, Filtering, Pagination, Dedup)
**Researched:** 2026-04-08
**Overall confidence:** HIGH

## Recommended Stack

### Principle: Zero New Dependencies

The existing stack covers 100% of what the Library Redesign needs. No new npm packages. No new Python packages. No new database extensions.

| Feature | Existing Tool | Why Sufficient |
|---------|--------------|----------------|
| Tags column (`TEXT[]`) | `sqlalchemy.dialects.postgresql.ARRAY(Text)` | Used in 10+ models already |
| GIN index on tags | Alembic raw SQL | Pattern in migrations 010, 028, 040 |
| Tag containment queries | `.contains()`, `.overlap()` | Used in pipeline_service, leads, entity_normalization |
| Cursor-based pagination | SQLAlchemy `select().where().limit()` | Pure SQL keyset pagination |
| Infinite scroll | `useInfiniteQuery` from `@tanstack/react-query` v5 | Installed, just not used yet |
| Scroll sentinel | Native `IntersectionObserver` | Used in LandingPage.tsx, DealTapeTheater.tsx |
| Tag autocomplete | `cmdk` + custom component | cmdk already powers CommandPalette |
| ILIKE search | SQLAlchemy `.ilike()` | Built-in operator |
| Debounced search | `setTimeout` | Already in DocumentLibrary.tsx |
| Dedup (content hash) | SHA-256 + unique partial index | Standard PostgreSQL |

---

## Implementation Patterns

### 1. Tags Column -- PostgreSQL ARRAY with GIN Index

**Confidence:** HIGH (identical pattern used across codebase)

**Model addition:**
```python
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Text

# Add to Document model in db/models.py
tags: Mapped[list[str]] = mapped_column(
    ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
)
```

**Migration SQL (each statement as individual commit per Supabase DDL workaround):**
```sql
-- Statement 1: Add column
ALTER TABLE documents ADD COLUMN tags TEXT[] NOT NULL DEFAULT '{}';

-- Statement 2: Create GIN index
CREATE INDEX idx_documents_tags ON documents USING GIN (tags);
```

**GIN + tenant scoping:** GIN indexes cannot composite with non-array columns like UUID. Since RLS already filters by `tenant_id` via `current_setting('app.tenant_id')`, the query planner uses the RLS B-tree index on `tenant_id` first, then the GIN index on `tags`. This is the same approach used in migration 040 (`idx_lead_tenant_purpose`).

**Querying tags (verified from existing codebase patterns):**
```python
# Filter: documents matching ANY selected tag (OR -- for browsing)
stmt = stmt.where(Document.tags.overlap(["meeting-prep", "company-intel"]))

# Filter: documents matching ALL selected tags (AND -- for drill-down)
stmt = stmt.where(Document.tags.contains(["meeting-prep", "company-intel"]))

# Autocomplete: distinct tags across tenant
distinct_tags = await db.execute(
    select(func.unnest(Document.tags).label("tag"))
    .where(Document.deleted_at.is_(None))
    .distinct()
    .order_by(text("tag"))
    .limit(50)
)
```

**Sources:** `pipeline_service.py:276` uses `.overlap()`, `leads.py:325` uses `.contains()`, `entity_normalization.py:84` uses `.op("@>")`.

---

### 2. Cursor-Based Pagination -- Replacing Offset

**Confidence:** HIGH (standard SQLAlchemy keyset pagination)

**Why replace offset pagination:** The current `list_documents` endpoint uses `offset/limit` with a separate `COUNT(*)` query. Problems:
- Skipped/duplicated items when data changes between page loads
- `COUNT(*)` is a full table scan (slow at scale)
- Not compatible with infinite scroll UX

**Cursor approach using `created_at` + `id` (tiebreaker):**
```python
@router.get("/")
async def list_documents(
    document_type: str | None = None,
    tags: list[str] | None = Query(None),
    search: str | None = None,
    cursor: str | None = None,       # ISO timestamp of last item
    cursor_id: str | None = None,    # UUID tiebreaker
    limit: int = Query(20, ge=1, le=100),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> DocumentCursorResponse:
    base = select(Document).where(Document.deleted_at.is_(None))

    if document_type:
        base = base.where(Document.document_type == document_type)
    if tags:
        base = base.where(Document.tags.overlap(tags))
    if search:
        base = base.where(Document.title.ilike(f"%{search}%"))

    # Keyset pagination
    if cursor and cursor_id:
        cursor_dt = datetime.fromisoformat(cursor)
        cursor_uuid = UUID(cursor_id)
        base = base.where(
            or_(
                Document.created_at < cursor_dt,
                and_(
                    Document.created_at == cursor_dt,
                    Document.id < cursor_uuid,
                ),
            )
        )

    base = base.order_by(Document.created_at.desc(), Document.id.desc())
    rows = (await db.execute(base.limit(limit + 1))).scalars().all()

    has_more = len(rows) > limit
    items = rows[:limit]

    return DocumentCursorResponse(
        documents=[_doc_to_list_item(doc) for doc in items],
        has_more=has_more,
        next_cursor=items[-1].created_at.isoformat() if items and has_more else None,
        next_cursor_id=str(items[-1].id) if items and has_more else None,
    )
```

**Why `limit + 1`:** Fetching one extra row to determine `has_more` avoids the expensive COUNT query. The current endpoint's separate COUNT will degrade at scale.

**Backward compatibility:** Keep `offset` parameter as deprecated optional. If provided (and no `cursor`), fall back to offset behavior so existing frontend code doesn't break during migration.

---

### 3. Infinite Scroll -- useInfiniteQuery + IntersectionObserver

**Confidence:** HIGH (`@tanstack/react-query` v5.91.2 already installed, IntersectionObserver already used)

**Frontend pattern:**
```typescript
import { useInfiniteQuery } from '@tanstack/react-query'

const {
  data,
  fetchNextPage,
  hasNextPage,
  isFetchingNextPage,
  isLoading,
} = useInfiniteQuery({
  queryKey: ['documents', { type: activeTab, tags: selectedTags, search: debouncedSearch }],
  queryFn: ({ pageParam }) => fetchDocuments({
    limit: 20,
    cursor: pageParam?.cursor,
    cursorId: pageParam?.cursorId,
    documentType: activeTab === 'all' ? undefined : activeTab,
    tags: selectedTags.length ? selectedTags : undefined,
    search: debouncedSearch || undefined,
  }),
  initialPageParam: null as { cursor: string; cursorId: string } | null,
  getNextPageParam: (lastPage) =>
    lastPage.has_more
      ? { cursor: lastPage.next_cursor, cursorId: lastPage.next_cursor_id }
      : undefined,
})

const documents = data?.pages.flatMap(p => p.documents) ?? []
```

**Sentinel element (reuse existing IntersectionObserver pattern from LandingPage.tsx):**
```typescript
const sentinelRef = useRef<HTMLDivElement>(null)

useEffect(() => {
  if (!sentinelRef.current || !hasNextPage) return
  const observer = new IntersectionObserver(
    ([entry]) => { if (entry.isIntersecting && !isFetchingNextPage) fetchNextPage() },
    { rootMargin: '200px' }  // Pre-fetch 200px before visible
  )
  observer.observe(sentinelRef.current)
  return () => observer.disconnect()
}, [hasNextPage, fetchNextPage, isFetchingNextPage])

// At bottom of document list:
// <div ref={sentinelRef} aria-hidden="true" />
```

**Replaces:** The current manual `extraPages` state + `handleLoadMore` button pattern in DocumentLibrary.tsx. `useInfiniteQuery` handles all page accumulation, caching, and refetching automatically.

---

### 4. Tag Input / Autocomplete -- Custom Component with cmdk

**Confidence:** HIGH (cmdk v1.1.1 already in use)

**Why NOT add a tag library (emblor, react-tag-input, etc.):** The project already has `cmdk` powering the command palette. A tag input with autocomplete is a small wrapper (~80 lines) around cmdk's `CommandInput` + `CommandGroup` + `CommandItem`. Adding a library for this is dependency bloat.

**Component approach:**
- Multi-select input built with `cmdk` primitives (same as `components/ui/command.tsx`)
- Popover dropdown shows matching tags from autocomplete endpoint
- Selected tags as removable pills (badge style, Tailwind)
- Keyboard: Enter to select, Backspace to remove last, Escape to close, free-form entry allowed
- Debounced API call for suggestions (reuse existing debounce pattern)

**Autocomplete endpoint:**
```python
@router.get("/tags")
async def list_tags(
    q: str = Query("", max_length=100),
    limit: int = Query(30, ge=1, le=100),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[str]:
    """Distinct tags for autocomplete, optionally filtered by prefix."""
    base = (
        select(func.unnest(Document.tags).label("tag"))
        .where(Document.deleted_at.is_(None))
        .distinct()
        .order_by(text("tag"))
        .limit(limit)
    )
    if q:
        # Use subquery to filter on the unnested value
        from sqlalchemy import literal_column
        subq = base.subquery()
        stmt = select(subq.c.tag).where(subq.c.tag.ilike(f"{q}%"))
    else:
        stmt = base
    result = await db.execute(stmt)
    return [row[0] for row in result]
```

---

### 5. ILIKE Search on Title (V1)

**Confidence:** HIGH (built into SQLAlchemy)

```python
if search:
    # Escape user input for LIKE special chars
    escaped = search.replace("%", "\\%").replace("_", "\\_")
    base = base.where(Document.title.ilike(f"%{escaped}%"))
```

**V1 ILIKE is sufficient.** For document library scale (hundreds to low thousands per tenant), `ILIKE` with leading wildcard is fast enough. No index needed for V1.

**V2 upgrade path if search gets slow:**
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_documents_title_trgm ON documents USING GIN (title gin_trgm_ops);
```

This would accelerate `ILIKE '%term%'` queries via trigram matching. But this is NOT needed for V1 -- premature optimization.

---

### 6. Document Deduplication -- Content Hash

**Confidence:** MEDIUM (approach is sound, but dedup strategy needs validation with real data)

**Add `content_hash` column:**
```python
# In Document model
content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Migration:**
```sql
-- Statement 1: Add column
ALTER TABLE documents ADD COLUMN content_hash TEXT;

-- Statement 2: Unique partial index (per tenant, non-deleted only)
CREATE UNIQUE INDEX idx_documents_dedup
    ON documents (tenant_id, content_hash)
    WHERE content_hash IS NOT NULL AND deleted_at IS NULL;
```

**On document creation:** Compute SHA-256 from rendered HTML content. Check for existing hash before inserting -- if match found, return existing document instead of creating duplicate.

**Fuzzy dedup (similar titles) is a UI concern, not a DB constraint.** Show a "possible duplicate" warning when title similarity is high, but don't block creation.

---

## Supabase / PgBouncer Considerations

| Concern | Mitigation |
|---------|------------|
| DDL migration (add columns + indexes) | Each DDL statement as individual commit per established workaround |
| `unnest()` in tag autocomplete | Pure SQL function, works through PgBouncer transaction mode |
| `ARRAY` operators (`@>`, `&&`) | Standard PostgreSQL, no PgBouncer issues |
| GIN index creation | Regular `CREATE INDEX` (not `CONCURRENTLY`). At current scale, locks for milliseconds. |
| RLS + cursor pagination | RLS adds `WHERE tenant_id = X` automatically. Cursor `WHERE created_at < Y` composes cleanly. |
| `UNIQUE` partial index for dedup | Standard PostgreSQL, works through PgBouncer |

---

## What NOT to Add

| Library/Tech | Why Skip |
|-------------|----------|
| `emblor` / `react-tag-input` / `react-tagsinput` | cmdk already provides typeahead primitives; ~80 lines custom vs new dependency |
| `react-infinite-scroll-component` | `useInfiniteQuery` + `IntersectionObserver` is simpler and already partially in codebase |
| `react-virtuoso` | `@tanstack/react-virtual` already installed; only needed for 500+ visible items (unlikely with 20-item pages) |
| `pg_trgm` extension | ILIKE sufficient for V1 title search; documented as V2 upgrade path |
| Full-text search (`tsvector` on documents) | Overkill for title-only search; context store already has FTS if full-content needed |
| Separate `document_tags` junction table | `TEXT[]` on document row is correct at this scale; junction table only needed for tag metadata (colors, hierarchy) |
| Elasticsearch / Meilisearch | Title ILIKE on hundreds of docs; no external search engine needed |
| `react-hook-form` | Tag input is a single component, not a form; controlled state is fine |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Tags storage | `TEXT[]` column + GIN | Junction table (`document_tags`) | Over-normalized for simple string tags at this scale |
| Tags storage | `TEXT[]` column + GIN | Tags in JSONB `metadata` | Can't GIN-index a nested JSONB array as efficiently; explicit column is clearer |
| Pagination | Cursor (keyset) | Offset (current) | Offset skips/duplicates rows on mutation; bad for infinite scroll |
| Pagination | Cursor (keyset) | Page numbers | Page numbers require COUNT; cursor is cheaper and UX is infinite scroll anyway |
| Infinite scroll | `useInfiniteQuery` + sentinel | Manual page state (current) | Current `extraPages` state is fragile; `useInfiniteQuery` handles caching, refetch, stale data |
| Tag input | Custom with cmdk | emblor library | Dependency for ~80 lines of code; cmdk already in bundle |
| Title search | ILIKE (V1) | pg_trgm GIN | Premature optimization; ILIKE is fine for <5K rows per tenant |
| Dedup | Content hash (SHA-256) | Title similarity matching | Hash catches exact dupes deterministically; fuzzy matching is UI warning, not constraint |

---

## Migration Checklist

Execute in order, each DDL as individual commit:

1. `ALTER TABLE documents ADD COLUMN tags TEXT[] NOT NULL DEFAULT '{}'`
2. `ALTER TABLE documents ADD COLUMN content_hash TEXT`
3. `CREATE INDEX idx_documents_tags ON documents USING GIN (tags)`
4. `CREATE UNIQUE INDEX idx_documents_dedup ON documents (tenant_id, content_hash) WHERE content_hash IS NOT NULL AND deleted_at IS NULL`
5. `alembic stamp <revision>`
6. Backfill script: extract tags from existing `metadata` JSONB (companies, skill names) into `tags` array
7. Backfill script: compute `content_hash` for existing documents

---

## Version Summary

| Component | Current Version | Change Needed |
|-----------|----------------|---------------|
| `@tanstack/react-query` | ^5.91.2 | None -- use `useInfiniteQuery` (already available) |
| `@tanstack/react-virtual` | ^3.13.23 | None -- available if list virtualization needed |
| `cmdk` | ^1.1.1 | None -- use for tag autocomplete component |
| SQLAlchemy | >=2.0 | None -- `ARRAY(Text)`, `.overlap()`, `.contains()` all available |
| asyncpg | >=0.29 | None -- handles array types natively |
| PostgreSQL | 15 (Supabase) | None -- GIN, ARRAY, ILIKE all built-in |
| Alembic | >=1.14 | None -- migration file + SQL Editor execution |

---

## Sources

- **Codebase (verified):** `db/models.py` lines 271, 571, 834, 977, 1202 -- ARRAY(Text) usage across 10+ models
- **Codebase (verified):** `pipeline_service.py:276` -- `.overlap()` for array filtering
- **Codebase (verified):** `leads.py:325` -- `.contains()` for array filtering
- **Codebase (verified):** `entity_normalization.py:84` -- `.op("@>")` for array containment
- **Codebase (verified):** `alembic/versions/028_*`, `040_*` -- GIN index creation patterns
- **Codebase (verified):** `frontend/src/pages/LandingPage.tsx:116` -- IntersectionObserver pattern
- **Codebase (verified):** `frontend/src/features/email/components/ThreadList.tsx` -- `@tanstack/react-virtual` usage
- **Codebase (verified):** `frontend/src/features/navigation/components/CommandPalette.tsx` -- cmdk usage
- **Codebase (verified):** `frontend/src/features/documents/components/DocumentLibrary.tsx` -- current offset pagination to replace
- [Emblor tag input](https://github.com/JaleelB/emblor) -- evaluated and rejected (dependency overhead)
- [shadcn/ui tag input discussion](https://github.com/shadcn-ui/ui/issues/3647) -- no official component; custom build is standard
