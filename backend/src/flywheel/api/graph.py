"""Context graph API: traversal, entity listing, alias management, backfill.

4 endpoints:
- GET /context/graph              -- N-hop traversal from a starting entity
- GET /context/graph/entities     -- paginated entity listing with search
- PUT /context/graph/aliases      -- tenant alias map management (admin)
- POST /context/graph/backfill    -- backfill graph for existing entries (admin)
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_admin, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import ContextEntity, ContextRelationship, Tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/context/graph", tags=["graph"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _paginated_response(items: list, total: int, offset: int, limit: int) -> dict:
    """Build a standard paginated response envelope."""
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


# ---------------------------------------------------------------------------
# GET /context/graph -- N-hop traversal
# ---------------------------------------------------------------------------


@router.get("")
async def query_graph(
    entity: str = Query(..., min_length=1),
    hops: int = Query(2, ge=1, le=3),
    entity_type: str | None = Query(None),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Return entities and relationships within N hops of a starting entity."""
    tid = str(user.tenant_id)

    # Step 1: Find starting entity by exact ILIKE on name
    start_query = select(ContextEntity).where(
        ContextEntity.name.ilike(entity),
    )
    if entity_type is not None:
        start_query = start_query.where(ContextEntity.entity_type == entity_type)
    start_query = start_query.limit(1)

    result = await db.execute(start_query)
    start = result.scalar_one_or_none()

    # Step 2: Check aliases array if not found
    if start is None:
        alias_query = select(ContextEntity).where(
            ContextEntity.aliases.any(entity.lower()),
        )
        if entity_type is not None:
            alias_query = alias_query.where(
                ContextEntity.entity_type == entity_type
            )
        alias_query = alias_query.limit(1)
        result = await db.execute(alias_query)
        start = result.scalar_one_or_none()

    # Step 3: Check tenant settings entity_aliases map
    if start is None:
        tenant_result = await db.execute(
            select(Tenant.settings).where(Tenant.id == user.tenant_id)
        )
        tenant_settings = tenant_result.scalar_one_or_none() or {}
        entity_aliases = tenant_settings.get("entity_aliases", {})
        canonical_name = entity_aliases.get(entity) or entity_aliases.get(
            entity.lower()
        )
        if canonical_name:
            canon_query = select(ContextEntity).where(
                ContextEntity.name.ilike(canonical_name),
            ).limit(1)
            result = await db.execute(canon_query)
            start = result.scalar_one_or_none()

    # Step 4: Not found at all
    if start is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity '{entity}' not found",
        )

    # Step 5: Recursive CTE traversal
    traversal_sql = text("""
        WITH RECURSIVE graph AS (
            SELECT id, name, entity_type, 0 AS depth
            FROM context_entities
            WHERE id = :start_id AND tenant_id = :tid

            UNION ALL

            SELECT e2.id, e2.name, e2.entity_type, g.depth + 1
            FROM graph g
            JOIN context_relationships r
                ON (r.entity_a_id = g.id OR r.entity_b_id = g.id)
                AND r.tenant_id = :tid
            JOIN context_entities e2
                ON e2.id = CASE
                    WHEN r.entity_a_id = g.id THEN r.entity_b_id
                    ELSE r.entity_a_id
                END
                AND e2.tenant_id = :tid
            WHERE g.depth < :max_hops
        )
        SELECT DISTINCT id, name, entity_type, MIN(depth) AS depth
        FROM graph
        GROUP BY id, name, entity_type
        LIMIT 200
    """)

    traversal_result = await db.execute(
        traversal_sql,
        {"start_id": str(start.id), "tid": tid, "max_hops": hops},
    )
    rows = traversal_result.fetchall()

    # Build node list with mention_count from the entities table
    node_ids = [row.id for row in rows]
    nodes = []
    if node_ids:
        # Fetch mention counts for all found nodes
        mention_stmt = select(
            ContextEntity.id, ContextEntity.mention_count
        ).where(ContextEntity.id.in_(node_ids))
        mention_result = await db.execute(mention_stmt)
        mention_map = {str(r.id): r.mention_count for r in mention_result.fetchall()}

        for row in rows:
            nodes.append({
                "id": str(row.id),
                "name": row.name,
                "entity_type": row.entity_type,
                "depth": row.depth,
                "mention_count": mention_map.get(str(row.id), 1),
            })

    # Step 6: Fetch relationships between found node IDs
    edges = []
    if node_ids:
        edge_stmt = select(ContextRelationship).where(
            ContextRelationship.entity_a_id.in_(node_ids)
            | ContextRelationship.entity_b_id.in_(node_ids),
        )
        edge_result = await db.execute(edge_stmt)
        for r in edge_result.scalars().all():
            edges.append({
                "id": str(r.id),
                "entity_a_id": str(r.entity_a_id),
                "entity_b_id": str(r.entity_b_id),
                "relationship": r.relationship,
                "confidence": r.confidence,
                "directional": r.directional,
                "source_entry_id": str(r.source_entry_id) if r.source_entry_id else None,
            })

    # Step 7: Return response
    return {
        "nodes": nodes,
        "edges": edges,
        "root": str(start.id),
    }


# ---------------------------------------------------------------------------
# GET /context/graph/entities -- entity listing with search
# ---------------------------------------------------------------------------


@router.get("/entities")
async def list_entities(
    search: str | None = Query(None),
    entity_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List and search entities for the current tenant."""
    base = select(ContextEntity)

    if search is not None:
        base = base.where(ContextEntity.name.ilike(f"%{search}%"))

    if entity_type is not None:
        base = base.where(ContextEntity.entity_type == entity_type)

    # Count total
    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch page
    data_stmt = (
        base.order_by(
            ContextEntity.mention_count.desc(),
            ContextEntity.last_seen_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(data_stmt)
    entities = result.scalars().all()

    items = [
        {
            "id": str(e.id),
            "name": e.name,
            "entity_type": e.entity_type,
            "aliases": e.aliases or [],
            "mention_count": e.mention_count,
            "first_seen_at": e.first_seen_at.isoformat() if e.first_seen_at else None,
            "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
        }
        for e in entities
    ]

    return _paginated_response(items, total, offset, limit)
