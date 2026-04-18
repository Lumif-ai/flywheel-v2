"""
quote_extractor.py - Pattern 3a helpers for carrier quote extraction.

Phase 150.1 Plan 04 completed the CC-as-Brain migration by deleting the
legacy `extract_quote` function (which constructed an async Anthropic
client at runtime). Backend no longer runs any LLM call for quote
extraction; Claude-in-conversation owns inference. The module exposes
only Pattern 3a public helpers:

  * `QUOTE_EXTRACTION_TOOL` — Anthropic tool schema for structured extraction.
  * `build_quote_extraction_prompt(project_coverages)`
    → rendered prompt string for /extract/quote-extraction.
  * `persist_quote_extraction(db, ..., tool_use_output)`
    → persists Claude's tool_use output into CarrierQuote rows.

Supporting helpers (_compute_pdf_hash, _normalize_coverage_type,
_match_coverage, _format_project_coverages_for_prompt) remain for the
Pattern 3a flow.

CC-as-Brain invariant (Phase 150.1): this module MUST NOT import or
construct an Anthropic async client. The `test_broker_zero_anthropic.py`
regression grep-guards enforce this at CI time.
"""

import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import BrokerActivity, CarrierQuote, ProjectCoverage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

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


# Public alias (Plan 02 — Pattern 3a) — extract endpoints import this.
format_project_coverages_for_prompt = _format_project_coverages_for_prompt


def build_quote_extraction_prompt(project_coverages: list[dict]) -> str:
    """Render the full quote-extraction system prompt.

    Phase 150.1 Plan 02 — Pattern 3a public helper. Used by the
    `POST /extract/quote-extraction` endpoint to return the fully-rendered
    prompt so Claude-in-conversation can invoke it with the PDF.

    Args:
        project_coverages: List of ProjectCoverage dicts with keys
            id, coverage_type, category, required_limit.

    Returns:
        Fully rendered system prompt string (ready to send with the PDF).
    """
    return EXTRACTION_SYSTEM_PROMPT.format(
        project_coverages=_format_project_coverages_for_prompt(project_coverages)
    )


# ---------------------------------------------------------------------------
# Phase 150.1 Plan 04 — legacy `extract_quote` DELETED.
# Backend owns zero LLM calls for quote extraction. Claude-in-conversation
# consumes `build_quote_extraction_prompt` + `QUOTE_EXTRACTION_TOOL`
# (Pattern 3a). The /save/quote-extraction endpoint calls
# `persist_quote_extraction` below with Claude's tool_use output shaped as
# QUOTE_EXTRACTION_TOOL.input_schema — no backend LLM call involvement.
# ---------------------------------------------------------------------------


async def persist_quote_extraction(
    db: AsyncSession,
    tenant_id: UUID,
    quote_id: UUID,
    tool_use_output: dict,
    project_coverages: list[dict] | None = None,
) -> dict:
    """Persist Claude's quote-extraction tool_use output.

    Mirrors the post-LLM persistence logic in `extract_quote` (lines ~388-500)
    without calling Anthropic. Creates/updates CarrierQuote rows for each
    line item, detects critical exclusions, logs BrokerActivity.

    Args:
        db: Async SQLAlchemy session (caller manages transaction).
        tenant_id: Tenant UUID.
        quote_id: CarrierQuote UUID — identifies the row to update (first
            line item writes to this row; additional line items create new
            CarrierQuote rows in the same project).
        tool_use_output: Dict matching QUOTE_EXTRACTION_TOOL.input_schema.
        project_coverages: Optional — if the caller has already loaded them.
            If None, the function loads them from the project linked to
            this quote.

    Returns:
        {
            "status": "extracted",
            "line_items_extracted": int,
            "carrier_name": str,
            "critical_exclusions_found": int,
            "line_items": list[dict],
        }
    """
    result = await db.execute(
        select(CarrierQuote).where(
            CarrierQuote.id == quote_id,
            CarrierQuote.tenant_id == tenant_id,
        )
    )
    quote = result.scalar_one_or_none()
    if quote is None:
        raise ValueError(
            f"CarrierQuote not found for persist_quote_extraction: "
            f"quote_id={quote_id} tenant_id={tenant_id}"
        )

    # Load project coverages if caller didn't supply them.
    if project_coverages is None:
        cov_result = await db.execute(
            select(ProjectCoverage).where(
                ProjectCoverage.broker_project_id == quote.broker_project_id
            )
        )
        project_coverages = [
            {
                "id": str(c.id),
                "coverage_type": c.coverage_type,
                "coverage_type_key": c.coverage_type_key,
                "category": c.category,
                "required_limit": float(c.required_limit)
                if c.required_limit is not None
                else None,
            }
            for c in cov_result.scalars().all()
        ]

    line_items = tool_use_output.get("line_items", []) or []
    carrier_name = tool_use_output.get("carrier_name", "Unknown")
    critical_exclusions_found = 0
    quotes_updated: list[dict] = []

    # Update the original quote row with top-level metadata.
    quote.carrier_name = carrier_name

    for idx, item in enumerate(line_items):
        if not isinstance(item, dict):
            continue
        coverage_type = item.get("coverage_type", "")
        matched_coverage = _match_coverage(coverage_type, project_coverages)

        if idx == 0:
            target_quote = quote
        else:
            target_quote = CarrierQuote(
                tenant_id=tenant_id,
                broker_project_id=quote.broker_project_id,
                carrier_config_id=quote.carrier_config_id,
                carrier_name=carrier_name,
                source_hash=f"{quote.source_hash or 'cc-brain'}:{idx}",
                source=quote.source,
                import_source=quote.import_source,
            )
            db.add(target_quote)

        if matched_coverage:
            mid = matched_coverage["id"]
            target_quote.coverage_id = UUID(mid) if isinstance(mid, str) else mid

        target_quote.premium = item.get("premium")
        target_quote.deductible = item.get("deductible")
        target_quote.limit_amount = item.get("limit_amount")
        target_quote.coinsurance = item.get("coinsurance")
        target_quote.term_months = item.get("term_months")
        target_quote.confidence = item.get("confidence", "medium")

        validity_str = item.get("validity_date")
        if validity_str:
            try:
                from datetime import date as date_type

                target_quote.validity_date = date_type.fromisoformat(
                    str(validity_str)[:10]
                )
            except (ValueError, TypeError):
                pass

        target_quote.exclusions = item.get("exclusions", []) or []
        target_quote.conditions = item.get("conditions", []) or []
        target_quote.endorsements = item.get("endorsements", []) or []

        critical_exclusions = item.get("critical_exclusions", []) or []
        if critical_exclusions:
            target_quote.has_critical_exclusion = True
            details = "; ".join(
                f"{ce.get('exclusion', '')} "
                f"(conflicts with {ce.get('conflicts_with', '')}: "
                f"{ce.get('reason', '')})"
                for ce in critical_exclusions
                if isinstance(ce, dict)
            )
            target_quote.critical_exclusion_detail = details
            critical_exclusions_found += len(critical_exclusions)
        else:
            target_quote.has_critical_exclusion = False

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

    await db.flush()

    # Log BrokerActivity.
    activity = BrokerActivity(
        tenant_id=tenant_id,
        broker_project_id=quote.broker_project_id,
        activity_type="quote_extracted",
        actor_type="system",
        description=(
            f"Quote extracted (CC-as-Brain) from {carrier_name}: "
            f"{len(quotes_updated)} coverage lines, "
            f"{critical_exclusions_found} critical exclusions"
        ),
        metadata_={
            "carrier_name": carrier_name,
            "line_items_extracted": len(quotes_updated),
            "critical_exclusions_found": critical_exclusions_found,
            "model": "claude-in-conversation",
            "quote_reference": tool_use_output.get("quote_reference"),
            "currency": tool_use_output.get("currency"),
            "total_premium": tool_use_output.get("total_premium"),
        },
    )
    db.add(activity)
    await db.flush()

    return {
        "status": "extracted",
        "line_items_extracted": len(quotes_updated),
        "carrier_name": carrier_name,
        "critical_exclusions_found": critical_exclusions_found,
        "line_items": quotes_updated,
        "quote_reference": tool_use_output.get("quote_reference"),
        "currency": tool_use_output.get("currency"),
        "total_premium": tool_use_output.get("total_premium"),
    }
