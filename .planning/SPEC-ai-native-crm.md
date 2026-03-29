# AI-Native CRM: Accounts, Pipeline & Pulse — Specification

> Status: Draft
> Created: 2026-03-26
> Last updated: 2026-03-26
> Source: CONCEPT-BRIEF-ai-native-crm.md (5-round brainstorm)

## Overview

Build three new surfaces in Flywheel — Accounts, Pipeline, and Pulse — that turn the compounding context store and GTM skill pipeline into a company-centric intelligence system. Every piece of data is produced by skill execution (meeting-prep, company-intel, GTM pipeline, meeting-processor), not manual entry. The CRM is a view layer over accumulated intelligence.

## Core Value

**Founders never lose track of an account again.** Every company they're engaging with — prospects, active deals, customers — has a single screen showing all contacts, interaction timeline, commitments, intel, and next actions. All populated automatically from skill runs.

## Users & Entry Points

| User Type | Entry Point | Primary Goal |
|-----------|-------------|--------------|
| Founder (any of 3) | Sidebar → Accounts | "Where are we with Suffolk Construction?" |
| Founder doing outreach | Sidebar → Pipeline | "Which scored leads need outreach? Who replied?" |
| Founder starting their day | Sidebar → Pulse (or Revenue focus) | "What needs my attention right now?" |
| Founder in a meeting | Account detail → [Prep for meeting] | "Give me full context before this call" |

---

## Requirements

### Must Have

#### Data Model & Migration

- **REQ-01**: Alembic migration creates `accounts`, `account_contacts`, and `outreach_activities` tables with RLS policies
  - **Acceptance Criteria:**
    - [ ] Migration `027_crm_tables` creates all three tables with columns matching the schema below
    - [ ] RLS enabled and forced on all three tables with tenant isolation policy
    - [ ] `GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user` for all three tables
    - [ ] `account_id` column added to `context_entries` (nullable, FK to accounts)
    - [ ] Partial index `idx_context_entries_account` on `context_entries(account_id) WHERE account_id IS NOT NULL`
    - [ ] `UNIQUE (tenant_id, name)` constraint on `accounts` prevents duplicate company names per tenant
    - [ ] All indexes from schema below are created
    - [ ] `downgrade()` drops all three tables and removes the `account_id` column from `context_entries`

- **REQ-02**: ORM models for `Account`, `AccountContact`, and `OutreachActivity` in `models.py`
  - **Acceptance Criteria:**
    - [ ] `Account` model with all columns, table args (indexes, unique constraint, RLS), and mapped relationships
    - [ ] `AccountContact` model with FK to `accounts`, all columns
    - [ ] `OutreachActivity` model with FKs to `accounts`, `account_contacts`, `profiles`, all columns
    - [ ] `ContextEntry` model updated with optional `account_id` FK and relationship
    - [ ] All status/enum fields use plain TEXT (not SQLAlchemy Enum) for flexibility

- **REQ-03**: Data seeding CLI command `flywheel db seed-crm` populates tables from existing GTM files
  - **Acceptance Criteria:**
    - [ ] Command reads `~/.claude/gtm-stack/gtm-leads-master.xlsx` "All Leads Scored" and "Company Summary" tabs
    - [ ] Command reads `~/.claude/gtm-stack/outreach-tracker.csv` for outreach history
    - [ ] Command reads `~/.claude/gtm-stack/pipeline-runs.json` for run metadata
    - [ ] Command reads scored CSVs from paths in `pipeline-runs.json` (skips missing files with warning)
    - [ ] Creates deduplicated `accounts` rows — company names normalized (strip Inc/LLC/Corp, lowercase compare, whitespace normalize)
    - [ ] Creates `account_contacts` from decision-maker fields (DM_Name, DM_Title, DM_Email, DM_LinkedIn) in scored CSVs
    - [ ] Creates `outreach_activities` from outreach-tracker.csv with correct status mapping (SENT→sent, PENDING→drafted, NOT_FOUND→failed)
    - [ ] Backfills `account_id` on existing `context_entries` by fuzzy-matching company names in entry content
    - [ ] Command is idempotent — running twice does not create duplicates (checks existing by tenant_id + normalized name)
    - [ ] Prints summary: X accounts, Y contacts, Z outreach activities, W context entries linked
    - [ ] Requires `--tenant-id` flag (or reads from environment) to scope all inserts
    - [ ] Requires `--user-id` flag for outreach_activities.user_id

#### Backend API

- **REQ-04**: Accounts REST API with list, detail, create, update
  - **Acceptance Criteria:**
    - [ ] `GET /api/v1/accounts/` — paginated list with `offset`, `limit` (max 100), `status` filter, `focus_id` filter, `search` (full-text on name+domain), `sort_by` (name, fit_score, updated_at, last_interaction_at)
    - [ ] Response: `{ accounts: [...], total, offset, limit, has_more }`
    - [ ] Each account in list includes: id, name, domain, status, fit_score, fit_tier, contact_count, outreach_count, last_interaction_at, next_action_due, focus_id, metadata, created_at
    - [ ] `contact_count` and `outreach_count` are computed via subquery (not denormalized)
    - [ ] `last_interaction_at` is MAX of outreach_activities.sent_at and context_entries.created_at for that account
    - [ ] `next_action_due` is derived from context_entries where file_name='action-items.md' AND account_id matches AND content contains a date
    - [ ] `GET /api/v1/accounts/{id}` — full detail including contacts array, recent timeline (last 20 activities), commitments, intel summary
    - [ ] `POST /api/v1/accounts/` — create account with name (required), domain, status, fit_score, fit_tier, focus_id, metadata
    - [ ] `PATCH /api/v1/accounts/{id}` — update any field (partial update)
    - [ ] `POST /api/v1/accounts/{id}/graduate` — sets status to 'engaged', returns updated account
    - [ ] All endpoints use `require_tenant` + `get_tenant_db` (RLS-scoped)
    - [ ] 404 if account not found or not in tenant

- **REQ-05**: Account Contacts REST API
  - **Acceptance Criteria:**
    - [ ] `GET /api/v1/accounts/{id}/contacts` — list contacts for an account
    - [ ] `POST /api/v1/accounts/{id}/contacts` — add contact to account
    - [ ] `PATCH /api/v1/accounts/{id}/contacts/{contact_id}` — update contact fields
    - [ ] `DELETE /api/v1/accounts/{id}/contacts/{contact_id}` — remove contact (hard delete)

- **REQ-06**: Outreach Activities REST API
  - **Acceptance Criteria:**
    - [ ] `GET /api/v1/accounts/{id}/outreach` — list outreach for an account, ordered by created_at desc
    - [ ] `POST /api/v1/accounts/{id}/outreach` — create outreach activity (requires contact_id, channel, direction)
    - [ ] `PATCH /api/v1/outreach/{id}` — update status (e.g., drafted → sent, sent → replied)
    - [ ] `GET /api/v1/pipeline/` — cross-account pipeline view: accounts with status='prospect', ordered by fit_score desc, includes latest outreach status per account
    - [ ] Pipeline endpoint supports `stage` filter: scored (no outreach), sent (outreach sent, no reply), replied (has reply), graduated (status != prospect)

- **REQ-07**: Account Timeline API
  - **Acceptance Criteria:**
    - [ ] `GET /api/v1/accounts/{id}/timeline` — unified chronological feed combining:
      - Outreach activities (sent, replied)
      - Context entries tagged with this account_id (meetings, research, intel)
      - Linked documents (skill runs that produced documents for this account)
    - [ ] Each timeline item has: type (outreach|context|document), timestamp, title, summary, actor (which founder), metadata
    - [ ] Paginated with offset/limit, ordered by timestamp desc
    - [ ] Returns at most 50 items per page

- **REQ-08**: Pulse Signals API
  - **Acceptance Criteria:**
    - [ ] `GET /api/v1/pulse/` — returns prioritized signal feed for the current tenant
    - [ ] Signal types with priority order:
      1. `reply_received` — outreach_activities where status='replied' AND replied_at > last_seen_at
      2. `followup_overdue` — context_entries in action-items.md with due dates in the past, linked to an account
      3. `meeting_prep_ready` — upcoming calendar meetings with known account contacts (future: requires calendar integration)
      4. `bump_suggested` — outreach_activities where status='sent' AND sent_at < now() - interval '5 days' AND no reply
      5. `new_companies_scored` — accounts created in last 7 days with fit_score IS NOT NULL
    - [ ] Each signal: type, priority (1-5), account_id, account_name, contact_name, message, created_at, action_url
    - [ ] Limit 50 signals, no pagination needed (feed is ephemeral)

#### Frontend: Accounts

- **REQ-09**: Accounts list page at `/accounts`
  - **Acceptance Criteria:**
    - [ ] Table showing all accounts with columns: name, status badge, fit score + tier badge, contacts count, last interaction (relative time), next action due
    - [ ] Click row → navigates to `/accounts/{id}`
    - [ ] Filter bar: status (all/prospect/engaged/customer), focus area dropdown
    - [ ] Search input with debounced full-text search
    - [ ] Sort by: name (alpha), fit score (desc), last interaction (desc)
    - [ ] Empty state: "No accounts yet. Run a GTM pipeline or meeting prep to get started."
    - [ ] Pagination with "Load more" button (20 per page)
    - [ ] Uses design tokens (Inter font, brand coral accent, 12px radius)

- **REQ-10**: Account detail page at `/accounts/{id}`
  - **Acceptance Criteria:**
    - [ ] Header: account name, domain link, status badge, fit score + tier badge, focus tag
    - [ ] Left panel: contacts list with name, title, role badge, email, LinkedIn link, last interaction date
    - [ ] Center: timeline feed (from REQ-07) showing all interactions chronologically
    - [ ] Each timeline entry shows: icon by type, title, summary text, actor name, relative timestamp
    - [ ] Outreach entries show channel badge (email/linkedin) and status badge (sent/replied/etc)
    - [ ] Context entries show source badge (meeting-prep/company-intel/etc)
    - [ ] Right panel: intel sidebar with key facts from metadata (industry, size, HQ, competitors, description)
    - [ ] Bottom section: commitments from action-items with due date and overdue highlighting
    - [ ] Action bar with buttons: [Prep for meeting] [Research company] [Draft follow-up]
    - [ ] Action buttons navigate to chat with pre-filled skill prompt (e.g., `/chat?skill=meeting-prep&input=...`)
    - [ ] Loading skeleton while data fetches
    - [ ] 404 page if account not found

#### Frontend: Pipeline

- **REQ-11**: Pipeline page at `/pipeline`
  - **Acceptance Criteria:**
    - [ ] Table view of accounts where status='prospect', sorted by fit_score desc
    - [ ] Columns: company name, fit score + tier badge, contact name + title, outreach status badge, days since last action, draft message preview (truncated to 100 chars)
    - [ ] Outreach status derived from latest outreach_activity: none → "Not contacted", drafted → "Draft ready", sent → "Awaiting reply (X days)", replied → "Replied"
    - [ ] Filter by: fit tier (Strong/Moderate/Low), outreach status
    - [ ] Click row → navigates to `/accounts/{id}`
    - [ ] "Graduate" action button on rows with status=replied (calls POST /accounts/{id}/graduate)
    - [ ] Empty state: "No scored leads yet. Run /gtm-leads-pipeline in Claude Code to get started."

#### Frontend: Navigation

- **REQ-12**: Sidebar navigation updates
  - **Acceptance Criteria:**
    - [ ] "Accounts" nav item added to sidebar with `Building2` icon, links to `/accounts`
    - [ ] "Pipeline" nav item added to sidebar with `TrendingUp` icon, links to `/pipeline`
    - [ ] Nav items appear between "Library" and "Email" in the sidebar
    - [ ] Active state highlights correctly when on `/accounts/*` or `/pipeline/*`
    - [ ] Pulse feed appears as a widget/section on the Briefing page (home) when Revenue focus is active

### Should Have

- **REQ-13**: Pulse feed component on Briefing page
  - **Acceptance Criteria:**
    - [ ] When user's active focus is "Revenue", Briefing page shows a "Revenue Pulse" section above existing briefing cards
    - [ ] Shows top 5 signals from Pulse API (REQ-08)
    - [ ] Each signal is a clickable card linking to the relevant account
    - [ ] Signal cards show: priority icon (color-coded), account name, signal description, time
    - [ ] "View all" link to dedicated `/pulse` page (future)

- **REQ-14**: Account graduation automation
  - **Acceptance Criteria:**
    - [ ] When outreach_activities.status is updated to 'replied', check if account.status is 'prospect'
    - [ ] If yes, auto-update account.status to 'engaged'
    - [ ] Log a context_entry with source='system', detail='auto-graduated', content describing the graduation trigger
    - [ ] This runs as a DB trigger or in the PATCH /outreach/{id} endpoint handler

- **REQ-15**: Company name normalization utility
  - **Acceptance Criteria:**
    - [ ] Python function `normalize_company_name(name: str) -> str` in a shared utils module
    - [ ] Strips suffixes: Inc, Inc., LLC, Corp, Corporation, Ltd, Ltd., Co, Co., Group, LP, LLP, PLC (case-insensitive)
    - [ ] Strips leading "The "
    - [ ] Collapses whitespace, strips leading/trailing whitespace
    - [ ] Lowercases for comparison (returns original casing for display)
    - [ ] Used by seed-crm command and by future skill integrations for dedup

### Won't Have (this version)

- Custom pipeline stages (fixed: scored → sent → awaiting → replied → graduated)
- Calendar integration for auto-detecting meetings with accounts
- Email sync / passive inbox capture (only skill-generated outreach)
- Mobile-optimized views
- Slack/email notification delivery for Pulse signals
- Kanban drag-and-drop for Pipeline (table view only)
- Bulk outreach sending from Pipeline UI
- Account merge/dedup UI (handled by normalization in seed command)

---

## Schema

### accounts

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | NO | gen_random_uuid() | PK |
| tenant_id | UUID | NO | — | FK tenants.id |
| name | TEXT | NO | — | Company name (display) |
| domain | TEXT | YES | — | Website domain (e.g., trustlayer.io) |
| status | TEXT | NO | 'prospect' | prospect, engaged, customer, churned, archived |
| fit_score | INTEGER | YES | — | 0-100 from gtm-company-fit-analyzer |
| fit_tier | TEXT | YES | — | Strong Fit, Moderate Fit, Low Fit, No Fit |
| focus_id | UUID | YES | — | FK focuses.id |
| source | TEXT | YES | — | Skill/pipeline that created this |
| metadata_ | JSONB | NO | '{}' | industry, size, HQ, description, logo_url, etc. |
| created_at | TIMESTAMPTZ | NO | now() | |
| updated_at | TIMESTAMPTZ | NO | now() | |

**Constraints:** `UNIQUE (tenant_id, name)`
**Indexes:** `(tenant_id)`, `(tenant_id, status)`, `(tenant_id, focus_id)`

### account_contacts

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | NO | gen_random_uuid() | PK |
| account_id | UUID | NO | — | FK accounts.id |
| tenant_id | UUID | NO | — | FK tenants.id |
| name | TEXT | NO | — | Contact full name |
| title | TEXT | YES | — | Job title |
| email | TEXT | YES | — | Email address |
| linkedin_url | TEXT | YES | — | LinkedIn profile URL |
| role | TEXT | NO | 'other' | primary, technical, executive, champion, other |
| last_interaction_at | TIMESTAMPTZ | YES | — | Denormalized for sort |
| metadata_ | JSONB | NO | '{}' | Degrees, location, notes, etc. |
| created_at | TIMESTAMPTZ | NO | now() | |
| updated_at | TIMESTAMPTZ | NO | now() | |

**Indexes:** `(account_id)`, `(tenant_id)`

### outreach_activities

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | NO | gen_random_uuid() | PK |
| account_id | UUID | NO | — | FK accounts.id |
| contact_id | UUID | NO | — | FK account_contacts.id |
| tenant_id | UUID | NO | — | FK tenants.id |
| user_id | UUID | NO | — | FK profiles.id (which founder) |
| channel | TEXT | NO | — | email, linkedin |
| direction | TEXT | NO | — | outbound, inbound |
| status | TEXT | NO | 'drafted' | drafted, sent, delivered, replied, bounced, failed |
| subject | TEXT | YES | — | Email subject line |
| body | TEXT | YES | — | Email body or message content |
| linkedin_message | TEXT | YES | — | LinkedIn connection note / DM |
| sent_at | TIMESTAMPTZ | YES | — | When sent |
| replied_at | TIMESTAMPTZ | YES | — | When reply received |
| metadata_ | JSONB | NO | '{}' | fit_score_at_send, campaign_source, error_reason |
| created_at | TIMESTAMPTZ | NO | now() | |
| updated_at | TIMESTAMPTZ | NO | now() | |

**Indexes:** `(account_id)`, `(tenant_id, status)`, `(contact_id)`

### context_entries (modified)

| Column | Type | Change |
|--------|------|--------|
| account_id | UUID | ADD — nullable FK to accounts.id |

**Index:** `(account_id) WHERE account_id IS NOT NULL`

---

## Edge Cases & Error States

| Scenario | Expected Behavior |
|----------|-------------------|
| Duplicate company name on create | Return 409 Conflict with existing account ID. Frontend shows "Account already exists" with link to it. |
| Account with no contacts | Show account detail with empty contacts panel and message "No contacts discovered yet. Run company research to find decision makers." |
| Account with no outreach | Timeline shows only context entries and documents. Pipeline shows "Not contacted" status. |
| Outreach activity for contact that was deleted | FK constraint prevents this. Contact delete blocked if outreach exists. |
| Seed command run twice | Idempotent — skips existing accounts (matched by normalized name), skips existing outreach (matched by contact + channel + sent_at), prints "X skipped, Y created" |
| Company name variants in seed data | Normalization function handles: "RMR Group" and "RMR" → same account. "Suffolk Construction" and "Suffolk Construction Co." → same account. |
| Context entry with no identifiable company | `account_id` stays NULL. Entry still visible in global context search but not on any account timeline. |
| Pulse API when no data exists | Returns empty signals array. Frontend shows "No signals yet. Your revenue pulse will come alive as you run skills." |
| Account graduated but has no context entries | Valid state — account appears in Accounts list with empty timeline. Prompt: "Start building intelligence — run meeting prep or company research." |
| Pipeline with 0 prospects | Empty state: "Pipeline is empty. Run /gtm-leads-pipeline to score and import companies." |

---

## Data Migration: `flywheel db seed-crm`

### Overview

A CLI command that reads existing GTM data files and populates the new CRM tables. Designed to run once during setup, idempotent for re-runs.

### Input Files

| Source | Path | What It Provides |
|--------|------|-----------------|
| Master workbook | `~/.claude/gtm-stack/gtm-leads-master.xlsx` | Company names, scores, tiers, contacts, industry tags |
| Outreach tracker | `~/.claude/gtm-stack/outreach-tracker.csv` | Outreach history with status, dates, messages |
| Pipeline runs | `~/.claude/gtm-stack/pipeline-runs.json` | Run metadata (source, filters, counts, scored CSV paths) |
| Scored CSVs | Paths from pipeline-runs.json (~/Downloads/*.csv) | Full lead data: DM_Name, DM_Title, DM_Email, DM_LinkedIn, Score, Tier, Rationale, Industry_Tag |
| Context entries | PostgreSQL context_entries table | Existing entries to backfill account_id |

### Process Steps

**Step 1: Build company registry (accounts)**
1. Read `gtm-leads-master.xlsx` "Company Summary" tab for company names + best score + industry
2. Read all scored CSVs for additional companies not in master
3. Read `outreach-tracker.csv` for companies not in either
4. For each company: `normalize_company_name()` → dedup by normalized form
5. INSERT into `accounts`: name (original casing from first occurrence), domain (extracted from Company_Website column if available), fit_score (best score seen), fit_tier (from best score), status ('prospect' for all, unless outreach has replied status → 'engaged'), source (pipeline run source), metadata (industry, location, est_employees)

**Step 2: Create contacts (account_contacts)**
1. Read scored CSVs for DM fields: DM_Name (or Name), DM_Title (or Title), DM_Email (or Email), DM_LinkedIn (or LinkedIn_URL)
2. Read `outreach-tracker.csv` for Name, First_Name, Email, Title, Company
3. Dedup contacts by (account_id, normalized name)
4. INSERT into `account_contacts`: link to account by company name match, set role='primary' for first contact per account

**Step 3: Create outreach activities (outreach_activities)**
1. Read `outreach-tracker.csv` row by row
2. Find matching account (by normalized company name)
3. Find matching contact (by name within account)
4. For each row with Email_Sent='Yes': create outreach_activity with channel='email', direction='outbound', status='sent', sent_at=Email_Sent_Date
5. For each row with LinkedIn_Status='SENT': create outreach_activity with channel='linkedin', direction='outbound', status='sent', sent_at=LinkedIn_Date
6. Map statuses: SENT→sent, PENDING→drafted, NOT_FOUND→failed, ALREADY_CONNECTED→delivered
7. Store Email_Subject, Email_Body in the activity if available (may need to read from scored CSV draft columns)

**Step 4: Backfill context entries**
1. Query all `context_entries` where `account_id IS NULL` and `file_name IN ('contacts.md', 'insights.md', 'action-items.md', 'competitive-intel.md', 'objections.md', 'pain-points.md')`
2. For each entry, scan `content` for company names from the accounts registry
3. Match using normalized substring search (case-insensitive)
4. If exactly one account matches, SET `account_id`
5. If multiple accounts match, skip (ambiguous — log warning)
6. If no match, skip (account not in CRM yet)

**Step 5: Store pipeline run metadata**
1. Read `pipeline-runs.json`
2. Store as metadata on affected accounts: `metadata_.pipeline_runs = [{run_id, date, source}]`

### CLI Interface

```
flywheel db seed-crm \
  --tenant-id <uuid> \
  --user-id <uuid> \
  [--gtm-dir ~/.claude/gtm-stack] \
  [--dry-run]
```

- `--tenant-id` (required): which tenant to scope all inserts to
- `--user-id` (required): which user created the outreach (profiles.id)
- `--gtm-dir` (optional): path to GTM stack directory, defaults to `~/.claude/gtm-stack`
- `--dry-run` (optional): print what would be created without writing to DB

### Company Name Normalization

```python
import re

_SUFFIXES = re.compile(
    r',?\s*\b(Inc\.?|LLC|Corp\.?|Corporation|Ltd\.?|Co\.?|Group|LP|LLP|PLC|SA|GmbH|AG|NV|BV)\b\.?\s*$',
    re.IGNORECASE,
)
_THE_PREFIX = re.compile(r'^The\s+', re.IGNORECASE)

def normalize_company_name(name: str) -> str:
    """Normalize company name for deduplication comparison."""
    name = name.strip()
    name = _SUFFIXES.sub('', name)
    name = _THE_PREFIX.sub('', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name.lower()
```

---

## Alembic Migration: `027_crm_tables`

```python
revision = "027_crm_tables"
down_revision = "026_docs_storage_nullable"
```

### upgrade()

```sql
-- 1. Create accounts table
CREATE TABLE accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            TEXT NOT NULL,
    domain          TEXT,
    status          TEXT NOT NULL DEFAULT 'prospect',
    fit_score       INTEGER,
    fit_tier        TEXT,
    focus_id        UUID REFERENCES focuses(id),
    source          TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE INDEX idx_accounts_tenant ON accounts(tenant_id);
CREATE INDEX idx_accounts_status ON accounts(tenant_id, status);
CREATE INDEX idx_accounts_focus ON accounts(tenant_id, focus_id) WHERE focus_id IS NOT NULL;

ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts FORCE ROW LEVEL SECURITY;
CREATE POLICY accounts_tenant_isolation ON accounts
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON accounts TO app_user;

-- 2. Create account_contacts table
CREATE TABLE account_contacts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    name                TEXT NOT NULL,
    title               TEXT,
    email               TEXT,
    linkedin_url        TEXT,
    role                TEXT NOT NULL DEFAULT 'other',
    last_interaction_at TIMESTAMPTZ,
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_account_contacts_account ON account_contacts(account_id);
CREATE INDEX idx_account_contacts_tenant ON account_contacts(tenant_id);

ALTER TABLE account_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_contacts FORCE ROW LEVEL SECURITY;
CREATE POLICY account_contacts_tenant_isolation ON account_contacts
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON account_contacts TO app_user;

-- 3. Create outreach_activities table
CREATE TABLE outreach_activities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    contact_id      UUID NOT NULL REFERENCES account_contacts(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID NOT NULL REFERENCES profiles(id),
    channel         TEXT NOT NULL,
    direction       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'drafted',
    subject         TEXT,
    body            TEXT,
    linkedin_message TEXT,
    sent_at         TIMESTAMPTZ,
    replied_at      TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_outreach_account ON outreach_activities(account_id);
CREATE INDEX idx_outreach_contact ON outreach_activities(contact_id);
CREATE INDEX idx_outreach_status ON outreach_activities(tenant_id, status);
CREATE INDEX idx_outreach_sent ON outreach_activities(sent_at DESC) WHERE sent_at IS NOT NULL;

ALTER TABLE outreach_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE outreach_activities FORCE ROW LEVEL SECURITY;
CREATE POLICY outreach_tenant_isolation ON outreach_activities
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON outreach_activities TO app_user;

-- 4. Add account_id to context_entries
ALTER TABLE context_entries ADD COLUMN account_id UUID REFERENCES accounts(id);
CREATE INDEX idx_context_entries_account ON context_entries(account_id) WHERE account_id IS NOT NULL;
```

### downgrade()

```sql
DROP INDEX IF EXISTS idx_context_entries_account;
ALTER TABLE context_entries DROP COLUMN IF EXISTS account_id;

DROP POLICY IF EXISTS outreach_tenant_isolation ON outreach_activities;
DROP TABLE IF EXISTS outreach_activities;

DROP POLICY IF EXISTS account_contacts_tenant_isolation ON account_contacts;
DROP TABLE IF EXISTS account_contacts;

DROP POLICY IF EXISTS accounts_tenant_isolation ON accounts;
DROP TABLE IF EXISTS accounts;
```

---

## API Endpoints Summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/v1/accounts/ | tenant | List accounts (paginated, filterable) |
| POST | /api/v1/accounts/ | tenant | Create account |
| GET | /api/v1/accounts/{id} | tenant | Account detail with contacts, timeline summary, intel |
| PATCH | /api/v1/accounts/{id} | tenant | Update account fields |
| POST | /api/v1/accounts/{id}/graduate | tenant | Promote to engaged status |
| GET | /api/v1/accounts/{id}/contacts | tenant | List contacts for account |
| POST | /api/v1/accounts/{id}/contacts | tenant | Add contact |
| PATCH | /api/v1/accounts/{id}/contacts/{cid} | tenant | Update contact |
| DELETE | /api/v1/accounts/{id}/contacts/{cid} | tenant | Remove contact |
| GET | /api/v1/accounts/{id}/outreach | tenant | List outreach for account |
| POST | /api/v1/accounts/{id}/outreach | tenant | Create outreach activity |
| PATCH | /api/v1/outreach/{id} | tenant | Update outreach status |
| GET | /api/v1/accounts/{id}/timeline | tenant | Unified activity timeline |
| GET | /api/v1/pipeline/ | tenant | Pipeline view (prospect accounts with outreach status) |
| GET | /api/v1/pulse/ | tenant | Priority-ranked signal feed |

---

## Constraints

- **No manual data entry forms.** Accounts, contacts, and outreach are created by skills and seed commands, not by users filling in forms. The create/update APIs exist for skills and automation, not for a "New Account" form in the UI. (User's decision: "This is a view into intelligence, not a database to fill.")
- **Company-first, not person-first.** Every contact belongs to an account. There is no standalone contact view. (User's decision from brainstorm Round 5.)
- **Clean break migration.** The seed command creates fresh data. No backward compatibility with old context entry formats. (User's decision: "We can afford to break.")
- **Existing API patterns.** All new endpoints follow the established pagination pattern (offset/limit, max 100, has_more), auth pattern (require_tenant + get_tenant_db), and RLS pattern (ENABLE + FORCE + policy + GRANT).
- **Design system.** All new frontend pages use existing design tokens (Inter font, #E94D35 coral accent, 12px radius, warm tints). Follow DocumentLibrary and BriefingPage patterns for layout.

## Anti-Requirements

- This is NOT a general-purpose CRM. No deals/opportunities table, no revenue forecasting, no sales stages beyond the fixed pipeline.
- This is NOT a communication tool. No email sending from the UI, no LinkedIn automation. Outreach happens through Claude Code skills.
- This does NOT replace the context store. Context entries remain the source of truth for intelligence. Accounts are an aggregation layer on top.
- This does NOT require calendar integration. Meeting-related signals come from meeting-prep and meeting-processor skill runs, not from Google Calendar sync.

## Open Questions

- [ ] How should "next action due" be derived from context entries? Parse dates from action-items.md content? Or add a structured `due_date` field to context entries?
- [ ] Should the seed command also import `sender-profile.md` data into a dedicated context file, or is it already in the context store via gtm-my-company?
- [ ] Should Pipeline show individual contacts or accounts? (Spec says accounts, but outreach is per-contact — may need expandable rows.)
- [ ] Graduation heuristic: any reply = graduate, or only positive replies? (V1: any reply = graduate. Iterate based on usage.)

## Artifacts Referenced

- CONCEPT-BRIEF-ai-native-crm.md — 5-round brainstorm with advisory board
- ~/.claude/gtm-stack/ — outreach-tracker.csv, pipeline-runs.json, gtm-leads-master.xlsx, sender-profile.md
- backend/src/flywheel/db/models.py — existing ContextEntry, Document, SkillRun models
- backend/src/flywheel/api/ — existing router patterns (context.py, documents.py, skills.py)
- frontend/src/features/documents/ — existing Library UI pattern (DocumentLibrary, DocumentViewer)
- frontend/src/features/navigation/components/AppSidebar.tsx — sidebar nav structure
- Competitor research: Rox (agent swarm, clever columns), Day.ai (conversation-first), Attio (flexible objects), Affinity (relationship scoring)

---

## Gaps Found During Generation

1. **Major: Timeline item types need discriminator.** The timeline API mixes outreach, context entries, and documents. The frontend needs a `type` field to render each differently. Specified in REQ-07 as `type (outreach|context|document)`. Confirm this covers all possible timeline item sources.

2. **Major: Pulse "meeting_prep_ready" signal requires calendar data.** Without calendar integration (explicitly in Won't Have), this signal type cannot fire. Remove from V1 Pulse, or implement as "upcoming meetings from context_entries with meeting-related source tags."

3. **Minor: Pipeline "days since last action" computation.** Needs to compare current time against either sent_at (if outreach exists) or created_at (if only scored). Not complex but worth confirming the business rule.

4. **Minor: Outreach body storage.** The outreach-tracker.csv doesn't store email body or LinkedIn message text. The scored CSVs have Email_Subject, Email_Body, LinkedIn_DM columns. The seed command needs to join these — match by contact name + company across files. May not always join cleanly.
