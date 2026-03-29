# Concept Brief: Team Privacy Foundation

> Generated: 2026-03-28
> Mode: Security Audit
> Artifacts Ingested: Full codebase audit — 35 tables, 120+ endpoints, all RLS policies, all API query filters

## Problem Statement

Flywheel has solid tenant isolation (RLS on all 32 tenant-scoped tables) but zero user-level privacy within a tenant. Every table uses `tenant_id`-only RLS. The moment a second user joins a workspace:

- **User B can see all of User A's emails** — the email API filters by tenant_id only
- **User B can delete User A's Gmail integration** — integration endpoints check ID only, no ownership verification
- **User B can read User A's email drafts** — draft text is fully exposed
- **User B can see User A's calendar items** — work_items has no user filtering
- **User B can access User A's skill run traces** — which may contain email content or transcript excerpts

These aren't theoretical attacks — they're normal API calls that happen to return everything in the tenant. No hacking required.

The infrastructure to fix this already exists: `app.user_id` is set on every DB session (via `deps.py`), and `context_entries` already has a `visibility`-aware RLS policy that checks `user_id`. The fix is extending this pattern to 7 more tables.

## Proposed Approach

### The Three-Zone Visibility Model

Every piece of data falls into one of three zones:

**Zone 1 — Personal**: Belongs to one user. Others must NEVER see it.
- Emails, drafts, voice profile, calendar items, integration credentials, meeting transcripts, meeting prep briefings
- RLS: `tenant_id + user_id`

**Zone 2 — Team Intelligence**: Derived from personal data but benefits everyone. The extraction step is the privacy boundary.
- Context entries, accounts, contacts, relationships, signals, pipeline, meeting metadata + summary, outreach activities, work streams
- RLS: `tenant_id` only (current behavior, correct)

**Zone 3 — Public**: Accessible without authentication.
- Shared documents (via share_token), company cache (onboarding)
- RLS: none / token-based (current behavior, correct)

**The key principle**: Raw personal content (emails, transcripts) is Zone 1. Intelligence extracted FROM that content (pain points, competitor mentions, contacts discovered) crosses into Zone 2 through the extraction pipeline. The extraction step is the one-way privacy gate.

### Tables Requiring User-Level RLS

| # | Table | Current RLS | Required RLS | Why |
|---|-------|-------------|--------------|-----|
| 1 | `emails` | tenant_id | tenant_id + user_id | Email content is deeply personal |
| 2 | `email_scores` | tenant_id | tenant_id + user_id | Scores reference private emails |
| 3 | `email_drafts` | tenant_id | tenant_id + user_id | Contains draft reply text |
| 4 | `email_voice_profiles` | tenant_id | tenant_id + user_id | Personal writing style fingerprint |
| 5 | `integrations` | tenant_id | tenant_id + user_id | Encrypted OAuth credentials |
| 6 | `work_items` | tenant_id | tenant_id + user_id | Calendar items from Google Calendar |
| 7 | `skill_runs` | tenant_id | tenant_id + user_id | Input/output may contain private content |

All 7 tables already have a `user_id` column. The fix is purely additive RLS policies.

### RLS Policy Pattern

```sql
-- Replace tenant-only policy with tenant+user policy
DROP POLICY IF EXISTS tenant_isolation ON {table};

CREATE POLICY user_isolation ON {table}
    FOR ALL
    USING (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND user_id = current_setting('app.user_id', true)::uuid
    )
    WITH CHECK (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND user_id = current_setting('app.user_id', true)::uuid
    );
```

### API-Level Guards (Belt AND Suspenders)

RLS is the database-level enforcement. API-level guards provide defense-in-depth:

**Email endpoints** — add explicit `user_id` filter:
```python
# All email queries add: .where(Email.user_id == user.sub)
```

**Integration endpoints** — add ownership verification:
```python
# DELETE, sync, and credential-access endpoints verify:
if integration.user_id != user.sub:
    raise HTTPException(403, "Not your integration")
```

**Skill runs** — add `user_id` filter to list, ownership check to detail:
```python
# GET /skills/runs adds: .where(SkillRun.user_id == user.sub)
```

### Tables That Stay Tenant-Only (Correct)

| Table | Why shared is correct |
|-------|----------------------|
| `context_entries` | Flywheel output — everyone benefits. Already has `visibility` column with user-aware RLS. |
| `context_catalog`, `context_events` | Organizational structure and audit trail |
| `context_entity`, `context_relationship`, `context_entity_entry` | Knowledge graph — shared intelligence |
| `accounts`, `account_contacts` | CRM records — team needs full visibility |
| `outreach_activities` | Team needs to know who reached out to avoid double-outreach |
| `work_streams`, `work_stream_entities` | Team-level organizational structure |
| `meeting_classifications` | Shared pattern learning model |
| `uploaded_files`, `documents` | Company assets (pitch decks, one-pagers) |
| `enrichment_cache` | LLM cache — saves everyone money |
| `density_snapshots`, `nudge_interactions`, `suggestion_dismissals` | Operational tables |

### The `meetings` Table (New — Design With Split Visibility)

The upcoming meetings table needs split visibility from day one:

| Column | Visibility | Enforcement |
|--------|-----------|-------------|
| title, meeting_date, duration, attendees, meeting_type, account_id | All team members | tenant_id RLS |
| `summary` JSONB (tldr, key_decisions, action_items) | All team members | tenant_id RLS (it's extracted intel) |
| transcript content | Meeting owner only | Supabase Storage ACL + API-level user_id check |
| processing_status, skill_run_id | Meeting owner only | Inherits from skill_runs user-level RLS |

Transcript stored in Supabase Storage (not inline in DB) with user-level access control. API endpoint `GET /meetings/{id}/transcript` returns 403 for non-owners.

### Edge Cases

**User leaves the team:**
- Their emails, drafts, voice profile, integration credentials → soft-deleted
- Their meeting transcripts → removed from Supabase Storage
- Meeting metadata they synced → stays (company knowledge), user_id nulled
- Context entries they generated → stays (extracted intelligence is company knowledge)
- Accounts they managed → stays, reassigned

**User joins mid-stream:**
- Sees all historical context entries (full company knowledge base)
- Sees all accounts, contacts, relationships, pipeline
- Sees all meeting metadata + summaries from other users
- Does NOT see other users' emails, transcripts, drafts, or calendar

**Context entry attribution:**
- Entries from User A's meeting show source: "Discovery call — Acme Corp (2026-03-28)"
- Metadata includes `meeting_id` — owner can click through to transcript, others see metadata only
- The context entry content itself is Zone 2 (shared) — the pain point, competitor mention, or action item

## Key Decisions Made

| Decision | Chosen Direction | Reasoning |
|----------|-----------------|-----------|
| Enforcement layer | RLS + API guards (belt and suspenders) | RLS prevents bypass via direct DB queries; API guards provide clear error messages and audit trail |
| Context entries | Stay tenant-scoped with existing `visibility` column | The flywheel only works if extracted intelligence is shared. The existing RLS policy already handles private entries correctly. |
| Outreach activities | Stay shared | Team needs visibility to avoid double-outreach. Outreach is about the account, not the user. |
| Documents/uploads | Stay shared | Company assets. If users need private docs, they shouldn't upload them to the company CRM. |
| Admin override | Deferred | Don't build compliance/admin access until an enterprise customer asks. Default to user-private. |

## Success Criteria

1. User A connects Gmail and syncs emails. User B (same tenant) calls `GET /email/threads` and gets zero results (not User A's emails).
2. User B calls `DELETE /integrations/{user_a_integration_id}` and gets 403 Forbidden.
3. User B calls `GET /skills/runs` and sees only their own runs, not User A's.
4. User A creates a context entry with `visibility='private'`. User B's `GET /context/files/{name}/entries` does not include it.
5. User A creates a context entry with `visibility='team'` (default). User B can see it.
6. All 7 affected tables have user-level RLS policies verified via `EXPLAIN` showing policy filter.
7. Existing single-user functionality is unaffected — all current tests pass.

## Prerequisite For

- Intelligence Flywheel Engine (CONCEPT-BRIEF-intelligence-flywheel.md) — team meeting processing requires the privacy model
- Any team invite / multi-user deployment
- Any future Slack integration (DMs must be private)

## Recommendation

**Proceed to /spec immediately.** This is security debt with active vulnerabilities. Ship as Phase 0 before the Intelligence Flywheel, before any team invite feature goes live.

Estimated scope: 1 phase, 2 plans.
- Plan 1: Alembic migration adding user-level RLS policies to 7 tables
- Plan 2: API-level ownership guards on email, integration, and skill_run endpoints
