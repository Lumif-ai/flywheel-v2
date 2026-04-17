"""
contract_analyzer.py - AI-powered construction contract PDF analysis engine.

Standalone async module that takes a PDF (as bytes), sends it to Claude via
native PDF document blocks, and uses tool_use (function calling) for guaranteed
structured extraction of insurance/surety coverage requirements.

This engine is invoked from a background task after a contract PDF is uploaded
to a BrokerProject. It populates ProjectCoverage rows with confidence scores
and updates the project's analysis_status.

Functions:
  analyze_contract(db, tenant_id, project_id, pdfs, api_key=None) -> dict
    Main entry point. Orchestrates the full analysis pipeline over all project PDFs.
"""

import base64
import logging
from datetime import datetime, timezone
from uuid import UUID

import anthropic
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.config import settings
from flywheel.db.models import (
    BrokerActivity,
    BrokerProject,
    CoverageType,
    ProjectCoverage,
)
from flywheel.engines.model_config import get_engine_model

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

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
                        "coverage_type_key": {
                            "type": "string",
                            "description": "Canonical key from the provided coverage taxonomy. If no existing key matches and this is a genuinely new coverage type, propose a new snake_case key.",
                        },
                        "is_new_type": {
                            "type": "boolean",
                            "description": "True if this coverage type is not in the provided taxonomy and requires a new entry.",
                        },
                        "new_type_display_names": {
                            "type": "object",
                            "description": "Required if is_new_type=true. Display names by locale, e.g. {\"en\": \"Earthquake Insurance\", \"es\": \"Seguro de Terremoto\"}.",
                        },
                        "raw_coverage_name": {
                            "type": "string",
                            "description": "The coverage name as written in the contract (verbatim).",
                        },
                        "suggested_alias": {
                            "type": "string",
                            "description": "If the raw name is a new phrasing for an existing key, suggest it as an alias.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Full description of the requirement as stated in the contract.",
                        },
                        "limit_amount": {
                            "type": "number",
                            "description": "Required limit as a number (e.g., 1000000). Null if not specified.",
                        },
                        "limit_currency": {
                            "type": "string",
                            "description": "Currency of the limit as stated in contract. Infer from context: $ in Mexican contracts = MXN, USD/US$ = USD.",
                        },
                        "deductible": {
                            "type": "string",
                            "description": "Deductible if mentioned, null otherwise.",
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
                            "description": "0.0-1.0 confidence that this is a real requirement.",
                        },
                        "contract_clause": {
                            "type": "string",
                            "description": "The specific contract clause or section reference (e.g., Section 11.1).",
                        },
                        "source_excerpt": {
                            "type": "string",
                            "description": "The exact verbatim text from the contract that defines this requirement. Quote the original language directly.",
                        },
                        "source_page": {
                            "type": "integer",
                            "description": "Page number where this requirement appears, if identifiable.",
                        },
                        "source_document_filename": {
                            "type": "string",
                            "description": "Filename of the document this coverage was extracted from. Must match one of the input document filenames exactly.",
                        },
                    },
                    "required": [
                        "coverage_type_key",
                        "is_new_type",
                        "raw_coverage_name",
                        "description",
                        "category",
                        "confidence_score",
                        "source_document_filename",
                    ],
                },
            },
            "contract_language": {
                "type": "string",
                "enum": ["en", "es", "pt", "other"],
            },
            "contract_summary": {
                "type": "string",
                "description": "Brief summary of the contract scope.",
            },
            "total_coverages_found": {"type": "integer"},
            "primary_contract_filename": {
                "type": "string",
                "description": "Filename of the document you identified as the PRIMARY CONTRACT (the MSA/construction agreement being executed). Must match one of the input document filenames exactly. Return empty string if none of the inputs is a primary contract.",
            },
        },
        "required": [
            "coverages",
            "contract_language",
            "total_coverages_found",
            "primary_contract_filename",
        ],
    },
}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_extraction_prompt(
    coverage_types: list[dict], project_currency: str
) -> str:
    """Build the extraction system prompt with embedded taxonomy.

    Args:
        coverage_types: List of dicts with key, display_name, aliases, category.
        project_currency: The project's default currency (e.g. 'MXN').

    Returns:
        Full system prompt string for the extraction API call.
    """
    taxonomy_block = "\n".join(
        f"- {ct['key']}: {ct['display_name']} (aliases: {', '.join(ct['aliases'])})"
        for ct in coverage_types
    )

    return f"""\
You are an expert insurance and surety analyst specializing in construction contracts.
You will receive ONE OR MORE documents from a single construction project and must
extract ALL insurance and surety coverage REQUIREMENTS.

DOCUMENT TYPES you may receive:
- Primary contract / MSA (e.g., "Contrato de Obra", "Master Service Agreement") -- extract from this.
- Exhibits / annexes / schedules referenced by the contract (bond schedules,
  insurance requirement annexes) -- extract from these and attribute to their filename.
- Current policy summaries / certificates of insurance / COIs -- DO NOT extract.
  These describe existing policies, not contract requirements.
- Quote letters from carriers or surety companies -- DO NOT extract. These are proposals,
  not requirements.

Identify the PRIMARY CONTRACT (the agreement being executed) and set
primary_contract_filename to its exact input filename. If multiple documents look
like contracts, pick the one with the most comprehensive scope/requirements body.

For every coverage you extract, set source_document_filename to the exact filename
of the input document where you found it.

COVERAGE TYPE TAXONOMY -- map each coverage to one of these canonical keys:
{taxonomy_block}

INSTRUCTIONS:
- Extract every insurance coverage and every surety bond stated as a REQUIREMENT of the
  contract or its requirement-annexes. Do not skip items because a limit or detail is
  missing; use lower confidence_score instead.
- Match each coverage to the most appropriate canonical key above. Spanish/Portuguese
  phrasings map to English keys (e.g., "Responsabilidad Civil General" -> general_liability,
  "Fianza de Cumplimiento" -> performance_bond, "Todo Riesgo Construccion" -> builders_risk,
  "Fianza de Anticipo" -> advance_payment_bond, "Fianza de Vicios Ocultos" -> maintenance_bond,
  "Fianza de Pago" -> payment_bond, "Responsabilidad Civil Vehicular" -> auto,
  "Riesgos de Trabajo" -> workers_compensation).
- If the contract uses a different name for an existing type (e.g., "CGL" for general_liability),
  use the existing key and set suggested_alias to the contract's phrasing.
- Only set is_new_type=true if the coverage is genuinely distinct from ALL existing types.
  When creating a new type, provide display_names in English and the contract's language.
- Use snake_case for new keys, following the pattern of existing keys.
- total_coverages_found MUST equal the length of the coverages array.

LIMIT EXTRACTION:
- Extract the numeric limit amount as a number (not a string).
- Determine the currency from contract context:
  - "$" in Mexican contracts = MXN, "USD" or "US$" = USD
  - If ambiguous or not stated, omit limit_currency (project default: {project_currency})
- If the contract states a limit in a currency different from {project_currency}, extract
  the original amount and currency. The system will flag the mismatch.

CONFIDENCE SCORING:
- 1.0 = Explicit, unambiguous requirement with specific limits
- 0.7-0.9 = Clear requirement but some details missing
- 0.4-0.6 = Implied or referenced but not fully specified
- 0.1-0.3 = Vague mention, may not be a firm requirement

COVERAGE CATEGORIES:
- liability: General Liability, Professional Liability, Errors & Omissions
- property: Builder's Risk, Property Insurance, Installation Floater
- surety: Performance Bond, Payment Bond, Bid Bond, Maintenance Bond
- specialty: Pollution/Environmental, Cyber, Marine
- auto: Commercial Auto, Non-Owned Auto
- workers_comp: Workers' Compensation, Employer's Liability

NOTE: Contracts may be in Spanish or Portuguese (Latin American construction industry).
Analyze in the original language and provide raw_coverage_name in the original language.
Always include source_excerpt with the exact verbatim text from the contract."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_limit(amount: float | int | str | None) -> float | None:
    """Validate and normalize a limit amount from AI extraction.

    Handles both numeric values and currency strings like
    "MX$42,000,000", "$5,000,000 USD", "MX$4,200,000 (10% of contract value)".
    """
    if amount is None:
        return None
    try:
        val = float(amount)
        return val if val > 0 else None
    except (TypeError, ValueError):
        pass
    # AI sometimes returns currency strings instead of numbers
    if isinstance(amount, str):
        import re
        # Remove parenthetical notes like "(10% of contract value)"
        cleaned = re.sub(r"\(.*?\)", "", amount)
        # Strip currency prefixes/suffixes and whitespace
        cleaned = re.sub(r"[A-Za-z$€£¥]+", "", cleaned).strip()
        # Remove commas (thousand separators)
        cleaned = cleaned.replace(",", "")
        try:
            val = float(cleaned)
            return val if val > 0 else None
        except (TypeError, ValueError):
            return None
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


async def _load_taxonomy(
    db: AsyncSession, country_code: str, lob: str
) -> list[dict]:
    """Load filtered coverage type taxonomy for the given context.

    Queries CoverageType where is_active=True AND (countries is empty OR
    country_code is in countries) AND (lines_of_business is empty OR lob
    is in lines_of_business).

    Args:
        db: Async SQLAlchemy session.
        country_code: Project country code (e.g. 'MX').
        lob: Line of business (e.g. 'construction').

    Returns:
        List of dicts with key, display_name, aliases (flat list), category.
    """
    result = await db.execute(
        select(CoverageType).where(CoverageType.is_active.is_(True))
    )
    all_types = result.scalars().all()

    filtered = []
    for ct in all_types:
        # Filter by country: include if countries is empty or country matches
        if ct.countries and country_code not in ct.countries:
            continue
        # Filter by LOB: include if lines_of_business is empty or lob matches
        if ct.lines_of_business and lob not in ct.lines_of_business:
            continue

        # Flatten aliases from all languages into a single list
        flat_aliases: list[str] = []
        if ct.aliases and isinstance(ct.aliases, dict):
            for lang_aliases in ct.aliases.values():
                if isinstance(lang_aliases, list):
                    flat_aliases.extend(lang_aliases)

        # Get English display name (fallback to first available)
        display_name = ""
        if ct.display_names and isinstance(ct.display_names, dict):
            display_name = ct.display_names.get("en", "")
            if not display_name:
                # Fallback to first available language
                for name in ct.display_names.values():
                    if name:
                        display_name = name
                        break

        filtered.append(
            {
                "key": ct.key,
                "display_name": display_name or ct.key,
                "aliases": flat_aliases,
                "category": ct.category,
            }
        )

    return filtered


async def _process_extracted_coverage(
    cov: dict,
    project: BrokerProject,
    db: AsyncSession,
    contract_language: str,
) -> ProjectCoverage:
    """Process a single AI-extracted coverage into a ProjectCoverage row.

    Handles:
    - New taxonomy type creation (is_new_type=True)
    - Alias learning (suggested_alias for existing types)
    - Currency mismatch detection
    - ProjectCoverage row creation with canonical key

    Args:
        cov: Single coverage dict from AI extraction.
        project: The BrokerProject being analyzed.
        db: Async SQLAlchemy session.
        contract_language: Detected contract language code.

    Returns:
        ProjectCoverage instance (not yet added to session).
    """
    key = cov["coverage_type_key"]

    # Handle new taxonomy type creation
    if cov.get("is_new_type"):
        new_entry = CoverageType(
            key=key,
            category=cov["category"],
            display_names=cov.get("new_type_display_names", {}),
            aliases={},
            countries=[project.country_code] if project.country_code else [],
            lines_of_business=(
                [project.line_of_business] if project.line_of_business else []
            ),
            is_verified=False,
            added_by="ai_extraction",
        )
        try:
            db.add(new_entry)
            await db.flush()
        except IntegrityError:
            # Duplicate key — another extraction already created it
            await db.rollback()
            logger.info(
                "CoverageType '%s' already exists, skipping insert", key
            )

    elif cov.get("suggested_alias"):
        # Enrich existing taxonomy entry with new alias
        existing = await db.get(CoverageType, key)
        if existing:
            lang = contract_language or project.language or "en"
            aliases = dict(existing.aliases) if existing.aliases else {}
            lang_aliases = list(aliases.get(lang, []))
            if cov["suggested_alias"] not in lang_aliases:
                lang_aliases.append(cov["suggested_alias"])
                aliases[lang] = lang_aliases
                # Reassignment pattern for SQLAlchemy change detection
                existing.aliases = {**aliases}
                logger.info(
                    "Added alias '%s' to CoverageType '%s' (lang=%s)",
                    cov["suggested_alias"],
                    key,
                    lang,
                )

    # Handle currency mismatch
    limit_currency = cov.get("limit_currency")
    currency_note = None
    if limit_currency and limit_currency != project.currency:
        currency_note = (
            f"Contract states limit in {limit_currency}, "
            f"project currency is {project.currency}"
        )

    # Build metadata
    meta = {
        "raw_coverage_name": cov.get("raw_coverage_name", ""),
        "limit_currency": limit_currency,
        "currency_mismatch": currency_note,
        "confidence_score": cov.get("confidence_score"),
        "ai_description": cov.get("description", ""),
        "raw_limit_text": str(cov.get("limit_amount")) if cov.get("limit_amount") is not None else None,
        "raw_deductible_text": cov.get("deductible"),
        "source_document_filename": cov.get("source_document_filename"),
    }

    # Create ProjectCoverage row
    coverage = ProjectCoverage(
        tenant_id=project.tenant_id,
        broker_project_id=project.id,
        coverage_type_key=key,
        coverage_type=cov.get("raw_coverage_name", key),  # backward compat
        display_name=cov.get("raw_coverage_name", key),
        category=cov["category"],
        language=contract_language or "es",
        required_limit=_validate_limit(cov.get("limit_amount")),
        required_deductible=_validate_limit(
            float(cov["deductible"]) if cov.get("deductible") else None
        )
        if cov.get("deductible") and cov["deductible"].replace(".", "").replace("-", "").isdigit()
        else None,
        required_terms=cov.get("description"),
        contract_clause=cov.get("contract_clause"),
        source_excerpt=cov.get("source_excerpt"),
        source_page=cov.get("source_page"),
        confidence=_score_to_confidence_text(
            cov.get("confidence_score", 0.5)
        ),
        source="ai_extraction",
        is_manual_override=False,
        metadata_=meta,
    )

    return coverage


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def analyze_contract(
    db: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    pdfs: list[tuple[UUID, str, bytes]],
    api_key: str | None = None,
) -> dict:
    """Analyze one or more construction-project PDFs and extract coverage requirements.

    Accepts the full set of PDFs attached to a project. The model classifies which
    document is the primary contract and extracts coverage requirements from the
    contract + its referenced exhibits/annexes. source_document_id is backfilled
    from the model's classification.

    On truncation or count mismatch: sets analysis_status='failed'. Does NOT accept
    partial extraction as success.

    Args:
        db: Async SQLAlchemy session. Caller sets RLS context and manages
            transaction (commit/rollback). This function flushes but does
            not commit.
        tenant_id: Tenant UUID.
        project_id: BrokerProject UUID to analyze.
        pdfs: List of (file_id, filename, content_bytes) tuples. Must be non-empty.
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

        # Step 2: Load taxonomy for project context
        taxonomy_types = await _load_taxonomy(
            db, project.country_code, project.line_of_business
        )
        logger.info(
            "Loaded %d taxonomy types for country=%s lob=%s",
            len(taxonomy_types),
            project.country_code,
            project.line_of_business,
        )

        # Step 3: Get model config
        model = await get_engine_model(
            db, tenant_id, "contract_analysis", "claude-opus-4-6"
        )

        # Step 4: Build dynamic prompt with taxonomy
        system_prompt = build_extraction_prompt(taxonomy_types, project.currency)

        # Step 5: Build and send Claude API request with one document block per PDF
        if not pdfs:
            raise ValueError("analyze_contract called with no PDFs")

        effective_api_key = api_key or settings.flywheel_subsidy_api_key
        client = anthropic.AsyncAnthropic(api_key=effective_api_key)

        content_blocks: list[dict] = []
        for _, filename, pdf_bytes in pdfs:
            pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
            content_blocks.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                    "title": filename,
                }
            )

        filename_list = "\n".join(f"  - {f}" for _, f, _ in pdfs)
        content_blocks.append(
            {
                "type": "text",
                "text": (
                    f"The {len(pdfs)} documents above are all from the same construction project. "
                    f"Their filenames are:\n{filename_list}\n\n"
                    "Identify the primary contract, ignore policy summaries and quote letters, "
                    "and extract every insurance and surety coverage REQUIREMENT from the contract "
                    "and any requirement-annexes. Set source_document_filename on each coverage "
                    "and primary_contract_filename at the top level, using the filenames above."
                ),
            }
        )

        response = await client.messages.create(
            model=model,
            max_tokens=16384,
            system=system_prompt,
            tools=[EXTRACTION_TOOL],
            tool_choice={
                "type": "tool",
                "name": "extract_coverage_requirements",
            },
            messages=[{"role": "user", "content": content_blocks}],
        )

        # Step 6: Parse tool_use response
        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_block is None:
            raise ValueError(
                "Claude response did not contain a tool_use block"
            )

        extracted = tool_block.input  # Already a dict when using tool_use

        # Diagnostic: surface response shape so 0-coverage outcomes are not silent
        stop_reason = getattr(response, "stop_reason", None)
        usage = getattr(response, "usage", None)
        output_tokens = getattr(usage, "output_tokens", None) if usage else None
        input_tokens = getattr(usage, "input_tokens", None) if usage else None
        extracted_keys = (
            list(extracted.keys()) if isinstance(extracted, dict) else None
        )
        raw_coverages = (
            extracted.get("coverages", []) if isinstance(extracted, dict) else []
        )
        logger.info(
            "Contract analysis API response: project_id=%s stop_reason=%s "
            "input_tokens=%s output_tokens=%s extracted_keys=%s coverages_in_response=%d "
            "total_coverages_found=%s contract_language=%s",
            project_id,
            stop_reason,
            input_tokens,
            output_tokens,
            extracted_keys,
            len(raw_coverages) if isinstance(raw_coverages, list) else -1,
            extracted.get("total_coverages_found") if isinstance(extracted, dict) else None,
            extracted.get("contract_language") if isinstance(extracted, dict) else None,
        )
        # Fail fast on truncation — partial extractions must not be saved as success
        if stop_reason == "max_tokens":
            raise ValueError(
                f"Response truncated at max_tokens (output_tokens={output_tokens}). "
                "Partial extraction rejected."
            )

        # Fail fast on count mismatch — indicates truncation or model inconsistency
        reported_total = (
            extracted.get("total_coverages_found")
            if isinstance(extracted, dict)
            else None
        )
        actual_count = len(raw_coverages) if isinstance(raw_coverages, list) else 0
        if (
            reported_total is not None
            and isinstance(reported_total, int)
            and reported_total != actual_count
        ):
            raise ValueError(
                f"total_coverages_found={reported_total} but coverages array has "
                f"{actual_count} items — response inconsistent, likely truncated"
            )

        contract_language = extracted.get("contract_language", "es")

        # Clear prior AI-extracted coverages for this project to prevent duplicates on
        # re-analysis. Manually-added or manually-overridden coverages are preserved.
        from sqlalchemy import delete

        delete_stmt = delete(ProjectCoverage).where(
            ProjectCoverage.broker_project_id == project_id,
            ProjectCoverage.tenant_id == tenant_id,
            ProjectCoverage.source == "ai_extraction",
            ProjectCoverage.is_manual_override.is_(False),
        )
        delete_result = await db.execute(delete_stmt)
        if delete_result.rowcount:
            logger.info(
                "Cleared %d prior AI-extracted coverages for project_id=%s",
                delete_result.rowcount,
                project_id,
            )

        # Backfill source_document_id from the model's classification of the primary
        # contract. This replaces the prior "first uploaded PDF" heuristic, which
        # could point source_document_id at an annex or policy summary.
        primary_filename = (extracted.get("primary_contract_filename") or "").strip()
        if primary_filename:
            pdf_by_name = {fname: fid for fid, fname, _ in pdfs}
            matched_id = pdf_by_name.get(primary_filename)
            if matched_id is not None:
                project.source_document_id = matched_id
            else:
                logger.warning(
                    "primary_contract_filename=%r not in input PDFs for project_id=%s",
                    primary_filename,
                    project_id,
                )

        # Step 7: Process each coverage through taxonomy pipeline
        coverages_created = []
        for cov in extracted.get("coverages", []):
            coverage = await _process_extracted_coverage(
                cov, project, db, contract_language
            )
            db.add(coverage)
            coverages_created.append(
                {
                    "coverage_type_key": cov["coverage_type_key"],
                    "coverage_type": cov.get("raw_coverage_name", cov["coverage_type_key"]),
                    "category": cov["category"],
                    "confidence_score": cov.get("confidence_score"),
                    "is_new_type": cov.get("is_new_type", False),
                    "limit_currency": cov.get("limit_currency"),
                }
            )

        # Step 8: Update project status and metadata
        project.analysis_status = "completed"
        project.analysis_completed_at = datetime.now(timezone.utc)

        if coverages_created and project.status != "gaps_identified":
            from flywheel.api.broker._shared import validate_transition
            validate_transition(
                project.status, "gaps_identified", client_id=project.client_id
            )
            project.status = "gaps_identified"
        # else keep current status -- no coverages found, or already in gaps_identified (re-run)

        # Store contract summary in project metadata
        contract_summary = extracted.get("contract_summary", "")
        project_meta = dict(project.metadata_) if project.metadata_ else {}
        project_meta["contract_summary"] = contract_summary
        project_meta["contract_language"] = contract_language
        project_meta["analysis_model"] = model
        project.metadata_ = project_meta

        # Update project language from contract if detected
        if contract_language and contract_language in ("en", "es", "pt"):
            project.language = contract_language

        await db.flush()

        # Step 9: Create BrokerActivity for successful analysis
        activity = BrokerActivity(
            tenant_id=tenant_id,
            broker_project_id=project_id,
            activity_type="analysis_completed",
            actor_type="system",
            description=f"Contract analysis completed: {len(coverages_created)} coverage requirements extracted",
            metadata_={
                "coverages_found": len(coverages_created),
                "language": contract_language,
                "model": model,
                "taxonomy_types_loaded": len(taxonomy_types),
                "new_types_created": sum(
                    1 for c in coverages_created if c.get("is_new_type")
                ),
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
            "contract_language": contract_language,
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
