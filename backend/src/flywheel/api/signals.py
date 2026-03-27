"""Signals REST API.

Endpoints:

SIG-01: GET /signals/  -- per-type badge counts for the sidebar navigation

SIGNAL TAXONOMY (SIG-02):
  reply_received   (P1) — New reply received in last 7 days
  followup_overdue (P2) — Follow-up is overdue (next_action_due < now)
  commitment_due   (P2) — Commitment coming due within 7 days
  stale_relationship (P3) — No interaction in 90+ days

PARTITION CONTRACT: ALL signal queries MUST include `Account.graduated_at.isnot(None)`.
Pipeline-only accounts (graduated_at IS NULL) are always excluded from signal counts.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Account, OutreachActivity

# No prefix — endpoint uses full path segment directly
router = APIRouter(tags=["signals"])

# ---------------------------------------------------------------------------
# Constants: signal taxonomy (SIG-02)
# ---------------------------------------------------------------------------

SIGNAL_TYPES: dict[str, dict] = {
    "reply_received": {
        "priority": 1,
        "description": "New reply received",
    },
    "followup_overdue": {
        "priority": 2,
        "description": "Follow-up is overdue",
    },
    "commitment_due": {
        "priority": 2,
        "description": "Commitment coming due",
    },
    "stale_relationship": {
        "priority": 3,
        "description": "No interaction in 90+ days",
    },
}

RELATIONSHIP_TYPES = ["prospect", "customer", "advisor", "investor"]

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SignalTypeCounts(BaseModel):
    reply_received: int
    followup_overdue: int
    commitment_due: int
    stale_relationship: int


class TypeBadge(BaseModel):
    type: str
    label: str
    total_signals: int
    counts: SignalTypeCounts


class SignalsResponse(BaseModel):
    types: list[TypeBadge]
    total: int


# ---------------------------------------------------------------------------
# Signal computation helpers
# ---------------------------------------------------------------------------


async def _compute_signals_for_type(
    db: AsyncSession,
    tenant_id,
    type_value: str,
    now: datetime.datetime,
) -> SignalTypeCounts:
    """Compute all signal counts for one relationship type.

    CRITICAL: ALL queries include graduated_at.isnot(None) partition predicate.
    """
    # Base partition + type filters applied to every signal query
    base_filters = [
        Account.tenant_id == tenant_id,
        Account.graduated_at.isnot(None),
        Account.relationship_type.any(type_value),
    ]

    seven_days_ago = now - datetime.timedelta(days=7)
    ninety_days_ago = now - datetime.timedelta(days=90)
    seven_days_ahead = now + datetime.timedelta(days=7)

    # --- reply_received ---
    # Accounts with an outreach activity status="replied" created in last 7 days
    reply_stmt = (
        select(func.count(func.distinct(OutreachActivity.account_id)))
        .select_from(OutreachActivity)
        .join(Account, Account.id == OutreachActivity.account_id)
        .where(
            *base_filters,
            OutreachActivity.status == "replied",
            OutreachActivity.created_at > seven_days_ago,
        )
    )
    reply_result = await db.execute(reply_stmt)
    reply_count: int = reply_result.scalar_one() or 0

    # --- followup_overdue ---
    # Accounts with next_action_due IS NOT NULL AND next_action_due < now
    followup_stmt = (
        select(func.count())
        .select_from(Account)
        .where(
            *base_filters,
            Account.next_action_due.isnot(None),
            Account.next_action_due < now,
        )
    )
    followup_result = await db.execute(followup_stmt)
    followup_count: int = followup_result.scalar_one() or 0

    # --- commitment_due ---
    # Accounts where next_action_type='commitment' AND next_action_due within 7 days
    commitment_stmt = (
        select(func.count())
        .select_from(Account)
        .where(
            *base_filters,
            Account.next_action_type == "commitment",
            Account.next_action_due.isnot(None),
            Account.next_action_due < seven_days_ahead,
        )
    )
    commitment_result = await db.execute(commitment_stmt)
    commitment_count: int = commitment_result.scalar_one() or 0

    # --- stale_relationship ---
    # Accounts with last_interaction_at < 90 days ago OR
    # last_interaction_at IS NULL AND created_at < 90 days ago
    stale_stmt = (
        select(func.count())
        .select_from(Account)
        .where(
            *base_filters,
        )
        .where(
            # stale if interacted but long ago, or never interacted and account is old
            (
                Account.last_interaction_at.isnot(None)
                & (Account.last_interaction_at < ninety_days_ago)
            )
            | (
                Account.last_interaction_at.is_(None)
                & (Account.created_at < ninety_days_ago)
            )
        )
    )
    stale_result = await db.execute(stale_stmt)
    stale_count: int = stale_result.scalar_one() or 0

    return SignalTypeCounts(
        reply_received=reply_count,
        followup_overdue=followup_count,
        commitment_due=commitment_count,
        stale_relationship=stale_count,
    )


# ---------------------------------------------------------------------------
# SIG-01: GET /signals/
# ---------------------------------------------------------------------------


@router.get("/signals/")
async def get_signals(
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> SignalsResponse:
    """Return per-type badge counts for sidebar navigation.

    PARTITION CONTRACT: graduated_at.isnot(None) enforced in every signal query.
    Pipeline-only accounts (graduated_at IS NULL) are excluded.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    type_badges: list[TypeBadge] = []
    for rel_type in RELATIONSHIP_TYPES:
        counts = await _compute_signals_for_type(db, user.tenant_id, rel_type, now)
        total_signals = (
            counts.reply_received
            + counts.followup_overdue
            + counts.commitment_due
            + counts.stale_relationship
        )
        type_badges.append(
            TypeBadge(
                type=rel_type,
                label=rel_type.capitalize() + "s",
                total_signals=total_signals,
                counts=counts,
            )
        )

    grand_total = sum(b.total_signals for b in type_badges)
    return SignalsResponse(types=type_badges, total=grand_total)
