"""Integration stub endpoints for external service connections.

4 endpoints:
- GET /integrations/                  -- list integrations for tenant
- POST /integrations/google-calendar  -- stub: returns 501
- DELETE /integrations/{id}           -- disconnect integration
- POST /integrations/{id}/sync        -- stub: returns 501
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Integration

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
# POST /integrations/google-calendar
# ---------------------------------------------------------------------------


@router.post("/google-calendar")
async def connect_google_calendar(
    user: TokenPayload = Depends(require_tenant),
):
    """Stub: Google Calendar integration is a Phase 23 feature."""
    return JSONResponse(
        status_code=501,
        content={
            "error": "NotImplemented",
            "message": "Google Calendar integration available in a future release",
            "code": 501,
        },
    )


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
    """Stub: Integration sync is not yet available."""
    return JSONResponse(
        status_code=501,
        content={
            "error": "NotImplemented",
            "message": "Sync not yet available",
            "code": 501,
        },
    )
