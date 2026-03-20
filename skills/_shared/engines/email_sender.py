"""
email_sender.py - Resend API email sender with Slack draft review.

Provides email sending via Resend API with a Slack-based draft review
approval flow (Send/Edit/Cancel buttons), sent email tracking for reply
detection integration with watcher_email, and JSONL send logging for
bounce/error tracking.

Public API:
    send_email(to, subject, body_html, from_email) -> dict
    get_email_status(email_id) -> dict
    format_draft_blocks(to, subject, body, draft_id) -> list
    create_draft(user_id, to, subject, body) -> str
    approve_draft(draft_id) -> dict
    cancel_draft(draft_id) -> None
    log_send(user_id, to, subject, status, error) -> None
    get_send_history(user_id, limit) -> list
    PENDING_DRAFTS - In-memory dict of pending email drafts
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Resend SDK -- graceful fallback if not installed
try:
    import resend
except ImportError:
    resend = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "noreply@example.com")

SEND_LOG = Path.home() / ".flywheel" / "watcher-state" / "email-send-log.jsonl"

# ---------------------------------------------------------------------------
# 1. Resend API wrapper
# ---------------------------------------------------------------------------


def send_email(to: str, subject: str, body_html: str, from_email: str = None) -> dict:
    """Send an email via the Resend API.

    Returns result dict with id, from, to, subject on success.
    Returns error dict with 'error' key on failure.
    """
    if resend is None:
        return {"error": "resend package not installed. Run: pip install resend"}

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return {"error": "RESEND_API_KEY not set"}

    resend.api_key = api_key
    sender = from_email or os.environ.get("RESEND_FROM_EMAIL", RESEND_FROM_EMAIL)

    try:
        result = resend.Emails.send({
            "from": sender,
            "to": [to],
            "subject": subject,
            "html": body_html,
        })
        return result
    except Exception as e:
        logger.error("Resend send failed: %s", e)
        return {"error": str(e)}


def get_email_status(email_id: str) -> dict:
    """Check delivery status for a sent email.

    Returns status dict or error dict.
    """
    if resend is None:
        return {"error": "resend package not installed"}

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return {"error": "RESEND_API_KEY not set"}

    resend.api_key = api_key

    try:
        result = resend.Emails.get(email_id)
        return result
    except Exception as e:
        logger.error("Resend get status failed: %s", e)
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 2. Draft review flow
# ---------------------------------------------------------------------------

# In-memory store for pending email drafts
PENDING_DRAFTS: dict = {}


def format_draft_blocks(to: str, subject: str, body: str, draft_id: str) -> list:
    """Create Slack Block Kit blocks for email draft preview.

    Shows the draft email content with Send/Edit/Cancel action buttons.
    Action IDs use the draft_id for routing: email_approve_{draft_id}, etc.
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Email Draft for Review",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*To:* {to}\n*Subject:* {subject}",
            },
        },
        {
            "type": "divider",
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": body[:3000],  # Slack block size limit
            },
        },
        {
            "type": "divider",
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Send"},
                    "action_id": f"email_approve_{draft_id}",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Edit"},
                    "action_id": f"email_edit_{draft_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "action_id": f"email_cancel_{draft_id}",
                    "style": "danger",
                },
            ],
        },
    ]
    return blocks


def create_draft(user_id: str, to: str, subject: str, body: str) -> str:
    """Store a draft email for approval. Returns the draft_id (uuid4)."""
    draft_id = str(uuid.uuid4())
    PENDING_DRAFTS[draft_id] = {
        "to": to,
        "subject": subject,
        "body": body,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return draft_id


def approve_draft(draft_id: str) -> dict:
    """Approve and send a pending draft email.

    Sends via Resend API, tracks via watcher_email if available,
    logs the send attempt, and removes from PENDING_DRAFTS.

    Raises KeyError if draft_id not found.
    Returns send result dict.
    """
    if draft_id not in PENDING_DRAFTS:
        raise KeyError(f"Draft not found: {draft_id}")

    draft = PENDING_DRAFTS[draft_id]
    result = send_email(
        to=draft["to"],
        subject=draft["subject"],
        body_html=draft["body"],
    )

    # Track sent email for reply detection (lazy import -- watcher_email may not exist yet)
    if "error" not in result:
        try:
            _track_sent(draft["user_id"], result, draft)
        except Exception as e:
            logger.warning("Tracking sent email failed (non-fatal): %s", e)
        log_send(draft["user_id"], draft["to"], draft["subject"], "sent")
    else:
        log_send(draft["user_id"], draft["to"], draft["subject"], "failed",
                 error=result.get("error"))

    # Remove from pending regardless of send outcome
    del PENDING_DRAFTS[draft_id]
    return result


def cancel_draft(draft_id: str) -> None:
    """Cancel a pending draft, removing it from PENDING_DRAFTS.

    Raises KeyError if draft_id not found.
    """
    if draft_id not in PENDING_DRAFTS:
        raise KeyError(f"Draft not found: {draft_id}")
    del PENDING_DRAFTS[draft_id]


# ---------------------------------------------------------------------------
# 3. Sent email tracking integration
# ---------------------------------------------------------------------------


def _track_sent(user_id: str, send_result: dict, draft: dict) -> None:
    """Track a sent email for reply detection via watcher_email.

    Uses lazy import since watcher_email.py may not exist yet (same wave).
    Graceful degradation: logs info and continues if unavailable.
    """
    try:
        from watcher_email import track_sent_email
        message_id = send_result.get("id", "")
        track_sent_email(user_id, message_id, draft["to"], draft["subject"])
        logger.info("Tracked sent email %s for reply detection", message_id)
    except ImportError:
        logger.info("watcher_email not available -- skipping reply tracking")
    except Exception as e:
        logger.warning("Failed to track sent email: %s", e)


# ---------------------------------------------------------------------------
# 4. Bounce/error handling -- JSONL send log
# ---------------------------------------------------------------------------


def log_send(user_id: str, to: str, subject: str, status: str,
             error: str = None) -> None:
    """Append a send attempt to the JSONL send log.

    Args:
        user_id: Slack user who initiated the send
        to: Recipient email address
        subject: Email subject line
        status: One of 'sent', 'failed', 'bounced'
        error: Error message if status is 'failed' or 'bounced'
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "to": to,
        "subject": subject,
        "status": status,
    }
    if error:
        entry["error"] = error

    try:
        SEND_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(SEND_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except IOError as e:
        logger.warning("Failed to write send log: %s", e)


def get_send_history(user_id: str, limit: int = 20) -> list:
    """Return recent send entries for a user, newest first.

    Args:
        user_id: Filter sends by this user
        limit: Maximum entries to return (default 20)

    Returns:
        List of send log dicts, newest first
    """
    if not SEND_LOG.exists():
        return []

    entries = []
    try:
        with open(SEND_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("user_id") == user_id:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except IOError as e:
        logger.warning("Failed to read send log: %s", e)
        return []

    # Return newest first, limited
    return entries[-limit:][::-1]
