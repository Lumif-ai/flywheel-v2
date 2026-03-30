"""email_context_extractor.py -- Email context extraction engine.

Extracts structured intelligence from email bodies and writes to the context
store via the shared writer. Entry point: ``extract_email_context()``.
Non-fatal on errors. Never stores email body.

The extraction pipeline:
  1. Guard on priority >= 3 (skip noise)
  2. Fetch body on-demand via get_message_body
  3. Call Claude for structured extraction (contacts, topics, deals,
     relationships, action items)
  4. Parse JSON response with regex fallback
  5. Write each item via shared context_store_writer
  6. Explicitly discard body (PII posture)

None of these functions call db.commit() -- the caller owns the transaction.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from uuid import UUID

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import Email, EmailScore, Integration
from flywheel.engines.context_store_writer import (
    write_action_item,
    write_contact,
    write_deal_signal,
    write_insight,
    write_relationship_signal,
)
from flywheel.engines.model_config import get_engine_model
from flywheel.services.gmail_read import get_message_body, get_valid_credentials

logger = logging.getLogger(__name__)

_SOURCE_LABEL = "email-context-engine"

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
You are an email intelligence extraction engine. Given an email's metadata and body,
extract structured intelligence into exactly these categories.

Respond ONLY with a valid JSON object using these exact keys:
- contacts: list of {name, title, company, email, role_in_context, notes, confidence}
- topics: list of {topic, relevance, context, confidence}
- deal_signals: list of {signal_type, description, confidence, counterparty}
- relationship_signals: list of {signal_type, description, people_involved, confidence}
- action_items: list of {action, owner, due_date, urgency, confidence}

Rules:
- confidence must be "high", "medium", or "low" for each item
- Use "high" when explicitly stated in the email (e.g., "I'm the VP of Sales")
- Use "medium" for strongly implied information
- Use "low" for inferred or uncertain information
- Use empty lists [] for categories with no data
- Only extract information explicitly stated or strongly implied — do not hallucinate
- relevance must be "high", "medium", or "low"
- urgency must be "high", "medium", or "low"
- due_date should be ISO format (YYYY-MM-DD) or null if not mentioned"""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_extraction_prompt(email: Email, body: str) -> tuple[str, str]:
    """Build system + user prompt for context extraction.

    Returns:
        (system_prompt, user_message)
    """
    system_prompt = EXTRACTION_SYSTEM_PROMPT
    user_message = (
        f"Subject: {email.subject or '(no subject)'}\n"
        f"From: {email.sender_name or email.sender_email}\n"
        f"Date: {email.received_at.strftime('%Y-%m-%d')}\n"
        f"\n{body[:8000]}"
    )
    return system_prompt, user_message


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

_VALID_CONFIDENCE = {"high", "medium", "low"}
_EXPECTED_KEYS = ("contacts", "topics", "deal_signals", "relationship_signals", "action_items")


def _parse_extraction_response(text: str) -> dict:
    """Parse the LLM extraction response into a validated dict.

    Strategy (mirrors email_scorer._parse_score_response):
    1. Try json.loads directly.
    2. Regex fallback for markdown-fenced JSON.
    3. Return empty extraction on total failure.

    Validates:
    - All expected keys exist and are lists.
    - Each item has a valid confidence value.
    """
    data = None
    used_fallback = False

    # 1. Try direct parse
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 2. Regex fallback for markdown-fenced or wrapped JSON
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                used_fallback = True
            except json.JSONDecodeError:
                data = None

    # 3. Total failure — return empty extraction
    if data is None or not isinstance(data, dict):
        logger.warning(
            "_parse_extraction_response: could not parse LLM output, returning empty extraction"
        )
        return {k: [] for k in _EXPECTED_KEYS}

    if used_fallback:
        logger.warning(
            "_parse_extraction_response: used regex fallback for LLM output"
        )

    # 4. Validate each key exists and is a list
    for key in _EXPECTED_KEYS:
        if key not in data or not isinstance(data[key], list):
            data[key] = []

    # 5. Validate confidence on each item
    for key in _EXPECTED_KEYS:
        for item in data[key]:
            if isinstance(item, dict):
                conf = item.get("confidence")
                if conf not in _VALID_CONFIDENCE:
                    item["confidence"] = "medium"

    return data


# ---------------------------------------------------------------------------
# Writer integration
# ---------------------------------------------------------------------------


async def _write_extracted_context(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    email_id: UUID,
    email_date: date,
    extracted: dict,
) -> dict:
    """Iterate over extracted items and write each via the shared writer.

    Individual item failures are caught and logged — one bad item does not
    prevent others from being written.

    Returns dict with keys: created, incremented, total.
    """
    results = {"created": 0, "incremented": 0, "total": 0}

    # Contacts
    for c in extracted.get("contacts", []):
        try:
            outcome = await write_contact(
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                name=c["name"],
                title=c.get("title"),
                company=c.get("company"),
                email_address=c.get("email"),
                notes=c.get("notes"),
                source_label=_SOURCE_LABEL,
                confidence=c.get("confidence", "medium"),
                entry_date=email_date,
            )
            results[outcome] = results.get(outcome, 0) + 1
            results["total"] += 1
        except Exception:
            logger.warning(
                "_write_extracted_context: failed to write contact for email_id=%s",
                email_id,
                exc_info=True,
            )

    # Topics (insights)
    for t in extracted.get("topics", []):
        try:
            outcome = await write_insight(
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                topic=t["topic"],
                relevance=t.get("relevance", "medium"),
                context_text=t.get("context", ""),
                source_label=_SOURCE_LABEL,
                confidence=t.get("confidence", "medium"),
                entry_date=email_date,
            )
            results[outcome] = results.get(outcome, 0) + 1
            results["total"] += 1
        except Exception:
            logger.warning(
                "_write_extracted_context: failed to write insight for email_id=%s",
                email_id,
                exc_info=True,
            )

    # Deal signals
    for d in extracted.get("deal_signals", []):
        try:
            outcome = await write_deal_signal(
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                signal_type=d["signal_type"],
                description=d["description"],
                counterparty=d.get("counterparty"),
                source_label=_SOURCE_LABEL,
                confidence=d.get("confidence", "medium"),
                entry_date=email_date,
            )
            results[outcome] = results.get(outcome, 0) + 1
            results["total"] += 1
        except Exception:
            logger.warning(
                "_write_extracted_context: failed to write deal_signal for email_id=%s",
                email_id,
                exc_info=True,
            )

    # Relationship signals
    for r in extracted.get("relationship_signals", []):
        try:
            outcome = await write_relationship_signal(
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                signal_type=r["signal_type"],
                description=r["description"],
                people_involved=r.get("people_involved", []),
                source_label=_SOURCE_LABEL,
                confidence=r.get("confidence", "medium"),
                entry_date=email_date,
            )
            results[outcome] = results.get(outcome, 0) + 1
            results["total"] += 1
        except Exception:
            logger.warning(
                "_write_extracted_context: failed to write relationship_signal for email_id=%s",
                email_id,
                exc_info=True,
            )

    # Action items
    for a in extracted.get("action_items", []):
        try:
            outcome = await write_action_item(
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                action=a["action"],
                owner=a.get("owner"),
                due_date_str=a.get("due_date"),
                urgency=a.get("urgency", "medium"),
                source_label=_SOURCE_LABEL,
                confidence=a.get("confidence", "medium"),
                entry_date=email_date,
            )
            results[outcome] = results.get(outcome, 0) + 1
            results["total"] += 1
        except Exception:
            logger.warning(
                "_write_extracted_context: failed to write action_item for email_id=%s",
                email_id,
                exc_info=True,
            )

    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def extract_email_context(
    db: AsyncSession,
    tenant_id: UUID,
    email: Email,
    integration: Integration,
    api_key: str | None = None,
) -> dict | None:
    """Extract structured intelligence from an email and write to context store.

    Guards on priority >= 3 before doing any expensive work. Fetches the email
    body on-demand, calls Claude for extraction, parses the structured response,
    and writes each item through the shared context_store_writer.

    Does NOT call db.commit() -- caller owns the transaction.

    Args:
        db: Async SQLAlchemy session (RLS already set by caller).
        tenant_id: Tenant UUID.
        email: Email model instance.
        integration: Gmail Integration for credential retrieval.
        api_key: Optional override for the Anthropic API key.

    Returns:
        Dict with keys ``extracted``, ``results``, ``model`` on success.
        None if skipped (low priority, empty body) or on error.
    """
    try:
        # 1. Priority guard
        score_row = await db.execute(
            select(EmailScore.priority).where(EmailScore.email_id == email.id)
        )
        priority = score_row.scalar_one_or_none()
        if priority is None or priority < 3:
            logger.debug(
                "extract_email_context: skipping email_id=%s priority=%s",
                email.id,
                priority,
            )
            return None

        # 2. Fetch body on-demand
        creds = await get_valid_credentials(integration)
        body = await get_message_body(creds, email.gmail_message_id)

        # 3. Fallback to snippet if body is missing or too short
        if body is None or len(body.strip()) < 50:
            body = email.snippet or ""
        if len(body.strip()) < 20:
            logger.debug(
                "extract_email_context: body too short for email_id=%s",
                email.id,
            )
            return None

        # 4. Get model
        model = await get_engine_model(db, tenant_id, "context_extraction")

        # 5. Build prompt
        system_prompt, user_message = _build_extraction_prompt(email, body)

        # 6. Call Claude
        client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.flywheel_subsidy_api_key
        )
        response = await client.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text.strip()

        # 7. PII posture: never retain email body beyond extraction
        del body

        # 8. Parse
        extracted = _parse_extraction_response(text)

        # 9. Write to context store
        results = await _write_extracted_context(
            db, tenant_id, email.user_id, email.id, email.received_at.date(), extracted
        )

        # 10. Log summary (no PII)
        logger.info(
            "extract_email_context: email_id=%s tenant_id=%s created=%d incremented=%d total=%d",
            email.id,
            tenant_id,
            results["created"],
            results["incremented"],
            results["total"],
        )

        return {"extracted": extracted, "results": results, "model": model}

    except Exception as exc:
        logger.error(
            "extract_email_context failed email_id=%s tenant_id=%s: %s",
            email.id,
            tenant_id,
            exc,
            exc_info=True,
        )
        return None
