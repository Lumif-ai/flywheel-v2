"""Google Gmail OAuth2 service for send-as-user email.

Handles:
- OAuth2 flow (authorize URL generation, code exchange) with gmail.send scope
- Credential encryption/decryption (reuses AES-256-GCM from auth.encryption)
- Token refresh with revocation detection
- Sending email via Gmail API as the authenticated user

Architecture note: Gmail and Calendar are SEPARATE Integration rows with
SEPARATE credentials.  Do NOT merge scopes -- each has its own OAuth grant.
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone
from email.mime.text import MIMEText

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from flywheel.auth.encryption import decrypt_api_key, encrypt_api_key
from flywheel.config import settings

# Send-only scope -- NOT gmail.modify or full access
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class TokenRevokedException(Exception):
    """Raised when a refresh token has been revoked by the user."""

    pass


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


def _create_oauth_flow() -> Flow:
    """Create an OAuth2 flow from application credentials."""
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_gmail_redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_gmail_redirect_uri,
    )


def generate_gmail_auth_url(state: str) -> str:
    """Generate the Google OAuth authorization URL for Gmail.

    Args:
        state: Cryptographic state parameter for CSRF protection.

    Returns:
        Authorization URL the user should be redirected to.
    """
    flow = _create_oauth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=state,
    )
    return auth_url


def exchange_gmail_code(code: str) -> Credentials:
    """Exchange an authorization code for OAuth credentials.

    Args:
        code: Authorization code from the OAuth callback.

    Returns:
        Google OAuth2 Credentials with refresh token.

    Raises:
        ValueError: If no refresh token was returned.
    """
    flow = _create_oauth_flow()
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
    """Encrypt OAuth credentials for database storage.

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
    """Decrypt and reconstruct OAuth credentials from database storage."""
    json_str = decrypt_api_key(encrypted)
    data = json.loads(json_str)

    expiry = None
    if data.get("expiry"):
        expiry = datetime.fromisoformat(data["expiry"])
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

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
    """Get valid (non-expired) credentials, refreshing if needed.

    Args:
        integration: Integration ORM object with credentials_encrypted.

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
                "Gmail access has been revoked. Please reconnect."
            ) from exc
        raise

    # Persist refreshed credentials back to the integration
    integration.credentials_encrypted = serialize_credentials(creds)

    return creds


# ---------------------------------------------------------------------------
# Gmail API -- send email
# ---------------------------------------------------------------------------


async def send_email_gmail(
    integration,
    to: str,
    subject: str,
    body_html: str,
) -> str:
    """Send an email via Gmail API as the authenticated user.

    Args:
        integration: Integration ORM object with credentials_encrypted.
        to: Recipient email address.
        subject: Email subject line.
        body_html: HTML body content.

    Returns:
        Gmail message ID of the sent email.
    """
    creds = await get_valid_credentials(integration)

    def _send():
        service = build("gmail", "v1", credentials=creds)
        message = MIMEText(body_html, "html")
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return result["id"]

    return await asyncio.to_thread(_send)
