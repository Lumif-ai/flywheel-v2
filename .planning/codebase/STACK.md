# Technology Stack

**Analysis Date:** 2026-03-26

## Languages

**Primary:**
- Python 3.12 - All backend application code, engines, services, API

**Secondary:**
- SQL (PostgreSQL dialect) - Alembic migration files in `alembic/versions/`

## Runtime

**Environment:**
- CPython 3.12 (specified in `pyproject.toml` `requires-python = ">=3.12"` and `Dockerfile` `FROM python:3.12-slim`)

**Package Manager:**
- `uv` (Astral) — specified via `COPY --from=ghcr.io/astral-sh/uv:latest` in `Dockerfile`
- Lockfile: `uv.lock` (present, committed)

## Frameworks

**Core:**
- FastAPI `>=0.115` — ASGI web framework, all HTTP and WebSocket endpoints (`src/flywheel/main.py`)
- Uvicorn `>=0.30` (standard extras) — ASGI server; start command: `uv run uvicorn flywheel.main:app`
- Pydantic `>=2.0` — Request/response models, all `BaseModel` schemas throughout `src/flywheel/api/`
- Pydantic Settings `>=2.0` — Environment config loading in `src/flywheel/config.py`
- SQLAlchemy `>=2.0` (asyncio extra) — Async ORM, all models in `src/flywheel/db/models.py`
- Alembic `>=1.14` — Database migrations, 27 versions in `alembic/versions/`

**Streaming:**
- `sse-starlette >=3.3.3` — Server-Sent Events for skill run streams (used in `src/flywheel/api/skills.py`, `src/flywheel/api/onboarding.py`)

**Rate Limiting:**
- `slowapi >=0.1.9` — Per-user/IP rate limiting middleware (`src/flywheel/middleware/rate_limit.py`)
- Configured via `RATE_LIMIT_MAGIC_LINK=3/hour` and `RATE_LIMIT_DEFAULT=60/minute`

**Testing:**
- `pytest >=8.0` — Test runner, config in `pyproject.toml` `[tool.pytest.ini_options]`
- `pytest-asyncio >=0.24` — Async test support, `asyncio_mode = "auto"`
- `httpx >=0.27` — Async HTTP client used in tests and production code

**Build/Dev:**
- `hatchling` — Build backend (`pyproject.toml` build-system)
- `ruff >=0.8` — Linter and formatter, line-length 100, targets Python 3.12
- `mypy >=1.8` — Type checker (engines directory excluded from type checking)

## Key Dependencies

**AI / LLM:**
- `anthropic >=0.86.0` — Anthropic Claude SDK; used extensively in `src/flywheel/services/skill_executor.py`, `src/flywheel/engines/`, `src/flywheel/services/chat_orchestrator.py`
- Models in use:
  - `claude-sonnet-4-20250514` — Primary skill execution model
  - `claude-haiku-4-5-20251001` — Intent classification, email scoring, fast/cheap tasks
  - `claude-haiku-4-20250514` — Used in `src/flywheel/api/auth.py` lifecycle classification

**Database:**
- `asyncpg >=0.29` — Async PostgreSQL driver (used via SQLAlchemy `postgresql+asyncpg://` URL)

**Auth:**
- `supabase >=2.28.2` — Supabase Python client for admin auth operations (`src/flywheel/auth/supabase_client.py`)
- `pyjwt >=2.12.1` — JWT verification of Supabase tokens (`src/flywheel/auth/jwt.py`); supports HS256 and ES256
- `cryptography >=46.0.5` — AES-256-GCM encryption for BYOK API keys (`src/flywheel/auth/encryption.py`)

**Google Integrations:**
- `google-api-python-client >=2.150` — Google Calendar API and Gmail API calls
- `google-auth-oauthlib >=1.2` — OAuth2 flow for Google Calendar and Gmail
- `google-auth-httplib2 >=0.2` — HTTP transport for Google auth

**Microsoft Integration:**
- `msal >=1.31` — Microsoft Authentication Library for Outlook/Azure AD OAuth (`src/flywheel/services/microsoft_outlook.py`)

**Slack Integration:**
- `slack-bolt >=1.21` — Slack app framework for Events API and slash commands

**Email Dispatch:**
- `resend >=2.0` — Transactional email (magic links, invites) via `src/flywheel/services/email.py`

**Web Research:**
- `tavily-python >=0.5` — Web search API wrapper (`src/flywheel/tools/web_search.py`); disabled when `TAVILY_API_KEY` is unset
- `readability-lxml >=0.8` — HTML readability extraction for web fetch tool
- `beautifulsoup4 >=4.12` — HTML parsing
- `html2text >=2024.2.26` — HTML-to-text conversion

**Document Processing:**
- `pdfplumber >=0.11.9` — PDF text extraction
- `python-docx >=1.2.0` — DOCX file processing
- `python-multipart >=0.0.22` — Multipart form data (file uploads)
- `python-frontmatter >=1.1.0` — YAML frontmatter parsing for skill SKILL.md files

**Observability:**
- `sentry-sdk[fastapi] >=2.0` — Error tracking; initialized in `src/flywheel/main.py` when `SENTRY_DSN` is set

**HTTP Client:**
- `httpx >=0.27` — Async HTTP client for Supabase Storage, Microsoft Graph API, Slack API calls

## Configuration

**Environment:**
- All config loaded from `.env` file via `pydantic-settings` (`src/flywheel/config.py`)
- Single `Settings` class with typed fields and defaults
- Backend mode controlled by `FLYWHEEL_BACKEND` env var: `flatfile` (default), `postgres`, or `remote`

**Key Config Variables:**
- `DATABASE_URL` — PostgreSQL connection string
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`
- `ENCRYPTION_KEY` — Base64-encoded 32-byte AES-256 key for BYOK
- `ANTHROPIC_API_KEY` implied (BYOK model; users store own key in `profiles.api_key_encrypted`)
- `FLYWHEEL_SUBSIDY_API_KEY` — Platform's own Anthropic key for anonymous onboarding (~$0.50/trial)
- `RESEND_API_KEY`, `EMAIL_DOMAIN`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`
- `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`
- `TAVILY_API_KEY`
- `SENTRY_DSN`
- `ENVIRONMENT` — `development` | `staging` | `production`

**Build:**
- `Dockerfile` — `python:3.12-slim` base, uv for dependency installation
- `railway.toml` — Railway deployment config; runs `alembic upgrade head` before starting

## Platform Requirements

**Development:**
- Python 3.12+
- `uv` package manager
- Docker Postgres on port 5434 for integration tests (marked `@pytest.mark.postgres`)

**Production:**
- Railway (Docker-based deployment via `railway.toml`)
- PostgreSQL database (Supabase-hosted)
- `PORT` env var injected by Railway

---

*Stack analysis: 2026-03-26*
