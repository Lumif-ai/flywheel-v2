"""BrokerContactService — CRUD for BrokerClientContact and CarrierContact.

Soft limits enforced via COUNT query before INSERT:
  - 20 contacts per BrokerClient
  - 10 contacts per CarrierConfig

None of these methods call db.commit() — caller owns the transaction.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException

from flywheel.db.models import BrokerClientContact, CarrierContact

logger = logging.getLogger(__name__)

_MAX_CLIENT_CONTACTS = 20
_MAX_CARRIER_CONTACTS = 10


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateClientContactRequest(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    role: str | None = None
    is_primary: bool = False


class CreateCarrierContactRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str = "submissions"
    is_primary: bool = False


class UpdateContactRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str | None = None
    is_primary: bool | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BrokerContactService:

    # ---- Client contacts ----

    async def create_client_contact(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        broker_client_id: UUID,
        req: CreateClientContactRequest,
    ) -> BrokerClientContact:
        """Create a contact for a broker client. Enforces 20-contact soft limit.

        Does NOT call db.commit().
        """
        count_result = await db.execute(
            select(func.count()).select_from(BrokerClientContact).where(
                BrokerClientContact.broker_client_id == broker_client_id,
                BrokerClientContact.tenant_id == tenant_id,
            )
        )
        count = count_result.scalar_one()
        if count >= _MAX_CLIENT_CONTACTS:
            raise HTTPException(
                status_code=422,
                detail=f"Client already has {_MAX_CLIENT_CONTACTS} contacts (limit reached)",
            )

        contact = BrokerClientContact(
            tenant_id=tenant_id,
            broker_client_id=broker_client_id,
            name=req.name,
            email=req.email,
            phone=req.phone,
            role=req.role,
            is_primary=req.is_primary,
        )
        db.add(contact)
        await db.flush()
        return contact

    async def list_client_contacts(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        broker_client_id: UUID,
    ) -> list[BrokerClientContact]:
        """List all contacts for a broker client."""
        result = await db.execute(
            select(BrokerClientContact).where(
                BrokerClientContact.broker_client_id == broker_client_id,
                BrokerClientContact.tenant_id == tenant_id,
            ).order_by(BrokerClientContact.is_primary.desc(), BrokerClientContact.name.asc())
        )
        return list(result.scalars().all())

    async def update_client_contact(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        contact_id: UUID,
        req: UpdateContactRequest,
    ) -> BrokerClientContact:
        """Update a client contact. Raises 404 if not found. Does NOT commit."""
        result = await db.execute(
            select(BrokerClientContact).where(
                BrokerClientContact.id == contact_id,
                BrokerClientContact.tenant_id == tenant_id,
            )
        )
        contact = result.scalar_one_or_none()
        if contact is None:
            raise HTTPException(status_code=404, detail="Contact not found")

        now = datetime.now(timezone.utc)
        if req.name is not None:
            contact.name = req.name
        if req.email is not None:
            contact.email = req.email
        if req.phone is not None:
            contact.phone = req.phone
        if req.role is not None:
            contact.role = req.role
        if req.is_primary is not None:
            contact.is_primary = req.is_primary
        contact.updated_at = now

        await db.flush()
        return contact

    async def delete_contact(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        contact_id: UUID,
        contact_type: str,  # 'client' or 'carrier'
    ) -> None:
        """Delete a contact by ID. Raises 404 if not found. Does NOT commit."""
        if contact_type == "client":
            result = await db.execute(
                select(BrokerClientContact).where(
                    BrokerClientContact.id == contact_id,
                    BrokerClientContact.tenant_id == tenant_id,
                )
            )
            contact = result.scalar_one_or_none()
        else:
            result = await db.execute(
                select(CarrierContact).where(
                    CarrierContact.id == contact_id,
                    CarrierContact.tenant_id == tenant_id,
                )
            )
            contact = result.scalar_one_or_none()

        if contact is None:
            raise HTTPException(status_code=404, detail="Contact not found")
        await db.delete(contact)
        await db.flush()

    # ---- Carrier contacts ----

    async def create_carrier_contact(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        carrier_config_id: UUID,
        req: CreateCarrierContactRequest,
    ) -> CarrierContact:
        """Create a contact for a carrier config. Enforces 10-contact soft limit.

        Does NOT call db.commit().
        """
        count_result = await db.execute(
            select(func.count()).select_from(CarrierContact).where(
                CarrierContact.carrier_config_id == carrier_config_id,
                CarrierContact.tenant_id == tenant_id,
            )
        )
        count = count_result.scalar_one()
        if count >= _MAX_CARRIER_CONTACTS:
            raise HTTPException(
                status_code=422,
                detail=f"Carrier already has {_MAX_CARRIER_CONTACTS} contacts (limit reached)",
            )

        contact = CarrierContact(
            tenant_id=tenant_id,
            carrier_config_id=carrier_config_id,
            name=req.name,
            email=req.email,
            phone=req.phone,
            role=req.role,
            is_primary=req.is_primary,
        )
        db.add(contact)
        await db.flush()
        return contact

    async def list_carrier_contacts(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        carrier_config_id: UUID,
    ) -> list[CarrierContact]:
        """List all contacts for a carrier config."""
        result = await db.execute(
            select(CarrierContact).where(
                CarrierContact.carrier_config_id == carrier_config_id,
                CarrierContact.tenant_id == tenant_id,
            ).order_by(CarrierContact.is_primary.desc(), CarrierContact.role.asc())
        )
        return list(result.scalars().all())

    async def update_carrier_contact(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        contact_id: UUID,
        req: UpdateContactRequest,
    ) -> CarrierContact:
        """Update a carrier contact. Raises 404 if not found. Does NOT commit."""
        result = await db.execute(
            select(CarrierContact).where(
                CarrierContact.id == contact_id,
                CarrierContact.tenant_id == tenant_id,
            )
        )
        contact = result.scalar_one_or_none()
        if contact is None:
            raise HTTPException(status_code=404, detail="Contact not found")

        now = datetime.now(timezone.utc)
        if req.name is not None:
            contact.name = req.name
        if req.email is not None:
            contact.email = req.email
        if req.phone is not None:
            contact.phone = req.phone
        if req.role is not None:
            contact.role = req.role
        if req.is_primary is not None:
            contact.is_primary = req.is_primary
        contact.updated_at = now

        await db.flush()
        return contact
