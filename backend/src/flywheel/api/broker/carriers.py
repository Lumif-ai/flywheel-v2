"""Broker carrier CRUD endpoints.

Endpoints:
  GET  /carriers             -- list active carriers
  POST /carriers             -- create carrier (with context entity)
  PUT  /carriers/{id}        -- update carrier
  DELETE /carriers/{id}      -- deactivate carrier
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_module
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import CarrierConfig

logger = logging.getLogger(__name__)

carriers_router = APIRouter(tags=["broker"])


# ---------------------------------------------------------------------------
# Pydantic request bodies
# ---------------------------------------------------------------------------


class CreateCarrierBody(BaseModel):
    carrier_name: str
    carrier_type: str = "insurance"
    submission_method: str = "email"
    portal_url: str | None = None
    coverage_types: list[str] = []
    regions: list[str] = []
    min_project_value: float | None = None
    max_project_value: float | None = None
    avg_response_days: float | None = None
    portal_limit: float | None = None
    notes: str | None = None


class UpdateCarrierBody(BaseModel):
    carrier_name: str | None = None
    carrier_type: str | None = None
    submission_method: str | None = None
    portal_url: str | None = None
    coverage_types: list[str] | None = None
    regions: list[str] | None = None
    min_project_value: float | None = None
    max_project_value: float | None = None
    avg_response_days: float | None = None
    portal_limit: float | None = None
    is_active: bool | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------


def _carrier_to_dict(c: CarrierConfig) -> dict[str, Any]:
    """Serialize a CarrierConfig to a JSON-friendly dict.

    NOTE: email_address was dropped in Phase 130. Use /carriers/{id}/contacts
    to manage carrier email contacts.
    """
    return {
        "id": str(c.id),
        "tenant_id": str(c.tenant_id),
        "carrier_name": c.carrier_name,
        "carrier_type": c.carrier_type,
        "submission_method": c.submission_method,
        "portal_url": c.portal_url,
        "portal_limit": float(c.portal_limit) if c.portal_limit is not None else None,
        "coverage_types": c.coverage_types or [],
        "regions": c.regions or [],
        "min_project_value": float(c.min_project_value) if c.min_project_value is not None else None,
        "max_project_value": float(c.max_project_value) if c.max_project_value is not None else None,
        "avg_response_days": float(c.avg_response_days) if c.avg_response_days is not None else None,
        "is_active": c.is_active,
        "context_entity_id": str(c.context_entity_id) if c.context_entity_id else None,
        "contacts_count": 0,  # loaded separately via /carriers/{id}/contacts
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@carriers_router.get("/carriers")
async def list_carriers(
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """List all active carrier configs for the tenant, ordered by name."""
    result = await db.execute(
        select(CarrierConfig)
        .where(
            CarrierConfig.tenant_id == user.tenant_id,
            CarrierConfig.is_active.is_(True),
        )
        .order_by(CarrierConfig.carrier_name)
    )
    carriers = result.scalars().all()
    return {"items": [_carrier_to_dict(c) for c in carriers], "total": len(carriers)}


@carriers_router.post("/carriers", status_code=201)
async def create_carrier(
    body: CreateCarrierBody,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Create a new carrier config with a context entity."""
    from flywheel.engines.context_store_writer import create_context_entity

    carrier = CarrierConfig(
        id=uuid4(),
        tenant_id=user.tenant_id,
        carrier_name=body.carrier_name,
        carrier_type=body.carrier_type,
        submission_method=body.submission_method,
        portal_url=body.portal_url,
        coverage_types=body.coverage_types,
        regions=body.regions,
        min_project_value=body.min_project_value,
        max_project_value=body.max_project_value,
        avg_response_days=body.avg_response_days,
        portal_limit=body.portal_limit,
        notes=body.notes,
        created_by_user_id=user.sub,
    )
    db.add(carrier)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Carrier with this name and type already exists",
        )

    # Create context entity after flush (carrier.id is now available)
    carrier.context_entity_id = await create_context_entity(
        db=db,
        tenant_id=user.tenant_id,
        name=body.carrier_name,
        entity_type="carrier",
    )

    await db.commit()
    await db.refresh(carrier)
    return _carrier_to_dict(carrier)


@carriers_router.put("/carriers/{carrier_id}")
async def update_carrier(
    carrier_id: UUID,
    body: UpdateCarrierBody,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Partially update a carrier config."""
    result = await db.execute(
        select(CarrierConfig).where(
            CarrierConfig.id == carrier_id,
            CarrierConfig.tenant_id == user.tenant_id,
        )
    )
    carrier = result.scalar_one_or_none()
    if carrier is None:
        raise HTTPException(status_code=404, detail="Carrier not found")

    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(carrier, field, value)

    carrier.updated_by_user_id = user.sub

    await db.commit()
    await db.refresh(carrier)
    return _carrier_to_dict(carrier)


@carriers_router.delete("/carriers/{carrier_id}")
async def delete_carrier(
    carrier_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, str]:
    """Soft-deactivate a carrier config (sets is_active=False)."""
    result = await db.execute(
        select(CarrierConfig).where(
            CarrierConfig.id == carrier_id,
            CarrierConfig.tenant_id == user.tenant_id,
        )
    )
    carrier = result.scalar_one_or_none()
    if carrier is None:
        raise HTTPException(status_code=404, detail="Carrier not found")

    carrier.is_active = False
    await db.commit()
    return {"status": "deactivated"}
