"""Entity extraction pipeline -- sync extraction and relationship detection.

Extracts entities (companies, people, pain points, products, roles, topics)
from structured context entry fields using deterministic regex rules.
Infers relationships from co-occurrence patterns within single entries.

All extraction is synchronous (<5ms target). The async process_entry_for_graph()
orchestrator handles DB upserts and is called from storage.append_entry().
"""

from __future__ import annotations

import logging
import re
import time
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import ContextRelationship
from flywheel.services.entity_normalization import (
    find_or_create_entity,
    link_entity_to_entry,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class ExtractedEntity(NamedTuple):
    name: str
    entity_type: str  # company, person, pain_point, product, role, topic
    source_field: str  # detail, source, content


class ExtractedRelationship(NamedTuple):
    entity_a_name: str
    entity_a_type: str
    relationship: str  # works_at, competes_with, has_pain_point, discussed, etc.
    entity_b_name: str
    entity_b_type: str


# ---------------------------------------------------------------------------
# File name -> entity type hints
# ---------------------------------------------------------------------------

_FILE_TYPE_HINTS: dict[str, str] = {
    "company-intel": "company",
    "contacts": "person",
    "pain-points": "pain_point",
    "competitive-intel": "company",
    "meeting-intel": "topic",
}

# ---------------------------------------------------------------------------
# Detail field regex patterns (case-insensitive)
# ---------------------------------------------------------------------------

_DETAIL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?:company|org|organization|vendor|partner|client)[:\s]+(.+)", re.IGNORECASE), "company"),
    (re.compile(r"(?:contact|person|attendee|speaker|name)[:\s]+(.+)", re.IGNORECASE), "person"),
    (re.compile(r"(?:pain[- ]?point|challenge|problem|issue)[:\s]+(.+)", re.IGNORECASE), "pain_point"),
    (re.compile(r"(?:product|tool|platform|software|service)[:\s]+(.+)", re.IGNORECASE), "product"),
    (re.compile(r"(?:role|title|position)[:\s]+(.+)", re.IGNORECASE), "role"),
]

# Content field: extract quoted entities starting with uppercase
_QUOTED_ENTITY_RE = re.compile(r'"([A-Z][^"]+)"')


# ---------------------------------------------------------------------------
# Sync extraction functions
# ---------------------------------------------------------------------------


def extract_entities_sync(entry: object) -> list[ExtractedEntity]:
    """Fast deterministic entity extraction from structured entry fields.

    Targets <5ms execution. Extracts from:
    1. File name hints (e.g., company-intel -> company type context)
    2. Detail field regex patterns
    3. Content field quoted names

    Args:
        entry: Object with file_name, detail, content, source attributes.

    Returns:
        List of ExtractedEntity tuples.
    """
    entities: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()  # (name_lower, entity_type) dedup

    def _add(name: str, entity_type: str, source_field: str) -> None:
        clean = name.strip()
        if not clean:
            return
        key = (clean.lower(), entity_type)
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(clean, entity_type, source_field))

    # 1. Detail field regex patterns
    detail = getattr(entry, "detail", None) or ""
    if detail:
        for pattern, etype in _DETAIL_PATTERNS:
            match = pattern.search(detail)
            if match:
                _add(match.group(1), etype, "detail")

    # 2. Content field: quoted entity names (typically company/org references)
    content = getattr(entry, "content", None) or ""
    if content:
        for match in _QUOTED_ENTITY_RE.finditer(content):
            quoted_name = match.group(1)
            # Quoted names in content are typically company/org references
            # regardless of file type (the file hint applies to primary entities)
            _add(quoted_name, "company", "content")

    return entities


def extract_relationships_sync(
    entry: object, entities: list[ExtractedEntity]
) -> list[ExtractedRelationship]:
    """Infer relationships from co-occurrence of entities in a single entry.

    Rules:
    - person + company -> (person, works_at, company)
    - company + pain_point -> (company, has_pain_point, pain_point)
    - two companies in competitive-* file -> (company_a, competes_with, company_b)
    - person + topic in meeting-* file -> (person, discussed, topic)

    Args:
        entry: Object with file_name attribute.
        entities: Entities extracted from the same entry.

    Returns:
        List of ExtractedRelationship tuples.
    """
    relationships: list[ExtractedRelationship] = []
    file_name = getattr(entry, "file_name", "") or ""

    by_type: dict[str, list[ExtractedEntity]] = {}
    for e in entities:
        by_type.setdefault(e.entity_type, []).append(e)

    persons = by_type.get("person", [])
    companies = by_type.get("company", [])
    pain_points = by_type.get("pain_point", [])
    topics = by_type.get("topic", [])

    # person + company -> works_at
    for person in persons:
        for company in companies:
            relationships.append(
                ExtractedRelationship(
                    person.name, "person", "works_at", company.name, "company"
                )
            )

    # company + pain_point -> has_pain_point
    for company in companies:
        for pp in pain_points:
            relationships.append(
                ExtractedRelationship(
                    company.name, "company", "has_pain_point", pp.name, "pain_point"
                )
            )

    # two companies in competitive file -> competes_with
    if "competitive" in file_name and len(companies) >= 2:
        for i, ca in enumerate(companies):
            for cb in companies[i + 1 :]:
                relationships.append(
                    ExtractedRelationship(
                        ca.name, "company", "competes_with", cb.name, "company"
                    )
                )

    # person + topic in meeting file -> discussed
    if "meeting" in file_name:
        for person in persons:
            for topic in topics:
                relationships.append(
                    ExtractedRelationship(
                        person.name, "person", "discussed", topic.name, "topic"
                    )
                )

    return relationships


# ---------------------------------------------------------------------------
# Async orchestrator
# ---------------------------------------------------------------------------


async def process_entry_for_graph(
    session: AsyncSession,
    entry: object,
    tenant_id: str,
) -> None:
    """Extract entities and relationships from an entry and persist to graph tables.

    Orchestration:
    1. Extract entities (sync, fast)
    2. Upsert each entity via find_or_create_entity (dedup)
    3. Link each entity to the entry
    4. Extract relationships (sync, fast)
    5. Persist relationships with duplicate check

    Never raises -- extraction failures are logged and swallowed to avoid
    blocking the write path.
    """
    start = time.monotonic()
    try:
        # 1. Extract entities
        entities = extract_entities_sync(entry)
        if not entities:
            return

        entry_id = getattr(entry, "id", None)
        if entry_id is None:
            logger.warning("Entry has no id, skipping graph extraction")
            return

        # 2-3. Upsert entities and link to entry
        entity_db_map: dict[tuple[str, str], object] = {}  # (name, type) -> DB entity
        for ext_entity in entities:
            db_entity = await find_or_create_entity(
                session,
                tenant_id,
                ext_entity.name,
                ext_entity.entity_type,
                ext_entity.source_field,
            )
            entity_db_map[(ext_entity.name.strip().lower(), ext_entity.entity_type)] = db_entity

            await link_entity_to_entry(
                session,
                db_entity.id,
                entry_id,
                tenant_id,
                ext_entity.source_field,
            )

        # 4. Extract relationships
        rels = extract_relationships_sync(entry, entities)

        # 5. Persist relationships (check for duplicates via SELECT before INSERT)
        tid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id

        # Read focus_id from session config (set by RLS middleware when active)
        focus_id_value = None
        try:
            from sqlalchemy import text as _sa_text
            focus_result = await session.execute(
                _sa_text("SELECT current_setting('app.focus_id', true)")
            )
            focus_id_str = focus_result.scalar()
            if focus_id_str:
                focus_id_value = UUID(focus_id_str)
        except Exception:
            pass  # No focus_id in session, relationships remain unscoped

        for rel in rels:
            a_key = (rel.entity_a_name.strip().lower(), rel.entity_a_type)
            b_key = (rel.entity_b_name.strip().lower(), rel.entity_b_type)
            db_a = entity_db_map.get(a_key)
            db_b = entity_db_map.get(b_key)
            if db_a is None or db_b is None:
                continue

            # Check for existing relationship to avoid duplicates
            existing_stmt = select(ContextRelationship).where(
                ContextRelationship.tenant_id == tid,
                ContextRelationship.entity_a_id == db_a.id,
                ContextRelationship.entity_b_id == db_b.id,
                ContextRelationship.relationship == rel.relationship,
            ).limit(1)
            existing_result = await session.execute(existing_stmt)
            if existing_result.scalar_one_or_none() is not None:
                continue

            new_rel = ContextRelationship(
                tenant_id=tid,
                entity_a_id=db_a.id,
                entity_b_id=db_b.id,
                relationship=rel.relationship,
                source_entry_id=entry_id,
                focus_id=focus_id_value,
            )
            session.add(new_rel)

        await session.flush()

        elapsed = time.monotonic() - start
        if elapsed > 0.05:
            logger.warning(
                "Graph extraction took %.0fms for entry %s",
                elapsed * 1000,
                entry_id,
            )
        else:
            logger.debug(
                "Graph extraction completed in %.1fms for entry %s",
                elapsed * 1000,
                entry_id,
            )

    except Exception:
        logger.warning(
            "Graph extraction failed for entry %s",
            getattr(entry, "id", "unknown"),
            exc_info=True,
        )
