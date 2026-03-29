# Phase 55: Relationships and Signals APIs - Research

**Researched:** 2026-03-27
**Domain:** FastAPI router patterns, Anthropic SDK LLM calls, DB-level rate-limiting, SQLAlchemy 2.0 async queries
**Confidence:** HIGH

## Summary

Phase 55 builds the `/api/v1/relationships/` and `/api/v1/signals/` router surfaces on top of the
Account model that Phase 54 extended. There are NO new library dependencies — every pattern needed
(FastAPI routers, SQLAlchemy 2.0 async queries, Anthropic async messages.create, Supabase Storage
upload) already exists in the codebase. The phase introduces one new concept per plan:
Plan 01 is a straightforward router, Plan 02 is the SynthesisEngine service with DB-level rate
limiting, and Plan 03 handles file upload to Supabase Storage and per-type badge counts.

The most important architectural discovery is that `graduated_at` does NOT exist in the Account
model or any migration — it is `None` for all current accounts. The partition predicate
(`graduated_at IS NOT NULL`) required by the success criteria is currently unenforced because
the column doesn't exist. Phase 55 Plan 01 must add a `030_graduated_at.py` migration (nullable
timestamptz column) and update the ORM model before the relationships router can filter on it.
The existing `_graduate_account()` function in `outreach.py` will need to be updated to set
`graduated_at = now` when it runs.

The `ai_summary_updated_at` column (Phase 54 DM-04) serves as the DB-level rate-limit anchor for
synthesis: "called twice within 5 minutes returns 429" is enforced by comparing
`ai_summary_updated_at` against `now() - interval '5 minutes'` in the endpoint, not via slowapi.
This approach avoids Redis and is consistent with existing DB-backed limits used in
`check_anonymous_run_limit` and `check_concurrent_run_limit`.

**Primary recommendation:** Follow the patterns in `outreach.py` (complex query joins, graduation
logic) and `onboarding_streams.py` (AsyncAnthropic messages.create, graceful degradation) exactly.
Add migration 030 for `graduated_at` in Plan 01 before writing any relationship endpoint.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | >=0.115 | Router, HTTPException, Query, Depends, UploadFile | All existing API files use this — no alternative considered |
| sqlalchemy[asyncio] | >=2.0 | Async ORM queries, select(), func.count(), join(), ANY() | All 20+ API files use this exact pattern |
| anthropic | >=0.86.0 | AsyncAnthropic client for synthesis + ask LLM calls | Already in pyproject.toml; pattern in onboarding_streams.py and gmail_sync.py |
| pydantic | >=2.0 | Request/Response models (BaseModel) | All API files use this for schema validation |
| supabase | >=2.28.2 | Supabase Storage upload for RAPI-06 files | Already in pyproject.toml; auth/supabase_client.py has the admin client factory |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| slowapi | >=0.1.9 | Request-level rate limiting via `@limiter.limit()` decorator | Only for per-IP/per-user HTTP throttling — NOT for synthesis rate limit |
| httpx | >=0.27 | Async HTTP client | Already in use; not needed for Phase 55 |
| python-multipart | >=0.0.22 | Enables FastAPI UploadFile parsing | Already installed; required for RAPI-06 file upload |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| DB-level synthesis rate limit (compare `ai_summary_updated_at` to now-5min) | slowapi `@limiter.limit("1/5minutes")` | slowapi is per-IP/user-ID and resets on server restart; DB-level check uses the already-persisted `ai_summary_updated_at` column and survives restarts |
| `graduated_at` nullable column | using `status != 'prospect'` as partition | `status` predicate is fragile (can be 'engaged', 'customer', etc.); `graduated_at IS NOT NULL` is a single stable boolean fact independent of future status renames |

**Installation:** No new packages needed. All required libraries are in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── alembic/versions/
│   └── 030_graduated_at.py              # nullable timestamptz column on accounts
└── src/flywheel/
    ├── api/
    │   ├── relationships.py             # Plans 01 + 02 endpoints
    │   └── signals.py                   # Plan 03 signals endpoint
    ├── services/
    │   └── synthesis_engine.py          # SynthesisEngine: generate, cache, rate-limit
    └── main.py                          # include new routers
```

Note: Files endpoint in Plan 03 (RAPI-06) could be added to `relationships.py` or a thin
`relationship_files.py` — existing convention puts sub-resource endpoints in the parent router file.

### Pattern 1: Partition Predicate for Relationships vs Pipeline

**What:** The relationships surface shows only accounts with `graduated_at IS NOT NULL`. The pipeline
surface (existing `GET /pipeline/`) shows only `status == 'prospect'`. These two predicates
partition the `accounts` table into disjoint surfaces.

**When to use:** Every query in relationships.py must include `Account.graduated_at.isnot(None)`.
The pipeline endpoint in `outreach.py` already has `Account.status == "prospect"`.

**Example (derived from existing accounts.py pattern):**
```python
# Source: backend/src/flywheel/api/accounts.py — base query pattern
# Modified to enforce partition predicate
stmt = (
    select(Account)
    .where(
        Account.tenant_id == user.tenant_id,
        Account.graduated_at.isnot(None),           # partition predicate — NEVER remove
        Account.relationship_type.any("advisor"),    # type filter via PostgreSQL ANY()
    )
    .order_by(Account.updated_at.desc())
    .offset(offset)
    .limit(limit)
)
```

**Critical:** The `any()` method on ARRAY columns in SQLAlchemy 2.0 generates `= ANY(column)` SQL.
Verify this works correctly — see Pitfall 3 below.

### Pattern 2: DB-Level Synthesis Rate Limit (5-min window)

**What:** Enforce "1 synthesis per 5 minutes" by comparing `ai_summary_updated_at` to current
time in the endpoint before calling the LLM. This is a DB-read, not a slowapi decorator.

**When to use:** `POST /relationships/{id}/synthesize` only. Do NOT use for the `ask` endpoint.

**Example (derived from check_anonymous_run_limit in middleware/rate_limit.py pattern):**
```python
# Source: pattern from backend/src/flywheel/middleware/rate_limit.py
# Applied to DB-column-based window check
from datetime import datetime, timedelta, timezone

async def _check_synthesis_rate_limit(account: Account) -> None:
    """Raise 429 if synthesize was called in the last 5 minutes."""
    if account.ai_summary_updated_at is None:
        return  # never synthesized — always allow
    window = datetime.now(timezone.utc) - timedelta(minutes=5)
    if account.ai_summary_updated_at > window:
        retry_after = int(
            (account.ai_summary_updated_at + timedelta(minutes=5)
             - datetime.now(timezone.utc)).total_seconds()
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "SynthesisRateLimitExceeded",
                "message": "AI synthesis is rate-limited to once per 5 minutes.",
                "code": 429,
            },
            headers={"Retry-After": str(max(retry_after, 1))},
        )
```

**CRITICAL for success criterion:** "called with null `ai_summary` returns cached null, not a new LLM
invocation" — the rate-limit check must run BEFORE the `ai_summary is None` branch. If `ai_summary`
is NULL but `ai_summary_updated_at` is recent, still return 429.

### Pattern 3: LLM Call via AsyncAnthropic (Synthesis and Ask)

**What:** Direct `anthropic.AsyncAnthropic(api_key=...).messages.create(...)` call. This is the
established codebase pattern for non-skill LLM calls.

**When to use:** `SynthesisEngine.generate()` (synthesize) and `POST /ask` endpoint.

**Example:**
```python
# Source: backend/src/flywheel/services/onboarding_streams.py lines 57-66
# Same pattern used in gmail_sync.py lines 760-764

import anthropic
from flywheel.config import settings
from flywheel.services.circuit_breaker import anthropic_breaker

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

async def _call_llm(system_prompt: str, user_content: str) -> str:
    """Call Haiku with graceful degradation."""
    if not anthropic_breaker.can_execute():
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
        response = await client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        anthropic_breaker.record_success()
        return response.content[0].text.strip()
    except Exception:
        anthropic_breaker.record_failure()
        raise
```

### Pattern 4: Signals Badge Count (per-type aggregation)

**What:** `GET /signals/` returns badge counts by relationship type. This requires aggregate queries
similar to the `outreach_stats` subquery in `outreach.py`'s pipeline endpoint, grouped by
relationship_type membership.

**When to use:** Plan 03 `GET /api/v1/signals/` endpoint.

**Example (derived from outreach.py subquery pattern):**
```python
# Source: outreach.py lines 351-360 — aggregate subquery pattern
# For signals, we count per-type overdue accounts using ANY() filter

from sqlalchemy import func, select, literal, and_
from datetime import datetime, timedelta, timezone

async def _compute_signal_counts(db: AsyncSession, tenant_id: UUID) -> dict:
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(days=90)

    # For each type, count accounts with graduated_at IS NOT NULL that have signals
    # Pattern: separate count queries per type, merged in Python
    type_map = {
        "advisor": ...,
        "customer": ...,
        "investor": ...,
        "prospect": ...,
    }
    ...
```

### Pattern 5: Contact Subquery (primary_contact per account)

**What:** RAPI-01 requires `primary_contact` per item in the list. Use correlated subquery
(same as `contact_count_subq` in `accounts.py`) ordered by `created_at ASC` limit 1.

**Example:**
```python
# Source: backend/src/flywheel/api/accounts.py lines 225-232 — correlated subquery pattern
primary_contact_subq = (
    select(AccountContact.name)
    .where(AccountContact.account_id == Account.id)
    .correlate(Account)
    .order_by(AccountContact.created_at.asc())
    .limit(1)
    .scalar_subquery()
)
```

### Anti-Patterns to Avoid

- **Forgetting the partition predicate:** Never query accounts in relationships.py without
  `Account.graduated_at.isnot(None)`. Any missing predicate leaks pipeline accounts to the
  relationships surface.
- **Auto-triggering synthesis on GET:** `GET /relationships/{id}` returns `ai_summary` from the
  column (which may be NULL) — it NEVER calls the LLM. Only `POST /relationships/{id}/synthesize`
  calls the LLM, and only when not rate-limited.
- **Using slowapi for the 5-min synthesis window:** slowapi keys expire in memory; DB-column check
  is the correct approach for a per-account rate limit that must survive restarts.
- **Calling `anthropic_breaker.record_failure()` outside the LLM path:** The circuit breaker in
  `circuit_breaker.py` is shared across all LLM calls. Do not trip it on validation errors (empty
  context, type validation) — only on actual `anthropic.APIError` or connection failures.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AI Q&A source attribution | Custom citation tracking | Pass ContextEntry IDs in the system prompt; parse them from the LLM response | The LLM can include `[source:UUID]` markers; parsing is 5 lines |
| File upload to Supabase | Raw `httpx.post()` to Supabase REST | `supabase.storage.from_bucket().upload()` via `get_supabase_admin()` | The admin client is already instantiated in `auth/supabase_client.py` |
| Rate-limit window math | Custom `timedelta` comparison | Inline `datetime.now(utc) - timedelta(minutes=5) > ai_summary_updated_at` | One expression, no class needed |
| Signal computation | Complex window functions | Separate count queries per signal type, merged in Python | Simpler to read and test; N=4 types means 4 small queries max |
| Sparse-context check for LLM guard | Always calling LLM | Check `count(ContextEntry.account_id == id)` before calling | One COUNT query; prevents LLM cost on accounts with <3 entries |

**Key insight:** Every complex pattern in Phase 55 has a near-identical version already in the
codebase. The value is in faithful replication of those patterns, not invention.

## Common Pitfalls

### Pitfall 1: graduated_at Column Missing — Partition Predicate Broken
**What goes wrong:** Writing `relationships.py` before migration 030 means `Account.graduated_at`
doesn't exist on the ORM, causing `AttributeError` at query time.
**Why it happens:** Phase 54 did not add `graduated_at` — it only added `relationship_type`,
`entity_level`, `ai_summary`, `relationship_status`, `pipeline_stage`.
**How to avoid:** Plan 01's first task must be writing and applying `030_graduated_at.py`.
Also update the `_graduate_account()` helper in `outreach.py` to set `account.graduated_at = now`.
**Warning signs:** `AttributeError: Account has no attribute 'graduated_at'` at startup or query time.

### Pitfall 2: Synthesize Rate-Limit Check Order (NULL ai_summary case)
**What goes wrong:** Checking `if account.ai_summary is None: return cached_null` BEFORE the rate-limit
check means a second call within 5 minutes returns the cached NULL without a 429, passing the first
call but failing the success criterion for the second call.
**Why it happens:** The intuitive logic puts "if NULL just return NULL" first.
**How to avoid:** Always run `_check_synthesis_rate_limit(account)` FIRST in the synthesize handler.
Only after the rate-limit clears should the code check `ai_summary` and decide whether to call LLM.
**Warning signs:** Integration test for "second call returns 429" passes on first run but fails after
`ai_summary` has been set to NULL.

### Pitfall 3: SQLAlchemy ARRAY ANY() Syntax
**What goes wrong:** Filtering `relationship_type` array for a specific type using the wrong idiom.
**Why it happens:** Two valid options exist and the wrong one generates a bad query:
- `Account.relationship_type.any("advisor")` — this is the SQLAlchemy column-level `.any()` which
  generates `= ANY(relationship_type)`, which is correct.
- `any_(Account.relationship_type)` — imported from `sqlalchemy` — this is for subqueries, not arrays.
**How to avoid:** Use `Account.relationship_type.any("advisor")` (method on the mapped column) for
"array contains value" checks. Verify with EXPLAIN.
**Warning signs:** Query returns 0 rows even when data exists, or a SQLAlchemy compilation error.

### Pitfall 4: Ask Endpoint Calls LLM When Context Entries < 3
**What goes wrong:** `POST /ask` calls the LLM even when the account has fewer than 3 context entries,
which the success criteria explicitly disallows.
**Why it happens:** The LLM call is the "happy path" — the sparse-data guard is easy to forget.
**How to avoid:** Before building the RAG prompt, execute `SELECT COUNT(*) FROM context_entries
WHERE account_id = :id AND deleted_at IS NULL`. If count < 3, return a structured "insufficient
context" response (not an LLM call, not a 4xx error — a graceful no-op response).
**Warning signs:** Success criterion 3 test fails: "does not call LLM when account has fewer than
3 context entries."

### Pitfall 5: Signal Counts Including Pipeline Accounts
**What goes wrong:** `GET /signals/` badge counts include accounts with `graduated_at IS NULL`
(pipeline-only accounts). SIG-02 explicitly states "excludes pipeline-only accounts."
**Why it happens:** A simple `WHERE tenant_id = :tid AND next_action_due < now()` would include
all accounts regardless of graduation status.
**How to avoid:** All signal queries must include `Account.graduated_at.isnot(None)` in the WHERE
clause — same partition predicate as the relationships router.
**Warning signs:** Signal counts are larger than expected; including counts from prospect accounts.

### Pitfall 6: Router Prefix Collision
**What goes wrong:** The new `relationships` router uses prefix `/relationships` but there's an
existing `GET /accounts/{id}/graduate` and `GET /pipeline/` in `outreach.py` with no prefix.
Mounting `relationships_router` at `/api/v1` and having `prefix="/relationships"` creates clean
separation, but the new `POST /relationships/{id}/graduate` must not collide with the old
`POST /accounts/{id}/graduate`.
**Why it happens:** Two graduation paths exist (old in outreach.py, new in relationships.py).
**How to avoid:** The new graduation endpoint is at `POST /relationships/{id}/graduate` (different
prefix). They are separate paths. The old `POST /accounts/{id}/graduate` remains for backward
compatibility. Both ultimately call `_graduate_account()` — refactor that helper into a shared
utility or duplicate the logic.
**Warning signs:** 422 routing errors or unintended endpoint shadowing.

### Pitfall 7: Supabase Storage Upload Pattern for Files
**What goes wrong:** RAPI-06 uploads files, but the existing `POST /files/upload` in `files.py`
stores files locally (`local://...` storage_path). If Phase 55 also uses local storage, it won't
be usable in production.
**Why it happens:** The `files.py` comment says "Supabase Storage in Phase 25" — it was never
implemented.
**How to avoid:** For RAPI-06 (`POST /relationships/{id}/files`), implement Supabase Storage upload
using the admin client. The bucket/path pattern: `tenant_id/account_id/uuid/filename`. The storage
path stored in ContextEntry (or a new FileLink row) should be the Supabase public URL.
If Supabase Storage is not available in the dev environment, fall back to local path with a flag.
**Warning signs:** Files uploaded via RAPI-06 return a `local://` storage path in responses —
this is acceptable for dev but the production path must use Supabase.

## Code Examples

Verified patterns from the codebase:

### Partition Predicate Query (relationships list)
```python
# Source: backend/src/flywheel/api/outreach.py lines 387-402 — complex filtered query pattern
# Applied to relationships surface

contact_count_subq = (
    select(func.count())
    .where(AccountContact.account_id == Account.id)
    .correlate(Account)
    .scalar_subquery()
)

stmt = (
    select(Account, contact_count_subq.label("contact_count"))
    .where(
        Account.tenant_id == user.tenant_id,
        Account.graduated_at.isnot(None),         # partition predicate
        Account.relationship_type.any(type_filter), # type param filter
    )
    .order_by(Account.updated_at.desc())
    .offset(offset)
    .limit(limit)
)
result = await db.execute(stmt)
rows = result.all()
items = [_rel_to_list_item(row[0], row[1] or 0) for row in rows]
```

### DB-Level Synthesis Rate Limit
```python
# Source: pattern from backend/src/flywheel/middleware/rate_limit.py (DB-backed check)
from datetime import datetime, timedelta, timezone

SYNTHESIS_WINDOW_MINUTES = 5

async def _enforce_synthesis_rate_limit(account: Account) -> None:
    if account.ai_summary_updated_at is None:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=SYNTHESIS_WINDOW_MINUTES)
    if account.ai_summary_updated_at > cutoff:
        remaining = (
            account.ai_summary_updated_at + timedelta(minutes=SYNTHESIS_WINDOW_MINUTES)
            - datetime.now(timezone.utc)
        )
        raise HTTPException(
            status_code=429,
            detail={"error": "SynthesisRateLimitExceeded", "code": 429},
            headers={"Retry-After": str(max(int(remaining.total_seconds()), 1))},
        )
```

### Graceful Degradation (sparse context)
```python
# Source: pattern from onboarding_streams.py — fallback before LLM call
MIN_CONTEXT_ENTRIES_FOR_ASK = 3

ctx_count = (await db.execute(
    select(func.count(ContextEntry.id)).where(
        ContextEntry.account_id == account_id,
        ContextEntry.deleted_at.is_(None),
    )
)).scalar() or 0

if ctx_count < MIN_CONTEXT_ENTRIES_FOR_ASK:
    return {
        "answer": None,
        "sources": [],
        "reason": "insufficient_context",
        "context_count": ctx_count,
    }
```

### Register New Routers in main.py
```python
# Source: backend/src/flywheel/main.py lines 45-173 — existing pattern
from flywheel.api.relationships import router as relationships_router
from flywheel.api.signals import router as signals_router

# Inside create_app():
app.include_router(relationships_router, prefix="/api/v1")
app.include_router(signals_router, prefix="/api/v1")
```

### graduated_at Migration (030)
```python
# Source: alembic/versions/028_relationship_type_entity_level_ai_summary.py — additive column pattern
revision: str = "030_graduated_at"
down_revision: Union[str, None] = "029_status_phase_a"

def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("graduated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_account_graduated_at",
        "accounts",
        ["tenant_id", "graduated_at"],
        postgresql_where=sa.text("graduated_at IS NOT NULL"),
    )

def downgrade() -> None:
    op.drop_index("idx_account_graduated_at", table_name="accounts")
    op.drop_column("accounts", "graduated_at")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `status == 'engaged'` as graduation signal | `graduated_at IS NOT NULL` | Phase 55 | Partition predicate is stable across future status renames |
| Slowapi for all rate limits | DB column comparison for per-resource rate limits | Phase 55 | Per-resource limits (synthesis) need the resource's own timestamp; slowapi is per-user |
| `POST /accounts/{id}/graduate` (in outreach.py) | `POST /relationships/{id}/graduate` (new endpoint) | Phase 55 | New endpoint sets `graduated_at`; old endpoint remains for backward compat |

**Deprecated/outdated:**
- Local file storage (`local://tenant_id/...`) in `files.py`: was a placeholder for "Phase 25"
  and was never replaced. For Phase 55 RAPI-06, implement the actual Supabase Storage path.

## Open Questions

1. **`_graduate_account()` function location — shared utility or duplicate?**
   - What we know: `_graduate_account()` in `outreach.py` currently sets `account.status = "engaged"`.
     Phase 55's `POST /relationships/{id}/graduate` also needs to set `account.graduated_at = now`.
   - What's unclear: Should `_graduate_account()` be refactored into a shared service module, or
     should the new relationships.py endpoint duplicate the logic with `graduated_at` included?
   - Recommendation: Refactor `_graduate_account()` into `services/graduation.py` that also sets
     `graduated_at`. Update `outreach.py` to import from there. Plan 01 owns this.

2. **Which LLM model for synthesis vs ask?**
   - What we know: The codebase uses `claude-haiku-4-5-20251001` for orchestration and Gmail parsing.
     The `skill_executor.py` uses user BYOK keys for full skill runs.
   - What's unclear: Whether synthesis/ask should use the subsidy key (Haiku) or require a BYOK key.
   - Recommendation: Use `settings.flywheel_subsidy_api_key` with Haiku for synthesis and ask — same
     pattern as `onboarding_streams.py`. These are low-token calls and the subsidy cost is modest.
     If the tenant has a BYOK key configured, prefer it (future optimization; not required in Phase 55).

3. **Supabase Storage bucket name for relationship files**
   - What we know: `supabase_url` and `supabase_service_key` are in settings. The admin client in
     `auth/supabase_client.py` can access storage. The bucket name is not defined anywhere.
   - What's unclear: Which Supabase bucket to use for relationship files (RAPI-06).
   - Recommendation: Use `"relationship-files"` as the bucket name with the convention
     `{tenant_id}/{account_id}/{uuid}/{filename}`. Document the bucket must be created manually in
     Supabase dashboard for production deploy. For local dev, fall back to `local://` path.

4. **SIG-02 stale_relationship signal — what defines "stale"?**
   - What we know: Signal types include `stale_relationship` (priority 3). The existing `briefing.py`
     uses `STALE_THRESHOLD_DAYS = 90` for stale context entries. The `timeline.py` pulse endpoint
     uses 14 days for "bump_suggested" outreach staleness.
   - What's unclear: For the relationships surface, what makes an account "stale" — no ContextEntry
     in N days? No outreach? No `last_interaction_at` update?
   - Recommendation: Define `stale_relationship` as `last_interaction_at < now() - 90 days OR
     (last_interaction_at IS NULL AND created_at < now() - 90 days)`. This mirrors the briefing
     engine's `STALE_THRESHOLD_DAYS = 90` constant.

## Sources

### Primary (HIGH confidence)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/db/models.py` (lines 1091-1154) — Account ORM model; confirmed `graduated_at` is absent
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/accounts.py` — Correlated subquery pattern, serialization helpers, paginated response envelope
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/outreach.py` — `_graduate_account()` helper, pipeline query with joins, graduation endpoint
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/timeline.py` — Pulse signal computation pattern, per-type signal queries
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/deps.py` — `require_tenant`, `get_tenant_db` dependency chain
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/middleware/rate_limit.py` — DB-backed rate limit pattern (`check_anonymous_run_limit`)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/services/onboarding_streams.py` — `AsyncAnthropic` call pattern, graceful degradation
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/services/circuit_breaker.py` — `anthropic_breaker` singleton, `can_execute()` / `record_success()` / `record_failure()`
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/main.py` — Router registration pattern
- `/Users/sharan/Projects/flywheel-v2/backend/alembic/versions/028_relationship_type_entity_level_ai_summary.py` — Latest migration before 029; `revision: "028_acct_ext"`
- `/Users/sharan/Projects/flywheel-v2/backend/alembic/versions/029_status_rename_phase_a.py` — Current head migration; `revision: "029_status_phase_a"`
- `/Users/sharan/Projects/flywheel-v2/backend/pyproject.toml` — `anthropic>=0.86.0`, `supabase>=2.28.2` confirmed

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.0 docs: `.any("value")` on a mapped ARRAY column generates `= ANY(column)` PostgreSQL expression — standard usage
- FastAPI docs: `UploadFile` with `python-multipart` for binary file uploads — confirmed already installed

### Tertiary (LOW confidence)
- Supabase Storage Python SDK pattern for `.upload()` — not directly verified in this codebase since the existing `files.py` uses local storage

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in `pyproject.toml`; no new dependencies
- Architecture patterns: HIGH — directly derived from existing API files in the codebase
- `graduated_at` migration gap: HIGH — verified by searching `models.py` and all migration files; column is absent
- Rate limit approach: HIGH — derived from existing `check_anonymous_run_limit` pattern in `rate_limit.py`
- Supabase Storage for files: MEDIUM — SDK is installed but no existing upload code in this codebase to reference
- Signal staleness threshold: MEDIUM — derived from `briefing.py` constant but not explicitly defined for relationships

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable stack; patterns won't change within 30 days)
