"""Broker contact CRUD endpoints.

Endpoints:
  GET  /clients/{id}/contacts          -- list client contacts
  POST /clients/{id}/contacts          -- create client contact
  PUT  /clients/{id}/contacts/{cid}    -- update client contact
  DELETE /clients/{id}/contacts/{cid}  -- delete client contact
  GET  /carriers/{id}/contacts         -- list carrier contacts
  POST /carriers/{id}/contacts         -- create carrier contact
  PUT  /carriers/{id}/contacts/{cid}   -- update carrier contact
  DELETE /carriers/{id}/contacts/{cid} -- delete carrier contact
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_module
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import BrokerClientContact, CarrierContact
from flywheel.services.broker_contact_service import (
    BrokerContactService,
    CreateCarrierContactRequest,
    CreateClientContactRequest,
    UpdateContactRequest,
)

contacts_router = APIRouter(tags=["broker"])
_svc = BrokerContactService()


def _client_contact_to_dict(c: BrokerClientContact) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "broker_client_id": str(c.broker_client_id),
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "role": c.role,
        "is_primary": c.is_primary,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _carrier_contact_to_dict(c: CarrierContact) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "carrier_config_id": str(c.carrier_config_id),
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "role": c.role,
        "is_primary": c.is_primary,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


# ---- Client contact endpoints ----

@contacts_router.get("/clients/{client_id}/contacts")
async def list_client_contacts(
    client_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    items = await _svc.list_client_contacts(db, user.tenant_id, client_id)
    return {"items": [_client_contact_to_dict(c) for c in items], "total": len(items)}


@contacts_router.post("/clients/{client_id}/contacts", status_code=201)
async def create_client_contact(
    client_id: UUID,
    body: CreateClientContactRequest,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    contact = await _svc.create_client_contact(db, user.tenant_id, client_id, body)
    await db.commit()
    await db.refresh(contact)
    return _client_contact_to_dict(contact)


@contacts_router.put("/clients/{client_id}/contacts/{contact_id}")
async def update_client_contact(
    client_id: UUID,
    contact_id: UUID,
    body: UpdateContactRequest,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    contact = await _svc.update_client_contact(db, user.tenant_id, contact_id, body)
    await db.commit()
    await db.refresh(contact)
    return _client_contact_to_dict(contact)


@contacts_router.delete("/clients/{client_id}/contacts/{contact_id}", status_code=204)
async def delete_client_contact(
    client_id: UUID,
    contact_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    await _svc.delete_contact(db, user.tenant_id, contact_id, "client")
    await db.commit()


# ---- Carrier contact endpoints ----

@contacts_router.get("/carriers/{carrier_id}/contacts")
async def list_carrier_contacts(
    carrier_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    items = await _svc.list_carrier_contacts(db, user.tenant_id, carrier_id)
    return {"items": [_carrier_contact_to_dict(c) for c in items], "total": len(items)}


@contacts_router.post("/carriers/{carrier_id}/contacts", status_code=201)
async def create_carrier_contact(
    carrier_id: UUID,
    body: CreateCarrierContactRequest,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    contact = await _svc.create_carrier_contact(db, user.tenant_id, carrier_id, body)
    await db.commit()
    await db.refresh(contact)
    return _carrier_contact_to_dict(contact)


@contacts_router.put("/carriers/{carrier_id}/contacts/{contact_id}")
async def update_carrier_contact(
    carrier_id: UUID,
    contact_id: UUID,
    body: UpdateContactRequest,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    contact = await _svc.update_carrier_contact(db, user.tenant_id, contact_id, body)
    await db.commit()
    await db.refresh(contact)
    return _carrier_contact_to_dict(contact)


@contacts_router.delete("/carriers/{carrier_id}/contacts/{contact_id}", status_code=204)
async def delete_carrier_contact(
    carrier_id: UUID,
    contact_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    await _svc.delete_contact(db, user.tenant_id, contact_id, "carrier")
    await db.commit()
