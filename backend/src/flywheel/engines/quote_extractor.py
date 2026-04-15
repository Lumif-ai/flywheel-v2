"""
quote_extractor.py - AI-powered quote PDF extraction engine.

Standalone async module that takes a carrier quote PDF (as bytes), sends it to
Claude via native PDF document blocks with tool_use for guaranteed structured
extraction of per-coverage-line quote terms.

This engine cross-references extracted exclusions against project coverage
requirements to detect critical exclusions that conflict with required coverages.

Functions:
  extract_quote(db, tenant_id, quote_id, pdf_content, project_coverages, api_key=None, force=False) -> dict
    Main entry point. Orchestrates the full extraction pipeline.
"""

import base64
import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import BrokerActivity, CarrierQuote, ProjectCoverage
from flywheel.engines.model_config import get_engine_model

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

API_TIMEOUT = 120  # seconds

EXTRACTION_SYSTEM_PROMPT = """\
You are an expert insurance analyst specializing in carrier quote evaluation.
Your job is to read a carrier quote PDF and extract ALL quote terms structured
by coverage line.

EXTRACTION INSTRUCTIONS:
1. Identify every coverage line item in the quote
2. For each line item, extract: coverage type, premium, deductible, limit,
   coinsurance percentage, term length, validity date, exclusions, conditions,
   and endorsements
3. Assign a confidence level based on how clearly the terms are stated:
   - high = Explicit, unambiguous numbers and terms
   - medium = Most terms clear but some missing or ambiguous
   - low = Significant information missing or unclear
4. Extract top-level quote metadata: carrier name, quote date, reference number,
   currency, total premium

CRITICAL EXCLUSION DETECTION:
The project requires the following coverages:
{project_coverages}

For EACH line item exclusion, check if it conflicts with any required coverage.
If an exclusion would leave a required coverage gap, flag it in the
critical_exclusions array with the conflicting coverage type and reason.

NOTE: Quotes may be in Spanish (Latin American insurance market). Extract in
the original language but provide coverage_type names in English for consistency.
"""

# Tool schema for structured extraction via Claude's tool_use
QUOTE_EXTRACTION_TOOL = {
    "name": "extract_quote_terms",
    "description": "Extract all quote terms from a carrier quote PDF, structured by coverage line",
    "input_schema": {
        "type": "object",
        "properties": {
            "carrier_name": {
                "type": "string",
                "description": "Name of the insurance carrier",
            },
            "quote_date": {
                "type": "string",
                "description": "Date of the quote (ISO format YYYY-MM-DD if possible)",
            },
            "quote_reference": {
                "type": "string",
                "description": "Quote reference or policy number",
            },
            "currency": {
                "type": "string",
                "enum": ["MXN", "USD", "EUR"],
                "description": "Currency of the quote",
            },
            "total_premium": {
                "type": "number",
                "description": "Total premium across all coverage lines",
            },
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "coverage_type": {
                            "type": "string",
                            "description": "Type of coverage (e.g., General Liability, Workers Compensation)",
                        },
                        "premium": {
                            "type": "number",
                            "description": "Premium for this coverage line",
                        },
                        "deductible": {
                            "type": "number",
                            "description": "Deductible amount",
                        },
                        "limit_amount": {
                            "type": "number",
                            "description": "Coverage limit amount",
                        },
                        "coinsurance": {
                            "type": "number",
                            "description": "Coinsurance percentage (0-100)",
                        },
                        "term_months": {
                            "type": "integer",
                            "description": "Policy term in months",
                        },
                        "validity_date": {
                            "type": "string",
                            "description": "Quote validity/expiration date (ISO format)",
                        },
                        "exclusions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of exclusions for this coverage",
                        },
                        "conditions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Special conditions or requirements",
                        },
                        "endorsements": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Endorsements included",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Confidence in extraction accuracy",
                        },
                        "critical_exclusions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "exclusion": {
                                        "type": "string",
                                        "description": "The exclusion text",
                                    },
                                    "conflicts_with": {
                                        "type": "string",
                                        "description": "The required coverage type this conflicts with",
                                    },
                                    "reason": {
                                        "type": "string",
                                        "description": "Why this exclusion is critical",
                                    },
                                },
                                "required": ["exclusion", "conflicts_with", "reason"],
                            },
                            "description": "Exclusions that conflict with project coverage requirements",
                        },
                    },
                    "required": ["coverage_type", "premium", "confidence"],
                },
            },
        },
        "required": ["line_items", "carrier_name"],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_pdf_hash(pdf_content: bytes) -> str:
    """Compute SHA-256 hash of PDF content for idempotency."""
    return hashlib.sha256(pdf_content).hexdigest()


def _normalize_coverage_type(name: str) -> str:
    """Normalize coverage type for fuzzy matching: lowercase, strip whitespace."""
    return name.lower().strip().replace("_", " ").replace("-", " ")


def _normalize_compact(name: str) -> str:
    """Compact normalization: lowercase, remove all separators for loose matching."""
    return name.lower().strip().replace("_", "").replace("-", "").replace(" ", "")


def _match_coverage(
    coverage_type: str, project_coverages: list[dict]
) -> dict | None:
    """Find matching ProjectCoverage by fuzzy coverage_type comparison.

    Tries exact normalized match first, then compact match (ignoring all
    separators), then partial/contains match as fallback.

    Returns the first matching coverage dict, or None if no match.
    """
    normalized = _normalize_coverage_type(coverage_type)
    compact = _normalize_compact(coverage_type)

    # Pass 1: exact normalized match (spaces normalized)
    for pc in project_coverages:
        if _normalize_coverage_type(pc.get("coverage_type", "")) == normalized:
            return pc

    # Pass 2: compact match (all separators removed)
    for pc in project_coverages:
        if _normalize_compact(pc.get("coverage_type", "")) == compact:
            logger.debug(
                "Coverage matched via compact normalization: '%s' -> '%s'",
                coverage_type, pc.get("coverage_type", ""),
            )
            return pc

    # Pass 3: partial/contains match (one string contains the other)
    for pc in project_coverages:
        pc_compact = _normalize_compact(pc.get("coverage_type", ""))
        if not pc_compact:
            continue
        if compact in pc_compact or pc_compact in compact:
            logger.debug(
                "Coverage matched via partial match: '%s' -> '%s'",
                coverage_type, pc.get("coverage_type", ""),
            )
            return pc

    logger.warning(
        "No coverage match found for extracted type '%s' among project coverages: %s",
        coverage_type,
        [pc.get("coverage_type", "") for pc in project_coverages],
    )
    return None


def _format_project_coverages_for_prompt(project_coverages: list[dict]) -> str:
    """Format project coverages for inclusion in the system prompt."""
    if not project_coverages:
        return "No specific coverage requirements provided."

    lines = []
    for pc in project_coverages:
        ctype = pc.get("coverage_type", "Unknown")
        category = pc.get("category", "")
        limit = pc.get("required_limit")
        limit_str = f" (required limit: {limit})" if limit else ""
        lines.append(f"- {ctype} [{category}]{limit_str}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def extract_quote(
    db: AsyncSession,
    tenant_id: UUID,
    quote_id: UUID,
    pdf_content: bytes,
    project_coverages: list[dict],
    api_key: str | None = None,
    force: bool = False,
) -> dict:
    """Extract structured quote terms from a carrier quote PDF.

    Main entry point. Orchestrates the full pipeline:
    1. Load CarrierQuote row, verify status
    2. Compute SHA-256 hash for idempotency check
    3. Build Anthropic message with PDF document block + tool_use
    4. Parse structured extraction result
    5. Match line items to project coverages, create/update CarrierQuote rows
    6. Detect critical exclusions and flag them
    7. Update quote status, log BrokerActivity

    On any failure: logs error, sets extraction_error in metadata, does NOT
    change status from "received" (allows retry). Returns error dict.

    Args:
        db: Async SQLAlchemy session (caller manages transaction).
        tenant_id: Tenant UUID.
        quote_id: CarrierQuote UUID to extract from.
        pdf_content: Raw PDF bytes of the carrier quote.
        project_coverages: List of ProjectCoverage dicts with keys:
            id, coverage_type, category, required_limit.
        api_key: Optional explicit API key. Falls back to subsidy key.
        force: If True, re-extract even if source_hash matches.

    Returns:
        Dict with keys: status, line_items_extracted, carrier_name,
        critical_exclusions_found. On error: status='error', message=str.
    """
    try:
        # Step 1: Load CarrierQuote, verify it exists
        result = await db.execute(
            select(CarrierQuote).where(
                CarrierQuote.id == quote_id,
                CarrierQuote.tenant_id == tenant_id,
            )
        )
        quote = result.scalar_one_or_none()
        if quote is None:
            logger.error(
                "CarrierQuote not found: quote_id=%s tenant_id=%s",
                quote_id,
                tenant_id,
            )
            return {"status": "error", "message": "Quote not found"}

        # Step 2: SHA-256 idempotency check
        pdf_hash = _compute_pdf_hash(pdf_content)
        if not force and quote.source_hash == pdf_hash:
            logger.info(
                "Skipping extraction for quote_id=%s — source_hash matches",
                quote_id,
            )
            return {
                "status": "skipped",
                "message": "PDF already extracted (hash matches)",
            }

        # Step 3: Build Anthropic API request
        model = await get_engine_model(
            db, tenant_id, "quote_extraction", "claude-opus-4-6"
        )

        effective_api_key = api_key or settings.flywheel_subsidy_api_key
        client = anthropic.AsyncAnthropic(api_key=effective_api_key)
        pdf_b64 = base64.standard_b64encode(pdf_content).decode("utf-8")

        # Build system prompt with project coverages for critical exclusion detection
        system_prompt = EXTRACTION_SYSTEM_PROMPT.format(
            project_coverages=_format_project_coverages_for_prompt(
                project_coverages
            )
        )

        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            tools=[QUOTE_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_quote_terms"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract all quote terms from this carrier quote document.",
                        },
                    ],
                }
            ],
            timeout=API_TIMEOUT,
        )

        # Step 4: Parse tool_use response
        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_block is None:
            raise ValueError(
                "Claude response did not contain a tool_use block"
            )

        extracted = tool_block.input  # Dict from tool_use

        # Step 5: Process line items — match to project coverages
        line_items = extracted.get("line_items", [])
        carrier_name = extracted.get("carrier_name", "Unknown")
        quotes_updated = []
        critical_exclusions_found = 0

        # Update the original quote row with carrier-level metadata
        quote.carrier_name = carrier_name
        quote.source_hash = pdf_hash

        for idx, item in enumerate(line_items):
            coverage_type = item.get("coverage_type", "")
            matched_coverage = _match_coverage(coverage_type, project_coverages)

            if idx == 0:
                # Update the original quote row with the first line item
                target_quote = quote
            else:
                # Create additional CarrierQuote rows for multi-coverage quotes
                target_quote = CarrierQuote(
                    tenant_id=tenant_id,
                    broker_project_id=quote.broker_project_id,
                    carrier_config_id=quote.carrier_config_id,
                    carrier_name=carrier_name,
                    source_hash=f"{pdf_hash}:{idx}",
                    source=quote.source,
                    import_source=quote.import_source,
                )
                db.add(target_quote)

            # Set coverage link if matched
            if matched_coverage:
                target_quote.coverage_id = UUID(matched_coverage["id"]) if isinstance(matched_coverage["id"], str) else matched_coverage["id"]

            # Set quote terms
            target_quote.premium = item.get("premium")
            target_quote.deductible = item.get("deductible")
            target_quote.limit_amount = item.get("limit_amount")
            target_quote.coinsurance = item.get("coinsurance")
            target_quote.term_months = item.get("term_months")
            target_quote.confidence = item.get("confidence", "medium")

            # Parse validity date if provided
            validity_str = item.get("validity_date")
            if validity_str:
                try:
                    from datetime import date as date_type
                    target_quote.validity_date = date_type.fromisoformat(
                        validity_str[:10]
                    )
                except (ValueError, TypeError):
                    pass

            # Set array fields
            target_quote.exclusions = item.get("exclusions", [])
            target_quote.conditions = item.get("conditions", [])
            target_quote.endorsements = item.get("endorsements", [])

            # Step 6: Critical exclusion detection
            critical_exclusions = item.get("critical_exclusions", [])
            if critical_exclusions:
                target_quote.has_critical_exclusion = True
                details = "; ".join(
                    f"{ce['exclusion']} (conflicts with {ce['conflicts_with']}: {ce['reason']})"
                    for ce in critical_exclusions
                )
                target_quote.critical_exclusion_detail = details
                critical_exclusions_found += len(critical_exclusions)
            else:
                target_quote.has_critical_exclusion = False

            # Step 7: Update status to extracted
            target_quote.status = "extracted"
            target_quote.received_at = datetime.now(timezone.utc)

            quotes_updated.append(
                {
                    "coverage_type": coverage_type,
                    "premium": item.get("premium"),
                    "has_critical_exclusion": bool(critical_exclusions),
                    "confidence": item.get("confidence", "medium"),
                }
            )

        # Update source_hash on original quote
        quote.source_hash = pdf_hash

        await db.flush()

        # Step 8: Log BrokerActivity
        activity = BrokerActivity(
            tenant_id=tenant_id,
            broker_project_id=quote.broker_project_id,
            activity_type="quote_extracted",
            actor_type="system",
            description=(
                f"Quote extracted from {carrier_name}: "
                f"{len(quotes_updated)} coverage lines, "
                f"{critical_exclusions_found} critical exclusions"
            ),
            metadata_={
                "carrier_name": carrier_name,
                "line_items_extracted": len(quotes_updated),
                "critical_exclusions_found": critical_exclusions_found,
                "model": model,
                "quote_reference": extracted.get("quote_reference"),
                "currency": extracted.get("currency"),
                "total_premium": extracted.get("total_premium"),
            },
        )
        db.add(activity)
        await db.flush()

        logger.info(
            "Quote extraction completed for quote_id=%s tenant_id=%s: "
            "%d line items, %d critical exclusions",
            quote_id,
            tenant_id,
            len(quotes_updated),
            critical_exclusions_found,
        )

        return {
            "status": "extracted",
            "line_items_extracted": len(quotes_updated),
            "carrier_name": carrier_name,
            "critical_exclusions_found": critical_exclusions_found,
            "line_items": quotes_updated,
            "quote_reference": extracted.get("quote_reference"),
            "currency": extracted.get("currency"),
            "total_premium": extracted.get("total_premium"),
        }

    except anthropic.APITimeoutError:
        logger.error(
            "Quote extraction timed out after %ds for quote_id=%s tenant_id=%s",
            API_TIMEOUT,
            quote_id,
            tenant_id,
        )
        # Set metadata flag but don't change status (allow retry)
        try:
            result = await db.execute(
                select(CarrierQuote).where(
                    CarrierQuote.id == quote_id,
                    CarrierQuote.tenant_id == tenant_id,
                )
            )
            q = result.scalar_one_or_none()
            if q:
                meta = dict(q.metadata_) if q.metadata_ else {}
                meta["extraction_error"] = f"API timeout after {API_TIMEOUT}s"
                meta["extraction_attempted_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
                q.metadata_ = meta
                await db.flush()
        except Exception as inner_exc:
            logger.error(
                "Failed to record timeout for quote_id=%s: %s",
                quote_id,
                inner_exc,
            )

        return {
            "status": "error",
            "message": f"API timeout after {API_TIMEOUT} seconds",
        }

    except Exception as exc:
        logger.error(
            "Quote extraction failed for quote_id=%s tenant_id=%s: %s: %s",
            quote_id,
            tenant_id,
            type(exc).__name__,
            exc,
        )

        # Set metadata flag but don't change status (allow retry)
        try:
            result = await db.execute(
                select(CarrierQuote).where(
                    CarrierQuote.id == quote_id,
                    CarrierQuote.tenant_id == tenant_id,
                )
            )
            q = result.scalar_one_or_none()
            if q:
                meta = dict(q.metadata_) if q.metadata_ else {}
                meta["extraction_error"] = f"{type(exc).__name__}: {exc}"
                meta["extraction_attempted_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
                q.metadata_ = meta
                await db.flush()
        except Exception as inner_exc:
            logger.error(
                "Failed to record extraction failure for quote_id=%s: %s",
                quote_id,
                inner_exc,
            )

        return {"status": "error", "message": str(exc)}
