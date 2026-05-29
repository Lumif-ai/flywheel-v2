"""
contract_analyzer.py - Pattern 3a helpers for contract + policy extraction.

Phase 150.1 Plan 04 completed the CC-as-Brain migration by deleting the
legacy `analyze_contract` and `extract_current_policies` functions (which
constructed an async Anthropic client at runtime). Backend no longer runs
any LLM call for contract analysis or policy extraction;
Claude-in-conversation owns inference. The module exposes only Pattern 3a
public helpers:

  * `EXTRACTION_TOOL` / `POLICY_EXTRACTION_TOOL` — Anthropic tool schemas.
  * `build_extraction_prompt(taxonomy, currency)` — requirements prompt.
  * `build_policy_extraction_prompt(taxonomy, currency)` — policy prompt.
  * `load_taxonomy(db, country_code, line_of_business)` — taxonomy loader.
  * `persist_contract_analysis(db, ..., tool_use_output)` — save-side.
  * `persist_policy_extraction(db, ..., tool_use_output)` — save-side.

Supporting coverage-row helpers (`_process_extracted_coverage`,
`_normalize_coverage_key`, `_validate_limit`, `_score_to_confidence_text`)
remain for the Pattern 3a flow.

CC-as-Brain invariant (Phase 150.1): this module MUST NOT import or
construct an Anthropic async client. The `test_broker_zero_anthropic.py`
regression grep-guards enforce this at CI time.
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import (
    BrokerActivity,
    BrokerProject,
    CoverageType,
    ProjectCoverage,
)
from flywheel.engines.gap_detector import detect_gaps, summarize_gaps

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
# Phase 150.1 Plan 04 — legacy `extract_current_policies` + `analyze_contract`
# DELETED.
#
# Backend owns zero LLM calls for contract-analysis or policy-extraction.
# Claude-in-conversation consumes `build_extraction_prompt` / `EXTRACTION_TOOL`
# and `build_policy_extraction_prompt` / `POLICY_EXTRACTION_TOOL` (Pattern 3a).
# The /save/contract-analysis + /save/policy-extraction endpoints call
# `persist_contract_analysis` / `persist_policy_extraction` below with
# Claude's tool_use output — no backend LLM call involvement.
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
