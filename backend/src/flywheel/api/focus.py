"""Focus CRUD endpoints: create, list, get, update, archive, join, leave, switch, members.

9 endpoints:
- POST /focuses               -- create a new focus (auto-joins creator)
- GET /focuses                 -- list non-archived focuses with member counts
- GET /focuses/{focus_id}      -- get single focus with member list
- PATCH /focuses/{focus_id}    -- update name/description/settings
- POST /focuses/{focus_id}/archive  -- archive a focus and deactivate members
- POST /focuses/{focus_id}/join     -- join a focus
- POST /focuses/{focus_id}/leave    -- leave a focus
- POST /focuses/{focus_id}/switch   -- switch active focus
- GET /focuses/{focus_id}/members   -- list focus members
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, text, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Focus, Profile, UserFocus

router = APIRouter(prefix="/focuses", tags=["focuses"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateFocusRequest(BaseModel):
    name: str
    description: str | None = None
    settings: dict | None = None


class UpdateFocusRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    settings: dict | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _focus_to_dict(focus: Focus, member_count: int | None = None) -> dict:
    """Serialize a Focus ORM object to a JSON-friendly dict."""
    result = {
        "id": str(focus.id),
        "name": focus.name,
        "description": focus.description,
        "settings": focus.settings,
        "created_by": str(focus.created_by),
        "created_at": focus.created_at.isoformat() if focus.created_at else None,
        "updated_at": focus.updated_at.isoformat() if focus.updated_at else None,
        "archived_at": focus.archived_at.isoformat() if focus.archived_at else None,
    }
    if member_count is not None:
        result["member_count"] = member_count
    return result


# ---------------------------------------------------------------------------
# POST /focuses
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def create_focus(
    body: CreateFocusRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new focus. Creator auto-joins as a member."""
    # Enforce soft limit: max 50 focuses per tenant
    count_stmt = select(func.count()).select_from(
        select(Focus.id)
        .where(Focus.tenant_id == user.tenant_id, Focus.archived_at.is_(None))
        .subquery()
    )
    count_result = await db.execute(count_stmt)
    current_count = count_result.scalar() or 0
    if current_count >= 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum of 50 active focuses per tenant",
        )

    new_focus = Focus(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        settings=body.settings or {},
        created_by=user.sub,
    )
    db.add(new_focus)
    await db.flush()

    # Auto-join creator
    membership = UserFocus(
        user_id=user.sub,
        focus_id=new_focus.id,
        tenant_id=user.tenant_id,
        active=False,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(new_focus)

    return {"focus": _focus_to_dict(new_focus, member_count=1)}


# ---------------------------------------------------------------------------
# GET /focuses
# ---------------------------------------------------------------------------


@router.get("")
async def list_focuses(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all non-archived focuses for the tenant with member counts."""
    member_count_sub = (
        select(
            UserFocus.focus_id,
            func.count().label("member_count"),
        )
        .group_by(UserFocus.focus_id)
        .subquery()
    )

    stmt = (
        select(Focus, member_count_sub.c.member_count)
        .outerjoin(member_count_sub, Focus.id == member_count_sub.c.focus_id)
        .where(Focus.archived_at.is_(None))
        .order_by(Focus.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    return {
        "items": [
            _focus_to_dict(focus, member_count=mc or 0)
            for focus, mc in rows
        ]
    }


# ---------------------------------------------------------------------------
# GET /focuses/{focus_id}
# ---------------------------------------------------------------------------


@router.get("/{focus_id}")
async def get_focus(
    focus_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a single focus with its member list."""
    focus_result = await db.execute(
        select(Focus).where(Focus.id == focus_id)
    )
    focus = focus_result.scalar_one_or_none()
    if focus is None:
        raise HTTPException(status_code=404, detail="Focus not found")

    # Get members with profile info
    members_stmt = (
        select(UserFocus, Profile)
        .join(Profile, UserFocus.user_id == Profile.id)
        .where(UserFocus.focus_id == focus_id)
    )
    members_result = await db.execute(members_stmt)
    members = [
        {
            "user_id": str(uf.user_id),
            "email": None,  # TODO: email lives in auth.users, fetch via Supabase Admin API if needed
            "active": uf.active,
            "joined_at": uf.joined_at.isoformat() if uf.joined_at else None,
        }
        for uf, u in members_result.all()
    ]

    result = _focus_to_dict(focus, member_count=len(members))
    result["members"] = members
    return {"focus": result}


# ---------------------------------------------------------------------------
# PATCH /focuses/{focus_id}
# ---------------------------------------------------------------------------


@router.patch("/{focus_id}")
async def update_focus(
    focus_id: UUID,
    body: UpdateFocusRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update focus name, description, or settings. Creator or admin only."""
    focus_result = await db.execute(
        select(Focus).where(Focus.id == focus_id)
    )
    focus = focus_result.scalar_one_or_none()
    if focus is None:
        raise HTTPException(status_code=404, detail="Focus not found")

    # Authorization: creator or admin
    if focus.created_by != user.sub and user.tenant_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator or an admin can update this focus",
        )

    if body.name is not None:
        focus.name = body.name
    if body.description is not None:
        focus.description = body.description
    if body.settings is not None:
        focus.settings = body.settings
    focus.updated_at = datetime.datetime.now(datetime.timezone.utc)

    await db.commit()
    await db.refresh(focus)

    return {"focus": _focus_to_dict(focus)}


# ---------------------------------------------------------------------------
# POST /focuses/{focus_id}/archive
# ---------------------------------------------------------------------------


@router.post("/{focus_id}/archive")
async def archive_focus(
    focus_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Archive a focus and deactivate all members. Creator or admin only."""
    focus_result = await db.execute(
        select(Focus).where(Focus.id == focus_id)
    )
    focus = focus_result.scalar_one_or_none()
    if focus is None:
        raise HTTPException(status_code=404, detail="Focus not found")

    if focus.created_by != user.sub and user.tenant_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator or an admin can archive this focus",
        )

    focus.archived_at = datetime.datetime.now(datetime.timezone.utc)

    # Deactivate all user_focuses for this focus
    await db.execute(
        update(UserFocus)
        .where(UserFocus.focus_id == focus_id, UserFocus.active == True)  # noqa: E712
        .values(active=False)
    )

    await db.commit()
    await db.refresh(focus)

    return {"focus": _focus_to_dict(focus)}


# ---------------------------------------------------------------------------
# POST /focuses/{focus_id}/join
# ---------------------------------------------------------------------------


@router.post("/{focus_id}/join")
async def join_focus(
    focus_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Join a focus. Uses INSERT ON CONFLICT DO NOTHING for idempotency."""
    # Verify focus exists and is not archived
    focus_result = await db.execute(
        select(Focus).where(Focus.id == focus_id, Focus.archived_at.is_(None))
    )
    if focus_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Focus not found or archived")

    stmt = pg_insert(UserFocus).values(
        user_id=user.sub,
        focus_id=focus_id,
        tenant_id=user.tenant_id,
        active=False,
    )
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["user_id", "focus_id"],
    )
    await db.execute(stmt)
    await db.commit()

    return {"joined": True, "focus_id": str(focus_id)}


# ---------------------------------------------------------------------------
# POST /focuses/{focus_id}/leave
# ---------------------------------------------------------------------------


@router.post("/{focus_id}/leave")
async def leave_focus(
    focus_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Leave a focus. If leaving the active focus, active is cleared."""
    await db.execute(
        delete(UserFocus).where(
            UserFocus.user_id == user.sub,
            UserFocus.focus_id == focus_id,
        )
    )
    await db.commit()

    return {"left": True, "focus_id": str(focus_id)}


# ---------------------------------------------------------------------------
# POST /focuses/{focus_id}/switch
# ---------------------------------------------------------------------------


@router.post("/{focus_id}/switch")
async def switch_focus(
    focus_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Switch active focus. Deactivates current, activates target. Must be a member."""
    # Check membership
    membership_result = await db.execute(
        select(UserFocus).where(
            UserFocus.user_id == user.sub,
            UserFocus.focus_id == focus_id,
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must join this focus before switching to it",
        )

    # Deactivate any current active focus for this user+tenant
    await db.execute(
        update(UserFocus)
        .where(
            UserFocus.user_id == user.sub,
            UserFocus.tenant_id == user.tenant_id,
            UserFocus.active == True,  # noqa: E712
        )
        .values(active=False)
    )

    # Activate the target focus
    await db.execute(
        update(UserFocus)
        .where(
            UserFocus.user_id == user.sub,
            UserFocus.focus_id == focus_id,
        )
        .values(active=True)
    )

    await db.commit()

    # Fetch the focus for the response
    focus_result = await db.execute(select(Focus).where(Focus.id == focus_id))
    focus = focus_result.scalar_one_or_none()

    return {"focus": _focus_to_dict(focus) if focus else {"id": str(focus_id)}}


# ---------------------------------------------------------------------------
# GET /focuses/{focus_id}/members
# ---------------------------------------------------------------------------


@router.get("/{focus_id}/members")
async def list_members(
    focus_id: UUID,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List members of a focus with user details."""
    members_stmt = (
        select(UserFocus, Profile)
        .join(Profile, UserFocus.user_id == Profile.id)
        .where(UserFocus.focus_id == focus_id)
    )
    result = await db.execute(members_stmt)
    members = [
        {
            "user_id": str(uf.user_id),
            "email": None,  # TODO: email lives in auth.users, fetch via Supabase Admin API if needed
            "name": p.name,
            "active": uf.active,
            "joined_at": uf.joined_at.isoformat() if uf.joined_at else None,
        }
        for uf, p in result.all()
    ]

    return {"items": members}
