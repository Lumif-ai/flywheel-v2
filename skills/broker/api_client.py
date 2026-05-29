#!/usr/bin/env python3
"""Shared HTTP client for broker skills. All API calls go through here.

Auth strategy (in priority order):
1. FLYWHEEL_API_TOKEN env var (explicit override)
2. ~/.flywheel/credentials.json (from `flywheel login` — auto-refreshes)

API URL strategy:
1. FLYWHEEL_API_URL env var (explicit override)
2. Flywheel CLI config default (https://uat-flywheel-backend.lumif.ai)

Functions: post(), get(), patch(), upload_file(), run()

Pattern 3a helpers (v1.2, Phase 150.1):
    extract_contract_analysis    / save_contract_analysis
    extract_policy_extraction    / save_policy_extraction
    extract_quote_extraction     / save_quote_extraction
    extract_solicitation_draft   / save_solicitation_draft
    extract_recommendation_draft / save_recommendation_draft

Each extract_* returns {prompt, tool_schema, documents, metadata} so the caller
(Claude-in-conversation) can run analysis inline using its own reasoning. Each
save_* persists the tool-use output verbatim; backend makes zero LLM calls.

BYOK wire format (locked in Plan 01 `_enforcement.py`): the optional `api_key`
field is sent in the JSON request body (NOT a header). Every Pattern 3a helper
also emits `X-Flywheel-Skill: <skill-name>` so the backend's
`require_subsidy_decision` dependency can enforce the allowlist truth table.
"""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Auto-discover API URL
# ---------------------------------------------------------------------------
_DEFAULT_API_URL = "https://uat-flywheel-backend.lumif.ai"
_LOCAL_API_URL = "http://localhost:8000"
_BASE = os.environ.get("FLYWHEEL_API_URL", "").strip()

if not _BASE:
    # Prefer local dev server if it's running (fast socket check, no HTTP overhead)
    import socket as _sock
    try:
        _s = _sock.create_connection(("127.0.0.1", 8000), timeout=0.3)
        _s.close()
        _BASE = _LOCAL_API_URL
    except (OSError, _sock.timeout):
        pass

if not _BASE:
    # Fall back to CLI config or production default
    try:
        from flywheel_cli.config import get_api_url
        _BASE = get_api_url()
    except ImportError:
        _BASE = _DEFAULT_API_URL

_BASE = _BASE.rstrip("/")
API_URL = f"{_BASE}/api/v1"

# ---------------------------------------------------------------------------
# Auto-discover token
# ---------------------------------------------------------------------------
_CREDENTIALS_FILE = Path.home() / ".flywheel" / "credentials.json"
_EXPIRY_BUFFER = 60


def _load_token_from_credentials() -> str:
    """Load access token from ~/.flywheel/credentials.json, refresh if expired."""
    if not _CREDENTIALS_FILE.exists():
        return ""

    try:
        data = json.loads(_CREDENTIALS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return ""

    access_token = data.get("access_token", "")
    refresh_token = data.get("refresh_token", "")
    expires_at = data.get("expires_at", 0)

    if not access_token:
        return ""

    # Check if still valid
    if expires_at - time.time() > _EXPIRY_BUFFER:
        return access_token

    # Try to refresh
    if not refresh_token:
        return access_token  # Return stale token, let server reject

    try:
        resp = httpx.post(
            f"{_BASE}/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=10.0,
        )
        resp.raise_for_status()
        new_data = resp.json()
        new_access = new_data["access_token"]
        new_refresh = new_data.get("refresh_token", refresh_token)
        new_expires = new_data.get("expires_at", time.time() + 3600)

        # Save refreshed credentials
        creds = {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "expires_at": new_expires,
        }
        _CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
        os.chmod(_CREDENTIALS_FILE, 0o600)
        return new_access
    except Exception:
        return access_token  # Return stale token on refresh failure


def _get_token() -> str:
    """Get token: env var first, then credentials file."""
    env_token = os.environ.get("FLYWHEEL_API_TOKEN", "").strip()
    if env_token:
        return env_token
    return _load_token_from_credentials()


def _headers(extra: Optional[dict] = None) -> dict:
    token = _get_token()
    if not token:
        raise RuntimeError(
            "No Flywheel auth token found.\n"
            "Either run `flywheel login` or set FLYWHEEL_API_TOKEN env var."
        )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if extra:
        headers.update(extra)
    return headers


async def post(path: str, payload: Optional[dict] = None, *, extra_headers: Optional[dict] = None) -> dict:
    """POST to broker API with Bearer auth. Raises httpx.HTTPStatusError on non-2xx.

    `extra_headers` lets Pattern 3a helpers inject `X-Flywheel-Skill: <name>`
    without duplicating fetch wiring.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_URL}/broker/{path.lstrip('/')}",
            json=payload or {},
            headers=_headers(extra_headers),
        )
        resp.raise_for_status()
        return resp.json()


async def get(path: str, params: Optional[dict] = None, *, extra_headers: Optional[dict] = None) -> dict:
    """GET from broker API with Bearer auth. Raises httpx.HTTPStatusError on non-2xx."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{API_URL}/broker/{path.lstrip('/')}",
            params=params,
            headers=_headers(extra_headers),
        )
        resp.raise_for_status()
        return resp.json()


async def patch(path: str, payload: Optional[dict] = None, *, extra_headers: Optional[dict] = None) -> dict:
    """PATCH broker API endpoint with Bearer auth. Raises httpx.HTTPStatusError on non-2xx."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(
            f"{API_URL}/broker/{path.lstrip('/')}",
            json=payload or {},
            headers=_headers(extra_headers),
        )
        resp.raise_for_status()
        return resp.json()


async def upload_file(project_id: str, pdf_path: str) -> dict:
    """Upload a PDF file to a broker project. Returns {"files": [...]}."""
    token = _get_token()
    if not token:
        raise RuntimeError(
            "No Flywheel auth token found.\n"
            "Either run `flywheel login` or set FLYWHEEL_API_TOKEN env var."
        )
    url = f"{API_URL}/broker/projects/{project_id}/documents"
    with open(pdf_path, "rb") as fh:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                files={"files": (os.path.basename(pdf_path), fh, "application/pdf")},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()


def run(coro):
    """Sync wrapper — call asyncio.run(coro). Use from non-async contexts (hooks, scripts)."""
    return asyncio.run(coro)


# ============================================================================
# PATTERN 3A: Extract / Save helpers (Phase 150.1, broker library v1.2)
# ============================================================================
#
# Each extract_* method returns {prompt, tool_schema, documents, metadata}.
# Claude-in-conversation runs inline analysis using the returned prompt +
# tool_schema against the provided documents, then calls the matching save_*
# method to persist the tool-use output verbatim. Backend makes ZERO LLM calls.
#
# Truth-table invariant (Plan 01 `_enforcement.py`): every call emits
# `X-Flywheel-Skill: <skill-name>` so `require_subsidy_decision` can enforce
# the allowlist. broker-* skills are non-allowlisted, so BYOK (`api_key=`)
# passes via the request body when the caller has their own Anthropic key.
# Non-allowlisted + no-api-key → 403 subsidy_not_allowed.
#
# BYOK wire format = JSON body `api_key` field (NOT a header). Keep consistent
# across all 10 helpers so the body-double-read pattern in the FastAPI
# dependency parses identical payloads.
# ============================================================================


async def extract_contract_analysis(
    project_id: str,
    *,
    api_key: Optional[str] = None,
    skill_name: str = "broker-parse-contract",
) -> dict:
    """Pattern 3a: fetch prompt + tool_schema + documents for contract coverage extraction.

    Returns: {
        "prompt": str,                     # fully-rendered extraction prompt
        "tool_schema": dict,               # Anthropic tool-use schema {name, description, input_schema}
        "documents": list[DocumentRef],    # [{file_id, filename, pdf_base64, document_type}]
        "metadata": dict                   # {project_id, currency, language, country_code, line_of_business, taxonomy_count, tool_schema_version}
    }
    """
    body: dict = {"project_id": project_id}
    if api_key:
        body["api_key"] = api_key
    return await post(
        "extract/contract-analysis",
        body,
        extra_headers={"X-Flywheel-Skill": skill_name},
    )


async def save_contract_analysis(
    project_id: str,
    analysis: dict,
    *,
    api_key: Optional[str] = None,
    skill_name: str = "broker-parse-contract",
) -> dict:
    """Pattern 3a: persist Claude's contract-analysis tool-use output verbatim.

    `analysis` MUST match the tool_schema.input_schema returned by
    extract_contract_analysis. Pass through metadata["tool_schema_version"]
    from the extract response so the backend can version-gate.

    Expected analysis keys (per EXTRACTION_TOOL.input_schema):
        coverages, contract_language, contract_summary, total_coverages_found,
        primary_contract_filename, misrouted_documents, tool_schema_version
    """
    body: dict = {"project_id": project_id, **analysis}
    if api_key:
        body["api_key"] = api_key
    return await post(
        "save/contract-analysis",
        body,
        extra_headers={"X-Flywheel-Skill": skill_name},
    )


async def extract_policy_extraction(
    project_id: str,
    *,
    api_key: Optional[str] = None,
    skill_name: str = "broker-parse-policies",
) -> dict:
    """Pattern 3a: fetch prompt + tool_schema + coverage-zone PDFs for policy extraction.

    Returns {prompt, tool_schema, documents, metadata}. documents filtered to
    document_type='coverage' (COIs, policy summaries).
    """
    body: dict = {"project_id": project_id}
    if api_key:
        body["api_key"] = api_key
    return await post(
        "extract/policy-extraction",
        body,
        extra_headers={"X-Flywheel-Skill": skill_name},
    )


async def save_policy_extraction(
    project_id: str,
    analysis: dict,
    *,
    api_key: Optional[str] = None,
    skill_name: str = "broker-parse-policies",
) -> dict:
    """Pattern 3a: persist Claude's policy-extraction tool-use output.

    Expected analysis keys (per POLICY_EXTRACTION_TOOL.input_schema):
        documents, policies, total_policies_found, tool_schema_version
    """
    body: dict = {"project_id": project_id, **analysis}
    if api_key:
        body["api_key"] = api_key
    return await post(
        "save/policy-extraction",
        body,
        extra_headers={"X-Flywheel-Skill": skill_name},
    )


async def extract_quote_extraction(
    quote_id: str,
    *,
    api_key: Optional[str] = None,
    skill_name: str = "broker-extract-quote",
) -> dict:
    """Pattern 3a: fetch prompt + tool_schema + quote PDFs for premium/exclusion extraction.

    Primary identifier is `quote_id` (not project_id) — quote row must already
    exist; brokers create them via the UI or mark-received flow.
    """
    body: dict = {"quote_id": quote_id}
    if api_key:
        body["api_key"] = api_key
    return await post(
        "extract/quote-extraction",
        body,
        extra_headers={"X-Flywheel-Skill": skill_name},
    )


async def save_quote_extraction(
    quote_id: str,
    analysis: dict,
    *,
    api_key: Optional[str] = None,
    skill_name: str = "broker-extract-quote",
) -> dict:
    """Pattern 3a: persist Claude's quote-extraction tool-use output.

    Expected analysis keys (per QUOTE_EXTRACTION_TOOL.input_schema):
        carrier_name, quote_date, quote_reference, currency, total_premium,
        line_items, tool_schema_version
    """
    body: dict = {"quote_id": quote_id, **analysis}
    if api_key:
        body["api_key"] = api_key
    return await post(
        "save/quote-extraction",
        body,
        extra_headers={"X-Flywheel-Skill": skill_name},
    )


async def extract_solicitation_draft(
    project_id: str,
    carrier_config_id: str,
    *,
    api_key: Optional[str] = None,
    skill_name: str = "broker-draft-emails",
) -> dict:
    """Pattern 3a: fetch prompt + tool_schema for solicitation email draft.

    Both `project_id` and `carrier_config_id` are required — the email is
    carrier-specific. Loop over carriers in the caller to draft one per carrier.
    """
    body: dict = {"project_id": project_id, "carrier_config_id": carrier_config_id}
    if api_key:
        body["api_key"] = api_key
    return await post(
        "extract/solicitation-draft",
        body,
        extra_headers={"X-Flywheel-Skill": skill_name},
    )


async def save_solicitation_draft(
    project_id: str,
    carrier_config_id: str,
    analysis: dict,
    *,
    api_key: Optional[str] = None,
    skill_name: str = "broker-draft-emails",
) -> dict:
    """Pattern 3a: persist Claude's solicitation-email tool-use output.

    Expected analysis keys (per SOLICITATION_TOOL.input_schema):
        subject, body_html, tool_schema_version
    """
    body: dict = {
        "project_id": project_id,
        "carrier_config_id": carrier_config_id,
        **analysis,
    }
    if api_key:
        body["api_key"] = api_key
    return await post(
        "save/solicitation-draft",
        body,
        extra_headers={"X-Flywheel-Skill": skill_name},
    )


async def extract_recommendation_draft(
    project_id: str,
    *,
    api_key: Optional[str] = None,
    skill_name: str = "broker-draft-recommendation",
) -> dict:
    """Pattern 3a: fetch prompt + tool_schema for client recommendation narrative.

    Backend assembles the comparison summary + project context into the prompt;
    Claude-in-conversation writes the narrative using RECOMMENDATION_TOOL.
    """
    body: dict = {"project_id": project_id}
    if api_key:
        body["api_key"] = api_key
    return await post(
        "extract/recommendation-draft",
        body,
        extra_headers={"X-Flywheel-Skill": skill_name},
    )


async def save_recommendation_draft(
    project_id: str,
    analysis: dict,
    *,
    api_key: Optional[str] = None,
    skill_name: str = "broker-draft-recommendation",
) -> dict:
    """Pattern 3a: persist Claude's recommendation-narrative tool-use output.

    Expected analysis keys (per RECOMMENDATION_TOOL.input_schema):
        subject, body_html, recipient_email (optional), tool_schema_version
    """
    body: dict = {"project_id": project_id, **analysis}
    if api_key:
        body["api_key"] = api_key
    return await post(
        "save/recommendation-draft",
        body,
        extra_headers={"X-Flywheel-Skill": skill_name},
    )
