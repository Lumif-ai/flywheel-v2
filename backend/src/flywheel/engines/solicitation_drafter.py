"""
solicitation_drafter.py - AI-powered solicitation email draft generation.

Generates carrier-specific solicitation emails using Claude, respecting the
project's language setting. Takes plain dicts (not ORM objects) so it can be
tested independently without a database.

Phase 150.1 Plan 02 — This module now exposes Pattern 3a public helpers
(`build_solicitation_prompt`, `SOLICITATION_TOOL`, `persist_solicitation_draft`)
for the /extract/solicitation-draft + /save/solicitation-draft endpoints.
The legacy `draft_solicitation_email` function (which instantiates
AsyncAnthropic via the `from anthropic import AsyncAnthropic` module-local
binding) is untouched — Plan 04 removes it. Tests MUST patch
`flywheel.engines.solicitation_drafter.AsyncAnthropic` (module-local path),
not `anthropic.AsyncAnthropic` (package path), to cover this shape.

Functions:
  draft_solicitation_email(project, carrier, coverages, documents, language)
    -> {"subject": str, "body_html": str}   (legacy; Plan 04 removes)
  build_solicitation_prompt(...) -> str     (Pattern 3a public helper)
  persist_solicitation_draft(...) -> SolicitationDraft  (save endpoint)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEADLINE_DAYS = 30


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_prompt(
    project: dict,
    carrier: dict,
    coverages: list[dict],
    documents: list[dict],
    language: str,
) -> str:
    """Build the solicitation email generation prompt."""
    deadline = (datetime.now(timezone.utc) + timedelta(days=DEADLINE_DAYS)).strftime("%Y-%m-%d")

    # Format coverages as a table
    coverage_lines = []
    for cov in coverages:
        coverage_lines.append(
            f"- {cov.get('coverage_type', 'Unknown')}: "
            f"Limit {cov.get('required_limit', 'TBD')}, "
            f"Gap status: {cov.get('gap_status', 'unknown')}"
        )
    coverage_text = "\n".join(coverage_lines) if coverage_lines else "No specific coverages listed."

    # Format documents as a list
    doc_lines = []
    for doc in documents:
        if doc.get("included", True):
            doc_lines.append(f"- {doc.get('display_name', 'Document')} ({doc.get('document_type', 'supporting')})")
    documents_text = "\n".join(doc_lines) if doc_lines else "No documents attached."

    language_instruction = ""
    if language == "es":
        language_instruction = (
            "\n\nIMPORTANT: Write the ENTIRE email in Spanish. "
            "All headings, greetings, body text, and closing must be in Spanish. "
            "Do not use any English."
        )
    elif language != "en":
        language_instruction = (
            f"\n\nIMPORTANT: Write the ENTIRE email in the language code '{language}'. "
            "All headings, greetings, body text, and closing must be in that language."
        )

    return f"""Generate a professional insurance solicitation email from a broker to a carrier requesting a quote.

PROJECT DETAILS:
- Project name: {project.get('name', 'Unnamed Project')}
- Project type: {project.get('project_type', 'construction')}
- Contract value: {project.get('contract_value', 'Not specified')} {project.get('currency', 'MXN')}

CARRIER:
- Carrier name: {carrier.get('carrier_name', 'Carrier')}

COVERAGE REQUIREMENTS:
{coverage_text}

AVAILABLE DOCUMENTS:
{documents_text}

DEADLINE: Please provide a quote by {deadline}

INSTRUCTIONS:
1. Write a professional, concise solicitation email
2. Include a carrier-specific greeting using the carrier name
3. Summarize the project scope and insurance needs
4. Present coverage requirements clearly
5. Reference the available documents (mention they are attached/available for download)
6. Request a quote with the deadline
7. Close professionally{language_instruction}

RESPONSE FORMAT:
Return a JSON object with exactly two keys:
- "subject": The email subject line (concise, professional)
- "body_html": The email body as HTML (use <p>, <ul>, <li>, <strong>, <table> tags for formatting)

Return ONLY the JSON object, no other text."""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def draft_solicitation_email(
    project: dict,
    carrier: dict,
    coverages: list[dict],
    documents: list[dict],
    language: str = "en",
) -> dict:
    """Generate a solicitation email draft using AI.

    Args:
        project: Dict with project details (name, project_type, contract_value, currency).
        carrier: Dict with carrier details (carrier_name).
        coverages: List of coverage dicts (coverage_type, required_limit, gap_status).
        documents: List of document dicts (display_name, document_type, included).
        language: Language code for the email ("en", "es", etc.).

    Returns:
        {"subject": str, "body_html": str}
    """
    prompt = _build_prompt(project, carrier, coverages, documents, language)

    client = AsyncAnthropic()
    message = await client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text content from the response
    response_text = ""
    for block in message.content:
        if block.type == "text":
            response_text += block.text

    # Parse JSON response
    try:
        # Handle potential markdown code fences around JSON
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            # Remove code fence
            lines = cleaned.split("\n")
            # Remove first and last lines (```json and ```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        result = json.loads(cleaned)
        subject = result.get("subject", "Insurance Quote Request")
        body_html = result.get("body_html", "<p>Error generating email body.</p>")
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse solicitation draft response: %s", e)
        # Fallback: use raw text as body
        subject = "Insurance Quote Request"
        body_html = f"<p>{response_text}</p>"

    return {"subject": subject, "body_html": body_html}


# ---------------------------------------------------------------------------
# Phase 150.1 Plan 02 — Pattern 3a public helpers for extract/save endpoints.
# ---------------------------------------------------------------------------


# Public alias — Pattern 3a prompt builder.
# Use `build_solicitation_prompt(...)` from api/broker/solicitations.py.
build_solicitation_prompt = _build_prompt


# Anthropic tool schema for structured solicitation-draft generation.
# Shape of `input_schema` matches the JSON object the legacy function parses
# (`subject` + `body_html`), promoted to a proper tool_use schema so
# Claude-in-conversation can return structured output on the save endpoint.
SOLICITATION_TOOL = {
    "name": "draft_solicitation_email",
    "description": (
        "Generate a professional insurance solicitation email to a carrier "
        "requesting a quote. Returns a structured {subject, body_html}."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Email subject line (concise, professional).",
            },
            "body_html": {
                "type": "string",
                "description": (
                    "Email body as HTML content tags only "
                    "(use <p>, <ul>, <li>, <strong>, <table>, <h3> — no <html>/<head>/<body>)."
                ),
            },
        },
        "required": ["subject", "body_html"],
    },
}


async def persist_solicitation_draft(
    db: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    carrier_config_id: UUID,
    tool_use_output: dict,
    sent_to_email: str | None = None,
    created_by_user_id: UUID | None = None,
):
    """Persist Claude's solicitation-draft tool_use output as a SolicitationDraft row.

    Args:
        db: Async SQLAlchemy session (caller manages transaction).
        tenant_id: Tenant UUID.
        project_id: BrokerProject UUID.
        carrier_config_id: CarrierConfig UUID.
        tool_use_output: Dict matching SOLICITATION_TOOL.input_schema —
            {subject: str, body_html: str}.
        sent_to_email: Optional carrier contact email to record.
        created_by_user_id: Optional — the user who triggered the save.

    Returns:
        SolicitationDraft ORM instance (flushed, not committed).
    """
    # Import models here to avoid circular-import cost at module load.
    from flywheel.db.models import BrokerActivity, SolicitationDraft

    subject = tool_use_output.get("subject", "") or ""
    body_html = tool_use_output.get("body_html", "") or ""

    # Reuse an existing active draft if one exists (same pattern as the
    # legacy batch endpoint).
    existing_result = await db.execute(
        select(SolicitationDraft).where(
            SolicitationDraft.broker_project_id == project_id,
            SolicitationDraft.carrier_config_id == carrier_config_id,
            SolicitationDraft.status.in_(["draft", "pending", "approved"]),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        existing.subject = subject
        existing.body = body_html
        existing.status = "pending"
        if sent_to_email:
            existing.sent_to_email = sent_to_email
        await db.flush()
        draft = existing
    else:
        draft = SolicitationDraft(
            tenant_id=tenant_id,
            broker_project_id=project_id,
            carrier_config_id=carrier_config_id,
            subject=subject,
            body=body_html,
            status="pending",
            sent_to_email=sent_to_email,
            created_by_user_id=created_by_user_id,
        )
        db.add(draft)
        await db.flush()

    activity = BrokerActivity(
        tenant_id=tenant_id,
        broker_project_id=project_id,
        activity_type="solicitations_drafted",
        actor_type="system",
        description=f"Solicitation draft persisted (CC-as-Brain)",
        metadata_={
            "carrier_config_id": str(carrier_config_id),
            "draft_id": str(draft.id),
            "model": "claude-in-conversation",
        },
    )
    db.add(activity)
    await db.flush()
    return draft
