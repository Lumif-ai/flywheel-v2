"""Saved views REST API — CRUD endpoints for pipeline view configurations.

4 endpoints:
- GET    /pipeline/views/               -- list saved views
- POST   /pipeline/views/               -- create saved view
- PATCH  /pipeline/views/{view_id}      -- update saved view
- DELETE /pipeline/views/{view_id}      -- delete saved view
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.services.saved_views_service import (
    CreateSavedViewRequest,
    SavedViewResponse,
    SavedViewsService,
    UpdateSavedViewRequest,
)

router = APIRouter(prefix="/pipeline/views", tags=["saved-views"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[SavedViewResponse])
async def list_views(
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
):
    """List all saved views for the current user."""
    svc = SavedViewsService(db, user)
    views = await svc.list_views()
    return [SavedViewResponse.model_validate(v) for v in views]


@router.post(
    "/", response_model=SavedViewResponse, status_code=status.HTTP_201_CREATED
)
async def create_view(
    req: CreateSavedViewRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
):
    """Create a new saved view."""
    svc = SavedViewsService(db, user)
    view = await svc.create_view(req)
    return SavedViewResponse.model_validate(view)


@router.patch("/{view_id}", response_model=SavedViewResponse)
async def update_view(
    view_id: UUID,
    req: UpdateSavedViewRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
):
    """Update an existing saved view."""
    svc = SavedViewsService(db, user)
    view = await svc.update_view(view_id, req)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved view not found",
        )
    return SavedViewResponse.model_validate(view)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_view(
    view_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
):
    """Delete a saved view."""
    svc = SavedViewsService(db, user)
    deleted = await svc.delete_view(view_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved view not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
