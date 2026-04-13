"""
solicitation_drafter.py - AI-powered solicitation email draft generation.

Generates carrier-specific solicitation emails using Claude, respecting the
project's language setting. Takes plain dicts (not ORM objects) so it can be
tested independently without a database.

Functions:
  draft_solicitation_email(project, carrier, coverages, documents, language)
    -> {"subject": str, "body_html": str}
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from anthropic import AsyncAnthropic

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
