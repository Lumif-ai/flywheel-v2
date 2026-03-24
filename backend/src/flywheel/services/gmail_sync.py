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
import logging
from datetime import datetime, timezone
from uuid import UUID

from googleapiclient.errors import HttpError
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import Email, Integration
from flywheel.db.session import get_session_factory, tenant_session
from flywheel.services.gmail_read import (
    TokenRevokedException,
    get_history,
    get_message_headers,
    get_profile,
    get_valid_credentials,
    list_message_headers,
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
) -> None:
    """Upsert a single email row from a Gmail message metadata dict.

    Extracts header fields, builds an Email row, and issues a PostgreSQL
    INSERT ... ON CONFLICT DO UPDATE so re-syncing is safe.

    Does NOT commit — caller commits after processing the full batch.

    Args:
        db: Active SQLAlchemy async session.
        tenant_id: UUID of the tenant owning this message.
        user_id: UUID of the user whose gmail-read integration produced this.
        msg: Gmail API message dict (metadata format — no body).
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
    )
    await db.execute(stmt)

    logger.debug(
        "upserted email message_id=%s thread_id=%s",
        msg["id"],
        msg["threadId"],
    )


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
            msg = await get_message_headers(creds, stub["id"])
            await upsert_email(db, integration.tenant_id, integration.user_id, msg)
            count += 1

        page_token = response.get("nextPageToken")
        if not page_token:
            break

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

    for record in history_records:
        for added_entry in record.get("messagesAdded", []):
            message_stub = added_entry.get("message", {})
            message_id = message_stub.get("id")
            if not message_id:
                continue
            msg = await get_message_headers(creds, message_id)
            await upsert_email(db, integration.tenant_id, integration.user_id, msg)
            count += 1
            logger.debug(
                "incremental sync: upserted message_id=%s for integration %s",
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
            return await sync_gmail(db, intg)
        except TokenRevokedException:
            logger.warning(
                "Token revoked for integration %s, marking disconnected",
                integration.id,
            )
            intg.status = "disconnected"
            intg.credentials_encrypted = None
            await db.commit()
            return 0


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
                integrations = result.scalars().all()

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
