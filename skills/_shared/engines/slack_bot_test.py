"""Flywheel Slack bot — with natural language routing and @mention support."""

import asyncio
import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from execution_gateway import ExecutionResult, execute_skill
from skill_converter import convert_skill
from user_memory import ensure_user_initialized, resolve_parameters

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

SKILL_ALIASES = {
    "prep": "meeting-prep",
    "score": "gtm-company-fit-analyzer",
    "pipeline": "gtm-pipeline",
    "update": "investor-update",
    "process": "meeting-processor",
    "company": "gtm-my-company",
}

# ---------------------------------------------------------------------------
# Natural language intent detection
# ---------------------------------------------------------------------------

INTENT_PATTERNS = [
    # (keywords, skill_name, arg_extraction_hint)
    {
        "keywords": ["prep", "prepare", "meeting", "briefing", "brief me", "call with", "meeting with"],
        "skill": "meeting-prep",
        "hint": "company_or_contact",
    },
    {
        "keywords": ["score", "qualify", "fit", "evaluate", "assess", "good fit", "is .* a fit"],
        "skill": "gtm-company-fit-analyzer",
        "hint": "company",
    },
    {
        "keywords": ["pipeline", "outreach", "gtm", "leads", "prospects"],
        "skill": "gtm-pipeline",
        "hint": None,
    },
    {
        "keywords": ["investor", "update", "monthly update", "board update"],
        "skill": "investor-update",
        "hint": None,
    },
    {
        "keywords": ["review", "contract", "legal", "nda", "agreement", "safe", "term sheet"],
        "skill": "legal",
        "hint": "document",
    },
    {
        "keywords": ["post", "draft", "tweet", "linkedin", "social", "write about", "content"],
        "skill": "social-media-manager",
        "hint": "topic",
    },
    {
        "keywords": ["process", "transcript", "meeting notes", "what was discussed"],
        "skill": "meeting-processor",
        "hint": "transcript",
    },
    {
        "keywords": ["company profile", "my company", "our company", "about us"],
        "skill": "gtm-my-company",
        "hint": "url",
    },
]


def detect_intent(text: str) -> tuple:
    """Detect skill intent from natural language input.

    Returns (skill_name, extracted_arg, confidence).
    confidence: "high" if strong keyword match, "low" if fuzzy.
    Returns (None, None, None) if no intent detected.
    """
    lower = text.lower()

    for pattern in INTENT_PATTERNS:
        for keyword in pattern["keywords"]:
            # Support regex patterns in keywords (e.g., "is .* a fit")
            if "." in keyword and "*" in keyword:
                if re.search(keyword, lower):
                    arg = _extract_arg(text, lower, pattern["hint"])
                    return pattern["skill"], arg, "high"
            elif keyword in lower:
                arg = _extract_arg(text, lower, pattern["hint"])
                return pattern["skill"], arg, "high"

    return None, None, None


def _extract_arg(original_text: str, lower_text: str, hint: str) -> str:
    """Extract the relevant argument from natural language text."""
    if not hint:
        return ""

    # Extract URLs first (LinkedIn, websites)
    url_match = re.search(r'https?://\S+', original_text)
    if url_match:
        return url_match.group(0)

    if hint == "company_or_contact":
        # Try to extract entity after "with", "for", "about", "on"
        for prep in ["with", "for", "about", "on", "regarding"]:
            match = re.search(rf'\b{prep}\s+(.+?)(?:\s+(?:tomorrow|today|next|this|on\s)|\s*$)', original_text, re.IGNORECASE)
            if match:
                return match.group(1).strip().rstrip("?.,!")
        # Fallback: return everything after the first recognized keyword
        return ""

    if hint == "company":
        # Similar extraction for company names
        for prep in ["for", "about", "on", "company"]:
            match = re.search(rf'\b{prep}\s+(.+?)(?:\s*$)', original_text, re.IGNORECASE)
            if match:
                return match.group(1).strip().rstrip("?.,!")
        return ""

    if hint == "topic":
        for prep in ["about", "on", "regarding"]:
            match = re.search(rf'\b{prep}\s+(.+?)$', original_text, re.IGNORECASE)
            if match:
                return match.group(1).strip().rstrip("?.,!")
        return ""

    return ""


# ---------------------------------------------------------------------------
# Skill execution (shared between /fly and @mention)
# ---------------------------------------------------------------------------

async def run_skill_and_respond(skill_name: str, args_text: str, user_id: str, respond_fn):
    """Execute a skill and send the result via respond_fn.

    respond_fn: either Slack's respond() or a wrapper around chat_postMessage.
    """
    # Initialize user silently
    try:
        ensure_user_initialized(user_id)
    except Exception:
        pass

    # Map args to params for known skills
    params = {}
    force_llm = False

    if skill_name in ("meeting-prep", "ctx-meeting-prep"):
        if args_text and ("http" in args_text or "linkedin.com" in args_text):
            force_llm = True
        else:
            params["company_name"] = args_text
            params["contact_name"] = ""
    elif skill_name in ("gtm-company-fit-analyzer", "company-fit-analyzer"):
        params["company_name"] = args_text
    elif skill_name in ("gtm-my-company", "ctx-gtm-my-company"):
        params["url"] = args_text

    # Execute
    try:
        if force_llm:
            logger.info("Forcing LLM path for %s (URL input)", skill_name)
            from execution_gateway import run_llm_skill
            from skill_converter import ExecutionSpec

            # Use a focused system prompt (not the full 800-line SKILL.md)
            # to keep token usage reasonable
            focused_spec = ExecutionSpec(
                name="meeting-prep",
                description="Prepare a meeting briefing",
                system_prompt=(
                    "You are a meeting preparation assistant with web research capabilities.\n\n"
                    "Available tools:\n"
                    "- web_fetch: Fetch and read any URL (LinkedIn profiles, company websites)\n"
                    "- web_search: Search the web via DuckDuckGo\n"
                    "- read_context: Read from the company knowledge base (contacts, competitive intel, etc.)\n\n"
                    "Your task: prepare a meeting briefing for the given person/company.\n\n"
                    "Steps:\n"
                    "1. Use web_fetch to read the provided URL (LinkedIn profile, company page)\n"
                    "2. Use web_search to find additional info (company, role, recent news)\n"
                    "3. Use read_context to check contacts.md, competitive-intel.md, pain-points.md for prior knowledge\n"
                    "4. Synthesize into a briefing: Person summary, Company context, "
                    "Relevant insights from our knowledge base, Suggested talking points\n\n"
                    "Be thorough in research but concise in output. Markdown format."
                ),
                parameters=[],
                tools=convert_skill(skill_name).tools,  # includes web_search + web_fetch now
                contract={"reads": ["*"], "writes": []},
                has_engine=False,
                token_budget=10000,
                skill_path=None,
            )
            llm_output, token_usage, attribution = await asyncio.to_thread(
                run_llm_skill, focused_spec,
                f"Prepare a meeting briefing for this person: {args_text}",
                user_id,
                8,  # enough iterations for web research + context reads
            )
            result = ExecutionResult(
                output=llm_output, mode="llm", skill_name=skill_name,
                user_id=user_id, token_usage=token_usage,
                duration_ms=0, context_attribution=attribution,
            )
        else:
            result = await asyncio.to_thread(
                execute_skill, skill_name, args_text or skill_name, user_id, params
            )

        # Format output
        output = result.output or "No output"
        if len(output) > 2900:
            output = output[:2900] + "\n\n_(truncated)_"

        mode_label = "engine" if result.mode == "engine" else "LLM"
        footer = f"_Mode: {mode_label} | Duration: {result.duration_ms}ms_"

        if result.token_usage:
            in_t = result.token_usage.get("input_tokens", 0)
            out_t = result.token_usage.get("output_tokens", 0)
            footer += f" _| Tokens: {in_t} in / {out_t} out_"

        await respond_fn(text=f"*{skill_name}*\n\n{output}\n\n{footer}")

    except Exception as e:
        logger.error("Skill execution failed: %s", e, exc_info=True)
        await respond_fn(text=f"Something went wrong running `{skill_name}`: {e}")


# ---------------------------------------------------------------------------
# /fly command handler
# ---------------------------------------------------------------------------

@app.command("/fly")
async def handle_fly(ack, command, respond, client):
    text = command.get("text", "").strip()
    user_id = command.get("user_id", "")
    logger.info("/fly command: text='%s' user=%s", text, user_id)

    # --- Fast responses via ack ---

    if not text or text == "help":
        aliases_text = "\n".join(f"- `/fly {a}` — {s}" for a, s in SKILL_ALIASES.items())
        await ack(text=(
            "*Flywheel Commands:*\n"
            f"{aliases_text}\n\n"
            "Or just describe what you need:\n"
            "- `/fly prepare for my meeting with Acme`\n"
            "- `/fly score BuildCo as a lead`\n"
            "- `/fly draft a post about our launch`\n\n"
            "You can also @mention me: `@Flywheel prep for Acme`"
        ))
        return

    if text == "skills":
        aliases_text = "\n".join(f"- `{a}` → {s}" for a, s in SKILL_ALIASES.items())
        await ack(text=f"*Available Skills:*\n{aliases_text}")
        return

    # --- Route: try alias first, then natural language ---

    parts = text.split(None, 1)
    subcommand = parts[0].lower()
    args_text = parts[1] if len(parts) > 1 else ""

    # Check if first word is a known alias or skill name
    skill_name = SKILL_ALIASES.get(subcommand)
    if skill_name:
        await ack(text=f"Running *{skill_name}*...")
        await run_skill_and_respond(skill_name, args_text, user_id, respond)
        return

    # Check if first word IS a skill name (e.g., "meeting-prep")
    try:
        convert_skill(subcommand)
        skill_name = subcommand
        await ack(text=f"Running *{skill_name}*...")
        await run_skill_and_respond(skill_name, args_text, user_id, respond)
        return
    except FileNotFoundError:
        pass

    # Natural language: detect intent from full text
    detected_skill, extracted_arg, confidence = detect_intent(text)
    if detected_skill:
        # Use extracted arg, or fall back to full text as context
        final_arg = extracted_arg or text
        await ack(text=f"Got it! Running *{detected_skill}*...")
        await run_skill_and_respond(detected_skill, final_arg, user_id, respond)
        return

    # Nothing matched
    await ack(text=(
        f"I'm not sure what you mean by `{text}`.\n\n"
        "Try `/fly help` for available commands, or describe what you need:\n"
        "- `prep for my call with Acme`\n"
        "- `score BuildCo`\n"
        "- `review this contract`"
    ))


# ---------------------------------------------------------------------------
# @mention handler (natural language)
# ---------------------------------------------------------------------------

@app.event("app_mention")
async def handle_mention(event, client, say):
    """Handle @Flywheel mentions with natural language routing."""
    text = event.get("text", "")
    user_id = event.get("user", "")
    channel_id = event.get("channel", "")

    # Strip the bot mention tag (<@BOT_ID>)
    clean_text = re.sub(r'<@\w+>\s*', '', text).strip()
    logger.info("@mention: text='%s' user=%s channel=%s", clean_text, user_id, channel_id)

    if not clean_text:
        await say(
            text=(
                "Hey! Tell me what you need:\n"
                "- `prep for my call with Acme`\n"
                "- `score BuildCo as a lead`\n"
                "- `draft a post about our launch`\n"
                "- `review this contract`\n\n"
                "Or use `/fly help` for all commands."
            ),
            channel=channel_id,
        )
        return

    # Try alias first (e.g., "@Flywheel prep Acme")
    parts = clean_text.split(None, 1)
    subcommand = parts[0].lower()
    args_text = parts[1] if len(parts) > 1 else ""

    skill_name = SKILL_ALIASES.get(subcommand)
    if skill_name:
        await say(text=f"Running *{skill_name}*...", channel=channel_id)

        async def respond_via_say(**kwargs):
            await client.chat_postMessage(channel=channel_id, **kwargs)

        await run_skill_and_respond(skill_name, args_text, user_id, respond_via_say)
        return

    # Natural language detection
    detected_skill, extracted_arg, confidence = detect_intent(clean_text)
    if detected_skill:
        final_arg = extracted_arg or clean_text
        await say(text=f"Got it! Running *{detected_skill}*...", channel=channel_id)

        async def respond_via_say(**kwargs):
            await client.chat_postMessage(channel=channel_id, **kwargs)

        await run_skill_and_respond(detected_skill, final_arg, user_id, respond_via_say)
        return

    # Nothing matched — be helpful
    await say(
        text=(
            f"I'm not sure what you mean by \"{clean_text}\".\n\n"
            "Try things like:\n"
            "- `prep for my call with Acme`\n"
            "- `score BuildCo`\n"
            "- `what's our pipeline status`"
        ),
        channel=channel_id,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logger.info("Starting Flywheel bot...")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
