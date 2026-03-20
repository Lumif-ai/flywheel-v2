"""Rate limiting middleware and dependency guards.

Provides:
- slowapi Limiter with user-id-or-IP key extraction
- check_anonymous_run_limit: DB-backed 3-run limit for anonymous users
- check_concurrent_run_limit: DB-backed 3-concurrent-run limit per user
"""

from __future__ import annotations

import logging
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import SkillRun

logger = logging.getLogger(__name__)


def get_user_id_or_ip(request: Request) -> str:
    """Extract user ID from JWT Authorization header, fallback to IP.

    Used as the slowapi key_func -- identifies who is making the request
    for per-user rate limiting.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
            user_id = payload.get("sub")
            if user_id:
                return str(user_id)
        except jwt.PyJWTError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=get_user_id_or_ip)


async def check_anonymous_run_limit(
    user_id: UUID,
    is_anonymous: bool,
    db: AsyncSession,
) -> None:
    """Enforce 3-run limit for anonymous users.

    Counts all SkillRun records for the user. If the user is anonymous
    and has >= 3 runs, raises 429.
    """
    if not is_anonymous:
        return

    count_q = select(func.count(SkillRun.id)).where(SkillRun.user_id == user_id)
    total = (await db.execute(count_q)).scalar() or 0

    if total >= 3:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "AnonymousRunLimitExceeded",
                "message": "Anonymous users are limited to 3 skill runs. Sign up to continue.",
                "code": 429,
            },
        )


async def check_concurrent_run_limit(
    user_id: UUID,
    db: AsyncSession,
) -> None:
    """Enforce max 3 concurrent (pending/running) runs per user.

    Counts SkillRun records with status IN ('pending', 'running').
    If >= 3, raises 429 with Retry-After header.
    """
    count_q = (
        select(func.count(SkillRun.id))
        .where(SkillRun.user_id == user_id)
        .where(SkillRun.status.in_(["pending", "running"]))
    )
    active = (await db.execute(count_q)).scalar() or 0

    if active >= 3:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "ConcurrentRunLimitExceeded",
                "message": "Maximum 3 concurrent runs. Wait for a run to complete.",
                "code": 429,
            },
            headers={"Retry-After": "30"},
        )
