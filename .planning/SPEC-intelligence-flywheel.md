# Spec: Intelligence Flywheel Engine

> Source: CONCEPT-BRIEF-intelligence-flywheel.md
> Prerequisite: SPEC-team-privacy-foundation.md (Phase 59)
> Created: 2026-03-28

## Overview

The Intelligence Flywheel Engine turns every conversation into structured CRM intelligence that compounds over time. It connects external meeting sources (starting with Granola), ingests transcripts through a shared extraction pipeline, writes structured intelligence to the context store, auto-links meetings to accounts/contacts, and enriches every relationship surface in the system. The engine closes the loop by powering meeting prep from the enriched context, so each meeting produces richer intelligence than the last. This is the centerpiece feature that transforms Flywheel from a manually-populated CRM into an intelligence platform that gets smarter with every conversation.

## Requirements

### Data Model

#### MDE-01: Meetings Table

Create the `meetings` table as a first-class entity in the data model. Meetings are distinct from `SkillRun` (which tracks processing jobs) and from `ContextEntry` (which stores extracted intelligence). The meetings table is the canonical record of "a conversation happened."

```sql
CREATE TABLE meetings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID NOT NULL REFERENCES profiles(id),

    -- Source tracking
    provider        TEXT NOT NULL,           -- 'granola', 'fathom', 'fireflies', 'manual-upload'
    external_id     TEXT,                    -- provider's meeting ID (dedup key)

    -- Meeting metadata (SHARED — visible to all team members)
    title           TEXT,
    meeting_date    TIMESTAMPTZ NOT NULL,
    duration_mins   INT,
    attendees       JSONB,                   -- [{email, name, role, is_external}]

    -- Content (PRIVATE — transcript visible to meeting owner only)
    transcript_url  TEXT,                    -- Supabase Storage path (not inline)
    ai_summary      TEXT,                    -- Provider's AI summary (Granola, Fathom, etc.)

    -- Extracted intelligence (read-path cache, source of truth is context_entries)
    summary         JSONB,                   -- {tldr, key_decisions, action_items, attendee_roles, pain_points}
    meeting_type    TEXT,                    -- discovery, prospect, advisor, investor-pitch, internal, etc.

    -- Relationship linking
    account_id      UUID REFERENCES accounts(id),  -- auto-inferred from attendee domains

    -- Processing tracking
    skill_run_id    UUID REFERENCES skill_runs(id),
    processed_at    TIMESTAMPTZ,
    processing_status TEXT DEFAULT 'pending', -- pending, processing, complete, failed, skipped

    -- Standard fields
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ              -- soft delete
);

-- Dedup: one meeting per provider + external_id per tenant
CREATE UNIQUE INDEX idx_meetings_dedup
    ON meetings(tenant_id, provider, external_id)
    WHERE external_id IS NOT NULL;

-- Fast queries by account for relationship timeline
CREATE INDEX idx_meetings_account
    ON meetings(account_id, meeting_date DESC)
    WHERE deleted_at IS NULL;

-- Fast queries by user for "my meetings" view
CREATE INDEX idx_meetings_user
    ON meetings(tenant_id, user_id, meeting_date DESC)
    WHERE deleted_at IS NULL;

-- Processing queue: find pending meetings
CREATE INDEX idx_meetings_pending
    ON meetings(tenant_id, processing_status)
    WHERE processing_status = 'pending';

-- RLS policies (split visibility model)
ALTER TABLE meetings ENABLE ROW LEVEL SECURITY;

-- Policy 1: Metadata visible to all tenant members
CREATE POLICY meetings_tenant_read ON meetings
    FOR SELECT
    USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Policy 2: Only meeting owner can INSERT/UPDATE/DELETE
CREATE POLICY meetings_owner_write ON meetings
    FOR ALL
    USING (
        tenant_id = current_setting('app.tenant_id')::uuid
        AND user_id = current_setting('app.user_id')::uuid
    );
```

**Privacy enforcement note:** The RLS policies allow all tenant members to SELECT meeting rows (metadata, summary JSONB, meeting_type, attendees, account link). However, the `transcript_url` column contains a Supabase Storage path — access to the actual transcript file is controlled by a Supabase Storage policy that restricts download to `user_id` match. This means the URL is visible but the content is not. The API layer adds an additional guard: the `GET /meetings/{id}` detail endpoint omits `transcript_url` and `ai_summary` from the response unless the requesting user is the meeting owner.

#### MDE-02: Meeting ORM Model

Add to `backend/src/flywheel/db/models.py`, in the CRM tables section alongside `Account`, `AccountContact`, and `OutreachActivity`:

```python
class Meeting(Base):
    """A meeting ingested from an external source (Granola, Fathom, etc.)
    or uploaded manually. First-class entity in the CRM data model.

    Privacy model: metadata is tenant-visible, transcript is user-scoped.
    Extracted intelligence flows to context_entries (tenant-visible).
    """

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

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )

    # Source tracking
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)

    # Meeting metadata (shared)
    title: Mapped[str | None] = mapped_column(Text)
    meeting_date: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    duration_mins: Mapped[int | None] = mapped_column(Integer)
    attendees: Mapped[dict | None] = mapped_column(JSONB)

    # Content (private — access controlled at API + storage layer)
    transcript_url: Mapped[str | None] = mapped_column(Text)
    ai_summary: Mapped[str | None] = mapped_column(Text)

    # Extracted intelligence cache
    summary: Mapped[dict | None] = mapped_column(JSONB)
    meeting_type: Mapped[str | None] = mapped_column(Text)

    # Relationship linking
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )

    # Processing tracking
    skill_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("skill_runs.id")
    )
    processed_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    processing_status: Mapped[str] = mapped_column(
        Text, server_default="pending"
    )

    # Standard fields
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    # Relationships
    account: Mapped["Account | None"] = relationship()
    skill_run: Mapped["SkillRun | None"] = relationship()
```

**Alembic migration:** Create `backend/alembic/versions/0XX_create_meetings_table.py` following the pattern of existing migrations (e.g., `023_tenant_company_link.py`). The migration creates the table, all indexes, and RLS policies.

### Granola Integration

#### GRA-01: Granola Integration Flow

Granola uses a personal API key (Bearer token), not OAuth. The integration flow is simpler than Google Calendar/Gmail but follows the same `Integration` model pattern from `backend/src/flywheel/api/integrations.py`.

**Storage:** A single `Integration` row with:
- `provider = "granola"`
- `credentials_encrypted` = AES-256-GCM encrypted API key (same encryption used for Google Calendar OAuth tokens — see `serialize_credentials()` pattern)
- `settings` = `{"last_sync_cursor": null, "processing_rules": {...}}` (see MPP-05 for processing_rules schema)
- `status` = `"connected"` | `"disconnected"` | `"error"`

**Connection flow:**
1. User navigates to Settings page, enters Granola API key
2. Frontend calls `POST /integrations/granola/connect` with `{"api_key": "gra_..."}`
3. Backend validates the key by calling Granola's `GET /v1/me` endpoint
4. On success: encrypt API key, create Integration row, return `{"status": "connected"}`
5. On failure: return 400 with descriptive error (invalid key, expired, rate limited)

**API endpoint** (add to `backend/src/flywheel/api/integrations.py`):

```python
@router.post("/granola/connect")
async def connect_granola(
    body: dict,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Connect Granola via API key (not OAuth).

    Validates the key against Granola's API, encrypts it,
    and creates/updates an Integration row.
    """
    api_key = body.get("api_key", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key required")

    # Validate against Granola API
    from flywheel.services.granola_adapter import test_connection
    valid, error = await test_connection(api_key)
    if not valid:
        raise HTTPException(status_code=400, detail=error)

    # Upsert: one Granola integration per user per tenant
    existing = (await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.user_id == user.sub,
            Integration.provider == "granola",
        )
    )).scalar_one_or_none()

    encrypted = _encrypt_api_key(api_key)  # AES-256-GCM, same pattern as OAuth

    if existing:
        existing.credentials_encrypted = encrypted
        existing.status = "connected"
        existing.settings = {**existing.settings, "last_sync_cursor": None}
    else:
        integration = Integration(
            tenant_id=user.tenant_id,
            user_id=user.sub,
            provider="granola",
            status="connected",
            credentials_encrypted=encrypted,
            settings={"last_sync_cursor": None, "processing_rules": {}},
        )
        db.add(integration)

    await db.commit()
    return {"status": "connected"}
```

#### GRA-02: Granola Adapter

Implement the `IntelligenceSource` interface as `backend/src/flywheel/services/granola_adapter.py`. The interface is deliberately minimal — three methods — because the intelligence extraction pipeline does not care where content comes from.

```python
"""Granola meeting source adapter.

Implements the IntelligenceSource interface for Granola's REST API.
Handles: list meetings, fetch full content, test connection.
"""

from __future__ import annotations
import httpx
from datetime import datetime
from dataclasses import dataclass

GRANOLA_API_BASE = "https://api.granola.ai/v1"


@dataclass
class RawMeeting:
    """Lightweight meeting metadata from list endpoint."""
    external_id: str
    title: str
    meeting_date: datetime
    duration_mins: int | None
    attendees: list[dict]   # [{email, name, role, is_external}]
    ai_summary: str | None  # Granola's own AI summary


@dataclass
class MeetingContent:
    """Full meeting content for processing."""
    external_id: str
    transcript: str          # Full verbatim transcript text
    ai_summary: str | None   # Granola's AI summary (distinct from transcript)
    attendees: list[dict]
    metadata: dict           # Provider-specific metadata


async def test_connection(api_key: str) -> tuple[bool, str | None]:
    """Validate a Granola API key.

    Calls GET /v1/me. Returns (True, None) on success,
    (False, error_message) on failure.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"{GRANOLA_API_BASE}/me",
                headers={"Authorization": f"Bearer {api_key}"},
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
    limit: int = 50,
) -> list[RawMeeting]:
    """Fetch meeting list from Granola.

    Calls GET /v1/meetings with optional since filter.
    Returns lightweight metadata — no transcripts (cheap call).
    """
    params = {"limit": limit}
    if since:
        params["since"] = since.isoformat()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{GRANOLA_API_BASE}/meetings",
            headers={"Authorization": f"Bearer {api_key}"},
            params=params,
        )
        resp.raise_for_status()

    meetings = []
    for item in resp.json().get("meetings", []):
        meetings.append(RawMeeting(
            external_id=item["id"],
            title=item.get("title", "Untitled"),
            meeting_date=datetime.fromisoformat(item["date"]),
            duration_mins=item.get("duration_mins"),
            attendees=item.get("attendees", []),
            ai_summary=item.get("ai_summary"),
        ))
    return meetings


async def get_meeting_content(
    api_key: str,
    external_id: str,
) -> MeetingContent:
    """Fetch full meeting content including transcript.

    Makes two calls:
    1. GET /v1/meetings/{id} — metadata + AI summary
    2. GET /v1/meetings/{id}/transcript — full verbatim transcript

    This is the expensive call (transcript can be 10k+ tokens).
    Only called for meetings that pass processing filters.
    """
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=60) as client:
        # Fetch meeting details + AI summary
        detail_resp = await client.get(
            f"{GRANOLA_API_BASE}/meetings/{external_id}",
            headers=headers,
        )
        detail_resp.raise_for_status()
        detail = detail_resp.json()

        # Fetch transcript separately
        transcript_resp = await client.get(
            f"{GRANOLA_API_BASE}/meetings/{external_id}/transcript",
            headers=headers,
        )
        transcript_resp.raise_for_status()
        transcript_data = transcript_resp.json()

    return MeetingContent(
        external_id=external_id,
        transcript=transcript_data.get("text", ""),
        ai_summary=detail.get("ai_summary"),
        attendees=detail.get("attendees", []),
        metadata={
            "provider": "granola",
            "title": detail.get("title"),
            "date": detail.get("date"),
            "duration_mins": detail.get("duration_mins"),
        },
    )
```

**Future adapters** (deferred, not v1): `FathomAdapter` (REST, Bearer), `FirefliesAdapter` (GraphQL, Bearer). Same interface, different I/O. Adding a new source should be ~200 lines.

#### GRA-03: Meeting Sync Endpoint

`POST /meetings/sync` triggers a sync from the user's connected Granola account. It creates a parent `SkillRun` for the sync operation, fetches the meeting list, deduplicates against existing `meetings` rows, inserts new meeting rows, and returns sync stats. Processing happens separately (see MPP-01).

**Add to a new file:** `backend/src/flywheel/api/meetings.py`

```python
router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/sync")
async def sync_meetings(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Sync meetings from connected Granola account.

    1. Find user's Granola Integration row
    2. Decrypt API key
    3. Call list_meetings(since=last_synced_at)
    4. Dedup against existing meetings (external_id match)
    5. Insert new meeting rows with processing_status='pending'
    6. Apply processing rules (skip internal, skip by domain, etc.)
    7. Create SkillRun for each meeting to process
    8. Update Integration.last_synced_at
    9. Return sync stats: {synced: N, skipped: N, already_seen: N}
    """
    # Step 1: Find Granola integration
    integration = (await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.user_id == user.sub,
            Integration.provider == "granola",
            Integration.status == "connected",
        )
    )).scalar_one_or_none()

    if not integration:
        raise HTTPException(
            status_code=400,
            detail="Granola not connected. Add your API key in Settings."
        )

    # Step 2: Decrypt and fetch
    api_key = _decrypt_api_key(integration.credentials_encrypted)
    since = integration.last_synced_at

    from flywheel.services.granola_adapter import list_meetings
    raw_meetings = await list_meetings(api_key, since=since)

    # Step 3: Dedup
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

    # Step 4-6: Insert new meetings, apply rules
    new_meetings = [m for m in raw_meetings if m.external_id not in existing_ids]
    rules = integration.settings.get("processing_rules", {})

    synced = 0
    skipped = 0
    for raw in new_meetings:
        status = _apply_processing_rules(raw, rules)  # 'pending' or 'skipped'
        meeting = Meeting(
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
        )
        db.add(meeting)
        if status == "pending":
            synced += 1
        else:
            skipped += 1

    # Step 7: Create SkillRuns for pending meetings (after flush to get IDs)
    await db.flush()
    # SkillRun creation happens in the processing pipeline (MPP-01)

    # Step 8: Update last_synced_at
    integration.last_synced_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "synced": synced,
        "skipped": skipped,
        "already_seen": len(existing_ids),
        "total_from_provider": len(raw_meetings),
    }
```

### Meeting Processing Pipeline

#### MPP-01: Meeting Processor Engine

Add `_execute_meeting_processor()` to `backend/src/flywheel/services/skill_executor.py`, following the exact same pattern as `_execute_company_intel()` (lines 840-1200+). The engine processes a single meeting through staged pipeline steps, emitting SSE events at each stage for real-time frontend feedback.

**Processing stages:**

```
Stage 1: "fetching"     — Fetch full transcript via Granola adapter
Stage 2: "storing"      — Upload transcript to Supabase Storage
Stage 3: "classifying"  — Classify meeting type (Haiku tier)
Stage 4: "extracting"   — Extract 9 insight types (Sonnet tier)
Stage 5: "linking"      — Auto-link to account, discover contacts
Stage 6: "writing"      — Write to 7 context files
Stage 7: "done"         — Update meeting row, emit completion
```

**Function signature and flow:**

```python
async def _execute_meeting_processor(
    factory: Callable,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    meeting_id: UUID,
    api_key: str | None = None,
) -> tuple[str, dict, list]:
    """Process a single meeting through the intelligence pipeline.

    Follows the company-intel execution pattern:
    - factory: async session factory for DB access
    - run_id: SkillRun ID for SSE event appending
    - Each stage emits events via _append_event_atomic()
    - Returns (output_text, metadata_dict, tool_calls_list)
    """
    from flywheel.db.models import Meeting, Integration
    from flywheel.services.granola_adapter import get_meeting_content
    from flywheel.storage import upload_to_storage

    output_parts = []
    tool_calls = []

    # Load meeting row
    async with factory() as sess:
        await sess.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        meeting = (await sess.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )).scalar_one_or_none()

    if not meeting:
        return "Meeting not found", {}, tool_calls

    # Update status to processing
    async with factory() as sess:
        await sess.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        meeting_row = (await sess.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )).scalar_one()
        meeting_row.processing_status = "processing"
        meeting_row.skill_run_id = run_id
        await sess.commit()

    # Stage 1: Fetch transcript
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "fetching", "message": f"Fetching transcript for: {meeting.title}..."},
    })

    # Decrypt Granola API key from Integration
    async with factory() as sess:
        await sess.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        integration = (await sess.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.user_id == user_id,
                Integration.provider == meeting.provider,
                Integration.status == "connected",
            )
        )).scalar_one_or_none()

    if not integration:
        # ... error handling, mark meeting as failed
        return "Integration not connected", {}, tool_calls

    api_key_provider = _decrypt_api_key(integration.credentials_encrypted)
    content = await get_meeting_content(api_key_provider, meeting.external_id)
    tool_calls.append({"tool": "get_meeting_content", "input": meeting.external_id})

    # Stage 2: Store transcript in Supabase Storage
    await _append_event_atomic(factory, run_id, {
        "event": "stage",
        "data": {"stage": "storing", "message": "Storing transcript..."},
    })
    transcript_path = f"transcripts/{tenant_id}/{meeting.id}.txt"
    await upload_to_storage(transcript_path, content.transcript)

    # Stage 3: Classify (see MPP-02)
    # Stage 4: Extract (see MPP-03)
    # Stage 5: Auto-link (see AAL-01, AAL-02, AAL-03)
    # Stage 6: Write context (see MPP-04)
    # Stage 7: Finalize
    # ... (see subsequent requirements for each stage's implementation)
```

**SSE events** follow the exact same schema as the company-intel engine. The frontend `useProfileRefresh` hook (at `frontend/src/features/profile/hooks/useProfileRefresh.ts`) handles `stage`, `discovery`, `done`, and `error` event types via `useSSE()`. The meeting processor emits the same event types so the same SSE infrastructure works without modification.

#### MPP-02: Meeting Type Classification

Classify each meeting into one of 8 types using Haiku for cost efficiency (~$0.01/meeting).

**8 Meeting Types:**

| Type | Code | Primary Write Targets |
|------|------|-----------------------|
| Discovery Call | `discovery` | pain-points, icp-profiles, contacts, competitive-intel |
| Expert Call | `expert` | pain-points, competitive-intel, insights |
| Prospect Call | `prospect` | contacts, pain-points, icp-profiles, competitive-intel |
| Advisor Session | `advisor` | insights, action-items |
| Investor Pitch | `investor-pitch` | insights, action-items, product-feedback |
| Internal Meeting | `internal` | action-items, insights |
| Customer Feedback | `customer-feedback` | product-feedback, pain-points, contacts |
| Team Meeting | `team-meeting` | action-items, insights |

**Classification logic (3-layer precedence):**

1. **Contact match** (highest priority): Query `account_contacts` table for attendee emails. If any attendee matches a known contact on an account with `relationship_type`:
   - `prospect` in types -> classify as `prospect`
   - `customer` in types -> classify as `customer-feedback`
   - `advisor` in types -> classify as `advisor`
   - `investor` in types -> classify as `investor-pitch`

2. **Internal check**: If ALL attendee emails share the same domain as the tenant's domain (`tenants.domain`), classify as `internal` or `team-meeting` (based on attendee count: <=3 = `internal`, >3 = `team-meeting`).

3. **LLM classification** (Haiku): For remaining meetings, send title + attendee names + first 500 chars of transcript to Haiku with a classification prompt. Use Granola's AI summary as a classification accelerator when available.

```python
async def classify_meeting(
    title: str,
    attendees: list[dict],
    transcript_preview: str,
    ai_summary: str | None,
    known_contacts: dict[str, str],  # email -> relationship_type
    tenant_domain: str,
    api_key: str | None = None,
) -> str:
    """Classify meeting into one of 8 types.

    Layer 1: Contact match (DB lookup, no LLM cost)
    Layer 2: Internal check (domain comparison, no LLM cost)
    Layer 3: LLM classification (Haiku, ~$0.01)
    """
```

#### MPP-03: Intelligence Extraction Prompt

The LLM extraction step uses Sonnet (~$0.15-0.25/meeting) and extracts 9 insight types from the transcript + AI summary. This adapts the existing `skills/meeting-processor/SKILL.md` extraction logic for server-side execution.

**9 Insight Types:**

1. **Hair on Fire Problems** — severity 1-5, painkiller/vitamin classification
2. **ICP Discovery Signals** — confirm existing or reveal new customer segments
3. **Workflow Details** — tools, steps, time, team size, costs mentioned
4. **Buying Signals & Willingness to Pay** — budget, timeline, decision process
5. **Competitor Intelligence** — tools mentioned, pricing, switching reasons
6. **Objections & Resistance** — blockers, regulatory, political concerns
7. **Quotable Moments** — exact phrases for pitch decks, marketing
8. **Cross-Call Patterns** — "3rd prospect this month mentioning compliance pain"
9. **Follow-up Linking** — relationship progression, prior meeting references

**Extraction depth by meeting type:**

| Type | All 9 Insights | Context Files | Notes |
|------|:--------------:|:-------------:|-------|
| `discovery` | Yes | All 7 | Full extraction |
| `expert` | Yes | All 7 | Full extraction |
| `prospect` | Yes | All 7 | Emphasis on buying signals |
| `advisor` | Partial | insights, action-items | Strategic advice, intros, market intel |
| `investor-pitch` | Partial | insights, action-items, product-feedback | Feedback, signals |
| `internal` | No | action-items, insights | Lightweight |
| `customer-feedback` | Partial | product-feedback, pain-points, contacts | Account health, expansion |
| `team-meeting` | No | action-items, insights | Lightweight |

**Prompt structure:**

```python
EXTRACTION_SYSTEM_PROMPT = """You are an intelligence extraction engine for a CRM system.
Given a meeting transcript and optional AI summary, extract structured intelligence.

Meeting type: {meeting_type}
Meeting date: {meeting_date}
Attendees: {attendees_formatted}

Extract the following into a JSON object:
{extraction_schema_for_type}

Rules:
- Distinguish speakers: prefix with role (Prospect:, Team:, Advisor:, Customer:)
- Extract partial contacts: name only is acceptable
- Exact quotes for quotable moments (no paraphrasing)
- Feature requests go to product_feedback, not pain_points
- Rate pain severity 1-5 with painkiller/vitamin classification
- For cross-call patterns: reference prior context when provided

Return ONLY valid JSON. No markdown fencing."""


EXTRACTION_USER_PROMPT = """## Transcript

{transcript}

## AI Summary (from meeting recording tool)

{ai_summary_or_none}

## Existing Context (for cross-referencing)

{existing_context_summary}"""
```

**Dual-source extraction:** When both transcript and Granola AI summary are available, the extraction prompt receives both. The transcript provides raw detail and exact quotes; the AI summary provides Granola's distillation from full audio (may capture things the transcript text misses). Items found only in the summary are tagged `[from-summary]`.

**LLM call pattern** (mirrors `structure_intelligence()` in `company_intel.py`):

```python
async def extract_meeting_intelligence(
    transcript: str,
    ai_summary: str | None,
    meeting_type: str,
    meeting_date: str,
    attendees: list[dict],
    existing_context: dict,
    api_key: str | None = None,
) -> dict:
    """Extract structured intelligence from a meeting.

    Uses Sonnet for deep extraction (~$0.15-0.25/meeting).
    Returns dict with keys matching the 7 context file targets.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=EXTRACTION_SYSTEM_PROMPT.format(...),
        messages=[{"role": "user", "content": EXTRACTION_USER_PROMPT.format(...)}],
    )
    # Parse JSON response, validate schema, return
```

#### MPP-04: Context Store Writes

After extraction, write structured intelligence to 7 context files using the existing `append_entry()` pattern from `backend/src/flywheel/storage.py`.

**7 Context Files and Entry Format:**

| File | What Gets Written | Source Tag |
|------|-------------------|------------|
| `competitive-intel.md` | Competitor mentions, pricing, switching signals, speaker attribution | `ctx-meeting-processor` |
| `pain-points.md` | Problems with severity, speaker attribution, painkiller/vitamin | `ctx-meeting-processor` |
| `icp-profiles.md` | Company segments, buying signals, decision-maker info | `ctx-meeting-processor` |
| `contacts.md` | Per-person: name, title, company, role, meeting history, notes | `ctx-meeting-processor` |
| `insights.md` | Strategic takeaways, quotable moments, cross-call patterns | `ctx-meeting-processor` |
| `action-items.md` | Commitments with owners, due dates, team vs external | `ctx-meeting-processor` |
| `product-feedback.md` | Feature requests, reactions, demo feedback | `ctx-meeting-processor` |

**Entry creation** (using the existing `ContextEntry` model and `append_entry` from `backend/src/flywheel/storage.py`):

```python
async def write_meeting_intelligence(
    factory: Callable,
    tenant_id: UUID,
    user_id: UUID,
    meeting_id: UUID,
    meeting_date: str,
    meeting_slug: str,  # e.g., "meeting-2026-03-28-acme-discovery"
    extracted: dict,
    account_id: UUID | None = None,
) -> dict[str, str]:
    """Write extracted intelligence to context store.

    Creates one ContextEntry per context file (max 7 entries per meeting).
    Returns dict of {file_name: status} for reporting.

    Dedup: checks for existing entry with same source + detail tag.
    If found, skips write (idempotent).
    """
    from flywheel.storage import append_entry as async_append_entry

    write_results = {}
    source = "ctx-meeting-processor"
    detail = f"meeting-{meeting_slug}"

    file_mapping = {
        "competitive_intel": "competitive-intel.md",
        "pain_points": "pain-points.md",
        "icp_profiles": "icp-profiles.md",
        "contacts": "contacts.md",
        "insights": "insights.md",
        "action_items": "action-items.md",
        "product_feedback": "product-feedback.md",
    }

    for extract_key, file_name in file_mapping.items():
        content_lines = extracted.get(extract_key)
        if not content_lines:
            continue

        # Dedup check
        async with factory() as sess:
            await sess.execute(
                sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            existing = (await sess.execute(
                select(ContextEntry).where(
                    ContextEntry.tenant_id == tenant_id,
                    ContextEntry.file_name == file_name,
                    ContextEntry.source == source,
                    ContextEntry.detail == detail,
                    ContextEntry.deleted_at.is_(None),
                )
            )).scalar_one_or_none()

        if existing:
            write_results[file_name] = "skipped (duplicate)"
            continue

        # Format content lines into single entry
        content = "\n".join(content_lines) if isinstance(content_lines, list) else content_lines

        await async_append_entry(
            factory=factory,
            tenant_id=tenant_id,
            user_id=user_id,
            file_name=file_name,
            source=source,
            detail=detail,
            content=content,
            confidence="medium",
            date=meeting_date,
            account_id=account_id,
        )
        write_results[file_name] = "written"

    return write_results
```

**Key property:** All `ContextEntry` rows created by the meeting processor have `visibility='team'` (the default). This means extracted intelligence is visible to all team members even though the source transcript is private. This is the core privacy boundary: raw content goes in private, structured intelligence comes out shared.

#### MPP-05: Processing Rules Engine

User-configurable rules stored in `Integration.settings["processing_rules"]` JSONB.

**Default behavior:** Auto-process all meetings with at least one external attendee.

**Rules schema:**

```json
{
  "processing_rules": {
    "skip_internal": true,
    "skip_domains": ["family.com", "personal.net"],
    "skip_meeting_types": [],
    "skip_recurring_same_attendees": false,
    "manually_skipped": ["granola-meeting-id-123"]
  }
}
```

**Rule evaluation function:**

```python
def _apply_processing_rules(meeting: RawMeeting, rules: dict) -> str:
    """Apply processing rules to determine if a meeting should be processed.

    Returns 'pending' (process) or 'skipped' (skip).
    """
    # Rule 1: Skip manually-excluded meetings
    if meeting.external_id in rules.get("manually_skipped", []):
        return "skipped"

    # Rule 2: Skip internal-only meetings (default: ON)
    if rules.get("skip_internal", True):
        external = [a for a in meeting.attendees if a.get("is_external", False)]
        if not external:
            return "skipped"

    # Rule 3: Skip by attendee domain
    skip_domains = set(rules.get("skip_domains", []))
    if skip_domains:
        domains = {a.get("email", "").split("@")[-1] for a in meeting.attendees}
        if domains and domains.issubset(skip_domains | {tenant_domain}):
            return "skipped"

    return "pending"
```

**Processing status transitions:**

```
pending -> processing -> complete    (happy path)
pending -> processing -> failed      (extraction error — retryable)
pending -> skipped                   (processing rules)
skipped -> pending                   (user overrides skip)
failed  -> pending                   (manual retry)
```

### Account Auto-Linking

#### AAL-01: Domain Matching

When a meeting is processed, extract attendee email domains and match against `accounts.domain` to auto-link the meeting to an existing account.

```python
async def auto_link_meeting_to_account(
    factory: Callable,
    tenant_id: UUID,
    meeting_id: UUID,
    attendees: list[dict],
) -> UUID | None:
    """Match attendee email domains to existing accounts.

    1. Extract unique external email domains from attendees
    2. Normalize: strip 'www.', handle subdomains (mail.acme.com -> acme.com)
    3. Query accounts.domain for exact match
    4. If multiple accounts match (multi-domain meeting), prefer the one
       with the most contacts (stronger existing relationship)
    5. Return account_id or None
    """
    external_domains = set()
    for a in attendees:
        if a.get("is_external") and a.get("email"):
            domain = a["email"].split("@")[-1].lower()
            # Normalize: strip common subdomains
            for prefix in ("mail.", "email.", "smtp.", "mx.", "www."):
                if domain.startswith(prefix):
                    domain = domain[len(prefix):]
            external_domains.add(domain)

    if not external_domains:
        return None

    async with factory() as sess:
        await sess.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        # Match against accounts.domain
        result = await sess.execute(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.domain.in_(external_domains),
                Account.deleted_at.is_(None) if hasattr(Account, 'deleted_at') else True,
            )
        )
        matches = result.scalars().all()

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0].id

    # Multiple matches: prefer account with most contacts
    best = max(matches, key=lambda a: len(a.contacts) if a.contacts else 0)
    return best.id
```

#### AAL-02: Contact Discovery

When a meeting is processed and linked to an account, create or update `AccountContact` rows for each external attendee.

```python
async def discover_contacts(
    factory: Callable,
    tenant_id: UUID,
    account_id: UUID,
    attendees: list[dict],
) -> list[UUID]:
    """Create or update AccountContact rows from meeting attendees.

    For each external attendee:
    1. Check if contact exists (email match on account)
    2. If exists: update last seen, append meeting to notes
    3. If new: create AccountContact with available info

    Returns list of contact IDs (created or updated).
    """
    contact_ids = []

    async with factory() as sess:
        await sess.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )

        for attendee in attendees:
            if not attendee.get("is_external"):
                continue

            email = attendee.get("email")
            name = attendee.get("name", "Unknown")

            # Check existing contact
            existing = None
            if email:
                existing = (await sess.execute(
                    select(AccountContact).where(
                        AccountContact.account_id == account_id,
                        AccountContact.email == email,
                    )
                )).scalar_one_or_none()

            if existing:
                # Update: touch updated_at, append to notes
                existing.updated_at = datetime.now(timezone.utc)
                contact_ids.append(existing.id)
            else:
                contact = AccountContact(
                    tenant_id=tenant_id,
                    account_id=account_id,
                    name=name,
                    email=email,
                    title=attendee.get("role"),
                    source="meeting-processor",
                )
                sess.add(contact)
                await sess.flush()
                contact_ids.append(contact.id)

        await sess.commit()

    return contact_ids
```

#### AAL-03: Prospect Auto-Creation

When attendee domains don't match any existing account, auto-create a prospect account. This ensures every external meeting produces a relationship in the CRM.

```python
async def auto_create_prospect(
    factory: Callable,
    tenant_id: UUID,
    user_id: UUID,
    domain: str,
    attendees: list[dict],
    meeting_title: str,
) -> UUID:
    """Create a prospect Account from meeting attendee info.

    1. Infer company name from domain (acme.com -> "Acme")
    2. Create Account with relationship_type=['prospect']
    3. Create AccountContact rows for attendees
    4. Return account_id

    The account is created un-graduated (graduated_at=NULL)
    so it appears in the Pipeline grid, not Relationships.
    """
    # Infer company name from domain
    company_name = domain.split(".")[0].title()  # acme.com -> "Acme"

    # Normalize name for dedup
    import re
    normalized = re.sub(r"[^a-z0-9]", "", company_name.lower())

    async with factory() as sess:
        await sess.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )

        # Check if account already exists with this normalized name
        existing = (await sess.execute(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.normalized_name == normalized,
            )
        )).scalar_one_or_none()

        if existing:
            return existing.id

        account = Account(
            tenant_id=tenant_id,
            name=company_name,
            normalized_name=normalized,
            domain=domain,
            status="prospect",
            source="meeting-auto-discovery",
            relationship_type=["prospect"],
            relationship_status="new",
            pipeline_stage="identified",
            last_interaction_at=datetime.now(timezone.utc),
        )
        sess.add(account)
        await sess.flush()

        # Create contacts for external attendees
        for attendee in attendees:
            if attendee.get("is_external") and attendee.get("email", "").endswith(f"@{domain}"):
                contact = AccountContact(
                    tenant_id=tenant_id,
                    account_id=account.id,
                    name=attendee.get("name", "Unknown"),
                    email=attendee.get("email"),
                    title=attendee.get("role"),
                    source="meeting-auto-discovery",
                )
                sess.add(contact)

        await sess.commit()
        return account.id
```

### Relationship Surface Enrichment

#### RSE-01: Timeline Integration

Meeting entries appear in the relationship timeline alongside existing entries (notes, emails, file uploads). The timeline is served by `GET /relationships/{id}` (RAPI-02 in `backend/src/flywheel/api/relationships.py`), which queries `ContextEntry` rows linked to the account.

**How meeting entries appear in timeline:**

Each processed meeting produces `ContextEntry` rows in `insights.md` (and other files) with `account_id` set. The existing `_serialize_timeline_item()` function in `relationships.py` (line 220) already handles these entries via `_derive_direction()`.

**Add meeting-specific direction detection** to `_derive_direction()`:

```python
def _derive_direction(source: str) -> str | None:
    """Derive interaction direction from ContextEntry.source."""
    # ... existing cases ...
    if source == "ctx-meeting-processor":
        return "bidirectional"
    return None
```

**Additionally, add meetings directly to the timeline query** in the relationship detail endpoint. Meetings linked to the account via `meeting.account_id` should appear as timeline items even before their extracted ContextEntries exist (e.g., during processing):

```python
# In RAPI-02 handler, alongside ContextEntry timeline query:
meeting_timeline = await db.execute(
    select(Meeting).where(
        Meeting.account_id == account_id,
        Meeting.deleted_at.is_(None),
    ).order_by(Meeting.meeting_date.desc()).limit(20)
)

# Serialize meetings as TimelineItems
for m in meeting_timeline.scalars():
    timeline_items.append({
        "id": m.id,
        "source": f"meeting:{m.meeting_type or 'unclassified'}",
        "content": f"Meeting: {m.title or 'Untitled'} — {m.meeting_type or ''} ({len(m.attendees or [])} attendees)",
        "date": m.meeting_date.date(),
        "created_at": m.created_at,
        "direction": "bidirectional",
        "contact_name": None,
        "meeting_id": str(m.id),  # extra field for meeting-specific UI
        "processing_status": m.processing_status,
        "summary_tldr": (m.summary or {}).get("tldr"),
    })
```

#### RSE-02: Intelligence Tab Enrichment

The relationship detail page's Intelligence tab shows `ContextEntry` rows grouped by file. After meeting processing, entries from `pain-points.md`, `competitive-intel.md`, `icp-profiles.md`, and `insights.md` with matching `account_id` automatically appear in this tab.

**No new code required** for basic display — the existing `intel` dict in `RelationshipDetail` is populated from `ContextEntry` rows. However, add meeting-sourced entries to the intel grouping:

```python
# In RAPI-02 handler, enhance intel aggregation:
intel_entries = await db.execute(
    select(ContextEntry).where(
        ContextEntry.account_id == account_id,
        ContextEntry.deleted_at.is_(None),
        ContextEntry.file_name.in_([
            "pain-points.md", "competitive-intel.md",
            "icp-profiles.md", "insights.md",
            "product-feedback.md",
        ]),
    ).order_by(ContextEntry.date.desc())
)

# Group by file_name for the intel dict
intel = {}
for entry in intel_entries.scalars():
    file_key = entry.file_name.replace(".md", "").replace("-", "_")
    intel.setdefault(file_key, []).append({
        "id": str(entry.id),
        "content": entry.content,
        "source": entry.source,
        "date": entry.date.isoformat(),
        "confidence": entry.confidence,
    })
```

**Meeting-specific intelligence display:**
- Pain points show severity badges (1-5) and painkiller/vitamin tags
- Competitor mentions show which meeting they came from
- Buying signals are highlighted with urgency indicators
- All entries show source attribution: "From discovery call with Acme on 2026-03-28"

#### RSE-03: Signal Integration

New meetings trigger signal updates on the relationship sidebar. Signals are counted as `ContextEntry` rows per account.

**Signal count update** (after meeting processing completes):

```python
async def update_account_signals(
    factory: Callable,
    tenant_id: UUID,
    account_id: UUID,
):
    """Refresh signal count and last_interaction_at for an account.

    Called after meeting processing or any new ContextEntry creation.
    """
    async with factory() as sess:
        await sess.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )

        # Count recent context entries for this account
        from sqlalchemy import func
        signal_count = (await sess.execute(
            select(func.count(ContextEntry.id)).where(
                ContextEntry.account_id == account_id,
                ContextEntry.deleted_at.is_(None),
            )
        )).scalar()

        # Update account
        account = (await sess.execute(
            select(Account).where(Account.id == account_id)
        )).scalar_one_or_none()

        if account:
            account.last_interaction_at = datetime.now(timezone.utc)
            await sess.commit()
```

**AI synthesis refresh trigger:** After meeting processing writes new ContextEntries, check if the account's `ai_summary_updated_at` is older than 24 hours. If so, queue a synthesis refresh (but do NOT auto-trigger — queue it as a suggestion via the existing `SynthesisEngine` in `backend/src/flywheel/services/synthesis_engine.py`).

### Frontend

#### FE-01: Meetings Page

New route: `/meetings` — a list view of all meetings for the current user.

**Component:** `frontend/src/features/meetings/components/MeetingsPage.tsx`

**Layout:**
- Header with "Meetings" title and "Sync from Granola" button
- Filter bar: by status (all, pending, complete, failed), by type (8 types), date range
- Meeting cards in a scrollable list, sorted by `meeting_date` DESC

**Meeting card contents:**
- Title, date, duration
- Meeting type badge (color-coded: discovery=blue, prospect=green, advisor=purple, etc.)
- Attendee avatars/names (external highlighted)
- Processing status indicator (pending=gray spinner, processing=blue spinner, complete=green check, failed=red x, skipped=gray dash)
- Account link (if linked)
- Summary TLDR (if processed)

**Sync button behavior:**
1. Click "Sync from Granola"
2. Call `POST /meetings/sync`
3. Display sync stats toast: "Synced 5 new meetings (2 skipped, 8 already seen)"
4. Auto-trigger processing for pending meetings
5. Show SSE-powered real-time status updates as each meeting processes

**API calls:**
- `GET /meetings/` — list meetings with pagination, filters
- `POST /meetings/sync` — trigger Granola sync
- `POST /meetings/{id}/process` — manually trigger processing for a single meeting
- `PATCH /meetings/{id}/skip` — manually skip a meeting

#### FE-02: Meeting Detail View

Route: `/meetings/{id}` — full detail view for a single meeting.

**Component:** `frontend/src/features/meetings/components/MeetingDetailPage.tsx`

**Split visibility enforcement at API level:**
- **All team members see:** title, date, duration, attendees, meeting type, account link, summary JSONB (tldr, key decisions, action items, attendee roles, pain points), processing status
- **Meeting owner only sees additionally:** full transcript (loaded from Supabase Storage via signed URL), Granola AI summary, raw extraction data

**Layout:**
- Header: title, type badge, date, duration, attendee list
- Account link (clickable to relationship page)
- Summary section: rendered from `summary` JSONB as a glanceable card layout
  - TLDR (1-2 sentences)
  - Key Decisions (bullet list)
  - Action Items (checkbox list with owners and dates)
  - Pain Points (with severity badges)
  - Attendee Roles (who was who)
- Transcript section (owner only): collapsible, searchable, with speaker highlighting
- Processing status bar: shows which stage completed, with timestamps

**API call:**
- `GET /meetings/{id}` — returns full detail (privacy-filtered by API)

#### FE-03: Granola Settings Integration

Add Granola connection UI to the existing Settings page (`frontend/src/pages/SettingsPage.tsx`).

**Component:** `frontend/src/features/meetings/components/GranolaSettings.tsx`

**Layout:**
- Section header: "Meeting Intelligence" with Granola logo
- Connection status: "Connected" (green) or "Not connected" (gray)
- API key input field (password type, masked when connected)
- "Connect" / "Disconnect" buttons
- Last sync timestamp
- Processing rules toggles:
  - "Skip internal-only meetings" (default: ON)
  - "Skip domains" with tag input for adding domains
- Manual sync trigger button with last sync time

**API calls:**
- `POST /integrations/granola/connect` — connect with API key
- `DELETE /integrations/{id}` — disconnect (existing endpoint)
- `PATCH /integrations/{id}/settings` — update processing rules

#### FE-04: SSE Processing Feedback

Reuse the existing SSE streaming pattern from `frontend/src/features/profile/hooks/useProfileRefresh.ts` and `frontend/src/lib/sse.ts`.

**New hook:** `frontend/src/features/meetings/hooks/useMeetingProcessing.ts`

```typescript
export function useMeetingProcessing() {
  const [phase, setPhase] = useState<'idle' | 'processing' | 'complete' | 'error'>('idle')
  const [currentStage, setCurrentStage] = useState<string | null>(null)
  const [discoveries, setDiscoveries] = useState<Discovery[]>([])
  const [error, setError] = useState<ProcessingError | null>(null)
  const [sseUrl, setSseUrl] = useState<string | null>(null)

  const queryClient = useQueryClient()

  const handleEvent = useCallback(
    (event: { type: string; data: Record<string, unknown> }) => {
      switch (event.type) {
        case 'stage': {
          // Stages: fetching, storing, classifying, extracting, linking, writing, done
          setCurrentStage(event.data.message as string)
          break
        }
        case 'discovery': {
          // Intelligence items extracted (pain points, competitors, etc.)
          setDiscoveries(prev => [...prev, event.data as Discovery])
          break
        }
        case 'done': {
          setPhase('complete')
          setSseUrl(null)
          // Invalidate meeting list, relationship queries
          queryClient.invalidateQueries({ queryKey: ['meetings'] })
          queryClient.invalidateQueries({ queryKey: ['relationships'] })
          break
        }
        case 'error': {
          setPhase('error')
          setError({ message: event.data.message as string, retryable: true })
          setSseUrl(null)
          break
        }
      }
    },
    [queryClient],
  )

  useSSE(sseUrl, handleEvent)

  const startProcessing = useCallback(async (meetingId: string) => {
    setPhase('processing')
    setDiscoveries([])
    setCurrentStage(null)
    setError(null)

    const res = await api.post<{ run_id: string }>(`/meetings/${meetingId}/process`, {})
    setSseUrl(`/api/v1/skills/runs/${res.run_id}/stream`)
  }, [])

  return { phase, currentStage, discoveries, error, startProcessing }
}
```

**Real-time UI during processing:** A slide-up panel (similar to the company profile refresh) showing:
- Current stage with progress indicator
- Intelligence items appearing as they're extracted (animated entry)
- Context file write confirmations
- Account linking result
- "View meeting" button on completion

### Meeting Prep (Closing the Loop)

#### PREP-01: Web Meeting Prep Engine

Adapt the existing `skills/meeting-prep/SKILL.md` for server-side execution as a skill engine. This reads the enriched context store and produces an HTML briefing.

**Engine:** `backend/src/flywheel/engines/meeting_prep.py`

**Input:** Account ID + optional meeting context (title, attendees, date)

**Output:** HTML briefing containing:
- **Relationship Summary:** AI summary from account, relationship type, status
- **Meeting History:** Previous meetings with this account (from `meetings` table), with dates and types
- **Known Pain Points:** From `pain-points.md` entries linked to this account
- **Open Action Items:** From `action-items.md` entries, with owner and status
- **Competitive Context:** From `competitive-intel.md` entries, what competitors they've mentioned
- **Key Contacts:** From `account_contacts` table, with roles and last interaction
- **Suggested Questions:** AI-generated based on gaps in intelligence (what we don't know yet)
- **Buying Signals:** From `icp-profiles.md`, timeline of engagement signals

**Context gathering:**

```python
async def gather_prep_context(
    factory: Callable,
    tenant_id: UUID,
    account_id: UUID,
) -> dict:
    """Gather all context for meeting prep from context store + meetings table.

    Reads:
    - Account row (name, domain, relationship_type, ai_summary)
    - AccountContact rows (people we know)
    - ContextEntry rows linked to account (pain-points, competitive-intel, etc.)
    - Meeting rows linked to account (meeting history)
    """
    async with factory() as sess:
        await sess.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )

        account = (await sess.execute(
            select(Account)
            .options(selectinload(Account.contacts))
            .where(Account.id == account_id)
        )).scalar_one()

        # Context entries grouped by file
        entries = (await sess.execute(
            select(ContextEntry).where(
                ContextEntry.account_id == account_id,
                ContextEntry.deleted_at.is_(None),
            ).order_by(ContextEntry.date.desc())
        )).scalars().all()

        # Meeting history
        meetings = (await sess.execute(
            select(Meeting).where(
                Meeting.account_id == account_id,
                Meeting.deleted_at.is_(None),
            ).order_by(Meeting.meeting_date.desc()).limit(20)
        )).scalars().all()

    return {
        "account": account,
        "contacts": account.contacts,
        "entries_by_file": _group_entries(entries),
        "meetings": meetings,
    }
```

#### PREP-02: Prep Trigger

Meeting prep is user-initiated only (v1). Two trigger points:

1. **From Meetings page:** "Prep for meeting" button on upcoming meeting cards
2. **From Relationship page:** "Prepare for meeting" action in the relationship detail header

**API endpoint:**

```python
@router.post("/meetings/prep")
async def trigger_meeting_prep(
    body: dict,  # {"account_id": "uuid", "meeting_context": {...}}
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Trigger meeting prep generation.

    Creates a SkillRun, gathers context, generates HTML briefing.
    Returns run_id for SSE streaming of generation progress.
    """
```

The prep output is stored as a `SkillRun` with `skill_name="meeting-prep"` and `rendered_html` containing the briefing. This follows the existing pattern where skill outputs are stored on the SkillRun row.

## Success Criteria

### Core Pipeline
- [ ] Granola API key can be added in Settings and validated against Granola API
- [ ] "Sync from Granola" fetches meetings and deduplicates correctly
- [ ] Meetings table correctly stores metadata with split RLS (shared metadata, private transcript)
- [ ] Each meeting processes through all 7 stages with SSE real-time feedback
- [ ] 9 insight types are extracted for discovery/expert/prospect meetings
- [ ] Extracted intelligence appears in correct context files with source attribution

### Account Linking
- [ ] Attendee email domains auto-match to existing accounts
- [ ] Unknown domains auto-create prospect accounts with inferred company name
- [ ] Meeting contacts are created/updated on the linked account
- [ ] Meetings appear on the correct relationship timeline

### Relationship Enrichment
- [ ] Pain points, competitor mentions, and buying signals from meetings appear in Intelligence tab
- [ ] New contacts from meetings appear in People tab
- [ ] Action items from meetings appear in Commitments tab
- [ ] Signal badges increment after meeting processing
- [ ] Last Action column in Pipeline grid reflects meeting dates

### Frontend
- [ ] Meetings page shows list with sync, filter, and status indicators
- [ ] Meeting detail page enforces privacy (transcript only for owner)
- [ ] Processing feedback shows real-time extraction progress via SSE
- [ ] Settings page has working Granola connection flow

### Meeting Prep (Loop Closure)
- [ ] Meeting prep reads from enriched context store
- [ ] Briefing includes relationship history, pain points, action items, competitive context
- [ ] Prep can be triggered from both Meetings page and Relationship page

### Cost & Performance
- [ ] Classification uses Haiku (~$0.01/meeting)
- [ ] Extraction uses Sonnet (~$0.15-0.25/meeting)
- [ ] Average processing time < 30 seconds per meeting
- [ ] Dedup prevents duplicate processing on re-sync

## Anti-Requirements

- Do NOT modify the existing CLI meeting-processor skill (`skills/meeting-processor/SKILL.md`) — the web engine is a separate implementation that shares the same extraction logic but runs server-side
- Do NOT build Fathom/Fireflies adapters in v1 (architecture supports them via `IntelligenceSource` interface, implementation deferred)
- Do NOT build Slack/Drive adapters in v1
- Do NOT auto-trigger meeting prep (user-initiated only for v1)
- Do NOT store transcripts inline in Postgres (use Supabase Storage, referenced by `transcript_url`)
- Do NOT add reprocessing logic in v1 (deferred — revisit after extraction pipeline stabilizes)
- Do NOT build a meeting sync daemon or cron job (sync is user-triggered via "Sync" button for v1)
- Do NOT modify the `ContextEntry` model — use existing fields (`source`, `detail`, `account_id`, `metadata`) for meeting attribution

## Phasing

- **Phase 59:** Team Privacy Foundation (prerequisite) — user-level RLS on 7 tables + API guards for transcript/email privacy
- **Phase 60:** Meetings data model + Granola adapter + sync endpoint + Settings UI for Granola connection
- **Phase 61:** Processing pipeline (`_execute_meeting_processor`) + classification + extraction + context store writes + account auto-linking + contact discovery
- **Phase 62:** Frontend meetings page + meeting detail view + SSE processing feedback + relationship surface enrichment (timeline, intelligence tab, signals)
- **Phase 63:** Meeting prep engine + prep triggers + briefing generation + loop closure

## Open Questions

- [ ] **Granola API key UX:** Settings page integration (current plan) vs onboarding flow? If onboarding, which step?
- [ ] **Auto-triggered meeting prep:** Should meeting prep auto-trigger before calendar events, or always user-initiated? v1 is user-initiated; revisit for v2.
- [ ] **Multi-account attendees:** How to handle meeting attendees who map to multiple accounts (person attends on behalf of different companies)?
- [ ] **Drive adapter scope:** Full document intelligence or just meeting-related docs (agendas, follow-up notes)?
- [ ] **Rate limiting / budget controls:** Hard cap per month or soft warning? Need a cost tracking mechanism.
- [ ] **Reprocessing strategy:** When extraction logic improves, do we reprocess all historical meetings or just new ones?
- [ ] **Team admin elevated access:** Should team admins see all transcripts for compliance? Current design says no.
- [ ] **Account ownership on auto-create:** When User A's meeting creates a prospect account, does User A become the "owner" or is it unassigned?
- [ ] **Granola API stability:** What are Granola's rate limits? Do we need exponential backoff? What happens when the API is down during sync?
- [ ] **Transcript size limits:** What's the max transcript size for Supabase Storage? Do we need chunking for multi-hour meetings?
