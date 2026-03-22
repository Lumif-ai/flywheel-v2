"""Onboarding stream services: Haiku-powered work stream parser and batch creator.

Public API:
    parse_work_streams(input_text) -> list[dict]
    create_streams_batch(streams, tenant_id, user_id, db) -> list[dict]
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import (
    ContextEntity,
    ContextEntityEntry,
    ContextEntry,
    WorkStream,
    WorkStreamEntity,
)

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

_PARSE_SYSTEM_PROMPT = """Parse the user's work description into 2-4 distinct work streams. Return JSON array: [{\"name\": string, \"description\": string, \"entity_seeds\": string[]}]. entity_seeds are key entities (company names, people, topics) related to each stream. Return ONLY valid JSON, no markdown fences or extra text."""


async def parse_work_streams(input_text: str) -> list[dict]:
    """Parse natural language into 2-4 structured work streams using Haiku.

    Falls back to simple splitting by comma/and if LLM call fails.

    Args:
        input_text: Natural language like "hiring engineers, closing Acme deal, Series A"

    Returns:
        List of dicts with name, description, entity_seeds keys.
    """
    if anthropic is None:
        logger.warning("anthropic SDK not available, using fallback parser")
        return _fallback_parse(input_text)

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)
        response = await client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=1024,
            system=_PARSE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": input_text}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        parsed = json.loads(raw)

        if not isinstance(parsed, list) or len(parsed) < 1:
            logger.warning("Haiku returned invalid structure, using fallback")
            return _fallback_parse(input_text)

        # Validate and normalize each item
        streams = []
        for item in parsed[:4]:  # Cap at 4
            if not isinstance(item, dict) or "name" not in item:
                continue
            streams.append({
                "name": item["name"],
                "description": item.get("description", ""),
                "entity_seeds": item.get("entity_seeds", []),
            })

        if len(streams) < 2:
            logger.warning("Haiku returned fewer than 2 streams, using fallback")
            return _fallback_parse(input_text)

        return streams

    except Exception:
        logger.exception("Haiku stream parsing failed, using fallback")
        return _fallback_parse(input_text)


def _fallback_parse(input_text: str) -> list[dict]:
    """Simple comma/and splitting fallback when LLM is unavailable."""
    # Split by comma, "and", or semicolon
    parts = re.split(r",\s*|\s+and\s+|;\s*", input_text.strip())
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) < 2:
        # If only one item, try to split by sentence
        parts = [s.strip() for s in input_text.split(".") if s.strip()]

    if len(parts) < 2:
        parts = [input_text.strip(), "General work"]

    streams = []
    for part in parts[:4]:
        streams.append({
            "name": part[:100],
            "description": part,
            "entity_seeds": [],
        })

    return streams


async def create_streams_batch(
    streams: list[dict],
    tenant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> list[dict]:
    """Batch-create work streams with entity seeds.

    For each stream dict (name, description, entity_seeds):
    1. Create WorkStream row
    2. For each entity_seed, create ContextEntity + WorkStreamEntity link
    3. Compute initial density_score

    Args:
        streams: List of {name, description, entity_seeds} dicts.
        tenant_id: Tenant UUID.
        user_id: User UUID.
        db: Async database session.

    Returns:
        List of created stream dicts with id, name, density_score.
    """
    created = []

    for stream_data in streams:
        name = stream_data["name"][:100]
        description = stream_data.get("description", "")

        # Create WorkStream
        ws = WorkStream(
            tenant_id=tenant_id,
            user_id=user_id,
            name=name,
            description=description,
        )
        db.add(ws)
        await db.flush()

        # Create entity seeds and link them
        entity_seeds = stream_data.get("entity_seeds", [])
        entity_count = 0

        for seed_name in entity_seeds:
            if not seed_name or not seed_name.strip():
                continue

            seed_name = seed_name.strip()[:200]

            # Check if entity already exists for this tenant
            existing = (
                await db.execute(
                    select(ContextEntity).where(
                        ContextEntity.tenant_id == tenant_id,
                        ContextEntity.name == seed_name,
                        ContextEntity.entity_type == "seed",
                    )
                )
            ).scalar_one_or_none()

            if existing:
                entity = existing
            else:
                entity = ContextEntity(
                    tenant_id=tenant_id,
                    name=seed_name,
                    entity_type="seed",
                )
                db.add(entity)
                await db.flush()

            # Link entity to stream (check for existing link)
            existing_link = (
                await db.execute(
                    select(WorkStreamEntity).where(
                        WorkStreamEntity.stream_id == ws.id,
                        WorkStreamEntity.entity_id == entity.id,
                    )
                )
            ).scalar_one_or_none()

            if not existing_link:
                link = WorkStreamEntity(
                    stream_id=ws.id,
                    entity_id=entity.id,
                    tenant_id=tenant_id,
                )
                db.add(link)
                entity_count += 1

        # Compute initial density score
        # Formula: entity_count*10 + entry_count*2 + meeting_count*5 - gap_count*10
        # For new streams: entry_count=0, meeting_count=0, gap_count=entity_count (all are gaps)
        raw_score = (entity_count * 10) + 0 + 0 - (entity_count * 10)
        score = max(0, min(100, raw_score))

        ws.density_score = Decimal(str(score))
        ws.density_details = {
            "entity_count": entity_count,
            "entry_count": 0,
            "meeting_count": 0,
            "gap_count": entity_count,
        }

        await db.flush()

        created.append({
            "id": str(ws.id),
            "name": ws.name,
            "density_score": float(ws.density_score),
        })

    await db.commit()

    return created
