# Codebase Concerns

**Analysis Date:** 2026-03-26

---

## Tech Debt

**Filesystem fallback in skill_executor (active dead code):**
- Issue: `_execute_with_tools()` still falls back to reading SKILL.md from the filesystem when no DB `system_prompt` exists. This is a dual-path to maintain — the DB path is canonical but the old path is live.
- Files: `src/flywheel/services/skill_executor.py` lines 2048–2064
- Impact: Any skills not yet seeded into `skill_definitions` silently use filesystem prompts, bypassing DB-managed overrides (RT-02 feature).
- Fix approach: Confirm all skills are seeded (`flywheel db seed`), then remove the `skill_converter` import and the `else` branch in `_execute_with_tools()`.

**Legacy `context_utils.py` kept alive alongside Postgres backend:**
- Issue: `storage_backend.py` uses a Strangler Fig pattern routing to either `context_utils.py` (flat-file) or `storage.py` (Postgres). The `context_utils.py` module is 1,561 lines and still imported in the postgres path for `parse_context_file`.
- Files: `src/flywheel/storage_backend.py`, `src/flywheel/context_utils.py`
- Impact: Any bugs fixed in `storage.py` may still exist in the flat-file path. Maintenance overhead of two implementations.
- Fix approach: Once flat-file backend is retired, delete `context_utils.py` and move `parse_context_file` to a shared utility. `FLYWHEEL_BACKEND` env var must be `postgres` in all production deployments.

**`_env_lock` global for BYOK key injection (thread-safety kludge):**
- Issue: `_execute_with_api_key()` in the CLI path mutates `os.environ["ANTHROPIC_API_KEY"]` under a `threading.Lock`. This is process-global state with a lock — concurrent CLI skill executions are serialised.
- Files: `src/flywheel/services/skill_executor.py` lines 48–52, 2201–2225
- Impact: CLI/Slack path cannot execute two skills in parallel for different users — one waits for the lock. Also fragile in multi-process WSGI environments.
- Fix approach: Pass the API key explicitly to `execute_skill()` instead of via env var. The web path already does this correctly.

**Admin dashboard reports zeroes for anonymous user metrics:**
- Issue: `admin_dashboard` hardcodes `anonymous_count = 0`, `total_anonymous_ever = 0`, `anonymous_with_runs = 0`, `promoted_users = 0` pending Supabase Admin API integration.
- Files: `src/flywheel/api/admin.py` lines 39–57
- Impact: Onboarding funnel metrics in the admin dashboard are completely inaccurate.
- Fix approach: Call Supabase Admin API (`/admin/v1/users?is_anonymous=true`) using the `SUPABASE_SERVICE_ROLE_KEY` already available via `supabase_client.py`.

**Email fields not queryable from API:**
- Issue: Several API responses return `"email": None` because the email column was moved to `auth.users` (Supabase-managed) and is not in the `profiles` table. The tenant members list and focus participant lists are affected.
- Files: `src/flywheel/api/tenant.py` lines 341, 462; `src/flywheel/api/focus.py` lines 188, 415
- Impact: Member and participant listings show no email addresses, breaking invite flows and collaborator identification.
- Fix approach: Fetch email via the Supabase Admin API (`/admin/v1/users/{id}`) for each user ID, or add a cached `email` column back to `profiles` populated on first sign-in.

**Per-tenant web search daily cap not implemented:**
- Issue: `handle_web_search` enforces only a per-run budget (max 20 searches). There is no daily cap per tenant.
- Files: `src/flywheel/tools/web_search.py` line 15
- Impact: A single tenant can run many skill runs per day, exhausting Tavily API credits with no guard.
- Fix approach: Add a `daily_search_count` counter in `EnrichmentCache` or a dedicated table, reset at midnight UTC.

---

## Security Considerations

**JWT passed as URL query parameter (SSE and WebSocket endpoints):**
- Risk: JWTs appear in access logs, proxy logs, Referer headers, and browser history when passed as `?token=...`.
- Files: `src/flywheel/api/skills.py` lines 302–317; `src/flywheel/api/agent_ws.py` line 42; `src/flywheel/api/onboarding.py` line 777
- Current mitigation: Required because the browser `EventSource` API and WebSocket API cannot send custom headers.
- Recommendations: Use short-lived one-time tokens (opaque, exchanged for the real JWT server-side) or ensure logs are scrubbed of `?token=` values at the reverse-proxy level.

**Admin `/admin/dashboard` is accessible to any tenant admin — not platform staff only:**
- Risk: `require_admin` checks `tenant_role == "admin"`, which means any tenant who promotes themselves to admin can view platform-wide aggregate metrics (total tenant count, total users, 30-day LLM cost).
- Files: `src/flywheel/api/admin.py` lines 28–101; `src/flywheel/api/deps.py` lines 103–112
- Current mitigation: `get_db_unscoped` is used so RLS doesn't limit the query — but the route is exposed to all tenant admins.
- Recommendations: Add a separate `is_platform_admin` claim in Supabase `app_metadata` and check it in a new `require_platform_admin` dependency, distinct from `require_admin`.

**Python sandbox is explicitly NOT a true sandbox:**
- Risk: LLM-generated code runs in a subprocess with cleared env vars and resource limits, but no container isolation. On Linux, `/proc`, filesystem access, and network calls remain possible.
- Files: `src/flywheel/tools/python_execute.py` lines 11–16
- Current mitigation: Env var clearing, 30s timeout, RLIMIT_CPU, RLIMIT_AS (skipped on macOS ARM64). Only "casual" credential leakage is prevented.
- Recommendations: Docker sandbox (referenced as backlog item "Python Sandbox Hardening"). At minimum, add `seccomp` profile or network namespace isolation before production multi-tenancy at scale.

**`debug: bool = True` in `Settings` default:**
- Risk: If `DEBUG=true` is inadvertently used in production (default is True, not False), FastAPI will expose detailed error tracebacks in responses.
- Files: `src/flywheel/config.py` line 11
- Recommendations: Change default to `False`. Require explicit `DEBUG=true` in development `.env`. Add an assertion in `lifespan` that `settings.debug is False` when `settings.environment == "production"`.

**Slack signing secret verification has no replay window enforcement:**
- Issue: `verify_slack_signature` checks the HMAC but the timestamp staleness check needs review to ensure it refuses requests older than 5 minutes (Slack's recommendation).
- Files: `src/flywheel/services/slack_events.py` lines 28–50
- Current mitigation: HMAC-SHA256 signature verified.
- Recommendations: Confirm the timestamp comparison enforces the 5-minute window; add a test.

---

## Performance Bottlenecks

**`events_log` JSONB column grows unbounded per `SkillRun`:**
- Problem: Every streaming event (tool calls, text tokens, tool results) is appended to `events_log` on the `skill_runs` row. Long-running multi-tool skills accumulate hundreds of events in a single JSONB column.
- Files: `src/flywheel/services/skill_executor.py` (multiple `_append_event_atomic` calls); `src/flywheel/db/models.py` line 312
- Cause: SSE polling reads the whole `events_log` on every poll iteration, sending the full array to deserialise each time.
- Improvement path: Move events to a separate `skill_run_events` table with auto-incrementing `seq` and index on `(run_id, seq)`. Query only new events since last `seen_seq`.

**`skill_runs` table has no index on `(user_id, created_at)` or `(tenant_id, created_at)`:**
- Problem: Queries that list runs by user or tenant (runs history, rate limit checks, lifecycle counts) do full scans or rely only on the partial `idx_runs_pending` index.
- Files: `src/flywheel/db/models.py` lines 283–292; `src/flywheel/api/skills.py`; `src/flywheel/api/auth.py` line 306; `src/flywheel/middleware/rate_limit.py` lines 67–68
- Cause: Only a partial index on `status = 'pending'` was added. No covering index for history queries.
- Improvement path: Add `Index("idx_runs_user_created", "user_id", text("created_at DESC"))` and `Index("idx_runs_tenant_created", "tenant_id", text("created_at DESC"))`.

**`_user_tenant_cache` in `deps.py` is process-local and unbounded:**
- Problem: `_user_tenant_cache: dict[str, str] = {}` grows without eviction for the process lifetime. In a long-running worker this leaks memory proportional to unique users.
- Files: `src/flywheel/api/deps.py` lines 31–52
- Cause: Simple dict with no TTL or size cap.
- Improvement path: Replace with `cachetools.TTLCache(maxsize=10_000, ttl=3600)` or use Redis if multi-process.

**`EnrichmentCache` rows are never purged:**
- Problem: The 24-hour TTL is enforced on reads (rows older than 24h are ignored), but no background job deletes old rows. The table grows indefinitely.
- Files: `src/flywheel/storage.py` lines 332–392; `src/flywheel/db/models.py` lines 331–347
- Cause: No cleanup task in `main.py` lifespan or stale job cleaner.
- Improvement path: Add a periodic `DELETE FROM enrichment_cache WHERE created_at < NOW() - INTERVAL '48 hours'` to `stale_job_cleaner.py`.

---

## Fragile Areas

**`skill_executor.py` is a 2,283-line god module:**
- Files: `src/flywheel/services/skill_executor.py`
- Why fragile: Mixes DB polling (job queue), SSE streaming, tool-use loop, CLI/Slack bridge, cost tracking, BYOK key resolution, context injection, and HTML rendering in one file. Changes in any area risk breaking others.
- Safe modification: Any new feature touching skill execution should extract a focused helper first. High test risk — integration tests in `src/tests/test_skills_api.py` cover the happy path but not edge cases.
- Test coverage: Partial — `test_skills_api.py` exists but does not cover the CLI/gateway path.

**`rate_limit.py` `get_user_id_or_ip` re-decodes JWT without verification claims:**
- Files: `src/flywheel/middleware/rate_limit.py` lines 36–47
- Why fragile: The rate-limiting key function decodes the JWT with `algorithms=["HS256"]` and `audience="authenticated"` — but the project also supports ES256 JWTs (Supabase new projects). An ES256 token will silently fall through to IP-based limiting, effectively bypassing per-user rate limiting.
- Safe modification: Use `decode_jwt()` from `auth/jwt.py` (which handles both algorithms) wrapped in try/except.

**Documents have dual storage path (Supabase Storage + DB content):**
- Files: `src/flywheel/api/documents.py` lines 178–210; `src/flywheel/db/models.py` lines 873–925 (`Document`) and lines 350–380 (`UploadedFile`)
- Why fragile: The `documents.storage_path` column was made nullable (migration `026`) to support DB-stored content, but the legacy Supabase Storage fallback path is still active. Both `Document` and `UploadedFile` exist as separate models for similar concepts.
- Safe modification: Always set `storage_path = None` for new documents. Do not create new code that writes to Supabase Storage for documents.

**Slack events endpoint has no per-tenant DB session (uses session factory directly):**
- Files: `src/flywheel/api/slack_events.py` lines 80–85, 132
- Why fragile: Background event processing creates a raw session without tenant RLS context set. If `process_slack_event` writes to tenant-scoped tables, RLS policies may reject the writes silently (or pass with service-role key if that's the connection).
- Safe modification: Ensure `process_slack_event` receives a properly scoped tenant session via `tenant_session()` helper.

---

## Missing Critical Features

**No platform-level admin role:**
- Problem: Any tenant who sets their own role to "admin" can view platform-wide metrics via `/admin/dashboard` and use `get_db_unscoped` queries.
- Blocks: Safe public launch — any paying customer becomes an effective platform admin.

**No test coverage for the CLI/gateway execution path:**
- Problem: `_execute_with_api_key` (sync CLI path through `execution_gateway.py`) has no dedicated unit or integration tests.
- Files: `src/flywheel/services/skill_executor.py` lines 2200–2225; `src/flywheel/engines/execution_gateway.py`
- Risk: Any refactoring of the BYOK key injection or the `_env_lock` mechanism goes undetected.
- Priority: High

**No test coverage for streaming SSE endpoint under concurrent access:**
- Problem: The SSE polling loop in `src/flywheel/api/skills.py` (`stream_run`) is tested via `test_skills_api.py` but concurrent multi-client scenarios and reconnect/replay are not covered.
- Files: `src/flywheel/api/skills.py` lines 299–400
- Risk: Race conditions in `seen_events` tracking could cause duplicate or missed events on reconnect.
- Priority: Medium

---

## Test Coverage Gaps

**`execution_gateway.py` (sync engine bridge):**
- What's not tested: Engine dispatch, token logging, concurrent execution under `_THREAD_ATTRIBUTION` threading.local
- Files: `src/flywheel/engines/execution_gateway.py`
- Risk: Engine registration bugs, cost calculation errors, token attribution mismatches
- Priority: High

**`gmail_sync.py` background service:**
- What's not tested: Incremental sync with `historyId`, token revocation detection, per-integration concurrency
- Files: `src/flywheel/services/gmail_sync.py`
- Risk: Silent data loss on historyId staleness; duplicate emails on full re-sync
- Priority: High

**`context_utils.py` flat-file backend (1,561 lines):**
- What's not tested: Many functions have coverage via `test_context_utils.py` (1,425 lines) but edge cases in batch operations and file-locking under concurrency are not tested
- Files: `src/flywheel/context_utils.py`, `src/tests/test_context_utils.py`
- Risk: Flat-file corruption on concurrent writes (fcntl-based locking)
- Priority: Medium (lower if flatfile backend is being retired)

**`onboarding_streams.py` SSE flows:**
- What's not tested: `test_onboarding_sse.py` exists but likely covers only the happy path; no tests for expired subsidy key, concurrent anonymous users hitting rate limits
- Files: `src/flywheel/services/onboarding_streams.py`, `src/tests/test_onboarding_sse.py`
- Risk: Anonymous user onboarding breaks silently on subsidy key exhaustion
- Priority: Medium

---

*Concerns audit: 2026-03-26*
