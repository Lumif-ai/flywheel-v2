"""
recommendation_drafter.py - Pattern 3a helpers for recommendation email drafts.

Phase 150.1 Plan 04 completed the CC-as-Brain migration by deleting the
legacy `draft_recommendation_email` function (which constructed an async
Anthropic client via a module-local import binding).
Backend no longer runs any LLM call for recommendation drafts;
Claude-in-conversation owns inference. The module exposes only Pattern 3a
public helpers:

  * `build_recommendation_prompt(project, comparison, summary, language)`
    → rendered prompt string for /extract/recommendation-draft.
  * `RECOMMENDATION_TOOL` — Anthropic tool schema declaring the expected
    {subject, body_html} output shape.
  * `persist_recommendation_draft(db, ..., tool_use_output)`
    → BrokerRecommendation ORM row (for /save/recommendation-draft).

CC-as-Brain invariant (Phase 150.1): this module MUST NOT import or
construct an Anthropic async client. The `test_broker_zero_anthropic.py`
regression grep-guards enforce this at CI time.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_recommendation_prompt(
    project: dict,
    comparison: dict,
    summary: dict,
    language: str,
) -> str:
    """Build the recommendation email generation prompt.

    Args:
        project: Dict with project details (name, project_type, contract_value, currency).
        comparison: Output of compare_quotes() — per-coverage ranked quotes.
        summary: Output of summarize_comparison() — counts and highlights.
        language: Language code for the email ("en", "es", etc.).

    Returns:
        Formatted prompt string for AI generation.
    """
    # Format coverage comparison data
    coverage_lines = []
    for cov in comparison.get("coverages", []):
        coverage_type = cov.get("coverage_type", "Unknown")
        recommended_quote = None
        all_quotes = []

        for q in cov.get("quotes", []):
            carrier = q.get("carrier_name", "Unknown")
            premium = q.get("premium")
            premium_str = f"${premium:,.2f}" if premium is not None else "N/A"
            limit = q.get("limit_amount")
            limit_str = f"${limit:,.2f}" if limit is not None else "N/A"
            exclusion_flag = " [CRITICAL EXCLUSION]" if q.get("has_critical_exclusion") else ""

            all_quotes.append(
                f"    - {carrier}: Premium {premium_str}, Limit {limit_str}{exclusion_flag}"
            )

            if q.get("is_recommended"):
                recommended_quote = carrier

        rec_label = f" (Recommended: {recommended_quote})" if recommended_quote else ""
        coverage_lines.append(f"  {coverage_type}{rec_label}:")
        coverage_lines.extend(all_quotes)

    comparison_text = "\n".join(coverage_lines) if coverage_lines else "No comparison data available."

    # Summary highlights
    summary_text = (
        f"- Coverages analyzed: {summary.get('total_coverages', 0)}\n"
        f"- Coverages with clear recommendation: {summary.get('coverages_with_recommendation', 0)}\n"
        f"- Coverages with critical exclusions: {summary.get('coverages_with_critical_exclusions', 0)}\n"
        f"- Best overall price carrier: {summary.get('best_price_carrier', 'N/A')}"
    )

    # Language instruction
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

    return f"""Generate a professional insurance recommendation email from a broker to their client, presenting the results of a quote comparison analysis.

PROJECT DETAILS:
- Project name: {project.get('name', 'Unnamed Project')}
- Project type: {project.get('project_type', 'construction')}
- Contract value: {project.get('contract_value', 'Not specified')} {project.get('currency', 'MXN')}

COMPARISON SUMMARY:
{summary_text}

DETAILED COMPARISON BY COVERAGE:
{comparison_text}

INSTRUCTIONS:
1. Write a professional, clear recommendation email addressed to the client
2. Start with a brief context (we've completed the market analysis for their project)
3. Present the recommended carrier(s) per coverage line with clear reasoning
4. Explain WHY each recommended carrier is the best choice (price, coverage limits, no critical exclusions)
5. Note any critical exclusions or concerns the client should be aware of
6. Include a clear call-to-action asking the client to confirm/approve so you can proceed with binding
7. Close professionally with next steps{language_instruction}

RESPONSE FORMAT:
Return a JSON object with exactly two keys:
- "subject": The email subject line (concise, professional, mentions the project name)
- "body_html": The email body as HTML content tags only (use <p>, <ul>, <li>, <strong>, <table>, <h3> for formatting — NO <html>, <head>, or <body> wrapper tags)

Return ONLY the JSON object, no other text."""


# ---------------------------------------------------------------------------
# Phase 150.1 Plan 04 — legacy `draft_recommendation_email` DELETED.
# Backend owns zero LLM calls for recommendation drafts. Claude-in-conversation
# consumes `build_recommendation_prompt` + `RECOMMENDATION_TOOL` (Pattern 3a).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase 150.1 Plan 02 — Pattern 3a public helpers for extract/save endpoints.
# ---------------------------------------------------------------------------


# Public alias — Pattern 3a prompt builder.
build_recommendation_prompt = _build_recommendation_prompt


# Anthropic tool schema for structured recommendation-draft generation.
RECOMMENDATION_TOOL = {
    "name": "draft_recommendation_email",
    "description": (
        "Generate a professional insurance recommendation email from broker "
        "to client presenting quote comparison results. Returns structured "
        "{subject, body_html}."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": (
                    "Email subject line (concise, professional, "
                    "mentions the project name)."
                ),
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


async def persist_recommendation_draft(
    db: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    tool_use_output: dict,
    recipient_email: str | None = None,
    created_by_user_id: UUID | None = None,
):
    """Persist Claude's recommendation-draft tool_use output as a BrokerRecommendation row.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Tenant UUID.
        project_id: BrokerProject UUID.
        tool_use_output: Dict matching RECOMMENDATION_TOOL.input_schema —
            {subject: str, body_html: str}.
        recipient_email: Optional — the email address the recommendation
            will be sent to.
        created_by_user_id: Optional — the user who triggered the save.

    Returns:
        BrokerRecommendation ORM instance (flushed, not committed).
    """
    from flywheel.db.models import (
        BrokerActivity,
        BrokerProject,
        BrokerRecommendation,
    )

    subject = tool_use_output.get("subject", "") or ""
    body_html = tool_use_output.get("body_html", "") or ""

    # Load project for status transition.
    project_result = await db.execute(
        select(BrokerProject).where(
            BrokerProject.id == project_id,
            BrokerProject.tenant_id == tenant_id,
            BrokerProject.deleted_at.is_(None),
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise ValueError(
            f"BrokerProject not found for persist_recommendation_draft: "
            f"project_id={project_id} tenant_id={tenant_id}"
        )

    # Status transition if project is at quotes_complete.
    if project.status == "quotes_complete":
        from flywheel.api.broker._shared import validate_transition

        validate_transition(
            project.status, "recommended", client_id=project.client_id
        )
        project.status = "recommended"
        project.updated_at = datetime.now(timezone.utc)

    recommendation = BrokerRecommendation(
        tenant_id=tenant_id,
        broker_project_id=project_id,
        subject=subject,
        body=body_html,
        recipient_email=recipient_email,
        status="draft",
        created_by_user_id=created_by_user_id,
    )
    db.add(recommendation)

    activity = BrokerActivity(
        tenant_id=tenant_id,
        broker_project_id=project_id,
        activity_type="recommendation_drafted",
        actor_type="system",
        description=f"AI recommendation drafted (CC-as-Brain) for {project.name}",
        metadata_={
            "recipient": recipient_email,
            "model": "claude-in-conversation",
        },
    )
    db.add(activity)
    await db.flush()
    return recommendation
