"""
recommendation_drafter.py - AI-powered recommendation email generation.

Generates a client-facing recommendation email from quote comparison results
using Claude. Takes plain dicts (not ORM objects) so it can be tested
independently without a database.

Functions:
  draft_recommendation_email(project, comparison, summary, language)
    -> {"subject": str, "body_html": str}
"""

import json
import logging

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-20250514"


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
# Main entry point
# ---------------------------------------------------------------------------


async def draft_recommendation_email(
    project: dict,
    comparison: dict,
    summary: dict,
    language: str = "en",
) -> dict:
    """Generate a recommendation email draft using AI.

    Args:
        project: Dict with project details (name, project_type, contract_value, currency).
        comparison: Output of compare_quotes() — per-coverage ranked quotes.
        summary: Output of summarize_comparison() — counts and highlights.
        language: Language code for the email ("en", "es", etc.).

    Returns:
        {"subject": str, "body_html": str}
    """
    prompt = _build_recommendation_prompt(project, comparison, summary, language)

    client = AsyncAnthropic()
    message = await client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=3000,
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
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        result = json.loads(cleaned)
        subject = result.get("subject", "Insurance Recommendation")
        body_html = result.get("body_html", "<p>Error generating recommendation body.</p>")
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse recommendation draft response: %s", e)
        # Fallback: use raw text as body
        subject = f"Insurance Recommendation - {project.get('name', 'Project')}"
        body_html = f"<p>{response_text}</p>"

    return {"subject": subject, "body_html": body_html}
