"""BrokerClientService — CRUD and search for BrokerClient entities.

All methods take db: AsyncSession and tenant_id: UUID per call.
None of these methods call db.commit() — the caller (endpoint handler) owns the transaction.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException

from flywheel.db.models import BrokerClient
from flywheel.engines.context_store_writer import create_context_entity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------


class CreateBrokerClientRequest(BaseModel):
    name: str
    legal_name: str | None = None
    domain: str | None = None
    tax_id: str | None = None
    industry: str | None = None
    location: str | None = None
    notes: str | None = None
    metadata: dict | None = None


class UpdateBrokerClientRequest(BaseModel):
    name: str | None = None
    legal_name: str | None = None
    domain: str | None = None
    tax_id: str | None = None
    industry: str | None = None
    location: str | None = None
    notes: str | None = None
    metadata: dict | None = None


# ---------------------------------------------------------------------------
# Normalization helper
# ---------------------------------------------------------------------------

# Legal suffixes to strip for dedup (case-insensitive)
_LEGAL_SUFFIXES = re.compile(
    r"\b(s\.a\. de c\.v\.|s\.a\.p\.i\.|s\.a\.|de c\.v\.|s\.c\.|"
    r"inc\.?|corp\.?|llc\.?|ltd\.?|co\.?|plc\.?|gmbh|ag|sa|srl|sl)\b",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    """Lowercase, strip accents, legal suffixes, collapse whitespace, strip punctuation."""
    # Normalize unicode accents
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    # Strip legal suffixes
    stripped_suffix = _LEGAL_SUFFIXES.sub("", ascii_only)
    # Lowercase
    lower = stripped_suffix.lower()
    # Remove punctuation (keep alphanumeric + spaces)
    no_punct = re.sub(r"[^a-z0-9\s]", "", lower)
    # Collapse whitespace
    return re.sub(r"\s+", " ", no_punct).strip()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BrokerClientService:

    async def create(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        req: CreateBrokerClientRequest,
    ) -> BrokerClient:
        """Create a new BrokerClient with normalized_name and context entity.

        Raises HTTPException(409) if normalized_name already exists for tenant.
        Does NOT call db.commit().
        """
        normalized = _normalize_name(req.name)
        if not normalized:
            raise HTTPException(status_code=422, detail="Client name normalizes to empty string")

        # Create context entity (upsert — does not commit)
        context_entity_id = await create_context_entity(
            db=db,
            tenant_id=tenant_id,
            name=req.name,
            entity_type="broker_client",
            metadata={"domain": req.domain} if req.domain else None,
        )

        client = BrokerClient(
            tenant_id=tenant_id,
            name=req.name,
            normalized_name=normalized,
            legal_name=req.legal_name,
            domain=req.domain,
            tax_id=req.tax_id,
            industry=req.industry,
            location=req.location,
            notes=req.notes,
            context_entity_id=context_entity_id,
            metadata_=req.metadata or {},
        )
        db.add(client)

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"Client with normalized name '{normalized}' already exists",
            )

        return client

    async def get(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        client_id: UUID,
    ) -> BrokerClient:
        """Fetch a single client by ID. Raises 404 if not found."""
        result = await db.execute(
            select(BrokerClient).where(
                BrokerClient.id == client_id,
                BrokerClient.tenant_id == tenant_id,
            )
        )
        client = result.scalar_one_or_none()
        if client is None:
            raise HTTPException(status_code=404, detail="Client not found")
        return client

    async def list(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[BrokerClient], int]:
        """List clients with optional search and pagination.

        Returns (items, total_count).
        """
        base_q = select(BrokerClient).where(BrokerClient.tenant_id == tenant_id)

        if search:
            normalized_search = _normalize_name(search)
            base_q = base_q.where(
                BrokerClient.normalized_name.ilike(f"%{normalized_search}%")
            )

        count_q = select(func.count()).select_from(base_q.subquery())
        total = (await db.execute(count_q)).scalar_one()

        offset = (page - 1) * page_size
        items_q = (
            base_q.order_by(BrokerClient.name.asc())
            .offset(offset)
            .limit(page_size)
        )
        items = (await db.execute(items_q)).scalars().all()

        return list(items), total

    async def update(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        client_id: UUID,
        req: UpdateBrokerClientRequest,
    ) -> BrokerClient:
        """Partial update a client. Raises 404 if not found, 409 on name collision.

        Does NOT call db.commit().
        """
        client = await self.get(db, tenant_id, client_id)
        now = datetime.now(timezone.utc)

        if req.name is not None:
            client.name = req.name
            client.normalized_name = _normalize_name(req.name)
        if req.legal_name is not None:
            client.legal_name = req.legal_name
        if req.domain is not None:
            client.domain = req.domain
        if req.tax_id is not None:
            client.tax_id = req.tax_id
        if req.industry is not None:
            client.industry = req.industry
        if req.location is not None:
            client.location = req.location
        if req.notes is not None:
            client.notes = req.notes
        if req.metadata is not None:
            client.metadata_ = req.metadata

        client.updated_at = now

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"Client with normalized name '{client.normalized_name}' already exists",
            )

        return client

    async def delete(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        client_id: UUID,
    ) -> None:
        """Hard-delete a client. Raises 404 if not found. Does NOT commit."""
        client = await self.get(db, tenant_id, client_id)
        await db.delete(client)
        await db.flush()
