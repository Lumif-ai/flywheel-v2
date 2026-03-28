# Phase 61: Meeting Intelligence Pipeline - Research

**Researched:** 2026-03-28
**Domain:** Python async pipeline, Anthropic LLM (Haiku + Sonnet), Supabase Storage, PostgreSQL/SQLAlchemy, server-sent events
**Confidence:** HIGH

## Summary

Phase 61 adds the intelligence extraction brain on top of Phase 60's meeting ingestion plumbing. The work is almost entirely Python backend: a new `_execute_meeting_processor()` engine function in `skill_executor.py`, a `POST /meetings/{id}/process` endpoint, plus domain-matching and contact-discovery helpers. No new dependencies are required — the full stack (Anthropic SDK, httpx, SQLAlchemy, Supabase Storage via httpx) is already installed.

The most important structural finding is that the spec's `write_meeting_intelligence()` function calls `append_entry(factory=..., account_id=...)` — neither of those parameters match the real `storage.py` signature. The real `append_entry(session, file, entry, source)` takes an `AsyncSession`, not a factory, and has no `account_id` parameter. The meeting processor must create `ContextEntry` ORM objects directly (with `account_id` set) inside a session block, mirroring the pattern used in `_execute_company_intel()`. This is the single biggest deviation between spec and reality.

The job queue mechanism is fully understood: `POST /meetings/{id}/process` creates a `SkillRun` with `status="pending"` and commits. The `job_queue_loop()` worker polls every 5 seconds via `FOR UPDATE SKIP LOCKED`, claims pending runs, and dispatches to `execute_run()`. No explicit enqueue call needed — just insert the SkillRun row. The confirmed model strings are: Haiku = `"claude-haiku-4-5-20251001"` (from `email_scorer.py` and `chat_orchestrator.py`), Sonnet = `"claude-sonnet-4-20250514"` (from `company_intel.py` and `execution_gateway.py`).

**Primary recommendation:** Follow the spec's 7-stage pipeline structure exactly, but write context entries directly as `ContextEntry` ORM objects with `account_id` set (not via `append_entry`). Use `_execute_company_intel()` as the structural template for session management, error handling, and event emission.

## Standard Stack

### Core (all already in backend/pyproject.toml — no new installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.40 | LLM calls (Haiku for classify, Sonnet for extract) | Already used by all engine functions |
| SQLAlchemy | >=2.0 | ORM, async sessions, direct ContextEntry creation | Existing stack |
| httpx | >=0.27 | Supabase Storage upload (transcript text to `uploads` bucket) | Already in deps, used by document_storage.py |
| flywheel.auth.encryption | existing | decrypt_api_key() for Granola credentials | Used in Phase 60 sync endpoint |
| flywheel.services.granola_adapter | Phase 60 | get_meeting_content() for transcript fetch | Built in Phase 60 |

### LLM Model Strings (verified in codebase)

| Model | String | Used In |
|-------|--------|---------|
| Haiku (classification) | `"claude-haiku-4-5-20251001"` | `email_scorer.py`, `chat_orchestrator.py`, `email_voice_updater.py` |
| Sonnet (extraction) | `"claude-sonnet-4-20250514"` | `company_intel.py`, `execution_gateway.py` |

### No New Dependencies

All required libraries exist. The Anthropic client used in `_execute_company_intel()` and `_execute_meeting_prep()` is the template. Supabase Storage upload follows `document_storage.py` pattern exactly.

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── src/flywheel/
│   ├── api/
│   │   └── meetings.py              # Add POST /meetings/{id}/process endpoint
│   ├── services/
│   │   └── skill_executor.py        # Add _execute_meeting_processor(), dispatch in execute_run()
│   └── engines/
│       └── meeting_processor_web.py # New: classify + extract helpers (web-tier adaptation)
```

The spec calls for adding everything to `skill_executor.py` directly (following `_execute_company_intel()`). Given the file is already very large (2400+ lines), the classify and extract helpers should live in a new `engines/meeting_processor_web.py` module, imported into `skill_executor.py` at call time (matching the `from flywheel.engines.company_intel import ...` pattern). The existing CLI `meeting_processor.py` engine uses the old sync `storage_backend` and should NOT be modified.

### Pattern 1: Engine Dispatch in execute_run()

**What:** Route `meeting-processor` skill runs to `_execute_meeting_processor()` in the same `if/elif` chain that handles `company-intel`, `meeting-prep`, and `email-scorer`.

**Where:** `skill_executor.py` lines 570-608.

```python
# Source: skill_executor.py lines 572-608 (existing company-intel pattern)
is_meeting_processor = run.skill_name == "meeting-processor"

# Add to the if/elif chain:
elif is_meeting_processor:
    output, token_usage, tool_calls = await _execute_meeting_processor(
        factory=factory,
        run_id=run.id,
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        meeting_id=UUID(run.input_text),  # input_text carries meeting UUID as string
        api_key=api_key,
    )
```

The `run.input_text` field carries the meeting UUID string — this is how meeting-specific context reaches the engine. The `POST /meetings/{id}/process` endpoint creates a `SkillRun` with `input_text=str(meeting_id)` and `skill_name="meeting-processor"`.

### Pattern 2: 7-Stage Pipeline in _execute_meeting_processor()

**What:** Each stage emits a `stage` SSE event via `_append_event_atomic()`, does its work, then passes output to the next stage. Error handling marks the meeting as `failed` and re-raises.

```python
# Source: SPEC-intelligence-flywheel.md MPP-01 + _execute_company_intel() pattern
async def _execute_meeting_processor(
    factory: async_sessionmaker,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    meeting_id: UUID,
    api_key: str | None = None,
) -> tuple[str, dict, list]:
    """Process a single meeting through the 7-stage intelligence pipeline."""
```

Stage flow:
1. **fetching** — `get_meeting_content(api_key, meeting.external_id)` via granola_adapter
2. **storing** — POST transcript text to Supabase Storage at `uploads/transcripts/{tenant_id}/{meeting_id}.txt`, store URL on `meeting.transcript_url`
3. **classifying** — 3-layer classification (contact match → internal check → Haiku LLM)
4. **extracting** — Sonnet extraction of 9 insight types into structured dict
5. **linking** — domain matching → contact discovery → prospect auto-creation
6. **writing** — create `ContextEntry` rows for up to 7 context files with `account_id` set
7. **done** — update `meeting.processing_status='complete'`, `meeting.summary=JSONB`, emit done event

### Pattern 3: Context Entry Creation (CRITICAL DIVERGENCE FROM SPEC)

**What:** The spec's `write_meeting_intelligence()` calls a non-existent `append_entry(factory=..., account_id=...)`. The real `storage.py:append_entry()` takes `(session, file, entry, source)` — no factory, no account_id.

**Correct approach:** Create `ContextEntry` ORM objects directly with `account_id` set, inside a `factory()` session block with tenant + user RLS context set. This is how all context writes work in the codebase.

```python
# Source: skill_executor.py lines 1258-1276 (_execute_company_intel pattern)
async with factory() as session:
    await session.execute(
        sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    await session.execute(
        sa_text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id)},
    )
    new_entry = ContextEntry(
        tenant_id=tenant_id,
        user_id=user_id,
        file_name=file_name,      # no .md extension (e.g., "pain-points" not "pain-points.md")
        source="ctx-meeting-processor",
        detail=meeting_slug,      # e.g., "meeting-2026-03-28-acme-discovery"
        confidence="medium",
        content=content,
        account_id=account_id,    # set directly on ORM object
        date=meeting_date_obj,    # datetime.date object
    )
    session.add(new_entry)
    await session.commit()
```

Note: `file_name` in ContextEntry stores the name WITHOUT `.md` (see existing entries: "company-details", "pain-points"). The `append_entry` helper strips `.md` when calling `file=filename.replace(".md", "")`.

### Pattern 4: Supabase Storage Upload (Transcript)

**What:** Upload transcript text to the `uploads` bucket (NOT a separate `transcripts` bucket — only `uploads` bucket is confirmed to exist per `api/health.py`). Path: `uploads/transcripts/{tenant_id}/{meeting_id}.txt`.

```python
# Source: document_storage.py + relationships.py upload pattern
async def upload_transcript_to_storage(tenant_id: str, meeting_id: str, text: str) -> str:
    """Upload transcript text to Supabase Storage. Returns storage path."""
    supabase_url = os.environ["SUPABASE_URL"]
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    path = f"transcripts/{tenant_id}/{meeting_id}.txt"
    url = f"{supabase_url}/storage/v1/object/uploads/{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            content=text.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "text/plain",
            },
        )
        resp.raise_for_status()
    return path
```

### Pattern 5: Meeting Classification (3-Layer)

Layer 1: Query `account_contacts` for attendee emails — if found, derive type from account's `relationship_type` array.
Layer 2: If all attendees share tenant domain → internal/team-meeting (≤3 = internal, >3 = team-meeting). Requires querying `tenants.domain` from DB. If `tenant.domain` is NULL, skip this layer.
Layer 3: Haiku LLM call with title + attendees + first 500 chars of transcript.

```python
# Source: SPEC-intelligence-flywheel.md MPP-02 + Haiku model from email_scorer.py
import asyncio
import anthropic

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

def _classify_with_llm(title, attendees_str, transcript_preview, ai_summary, api_key):
    """Sync Haiku call — run in executor to avoid blocking."""
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    prompt = f"""Classify this meeting into one of: discovery, expert, prospect, advisor, investor-pitch, internal, customer-feedback, team-meeting.

Title: {title}
Attendees: {attendees_str}
Summary: {ai_summary or 'None'}
Transcript preview: {transcript_preview[:500]}

Return ONLY the classification code (e.g. "discovery"). No explanation."""
    resp = client.messages.create(
        model=_HAIKU_MODEL,
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip().lower()

meeting_type = await asyncio.get_event_loop().run_in_executor(
    None, lambda: _classify_with_llm(title, attendees_str, transcript, ai_summary, api_key)
)
```

### Pattern 6: Sonnet Extraction Call

```python
# Source: SPEC-intelligence-flywheel.md MPP-03 + Sonnet model from company_intel.py
_SONNET_MODEL = "claude-sonnet-4-20250514"

def _extract_intelligence(transcript, ai_summary, meeting_type, existing_context, api_key):
    """Sync Sonnet call — run in executor."""
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    resp = client.messages.create(
        model=_SONNET_MODEL,
        max_tokens=4096,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": EXTRACTION_USER_PROMPT}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    return json.loads(raw)

extracted = await asyncio.get_event_loop().run_in_executor(
    None, lambda: _extract_intelligence(transcript, ai_summary, meeting_type, ctx, api_key)
)
```

### Pattern 7: POST /meetings/{id}/process Endpoint

Create a `SkillRun` with `status="pending"` and commit. The `job_queue_loop()` worker polls every 5s and automatically picks it up — no explicit dispatch call needed.

```python
# Source: job_queue.py + existing skill run creation pattern
@router.post("/{meeting_id}/process")
async def process_meeting(
    meeting_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.tenant_id == user.tenant_id)
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.processing_status not in ("pending", "failed"):
        raise HTTPException(status_code=409, detail=f"Meeting is {meeting.processing_status}")

    # Update status to processing immediately (prevents duplicate triggers)
    meeting.processing_status = "processing"

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name="meeting-processor",
        input_text=str(meeting_id),
        status="pending",       # job_queue_loop picks this up within 5s
    )
    db.add(run)
    await db.commit()

    return {"run_id": str(run.id)}
```

### Pattern 8: Account Auto-Linking (Domain Match → Prospect Creation)

Phase 61 populates `meeting.account_id` (which Phase 60 always set to NULL). Three-step flow:

1. **AAL-01:** Extract external email domains from `content.attendees` (from the Phase 61 detail fetch — NOT `meeting.attendees` from DB row, which may be `[]` for meetings where Phase 60 list call had no `calendar_event`). Match against `accounts.domain`.
2. **AAL-02:** For matched account: upsert `AccountContact` rows per external attendee (email dedup within account).
3. **AAL-03:** For unmatched domains: auto-create `Account` with all required fields.

**Key constraint from Account model:** `Account` requires all of: `name`, `normalized_name`, `source`, `relationship_status`, `pipeline_stage`. Use these defaults for auto-created accounts:
- `source="meeting-auto-discovery"`
- `relationship_status="new"`
- `pipeline_stage="identified"`
- `relationship_type=["prospect"]`
- `graduated_at=NULL` (appears in Pipeline grid, not Relationships)

**Dedup:** `Account` has `UniqueConstraint("tenant_id", "normalized_name")`. Check before creating.

### Pattern 9: summary JSONB Structure

After extraction, write structured summary to `meeting.summary` (in Stage 7):

```python
meeting.summary = {
    "tldr": extracted.get("tldr"),
    "key_decisions": extracted.get("key_decisions", []),
    "action_items": extracted.get("action_items", []),
    "attendee_roles": {a["email"]: a.get("role") for a in content.attendees if a.get("email")},
    "meeting_type": meeting_type,
    "pain_points": extracted.get("pain_points", []),
}
meeting.processing_status = "complete"
meeting.processed_at = datetime.now(timezone.utc)
meeting.meeting_type = meeting_type
meeting.account_id = account_id   # may be None if no match
```

### Anti-Patterns to Avoid

- **Calling `append_entry(factory=..., account_id=...):`** The real signature is `append_entry(session, file, entry, source)`. Use direct ORM creation.
- **Using the existing CLI `meeting_processor.py`:** It uses the sync `storage_backend` (filesystem-based), not the async Postgres `storage.py`. Never import from it for the web engine.
- **Uploading to a `transcripts` Supabase bucket:** Only the `uploads` bucket is confirmed to exist. Use path `uploads/transcripts/{tenant_id}/{meeting_id}.txt`.
- **Setting `app.user_id` without `app.tenant_id`:** RLS requires BOTH to be set before any tenant-scoped write. Always set both in the same session block.
- **Blocking the event loop with synchronous Anthropic client:** Use `asyncio.get_event_loop().run_in_executor(None, lambda: ...)` to wrap sync LLM calls. This is the established pattern in `_execute_company_intel()` and `_execute_meeting_prep()`.
- **Missing `meeting.skill_run_id` update:** The `Meeting` ORM has `skill_run_id` FK. Update it when processing starts so the run can be found from the meeting.
- **Using `meeting.attendees` from DB row for domain matching:** Phase 60 may have stored `[]` if Granola's list response lacked `calendar_event`. Always use `content.attendees` from the Phase 61 `get_meeting_content()` call.
- **Calling `enqueue_run()`:** No such function exists. Just insert a `SkillRun` with `status="pending"` — the polling worker picks it up automatically.
- **file_name with `.md` extension:** ContextEntry stores file names without `.md`. Use `"pain-points"` not `"pain-points.md"`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Transcript upload | Custom S3/Storage wrapper | `document_storage.py` httpx pattern | Established pattern, handles auth headers |
| Event streaming | Custom WebSocket or polling | `_append_event_atomic()` + existing SSE stream endpoint | Already built, reused by all skills |
| API key decryption | Custom AES | `flywheel.auth.encryption.decrypt_api_key()` | AES-256-GCM, used in Phase 60 sync |
| Job dispatching | `enqueue_run()` / background task | Insert `SkillRun(status="pending")` + commit | `job_queue_loop()` polls every 5s automatically |
| Context dedup | Custom hash check | ContextEntry `(file_name, source, detail)` dedup | Built into `append_entry()`, replicate for direct ORM creation |

**Key insight:** The entire SSE infrastructure, SkillRun state machine, and job queue are already working. Phase 61 only adds a new engine function behind the same dispatch mechanism.

## Common Pitfalls

### Pitfall 1: append_entry Signature Mismatch
**What goes wrong:** Calling `append_entry(factory=factory, account_id=...)` — neither param exists on the real function.
**Why it happens:** Spec was written with an idealized signature, not the real one.
**How to avoid:** Create `ContextEntry` ORM objects directly with `account_id` set. Set RLS context first (both `app.tenant_id` and `app.user_id`).
**Warning signs:** `TypeError: append_entry() got unexpected keyword argument 'factory'`

### Pitfall 2: file_name Format in ContextEntry
**What goes wrong:** Storing `file_name="pain-points.md"` (with `.md`). Existing entries omit the extension.
**Why it happens:** Context files have `.md` suffix in filesystem/spec, but DB stores without extension.
**How to avoid:** Strip `.md` when setting `file_name`. E.g., `file_name="pain-points"`.
**Warning signs:** Entries not appearing in intelligence tab (file_name query mismatch).

### Pitfall 3: Transcript in Wrong Storage Bucket
**What goes wrong:** Trying to upload to a `transcripts` bucket that doesn't exist.
**Why it happens:** Spec mentions path prefix but doesn't specify which bucket name.
**How to avoid:** Use the existing `uploads` bucket. URL: `.../storage/v1/object/uploads/transcripts/{tenant_id}/{meeting_id}.txt`.
**Warning signs:** HTTP 404/400 from Supabase Storage on upload.

### Pitfall 4: Sync Anthropic Client Blocking Event Loop
**What goes wrong:** `anthropic.Anthropic().messages.create(...)` is synchronous — calling it directly in an async function blocks the event loop.
**Why it happens:** Easy to miss; the existing engines use `run_in_executor`.
**How to avoid:** Wrap sync calls: `await asyncio.get_event_loop().run_in_executor(None, lambda: client.messages.create(...))`.
**Warning signs:** Other async operations stall while LLM is running; 5s poll interval missed.

### Pitfall 5: Missing Required Account Fields on Auto-Create
**What goes wrong:** `Account` created without `relationship_status` or `pipeline_stage` — both NOT NULL.
**Why it happens:** Spec code in one revision omits `relationship_status`.
**How to avoid:** Always include: `relationship_status="new"`, `pipeline_stage="identified"`, `source="meeting-auto-discovery"`.
**Warning signs:** `sqlalchemy.exc.IntegrityError: NOT NULL violation on column relationship_status`

### Pitfall 6: Duplicate Processing Race Condition
**What goes wrong:** Two concurrent `POST /meetings/{id}/process` calls create two SkillRun rows.
**Why it happens:** No lock on the status transition check.
**How to avoid:** The endpoint checks `processing_status in ("pending", "failed")` and updates it to `"processing"` in the same commit before creating the SkillRun. The status check acts as a lightweight guard.
**Warning signs:** Duplicate ContextEntry rows with same `detail` tag.

### Pitfall 7: Empty Attendees from Phase 60 DB Row
**What goes wrong:** Domain matching finds no external domains because `meeting.attendees` was stored as `[]` — Phase 60's `list_meetings()` could not extract attendees from list response if `calendar_event` was absent.
**Why it happens:** Granola list response may lack `calendar_event.invitees`.
**How to avoid:** Use `content.attendees` from Phase 61's `get_meeting_content()` call (Stage 1) for all downstream domain matching and contact work. Do not rely on `meeting.attendees` from the DB row.
**Warning signs:** `meeting.account_id` always NULL even for known companies.

### Pitfall 8: Tenant Domain NULL in Layer 2 Classification
**What goes wrong:** `Tenant.domain` is nullable — querying it to detect internal meetings may return None.
**Why it happens:** Not all tenants have `domain` configured.
**How to avoid:** If `tenant.domain` is None, skip Layer 2 entirely and proceed to Layer 3 (LLM). Log a debug warning. Do NOT crash.
**Warning signs:** `AttributeError` or incorrect internal classification.

## Code Examples

### Engine Dispatch Addition (skill_executor.py)

```python
# Source: skill_executor.py lines 572-608 existing pattern
# Add is_meeting_processor to the flag group:
is_company_intel = run.skill_name == "company-intel"
is_meeting_prep = run.skill_name == "meeting-prep"
is_email_scorer = run.skill_name == "email-scorer"
is_meeting_processor = run.skill_name == "meeting-processor"   # NEW

# In the if/elif dispatch:
elif is_meeting_processor:
    output, token_usage, tool_calls = await _execute_meeting_processor(
        factory=factory,
        run_id=run.id,
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        meeting_id=UUID(run.input_text),
        api_key=api_key,
    )
```

### Also add to subsidy key allowlist

```python
# Source: skill_executor.py line 506 (existing allowlist)
if run.skill_name in ("company-intel", "meeting-prep", "email-scorer", "meeting-processor") \
        and settings.flywheel_subsidy_api_key:
    api_key = settings.flywheel_subsidy_api_key
```

### Direct ContextEntry Creation with account_id

```python
# Source: db/models.py ContextEntry + skill_executor.py context write pattern
from flywheel.db.models import ContextEntry
import datetime

async with factory() as session:
    await session.execute(
        sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    await session.execute(
        sa_text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id)},
    )
    entry = ContextEntry(
        tenant_id=tenant_id,
        user_id=user_id,
        file_name=file_name,              # no .md extension
        source="ctx-meeting-processor",
        detail=meeting_slug,              # e.g. "meeting-2026-03-28-acme-discovery"
        confidence="medium",
        content=content,
        account_id=account_id,            # set directly — append_entry cannot do this
        date=meeting_date_as_date,        # datetime.date object
    )
    session.add(entry)
    await session.commit()
```

### Account Auto-Link (Domain Match)

```python
# Source: SPEC-intelligence-flywheel.md AAL-01 + db/models.py Account
from flywheel.db.models import Account, AccountContact

async def auto_link_meeting_to_account(
    factory, tenant_id: UUID, meeting_id: UUID, attendees: list[dict]
) -> UUID | None:
    external_domains = set()
    for a in attendees:
        if a.get("is_external") and a.get("email"):
            domain = a["email"].split("@")[-1].lower()
            for prefix in ("mail.", "email.", "smtp.", "mx.", "www."):
                if domain.startswith(prefix):
                    domain = domain[len(prefix):]
            external_domains.add(domain)

    if not external_domains:
        return None

    async with factory() as sess:
        await sess.execute(sa_text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})
        result = await sess.execute(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.domain.in_(external_domains),
            )
        )
        matches = result.scalars().all()

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0].id
    # Multiple matches: prefer account with most contacts
    return max(matches, key=lambda a: len(a.contacts or [])).id
```

### Prospect Auto-Creation

```python
# Source: SPEC-intelligence-flywheel.md AAL-03 + db/models.py Account required fields
import re
from datetime import datetime, timezone

async def auto_create_prospect(
    factory, tenant_id: UUID, user_id: UUID, domain: str, attendees: list[dict], title: str
) -> UUID:
    company_name = domain.split(".")[0].title()
    normalized = re.sub(r"[^a-z0-9]", "", company_name.lower())

    async with factory() as sess:
        await sess.execute(sa_text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})

        existing = (await sess.execute(
            select(Account).where(Account.tenant_id == tenant_id, Account.normalized_name == normalized)
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
            relationship_status="new",       # NOT NULL
            pipeline_stage="identified",     # NOT NULL
            last_interaction_at=datetime.now(timezone.utc),
        )
        sess.add(account)
        await sess.flush()

        for attendee in attendees:
            if attendee.get("is_external") and (attendee.get("email") or "").endswith(f"@{domain}"):
                sess.add(AccountContact(
                    tenant_id=tenant_id,
                    account_id=account.id,
                    name=attendee.get("name", "Unknown"),
                    email=attendee.get("email"),
                    source="meeting-auto-discovery",
                ))
        await sess.commit()
        return account.id
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CLI `meeting_processor.py` + sync `storage_backend` | Web `_execute_meeting_processor()` + async SQLAlchemy | Phase 61 | Same extraction logic, different I/O layer |
| No auto-linking | Domain-based account auto-link + prospect creation | Phase 61 | Every meeting produces CRM intelligence |
| Manual transcript filing | Supabase Storage at `uploads/transcripts/{tenant_id}/{id}.txt` | Phase 61 | Private transcripts, shared extracted intelligence |

**Deprecated/outdated (in context of this phase):**
- `engines/meeting_processor.py` (the CLI version): still needed for CLI skill runs via `execution_gateway.py`, but must NOT be used for the web engine. The two implementations coexist permanently.

## Open Questions

1. **Granola `calendar_event` attendance detail**
   - What we know: Phase 60's `list_meetings()` may store `meeting.attendees = []` if the Granola list response lacked `calendar_event.invitees`. Phase 61 calls `get_meeting_content()` which fetches the full note with `calendar_event`.
   - What's unclear: Whether `content.attendees` from the detail endpoint is always populated even for older meetings.
   - Recommendation: Use `content.attendees` from Stage 1's `get_meeting_content()` call for all domain matching. Fall back gracefully (no auto-link) if still empty.

2. **`meeting_slug` format for ContextEntry.detail**
   - What we know: Spec suggests `meeting-{date}-{account-name}-{type}` as the `detail` field.
   - What's unclear: What to use when account is not yet known (account IS known by Stage 6 since linking happens in Stage 5).
   - Recommendation: Use `meeting-{date}-{title_slug}` format. title_slug = first 20 chars of title, lowercased, spaces to hyphens. This avoids special chars in the detail field.

3. **`Tenant.domain` field population**
   - What we know: `Tenant.domain` is nullable. Needed for Layer 2 internal meeting detection.
   - What's unclear: Whether existing tenants have `domain` set.
   - Recommendation: If `tenant.domain` is NULL, skip Layer 2 and go to Layer 3. Log debug warning. Do not block.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/services/skill_executor.py` — engine dispatch pattern (lines 565-608), `_append_event_atomic()` (line 2400), `_execute_company_intel()` (line 811), model strings used in auth.py (`claude-haiku-4-20250514`) vs email_scorer model string
- `backend/src/flywheel/services/job_queue.py` — `job_queue_loop()` polling every 5s, no explicit enqueue needed
- `backend/src/flywheel/storage.py` — real `append_entry()` signature (lines 89-95), ContextEntry creation pattern
- `backend/src/flywheel/db/models.py` — `Meeting` (line 1245), `Account` (line 1091), `AccountContact` (line 1165), `ContextEntry` (line 182), `Tenant` (line 45) ORM definitions with all required fields
- `backend/src/flywheel/api/meetings.py` — Phase 60 sync endpoint (complete implementation, confirmed working)
- `backend/src/flywheel/services/granola_adapter.py` — `get_meeting_content()` ready to call (Phase 60)
- `backend/src/flywheel/services/document_storage.py` — Supabase Storage upload pattern
- `backend/src/flywheel/api/health.py` — confirms only `uploads` bucket required
- `backend/src/flywheel/engines/email_scorer.py` — `_HAIKU_MODEL = "claude-haiku-4-5-20251001"` (verified)
- `backend/src/flywheel/engines/company_intel.py` — `model="claude-sonnet-4-20250514"` (verified)
- `.planning/SPEC-intelligence-flywheel.md` — MPP-01 through MPP-05, AAL-01 through AAL-03 requirements
- `.planning/phases/60-meeting-data-model-and-granola-adapter/60-RESEARCH.md` — Phase 60 findings (Granola API shape, attendees caveat)

### Secondary (MEDIUM confidence)
- `.planning/SPEC-intelligence-flywheel.md` — spec code samples (verified against real codebase; deviations documented in Patterns 3, 7)
- `backend/src/flywheel/engines/meeting_processor.py` — `WRITE_TARGETS` list of 7 context files (CLI engine, names confirmed valid)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in pyproject.toml
- Engine dispatch pattern: HIGH — directly verified in skill_executor.py source
- Job queue mechanism: HIGH — read job_queue.py source; no enqueue_run() function exists; polling-based
- LLM model strings: HIGH — verified in email_scorer.py (Haiku) and company_intel.py (Sonnet)
- Context entry creation: HIGH — confirmed by reading storage.py and models.py
- Storage upload pattern: HIGH — confirmed by reading document_storage.py
- Granola adapter: HIGH — Phase 60 built and working, get_meeting_content() verified
- Account required fields: HIGH — read Account ORM definition, all NOT NULL fields documented
- Attendees from list vs detail: MEDIUM — behavioral inference from Phase 60 research, not directly tested

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stack is stable; Anthropic model strings are internal and could change)
