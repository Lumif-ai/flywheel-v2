# Phase 1: Data Layer and Gmail Foundation - Research

**Researched:** 2026-03-24
**Domain:** SQLAlchemy 2.0 ORM + Alembic migrations + Google Gmail API + PostgreSQL RLS
**Confidence:** HIGH

---

## Summary

This phase adds four new ORM models and their Alembic migration, then implements a separate
`gmail_read.py` service with its own OAuth flow. Every pattern needed already exists in the
codebase — the planner is connecting existing dots, not inventing new ones.

The four models (Email, EmailScore, EmailDraft, EmailVoiceProfile) follow the exact SQLAlchemy
2.0 `Mapped`/`mapped_column` patterns used by all 16+ existing models in `db/models.py`. The
migration follows the hand-written style of `010_context_graph_tables.py` — no Alembic autogenerate.
The `gmail_read.py` service is a near-copy of `google_gmail.py` (same auth, same `build()` call,
different scopes and operations). The OAuth flow follows `integrations.py` (same pending-row-then-
callback pattern, new provider name `gmail-read`).

The only genuinely new territory is the Gmail `historyId` incremental-sync pattern, which differs
from Google Calendar's `syncToken`. The Gmail API returns HTTP 404 (not 410) for an expired
`historyId`, and the fallback is a full re-list — both must be handled from day one per the prior
decisions.

**Primary recommendation:** Build in this exact order: ORM models → migration → `gmail_read.py`
service → OAuth API endpoints → settings/config additions. Each step is independently testable.

---

## Standard Stack

### Core (already installed — no new packages needed)

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| `google-api-python-client` | `>=2.150` | Gmail API via `build("gmail", "v1", creds)` | HIGH — in `pyproject.toml` |
| `google-auth-oauthlib` | `>=1.2` | OAuth2 flow (`google_auth_oauthlib.flow.Flow`) | HIGH — in `pyproject.toml` |
| `google-auth` | transitive | `google.oauth2.credentials.Credentials`, `RefreshError` | HIGH — in `pyproject.toml` |
| `sqlalchemy[asyncio]` | `>=2.0` | ORM models, `Mapped`, `mapped_column`, `JSONB`, `ARRAY` | HIGH — in `pyproject.toml` |
| `alembic` | `>=1.14` | Hand-written migration (RLS, indexes, constraints) | HIGH — in `pyproject.toml` |
| `asyncpg` | `>=0.29` | Async PostgreSQL driver | HIGH — in `pyproject.toml` |

**No new packages required.** The Gmail read service uses the same library stack as the
send service and the calendar service.

### Required Scopes for `gmail-read` OAuth grant

| Scope | Purpose | Note |
|-------|---------|------|
| `https://www.googleapis.com/auth/gmail.readonly` | List and fetch messages | Needed for sync |
| `https://www.googleapis.com/auth/gmail.modify` | Modify labels (mark read/unread) | Needed for future phases |
| `https://www.googleapis.com/auth/gmail.send` | Send approved drafts | Needed for draft approval (Phase 3) |

Include all three scopes in the `gmail-read` OAuth grant. Including `gmail.send` here means the
drafting phase (Phase 3) can send via this same credential rather than needing yet another grant.

---

## Architecture Patterns

### Pattern 1: SQLAlchemy 2.0 Model Convention (from `db/models.py`)

All models in this codebase use:
- `Mapped[T]` type annotation syntax (not `Column()` bare style)
- `mapped_column()` for column definitions
- `server_default=text("gen_random_uuid()")` for UUID PKs
- `TIMESTAMP(timezone=True)` with `server_default=text("now()")`
- `JSONB` from `sqlalchemy.dialects.postgresql` for JSON columns
- `ARRAY(Text)` for array columns
- The `metadata_` ORM attribute mapped to `"metadata"` DB column name
  (avoids collision with SQLAlchemy's internal `.metadata` attribute)
- `__table_args__` tuple for indexes and constraints

```python
# Source: backend/src/flywheel/db/models.py (ContextEntity pattern)
class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (
        Index("idx_emails_tenant_received", "tenant_id", text("received_at DESC")),
        Index("idx_emails_tenant_user", "tenant_id", "user_id"),
        Index("idx_emails_thread", "tenant_id", "gmail_thread_id"),
        UniqueConstraint("tenant_id", "gmail_message_id", name="uq_email_tenant_message"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    gmail_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    gmail_thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    sender_email: Mapped[str] = mapped_column(Text, nullable=False)
    sender_name: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    labels: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    is_read: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_replied: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    synced_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
```

### Pattern 2: Alembic Migration Convention (from `010_context_graph_tables.py` and `019_documents.py`)

All new migrations in this codebase:
- Use hand-written `op.execute()` raw SQL for RLS (Alembic autogenerate cannot handle RLS)
- Follow the revision naming convention: `020_email_models.py`
- Chain `down_revision = "019_documents"` to the latest migration
- Enable RLS with `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`
- Grant table permissions to `app_user` role (already exists from `002_enable_rls_policies.py`)
- Create separate policies per operation (SELECT/INSERT/UPDATE/DELETE) for new tables
- The `set_updated_at()` trigger function already exists in DB — just attach new triggers to it
- The `app_user` role and `set_config` RLS pattern already exists — do not re-create it

```python
# Source: backend/alembic/versions/010_context_graph_tables.py (pattern)
def upgrade() -> None:
    # 1. Create table
    op.execute("""
        CREATE TABLE emails (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            ...
        );
    """)

    # 2. Indexes
    op.execute("CREATE INDEX idx_emails_tenant ON emails (tenant_id);")

    # 3. RLS
    op.execute("ALTER TABLE emails ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE emails FORCE ROW LEVEL SECURITY")

    # 4. Grant to app_user
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON emails TO app_user")

    # 5. Policies
    op.execute("""
        CREATE POLICY tenant_isolation_select ON emails
            FOR SELECT
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    # ... INSERT, UPDATE, DELETE policies

    # 6. Verify
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='emails' AND relrowsecurity) "
        "THEN RAISE EXCEPTION 'RLS not enabled on table: emails'; "
        "END IF; END $$;"
    )
```

### Pattern 3: Gmail API Service (from `google_gmail.py`)

`gmail_read.py` mirrors `google_gmail.py` structure exactly:
- Same `_create_oauth_flow()` / `generate_auth_url()` / `exchange_code()` pattern
- Same `serialize_credentials()` / `deserialize_credentials()` using `encrypt_api_key()`
- Same `get_valid_credentials(integration)` with `RefreshError` → `TokenRevokedException`
- Same `asyncio.to_thread()` wrapper for synchronous `googleapiclient` calls
- Different: scopes, redirect URI setting name, and operations (list/get instead of send)

```python
# Source: backend/src/flywheel/services/google_gmail.py (structural pattern)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

def _create_oauth_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_gmail_read_redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config, scopes=SCOPES,
        redirect_uri=settings.google_gmail_read_redirect_uri,
    )
```

### Pattern 4: Gmail historyId Incremental Sync

Gmail uses `historyId` for incremental sync, not `syncToken` (that is Calendar's mechanism).
The pattern diverges from calendar sync in a critical way:

| Aspect | Google Calendar | Gmail |
|--------|----------------|-------|
| State token | `syncToken` | `historyId` |
| Stored in | `integration.settings["sync_token"]` | `integration.settings["history_id"]` |
| Error on stale | HTTP 410 GONE | HTTP 404 NOT FOUND |
| Recovery | Clear token, full re-list | Clear history_id, full re-list |
| API method | `events().list()` with `syncToken` | `history().list()` with `startHistoryId` |

**Gmail sync flow:**

1. **Initial full sync (no historyId stored):** Call `messages.list(userId="me", labelIds=["INBOX"])` with pagination. For each message ID, call `messages.get(userId="me", id=msg_id, format="metadata", metadataHeaders=["From","Subject","Date"])` to fetch headers. Store the `historyId` from the first message in the list response (most recent).

2. **Incremental sync (historyId stored):** Call `history.list(userId="me", startHistoryId=stored_id, historyTypes=["messageAdded"])`. If HTTP 404, fall back to full sync (same as 410 for calendar).

3. **Sent mail fetch (for voice profile):** Use `messages.list(userId="me", labelIds=["SENT"])` with a `maxResults=200` parameter. Fetch headers + snippet only — **never body**.

```python
# Source: Gmail API docs + google_gmail.py structural pattern
async def list_message_headers(creds: Credentials, page_token: str | None = None) -> dict:
    """List messages in INBOX, return headers only."""
    def _list():
        service = build("gmail", "v1", credentials=creds)
        kwargs = {
            "userId": "me",
            "labelIds": ["INBOX"],
            "maxResults": 100,
            "format": "metadata",
        }
        if page_token:
            kwargs["pageToken"] = page_token
        return service.users().messages().list(**kwargs).execute()
    return await asyncio.to_thread(_list)


async def get_message_headers(creds: Credentials, message_id: str) -> dict:
    """Fetch message metadata (headers only, no body)."""
    def _get():
        service = build("gmail", "v1", credentials=creds)
        return service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "To", "Subject", "Date"],
        ).execute()
    return await asyncio.to_thread(_get)


async def get_message_body(creds: Credentials, message_id: str) -> str:
    """Fetch full message body on-demand for drafting. Called only by drafter."""
    def _get():
        service = build("gmail", "v1", credentials=creds)
        msg = service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
        # Extract text/plain or text/html from payload parts
        return _extract_body(msg)
    return await asyncio.to_thread(_get)


async def list_sent_messages(creds: Credentials, max_results: int = 200) -> dict:
    """List sent messages for voice profile extraction."""
    def _list():
        service = build("gmail", "v1", credentials=creds)
        return service.users().messages().list(
            userId="me", labelIds=["SENT"], maxResults=max_results
        ).execute()
    return await asyncio.to_thread(_list)
```

### Pattern 5: OAuth Integration Row (from `integrations.py`)

The new `gmail-read` OAuth flow follows the exact pattern of existing flows:

1. `GET /integrations/gmail-read/authorize` — create pending Integration row with `provider="gmail-read"`, return auth URL
2. `GET /integrations/gmail-read/callback` — find pending row by state, exchange code, encrypt creds, set status=connected

The existing `provider="gmail"` (send-only) is **never touched**. These are separate rows with separate credentials.

Add new config setting to `config.py`:
```python
google_gmail_read_redirect_uri: str = "http://localhost:5173/api/v1/integrations/gmail-read/callback"
```

Add new entry to `_PROVIDER_DISPLAY` in `integrations.py`:
```python
"gmail-read": "Gmail (Read)",
```

### Recommended File Structure

```
backend/src/flywheel/
├── db/
│   └── models.py                  # Add Email, EmailScore, EmailDraft, EmailVoiceProfile
├── services/
│   └── gmail_read.py              # New file (mirror of google_gmail.py structure)
└── api/
    └── integrations.py            # Add gmail-read authorize + callback endpoints

backend/alembic/versions/
└── 020_email_models.py            # New migration
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Credential encryption | Custom crypto | `auth.encryption.encrypt_api_key()` / `decrypt_api_key()` | AES-256-GCM already in codebase |
| Token refresh | Manual HTTP refresh | `get_valid_credentials(integration)` from `google_gmail.py` — copy the function | Handles `RefreshError`, `invalid_grant` detection |
| Async Google API | Custom async wrapper | `asyncio.to_thread(_sync_fn)` | google-api-python-client is sync; existing pattern wraps correctly |
| OAuth CSRF protection | Custom nonce | `secrets.token_urlsafe(32)` stored in `Integration.settings["oauth_state"]` | Already the project pattern |
| RLS tenant isolation | App-layer filtering | PostgreSQL RLS via `set_config('app.tenant_id', ...)` | Already in `session.py`; new tables just need RLS enabled |
| Updated_at trigger | ORM hook | `set_updated_at()` PL/pgSQL function (already in DB) | Already created in migration 003/005; just add trigger |

**Key insight:** The `google-api-python-client` library is synchronous. Every call to `build().users().messages().*` must be wrapped in `asyncio.to_thread()`. The calendar and gmail services already demonstrate this pattern — copy it exactly.

---

## Common Pitfalls

### Pitfall 1: Accidentally Modifying the Existing `gmail` Integration Row
**What goes wrong:** Using `provider="gmail"` in the new read OAuth flow or filtering for
`provider="gmail"` in the new callback finds the old send-only Integration row and overwrites
its credentials with the broader-scoped token.
**Why it happens:** The existing send-only flow uses `provider="gmail"`. Developers assume
they should "upgrade" it rather than create a parallel row.
**How to avoid:** Use `provider="gmail-read"` everywhere in the new flow. Never issue a SELECT
for `provider="gmail"` in the read service code. In the callback, filter by `provider="gmail-read"`.
**Warning signs:** `gmail_read` callback returning `provider="gmail"` rows.

### Pitfall 2: Logging Email Content
**What goes wrong:** A `logger.debug("Fetched email: %s", message)` logs the full Gmail
message dict, which includes the body text or snippet in response bodies.
**Why it happens:** Developers add debug logging to trace issues without realizing Gmail API
responses contain PII-laden content.
**How to avoid:** Only log message_id and thread_id, never snippet, subject content with
PII, or body. Log format: `"synced message_id=%s thread_id=%s"`.
**Verification:** Trigger a parse error in `gmail_read.py` and inspect log output — no email
content should appear at any log level.

### Pitfall 3: historyId Stale (HTTP 404)
**What goes wrong:** After a historyId is older than ~1 week, `history.list()` returns
HTTP 404. If not caught, sync fails silently or raises an unhandled exception.
**Why it happens:** Gmail historyIds have limited retention (at least 1 week, sometimes less).
Developers familiar with Google Calendar expect HTTP 410 (that's Calendar's stale token error).
**How to avoid:** Catch `HttpError` with `exc.resp.status == 404` in the history sync path.
Clear the stored `history_id` from `integration.settings` and call full re-sync (equivalent
to the `_retry_count` pattern in `calendar_sync.py`).
**Warning signs:** `HttpError` with status 404 in sync logs.

### Pitfall 4: FORCE ROW LEVEL SECURITY Missing
**What goes wrong:** Table has RLS enabled but not FORCED. A superuser connection (used
during migrations and some admin paths) bypasses RLS policies, meaning a bug can expose
cross-tenant data through admin endpoints.
**Why it happens:** `ENABLE ROW LEVEL SECURITY` only enforces policies for non-superusers.
`FORCE ROW LEVEL SECURITY` enforces policies for ALL users including superusers.
**How to avoid:** Every new tenant-scoped table needs BOTH statements. Review pattern from
`010_context_graph_tables.py` — it uses both.
**Warning signs:** Table has `relrowsecurity=true` but `relforcerowsecurity=false` in `pg_class`.

### Pitfall 5: Missing `app_user` GRANT on New Tables
**What goes wrong:** RLS policies exist but the `app_user` role has no access. All queries
from the application (which runs as `app_user` after `SET ROLE app_user`) fail with
permission denied, even with valid RLS context.
**Why it happens:** `ALTER DEFAULT PRIVILEGES` in migration 002 only covers tables that
existed at that time. New tables need explicit `GRANT` statements.
**How to avoid:** Every new tenant-scoped table needs:
`GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user`
Pattern is visible in `010_context_graph_tables.py`.

### Pitfall 6: ORM attribute `metadata_` vs DB column `metadata`
**What goes wrong:** The Python attribute is named `metadata_` but the DB column is `metadata`.
Missing this causes Alembic/SQLAlchemy to generate a column named `metadata_` or fail to
map queries correctly.
**Why it happens:** SQLAlchemy's `Base` class has an internal `.metadata` attribute that
conflicts with a column also named `metadata`.
**How to avoid:** In `mapped_column()`, explicitly pass the DB column name:
`metadata_: Mapped[dict] = mapped_column("metadata", JSONB, ...)`.
Already established pattern in `ContextEntry`, `Document`, and others.

### Pitfall 7: historyId Full-Sync Must Store the `historyId` of the FIRST (most recent) Message
**What goes wrong:** Storing the historyId from the last-fetched page means your checkpoint
is out of date. New messages arriving between first and last page fetch will be missed.
**Why it happens:** `messages.list()` returns newest-first by default. Developers iterate
through all pages and store the historyId of the last page (oldest messages).
**How to avoid:** On initial full sync, capture the `historyId` from the FIRST response
(first page, most recent messages) before paginating. Store that value.

---

## Code Examples

### Registering the Background Sync Task (from `main.py`)

```python
# Source: backend/src/flywheel/main.py (lifespan pattern)
# Add alongside calendar_sync_task:
from flywheel.services.gmail_read import gmail_sync_loop

gmail_sync_task = asyncio.create_task(gmail_sync_loop())
```

### RLS Session Context (from `session.py`)

```python
# Source: backend/src/flywheel/db/session.py
# Email models use the same RLS context as all other tenant-scoped tables.
# No special handling needed — set_config('app.tenant_id', ...) covers them.
await session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_id})
await session.execute(text("SET ROLE app_user"))
```

### TokenRevokedException Pattern (from `google_gmail.py`)

```python
# Source: backend/src/flywheel/services/google_gmail.py
async def get_valid_credentials(integration) -> Credentials:
    creds = deserialize_credentials(integration.credentials_encrypted)
    if creds.valid:
        return creds
    try:
        await asyncio.to_thread(creds.refresh, GoogleAuthRequest())
    except RefreshError as exc:
        if "invalid_grant" in str(exc):
            raise TokenRevokedException("Gmail read access has been revoked.") from exc
        raise
    integration.credentials_encrypted = serialize_credentials(creds)
    return creds
```

---

## State of the Art

| Old Pattern | Current Pattern | Impact for This Phase |
|-------------|----------------|----------------------|
| Single Gmail integration row with expanded scopes | Separate `gmail-read` Integration row (`provider="gmail-read"`) | Critical — never touch `provider="gmail"` row |
| Calendar uses `syncToken` (HTTP 410 on stale) | Gmail uses `historyId` (HTTP 404 on stale) | Different error code to catch in fallback path |
| `moddatetime` extension for `updated_at` | PL/pgSQL `set_updated_at()` function (migration 003) | Attach trigger to tables that have `updated_at` column |

**Deprecated/outdated:**
- `include_granted_scopes="true"` in OAuth flow: This parameter chains scopes across OAuth
  grants from the same Google account. Do NOT use it for the `gmail-read` grant — you want
  separate, isolated credentials, not cumulative scopes.

---

## Open Questions

1. **`gmail-read` redirect URI: separate endpoint needed?**
   - What we know: `config.py` has `google_gmail_redirect_uri` for send-only. New read flow
     needs its own redirect URI at a different path.
   - What's unclear: Should it be `/integrations/gmail-read/callback` or
     `/integrations/gmail/read/callback`?
   - Recommendation: Use `/integrations/gmail-read/callback` (consistent with `provider="gmail-read"`).
     Add `google_gmail_read_redirect_uri` setting to `config.py`.

2. **`EmailVoiceProfile`: one row per user or one per tenant?**
   - What we know: The data model in CONCEPT-BRIEF has `tenant_id` + `user_id`.
   - What's unclear: Is it user-scoped (personal voice) or tenant-scoped (team voice)?
   - Recommendation: User-scoped (one profile per user per tenant). Unique constraint on
     `(tenant_id, user_id)`. Voice is personal.

3. **`historyId` storage location**
   - What we know: Google Calendar stores `sync_token` in `integration.settings["sync_token"]`.
   - Recommendation: Store `history_id` in `integration.settings["history_id"]` on the
     `gmail-read` Integration row. Consistent pattern, no new column needed.

4. **Sent mail fetch for voice profile: Phase 1 or Phase 2?**
   - What we know: Phase description says `gmail_read.py` should fetch sent messages.
     Voice profile extraction requires an LLM (Phase 2+ work).
   - Recommendation: `gmail_read.py` implements `list_sent_messages()` in Phase 1.
     The voice profile _extraction_ (LLM call) is Phase 2. Phase 1 only needs the
     capability to fetch — not the extraction logic.

---

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/db/models.py` — SQLAlchemy 2.0 model conventions (all 16+ models)
- `backend/src/flywheel/services/google_gmail.py` — OAuth flow, credential encryption, API call pattern
- `backend/src/flywheel/services/google_calendar.py` — `syncToken` incremental sync pattern (contrast with `historyId`)
- `backend/src/flywheel/services/calendar_sync.py` — background sync loop, 410 fallback, `asyncio.create_task`
- `backend/alembic/versions/010_context_graph_tables.py` — RLS + FORCE + GRANT + separate per-operation policies
- `backend/alembic/versions/002_enable_rls_policies.py` — `app_user` role and `set_config` RLS mechanism
- `backend/alembic/versions/005_add_integrations_table.py` — `set_updated_at()` trigger pattern
- `backend/src/flywheel/api/integrations.py` — OAuth pending-row → callback pattern
- `backend/src/flywheel/config.py` — existing Google config settings
- `backend/src/flywheel/main.py` — background task registration via `asyncio.create_task()`
- `backend/pyproject.toml` — confirmed `google-api-python-client>=2.150` installed

### Secondary (MEDIUM confidence)
- `https://developers.google.com/workspace/gmail/api/guides/sync` — Gmail historyId sync pattern
  (initial full sync, incremental via `history.list()`, 404 fallback)

### Tertiary (LOW confidence — flag for validation)
- Gmail historyId validity window (stated as "typically at least a week" — verify under load
  conditions with many label changes)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in pyproject.toml, all patterns confirmed in codebase
- Architecture patterns: HIGH — copied from existing working services and migrations
- historyId sync: HIGH — verified against official Gmail API docs
- Pitfalls: HIGH — most derived directly from reading existing code patterns

**Research date:** 2026-03-24
**Valid until:** 2026-06-01 (stable Google APIs, stable SQLAlchemy 2.0 patterns)
