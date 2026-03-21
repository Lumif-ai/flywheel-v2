"""Slack OAuth workspace installation and bot token management.

Handles:
- OAuth v2 flow (authorize URL generation, code exchange via oauth.v2.access)
- Credential encryption/decryption (reuses AES-256-GCM from auth.encryption)
- Bot token lookup by team_id for multi-workspace support
"""

from __future__ import annotations

import json

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.auth.encryption import decrypt_api_key, encrypt_api_key
from flywheel.config import settings
from flywheel.db.models import Integration

# Bot token scopes requested during OAuth install
SLACK_SCOPES = ["commands", "chat:write", "channels:history", "channels:read", "users:read"]


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


def generate_slack_auth_url(state: str) -> str:
    """Generate the Slack OAuth v2 authorization URL.

    Args:
        state: Cryptographic state parameter for CSRF protection.

    Returns:
        Authorization URL the user should be redirected to.
    """
    scopes = ",".join(SLACK_SCOPES)
    return (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={settings.slack_client_id}"
        f"&scope={scopes}"
        f"&state={state}"
        f"&redirect_uri={settings.slack_redirect_uri}"
    )


async def exchange_slack_code(code: str) -> dict:
    """Exchange an authorization code for Slack OAuth tokens.

    Posts to Slack's oauth.v2.access endpoint to complete the install flow.

    Args:
        code: Authorization code from the OAuth callback.

    Returns:
        Full response dict containing access_token, team, bot_user_id,
        authed_user, etc.

    Raises:
        ValueError: If Slack's response indicates failure (ok=false).
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret,
                "code": code,
                "redirect_uri": settings.slack_redirect_uri,
            },
        )
        data = response.json()

    if not data.get("ok"):
        error = data.get("error", "unknown_error")
        raise ValueError(f"Slack OAuth exchange failed: {error}")

    return data


# ---------------------------------------------------------------------------
# Credential serialization (AES-256-GCM via encryption.py)
# ---------------------------------------------------------------------------


def serialize_slack_credentials(install_data: dict) -> bytes:
    """Encrypt Slack install credentials for database storage.

    Extracts the essential fields from the oauth.v2.access response and
    encrypts them using the project's AES-256-GCM encryption.

    Returns:
        Encrypted bytes suitable for LargeBinary column.
    """
    cred_data = {
        "access_token": install_data["access_token"],
        "team_id": install_data["team"]["id"],
        "team_name": install_data["team"]["name"],
        "bot_user_id": install_data.get("bot_user_id", ""),
        "authed_user_id": install_data.get("authed_user", {}).get("id", ""),
    }
    json_str = json.dumps(cred_data)
    return encrypt_api_key(json_str)


def deserialize_slack_credentials(encrypted: bytes) -> dict:
    """Decrypt Slack credentials from database storage.

    Args:
        encrypted: Encrypted bytes from the credentials_encrypted column.

    Returns:
        Dict with access_token, team_id, team_name, bot_user_id, authed_user_id.
    """
    json_str = decrypt_api_key(encrypted)
    return json.loads(json_str)


# ---------------------------------------------------------------------------
# Bot token lookup
# ---------------------------------------------------------------------------


async def get_bot_token_for_team(db: AsyncSession, team_id: str) -> str | None:
    """Look up the bot token for a Slack workspace by team_id.

    Queries the Integration table for a connected Slack integration whose
    settings contain the given team_id, then decrypts and returns the
    bot access token.

    Args:
        db: Async database session.
        team_id: Slack workspace team ID (e.g., T01234ABCDE).

    Returns:
        Bot access token (xoxb-*) or None if no matching integration found.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.provider == "slack",
            Integration.status == "connected",
        )
    )
    integrations = result.scalars().all()

    for integration in integrations:
        if integration.settings and integration.settings.get("team_id") == team_id:
            if integration.credentials_encrypted:
                creds = deserialize_slack_credentials(integration.credentials_encrypted)
                return creds.get("access_token")

    return None
