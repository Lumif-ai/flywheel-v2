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
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
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
from flywheel.engines.gap_detector import detect_gaps, summarize_gaps
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
                        "source_excerpt",  # NEW — INFRA-05: every AI-extracted coverage must carry its verbatim source
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
            "misrouted_documents": {
                "type": "array",
                "description": (
                    "Documents in this call that appear to be CURRENT POLICIES (COIs, "
                    "declarations pages, in-force schedules) or CARRIER QUOTES rather than "
                    "contract requirements. Populate ONLY when very confident. Do NOT "
                    "extract coverages from these — list them here instead."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "source_document_filename": {"type": "string"},
                        "detected_type": {
                            "type": "string",
                            "enum": ["coverage", "quote", "unknown"],
                            "description": "Best guess at what the document actually is.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "One-sentence human-readable reason.",
                        },
                    },
                    "required": ["source_document_filename", "detected_type"],
                },
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


def _format_taxonomy(coverage_types: list[dict]) -> str:
    """Format the coverage taxonomy into a prompt-ready bullet list.

    Shared by build_extraction_prompt and build_policy_extraction_prompt so both
    extraction passes see the same taxonomy rendering.
    """
    return "\n".join(
        f"- {ct['key']}: {ct['display_name']} (aliases: {', '.join(ct['aliases'])})"
        for ct in coverage_types
    )


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
    taxonomy_block = _format_taxonomy(coverage_types)

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

If a document in this call appears to be a Certificate of Insurance (COI), a policy
declarations page, an in-force coverage schedule, or a carrier quote letter, DO NOT
extract coverages from it. Instead, add an entry to `misrouted_documents` with:
- `source_document_filename`: the EXACT filename as provided,
- `detected_type`: one of `'coverage' | 'quote' | 'unknown'`,
- `reason`: a one-sentence explanation (e.g., "Document is a COI listing policy
  numbers -- belongs in the coverage zone").
Be conservative: only flag when very confident. Borderline docs get no misrouted
entry and zero extracted coverages. `misrouted_documents` may be absent or empty
on normal runs.

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
# Policy extraction (current in-force coverage pass — Phase 145 Plan 02)
# ---------------------------------------------------------------------------

# Tool schema for the second extraction pass: pulls current in-force policies
# out of COIs / policy summaries / schedules so we can populate the
# current_limit / current_carrier / current_policy_number / current_expiry
# fields on matched ProjectCoverage rows and surface orphans. Mirrors
# EXTRACTION_TOOL's misrouted_documents mechanism so no document is silently
# dropped.
POLICY_EXTRACTION_TOOL = {
    "name": "extract_current_policies",
    "description": (
        "Extract current in-force insurance policies and surety bonds from "
        "Certificates of Insurance (COIs), policy summaries, and schedules. "
        "Do NOT extract contract requirements or quote proposals."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "documents": {
                "type": "array",
                "description": "One entry per input document. Use filename as id.",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_document_filename": {"type": "string"},
                        "document_misrouted": {
                            "type": "boolean",
                            "description": (
                                "True ONLY if this document is clearly NOT a current-"
                                "policy / COI / in-force policy summary (e.g., it is a "
                                "contract, MSA, or carrier quote letter). Be conservative "
                                "-- only flag if very high confidence."
                            ),
                        },
                        "misrouted_reason": {
                            "type": "string",
                            "description": "Short human-readable reason when document_misrouted=true.",
                        },
                        "detected_type": {
                            "type": "string",
                            "enum": ["requirements", "quote", "unknown"],
                            "description": "Best guess at what this document actually is, when misrouted.",
                        },
                    },
                    "required": ["source_document_filename", "document_misrouted"],
                },
            },
            "policies": {
                "type": "array",
                "description": "All extracted policies across ALL documents in this call.",
                "items": {
                    "type": "object",
                    "properties": {
                        "coverage_type_key": {
                            "type": "string",
                            "description": "Canonical snake_case key from taxonomy.",
                        },
                        "raw_coverage_name": {"type": "string"},
                        "category": {"type": "string"},
                        "carrier": {"type": "string"},
                        "policy_number": {"type": "string"},
                        "limit_amount": {
                            "type": ["number", "null"],
                            "description": "Numeric limit; null if unstated.",
                        },
                        "limit_currency": {"type": "string"},
                        "expiry_date": {
                            "type": "string",
                            "description": "ISO 8601 date (YYYY-MM-DD) when the policy expires.",
                        },
                        "source_document_filename": {"type": "string"},
                        "confidence_score": {"type": "number"},
                    },
                    "required": ["coverage_type_key", "source_document_filename"],
                },
            },
            "total_policies_found": {"type": "integer"},
        },
        "required": ["documents", "policies", "total_policies_found"],
    },
}


def build_policy_extraction_prompt(
    coverage_types: list[dict], project_currency: str
) -> str:
    """Build the policy-extraction system prompt with embedded taxonomy.

    Mirrors `build_extraction_prompt` but for the coverage-zone pass: the
    model extracts current in-force policies instead of contract requirements
    and emits a per-document misrouted flag when it sees a contract / quote
    by mistake.

    Args:
        coverage_types: List of dicts with key, display_name, aliases, category.
        project_currency: The project's default currency (e.g. 'MXN').

    Returns:
        Full system prompt string for the policy-extraction API call.
    """
    taxonomy_block = _format_taxonomy(coverage_types)

    return f"""\
You are an expert insurance and surety analyst. You will receive ONE OR MORE
documents and must extract CURRENT IN-FORCE POLICIES -- i.e., the coverage the
insured already has.

DOCUMENT TYPES you may receive:
- Certificates of Insurance (COIs) -- extract from these.
- Current policy summaries / declarations pages / schedules of insurance -- extract.
- Surety bond schedules listing in-force bonds -- extract.

DOCUMENT TYPES you MUST REFUSE:
- Construction contracts / MSAs / bond requirement annexes -- DO NOT extract.
  These describe requirements, not current coverage.
- Carrier quote letters / surety proposals -- DO NOT extract. These are
  proposals, not in-force policies.

If you receive a document that is NOT a current-policy / COI / in-force
policy summary, set its `document_misrouted` flag to true with a concise
`misrouted_reason` and a `detected_type` ('requirements' | 'quote' | 'unknown').
Do NOT attempt to extract policies from a misrouted document. Set
document_misrouted to true ONLY when you are very confident the document is
not what the user intended (e.g., it is clearly a contract with no policy
numbers). Borderline documents get document_misrouted=false and zero
extracted policies.

COVERAGE TYPE TAXONOMY -- map each policy to one of these canonical keys:
{taxonomy_block}

INSTRUCTIONS:
- Extract every policy / bond stated as CURRENTLY IN-FORCE.
- Use the canonical snake_case key from the taxonomy above. If a genuinely
  distinct type exists and is not in the taxonomy, use a new snake_case key
  (the backend will create the type if needed).
- total_policies_found MUST equal the length of the policies array.

POLICY FIELDS:
- carrier: The insurer / surety company name (e.g., "Travelers", "Liberty Mutual").
- policy_number: The policy or bond number as printed.
- limit_amount: Numeric limit. If the limit is stated as "per occurrence" vs
  "aggregate", prefer the per-occurrence limit for liability coverages and
  the penal sum for surety bonds.
- limit_currency: ISO code. Project currency is {project_currency}.
- expiry_date: ISO 8601 YYYY-MM-DD.
- source_document_filename: EXACT filename of the input document.
- confidence_score: 0.0-1.0.

NOTE: Documents may be in Spanish or Portuguese. Analyze in the original
language. Policy numbers and carrier names stay in their original casing.
"""


def _normalize_coverage_key(key: str | None) -> str:
    """Normalize canonical coverage_type_key for exact matching.

    Keys are canonical snake_case post-Phase 140. Defensive strip+lower only.
    DO NOT use `_normalize_coverage_type` from quote_extractor.py -- that one
    replaces underscores with spaces and is for display-name fuzzy matching.
    """
    if not key:
        return ""
    return key.strip().lower()


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
    pdf_by_name: dict[str, UUID],
) -> ProjectCoverage:
    """Process a single AI-extracted coverage into a ProjectCoverage row.

    Handles:
    - New taxonomy type creation (is_new_type=True)
    - Alias learning (suggested_alias for existing types)
    - Currency mismatch detection
    - Resolution of source_document_filename -> source_document_id UUID
    - ProjectCoverage row creation with canonical key

    Args:
        cov: Single coverage dict from AI extraction.
        project: The BrokerProject being analyzed.
        db: Async SQLAlchemy session.
        contract_language: Detected contract language code.
        pdf_by_name: Map from input-PDF filename to file UUID. Pre-computed
            once per analysis run by the caller; used here to resolve
            per-coverage source_document_id.

    Returns:
        ProjectCoverage instance (not yet added to session).
    """
    key = cov["coverage_type_key"]

    # Resolve per-coverage source_document_id from the filename Claude returned.
    # pdf_by_name is pre-computed once per analysis at the caller; don't recompute here.
    source_doc_id: UUID | None = None
    extracted_filename = (cov.get("source_document_filename") or "").strip()
    if extracted_filename:
        source_doc_id = pdf_by_name.get(extracted_filename)
        if source_doc_id is None:
            # Case-insensitive fallback — Claude sometimes normalizes case
            for fname, fid in pdf_by_name.items():
                if fname.lower() == extracted_filename.lower():
                    source_doc_id = fid
                    break
        if source_doc_id is None:
            logger.warning(
                "source_document_filename=%r not matched for coverage key=%r",
                extracted_filename,
                key,
            )

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
        source_document_id=source_doc_id,
        confidence=_score_to_confidence_text(
            cov.get("confidence_score", 0.5)
        ),
        source="ai_extraction",
        is_manual_override=False,
        metadata_=meta,
    )

    return coverage


# ---------------------------------------------------------------------------
# Current-policies extraction pass (coverage-zone docs)
# ---------------------------------------------------------------------------


async def extract_current_policies(
    db: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    policy_pdfs: list[tuple[UUID, str, bytes]],
    taxonomy_types: list[dict],
    model: str,
    api_key: str | None = None,
) -> dict:
    """Extract current in-force policies and update matching ProjectCoverage rows.

    Mirrors the structure of analyze_contract but runs the new
    POLICY_EXTRACTION_TOOL on `document_type='coverage'` PDFs only. Populates
    current_limit / current_carrier / current_policy_number / current_expiry
    on rows matched by canonical coverage_type_key. Unmatched policies become
    orphans and are returned in the result so the caller can persist them to
    `project.metadata_.orphan_policies[]`. Preserves rows with
    is_manual_override=True untouched.

    Args:
        db: Async SQLAlchemy session. Caller owns the transaction; this
            function flushes but does not commit.
        tenant_id: Tenant UUID.
        project_id: BrokerProject UUID.
        policy_pdfs: List of (file_id, filename, bytes) tuples tagged as
            coverage-zone docs. May be empty — function early-returns.
        taxonomy_types: Pre-loaded taxonomy (same shape as _load_taxonomy).
        model: Anthropic model name.
        api_key: Optional override; defaults to settings.flywheel_subsidy_api_key.

    Returns:
        On success:
            {
                "status": "completed",
                "policies_extracted": int,
                "rows_updated": int,
                "orphans": [{coverage_type_key, carrier, policy_number,
                             limit_amount, source_document_filename}],
                "misrouted": {file_id_str: {reason: str, detected_type: str}},
            }
        On failure:
            {"status": "failed", "error": str}
    """
    # Early exit — no coverage-zone docs means nothing to do.
    if not policy_pdfs:
        return {
            "status": "completed",
            "policies_extracted": 0,
            "rows_updated": 0,
            "orphans": [],
            "misrouted": {},
        }

    try:
        # Load project for currency context.
        project_result = await db.execute(
            select(BrokerProject).where(
                BrokerProject.id == project_id,
                BrokerProject.tenant_id == tenant_id,
            )
        )
        project = project_result.scalar_one_or_none()
        if project is None:
            logger.error(
                "extract_current_policies: project not found project_id=%s tenant_id=%s",
                project_id,
                tenant_id,
            )
            return {"status": "failed", "error": "Project not found"}

        system_prompt = build_policy_extraction_prompt(
            taxonomy_types, project.currency or "USD"
        )

        effective_api_key = api_key or settings.flywheel_subsidy_api_key
        client = anthropic.AsyncAnthropic(api_key=effective_api_key)

        # Build one document block per PDF + trailing text block listing filenames.
        content_blocks: list[dict] = []
        for _, filename, pdf_bytes in policy_pdfs:
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

        filename_list = "\n".join(f"  - {f}" for _, f, _ in policy_pdfs)
        content_blocks.append(
            {
                "type": "text",
                "text": (
                    f"The {len(policy_pdfs)} documents above are current-policy / "
                    "COI / in-force schedule uploads. Their filenames are:\n"
                    f"{filename_list}\n\n"
                    "Extract every current in-force policy and bond. Use the canonical "
                    "taxonomy keys. Populate the `documents` array with one entry per "
                    "input filename, flagging misrouted contracts/quotes. The "
                    "`policies` array is flat across all input documents — set "
                    "source_document_filename on each policy."
                ),
            }
        )

        response = await client.messages.create(
            model=model,
            max_tokens=16384,
            system=system_prompt,
            tools=[POLICY_EXTRACTION_TOOL],
            tool_choice={
                "type": "tool",
                "name": "extract_current_policies",
            },
            messages=[{"role": "user", "content": content_blocks}],
        )

        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_block is None:
            raise ValueError(
                "Claude response did not contain a tool_use block (policy pass)"
            )

        extracted = tool_block.input

        stop_reason = getattr(response, "stop_reason", None)
        usage = getattr(response, "usage", None)
        output_tokens = getattr(usage, "output_tokens", None) if usage else None
        input_tokens = getattr(usage, "input_tokens", None) if usage else None
        raw_policies = (
            extracted.get("policies", []) if isinstance(extracted, dict) else []
        )
        logger.info(
            "Policy extraction API response: project_id=%s stop_reason=%s "
            "input_tokens=%s output_tokens=%s policies_in_response=%d "
            "total_policies_found=%s",
            project_id,
            stop_reason,
            input_tokens,
            output_tokens,
            len(raw_policies) if isinstance(raw_policies, list) else -1,
            extracted.get("total_policies_found") if isinstance(extracted, dict) else None,
        )

        # Fail fast on truncation — partial extractions must not be saved as success.
        if stop_reason == "max_tokens":
            raise ValueError(
                f"Policy response truncated at max_tokens (output_tokens={output_tokens}). "
                "Partial extraction rejected."
            )

        reported_total = (
            extracted.get("total_policies_found")
            if isinstance(extracted, dict)
            else None
        )
        actual_count = len(raw_policies) if isinstance(raw_policies, list) else 0
        if (
            reported_total is not None
            and isinstance(reported_total, int)
            and reported_total != actual_count
        ):
            raise ValueError(
                f"total_policies_found={reported_total} but policies array has "
                f"{actual_count} items — response inconsistent, likely truncated"
            )

        # Surface per-document misrouted flags keyed by file_id string.
        filename_to_file_id = {fname: str(fid) for fid, fname, _ in policy_pdfs}
        misrouted: dict[str, dict] = {}
        for doc_entry in extracted.get("documents", []) or []:
            if doc_entry.get("document_misrouted"):
                fname = doc_entry.get("source_document_filename") or ""
                file_id_str = filename_to_file_id.get(fname)
                if file_id_str:
                    misrouted[file_id_str] = {
                        "reason": doc_entry.get(
                            "misrouted_reason",
                            "Document does not appear to be a current policy",
                        ),
                        "detected_type": doc_entry.get("detected_type", "unknown"),
                    }

        # Load existing ProjectCoverage rows to match against.
        cov_result = await db.execute(
            select(ProjectCoverage).where(
                ProjectCoverage.broker_project_id == project_id,
                ProjectCoverage.tenant_id == tenant_id,
            )
        )
        existing_coverages = cov_result.scalars().all()
        coverage_by_key = {
            _normalize_coverage_key(c.coverage_type_key): c
            for c in existing_coverages
            if c.coverage_type_key
        }

        rows_updated = 0
        orphans: list[dict] = []
        for policy in extracted.get("policies", []) or []:
            norm_key = _normalize_coverage_key(policy.get("coverage_type_key"))
            if not norm_key:
                continue
            match = coverage_by_key.get(norm_key)
            if match is None:
                orphans.append(
                    {
                        "coverage_type_key": policy.get("coverage_type_key"),
                        "carrier": policy.get("carrier"),
                        "policy_number": policy.get("policy_number"),
                        "limit_amount": policy.get("limit_amount"),
                        "source_document_filename": policy.get("source_document_filename"),
                    }
                )
                continue
            if match.is_manual_override:
                logger.info(
                    "Skipping policy for %s: is_manual_override=True preserves broker edit",
                    norm_key,
                )
                continue

            # Write current_* fields. Use Decimal via str() so float-binary
            # drift does not corrupt money values.
            limit_amount = policy.get("limit_amount")
            if limit_amount is not None:
                try:
                    match.current_limit = Decimal(str(limit_amount))
                except (InvalidOperation, TypeError, ValueError):
                    logger.warning(
                        "Invalid current_limit %r for %s", limit_amount, norm_key
                    )
            if policy.get("carrier"):
                match.current_carrier = policy["carrier"]
            if policy.get("policy_number"):
                match.current_policy_number = policy["policy_number"]
            expiry = policy.get("expiry_date")
            if expiry:
                try:
                    match.current_expiry = date.fromisoformat(expiry)
                except (ValueError, TypeError):
                    logger.warning(
                        "Invalid expiry_date %r for %s", expiry, norm_key
                    )
            rows_updated += 1

        await db.flush()

        logger.info(
            "Policy extraction completed for project_id=%s: %d policies extracted, "
            "%d rows updated, %d orphans, %d misrouted",
            project_id,
            actual_count,
            rows_updated,
            len(orphans),
            len(misrouted),
        )

        return {
            "status": "completed",
            "policies_extracted": actual_count,
            "rows_updated": rows_updated,
            "orphans": orphans,
            "misrouted": misrouted,
        }

    except Exception as exc:
        import traceback
        logger.error(
            "Policy extraction failed for project_id=%s tenant_id=%s: %s: %s\n%s",
            project_id,
            tenant_id,
            type(exc).__name__,
            exc,
            traceback.format_exc(),
        )
        return {"status": "failed", "error": str(exc)}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def analyze_contract(
    db: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    pdfs: list[tuple[UUID, str, bytes, str]],
    api_key: str | None = None,
) -> dict:
    """Analyze one or more construction-project PDFs and extract coverage requirements.

    Accepts the full set of PDFs attached to a project. PDFs are partitioned by
    their `document_type` tag (fourth tuple element) and dispatched to two
    passes:

    * `document_type='requirements'` (MSAs, annexes, default for legacy) →
      contract-requirements extraction populating `required_limit` /
      `required_terms` / etc.
    * `document_type='coverage'` (COIs, policy schedules) →
      `extract_current_policies` populating `current_limit` / `current_carrier`
      / `current_policy_number` / `current_expiry` on matched rows, with
      orphans landing in `project.metadata_.orphan_policies[]`.

    Misrouted documents from BOTH passes are merged into
    `misrouted_by_file_id` in the return dict so the caller can persist the
    flag onto `metadata.documents[i]` (Plan 03).

    On truncation or count mismatch: sets analysis_status='failed'. Does NOT
    accept partial extraction as success.

    Args:
        db: Async SQLAlchemy session. Caller sets RLS context and manages
            transaction (commit/rollback). This function flushes but does
            not commit.
        tenant_id: Tenant UUID.
        project_id: BrokerProject UUID to analyze.
        pdfs: List of (file_id, filename, content_bytes, document_type)
            tuples. Must be non-empty. `document_type` is 'requirements' |
            'coverage'; legacy docs default to 'requirements' via
            `_get_project_pdfs`.
        api_key: Optional explicit API key. If None, uses
                 settings.flywheel_subsidy_api_key (background job default).

    Returns:
        Dict with keys: status, coverages_found, coverages, contract_language,
        contract_summary, policies_extracted, policy_rows_updated,
        orphans_count, misrouted_by_file_id. On error: status='failed',
        error=str.
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

        # Step 4: Partition PDFs by document_type. Legacy docs default to
        # 'requirements' (set by _get_project_pdfs).
        if not pdfs:
            raise ValueError("analyze_contract called with no PDFs")

        requirements_pdfs = [
            (fid, fname, content)
            for fid, fname, content, dt in pdfs
            if dt == "requirements"
        ]
        coverage_pdfs = [
            (fid, fname, content)
            for fid, fname, content, dt in pdfs
            if dt == "coverage"
        ]
        logger.info(
            "Analysis dispatch: project_id=%s requirements=%d coverage=%d",
            project_id,
            len(requirements_pdfs),
            len(coverage_pdfs),
        )

        if not requirements_pdfs and not coverage_pdfs:
            raise ValueError(
                "analyze_contract called with no usable PDFs (all had unknown document_type)"
            )

        # Step 5: UNCONDITIONALLY clear prior AI-extracted coverages. This
        # runs on every invocation so coverage-only re-runs start from a
        # clean slate. Manually-added or manually-overridden coverages are
        # preserved.
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
        await db.flush()

        # Reset prior misrouted flags on ALL documents before re-analysis.
        # Safer than clearing only coverage-typed docs — keeps the slate clean.
        # The new pass will re-apply flags only for truly misrouted docs.
        # Both passes now emit structured misrouted flags (Plan 02 Task 2b
        # extended EXTRACTION_TOOL + POLICY_EXTRACTION_TOOL), so clearing ALL
        # `misrouted` keys is correct.
        #
        # Spread-and-reassign (required for SQLAlchemy JSONB dirty detection).
        pre_meta = dict(project.metadata_) if project.metadata_ else {}
        pre_docs = list(pre_meta.get("documents", []))
        reset_docs: list[dict] = []
        for d in pre_docs:
            if isinstance(d, dict) and "misrouted" in d:
                clean = dict(d)
                clean.pop("misrouted", None)
                reset_docs.append(clean)
            else:
                reset_docs.append(d)
        pre_meta["documents"] = reset_docs
        project.metadata_ = pre_meta
        await db.flush()

        # State the rest of the function reads — initialized to defaults so
        # the no-requirements branch still has valid values.
        coverages_created: list[dict] = []
        contract_language = project.language or "es"
        contract_summary = ""
        req_misrouted: dict[str, dict] = {}

        effective_api_key = api_key or settings.flywheel_subsidy_api_key

        if requirements_pdfs:
            # Step 6: Build dynamic prompt with taxonomy.
            system_prompt = build_extraction_prompt(
                taxonomy_types, project.currency
            )

            # Step 7: Build and send Claude API request with one document
            # block per requirements PDF.
            client = anthropic.AsyncAnthropic(api_key=effective_api_key)

            content_blocks: list[dict] = []
            for _, filename, pdf_bytes in requirements_pdfs:
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

            filename_list = "\n".join(f"  - {f}" for _, f, _ in requirements_pdfs)
            content_blocks.append(
                {
                    "type": "text",
                    "text": (
                        f"The {len(requirements_pdfs)} documents above are all from the same construction project. "
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

            # Step 8: Parse tool_use response
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

            # Build filename->id map once; used for both primary-contract backfill
            # and per-coverage source_document_id resolution.
            pdf_by_name = {fname: fid for fid, fname, _ in requirements_pdfs}

            # Backfill source_document_id from the model's classification of the primary
            # contract. This replaces the prior "first uploaded PDF" heuristic, which
            # could point source_document_id at an annex or policy summary.
            primary_filename = (extracted.get("primary_contract_filename") or "").strip()
            if primary_filename:
                matched_id = pdf_by_name.get(primary_filename)
                if matched_id is not None:
                    project.source_document_id = matched_id
                else:
                    logger.warning(
                        "primary_contract_filename=%r not in input PDFs for project_id=%s",
                        primary_filename,
                        project_id,
                    )

            # Surface requirements-pass misrouted entries keyed by file_id string.
            req_filename_to_file_id = {
                fname: str(fid) for fid, fname, _ in requirements_pdfs
            }
            for entry in extracted.get("misrouted_documents", []) or []:
                fname = entry.get("source_document_filename") or ""
                fid = req_filename_to_file_id.get(fname)
                if fid:
                    req_misrouted[fid] = {
                        "reason": entry.get(
                            "reason",
                            "Document does not appear to be a contract/requirements doc",
                        ),
                        "detected_type": entry.get("detected_type", "unknown"),
                    }

            # Step 9: Process each coverage through taxonomy pipeline
            for cov in extracted.get("coverages", []):
                coverage = await _process_extracted_coverage(
                    cov, project, db, contract_language, pdf_by_name
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

            # Status transition + language update only run when requirements
            # extraction actually happened.
            if coverages_created and project.status != "gaps_identified":
                from flywheel.api.broker._shared import validate_transition
                validate_transition(
                    project.status, "gaps_identified", client_id=project.client_id
                )
                project.status = "gaps_identified"
            # else keep current status -- no coverages found, or already in gaps_identified (re-run)

            contract_summary = extracted.get("contract_summary", "")

            # Update project language from contract if detected
            if contract_language and contract_language in ("en", "es", "pt"):
                project.language = contract_language

        # Step 10: Policy extraction pass on coverage-zone PDFs. ALWAYS runs
        # (the function itself early-returns cleanly when coverage_pdfs is
        # empty) so a coverage-only re-run still updates policies + orphans.
        policy_result = await extract_current_policies(
            db=db,
            tenant_id=tenant_id,
            project_id=project_id,
            policy_pdfs=coverage_pdfs,
            taxonomy_types=taxonomy_types,
            model=model,
            api_key=api_key,
        )
        if policy_result.get("status") == "failed":
            # Do not fail the whole analysis; surface in metadata and continue.
            logger.error(
                "Policy extraction failed for project %s: %s",
                project_id,
                policy_result.get("error"),
            )
            policy_result.setdefault("orphans", [])
            policy_result.setdefault("misrouted", {})

        # Merge misrouted dicts from both passes. file_id is globally unique
        # so no collision is expected, but if one occurs policy-pass wins
        # (it's the semantically narrower check).
        merged_misrouted: dict[str, dict] = {}
        merged_misrouted.update(req_misrouted)
        merged_misrouted.update(policy_result.get("misrouted", {}) or {})

        # Persist merged misrouted flags (from both requirements + policy
        # extraction passes) onto project.metadata_.documents[i]. Plan 02 built
        # `merged_misrouted` above; this block writes it onto the JSONB
        # documents array.
        #
        # ORDERING INVARIANT: this block MUST run BEFORE Step 11's
        # `project_meta = dict(project.metadata_)` rebuild. Step 11's shallow
        # copy picks up whatever documents[] state exists at that moment; if
        # this write runs AFTER the rebuild, Step 11 overwrites the misrouted
        # flags.
        if merged_misrouted:
            post_meta = dict(project.metadata_) if project.metadata_ else {}
            post_docs = list(post_meta.get("documents", []))
            updated_docs: list[dict] = []
            for d in post_docs:
                fid = d.get("file_id") if isinstance(d, dict) else None
                if fid and fid in merged_misrouted:
                    new_doc = dict(d)
                    new_doc["misrouted"] = {
                        "reason": merged_misrouted[fid].get(
                            "reason", "Document routing mismatch"
                        ),
                        "detected_type": merged_misrouted[fid].get(
                            "detected_type", "unknown"
                        ),
                    }
                    updated_docs.append(new_doc)
                else:
                    updated_docs.append(d)
            post_meta["documents"] = updated_docs
            project.metadata_ = post_meta
            await db.flush()

        # Step 11: Update project completion state + metadata (ALWAYS runs).
        project.analysis_status = "completed"
        project.analysis_completed_at = datetime.now(timezone.utc)

        project_meta = dict(project.metadata_) if project.metadata_ else {}
        project_meta["contract_summary"] = contract_summary
        project_meta["contract_language"] = contract_language
        project_meta["analysis_model"] = model
        project_meta["orphan_policies"] = policy_result.get("orphans", [])
        # Spread-and-reassign pattern: reassignment is required for SQLAlchemy
        # JSONB dirty detection. Do NOT mutate project.metadata_ in place.
        project.metadata_ = project_meta

        await db.flush()

        # Step 11.5: Inline gap detection — every ProjectCoverage row gets a
        # non-NULL gap_status before the caller commits. Replaces the historical
        # requirement to manually POST /analyze-gaps after analysis.
        # (See Phase 145 RESEARCH Architecture Pattern #5.)
        #
        # Anchor invariant: this block runs AFTER Step 11's project_meta flush
        # and BEFORE the BrokerActivity construction, so gap_summary is
        # available for the activity's metadata_ dict.
        #
        # Note: rows where required_limit is None will receive gap_status="unknown"
        # (per gap_detector.py rules) — this is correct when required data is
        # missing and does not violate the "no NULL gap_status" invariant.
        cov_reload = await db.execute(
            select(ProjectCoverage)
            .where(ProjectCoverage.broker_project_id == project_id)
            .order_by(ProjectCoverage.created_at)
        )
        all_coverages = cov_reload.scalars().all()
        coverage_dicts = [
            {
                "id": str(c.id),
                "required_limit": float(c.required_limit)
                if c.required_limit is not None
                else None,
                "current_limit": float(c.current_limit)
                if c.current_limit is not None
                else None,
                "is_manual_override": c.is_manual_override,
            }
            for c in all_coverages
        ]
        gap_results = detect_gaps(coverage_dicts)
        gap_summary = summarize_gaps(gap_results)
        result_by_id = {r["id"]: r for r in gap_results}
        for cov_orm in all_coverages:
            updated = result_by_id.get(str(cov_orm.id))
            if updated is None:
                continue
            # is_manual_override rows are passed through unchanged by detect_gaps
            # (no gap_status/gap_amount keys set on them), so skip assignment
            # when those keys are absent — preserves the broker's manual values.
            if "gap_status" in updated:
                cov_orm.gap_status = updated.get("gap_status")
            if "gap_amount" in updated:
                cov_orm.gap_amount = updated.get("gap_amount")
        await db.flush()

        logger.info(
            "Inline gap detection for project_id=%s: "
            "covered=%d insufficient=%d missing=%d unknown=%d",
            project_id,
            gap_summary.get("covered", 0),
            gap_summary.get("insufficient", 0),
            gap_summary.get("missing", 0),
            gap_summary.get("unknown", 0),
        )

        # Step 12: Create BrokerActivity for successful analysis
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
                "policies_extracted": policy_result.get("policies_extracted", 0),
                "policy_rows_updated": policy_result.get("rows_updated", 0),
                "orphans_count": len(policy_result.get("orphans", [])),
                "misrouted_count": len(merged_misrouted),
                "gap_summary": gap_summary,
            },
        )
        db.add(activity)
        await db.flush()

        logger.info(
            "Contract analysis completed for project_id=%s tenant_id=%s: "
            "%d coverages, %d policies, %d rows updated, %d orphans, %d misrouted",
            project_id,
            tenant_id,
            len(coverages_created),
            policy_result.get("policies_extracted", 0),
            policy_result.get("rows_updated", 0),
            len(policy_result.get("orphans", [])),
            len(merged_misrouted),
        )

        return {
            "status": "completed",
            "coverages_found": len(coverages_created),
            "coverages": coverages_created,
            "contract_language": contract_language,
            "contract_summary": contract_summary,
            "policies_extracted": policy_result.get("policies_extracted", 0),
            "policy_rows_updated": policy_result.get("rows_updated", 0),
            "orphans_count": len(policy_result.get("orphans", [])),
            "misrouted_by_file_id": merged_misrouted,
            "gap_summary": gap_summary,
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


# ---------------------------------------------------------------------------
# Phase 150.1 Plan 02 — public helpers + persist_* functions for the
# Pattern 3a extract/save endpoint pairs.
#
# Legacy functions (analyze_contract, extract_current_policies) remain
# untouched for the existing /analyze endpoint. Plan 04 will rename them to
# `_legacy` and eventually delete the AsyncAnthropic call sites entirely.
#
# The public helpers below are what api/broker/projects.py's new
# /extract/{op} + /save/{op} endpoints import and call. They never
# instantiate AsyncAnthropic — they only assemble prompts (extract side) or
# persist Claude's tool_use output (save side).
# ---------------------------------------------------------------------------


# Public alias for the taxonomy loader — used by extract endpoints.
load_taxonomy = _load_taxonomy


async def persist_contract_analysis(
    db: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    tool_use_output: dict,
    input_filenames: list[str] | None = None,
) -> dict:
    """Persist Claude's contract-analysis tool_use output.

    This function is called by the `POST /save/contract-analysis` endpoint
    with Claude's in-conversation tool-use output (the shape declared by
    EXTRACTION_TOOL.input_schema). It replicates the post-LLM persistence
    logic from `analyze_contract` (lines ~1285-1530) but does NOT call
    Claude — the AI analysis happens in the Claude-in-conversation flow.

    Args:
        db: Async SQLAlchemy session (caller manages transaction).
        tenant_id: Tenant UUID.
        project_id: BrokerProject UUID.
        tool_use_output: Dict matching EXTRACTION_TOOL.input_schema —
            {coverages, contract_language, contract_summary,
             total_coverages_found, primary_contract_filename,
             misrouted_documents}.
        input_filenames: Filenames of the requirements PDFs the extract
            endpoint returned in `documents`. Used to map Claude's
            `source_document_filename` outputs back to file_ids. Optional;
            if omitted, source_document_id backfill is skipped.

    Returns:
        {
            "status": "completed",
            "coverages_saved": int,
            "contract_language": str,
            "contract_summary": str,
            "misrouted_by_file_id": dict,
            "primary_contract_filename": str | None,
        }
    """
    # Load project for currency/tenant context + write-back fields.
    result = await db.execute(
        select(BrokerProject).where(
            BrokerProject.id == project_id,
            BrokerProject.tenant_id == tenant_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ValueError(
            f"BrokerProject not found for persist_contract_analysis: "
            f"project_id={project_id} tenant_id={tenant_id}"
        )

    # Clear prior AI-extracted coverages (same pattern as analyze_contract).
    from sqlalchemy import delete

    delete_stmt = delete(ProjectCoverage).where(
        ProjectCoverage.broker_project_id == project_id,
        ProjectCoverage.tenant_id == tenant_id,
        ProjectCoverage.source == "ai_extraction",
        ProjectCoverage.is_manual_override.is_(False),
    )
    await db.execute(delete_stmt)
    await db.flush()

    # Reset prior misrouted flags on all documents before re-applying.
    pre_meta = dict(project.metadata_) if project.metadata_ else {}
    pre_docs = list(pre_meta.get("documents", []))
    reset_docs: list[dict] = []
    for d in pre_docs:
        if isinstance(d, dict) and "misrouted" in d:
            clean = dict(d)
            clean.pop("misrouted", None)
            reset_docs.append(clean)
        else:
            reset_docs.append(d)
    pre_meta["documents"] = reset_docs
    project.metadata_ = pre_meta
    await db.flush()

    # Build filename->file_id map from project.metadata_.documents (so we
    # don't require the caller to pass input_filenames — but honor it if
    # supplied for precision).
    pdf_by_name: dict[str, UUID] = {}
    for d in (pre_meta.get("documents") or []):
        if not isinstance(d, dict):
            continue
        fname = d.get("name") or d.get("filename")
        fid = d.get("file_id")
        if fname and fid:
            try:
                pdf_by_name[fname] = UUID(fid) if isinstance(fid, str) else fid
            except (ValueError, TypeError):
                continue

    coverages = tool_use_output.get("coverages", []) or []
    contract_language = tool_use_output.get("contract_language", "es")
    contract_summary = tool_use_output.get("contract_summary", "")
    primary_filename = (tool_use_output.get("primary_contract_filename") or "").strip()

    # Backfill project.source_document_id from Claude's primary-contract pick.
    if primary_filename:
        matched_id = pdf_by_name.get(primary_filename)
        if matched_id is None:
            # Case-insensitive fallback
            for fname, fid in pdf_by_name.items():
                if fname.lower() == primary_filename.lower():
                    matched_id = fid
                    break
        if matched_id is not None:
            project.source_document_id = matched_id

    # Insert ProjectCoverage rows for every extracted coverage.
    coverages_saved = 0
    for cov in coverages:
        if not isinstance(cov, dict) or not cov.get("coverage_type_key"):
            continue
        coverage = await _process_extracted_coverage(
            cov, project, db, contract_language, pdf_by_name
        )
        db.add(coverage)
        coverages_saved += 1

    # Build misrouted_by_file_id map from requirements-pass misrouted docs.
    req_misrouted: dict[str, dict] = {}
    req_filename_to_file_id = {fname: str(fid) for fname, fid in pdf_by_name.items()}
    for entry in tool_use_output.get("misrouted_documents", []) or []:
        if not isinstance(entry, dict):
            continue
        fname = (entry.get("source_document_filename") or "").strip()
        fid_str = req_filename_to_file_id.get(fname)
        if not fid_str:
            # case-insensitive fallback
            for real_fname, real_fid in pdf_by_name.items():
                if real_fname.lower() == fname.lower():
                    fid_str = str(real_fid)
                    break
        if fid_str:
            req_misrouted[fid_str] = {
                "reason": entry.get("reason", "Document routing mismatch"),
                "detected_type": entry.get("detected_type", "unknown"),
            }

    # Persist misrouted flags back onto project.metadata_.documents[i].
    if req_misrouted:
        post_meta = dict(project.metadata_) if project.metadata_ else {}
        post_docs = list(post_meta.get("documents", []))
        updated_docs: list[dict] = []
        for d in post_docs:
            fid = d.get("file_id") if isinstance(d, dict) else None
            if fid and fid in req_misrouted:
                new_doc = dict(d)
                new_doc["misrouted"] = {
                    "reason": req_misrouted[fid].get("reason", "Document routing mismatch"),
                    "detected_type": req_misrouted[fid].get("detected_type", "unknown"),
                }
                updated_docs.append(new_doc)
            else:
                updated_docs.append(d)
        post_meta["documents"] = updated_docs
        project.metadata_ = post_meta
        await db.flush()

    # Status transition + language update (mirrors analyze_contract).
    if coverages_saved and project.status != "gaps_identified":
        from flywheel.api.broker._shared import validate_transition

        validate_transition(
            project.status, "gaps_identified", client_id=project.client_id
        )
        project.status = "gaps_identified"

    if contract_language and contract_language in ("en", "es", "pt"):
        project.language = contract_language

    # Write contract_summary + contract_language into metadata_
    project_meta = dict(project.metadata_) if project.metadata_ else {}
    project_meta["contract_summary"] = contract_summary
    project_meta["contract_language"] = contract_language
    project_meta["analysis_model"] = "claude-in-conversation"
    project.metadata_ = project_meta

    project.analysis_status = "completed"
    project.analysis_completed_at = datetime.now(timezone.utc)

    await db.flush()

    # Inline gap detection — every ProjectCoverage row gets a non-NULL
    # gap_status before the caller commits.
    cov_reload = await db.execute(
        select(ProjectCoverage)
        .where(ProjectCoverage.broker_project_id == project_id)
        .order_by(ProjectCoverage.created_at)
    )
    all_coverages = cov_reload.scalars().all()
    coverage_dicts = [
        {
            "id": str(c.id),
            "required_limit": float(c.required_limit)
            if c.required_limit is not None
            else None,
            "current_limit": float(c.current_limit)
            if c.current_limit is not None
            else None,
            "is_manual_override": c.is_manual_override,
        }
        for c in all_coverages
    ]
    gap_results = detect_gaps(coverage_dicts)
    gap_summary = summarize_gaps(gap_results)
    result_by_id = {r["id"]: r for r in gap_results}
    for cov_orm in all_coverages:
        updated = result_by_id.get(str(cov_orm.id))
        if updated is None:
            continue
        if "gap_status" in updated:
            cov_orm.gap_status = updated.get("gap_status")
        if "gap_amount" in updated:
            cov_orm.gap_amount = updated.get("gap_amount")
    await db.flush()

    # Log BrokerActivity for the save
    activity = BrokerActivity(
        tenant_id=tenant_id,
        broker_project_id=project_id,
        activity_type="analysis_completed",
        actor_type="system",
        description=(
            f"Contract analysis persisted (CC-as-Brain): "
            f"{coverages_saved} coverage requirements saved"
        ),
        metadata_={
            "coverages_found": coverages_saved,
            "language": contract_language,
            "model": "claude-in-conversation",
            "misrouted_count": len(req_misrouted),
            "gap_summary": gap_summary,
        },
    )
    db.add(activity)
    await db.flush()

    return {
        "status": "completed",
        "coverages_saved": coverages_saved,
        "contract_language": contract_language,
        "contract_summary": contract_summary,
        "misrouted_by_file_id": req_misrouted,
        "primary_contract_filename": primary_filename or None,
        "gap_summary": gap_summary,
    }


async def persist_policy_extraction(
    db: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    tool_use_output: dict,
    input_filenames: list[str] | None = None,
) -> dict:
    """Persist Claude's policy-extraction tool_use output.

    Called by `POST /save/policy-extraction` with Claude's tool-use output
    matching POLICY_EXTRACTION_TOOL.input_schema. Replicates the post-LLM
    persistence logic from `extract_current_policies` (the current_*
    field writes + orphan bookkeeping + misrouted flag persistence) without
    invoking Claude.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant UUID.
        project_id: BrokerProject UUID.
        tool_use_output: Dict matching POLICY_EXTRACTION_TOOL.input_schema —
            {documents: [{source_document_filename, document_misrouted,
                          misrouted_reason, detected_type}],
             policies: [{coverage_type_key, carrier, policy_number,
                         limit_amount, limit_currency, expiry_date,
                         source_document_filename, confidence_score}],
             total_policies_found: int}.
        input_filenames: Filenames of the policy PDFs (coverage-zone docs).

    Returns:
        {
            "status": "completed",
            "policies_extracted": int,
            "rows_updated": int,
            "orphans": list[dict],
            "misrouted_by_file_id": dict,
        }
    """
    # Load project for tenant check + metadata access.
    project_result = await db.execute(
        select(BrokerProject).where(
            BrokerProject.id == project_id,
            BrokerProject.tenant_id == tenant_id,
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise ValueError(
            f"BrokerProject not found for persist_policy_extraction: "
            f"project_id={project_id} tenant_id={tenant_id}"
        )

    # Build filename->file_id map from project.metadata_.documents
    pdf_by_name: dict[str, str] = {}
    for d in (project.metadata_ or {}).get("documents", []) or []:
        if not isinstance(d, dict):
            continue
        fname = d.get("name") or d.get("filename")
        fid = d.get("file_id")
        if fname and fid:
            pdf_by_name[fname] = str(fid)

    # Extract misrouted flags from the `documents` array of tool output.
    misrouted: dict[str, dict] = {}
    for doc_entry in tool_use_output.get("documents", []) or []:
        if not isinstance(doc_entry, dict):
            continue
        if not doc_entry.get("document_misrouted"):
            continue
        fname = (doc_entry.get("source_document_filename") or "").strip()
        fid_str = pdf_by_name.get(fname)
        if not fid_str:
            for real_fname, real_fid in pdf_by_name.items():
                if real_fname.lower() == fname.lower():
                    fid_str = real_fid
                    break
        if fid_str:
            misrouted[fid_str] = {
                "reason": doc_entry.get(
                    "misrouted_reason",
                    "Document does not appear to be a current policy",
                ),
                "detected_type": doc_entry.get("detected_type", "unknown"),
            }

    # Load existing ProjectCoverage rows for key-based matching.
    cov_result = await db.execute(
        select(ProjectCoverage).where(
            ProjectCoverage.broker_project_id == project_id,
            ProjectCoverage.tenant_id == tenant_id,
        )
    )
    existing_coverages = cov_result.scalars().all()
    coverage_by_key = {
        _normalize_coverage_key(c.coverage_type_key): c
        for c in existing_coverages
        if c.coverage_type_key
    }

    policies = tool_use_output.get("policies", []) or []
    rows_updated = 0
    orphans: list[dict] = []
    for policy in policies:
        if not isinstance(policy, dict):
            continue
        norm_key = _normalize_coverage_key(policy.get("coverage_type_key"))
        if not norm_key:
            continue
        match = coverage_by_key.get(norm_key)
        if match is None:
            orphans.append(
                {
                    "coverage_type_key": policy.get("coverage_type_key"),
                    "carrier": policy.get("carrier"),
                    "policy_number": policy.get("policy_number"),
                    "limit_amount": policy.get("limit_amount"),
                    "source_document_filename": policy.get(
                        "source_document_filename"
                    ),
                }
            )
            continue
        if match.is_manual_override:
            continue

        # Write current_* fields.
        limit_amount = policy.get("limit_amount")
        if limit_amount is not None:
            try:
                match.current_limit = Decimal(str(limit_amount))
            except (InvalidOperation, TypeError, ValueError):
                pass
        if policy.get("carrier"):
            match.current_carrier = policy["carrier"]
        if policy.get("policy_number"):
            match.current_policy_number = policy["policy_number"]
        expiry = policy.get("expiry_date")
        if expiry:
            try:
                match.current_expiry = date.fromisoformat(str(expiry))
            except (ValueError, TypeError):
                pass
        rows_updated += 1

    # Persist misrouted flags onto project.metadata_.documents[i].
    if misrouted:
        post_meta = dict(project.metadata_) if project.metadata_ else {}
        post_docs = list(post_meta.get("documents", []))
        updated_docs: list[dict] = []
        for d in post_docs:
            fid = d.get("file_id") if isinstance(d, dict) else None
            if fid and fid in misrouted:
                new_doc = dict(d)
                new_doc["misrouted"] = {
                    "reason": misrouted[fid]["reason"],
                    "detected_type": misrouted[fid]["detected_type"],
                }
                updated_docs.append(new_doc)
            else:
                updated_docs.append(d)
        post_meta["documents"] = updated_docs
        project.metadata_ = post_meta

    # Persist orphans + re-run gap detection so current_limit changes are
    # reflected in gap_status.
    project_meta = dict(project.metadata_) if project.metadata_ else {}
    project_meta["orphan_policies"] = orphans
    project.metadata_ = project_meta
    await db.flush()

    # Inline gap detection pass on reloaded coverages.
    cov_reload = await db.execute(
        select(ProjectCoverage)
        .where(ProjectCoverage.broker_project_id == project_id)
        .order_by(ProjectCoverage.created_at)
    )
    all_coverages = cov_reload.scalars().all()
    coverage_dicts = [
        {
            "id": str(c.id),
            "required_limit": float(c.required_limit)
            if c.required_limit is not None
            else None,
            "current_limit": float(c.current_limit)
            if c.current_limit is not None
            else None,
            "is_manual_override": c.is_manual_override,
        }
        for c in all_coverages
    ]
    gap_results = detect_gaps(coverage_dicts)
    gap_summary = summarize_gaps(gap_results)
    result_by_id = {r["id"]: r for r in gap_results}
    for cov_orm in all_coverages:
        updated = result_by_id.get(str(cov_orm.id))
        if updated is None:
            continue
        if "gap_status" in updated:
            cov_orm.gap_status = updated.get("gap_status")
        if "gap_amount" in updated:
            cov_orm.gap_amount = updated.get("gap_amount")
    await db.flush()

    return {
        "status": "completed",
        "policies_extracted": len(policies),
        "rows_updated": rows_updated,
        "orphans": orphans,
        "misrouted_by_file_id": misrouted,
        "gap_summary": gap_summary,
    }
