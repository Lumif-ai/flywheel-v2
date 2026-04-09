# Domain Pitfalls

**Domain:** Library redesign -- tags, filtering, cursor pagination, dedup-on-save, data cleanup for existing Flywheel V2 documents
**Researched:** 2026-04-08
**Confidence:** HIGH (based on direct codebase analysis of documents API, Document model, 8 skill save paths, frontend DocumentLibrary, 52 Alembic migrations, PgBouncer behavior, and PostgreSQL documentation)

---

## Critical Pitfalls

Mistakes that cause data loss, silent corruption, or require rewrites.

---

### Pitfall 1: Supabase PgBouncer Silently Rolls Back Multi-Statement DDL

**What goes wrong:** The library redesign requires multiple DDL statements: `ALTER TABLE documents ADD COLUMN tags TEXT[]`, `CREATE INDEX ... USING GIN`, `ALTER TABLE documents ADD COLUMN account_id UUID`, `CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL`. Alembic wraps all of these in a single transaction. PgBouncer commits the `alembic_version` UPDATE but silently rolls back the actual DDL. The migration reports success, `alembic current` shows the new revision, but no columns/indexes exist.

**Why it happens:** PgBouncer in transaction pooling mode cannot handle multi-statement DDL transactions. Supabase uses PgBouncer by default on the pooled connection string (port 6543). This is a KNOWN issue in this project -- documented in CLAUDE.md, `feedback_supabase_ddl.md`, and the previous pipeline migration research.

**Consequences:** Code deploys expecting `tags`, `account_id`, and the dedup unique index. Every document save/list call returns 500. Worst case: the dedup index silently doesn't exist, so ON CONFLICT fails with "no unique constraint matching" errors, and duplicate documents accumulate instead of being caught.

**Prevention:**
1. Write the Alembic migration for documentation and downgrade support
2. Apply each DDL statement individually via Supabase SQL Editor or as separate `session.execute() + session.commit()` calls
3. Run `alembic stamp <revision>` after manual application
4. VERIFY every column and index exists before deploying code: `SELECT column_name FROM information_schema.columns WHERE table_name = 'documents'` and `SELECT indexname FROM pg_indexes WHERE tablename = 'documents'`

**Detection:** After migration, run verification queries. If `tags` column is missing but `alembic current` shows the revision, PgBouncer ate the DDL.

**Phase:** Must be addressed in EVERY migration phase. This is not a one-time fix -- every DDL migration in this milestone hits this.

**Confidence:** HIGH -- verified in this project's history, documented in project memory.

---

### Pitfall 2: ON CONFLICT Dedup Index + PgBouncer = Silent Dedup Failure

**What goes wrong:** The dedup strategy relies on a partial unique index:
```sql
CREATE UNIQUE INDEX idx_documents_dedup
ON documents (tenant_id, document_type, title)
WHERE deleted_at IS NULL;
```
If this index doesn't exist (Pitfall 1), `INSERT ... ON CONFLICT ON CONSTRAINT idx_documents_dedup DO UPDATE` throws `there is no unique or exclusion constraint matching the ON CONFLICT specification`. But if you use `ON CONFLICT DO NOTHING` as a fallback, duplicates silently accumulate.

**Why it happens:** The ON CONFLICT clause requires an exact match to an existing unique index/constraint. If the index creation was rolled back by PgBouncer but the Alembic version was stamped, the application code thinks the index exists.

**Consequences:** Either all document saves fail with 500 errors (if ON CONFLICT references missing index), or duplicates silently accumulate (if fallback to DO NOTHING). Both are production-breaking for a library with ~800 existing documents.

**Prevention:**
1. After creating the index via SQL Editor, verify: `SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'documents' AND indexname = 'idx_documents_dedup'`
2. Add a startup health check that verifies the dedup index exists before the API accepts writes
3. In the save_document path, catch `ProgrammingError` for missing index and log a CRITICAL alert rather than silently falling back

**Detection:** Monitor for duplicate documents after deployment. Check `SELECT title, document_type, tenant_id, count(*) FROM documents WHERE deleted_at IS NULL GROUP BY 1,2,3 HAVING count(*) > 1`.

**Phase:** Schema migration phase (before any code changes to the save path).

**Confidence:** HIGH -- ON CONFLICT behavior is well-documented in PostgreSQL docs; PgBouncer interaction is project-verified.

---

### Pitfall 3: Partial Unique Index WHERE Clause Must Match Insert Filter Exactly

**What goes wrong:** The dedup index uses `WHERE deleted_at IS NULL`. For ON CONFLICT to match this index, the INSERT statement must also include the same WHERE condition in its conflict target, OR the inserted row must satisfy the index predicate. If you insert a row where `deleted_at IS NOT NULL` (e.g., re-saving a soft-deleted document), PostgreSQL cannot find a matching arbiter index and throws an error.

**Why it happens:** PostgreSQL's ON CONFLICT resolution requires the inserted row to be covered by the specified arbiter index. A partial index only covers rows matching its WHERE clause. If the new row doesn't match the predicate, the index can't serve as the conflict arbiter.

**Consequences:** Edge case: if someone undeletes a document or the merge-duplicates logic soft-deletes then re-inserts, the ON CONFLICT clause fails. The save path crashes for specific documents that have a deleted_at history.

**Prevention:**
1. Always INSERT with `deleted_at = NULL` (which is the default). Never set deleted_at on insert.
2. For the undelete/merge flow, use a separate UPDATE path, not INSERT ON CONFLICT.
3. Add a code comment above the ON CONFLICT explaining the partial index dependency: `-- Requires idx_documents_dedup WHERE deleted_at IS NULL; row MUST have deleted_at IS NULL`
4. Test: insert a document, soft-delete it, insert same title again -- verify it creates a new row (not conflict with the deleted one).

**Detection:** Integration test that soft-deletes a document and re-saves with the same title should succeed (no conflict with the deleted version).

**Phase:** Save-path implementation phase.

**Confidence:** HIGH -- per PostgreSQL documentation on partial unique indexes.

---

### Pitfall 4: Data Migration Merging 800 Documents Without Losing Provenance

**What goes wrong:** The ~800 existing documents have bad titles (like "Meeting Prep: None" or generic skill names), no tags, no account_id, and duplicates. A cleanup migration that bulk-updates titles, merges duplicates, and backfills tags can:
- Lose the original title (no way to undo if the heuristic was wrong)
- Merge two documents that looked like duplicates but had different content
- Break skill_run_id references if the "winner" of a merge is deleted
- Lock the documents table for extended time on a batch UPDATE

**Why it happens:** Cleanup migrations are write-heavy and heuristic-driven. Title extraction from metadata is imperfect. "Same title + same type + same tenant" doesn't mean "same document" if they were created months apart with different content.

**Consequences:** Users lose access to specific documents. Skill run provenance is broken. If the migration runs in a single transaction and fails partway, PgBouncer may commit some changes and roll back others (see Pitfall 1).

**Prevention:**
1. **Never delete originals.** Soft-delete losers in a merge, keeping all skill_run_id references intact.
2. **Backup before migration:** `CREATE TABLE documents_backup_20260408 AS SELECT * FROM documents`
3. **Batch in small chunks:** Process 50 documents per commit, not all 800 in one transaction.
4. **Add `original_title` column** before cleanup so the original is preserved: `ALTER TABLE documents ADD COLUMN original_title TEXT`
5. **Time-window dedup:** Only merge documents with the same title created within 5 minutes of each other (same skill run), not months apart.
6. **Dry-run first:** Run the dedup query as a SELECT to review candidates before executing: `SELECT title, document_type, count(*), array_agg(id) FROM documents WHERE deleted_at IS NULL GROUP BY 1,2 HAVING count(*) > 1`
7. **Title improvement heuristic:** Extract company/contact from metadata JSONB: `metadata->>'companies'->0` to build better titles. Fall back to existing title if metadata is empty.

**Detection:** After migration, compare `documents_backup` row count vs `documents WHERE deleted_at IS NULL` count. Verify no skill_run_ids were orphaned.

**Phase:** Dedicated data migration phase, AFTER schema changes but BEFORE new save-path code.

**Confidence:** HIGH -- based on examination of the 800 existing documents via the current schema.

---

### Pitfall 5: Account FK on Documents When Account Doesn't Exist

**What goes wrong:** Adding `account_id UUID REFERENCES accounts(id)` to documents requires that every `account_id` value references an existing account. But the MCP `flywheel_save_document` tool currently accepts an `account_id` string from Claude Code, which may be:
- A hallucinated UUID that doesn't exist in the accounts table
- A valid UUID from a different tenant (cross-tenant reference)
- An empty string (current code puts it in metadata, not as a FK)

**Why it happens:** The current save path passes `account_id` through metadata as a string. Moving it to a proper FK column means the database will reject invalid references. Skills running in Claude Code don't validate account existence before calling save_document.

**Consequences:** Document saves fail with `violates foreign key constraint` for any skill that passes a bad account_id. Since 8 skills save documents, this could break all skill output persistence.

**Prevention:**
1. Make `account_id` nullable on the documents table (`account_id UUID REFERENCES accounts(id) ON DELETE SET NULL, nullable=True`)
2. In the save endpoint, **resolve account by name, not by ID**: accept `account_name` string, look up the account, set account_id if found, leave NULL if not.
3. Never trust client-supplied UUIDs for FK references. Always validate: `SELECT id FROM accounts WHERE id = :account_id AND tenant_id = :tenant_id`
4. Add tenant_id check to prevent cross-tenant account references.
5. Update the MCP tool signature to accept `account_name` (string) instead of `account_id` (UUID).

**Detection:** After deploying the FK, monitor for 500 errors on document saves with stack traces containing `ForeignKeyViolationError`.

**Phase:** Schema migration phase + MCP tool update phase (must be coordinated).

**Confidence:** HIGH -- examined current MCP save_document code which passes account_id as string metadata.

---

## Moderate Pitfalls

Mistakes that cause degraded UX, performance issues, or extra rework.

---

### Pitfall 6: Cursor Pagination with Timestamp Ties Causing Skipped/Duplicate Documents

**What goes wrong:** Cursor-based pagination using `created_at` alone will skip or duplicate documents when multiple documents share the same timestamp. With ~800 documents and skill runs that create multiple documents per execution, timestamp ties are common.

**Why it happens:** PostgreSQL's `now()` returns the same value for all statements in a transaction. If a skill run creates 3 documents in one transaction, all have identical `created_at`. A cursor like `WHERE created_at < :cursor_timestamp ORDER BY created_at DESC LIMIT 20` will either skip some of the tied documents or return them again on the next page.

**Prevention:**
1. Use a **compound cursor**: `(created_at, id)` -- the UUID provides a guaranteed tiebreaker.
2. Query: `WHERE (created_at, id) < (:cursor_ts, :cursor_id) ORDER BY created_at DESC, id DESC LIMIT 20`
3. Create a composite index: `CREATE INDEX idx_documents_cursor ON documents (created_at DESC, id DESC) WHERE deleted_at IS NULL`
4. Encode cursor as base64 of `timestamp|uuid` for clean API contracts.
5. Keep backward compatibility: support both `offset` (existing pattern used by ALL other endpoints) and `cursor` parameters during transition.

**Detection:** Test with a batch insert of 5 documents with identical created_at. Paginate with page_size=2. Verify all 5 documents appear across pages with no duplicates.

**Phase:** API pagination phase.

**Confidence:** HIGH -- per PostgreSQL documentation and keyset pagination best practices.

---

### Pitfall 7: PostgreSQL TEXT[] Tags -- NULL vs Empty Array vs Missing Column

**What goes wrong:** A `TEXT[]` column has three distinct states: `NULL`, `'{}'` (empty array), and `'{"tag1","tag2"}'`. Code that checks `tags IS NOT NULL` will pass for empty arrays. Code that checks `array_length(tags, 1) > 0` will return NULL for empty arrays (not 0). GIN indexes on `TEXT[]` handle NULL and empty arrays differently from populated arrays.

**Why it happens:** PostgreSQL arrays have notoriously confusing NULL semantics. `NULL` means "unknown tags," `'{}'` means "explicitly no tags," and these are logically different but commonly conflated.

**Consequences:**
- Filtering by `'meeting-prep' = ANY(tags)` correctly excludes NULL and empty arrays, but `NOT ('meeting-prep' = ANY(tags))` returns FALSE for NULL (not TRUE), so untagged documents vanish from "not this tag" filters.
- `array_length(tags, 1)` returns NULL for empty arrays, breaking count queries.
- Tag concatenation with `||` operator: `NULL || '{"new-tag"}'` returns NULL, losing the new tag.

**Prevention:**
1. **Default to empty array, never NULL:** `tags TEXT[] NOT NULL DEFAULT '{}'::text[]`
2. Backfill existing rows: `UPDATE documents SET tags = '{}' WHERE tags IS NULL`
3. For "not tagged with X" queries, use: `NOT (tags @> ARRAY['X']::text[])` which correctly includes empty arrays.
4. For tag append, use: `array_cat(COALESCE(tags, '{}'), ARRAY['new-tag'])` or better, `array_append(tags, 'new-tag')` since the column is NOT NULL.
5. For tag count, use: `COALESCE(array_length(tags, 1), 0)`

**Detection:** Unit test: create document with no tags, verify `tags = '{}'` not NULL. Test "exclude tag X" filter includes untagged documents.

**Phase:** Schema migration phase (column definition) + API filter phase.

**Confidence:** HIGH -- per PostgreSQL array documentation and direct testing.

---

### Pitfall 8: GIN Index on TEXT[] Not Used for Small Result Sets

**What goes wrong:** You create `CREATE INDEX idx_documents_tags ON documents USING GIN (tags)` and expect tag filtering to be fast. But PostgreSQL's query planner may choose a sequential scan over the GIN index for small tables (~800 rows), making the index useless at current scale but essential at 10K+.

**Why it happens:** GIN index lookups have higher fixed overhead than sequential scans. For tables under ~5000 rows, PostgreSQL correctly determines that a seq scan is faster. The index is "insurance" for future scale, not a current performance need.

**Consequences:** No immediate performance issue -- the pitfall is spending time optimizing queries to use the GIN index at current scale. The real risk is writing queries that can't use the GIN index when scale demands it (e.g., using `tags::text LIKE '%meeting%'` instead of `tags @> ARRAY['meeting']`).

**Prevention:**
1. Create the GIN index now for future-proofing, but don't add `SET enable_seqscan = off` hacks to force its use.
2. Use array operators (`@>`, `&&`, `= ANY`) not text casting for tag queries. These are GIN-compatible.
3. `@>` (contains) for "has this tag": `tags @> ARRAY['meeting-prep']::text[]`
4. `&&` (overlaps) for "has any of these tags": `tags && ARRAY['meeting-prep', 'company-intel']::text[]`
5. Do NOT use `'meeting-prep' IN (SELECT unnest(tags))` -- this can't use the GIN index.

**Detection:** `EXPLAIN ANALYZE` on tag filter queries at 800 rows (expect seq scan -- that's fine). Re-check at 5000+ rows.

**Phase:** API filter implementation phase.

**Confidence:** HIGH -- per PostgreSQL GIN index documentation and query planner behavior.

---

### Pitfall 9: Tag Validation -- Case Sensitivity and Namespace Pollution

**What goes wrong:** Without validation, tags accumulate as `"Meeting Prep"`, `"meeting-prep"`, `"meeting_prep"`, `"MEETING PREP"` -- all treated as different values. The tag filter dropdown shows 4 entries for what the user considers one tag. Over time, the tag namespace becomes unusable.

**Why it happens:** Different skills generate tags with different casing conventions. MCP tool users type free-form text. No enforcement layer exists between tag input and database storage.

**Consequences:** Tag cloud/filter becomes polluted with near-duplicates. Users can't reliably filter because they don't know which variant was used. Search by tag misses documents with variant spellings.

**Prevention:**
1. **Normalize on write:** Lowercase, trim, replace spaces/underscores with hyphens: `re.sub(r'[\s_]+', '-', tag.strip().lower())`
2. **Validate format:** `^[a-z0-9][a-z0-9\-]{0,48}[a-z0-9]$` -- lowercase alphanumeric with hyphens, 2-50 chars.
3. **Reject duplicates within array:** Use `SELECT DISTINCT unnest(...)` or Python `list(set(tags))` before saving.
4. **Consider a tags lookup table** for future: `CREATE TABLE document_tags (id SERIAL, name TEXT UNIQUE, display_name TEXT)`. But for V1, inline TEXT[] with validation is sufficient.
5. **XSS prevention:** Tags will appear in the UI. Sanitize: no HTML, no script content. The regex above handles this implicitly.
6. **Max tags per document:** Cap at 20 to prevent abuse: `CHECK (array_length(tags, 1) <= 20 OR tags = '{}')`

**Detection:** After 1 month of usage, run: `SELECT DISTINCT unnest(tags) FROM documents ORDER BY 1` and check for near-duplicates.

**Phase:** Save-path implementation phase (normalize before write).

**Confidence:** HIGH -- common pattern, well-understood.

---

### Pitfall 10: Infinite Scroll Memory Leak with Growing DOM

**What goes wrong:** The current DocumentLibrary uses a "Load more" button that appends to `extraPages` state. Each load adds 50 more DocumentRow/DocumentGridCard components to the DOM. At 800+ documents, the browser holds 800 rendered components in memory, causing slow scrolling, high memory usage, and eventual tab crashes on mobile.

**Why it happens:** The current implementation (line 74 in DocumentLibrary.tsx: `const [extraPages, setExtraPages] = useState<DocumentListItem[]>([])`) accumulates all loaded documents in React state and renders every one. No virtualization is used.

**Consequences:** At 100 documents, negligible. At 500+, noticeable jank on scroll. At 1000+, mobile Safari may kill the tab. Users with large libraries get a degraded experience.

**Prevention:**
1. **Use TanStack Query's `useInfiniteQuery`** instead of manual state accumulation. It handles page caching, refetching stale pages, and garbage collection.
2. **Add windowed rendering** with `@tanstack/react-virtual` or `react-window` if document count exceeds 200.
3. **Cap initial render:** Only render the visible viewport + 2 pages of buffer. Virtualize the rest.
4. **For V1, "Load more" with 50-item pages is fine for 800 docs** -- but plan the virtualization escape hatch for when document count exceeds 2000.
5. **Scroll position restoration:** TanStack Query handles this automatically if query cache isn't garbage collected. But navigating to a document detail and back requires the scroll position to be preserved. Current implementation loses it.

**Detection:** Chrome DevTools Performance tab: measure memory growth after loading all pages. If it exceeds 50MB for document list data, virtualization is needed.

**Phase:** Frontend pagination phase. V1 can keep "Load more" but must switch from manual state to useInfiniteQuery.

**Confidence:** MEDIUM -- exact memory threshold depends on component complexity and device.

---

### Pitfall 11: Breaking 8 Skills' Save Path During Migration

**What goes wrong:** The library redesign changes the document save contract: new required fields (tags), account resolution (name-based instead of ID-based), and dedup behavior (ON CONFLICT). All 8 skills that call `flywheel_save_document` via MCP must be updated, but they run in external Claude Code sessions that may have cached the old API.

**Skills affected:**
- `call-intelligence`
- `gtm-company-fit-analyzer`
- `gtm-outbound-messenger`
- `gtm-pipeline`
- `gtm-web-scraper-extractor`
- `meeting-prep`
- `meeting-processor`
- `outreach-drafter`

**Why it happens:** The MCP tool `flywheel_save_document` is the single write path for all skills. Changing its signature or behavior affects every skill simultaneously. Skills don't pin to API versions.

**Consequences:** If the backend save endpoint changes its contract (e.g., requires tags, rejects account_id in metadata), all running skill sessions break until Claude Code restarts and picks up the new MCP tool definition.

**Prevention:**
1. **Make new fields optional with defaults:** `tags` defaults to `[]`, `account_name` defaults to `""`. The old save call signature must still work.
2. **Don't remove the `account_id` metadata path.** Add `account_name` as a NEW parameter alongside. Deprecate `account_id` in metadata after all skills are updated.
3. **Phase the rollout:** Deploy backend changes with backward compatibility first. Then update MCP tool definition. Then update skill prompts to use new parameters.
4. **Test old call signature** against new endpoint: `flywheel_save_document(title="test", content="test", skill_name="meeting-prep")` must still work with zero new parameters.

**Detection:** After deploying the new save endpoint, run each skill once and verify the document appears in the library with correct tags and account linkage.

**Phase:** Save-path implementation must be backward-compatible. Skill updates are a separate follow-up phase.

**Confidence:** HIGH -- examined all 8 skill SKILL.md files and the MCP server.py save_document definition.

---

### Pitfall 12: Offset-to-Cursor Migration Breaking Frontend Pagination

**What goes wrong:** The entire codebase uses offset-based pagination (`offset` + `limit` + `total` + `has_more`). Switching the documents endpoint to cursor-based pagination changes the API contract. The frontend `fetchDocuments` function, the DocumentLibrary component, and the "Load more" button all assume offset-based semantics.

**Current pattern (used in 8+ endpoints):**
```typescript
{ items: [...], total: 42, offset: 0, limit: 20, has_more: true }
```

**Why it happens:** Cursor pagination returns a different response shape: `{ items: [...], next_cursor: "...", has_more: true }` -- no `total`, no `offset`. The frontend "Showing X of Y documents" counter requires `total`, which cursor pagination can't efficiently provide.

**Consequences:** The "42 documents" count badge, the "Showing 20 of 42" text, and the date-group-based rendering all break if `total` is removed.

**Prevention:**
1. **Hybrid approach:** Keep `total` via a separate `COUNT(*)` query (cheap at 800 rows, fine up to 50K). Return cursor AND total.
2. **Response shape:** `{ items: [...], total: 42, next_cursor: "abc123", has_more: true }` -- compatible with existing frontend patterns.
3. **Keep offset support** during transition. Accept both `offset` and `cursor` parameters. If cursor is provided, use keyset. If offset is provided, use offset. Default to cursor for new code.
4. **Don't change the response shape of other endpoints.** Only documents gets cursor pagination. Keep the rest on offset.

**Detection:** Frontend build should type-check the response. If `total` is missing, TypeScript catches it if the interface is properly defined.

**Phase:** API + frontend pagination phase.

**Confidence:** HIGH -- examined all existing pagination endpoints in the codebase.

---

## Minor Pitfalls

Issues that cause small inconveniences or tech debt.

---

### Pitfall 13: RLS Policy Must Be Updated for New Columns

**What goes wrong:** The existing RLS policy `documents_tenant_isolation` uses `USING (tenant_id = current_setting('app.tenant_id', true)::uuid)`. This policy covers SELECT/UPDATE/DELETE but not INSERT. If a new INSERT policy is added that checks `account_id` references, it must also validate tenant_id on the account.

**Prevention:** After adding `account_id` column, verify the existing RLS policy still works. No changes needed to the policy itself (it only checks tenant_id), but the application code must validate that the account's tenant_id matches the document's tenant_id.

**Phase:** Schema migration phase.

**Confidence:** HIGH.

---

### Pitfall 14: Frontend Search is Client-Side Only

**What goes wrong:** The current DocumentLibrary (line 125-134) filters by title, companies, and contacts in JavaScript after fetching all documents. With tags and more filter dimensions, client-side filtering becomes unreliable because it only filters the loaded pages, not the full dataset.

**Prevention:**
1. For V1 with 800 documents, client-side filtering is acceptable if all documents are loaded.
2. For V2, move filtering to the server: `GET /documents/?tags=meeting-prep&search=acme&account_id=xxx`
3. Server-side tag filtering uses GIN index: `WHERE tags @> ARRAY['meeting-prep']::text[]`
4. Plan the API to accept filter parameters from day one, even if V1 frontend doesn't use all of them.

**Phase:** API design phase. Define the filter parameters in the API even if the frontend starts with client-side filtering.

**Confidence:** MEDIUM.

---

### Pitfall 15: Scroll Position Lost on Navigate-Back

**What goes wrong:** User scrolls to document #40 in the library, clicks to view it, clicks browser back. The library re-renders from the top because the scroll position and loaded pages are not preserved.

**Prevention:**
1. Use TanStack Query's `useInfiniteQuery` with `staleTime: 5 * 60 * 1000` -- the cached pages persist across navigations.
2. The browser's native scroll restoration works IF the DOM height is restored before the scroll position is applied. This requires the cached data to be available synchronously (which TanStack Query provides).
3. Do NOT use `window.scrollTo(0, 0)` on the library page mount.

**Phase:** Frontend pagination phase.

**Confidence:** MEDIUM -- depends on TanStack Query cache configuration and React Router behavior.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| Schema migration (tags, account_id, dedup index) | PgBouncer rolls back DDL (Pitfall 1) | Apply via SQL Editor, stamp alembic, verify every column/index |
| Schema migration (tags column) | NULL vs empty array confusion (Pitfall 7) | NOT NULL DEFAULT '{}', backfill existing rows |
| Data cleanup migration | Losing original titles, breaking skill_run refs (Pitfall 4) | Backup table, original_title column, time-window dedup, dry-run |
| Save-path implementation (dedup) | Partial index mismatch (Pitfall 3) | Always insert with deleted_at NULL, test soft-delete + re-save |
| Save-path implementation (account FK) | FK violation from bad account_id (Pitfall 5) | Resolve by name not ID, nullable FK, validate tenant match |
| Save-path implementation (tags) | Case pollution (Pitfall 9) | Normalize on write, validate format regex |
| Save-path implementation (backward compat) | Breaking 8 skills (Pitfall 11) | All new params optional with defaults, don't remove old params |
| API pagination | Timestamp ties skip documents (Pitfall 6) | Compound cursor (created_at, id), composite index |
| API pagination | Breaking frontend contract (Pitfall 12) | Hybrid response with total + cursor, keep offset support |
| Frontend infinite scroll | Memory growth (Pitfall 10) | useInfiniteQuery, plan virtualization escape hatch |
| Frontend navigation | Scroll position lost (Pitfall 15) | TanStack Query cache + staleTime |
| All API filter phases | GIN index misuse (Pitfall 8) | Use array operators (@>, &&), not text casting |

---

## Testing Strategies

### Migration Safety Tests (run in staging before production)
1. Create backup table, run migration, compare row counts
2. Verify all columns exist: `\d documents` in psql
3. Verify all indexes exist: `SELECT indexname FROM pg_indexes WHERE tablename = 'documents'`
4. Verify dedup index predicate: `SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_documents_dedup'`
5. Run old save_document call against new endpoint -- must succeed with no new params
6. Insert duplicate title -- must trigger ON CONFLICT, not create new row

### Tag System Tests
1. Insert with NULL tags -- should be rejected (NOT NULL constraint)
2. Insert with empty array -- should succeed
3. Insert with mixed case tags -- should be normalized to lowercase-hyphenated
4. Filter by tag using `@>` operator -- should return correct documents
5. "Not tagged with X" filter -- should include untagged documents
6. Insert document with 21 tags -- should be rejected (max 20 check)

### Cursor Pagination Tests
1. Insert 5 documents with identical created_at (batch insert)
2. Paginate with page_size=2 -- verify all 5 appear, no duplicates
3. Insert a new document between page fetches -- verify it doesn't appear on current page
4. Decode cursor -- verify it contains both timestamp and UUID
5. Pass invalid cursor -- verify 400 error, not 500

### Save-Path Backward Compatibility Tests
1. Call save_document with old signature (title, content, skill_name only) -- must succeed
2. Call save_document with account_id in metadata (old pattern) -- must succeed
3. Call save_document with account_name (new pattern) -- must resolve to account_id
4. Call save_document with nonexistent account_name -- must succeed with account_id = NULL
5. Call save_document with tags -- must normalize and save
6. Call save_document without tags -- must default to empty array

---

## Sources

- [PostgreSQL GIN Index Documentation](https://www.postgresql.org/docs/current/gin.html) -- NULL handling, empty array behavior
- [PostgreSQL INSERT ON CONFLICT Documentation](https://www.postgresql.org/docs/current/sql-insert.html) -- partial index arbiter requirements
- [Supabase PgBouncer Silent Rollback Issue](https://github.com/supabase/supabase/issues/43753) -- serializable transactions silently discarded
- [Keyset Pagination Best Practices](https://blog.sequinstream.com/keyset-cursors-not-offsets-for-postgres-pagination/) -- compound cursor with tiebreaker
- [Cursor Pagination Guide](https://bun.uptrace.dev/guide/cursor-pagination.html) -- timestamp tie handling
- [TanStack Query Infinite Queries](https://tanstack.com/query/latest/docs/framework/react/guides/infinite-queries) -- stale page refetching, scroll restoration
- [TanStack Query Scroll Restoration](https://tanstack.com/query/v4/docs/framework/react/guides/scroll-restoration) -- automatic with cache
- [PostgreSQL GIN Index Analysis (pganalyze)](https://pganalyze.com/blog/gin-index) -- when GIN is/isn't used by planner
- [PostgreSQL Duplicate Removal Techniques (CYBERTEC)](https://www.cybertec-postgresql.com/en/removing-duplicate-rows-in-postgresql/) -- safe dedup strategies
- Project-internal: `backend/src/flywheel/api/documents.py`, `cli/flywheel_mcp/server.py`, `backend/src/flywheel/db/models.py`, `backend/alembic/versions/019_documents.py`, `.planning/CONCEPT-BRIEF-documents-architecture.md`
