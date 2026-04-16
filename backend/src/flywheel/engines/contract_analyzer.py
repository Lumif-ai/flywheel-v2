"""
contract_analyzer.py - AI-powered construction contract PDF analysis engine.

Standalone async module that takes a PDF (as bytes), sends it to Claude via
native PDF document blocks, and uses tool_use (function calling) for guaranteed
structured extraction of insurance/surety coverage requirements.

This engine is invoked from a background task after a contract PDF is uploaded
to a BrokerProject. It populates ProjectCoverage rows with confidence scores
and updates the project's analysis_status.

Functions:
  analyze_contract(db, tenant_id, project_id, pdf_content, api_key=None) -> dict
    Main entry point. Orchestrates the full analysis pipeline.
"""

import base64
import logging
from datetime import datetime, timezone
from uuid import UUID

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import BrokerActivity, BrokerProject, ProjectCoverage
from flywheel.engines.model_config import get_engine_model

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """\
You are an expert insurance and surety analyst specializing in construction contracts.
Your job is to read a construction contract PDF and extract ALL insurance and surety
coverage requirements.

ANALYSIS INSTRUCTIONS:
1. Identify every insurance or surety requirement mentioned in the contract
2. For each requirement, extract the coverage type, description, required limits,
   deductibles, and categorize it
3. Assign a confidence score (0.0-1.0) based on how clearly the requirement is stated:
   - 1.0 = Explicit, unambiguous requirement with specific limits
   - 0.7-0.9 = Clear requirement but some details missing
   - 0.4-0.6 = Implied or referenced but not fully specified
   - 0.1-0.3 = Vague mention, may not be a firm requirement
4. Detect the contract language (English or Spanish)
5. Provide a brief summary of the contract scope

COVERAGE CATEGORIES:
- liability: General Liability, Professional Liability, Errors & Omissions
- property: Builder's Risk, Property Insurance, Installation Floater
- surety: Performance Bond, Payment Bond, Bid Bond, Maintenance Bond
- specialty: Pollution/Environmental, Cyber, Marine
- auto: Commercial Auto, Non-Owned Auto
- workers_comp: Workers' Compensation, Employer's Liability

NOTE: Contracts may be in Spanish (Latin American construction industry). Analyze
in the original language and provide coverage_type names in English for consistency.
"""

# Tool schema for structured extraction via Claude's tool_use
EXTRACTION_TOOL = {
    "name": "extract_coverage_requirements",
    "description": "Extract all insurance/surety coverage requirements from the contract",
    "input_schema": {
        "type": "object",
        "properties": {
            "coverages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "coverage_type": {
                            "type": "string",
                            "description": "Type of coverage (e.g., General Liability, Workers Compensation)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Full description of the requirement as stated in the contract",
                        },
                        "limit_amount": {
                            "type": "string",
                            "description": "Required limit amount (e.g., $1,000,000). Null if not specified.",
                        },
                        "deductible": {
                            "type": "string",
                            "description": "Deductible if mentioned, null otherwise",
                        },
                        "category": {
                            "type": "string",
                            "enum": [
                                "liability",
                                "property",
                                "surety",
                                "specialty",
                                "auto",
                                "workers_comp",
                            ],
                        },
                        "confidence_score": {
                            "type": "number",
                            "description": "0.0-1.0 confidence that this is a real requirement",
                        },
                        "contract_clause": {
                            "type": "string",
                            "description": "The specific contract clause or section reference (e.g., Section 11.1)",
                        },
                        "source_excerpt": {
                            "type": "string",
                            "description": "The exact verbatim text from the contract that defines this requirement. Quote the original language directly.",
                        },
                        "source_page": {
                            "type": "integer",
                            "description": "Page number where this requirement appears, if identifiable",
                        },
                    },
                    "required": [
                        "coverage_type",
                        "description",
                        "category",
                        "confidence_score",
                        "source_excerpt",
                    ],
                },
            },
            "contract_language": {
                "type": "string",
                "enum": ["en", "es", "other"],
            },
            "contract_summary": {
                "type": "string",
                "description": "Brief summary of the contract scope",
            },
            "total_coverages_found": {"type": "integer"},
        },
        "required": [
            "coverages",
            "contract_language",
            "total_coverages_found",
        ],
    },
}


def _parse_limit_amount(limit_str: str | None) -> float | None:
    """Parse a human-readable limit amount string into a numeric value.

    Handles formats like '$1,000,000', '1000000', '$2M', '500K', etc.
    Returns None if parsing fails or input is None/empty.
    """
    if not limit_str or not limit_str.strip():
        return None

    cleaned = limit_str.strip().replace("$", "").replace(",", "").replace(" ", "")

    # Handle shorthand: 2M, 500K, etc.
    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    if cleaned and cleaned[-1].lower() in multipliers:
        try:
            return float(cleaned[:-1]) * multipliers[cleaned[-1].lower()]
        except (ValueError, IndexError):
            return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def _score_to_confidence_text(score: float) -> str:
    """Convert a numeric confidence score (0.0-1.0) to a text confidence level.

    Maps to the ProjectCoverage.confidence column which uses text values:
    high (>= 0.7), medium (0.4-0.69), low (< 0.4).
    """
    if score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "medium"
    else:
        return "low"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def analyze_contract(
    db: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    pdf_content: bytes,
    api_key: str | None = None,
) -> dict:
    """Analyze a construction contract PDF and extract coverage requirements.

    Main entry point. Orchestrates the full pipeline:
    1. Set analysis_status='running' on BrokerProject
    2. Get model config for contract_analysis engine
    3. Encode PDF as base64 and send to Claude with tool_use
    4. Parse structured extraction result
    5. Create ProjectCoverage rows for each extracted coverage
    6. Update project status and analysis timestamps
    7. Log BrokerActivity events

    On any failure: sets analysis_status='failed', logs BrokerActivity error
    event, and returns error dict. Does NOT re-raise (safe for background tasks).

    Args:
        db: Async SQLAlchemy session. Caller sets RLS context and manages
            transaction (commit/rollback). This function flushes but does
            not commit.
        tenant_id: Tenant UUID.
        project_id: BrokerProject UUID to analyze.
        pdf_content: Raw PDF bytes.
        api_key: Optional explicit API key. If None, uses
                 settings.flywheel_subsidy_api_key (background job default).

    Returns:
        Dict with keys: status, coverages_found, contract_language,
        contract_summary. On error: status='failed', error=str.
    """
    try:
        # Step 1: Update project analysis_status to 'running'
        result = await db.execute(
            select(BrokerProject).where(
                BrokerProject.id == project_id,
                BrokerProject.tenant_id == tenant_id,
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            logger.error(
                "BrokerProject not found: project_id=%s tenant_id=%s",
                project_id,
                tenant_id,
            )
            return {"status": "failed", "error": "Project not found"}

        project.analysis_status = "running"
        await db.flush()

        # Step 2: Get model config
        model = await get_engine_model(
            db, tenant_id, "contract_analysis", "claude-opus-4-6"
        )

        # Step 3: Build and send Claude API request with PDF document block
        effective_api_key = api_key or settings.flywheel_subsidy_api_key
        client = anthropic.AsyncAnthropic(api_key=effective_api_key)
        pdf_b64 = base64.standard_b64encode(pdf_content).decode("utf-8")

        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=ANALYSIS_SYSTEM_PROMPT,
            tools=[EXTRACTION_TOOL],
            tool_choice={
                "type": "tool",
                "name": "extract_coverage_requirements",
            },
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
                            "text": "Analyze this construction contract and extract all insurance/surety coverage requirements.",
                        },
                    ],
                }
            ],
        )

        # Step 4: Parse tool_use response
        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_block is None:
            raise ValueError(
                "Claude response did not contain a tool_use block"
            )

        extracted = tool_block.input  # Already a dict when using tool_use

        # Step 5: Create ProjectCoverage rows
        coverages_created = []
        for cov in extracted.get("coverages", []):
            coverage = ProjectCoverage(
                tenant_id=tenant_id,
                broker_project_id=project_id,
                coverage_type=cov["coverage_type"],
                display_name=cov["coverage_type"],
                category=cov["category"],
                language=extracted.get("contract_language", "es"),
                required_limit=_parse_limit_amount(cov.get("limit_amount")),
                required_deductible=_parse_limit_amount(cov.get("deductible")),
                required_terms=cov.get("description"),
                contract_clause=cov.get("contract_clause"),
                source_excerpt=cov.get("source_excerpt"),
                source_page=cov.get("source_page"),
                confidence=_score_to_confidence_text(
                    cov.get("confidence_score", 0.5)
                ),
                source="ai_extraction",
                is_manual_override=False,
                metadata_={
                    "raw_limit_text": cov.get("limit_amount"),
                    "raw_deductible_text": cov.get("deductible"),
                    "confidence_score": cov.get("confidence_score"),
                    "ai_description": cov.get("description", ""),
                },
            )
            db.add(coverage)
            coverages_created.append(
                {
                    "coverage_type": cov["coverage_type"],
                    "category": cov["category"],
                    "confidence_score": cov.get("confidence_score"),
                }
            )

        # Step 6: Update project status and metadata
        project.analysis_status = "completed"
        project.analysis_completed_at = datetime.now(timezone.utc)

        if coverages_created:
            from flywheel.api.broker._shared import validate_transition
            validate_transition(
                project.status, "gaps_identified", client_id=project.client_id
            )
            project.status = "gaps_identified"
        # else keep "new_request" — no coverages found

        # Store contract summary in project metadata
        contract_summary = extracted.get("contract_summary", "")
        project_meta = dict(project.metadata_) if project.metadata_ else {}
        project_meta["contract_summary"] = contract_summary
        project_meta["contract_language"] = extracted.get(
            "contract_language", "unknown"
        )
        project_meta["analysis_model"] = model
        project.metadata_ = project_meta

        # Update project language from contract if detected
        detected_language = extracted.get("contract_language")
        if detected_language and detected_language in ("en", "es"):
            project.language = detected_language

        await db.flush()

        # Step 7: Create BrokerActivity for successful analysis
        activity = BrokerActivity(
            tenant_id=tenant_id,
            broker_project_id=project_id,
            activity_type="analysis_completed",
            actor_type="system",
            description=f"Contract analysis completed: {len(coverages_created)} coverage requirements extracted",
            metadata_={
                "coverages_found": len(coverages_created),
                "language": extracted.get("contract_language"),
                "model": model,
            },
        )
        db.add(activity)
        await db.flush()

        logger.info(
            "Contract analysis completed for project_id=%s tenant_id=%s: %d coverages",
            project_id,
            tenant_id,
            len(coverages_created),
        )

        return {
            "status": "completed",
            "coverages_found": len(coverages_created),
            "coverages": coverages_created,
            "contract_language": extracted.get("contract_language"),
            "contract_summary": contract_summary,
        }

    except Exception as exc:
        # Non-fatal error handling: set analysis_status='failed' and log
        import traceback
        logger.error(
            "Contract analysis failed for project_id=%s tenant_id=%s: %s: %s\n%s",
            project_id,
            tenant_id,
            type(exc).__name__,
            exc,
            traceback.format_exc(),
        )

        try:
            # Update project to failed state
            result = await db.execute(
                select(BrokerProject).where(
                    BrokerProject.id == project_id,
                    BrokerProject.tenant_id == tenant_id,
                )
            )
            project = result.scalar_one_or_none()
            if project:
                project.analysis_status = "failed"

            # Log failure activity
            failure_activity = BrokerActivity(
                tenant_id=tenant_id,
                broker_project_id=project_id,
                activity_type="analysis_failed",
                actor_type="system",
                description=f"Contract analysis failed: {type(exc).__name__}",
                metadata_={"error": str(exc)},
            )
            db.add(failure_activity)
            await db.flush()
        except Exception as inner_exc:
            logger.error(
                "Failed to record analysis failure for project_id=%s: %s",
                project_id,
                inner_exc,
            )

        return {"status": "failed", "error": str(exc)}
