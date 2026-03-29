# Phase 60: Meeting Data Model and Granola Adapter - Research

**Researched:** 2026-03-28
**Domain:** PostgreSQL/Alembic data modeling, split-visibility RLS, external API adapter, Granola REST API
**Confidence:** HIGH

## Summary

Phase 60 builds the data foundation for the Intelligence Flywheel: a `meetings` table with split-visibility RLS (metadata visible to all tenant members, transcript access restricted to the meeting owner), a Granola integration using API-key authentication rather than OAuth, and a sync endpoint that pulls meetings from Granola and deduplicates them into the database. No processing happens — only ingestion.

The codebase is already well-set up for this. The `Integration` ORM model with `credentials_encrypted` (AES-256-GCM via `flywheel.auth.encryption`) already handles API key storage for any provider. The Alembic migration pattern from `027_crm_tables.py` and `031_user_level_rls.py` is the template to follow. The `integrations.py` API router is the right home for the Granola connect endpoint, and a new `meetings.py` router for the sync endpoint.

**Critical discovery:** The real Granola API endpoint is `GET https://public-api.granola.ai/v1/notes` (not `/v1/meetings`). Resources are called "notes" not "meetings." There is no `/v1/me` validation endpoint — key validation must be done by making a `GET /v1/notes?page_size=1` call. Transcripts are returned inline on the `GET /v1/notes/{note_id}?include=transcript` endpoint (not a separate `/transcript` sub-resource). The spec's assumed API shape is incorrect in several places. The adapter implementation must be reconciled against the real API.

**Primary recommendation:** Follow the spec's data model and RLS design exactly, but reconcile the `GranolaAdapter` code against the real Granola API (`/v1/notes`, cursor pagination, transcript via `?include=transcript`, key validation via listing one note).

## Standard Stack

### Core (already in pyproject.toml — no new installs required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | >=2.0 | ORM + Alembic migrations | Existing stack |
| asyncpg | >=0.29 | Async PostgreSQL driver | Existing stack |
| Alembic | >=1.14 | Migration management | Existing stack |
| httpx | >=0.27 | Async HTTP for Granola API calls | Already in deps, used in engines |
| cryptography | >=46.0 | AES-256-GCM key encryption | Already in deps via `flywheel.auth.encryption` |

### No New Dependencies

All needed libraries are already in `backend/pyproject.toml`. The Granola adapter uses `httpx` (already present), encryption reuses `flywheel.auth.encryption.encrypt_api_key` / `decrypt_api_key`, and the ORM follows existing SQLAlchemy 2.0 `Mapped` patterns.

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── alembic/versions/
│   └── 032_create_meetings_table.py   # new migration
├── src/flywheel/
│   ├── db/models.py                   # add Meeting class (end of CRM TABLES section)
│   ├── api/
│   │   ├── integrations.py            # add POST /granola/connect endpoint
│   │   └── meetings.py                # new file — POST /meetings/sync
│   └── services/
│       └── granola_adapter.py         # new file — IntelligenceSource adapter
```

### Pattern 1: Split-Visibility RLS (Two Policies)

The `meetings` table needs two distinct RLS policies — a different pattern from all other tables in the codebase.

**What:** Policy 1 allows all tenant members to SELECT (metadata visible). Policy 2 restricts INSERT/UPDATE/DELETE to the meeting owner (user_id match). The transcript privacy is enforced at the API layer (strip `transcript_url` and `ai_summary` from response if not owner) and at the Supabase Storage layer (Storage policy checks user_id).

**Key difference from other tables:** Prior tables use either full tenant isolation (everyone reads + writes) or full user isolation (only owner reads + writes). The meetings table is the first to split SELECT from write operations by policy level.

**Alembic implementation:**

```python
# Source: .planning/SPEC-intelligence-flywheel.md MDE-01
op.execute("ALTER TABLE meetings ENABLE ROW LEVEL SECURITY")
op.execute("ALTER TABLE meetings FORCE ROW LEVEL SECURITY")
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON meetings TO app_user")

# Policy 1: All tenant members can read meeting metadata
op.execute("""
    CREATE POLICY meetings_tenant_read ON meetings
        FOR SELECT
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
""")

# Policy 2: Only meeting owner can write (INSERT/UPDATE/DELETE)
op.execute("""
    CREATE POLICY meetings_owner_write ON meetings
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
```

**Warning:** `FOR ALL` in Policy 2 also covers SELECT. PostgreSQL evaluates ALL matching policies with OR logic — so a row is visible if Policy 1 OR Policy 2 passes. This means the tenant-read policy handles visibility for all members, and the owner-write policy also incidentally allows the owner to SELECT (which is fine). The write restriction comes from Policy 2's `WITH CHECK` on INSERT/UPDATE only. DELETE uses `USING` from Policy 2. Reads use Policy 1's `USING` (any tenant member). This is the correct PostgreSQL multi-policy behavior.

### Pattern 2: ORM Model with Partial Indexes

The `Meeting` ORM class goes in `db/models.py` in the CRM TABLES section (after `OutreachActivity`). Follow existing patterns exactly:

```python
# Source: db/models.py existing pattern + SPEC-intelligence-flywheel.md MDE-02
from sqlalchemy import Index, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (
        Index(
            "idx_meetings_dedup",
            "tenant_id", "provider", "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index(
            "idx_meetings_account",
            "account_id", text("meeting_date DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_meetings_user",
            "tenant_id", "user_id", text("meeting_date DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_meetings_pending",
            "tenant_id", "processing_status",
            postgresql_where=text("processing_status = 'pending'"),
        ),
    )
    # ... (full spec in SPEC-intelligence-flywheel.md MDE-02)
```

**Note on `text()` inside `Index()`:** The existing `027_crm_tables.py` uses `sa.text()` inside `create_index()` for descending indexes. The ORM model uses `text()` from `sqlalchemy` inside `Index()`. Both are equivalent; the ORM pattern is already used in `WorkItem`, `Focus`, etc.

### Pattern 3: API Key Integration (Non-OAuth)

Granola uses a Bearer API key, not OAuth. The connect endpoint is simpler than Google Calendar but must still follow the Integration model pattern. Key differences vs OAuth providers:

1. No `pending` state needed — key is either valid or not at connect time
2. No state parameter or CSRF protection needed
3. Use `upsert` (update existing row if reconnecting) rather than always creating a new row
4. Validation by calling `GET /v1/notes?page_size=1` — NOT `/v1/me` (does not exist)

```python
# Source: SPEC-intelligence-flywheel.md GRA-01 (adapted for real API)
# In backend/src/flywheel/api/integrations.py

@router.post("/granola/connect")
async def connect_granola(
    body: dict,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    api_key = body.get("api_key", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key required")

    from flywheel.services.granola_adapter import test_connection
    valid, error = await test_connection(api_key)
    if not valid:
        raise HTTPException(status_code=400, detail=error)

    encrypted = encrypt_api_key(api_key)  # from flywheel.auth.encryption
    # upsert pattern — one Granola integration per user per tenant
    existing = (await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.user_id == user.sub,
            Integration.provider == "granola",
        )
    )).scalar_one_or_none()

    if existing:
        existing.credentials_encrypted = encrypted
        existing.status = "connected"
        existing.settings = {**existing.settings, "last_sync_cursor": None}
    else:
        db.add(Integration(
            tenant_id=user.tenant_id,
            user_id=user.sub,
            provider="granola",
            status="connected",
            credentials_encrypted=encrypted,
            settings={"last_sync_cursor": None, "processing_rules": {}},
        ))

    await db.commit()
    return {"status": "connected"}
```

### Pattern 4: Granola Adapter (Real API Shape)

The actual Granola API (verified at docs.granola.ai, March 2026):

- **Base URL:** `https://public-api.granola.ai/v1`
- **Auth:** `Authorization: Bearer <api_key>`
- **List notes:** `GET /v1/notes?page_size=N&cursor=...&created_after=...`
- **Get note:** `GET /v1/notes/{note_id}?include=transcript`
- **No `/v1/me` endpoint** — test_connection must call list endpoint
- **Response fields:** `id`, `title`, `owner`, `created_at`, `updated_at`, `calendar_event`, `attendees`, `summary_text`, `summary_markdown`, `transcript` (array when included)
- **Pagination:** cursor-based via `cursor` field in response, `hasMore` boolean
- **Note ID pattern:** `not_[a-zA-Z0-9]{14}` (e.g. `not_AbCdEf12345678`)
- **Rate limits:** 25 req/5s burst, 5 req/s sustained

The spec's adapter code assumes `/v1/meetings`, a `GET /v1/me` validation endpoint, a separate `/transcript` sub-resource, and `since` parameter named differently. The adapter must be rewritten to match the real API:

```python
# Source: https://docs.granola.ai/api-reference/list-notes.md (verified 2026-03-28)
GRANOLA_API_BASE = "https://public-api.granola.ai/v1"

async def test_connection(api_key: str) -> tuple[bool, str | None]:
    """Validate a Granola API key by listing one note."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"{GRANOLA_API_BASE}/notes",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"page_size": 1},
            )
            if resp.status_code == 200:
                return True, None
            elif resp.status_code == 401:
                return False, "Invalid API key. Check your Granola settings."
            else:
                return False, f"Granola API returned {resp.status_code}"
        except httpx.RequestError as e:
            return False, f"Could not reach Granola API: {e}"


async def list_meetings(
    api_key: str,
    since: datetime | None = None,
    limit: int = 30,  # max per page is 30
) -> list[RawMeeting]:
    """Fetch meeting list. Uses created_after for incremental sync."""
    params = {"page_size": limit}
    if since:
        params["created_after"] = since.isoformat()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{GRANOLA_API_BASE}/notes",
            headers={"Authorization": f"Bearer {api_key}"},
            params=params,
        )
        resp.raise_for_status()

    meetings = []
    for item in resp.json().get("notes", []):
        cal = item.get("calendar_event") or {}
        # Extract duration from calendar_event start/end if present
        start = cal.get("start_time")
        end = cal.get("end_time")
        duration = None
        if start and end:
            from datetime import datetime as dt
            try:
                d = (dt.fromisoformat(end) - dt.fromisoformat(start)).seconds // 60
                duration = d
            except Exception:
                pass

        # Attendees from calendar_event.invitees
        attendees = [
            {"email": a.get("email"), "name": a.get("name"), "is_external": True}
            for a in cal.get("invitees", [])
        ]

        meetings.append(RawMeeting(
            external_id=item["id"],
            title=item.get("title") or "Untitled",
            meeting_date=datetime.fromisoformat(item["created_at"]),
            duration_mins=duration,
            attendees=attendees,
            ai_summary=item.get("summary_text"),
        ))
    return meetings


async def get_meeting_content(api_key: str, external_id: str) -> MeetingContent:
    """Fetch full note content including transcript (single endpoint call)."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            f"{GRANOLA_API_BASE}/notes/{external_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"include": "transcript"},
        )
        resp.raise_for_status()

    detail = resp.json()

    # transcript is an array of {speaker, text, start_time, end_time}
    transcript_parts = detail.get("transcript") or []
    transcript_text = "\n".join(
        f"[{t.get('speaker', 'Unknown')}]: {t.get('text', '')}"
        for t in transcript_parts
    )

    cal = detail.get("calendar_event") or {}
    attendees = [
        {"email": a.get("email"), "name": a.get("name"), "is_external": True}
        for a in cal.get("invitees", [])
    ]

    return MeetingContent(
        external_id=external_id,
        transcript=transcript_text,
        ai_summary=detail.get("summary_text"),
        attendees=attendees,
        metadata={
            "provider": "granola",
            "title": detail.get("title"),
            "date": detail.get("created_at"),
        },
    )
```

### Pattern 5: Sync Endpoint with Dedup

The sync endpoint deduplicates by `(tenant_id, provider, external_id)` — matching the unique index defined on the table. The dedup logic checks existing rows before inserting. The `last_synced_at` field on `Integration` (already exists in ORM) is used as the `since` cursor.

```python
# Source: SPEC-intelligence-flywheel.md GRA-03 + codebase patterns
# In backend/src/flywheel/api/meetings.py

router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.post("/sync")
async def sync_meetings(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    # 1. Find connected Granola integration
    integration = (await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.user_id == user.sub,
            Integration.provider == "granola",
            Integration.status == "connected",
        )
    )).scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=400,
            detail="Granola not connected. Add your API key in Settings.")

    # 2. Decrypt and fetch
    from flywheel.auth.encryption import decrypt_api_key
    api_key = decrypt_api_key(integration.credentials_encrypted)
    since = integration.last_synced_at

    from flywheel.services.granola_adapter import list_meetings
    raw_meetings = await list_meetings(api_key, since=since)

    # 3. Dedup: find already-known external_ids
    existing_ids = set()
    if raw_meetings:
        ext_ids = [m.external_id for m in raw_meetings]
        rows = await db.execute(
            select(Meeting.external_id).where(
                Meeting.tenant_id == user.tenant_id,
                Meeting.provider == "granola",
                Meeting.external_id.in_(ext_ids),
            )
        )
        existing_ids = {r[0] for r in rows.all()}

    # 4. Insert new meetings with processing rules
    new_meetings = [m for m in raw_meetings if m.external_id not in existing_ids]
    rules = integration.settings.get("processing_rules", {})
    synced = skipped = 0

    for raw in new_meetings:
        status = _apply_processing_rules(raw, rules)
        db.add(Meeting(
            tenant_id=user.tenant_id,
            user_id=user.sub,
            provider="granola",
            external_id=raw.external_id,
            title=raw.title,
            meeting_date=raw.meeting_date,
            duration_mins=raw.duration_mins,
            attendees=raw.attendees,
            ai_summary=raw.ai_summary,
            processing_status=status,
        ))
        if status == "pending":
            synced += 1
        else:
            skipped += 1

    # 5. Update last_synced_at and commit
    from datetime import datetime, timezone
    integration.last_synced_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "synced": synced,
        "skipped": skipped,
        "already_seen": len(existing_ids),
        "total_from_provider": len(raw_meetings),
    }
```

### Anti-Patterns to Avoid

- **Using `/v1/me` for API key validation:** This endpoint does not exist in the Granola API. Use `GET /v1/notes?page_size=1` instead.
- **Calling a separate `/transcript` endpoint:** Transcripts are returned inline on `GET /v1/notes/{id}?include=transcript`. No second API call needed.
- **Using `since` parameter directly on Granola API:** The real parameter is `created_after` (ISO 8601 datetime string).
- **Building a FOR ALL write policy that blocks reads:** PostgreSQL multi-policy RLS uses OR logic — having two policies (tenant_read SELECT + owner_write ALL) is correct. The owner can still read their own meeting through Policy 1.
- **Alembic revision IDs longer than 32 chars:** Must be `<=32 chars`. Previous revisions use patterns like `031_user_level_rls`. Use `032_create_meetings_table` (26 chars, safe).
- **Forgetting `FORCE ROW LEVEL SECURITY`:** Required alongside `ENABLE ROW LEVEL SECURITY` so table owners bypass doesn't apply.
- **Forgetting `GRANT` statement:** The `027_crm_tables.py` migration GRANTs to `app_user`. The meetings migration must do the same.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| API key encryption | Custom encryption | `flywheel.auth.encryption.encrypt_api_key` / `decrypt_api_key` | Already AES-256-GCM, used by all other integrations |
| Dedup logic | Custom hash-based dedup | Unique index `idx_meetings_dedup` + SELECT before INSERT | PostgreSQL handles it; unique constraint prevents race condition dupes |
| HTTP client for Granola | Custom requests wrapper | `httpx.AsyncClient` with context manager | Already in deps, async-native, proper timeout handling |
| Processing rules | Custom rule engine | Simple dict-based rule check in `_apply_processing_rules()` | Rules are simple (skip_internal, skip_domain, min_duration); no library needed |

**Key insight:** The hardest part of this phase is reconciling the spec's assumed Granola API shape with the real API. Everything else reuses established codebase patterns exactly.

## Common Pitfalls

### Pitfall 1: Granola API Field Mapping Mismatch
**What goes wrong:** The spec assumes `external_id`, `meeting_date`, and `/v1/meetings` endpoints. The real API returns `id` (not `external_id`), uses `created_at` (not `meeting_date`), and serves `/v1/notes`.
**Why it happens:** Spec was written before verifying the real API.
**How to avoid:** Map `item["id"]` → `external_id`, `item["created_at"]` → `meeting_date`. Use `GET /v1/notes` throughout.
**Warning signs:** 404 errors on API calls, empty meeting lists, field KeyErrors.

### Pitfall 2: Duration Extraction from Calendar Event
**What goes wrong:** Granola's `/v1/notes` list endpoint does not return `duration_mins` as a direct field. Duration must be computed from `calendar_event.start_time` and `calendar_event.end_time`.
**Why it happens:** The spec's `RawMeeting.duration_mins` field implied a direct API field.
**How to avoid:** Compute duration in the adapter using `(end - start).seconds // 60`. Handle `None` for calls without calendar events.
**Warning signs:** `duration_mins` always being `None`, or KeyError on `duration_mins`.

### Pitfall 3: Two-Policy RLS Write Blocking
**What goes wrong:** If Policy 2 (`meetings_owner_write`) is set as `FOR ALL` and Policy 1 (`meetings_tenant_read`) is only `FOR SELECT`, a non-owner tenant member's INSERT would fail because no write policy grants them access. But this is intentional — only the meeting owner inserts their own meetings. A common mistake is trying to allow team members to INSERT rows created by others.
**Why it happens:** Misunderstanding of RLS multi-policy OR logic.
**How to avoid:** Accept the design: only `user_id == current_user` can INSERT/UPDATE/DELETE meetings. All tenant members can SELECT. The sync endpoint always inserts as the authenticated user.
**Warning signs:** 403 errors on INSERT for non-owner users (correct behavior), or 0 rows returned for tenant members who aren't the owner (incorrect if SELECT policy is broken).

### Pitfall 4: Integration `last_synced_at` vs `last_sync_cursor`
**What goes wrong:** The spec's GRA-01 mentions `last_sync_cursor: null` in `settings`, while the `Integration` ORM already has a `last_synced_at` TIMESTAMPTZ column. The sync endpoint should use `integration.last_synced_at` (the column), not a value nested in `settings`.
**Why it happens:** Spec was written before checking the existing ORM model.
**How to avoid:** Use `integration.last_synced_at` directly. Pass it as `created_after` to the Granola API. Update it after sync. Do NOT add a redundant `last_sync_cursor` field in `settings`.
**Warning signs:** Always syncing all meetings (not using cursor), or storing cursor in settings when the column exists.

### Pitfall 5: Alembic Revision ID Length
**What goes wrong:** Revision ID exceeds 32 chars and migration fails.
**Why it happens:** Long descriptive names.
**How to avoid:** Use `032_create_meetings_table` (26 chars). Check: `len("032_create_meetings_table") == 25`.
**Warning signs:** `alembic upgrade` complains about revision ID length.

### Pitfall 6: Granola API Rate Limits
**What goes wrong:** Syncing a large backlog of meetings hits the 25 req/5s burst limit.
**Why it happens:** Unthrottled concurrent calls.
**How to avoid:** Phase 60 only calls `list_meetings` (one call) and does NOT fetch full content (`get_meeting_content` is for the processing pipeline in Phase 61+). The sync endpoint stays within rate limits for all realistic use cases.
**Warning signs:** HTTP 429 responses from Granola.

## Code Examples

### Migration File Header (correct revision ID length)

```python
# Source: 027_crm_tables.py, 031_user_level_rls.py patterns

"""Create meetings table with split-visibility RLS.

Adds the meetings table as a first-class CRM entity. Metadata is
visible to all tenant members; transcript content is user-scoped
via API and Storage policies.

Revision ID: 032_create_meetings_table
Revises: 031_user_level_rls
Create Date: 2026-03-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "032_create_meetings_table"
down_revision: Union[str, None] = "031_user_level_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

### Encryption Import in integrations.py

```python
# Source: flywheel/auth/encryption.py + flywheel/services/google_calendar.py pattern
from flywheel.auth.encryption import encrypt_api_key, decrypt_api_key

# Encrypt before storing:
encrypted = encrypt_api_key(api_key)  # returns bytes for LargeBinary column

# Decrypt when needed:
plaintext = decrypt_api_key(integration.credentials_encrypted)  # returns str
```

### Register meetings.py router in main.py

```python
# Source: flywheel/main.py existing pattern
from flywheel.api.meetings import router as meetings_router
# ... add to app.include_router() calls
app.include_router(meetings_router, prefix="/api/v1")
```

### Add "granola" to provider display map in integrations.py

```python
_PROVIDER_DISPLAY = {
    "google-calendar": "Google Calendar",
    "gmail": "Gmail",
    "gmail-read": "Gmail (Read)",
    "outlook": "Outlook",
    "slack": "Slack",
    "granola": "Granola",  # add this
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Granola had no public API | Personal + Enterprise API launched | Feb-Mar 2026 | Enables this integration |
| `/v1/meetings` (assumed) | `/v1/notes` (actual) | API design | Must update adapter code |
| Separate transcript endpoint | `?include=transcript` on GET /v1/notes/{id} | Current | Single call fetches everything |
| `/v1/me` for validation | No such endpoint — use `GET /v1/notes?page_size=1` | Current | Test connection approach differs |

## Open Questions

1. **Granola API key prefix format**
   - What we know: Docs show `grn_YOUR_API_KEY` format in examples; personal API keys are created in Granola desktop app Settings → API → Personal API key
   - What's unclear: Whether the key prefix `grn_` is stable or an example; whether the adapter should validate the key format locally before making an API call
   - Recommendation: Do NOT validate prefix locally — just send it to the API and return the error message as-is if invalid

2. **Granola `calendar_event` field presence**
   - What we know: List endpoint response includes `owner`, `title`, `created_at`, `updated_at`; full note includes `calendar_event` with invitees
   - What's unclear: Whether `calendar_event` is always present in the list response or only in the full note response
   - Recommendation: Fetch attendees/duration from full note (`get_meeting_content`) rather than the list response. For Phase 60's sync (which only creates meeting rows), store `attendees: []` from the list and populate them from the full note during processing (Phase 61+)

3. **Supabase Storage bucket for transcripts**
   - What we know: The spec references `transcripts/{tenant_id}/{meeting_id}.txt` as the storage path; the health endpoint already checks for an `uploads` bucket
   - What's unclear: Whether a separate `transcripts` bucket is needed or if the existing `uploads` bucket is reused; Phase 60 does NOT upload transcripts (only Phase 61+)
   - Recommendation: Phase 60 does not upload any transcripts (deferred to processing pipeline). The `transcript_url` column can remain NULL for all synced meetings. No storage bucket needed in this phase.

4. **Granola `updated_after` vs `created_after` for incremental sync**
   - What we know: Both `created_after` and `updated_after` params exist on `GET /v1/notes`; `Integration.last_synced_at` tracks last sync time
   - What's unclear: Should incremental sync use `created_after` (only new meetings) or `updated_after` (also catches edits to existing meetings)
   - Recommendation: Use `created_after` in Phase 60 to keep scope minimal (new meetings only). Updated content sync is a Phase 61+ concern.

## Sources

### Primary (HIGH confidence)
- `https://docs.granola.ai/api-reference/list-notes.md` — List endpoint URL, parameters, response fields verified 2026-03-28
- `https://docs.granola.ai/api-reference/get-note.md` — Get note endpoint, transcript via `?include=transcript` verified 2026-03-28
- `https://docs.granola.ai/api-reference/openapi.json` — OpenAPI spec confirms exactly 2 endpoints, no `/v1/me`, Bearer auth verified 2026-03-28
- `backend/src/flywheel/auth/encryption.py` — AES-256-GCM encrypt/decrypt pattern
- `backend/alembic/versions/027_crm_tables.py` — Table creation + GRANT + RLS policy migration pattern
- `backend/alembic/versions/031_user_level_rls.py` — User isolation RLS policy pattern, `current_setting('app.user_id', true)` usage
- `backend/src/flywheel/db/models.py` — Integration, Account, SkillRun ORM patterns
- `backend/src/flywheel/api/integrations.py` — Provider connect endpoint pattern
- `backend/pyproject.toml` — Dependency versions confirmed (httpx, cryptography, sqlalchemy)

### Secondary (MEDIUM confidence)
- `https://docs.granola.ai/help-center/sharing/integrations/personal-api.md` — Personal API key acquisition flow (Business/Enterprise plan required)
- Granola API rate limits (25 req/5s burst, 5 req/s sustained) — from docs.granola.ai introduction page

### Tertiary (LOW confidence)
- Granola `calendar_event` field availability in list vs. detail responses — not explicitly documented, inferred from OpenAPI schema shape

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in pyproject.toml
- Architecture patterns: HIGH — derived from codebase patterns + real API verification
- Alembic migration: HIGH — revision ID constraint documented in prior decisions, pattern from 027/031
- RLS split-visibility: HIGH — spec design verified against PostgreSQL multi-policy OR semantics
- Granola API shape: HIGH — verified against official OpenAPI spec at docs.granola.ai
- Granola attendees/duration in list response: MEDIUM — OpenAPI schema shows `calendar_event` in GET /note, less clear for list
- Supabase Storage for transcripts: HIGH (deferred to Phase 61 — not needed in Phase 60)

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (Granola API is newly launched and could change; re-verify if > 2 weeks old)
