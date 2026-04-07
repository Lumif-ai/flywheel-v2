"""Tasks CRUD API — 7 endpoints for task lifecycle management.

Endpoints:
- GET    /tasks/                   -- paginated list with filters
- GET    /tasks/summary            -- count by status + overdue
- GET    /tasks/{task_id}          -- single task detail
- POST   /tasks/                   -- create manual task
- PATCH  /tasks/{task_id}          -- update task fields
- PATCH  /tasks/{task_id}/status   -- validated status transition
- DELETE /tasks/{task_id}          -- soft-delete (set status=dismissed)
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Task

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Valid enum values
# ---------------------------------------------------------------------------

VALID_TASK_TYPES = {"followup", "deliverable", "introduction", "research", "other"}
VALID_COMMITMENT_DIRECTIONS = {"yours", "theirs", "mutual", "signal", "speculation"}
VALID_TRUST_LEVELS = {"auto", "review", "confirm"}
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_STATUSES = {
    "detected", "in_review", "confirmed", "in_progress",
    "done", "blocked", "dismissed", "deferred",
}

VALID_TRANSITIONS: dict[str, set[str]] = {
    "detected":    {"in_review", "confirmed", "dismissed", "deferred"},
    "in_review":   {"confirmed", "dismissed", "deferred"},
    "confirmed":   {"in_review", "in_progress", "done", "dismissed"},
    "in_progress": {"done", "blocked", "dismissed"},
    "blocked":     {"in_progress", "dismissed"},
    "done":        set(),
    "dismissed":   {"detected"},
    "deferred":    {"in_review"},
}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    task_type: str
    commitment_direction: str = "yours"
    suggested_skill: str | None = None
    skill_context: dict | None = None
    trust_level: str = "review"
    priority: str = "medium"
    due_date: datetime.datetime | None = None
    meeting_id: UUID | None = None
    account_id: UUID | None = None
    pipeline_entry_id: UUID | None = None

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, v: str) -> str:
        if v not in VALID_TASK_TYPES:
            raise ValueError(f"task_type must be one of {sorted(VALID_TASK_TYPES)}")
        return v

    @field_validator("commitment_direction")
    @classmethod
    def validate_commitment_direction(cls, v: str) -> str:
        if v not in VALID_COMMITMENT_DIRECTIONS:
            raise ValueError(
                f"commitment_direction must be one of {sorted(VALID_COMMITMENT_DIRECTIONS)}"
            )
        return v

    @field_validator("trust_level")
    @classmethod
    def validate_trust_level(cls, v: str) -> str:
        if v not in VALID_TRUST_LEVELS:
            raise ValueError(f"trust_level must be one of {sorted(VALID_TRUST_LEVELS)}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(VALID_PRIORITIES)}")
        return v


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    due_date: datetime.datetime | None = None
    suggested_skill: str | None = None
    trust_level: str | None = None
    resolved_by: str | None = None
    resolution_source_id: UUID | None = None
    resolution_note: str | None = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(VALID_PRIORITIES)}")
        return v

    @field_validator("trust_level")
    @classmethod
    def validate_trust_level(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_TRUST_LEVELS:
            raise ValueError(f"trust_level must be one of {sorted(VALID_TRUST_LEVELS)}")
        return v

    @field_validator("resolved_by")
    @classmethod
    def validate_resolved_by(cls, v: str | None) -> str | None:
        if v is not None and v not in {"user", "system"}:
            raise ValueError("resolved_by must be 'user' or 'system'")
        return v


class StatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return v


class TaskResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    meeting_id: UUID | None
    account_id: UUID | None
    pipeline_entry_id: UUID | None = None
    email_id: UUID | None = None
    title: str
    description: str | None
    source: str
    task_type: str
    commitment_direction: str
    suggested_skill: str | None
    skill_context: dict | None
    trust_level: str
    status: str
    priority: str
    due_date: datetime.datetime | None
    completed_at: datetime.datetime | None
    resolved_by: str | None = None
    resolution_source_id: UUID | None = None
    resolution_note: str | None = None
    metadata: dict | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class TasksListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int


class TaskSummaryResponse(BaseModel):
    detected: int = 0
    in_review: int = 0
    confirmed: int = 0
    in_progress: int = 0
    done: int = 0
    blocked: int = 0
    dismissed: int = 0
    deferred: int = 0
    overdue: int = 0


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def _task_to_response(t: Task) -> dict:
    """Serialize a Task ORM object to TaskResponse dict shape."""
    return {
        "id": t.id,
        "tenant_id": t.tenant_id,
        "user_id": t.user_id,
        "meeting_id": t.meeting_id,
        "account_id": t.account_id,
        "pipeline_entry_id": t.pipeline_entry_id,
        "email_id": t.email_id,
        "title": t.title,
        "description": t.description,
        "source": t.source,
        "task_type": t.task_type,
        "commitment_direction": t.commitment_direction,
        "suggested_skill": t.suggested_skill,
        "skill_context": t.skill_context,
        "trust_level": t.trust_level,
        "status": t.status,
        "priority": t.priority,
        "due_date": t.due_date,
        "completed_at": t.completed_at,
        "resolved_by": t.resolved_by,
        "resolution_source_id": t.resolution_source_id,
        "resolution_note": t.resolution_note,
        "metadata": t.metadata_,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


# ---------------------------------------------------------------------------
# GET /tasks/
# ---------------------------------------------------------------------------


@router.get("/")
async def list_tasks(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = Query(None),
    commitment_direction: str | None = Query(None),
    priority: str | None = Query(None),
    meeting_id: UUID | None = Query(None),
    account_id: UUID | None = Query(None),
    pipeline_entry_id: UUID | None = Query(None),
    source: str | None = Query(None),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Paginated list of tasks with optional filters."""
    limit = min(limit, 100)

    base = select(Task)

    if status is not None:
        base = base.where(Task.status == status)
    if commitment_direction is not None:
        base = base.where(Task.commitment_direction == commitment_direction)
    if priority is not None:
        base = base.where(Task.priority == priority)
    if meeting_id is not None:
        base = base.where(Task.meeting_id == meeting_id)
    if account_id is not None:
        base = base.where(Task.account_id == account_id)
    if pipeline_entry_id is not None:
        base = base.where(Task.pipeline_entry_id == pipeline_entry_id)
    if source is not None:
        base = base.where(Task.source == source)

    # Count
    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch page
    data_stmt = base.order_by(Task.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(data_stmt)
    tasks = result.scalars().all()

    return TasksListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /tasks/summary  (BEFORE /{task_id} to avoid path conflict)
# ---------------------------------------------------------------------------


@router.get("/summary")
async def task_summary(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Return count per status plus overdue count."""
    # Count by status
    stmt = select(Task.status, func.count()).group_by(Task.status)
    result = await db.execute(stmt)
    counts = {row[0]: row[1] for row in result.all()}

    # Overdue: due_date < now AND status not in done/dismissed
    now = datetime.datetime.now(datetime.timezone.utc)
    overdue_stmt = select(func.count()).select_from(
        select(Task).where(
            Task.due_date < now,
            Task.status.notin_(["done", "dismissed"]),
        ).subquery()
    )
    overdue_result = await db.execute(overdue_stmt)
    overdue = overdue_result.scalar() or 0

    return TaskSummaryResponse(
        detected=counts.get("detected", 0),
        in_review=counts.get("in_review", 0),
        confirmed=counts.get("confirmed", 0),
        in_progress=counts.get("in_progress", 0),
        done=counts.get("done", 0),
        blocked=counts.get("blocked", 0),
        dismissed=counts.get("dismissed", 0),
        deferred=counts.get("deferred", 0),
        overdue=overdue,
    )


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}
# ---------------------------------------------------------------------------


@router.get("/{task_id}")
async def get_task(
    task_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Return a single task. RLS scopes to current user."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return _task_to_response(task)


# ---------------------------------------------------------------------------
# POST /tasks/
# ---------------------------------------------------------------------------


@router.post("/", status_code=201)
async def create_task(
    body: TaskCreate,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a manual task."""
    new_task = Task(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        title=body.title,
        description=body.description,
        source="manual",
        task_type=body.task_type,
        commitment_direction=body.commitment_direction,
        suggested_skill=body.suggested_skill,
        skill_context=body.skill_context,
        trust_level=body.trust_level,
        status="detected",
        priority=body.priority,
        due_date=body.due_date,
        meeting_id=body.meeting_id,
        account_id=body.account_id,
        pipeline_entry_id=body.pipeline_entry_id,
    )
    db.add(new_task)
    await db.flush()
    await db.refresh(new_task)
    await db.commit()

    return _task_to_response(new_task)


# ---------------------------------------------------------------------------
# PATCH /tasks/{task_id}
# ---------------------------------------------------------------------------


@router.patch("/{task_id}")
async def update_task(
    task_id: UUID,
    body: TaskUpdate,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update allowed task fields."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.priority is not None:
        task.priority = body.priority
    if body.due_date is not None:
        task.due_date = body.due_date
    if body.suggested_skill is not None:
        task.suggested_skill = body.suggested_skill
    if body.trust_level is not None:
        task.trust_level = body.trust_level
    if body.resolved_by is not None:
        task.resolved_by = body.resolved_by
    if body.resolution_source_id is not None:
        task.resolution_source_id = body.resolution_source_id
    if body.resolution_note is not None:
        task.resolution_note = body.resolution_note

    task.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    await db.refresh(task)

    return _task_to_response(task)


# ---------------------------------------------------------------------------
# PATCH /tasks/{task_id}/status
# ---------------------------------------------------------------------------


@router.patch("/{task_id}/status")
async def update_task_status(
    task_id: UUID,
    body: StatusUpdate,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Validate and apply a status transition."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    current = task.status
    target = body.status

    valid_targets = VALID_TRANSITIONS.get(current, set())
    if target not in valid_targets:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot transition from '{current}' to '{target}'. "
                f"Valid transitions: {sorted(valid_targets) if valid_targets else 'none (terminal state)'}"
            ),
        )

    task.status = target
    task.updated_at = datetime.datetime.now(datetime.timezone.utc)

    # Set completed_at when reaching done
    if target == "done":
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)
    # Clear completed_at if reopening (dismissed -> detected)
    elif current == "dismissed" and target == "detected":
        task.completed_at = None

    await db.commit()
    await db.refresh(task)

    return _task_to_response(task)


# ---------------------------------------------------------------------------
# DELETE /tasks/{task_id}
# ---------------------------------------------------------------------------


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Soft-delete: set status to dismissed."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "dismissed"
    task.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
