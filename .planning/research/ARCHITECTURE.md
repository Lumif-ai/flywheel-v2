# Architecture Patterns: AI Synthesis + Premium CRM Integration

**Domain:** Adding AI synthesis, configurable grid, and multi-type relationships to existing Flywheel CRM
**Researched:** 2026-03-27
**Confidence:** HIGH — direct codebase inspection supplemented by verified patterns

---

## Existing Architecture Baseline

Before documenting integration points, here is what already exists (v2.0 CRM milestone):

```
FRONTEND (React + Vite)
  routes.tsx               -- lazy-loaded page routes
  features/accounts/       -- AccountsPage, AccountDetailPage, Pipeline
    api.ts                 -- fetchAccounts, fetchAccountDetail, fetchTimeline
    hooks/                 -- useAccounts, useAccountDetail, useTimeline (React Query)
    components/            -- AccountsPage, AccountDetailPage, ContactsPanel,
                              TimelineFeed, IntelSidebar, ActionBar
    types/accounts.ts      -- AccountListItem, AccountDetail, TimelineItem etc.
  stores/ui.ts             -- Zustand: sidebarOpen, commandPalette
  stores/auth.ts           -- Zustand: JWT token
  stores/focus.ts          -- Zustand: activeFocus
  lib/api.ts               -- Central fetch wrapper (Bearer + X-Focus-Id headers)
  lib/realtime.ts          -- Supabase Realtime for skill_run completion events

BACKEND (FastAPI + SQLAlchemy 2.0 async)
  main.py                  -- lifespan: job_queue_loop, calendar_sync_loop,
                              email_sync_loop, cleanup tasks
  api/accounts.py          -- GET/POST/PATCH accounts, contacts CRUD (8 endpoints)
  api/outreach.py          -- Outreach CRUD, pipeline view, graduation (7 endpoints)
  api/timeline.py          -- Unified timeline + pulse signals (2 endpoints)
  api/context.py           -- Context entries CRUD, full-text search (10 endpoints)
  api/files.py             -- File upload + extraction (3 endpoints)
  api/chat.py              -- Haiku intent routing -> SkillRun (1 endpoint)
  services/skill_executor.py -- AsyncAnthropic tool-use loop + streaming
  services/job_queue.py    -- FOR UPDATE SKIP LOCKED background worker (5s poll)
  storage.py               -- context read/append/query/batch with evidence dedup
  storage_backend.py       -- strangler fig: flatfile / postgres / remote routing

DATABASE (PostgreSQL with RLS)
  accounts                 -- tenant_id, name, normalized_name, domain, status,
                              fit_score, fit_tier, intel JSONB, source,
                              last_interaction_at, next_action_due
  account_contacts         -- tenant_id, account_id FK, name, email, title,
                              role_in_deal, linkedin_url, notes
  outreach_activities      -- tenant_id, account_id FK, contact_id FK, channel,
                              direction, status, subject, body_preview, sent_at, metadata JSONB
  context_entries          -- tenant_id, file_name, content, source, detail,
                              confidence, focus_id, account_id FK, search_vector TSVECTOR,
                              metadata JSONB
  uploaded_files           -- tenant_id, filename, mimetype, storage_path,
                              extracted_text, metadata JSONB
  enrichment_cache         -- tenant_id, query_hash, results JSONB, created_at
  skill_runs               -- tenant_id, skill_name, input_text, output,
                              events_log JSONB, status, scheduled_for
```

---

## Feature 1: AI Synthesis Engine

### What it needs to do

Generate, cache, and serve LLM-written summaries per account relationship. A summary
synthesizes context_entries (linked via account_id), outreach history, and intel JSONB
into 2-3 sentences like "Acme Corp is an engaged prospect — last replied 6 days ago.
3 open loop items. CEO conversation tracked in June."

### Integration Point: New DB Table

Add `account_syntheses` table. Do NOT store synthesis in the `accounts.intel` JSONB
column — that field is for structured key-value intel (industry, funding, etc.), not
prose. Separate table allows versioning and explicit invalidation.

```sql
CREATE TABLE account_syntheses (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenants(id),
    account_id  uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    synthesis   text NOT NULL,
    model       text NOT NULL DEFAULT 'claude-haiku-4-5',
    tokens_used int,
    generated_at timestamptz NOT NULL DEFAULT now(),
    invalidated_at timestamptz,        -- null = current/valid
    trigger     text NOT NULL          -- 'manual' | 'context_write' | 'outreach_write' | 'ttl'
);
CREATE UNIQUE INDEX idx_synthesis_current
    ON account_syntheses (account_id)
    WHERE invalidated_at IS NULL;
CREATE INDEX idx_synthesis_tenant ON account_syntheses (tenant_id, account_id);
```

RLS follows the same pattern as accounts — tenant_isolation_select/insert/update/delete
using `current_setting('app.tenant_id', true)::uuid`.

### Integration Point: Invalidation Triggers

The synthesis goes stale when its source data changes. Two trigger locations exist in
the current codebase:

1. `storage.append_entry()` — called when a context_entry is written. If the entry
   has `account_id` set, invalidate that account's synthesis. This is the right place
   because all skill writes go through this function.

2. `api/outreach.py` (PATCH outreach status, POST create outreach) — after any write
   to outreach_activities for an account, invalidate that account's synthesis.

Both locations should call a shared `invalidate_synthesis(session, account_id)` helper
that sets `invalidated_at = now()` on the current row without deleting it (preserves
history).

### Integration Point: New Service

New `services/synthesis_engine.py`:

```
generate_synthesis(session, account_id) -> str
  1. Load account row + contacts
  2. Load context_entries WHERE account_id = ? ORDER BY date DESC LIMIT 20
  3. Load outreach_activities WHERE account_id = ? ORDER BY created_at DESC LIMIT 10
  4. Call AsyncAnthropic (haiku-4-5, ~300 token budget) with prompt
  5. INSERT into account_syntheses
  6. Return synthesis text

get_or_generate_synthesis(session, account_id) -> str
  1. SELECT from account_syntheses WHERE account_id = ? AND invalidated_at IS NULL
  2. If found AND age < 24h: return cached
  3. Else: call generate_synthesis, return result
```

The 24-hour TTL is an additional freshness gate even when not explicitly invalidated.
Use `haiku-4-5` (not sonnet) — synthesis is a brief summarization task.

### Integration Point: API

Extend `GET /accounts/{account_id}` response to include `synthesis: str | null`.
The AccountDetail Pydantic model gains one optional field. The endpoint calls
`get_or_generate_synthesis(session, account_id)` before returning — this is
synchronous from the client's perspective but generation adds ~1-2s on cache miss.
Frontend can show a skeleton for the synthesis panel while the detail request resolves.

Do NOT add a separate `/synthesis` endpoint unless the AI panel needs on-demand
regeneration (which is a legitimate separate endpoint: `POST /accounts/{id}/synthesis/regenerate`).

### Data Flow

```
User opens AccountDetailPage
  -> GET /accounts/{id}  (existing)
  -> FastAPI calls get_or_generate_synthesis(session, account_id)
      -> DB hit: return cached synthesis (fast, <5ms)
      -> DB miss / stale: call Anthropic Haiku (~1.5s), write, return
  -> Response includes synthesis field
  -> Frontend renders synthesis in IntelSidebar or new SynthesisPanel

Background invalidation:
  append_entry(..., account_id=X) in storage.py
    -> invalidate_synthesis(session, account_id=X)

PATCH /outreach/{id} with status='replied'
    -> update outreach_activities
    -> invalidate_synthesis(session, account_id=outreach.account_id)
```

---

## Feature 2: AI Q&A Panel (RAG)

### What it needs to do

User types a question about an account ("What did we discuss with their CTO?") and
gets a contextual answer grounded in context_entries and outreach for that account.

### Integration Point: Existing Full-Text Search

The `context_entries` table has a persisted `search_vector TSVECTOR` column computed
from `detail || content`. The existing `GET /context/search` endpoint already performs
`ts_rank` queries. This is the retrieval layer — no pgvector/embeddings needed for MVP.

Retrieval strategy: hybrid — full-text search for keyword matching + recency filter
for temporal questions. This is adequate for the account-scoped knowledge base (typically
20-100 entries per account) and avoids adding pgvector as a dependency.

If pgvector becomes necessary later (>500 entries per account, multi-lingual content),
it can be added as a column to context_entries without schema changes to the rest of
the system. MEDIUM confidence that full-text is sufficient for v3.0 scope.

### Integration Point: New Endpoint

New endpoint in `api/accounts.py` (or new `api/account_qa.py`):

```
POST /accounts/{account_id}/ask
  body: { question: str, history: list[dict] | None }
  response: { answer: str, sources: list[{ id, file_name, detail, date }] }
```

The endpoint:
1. Performs `ts_query` on context_entries WHERE account_id = ? using the question text
2. Fetches top 10 matching entries + 5 most recent outreach activities
3. Builds RAG prompt: system context + retrieved snippets + question
4. Calls AsyncAnthropic (haiku-4-5 for speed) with streaming or sync
5. Returns answer + source citations

This reuses the existing `_execute_with_tools` pattern from skill_executor, but as a
direct API call (not a SkillRun job) because Q&A is interactive and needs low latency.

### Integration Point: Frontend

New `AskPanel` component in `features/accounts/components/`. It renders as a drawer
or expandable section in `AccountDetailPage`. State is local (useState for messages),
not React Query (conversational, not cacheable). The `POST /accounts/{id}/ask` call
goes through the central `api.post()` wrapper.

---

## Feature 3: Multi-Type Relationship Model

### What it needs to do

An account can be: prospect, customer, partner, investor, advisor, vendor — potentially
multiple simultaneously. Current schema has a single `status` text column ('prospect',
'engaged', 'customer', 'churned', 'disqualified') which models pipeline stage, not
relationship type.

These are orthogonal concerns: pipeline stage (status) vs relationship type (customer
AND partner simultaneously is valid).

### Integration Point: Schema Addition

Add `relationship_types` ARRAY(Text) column to `accounts` table. Preserve `status`
as-is — it models lifecycle stage, which remains useful. The new column models the
classification taxonomy.

```sql
ALTER TABLE accounts
ADD COLUMN relationship_types text[] NOT NULL DEFAULT '{}'::text[];

CREATE INDEX idx_account_rel_types ON accounts
    USING GIN (relationship_types);
```

GIN index on the array enables efficient `WHERE 'partner' = ANY(relationship_types)`
queries for filtering the grid by relationship type.

### Integration Point: API

Extend `CreateAccountRequest` and `UpdateAccountRequest` in `api/accounts.py` to include
`relationship_types: list[str] | None`. The `AccountListItem` and `AccountDetail`
Pydantic models gain `relationship_types: list[str]`.

Extend `GET /accounts/` list endpoint filter to accept `relationship_type: str` query
parameter (filters for accounts where that type is in the array).

### Integration Point: Frontend

`AccountListItem` type in `features/accounts/types/accounts.ts` gains `relationship_types: string[]`.
The `AccountsPage` filter bar adds a relationship type multi-select. The `AccountDetailPage`
header renders relationship type badges alongside the existing status badge.

The `IntelSidebar` component or a new `RelationshipPanel` renders and allows inline
editing of relationship types via PATCH account.

---

## Feature 4: Configurable Grid State

### What it needs to do

Users can show/hide columns, reorder them, resize them, and save named views
("My Pipeline View", "Customer Accounts"). State persists across sessions per user.

### Integration Point: Where to Store State

Two options exist in this codebase:

**Option A: profiles.settings JSONB** — The `profiles` table already has a `settings JSONB`
column. Grid state can be stored as a nested key:
`settings.grid_views.accounts = { columns: [...], saved_views: [...] }`.
Requires no new table, no new migration, but mixes UI preferences with account settings.

**Option B: New `user_grid_prefs` table** — Clean separation, RLS enforceable, queryable.

Recommendation: Use `profiles.settings` for MVP. The profiles.settings JSONB is already
used by the app for other preferences (HIGH confidence from models.py inspection). Grid
state is genuinely a user preference. Add a new table only if the number of saved views
per user grows large (>20) or if multi-tenant sharing of views becomes a requirement.

Grid state shape stored in `profiles.settings.grid_views`:
```json
{
  "accounts": {
    "column_visibility": { "fit_score": false, "source": false },
    "column_order": ["name", "status", "relationship_types", "contact_count", ...],
    "saved_views": [
      { "id": "uuid", "name": "Pipeline View", "filters": {...}, "columns": {...} }
    ],
    "active_view_id": "uuid | null"
  }
}
```

### Integration Point: API

New endpoints on existing `api/profile.py` router (already exists):
```
GET  /profile/grid-prefs/{grid_name}     -- returns grid state for named grid
PATCH /profile/grid-prefs/{grid_name}    -- saves partial update (column state only,
                                            or saved views, not full overwrite)
```

Alternatively, reuse `PATCH /profile` if it already accepts a `settings` field. Check
existing profile endpoint before adding new ones.

### Integration Point: Frontend Library

The existing `AccountsPage` uses a hand-rolled table (useState + manual column rendering).
For a configurable grid, use **TanStack Table v8** — it is already the industry standard
for this pattern, has column visibility + ordering APIs built-in, and integrates cleanly
with React Query.

Column state management flow:
```
TanStack Table instance
  -> columnVisibility, columnOrder state (initialized from React Query cache)
  -> onColumnVisibilityChange / onColumnOrderChange callbacks
  -> debounced PATCH /profile/grid-prefs/accounts (save to DB)
  -> React Query invalidates 'grid-prefs' query key on success
```

Do not use localStorage for persistence — the existing architecture uses the DB for all
persistent state, and localStorage creates cross-device inconsistency. Use localStorage
only as a write-through cache for instant initialization before the API response.

### Integration Point: Zustand

Add a `useGridPrefsStore` Zustand store that holds column state in-memory. Initialize
it from the React Query fetch of `/profile/grid-prefs/accounts`. Updates flow:
`user interaction -> Zustand update (instant) -> debounced DB write`.

---

## Feature 5: Signal Computation

### What it needs to do

Compute "attention signals" — accounts needing action: reply received, follow-up overdue,
bump suggested, relationship gone cold. Currently the pulse endpoint computes these
at read time (on each GET /pulse request).

### Existing Foundation

`GET /pulse/` in `api/timeline.py` already exists and computes signals in Python at
request time by querying outreach_activities for overdue actions and recent replies.
This is the "real-time computation" pattern.

### Recommendation: Keep Real-Time Computation for MVP

The current approach (compute on request) is correct for <500 accounts per tenant.
The computation is simple SQL — a few index scans — and completes in <50ms. Background
pre-computation adds operational complexity (worker scheduling, cache invalidation)
without meaningful benefit at this scale.

Pre-computation becomes worthwhile when:
- Tenant has >1,000 accounts and pulse load is >10 requests/minute
- Signals require expensive LLM calls (they currently don't)
- Push notifications are needed (which require background computation anyway)

If push notifications are added (a separate feature), introduce a `pulse_signals` table
that caches computed signals. The job_queue worker (already running) can populate it.
The GET /pulse endpoint then reads from the cache table instead of computing live.

### Signal Computation Logic (current, verified from codebase)

```
followup_overdue:  accounts WHERE next_action_due < now() AND status = 'prospect'
reply_received:    outreach WHERE status = 'replied' AND created_at > now() - 7d
                   AND account.status = 'prospect'
bump_suggested:    outreach WHERE status = 'sent' AND sent_at < now() - 5d
                   AND no subsequent outreach for same account
```

These run as SQL queries in the pulse endpoint handler. No new infrastructure needed.

---

## Feature 6: File Attachments to Relationships

### What it needs to do

Link uploaded files (already in `uploaded_files` table + Supabase Storage) to specific
accounts. Currently files are tenant-scoped with no account link.

### Integration Point: Schema Addition

Add `account_id` nullable FK to `uploaded_files`:

```sql
ALTER TABLE uploaded_files
ADD COLUMN account_id uuid REFERENCES accounts(id) ON DELETE SET NULL;

CREATE INDEX idx_files_account ON uploaded_files (account_id)
    WHERE account_id IS NOT NULL;
```

### Integration Point: API

Extend `POST /files/upload` to accept optional `account_id` query parameter or form
field. Extend `GET /files/` to accept `account_id` filter. Add to `AccountDetail`
response a `files: list[FileMetadata]` field populated by querying `uploaded_files
WHERE account_id = ?`.

### Integration Point: Frontend

New `FilesPanel` component in account detail page. Renders a file list with upload
button. Reuses the existing file upload flow (already implemented in the frontend for
the context store) with an additional `account_id` parameter passed on upload.

---

## Component Boundaries: New vs Modified

### New Components (Backend)

| Component | File | Purpose |
|-----------|------|---------|
| SynthesisEngine | `services/synthesis_engine.py` | generate/cache/invalidate account summaries |
| AccountQA endpoint | `api/accounts.py` or `api/account_qa.py` | RAG Q&A for account context |
| Synthesis migration | `alembic/versions/028_account_syntheses.py` | account_syntheses table |
| RelTypes migration | `alembic/versions/029_account_rel_types.py` | relationship_types column |
| FileAccount migration | `alembic/versions/030_file_account_fk.py` | account_id on uploaded_files |
| Grid prefs endpoints | `api/profile.py` (extend) | GET/PATCH grid state |

### New Components (Frontend)

| Component | File | Purpose |
|-----------|------|---------|
| SynthesisPanel | `features/accounts/components/SynthesisPanel.tsx` | display AI summary |
| AskPanel | `features/accounts/components/AskPanel.tsx` | Q&A chat interface |
| FilesPanel | `features/accounts/components/FilesPanel.tsx` | file list + upload |
| useGridPrefs | `features/accounts/hooks/useGridPrefs.ts` | React Query for grid state |
| useGridPrefsStore | `stores/gridPrefs.ts` | Zustand for in-memory column state |
| GridView | `features/accounts/components/GridView.tsx` | TanStack Table wrapper |

### Modified Components (Backend)

| Component | Change | Risk |
|-----------|--------|------|
| `storage.py:append_entry()` | Call `invalidate_synthesis()` if account_id set | Low — additive |
| `api/outreach.py` | Call `invalidate_synthesis()` after status write | Low — additive |
| `api/accounts.py` | Add `synthesis`, `files`, `relationship_types` to AccountDetail | Low — additive |
| `api/files.py` | Accept `account_id` on upload, filter by it | Low — additive |
| `db/models.py:Account` | Add `relationship_types: ARRAY(Text)` mapped column | Low — additive |
| `db/models.py:UploadedFile` | Add `account_id` FK mapped column | Low — additive |

### Modified Components (Frontend)

| Component | Change | Risk |
|-----------|--------|------|
| `AccountDetailPage.tsx` | Add SynthesisPanel, AskPanel, FilesPanel to layout | Low |
| `AccountsPage.tsx` | Replace hand-rolled table with TanStack Table GridView | Medium — rewrite |
| `types/accounts.ts` | Add synthesis, files, relationship_types to AccountDetail | Low |
| `features/accounts/api.ts` | Add askAccount(), getGridPrefs(), saveGridPrefs() | Low |

---

## Data Flow Changes

### Synthesis Write Path

```
Before (v2.0):
  POST /context/entries  ->  storage.append_entry()  ->  context_entries row

After (new):
  POST /context/entries  ->  storage.append_entry()
                          ->  if account_id: invalidate_synthesis(account_id)
                          ->  context_entries row
```

### Account Detail Read Path

```
Before (v2.0):
  GET /accounts/{id}  ->  SELECT account + contacts + timeline  ->  AccountDetail response

After (new):
  GET /accounts/{id}  ->  SELECT account + contacts + timeline
                      ->  get_or_generate_synthesis(account_id)   [+0-2s on miss]
                      ->  SELECT uploaded_files WHERE account_id
                      ->  Extended AccountDetail response
```

### Grid Initialization Path

```
Mount AccountsPage
  ->  React Query: GET /profile/grid-prefs/accounts
  ->  Initialize useGridPrefsStore with DB state
  ->  TanStack Table reads column state from store
  ->  Render grid with persisted configuration
```

---

## Suggested Build Order

Build order is driven by three rules:
1. Data model first — schema migrations before any service or API code
2. Backend before frontend — stable API contracts before UI components
3. Independent features before integrated features — synthesis before Q&A (synthesis
   provides the summary panel that makes Q&A contextually richer)

```
Phase A: Schema + Model Additions (1 migration per concern)
  028_account_syntheses.py    -- new table
  029_account_rel_types.py    -- ADD COLUMN to accounts
  030_file_account_fk.py      -- ADD COLUMN to uploaded_files
  db/models.py                -- add mapped columns for all three

Phase B: AI Synthesis Engine
  services/synthesis_engine.py    -- generate + cache + invalidate
  storage.py                      -- hook invalidation into append_entry
  api/outreach.py                 -- hook invalidation into outreach writes
  api/accounts.py                 -- add synthesis to AccountDetail response
  SynthesisPanel.tsx              -- read-only display in account detail

Phase C: Multi-Type Relationships
  api/accounts.py                 -- relationship_types in create/update/list
  AccountsPage.tsx                -- add relationship type filter
  AccountDetailPage.tsx           -- show badges + inline edit

Phase D: Configurable Grid
  api/profile.py                  -- GET/PATCH grid prefs endpoints
  stores/gridPrefs.ts             -- Zustand store
  GridView.tsx                    -- TanStack Table wrapper
  AccountsPage.tsx                -- replace hand-rolled table with GridView

Phase E: File Attachments
  api/files.py                    -- account_id on upload + filter
  api/accounts.py                 -- files in AccountDetail response
  FilesPanel.tsx                  -- file list + upload in account detail

Phase F: AI Q&A Panel
  api/accounts.py (or account_qa.py)  -- POST /accounts/{id}/ask
  AskPanel.tsx                        -- conversational UI in account detail
```

Phases B and C have no dependency on each other and can be built in parallel.
Phase D (configurable grid) depends on Phase C completing relationship_types schema
so the grid has all columns available to configure.
Phase F (Q&A) should come last — it reuses synthesis infrastructure from Phase B
and benefits from having richer account data from C and E already indexed.

---

## Scalability Notes

| Concern | Current approach | Threshold to revisit |
|---------|-----------------|---------------------|
| Synthesis generation latency | Synchronous on GET /accounts/{id}, Haiku ~1.5s | >200 accounts loaded in list view (then pre-warm on list load) |
| Signal computation | Real-time SQL on GET /pulse | >1,000 accounts per tenant, >10 req/min |
| Grid state storage | profiles.settings JSONB | >20 saved views per user or view sharing needed |
| Q&A retrieval | PostgreSQL full-text search | >500 context entries per account or multilingual content |
| File-to-account linking | FK on uploaded_files | No scale concern at CRM scale |

---

## Sources

- Codebase inspection: `/backend/src/flywheel/db/models.py` (direct read)
- Codebase inspection: `/backend/src/flywheel/storage.py` (direct read)
- Codebase inspection: `/backend/src/flywheel/services/skill_executor.py` (direct read)
- Codebase inspection: `/backend/src/flywheel/api/accounts.py`, `outreach.py`, `timeline.py` (direct read)
- Codebase inspection: `/backend/alembic/versions/027_crm_tables.py` (direct read)
- Codebase inspection: `/frontend/src/features/accounts/` (direct read)
- [TanStack Table Column Visibility API](https://tanstack.com/table/v8/docs/api/features/column-visibility) — HIGH confidence
- [TanStack Table State Guide](https://tanstack.com/table/v8/docs/framework/react/guide/table-state) — HIGH confidence
- [pgvector PostgreSQL vector search](https://calmops.com/database/postgresql-vector-search-pgvector-2026/) — MEDIUM confidence (for if/when embeddings needed)
- [LLM caching strategies 2026](https://dasroot.net/posts/2026/02/caching-strategies-for-llm-responses/) — MEDIUM confidence (informed synthesis cache TTL decision)
