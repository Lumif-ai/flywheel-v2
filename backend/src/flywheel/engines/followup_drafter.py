"""
followup_drafter.py - AI-powered follow-up email draft generation.

Generates follow-up emails for carriers that haven't responded to solicitations
within their expected response window. Uses Claude Sonnet for cost-effective
generation, respecting the project's language setting.

Functions:
  draft_followup(db, tenant_id, quote, project, carrier, api_key=None)
    -> {"status": "drafted", "subject": str, "body": str}
    OR {"status": "not_due", "days_remaining": int}
"""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.engines.model_config import get_engine_model

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def draft_followup(
    db: AsyncSession,
    tenant_id: UUID,
    quote,
    project,
    carrier,
    api_key: str | None = None,
) -> dict:
    """Generate a follow-up email draft for a slow carrier.

    Checks timing threshold before generating. If the carrier hasn't exceeded
    their expected response window + 2 day buffer, returns not_due status.

    This function does NOT update the CarrierQuote row -- the calling endpoint
    handles persistence of draft_subject/draft_body/draft_status.

    Args:
        db: Database session (for model config lookup).
        tenant_id: Tenant UUID.
        quote: CarrierQuote ORM object (needs solicited_at).
        project: BrokerProject ORM object (needs name, language).
        carrier: CarrierConfig ORM object (needs carrier_name, avg_response_days).
        api_key: Optional Anthropic API key override.

    Returns:
        {"status": "drafted", "subject": str, "body": str}
        OR {"status": "not_due", "days_remaining": int}
    """
    now = datetime.now(timezone.utc)

    # Calculate days since solicitation
    if not quote.solicited_at:
        return {"status": "not_due", "days_remaining": 0}

    days_since = (now - quote.solicited_at).days

    # Threshold: avg_response_days + 2 buffer
    threshold = (carrier.avg_response_days or 5) + 2
    # Ensure threshold is int for comparison
    threshold = int(threshold)

    if days_since < threshold:
        return {"status": "not_due", "days_remaining": threshold - days_since}

    # Get model (same as solicitation drafter -- Sonnet for cost)
    model = await get_engine_model(
        db, tenant_id, "solicitation_drafting", "claude-sonnet-4-20250514"
    )

    # Build prompt
    language = getattr(project, "language", None) or "en"
    solicited_date = quote.solicited_at.strftime("%Y-%m-%d")

    language_instruction = ""
    if language == "es":
        language_instruction = (
            "\n\nIMPORTANT: Write the ENTIRE email in Spanish. "
            "All headings, greetings, body text, and closing must be in Spanish."
        )
    elif language != "en":
        language_instruction = (
            f"\n\nIMPORTANT: Write the ENTIRE email in language code '{language}'."
        )

    prompt = f"""Draft a polite follow-up email to {carrier.carrier_name} regarding the quote solicitation for project '{project.name}'.

CONTEXT:
- Original solicitation sent: {solicited_date}
- Days since solicitation: {days_since}
- Carrier: {carrier.carrier_name}
- Project: {project.name}

INSTRUCTIONS:
1. Reference the original solicitation date ({solicited_date})
2. Be polite and professional -- this is a gentle reminder, not a demand
3. Request a status update on the quote
4. Keep it concise (3-5 sentences in body)
5. Include a clear subject line{language_instruction}

RESPONSE FORMAT:
Return a JSON object with exactly two keys:
- "subject": The email subject line
- "body": The email body as plain text (no HTML)

Return ONLY the JSON object, no other text."""

    # Call Claude
    client_kwargs = {}
    if api_key:
        client_kwargs["api_key"] = api_key
    client = AsyncAnthropic(**client_kwargs)

    message = await client.messages.create(
        model=model,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text
    response_text = ""
    for block in message.content:
        if block.type == "text":
            response_text += block.text

    # Parse JSON
    try:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        result = json.loads(cleaned)
        subject = result.get("subject", f"Follow-up: Quote request for {project.name}")
        body = result.get("body", "")
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse followup draft response: %s", e)
        subject = f"Follow-up: Quote request for {project.name}"
        body = response_text

    return {"status": "drafted", "subject": subject, "body": body}
