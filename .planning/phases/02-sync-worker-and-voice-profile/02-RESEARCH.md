# Phase 2: Sync Worker and Voice Profile - Research

**Researched:** 2026-03-24
**Domain:** Python asyncio background workers + Gmail historyId incremental sync + LLM-based voice profile extraction
**Confidence:** HIGH

---

## Summary

Phase 2 implements two services in `gmail_sync.py`: `email_sync_loop()` which polls every 5 minutes using Gmail's historyId incremental sync (with mandatory 404 fallback to full re-sync), and `voice_profile_init()` which fetches up to 200 sent emails, filters down to ~100 substantive ones, and uses a single Claude Haiku LLM call to extract the user's writing voice into an `EmailVoiceProfile` row.

Everything this phase needs is already established in the codebase. The sync loop pattern is a near-copy of `calendar_sync.py`, the LLM calling pattern is taken directly from `chat_orchestrator.py` and `onboarding_streams.py`, and the PostgreSQL upsert pattern (`pg_insert().on_conflict_do_update()`) is verified in `seed.py`. The only novel territory is Gmail's `history.list()` response structure (not identical to Calendar's `events.list()`) and the per-user `asyncio.wait_for()` timeout strategy to satisfy GMAIL-08.

Python 3.12 is in use (`pyproject.toml`), which means `asyncio.TaskGroup` and `asyncio.timeout()` are available, but the codebase currently uses `asyncio.gather(return_exceptions=True)` style — using the simpler `asyncio.wait_for()` per-integration approach inside the loop is the correct idiom to match existing style.

**Primary recommendation:** Model `gmail_sync.py` directly on `calendar_sync.py` — same loop structure, same session lifecycle, same token-revocation handling. The historyId 404-fallback maps exactly to Calendar's 410-fallback. Voice profile extraction is one LLM call after filtering, using the existing Haiku pattern.

---

## Standard Stack

### Core (all already installed — no new packages needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `google-api-python-client` | `>=2.150` | `history.list()`, `messages.get()`, `users.getProfile()` | Already in `pyproject.toml`; all calls exist in `gmail_read.py` |
| `googleapiclient.errors.HttpError` | transitive | Catch 404 from `history.list()` | Same import used in `calendar_sync.py` for 410 detection |
| `sqlalchemy[asyncio]` | `>=2.0` | Email upsert, EmailVoiceProfile upsert | `pg_insert().on_conflict_do_update()` pattern confirmed in `seed.py` |
| `sqlalchemy.dialects.postgresql.insert` | transitive | `INSERT ... ON CONFLICT DO UPDATE` | `from sqlalchemy.dialects.postgresql import insert as pg_insert` |
| `anthropic` | installed | `AsyncAnthropic` for voice profile LLM call | `settings.flywheel_subsidy_api_key`; Haiku model confirmed in chat_orchestrator/onboarding |
| `asyncio` | stdlib | `wait_for()` per-integration timeout, task sleep | Python 3.12 stdlib |

### Model Being Targeted

| Model | Relevant Fields | Upsert Key |
|-------|-----------------|------------|
| `Email` | `gmail_message_id`, `gmail_thread_id`, `sender_email`, `sender_name`, `subject`, `snippet`, `received_at`, `labels`, `is_read` | `UniqueConstraint("tenant_id", "gmail_message_id")` → `uq_email_tenant_message` |
| `EmailVoiceProfile` | `tone`, `avg_length`, `sign_off`, `phrases`, `samples_analyzed` | `UniqueConstraint("tenant_id", "user_id")` → `uq_voice_profile_tenant_user` |
| `Integration` | `settings["history_id"]`, `status`, `last_synced_at` | `provider="gmail-read"` |

### LLM Model for Voice Profile

Use `claude-haiku-4-5-20251001` (the same model as `chat_orchestrator.py` and `onboarding_streams.py`). Voice profile extraction is a cheap summarization task — Haiku is cost-appropriate. Use `client.messages.create()` with a JSON-output prompt (not `output_config` — that API variant is new and not currently used anywhere in the codebase; stick with the established pattern of prompting for JSON and parsing with `json.loads()`).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.wait_for()` per integration | `asyncio.TaskGroup` | TaskGroup is cleaner Python 3.11+ but codebase uses the simpler loop-based approach in `calendar_sync.py`. Consistency matters more than elegance here. |
| Haiku LLM voice extraction | spaCy/NLTK heuristic extraction | NLP libraries would require new dependencies and cannot produce the nuanced "characteristic phrases" and tone description that the schema requires. LLM approach is what the existing codebase always uses for extraction tasks. |
| `client.messages.parse()` structured output | JSON-prompt + `json.loads()` | `messages.parse()` is a newer SDK feature not used anywhere in the codebase yet. The established pattern (`messages.create()` + `json.loads()` + regex fallback) is proven and already in production. |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended File Structure

```
backend/src/flywheel/services/
├── gmail_sync.py        # NEW: email_sync_loop() + voice_profile_init()
└── gmail_read.py        # EXISTS: API operations (list_message_headers, get_history, etc.)

backend/src/flywheel/
└── main.py              # MODIFY: register gmail_sync_task in lifespan
```

This mirrors `calendar_sync.py` which is also separate from `google_calendar.py`.

### Pattern 1: Background Sync Loop (from `calendar_sync.py`)

**What:** Infinite `while True` loop with `asyncio.sleep(SYNC_INTERVAL)`. Short-lived DB sessions per cycle. Exception logged and swallowed at loop level to prevent crash.
**When to use:** All background workers in this codebase follow this pattern.

```python
# Source: backend/src/flywheel/services/calendar_sync.py (calendar_sync_loop)
SYNC_INTERVAL = 300  # 5 minutes

async def email_sync_loop() -> None:
    while True:
        try:
            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    select(Integration).where(
                        and_(
                            Integration.provider == "gmail-read",
                            Integration.status == "connected",
                        )
                    )
                )
                integrations = result.scalars().all()

                tasks = [
                    asyncio.wait_for(sync_gmail(session, intg), timeout=60.0)
                    for intg in integrations
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for intg, result in zip(integrations, results):
                    if isinstance(result, Exception):
                        logger.exception(
                            "Error syncing integration %s: %s", intg.id, result
                        )
        except Exception:
            logger.exception("Error in email sync loop iteration")
        await asyncio.sleep(SYNC_INTERVAL)
```

**Key difference from calendar:** Use `asyncio.wait_for()` per integration wrapped in `asyncio.gather()` to satisfy GMAIL-08 (5 concurrent users without timeout errors). Calendar loop processes integrations serially; email sync processes them concurrently.

### Pattern 2: historyId Incremental Sync with 404 Fallback

**What:** Try `history.list(startHistoryId=stored_id)`. If HTTP 404, clear stored `history_id` and call full re-sync. Mirror of Calendar's 410 fallback but with 404.

```python
# Source: derived from calendar_sync.py (_retry_count pattern) +
#         gmail_read.get_history() + Google official docs
# https://developers.google.com/workspace/gmail/api/guides/sync

async def sync_gmail(
    db: AsyncSession,
    integration: Integration,
    _retry_count: int = 0,
) -> int:
    creds = await get_valid_credentials(integration)
    history_id = (integration.settings or {}).get("history_id")

    if history_id is None:
        # Full sync path: fetch all INBOX messages
        return await _full_sync(db, integration, creds)

    try:
        response = await get_history(creds, history_id)
    except HttpError as exc:
        if exc.resp.status == 404 and _retry_count < 1:
            logger.info(
                "historyId expired for integration %s, doing full re-sync",
                integration.id,
            )
            settings = dict(integration.settings or {})
            settings["history_id"] = None
            integration.settings = settings
            return await sync_gmail(db, integration, _retry_count=1)
        raise

    # Process messageAdded events from history records
    message_ids = []
    for record in response.get("history", []):
        for msg_added in record.get("messagesAdded", []):
            message_ids.append(msg_added["message"]["id"])

    # Fetch headers for new messages and upsert Email rows
    count = 0
    for message_id in message_ids:
        msg = await get_message_headers(creds, message_id)
        await upsert_email(db, integration.tenant_id, integration.user_id, msg)
        count += 1

    # Store the new historyId returned by history.list()
    new_history_id = response.get("historyId")
    if new_history_id:
        settings = dict(integration.settings or {})
        settings["history_id"] = new_history_id
        integration.settings = settings

    integration.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    return count
```

### Pattern 3: Full Sync (historyId=None or 404 recovery)

**What:** On initial connect or after 404, call `list_message_headers()` with pagination (INBOX label), fetch headers for each, upsert Email rows. Store the `historyId` from `get_profile()` — NOT from the last page of messages.

```python
# Source: derived from gmail_read.list_message_headers + get_profile
# Key: capture historyId from get_profile() BEFORE paginating message list
# This ensures no messages are missed between paginator pages

async def _full_sync(
    db: AsyncSession,
    integration: Integration,
    creds: Credentials,
) -> int:
    # Capture historyId FIRST before fetching message list
    profile = await get_profile(creds)
    checkpoint_history_id = profile["historyId"]

    count = 0
    page_token = None
    while True:
        response = await list_message_headers(
            creds,
            page_token=page_token,
            label_ids=["INBOX"],
            max_results=100,
        )
        for stub in response.get("messages", []):
            msg = await get_message_headers(creds, stub["id"])
            await upsert_email(db, integration.tenant_id, integration.user_id, msg)
            count += 1

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    # Store the historyId captured before pagination started
    settings = dict(integration.settings or {})
    settings["history_id"] = checkpoint_history_id
    integration.settings = settings
    integration.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    return count
```

### Pattern 4: Email Upsert (pg_insert ON CONFLICT DO UPDATE)

**What:** Insert Email row or update on conflict with `(tenant_id, gmail_message_id)` unique constraint. Uses `pg_insert` from `sqlalchemy.dialects.postgresql`.

```python
# Source: backend/src/flywheel/db/seed.py (pg_insert pattern, lines 428-444)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from flywheel.db.models import Email

async def upsert_email(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    msg: dict,  # raw dict from get_message_headers()
) -> None:
    headers = {
        h["name"]: h["value"]
        for h in msg.get("payload", {}).get("headers", [])
    }
    # Parse Date header into datetime — use dateutil.parser.isoparse
    received_at = parse_email_date(headers.get("Date"))

    values = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "gmail_message_id": msg["id"],
        "gmail_thread_id": msg["threadId"],
        "sender_email": extract_email_address(headers.get("From", "")),
        "sender_name": extract_display_name(headers.get("From", "")),
        "subject": headers.get("Subject"),
        "snippet": msg.get("snippet"),  # snippet is on message root, not headers
        "received_at": received_at,
        "labels": msg.get("labelIds", []),
        "is_read": "UNREAD" not in msg.get("labelIds", []),
    }

    stmt = pg_insert(Email).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_email_tenant_message",
        set_={
            "subject": stmt.excluded.subject,
            "snippet": stmt.excluded.snippet,
            "labels": stmt.excluded.labels,
            "is_read": stmt.excluded.is_read,
            "synced_at": func.now(),
        },
    )
    await db.execute(stmt)
    # NOTE: do NOT commit here — caller commits after all upserts
```

**Note:** `msg.get("snippet")` — when using `format="metadata"`, the Gmail API returns a `snippet` field at the message root level (not inside headers). Verify this is acceptable per PII policy. The snippet is ~100 chars and is distinct from the body. Given the existing `snippet` column on the Email model, storing it is intended.

### Pattern 5: Voice Profile Init (LLM extraction)

**What:** Fetch up to 200 sent messages, get body for each substantive one, filter out auto-replies/OOO/one-liners, send ~100 sample bodies to Haiku for structured voice extraction, upsert `EmailVoiceProfile`.

```python
# Source: derived from onboarding_streams.py (AsyncAnthropic + Haiku pattern)
# and seed.py (pg_insert upsert)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

VOICE_SYSTEM_PROMPT = """\
You are analyzing email samples to extract a user's writing voice profile.
Return a JSON object with exactly these fields:
- tone: string (e.g., "professional and concise", "warm and conversational")
- avg_length: integer (estimated average email length in words)
- sign_off: string (most common sign-off phrase, e.g., "Best," or "Thanks,")
- phrases: array of strings (3-5 characteristic phrases or expressions the person uses)
- samples_analyzed: integer (number of emails analyzed)

Return only the JSON object, no other text."""

async def voice_profile_init(
    db: AsyncSession,
    integration: Integration,
) -> bool:
    """Extract voice profile from sent mail and store in EmailVoiceProfile.

    Returns True if profile was created/updated, False if skipped (already exists).
    """
    # Check if voice profile already exists — idempotent
    existing = await db.execute(
        select(EmailVoiceProfile).where(
            and_(
                EmailVoiceProfile.tenant_id == integration.tenant_id,
                EmailVoiceProfile.user_id == integration.user_id,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False  # Already initialized

    creds = await get_valid_credentials(integration)
    sent_response = await list_sent_messages(creds, max_results=200)
    stubs = sent_response.get("messages", [])

    # Fetch bodies and filter to substantive emails
    substantive_bodies = []
    for stub in stubs:
        if len(substantive_bodies) >= 100:
            break
        body = await get_message_body(creds, stub["id"])
        if _is_substantive(body):
            substantive_bodies.append(body)

    if not substantive_bodies:
        logger.warning(
            "No substantive sent emails found for integration %s", integration.id
        )
        return False

    # LLM call — use subsidy key, Haiku model
    profile_data = await _extract_voice_profile(substantive_bodies)

    # Upsert voice profile
    stmt = pg_insert(EmailVoiceProfile).values(
        tenant_id=integration.tenant_id,
        user_id=integration.user_id,
        tone=profile_data.get("tone"),
        avg_length=profile_data.get("avg_length"),
        sign_off=profile_data.get("sign_off"),
        phrases=profile_data.get("phrases", []),
        samples_analyzed=profile_data.get("samples_analyzed", len(substantive_bodies)),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_voice_profile_tenant_user",
        set_={
            "tone": stmt.excluded.tone,
            "avg_length": stmt.excluded.avg_length,
            "sign_off": stmt.excluded.sign_off,
            "phrases": stmt.excluded.phrases,
            "samples_analyzed": stmt.excluded.samples_analyzed,
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)
    await db.commit()
    return True


def _is_substantive(body: str) -> bool:
    """Return True if email body is substantive (not auto-reply, OOO, or one-liner).

    Filters (all must pass):
    1. Body has at least 3 sentences (proxy for >3 sentence requirement)
    2. Does not match common auto-reply patterns
    """
    if not body or len(body.strip()) < 50:
        return False
    # Auto-reply / OOO / calendar acceptance patterns
    body_lower = body.lower()
    auto_reply_patterns = [
        "out of office",
        "auto-reply",
        "automatic reply",
        "i am currently out",
        "accepted:",
        "declined:",
        "tentative:",
        "has accepted your invitation",
        "this is an automated",
        "do not reply to this",
    ]
    if any(p in body_lower for p in auto_reply_patterns):
        return False
    # Count sentences as a proxy (split on ". " or "? " or "! ")
    import re
    sentences = re.split(r'[.!?]\s+', body.strip())
    sentences = [s for s in sentences if len(s.strip()) > 10]
    return len(sentences) >= 3
```

### Pattern 6: Background Task Registration (from `main.py`)

**What:** Register `email_sync_loop` as an `asyncio.create_task()` in the lifespan function alongside `calendar_sync_loop`.

```python
# Source: backend/src/flywheel/main.py (lifespan function)
from flywheel.services.gmail_sync import email_sync_loop

gmail_sync_task = asyncio.create_task(email_sync_loop())

# In shutdown block:
for task in (..., gmail_sync_task):
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
```

### Pattern 7: RLS Context for Background Workers

Background workers cannot use the FastAPI `Depends(get_tenant_db)` injection. They use `get_session_factory()` to get a session factory, then `tenant_session()` context manager for per-integration RLS context.

```python
# Source: backend/src/flywheel/db/session.py (tenant_session context manager)
from flywheel.db.session import get_session_factory, tenant_session

factory = get_session_factory()
async with tenant_session(factory, str(integration.tenant_id), str(integration.user_id)) as session:
    await upsert_email(session, ...)
```

**Critical:** The outer `calendar_sync_loop` uses `factory() as session` directly (superuser context) to read the `Integration` rows. The per-email upserts must be done in a `tenant_session` context so RLS is enforced. The planner must decide whether to (a) load integrations in superuser context then switch to tenant context per-integration, or (b) use separate sessions. Option (a) is simpler and matches calendar behavior.

### Anti-Patterns to Avoid

- **Storing historyId from last pagination page:** Always capture historyId from `get_profile()` BEFORE starting pagination. Capturing it afterward produces a stale checkpoint.
- **Processing all 200 sent bodies for voice profile:** Filter to `_is_substantive()` first, then stop at 100. Sending 200 full email bodies to the LLM is unnecessary and expensive.
- **Committing inside `upsert_email()`:** The upsert function must NOT commit. Commit is done once after all messages in a batch are processed — prevents partial-sync state.
- **Using `asyncio.gather()` without `return_exceptions=True` for multi-user sync:** Without this flag, a single integration failure raises immediately and cancels all other in-flight syncs.
- **Logging email content (snippet, subject, body) anywhere in gmail_sync.py:** Log only `message_id`, `thread_id`, `integration_id`. This is a hard requirement from DATA-01 / Pitfall 2 from Phase 1 research.
- **Calling `voice_profile_init()` on every sync cycle:** Check for existing `EmailVoiceProfile` row first. Voice profile init runs once per user, not on every poll.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Email date parsing | Custom date string parser | `dateutil.parser.parse()` (already installed via `python-dateutil` transitive dep) | RFC 2822 email dates have dozens of formats; dateutil handles them all |
| Email address extraction from "Name <email>" header | Custom regex | `email.headerregistry` (stdlib) or simple split on `<`/`>` | Multiple valid From header formats; stdlib handles them correctly |
| Sentence counting for `_is_substantive()` | NLTK sentence tokenizer | Simple `re.split(r'[.!?]\s+', ...)` | NLTK adds 20MB+ of data downloads not needed for this simple filter |
| JSON output from LLM | Pydantic + `messages.parse()` | `messages.create()` + `json.loads()` + regex fallback | Matches existing pattern in chat_orchestrator.py and onboarding_streams.py; no new SDK feature to validate |
| Concurrent user sync | Thread pool executor | `asyncio.wait_for()` + `asyncio.gather()` | Already async; threads waste resources and add complexity |

**Key insight:** Every complex sub-problem in this phase already has an established solution in the codebase. The pattern library is `calendar_sync.py` (loop), `seed.py` (upsert), `chat_orchestrator.py` (LLM).

---

## Common Pitfalls

### Pitfall 1: historyId Captured from Wrong Point in Full Sync
**What goes wrong:** The `history_id` stored after full sync is stale — new messages arrive during pagination and are missed in the first incremental sync cycle.
**Why it happens:** `messages.list()` pagination can take multiple seconds. Messages arriving during pagination fall between `page N historyId` and `page 1 historyId`.
**How to avoid:** Call `get_profile()` first to get the current `historyId`, THEN paginate messages. Store the `historyId` from `get_profile()`, not from any message response.
**Warning signs:** Missing messages in the first 5-minute window after initial sync.

### Pitfall 2: Gmail `history.list()` Returns Empty `history` Array (Not an Error)
**What goes wrong:** When no new messages have arrived since last sync, `history.list()` returns `{"historyId": "xxx"}` with NO `history` key (not an empty list). Code doing `response["history"]` raises `KeyError`.
**Why it happens:** The Gmail API omits the `history` key entirely when there are no changes, rather than returning `[]`.
**How to avoid:** Always use `response.get("history", [])` not `response["history"]`.
**Warning signs:** `KeyError: 'history'` in sync logs on quiet inboxes.

### Pitfall 3: `snippet` on `format="metadata"` Messages
**What goes wrong:** Code tries `msg["payload"]["headers"]` for the snippet, but snippet is at `msg["snippet"]` — the message root level, not inside the payload.
**Why it happens:** `snippet` is a top-level field in the Gmail message resource, not a header.
**How to avoid:** Access `msg.get("snippet")` directly.
**Warning signs:** `None` values in the `snippet` column despite messages having content.

### Pitfall 4: Per-Integration Session Shares DB Transaction with Integration Load
**What goes wrong:** Modifying `integration.settings["history_id"]` inside a shared session that loaded the integration row creates implicit transaction coupling. A failure in one integration's sync can roll back another integration's committed checkpoint.
**Why it happens:** All integrations loaded into the same session share a transaction.
**How to avoid:** Either commit after each integration (current pattern in calendar_sync.py), or load integrations in one session and process each in an isolated session. The calendar pattern of committing inside `sync_calendar()` is acceptable — use the same approach.
**Warning signs:** `history_id` not being updated after successful sync cycles.

### Pitfall 5: Voice Profile LLM Call on Every Sync Cycle
**What goes wrong:** `voice_profile_init()` is called inside the sync loop without checking for an existing profile. Each 5-minute cycle triggers a 200-email fetch + LLM call for every user.
**Why it happens:** Developers call `voice_profile_init()` unconditionally after `sync_gmail()`.
**How to avoid:** Check `EmailVoiceProfile` existence first. Run `voice_profile_init()` only when no profile exists for the user. The function itself has an idempotency guard, but the caller should also avoid the unnecessary DB lookup.
**Warning signs:** Repeated `list_sent_messages` calls visible in logs every 5 minutes.

### Pitfall 6: Auto-Reply Filter Must Run BEFORE Body Fetch
**What goes wrong:** Fetching full body for all 200 sent messages then filtering — 200 API calls instead of ~50.
**Why it happens:** Filter logic placed after body fetch loop.
**How to avoid:** For the voice profile, first get message stubs (list_sent_messages), then for each: check if we already have 100 substantive bodies, fetch body, apply `_is_substantive()` filter, add to list if passes. Stop when 100 reached.
**Warning signs:** `get_message_body` called 200 times in logs for voice init.

### Pitfall 7: Logging Email Content
**What goes wrong:** `logger.debug("Processing message: %s", msg)` logs the full message dict which contains `snippet` (PII-laden subject content).
**Why it happens:** Developer adds debug logging without realizing message dict contains content.
**How to avoid:** Log only `message_id`, `thread_id`, `integration_id`. Never log the msg dict.
**Warning signs:** Email subjects or sender names visible in log output.

---

## Code Examples

Verified patterns from existing codebase sources:

### asyncio.gather with per-task timeout and return_exceptions

```python
# Source: derived from calendar_sync.py loop structure +
#         asyncio.wait_for documented in Python 3.12 stdlib

tasks = [
    asyncio.wait_for(sync_gmail(session, intg), timeout=60.0)
    for intg in integrations
]
results = await asyncio.gather(*tasks, return_exceptions=True)
for intg, result in zip(integrations, results):
    if isinstance(result, TimeoutError):
        logger.warning("Sync timeout for integration %s", intg.id)
    elif isinstance(result, Exception):
        logger.exception("Sync error for integration %s: %s", intg.id, result)
```

### PostgreSQL Upsert (pg_insert + on_conflict_do_update)

```python
# Source: backend/src/flywheel/db/seed.py, lines 427-444
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

stmt = pg_insert(Email).values(**values)
stmt = stmt.on_conflict_do_update(
    constraint="uq_email_tenant_message",
    set_={
        "labels": stmt.excluded.labels,
        "is_read": stmt.excluded.is_read,
        "synced_at": func.now(),
    },
)
await db.execute(stmt)
```

### Haiku LLM Call with JSON Prompt

```python
# Source: backend/src/flywheel/services/onboarding_streams.py (lines 53-75)
import anthropic
import json

client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
response = await client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1000,
    system=VOICE_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": "\n\n---\n\n".join(sample_bodies[:20])}],
)
text = response.content[0].text.strip()
try:
    return json.loads(text)
except json.JSONDecodeError:
    import re
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise
```

### historyId 404 Fallback (mirrors calendar 410 pattern)

```python
# Source: backend/src/flywheel/services/calendar_sync.py (lines 183-196)
# Gmail equivalent — same _retry_count guard

try:
    response = await get_history(creds, history_id)
except HttpError as exc:
    if exc.resp.status == 404 and _retry_count < 1:
        logger.info("historyId expired for %s, doing full re-sync", integration.id)
        settings = dict(integration.settings or {})
        settings["history_id"] = None
        integration.settings = settings
        return await sync_gmail(db, integration, _retry_count=1)
    raise
```

### Token Revocation Handling

```python
# Source: backend/src/flywheel/services/calendar_sync.py (lines 243-250)
# Identical pattern works for gmail-read

except TokenRevokedException:
    logger.warning(
        "Token revoked for integration %s, marking disconnected", integration.id
    )
    integration.status = "disconnected"
    integration.credentials_encrypted = None
    await session.commit()
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `asyncio.gather()` bare (stops on first exception) | `asyncio.gather(return_exceptions=True)` with `asyncio.wait_for()` per task | Multi-user sync doesn't crash on one bad token |
| `client.messages.parse()` with Pydantic (newer API) | `client.messages.create()` + `json.loads()` + regex fallback | Consistent with existing codebase; no new SDK feature to test |
| `asyncio.TaskGroup` (Python 3.11+) | `asyncio.gather()` loop (existing codebase style) | TaskGroup is more elegant but calendar_sync.py doesn't use it; consistency matters |

**Gmail-specific:**
- `history.list()` returns `historyId` in the response root even when `history` array is absent — always use `response.get("historyId")` to update the checkpoint on every incremental sync call, even empty ones.
- `historyTypes=["messageAdded"]` filter in `get_history()` (already set in `gmail_read.py`) means `history` records only contain `messagesAdded` — no need to handle `labelsAdded` or `messageDeleted` sub-arrays for this phase.

---

## Open Questions

1. **Should voice_profile_init() be triggered inside email_sync_loop() or as a separate call on OAuth callback?**
   - What we know: Phase requirement says "before first draft request ever arrives" and "after first sync." Triggering in sync loop on first cycle (when no voice profile exists) satisfies both constraints.
   - What's unclear: Whether triggering it on every sync loop iteration (with idempotency check) is acceptable, or if it should be a one-time callback from the OAuth flow.
   - Recommendation: Trigger it inside `email_sync_loop()` after the first successful `sync_gmail()`. Check `EmailVoiceProfile` existence in the loop. This keeps the sync worker self-contained and avoids a separate background trigger mechanism.

2. **How many sample bodies should be sent to the LLM in one call?**
   - What we know: Up to 100 substantive emails pass the filter, but sending 100 full email bodies in one prompt is expensive (potentially 50k+ tokens).
   - What's unclear: Whether to send all 100 or a representative sample (e.g., 20 most recent).
   - Recommendation: Send the 20 most recent substantive bodies (most recent writing style is most representative). Cap at 20 to keep the prompt under ~8k tokens with Haiku's context.

3. **Does `format="metadata"` from `get_message_headers()` return the `snippet` field?**
   - What we know: `snippet` is a top-level message field. `list_message_headers()` returns stubs (id + threadId only). `get_message_headers()` uses `format="metadata"`.
   - What's unclear: Whether `format="metadata"` includes `snippet` in the response.
   - Recommendation: Use `get_message_headers()` for the metadata, and access `msg.get("snippet", "")`. If snippet is absent, the column default (`NULL`) is acceptable. Verify by inspecting a test response.

4. **Voice profile: what happens if the user has fewer than 3 substantive sent emails?**
   - What we know: New accounts or privacy-conscious senders may have few sent items.
   - What's unclear: Whether to skip voice profile init or create a minimal one.
   - Recommendation: Skip (return `False` from `voice_profile_init()`) if fewer than 3 substantive bodies found. Log a warning. The sync loop can retry on subsequent cycles.

---

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/services/calendar_sync.py` — sync loop pattern, 410-fallback (_retry_count), token revocation, session lifecycle
- `backend/src/flywheel/services/gmail_read.py` — `get_history()`, `list_message_headers()`, `get_message_headers()`, `list_sent_messages()`, `get_message_body()`, `get_profile()` — all Phase 2 uses confirmed
- `backend/src/flywheel/services/chat_orchestrator.py` — `AsyncAnthropic` + Haiku pattern, `json.loads()` + regex fallback
- `backend/src/flywheel/services/onboarding_streams.py` — confirmed second usage of Haiku for extraction tasks
- `backend/src/flywheel/db/seed.py` — `pg_insert().on_conflict_do_update()` confirmed with `constraint=` named constraint
- `backend/src/flywheel/db/models.py` — `Email` (uq_email_tenant_message), `EmailVoiceProfile` (uq_voice_profile_tenant_user) confirmed
- `backend/src/flywheel/db/session.py` — `tenant_session()` context manager, `get_session_factory()`
- `backend/src/flywheel/main.py` — `asyncio.create_task()` in lifespan, shutdown cancellation pattern
- `backend/src/flywheel/api/integrations.py` — confirmed `settings["history_id"] = None` in OAuth callback
- `pyproject.toml` — confirmed Python 3.12, `asyncio_mode = "auto"`, all libraries already installed

### Secondary (MEDIUM confidence)
- [Google Gmail API Sync Guide](https://developers.google.com/workspace/gmail/api/guides/sync) — historyId validity, 404 fallback requirement, store historyId from most recent message pattern
- [Python asyncio docs - asyncio.gather](https://docs.python.org/3/library/asyncio-task.html) — `return_exceptions=True`, `asyncio.wait_for()` per-task timeout

### Tertiary (LOW confidence — flag for validation)
- Gmail `format="metadata"` response structure including `snippet` field presence — verify with a live API call before implementing upsert_email
- Haiku context window capacity for 20 email bodies — estimate based on typical email length; validate during implementation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages confirmed in pyproject.toml, zero new dependencies
- Sync loop architecture: HIGH — directly derived from calendar_sync.py with documented Gmail-specific delta
- historyId sync pattern: HIGH — confirmed via official Google docs + existing `get_history()` implementation
- Email upsert pattern: HIGH — pg_insert + on_conflict confirmed in seed.py
- Voice profile LLM call: HIGH — AsyncAnthropic + Haiku + json.loads pattern confirmed in two existing services
- Filtering heuristics (`_is_substantive`): MEDIUM — logic is reasonable but exact sentence thresholds are a judgment call

**Research date:** 2026-03-24
**Valid until:** 2026-06-01 (stable Google APIs, stable SQLAlchemy 2.0, stable Anthropic SDK patterns)
