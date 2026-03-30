"""context_store_writer.py -- Shared context store writer for all backend engines.

Provides a unified interface for writing structured intelligence to the context
store with consistent dedup and evidence counting. Any source (email, meeting,
future Slack) can use these functions to write entries that are automatically
deduplicated by (file_name, source, detail, tenant_id, date).

Public functions:
  write_contact()            -- write a person/contact entry
  write_insight()            -- write a business insight or topic
  write_action_item()        -- write an action item or commitment
  write_deal_signal()        -- write a deal/commercial signal
  write_relationship_signal() -- write a relationship signal (stored in insights)

Private helper:
  _write_entry()  -- core dedup + insert/increment logic

None of these functions call db.commit() -- the caller owns the transaction.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import ContextCatalog, ContextEntry

logger = logging.getLogger(__name__)

_MAX_CONTENT_LENGTH = 4000

_CATALOG_DESCRIPTIONS: dict[str, str] = {
    "contacts": "People and contacts extracted from emails and meetings",
    "insights": "Business insights, topics, and relationship signals",
    "action-items": "Action items and commitments extracted from communications",
    "deal-signals": "Deal and commercial signals from conversations",
}


# ---------------------------------------------------------------------------
# Core private helper
# ---------------------------------------------------------------------------


async def _write_entry(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    file_name: str,
    source: str,
    detail: str,
    content: str,
    confidence: str = "medium",
    entry_date: date | None = None,
    account_id: UUID | None = None,
) -> str:
    """Write or deduplicate a context entry.

    Dedup key: (file_name, source, detail, tenant_id, date).
    If a matching non-deleted entry exists, increments evidence_count.
    Otherwise inserts a new ContextEntry and upserts the ContextCatalog.

    Returns "created" or "incremented".

    Does NOT call db.commit() -- caller owns the transaction.
    """
    # 1. Truncate content
    content = content[:_MAX_CONTENT_LENGTH]

    # 2. Default date
    if entry_date is None:
        entry_date = date.today()

    # 3. Dedup query
    stmt = (
        select(ContextEntry.id, ContextEntry.evidence_count)
        .where(
            ContextEntry.file_name == file_name,
            ContextEntry.source == source,
            ContextEntry.detail == detail,
            ContextEntry.tenant_id == tenant_id,
            ContextEntry.date == entry_date,
            ContextEntry.deleted_at.is_(None),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    existing = result.first()

    # 4. Increment if exists
    if existing is not None:
        await db.execute(
            update(ContextEntry)
            .where(ContextEntry.id == existing.id)
            .values(evidence_count=ContextEntry.evidence_count + 1)
        )
        outcome = "incremented"
    else:
        # 5. Insert new entry
        entry = ContextEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            file_name=file_name,
            source=source,
            detail=detail,
            content=content,
            confidence=confidence,
            date=entry_date,
            account_id=account_id,
            metadata_={},
        )
        db.add(entry)

        # 6. Upsert catalog
        catalog_stmt = pg_insert(ContextCatalog).values(
            tenant_id=tenant_id,
            file_name=file_name,
            description=_CATALOG_DESCRIPTIONS.get(file_name, file_name),
            status="active",
        )
        catalog_stmt = catalog_stmt.on_conflict_do_update(
            index_elements=["tenant_id", "file_name"],
            set_={"status": "active"},
        )
        await db.execute(catalog_stmt)
        outcome = "created"

    # 7. Debug log (no content, no PII)
    logger.debug(
        "context_store_writer: %s entry file=%s detail=%s tenant=%s",
        outcome,
        file_name,
        (detail or "")[:50],
        tenant_id,
    )

    return outcome


# ---------------------------------------------------------------------------
# Public write functions
# ---------------------------------------------------------------------------


async def write_contact(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    name: str,
    title: str | None = None,
    company: str | None = None,
    email_address: str | None = None,
    notes: str | None = None,
    source_label: str = "email-context-engine",
    confidence: str = "medium",
    entry_date: date | None = None,
    account_id: UUID | None = None,
) -> str:
    """Write a contact entry to the context store.

    Detail tag format: ``contact:{name}`` or ``contact:{name}:{company}``
    Dedup: same name+company on the same date from the same source increments
    evidence_count rather than creating a duplicate.

    Returns "created" or "incremented".
    """
    detail_tag = f"contact:{name.lower().strip()}"
    if company:
        detail_tag += f":{company.lower().strip()}"

    lines: list[str] = [f"Name: {name}"]
    if title:
        lines.append(f"Title: {title}")
    if company:
        lines.append(f"Company: {company}")
    if email_address:
        lines.append(f"Email: {email_address}")
    if notes:
        lines.append(f"Notes: {notes}")

    return await _write_entry(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        file_name="contacts",
        source=source_label,
        detail=detail_tag,
        content="\n".join(lines),
        confidence=confidence,
        entry_date=entry_date,
        account_id=account_id,
    )


async def write_insight(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    topic: str,
    relevance: str,
    context_text: str,
    source_label: str = "email-context-engine",
    confidence: str = "medium",
    entry_date: date | None = None,
    account_id: UUID | None = None,
) -> str:
    """Write a business insight to the context store.

    Detail tag format: ``insight:{topic[:80]}``
    Topic is truncated to 80 chars in the tag for stability; full topic is in content.

    Returns "created" or "incremented".
    """
    detail_tag = f"insight:{topic.lower().strip()[:80]}"
    content = f"Topic: {topic}\nRelevance: {relevance}\n{context_text}"

    return await _write_entry(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        file_name="insights",
        source=source_label,
        detail=detail_tag,
        content=content,
        confidence=confidence,
        entry_date=entry_date,
        account_id=account_id,
    )


async def write_action_item(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    action: str,
    owner: str | None = None,
    due_date_str: str | None = None,
    urgency: str | None = None,
    source_label: str = "email-context-engine",
    confidence: str = "medium",
    entry_date: date | None = None,
    account_id: UUID | None = None,
) -> str:
    """Write an action item to the context store.

    Detail tag format: ``action:{action[:80]}``
    Action text is truncated to 80 chars in the tag for dedup stability.

    Returns "created" or "incremented".
    """
    detail_tag = f"action:{action.lower().strip()[:80]}"

    lines: list[str] = [f"Action: {action}"]
    if owner:
        lines.append(f"Owner: {owner}")
    if due_date_str:
        lines.append(f"Due: {due_date_str}")
    if urgency:
        lines.append(f"Urgency: {urgency}")

    return await _write_entry(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        file_name="action-items",
        source=source_label,
        detail=detail_tag,
        content="\n".join(lines),
        confidence=confidence,
        entry_date=entry_date,
        account_id=account_id,
    )


async def write_deal_signal(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    signal_type: str,
    description: str,
    counterparty: str | None = None,
    source_label: str = "email-context-engine",
    confidence: str = "medium",
    entry_date: date | None = None,
    account_id: UUID | None = None,
) -> str:
    """Write a deal/commercial signal to the context store.

    Detail tag format: ``deal:{signal_type}:{counterparty[:40]}``
    Counterparty defaults to "unknown" if not provided.

    Returns "created" or "incremented".
    """
    cp = (counterparty or "unknown").lower().strip()[:40]
    detail_tag = f"deal:{signal_type.lower().strip()}:{cp}"

    lines: list[str] = [
        f"Signal: {signal_type}",
        f"Description: {description}",
    ]
    if counterparty:
        lines.append(f"Counterparty: {counterparty}")

    return await _write_entry(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        file_name="deal-signals",
        source=source_label,
        detail=detail_tag,
        content="\n".join(lines),
        confidence=confidence,
        entry_date=entry_date,
        account_id=account_id,
    )


async def write_relationship_signal(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    signal_type: str,
    description: str,
    people_involved: list[str] | None = None,
    source_label: str = "email-context-engine",
    confidence: str = "medium",
    entry_date: date | None = None,
    account_id: UUID | None = None,
) -> str:
    """Write a relationship signal to the insights context file.

    Detail tag format: ``relationship:{signal_type}:{person1}:{person2}:...``
    Up to 3 people are included in the tag, sorted alphabetically for stability.
    Stored in the "insights" file (same as meeting processor pattern).

    Returns "created" or "incremented".
    """
    people_parts = sorted(p.lower().strip() for p in (people_involved or [])[:3])
    detail_tag = f"relationship:{signal_type.lower().strip()}:{':'.join(people_parts)}"

    content = (
        f"Signal: {signal_type}\n"
        f"Description: {description}\n"
        f"People: {', '.join(people_involved or [])}"
    )

    return await _write_entry(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        file_name="insights",
        source=source_label,
        detail=detail_tag,
        content=content,
        confidence=confidence,
        entry_date=entry_date,
        account_id=account_id,
    )
