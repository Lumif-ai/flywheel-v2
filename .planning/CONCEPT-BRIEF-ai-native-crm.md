# Concept Brief: AI-Native CRM — Accounts, Pipeline & Pulse

> Generated: 2026-03-26
> Mode: Deep (5 rounds)
> Rounds: 5 deliberation rounds
> Active Advisors: Bezos, Chesky, PG, Rams, Ive, Hickey, Vogels, Carmack, Torvalds, Helmer (core) + Thompson, Christensen, Tufte, Patil (situational) + Regulatory (domain)
> Artifacts Ingested: GTM skill stack (6 skills), context store schema, competitor research (Rox, Day.ai, Attio, Folk, Affinity, Lightfield), existing data (132+ scored companies, 43 outreach attempts, 6 pipeline runs)

## Problem Statement

Three founders at Lumif.ai run GTM outreach through Claude Code skills that scrape leads, score companies for fit, draft personalized messages, and send via browser. The intelligence this produces — fit scores, company research, meeting insights, outreach history, commitments made — lives in scattered CSV files and a compounding context store with no unified UI. Founders lose track of follow-ups, can't see each other's engagement history, and have no company-level view of "where are we with this account?" The data compounds but the visibility doesn't.

*Sharpened from original framing:* The original ask was "mini CRM in the Revenue focus area." Through deliberation, the board surfaced that (a) this is company-first not person-first, (b) the CRM is a view into intelligence that already exists, not a new database to fill, and (c) Relationships (now "Accounts") should be a top-level surface across all focus areas, not buried inside Revenue.

## Proposed Approach

Build three new surfaces in Flywheel that turn the compounding context store and skill execution pipeline into a company-centric intelligence system:

1. **Accounts** — A top-level nav item showing every company the team is engaged with. Company-first detail view aggregating all contacts, interaction timeline, commitments, intel, and linked documents. Populated entirely by skill execution — zero manual data entry.

2. **Pipeline** — A top-level nav item showing the GTM outreach funnel. Companies flow from scored → contacted → replied → graduated (to Accounts). Replaces the Excel/CSV workflow with fit scores, draft messages, and outreach status in one view.

3. **Pulse** — The daily intelligence feed (home for Revenue focus). Surfaces signals: new replies, overdue follow-ups, meeting prep ready, cold outreach needing a bump, new companies scored. Action-oriented, not dashboard-oriented.

**The core insight:** Flywheel doesn't ingest data and then build intelligence (like Rox/Day.ai). It already HAS the intelligence from skill execution. The CRM is a **view layer over accumulated intelligence**, not a new system of record.

## Key Decisions Made

| Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|----------|-----------------|------------------|-------------------|---------------------|
| Company-first vs person-first | Company-first (Accounts) | "We deal by company name — Phillips project, Satguru, RMR. Person belongs to company." | Christensen (B2B JTBD: unit of work is the account), Bezos (working backwards from how founders actually talk) | Person-first CRM (how Affinity/Folk work) — rejected because B2B engagement is account-level |
| Relationships scope | Top-level nav, not inside Revenue | "Separated is better, so can focus when there" | Hickey (don't complect — investors aren't revenue), Rams (one view, focus areas as filters) | Nested inside Revenue focus — rejected because advisors/investors/partners would need separate views |
| Data model: breaking vs additive migration | Clean break, seed data later | "We can afford to break. I have everything in local context store." | PG (3 users, no legacy debt), Carmack (kill the null-handling branch), Torvalds (non-nullable where it matters) | Nullable account_id with gradual migration — rejected because it creates permanent second-class citizen problem |
| Pipeline vs Accounts as separate surfaces | Two separate views with graduation flow | "Two flows: outreach/follow-ups, and actively engaged people" | Hickey (different things being complected), Christensen (different JTBD: triage/execute vs nurture/track) | Single unified CRM view — rejected because pre-relationship outreach and active engagement have fundamentally different workflows |
| Feed vs Table | Both — Pulse (feed) + Pipeline/Accounts (structured) | Board consensus after tension surfaced | Chesky (feed for daily action), Tufte (table for portfolio assessment), Rams (both serve different temporal needs) | Feed-only (Day.ai style) or Table-only (Salesforce style) |
| Outreach data: CSV vs DB | Move to database (outreach_activities table) | Replaces flat file tracker with relational data for joins, timeline, multi-founder visibility | Patil (CSV was fine for Claude Code; web app needs relational data) | Keep CSV tracker — rejected because can't query, join, or show in timeline |

## Advisory Analysis

### Theme 1: Intelligence as View Layer (Bezos, PG, Patil)

The fundamental architectural insight is that Flywheel's CRM is downstream of value creation, not upstream. Every competitor starts by ingesting data and building intelligence on top. Flywheel already has the intelligence from skill execution — the CRM surfaces it. This means zero data entry, which is the #1 complaint about every traditional CRM. The "manual version" (Excel/CSV) already proves demand; the question is what view makes the workflow 10x better.

### Theme 2: The Compounding Moat (Helmer, Thompson, Hickey)

The competitive moat is **Process Power** — the compounding loop where skills produce intelligence → context store accumulates it → views surface it → views trigger more skills → intelligence deepens. Competitors can copy any single screen but not the accumulated intelligence or compounding rate. Additionally, **Switching Costs** grow with every meeting processed and every outreach tracked — the institutional memory becomes irreplaceable. **Counter-Positioning** against Salesforce/HubSpot: they can't rebuild around a knowledge graph without abandoning their field-and-form ecosystem.

### Theme 3: Company-First B2B Design (Christensen, Chesky, Tufte)

The pivot from person-first to company-first came from how founders actually talk about their work ("where are we with Suffolk?", not "where are we with Chris?"). In B2B, the account is the unit of work. Multiple contacts exist within an account. The account detail view becomes the "killer screen" — a company-level intelligence dossier showing contacts, timeline, commitments, intel, and documents, all populated by skill execution. Every pixel is earned data, not entered data.

### Theme 4: The Three Jobs (Christensen, PG, Vogels)

Three distinct jobs are currently hired to one spreadsheet: (1) Triage — which leads are worth pursuing, (2) Execute — send outreach with context in one place, (3) Follow-up — don't lose track of replies and commitments. Job 3 is where deals die. The Pipeline handles jobs 1-2, the Accounts view + Pulse feed handle job 3. The "losing track" problem is the core pain — follow-up overdue signals in Pulse are the highest-value feature.

### Situational: 11-Star Experience Design (Chesky)

- **5-star:** Dashboard showing companies and scores (current static HTML)
- **7-star:** Opening the app and seeing "3 follow-ups due, 2 warm replies, 1 meeting prep ready"
- **9-star:** Before every meeting, a briefing appears with full context from past outreach, their response, company changes, suggested talking points
- **11-star:** You never open the CRM. It messages you "Chris replied positively. Follow-up drafted. Meeting prep ready. Confirm?"
- **Shippable insight (7-9 range):** Push-based intelligence feed (Pulse) + skill triggers from account view

## Tensions Surfaced

### Tension 1: Feed vs Table
- **Chesky + Tufte** argue: Revenue intelligence should flow like a timeline — most recent signals first. Matches how founders work (reacting to signals).
- **Rams + Carmack** argue: Founders need the full portfolio at a glance — sortable, filterable. A feed buries the portfolio view.
- **Why both are right:** Different temporal needs. Daily = feed (what now?). Weekly = table (how's pipeline?).
- **User's resolution:** Build both. Pulse is the feed. Pipeline/Accounts are the structured views.
- **User's reasoning:** "Need to react to signals AND assess portfolio. Not either/or."

### Tension 2: Breaking vs Additive Migration
- **Vogels** argues: Additive migration with nullable account_id. Old entries still work. No risk.
- **PG + Carmack** argue: 3 users, can afford to break. Clean model now avoids permanent null-handling debt.
- **User's resolution:** Clean break. Seed data from local context store.
- **User's reasoning:** "We can afford to break. I have everything in my local context store."

### Unresolved Tensions
- **Pulse notification delivery:** In-app feed vs email digest vs both? Deferred to design phase.
- **Graduation automation:** How much should be automatic (reply detected → promote to Accounts) vs manual? Decided: reply + positive meeting = auto-promote, with manual override. Exact heuristics TBD.

## Moat Assessment

**Achievable powers:**
1. **Process Power** (primary) — The compounding intelligence loop (skills → context → views → skills) creates organizational knowledge that deepens with every interaction. Cannot be replicated by copying the UI.
2. **Switching Costs** (secondary) — Every meeting processed, every outreach tracked, every context entry accumulated raises the cost of leaving. After 6 months, the institutional memory is irreplaceable.
3. **Counter-Positioning** (tertiary) — Salesforce/HubSpot structurally cannot rebuild around a knowledge graph + skill execution model without abandoning their field-and-form ecosystem and partner network.

**Moat status:** Emerging — powers are achievable and the architecture enables them, but requires usage depth (more meetings, more outreach, more skill runs) to realize. The moat strengthens with every interaction.

## Competitive Landscape

| Competitor | Valuation | Core Approach | Flywheel Advantage |
|-----------|-----------|--------------|-------------------|
| **Rox** | $1.2B | Agent swarm per account, warehouse-native | Flywheel already has the agents (skills) AND the accumulated intelligence. Rox starts from scratch per customer. |
| **Day.ai** | $24M Series A | Conversation-first, self-populating from email/calendar | Flywheel populates from skill execution + web research, not just passive email ingestion. Richer intelligence. |
| **Attio** | — | Flexible objects, Notion-meets-CRM | More flexible data model but no skill execution engine. Manual enrichment vs automatic. |
| **Folk** | — | Relationship warmth, voice-preserving AI | Good for light-touch relationships. Flywheel wins on depth of intelligence per account. |
| **Affinity** | — | Network scoring for private capital | Relevant pattern (collective network) but wrong vertical. Flywheel adapts this for B2B sales: "every founder benefits from every other founder's intel." |
| **Lightfield** | — | Schema-less, builds from communications | Similar philosophy but ingests only communications. Flywheel ingests research, scoring, outreach, meetings — much richer signal set. |

**Unique positioning:** Flywheel is the only system where the CRM is a **view into intelligence produced by AI skill execution**, not a database that AI helps you fill. The intelligence exists before the CRM view does.

## Data Model

### New Tables

```sql
-- Companies the team is engaging with
CREATE TABLE accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            TEXT NOT NULL,
    domain          TEXT,
    status          TEXT NOT NULL DEFAULT 'prospect',
        -- prospect | engaged | customer | churned | archived
    fit_score       INTEGER,
    fit_tier        TEXT,
    focus_id        UUID REFERENCES focuses(id),
    source          TEXT,  -- which skill/pipeline created this
    metadata_       JSONB DEFAULT '{}',
        -- industry, size, HQ, logo_url, description, etc.
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, name)
);

-- People within accounts
CREATE TABLE account_contacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            TEXT NOT NULL,
    title           TEXT,
    email           TEXT,
    linkedin_url    TEXT,
    role            TEXT DEFAULT 'other',
        -- primary | technical | executive | champion | other
    last_interaction_at  TIMESTAMPTZ,
    metadata_       JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Outreach and communication activities (replaces CSV tracker)
CREATE TABLE outreach_activities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id),
    contact_id      UUID NOT NULL REFERENCES account_contacts(id),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID NOT NULL REFERENCES profiles(id),
    channel         TEXT NOT NULL,  -- email | linkedin
    direction       TEXT NOT NULL,  -- outbound | inbound
    status          TEXT NOT NULL DEFAULT 'drafted',
        -- drafted | sent | delivered | replied | bounced | failed
    subject         TEXT,
    body            TEXT,
    linkedin_message TEXT,
    sent_at         TIMESTAMPTZ,
    replied_at      TIMESTAMPTZ,
    metadata_       JSONB DEFAULT '{}',
        -- fit_score_at_send, campaign_source, error_reason, etc.
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Link context entries to accounts (add column)
ALTER TABLE context_entries ADD COLUMN account_id UUID REFERENCES accounts(id);
```

### RLS Policies

All new tables follow existing tenant isolation pattern:
```sql
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts FORCE ROW LEVEL SECURITY;
CREATE POLICY accounts_tenant ON accounts
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON accounts TO app_user;
-- (same pattern for account_contacts and outreach_activities)
```

### Key Indexes

```sql
CREATE INDEX idx_accounts_tenant ON accounts(tenant_id);
CREATE INDEX idx_accounts_status ON accounts(tenant_id, status);
CREATE INDEX idx_accounts_focus ON accounts(tenant_id, focus_id);
CREATE INDEX idx_account_contacts_account ON account_contacts(account_id);
CREATE INDEX idx_outreach_account ON outreach_activities(account_id);
CREATE INDEX idx_outreach_status ON outreach_activities(tenant_id, status);
CREATE INDEX idx_context_entries_account ON context_entries(account_id)
    WHERE account_id IS NOT NULL;
```

## UI Surfaces

### 1. Accounts (top-level nav)

**List view:** Table of all accounts with columns:
- Company name + domain
- Status badge (prospect/engaged/customer)
- Fit score + tier badge
- # contacts · # interactions
- Last interaction date
- Next action due (derived from action-items.md entries)
- Focus area tag

**Detail view (the killer screen):**
- Header: company name, domain, fit score, status, focus tag
- Left panel: Contacts list with roles and last interaction
- Center: Timeline of all activity — meetings, outreach, scoring, research (across all contacts, all founders)
- Right panel: Intel sidebar — industry, size, competitors, key facts from company-intel
- Bottom: Commitments (from action-items.md, meeting-processor) with due dates and status
- Action bar: [Prep for meeting] [Research company] [Draft follow-up] — each triggers a skill

### 2. Pipeline (top-level nav)

**Kanban or table view** of accounts in pre-relationship stages:
- Columns: Scored → Outreach Sent → Awaiting Reply → Replied → Graduated
- Cards show: company name, fit score/tier, contact name, days in stage, draft message preview
- Bulk actions: send outreach to selected, bump all overdue
- Filter by: fit tier, source/campaign, days in stage

### 3. Pulse (Revenue focus home / widget)

**Signal feed** sorted by priority:
- 🔴 Replies received (Pipeline → may graduate)
- 🟡 Follow-ups overdue (from Accounts commitments)
- 🟢 Meeting prep ready (upcoming meetings with known accounts)
- 🔵 New companies scored (from pipeline runs)
- ⚪ Bump suggested (silent outreach past threshold)
- Each signal links to the relevant Account or Pipeline item

## Skill Integration

### Skills that write to accounts/contacts/outreach:

| Skill | Creates Account? | Creates Contact? | Writes Outreach? | Writes Context? |
|-------|-----------------|-----------------|-----------------|----------------|
| gtm-company-fit-analyzer | Yes (prospect) | Yes (decision maker) | No | competitive-intel, icp-profiles |
| gtm-outbound-messenger | No (must exist) | No (must exist) | Yes (outbound) | contacts, insights |
| gtm-leads-pipeline | Yes (orchestrates) | Yes (orchestrates) | Yes (orchestrates) | contacts, insights, objections |
| meeting-prep | No | Updates existing | No | contacts, competitive-intel, industry-signals |
| meeting-processor | No | Updates existing | No | insights, action-items, objections, contacts |
| company-intel | Updates existing | May discover new | No | competitive-intel, positioning |
| account-research | Updates existing | Discovers new | No | contacts, competitive-intel, pain-points |

### Graduation flow:

```
Pipeline (prospect status)
    │
    ├── Reply detected (outreach_activities.status → replied)
    │   └── Auto: account.status → engaged, appears in Accounts
    │
    ├── Meeting booked (calendar event + account match)
    │   └── Auto: account.status → engaged
    │
    └── Manual promotion by founder
        └── account.status → engaged
```

## Seeding Strategy

Since we're doing a clean break, seed data from existing sources:

1. **Accounts:** Parse `gtm-leads-master.xlsx` "All Companies" tab → create account rows with fit scores
2. **Contacts:** Parse scored CSVs → create account_contacts with DM_Name, DM_Title, DM_LinkedIn, DM_Email
3. **Outreach:** Parse `outreach-tracker.csv` → create outreach_activities with status, dates, messages
4. **Context entries:** Parse existing entries in contacts.md, insights.md, etc. → backfill account_id by matching company names
5. **Pipeline runs:** Parse `pipeline-runs.json` → metadata for audit trail

## Ship Priority

1. **Accounts table + detail view** — highest value, fixes "losing track" problem
2. **Pipeline view** — replaces Excel workflow, shows outreach funnel
3. **Pulse feed** — needs both Accounts and Pipeline data to be useful
4. **Skill integration** — update skills to write to new tables (incremental, per-skill)

## Open Questions

- [ ] Pulse notification delivery: in-app only, or also email digest / Slack?
- [ ] Graduation heuristics: exact rules for auto-promoting (reply sentiment analysis? any reply = promote?)
- [ ] Account deduplication: how to handle company name variants (RMR vs RMR Group)?
- [ ] Pipeline stages: fixed (Scored → Sent → Awaiting → Replied → Graduated) or customizable?
- [ ] Offline/mobile: any need for mobile access to Pulse signals?
- [ ] Calendar integration: detect meetings with known accounts for automatic timeline entries?
- [ ] Email sync: passive capture of email threads (like Day.ai) or only skill-generated outreach?

## Recommendation

**Proceed to /spec.** The idea survived 5 rounds of advisory scrutiny with strong consensus. The data model is clean, the architecture builds on existing infrastructure (context store, skill execution, focus areas), and the competitive positioning is defensible. The concept brief is ready for specification.

Recommended spec scope: Start with Accounts (table + detail view) + data model migration + skill integration for gtm-pipeline. This alone replaces the Excel workflow and fixes the "losing track" problem.

## Artifacts Referenced

- GTM skill SKILL.md files (6 skills analyzed for data flow)
- Context store schema (backend/src/flywheel/db/models.py)
- Existing GTM data (~/.claude/gtm-stack/): outreach-tracker.csv, pipeline-runs.json, gtm-leads-master.xlsx, sender-profile.md
- Competitor research: Rox, Day.ai, Attio, Folk, Affinity, Lightfield (web research)
- Design tokens (frontend/src/lib/design-tokens.ts)
- Existing frontend surfaces: DocumentLibrary, BriefingFullViewer, BriefingPage
