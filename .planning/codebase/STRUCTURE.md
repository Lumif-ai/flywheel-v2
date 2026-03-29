# Codebase Structure

**Analysis Date:** 2026-03-26

## Directory Layout

```
flywheel-v2/backend/
├── src/
│   ├── flywheel/               # Main application package
│   │   ├── api/                # FastAPI routers (one file per resource)
│   │   ├── auth/               # JWT, anonymous provisioning, encryption
│   │   ├── db/                 # ORM models, engine, session factory
│   │   ├── engines/            # Deterministic Python skill engines (legacy)
│   │   ├── middleware/         # Rate limiting
│   │   ├── services/           # Business logic, background workers, integrations
│   │   ├── tools/              # LLM-callable tool registry and handlers
│   │   ├── config.py           # Pydantic Settings (env-driven config)
│   │   ├── context_utils.py    # Legacy context util (deprecated, kept for compat)
│   │   ├── main.py             # App factory + lifespan + all router registration
│   │   ├── migration_tool.py   # DB migration helper
│   │   ├── storage.py          # Async Postgres context store (4-function API)
│   │   └── storage_backend.py  # Flat-file context backend (engines/CLI only)
│   ├── tests/                  # Pytest test suite
│   └── context_utils.py        # (duplicate legacy file at src/ root — ignore)
├── alembic/
│   ├── env.py                  # Alembic migration runner
│   └── versions/               # Numbered migration scripts (001-026+)
├── scripts/
│   └── apply_rls_policies.py   # One-shot script to apply Postgres RLS policies
├── Dockerfile                  # Production container build
├── railway.toml                # Railway.app deployment config
├── pyproject.toml              # Project metadata, deps, ruff/mypy/pytest config
├── alembic.ini                 # Alembic config
└── uv.lock                     # Locked dependency versions (uv)
```

## Directory Purposes

**`src/flywheel/api/`:**
- Purpose: One FastAPI `APIRouter` per resource domain
- Contains: ~20 router modules; each defines its own Pydantic request/response models inline
- Key files:
  - `deps.py` — auth dependency chain (`get_current_user`, `require_tenant`, `require_admin`, `get_tenant_db`)
  - `errors.py` — global exception handlers registered on the app
  - `main.py` (parent) — imports and registers all routers at `/api/v1`

**`src/flywheel/auth/`:**
- Purpose: Auth primitives (JWT decode, anonymous user provisioning, AES encryption)
- Key files:
  - `jwt.py` — `decode_jwt()`, `TokenPayload` Pydantic model
  - `anonymous.py` — `ensure_provisioned()` for anonymous Supabase users
  - `encryption.py` — AES-256 encrypt/decrypt for BYOK API keys
  - `supabase_client.py` — Supabase admin client (used for magic links / admin ops)

**`src/flywheel/db/`:**
- Purpose: Database access primitives
- Key files:
  - `models.py` — ALL ORM models in one file (system tables, tenant-scoped, focus tables, graph tables, work stream tables)
  - `engine.py` — `get_engine()` with pool checkout hook to reset RLS session vars
  - `session.py` — `get_session_factory()`, `get_db()`, `get_tenant_session()`, `tenant_session()`
  - `seed.py` — DB seeding for skill definitions

**`src/flywheel/engines/`:**
- Purpose: Deterministic Python engines for specific skill domains
- Key files:
  - `execution_gateway.py` — routes skill invocations to engine or LLM; used by CLI/Slack
  - `meeting_prep.py` — meeting preparation report generator
  - `meeting_processor.py` — processes meeting notes into context entries
  - `gtm_pipeline.py` — GTM effectiveness tracking
  - `investor_update.py` — investor update report generator
  - `company_intel.py` — company intelligence engine
  - `email_drafter.py`, `email_scorer.py`, `email_voice_updater.py`, `email_dismiss_tracker.py` — email flywheel engines
  - `output_renderer.py` — HTML output rendering
- Note: Excluded from ruff linting and mypy type checking (`pyproject.toml`)

**`src/flywheel/middleware/`:**
- Purpose: HTTP middleware
- Key files: `rate_limit.py` — slowapi `Limiter` + anonymous run limit + concurrent run limit guards

**`src/flywheel/services/`:**
- Purpose: Reusable business logic, external integrations, background loops
- Key files:
  - `skill_executor.py` — `execute_run()`, async tool-use loop via `AsyncAnthropic`
  - `chat_orchestrator.py` — `classify_intent()` using Claude Haiku for skill routing
  - `job_queue.py` — `job_queue_loop()`, `claim_next_job()` via `FOR UPDATE SKIP LOCKED`
  - `learning_engine.py` — evidence scoring, contradiction detection, suggestions
  - `entity_extraction.py` — extracts `ContextEntity` records from context entries
  - `entity_normalization.py` — deduplicates/merges entity records
  - `briefing.py`, `briefing_context.py` — daily briefing generation and injection
  - `google_calendar.py`, `calendar_sync.py` — Google Calendar OAuth + sync loop
  - `google_gmail.py`, `gmail_read.py`, `gmail_sync.py` — Gmail OAuth + sync loop
  - `microsoft_outlook.py` — Microsoft Outlook/Graph OAuth
  - `slack_oauth.py`, `slack_events.py`, `slack_commands.py`, `slack_channel_monitor.py` — Slack integration
  - `document_storage.py` — document upload/retrieval (Supabase Storage or local)
  - `file_extraction.py` — PDF/DOCX text extraction
  - `email.py`, `email_dispatch.py` — transactional email via Resend
  - `circuit_breaker.py` — `anthropic_breaker` guards all Anthropic API calls
  - `cost_tracker.py` — `calculate_cost()` from token usage
  - `agent_manager.py` — `AgentManager` tracks connected local browser agents via WebSocket
  - `stream_context.py` — loads work stream context for chat routing
  - `nudge_engine.py` — proactive nudge generation
  - `onboarding_streams.py`, `team_onboarding.py` — onboarding SSE flows
  - `stale_job_cleaner.py`, `anonymous_cleanup.py` — housekeeping workers

**`src/flywheel/tools/`:**
- Purpose: LLM-callable tool implementations
- Key files:
  - `registry.py` — `ToolRegistry`, `ToolDefinition`, `RunContext`, `RunBudget` integration
  - `context_tools.py` — `read_context`, `append_entry`, `query_context` tool handlers
  - `browser_tools.py` — browser automation tools (require local agent)
  - `web_search.py`, `web_fetch.py` — Tavily/DuckDuckGo search and URL fetch
  - `file_tools.py` — file read/write tools for skill execution
  - `python_execute.py` — sandboxed Python execution tool
  - `schemas.py` — shared Anthropic-format tool schemas
  - `budget.py` — `RunBudget` — per-run limits on expensive tool calls

**`src/tests/`:**
- Purpose: Pytest test suite
- Key files: `conftest.py` (fixtures), test files named `test_<area>.py`

**`alembic/versions/`:**
- Purpose: Numbered migration scripts for schema evolution
- Pattern: `{NNN}_{description}.py` starting from `5e96a39d5776_create_schema.py` then `002_` → `026_`

## Key File Locations

**Entry Points:**
- `src/flywheel/main.py` — ASGI app, lifespan, all router registrations
- `src/flywheel/config.py` — all environment-driven settings via `settings` singleton

**Configuration:**
- `pyproject.toml` — dependency spec, ruff/mypy/pytest config
- `alembic.ini` — Alembic migration config
- `railway.toml` — Railway.app deployment settings
- `Dockerfile` — production container
- `.env` — local environment variables (not committed)

**Core Logic:**
- `src/flywheel/api/deps.py` — auth dependency chain (read before touching any endpoint)
- `src/flywheel/db/models.py` — all database models (single source of truth for schema)
- `src/flywheel/storage.py` — context read/write API
- `src/flywheel/services/skill_executor.py` — web skill execution (async tool-use loop)
- `src/flywheel/engines/execution_gateway.py` — CLI/Slack skill execution

**Testing:**
- `src/tests/conftest.py` — shared fixtures
- `src/tests/test_*.py` — test modules

## Naming Conventions

**Files:**
- API routers: `src/flywheel/api/{resource_noun}.py` (e.g., `context.py`, `documents.py`, `work_items.py`)
- Services: `src/flywheel/services/{domain}[_{verb}].py` (e.g., `gmail_sync.py`, `entity_extraction.py`)
- Engines: `src/flywheel/engines/{skill_name}.py` using underscores (e.g., `meeting_prep.py`)
- Tests: `src/tests/test_{area}_[suffix].py` (e.g., `test_auth_endpoints.py`, `test_context_api.py`)
- Migrations: `alembic/versions/{NNN}_{description}.py`

**Directories:**
- Lowercase with underscores
- Named by responsibility layer (`api`, `auth`, `db`, `services`, `tools`, `engines`, `middleware`)

**Python identifiers:**
- Classes: `PascalCase` (ORM models, Pydantic models, service classes)
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers: `_leading_underscore` (e.g., `_reset_connection_config`, `_format_entry`)
- FastAPI routers: `router = APIRouter(prefix=..., tags=[...])`

## Where to Add New Code

**New API endpoint (new resource):**
- Create `src/flywheel/api/{resource}.py` with `router = APIRouter(prefix="/{resource}", tags=[...])`
- Register in `src/flywheel/main.py` via `app.include_router({resource}_router, prefix="/api/v1")`
- Use `Depends(require_tenant)` + `Depends(get_tenant_db)` for authenticated + DB access

**New service (business logic):**
- Create `src/flywheel/services/{name}.py`
- Import `get_session_factory` from `flywheel.db.session` for DB access if needed outside request scope

**New ORM model:**
- Add to `src/flywheel/db/models.py`
- Create migration: `alembic revision --autogenerate -m "{NNN}_{description}"` (use next sequential number)

**New LLM-callable tool:**
- Add handler in `src/flywheel/tools/{category}_tools.py`
- Create `ToolDefinition` and register via `registry.register(ToolDefinition(...))`
- Add Anthropic-format schema to `src/flywheel/tools/schemas.py`

**New engine skill:**
- Add module to `src/flywheel/engines/{skill_name}.py`
- Register in `ENGINE_REGISTRY` in `src/flywheel/engines/execution_gateway.py`
- Add adapter function `_adapt_{skill_name}()` in the same file

**New background worker:**
- Implement async loop function in `src/flywheel/services/{name}.py`
- Start as `asyncio.create_task(loop_fn())` in `src/flywheel/main.py` lifespan startup
- Cancel in the lifespan shutdown block

**New migration:**
- File path: `alembic/versions/{NNN}_{snake_case_description}.py` where `NNN` is the next sequential number after the current highest (026)

## Special Directories

**`alembic/versions/`:**
- Purpose: Database schema migration history
- Generated: Partially (autogenerate) + manually edited
- Committed: Yes

**`src/tests/`:**
- Purpose: Pytest test suite
- Generated: No
- Committed: Yes

**`.venv/`:**
- Purpose: Python virtual environment managed by `uv`
- Generated: Yes
- Committed: No

**`.mypy_cache/` and `.ruff_cache/`:**
- Purpose: Static analysis caches
- Generated: Yes
- Committed: No

**`.planning/`:**
- Purpose: GSD planning artifacts (phases, quick plans, codebase docs)
- Generated: No (human + AI authored)
- Committed: Yes

---

*Structure analysis: 2026-03-26*
