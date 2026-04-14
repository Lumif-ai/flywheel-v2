"""Broker client CRUD endpoints.

Endpoints:
  GET  /clients           -- list clients (paginated, searchable)
  POST /clients           -- create client (normalized_name, context entity)
  GET  /clients/{id}      -- get single client
  PUT  /clients/{id}      -- update client
  DELETE /clients/{id}    -- delete client
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_module
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import BrokerClient
from flywheel.services.broker_client_service import (
    BrokerClientService,
    CreateBrokerClientRequest,
    UpdateBrokerClientRequest,
)

clients_router = APIRouter(tags=["broker"])
_svc = BrokerClientService()


def _client_to_dict(c: BrokerClient) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "tenant_id": str(c.tenant_id),
        "name": c.name,
        "normalized_name": c.normalized_name,
        "legal_name": c.legal_name,
        "domain": c.domain,
        "tax_id": c.tax_id,
        "industry": c.industry,
        "location": c.location,
        "notes": c.notes,
        "context_entity_id": str(c.context_entity_id) if c.context_entity_id else None,
        "metadata": c.metadata_,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@clients_router.get("/clients")
async def list_clients(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    items, total = await _svc.list(db, user.tenant_id, search=search, page=page, page_size=page_size)
    return {
        "items": [_client_to_dict(c) for c in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@clients_router.post("/clients", status_code=201)
async def create_client(
    body: CreateBrokerClientRequest,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    client = await _svc.create(db, user.tenant_id, user.sub, body)
    await db.commit()
    await db.refresh(client)
    return _client_to_dict(client)


@clients_router.get("/clients/{client_id}")
async def get_client(
    client_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    client = await _svc.get(db, user.tenant_id, client_id)
    return _client_to_dict(client)


@clients_router.put("/clients/{client_id}")
async def update_client(
    client_id: UUID,
    body: UpdateBrokerClientRequest,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    client = await _svc.update(db, user.tenant_id, client_id, body)
    await db.commit()
    await db.refresh(client)
    return _client_to_dict(client)


@clients_router.delete("/clients/{client_id}", status_code=204)
async def delete_client(
    client_id: UUID,
    user: TokenPayload = Depends(require_module("broker")),
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    await _svc.delete(db, user.tenant_id, client_id)
    await db.commit()
