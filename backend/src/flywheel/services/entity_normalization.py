"""Entity normalization service -- canonical name resolution and entity dedup.

Provides utilities to normalize entity names (strip suffixes, lowercase, collapse
whitespace), resolve aliases, and find-or-create entities idempotently.

All async functions receive an AsyncSession that is already tenant-scoped via RLS.
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import ContextEntity, ContextEntityEntry, Tenant

logger = logging.getLogger(__name__)

# Company name suffixes to strip during normalization (case-insensitive).
# Order matters: longer suffixes first to avoid partial matches.
_COMPANY_SUFFIXES = re.compile(
    r"\s*\b(corporation|company|corp|inc|llc|ltd|co)\.?\s*$",
    re.IGNORECASE,
)


def normalize_entity_name(name: str) -> str:
    """Normalize an entity name to its canonical form.

    Steps:
    1. Strip leading/trailing whitespace
    2. Lowercase
    3. Remove trailing company suffixes (Corp, Inc, LLC, Ltd, Co, etc.)
    4. Collapse multiple spaces to single space
    5. Strip again (suffix removal may leave trailing space)

    Examples:
        "  Acme Corporation  " -> "acme"
        "Beta Inc." -> "beta"
        "  John   Smith  " -> "john smith"
    """
    result = name.strip().lower()
    result = _COMPANY_SUFFIXES.sub("", result)
    result = re.sub(r"\s+", " ", result).strip()
    return result


async def resolve_alias(
    session: AsyncSession,
    tenant_id: str,
    name: str,
    entity_type: str,
) -> ContextEntity | None:
    """Resolve a name to an existing entity via exact match or alias lookup.

    Resolution order:
    1. Exact match on context_entities.name (normalized)
    2. Alias array containment (@>) on context_entities.aliases
    3. Tenant settings entity_aliases map (if configured)

    Returns the matching ContextEntity or None.
    """
    normalized = normalize_entity_name(name)
    tid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id

    # 1. Exact match on canonical name
    stmt = select(ContextEntity).where(
        ContextEntity.tenant_id == tid,
        ContextEntity.name == normalized,
        ContextEntity.entity_type == entity_type,
    )
    result = await session.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is not None:
        return entity

    # 2. Alias array containment: check if normalized name is in any entity's aliases
    stmt = select(ContextEntity).where(
        ContextEntity.tenant_id == tid,
        ContextEntity.entity_type == entity_type,
        ContextEntity.aliases.op("@>")(text(f"ARRAY['{normalized}']::text[]")),
    )
    result = await session.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is not None:
        return entity

    # 3. Check tenant settings for manual alias mappings
    stmt = select(Tenant.settings).where(Tenant.id == tid)
    result = await session.execute(stmt)
    settings = result.scalar_one_or_none()
    if settings and isinstance(settings, dict):
        entity_aliases = settings.get("entity_aliases", {})
        canonical = entity_aliases.get(normalized)
        if canonical:
            # Look up the canonical name
            stmt = select(ContextEntity).where(
                ContextEntity.tenant_id == tid,
                ContextEntity.name == canonical,
                ContextEntity.entity_type == entity_type,
            )
            result = await session.execute(stmt)
            entity = result.scalar_one_or_none()
            if entity is not None:
                return entity

    return None


async def find_or_create_entity(
    session: AsyncSession,
    tenant_id: str,
    name: str,
    entity_type: str,
    source_field: str = "detail",
) -> ContextEntity:
    """Find an existing entity or create a new one. Idempotent.

    Uses SELECT ... FOR UPDATE on match to prevent race conditions when
    multiple workers process the same entity concurrently.

    If found: increments mention_count and updates last_seen_at.
    If not found: creates a new entity with the normalized name.

    Returns the ContextEntity (existing or newly created).
    """
    normalized = normalize_entity_name(name)
    tid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id

    # Try resolve via alias first
    existing = await resolve_alias(session, str(tid), normalized, entity_type)
    if existing is not None:
        # Lock and update -- use FOR UPDATE to prevent concurrent increments
        stmt = (
            select(ContextEntity)
            .where(ContextEntity.id == existing.id)
            .with_for_update()
        )
        result = await session.execute(stmt)
        locked = result.scalar_one()
        locked.mention_count = (locked.mention_count or 1) + 1
        locked.last_seen_at = func.now()
        await session.flush()
        logger.debug(
            "Entity found: %s (%s) mention_count=%d",
            locked.name,
            entity_type,
            locked.mention_count,
        )
        return locked

    # Not found -- create new entity
    entity = ContextEntity(
        tenant_id=tid,
        name=normalized,
        entity_type=entity_type,
    )
    session.add(entity)
    await session.flush()
    logger.info("Entity created: %s (%s)", normalized, entity_type)
    return entity


async def link_entity_to_entry(
    session: AsyncSession,
    entity_id: UUID,
    entry_id: UUID,
    tenant_id: str,
    mention_type: str = "explicit",
) -> None:
    """Link an entity to a context entry (idempotent).

    Inserts into context_entity_entries with ON CONFLICT DO NOTHING
    so duplicate links are silently ignored.
    """
    tid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
    await session.execute(
        text(
            """
            INSERT INTO context_entity_entries (entity_id, entry_id, tenant_id, mention_type)
            VALUES (:entity_id, :entry_id, :tenant_id, :mention_type)
            ON CONFLICT (entity_id, entry_id) DO NOTHING
            """
        ),
        {
            "entity_id": entity_id,
            "entry_id": entry_id,
            "tenant_id": tid,
            "mention_type": mention_type,
        },
    )
    await session.flush()
