# Concept Brief: Intelligence Flywheel Engine

> Generated: 2026-03-28
> Mode: Deep (4 rounds)
> Rounds: 4
> Active Advisors: Bezos, Chesky, Paul Graham, Dieter Rams, Jony Ive, Rich Hickey, Werner Vogels, John Carmack, Linus Torvalds, Hamilton Helmer, Ben Thompson, Clayton Christensen, DJ Patil, Integration Reality
> Artifacts Ingested: existing meeting-processor SKILL.md (v2.3), meeting_processor.py engine, skill_executor.py (company-intel pattern), context store API, integration credentials model, Granola/Fathom/Fireflies API research

## Problem Statement

Flywheel has five rich relationship surfaces (Pipeline, Prospects, Customers, Advisors, Investors) — but they're only as valuable as the intelligence that fills them. Today, the context store is populated primarily by document uploads and web crawls. The highest-value intelligence source — **conversations** (meetings, emails, Slack threads) — doesn't flow into the system automatically.

Every meeting a founder takes generates pain points, competitor mentions, buying signals, action items, contact discoveries, and relationship progression signals. Today this intelligence lives in transcript files, email inboxes, and the founder's head. It decays within days.

The Intelligence Flywheel Engine turns every conversation into structured CRM intelligence that compounds over time. Each source connected makes every relationship page richer, every meeting prep sharper, and every pipeline signal more accurate.

## Proposed Approach

Build a **unified intelligence ingestion pipeline** with thin provider adapters and a shared extraction core. The pipeline has three stages that form a self-reinforcing loop:

```
INGEST → ENRICH → PREPARE
  ↑                    ↓
  └────────────────────┘
```

**INGEST**: Connect conversation sources (Granola, Fathom, Fireflies, Gmail, Slack, Drive). Each source syncs through a common `IntelligenceSource` adapter. Raw content flows through: classify → extract 9 insight types → write to context store → auto-link to accounts and contacts.

**ENRICH**: Every ingested source enriches the relationship graph. Timeline tabs fill with meeting entries. Intelligence tabs surface pain points, competitor mentions, buying signals. People tabs discover new contacts. Signal badges increment. Account-level AI synthesis gets smarter with more data points feeding it.

**PREPARE**: Meeting prep reads the enriched context store and produces briefings with full relationship history, known pain points, open action items, and competitive positioning. The founder walks into every meeting fully informed. That meeting produces richer intelligence. The flywheel spins faster.

### Architecture: Shared Pipeline, Thin Adapters

```
IntelligenceSource (adapter interface)
  ├── connect(credentials) → Integration row
  ├── sync(since: datetime) → RawItem[]
  └── get_content(item_id) → { text, participants, metadata }

Provider Adapters:
  ├── GranolaAdapter    (REST API, Bearer token)
  ├── FathomAdapter     (REST API, Bearer token)
  ├── FirefliesAdapter  (GraphQL, Bearer token)
  ├── GmailAdapter      (already exists — email sync)
  ├── SlackAdapter      (future)
  └── DriveAdapter      (future)

Shared Pipeline:
  RawItem → Classifier → TypedItem → Extractor → ContextEntry[]
                                        ↓
                                  Meeting/Email row
                                        ↓
                                  Account auto-link
                                        ↓
                                  Signal badge update
```

The adapter does I/O. The pipeline does intelligence. Adding a new source is just a new adapter — same classifier, same extractor, same context store writes, same relationship enrichment.

### Data Model: Meetings as First-Class Entities

```sql
CREATE TABLE meetings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID NOT NULL REFERENCES users(id),

    -- Source tracking
    provider        TEXT NOT NULL,           -- granola, fathom, fireflies, manual-upload
    external_id     TEXT,                    -- provider's meeting ID (dedup key)

    -- Meeting metadata
    title           TEXT,
    meeting_date    TIMESTAMPTZ NOT NULL,
    duration_mins   INT,
    attendees       JSONB,                   -- [{email, name, role, is_external}]

    -- Content
    transcript_url  TEXT,                    -- Supabase Storage reference (not inline)
    ai_summary      TEXT,                    -- Provider's AI summary (Granola, Fathom, etc.)

    -- Extracted intelligence (read-path cache, not source of truth)
    summary         JSONB,                   -- {tldr, key_decisions, action_items, attendee_roles, pain_points}
    meeting_type    TEXT,                    -- discovery, prospect, advisor, investor, internal, etc.

    -- Relationship linking
    account_id      UUID REFERENCES accounts(id),  -- auto-inferred from attendee domains

    -- Processing tracking
    skill_run_id    UUID REFERENCES skill_runs(id),
    processed_at    TIMESTAMPTZ,
    processing_status TEXT DEFAULT 'pending', -- pending, processing, complete, failed, skipped

    -- Standard fields
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ              -- soft delete
);

-- Dedup: one meeting per provider + external_id per tenant
CREATE UNIQUE INDEX idx_meetings_dedup ON meetings(tenant_id, provider, external_id)
    WHERE external_id IS NOT NULL;

-- Fast queries by account for relationship timeline
CREATE INDEX idx_meetings_account ON meetings(account_id, meeting_date DESC)
    WHERE deleted_at IS NULL;

-- RLS policy: tenant_id = current_setting('app.tenant_id')::uuid
```

### Processing Flow

1. **Sync trigger** (periodic or manual): SkillRun of type `meeting-sync` calls adapter's `list_meetings(since=last_sync)`
2. **Dedup**: Match `external_id` against existing meetings table — skip already-seen
3. **Create meeting rows**: Insert with `processing_status='pending'`
4. **Auto-filter**: Apply user's processing rules — mark skipped meetings as `processing_status='skipped'`
5. **Process each meeting**: Individual SkillRun per meeting:
   - Fetch full transcript via adapter's `get_content()`
   - Store transcript in Supabase Storage
   - Classify meeting type (8 types)
   - Extract 9 insight types via LLM
   - Write ContextEntries to 7 context files
   - Auto-link to account (attendee domain → accounts.domain)
   - Auto-discover contacts (attendee info → contacts on account)
   - Update meeting row: `summary` JSONB, `processed_at`, `processing_status='complete'`
   - Emit SSE events for real-time UI feedback
6. **Post-processing**: Update signal badges, trigger AI synthesis refresh if account has new data

### 9 Intelligence Extraction Types (from existing SKILL.md)

1. **Hair on Fire Problems** — severity 1-5, painkiller vs vitamin classification
2. **ICP Discovery Signals** — confirm existing or reveal new customer segments
3. **Workflow Details** — tools, steps, time, team size, costs mentioned
4. **Buying Signals & Willingness to Pay** — budget, timeline, decision process
5. **Competitor Intelligence** — tools mentioned, pricing, switching reasons
6. **Objections & Resistance** — blockers, regulatory, political concerns
7. **Quotable Moments** — exact phrases for pitch decks, marketing
8. **Cross-Call Patterns** — "3rd prospect this month mentioning compliance pain"
9. **Follow-up Linking** — relationship progression, prior meeting references

### 7 Context Store Write Targets

| File | What gets written | Source meeting types |
|------|-------------------|---------------------|
| competitive-intel.md | Competitor mentions, pricing, switching signals | discovery, expert, prospect |
| pain-points.md | Problems with severity, speaker attribution | discovery, expert, prospect, customer-feedback |
| icp-profiles.md | Company segments, buying signals, decision-maker info | discovery, prospect |
| contacts.md | Per-person: name, title, company, role, notes | all external meetings |
| insights.md | Strategic takeaways, quotable moments, cross-call patterns | all meetings |
| action-items.md | Commitments with owners, due dates | all meetings |
| product-feedback.md | Feature requests, reactions, demo feedback | customer-feedback, investor-pitch |

### Team Visibility & Privacy Model

The extraction step is the privacy boundary. Raw content goes in private, structured intelligence comes out shared.

```
Private (user-scoped)              Shared (tenant-scoped)
─────────────────────              ─────────────────────
Email bodies/threads         →→→   Extracted intel (ContextEntries)
Full meeting transcripts     →→→   Extracted intel (ContextEntries)
Slack DMs                    →→→   Extracted intel (ContextEntries)
Draft replies                      Account pages, relationship surfaces
Meeting prep briefings             Pipeline, signals, contacts
```

**Per-table visibility rules:**

| Data | Visibility | RLS Rule |
|------|-----------|----------|
| `context_entries` (extracted intel) | All team members | `tenant_id` only — this IS the flywheel |
| `accounts`, `contacts` | All team members | `tenant_id` only |
| Meeting metadata (title, date, attendees, type, account link, `summary` JSONB) | All team members | `tenant_id` only |
| Meeting transcript (full text via `transcript_url`) | Meeting owner only | `tenant_id + user_id` |
| `emails`, `email_drafts` | Email owner only | `tenant_id + user_id` |
| `skill_runs` | Run owner only | `tenant_id + user_id` |
| Meeting prep briefings | Requester only | `tenant_id + user_id` |

**What a team member sees on a relationship page:**
- Timeline: "Meeting with Acme — Discovery call" with date, attendees, type, tldr — from ANY team member's meetings. But NOT the full transcript unless it was their own meeting.
- Intelligence: All extracted pain points, buying signals, competitor mentions — regardless of whose meeting produced them.
- Contacts: All discovered contacts from all team members' meetings.
- Action items: All, with owner attribution ("Sarah owes them SOC2 docs by Friday").

**What they DON'T see:**
- Other users' email threads, drafts, or inbox
- Other users' full meeting transcripts
- Other users' meeting prep briefings

**Implementation:** Additive RLS policies using `app.user_id` on private tables. The existing `app.tenant_id` RLS on shared tables stays unchanged. No rearchitecting required — it's new policies on specific tables.

### Auto-Processing Rules

**Default behavior**: auto-process all meetings with external attendees.

**User-configurable skip rules** (stored in Integration `settings` JSONB):
- Skip specific meetings (one-time, from meetings list UI)
- Skip by meeting type: "don't process investor meetings"
- Skip by attendee domain: "skip all @family.com meetings"
- Skip internal-only meetings (default: ON)
- Skip recurring meetings with same attendee set (optional)

### Account Auto-Linking

When a meeting is processed:
1. Extract attendee email domains
2. Match domains against `accounts.domain` (fuzzy: strip www, handle subdomains)
3. If match found → link `meeting.account_id` to existing account
4. If no match → **auto-create a prospect account** from meeting metadata (company name inferred from domain, contacts from attendees)
5. Add meeting as timeline entry on the account
6. Update relationship signal count

This means connecting Granola and syncing immediately populates Pipeline and Relationship pages with meeting data — zero manual data entry.

### Relationship Surface Enrichment

After meeting processing, the existing CRM surfaces automatically show richer data:

| Surface | What changes |
|---------|-------------|
| **Timeline tab** | Meeting entries appear with date, type badge, attendees, tldr |
| **Intelligence tab** | Pain points, buying signals, competitor mentions from meetings |
| **People tab** | New contacts discovered from meeting attendees |
| **Commitments tab** | Action items with owners and due dates from meetings |
| **AI Summary** | Synthesis incorporates meeting-extracted intelligence |
| **Signal badges** | New meetings increment signal count on sidebar |
| **Pipeline grid** | Last Action column reflects meeting dates |

### Meeting Prep (Closing the Loop)

The meeting-prep skill (already exists as SKILL.md v4.0) reads the enriched context store to produce briefings. After the intelligence engine has processed 10+ meetings:

- Briefing includes full relationship history with the account
- Known pain points from previous meetings are listed
- Open action items (yours and theirs) are surfaced
- Competitive positioning based on what competitors they've mentioned
- Suggested questions based on gaps in your intelligence

The founder walks in prepared. The meeting produces richer intelligence. The flywheel spins.

### Tiered Processing Cost Model

| Tier | Model | Cost/meeting | When |
|------|-------|-------------|------|
| Quick classify | Haiku | ~$0.01 | Every synced meeting — determines type and whether to deep-process |
| Deep extract | Sonnet | ~$0.15-0.25 | External meetings that pass filter rules |
| Cross-reference | Local | ~$0 | Pattern matching against existing context (no LLM) |

Estimated cost: ~$0.20/meeting average. 15 meetings/week = ~$12/month/user for meetings alone. Manageable, scales with user's plan tier.

## Key Decisions Made

| Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|----------|-----------------|------------------|-------------------|---------------------|
| Pipeline scope | Multi-source intelligence engine, not just meetings | "We already have email, Slack for sure, support tickets maybe" — this is the platform, not a feature | Hickey (composability), Thompson (aggregation) | Meeting-only processor |
| Meetings as data model | First-class `meetings` table, not just SkillRuns | Need to browse, search, link to accounts, see on timeline | Christensen (business entity), Thompson (query need) | SkillRun with JSONB metadata |
| Auto vs manual processing | Auto-process everything, user opts out specific meetings/categories | "Auto process everything, user can opt out" | Bezos (no-interface UX), PG (trust concern → solved via opt-out) | Manual trigger per meeting |
| Transcript storage | Supabase Storage (like documents), not inline in DB | Transcripts are blobs, not queryable; need for reprocessing | Carmack (don't store blobs in DB), Vogels (need for reprocessing) | TEXT column on meetings table |
| Provider abstraction | `IntelligenceSource` with 3 methods, not meeting-specific | Same pattern works for email, Slack, Drive | Hickey (right abstraction level), Integration Reality (API convergence) | `MeetingProvider` interface |
| Summary on meetings row | JSONB cache for read path, ContextEntries as source of truth | Founders need glanceable meeting view without querying 7 context files | Bezos (read-path need), Carmack (single source of truth via context store) | Dedicated columns per extract type |
| Account auto-creation | Unknown attendee domains create prospect accounts | Every external meeting is a potential relationship — don't lose it | Christensen (JTBD), Helmer (switching cost from auto-populated graph) | Manual account creation only |
| Full loop scope | Ingest → Enrich → Prepare, not just ingest | "Include the full loop — and it can also do the same for email, Slack, Drive" | Thompson (aggregation moat), Helmer (compounding value) | Just the ingestion pipeline |
| Team privacy model | Extraction is the privacy boundary: raw content private, extracted intel shared | Team members should see company intel from everyone's meetings, but never each other's emails or full transcripts | Vogels (security boundary), Bezos (team value from shared intel) | Everything private per user (kills the flywheel) / Everything shared (privacy violation) |

## Advisory Analysis

### Customer Value: The Intelligence Compounds

Bezos and Christensen converge: the value isn't in processing one meeting — it's in what happens after 50 meetings. The system knows every competitor mentioned across all calls, pain patterns across your ICP, relationship depth from meeting frequency, and which action items are stale. A founder opens a relationship page and sees the full picture without ever manually entering data. This is working backward from the real need: "I never want to walk into a meeting unprepared, and I never want to forget what was discussed."

### Architecture: Compose, Don't Complect

Hickey, Carmack, and Torvalds agree on the architecture: thin adapters that do I/O, a shared pipeline that does intelligence, and clean separation between the meeting entity (business object) and the SkillRun (processing job). The IntelligenceSource interface is deliberately minimal — 3 methods — because the intelligence extraction doesn't care where the text came from. Adding Fathom or Fireflies should be a 200-line adapter, not a new pipeline.

### Strategic Defensibility: The Moat Is Real

Helmer and Thompson identify the moat: counter-positioning (incumbents can't rebuild their data model around conversation intelligence) plus switching costs (after 6 months of processed meetings, the accumulated context graph is irreplaceable). Thompson adds the aggregation argument: Flywheel aggregates intelligence from fragmented sources into a single relationship graph. The aggregator wins because one place with everything beats five tools with pieces.

### Operational Realism: Cost and Scale

Vogels flags the cost model: auto-processing 15 meetings/week at $0.20/meeting is $12/month/user. Add emails and Slack and it grows. The tiered processing model (Haiku for classify, Sonnet for extract) keeps costs manageable. Smart filtering (skip internal, skip low-value recurring) reduces unnecessary processing. The SkillRun job queue handles scale without a custom sync daemon.

### Domain: Multi-Provider Integration

Integration Reality analysis confirms the adapter pattern: Granola, Fathom, and Fireflies all converge to list+get APIs with Bearer token auth. The abstraction isn't theoretical — it matches real API shapes. Gmail already exists. Slack and Drive follow the same pattern. The hardest part isn't the adapter — it's the account auto-linking (domain matching, fuzzy company name resolution).

## Tensions Surfaced

### Tension 1: Transcript Storage — DB vs Object Storage
- **Carmack** argues: "Transcripts are blobs. Don't put blobs in Postgres. Use object storage."
- **Vogels** argues: "You need transcripts for reprocessing when extraction logic improves."
- **Why both are right:** Transcripts need to be accessible but aren't queryable data.
- **User's resolution:** Store in Supabase Storage (like documents), reference by URL. Reprocess on demand.
- **User's reasoning:** Follows existing document upload pattern. Consistent architecture.

### Tension 2: Auto-Process vs Trust
- **Bezos** argues: "The best interface is no interface. Meetings should just appear processed."
- **PG** argues: "Users will freak out when an AI reads their investor call without asking."
- **Why both are right:** Convenience vs control is a real tradeoff.
- **User's resolution:** "Auto process everything, user can opt out."
- **User's reasoning:** Default to value. Users who care about specific meetings can exclude them. Most won't bother.

### Tension 3: Meetings Table vs SkillRun Extension
- **Carmack** argues: "Don't create a third storage concept. A meeting is just a SkillRun with metadata."
- **Christensen** argues: "Meetings are a first-class business object that need their own identity."
- **Why both are right:** Minimal schema vs proper domain modeling.
- **User's resolution:** Dedicated meetings table that references SkillRun for processing.
- **User's reasoning:** Meetings have relationships to accounts, contacts, timeline. Can't model that as SkillRun JSON.

### Unresolved Tensions
- **Reprocessing strategy**: When extraction logic improves, do you reprocess all historical meetings or just new ones? Deferred — revisit after v1 ships.
- **Cross-source dedup**: Same conversation captured in both Granola (meeting) and Gmail (follow-up email) — how to link them? Deferred — requires entity resolution work.

## Moat Assessment

**Achievable powers:**
1. **Counter-positioning** (Strong) — Incumbents (HubSpot, Salesforce) bolt on call recording but can't rebuild their data model around conversation intelligence feeding a unified relationship graph.
2. **Switching costs** (Strong) — After 6 months of processed meetings + emails + Slack, the accumulated context graph is irreplaceable. Every relationship page, pain point, competitive signal, and action item represents institutional memory that can't be exported.
3. **Process power** (Emerging) — The flywheel loop (conversations → context → prep → better conversations) is a process that compounds. Each cycle makes the system smarter and harder to replicate.

**Moat status: Strong.** Counter-positioning + switching costs is a durable combination. Process power emerges with usage.

## Prerequisites

- **Team Privacy Foundation** (`CONCEPT-BRIEF-team-privacy-foundation.md`) — user-level RLS on 7 tables + API guards. Must ship before Intelligence Flywheel. The meeting processing feature assumes multi-user from day one and the privacy model (Zone 1 personal / Zone 2 team intelligence) is load-bearing for the entire design.

## Open Questions

- [ ] Granola API key setup UX — settings page integration or onboarding flow?
- [ ] Should meeting prep be auto-triggered before calendar events, or always user-initiated?
- [ ] How to handle meeting attendees who map to multiple accounts (person attends on behalf of different companies)?
- [ ] Drive adapter scope — full doc intelligence or just meeting-related docs?
- [ ] Rate limiting / budget controls — hard cap per month or soft warning?
- [ ] Reprocessing strategy when extraction logic improves
- [ ] Should team admins have elevated access (e.g. see all transcripts for compliance)?
- [ ] When User A's meeting creates a prospect account, does User A become the "owner" or is it unassigned?

## Recommendation

**Proceed to /spec.** The concept is validated, the architecture is clean, the moat is real. This is the centerpiece feature that makes Flywheel irreplaceable.

**Phasing recommendation:**
1. **Phase 0**: Team Privacy Foundation (separate spec) — user-level RLS on 7 tables + API guards. Prerequisite for everything.
2. **Phase A**: Meetings table + Granola adapter + shared extraction pipeline + context store writes
3. **Phase B**: Account auto-linking + relationship surface enrichment (timeline, intelligence, people, signals)
4. **Phase C**: Meeting prep from enriched context (closing the loop)
5. **Phase D**: Additional adapters (Fathom, Fireflies) + email integration into shared pipeline
6. **Phase E**: Slack + Drive adapters

Phase 0 is security debt. Phase A is the foundation. Phase B is where the CRM surfaces light up. Phase C is where the flywheel starts spinning. Phases D-E widen the moat.

## Artifacts Referenced

- `skills/meeting-processor/SKILL.md` (v2.3) — 9 insight types, 8 meeting types, context store write targets, Granola MCP integration pattern
- `backend/src/flywheel/engines/meeting_processor.py` — write targets, type weights, utility functions
- `backend/src/flywheel/services/skill_executor.py` — company-intel execution pattern (stages, SSE events, context writes)
- `backend/src/flywheel/api/context.py` — context store endpoints
- `backend/src/flywheel/api/integrations.py` — OAuth/API key storage pattern (AES-256-GCM)
- `backend/src/flywheel/db/models.py` — Integration model, ContextEntry model
- Granola API docs (`https://docs.granola.ai`) — REST API, Bearer auth, rate limits
- Fathom/Fireflies API research — similar REST/GraphQL patterns with Bearer auth
