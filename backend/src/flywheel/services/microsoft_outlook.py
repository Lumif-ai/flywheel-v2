"""Microsoft Outlook OAuth2 service for send-as-user email via Graph API.

Handles:
- OAuth2 flow via MSAL (authorize URL generation, code exchange)
- Custom credential serialization (NOT MSAL's built-in cache -- doesn't persist)
- Token refresh via MSAL acquire_token_by_refresh_token
- Sending email via Microsoft Graph API /me/sendMail
"""

from __future__ import annotations

import json
import logging
import time

import httpx
import msal

from flywheel.auth.encryption import decrypt_api_key, encrypt_api_key
from flywheel.config import settings

logger = logging.getLogger(__name__)

# Delegated permissions -- send mail, read mail, and read calendar as the signed-in user.
# Ensure Supabase Azure provider config includes these scopes in the dashboard.
SCOPES = ["Mail.Send", "Calendars.Read", "Mail.Read"]

# MSAL authority for multi-tenant support
AUTHORITY = "https://login.microsoftonline.com/common"


class TokenRevokedException(Exception):
    """Raised when a refresh token has been revoked by the user."""

    pass


# ---------------------------------------------------------------------------
# MSAL app
# ---------------------------------------------------------------------------


def _get_msal_app() -> msal.ConfidentialClientApplication:
    """Create an MSAL ConfidentialClientApplication."""
    return msal.ConfidentialClientApplication(
        client_id=settings.microsoft_client_id,
        client_credential=settings.microsoft_client_secret,
        authority=AUTHORITY,
    )


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


def generate_outlook_auth_url(state: str, redirect_uri: str) -> str:
    """Generate the Microsoft OAuth authorization URL for Outlook.

    Args:
        state: Cryptographic state parameter for CSRF protection.
        redirect_uri: The callback URI registered in Azure AD.

    Returns:
        Authorization URL the user should be redirected to.
    """
    app = _get_msal_app()
    return app.get_authorization_request_url(
        SCOPES,
        state=state,
        redirect_uri=redirect_uri,
    )


def exchange_outlook_code(code: str, redirect_uri: str) -> dict:
    """Exchange an authorization code for OAuth tokens.

    Args:
        code: Authorization code from the OAuth callback.
        redirect_uri: Must match the redirect_uri used in the auth request.

    Returns:
        Token result dict containing access_token, refresh_token, etc.

    Raises:
        ValueError: If the token exchange fails.
    """
    app = _get_msal_app()
    result = app.acquire_token_by_authorization_code(
        code, scopes=SCOPES, redirect_uri=redirect_uri
    )
    if "error" in result:
        desc = result.get("error_description", result["error"])
        raise ValueError(f"Outlook OAuth code exchange failed: {desc}")
    return result


# ---------------------------------------------------------------------------
# Credential serialization (AES-256-GCM via encryption.py)
# ---------------------------------------------------------------------------


def serialize_outlook_credentials(token_result: dict) -> bytes:
    """Encrypt Outlook OAuth credentials for database storage.

    Extracts only the fields we need (not the full MSAL cache) and encrypts.

    Returns:
        Encrypted bytes suitable for LargeBinary column.
    """
    data = {
        "access_token": token_result["access_token"],
        "refresh_token": token_result.get("refresh_token", ""),
        "token_type": token_result.get("token_type", "Bearer"),
        "expires_in": token_result.get("expires_in", 3600),
        "scope": token_result.get("scope", ""),
        "expires_at": time.time() + token_result.get("expires_in", 3600),
    }
    json_str = json.dumps(data)
    return encrypt_api_key(json_str)


def deserialize_outlook_credentials(encrypted: bytes) -> dict:
    """Decrypt Outlook OAuth credentials from database storage."""
    json_str = decrypt_api_key(encrypted)
    return json.loads(json_str)


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


def refresh_outlook_token(creds_dict: dict) -> dict:
    """Refresh an expired Outlook access token via MSAL.

    Args:
        creds_dict: Deserialized credentials dict with refresh_token.

    Returns:
        New token result dict from MSAL.

    Raises:
        TokenRevokedException: If the refresh token has been revoked.
    """
    app = _get_msal_app()
    result = app.acquire_token_by_refresh_token(
        creds_dict["refresh_token"], scopes=SCOPES
    )
    if "error" in result:
        raise TokenRevokedException(
            f"Outlook access has been revoked: {result.get('error_description', result['error'])}. "
            "Please reconnect."
        )
    return result


async def get_valid_outlook_credentials(integration) -> str:
    """Get a valid access token, refreshing if expired.

    Args:
        integration: Integration ORM object with credentials_encrypted.

    Returns:
        Valid access_token string for Authorization header.

    Raises:
        TokenRevokedException: If the refresh token has been revoked.
    """
    creds = deserialize_outlook_credentials(integration.credentials_encrypted)

    # Check if token is still valid (with 5-minute buffer)
    if creds.get("expires_at", 0) > time.time() + 300:
        return creds["access_token"]

    # Token expired -- refresh
    new_result = refresh_outlook_token(creds)

    # Re-serialize refreshed credentials back to the integration
    integration.credentials_encrypted = serialize_outlook_credentials(new_result)

    return new_result["access_token"]


# ---------------------------------------------------------------------------
# Microsoft Graph API -- send email
# ---------------------------------------------------------------------------


async def send_email_outlook(
    integration,
    to: str,
    subject: str,
    body_html: str,
) -> dict:
    """Send an email via Microsoft Graph API as the authenticated user.

    Args:
        integration: Integration ORM object with credentials_encrypted.
        to: Recipient email address.
        subject: Email subject line.
        body_html: HTML body content.

    Returns:
        Dict with status information.

    Raises:
        httpx.HTTPStatusError: If the Graph API returns an error.
    """
    access_token = await get_valid_outlook_credentials(integration)

    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body_html,
            },
            "toRecipients": [
                {"emailAddress": {"address": to}}
            ],
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    # 202 Accepted = success for sendMail
    if response.status_code == 202:
        return {"status": "sent", "provider": "outlook"}

    # Raise on error
    response.raise_for_status()
    return {"status": "sent", "provider": "outlook"}
