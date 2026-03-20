"""Work item CRUD endpoints with skill-run trigger.

6 endpoints:
- GET /work-items/             -- list work items (paginated, status filter)
- POST /work-items/            -- create work item
- GET /work-items/{item_id}    -- get single work item
- PATCH /work-items/{item_id}  -- update work item
- DELETE /work-items/{item_id} -- hard delete work item
- POST /work-items/{item_id}/run -- start skill run for work item
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import SkillRun, WorkItem
from flywheel.middleware.rate_limit import check_concurrent_run_limit

router = APIRouter(prefix="/work-items", tags=["work-items"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateWorkItemRequest(BaseModel):
    type: str
    title: str
    data: dict | None = None
    scheduled_at: datetime.datetime | None = None


class UpdateWorkItemRequest(BaseModel):
    title: str | None = None
    status: str | None = None
    data: dict | None = None
    scheduled_at: datetime.datetime | None = None


class RunSkillRequest(BaseModel):
    skill_name: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _work_item_to_dict(w: WorkItem) -> dict:
    """Serialize a WorkItem ORM object to a JSON-friendly dict."""
    return {
        "id": str(w.id),
        "type": w.type,
        "title": w.title,
        "status": w.status,
        "data": w.data,
        "source": w.source,
        "external_id": w.external_id,
        "scheduled_at": w.scheduled_at.isoformat() if w.scheduled_at else None,
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


def _paginated_response(items: list, total: int, offset: int, limit: int) -> dict:
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


# ---------------------------------------------------------------------------
# GET /work-items/
# ---------------------------------------------------------------------------


@router.get("/")
async def list_work_items(
    status_filter: str | None = Query(None, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List work items with optional status filter and pagination."""
    limit = min(limit, 100)

    base = select(WorkItem)
    if status_filter is not None:
        base = base.where(WorkItem.status == status_filter)

    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    data_stmt = base.order_by(WorkItem.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(data_stmt)
    items = result.scalars().all()

    return _paginated_response(
        [_work_item_to_dict(w) for w in items], total, offset, limit
    )


# ---------------------------------------------------------------------------
# POST /work-items/
# ---------------------------------------------------------------------------


@router.post("/", status_code=201)
async def create_work_item(
    body: CreateWorkItemRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new work item."""
    item = WorkItem(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        type=body.type,
        title=body.title,
        data=body.data or {},
        scheduled_at=body.scheduled_at,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return _work_item_to_dict(item)


# ---------------------------------------------------------------------------
# GET /work-items/{item_id}
# ---------------------------------------------------------------------------


@router.get("/{item_id}")
async def get_work_item(
    item_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a single work item by ID."""
    item = (
        await db.execute(select(WorkItem).where(WorkItem.id == item_id))
    ).scalar_one_or_none()

    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")

    return _work_item_to_dict(item)


# ---------------------------------------------------------------------------
# PATCH /work-items/{item_id}
# ---------------------------------------------------------------------------


@router.patch("/{item_id}")
async def update_work_item(
    item_id: UUID,
    body: UpdateWorkItemRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a work item (partial update)."""
    item = (
        await db.execute(select(WorkItem).where(WorkItem.id == item_id))
    ).scalar_one_or_none()

    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")

    if body.title is not None:
        item.title = body.title
    if body.status is not None:
        item.status = body.status
    if body.data is not None:
        item.data = body.data
    if body.scheduled_at is not None:
        item.scheduled_at = body.scheduled_at

    await db.commit()
    await db.refresh(item)

    return _work_item_to_dict(item)


# ---------------------------------------------------------------------------
# DELETE /work-items/{item_id}
# ---------------------------------------------------------------------------


@router.delete("/{item_id}", status_code=200)
async def delete_work_item(
    item_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Hard delete a work item."""
    item = (
        await db.execute(select(WorkItem).where(WorkItem.id == item_id))
    ).scalar_one_or_none()

    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")

    await db.delete(item)
    await db.commit()

    return {"deleted": True, "id": str(item_id)}


# ---------------------------------------------------------------------------
# POST /work-items/{item_id}/run
# ---------------------------------------------------------------------------


@router.post("/{item_id}/run", status_code=201)
async def run_skill_for_item(
    item_id: UUID,
    body: RunSkillRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Start a skill run for a work item. Actual execution is Phase 20."""
    # Rate limit check
    await check_concurrent_run_limit(user.sub, db)

    item = (
        await db.execute(select(WorkItem).where(WorkItem.id == item_id))
    ).scalar_one_or_none()

    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")

    # Extract input text from work item data
    input_text = item.data.get("description", item.title) if item.data else item.title

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name=body.skill_name,
        input_text=input_text,
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    return {"run_id": str(run.id), "status": "pending"}
