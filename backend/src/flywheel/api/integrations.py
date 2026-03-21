"""Integration endpoints for external service connections.

Endpoints:
- GET  /integrations/                          -- list integrations for tenant
- GET  /integrations/google-calendar/authorize -- start OAuth flow
- GET  /integrations/google-calendar/callback  -- OAuth callback (exchange code)
- DELETE /integrations/{id}                    -- disconnect integration
- POST /integrations/{id}/sync                 -- stub: returns 501 (Phase 23 Plan 02)
"""

from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Integration
from flywheel.services.google_calendar import (
    exchange_code,
    generate_auth_url,
    serialize_credentials,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _integration_to_dict(i: Integration) -> dict:
    """Serialize an Integration ORM object to a JSON-friendly dict."""
    return {
        "id": str(i.id),
        "provider": i.provider,
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
    """List all integrations for the current tenant."""
    result = await db.execute(select(Integration))
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
            select(Integration).where(Integration.id == integration_id)
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
):
    """Stub: Calendar sync available after first background sync (Plan 02)."""
    return JSONResponse(
        status_code=501,
        content={
            "error": "NotImplemented",
            "message": "Calendar sync available after first background sync",
            "code": 501,
        },
    )
