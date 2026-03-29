"""Google Calendar OAuth2 service and Calendar API wrapper.

Handles:
- OAuth2 flow (authorize URL generation, code exchange)
- Credential encryption/decryption (reuses AES-256-GCM from auth.encryption)
- Token refresh with revocation detection
- Async-wrapped Calendar API calls (google-api-python-client is synchronous)
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from flywheel.auth.encryption import decrypt_api_key, encrypt_api_key
from flywheel.config import settings

# Read-only access to calendar events
SCOPES = ["https://www.googleapis.com/auth/calendar.events.readonly"]


class TokenRevokedException(Exception):
    """Raised when a refresh token has been revoked by the user."""

    pass


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


def create_oauth_flow() -> Flow:
    """Create an OAuth2 flow from application credentials."""
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )
    return flow


def generate_auth_url(state: str) -> str:
    """Generate the Google OAuth authorization URL.

    Args:
        state: Cryptographic state parameter for CSRF protection.

    Returns:
        Authorization URL the user should be redirected to.
    """
    flow = create_oauth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=state,
    )
    return auth_url


def exchange_code(code: str) -> Credentials:
    """Exchange an authorization code for OAuth credentials.

    Args:
        code: Authorization code from the OAuth callback.

    Returns:
        Google OAuth2 Credentials with refresh token.

    Raises:
        ValueError: If no refresh token was returned (user may not have
            granted offline access or consent was not forced).
    """
    flow = create_oauth_flow()
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

    Serializes the credential fields to JSON, then encrypts using
    the project's AES-256-GCM encryption (same as BYOK API keys).

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
    """Decrypt and reconstruct OAuth credentials from database storage.

    Args:
        encrypted: Encrypted bytes from the credentials_encrypted column.

    Returns:
        Reconstructed Google OAuth2 Credentials object.
    """
    json_str = decrypt_api_key(encrypted)
    data = json.loads(json_str)

    expiry = None
    if data.get("expiry"):
        expiry = datetime.fromisoformat(data["expiry"])
        # Google's Credentials.valid compares expiry against a naive UTC datetime,
        # so strip timezone info to avoid "can't compare offset-naive and offset-aware" errors.
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
    """Get valid (non-expired) credentials, refreshing if needed.

    Args:
        integration: Integration ORM object with credentials_encrypted.

    Returns:
        Valid Google OAuth2 Credentials.

    Raises:
        TokenRevokedException: If the refresh token has been revoked.
        ValueError: If credentials cannot be decrypted.
    """
    creds = deserialize_credentials(integration.credentials_encrypted)

    if creds.valid:
        return creds

    # Token expired -- attempt refresh in a thread (synchronous Google API)
    try:
        await asyncio.to_thread(creds.refresh, GoogleAuthRequest())
    except RefreshError as exc:
        # "invalid_grant" means the user revoked access or refresh token expired
        if "invalid_grant" in str(exc):
            raise TokenRevokedException(
                "Google Calendar access has been revoked. Please reconnect."
            ) from exc
        raise

    # Persist refreshed credentials back to the integration
    integration.credentials_encrypted = serialize_credentials(creds)

    return creds


# ---------------------------------------------------------------------------
# Calendar API wrapper
# ---------------------------------------------------------------------------


async def list_upcoming_events(
    credentials: Credentials,
    time_min: str,
    time_max: str,
    sync_token: str | None = None,
) -> dict:
    """List upcoming calendar events, optionally using incremental sync.

    All Google API calls are wrapped in asyncio.to_thread() since
    google-api-python-client is synchronous.

    Args:
        credentials: Valid Google OAuth2 Credentials.
        time_min: RFC3339 timestamp for range start (ignored if sync_token set).
        time_max: RFC3339 timestamp for range end (ignored if sync_token set).
        sync_token: Incremental sync token from a previous response.

    Returns:
        Raw response dict from the Google Calendar API.
    """

    def _fetch():
        service = build("calendar", "v3", credentials=credentials)
        request_kwargs = {
            "calendarId": "primary",
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if sync_token:
            request_kwargs["syncToken"] = sync_token
        else:
            request_kwargs["timeMin"] = time_min
            request_kwargs["timeMax"] = time_max

        return service.events().list(**request_kwargs).execute()

    return await asyncio.to_thread(_fetch)
