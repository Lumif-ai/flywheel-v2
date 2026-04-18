"""
solicitation_drafter.py - Pattern 3a helpers for solicitation email drafts.

Phase 150.1 Plan 04 completed the CC-as-Brain migration by deleting the
legacy `draft_solicitation_email` function (which constructed an async
Anthropic client via a module-local import binding).
Backend no longer runs any LLM call for solicitation drafts;
Claude-in-conversation owns inference. The module exposes only Pattern 3a
public helpers:

  * `build_solicitation_prompt(project, carrier, coverages, documents, language)`
    → rendered prompt string for the /extract/solicitation-draft endpoint.
  * `SOLICITATION_TOOL` — Anthropic tool schema declaring the expected
    {subject, body_html} output shape.
  * `persist_solicitation_draft(db, ..., tool_use_output)`
    → SolicitationDraft ORM row (for /save/solicitation-draft).

CC-as-Brain invariant (Phase 150.1): this module MUST NOT import or
construct an Anthropic async client. The `test_broker_zero_anthropic.py`
regression grep-guards enforce this at CI time.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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
# Phase 150.1 Plan 04 — legacy `draft_solicitation_email` DELETED.
# Backend owns zero LLM calls for solicitation drafts. Claude-in-conversation
# consumes `build_solicitation_prompt` + `SOLICITATION_TOOL` (Pattern 3a).
# ---------------------------------------------------------------------------


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
