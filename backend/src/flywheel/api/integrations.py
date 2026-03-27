"""Integration endpoints for external service connections.

Endpoints:
- GET  /integrations/                          -- list integrations for tenant
- GET  /integrations/google-calendar/authorize -- start OAuth flow
- GET  /integrations/google-calendar/callback  -- OAuth callback (exchange code)
- GET  /integrations/gmail/authorize           -- start Gmail OAuth flow (send-only)
- GET  /integrations/gmail/callback            -- Gmail OAuth callback (send-only)
- GET  /integrations/gmail-read/authorize      -- start Gmail Read OAuth flow (read+send)
- GET  /integrations/gmail-read/callback       -- Gmail Read OAuth callback
- GET  /integrations/outlook/authorize         -- start Outlook OAuth flow
- GET  /integrations/outlook/callback          -- Outlook OAuth callback
- GET  /integrations/slack/authorize           -- start Slack OAuth install flow
- GET  /integrations/slack/callback            -- Slack OAuth callback
- DELETE /integrations/{id}                    -- disconnect integration
- POST /integrations/{id}/sync                 -- trigger immediate calendar sync
- GET  /integrations/suggestions               -- meeting prep suggestions
"""

from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Integration
from flywheel.services.calendar_sync import (
    get_meeting_prep_suggestions,
    sync_calendar,
)
from flywheel.config import settings
from flywheel.services.google_calendar import (
    TokenRevokedException,
    exchange_code,
    generate_auth_url,
    serialize_credentials,
)
from flywheel.services.google_gmail import (
    exchange_gmail_code,
    generate_gmail_auth_url,
    serialize_credentials as serialize_gmail_credentials,
)
from flywheel.services.gmail_read import (
    exchange_gmail_read_code,
    generate_gmail_read_auth_url,
    serialize_credentials as serialize_gmail_read_credentials,
)
from flywheel.services.microsoft_outlook import (
    exchange_outlook_code,
    generate_outlook_auth_url,
    serialize_outlook_credentials,
)
from flywheel.services.slack_oauth import (
    exchange_slack_code,
    generate_slack_auth_url,
    serialize_slack_credentials,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_PROVIDER_DISPLAY = {
    "google-calendar": "Google Calendar",
    "gmail": "Gmail",
    "gmail-read": "Gmail (Read)",
    "outlook": "Outlook",
    "slack": "Slack",
}


def _integration_to_dict(i: Integration) -> dict:
    """Serialize an Integration ORM object to a JSON-friendly dict."""
    return {
        "id": str(i.id),
        "provider": i.provider,
        "provider_display": _PROVIDER_DISPLAY.get(i.provider, i.provider),
        "status": i.status,
        "settings": i.settings,
        "last_synced_at": i.last_synced_at.isoformat() if i.last_synced_at else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


# ---------------------------------------------------------------------------
# GET /integrations/
# ---------------------------------------------------------------------------


@router.get("/")
async def list_integrations(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all integrations for the current user (defense-in-depth user filter)."""
    result = await db.execute(
        select(Integration).where(Integration.user_id == user.sub)
    )
    integrations = result.scalars().all()
    return {
        "items": [_integration_to_dict(i) for i in integrations]
    }


# ---------------------------------------------------------------------------
# GET /integrations/google-calendar/authorize
# ---------------------------------------------------------------------------


@router.get("/google-calendar/authorize")
async def authorize_google_calendar(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Start Google Calendar OAuth flow.

    Creates a pending Integration row with a cryptographic state parameter
    for CSRF protection, then returns the Google authorization URL.
    """
    state = secrets.token_urlsafe(32)

    # Create a pending integration row to track the OAuth state
    integration = Integration(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        provider="google-calendar",
        status="pending",
        settings={"oauth_state": state, "sync_token": None},
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    auth_url = generate_auth_url(state)

    return {"auth_url": auth_url, "state": state}


# ---------------------------------------------------------------------------
# GET /integrations/google-calendar/callback
# ---------------------------------------------------------------------------


@router.get("/google-calendar/callback")
async def google_calendar_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF verification"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Handle Google Calendar OAuth callback.

    Verifies the state parameter, exchanges the authorization code for
    credentials, encrypts them, and updates the Integration row.
    """
    # Find the pending integration matching this state
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.provider == "google-calendar",
            Integration.status == "pending",
        )
    )
    pending = result.scalars().all()

    # Match state parameter (CSRF protection)
    integration = None
    for p in pending:
        if p.settings and p.settings.get("oauth_state") == state:
            integration = p
            break

    if integration is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state. Please restart the authorization flow.",
        )

    # Exchange authorization code for credentials
    try:
        creds = exchange_code(code)
    except ValueError as exc:
        # Clean up the pending row on failure
        await db.delete(integration)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await db.delete(integration)
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"OAuth code exchange failed: {exc}",
        ) from exc

    # Encrypt and store credentials
    encrypted = serialize_credentials(creds)
    integration.status = "connected"
    integration.credentials_encrypted = encrypted
    integration.settings = {"sync_token": None}  # Clear oauth_state, init sync_token
    await db.commit()

    return {"status": "connected", "id": str(integration.id)}


# ---------------------------------------------------------------------------
# GET /integrations/gmail/authorize
# ---------------------------------------------------------------------------


@router.get("/gmail/authorize")
async def authorize_gmail(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Start Gmail OAuth flow.

    Creates a pending Integration row with a cryptographic state parameter
    for CSRF protection, then returns the Google authorization URL with
    gmail.send scope.
    """
    state = secrets.token_urlsafe(32)

    integration = Integration(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        provider="gmail",
        status="pending",
        settings={"oauth_state": state},
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    auth_url = generate_gmail_auth_url(state)

    return {"auth_url": auth_url, "state": state}


# ---------------------------------------------------------------------------
# GET /integrations/gmail/callback
# ---------------------------------------------------------------------------


@router.get("/gmail/callback")
async def gmail_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF verification"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Handle Gmail OAuth callback.

    Verifies the state parameter, exchanges the authorization code for
    credentials, encrypts them, and updates the Integration row.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.provider == "gmail",
            Integration.status == "pending",
        )
    )
    pending = result.scalars().all()

    integration = None
    for p in pending:
        if p.settings and p.settings.get("oauth_state") == state:
            integration = p
            break

    if integration is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state. Please restart the Gmail authorization flow.",
        )

    try:
        creds = exchange_gmail_code(code)
    except ValueError as exc:
        await db.delete(integration)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await db.delete(integration)
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Gmail OAuth code exchange failed: {exc}",
        ) from exc

    encrypted = serialize_gmail_credentials(creds)
    integration.status = "connected"
    integration.credentials_encrypted = encrypted
    integration.settings = {}  # Clear oauth_state
    await db.commit()

    return {"status": "connected", "id": str(integration.id)}


# ---------------------------------------------------------------------------
# GET /integrations/gmail-read/authorize
# ---------------------------------------------------------------------------


@router.get("/gmail-read/authorize")
async def authorize_gmail_read(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Start Gmail Read OAuth flow.

    Creates a pending Integration row with provider="gmail-read" and a
    cryptographic state parameter for CSRF protection. Returns the Google
    authorization URL with gmail.readonly, gmail.modify, and gmail.send scopes.

    IMPORTANT: This endpoint uses provider="gmail-read" exclusively and
    NEVER queries or modifies provider="gmail" Integration rows.
    """
    state = secrets.token_urlsafe(32)

    integration = Integration(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        provider="gmail-read",
        status="pending",
        settings={"oauth_state": state, "history_id": None},
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    auth_url = generate_gmail_read_auth_url(state)

    return {"auth_url": auth_url, "state": state}


# ---------------------------------------------------------------------------
# GET /integrations/gmail-read/callback
# ---------------------------------------------------------------------------


@router.get("/gmail-read/callback")
async def gmail_read_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF verification"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Handle Gmail Read OAuth callback.

    Verifies the state parameter, exchanges the authorization code for
    credentials (gmail.readonly + gmail.modify + gmail.send), encrypts them,
    and updates the Integration row with provider="gmail-read".

    IMPORTANT: The query filter is always provider="gmail-read". This callback
    NEVER queries provider="gmail" rows.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.provider == "gmail-read",
            Integration.status == "pending",
        )
    )
    pending = result.scalars().all()

    integration = None
    for p in pending:
        if p.settings and p.settings.get("oauth_state") == state:
            integration = p
            break

    if integration is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state. Please restart the Gmail Read authorization flow.",
        )

    try:
        creds = exchange_gmail_read_code(code)
    except ValueError as exc:
        await db.delete(integration)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await db.delete(integration)
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Gmail Read OAuth code exchange failed: {exc}",
        ) from exc

    encrypted = serialize_gmail_read_credentials(creds)
    integration.status = "connected"
    integration.credentials_encrypted = encrypted
    integration.settings = {"history_id": None}  # Clear oauth_state, keep history_id slot
    await db.commit()

    return {"status": "connected", "id": str(integration.id)}


# ---------------------------------------------------------------------------
# GET /integrations/outlook/authorize
# ---------------------------------------------------------------------------


@router.get("/outlook/authorize")
async def authorize_outlook(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Start Outlook OAuth flow.

    Creates a pending Integration row with a cryptographic state parameter
    for CSRF protection, then returns the Microsoft authorization URL.
    """
    state = secrets.token_urlsafe(32)

    integration = Integration(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        provider="outlook",
        status="pending",
        settings={"oauth_state": state},
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    auth_url = generate_outlook_auth_url(state, settings.microsoft_redirect_uri)

    return {"auth_url": auth_url, "state": state}


# ---------------------------------------------------------------------------
# GET /integrations/outlook/callback
# ---------------------------------------------------------------------------


@router.get("/outlook/callback")
async def outlook_callback(
    code: str = Query(..., description="Authorization code from Microsoft"),
    state: str = Query(..., description="State parameter for CSRF verification"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Handle Outlook OAuth callback.

    Verifies the state parameter, exchanges the authorization code for
    tokens via MSAL, encrypts them, and updates the Integration row.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.provider == "outlook",
            Integration.status == "pending",
        )
    )
    pending = result.scalars().all()

    integration = None
    for p in pending:
        if p.settings and p.settings.get("oauth_state") == state:
            integration = p
            break

    if integration is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state. Please restart the Outlook authorization flow.",
        )

    try:
        token_result = exchange_outlook_code(code, settings.microsoft_redirect_uri)
    except ValueError as exc:
        await db.delete(integration)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await db.delete(integration)
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Outlook OAuth code exchange failed: {exc}",
        ) from exc

    encrypted = serialize_outlook_credentials(token_result)
    integration.status = "connected"
    integration.credentials_encrypted = encrypted
    integration.settings = {}  # Clear oauth_state
    await db.commit()

    return {"status": "connected", "id": str(integration.id)}


# ---------------------------------------------------------------------------
# GET /integrations/slack/authorize
# ---------------------------------------------------------------------------


@router.get("/slack/authorize")
async def authorize_slack(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Start Slack OAuth install flow.

    Creates a pending Integration row with a cryptographic state parameter
    for CSRF protection, then returns the Slack authorization URL.
    """
    state = secrets.token_urlsafe(32)

    integration = Integration(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        provider="slack",
        status="pending",
        settings={"oauth_state": state},
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    auth_url = generate_slack_auth_url(state)

    return {"auth_url": auth_url, "state": state}


# ---------------------------------------------------------------------------
# GET /integrations/slack/callback
# ---------------------------------------------------------------------------


@router.get("/slack/callback")
async def slack_callback(
    code: str = Query(..., description="Authorization code from Slack"),
    state: str = Query(..., description="State parameter for CSRF verification"),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Handle Slack OAuth callback.

    Verifies the state parameter, exchanges the authorization code for
    workspace install data, encrypts the bot token, and updates the
    Integration row with team metadata.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.provider == "slack",
            Integration.status == "pending",
        )
    )
    pending = result.scalars().all()

    integration = None
    for p in pending:
        if p.settings and p.settings.get("oauth_state") == state:
            integration = p
            break

    if integration is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state. Please restart the Slack authorization flow.",
        )

    try:
        install_data = await exchange_slack_code(code)
    except ValueError as exc:
        await db.delete(integration)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await db.delete(integration)
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Slack OAuth code exchange failed: {exc}",
        ) from exc

    encrypted = serialize_slack_credentials(install_data)
    integration.status = "connected"
    integration.credentials_encrypted = encrypted
    integration.settings = {
        "team_id": install_data["team"]["id"],
        "team_name": install_data["team"]["name"],
    }
    await db.commit()

    return {"status": "connected", "id": str(integration.id)}


# ---------------------------------------------------------------------------
# DELETE /integrations/{integration_id}
# ---------------------------------------------------------------------------


@router.delete("/{integration_id}")
async def disconnect_integration(
    integration_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Disconnect an integration by setting status to 'disconnected'."""
    integration = (
        await db.execute(
            select(Integration).where(
                Integration.id == integration_id,
                Integration.user_id == user.sub,
            )
        )
    ).scalar_one_or_none()

    if integration is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration.status = "disconnected"
    integration.credentials_encrypted = None  # Clear sensitive credential data
    await db.commit()

    return {"disconnected": True, "id": str(integration_id)}


# ---------------------------------------------------------------------------
# POST /integrations/{integration_id}/sync
# ---------------------------------------------------------------------------


@router.post("/{integration_id}/sync")
async def sync_integration(
    integration_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Trigger an immediate calendar sync for a specific integration."""
    integration = (
        await db.execute(
            select(Integration).where(
                Integration.id == integration_id,
                Integration.user_id == user.sub,
            )
        )
    ).scalar_one_or_none()

    if integration is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    if integration.status != "connected":
        raise HTTPException(
            status_code=400, detail="Integration not connected"
        )

    try:
        count = await sync_calendar(db, integration)
    except TokenRevokedException:
        integration.status = "disconnected"
        integration.credentials_encrypted = None
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="Google Calendar access has been revoked. Please reconnect.",
        )

    return {"synced": True, "events_processed": count}


# ---------------------------------------------------------------------------
# GET /integrations/suggestions
# ---------------------------------------------------------------------------


@router.get("/suggestions")
async def list_suggestions(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get proactive meeting prep suggestions.

    Returns meetings with external attendees within the next 48 hours
    that haven't been dismissed by the user.
    """
    suggestions = await get_meeting_prep_suggestions(
        db, user.tenant_id, user.sub
    )
    return {"suggestions": suggestions}
