# Phase 59: Team Privacy Foundation - Research

**Researched:** 2026-03-28
**Domain:** PostgreSQL Row Level Security (RLS) policy upgrades + FastAPI API-layer ownership guards
**Confidence:** HIGH

## Summary

Phase 59 upgrades 7 database tables from tenant-level-only RLS to user-level RLS policies. The codebase already has a working RLS infrastructure: `get_tenant_session()` sets both `app.tenant_id` and `app.user_id` as transaction-local postgres config variables, and all protected endpoints use `get_tenant_db` which calls `get_tenant_session`. The session layer is already wiring `user.sub` into `app.user_id` on every request — what's missing is that the RLS policies on these 7 tables don't check `app.user_id` yet, and some API endpoints add redundant tenant-only WHERE clauses that also don't filter by user.

The migration work is policy replacement only — zero schema changes. All 7 tables already have `user_id` columns or FK relationships that enable user-scoping. The API work (PRIV-05 through PRIV-07) is defense-in-depth: explicit `user_id` filters in WHERE clauses, not new authorization logic.

One noteworthy complexity: `email_scores` and `email_drafts` have no `user_id` column — they inherit ownership through the parent `emails` row via `email_id` FK. Their RLS policies use a subquery (`email_id IN (SELECT id FROM emails WHERE user_id = ...)`). The API-layer draft ownership checks (approve, dismiss, edit) must similarly navigate through the parent email row.

**Primary recommendation:** Execute PRIV-01 through PRIV-07 exactly as specified in the SPEC. The SQL and code patterns are fully specified; the planner should translate them directly into task actions.

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|--------------|---------|---------|--------------|
| Alembic | current | Database migration runner | Already in use; RLS policy changes must go through Alembic per project pattern |
| SQLAlchemy async | current | ORM/query building | Already in use for all DB access |
| PostgreSQL RLS | 14+ | Row-level security enforcement | Infrastructure already provisioned in migration 002 |
| FastAPI | current | API layer | All endpoints already use this |

### No new dependencies
No new packages required. This phase is pure migration + code modification.

## Architecture Patterns

### Existing RLS Infrastructure (HIGH confidence)

The session layer already sets `app.user_id` on every request:

```python
# Source: backend/src/flywheel/db/session.py — get_tenant_session()
await session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_id})
await session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})
await session.execute(text("SET ROLE app_user"))
```

`get_tenant_db` (in `deps.py`) calls `get_tenant_session(factory, str(user.tenant_id), str(user.sub))` — so `app.user_id` is already set to `user.sub` for every authenticated endpoint. The RLS policies just don't check it yet.

### Current Policy Names Per Table (HIGH confidence — verified in migrations)

| Table | Current Policy Names | Migration Source |
|-------|---------------------|-----------------|
| `emails` | `tenant_isolation_select`, `tenant_isolation_insert`, `tenant_isolation_update`, `tenant_isolation_delete` | `020_email_models.py` |
| `email_scores` | `tenant_isolation_select`, `tenant_isolation_insert`, `tenant_isolation_update`, `tenant_isolation_delete` | `020_email_models.py` |
| `email_drafts` | `tenant_isolation_select`, `tenant_isolation_insert`, `tenant_isolation_update`, `tenant_isolation_delete` | `020_email_models.py` |
| `email_voice_profiles` | `tenant_isolation_select`, `tenant_isolation_insert`, `tenant_isolation_update`, `tenant_isolation_delete` | `020_email_models.py` |
| `integrations` | `tenant_isolation` (single policy) | `002_enable_rls_policies.py` |
| `work_items` | `tenant_isolation` (single policy) | `002_enable_rls_policies.py` |
| `skill_runs` | `tenant_isolation` (single policy) | `002_enable_rls_policies.py` |

Critical: the DROP POLICY statements in the migration must match these exact policy names per table. Email tables use per-operation names; the other three use a single `tenant_isolation` name.

### Pattern 1: Direct user_id column tables

Used for: `emails`, `email_voice_profiles`, `integrations`

```sql
-- Source: SPEC-team-privacy-foundation.md
DROP POLICY IF EXISTS tenant_isolation_select ON emails;
DROP POLICY IF EXISTS tenant_isolation_insert ON emails;
DROP POLICY IF EXISTS tenant_isolation_update ON emails;
DROP POLICY IF EXISTS tenant_isolation_delete ON emails;

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

### Pattern 2: Nullable user_id tables

Used for: `work_items`, `skill_runs` (user_id is nullable — NULL means tenant-shared)

```sql
-- Source: SPEC-team-privacy-foundation.md
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

### Pattern 3: No user_id column — subquery via FK to parent table

Used for: `email_scores`, `email_drafts` (reference `emails.id` via `email_id` FK)

```sql
-- Source: SPEC-team-privacy-foundation.md
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

### Pattern 4: API-layer list endpoint user scoping

```python
# Source: SPEC-team-privacy-foundation.md (PRIV-07, list_runs pattern)
# Applied to: GET /skills/runs, GET /email/threads, GET /email/digest
base = select(SkillRun).where(SkillRun.user_id == user.sub)
count_q = select(func.count(SkillRun.id)).where(SkillRun.user_id == user.sub)
```

### Pattern 5: API-layer draft ownership check through parent email

```python
# Source: SPEC-team-privacy-foundation.md (PRIV-05)
# Applied to: approve_draft, dismiss_draft, edit_draft
# After loading the draft, load parent email and verify ownership:
email_result = await db.execute(
    select(Email).where(Email.id == draft.email_id)
)
email = email_result.scalar_one_or_none()
if email is None or email.user_id != user.sub:
    raise HTTPException(status_code=404, detail="Draft not found")
```

### Pattern 6: Integration ownership check in query (belt-and-suspenders)

```python
# Source: SPEC-team-privacy-foundation.md (PRIV-06)
# Applied to: disconnect_integration, sync_integration
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

### Alembic Migration File Pattern

```python
# Source: existing migrations (002, 020, 030)
revision: str = "031_user_level_rls"     # Must be <= 32 chars
down_revision: Union[str, None] = "030_grad_at"   # Current head
```

Use `op.execute()` for all raw SQL. No `sa.Column` or DDL helpers — pure SQL strings.

### Anti-Patterns to Avoid

- **Changing `context_entries` RLS**: It already has correct user-aware policies with `visibility` column logic. Do not touch it.
- **Modifying `accounts`, `account_contacts`, `outreach_activities` RLS**: These are intentionally tenant-scoped (team visibility). Do not add user scoping.
- **Adding `user_id` columns to `email_scores` or `email_drafts`**: The subquery approach avoids redundant columns. Do not alter their schema.
- **Using `op.execute()` with f-strings in a loop for policy creation**: Safe here (table names are hardcoded, no user input), but be explicit per-table to match the SPEC exactly.
- **Returning 403 instead of 404 for integration ownership failures**: The spec says return 404 ("Integration not found") not 403, to avoid leaking whether the resource exists.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| User identity in SQL | Custom user lookup in migration | `current_setting('app.user_id', true)::uuid` | Already set by `get_tenant_session`; is transaction-local so no connection pool leakage |
| Ownership verification | Custom permission middleware | Direct `.where(Integration.user_id == user.sub)` in query | RLS is the primary enforcement; API filter is just defense-in-depth |
| Policy idempotency | Version checks | `DROP POLICY IF EXISTS` before `CREATE POLICY` | Standard PostgreSQL pattern used in all existing migrations |

## Common Pitfalls

### Pitfall 1: Wrong policy name in DROP statement
**What goes wrong:** Migration fails with "policy does not exist" because the email tables use per-operation policy names (`tenant_isolation_select`, etc.) while `integrations`, `work_items`, `skill_runs` use a single `tenant_isolation`.
**Why it happens:** Different migrations created these tables with different policy naming conventions.
**How to avoid:** Match exactly: email-family tables use per-operation names; the 002-migration tables use single `tenant_isolation`.
**Warning signs:** Migration fails on `DROP POLICY` statement during upgrade.

### Pitfall 2: Missing user_id filter on both base query and count query in list_runs
**What goes wrong:** Total count includes all tenant runs but items are scoped — pagination math breaks.
**Why it happens:** `count_q` and `base` are constructed independently and the filter must be added to both.
**How to avoid:** Apply `where(SkillRun.user_id == user.sub)` to BOTH `base` and `count_q` as specified in PRIV-07.

### Pitfall 3: email/sync endpoint filters integration by tenant_id only
**What goes wrong:** After PRIV-02 upgrades integrations RLS to user-level, the `trigger_sync` integration lookup already works correctly (RLS enforces user scoping). But the code has an explicit `.where(Integration.tenant_id == user.tenant_id)` that misses the user filter — leaving a gap in defense-in-depth.
**Why it happens:** `trigger_sync` at line 372-381 queries Integration with `tenant_id + provider + status` but no `user_id`. After PRIV-02, RLS prevents reading other users' integrations, so functionality is safe. PRIV-05 spec says to add `.where(Integration.user_id == user.sub)` for explicit defense-in-depth.
**How to avoid:** Add `Integration.user_id == user.sub` to the integration lookup in `trigger_sync`.

### Pitfall 4: Draft ownership check missing in `approve_draft` — parent email already loaded but user_id not verified
**What goes wrong:** The `approve_draft` endpoint at lines 562-568 loads the parent email for the Message-ID header but does NOT verify `email.user_id == user.sub`. If RLS is the only enforcement, this is safe. For defense-in-depth, the explicit check must be added after the email load.
**Why it happens:** The existing load was added for reply threading, not ownership.
**How to avoid:** After `email_result.scalar_one_or_none()`, add: `if email is None or email.user_id != user.sub: raise HTTPException(status_code=404, ...)`.

### Pitfall 5: `list_integrations` returns all tenant integrations without explicit user filter
**What goes wrong:** After PRIV-02, RLS handles the filtering. But the endpoint does `select(Integration)` with no WHERE clause — intent is unclear to a future reader.
**Why it happens:** `list_integrations` at line 106 is `select(Integration)` with no filters at all — RLS does all the work.
**How to avoid:** Add explicit `.where(Integration.user_id == user.sub)` as defense-in-depth per PRIV-06 spec.

### Pitfall 6: Downgrade function not restoring the original per-operation policy names on email tables
**What goes wrong:** Downgrade drops `user_isolation` and tries to recreate the original `tenant_isolation_select`/etc. policies but uses wrong syntax or misses any of the four operations.
**Why it happens:** The original `020_email_models.py` created 4 per-operation policies; the downgrade must recreate exactly 4.
**How to avoid:** Include full downgrade code with all 4 per-operation policies for email-family tables and single `tenant_isolation` for the 002-migration tables.

## Code Examples

### Alembic migration skeleton

```python
# Source: existing migrations 002, 020, 030 as patterns
"""Upgrade email, integrations, work_items, skill_runs to user-level RLS.

Revision ID: 031_user_level_rls
Revises: 030_grad_at
"""

from typing import Sequence, Union
from alembic import op

revision: str = "031_user_level_rls"
down_revision: Union[str, None] = "030_grad_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # emails: drop 4 per-operation policies, create 1 user_isolation
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON emails")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON emails")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON emails")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON emails")
    op.execute("""
        CREATE POLICY user_isolation ON emails
            FOR ALL
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
                AND user_id = current_setting('app.user_id', true)::uuid
            )
    """)
    # ... repeat for other tables per SPEC
```

### Exact line targets in API files (verified against actual source)

| File | Location | Current code | Fix |
|------|----------|-------------|-----|
| `email.py:182` | `list_threads` WHERE | `.where(Email.tenant_id == user.tenant_id)` | Add `, Email.user_id == user.sub` |
| `email.py:284-289` | `get_thread` WHERE | `and_(Email.gmail_thread_id == thread_id, Email.tenant_id == user.tenant_id)` | Add `Email.user_id == user.sub` to `and_()` |
| `email.py:484-489` | `get_digest` WHERE | `and_(Email.tenant_id == user.tenant_id, ...)` | Add `Email.user_id == user.sub` |
| `email.py:373-380` | `trigger_sync` integration lookup | `and_(Integration.tenant_id == ..., Integration.provider == ..., Integration.status == ...)` | Add `Integration.user_id == user.sub` |
| `email.py:562-568` | `approve_draft` parent email load | No ownership check | Add `email.user_id != user.sub` guard after load |
| `email.py:663-673` | `dismiss_draft` | Draft loaded by tenant only | Add parent email ownership check |
| `email.py:712-722` | `edit_draft` | Draft loaded by tenant only | Add parent email ownership check |
| `integrations.py:106` | `list_integrations` | `select(Integration)` no filter | Add `.where(Integration.user_id == user.sub)` |
| `integrations.py:614-618` | `disconnect_integration` | `select(Integration).where(Integration.id == ...)` | Add `Integration.user_id == user.sub` |
| `integrations.py:643-647` | `sync_integration` | Same | Same |
| `skills.py:419-420` | `list_runs` | `base = select(SkillRun)` no user filter | Add `.where(SkillRun.user_id == user.sub)` to both base and count_q |
| `skills.py:457` | `get_run` | `.where(SkillRun.id == run_id)` | Add `SkillRun.user_id == user.sub` |
| `skills.py:479` | `get_run_attribution` | Same | Same |
| `skills.py:526` | `get_run_trace` | Same | Same |

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| Tenant-only RLS (`002_enable_rls_policies.py`) | User-level RLS | Phase 59 upgrade |
| `app.user_id` set but not checked by most policies | `app.user_id` checked by all personal-data policies | Infrastructure was already correct; policies lagged |

**Already correctly user-scoped (do not change):**
- `context_entries`: has `visibility` column with user-aware policies in `002_enable_rls_policies.py`
- `accounts`, `account_contacts`, `outreach_activities`: intentionally tenant-scoped for team visibility

## Open Questions

1. **`stream_run` endpoint (skills.py ~line 299)**
   - What we know: Queries by `SkillRun.id` inside a `get_tenant_session(factory, str(user.tenant_id), str(user.sub))` call — RLS enforces user scoping already
   - What's unclear: Whether the SPEC's "no code change needed" guidance reflects the correct behavior when `user_id IS NULL` on old runs
   - Recommendation: PRIV-04 makes `user_id IS NULL` runs visible to all tenant users (tenant-shared). Old runs with no `user_id` will remain visible to everyone in the tenant via the streaming endpoint. This is the intended behavior per the spec.

2. **downgrade() completeness**
   - What we know: Must restore exact original policy names per table
   - What's unclear: Whether the downgrade needs to handle partial upgrade state
   - Recommendation: Use `DROP POLICY IF EXISTS user_isolation` + `CREATE POLICY` to restore originals. Follow the exact pattern from `020_email_models.py` for the email tables.

## Sources

### Primary (HIGH confidence)
- Verified directly in source: `backend/alembic/versions/002_enable_rls_policies.py` — confirms `tenant_isolation` single policy on `skill_runs`, `work_items`, `integrations`
- Verified directly in source: `backend/alembic/versions/020_email_models.py` — confirms per-operation policy names on all 4 email tables
- Verified directly in source: `backend/src/flywheel/db/session.py` — confirms `app.user_id` is already set via `set_config` in `get_tenant_session`
- Verified directly in source: `backend/src/flywheel/api/deps.py` — confirms `get_tenant_db` passes `str(user.sub)` as `user_id`
- Verified directly in source: `backend/src/flywheel/auth/jwt.py` — confirms `TokenPayload.sub` is the user UUID (no `.id` attribute)
- Verified directly in source: `backend/src/flywheel/api/email.py` — line numbers for all 7 email endpoints confirmed
- Verified directly in source: `backend/src/flywheel/api/integrations.py` — lines 606-667 for DELETE and sync
- Verified directly in source: `backend/src/flywheel/api/skills.py` — lines 409-530 for runs endpoints
- Verified directly in source: `.planning/SPEC-team-privacy-foundation.md` — exact SQL and code patterns for all 7 requirements

### Secondary (MEDIUM confidence)
- Alembic migration `030_graduated_at.py` confirms `down_revision = "030_grad_at"` is the current migration chain head

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; existing codebase fully verified
- Architecture: HIGH — all patterns verified against actual source files, SPEC SQL matches migration conventions
- Pitfalls: HIGH — identified by directly reading the current code and comparing against SPEC requirements

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable codebase; RLS patterns won't change)
