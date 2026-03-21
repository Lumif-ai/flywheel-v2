"""Slack Events API verification, deduplication, and background processing.

Handles:
- HMAC-SHA256 signing secret verification per Slack docs
- Event deduplication with bounded in-memory OrderedDict
- Event routing: messages -> channel monitor, commands -> slash command handler
- Bot message filtering (prevents self-loops)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from collections import OrderedDict

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signing secret verification
# ---------------------------------------------------------------------------


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> None:
    """Verify a Slack request's signing secret via HMAC-SHA256.

    Per Slack docs: compute HMAC of "v0:{timestamp}:{body}" using the
    signing secret, then compare with the provided signature using
    timing-safe comparison.

    Args:
        signing_secret: App's signing secret from Slack dashboard.
        timestamp: Value of X-Slack-Request-Timestamp header.
        body: Raw request body bytes.
        signature: Value of X-Slack-Signature header (v0=...).

    Raises:
        HTTPException(403): If signature is invalid or timestamp is stale.
    """
    # Reject requests older than 5 minutes (replay prevention)
    try:
        request_time = int(timestamp)
    except (ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Invalid timestamp")

    if abs(time.time() - request_time) > 300:
        raise HTTPException(status_code=403, detail="Request timestamp too old")

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    computed = (
        "v0="
        + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )

    # Timing-safe comparison
    if not hmac.compare_digest(computed, signature):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")


# ---------------------------------------------------------------------------
# Event deduplication (in-memory, bounded OrderedDict)
# ---------------------------------------------------------------------------

# Slack may retry event delivery up to 3 times. We track seen event IDs
# in memory to ignore duplicates. Bounded at 10K entries to prevent
# unbounded growth. On restart, we may re-process a few events -- this is
# acceptable per the research recommendation.

_seen_events: OrderedDict[str, bool] = OrderedDict()
MAX_SEEN = 10000


def is_duplicate_event(event_id: str) -> bool:
    """Check if an event has already been seen.

    If not seen, records it. Evicts oldest entries when over MAX_SEEN.

    Args:
        event_id: Slack event_id from the Events API payload.

    Returns:
        True if this event_id was already seen (duplicate).
    """
    if event_id in _seen_events:
        return True

    _seen_events[event_id] = True

    # Evict oldest entries if over limit
    while len(_seen_events) > MAX_SEEN:
        _seen_events.popitem(last=False)

    return False


# ---------------------------------------------------------------------------
# Event and command processors (wired to handlers in Plan 03)
# ---------------------------------------------------------------------------


async def process_slack_event(payload: dict, db: AsyncSession) -> None:
    """Process an incoming Slack event in the background.

    Routes events by type:
    - message (non-bot): -> channel monitor for keyword intelligence
    - app_mention: logged (future: respond to mentions)
    - other: logged at debug level

    Bot messages are filtered to prevent self-loops.
    """
    event = payload.get("event", {})
    event_type = event.get("type", "unknown")
    team_id = payload.get("team_id", "unknown")

    logger.info("Slack event received: type=%s team=%s", event_type, team_id)

    if event_type == "message":
        # Filter bot messages to prevent self-loops
        if event.get("bot_id") is not None:
            logger.debug("Ignoring bot message from bot_id=%s", event.get("bot_id"))
            return

        # Also filter message subtypes that aren't real user messages
        subtype = event.get("subtype")
        if subtype is not None:
            logger.debug("Ignoring message subtype=%s", subtype)
            return

        # Route to channel monitor -- inject team_id into event for tenant resolution
        event_with_team = {**event, "team_id": team_id}

        from flywheel.services.slack_channel_monitor import process_channel_message

        await process_channel_message(event_with_team, db)

    elif event_type == "app_mention":
        logger.info("App mention from user=%s in channel=%s", event.get("user"), event.get("channel"))
        # Future: respond to @mentions

    else:
        logger.debug("Unhandled Slack event type: %s", event_type)


async def process_slack_command(payload: dict, db: AsyncSession) -> dict:
    """Process an incoming Slack slash command.

    Delegates to the slash command handler which routes subcommands
    to skills, help, or skills listing.

    Returns:
        Slack-compatible response dict.
    """
    from flywheel.services.slack_commands import handle_slash_command

    return await handle_slash_command(payload, db)
