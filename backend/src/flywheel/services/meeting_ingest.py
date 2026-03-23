"""Meeting notes batch ingest with entity matching and stream auto-assignment.

Public API:
    ingest_meeting_notes(notes, tenant_id, user_id, db) -> dict
    compute_density_changes(stream_ids, db) -> list[dict]
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import (
    ContextEntity,
    ContextEntityEntry,
    ContextEntry,
    WorkStream,
    WorkStreamEntity,
)

logger = logging.getLogger(__name__)

# Regex for extracting capitalized multi-word phrases (2+ words starting with uppercase)
_CAPITALIZED_PHRASE_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
# Regex for email domains
_EMAIL_DOMAIN_RE = re.compile(r"@([\w.-]+\.\w+)")
# Regex for @mentions
_AT_MENTION_RE = re.compile(r"@(\w+)")


def _extract_entities(content: str) -> list[str]:
    """Extract candidate entity names from text using simple NLP patterns.

    Finds:
    - Capitalized multi-word phrases (e.g., "Acme Corp", "John Smith")
    - Email domains (e.g., "acme.com" from "john@acme.com")
    - @mentions (e.g., "sarah" from "@sarah")

    Returns deduplicated list of entity name strings.
    """
    entities: set[str] = set()

    # Capitalized multi-word phrases
    for match in _CAPITALIZED_PHRASE_RE.finditer(content):
        phrase = match.group(1).strip()
        if len(phrase) >= 3:
            entities.add(phrase)

    # Email domains
    for match in _EMAIL_DOMAIN_RE.finditer(content):
        domain = match.group(1)
        if domain and not domain.endswith(("gmail.com", "yahoo.com", "hotmail.com", "outlook.com")):
            entities.add(domain)

    # @mentions
    for match in _AT_MENTION_RE.finditer(content):
        mention = match.group(1)
        if len(mention) >= 3:
            entities.add(mention)

    return list(entities)


async def _match_entities(
    entity_names: list[str],
    tenant_id: UUID,
    db: AsyncSession,
) -> list[ContextEntity]:
    """Match extracted entity names against existing ContextEntity rows.

    Uses case-insensitive word-level matching (words >= 3 chars) per the
    32-02 pattern.

    Returns list of matched ContextEntity objects.
    """
    if not entity_names:
        return []

    matched: list[ContextEntity] = []

    for name in entity_names:
        # Split into words >= 3 chars for matching
        words = [w for w in name.split() if len(w) >= 3]
        if not words:
            continue

        # Try exact name match first (case-insensitive)
        stmt = select(ContextEntity).where(
            ContextEntity.tenant_id == tenant_id,
            ContextEntity.name.ilike(name),
        )
        result = await db.execute(stmt)
        exact = result.scalars().all()
        if exact:
            matched.extend(exact)
            continue

        # Try word-level matching: any word matches entity name
        for word in words:
            stmt = select(ContextEntity).where(
                ContextEntity.tenant_id == tenant_id,
                ContextEntity.name.ilike(f"%{word}%"),
            )
            result = await db.execute(stmt)
            word_matches = result.scalars().all()
            for entity in word_matches:
                if entity not in matched:
                    matched.append(entity)

    return matched


async def compute_density_changes(
    stream_ids: list[UUID],
    db: AsyncSession,
) -> list[dict]:
    """Recompute density scores for streams and return old vs new scores.

    Uses the standard density formula:
    entity_count*10 + entry_count*2 + meeting_count*5 - gap_count*10
    Clamped to [0, 100].
    """
    changes = []

    for stream_id in stream_ids:
        # Get current score
        ws = (
            await db.execute(
                select(WorkStream).where(WorkStream.id == stream_id)
            )
        ).scalar_one_or_none()
        if ws is None:
            continue

        old_score = float(ws.density_score) if ws.density_score is not None else 0.0

        # Get linked entity IDs
        linked_stmt = select(WorkStreamEntity.entity_id).where(
            WorkStreamEntity.stream_id == stream_id
        )
        result = await db.execute(linked_stmt)
        entity_ids = [row[0] for row in result.all()]
        entity_count = len(entity_ids)

        if entity_count == 0:
            new_score = 0.0
        else:
            # Count entries per entity
            entry_counts_stmt = (
                select(
                    ContextEntityEntry.entity_id,
                    func.count(ContextEntityEntry.entry_id).label("cnt"),
                )
                .where(ContextEntityEntry.entity_id.in_(entity_ids))
                .group_by(ContextEntityEntry.entity_id)
            )
            entry_counts_result = await db.execute(entry_counts_stmt)
            entity_entry_counts = {row[0]: row[1] for row in entry_counts_result.all()}
            entry_count = sum(entity_entry_counts.values())

            # Count meeting entries
            meeting_stmt = (
                select(func.count())
                .select_from(ContextEntityEntry)
                .join(ContextEntry, ContextEntry.id == ContextEntityEntry.entry_id)
                .where(
                    ContextEntityEntry.entity_id.in_(entity_ids),
                    ContextEntry.source.ilike("%meeting%"),
                )
            )
            meeting_result = await db.execute(meeting_stmt)
            meeting_count = meeting_result.scalar() or 0

            # Gap count: entities with < 3 entries
            gap_count = sum(
                1 for eid in entity_ids
                if entity_entry_counts.get(eid, 0) < 3
            )

            raw_score = (entity_count * 10) + (entry_count * 2) + (meeting_count * 5) - (gap_count * 10)
            new_score = float(max(0, min(100, raw_score)))

        # Update the stream
        await db.execute(
            update(WorkStream)
            .where(WorkStream.id == stream_id)
            .values(density_score=Decimal(str(new_score)))
        )

        changes.append({
            "stream_id": str(stream_id),
            "old_score": old_score,
            "new_score": new_score,
        })

    return changes


async def ingest_meeting_notes(
    notes: list[dict],
    tenant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> dict:
    """Batch ingest meeting notes into context entries with entity matching.

    For each note:
    1. Extract entities using simple NLP
    2. Create ContextEntry row
    3. Match entities against existing ContextEntity rows
    4. Link entries to matched entities via ContextEntityEntry
    5. Find stream assignments via WorkStreamEntity links

    Args:
        notes: List of {content, source, title} dicts.
        tenant_id: Tenant UUID.
        user_id: User UUID.
        db: Async database session.

    Returns:
        Dict with total_processed, entries_created, stream_assignments, density_changes.
    """
    total_processed = 0
    entries_created = 0
    stream_assignments: list[dict] = []
    affected_stream_ids: set[UUID] = set()

    for idx, note in enumerate(notes):
        content = note.get("content", "")
        source = note.get("source", "paste")
        title = note.get("title")

        if not content.strip():
            total_processed += 1
            continue

        # Extract entities from note content
        entity_names = _extract_entities(content)

        # Create ContextEntry
        ce = ContextEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            file_name="meetings.md",
            source=source,
            detail=title or "Meeting notes",
            content=content,
            confidence="medium",
            metadata_={},
        )
        db.add(ce)
        await db.flush()

        entries_created += 1
        total_processed += 1

        # Match extracted entities against existing ContextEntity rows
        matched_entities = await _match_entities(entity_names, tenant_id, db)

        # Link entry to matched entities
        for entity in matched_entities:
            # Check if link already exists
            existing_link = (
                await db.execute(
                    select(ContextEntityEntry).where(
                        ContextEntityEntry.entity_id == entity.id,
                        ContextEntityEntry.entry_id == ce.id,
                    )
                )
            ).scalar_one_or_none()

            if not existing_link:
                cee = ContextEntityEntry(
                    entity_id=entity.id,
                    entry_id=ce.id,
                    tenant_id=tenant_id,
                    mention_type="meeting_ingest",
                )
                db.add(cee)

            # Find stream assignments for this entity
            stream_links = (
                await db.execute(
                    select(WorkStreamEntity).where(
                        WorkStreamEntity.entity_id == entity.id
                    )
                )
            ).scalars().all()

            for link in stream_links:
                affected_stream_ids.add(link.stream_id)
                # Get stream name for the assignment record
                ws = (
                    await db.execute(
                        select(WorkStream.name).where(
                            WorkStream.id == link.stream_id
                        )
                    )
                ).scalar_one_or_none()
                if ws:
                    stream_assignments.append({
                        "stream_name": ws,
                        "note_index": idx,
                    })

    # Compute density changes for affected streams
    density_changes = []
    if affected_stream_ids:
        density_changes = await compute_density_changes(
            list(affected_stream_ids), db
        )

    await db.commit()

    return {
        "total_processed": total_processed,
        "entries_created": entries_created,
        "stream_assignments": stream_assignments,
        "density_changes": density_changes,
    }
