"""
watcher_email.py - Email reply detection watcher for Flywheel.

Polls Gmail API for replies to tracked outreach emails and updates
effectiveness data in the context store. Uses historyId-based incremental
fetch to avoid reprocessing.

Public API:
    EmailWatcher - WatcherBase subclass for Gmail reply detection
    connect_email(user_id) -> bool - OAuth flow for Gmail
    get_gmail_service(user_id) - Build Gmail API service
    track_sent_email(user_id, message_id, to, subject) -> None
    get_tracked_emails(user_id) -> list[dict]
    match_reply(message_headers, tracked_emails) -> Optional[dict]
    record_reply(user_id, matched_email, reply_snippet) -> None
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# Import from src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import context_utils
from integration_framework import WatcherBase
from oauth_store import save_credentials, load_credentials

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Sent email tracking log path template
_SENT_LOG_DIR = Path.home() / ".flywheel" / "watcher-state"

# Polling interval in minutes
POLL_INTERVAL_MINUTES = 30


# ---------------------------------------------------------------------------
# 1. OAuth for Gmail
# ---------------------------------------------------------------------------


def connect_email(user_id: str) -> bool:
    """Run OAuth InstalledAppFlow for Gmail scope, save credentials.

    Reuses client_secret.json from calendar setup (same Google Cloud project).

    Args:
        user_id: User identifier.

    Returns:
        True if credentials were saved successfully, False on error.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        # Look for client_secret.json in standard locations
        client_secret_paths = [
            Path.home() / ".flywheel" / "oauth" / "client_secret.json",
            Path.home() / ".flywheel" / "client_secret.json",  # legacy fallback
            Path("client_secret.json"),
        ]

        client_secret = None
        for p in client_secret_paths:
            if p.exists():
                client_secret = p
                break

        if client_secret is None:
            logger.error("client_secret.json not found. Download from Google Cloud Console.")
            return False

        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret), scopes=GMAIL_SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Save credentials via oauth_store
        creds_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else GMAIL_SCOPES,
        }
        save_credentials(user_id, "gmail", creds_data)
        logger.info("Gmail credentials saved for user %s", user_id)
        return True

    except ImportError:
        logger.error(
            "google-auth-oauthlib not installed. "
            "Install with: pip3 install google-auth-oauthlib google-api-python-client"
        )
        return False
    except Exception as e:
        logger.error("Gmail OAuth flow failed: %s", e)
        return False


def get_gmail_service(user_id: str):
    """Build Gmail API service from saved credentials.

    Handles token refresh automatically.

    Args:
        user_id: User identifier.

    Returns:
        Gmail API service object, or None if credentials unavailable.
    """
    creds_data = load_credentials(user_id, "gmail")
    if creds_data is None:
        logger.error("No Gmail credentials for user %s. Run connect_email() first.", user_id)
        return None

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=creds_data.get("token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_data.get("client_id"),
            client_secret=creds_data.get("client_secret"),
            scopes=creds_data.get("scopes", GMAIL_SCOPES),
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            # Save refreshed token
            creds_data["token"] = creds.token
            save_credentials(user_id, "gmail", creds_data)

        service = build("gmail", "v1", credentials=creds)
        return service

    except ImportError:
        logger.error(
            "Google API client not installed. "
            "Install with: pip3 install google-api-python-client google-auth"
        )
        return None
    except Exception as e:
        logger.error("Failed to build Gmail service for user %s: %s", user_id, e)
        return None


# ---------------------------------------------------------------------------
# 2. Sent email tracking
# ---------------------------------------------------------------------------


def _get_sent_log_path(user_id: str) -> Path:
    """Get path to user's sent email tracking log."""
    return _SENT_LOG_DIR / f"{user_id}-sent-emails.jsonl"


def track_sent_email(user_id: str, message_id: str, to: str, subject: str) -> None:
    """Track an outbound email for reply matching.

    Appends to the user's sent email JSONL log.

    Args:
        user_id: User identifier.
        message_id: Message-ID header value of the sent email.
        to: Recipient email address.
        subject: Email subject line.
    """
    log_path = _get_sent_log_path(user_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "message_id": message_id,
        "to": to.lower().strip(),
        "subject": subject,
        "send_date": datetime.now(timezone.utc).isoformat(),
    }

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info("Tracked sent email to %s: %s", to, subject)
    except IOError as e:
        logger.error("Failed to track sent email: %s", e)


def get_tracked_emails(user_id: str) -> list:
    """Read all tracked sent emails for a user.

    Args:
        user_id: User identifier.

    Returns:
        List of sent email dicts with message_id, to, subject, send_date.
    """
    log_path = _get_sent_log_path(user_id)
    if not log_path.exists():
        return []

    entries = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except IOError as e:
        logger.error("Failed to read sent email log for %s: %s", user_id, e)

    return entries


# ---------------------------------------------------------------------------
# 3. Reply matching
# ---------------------------------------------------------------------------


def _strip_reply_prefixes(subject: str) -> str:
    """Strip Re:/Fwd:/FW: prefixes from a subject line.

    Handles nested prefixes like "Re: Fwd: Re: Original Subject".

    Args:
        subject: Email subject string.

    Returns:
        Subject with all Re:/Fwd:/FW: prefixes stripped.
    """
    pattern = r"^(?:(?:Re|Fwd|FW)\s*:\s*)+(.*)$"
    match = re.match(pattern, subject, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return subject.strip()


def match_reply(message_headers: dict, tracked_emails: list) -> Optional[dict]:
    """Match an incoming message against tracked outbound emails.

    Primary: Match In-Reply-To header against tracked Message-IDs.
    Fallback: Match subject (stripped Re:/Fwd:) + sender against tracked recipients.

    Args:
        message_headers: Dict with keys like 'In-Reply-To', 'Subject', 'From'.
        tracked_emails: List of tracked sent email dicts.

    Returns:
        Matched sent email dict, or None if no match.
    """
    if not tracked_emails:
        return None

    # Primary: In-Reply-To header match
    in_reply_to = message_headers.get("In-Reply-To", "").strip()
    if in_reply_to:
        for tracked in tracked_emails:
            if tracked.get("message_id") == in_reply_to:
                return tracked

    # Fallback: subject + sender match
    raw_subject = message_headers.get("Subject", "")
    stripped_subject = _strip_reply_prefixes(raw_subject)

    from_header = message_headers.get("From", "")
    # Extract email from "Name <email>" format
    email_match = re.search(r"<([^>]+)>", from_header)
    sender_email = email_match.group(1).lower().strip() if email_match else from_header.lower().strip()

    if stripped_subject and sender_email:
        for tracked in tracked_emails:
            tracked_subject = _strip_reply_prefixes(tracked.get("subject", ""))
            tracked_to = tracked.get("to", "").lower().strip()
            if (
                stripped_subject.lower() == tracked_subject.lower()
                and sender_email == tracked_to
            ):
                return tracked

    return None


# ---------------------------------------------------------------------------
# 4. Effectiveness update
# ---------------------------------------------------------------------------


def record_reply(user_id: str, matched_email: dict, reply_snippet: str) -> None:
    """Write effectiveness entry to context store for a detected reply.

    Writes to _learning/gtm-learning.md with source=email-watcher.

    Args:
        user_id: User identifier.
        matched_email: The tracked sent email dict that was matched.
        reply_snippet: Short snippet or summary of the reply.
    """
    try:
        recipient = matched_email.get("to", "unknown")
        subject = matched_email.get("subject", "unknown")
        send_date_str = matched_email.get("send_date", "")

        # Calculate time-to-reply
        time_to_reply = "unknown"
        if send_date_str:
            try:
                send_date = datetime.fromisoformat(send_date_str)
                now = datetime.now(timezone.utc)
                delta = now - send_date
                days = delta.days
                hours = delta.seconds // 3600
                if days > 0:
                    time_to_reply = f"{days}d {hours}h"
                else:
                    time_to_reply = f"{hours}h"
            except (ValueError, TypeError):
                time_to_reply = "unknown"

        entry = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "email-watcher",
            "detail": f"reply-received: {recipient}",
            "confidence": "medium",
            "content": (
                f"- Reply received from {recipient}\n"
                f"- Original subject: {subject}\n"
                f"- Time to reply: {time_to_reply}\n"
                f"- Snippet: {reply_snippet[:200] if reply_snippet else 'N/A'}"
            ),
        }

        result = context_utils.append_entry(
            "_learning/gtm-learning.md",
            entry,
            source="email-watcher",
            agent_id="email-watcher",
        )
        logger.info("Recorded reply effectiveness for %s: %s", recipient, result)

    except Exception as e:
        # Best-effort: do not block on write failure
        logger.error("Failed to record reply effectiveness: %s", e)


# ---------------------------------------------------------------------------
# 5. EmailWatcher (WatcherBase subclass)
# ---------------------------------------------------------------------------


def _extract_headers(message_data: dict) -> dict:
    """Extract relevant headers from a Gmail message payload.

    Args:
        message_data: Full Gmail message resource dict.

    Returns:
        Dict with header names as keys (In-Reply-To, Subject, From, Date).
    """
    headers = {}
    payload = message_data.get("payload", {})
    for header in payload.get("headers", []):
        name = header.get("name", "")
        if name in ("In-Reply-To", "Subject", "From", "Date", "Message-ID"):
            headers[name] = header.get("value", "")
    return headers


class EmailWatcher(WatcherBase):
    """Gmail reply detection watcher.

    Polls Gmail API for new inbox messages using historyId-based
    incremental fetch. Matches incoming messages against tracked
    outbound emails and records reply effectiveness in context store.

    Polling interval: 30 minutes.
    Does NOT use Gmail push notifications (requires Pub/Sub).
    """

    def __init__(self, user_id: str):
        super().__init__(name="email", user_id=user_id)

    def check(self) -> list:
        """Poll Gmail for new inbox messages.

        First run: uses `after:YYYY/MM/DD` (7 days ago).
        Subsequent runs: uses historyId-based incremental fetch.

        Returns:
            List of message dicts with 'id' and 'threadId' keys.
        """
        service = get_gmail_service(self.user_id)
        if service is None:
            logger.warning("Gmail service unavailable for user %s", self.user_id)
            return []

        try:
            last_history_id = self.state.get("last_history_id")

            if last_history_id:
                # Incremental fetch using historyId
                try:
                    response = (
                        service.users()
                        .history()
                        .list(
                            userId="me",
                            startHistoryId=last_history_id,
                            historyTypes=["messageAdded"],
                            labelId="INBOX",
                        )
                        .execute()
                    )

                    # Update historyId for next poll
                    new_history_id = response.get("historyId")
                    if new_history_id:
                        self.state["last_history_id"] = new_history_id
                        self._save_state()

                    # Extract messages from history records
                    messages = []
                    for record in response.get("history", []):
                        for msg_added in record.get("messagesAdded", []):
                            msg = msg_added.get("message", {})
                            if msg.get("id"):
                                messages.append({"id": msg["id"], "threadId": msg.get("threadId", "")})

                    return messages

                except Exception as e:
                    # If historyId is invalid (expired), fall back to list
                    logger.warning("History fetch failed, falling back to list: %s", e)

            # First run or fallback: list recent inbox messages
            seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y/%m/%d")
            response = (
                service.users()
                .messages()
                .list(userId="me", q=f"is:inbox after:{seven_days_ago}", maxResults=50)
                .execute()
            )

            messages = response.get("messages", [])

            # Get current historyId from profile for future incremental fetches
            try:
                profile = service.users().getProfile(userId="me").execute()
                self.state["last_history_id"] = profile.get("historyId")
                self._save_state()
            except Exception as e:
                logger.warning("Failed to get profile historyId: %s", e)

            return messages

        except Exception as e:
            logger.error("Gmail check failed for user %s: %s", self.user_id, e)
            return []

    def process(self, item) -> dict:
        """Process a single Gmail message -- check if it's a reply to tracked email.

        Args:
            item: Message dict with 'id' key from check().

        Returns:
            Result dict with 'status' key ('reply_matched', 'no_match', or 'error').
        """
        message_id = item.get("id") if isinstance(item, dict) else str(item)

        service = get_gmail_service(self.user_id)
        if service is None:
            return {"status": "error", "reason": "Gmail service unavailable"}

        try:
            # Fetch full message
            message_data = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            # Extract headers
            headers = _extract_headers(message_data)

            # Match against tracked emails
            tracked = get_tracked_emails(self.user_id)
            matched = match_reply(headers, tracked)

            if matched:
                # Get reply snippet
                snippet = message_data.get("snippet", "")
                record_reply(self.user_id, matched, snippet)
                return {
                    "status": "reply_matched",
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", ""),
                    "matched_to": matched.get("to", ""),
                }
            else:
                return {"status": "no_match"}

        except Exception as e:
            logger.error("Failed to process message %s: %s", message_id, e)
            return {"status": "error", "reason": str(e)}
