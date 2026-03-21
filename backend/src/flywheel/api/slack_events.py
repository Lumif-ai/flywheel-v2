"""Slack webhook endpoints for Events API and slash commands.

These endpoints are called by Slack's servers (not authenticated users),
so they use signing secret verification instead of tenant auth.

Endpoints:
- POST /integrations/slack/events   -- Events API webhook (URL verification, events)
- POST /integrations/slack/commands -- Slash command receiver (form-encoded)
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db
from flywheel.config import settings
from flywheel.services.slack_events import (
    is_duplicate_event,
    process_slack_command,
    process_slack_event,
    verify_slack_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/slack", tags=["slack"])


# ---------------------------------------------------------------------------
# POST /integrations/slack/events
# ---------------------------------------------------------------------------


@router.post("/events")
async def slack_events_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Slack Events API webhook endpoint.

    Handles:
    1. Signing secret verification (HMAC-SHA256)
    2. URL verification challenge (required during app setup)
    3. Event deduplication by event_id
    4. Background event processing (ACK within 3 seconds)

    This endpoint does NOT use require_tenant auth -- authentication
    is via Slack signing secret verification.
    """
    # Read raw body for signature verification
    body = await request.body()

    # Extract signing headers
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Verify signing secret (raises 403 on failure)
    verify_slack_signature(settings.slack_signing_secret, timestamp, body, signature)

    # Parse payload
    payload = json.loads(body)

    # URL verification challenge (required during Slack app setup)
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    # Event deduplication
    event_id = payload.get("event_id")
    if event_id and is_duplicate_event(event_id):
        return {"ok": True, "duplicate": True}

    # Queue for background processing and ACK immediately (3-second requirement)
    # We need a DB session for background processing -- get it lazily
    from flywheel.db.engine import async_session_factory

    async def _process_event():
        async with async_session_factory() as db:
            await process_slack_event(payload, db)

    background_tasks.add_task(_process_event)

    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /integrations/slack/commands
# ---------------------------------------------------------------------------


@router.post("/commands")
async def slack_commands_webhook(
    request: Request,
):
    """Slack slash command receiver.

    Slack sends slash commands as form-encoded POST (not JSON).
    Must respond within 3 seconds. For longer operations, use
    response_url to post results asynchronously (Plan 03).

    This endpoint does NOT use require_tenant auth -- authentication
    is via Slack signing secret verification.
    """
    # Read raw body for signature verification
    body = await request.body()

    # Extract signing headers
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Verify signing secret (raises 403 on failure)
    verify_slack_signature(settings.slack_signing_secret, timestamp, body, signature)

    # Parse form-encoded data
    form = await request.form()
    command_payload = {
        "command": form.get("command"),
        "text": form.get("text"),
        "team_id": form.get("team_id"),
        "user_id": form.get("user_id"),
        "response_url": form.get("response_url"),
        "trigger_id": form.get("trigger_id"),
        "channel_id": form.get("channel_id"),
    }

    # Process command (placeholder returns acknowledgment in Plan 03)
    from flywheel.db.engine import async_session_factory

    async with async_session_factory() as db:
        result = await process_slack_command(command_payload, db)

    return result
