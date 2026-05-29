"""Saved views service — CRUD for user pipeline view configurations.

Handles list, create, update, and delete operations on SavedView.
Enforces tenant + owner isolation.
"""

from __future__ import annotations

import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import SavedView

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateSavedViewRequest(BaseModel):
    name: str
    filters: dict = {}
    sort: dict | None = None
    columns: list | None = None
    is_default: bool = False


class UpdateSavedViewRequest(BaseModel):
    name: str | None = None
    filters: dict | None = None
    sort: dict | None = None
    columns: list | None = None
    is_default: bool | None = None
    position: int | None = None


class SavedViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    filters: dict
    sort: dict | None
    columns: list | None
    is_default: bool
    position: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SavedViewsService:
    """CRUD operations for saved pipeline views."""

    def __init__(self, db: AsyncSession, user: TokenPayload):
        self.db = db
        self.user = user

    # -- helpers --

    def _ownership_filter(self):
        """Return SQLAlchemy filter for tenant + owner isolation."""
        return (
            SavedView.tenant_id == self.user.tenant_id,
            SavedView.owner_id == self.user.sub,
        )

    async def _get_owned_view(self, view_id: UUID) -> SavedView | None:
        """Fetch a single view owned by the current user."""
        result = await self.db.execute(
            select(SavedView).where(
                SavedView.id == view_id,
                *self._ownership_filter(),
            )
        )
        return result.scalar_one_or_none()

    # -- public API --

    async def list_views(self) -> list[SavedView]:
        """Return all saved views for the current user, ordered by position."""
        result = await self.db.execute(
            select(SavedView)
            .where(*self._ownership_filter())
            .order_by(SavedView.position.asc(), SavedView.created_at.asc())
        )
        return list(result.scalars().all())

    async def create_view(self, req: CreateSavedViewRequest) -> SavedView:
        """Create a new saved view with auto-incrementing position."""
        # Determine next position
        max_pos_result = await self.db.execute(
            select(func.coalesce(func.max(SavedView.position), -1)).where(
                *self._ownership_filter()
            )
        )
        next_position = max_pos_result.scalar() + 1

        view = SavedView(
            tenant_id=self.user.tenant_id,
            owner_id=self.user.sub,
            name=req.name,
            filters=req.filters,
            sort=req.sort,
            columns=req.columns,
            is_default=req.is_default,
            position=next_position,
        )
        self.db.add(view)
        await self.db.flush()
        await self.db.refresh(view)
        return view

    async def update_view(
        self, view_id: UUID, req: UpdateSavedViewRequest
    ) -> SavedView | None:
        """Update an existing saved view. Returns None if not found/not owned."""
        view = await self._get_owned_view(view_id)
        if view is None:
            return None

        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(view, field, value)

        view.updated_at = datetime.datetime.now(datetime.timezone.utc)
        await self.db.flush()
        await self.db.refresh(view)
        return view

    async def delete_view(self, view_id: UUID) -> bool:
        """Delete a saved view. Returns False if not found/not owned."""
        view = await self._get_owned_view(view_id)
        if view is None:
            return False

        await self.db.delete(view)
        await self.db.flush()
        return True
