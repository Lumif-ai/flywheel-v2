"""Gmail inbox sync background service.

Handles:
- Background sync loop (5-minute interval) polling connected gmail-read integrations
- Incremental sync using historyId (messagesAdded events only)
- Full re-sync on stale historyId (HTTP 404 response)
- historyId captured from get_profile() BEFORE pagination to prevent missed messages
- Email upsert with ON CONFLICT DO UPDATE (no duplicates)
- Token revocation detection (marks integration disconnected)
- Per-integration asyncio timeout + concurrent gather (multi-user safe)

PII compliance:
- NEVER log subject, snippet, sender_email, body, or msg dict contents
- Only log message_id, thread_id, integration.id, and counts
"""

from __future__ import annotations

import asyncio
import email.utils
import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

import anthropic
from googleapiclient.errors import HttpError
from sqlalchemy import and_, select
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import Email, EmailDraft, EmailScore, EmailVoiceProfile, Integration
from flywheel.engines.email_drafter import draft_email
from flywheel.engines.model_config import get_engine_model
from flywheel.engines.email_scorer import score_email
from flywheel.db.session import get_session_factory, tenant_session
from flywheel.services.gmail_read import (
    TokenRevokedException,
    get_history,
    get_message_body,
    get_message_headers,
    get_profile,
    get_valid_credentials,
    list_message_headers,
    list_sent_messages,
)

logger = logging.getLogger(__name__)

SYNC_INTERVAL = 300  # 5 minutes
PER_INTEGRATION_TIMEOUT = 60.0  # seconds


# ---------------------------------------------------------------------------
# Email date parsing
# ---------------------------------------------------------------------------


def _parse_email_date(date_str: str | None) -> datetime | None:
    """Parse an RFC 2822 email Date header into a timezone-aware datetime.

    Uses email.utils.parsedate_to_datetime from stdlib — handles RFC 2822
    email date format natively. Returns None on any parse failure.
    """
    if not date_str:
        return None
    try:
        return email.utils.parsedate_to_datetime(date_str)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Email upsert
# ---------------------------------------------------------------------------


async def upsert_email(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    msg: dict,
) -> UUID:
    """Upsert a single email row from a Gmail message metadata dict.

    Extracts header fields, builds an Email row, and issues a PostgreSQL
    INSERT ... ON CONFLICT DO UPDATE so re-syncing is safe.

    Does NOT commit — caller commits after processing the full batch.

    Args:
        db: Active SQLAlchemy async session.
        tenant_id: UUID of the tenant owning this message.
        user_id: UUID of the user whose gmail-read integration produced this.
        msg: Gmail API message dict (metadata format — no body).

    Returns:
        UUID of the upserted Email row (for scoring integration).
    """
    # Extract headers into a lookup dict
    raw_headers = msg.get("payload", {}).get("headers", [])
    headers: dict[str, str] = {h["name"]: h["value"] for h in raw_headers if "name" in h and "value" in h}

    # Parse sender
    from_header = headers.get("From", "")
    sender_name_raw, sender_email_parsed = email.utils.parseaddr(from_header)
    sender_email_str = sender_email_parsed or from_header
    sender_name_str = sender_name_raw or None

    # Parse received_at — fall back to now() if unparseable
    received_at = _parse_email_date(headers.get("Date"))
    if received_at is None:
        received_at = datetime.now(timezone.utc)

    label_ids: list[str] = msg.get("labelIds", [])
    is_read = "UNREAD" not in label_ids

    values = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "gmail_message_id": msg["id"],
        "gmail_thread_id": msg["threadId"],
        "sender_email": sender_email_str,
        "sender_name": sender_name_str,
        "subject": headers.get("Subject"),
        "snippet": msg.get("snippet"),
        "received_at": received_at,
        "labels": label_ids,
        "is_read": is_read,
    }

    stmt = (
        pg_insert(Email)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_email_tenant_message",
            set_={
                "subject": values["subject"],
                "snippet": values["snippet"],
                "labels": values["labels"],
                "is_read": values["is_read"],
                "synced_at": datetime.now(timezone.utc),
            },
        )
        .returning(Email.id)
    )
    result = await db.execute(stmt)
    email_id: UUID = result.scalar_one()

    logger.debug(
        "upserted email message_id=%s thread_id=%s",
        msg["id"],
        msg["threadId"],
    )
    return email_id


# ---------------------------------------------------------------------------
# Scoring integration helpers
# ---------------------------------------------------------------------------


async def _check_daily_scoring_cap(
    db: AsyncSession,
    tenant_id: UUID,
    cap: int = 500,
) -> int:
    """Return remaining scoring budget for today. Default cap: 500/day.

    Counts EmailScore rows created today (UTC) for the given tenant by joining
    email_scores to emails on tenant_id. Uses scored_at >= today so re-scoring
    an email that was already scored today counts against the cap.

    Args:
        db: Tenant-scoped async session (RLS enforced).
        tenant_id: Tenant UUID.
        cap: Maximum number of scores allowed per day (default 500).

    Returns:
        Remaining budget: max(0, cap - count_today). Returns 0 if cap reached.
    """
    today_utc = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    result = await db.execute(
        sa_text(
            "SELECT COUNT(*) FROM email_scores es "
            "JOIN emails e ON es.email_id = e.id "
            "WHERE e.tenant_id = :tid AND es.scored_at >= :today"
        ).bindparams(tid=tenant_id, today=today_utc)
    )
    count = result.scalar_one()
    return max(0, cap - count)


async def _score_new_emails(
    db: AsyncSession,
    tenant_id: UUID,
    email_ids: list[UUID],
) -> int:
    """Score a batch of newly synced emails. Returns count of emails scored.

    SCORE-08: New messages in existing threads are scored here automatically.
    Thread priority (SCORE-07) is computed at read time via get_thread_priority().

    FEED-03 (Thread Re-scoring): New messages in existing threads are automatically
    handled here. When incremental sync picks up a messagesAdded event for an existing
    thread, the new email_id is included in the email_ids list passed to this function.
    The new message gets its own EmailScore row. Thread-level priority auto-updates
    because get_thread_priority() is a read-time MAX query (SCORE-07) — no additional
    re-scoring trigger is needed.

    Enforces the per-tenant daily cap before scoring. If the cap is reached,
    logs a warning and returns 0 without scoring any emails.

    Per-email exceptions are caught and logged (non-fatal) — one bad email
    never blocks the rest or the sync cycle.

    Args:
        db: Tenant-scoped async session (RLS enforced). Caller commits after
            this function returns.
        tenant_id: Tenant UUID.
        email_ids: List of Email UUIDs from the current sync batch.

    Returns:
        Number of emails successfully scored.
    """
    if not email_ids:
        return 0

    # Check daily cap
    remaining = await _check_daily_scoring_cap(db, tenant_id)
    if remaining == 0:
        logger.warning(
            "Daily scoring cap reached for tenant %s — skipping %d email(s)",
            tenant_id,
            len(email_ids),
        )
        return 0

    # Truncate to remaining budget
    ids_to_score = email_ids[:remaining]
    total = len(email_ids)

    # Load Email ORM rows for the IDs to score
    result = await db.execute(
        select(Email).where(Email.id.in_(ids_to_score))
    )
    emails = result.scalars().all()

    scored_count = 0
    for email in emails:
        try:
            score = await score_email(db, tenant_id, email)
            if score is None:
                logger.warning(
                    "score_email returned None for email_id=%s tenant_id=%s",
                    email.id,
                    tenant_id,
                )
            else:
                scored_count += 1
        except Exception:
            logger.exception(
                "Unexpected error scoring email_id=%s tenant_id=%s",
                email.id,
                tenant_id,
            )
            # Non-fatal: continue scoring remaining emails

    # Single commit for the entire batch (caller-commits pattern)
    await db.commit()

    logger.info(
        "Scored %d/%d emails for tenant %s",
        scored_count,
        total,
        tenant_id,
    )
    return scored_count


async def _draft_important_emails(
    db: AsyncSession,
    tenant_id: UUID,
    integration: Integration,
    email_ids: list[UUID],
) -> int:
    """Draft replies for scored emails with priority >= 3 and suggested_action=draft_reply.

    Queries EmailScore rows for the given email_ids, filters for draftable criteria,
    skips emails that already have an EmailDraft row (LEFT JOIN IS NULL guard),
    calls draft_email() per match. Returns count of drafts created.

    Non-fatal: individual draft failures are logged but never block the sync loop.

    Args:
        db: Tenant-scoped async session (RLS enforced).
        tenant_id: Tenant UUID.
        integration: gmail-read Integration row (passed to draft_email for credential access).
        email_ids: List of Email UUIDs from the current sync batch (already scored).

    Returns:
        Number of draft rows successfully created.
    """
    if not email_ids:
        return 0

    # Query emails that need drafting: scored >= 3 with draft_reply action, no existing draft
    from sqlalchemy.orm import aliased

    EmailDraftAlias = aliased(EmailDraft)

    result = await db.execute(
        select(Email, EmailScore)
        .join(EmailScore, EmailScore.email_id == Email.id)
        .outerjoin(EmailDraftAlias, EmailDraftAlias.email_id == Email.id)
        .where(
            and_(
                Email.id.in_(email_ids),
                Email.tenant_id == tenant_id,
                EmailScore.priority >= 3,
                EmailScore.suggested_action == "draft_reply",
                EmailDraftAlias.id.is_(None),
            )
        )
    )
    rows = result.all()

    draft_count = 0
    for email_row, score_row in rows:
        try:
            draft = await draft_email(db, tenant_id, email_row, score_row, integration)
            if draft is None:
                logger.warning(
                    "draft_email returned None for email_id=%s tenant_id=%s",
                    email_row.id,
                    tenant_id,
                )
            else:
                draft_count += 1
        except Exception:
            logger.exception(
                "Unexpected error drafting email_id=%s tenant_id=%s",
                email_row.id,
                tenant_id,
            )
            # Non-fatal: continue drafting remaining emails

    # Single commit for the entire batch (caller-commits pattern)
    await db.commit()

    logger.info(
        "Drafted %d/%d qualifying emails for tenant %s",
        draft_count,
        len(rows),
        tenant_id,
    )
    return draft_count


async def get_thread_priority(
    db: AsyncSession,
    tenant_id: UUID,
    gmail_thread_id: str,
) -> int | None:
    """Compute thread priority as MAX(priority) of unhandled messages in the thread.

    SCORE-07: Thread-level priority is a read-time computation — not a stored
    column. The highest priority score among all unhandled (is_replied=False)
    messages in the thread determines the thread's displayed priority.

    Used by Phase 5 API layer — exported for import.

    Args:
        db: Tenant-scoped async session (RLS enforced).
        tenant_id: Tenant UUID.
        gmail_thread_id: Gmail thread ID string (e.g. "187abc123def4567").

    Returns:
        Integer priority 1-5, or None if no scored messages exist for the thread.
    """
    result = await db.execute(
        sa_text(
            "SELECT MAX(es.priority) FROM email_scores es "
            "JOIN emails e ON es.email_id = e.id "
            "WHERE e.tenant_id = :tid "
            "AND e.gmail_thread_id = :thread_id "
            "AND e.is_replied = FALSE"
        ).bindparams(tid=tenant_id, thread_id=gmail_thread_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Full sync (initial or recovery)
# ---------------------------------------------------------------------------


async def _full_sync(
    db: AsyncSession,
    integration: Integration,
    creds,
) -> int:
    """Perform a full inbox sync for an integration.

    CRITICAL: get_profile() is called BEFORE pagination begins so the
    historyId checkpoint reflects the state at sync-start. Any messages
    that arrive during pagination will be caught on the next incremental
    sync rather than missed entirely.

    Args:
        db: Tenant-scoped async session.
        integration: Integration ORM row with provider="gmail-read".
        creds: Valid Google OAuth2 Credentials.

    Returns:
        Total number of email rows upserted.
    """
    # Capture historyId BEFORE pagination — prevents missed messages
    profile = await get_profile(creds)
    checkpoint_history_id = profile.get("historyId")

    logger.info(
        "Starting full sync for integration %s (checkpoint historyId=%s)",
        integration.id,
        checkpoint_history_id,
    )

    count = 0
    new_email_ids: list[UUID] = []
    synced_gmail_ids: set[str] = set()
    page_token: str | None = None

    while True:
        response = await list_message_headers(
            creds,
            page_token=page_token,
            label_ids=["INBOX"],
            max_results=100,
        )
        messages = response.get("messages", [])

        for stub in messages:
            synced_gmail_ids.add(stub["id"])
            msg = await get_message_headers(creds, stub["id"])
            email_id = await upsert_email(
                db, integration.tenant_id, integration.user_id, msg
            )
            # FEED-03: Both new threads and new messages in existing threads get scored.
            new_email_ids.append(email_id)
            count += 1

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    # Reconcile: remove emails in our DB that are no longer in Gmail INBOX.
    # Compare DB gmail_message_ids against the set we just synced.
    all_db_result = await db.execute(
        select(Email.id, Email.gmail_message_id).where(
            Email.tenant_id == integration.tenant_id,
            Email.user_id == integration.user_id,
        )
    )
    stale_ids = [
        row[0] for row in all_db_result.fetchall()
        if row[1] not in synced_gmail_ids
    ]
    if stale_ids:
        await db.execute(EmailDraft.__table__.delete().where(EmailDraft.email_id.in_(stale_ids)))
        await db.execute(EmailScore.__table__.delete().where(EmailScore.email_id.in_(stale_ids)))
        await db.execute(Email.__table__.delete().where(Email.id.in_(stale_ids)))
        logger.info(
            "Full sync: removed %d stale emails for integration %s",
            len(stale_ids),
            integration.id,
        )

    # Store checkpoint historyId from BEFORE pagination
    settings = dict(integration.settings or {})
    settings["history_id"] = checkpoint_history_id
    integration.settings = settings
    integration.last_synced_at = datetime.now(timezone.utc)

    await db.commit()

    logger.info(
        "Full sync complete for integration %s: %d emails upserted",
        integration.id,
        count,
    )

    # Score new emails AFTER commit — scoring failure cannot lose synced emails
    if new_email_ids:
        try:
            scored = await _score_new_emails(db, integration.tenant_id, new_email_ids)
            logger.info(
                "Scored %d new emails for integration %s", scored, integration.id
            )
        except Exception:
            logger.exception(
                "Scoring failed for integration %s", integration.id
            )
            # Non-fatal — sync is already committed, scoring failure doesn't lose emails

        # Draft important emails AFTER scoring — draft failure cannot lose synced/scored emails
        try:
            drafted = await _draft_important_emails(
                db, integration.tenant_id, integration, new_email_ids
            )
            logger.info("Drafted %d emails for integration %s", drafted, integration.id)
        except Exception:
            logger.exception("Drafting failed for integration %s", integration.id)
            # Non-fatal — sync and scoring already committed

    return count


# ---------------------------------------------------------------------------
# Incremental sync (historyId-based)
# ---------------------------------------------------------------------------


async def sync_gmail(
    db: AsyncSession,
    integration: Integration,
    _retry_count: int = 0,
) -> int:
    """Sync a single gmail-read integration using historyId incremental sync.

    Falls back to _full_sync when:
    - history_id is None (first sync)
    - Gmail returns HTTP 404 (stale historyId)

    Args:
        db: Tenant-scoped async session.
        integration: Integration ORM row with provider="gmail-read".
        _retry_count: Internal recursion guard — do not pass externally.

    Returns:
        Number of messages processed this cycle.

    Raises:
        TokenRevokedException: Propagated from get_valid_credentials.
        HttpError: Re-raised if not a retryable 404.
    """
    creds = await get_valid_credentials(integration)

    history_id = (integration.settings or {}).get("history_id")

    if history_id is None:
        return await _full_sync(db, integration, creds)

    try:
        response = await get_history(creds, history_id)
    except HttpError as exc:
        if exc.resp.status == 404 and _retry_count < 1:
            logger.warning(
                "historyId stale (404) for integration %s — falling back to full sync",
                integration.id,
            )
            settings = dict(integration.settings or {})
            settings["history_id"] = None
            integration.settings = settings
            return await sync_gmail(db, integration, _retry_count=1)
        raise

    # Gmail omits "history" key when there are no new records — use .get()
    history_records = response.get("history", [])
    count = 0
    new_email_ids: list[UUID] = []

    for record in history_records:
        # --- Handle new messages (only if they're in INBOX) ---
        for added_entry in record.get("messagesAdded", []):
            message_stub = added_entry.get("message", {})
            message_id = message_stub.get("id")
            if not message_id:
                continue
            # Only sync messages with INBOX label (skip sent, drafts, spam)
            stub_labels = message_stub.get("labelIds", [])
            if "INBOX" not in stub_labels:
                continue
            msg = await get_message_headers(creds, message_id)
            email_id = await upsert_email(
                db, integration.tenant_id, integration.user_id, msg
            )
            new_email_ids.append(email_id)
            count += 1
            logger.debug(
                "incremental sync: upserted message_id=%s for integration %s",
                message_id,
                integration.id,
            )

        # --- Handle label removals (archive, trash, delete remove INBOX label) ---
        for removed_entry in record.get("labelsRemoved", []):
            removed_labels = removed_entry.get("labelIds", [])
            if "INBOX" not in removed_labels:
                continue
            message_stub = removed_entry.get("message", {})
            message_id = message_stub.get("id")
            if not message_id:
                continue
            # Delete the email row (cascade will remove scores/drafts via FK)
            result = await db.execute(
                select(Email.id).where(
                    Email.tenant_id == integration.tenant_id,
                    Email.gmail_message_id == message_id,
                )
            )
            email_row_id = result.scalar_one_or_none()
            if email_row_id:
                # Delete child rows first (no FK cascade on email_id)
                await db.execute(
                    EmailDraft.__table__.delete().where(EmailDraft.email_id == email_row_id)
                )
                await db.execute(
                    EmailScore.__table__.delete().where(EmailScore.email_id == email_row_id)
                )
                await db.execute(
                    Email.__table__.delete().where(Email.id == email_row_id)
                )
                logger.debug(
                    "incremental sync: removed message_id=%s (INBOX label removed) for integration %s",
                    message_id,
                    integration.id,
                )

    # Advance historyId checkpoint
    new_history_id = response.get("historyId")
    if new_history_id:
        settings = dict(integration.settings or {})
        settings["history_id"] = new_history_id
        integration.settings = settings

    integration.last_synced_at = datetime.now(timezone.utc)
    await db.commit()

    if count > 0:
        logger.info(
            "Incremental sync complete for integration %s: %d messages",
            integration.id,
            count,
        )

    # Score new emails AFTER commit — scoring failure cannot lose synced emails
    if new_email_ids:
        try:
            scored = await _score_new_emails(db, integration.tenant_id, new_email_ids)
            logger.info(
                "Scored %d new emails for integration %s", scored, integration.id
            )
        except Exception:
            logger.exception(
                "Scoring failed for integration %s", integration.id
            )
            # Non-fatal — sync is already committed, scoring failure doesn't lose emails

        # Draft important emails AFTER scoring — draft failure cannot lose synced/scored emails
        try:
            drafted = await _draft_important_emails(
                db, integration.tenant_id, integration, new_email_ids
            )
            logger.info("Drafted %d emails for integration %s", drafted, integration.id)
        except Exception:
            logger.exception("Drafting failed for integration %s", integration.id)
            # Non-fatal — sync and scoring already committed

    return count


# ---------------------------------------------------------------------------
# Per-integration wrapper
# ---------------------------------------------------------------------------


async def _sync_one_integration(factory, integration: Integration) -> int:
    """Open a tenant session and run sync_gmail for a single integration.

    Catches TokenRevokedException and marks integration disconnected.
    All other exceptions are propagated to the caller (email_sync_loop).

    Args:
        factory: async_sessionmaker from get_session_factory().
        integration: Integration row read in superuser context (may be detached).

    Returns:
        Number of emails processed.
    """
    async with tenant_session(
        factory,
        str(integration.tenant_id),
        str(integration.user_id),
    ) as db:
        # Re-load the integration inside the tenant session — the outer
        # superuser session's object is detached in a different transaction.
        result = await db.execute(
            select(Integration).where(Integration.id == integration.id)
        )
        intg = result.scalar_one()

        try:
            count = await sync_gmail(db, intg)
        except TokenRevokedException:
            logger.warning(
                "Token revoked for integration %s, marking disconnected",
                integration.id,
            )
            intg.status = "disconnected"
            intg.credentials_encrypted = None
            await db.commit()
            return 0

        # Check if voice profile needs initialization (runs once per user)
        existing_profile = await db.execute(
            select(EmailVoiceProfile).where(
                and_(
                    EmailVoiceProfile.tenant_id == intg.tenant_id,
                    EmailVoiceProfile.user_id == intg.user_id,
                )
            )
        )
        if existing_profile.scalar_one_or_none() is None:
            try:
                created = await voice_profile_init(db, intg)
                if created:
                    logger.info(
                        "Voice profile initialized for integration %s", intg.id
                    )
            except Exception:
                logger.exception(
                    "Voice profile init failed for integration %s", intg.id
                )
                # Non-fatal — sync continues even if voice init fails

        return count


# ---------------------------------------------------------------------------
# Voice profile extraction
# ---------------------------------------------------------------------------

VOICE_SYSTEM_PROMPT = """\
You are analyzing email samples to extract a user's writing voice profile.
Return a JSON object with exactly these fields:
- tone: string (e.g., "professional and concise", "warm and conversational")
- avg_length: integer (estimated average email length in words)
- sign_off: string (most common sign-off phrase, e.g., "Best," or "Thanks,")
- phrases: array of strings (3-5 characteristic phrases or expressions the person uses)
- samples_analyzed: integer (number of emails you analyzed)

Return only the JSON object, no other text.\
"""

# Auto-reply / calendar / OOO patterns (case-insensitive match against body)
_AUTO_REPLY_PATTERNS = [
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
    "i'm ooo",
    "i will be out",
]


def _is_substantive(body: str | None) -> bool:
    """Return True only if the body is a real, substantive human-written email.

    Filters out: None, empty strings, very short messages, auto-replies, OOO
    messages, calendar acceptances/declines, and emails with fewer than 3 real
    sentences.

    Args:
        body: Raw email body text.

    Returns:
        True if the email should be included in voice extraction samples.
    """
    if not body or len(body.strip()) < 50:
        return False

    lower = body.lower()
    for pattern in _AUTO_REPLY_PATTERNS:
        if pattern in lower:
            return False

    sentences = re.split(r"[.!?]\s+", body.strip())
    real_sentences = [s for s in sentences if len(s.strip()) > 10]
    return len(real_sentences) >= 3


async def _extract_voice_profile(bodies: list[str], model: str = "claude-sonnet-4-6") -> dict:
    """Call the voice extraction model to extract a voice profile from email bodies.

    Uses the same AsyncAnthropic + json.loads + regex-fallback pattern as
    onboarding_streams.py.

    Args:
        bodies: List of substantive email body strings to analyze.
        model: Claude model identifier (resolved by caller via get_engine_model).

    Returns:
        Parsed dict with keys: tone, avg_length, sign_off, phrases,
        samples_analyzed.

    Raises:
        json.JSONDecodeError: If the LLM response cannot be parsed as JSON.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=1000,
        system=VOICE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n\n---\n\n".join(bodies)}],
    )

    text = response.content[0].text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


async def voice_profile_init(db: AsyncSession, integration: Integration) -> bool:
    """Extract the user's writing voice from substantive sent emails.

    Idempotent: returns False immediately if an EmailVoiceProfile already exists
    for this (tenant_id, user_id) pair. Skips if fewer than 3 substantive bodies
    are found — not enough signal for a meaningful profile.

    Sends at most 20 bodies to the LLM (cost control). Up to 100 substantive
    bodies are collected from the most recent 200 sent messages.

    Args:
        db: Tenant-scoped async session (RLS enforced).
        integration: gmail-read Integration row for the user.

    Returns:
        True if a new voice profile was created, False otherwise.
    """
    # Idempotency guard — bail out early if profile already exists
    existing = await db.execute(
        select(EmailVoiceProfile).where(
            and_(
                EmailVoiceProfile.tenant_id == integration.tenant_id,
                EmailVoiceProfile.user_id == integration.user_id,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False

    creds = await get_valid_credentials(integration)

    # Fetch up to 200 sent message stubs
    response = await list_sent_messages(creds, max_results=200)
    stubs = response.get("messages", [])

    # Collect up to 100 substantive bodies
    substantive_bodies: list[str] = []
    for stub in stubs:
        if len(substantive_bodies) >= 100:
            break
        body = await get_message_body(creds, stub["id"])
        if _is_substantive(body):
            substantive_bodies.append(body)

    if len(substantive_bodies) < 3:
        logger.warning(
            "voice_profile_init: not enough substantive emails for integration %s "
            "(found %d, need at least 3)",
            integration.id,
            len(substantive_bodies),
        )
        return False

    # Resolve voice extraction model for this tenant
    model = await get_engine_model(db, integration.tenant_id, "voice_extraction")

    # Send only the 20 most recent bodies to control token cost
    profile_data = await _extract_voice_profile(substantive_bodies[:20], model=model)

    samples_count = profile_data.get("samples_analyzed", len(substantive_bodies[:20]))

    stmt = (
        pg_insert(EmailVoiceProfile)
        .values(
            tenant_id=integration.tenant_id,
            user_id=integration.user_id,
            tone=profile_data.get("tone"),
            avg_length=profile_data.get("avg_length"),
            sign_off=profile_data.get("sign_off"),
            phrases=profile_data.get("phrases", []),
            samples_analyzed=samples_count,
        )
        .on_conflict_do_update(
            constraint="uq_voice_profile_tenant_user",
            set_={
                "tone": profile_data.get("tone"),
                "avg_length": profile_data.get("avg_length"),
                "sign_off": profile_data.get("sign_off"),
                "phrases": profile_data.get("phrases", []),
                "samples_analyzed": samples_count,
                "updated_at": datetime.now(timezone.utc),
            },
        )
    )
    await db.execute(stmt)
    await db.commit()

    logger.info(
        "Voice profile created for integration %s (%d samples analyzed)",
        integration.id,
        samples_count,
    )
    return True


# ---------------------------------------------------------------------------
# Background sync loop
# ---------------------------------------------------------------------------


async def email_sync_loop() -> None:
    """Infinite background loop: polls all connected gmail-read integrations.

    Runs every SYNC_INTERVAL seconds (5 minutes). Each integration is wrapped
    in asyncio.wait_for with PER_INTEGRATION_TIMEOUT and all integrations are
    processed concurrently via asyncio.gather(return_exceptions=True).

    Never crashes — outer try/except swallows iteration errors and logs them.
    """
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
                integrations = [
                    i for i in result.scalars().all()
                    if i.credentials_encrypted is not None
                ]

            if not integrations:
                await asyncio.sleep(SYNC_INTERVAL)
                continue

            logger.info(
                "email_sync_loop: syncing %d gmail-read integration(s)",
                len(integrations),
            )

            tasks = [
                asyncio.wait_for(
                    _sync_one_integration(factory, intg),
                    timeout=PER_INTEGRATION_TIMEOUT,
                )
                for intg in integrations
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for intg, outcome in zip(integrations, results):
                if isinstance(outcome, asyncio.TimeoutError):
                    logger.warning(
                        "email_sync_loop: integration %s timed out after %.0fs",
                        intg.id,
                        PER_INTEGRATION_TIMEOUT,
                    )
                elif isinstance(outcome, Exception):
                    logger.exception(
                        "email_sync_loop: error syncing integration %s",
                        intg.id,
                        exc_info=outcome,
                    )
                else:
                    if outcome > 0:
                        logger.info(
                            "email_sync_loop: integration %s synced %d message(s)",
                            intg.id,
                            outcome,
                        )

        except Exception:
            logger.exception("email_sync_loop: unhandled error in iteration")

        await asyncio.sleep(SYNC_INTERVAL)
