# Architecture

**Analysis Date:** 2026-03-26

## Pattern Overview

**Overall:** Layered service-oriented backend — FastAPI HTTP/WebSocket API over a multi-tenant PostgreSQL database, with an async job queue for background skill execution and a separate legacy engine subsystem for headless CLI/Slack invocations.

**Key Characteristics:**
- Multi-tenancy enforced at the database layer via PostgreSQL Row-Level Security (RLS). Every tenant-scoped request sets `app.tenant_id`, `app.user_id`, and optionally `app.focus_id` as Postgres session config variables before downgrading to `app_user` role.
- Dual execution paths: web requests use an async `AsyncAnthropic` tool-use loop via `SkillRun` + job queue; CLI/Slack routes use a synchronous `execution_gateway` with an `anthropic.Anthropic()` sync client.
- Authentication is delegated to Supabase (JWT issuing); the backend verifies tokens and enriches them with tenant context from its own `user_tenants` table.
- All API routes share the prefix `/api/v1`.

## Layers

**HTTP API Layer:**
- Purpose: Route HTTP requests, validate inputs, enforce auth, return responses
- Location: `src/flywheel/api/`
- Contains: FastAPI `APIRouter` modules, Pydantic request/response models, inline SQL via SQLAlchemy ORM
- Depends on: `auth`, `db`, `services`, `middleware`
- Used by: Frontend clients, CLI

**Auth Layer:**
- Purpose: JWT decoding, tenant resolution, anonymous provisioning, credential encryption
- Location: `src/flywheel/auth/`
- Contains: `jwt.py` (Supabase HS256/ES256 decode), `anonymous.py` (auto-provision), `encryption.py` (AES-256 BYOK), `supabase_client.py`
- Depends on: `config`, `db`
- Used by: `api/deps.py` (FastAPI dependency chain)

**Dependency Chain (FastAPI):**
- Purpose: Composable auth + DB session injection
- Location: `src/flywheel/api/deps.py`
- Contains: `get_current_user` → `require_tenant` → `require_admin`; `get_tenant_db` (RLS-scoped session); `get_db_unscoped` (system-level session)
- Pattern: Each endpoint declares its minimum auth level as a `Depends()` argument

**Services Layer:**
- Purpose: Business logic, integrations, background sync loops
- Location: `src/flywheel/services/`
- Contains: ~30 service modules covering email, calendar, Slack, entity extraction, learning engine, job queue, cost tracking, circuit breaker, etc.
- Depends on: `db`, `config`, `storage`
- Used by: `api/` routers and background tasks in `main.py` lifespan

**Storage Layer:**
- Purpose: Async Postgres-backed implementation of the 4-function context API
- Location: `src/flywheel/storage.py`
- Contains: `read_context()`, `append_entry()`, `query_context()`, `batch_context()`, `get_cached_enrichment()`, `set_cached_enrichment()`
- Depends on: `db/models.py`, `db/session.py`
- Used by: `api/context.py`, services, engines

**Legacy Storage Backend:**
- Purpose: Flat-file context API for CLI/engine invocations (compatibility shim)
- Location: `src/flywheel/storage_backend.py`
- Used by: `engines/execution_gateway.py` only

**Engines Layer:**
- Purpose: Deterministic Python engines for specific skill computations (meeting-prep, GTM pipeline, investor update, etc.)
- Location: `src/flywheel/engines/`
- Contains: One module per engine skill; `execution_gateway.py` (routes to engine or LLM); `output_renderer.py`
- Note: These modules are excluded from ruff and mypy linting (`pyproject.toml`). They operate synchronously and are invoked via `asyncio.to_thread()` from the async skill executor.

**Tools Layer:**
- Purpose: LLM-callable tool implementations and runtime registry
- Location: `src/flywheel/tools/`
- Contains: `registry.py` (`ToolRegistry`, `RunContext`, `ToolDefinition`), `context_tools.py`, `browser_tools.py`, `web_search.py`, `web_fetch.py`, `file_tools.py`, `python_execute.py`, `budget.py` (`RunBudget`)
- Depends on: `db`, `services`
- Used by: `services/skill_executor.py`

**Database Layer:**
- Purpose: ORM models, session management, engine initialization
- Location: `src/flywheel/db/`
- Contains: `models.py` (all ORM models), `engine.py` (async SQLAlchemy engine with pool reset hooks), `session.py` (session factory, tenant session), `seed.py`

**Middleware:**
- Purpose: Rate limiting
- Location: `src/flywheel/middleware/`
- Contains: `rate_limit.py` — slowapi `Limiter` + `check_anonymous_run_limit()` + `check_concurrent_run_limit()`

## Data Flow

**Chat Request (web, primary path):**

1. `POST /api/v1/chat` → `api/chat.py` receives `ChatRequest`
2. `require_tenant` dep validates JWT; `get_tenant_db` opens RLS-scoped session
3. Optional: `stream_context` loaded from `work_streams`; `briefing_context` from `briefings`
4. `services/chat_orchestrator.py:classify_intent()` calls Claude Haiku (subsidized key) to detect intent
5. If `action=execute`: a `SkillRun` row is inserted with `status=pending`
6. Response returns `run_id` + `stream_url` immediately (async SSE)
7. Background worker (`services/job_queue.py:job_queue_loop()`) claims the pending run via `FOR UPDATE SKIP LOCKED`
8. `services/skill_executor.py:execute_run()` runs the async tool-use loop with `AsyncAnthropic`
9. Tools execute via `tools/registry.py:ToolRegistry.execute()` with `RunBudget` enforcement
10. Output written back to `skill_runs.output` + `rendered_html`; status set to `completed`
11. Frontend polls or streams SSE events from `api/skills.py` `/skill-runs/{run_id}/stream`

**Context Read/Write:**

1. Endpoint in `api/context.py` receives authenticated request
2. `get_tenant_db` injects session with `SET app.tenant_id`, `app.user_id`, `SET ROLE app_user`
3. `storage.py:read_context(session, file)` or `append_entry()` executes ORM queries
4. RLS policies in Postgres automatically filter rows by `app.tenant_id`
5. Entries formatted as `[YYYY-MM-DD | source: ... | detail] confidence: ... | evidence: N`

**Skill Execution via Legacy Gateway (CLI/Slack):**

1. Slack event or CLI → `engines/execution_gateway.py:execute_skill()`
2. `route_skill()` checks `ENGINE_REGISTRY` → if engine exists, call `run_engine()`; else `run_llm_skill()`
3. Engine path: dynamic `importlib.import_module()` + adapter function
4. LLM path: sync `anthropic.Anthropic()` client with tool-use loop (max 25 iterations)
5. Result returned as `ExecutionResult` dataclass

**State Management:**
- No in-process state store. All state lives in PostgreSQL.
- Background worker tasks registered as `asyncio.Task` in `main.py` lifespan, cancelled on shutdown.
- Per-user tenant ID cached in `api/deps.py:_user_tenant_cache` (process-lifetime dict).
- Tool attribution tracked in thread-local storage (`threading.local`) during engine execution.

## Key Abstractions

**ContextEntry:**
- Purpose: The atomic unit of knowledge — a dated, sourced, confidence-tagged piece of text scoped to a `(tenant, file_name)` key
- Examples: `src/flywheel/db/models.py:ContextEntry`, `src/flywheel/storage.py`
- Pattern: File-per-domain (e.g. `positioning`, `icp-profiles`, `competitive-intel`); full-text search via `TSVECTOR` generated column

**SkillRun:**
- Purpose: Durable record of a skill execution request — job queue row and result store in one
- Examples: `src/flywheel/db/models.py:SkillRun`, `src/flywheel/services/job_queue.py`
- Pattern: State machine — `pending` → `running` → `completed`/`failed`; `FOR UPDATE SKIP LOCKED` for worker safety

**TokenPayload:**
- Purpose: Parsed Supabase JWT with tenant metadata extracted from `app_metadata`
- Location: `src/flywheel/auth/jwt.py`
- Pattern: Pydantic model with `@property` accessors for `tenant_id` and `tenant_role`

**RunContext:**
- Purpose: Carries tenant isolation, run identity, budget, and DB access into every tool call
- Location: `src/flywheel/tools/registry.py:RunContext`
- Pattern: Dataclass passed through tool dispatch; not stored

**Focus:**
- Purpose: Optional "lens" that scopes context entries to a sub-namespace within a tenant
- Location: `src/flywheel/db/models.py:Focus`, `src/flywheel/db/models.py:UserFocus`
- Pattern: Active focus propagated via `X-Focus-Id` HTTP header → `app.focus_id` Postgres session var

## Entry Points

**ASGI Application:**
- Location: `src/flywheel/main.py:app`
- Triggers: `uvicorn flywheel.main:app`
- Responsibilities: App factory (`create_app()`), lifespan hooks, background task start/stop, CORS, rate limiter, error handlers, router registration

**Background Workers (started in lifespan):**
- `services/job_queue.py:job_queue_loop()` — polls for pending `SkillRun` rows every 5 seconds
- `services/stale_job_cleaner.py:cleanup_stale_jobs()` — marks stuck runs as failed
- `services/calendar_sync.py:calendar_sync_loop()` — syncs Google Calendar events to `work_items`
- `services/anonymous_cleanup.py:anonymous_cleanup_loop()` — removes expired anonymous sessions
- `services/gmail_sync.py:email_sync_loop()` — syncs Gmail messages

**WebSocket Endpoint:**
- Location: `src/flywheel/api/agent_ws.py`
- Triggers: `ws://host/api/v1/ws/agent?token=<JWT>`
- Responsibilities: Registers local browser agent with `services/agent_manager.py:agent_manager`; forwards tool commands to connected agent for browser automation

## Error Handling

**Strategy:** Uniform JSON error format (`{"error": str, "message": str, "code": int}`) across all error types. Registered via `api/errors.py:register_error_handlers()` after CORS middleware so errors include CORS headers.

**Patterns:**
- `HTTPException` with appropriate 4xx status for client errors (raised in route handlers and deps)
- `RequestValidationError` → 422 with Pydantic error details
- Unhandled exceptions → 500 with generic message (logged via `logger.exception`)
- Rate limit exceeded → 429 with `Retry-After` header (slowapi)
- Circuit breaker open → 503 `SERVICE_UNAVAILABLE` (Anthropic API guard in `services/circuit_breaker.py`)
- Tool errors in LLM loop: never raise — return error strings so the LLM can recover

## Cross-Cutting Concerns

**Logging:** `logging.basicConfig` at INFO level in `main.py`. Module-level `logger = logging.getLogger(__name__)` throughout. No structured logging library.

**Validation:** Pydantic v2 models for all request/response bodies. DB-level constraints (FK, unique indexes, check via RLS) as secondary enforcement.

**Authentication:** Supabase JWT (HS256 or ES256). Auth verified per-request in `api/deps.py:get_current_user`. Anonymous users auto-provisioned on first API call.

**Tenant Isolation:** PostgreSQL RLS — `SET ROLE app_user` + `set_config('app.tenant_id', ...)` per session. Pool checkout hook in `db/engine.py` resets these to prevent leakage between requests.

**BYOK Encryption:** User API keys stored AES-256 encrypted in `profiles.api_key_encrypted`. Decrypted per-request in `services/skill_executor.py` before calling Anthropic.

---

*Architecture analysis: 2026-03-26*
