# External Integrations

**Analysis Date:** 2026-03-26

## APIs & External Services

**AI / LLM:**
- Anthropic Claude API — Skill execution, intent classification, email scoring, company intel
  - SDK/Client: `anthropic` package (`src/flywheel/services/skill_executor.py`, `src/flywheel/services/chat_orchestrator.py`, `src/flywheel/engines/`)
  - Auth: BYOK model — user API keys stored encrypted in `profiles.api_key_encrypted` (AES-256-GCM)
  - Platform subsidy key: `FLYWHEEL_SUBSIDY_API_KEY` for anonymous onboarding flows
  - Models: `claude-sonnet-4-20250514` (primary), `claude-haiku-4-5-20251001` (classification/fast tasks)

**Web Search:**
- Tavily API — Web search for skill research tools
  - SDK/Client: `tavily-python`, `AsyncTavilyClient` in `src/flywheel/tools/web_search.py`
  - Auth: `TAVILY_API_KEY` — if unset, web search is disabled gracefully
  - Budget: max 20 searches per skill run via `RunBudget`

## Data Storage

**Databases:**
- PostgreSQL (Supabase-hosted) — Primary data store; all application data
  - Connection: `DATABASE_URL` env var (`postgresql+asyncpg://...`)
  - Client: SQLAlchemy 2.0 async ORM + asyncpg driver (`src/flywheel/db/engine.py`, `src/flywheel/db/session.py`)
  - ORM models: `src/flywheel/db/models.py` (16 tables: tenants, profiles, companies, context_entries, skills, skill_runs, integrations, work_items, emails, email_drafts, email_scores, email_voice_profiles, uploaded_files, and more)
  - Migrations: Alembic, 27 versions in `alembic/versions/`
  - Row-Level Security (RLS): enforced via PostgreSQL session variables `app.tenant_id`, `app.user_id` (set per-request in `src/flywheel/db/session.py`)

**Flat-File Storage (legacy/dev mode):**
- Markdown files — Context storage when `FLYWHEEL_BACKEND=flatfile`
  - Implementation: `src/flywheel/context_utils.py`
  - Active in development by default; Postgres used in production

**File Storage:**
- Supabase Storage — Document artifact storage (HTML skill outputs)
  - Bucket: `documents`
  - Client: Direct `httpx` REST calls in `src/flywheel/services/document_storage.py`
  - Auth: `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` env vars
  - Pattern: `{tenant_id}/{document_type}/{document_id}.html`
  - Signed URLs generated for download (1-hour expiry by default)

**Caching:**
- PostgreSQL `enrichment_cache` table — Web research result caching
  - Managed in `src/flywheel/storage.py` via `get_cached_enrichment` / `set_cached_enrichment`
  - Hash key: SHA-256 of `(tenant_id, query_text)`

## Authentication & Identity

**Auth Provider:**
- Supabase Auth — Identity management, magic links, anonymous sessions, JWT issuance
  - Client: `src/flywheel/auth/supabase_client.py` — singleton async admin client using `service_role` key
  - Auth: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
  - Usage: magic link sending, anonymous sign-in, token refresh, user promotion

**JWT Verification:**
- `src/flywheel/auth/jwt.py` — Verifies Supabase JWTs on every authenticated request
  - Supports both HS256 (shared secret) and ES256 (ECDSA via JWKS)
  - JWKS endpoint: `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`
  - Auth: `SUPABASE_JWT_SECRET` for HS256

**BYOK Encryption:**
- `src/flywheel/auth/encryption.py` — AES-256-GCM encryption for stored user API keys
  - Key: `ENCRYPTION_KEY` env var (base64-encoded 32-byte key)
  - Applied to: Anthropic API keys, OAuth credential tokens (Google, Microsoft, Slack)

## Google Integrations

**Google Calendar:**
- Google Calendar API — Read-only calendar event sync
  - SDK: `google-api-python-client`, `google-auth-oauthlib`
  - Service: `src/flywheel/services/google_calendar.py`
  - OAuth flow: `src/flywheel/api/integrations.py` (`/integrations/google-calendar/authorize` → `/callback`)
  - Scopes: `https://www.googleapis.com/auth/calendar.events.readonly`
  - Auth: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
  - Background sync: `src/flywheel/services/calendar_sync.py` (`calendar_sync_loop()`)

**Gmail (Send-Only):**
- Gmail API — Send emails as user
  - Service: `src/flywheel/services/google_gmail.py`
  - OAuth flow: `/integrations/gmail/authorize` → `/callback`
  - Auth: same Google OAuth app (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_GMAIL_REDIRECT_URI`)

**Gmail (Read + Send):**
- Gmail API — Full inbox read + send
  - Service: `src/flywheel/services/gmail_read.py`
  - OAuth flow: `/integrations/gmail-read/authorize` → `/callback`
  - Background sync: `src/flywheel/services/gmail_sync.py` (`email_sync_loop()`, 5-minute interval)
  - Sync strategy: Incremental via `historyId`; full re-sync on stale history
  - Auth: `GOOGLE_GMAIL_READ_REDIRECT_URI`

## Microsoft Integration

**Microsoft Outlook:**
- Microsoft Graph API — Send email as user + read mail and calendar
  - SDK: `msal` (Microsoft Authentication Library)
  - Service: `src/flywheel/services/microsoft_outlook.py`
  - OAuth flow: `/integrations/outlook/authorize` → `/callback`
  - Scopes: `Mail.Send`, `Calendars.Read`, `Mail.Read`
  - Auth: `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_REDIRECT_URI`
  - Authority: `https://login.microsoftonline.com/common` (multi-tenant)

## Slack Integration

**Slack Workspace App:**
- Slack Events API + Slash Commands — Message monitoring and command execution
  - SDK: `slack-bolt`
  - OAuth service: `src/flywheel/services/slack_oauth.py`
  - Events handler: `src/flywheel/services/slack_events.py`
  - OAuth flow: `/integrations/slack/authorize` → `/callback`
  - Bot scopes: `commands`, `chat:write`, `channels:history`, `channels:read`, `users:read`
  - Auth: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`, `SLACK_REDIRECT_URI`
  - Channel monitor: `src/flywheel/services/slack_channel_monitor.py`

## Email (Transactional)

**Resend:**
- Transactional email delivery — magic links, team invites, export notifications
  - SDK: `resend` package
  - Service: `src/flywheel/services/email.py`
  - Auth: `RESEND_API_KEY` — if unset, emails are logged but not sent (graceful degradation)
  - From domain: `EMAIL_DOMAIN` (default: `flywheel.app`)
  - Sync SDK wrapped in `asyncio.to_thread()` for async compatibility

**Unified Email Dispatch:**
- `src/flywheel/services/email_dispatch.py` — Routes outbound email to:
  1. Gmail API (if Gmail integration connected)
  2. Microsoft Graph (if Outlook integration connected)
  3. Resend fallback (noreply@flywheel.app)

## Monitoring & Observability

**Error Tracking:**
- Sentry — Exception and error tracking
  - SDK: `sentry-sdk[fastapi]`
  - Initialized in `src/flywheel/main.py` if `SENTRY_DSN` is set
  - Config: `traces_sample_rate=0.1`, `send_default_pii=False`
  - Environment-tagged via `ENVIRONMENT` setting

**Logs:**
- Python `logging` module — `logging.basicConfig` configured in `src/flywheel/main.py`
- Format: `%(asctime)s %(levelname)s %(name)s: %(message)s`
- Level: `INFO`
- PII compliance enforced in `src/flywheel/services/gmail_sync.py` (no subject/body/sender logging)

**Cost Tracking:**
- Internal — Token usage and USD cost calculated per skill run
  - `src/flywheel/services/cost_tracker.py` — per-model pricing table
  - Stored in `skill_runs` table (`token_usage` JSONB column)

## CI/CD & Deployment

**Hosting:**
- Railway — Production deployment platform
  - Config: `railway.toml` (Dockerfile builder, `uvicorn` start command)
  - Pre-deploy migration: `uv run alembic upgrade head`
  - Health check: `GET /api/v1/health` (120s timeout)
  - Restart policy: `ON_FAILURE`, max 3 retries

**CI Pipeline:**
- Not detected (no `.github/workflows/` or similar CI config files present)

## Webhooks & Callbacks

**Incoming Webhooks:**
- `POST /api/v1/integrations/slack/events` — Slack Events API webhook; signature verified via `SLACK_SIGNING_SECRET` (`src/flywheel/api/slack_events.py`)
- `POST /api/v1/integrations/slack/commands` — Slack slash command receiver

**OAuth Callbacks:**
- `GET /api/v1/integrations/google-calendar/callback` — Google Calendar OAuth
- `GET /api/v1/integrations/gmail/callback` — Gmail send OAuth
- `GET /api/v1/integrations/gmail-read/callback` — Gmail read+send OAuth
- `GET /api/v1/integrations/outlook/callback` — Microsoft Outlook OAuth
- `GET /api/v1/integrations/slack/callback` — Slack workspace install OAuth

## WebSocket Connections

**Browser Agent WebSocket:**
- `ws /api/v1/agent/ws` — Persistent WebSocket for browser agent (local Claude Code MCP integration)
  - Manager: `src/flywheel/services/agent_manager.py` — tracks one connection per user
  - Router: `src/flywheel/api/agent_ws.py`

## Environment Configuration

**Required env vars (production):**
- `DATABASE_URL` — PostgreSQL connection string
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_KEY` — Supabase service role key
- `SUPABASE_JWT_SECRET` — JWT verification secret
- `ENCRYPTION_KEY` — AES-256 key (base64, 32 bytes)
- `FLYWHEEL_SUBSIDY_API_KEY` — Platform Anthropic key for anonymous users
- `RESEND_API_KEY` — Resend email API key
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — Google OAuth app
- `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` — Azure AD app
- `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`
- `TAVILY_API_KEY` — Web search (optional; disables web search if absent)
- `SENTRY_DSN` — Error tracking (optional; monitoring disabled if absent)
- `ENVIRONMENT` — `development` | `staging` | `production`
- `PORT` — Injected by Railway

**Secrets location:**
- Local development: `.env` file (not committed, gitignored)
- Production: Railway environment variable dashboard

---

*Integration audit: 2026-03-26*
