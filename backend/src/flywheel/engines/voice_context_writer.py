"""voice_context_writer.py -- Mirror voice profile to context store.

Provides two functions that keep the context_entries table in sync with
the email_voice_profiles table so that any skill can read the user's
writing voice via flywheel_read_context.

Functions:
  write_voice_to_context(db, tenant_id, user_id, profile_dict, samples_analyzed)
    Soft-deletes stale sender-voice entry, inserts fresh one, upserts catalog.

  delete_voice_from_context(db, tenant_id)
    Soft-deletes all sender-voice entries for the tenant (used on reset).

Neither function calls db.commit() -- the caller owns the transaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import ContextCatalog, ContextEntry

FILE_NAME = "sender-voice"
SOURCE = "email-voice-engine"


def _format_voice_content(profile: dict, samples_analyzed: int) -> str:
    """Format all 10 voice fields as human-readable markdown."""
    lines: list[str] = [
        f"Writing Voice Profile (extracted from {samples_analyzed} sent emails)",
        "",
    ]

    field_map = [
        ("tone", "Tone"),
        ("formality_level", "Formality"),
        ("greeting_style", "Greeting style"),
        ("sign_off", "Sign-off"),
        ("question_style", "Question style"),
        ("paragraph_pattern", "Paragraph pattern"),
        ("emoji_usage", "Emoji usage"),
    ]

    for key, label in field_map:
        value = profile.get(key)
        if value is not None:
            lines.append(f"{label}: {value}")
        else:
            lines.append(f"{label}: not yet learned")

    # avg_length + avg_sentences combined line
    avg_length = profile.get("avg_length")
    avg_sentences = profile.get("avg_sentences")
    if avg_length is not None or avg_sentences is not None:
        length_part = f"~{avg_length} words" if avg_length is not None else "unknown"
        sentences_part = (
            f"~{avg_sentences} sentences" if avg_sentences is not None else "unknown"
        )
        lines.append(f"Average length: {length_part}, {sentences_part}")
    else:
        lines.append("Average length: not yet learned")

    # phrases (list)
    phrases = profile.get("phrases")
    if phrases and isinstance(phrases, list):
        quoted = ", ".join(f'"{p}"' for p in phrases)
        lines.append(f"Characteristic phrases: {quoted}")
    else:
        lines.append("Characteristic phrases: not yet learned")

    return "\n".join(lines)


async def write_voice_to_context(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    profile_dict: dict,
    samples_analyzed: int,
) -> None:
    """Write voice profile as a context store entry.

    1. Soft-delete existing sender-voice entries for this tenant+user.
    2. Insert new ContextEntry with formatted markdown content.
    3. Upsert ContextCatalog to active.

    Does NOT call db.commit() -- caller owns the transaction.
    """
    now = datetime.now(timezone.utc)

    # 1. Soft-delete existing entries
    await db.execute(
        update(ContextEntry)
        .where(
            ContextEntry.tenant_id == tenant_id,
            ContextEntry.file_name == FILE_NAME,
            ContextEntry.source == SOURCE,
            ContextEntry.deleted_at.is_(None),
        )
        .values(deleted_at=now)
    )

    # 2. Insert new entry
    content = _format_voice_content(profile_dict, samples_analyzed)

    if samples_analyzed >= 20:
        confidence = "high"
    elif samples_analyzed >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    entry = ContextEntry(
        tenant_id=tenant_id,
        user_id=user_id,
        file_name=FILE_NAME,
        source=SOURCE,
        detail="Voice profile snapshot",
        content=content,
        confidence=confidence,
        evidence_count=samples_analyzed,
        metadata_={},
    )
    db.add(entry)

    # 3. Upsert catalog
    catalog_stmt = pg_insert(ContextCatalog).values(
        tenant_id=tenant_id,
        file_name=FILE_NAME,
        description="User's writing voice profile extracted from email patterns",
        status="active",
    )
    catalog_stmt = catalog_stmt.on_conflict_do_update(
        index_elements=["tenant_id", "file_name"],
        set_={"status": "active"},
    )
    await db.execute(catalog_stmt)


async def delete_voice_from_context(
    db: AsyncSession,
    tenant_id: UUID,
) -> None:
    """Soft-delete all sender-voice context entries for a tenant.

    Used when the voice profile is reset. The catalog entry stays active --
    a fresh entry will be written after re-extraction completes.

    Does NOT call db.commit() -- caller owns the transaction.
    """
    now = datetime.now(timezone.utc)

    await db.execute(
        update(ContextEntry)
        .where(
            ContextEntry.tenant_id == tenant_id,
            ContextEntry.file_name == FILE_NAME,
            ContextEntry.source == SOURCE,
            ContextEntry.deleted_at.is_(None),
        )
        .values(deleted_at=now)
    )
