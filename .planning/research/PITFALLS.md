# Domain Pitfalls: CRM Redesign — Multi-Type Relationships, AI Synthesis, Configurable Grid

**Domain:** Brownfield CRM migration — adding multi-type relationships, AI synthesis caching,
configurable data grid, and entity-level switching (person vs company) to existing system
**Researched:** 2026-03-27
**Confidence:** HIGH for migration/backend pitfalls (direct codebase inspection + official docs).
MEDIUM for frontend grid pitfalls (official TanStack docs + community patterns). MEDIUM for AI
cost/caching (multiple credible sources, no single authoritative reference).

---

## Context: What Already Exists

The existing system has:
- `accounts` table with a `status TEXT` column (values: `prospect`, `engaged`, etc.)
- 206 seeded accounts, all with `status = 'prospect'` or `status = 'engaged'`
- `GET /pipeline/` filters on `Account.status`
- `POST /accounts/{id}/graduate` sets `status = 'engaged'`
- Frontend `PipelineItem` TypeScript type has `status: string` field
- Frontend `pipeline/api.ts` calls `GET /pipeline/` and `POST /accounts/{id}/graduate`
- `GET /accounts/?status=...` filters on the `status` column directly

The migration renames `status` → `pipeline_stage`, adds `relationship_type text[]`,
`relationship_status text`, `entity_level text`, `ai_summary text`, and `ai_summary_updated_at`.

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or major regressions.

---

### Pitfall 1: Atomic Rename — The Gap Between Migration and Code Deploy

**What goes wrong:**
`status` is renamed to `pipeline_stage` in Alembic. The migration runs. For the window
between migration completion and code deploy, the existing API code still references
`Account.status`. SQLAlchemy raises `AttributeError: Account has no attribute 'status'` on
every request. The entire `/accounts/`, `/pipeline/`, and `/graduate` API surface goes 500.
With 206 accounts in the DB, this affects every user immediately.

**Why it happens:**
In Python SQLAlchemy, the ORM model attribute name and the DB column name must stay in sync.
When you rename a column in the DB (via `op.alter_column`) but haven't updated the ORM model or
the API code, every ORM reference to `Account.status` compiles to SQL referencing a column that
no longer exists. PostgreSQL returns `column "status" does not exist`.

Additionally, the existing `PATCH /accounts/{id}` endpoint accepts `UpdateAccountRequest` with
a `status` field. After the migration, this field silently does nothing (the column is gone) —
no error, just silent data loss if not updated.

**Consequences:**
- Total API outage for all CRM endpoints during the deploy gap
- Silent silent data loss if any client writes to `status` field after rename
- Pipeline frontend breaks (reads `item.status` from API response)

**Prevention:**
Use a two-phase migration:
1. Phase A (additive): Add `pipeline_stage`, `relationship_type`, `relationship_status`,
   `entity_level` as new columns. Copy data: `UPDATE accounts SET pipeline_stage = status`.
   Deploy code that writes to BOTH `status` AND `pipeline_stage`, reads from `pipeline_stage`.
2. Phase B (cleanup): After Phase A is stable for ≥1 deploy cycle, drop `status` column.
   Remove dual-write code. Remove `status` field from all Pydantic models.

Never do a single-phase rename in a brownfield system with live traffic.

**Detection:**
- Any Alembic migration that calls `op.alter_column(..., new_column_name='...')` without a
  matching same-commit ORM model update.
- SQLAlchemy errors containing `column "status" does not exist` in staging logs.
- `grep -r "Account.status" backend/src/` should return zero results after Phase A deploy.

**Phase to address:** Data Model phase (first phase of milestone). Phase A migration must be
deployed and verified before any relationship API code is written. Phase B is a cleanup task
in a later phase or a follow-up commit.

---

### Pitfall 2: Array Column Filter Without GIN Index — Silent Full Table Scan

**What goes wrong:**
The new `relationship_type text[]` column is added. The relationships API filters with
`WHERE 'advisor' = ANY(relationship_type)`. PostgreSQL executes this correctly but performs a
full sequential scan on the `accounts` table for every request. At 206 rows this is imperceptible.
At 2,000+ rows (after sales and seeding cycles), list page latency crosses 300ms. By 5,000 rows
it is visibly slow. The query never shows up in slow-query logs because it is measured in
milliseconds per row, not absolute time — until it isn't.

**Why it happens:**
PostgreSQL's standard B-tree index does not support the `ANY()` operator on arrays. The GIN
(Generalized Inverted Index) index is required. Without it, every relationship type filter
is a full table scan. This is a well-documented PostgreSQL behavior that developers miss because
the query "works" without the index — it just doesn't scale.

**Consequences:**
- Relationship list page degrades progressively as account count grows
- Signal computation (which queries across all accounts by type) hits the same problem
- Performance cliff is invisible in dev/staging with small datasets

**Prevention:**
Add the GIN index in the same Alembic migration that creates `relationship_type`:
```sql
CREATE INDEX idx_account_relationship_type
  ON accounts USING GIN (relationship_type);
```

In Alembic:
```python
op.create_index(
    'idx_account_relationship_type',
    'accounts',
    ['relationship_type'],
    postgresql_using='gin'
)
```

Also index `(tenant_id, relationship_type)` for the most common query pattern
(all queries are scoped by tenant first).

Note on GIN index cost: GIN indexes are larger than the table itself and updates are
more expensive than B-tree (`UPDATE` to an array-indexed column is effectively a DELETE
+ INSERT in the index). For 200-2000 accounts with infrequent type changes, this is
completely acceptable. Flag for reconsideration at 100K+ rows.

**Detection:**
- `EXPLAIN ANALYZE SELECT * FROM accounts WHERE 'advisor' = ANY(relationship_type)` shows
  `Seq Scan` instead of `Bitmap Index Scan`.
- Missing `postgresql_using='gin'` in the migration that adds `relationship_type`.

**Phase to address:** Data Model phase. The GIN index must ship in the same migration as
the column. Do not add it as a "follow-up optimization."

---

### Pitfall 3: Account Appears in Both Pipeline AND Relationship Surface Simultaneously

**What goes wrong:**
The pipeline query filters on `pipeline_stage IN ('prospect', 'sent', 'awaiting')`. The
relationships query filters on `relationship_type`. After graduation, an account has
`relationship_type = ['customer']` AND `pipeline_stage = 'engaged'`. Both queries match it.
The account appears in the Pipeline grid AND the Customers list. A founder graduates a company,
navigates to Customers, sees it there — then goes back to Pipeline and finds it still listed.
They graduate it again. The graduation endpoint returns 409 (already has this type), but the
frontend shows no clear explanation.

**Why it happens:**
The partition between Pipeline and Relationship surfaces is defined by business logic in the
API query, not enforced by the data model. If the query predicates are not precisely defined
and enforced consistently in BOTH the pipeline and relationships endpoints, accounts leak across
surfaces.

**Consequences:**
- Data integrity confusion — the same account appears in two places
- Double-graduation attempts cause confusing 409 errors
- React Query caches both surfaces independently; after graduation one cache is stale

**Prevention:**
Define the partition predicate once and use it in both endpoints:
- **Pipeline:** accounts where `relationship_type = '{prospect}'` (exactly, no other types)
  AND `pipeline_stage NOT IN ('engaged')`, OR `relationship_type @> '{prospect}'` AND
  no other type AND `pipeline_stage` is pre-engagement.
- **Relationships:** accounts where `relationship_type && ARRAY['customer','advisor','investor']`
  OR (`relationship_type = '{prospect}'` AND `pipeline_stage = 'engaged'`).

The cleanest implementation: add a `graduated_at timestamp` column. When `graduated_at IS NOT
NULL`, the account is a relationship. Pipeline filters `WHERE graduated_at IS NULL`.

After graduation mutation, React Query must invalidate BOTH `['pipeline']` and `['relationships']`
query keys in the same `onSuccess` callback.

**Detection:**
- Test: graduate an account; assert it no longer appears in `GET /pipeline/`; assert it does
  appear in `GET /relationships/?type=customer`.
- Frontend: after graduation modal confirm, check that `usePipeline` and `useRelationships`
  both re-fetch.

**Phase to address:** Backend API phase (relationships endpoint). The Pipeline endpoint must
also be updated in the same phase to filter graduated accounts out.

---

### Pitfall 4: Person vs Company Entity Confusion — The Self-Contact Trap

**What goes wrong:**
An advisor is created as a person-level account (`entity_level = 'person'`). The spec says
"a single AccountContact exists where the contact IS the relationship (self-contact pattern)."
In practice, a developer creates the AccountContact for the advisor but uses the advisor's
own name/email. Later, the People tab queries contacts for this account and shows one card.
Another developer adds the graduation flow: when graduating a company as "Advisor", the UI
asks "Who is the advisor?" and creates a second AccountContact with the same person's details.
Now there are two identical contacts for the same person-level account, and the dedup logic
doesn't exist.

A related failure: a prospect has a contact named "Laurie Chen" (CFO at Howden). Laurie
becomes an advisor. The team creates a new person-level account for "Laurie Chen (Advisor)".
Now Laurie appears in two places — as a contact under Howden (company) and as a standalone
advisor account. In v2.1 these are intentionally not linked. But if the graduation flow
incorrectly creates a NEW account instead of a NEW contact entry on the same account, the
person-level logic is broken.

**Why it happens:**
The `entity_level` column is a convention, not a database constraint. There is no FK linking
a person-level account to the contact who IS that account. The self-contact pattern is
implicit — it relies on the application layer to maintain the invariant.

**Consequences:**
- Duplicate contacts for the same person-level account
- People tab rendering shows 2 identical cards (confusing UX)
- AI synthesis pulls duplicate context and double-counts interactions
- The advisor/investor graduation flow creates a dangling person-level account with no self-contact

**Prevention:**
- Add a `primary_contact_id UUID FK -> account_contacts.id` nullable column to `accounts`.
  For person-level accounts, this FK points to the self-contact. This makes the relationship
  explicit and queryable.
- In the graduation flow: when graduating as advisor/investor, create the person-level
  `AccountContact` first, then set `accounts.primary_contact_id` to that contact's ID.
- Add a uniqueness constraint or application-layer guard: person-level accounts may not have
  more than one `AccountContact` of type `self`.
- Test: graduate a company as Advisor → verify exactly 1 contact created → verify
  `primary_contact_id` is set on the account.

**Detection:**
- `SELECT account_id, COUNT(*) FROM account_contacts GROUP BY account_id HAVING COUNT(*) > 1`
  on person-level accounts (should always be 1).
- Missing `primary_contact_id` FK on `accounts` table.

**Phase to address:** Data Model phase (schema) + Graduation API phase (enforcement).
The `primary_contact_id` column should be added in the schema migration. The graduation
endpoint must create the self-contact atomically.

---

### Pitfall 5: AI Synthesis Cost Runaway — LLM Called on Cache Miss, Not on Request

**What goes wrong:**
The detail page loads. `ai_summary` is NULL (account has never been synthesized). The API
automatically calls the LLM to generate a summary and blocks the response until generation
completes (5-15 seconds). The user sees a spinner. Meanwhile, 8 other detail pages load —
same behavior. 8 LLM calls in parallel, each with full account context (10-20KB of context
per call). The Anthropic bill for that hour is $12. Multiplied by daily usage, the monthly
AI synthesis bill exceeds the product's ARR.

A more subtle variant: the synthesis endpoint has no rate limiting. A bug in the frontend
calls `POST /relationships/{id}/synthesize` in a `useEffect` with a dependency that fires on
every render. Each account detail load triggers 3-5 synthesis calls before the user even
reads the page.

**Why it happens:**
"Cached AI synthesis" sounds solved at architecture time but implementation defaults to
"generate if null." The cache invalidation logic is undefined. The spec says "regenerated on
new data arrival" — but no one defines what "new data arrival" means as a trigger. Without
explicit triggers, the path of least resistance is to always regenerate.

**Consequences:**
- Unbounded LLM cost correlated with page loads (not user value)
- Detail page latency of 5-15 seconds for first-time loads (cold cache = slow page)
- Synthesis rate limiter (1 per account per 5 min) is the only guard, but frontend bugs
  bypass it via multiple parallel calls

**Prevention:**
- `ai_summary` being NULL should return NULL, not trigger generation. The page renders with
  a "Generate summary" CTA.
- Synthesis is ALWAYS explicit: user clicks a button OR a background job runs after
  new data arrives. Never auto-triggered on page load.
- Background trigger: after `POST /relationships/{id}/notes` or `POST /relationships/{id}/files`
  or graduation, enqueue a synthesis job. Do not block the response.
- The `/synthesize` endpoint must be rate-limited at the DB level: store `synthesis_requested_at`,
  return 429 if within 5 minutes of last request (not just last completion).
- Frontend: call synthesis only from an explicit user action (button click), never from
  `useEffect` or query lifecycle hooks.
- Token budget guard: count context tokens before LLM call. If context is under a minimum
  threshold (< 3 meaningful entries), return a template string without an LLM call.

**Detection:**
- LLM call count per hour exceeds (number of active users × 2). Any higher indicates
  automated triggering.
- Any `useEffect` or `useQuery` in frontend code that calls `/synthesize` without a user
  interaction event as its trigger.
- Synthesis endpoint logs showing multiple calls per account within seconds.

**Phase to address:** AI Synthesis phase. Rate limiting and explicit-trigger-only must be
designed before the endpoint is built, not added afterward.

---

## Moderate Pitfalls

Mistakes that cause rework or significant UX degradation without data loss.

---

### Pitfall 6: Signal Computation on Every Request — Scan-on-Read Anti-Pattern

**What goes wrong:**
`GET /api/v1/signals/` is called on app mount and polled every 60 seconds. Each call computes
signals by scanning `outreach_activities` for overdue follow-ups, `context_entries` for stale
relationships, and `accounts` for next_action_due dates. At 206 accounts with ~1 outreach
activity each, this is ~3 table scans per poll cycle. At 1,000 accounts across multiple users,
the signal endpoint becomes the most expensive API call in the system, running every 60 seconds
per connected user.

**Why it happens:**
Signal computation seems simple when the data is small. The temptation is to compute signals
in real-time as a query so they're always fresh. The problem is that "fresh every 60 seconds"
does not require "computed on every request" — these are different things.

**Prevention:**
- For v2.1 at 206 accounts: accept real-time computation. Add `EXPLAIN ANALYZE` to the
  signal query before shipping to verify it uses existing indexes.
- Add a defensive cap: `LIMIT 50` on signal results. Never scan unboundedly.
- Ensure `idx_account_next_action` partial index (already exists from migration 027) is
  used by the query.
- Design the signal count response as a separate lightweight query (just counts, no full
  objects) for the sidebar badges. The full signal list is only fetched when the user opens
  a signal drawer.
- Document the scale threshold: at >500 accounts, move signal computation to a background
  job that writes to a `signals` table, polled by the API. Do not wait until you hit the
  wall to plan the migration.

**Detection:**
- Signal endpoint p95 latency exceeds 200ms with < 1000 accounts.
- `EXPLAIN ANALYZE` shows sequential scans on `outreach_activities` or `accounts` without
  index usage during signal computation.

**Phase to address:** Backend API phase (signals endpoint). Add EXPLAIN verification before
declaring the endpoint done.

---

### Pitfall 7: React Query Key Collision — Pipeline and Relationships Share Stale Cache

**What goes wrong:**
The graduation mutation completes. The success handler calls
`queryClient.invalidateQueries(['pipeline'])`. The Relationships list page is open in another
tab. The `['relationships', 'advisor']` query key is NOT invalidated. The Relationships page
still shows 0 advisors (the just-graduated account is not there yet). The user thinks
graduation failed. They try again — the second call hits the graduation endpoint with the
same type, gets 409, and the frontend shows an unhelpful error.

A related variant: the existing `useAccounts` hook in `features/accounts/` uses query key
`['accounts']`. The new relationships endpoint is `['relationships']`. These are separate caches.
If any legacy code path writes to an account via the old `/accounts/PATCH` endpoint, the
`['relationships']` cache is not invalidated, and the relationship detail shows stale data.

**Why it happens:**
React Query's cache invalidation requires exact key matching by default. When query keys
evolve across a brownfield migration (old `['accounts']` plus new `['relationships']` plus
`['pipeline']`), no single mutation knows to invalidate all affected caches.

**Prevention:**
- Define a query key factory in a single file (`queryKeys.ts`):
  ```typescript
  export const queryKeys = {
    pipeline: () => ['pipeline'],
    relationships: (type?: string) => ['relationships', type].filter(Boolean),
    relationshipDetail: (id: string) => ['relationships', 'detail', id],
    signals: () => ['signals'],
  }
  ```
- Graduation mutation invalidates all three: `pipeline`, `relationships`, `signals`.
- Use `queryClient.invalidateQueries({ queryKey: ['relationships'], exact: false })` to
  invalidate ALL relationship queries regardless of type parameter.
- After any account mutation (PATCH, graduation, note-add), run:
  `['pipeline', 'relationships', 'signals'].forEach(key => queryClient.invalidateQueries(key))`
- Remove or redirect the old `useAccounts` hook so it does not exist in parallel with
  `useRelationships`.

**Detection:**
- After graduation, manually check: does the item disappear from Pipeline list? Does it
  appear in the target Relationship list? Both must be true within the same 200ms window.
- Search frontend code for any component that reads `queryClient.getQueryData(['accounts'])`
  — these are stale cache reads that bypass the new key structure.

**Phase to address:** Frontend Pipeline Grid phase (graduation flow). The query key factory
must be established before any mutation hooks are written.

---

### Pitfall 8: Multi-Type Display — Account Appears in Two Sidebar Sections, UI Looks Broken

**What goes wrong:**
An account has `relationship_type = ['advisor', 'investor']`. It correctly appears in both the
Advisors list and the Investors list. The user opens Advisors, clicks the account, sees the
detail page. The detail page back-link shows "← Advisors." The user then opens Investors,
clicks the same account — same detail page, but the back-link still says "← Advisors" (cached
from the previous navigation). The tab configuration shows advisor-specific tabs, not investor-
specific tabs. The user thinks the investor view is broken.

**Why it happens:**
The detail page is shared across all relationship types. When it receives an account with
`relationship_type = ['advisor', 'investor']`, it must know WHICH type context the user
arrived from to render the correct tabs and back-link. Without navigation state tracking,
the detail page either picks one type arbitrarily or shows all tabs from all types mixed
together.

**Prevention:**
- Pass `fromType` as a URL query parameter: `/relationships/{id}?from=investor`
- The detail page reads `fromType` from the URL to:
  1. Render the back-link as "← Investors"
  2. Show the tab set for investor context first
  3. Still show type badges indicating all types (advisor, investor both badged)
- If `fromType` is absent (e.g., direct link or signal navigation), default to the first
  type in `relationship_type` array.
- On graduation modal confirm, the navigation `push` must include `?from={type}`.

**Detection:**
- Create a test account with `relationship_type = ['advisor', 'investor']`.
- Navigate to it from Advisors — verify back-link says "← Advisors", tabs show advisor config.
- Navigate to it from Investors — verify back-link says "← Investors", tabs show investor config.

**Phase to address:** Frontend Relationship Surfaces phase (detail page). The `fromType`
routing pattern must be designed before the detail page is built.

---

### Pitfall 9: Configurable Grid Column State Not Persisted — Lost on Navigation

**What goes wrong:**
The user opens Pipeline, adds the "Industry" column, resizes the "Company" column to 250px,
reorders "Fit Tier" to the third position. They click a row to open the preview card, close it,
and navigate to Briefing. They come back to Pipeline. All column customizations are gone.
The grid is back to its 8-column default. The user configures it again. This happens every
session. The "configurable grid" feature feels like a toy, not a tool.

**Why it happens:**
Column state (visible columns, order, widths) is stored in React local state. React state is
destroyed on component unmount. Pipeline unmounts on navigation. Even if state is lifted to
Zustand or a React context, the default Vite/React setup does not persist across page refreshes.

**Prevention:**
- Store column state in `localStorage` under a key like `flywheel:pipeline:columns`.
- Shape: `{ visible: string[], widths: Record<string, number>, order: string[] }`.
- Load from localStorage on grid mount as initial state.
- Debounce writes to localStorage (don't write on every pixel of column drag).
- Provide a "Reset to defaults" button that clears the localStorage key and resets state.
- Do NOT persist column state to the backend for v2.1 — localStorage per browser is
  acceptable for a single-user founder tool.

**Detection:**
- Configure columns; navigate away and back; verify configuration is preserved.
- Hard-refresh the page; verify configuration is preserved (requires localStorage, not just Zustand).

**Phase to address:** Frontend Pipeline Grid phase. localStorage persistence must be
built into the initial grid implementation, not added later.

---

### Pitfall 10: Drag-and-Drop Column Reorder Conflicts with Column Resize Handles

**What goes wrong:**
The grid has both column resize (drag on column edge) and column reorder (drag on column header).
When the user tries to resize the "Company" column by dragging the right edge, the drag
event is captured by the header's drag-to-reorder handler first. The column reorders instead
of resizes. The user has to click precisely on the 4px resize handle border — but at 56px row
height, the resize zone is tiny and the drag start ambiguity triggers reorder instead.

**Why it happens:**
TanStack Table's column resizing and drag-based column reordering both listen to `onMouseDown`
or `onPointerDown` events on the `<th>` element. When both are active, the event propagation
order determines which wins. If the resize handler does not properly `stopPropagation`, the
reorder handler fires.

**Prevention:**
- Implement resize handles as a distinct child element inside `<th>` with explicit event
  capture and `stopPropagation`:
  ```tsx
  <th onMouseDown={header.getResizeHandler()}>
    <div className="header-content" onMouseDown={handleReorderDragStart}>
      {header.column.columnDef.header}
    </div>
    <div
      className="resize-handle"
      onMouseDown={(e) => { e.stopPropagation(); header.getResizeHandler()(e); }}
    />
  </th>
  ```
- Make the resize zone visually obvious: 8-12px wide, with a distinct cursor and a visible
  separator line on hover.
- Test the interaction explicitly: click anywhere in the header text → triggers reorder.
  Click on the right-edge resize zone → triggers resize, not reorder.

**Detection:**
- Manual test: attempt to resize a column by clicking 3px from the right edge of the header.
  Verify it resizes, not reorders.
- Browser DevTools: add `console.log` to both handlers and verify only the correct one fires.

**Phase to address:** Frontend Pipeline Grid phase. The resize/reorder interaction must be
tested before the grid is declared done.

---

## Minor Pitfalls

Mistakes that cause small regressions or cosmetic issues.

---

### Pitfall 11: AI Summary Preview Truncation at Wrong Boundary

**What goes wrong:**
`ai_summary_preview` is defined as "first 200 chars" of `ai_summary`. A 200-character slice
mid-word produces: "Satguru Industries has been in engaged outreach since January. Key champion
is Rajiv Mehta (CFO). Last interaction was a demo call where they expressed interest in
enterprise tier. Budget convers..." — truncated mid-word. The card reads awkwardly.

**Prevention:**
Truncate at the last word boundary before 200 characters:
```python
def truncate_at_word(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(' ', 1)[0] + '…'
```

---

### Pitfall 12: Relationship Status vs Pipeline Stage Semantic Confusion in API Responses

**What goes wrong:**
The API response for `GET /relationships/` includes both `pipeline_stage` and
`relationship_status` fields. Frontend developers misread `relationship_status` (which means
`active|inactive|churned`) as a status indicator for filtering in the Pipeline grid. They
wire the Pipeline's "Outreach Status" column to `relationship_status` instead of
`last_outreach_status`. The Pipeline shows "active" for every company. The status filter
does nothing useful.

**Prevention:**
- Name fields unambiguously in the response schemas:
  - `pipeline_stage`: only present in Pipeline endpoint responses
  - `relationship_status`: only present in Relationship endpoint responses
  - `outreach_status`: the latest outreach activity status (sent/replied/bounced)
- Do not return `pipeline_stage` in relationship responses or vice versa.
- Write an API contract test that verifies the Pipeline response does NOT contain
  `relationship_status` and the Relationships response does NOT contain `pipeline_stage`.

---

### Pitfall 13: RLS Bypass When Querying for Signal Counts

**What goes wrong:**
The signals endpoint aggregates counts across accounts. A developer writes:
```python
result = await db.execute(
    select(func.count()).select_from(Account).where(
        Account.relationship_type.any("prospect")
    )
)
```
This uses `db` which is the tenant-scoped session (RLS enforced). But if the developer uses
`db` from a different dependency (e.g., a shared session not from `get_tenant_db`), the
RLS `app.tenant_id` setting is not applied and the query returns counts across ALL tenants.

**Prevention:**
- Signal computation must always use `db: AsyncSession = Depends(get_tenant_db)`.
- Add a CI test: create two tenants with accounts, call signals endpoint as tenant A,
  verify total count is only tenant A's accounts.
- The signal computation code must never use a raw `engine.connect()` or any session
  obtained outside the `get_tenant_db` dependency.

---

### Pitfall 14: Stale Sidebar Badge Count After In-Page Actions

**What goes wrong:**
The user opens the Advisors list. One advisor has a stale relationship signal (badge count: 1).
The user opens the advisor detail, adds a note (which resolves the staleness). Navigates back to
Advisors list. The badge still shows 1. The signal was resolved but the badge count didn't
update until the 60-second poll cycle.

**Prevention:**
- After any note-add, file-add, or synthesis call, also invalidate the `['signals']` query key.
- The signal polling is 60 seconds — this is acceptable as documented in the spec. But
  explicit mutations that clearly resolve a signal should trigger an immediate re-fetch.
- `queryClient.invalidateQueries({ queryKey: ['signals'] })` must be called from the same
  mutation `onSuccess` callbacks as relationship invalidation.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Data model migration | Atomic rename causes API outage | Two-phase migration: add columns first, rename later |
| Data model migration | Missing GIN index on `relationship_type` | Add `CREATE INDEX ... USING GIN` in same migration |
| Data model migration | Person-level accounts missing self-contact FK | Add `primary_contact_id` FK to `accounts` table now |
| Backend relationships API | Accounts in both Pipeline and Relationships | Strictly defined partition predicate; test both endpoints |
| Backend graduation endpoint | Person-level entity_level not set atomically | Graduation endpoint sets `entity_level`, creates self-contact, sets `primary_contact_id` in one transaction |
| Backend signals API | Full table scan on every 60-second poll | Add EXPLAIN ANALYZE; verify GIN index usage; separate count vs full signals queries |
| Backend AI synthesis | LLM called on cache miss automatically | NULL summary → return NULL; synthesis always explicit; rate limit at DB level |
| Frontend pipeline grid | Column state lost on navigation | localStorage persistence from day one |
| Frontend pipeline grid | Drag reorder conflicts with column resize | Explicit resize handle zones; stopPropagation from resize handler |
| Frontend pipeline grid | Graduation: stale pipeline and relationships caches | Query key factory; invalidate pipeline + relationships + signals on graduation success |
| Frontend relationship detail | Multi-type accounts show wrong tabs/back-link | `?from=type` URL param; detail page renders based on fromType |
| Frontend relationship detail | AI synthesis triggered on page load | Synthesis only via explicit user action; never from useEffect or query lifecycle |
| Signal layer | Sidebar badge stale after in-page resolution | Invalidate signals on every mutation that could resolve a signal |

---

## "Looks Done But Isn't" Checklist

- [ ] **Migration**: Phase A migration adds columns AND copies `status → pipeline_stage` data in same transaction
- [ ] **Migration**: GIN index on `relationship_type` created in same migration as the column
- [ ] **Migration**: All 206 existing accounts have `relationship_type = '{prospect}'` after migration (verify with count query)
- [ ] **Migration**: `PATCH /accounts/{id}` no longer accepts `status` field (field removed from Pydantic model)
- [ ] **Pipeline API**: `GET /pipeline/` returns zero results for graduated accounts (verify with post-graduation query)
- [ ] **Pipeline API**: `GET /pipeline/` uses `pipeline_stage`, not `status`, in WHERE clause
- [ ] **Relationships API**: `GET /relationships/?type=advisor` returns ONLY accounts where `'advisor' = ANY(relationship_type)`, scoped by tenant
- [ ] **Graduation**: After graduation, account disappears from Pipeline list AND appears in target Relationship list (test both in sequence)
- [ ] **Graduation**: Person-level graduation creates exactly 1 self-contact and sets `primary_contact_id`
- [ ] **AI synthesis**: `GET /relationships/{id}` returns `ai_summary: null` for unsynthesized accounts without triggering LLM call
- [ ] **AI synthesis**: `POST /relationships/{id}/synthesize` returns 429 if called within 5 minutes of previous call
- [ ] **AI synthesis**: Accounts with < 3 context entries return template string, not LLM call
- [ ] **Signals**: Signal count query uses existing `idx_account_next_action` index (verify with EXPLAIN)
- [ ] **Signals**: Signal counts are tenant-scoped (two-tenant isolation test)
- [ ] **Grid**: Column config survives page navigation (localStorage write verified in Network tab)
- [ ] **Grid**: Column config survives hard refresh (localStorage read on mount verified)
- [ ] **Grid**: Column resize does not accidentally trigger column reorder (manual interaction test)
- [ ] **Frontend**: `fromType` URL param drives back-link and initial tab on detail page
- [ ] **Frontend**: Query key factory used for all pipeline/relationships/signals queries
- [ ] **Frontend**: Graduation success invalidates pipeline, relationships (all types), and signals simultaneously

---

## Recovery Strategies

When pitfalls occur despite prevention.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Atomic rename caused API outage | HIGH | Roll back migration (downgrade removes new columns, restores status column); revert code deploy; execute two-phase approach |
| Missing GIN index on production | LOW | `CREATE INDEX CONCURRENTLY idx_account_relationship_type ON accounts USING GIN (relationship_type);` — CONCURRENTLY avoids table lock |
| Account stuck in both Pipeline and Relationships | LOW | Direct DB fix: verify `relationship_type` is correct; query returns correct results after fix |
| Self-contact not created during graduation | MEDIUM | Write a backfill script: for each person-level account missing a contact, create one from the account's own data; set `primary_contact_id` |
| AI synthesis runaway cost | MEDIUM | Kill frontend query triggering synthesis; add rate limiter retroactively; review Anthropic bill for unbounded calls |
| Column state not persisting | LOW | Add localStorage persistence in a hotfix; no data loss, only UX regression |
| Wrong partition logic — graduated account in Pipeline | LOW | Update Pipeline query predicate; no data migration needed, just query fix |

---

## Sources

- Codebase inspection: `backend/src/flywheel/api/accounts.py` — existing `status` field usage in Pydantic models, ORM queries, and serializers
- Codebase inspection: `backend/alembic/versions/027_crm_tables.py` — `status` column definition and existing indexes
- Codebase inspection: `frontend/src/features/pipeline/types/pipeline.ts` — `status: string` field in TypeScript type
- Codebase inspection: `backend/src/flywheel/api/outreach.py` — `GET /pipeline/` filters on `Account.status`
- PostgreSQL GIN indexes: [Optimizing Array Queries With GIN Indexes in PostgreSQL](https://www.tigerdata.com/learn/optimizing-array-queries-with-gin-indexes-in-postgresql) — `ANY()` operator requires GIN, not B-tree
- PostgreSQL GIN performance: [Understanding Postgres GIN Indexes: The Good and the Bad](https://pganalyze.com/blog/gin-index) — update cost analysis
- PostgreSQL backward-compatible migration: [Using PostgreSQL views for non-breaking migrations](https://medium.com/ovrsea/using-postgresql-views-to-ensure-backwards-compatible-non-breaking-migrations-017288e77f06) — two-phase rename pattern
- PostgreSQL migration safety: [How to Rename Tables and Columns Safely in PostgreSQL](https://oneuptime.com/blog/post/2026-01-21-postgresql-rename-tables-columns/view) — ACCESS EXCLUSIVE lock during rename
- TanStack Table virtualization: [TanStack Virtual issue #685](https://github.com/TanStack/virtual/issues/685) — rendering lag with both row and column virtualization
- TanStack Table virtualization: [Virtualization Guide](https://tanstack.com/table/v8/docs/guide/virtualization) — 50+ rows threshold for virtualization benefit
- React Query cache invalidation: [Concurrent Optimistic Updates in React Query](https://tkdodo.eu/blog/concurrent-optimistic-updates-in-react-query) — race condition with optimistic updates
- React Query cache invalidation: [Cache Invalidation Why UI Doesn't Update](https://medium.com/@kennediowusu/react-query-cache-invalidation-why-your-mutations-work-but-your-ui-doesnt-update-a1ad23bc7ef1) — exact key matching pitfall
- LLM cost control: [LLM Cost Optimization: Complete Guide](https://ai.koombea.com/blog/llm-cost-optimization) — context window overload as primary cost driver
- LLM cost control: [Practical LLMOps Cost Control](https://radicalbit.ai/resources/blog/cost-control/) — per-account budget controls and runaway cost patterns
- Two-phase migration pattern: [Alembic Complete Developer's Guide](https://medium.com/@tejpal.abhyuday/alembic-database-migrations-the-complete-developers-guide-d3fc852a6a9e) — add/copy/remove pattern for zero-downtime renames
- Multi-type entity design: [CRM Database Schema Example](https://www.dragonflydb.io/databases/schema/crm) — normalization principles for entity type hierarchies

---

*Pitfalls research for: CRM Redesign — Multi-type relationships, AI synthesis, configurable grid*
*Researched: 2026-03-27*
*Codebase: brownfield FastAPI + SQLAlchemy 2.0 async + PostgreSQL + React + shadcn/ui*
