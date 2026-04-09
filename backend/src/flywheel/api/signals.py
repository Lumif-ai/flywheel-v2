"""Signals REST API.

Endpoints:

SIG-01: GET /signals/  -- per-type badge counts for the sidebar navigation

SIGNAL TAXONOMY (SIG-02):
  reply_received   (P1) — New reply received in last 7 days
  followup_overdue (P2) — Follow-up is overdue (next_action_date < today)
  commitment_due   (P2) — Commitment coming due within 7 days
  stale_relationship (P3) — No interaction in 90+ days

TASK SIGNALS (TASK-04):
  tasks_detected   — Tasks in 'detected' status awaiting triage
  tasks_in_review  — Tasks in 'in_review' status awaiting confirmation
  tasks_overdue    — Tasks past due_date that are not done/dismissed

PARTITION CONTRACT: ALL signal queries filter on pipeline_entries with
retired_at IS NULL (active entries only). Retired entries are excluded.

PERFORMANCE: Uses 2 SQL queries (down from 16) with PostgreSQL FILTER clauses
and unnest() to compute all signals across all types in one pass. Results are
cached per tenant with a 60-second TTL. Task signals use a separate user-scoped
cache with the same TTL.
"""

from __future__ import annotations

import datetime
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload

# No prefix — endpoint uses full path segment directly
router = APIRouter(tags=["signals"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RELATIONSHIP_TYPES = ("prospect", "customer", "advisor", "investor")

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
    tasks_detected: int = 0
    tasks_in_review: int = 0
    tasks_overdue: int = 0


# ---------------------------------------------------------------------------
# In-memory TTL cache — signals change slowly (date-based), so 60s is safe
# ---------------------------------------------------------------------------

# Tenant-scoped cache for relationship signals
_signals_cache: dict[str, tuple[float, SignalsResponse]] = {}
_CACHE_TTL = 60  # seconds


def _get_cached(tenant_id: str) -> SignalsResponse | None:
    entry = _signals_cache.get(tenant_id)
    if entry and time.monotonic() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


def _set_cached(tenant_id: str, response: SignalsResponse) -> None:
    _signals_cache[tenant_id] = (time.monotonic(), response)


# User-scoped cache for task signals (separate from tenant-scoped relationship cache)
_task_signals_cache: dict[str, tuple[float, dict]] = {}


def _get_task_cached(key: str) -> dict | None:
    entry = _task_signals_cache.get(key)
    if entry and time.monotonic() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


def _set_task_cached(key: str, value: dict) -> None:
    _task_signals_cache[key] = (time.monotonic(), value)


# ---------------------------------------------------------------------------
# SQL-based signal computation — 2 queries instead of 16
# ---------------------------------------------------------------------------

# Query 1: pipeline-entry signals (followup_overdue, commitment_due, stale)
# Uses unnest() + FILTER to compute all 3 signals x 4 types in one pass.
# next_action_date is DATE (not TIMESTAMP), so comparisons use :today (date).
_ACCOUNT_SIGNALS_SQL = text("""
    SELECT
        t.type AS rel_type,
        COUNT(DISTINCT a.id) FILTER (
            WHERE a.next_action_date IS NOT NULL
              AND a.next_action_date < :today
        ) AS followup_overdue,
        COUNT(DISTINCT a.id) FILTER (
            WHERE a.next_action_note = 'commitment'
              AND a.next_action_date IS NOT NULL
              AND a.next_action_date < :seven_ahead_date
        ) AS commitment_due,
        COUNT(DISTINCT a.id) FILTER (
            WHERE (a.last_activity_at IS NOT NULL AND a.last_activity_at < :ninety_ago)
               OR (a.last_activity_at IS NULL AND a.created_at < :ninety_ago)
        ) AS stale_relationship
    FROM pipeline_entries a,
         unnest(a.relationship_type) AS t(type)
    WHERE a.tenant_id = :tid
      AND a.retired_at IS NULL
      AND a.stage NOT IN ('identified')
      AND t.type IN ('prospect', 'customer', 'advisor', 'investor')
    GROUP BY t.type
""")

# Query 2: reply_received (needs JOIN to activities)
_REPLY_SIGNALS_SQL = text("""
    SELECT
        t.type AS rel_type,
        COUNT(DISTINCT a.id) AS reply_received
    FROM pipeline_entries a
    JOIN activities oa
      ON oa.pipeline_entry_id = a.id
     AND oa.status = 'completed'
     AND oa.direction = 'inbound'
     AND oa.occurred_at > :seven_ago
    CROSS JOIN LATERAL unnest(a.relationship_type) AS t(type)
    WHERE a.tenant_id = :tid
      AND a.retired_at IS NULL
      AND a.stage NOT IN ('identified')
      AND t.type IN ('prospect', 'customer', 'advisor', 'investor')
    GROUP BY t.type
""")

# Query 3: task signals (user-scoped, not relationship-type-scoped)
_TASK_SIGNALS_SQL = text("""
    SELECT
        COUNT(*) FILTER (WHERE status = 'detected') AS tasks_detected,
        COUNT(*) FILTER (WHERE status = 'in_review') AS tasks_in_review,
        COUNT(*) FILTER (
            WHERE due_date IS NOT NULL
              AND due_date < :now
              AND status NOT IN ('done', 'dismissed')
        ) AS tasks_overdue
    FROM tasks
    WHERE tenant_id = :tid
      AND user_id = :uid
""")


async def _compute_all_signals(
    db: AsyncSession,
    tenant_id: str,
    now: datetime.datetime,
) -> dict[str, SignalTypeCounts]:
    """Compute all signal counts for all relationship types in 2 queries."""
    seven_ago = now - datetime.timedelta(days=7)
    ninety_ago = now - datetime.timedelta(days=90)
    seven_ahead = now + datetime.timedelta(days=7)

    today = now.date()
    seven_ahead_date = (now + datetime.timedelta(days=7)).date()

    params = {
        "tid": tenant_id,
        "now": now,
        "today": today,
        "seven_ago": seven_ago,
        "seven_ahead": seven_ahead,
        "seven_ahead_date": seven_ahead_date,
        "ninety_ago": ninety_ago,
    }

    # Initialize all types with zeros
    results: dict[str, dict[str, int]] = {
        rt: {"reply_received": 0, "followup_overdue": 0, "commitment_due": 0, "stale_relationship": 0}
        for rt in RELATIONSHIP_TYPES
    }

    # Query 1: pipeline-entry signals
    acct_result = await db.execute(_ACCOUNT_SIGNALS_SQL, params)
    for row in acct_result:
        rt = row.rel_type
        if rt in results:
            results[rt]["followup_overdue"] = row.followup_overdue or 0
            results[rt]["commitment_due"] = row.commitment_due or 0
            results[rt]["stale_relationship"] = row.stale_relationship or 0

    # Query 2: reply_received
    reply_result = await db.execute(_REPLY_SIGNALS_SQL, params)
    for row in reply_result:
        rt = row.rel_type
        if rt in results:
            results[rt]["reply_received"] = row.reply_received or 0

    return {
        rt: SignalTypeCounts(**counts) for rt, counts in results.items()
    }


async def _compute_task_signals(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    now: datetime.datetime,
) -> dict:
    """Compute task signal counts for a specific user."""
    result = await db.execute(
        _TASK_SIGNALS_SQL, {"tid": tenant_id, "uid": user_id, "now": now}
    )
    row = result.first()
    if row is None:
        return {"tasks_detected": 0, "tasks_in_review": 0, "tasks_overdue": 0}
    return {
        "tasks_detected": row.tasks_detected or 0,
        "tasks_in_review": row.tasks_in_review or 0,
        "tasks_overdue": row.tasks_overdue or 0,
    }


# ---------------------------------------------------------------------------
# SIG-01: GET /signals/
# ---------------------------------------------------------------------------


@router.get("/signals/")
async def get_signals(
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> SignalsResponse:
    """Return per-type badge counts for sidebar navigation.

    PARTITION CONTRACT: retired_at IS NULL enforced in every signal query.
    Retired and identified-only entries are excluded.

    Performance: 2 SQL queries with 60s TTL cache per tenant for relationship
    signals, plus 1 SQL query with 60s TTL cache per user for task signals.
    Task signals always run (even on relationship cache hit) since they are
    user-scoped, not tenant-scoped.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    # Step A: Relationship signals (tenant-scoped cache)
    response = _get_cached(user.tenant_id)
    if response is None:
        all_counts = await _compute_all_signals(db, user.tenant_id, now)

        type_badges: list[TypeBadge] = []
        for rel_type in RELATIONSHIP_TYPES:
            counts = all_counts[rel_type]
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
        response = SignalsResponse(types=type_badges, total=grand_total)
        _set_cached(user.tenant_id, response)

    # Step B: Task signals (user-scoped cache — always runs)
    task_key = f"{user.tenant_id}:{user.sub}"
    task_counts = _get_task_cached(task_key)
    if task_counts is None:
        task_counts = await _compute_task_signals(
            db, user.tenant_id, user.sub, now
        )
        _set_task_cached(task_key, task_counts)

    # Step C: Merge task counts into response
    response.tasks_detected = task_counts["tasks_detected"]
    response.tasks_in_review = task_counts["tasks_in_review"]
    response.tasks_overdue = task_counts["tasks_overdue"]
    return response
