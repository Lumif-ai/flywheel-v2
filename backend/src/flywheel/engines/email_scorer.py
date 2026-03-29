"""
email_scorer.py - Email priority scoring engine.

Standalone async module that takes an Email row + tenant_id, enriches it with
pre-fetched context store data (sender entity + FTS-matched context entries),
calls Claude Haiku for structured scoring, and upserts an EmailScore row.

This engine is invoked directly from the Gmail sync loop (not via execute_run),
using the same subsidy API key pattern as voice_profile_init in gmail_sync.py.

Functions:
  score_email(db, tenant_id, email, api_key=None) -> dict | None
    Main entry point. Orchestrates the full scoring pipeline.

  _lookup_sender_entity(db, tenant_id, sender_email) -> ContextEntity | None
    Fetch the sender's context entity by domain or exact alias match.

  _search_context_entries(db, tenant_id, subject) -> list[ContextEntry]
    Full-text search context entries using plainto_tsquery on subject keywords.

  _build_score_prompt(email, sender_entity, context_entries) -> tuple[str, str]
    Build (system_prompt, user_message) for Haiku scoring call.

  _parse_score_response(text, valid_entity_ids, valid_entry_ids) -> dict
    Parse and validate the JSON scoring response from Haiku.

  _upsert_email_score(db, tenant_id, email_id, score_dict, sender_entity_id) -> None
    Upsert EmailScore row using ON CONFLICT on uq_email_score_email constraint.
"""

import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

import anthropic
from sqlalchemy import or_, select
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import ContextEntry, ContextEntity, Email, EmailScore
from flywheel.engines.email_dismiss_tracker import get_dismiss_signal
from flywheel.engines.model_config import get_engine_model

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

SCORE_SYSTEM_PROMPT = """\
You are an email priority scorer for a busy professional. Your job is to assign
a priority score and category to each incoming email using the context provided.

PRIORITY SCALE:
5 = CRITICAL — requires same-day action; involves a known key contact or active deal
4 = IMPORTANT — requires response within 24h; from a known contact or on a relevant topic
3 = NORMAL — warrants attention; no specific urgency signal
2 = LOW — FYI only; no action needed
1 = NOISE — marketing, auto-notifications, newsletters, or clearly irrelevant

SCORING BIAS: When uncertain, score UP. A false positive (overscoring) is acceptable.
A false negative (underscoring a critical email) is a critical product failure.
If you see ANY signal of urgency, deal relevance, or known-contact involvement, score UP.
If no context is available (empty context section), score conservatively (default 3) but
apply urgency keyword heuristics to boost when warranted.

CATEGORIES (choose one):
- meeting_followup — follow-up on a previous meeting, call, or conversation
- deal_related — related to a deal, contract, proposal, or commercial transaction
- action_required — requires a specific action or decision from the recipient
- informational — updates, newsletters, or FYI messages
- marketing — promotional content, product announcements, sales outreach from unknown senders
- personal — personal or social communication

SUGGESTED ACTIONS (choose one):
- notify — surface to user immediately (high priority)
- draft_reply — generate a reply draft
- file — file for reference, no action needed
- archive — low value, archive without notification

SIGNAL HIERARCHY (use these rules to calibrate your score):
- Known entity with mention_count >= 5: score UP (+1 to +2) — high-frequency contact = important relationship
- Entity type "company" + matching context entries: score UP (+2) — active client or deal
- Subject keyword matches a context entry: score UP (+1 to +2) — directly relevant to active work
- Label includes IMPORTANT: score UP (+1)
- Label includes CATEGORY_PROMOTIONS or CATEGORY_UPDATES: score DOWN (baseline 1-2)
- Urgency words in subject or snippet (urgent, deadline, ASAP, closing, by [date], today, tonight): score UP (+1)
- is_replied=false + received more than 7 days ago: stale thread, score UP (+1)
- Sender domain matches own company domain: likely internal, consider -1

FEW-SHOT EXAMPLES:

Example 1 (Score 5 — CRITICAL):
Context: Sender entity "Acme Capital" (company, mention_count=12). Matching entry from deal-pipeline.md: "Series A term sheet under review, closing target Q1".
Email: From: david@acmecapital.com, Subject: "Urgent: Term sheet revisions needed before Thursday", Labels: [UNREAD, IMPORTANT]
Response:
{
  "priority": 5,
  "category": "deal_related",
  "suggested_action": "notify",
  "reasoning": "Sender matches known entity 'Acme Capital' (mention_count=12, active deal). Subject contains 'Urgent' and explicit deadline 'before Thursday'. Context entry confirms active Series A term sheet. Critical escalation required.",
  "context_refs": [
    {"type": "entity", "id": "ENTITY_ID_PLACEHOLDER", "name": "Acme Capital"},
    {"type": "entry", "id": "ENTRY_ID_PLACEHOLDER", "file": "deal-pipeline.md", "snippet": "Series A term sheet under review"}
  ]
}

Example 2 (Score 4 — IMPORTANT):
Context: Sender entity "Bravo SaaS" (company, mention_count=6). No matching context entries.
Email: From: james@bravosaas.com, Subject: "Following up on our proposal", Labels: [UNREAD]
Response:
{
  "priority": 4,
  "category": "deal_related",
  "suggested_action": "draft_reply",
  "reasoning": "Sender matches known entity 'Bravo SaaS' (mention_count=6, active relationship). Subject indicates a pending proposal requiring follow-up. No urgency keyword but known contact warrants prompt response.",
  "context_refs": [
    {"type": "entity", "id": "ENTITY_ID_PLACEHOLDER", "name": "Bravo SaaS"}
  ]
}

Example 3 (Score 2 — LOW):
Context: No known entity. No matching context entries.
Email: From: noreply@newsletter.io, Subject: "10 tips to grow your startup", Labels: [UNREAD, CATEGORY_PROMOTIONS]
Response:
{
  "priority": 2,
  "category": "marketing",
  "suggested_action": "archive",
  "reasoning": "Unknown sender, CATEGORY_PROMOTIONS label, and generic marketing subject with no context store match. Low priority, no action required.",
  "context_refs": []
}

OUTPUT FORMAT:
Return ONLY a JSON object with exactly these fields. No markdown fencing, no explanation.
{
  "priority": <integer 1-5>,
  "category": <one of: meeting_followup, deal_related, action_required, informational, marketing, personal>,
  "suggested_action": <one of: notify, draft_reply, file, archive>,
  "reasoning": <1-3 sentences citing specific context matches if present>,
  "context_refs": <array of {type, id, name?, file?, snippet?} for each context item cited>
}
"""

_VALID_CATEGORIES = frozenset(
    {
        "meeting_followup",
        "deal_related",
        "action_required",
        "informational",
        "marketing",
        "personal",
    }
)

_VALID_ACTIONS = frozenset({"notify", "draft_reply", "file", "archive"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _lookup_sender_entity(
    db: AsyncSession,
    tenant_id: UUID,
    sender_email: str,
) -> "ContextEntity | None":
    """Fetch the sender's context entity by domain or exact alias match.

    Extracts the domain from the sender email address and queries
    context_entities by name ILIKE %domain% OR aliases @> [sender_email].
    Returns the first match or None if no entity is found.

    Args:
        db: Async SQLAlchemy session (caller-owned, RLS already set).
        tenant_id: Tenant UUID for row-level filtering.
        sender_email: Full sender email address (e.g. "alice@acme.com").

    Returns:
        ContextEntity ORM instance, or None if not found.
    """
    domain = sender_email.split("@")[-1] if "@" in sender_email else None

    filters = [ContextEntity.tenant_id == tenant_id]
    if domain:
        filters.append(
            or_(
                ContextEntity.name.ilike(f"%{domain}%"),
                ContextEntity.aliases.contains([sender_email]),
            )
        )
    else:
        filters.append(ContextEntity.aliases.contains([sender_email]))

    result = await db.execute(
        select(ContextEntity).where(*filters).limit(1)
    )
    return result.scalar_one_or_none()


async def _search_context_entries(
    db: AsyncSession,
    tenant_id: UUID,
    subject: str | None,
) -> list:
    """Full-text search context entries using plainto_tsquery on subject keywords.

    Strips Re:/Fwd:/Fw: prefixes from the subject, then runs
    plainto_tsquery('english', cleaned_subject) against search_vector.
    Returns top-3 entries ranked by ts_rank DESC.

    Uses plainto_tsquery (not to_tsquery) to handle arbitrary subject text
    safely — prevents SQL errors from punctuation, commas, or special chars.

    Args:
        db: Async SQLAlchemy session (caller-owned, RLS already set).
        tenant_id: Tenant UUID for row-level filtering.
        subject: Raw email subject line (may be None or contain Re:/Fwd: prefix).

    Returns:
        List of up to 3 ContextEntry ORM instances. Empty list if subject is
        empty or no FTS matches found.
    """
    # Strip Re:/Fwd:/Fw: prefixes
    clean_subject = re.sub(
        r"^(Re:|Fwd:|Fw:)\s*", "", subject or "", flags=re.IGNORECASE
    ).strip()

    if not clean_subject:
        return []

    result = await db.execute(
        select(ContextEntry)
        .where(
            ContextEntry.tenant_id == tenant_id,
            ContextEntry.deleted_at.is_(None),
            sa_text("search_vector @@ plainto_tsquery('english', :q)").bindparams(
                q=clean_subject
            ),
        )
        .order_by(
            sa_text(
                "ts_rank(search_vector, plainto_tsquery('english', :q)) DESC"
            ).bindparams(q=clean_subject)
        )
        .limit(3)
    )
    return list(result.scalars().all())


def _build_score_prompt(
    email: Email,
    sender_entity: "ContextEntity | None",
    context_entries: list,
    dismiss_signal: str = "",
) -> tuple[str, str]:
    """Build (system_prompt, user_message) for the Haiku scoring call.

    Structures the pre-fetched context (sender entity + matching context entries)
    and the email metadata into a user message block. The system prompt is the
    module-level SCORE_SYSTEM_PROMPT constant.

    Args:
        email: Email ORM instance (sender_email, sender_name, subject, snippet,
               labels, is_replied, received_at fields used).
        sender_entity: ContextEntity ORM instance, or None if not found.
        context_entries: List of ContextEntry ORM instances (0-3 items).

    Returns:
        Tuple of (system_prompt_str, user_message_str).
    """
    # Build sender entity block
    if sender_entity is not None:
        entity_json = json.dumps(
            {
                "id": str(sender_entity.id),
                "name": sender_entity.name,
                "entity_type": sender_entity.entity_type,
                "mention_count": sender_entity.mention_count,
                "last_seen_at": (
                    sender_entity.last_seen_at.isoformat()
                    if sender_entity.last_seen_at
                    else None
                ),
            },
            indent=2,
        )
        entity_block = f"Sender entity:\n{entity_json}"
    else:
        entity_block = "Sender entity: No known entity in context store."

    # Build context entries block
    if context_entries:
        entries_data = [
            {
                "id": str(entry.id),
                "file_name": getattr(entry, "file_name", None)
                or getattr(entry, "source", "unknown"),
                "detail": (entry.detail or "")[:100],
                "content_snippet": (entry.content or "")[:200],
            }
            for entry in context_entries
        ]
        entries_block = "Matching context entries:\n" + json.dumps(
            entries_data, indent=2
        )
    else:
        entries_block = "Matching context entries: None found."

    # Build staleness signal
    received_at_str = (
        email.received_at.isoformat() if email.received_at else "unknown"
    )
    stale_signal = ""
    if email.received_at and not email.is_replied:
        age_days = (
            datetime.now(timezone.utc) - email.received_at
        ).days
        if age_days > 7:
            stale_signal = f"\nSTALE THREAD: {age_days} days old, not replied."

    # Build labels string
    labels_str = ", ".join(email.labels) if email.labels else "none"

    user_message = f"""\
CONTEXT AVAILABLE:
{entity_block}

{entries_block}
{dismiss_signal}
EMAIL TO SCORE:
From: {email.sender_name or ""} <{email.sender_email}>
Subject: {email.subject or "(no subject)"}
Snippet: {email.snippet or "(no snippet)"}
Labels: {labels_str}
is_replied: {email.is_replied}
received_at: {received_at_str}{stale_signal}
"""

    return SCORE_SYSTEM_PROMPT, user_message


def _parse_score_response(
    text: str,
    valid_entity_ids: set,
    valid_entry_ids: set,
) -> dict:
    """Parse and validate the JSON scoring response from Haiku.

    Handles the rare case where Haiku wraps the JSON in markdown fencing by
    using re.search as a fallback (same pattern as voice_profile_init).

    Validates:
    - priority: integer 1-5 (clamps out-of-range values)
    - category: one of 6 allowed values (defaults to "informational")
    - suggested_action: one of 4 allowed values (defaults to "file")
    - context_refs: filters out any ref whose id is NOT in valid_entity_ids
      or valid_entry_ids (prevents hallucinated references)

    Args:
        text: Raw LLM response text.
        valid_entity_ids: Set of str UUIDs for pre-fetched ContextEntity rows.
        valid_entry_ids: Set of str UUIDs for pre-fetched ContextEntry rows.

    Returns:
        Cleaned and validated score dict with keys: priority, category,
        suggested_action, reasoning, context_refs.

    Raises:
        json.JSONDecodeError: If no valid JSON can be extracted.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise

    # Validate and clamp priority
    try:
        priority = int(data.get("priority", 3))
    except (TypeError, ValueError):
        priority = 3
    priority = max(1, min(5, priority))

    # Validate category
    category = data.get("category", "informational")
    if category not in _VALID_CATEGORIES:
        category = "informational"

    # Validate suggested_action
    suggested_action = data.get("suggested_action", "file")
    if suggested_action not in _VALID_ACTIONS:
        suggested_action = "file"

    # Validate and filter context_refs (prevent hallucinated IDs)
    all_valid_ids = valid_entity_ids | valid_entry_ids
    raw_refs = data.get("context_refs", [])
    if not isinstance(raw_refs, list):
        raw_refs = []
    context_refs = [
        ref
        for ref in raw_refs
        if isinstance(ref, dict) and str(ref.get("id", "")) in all_valid_ids
    ]

    return {
        "priority": priority,
        "category": category,
        "suggested_action": suggested_action,
        "reasoning": str(data.get("reasoning", ""))[:500],
        "context_refs": context_refs,
    }


async def _upsert_email_score(
    db: AsyncSession,
    tenant_id: UUID,
    email_id: UUID,
    score_dict: dict,
    sender_entity_id: "UUID | None",
) -> None:
    """Upsert an EmailScore row using ON CONFLICT on uq_email_score_email.

    Uses pg_insert for an atomic upsert. On conflict (same email_id), updates
    all scoring fields and scored_at. Does NOT commit — caller is responsible
    for committing the session (caller-commits pattern from Phase 2).

    Args:
        db: Async SQLAlchemy session (caller-owned).
        tenant_id: Tenant UUID.
        email_id: Email UUID (FK to emails.id).
        score_dict: Validated score dict from _parse_score_response.
        sender_entity_id: ContextEntity UUID or None.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(EmailScore)
        .values(
            tenant_id=tenant_id,
            email_id=email_id,
            priority=score_dict["priority"],
            category=score_dict["category"],
            suggested_action=score_dict.get("suggested_action"),
            reasoning=score_dict.get("reasoning"),
            context_refs=score_dict.get("context_refs", []),
            sender_entity_id=sender_entity_id,
            scored_at=now,
        )
        .on_conflict_do_update(
            constraint="uq_email_score_email",
            set_={
                "priority": pg_insert(EmailScore).excluded.priority,
                "category": pg_insert(EmailScore).excluded.category,
                "suggested_action": pg_insert(EmailScore).excluded.suggested_action,
                "reasoning": pg_insert(EmailScore).excluded.reasoning,
                "context_refs": pg_insert(EmailScore).excluded.context_refs,
                "sender_entity_id": pg_insert(EmailScore).excluded.sender_entity_id,
                "scored_at": now,
            },
        )
    )
    await db.execute(stmt)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def score_email(
    db: AsyncSession,
    tenant_id: UUID,
    email: Email,
    api_key: str | None = None,
) -> dict | None:
    """Score a single email and upsert the EmailScore row.

    Main entry point for the scoring engine. Orchestrates the full pipeline:
    1. Sender entity lookup in context_entities
    2. FTS search of context_entries by subject keywords
    3. Build scoring prompt with pre-fetched context
    4. Call Claude Haiku for structured JSON scoring
    5. Parse and validate response (hallucination filtering)
    6. Upsert EmailScore row (caller commits)
    7. Return parsed score dict for caller logging/chaining

    On any exception, logs the error (email ID only, no PII) and returns None.
    Failure is non-fatal — the sync loop always continues regardless of scoring
    outcome (same pattern as voice_profile_init in gmail_sync.py).

    Args:
        db: Async SQLAlchemy session. Caller sets RLS context (set_config) and
            commits. This function does not commit.
        tenant_id: Tenant UUID.
        email: Email ORM instance to score.
        api_key: Optional explicit API key. If None, uses
                 settings.flywheel_subsidy_api_key (background job default).

    Returns:
        Validated score dict with keys: priority, category, suggested_action,
        reasoning, context_refs. Or None on any error.
    """
    try:
        # Step 1: Sender entity lookup
        sender_entity = await _lookup_sender_entity(db, tenant_id, email.sender_email)

        # Step 2: FTS search on subject
        context_entries = await _search_context_entries(db, tenant_id, email.subject)

        # Step 2b: Dismiss signal lookup (non-fatal — returns "" on error)
        dismiss_block = await get_dismiss_signal(
            db,
            tenant_id,
            email.sender_email,
            days=settings.dismiss_lookback_days,
            threshold=settings.dismiss_threshold,
        )

        # Step 3: Build prompt
        system_prompt, user_message = _build_score_prompt(
            email, sender_entity, context_entries, dismiss_signal=dismiss_block
        )

        # Collect valid IDs for hallucination filtering
        valid_entity_ids: set[str] = (
            {str(sender_entity.id)} if sender_entity else set()
        )
        valid_entry_ids: set[str] = {str(e.id) for e in context_entries}

        # Step 4: Call scoring model (configurable per tenant)
        model = await get_engine_model(db, tenant_id, "scoring")
        effective_api_key = api_key or settings.flywheel_subsidy_api_key
        client = anthropic.AsyncAnthropic(api_key=effective_api_key)
        response = await client.messages.create(
            model=model,
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text.strip()

        # Step 5: Parse and validate
        score_dict = _parse_score_response(text, valid_entity_ids, valid_entry_ids)

        # Step 6: Upsert EmailScore (caller commits)
        await _upsert_email_score(
            db,
            tenant_id,
            email.id,
            score_dict,
            sender_entity.id if sender_entity else None,
        )

        # Step 7: Return for caller logging
        logger.info(
            "Scored email %s for tenant %s: priority=%d category=%s",
            email.id,
            tenant_id,
            score_dict["priority"],
            score_dict["category"],
        )
        return score_dict

    except Exception as exc:
        # Non-fatal: log email ID only (no PII — no subject/sender in log)
        logger.error(
            "score_email failed for email_id=%s tenant_id=%s: %s: %s",
            email.id,
            tenant_id,
            type(exc).__name__,
            exc,
        )
        return None
