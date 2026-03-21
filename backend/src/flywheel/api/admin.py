"""Admin dashboard endpoint with aggregated platform metrics.

Protected by require_admin dependency -- only tenant admins can access.
Uses get_db_unscoped for cross-tenant visibility (no RLS).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_db_unscoped, require_admin
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import SkillRun, Tenant, User, UserTenant

router = APIRouter(prefix="/admin", tags=["admin"])


class DashboardResponse(BaseModel):
    tenants: int
    users: int
    skill_runs_30d: int
    anonymous_users: int
    onboarding_funnel: dict
    cost_tracking: dict


@router.get("/dashboard", response_model=DashboardResponse)
async def admin_dashboard(
    admin: TokenPayload = Depends(require_admin),
    db: AsyncSession = Depends(get_db_unscoped),
):
    """Admin-only dashboard with platform metrics."""

    # Total counts
    tenant_count = await db.scalar(select(func.count()).select_from(Tenant)) or 0
    user_count = await db.scalar(select(func.count()).select_from(User)) or 0

    # Anonymous users (is_anonymous flag on User model, or users with no email)
    # User model currently has email as NOT NULL, so is_anonymous field check
    if hasattr(User, "is_anonymous"):
        anonymous_count = (
            await db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.is_anonymous == True)  # noqa: E712
            )
            or 0
        )
    else:
        anonymous_count = (
            await db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.email.is_(None))
            )
            or 0
        )

    # Skill runs in last 30 days
    skill_runs_30d = (
        await db.scalar(
            select(func.count())
            .select_from(SkillRun)
            .where(SkillRun.created_at >= func.now() - text("interval '30 days'"))
        )
        or 0
    )

    # Onboarding funnel — counts users by auth provider
    # Anonymous users use Supabase anonymous auth; promoted users have email set
    total_anonymous_ever = (
        await db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.email.is_(None))
        )
        or 0
    )
    # Count anonymous users who have at least one skill run
    anonymous_with_runs = (
        await db.scalar(
            select(func.count(func.distinct(SkillRun.user_id)))
            .select_from(SkillRun)
            .join(User, User.id == SkillRun.user_id)
            .where(User.email.is_(None))
        )
        or 0
    )
    # Promoted = users who originally had no email but now have one
    # Approximation: users with email who have skill runs predating their email being set
    # TODO: add promoted_at timestamp column for accurate tracking
    promoted_users = 0

    onboarding_funnel = {
        "anonymous_created": total_anonymous_ever,
        "anonymous_ran_skill": anonymous_with_runs,
        "promoted_to_account": promoted_users,
    }

    # Cost tracking: sum of cost_estimate from skill_runs in last 30 days
    total_cost_30d = 0.0
    total_tokens_30d = 0

    if hasattr(SkillRun, "cost_estimate"):
        total_cost_30d = (
            await db.scalar(
                select(func.sum(SkillRun.cost_estimate)).where(
                    SkillRun.created_at >= func.now() - text("interval '30 days'")
                )
            )
            or 0.0
        )

    if hasattr(SkillRun, "tokens_used"):
        total_tokens_30d = (
            await db.scalar(
                select(func.sum(SkillRun.tokens_used)).where(
                    SkillRun.created_at >= func.now() - text("interval '30 days'")
                )
            )
            or 0
        )

    cost_tracking = {
        "total_cost_30d_usd": round(float(total_cost_30d), 2),
        "total_tokens_30d": total_tokens_30d,
    }

    return DashboardResponse(
        tenants=tenant_count,
        users=user_count,
        skill_runs_30d=skill_runs_30d,
        anonymous_users=anonymous_count,
        onboarding_funnel=onboarding_funnel,
        cost_tracking=cost_tracking,
    )
