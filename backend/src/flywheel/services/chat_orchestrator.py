"""Chat orchestrator -- Haiku intent classification + parameter extraction.

Uses Claude Haiku (fast, cheap ~$0.005/call) to classify user intent from
natural language and route to the correct skill. The orchestrator uses the
platform's subsidized API key, NOT the user's BYOK key.

Public API:
    classify_intent(user_message, available_skills, history, stream_context) -> dict
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
Given the user's message and available skills, determine the appropriate action.

Available skills:
{skills_json}

{stream_context_block}

Respond with ONLY a JSON object, no markdown fences or extra text:
- If clear skill match: {{"action": "execute", "skill_name": "...", "input_text": "...", "confidence": 0.0-1.0}}
- If ambiguous, could map to multiple skills: {{"action": "clarify", "message": "...", "candidates": ["skill1", "skill2"]}}
- If conversational (question, greeting, follow-up, or request that does NOT require running a skill): {{"action": "conversational", "response": "your helpful reply here"}}
- If completely off-topic or unsupported: {{"action": "none", "message": "I can help with..."}}

CRITICAL ROUTING RULES:
- ALWAYS prefer "execute" over "conversational" when a skill can handle the request. Skills have web search, research capabilities, and produce rich outputs that conversational responses cannot.
- Do NOT ask clarifying questions if you have enough to run the skill. Pass what you have in input_text -- the skill engine will handle the rest.
- "meeting", "prepare for", "prep for", "meeting with [name]" -> ALWAYS route to meeting-prep skill. Include the person's name, company, LinkedIn URL, and meeting purpose in input_text.
- "research [company]", "tell me about [company]", "analyze [company]" -> route to company-intel skill.
- Only use "conversational" for greetings, thanks, meta-questions about Flywheel, or questions answerable from the provided business context without needing a skill run.
- Only use "clarify" when the request genuinely maps to 2+ skills and you cannot determine which one.

Action guidelines:
- "execute" -- user wants to run a skill (research, analyze, prepare, generate, etc.)
- "clarify" -- genuinely ambiguous between multiple skills (rare)
- "conversational" -- greetings, thanks, meta-questions, or simple factual answers from context
- "none" -- completely off-topic or unsupported request
"""

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

# Maximum number of history messages to include in the Haiku prompt
_MAX_HISTORY_MESSAGES = 5


async def classify_intent(
    user_message: str,
    available_skills: list[dict],
    history: list[dict] | None = None,
    stream_context: str | None = None,
    briefing_context: str | None = None,
    tenant_context: str | None = None,
) -> dict:
    """Classify user intent using Haiku (fast, cheap: ~$0.005/call).

    Uses the platform's subsidized API key for orchestration -- this cost
    is borne by the platform, not the user.

    Args:
        user_message: The natural language message from the user.
        available_skills: List of skill metadata dicts with 'name' and 'description'.
        history: Optional conversation history (list of dicts with 'role' and 'content').
            Only the last 5 messages are included for context.
        stream_context: Optional work stream context string from stream_id resolution.
            Prepended to the system prompt to improve routing decisions.
        briefing_context: Optional briefing content string from briefing_id resolution.
            Injected into the system prompt so the LLM can answer questions about the briefing.

    Returns:
        Dict with 'action' key ('execute', 'clarify', 'conversational', or 'none')
        and action-specific fields.
    """
    if anthropic is None:
        raise ImportError("anthropic SDK required for chat orchestration")

    client = anthropic.AsyncAnthropic(api_key=settings.flywheel_subsidy_api_key)

    skills_json = json.dumps(
        [{"name": s["name"], "description": s["description"]} for s in available_skills],
        indent=2,
    )

    # Build stream context block for the system prompt
    stream_context_block = ""
    if stream_context:
        stream_context_block = f"The user is working in the context of: {stream_context}"

    system_prompt = INTENT_SYSTEM_PROMPT.format(
        skills_json=skills_json,
        stream_context_block=stream_context_block,
    )

    # Inject tenant business context so the classifier (and conversational
    # responses) are grounded in what the platform already knows about the user's
    # company. This is the core Flywheel value: every interaction is informed.
    if tenant_context:
        system_prompt += (
            "\n\nThe user's company context (from their knowledge store):\n"
            + tenant_context
            + "\n\nUse this context when generating conversational responses. "
            "Do NOT ask the user for information already provided above."
        )

    # Inject briefing context when user is reading a specific briefing
    if briefing_context:
        system_prompt += (
            "\n\nThe user is currently reading a briefing. "
            "When they ask questions, answer based on this briefing content. "
            "Prefer 'conversational' action for questions about the briefing.\n\n"
            f"Briefing content:\n{briefing_context}"
        )

    # Build messages list: include recent history for multi-turn context
    messages: list[dict] = []
    if history:
        # Include last N messages for conversation context
        recent_history = history[-_MAX_HISTORY_MESSAGES:]
        for msg in recent_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # Always append the current user message
    messages.append({"role": "user", "content": user_message})

    response = await client.messages.create(
        model=_HAIKU_MODEL,
        max_tokens=500,
        system=system_prompt,
        messages=messages,
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
