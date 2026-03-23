"""Team onboarding endpoints: stream listing and joining for new team members.

Endpoints:
- GET  /team-onboarding/streams      -- list team streams with counts and join prompt
- POST /team-onboarding/join-streams -- join selected streams (stores in user settings)
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.services.team_onboarding import get_team_streams_for_join, join_streams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/team-onboarding", tags=["team-onboarding"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class JoinStreamsRequest(BaseModel):
    stream_ids: list[str] = Field(..., min_length=1)


class StreamInfo(BaseModel):
    id: str
    name: str
    description: str
    density_score: float
    entity_count: int
    entry_count: int
    member_count: int
    user_joined: bool


class StreamsResponse(BaseModel):
    streams: list[StreamInfo]
    prompt: str


class JoinStreamsResponse(BaseModel):
    joined: list[str]
    message: str


# ---------------------------------------------------------------------------
# GET /team-onboarding/streams
# ---------------------------------------------------------------------------


@router.get("/streams", response_model=StreamsResponse)
async def list_team_streams(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List the team's existing work streams with entity/entry/member counts.

    Returns streams with a natural language prompt for joining.
    """
    streams = await get_team_streams_for_join(db, user.tenant_id, user.sub)

    stream_names = [s["name"] for s in streams]
    if stream_names:
        names_str = ", ".join(stream_names)
        prompt = f"Your team is tracking {names_str}. Which are you involved in?"
    else:
        prompt = "Your team hasn't set up any work streams yet."

    return StreamsResponse(
        streams=[StreamInfo(**s) for s in streams],
        prompt=prompt,
    )


# ---------------------------------------------------------------------------
# POST /team-onboarding/join-streams
# ---------------------------------------------------------------------------


@router.post("/join-streams", response_model=JoinStreamsResponse)
async def join_team_streams(
    body: JoinStreamsRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Join selected work streams by storing them in user settings.

    The frontend uses joined_streams to tailor the briefing experience.
    """
    stream_uuids = [UUID(sid) for sid in body.stream_ids]
    joined = await join_streams(db, user.tenant_id, user.sub, stream_uuids)

    return JoinStreamsResponse(
        joined=joined,
        message=f"You've joined {len(joined)} stream{'s' if len(joined) != 1 else ''}",
    )
