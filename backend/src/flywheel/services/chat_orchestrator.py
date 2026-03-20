"""Chat orchestrator -- Haiku intent classification + parameter extraction.

Uses Claude Haiku (fast, cheap ~$0.005/call) to classify user intent from
natural language and route to the correct skill. The orchestrator uses the
platform's subsidized API key, NOT the user's BYOK key.

Public API:
    classify_intent(user_message, available_skills) -> dict
"""

from __future__ import annotations

import json
import logging
import re

from flywheel.config import settings

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]  # Deferred -- only needed at call time

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """You are a skill router for Flywheel, a knowledge compounding engine.
Given the user's message and available skills, determine:
1. Which skill to run (skill_name) -- must be one of the available skills
2. What input text to pass to the skill (input_text)
3. Your confidence level (0.0 to 1.0)

Available skills:
{skills_json}

Respond with ONLY a JSON object, no markdown fences or extra text:
- If clear match: {{"action": "execute", "skill_name": "...", "input_text": "...", "confidence": 0.0-1.0}}
- If ambiguous: {{"action": "clarify", "message": "...", "candidates": ["skill1", "skill2"]}}
- If no match: {{"action": "none", "message": "I can help with..."}}
"""

_HAIKU_MODEL = "claude-haiku-4-5-20251001"


async def classify_intent(
    user_message: str,
    available_skills: list[dict],
) -> dict:
    """Classify user intent using Haiku (fast, cheap: ~$0.005/call).

    Uses the platform's subsidized API key for orchestration -- this cost
    is borne by the platform, not the user.

    Args:
        user_message: The natural language message from the user.
        available_skills: List of skill metadata dicts with 'name' and 'description'.

    Returns:
        Dict with 'action' key ('execute', 'clarify', or 'none') and
        action-specific fields.
    """
    if anthropic is None:
        raise ImportError("anthropic SDK required for chat orchestration")

    client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)

    skills_json = json.dumps(
        [{"name": s["name"], "description": s["description"]} for s in available_skills],
        indent=2,
    )

    response = await client.messages.create(
        model=_HAIKU_MODEL,
        max_tokens=500,
        system=INTENT_SYSTEM_PROMPT.format(skills_json=skills_json),
        messages=[{"role": "user", "content": user_message}],
    )

    text = response.content[0].text.strip()

    # Parse response: try direct JSON first, then regex fallback for markdown-fenced JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Regex fallback: extract JSON object from markdown fences or surrounding text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Complete parse failure -- return safe fallback
    logger.warning("Failed to parse Haiku response as JSON: %s", text[:200])
    return {
        "action": "none",
        "message": "I couldn't understand that. Could you rephrase?",
    }
