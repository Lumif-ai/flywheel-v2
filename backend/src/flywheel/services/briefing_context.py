"""Briefing context loader for chat orchestration.

Resolves a briefing_id (SkillRun ID) to a context string that helps the
chat orchestrator answer questions about the briefing the user is reading.
The briefing content is injected into the system prompt per-request and
NOT stored in chat history.
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import SkillRun

logger = logging.getLogger(__name__)

# Maximum characters of briefing content to include in the system prompt.
# Beyond this, we truncate and use metadata/input_text as fallback context.
_MAX_CONTENT_CHARS = 4000


def _strip_html_tags(html: str) -> str:
    """Remove HTML tags, leaving only text content."""
    return re.sub(r"<[^>]+>", " ", html).strip()


def _truncate_content(text: str, max_chars: int = _MAX_CONTENT_CHARS) -> str:
    """Truncate text to max_chars, breaking at a sentence boundary if possible."""
    if len(text) <= max_chars:
        return text
    # Try to break at a sentence boundary
    truncated = text[:max_chars]
    last_period = truncated.rfind(". ")
    if last_period > max_chars * 0.5:
        return truncated[: last_period + 1] + " [truncated]"
    return truncated + "... [truncated]"


async def load_briefing_context(
    briefing_id: str,
    db: AsyncSession,
) -> str | None:
    """Load briefing content as context for the chat orchestrator.

    Fetches the SkillRun by ID and extracts a text summary from its
    rendered_html. If the HTML is too long, falls back to input_text
    and metadata.

    Args:
        briefing_id: The SkillRun UUID string from the frontend.
        db: Async database session.

    Returns:
        A context string describing the briefing content, or None if not found.
    """
    try:
        run_id = UUID(briefing_id)
    except (ValueError, AttributeError):
        return None

    result = await db.execute(
        select(SkillRun).where(SkillRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None

    parts: list[str] = []

    # Add skill name and input for context
    if run.skill_name:
        parts.append(f"Briefing type: {run.skill_name}.")
    if run.input_text:
        parts.append(f"Subject: {run.input_text}.")

    # Extract text content from rendered HTML
    if run.rendered_html:
        plain_text = _strip_html_tags(run.rendered_html)
        # Collapse whitespace
        plain_text = re.sub(r"\s+", " ", plain_text).strip()
        if plain_text:
            parts.append(_truncate_content(plain_text))
    elif run.input_text:
        # No HTML available -- use input_text as the only context
        parts.append(f"The briefing is about: {run.input_text}")

    if not parts:
        return None

    return "\n".join(parts)
