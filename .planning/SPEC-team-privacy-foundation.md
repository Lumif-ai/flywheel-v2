# Spec: Team Privacy Foundation

> Source: CONCEPT-BRIEF-team-privacy-foundation.md
> Created: 2026-03-28

## Overview

This spec covers adding user-level Row Level Security (RLS) policies to 7 database tables that currently only enforce tenant-level isolation. When a second user joins a workspace, they can currently see all emails, drafts, integrations, calendar items, and skill runs belonging to every other user in the tenant. The fix adds `user_id` checks to RLS policies on these tables and adds defense-in-depth ownership guards at the API layer.

All 5 tables with direct `user_id` columns (`emails`, `email_voice_profiles`, `integrations`, `work_items`, `skill_runs`) get straightforward `tenant_id + user_id` RLS policies. The 2 tables without `user_id` columns (`email_scores`, `email_drafts`) use a subquery against the parent `emails` table to enforce ownership.

## Requirements

### PRIV-01: User-Level RLS on Email Tables

Four tables need upgraded RLS policies. The `emails` and `email_voice_profiles` tables have a direct `user_id` column. The `email_scores` and `email_drafts` tables do NOT have `user_id` — they reference emails via `email_id` FK and must use a subquery to check ownership through the parent `emails` row.

**Current state:** Each table has per-operation policies (`tenant_isolation_select`, `tenant_isolation_insert`, `tenant_isolation_update`, `tenant_isolation_delete`) that check only `tenant_id`. Created in migration `020_email_models.py`.

**`emails` table** — has `user_id UUID NOT NULL`:

```sql
-- Drop existing per-operation tenant-only policies
DROP POLICY IF EXISTS tenant_isolation_select ON emails;
DROP POLICY IF EXISTS tenant_isolation_insert ON emails;
DROP POLICY IF EXISTS tenant_isolation_update ON emails;
DROP POLICY IF EXISTS tenant_isolation_delete ON emails;

-- Single user-isolation policy replacing all four
CREATE POLICY user_isolation ON emails
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

**`email_scores` table** — NO `user_id` column, has `email_id UUID NOT NULL REFERENCES emails(id)`:

```sql
DROP POLICY IF EXISTS tenant_isolation_select ON email_scores;
DROP POLICY IF EXISTS tenant_isolation_insert ON email_scores;
DROP POLICY IF EXISTS tenant_isolation_update ON email_scores;
DROP POLICY IF EXISTS tenant_isolation_delete ON email_scores;

CREATE POLICY user_isolation ON email_scores
    FOR ALL
    USING (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND email_id IN (
            SELECT id FROM emails
            WHERE user_id = current_setting('app.user_id', true)::uuid
        )
    )
    WITH CHECK (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND email_id IN (
            SELECT id FROM emails
            WHERE user_id = current_setting('app.user_id', true)::uuid
        )
    );
```

**`email_drafts` table** — NO `user_id` column, has `email_id UUID NOT NULL REFERENCES emails(id)`:

```sql
DROP POLICY IF EXISTS tenant_isolation_select ON email_drafts;
DROP POLICY IF EXISTS tenant_isolation_insert ON email_drafts;
DROP POLICY IF EXISTS tenant_isolation_update ON email_drafts;
DROP POLICY IF EXISTS tenant_isolation_delete ON email_drafts;

CREATE POLICY user_isolation ON email_drafts
    FOR ALL
    USING (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND email_id IN (
            SELECT id FROM emails
            WHERE user_id = current_setting('app.user_id', true)::uuid
        )
    )
    WITH CHECK (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND email_id IN (
            SELECT id FROM emails
            WHERE user_id = current_setting('app.user_id', true)::uuid
        )
    );
```

**`email_voice_profiles` table** — has `user_id UUID NOT NULL`:

```sql
DROP POLICY IF EXISTS tenant_isolation_select ON email_voice_profiles;
DROP POLICY IF EXISTS tenant_isolation_insert ON email_voice_profiles;
DROP POLICY IF EXISTS tenant_isolation_update ON email_voice_profiles;
DROP POLICY IF EXISTS tenant_isolation_delete ON email_voice_profiles;

CREATE POLICY user_isolation ON email_voice_profiles
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

### PRIV-02: User-Level RLS on Integration Table

**`integrations` table** — has `user_id UUID NOT NULL`. Currently uses a single `tenant_isolation` policy (from migration `002_enable_rls_policies.py`).

```sql
DROP POLICY IF EXISTS tenant_isolation ON integrations;

CREATE POLICY user_isolation ON integrations
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

### PRIV-03: User-Level RLS on Work Items Table

**`work_items` table** — has `user_id UUID` (nullable). Currently uses a single `tenant_isolation` policy (from migration `002_enable_rls_policies.py`).

Since `user_id` is nullable on `work_items`, the policy must handle NULL gracefully. Items with `user_id IS NULL` are treated as tenant-shared (e.g., system-generated work items). Items with a `user_id` are private to that user.

```sql
DROP POLICY IF EXISTS tenant_isolation ON work_items;

CREATE POLICY user_isolation ON work_items
    FOR ALL
    USING (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND (
            user_id IS NULL
            OR user_id = current_setting('app.user_id', true)::uuid
        )
    )
    WITH CHECK (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND (
            user_id IS NULL
            OR user_id = current_setting('app.user_id', true)::uuid
        )
    );
```

### PRIV-04: User-Level RLS on Skill Runs Table

**`skill_runs` table** — has `user_id UUID` (nullable). Currently uses a single `tenant_isolation` policy (from migration `002_enable_rls_policies.py`).

Same nullable pattern as `work_items`: runs with `user_id IS NULL` remain visible to the tenant; runs with a `user_id` are private.

```sql
DROP POLICY IF EXISTS tenant_isolation ON skill_runs;

CREATE POLICY user_isolation ON skill_runs
    FOR ALL
    USING (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND (
            user_id IS NULL
            OR user_id = current_setting('app.user_id', true)::uuid
        )
    )
    WITH CHECK (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND (
            user_id IS NULL
            OR user_id = current_setting('app.user_id', true)::uuid
        )
    );
```

### PRIV-05: Email API User Scoping

**File:** `backend/src/flywheel/api/email.py`

All email queries currently filter by `Email.tenant_id == user.tenant_id` but NOT by `user_id`. While the RLS policy (PRIV-01) enforces this at the DB level, explicit API-level filters provide defense-in-depth and clearer error messages.

| Endpoint | Function | Current filter | Required filter |
|----------|----------|---------------|-----------------|
| `GET /email/threads` | `list_threads()` (line 158) | `.where(Email.tenant_id == user.tenant_id)` | Add `.where(Email.user_id == user.sub)` |
| `GET /email/threads/{thread_id}` | `get_thread()` (line 267) | `.where(Email.tenant_id == user.tenant_id)` | Add `.where(Email.user_id == user.sub)` to the `and_()` clause |
| `GET /email/digest` | `get_digest()` (line 466) | `.where(Email.tenant_id == user.tenant_id)` | Add `Email.user_id == user.sub` to the `and_()` clause |
| `POST /email/drafts/{draft_id}/approve` | `approve_draft()` (line 525) | `.where(EmailDraft.tenant_id == user.tenant_id)` | Add check after loading draft: verify parent email's `user_id == user.sub` |
| `POST /email/drafts/{draft_id}/dismiss` | `dismiss_draft()` (line 656) | `.where(EmailDraft.tenant_id == user.tenant_id)` | Same parent email ownership check |
| `PUT /email/drafts/{draft_id}` | `edit_draft()` (line 699) | `.where(EmailDraft.tenant_id == user.tenant_id)` | Same parent email ownership check |
| `POST /email/sync` | `trigger_sync()` (line 361) | `.where(Integration.tenant_id == user.tenant_id)` | Add `.where(Integration.user_id == user.sub)` to the integration lookup |

**Pattern for draft endpoints** (approve, dismiss, edit): After loading the draft, load the parent email and verify ownership:

```python
# After loading draft...
email_result = await db.execute(
    select(Email).where(Email.id == draft.email_id)
)
email = email_result.scalar_one_or_none()
if email is None or email.user_id != user.sub:
    raise HTTPException(status_code=404, detail="Draft not found")
```

**Pattern for list/query endpoints** (threads, digest): Add `Email.user_id == user.sub` to existing `.where()` clauses:

```python
# list_threads: line 182
.where(Email.tenant_id == user.tenant_id)
# becomes:
.where(Email.tenant_id == user.tenant_id, Email.user_id == user.sub)
```

### PRIV-06: Integration API Ownership Guards

**File:** `backend/src/flywheel/api/integrations.py`

| Endpoint | Function | Current behavior | Required fix |
|----------|----------|-----------------|--------------|
| `GET /integrations/` | `list_integrations()` (line 100) | `select(Integration)` with no filter — RLS handles tenant but returns all users' integrations | RLS will now handle this (PRIV-02). Optionally add explicit `.where(Integration.user_id == user.sub)` for defense-in-depth. |
| `DELETE /integrations/{id}` | `disconnect_integration()` (line 607) | Loads by `Integration.id` only, no user check | Add ownership verification |
| `POST /integrations/{id}/sync` | `sync_integration()` (line 635) | Loads by `Integration.id` only, no user check | Add ownership verification |

**Pattern for DELETE and sync** — add ownership check after loading:

```python
# disconnect_integration (line 614) and sync_integration (line 642):
integration = (
    await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == user.sub,
        )
    )
).scalar_one_or_none()

if integration is None:
    raise HTTPException(status_code=404, detail="Integration not found")
```

Note: The RLS policy (PRIV-02) provides the real enforcement. If a user queries for another user's integration by ID, the RLS policy will return no rows and the API returns 404. The explicit `.where(Integration.user_id == user.sub)` is belt-and-suspenders.

**OAuth authorize endpoints** (google-calendar, gmail, gmail-read, outlook, slack): Already correct — they create new Integration rows with `user_id=user.sub`. No change needed.

**OAuth callback endpoints**: Already correct — they query for pending integrations with `Integration.tenant_id == user.tenant_id` which RLS will further restrict to the current user's pending integrations. The user who initiated the OAuth flow is the one completing it.

### PRIV-07: Skill Runs API User Scoping

**File:** `backend/src/flywheel/api/skills.py`

| Endpoint | Function | Current behavior | Required fix |
|----------|----------|-----------------|--------------|
| `GET /skills/runs` | `list_runs()` (line 409) | `select(SkillRun)` with no user filter | Add `.where(SkillRun.user_id == user.sub)` to both `base` and `count_q` |
| `GET /skills/runs/{run_id}` | `get_run()` (line 450) | `select(SkillRun).where(SkillRun.id == run_id)` | Add `.where(SkillRun.user_id == user.sub)` (or rely on RLS and return 404 if not found) |
| `GET /skills/runs/{run_id}/attribution` | `get_run_attribution()` (line 472) | Same as above | Same fix |
| `GET /skills/runs/{run_id}/trace` | `get_run_trace()` (line 519) | Same as above | Same fix |
| `GET /skills/runs/{run_id}/stream` | `stream_run()` (line 299) | Queries by `SkillRun.id` inside tenant session | Already scoped by `get_tenant_session(factory, str(user.tenant_id), str(user.sub))` which sets `app.user_id`. RLS (PRIV-04) handles enforcement. No code change needed. |

**Pattern for list endpoint:**

```python
# list_runs: line 419-420
base = select(SkillRun).where(SkillRun.user_id == user.sub)
count_q = select(func.count(SkillRun.id)).where(SkillRun.user_id == user.sub)
```

**Pattern for detail endpoints** (get_run, attribution, trace):

```python
# get_run: line 457
result = await db.execute(
    select(SkillRun).where(SkillRun.id == run_id, SkillRun.user_id == user.sub)
)
```

## Success Criteria

1. User A connects Gmail and syncs emails. User B (same tenant) calls `GET /email/threads` and gets zero results (not User A's emails).
2. User B calls `DELETE /integrations/{user_a_integration_id}` and gets 404 (not 200).
3. User B calls `GET /skills/runs` and sees only their own runs, not User A's.
4. User A creates a context entry with `visibility='private'`. User B's `GET /context/files/{name}/entries` does not include it (existing behavior, unchanged).
5. User A creates a context entry with `visibility='team'` (default). User B can see it (existing behavior, unchanged).
6. All 7 affected tables have user-level RLS policies verified via `EXPLAIN` showing policy filter.
7. Existing single-user functionality is unaffected — all current tests pass.

## Anti-Requirements

- Do NOT change `context_entries` RLS (already correct with `visibility` column and user-aware policies in migration `002_enable_rls_policies.py`)
- Do NOT change `accounts`, `account_contacts`, `outreach_activities` (correctly tenant-scoped — team needs full visibility)
- Do NOT add admin override (deferred until enterprise customer requests it)
- Do NOT change the RLS policy on `apply_rls_policies.py` script — use Alembic migration instead

## Migration Notes

- **5 of 7 tables** already have `user_id` columns: `emails`, `email_voice_profiles`, `integrations`, `work_items`, `skill_runs`. No schema changes needed for these.
- **2 of 7 tables** (`email_scores`, `email_drafts`) do NOT have `user_id` columns. They use `email_id` FK to `emails`. RLS policies use a subquery `email_id IN (SELECT id FROM emails WHERE user_id = ...)` to enforce ownership through the parent row. No schema changes needed — the subquery approach avoids adding redundant columns.
- The migration only adds/replaces RLS policies. Zero DDL schema changes.
- Alembic revision chain: `down_revision = "030_grad_at"` (the current head).
- Alembic revision ID must be <= 32 chars. Use `"031_user_level_rls"`.
- Use `op.execute()` for raw SQL in the Alembic migration.
- The `emails` table policies use per-operation names (`tenant_isolation_select`, `tenant_isolation_insert`, `tenant_isolation_update`, `tenant_isolation_delete`). The `integrations`, `work_items`, `skill_runs` tables use a single `tenant_isolation` policy. The migration must drop the correct policy names per table.
- `email_voice_profiles` also uses per-operation policy names (`tenant_isolation_select`, etc.) — same drop pattern as other email tables.
