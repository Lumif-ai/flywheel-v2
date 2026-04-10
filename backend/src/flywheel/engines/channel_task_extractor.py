"""Channel task extraction engine -- extract actionable tasks from scored emails.

Converts high-priority scored emails (action_required, meeting_followup) into Task rows.
Architecture supports future channels (Slack, calendar) via CHANNEL_EXTRACTORS registry.

Public API:
    extract_channel_tasks(factory, tenant_id, user_id, extractors=None)
        -> dict  (summary with tasks_created, duplicates_found, tasks_detail, etc.)
    extract_email_tasks(session, tenant_id, user_id, last_ritual_at)
        -> tuple[list[CandidateTask], dict]

Internal helpers:
    _resolve_entity_to_account(session, tenant_id, sender_entity_id) -> UUID | None
    _normalize_title(title) -> set[str]
    _find_duplicate(session, tenant_id, user_id, account_id, title, cutoff_hours=48)
        -> tuple[UUID | None, str | None]
    _extract_sender_name(description) -> str
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TypedDict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flywheel.db.models import (
    Contact,
    ContextEntity,
    Email,
    EmailScore,
    PipelineEntry,
    SkillRun,
    Task,
)

logger = logging.getLogger("flywheel.engines.channel_task_extractor")

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class CandidateTask(TypedDict):
    title: str
    description: str
    source: str              # "email", "slack", etc.
    source_id: UUID          # email.id, slack_message.id, etc.
    pipeline_entry_id: UUID | None
    task_type: str
    commitment_direction: str
    suggested_skill: str | None
    skill_context: dict | None
    trust_level: str
    priority: str
    email_id: UUID | None    # Only for email-sourced (FK)
    metadata: dict           # Channel-specific (thread_id, score_id, etc.)


# ---------------------------------------------------------------------------
# Stop words for dedup normalization
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "to", "for", "with", "on", "in", "at", "by",
    "up", "and", "or", "of", "is", "it", "re", "fwd", "fw",
})

_SUBJECT_PREFIX_RE = re.compile(r"^(Re|Fwd|Fw)\s*:\s*", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Channel Extractors Registry
# ---------------------------------------------------------------------------

# Future: append extract_slack_tasks, extract_calendar_tasks
CHANNEL_EXTRACTORS: list = []  # Populated after function definitions below


# ---------------------------------------------------------------------------
# Public API: extract_channel_tasks
# ---------------------------------------------------------------------------


async def extract_channel_tasks(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    user_id: UUID,
    extractors: list | None = None,
) -> dict:
    """Orchestrate channel task extraction -- pure data function (NO SSE emission).

    Opens a session, determines last ritual timestamp, calls each extractor,
    dedup-checks candidates, creates Task rows, and returns a summary dict.

    Returns:
        {
            "total_scored": N,
            "tasks_created": M,
            "duplicates_found": D,
            "skipped_existing": S,
            "is_first_run": bool,
            "channels": {"email": {...}},
            "tasks_detail": [...]
        }
    """
    if extractors is None:
        extractors = CHANNEL_EXTRACTORS

    async with factory() as session:
        # Set RLS context
        await session.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        await session.execute(
            sa_text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )

        # Determine last ritual timestamp
        last_ritual_result = await session.execute(
            select(func.max(SkillRun.created_at)).where(
                SkillRun.skill_name == "flywheel",
                SkillRun.status == "completed",
                SkillRun.tenant_id == tenant_id,
                SkillRun.user_id == user_id,
            )
        )
        last_ritual_at = last_ritual_result.scalar_one_or_none()

        # Collect candidates from all extractors
        all_candidates: list[CandidateTask] = []
        channels_summary: dict[str, dict] = {}

        for extractor in extractors:
            try:
                candidates, channel_summary = await extractor(
                    session, tenant_id, user_id, last_ritual_at,
                )
                all_candidates.extend(candidates)
                channel_name = candidates[0]["source"] if candidates else "unknown"
                channels_summary[channel_name] = channel_summary
            except Exception as e:
                logger.error("Extractor %s failed: %s", extractor.__name__, e)

        # Create Task rows with dedup
        tasks_created = 0
        duplicates_found = 0
        tasks_detail: list[dict] = []

        for candidate in all_candidates:
            # Dedup check
            dup_id, dup_title = await _find_duplicate(
                session, tenant_id, user_id,
                candidate["pipeline_entry_id"], candidate["title"],
            )

            if dup_id is not None:
                candidate["metadata"]["duplicate_of_task_id"] = str(dup_id)
                duplicates_found += 1
                logger.info(
                    "Duplicate detected: '%s' overlaps with existing task '%s' (%s)",
                    candidate["title"], dup_title, dup_id,
                )

            # Create Task ORM object
            task = Task(
                tenant_id=tenant_id,
                user_id=user_id,
                meeting_id=None,
                email_id=candidate["email_id"],
                pipeline_entry_id=candidate["pipeline_entry_id"],
                title=candidate["title"],
                description=candidate["description"],
                source=candidate["source"],
                task_type=candidate["task_type"],
                commitment_direction=candidate["commitment_direction"],
                suggested_skill=candidate["suggested_skill"],
                skill_context=candidate["skill_context"],
                trust_level=candidate["trust_level"],
                status="detected",
                priority=candidate["priority"],
                metadata_=candidate["metadata"],
            )
            session.add(task)
            tasks_created += 1

            tasks_detail.append({
                "title": candidate["title"],
                "sender_name": _extract_sender_name(candidate["description"]),
                "source": candidate["source"],
                "priority": candidate["priority"],
                "duplicate_of_title": dup_title,
            })

        if all_candidates:
            await session.flush()
            await session.commit()

    is_first_run = last_ritual_at is None
    total_scored = sum(
        cs.get("total_scored", 0) for cs in channels_summary.values()
    )

    summary = {
        "total_scored": total_scored,
        "tasks_created": tasks_created,
        "duplicates_found": duplicates_found,
        "skipped_existing": 0,  # Emails with existing tasks are excluded at query time
        "is_first_run": is_first_run,
        "channels": channels_summary,
        "tasks_detail": tasks_detail,
    }

    logger.info(
        "Channel task extraction complete: %d scored, %d created, %d duplicates (first_run=%s)",
        total_scored, tasks_created, duplicates_found, is_first_run,
    )

    return summary


# ---------------------------------------------------------------------------
# Email Channel Extractor
# ---------------------------------------------------------------------------


async def extract_email_tasks(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    last_ritual_at: datetime | None,
) -> tuple[list[CandidateTask], dict]:
    """Extract candidate tasks from scored emails.

    Queries emails with priority >= 4 and category in (action_required, meeting_followup)
    that were scored since the last ritual run. Excludes emails already linked to tasks
    via email_id FK (idempotency).

    Returns (candidates, channel_summary).
    """
    is_first_run = last_ritual_at is None

    if is_first_run:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        limit = 15
    else:
        cutoff = last_ritual_at
        limit = 100

    # Build query: Email JOIN EmailScore, filtered by category/priority/scored_at
    # Exclude emails that already have a Task row (idempotency via email_id FK)
    existing_task_emails = select(Task.email_id).where(
        Task.email_id.isnot(None),
    ).correlate(None)

    query = (
        select(Email, EmailScore)
        .join(EmailScore, EmailScore.email_id == Email.id)
        .where(
            Email.tenant_id == tenant_id,
            Email.user_id == user_id,
            EmailScore.category.in_(["action_required", "meeting_followup"]),
            EmailScore.priority >= 4,
            EmailScore.scored_at > cutoff,
            ~Email.id.in_(existing_task_emails),
        )
        .order_by(EmailScore.priority.desc(), Email.received_at.desc())
        .limit(limit)
    )

    result = await session.execute(query)
    rows = result.all()

    candidates: list[CandidateTask] = []

    for email, score in rows:
        # Clean title: strip Re:/Fwd:/Fw: prefixes
        raw_subject = email.subject or ""
        clean_title = _SUBJECT_PREFIX_RE.sub("", raw_subject).strip()
        if not clean_title:
            sender = email.sender_name or email.sender_email
            clean_title = f"(No subject) -- from {sender}"

        # Build description
        snippet = email.snippet or ""
        reasoning = score.reasoning or ""
        sender_name = email.sender_name or email.sender_email
        sender_email_addr = email.sender_email
        description = (
            f"From: {sender_name} ({sender_email_addr})\n"
            f"{snippet}\n\n"
            f"Scorer reasoning: {reasoning}"
        )

        # Determine commitment direction
        commitment_direction = (
            "yours" if score.category == "action_required" else "mutual"
        )

        # Determine priority
        priority = "high" if score.priority == 5 else "medium"

        # Determine suggested_skill and skill_context
        suggested_skill: str | None = None
        skill_context: dict | None = None
        if score.suggested_action == "draft_reply":
            suggested_skill = "email-drafter"
            skill_context = {
                "email_id": str(email.id),
                "gmail_thread_id": email.gmail_thread_id,
            }

        # Determine trust_level
        trust_level = "review"
        if suggested_skill and "email" in suggested_skill.lower():
            trust_level = "confirm"

        # Resolve entity to pipeline entry
        pipeline_entry_id = await _resolve_entity_to_account(
            session, tenant_id, score.sender_entity_id,
        )

        candidate: CandidateTask = {
            "title": clean_title,
            "description": description,
            "source": "email",
            "source_id": email.id,
            "pipeline_entry_id": pipeline_entry_id,
            "task_type": "followup",
            "commitment_direction": commitment_direction,
            "suggested_skill": suggested_skill,
            "skill_context": skill_context,
            "trust_level": trust_level,
            "priority": priority,
            "email_id": email.id,
            "metadata": {
                "email_score_id": str(score.id),
                "gmail_thread_id": email.gmail_thread_id,
            },
        }
        candidates.append(candidate)

    channel_summary = {
        "total_scored": len(candidates),
        "is_first_run": is_first_run,
    }

    return candidates, channel_summary


# ---------------------------------------------------------------------------
# Entity-to-Account Resolution
# ---------------------------------------------------------------------------


async def _resolve_entity_to_account(
    session: AsyncSession,
    tenant_id: UUID,
    sender_entity_id: UUID | None,
) -> UUID | None:
    """Best-effort resolution of a ContextEntity to an Account.

    For company entities: match by Account.name.
    For person entities: match by AccountContact.name.
    Returns account_id if found, None otherwise. Never raises.
    """
    if sender_entity_id is None:
        return None

    try:
        entity = (await session.execute(
            select(ContextEntity).where(ContextEntity.id == sender_entity_id)
        )).scalar_one_or_none()

        if entity is None:
            logger.debug("Entity %s not found", sender_entity_id)
            return None

        if entity.entity_type == "company":
            entry_id = (await session.execute(
                select(PipelineEntry.id).where(
                    PipelineEntry.name == entity.name,
                    PipelineEntry.tenant_id == tenant_id,
                ).limit(1)
            )).scalar_one_or_none()
            if entry_id:
                logger.debug(
                    "Resolved company entity '%s' to pipeline entry %s",
                    entity.name, entry_id,
                )
            return entry_id

        if entity.entity_type == "person":
            entry_id = (await session.execute(
                select(Contact.pipeline_entry_id).where(
                    Contact.name == entity.name,
                    Contact.tenant_id == tenant_id,
                ).limit(1)
            )).scalar_one_or_none()
            if entry_id:
                logger.debug(
                    "Resolved person entity '%s' to pipeline entry %s",
                    entity.name, entry_id,
                )
            return entry_id

        return None

    except Exception as e:
        logger.debug("Entity resolution failed for %s: %s", sender_entity_id, e)
        return None


# ---------------------------------------------------------------------------
# Dedup Guard
# ---------------------------------------------------------------------------


def _normalize_title(title: str) -> set[str]:
    """Normalize a task title for dedup comparison.

    Strips Re:/Fwd:/Fw: prefixes, lowercases, removes stop words.
    Returns set of meaningful words.
    """
    cleaned = _SUBJECT_PREFIX_RE.sub("", title).strip().lower()
    words = cleaned.split()
    return {w for w in words if w not in _STOP_WORDS}


async def _find_duplicate(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    account_id: UUID | None,
    title: str,
    cutoff_hours: int = 48,
) -> tuple[UUID | None, str | None]:
    """Check if a candidate task title overlaps with existing open tasks.

    Uses ratio-based word matching: overlap / min(len_a, len_b) >= 0.5.
    Returns (task_id, task_title) if duplicate found, else (None, None).
    """
    new_words = _normalize_title(title)
    if len(new_words) < 2:
        return None, None

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)

    # Build base query for open tasks
    base_filter = [
        Task.tenant_id == tenant_id,
        Task.user_id == user_id,
        ~Task.status.in_(["done", "dismissed"]),
        Task.created_at > cutoff_time,
    ]

    # Try account-scoped first if account_id is set
    if account_id is not None:
        result = await session.execute(
            select(Task.id, Task.title).where(
                *base_filter,
                Task.pipeline_entry_id == account_id,
            )
        )
        rows = result.all()
        match = _check_word_overlap(new_words, rows)
        if match:
            return match

    # Fall through: check all user tasks (cross-source dedup)
    result = await session.execute(
        select(Task.id, Task.title).where(*base_filter)
    )
    rows = result.all()
    return _check_word_overlap(new_words, rows)


def _check_word_overlap(
    new_words: set[str],
    rows: list,
) -> tuple[UUID | None, str | None]:
    """Check word overlap ratio against a list of (task_id, task_title) rows."""
    for task_id, task_title in rows:
        existing_words = _normalize_title(task_title)
        if not existing_words:
            continue
        overlap = len(new_words & existing_words)
        shorter = min(len(new_words), len(existing_words))
        if shorter > 0 and overlap / shorter >= 0.5:
            return task_id, task_title
    return None, None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_sender_name(description: str) -> str:
    """Parse sender name from the 'From: {name} ({email})' line in description."""
    match = re.match(r"^From:\s*(.+?)\s*\(", description)
    return match.group(1) if match else "Unknown"


# ---------------------------------------------------------------------------
# Registry (must be after function definitions)
# ---------------------------------------------------------------------------

CHANNEL_EXTRACTORS.append(extract_email_tasks)
