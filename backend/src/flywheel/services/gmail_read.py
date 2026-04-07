"""Gmail READ service — OAuth2 + inbox/sent message operations.

This is the Gmail READ service, architecturally separate from the send-only
service in google_gmail.py. Key distinctions:

- This service uses provider="gmail-read" Integration rows exclusively.
- It MUST NEVER query or modify provider="gmail" Integration rows.
- Scopes include gmail.readonly, gmail.modify, and gmail.send so that the
  same credential handles both triage (Phase 2-3) and draft approval (Phase 4).
- include_granted_scopes is NOT used so credentials stay isolated from
  the send-only gmail grant.

Architecture note: gmail.py (send-only) and gmail_read.py (read+send) are
SEPARATE OAuth grants, SEPARATE Integration rows, SEPARATE credentials.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from flywheel.auth.encryption import decrypt_api_key, encrypt_api_key
from flywheel.config import settings

logger = logging.getLogger(__name__)

# Three scopes: readonly + modify for triage/sync, send for draft approval (Phase 4)
# Do NOT add include_granted_scopes — must stay isolated from the send-only grant.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


class TokenRevokedException(Exception):
    """Raised when a Gmail Read refresh token has been revoked by the user."""

    pass


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


def _create_oauth_flow() -> Flow:
    """Create an OAuth2 flow using the gmail-read redirect URI.

    Uses settings.google_gmail_read_redirect_uri (NOT google_gmail_redirect_uri)
    to keep this grant's callback separate from the send-only grant.
    """
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_gmail_read_redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_gmail_read_redirect_uri,
    )


def generate_gmail_read_auth_url(state: str) -> tuple[str, str | None]:
    """Generate the Google OAuth authorization URL for Gmail Read.

    Args:
        state: Cryptographic state parameter for CSRF protection.

    Returns:
        Tuple of (authorization URL, code_verifier for PKCE).

    Note:
        include_granted_scopes is intentionally NOT passed here. Per research
        decision DATA-01, the gmail-read grant must stay isolated from the
        send-only gmail grant to prevent scope merging.
    """
    flow = _create_oauth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    return auth_url, flow.code_verifier


def exchange_gmail_read_code(code: str, code_verifier: str | None = None) -> Credentials:
    """Exchange an authorization code for Gmail Read OAuth credentials.

    Args:
        code: Authorization code from the OAuth callback.
        code_verifier: PKCE code verifier from the authorize step.

    Returns:
        Google OAuth2 Credentials with refresh token.

    Raises:
        ValueError: If no refresh token was returned.
    """
    flow = _create_oauth_flow()
    flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    creds = flow.credentials
    if creds.refresh_token is None:
        raise ValueError(
            "No refresh token returned. Ensure access_type='offline' "
            "and prompt='consent' are set."
        )
    return creds


# ---------------------------------------------------------------------------
# Credential serialization (AES-256-GCM via encryption.py)
# ---------------------------------------------------------------------------


def serialize_credentials(creds: Credentials) -> bytes:
    """Encrypt Gmail Read OAuth credentials for database storage.

    Returns:
        Encrypted bytes suitable for LargeBinary column.
    """
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }
    json_str = json.dumps(data)
    return encrypt_api_key(json_str)


def deserialize_credentials(encrypted: bytes) -> Credentials:
    """Decrypt and reconstruct Gmail Read OAuth credentials from database storage."""
    json_str = decrypt_api_key(encrypted)
    data = json.loads(json_str)

    expiry = None
    if data.get("expiry"):
        expiry = datetime.fromisoformat(data["expiry"])
        # Google's Credentials.valid compares expiry against a naive UTC datetime,
        # so strip timezone info to avoid comparison errors.
        if expiry.tzinfo is not None:
            expiry = expiry.replace(tzinfo=None)

    return Credentials(
        token=data["token"],
        refresh_token=data["refresh_token"],
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        expiry=expiry,
    )


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


async def get_valid_credentials(integration) -> Credentials:
    """Get valid (non-expired) credentials for a gmail-read integration.

    Args:
        integration: Integration ORM object with provider="gmail-read"
                     and credentials_encrypted.

    Returns:
        Valid Google OAuth2 Credentials.

    Raises:
        TokenRevokedException: If the refresh token has been revoked.
    """
    creds = deserialize_credentials(integration.credentials_encrypted)

    if creds.valid:
        return creds

    try:
        await asyncio.to_thread(creds.refresh, GoogleAuthRequest())
    except RefreshError as exc:
        if "invalid_grant" in str(exc):
            raise TokenRevokedException(
                "Gmail Read access has been revoked. Please reconnect."
            ) from exc
        raise

    # Persist refreshed credentials back to the integration
    integration.credentials_encrypted = serialize_credentials(creds)

    return creds


# ---------------------------------------------------------------------------
# Gmail API — message operations
# ---------------------------------------------------------------------------


async def list_message_headers(
    creds: Credentials,
    page_token: str | None = None,
    label_ids: list[str] | None = None,
    max_results: int = 100,
) -> dict:
    """List inbox message stubs (id + threadId only — no content fetched).

    Args:
        creds: Valid Gmail OAuth2 credentials.
        page_token: Pagination token from a previous response.
        label_ids: Gmail label filters. Defaults to ["INBOX"].
        max_results: Maximum number of messages to return (1-500).

    Returns:
        Raw API response dict with keys: messages, nextPageToken,
        resultSizeEstimate.
    """
    def _list():
        service = build("gmail", "v1", credentials=creds)
        kwargs = {
            "userId": "me",
            "labelIds": label_ids or ["INBOX"],
            "maxResults": max_results,
        }
        if page_token:
            kwargs["pageToken"] = page_token
        result = service.users().messages().list(**kwargs).execute()
        logger.debug(
            "list_message_headers completed label_ids=%s max_results=%s",
            label_ids or ["INBOX"],
            max_results,
        )
        return result

    return await asyncio.to_thread(_list)


async def get_message_headers(creds: Credentials, message_id: str) -> dict:
    """Fetch metadata headers for a single message (no body content).

    Retrieves only From, To, Subject, Date headers in metadata format.

    Args:
        creds: Valid Gmail OAuth2 credentials.
        message_id: Gmail message ID.

    Returns:
        Raw API response dict with id, threadId, labelIds, payload.headers.
    """
    def _get():
        service = build("gmail", "v1", credentials=creds)
        result = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            )
            .execute()
        )
        logger.debug("get_message_headers message_id=%s", message_id)
        return result

    return await asyncio.to_thread(_get)


def _extract_body(msg: dict) -> str:
    """Extract plain text body from a Gmail message payload.

    Walks payload parts recursively. Prefers text/plain, falls back to
    text/html. Returns empty string if no text part is found.

    Args:
        msg: Full Gmail message dict (format="full") from the API.

    Returns:
        Decoded body text string (may be empty).
    """
    payload = msg.get("payload", {})

    def _walk_parts(parts: list) -> str | None:
        plain = None
        html = None
        for part in parts:
            mime = part.get("mimeType", "")
            if mime == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    plain = base64.urlsafe_b64decode(data + "==").decode(
                        "utf-8", errors="replace"
                    )
            elif mime == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    html = base64.urlsafe_b64decode(data + "==").decode(
                        "utf-8", errors="replace"
                    )
            elif "parts" in part:
                result = _walk_parts(part["parts"])
                if result:
                    return result
        return plain or html

    # Single-part message
    if "body" in payload and payload.get("body", {}).get("data"):
        data = payload["body"]["data"]
        try:
            return base64.urlsafe_b64decode(data + "==").decode(
                "utf-8", errors="replace"
            )
        except Exception:
            logger.warning(
                "failed to extract body from message_id=%s", msg.get("id")
            )
            return ""

    # Multi-part message
    parts = payload.get("parts", [])
    if parts:
        try:
            result = _walk_parts(parts)
            return result or ""
        except Exception:
            logger.warning(
                "failed to extract body from message_id=%s", msg.get("id")
            )
            return ""

    return ""


async def get_message_body(creds: Credentials, message_id: str) -> str:
    """Fetch full message body on-demand (for drafter use only).

    This is intentionally NOT called during inbox sync — body content
    is fetched only when needed for draft generation (Phase 4).

    Args:
        creds: Valid Gmail OAuth2 credentials.
        message_id: Gmail message ID.

    Returns:
        Plain text body string (may be empty if message has no text parts).
    """
    def _get():
        service = build("gmail", "v1", credentials=creds)
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        logger.debug("get_message_body message_id=%s", message_id)
        return _extract_body(msg)

    return await asyncio.to_thread(_get)


async def list_sent_messages(
    creds: Credentials,
    max_results: int = 200,
) -> dict:
    """List sent messages for voice profile extraction.

    Used by Phase 3 voice profile builder to extract writing style.
    Returns message stubs (id + threadId) — body fetched separately.

    Args:
        creds: Valid Gmail OAuth2 credentials.
        max_results: Maximum number of sent messages to return.

    Returns:
        Raw API response dict with keys: messages, nextPageToken,
        resultSizeEstimate.
    """
    def _list():
        service = build("gmail", "v1", credentials=creds)
        result = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["SENT"], maxResults=max_results)
            .execute()
        )
        logger.debug(
            "list_sent_messages max_results=%s", max_results
        )
        return result

    return await asyncio.to_thread(_list)


async def get_history(creds: Credentials, start_history_id: str) -> dict:
    """Fetch Gmail history changes since a given historyId.

    Used by sync worker to detect new inbox messages and label changes
    (archive, trash, delete) incrementally. Caller is responsible for
    handling HttpError 404 (stale historyId) with a full re-sync fallback.

    Args:
        creds: Valid Gmail OAuth2 credentials.
        start_history_id: History ID from a previous sync (or initial profile).

    Returns:
        Raw API response dict with history records for messageAdded and
        labelRemoved events.
    """
    def _get():
        service = build("gmail", "v1", credentials=creds)
        result = (
            service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded", "labelRemoved"],
            )
            .execute()
        )
        logger.debug(
            "get_history start_history_id=%s", start_history_id
        )
        return result

    return await asyncio.to_thread(_get)


async def send_reply(
    creds: Credentials,
    to: str,
    subject: str,
    body_text: str,
    thread_id: str,
    in_reply_to: str,
) -> str:
    """Send a threaded reply via Gmail API. Returns sent message ID.

    Constructs MIME with In-Reply-To and References headers to keep the
    reply inside the original Gmail thread (not orphaned as a new thread).

    Args:
        creds: Valid Gmail OAuth2 credentials (must have gmail.send scope).
        to: Recipient email address.
        subject: Email subject (will be prefixed with "Re: " if not already).
        body_text: Plain text reply body.
        thread_id: Gmail thread ID to attach the reply to.
        in_reply_to: Original email's Message-ID header value.

    Returns:
        Gmail message ID of the sent reply.
    """
    from email.mime.text import MIMEText

    def _send():
        service = build("gmail", "v1", credentials=creds)
        msg = MIMEText(body_text, "plain")
        msg["To"] = to
        msg["Subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw, "threadId": thread_id})
            .execute()
        )
        logger.debug("send_reply thread_id=%s", thread_id)
        return result["id"]

    return await asyncio.to_thread(_send)


async def get_message_id_header(creds: Credentials, message_id: str) -> str | None:
    """Fetch the Message-ID header for a Gmail message (for reply threading).

    Used at draft approval time to construct In-Reply-To header.
    Lightweight call -- metadata format with single header.

    Args:
        creds: Valid Gmail OAuth2 credentials.
        message_id: Gmail message ID.

    Returns:
        Message-ID header value string, or None if not found.
    """
    def _get():
        service = build("gmail", "v1", credentials=creds)
        result = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["Message-ID"],
            )
            .execute()
        )
        headers = result.get("payload", {}).get("headers", [])
        for h in headers:
            if h.get("name", "").lower() == "message-id":
                return h["value"]
        return None

    return await asyncio.to_thread(_get)


async def get_profile(creds: Credentials) -> dict:
    """Fetch the authenticated user's Gmail profile.

    Returns emailAddress and historyId. The historyId from this call is
    used to initialize the Phase 2 sync worker's starting position —
    ensuring no messages are missed after the initial full sync.

    Args:
        creds: Valid Gmail OAuth2 credentials.

    Returns:
        Dict with emailAddress, messagesTotal, threadsTotal, historyId.
    """
    def _get():
        service = build("gmail", "v1", credentials=creds)
        result = service.users().getProfile(userId="me").execute()
        logger.debug("get_profile completed")
        return result

    return await asyncio.to_thread(_get)
