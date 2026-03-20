"""
Slack bot for headless skill invocation via Socket Mode.

Provides /fly slash command for invoking skills from Slack. Supports:
- Mode 1: Fully specified commands (e.g., /fly prep Acme)
- Mode 2: Guided mode for missing parameters (DM conversation)
- DM onboarding for new users
- Block Kit formatted results
- Async execution with 3-second ack deadline

Public API:
    app: AsyncApp instance
    main(): Start the bot via Socket Mode
    format_result_blocks(result): Format ExecutionResult as Slack blocks
"""

import asyncio
import logging
import os
import re
import sys
from pathlib import Path

import frontmatter

try:
    import httpx as _httpx
except ImportError:
    _httpx = None

# Import from src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import company_intel
import context_utils
import retention
from execution_gateway import ExecutionResult, execute_skill
from user_memory import (
    ensure_user_initialized,
    is_onboarding_complete,
    load_user_preferences,
    resolve_parameters,
    save_preferences_batch,
    save_user_preference,
)
from skill_converter import convert_skill
from skill_governance import init_skills_repo, check_token_budget

# Integration modules (graceful fallback if not all dependencies installed)
_integration_framework = None
_nudge_engine = None
_email_sender = None
_browser_sessions = None
_watcher_meeting_notes = None
_watcher_calendar = None
_watcher_email = None
_watcher_slack_channels = None

try:
    import integration_framework as _integration_framework
except ImportError:
    pass

try:
    import nudge_engine as _nudge_engine
except ImportError:
    pass

try:
    import email_sender as _email_sender
except ImportError:
    pass

try:
    import browser_sessions as _browser_sessions
except ImportError:
    pass

try:
    import watcher_meeting_notes as _watcher_meeting_notes
except ImportError:
    pass

try:
    import watcher_calendar as _watcher_calendar
except ImportError:
    pass

try:
    import watcher_email as _watcher_email
except ImportError:
    pass

try:
    import watcher_slack_channels as _watcher_slack_channels
except ImportError:
    pass

try:
    from slack_bolt.async_app import AsyncApp
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
except ImportError:
    AsyncApp = None
    AsyncSocketModeHandler = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

def _create_app():
    """Create AsyncApp lazily to avoid requiring token at import time."""
    if AsyncApp and os.environ.get("SLACK_BOT_TOKEN"):
        return AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
    return None

app = _create_app()

# ---------------------------------------------------------------------------
# Skill aliases for user-friendly subcommands
# ---------------------------------------------------------------------------

SKILL_ALIASES = {
    "prep": "meeting-prep",
    "score": "gtm-company-fit-analyzer",
    "pipeline": "gtm-pipeline",
    "update": "investor-update",
    "process": "meeting-processor",
    "company": "gtm-my-company",
}

# ---------------------------------------------------------------------------
# Guided mode state (in-memory, per user+channel)
# ---------------------------------------------------------------------------

GUIDED_SESSIONS = {}  # keyed by (user_id, channel_id)

# ---------------------------------------------------------------------------
# Onboarding state (in-memory, per user)
# ---------------------------------------------------------------------------

ONBOARDING_SESSIONS = {}  # keyed by user_id

# ---------------------------------------------------------------------------
# Dynamic skill listing and smart recommendation
# ---------------------------------------------------------------------------


def list_available_skills(skills_dir: Path = None) -> list:
    """List all installed skills with name and description from SKILL.md frontmatter.

    Walks the skills directory, reads SKILL.md frontmatter from each
    subdirectory (skipping directories starting with '_'), and returns
    a sorted list of skill info dicts.

    Args:
        skills_dir: Root directory containing skill subdirectories.
            Defaults to ~/.claude/skills.

    Returns:
        List of dicts with keys: name, description, dir_name. Sorted by name.
    """
    if skills_dir is None:
        skills_dir = Path.home() / ".claude" / "skills"

    if not skills_dir.exists():
        return []

    skills = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_"):
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            post = frontmatter.load(str(skill_md))
            name = post.get("name", entry.name)
            description = post.get("description", "")
            if isinstance(description, str):
                description = description.strip()
            skills.append({
                "name": name,
                "description": description,
                "dir_name": entry.name,
            })
        except Exception:
            # Skip skills with malformed SKILL.md
            continue

    skills.sort(key=lambda s: s["name"].lower())
    return skills


def recommend_skill(skills_dir: Path = None) -> dict:
    """Recommend the best next skill based on available context.

    Checks context store for existing data and recommends a skill
    based on what would be most valuable given current context state.

    Priority logic:
    1. If ICP populated and company-fit skill available -> recommend scoring
    2. If positioning strong and social-post skill available -> recommend social post
    3. Default -> meeting-prep (universally useful, needs only company name)

    Args:
        skills_dir: Root directory containing skill subdirectories.
            Defaults to ~/.claude/skills.

    Returns:
        Dict with keys: skill_name, alias, reason, example_prompt.
    """
    # Check what context data exists
    icp_content = ""
    positioning_content = ""
    try:
        icp_content = context_utils.read_context("icp-profiles.md", agent_id="recommend")
    except Exception:
        pass
    try:
        positioning_content = context_utils.read_context("positioning.md", agent_id="recommend")
    except Exception:
        pass

    available = list_available_skills(skills_dir)
    available_names = {s["dir_name"] for s in available}

    # Priority 1: ICP populated + company-fit skill available
    if icp_content and icp_content.strip():
        fit_names = ["gtm-company-fit-analyzer", "company-fit-analyzer"]
        for fit_name in fit_names:
            if fit_name in available_names:
                return {
                    "skill_name": fit_name,
                    "alias": "score",
                    "reason": "You have ICP profiles set up. Score a company against your ideal customer profile.",
                    "example_prompt": "/fly score Acme Corp",
                }

    # Priority 2: Positioning strong + social post skill available
    if positioning_content and positioning_content.strip():
        social_names = ["social-post-crafter", "social-media-manager"]
        for social_name in social_names:
            if social_name in available_names:
                return {
                    "skill_name": social_name,
                    "alias": social_name,
                    "reason": "Your positioning is set up. Create a social post based on your company story.",
                    "example_prompt": f"/fly {social_name}",
                }

    # Default: meeting-prep (universally useful)
    return {
        "skill_name": "meeting-prep",
        "alias": "prep",
        "reason": "Meeting prep is a great starting point. Just provide a company name.",
        "example_prompt": "/fly prep Acme Corp",
    }


# ---------------------------------------------------------------------------
# Slack Block Kit formatting
# ---------------------------------------------------------------------------

MAX_SLACK_TEXT = 3000  # Slack block text limit


def format_result_blocks(result: ExecutionResult) -> list:
    """Format an ExecutionResult as Slack Block Kit blocks.

    Args:
        result: ExecutionResult from execution_gateway.

    Returns:
        List of Slack Block Kit block dicts.
    """
    # Status emoji
    if result.mode == "error":
        emoji = ":x:"
        status = "Error"
    else:
        emoji = ":white_check_mark:"
        status = "Complete"

    blocks = []

    # Header block
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"{emoji} {result.skill_name} - {status}",
            "emoji": True,
        },
    })

    # Result text (truncated if needed)
    output_text = result.output or "(no output)"
    truncated = False
    if len(output_text) > MAX_SLACK_TEXT:
        output_text = output_text[:MAX_SLACK_TEXT] + "\n\n... (truncated)"
        truncated = True

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": output_text,
        },
    })

    # Context block: mode, duration, tokens
    context_elements = [
        {
            "type": "mrkdwn",
            "text": f"*Mode:* {result.mode}",
        },
        {
            "type": "mrkdwn",
            "text": f"*Duration:* {result.duration_ms}ms",
        },
    ]

    if result.token_usage:
        input_tokens = result.token_usage.get("input_tokens", 0)
        output_tokens = result.token_usage.get("output_tokens", 0)
        context_elements.append({
            "type": "mrkdwn",
            "text": f"*Tokens:* {input_tokens} in / {output_tokens} out",
        })

    blocks.append({
        "type": "context",
        "elements": context_elements,
    })

    # Attribution card (context store sources used)
    if result.context_attribution:
        attribution_blocks = retention.format_attribution_blocks(
            result.context_attribution
        )
        blocks.extend(attribution_blocks)

    # Contract violations warning
    if result.contract_violations:
        violations_text = "\n".join(
            f"- {v}" for v in result.contract_violations
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":warning: *Contract Violations:*\n{violations_text}",
            },
        })

    return blocks


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

def _build_help_blocks() -> list:
    """Build help text blocks listing available skills dynamically.

    Reads installed skills from filesystem via list_available_skills()
    and includes SKILL_ALIASES as convenience shortcuts.
    """
    blocks = []

    # Shortcut aliases section
    lines = ["*Quick commands (shortcuts):*\n"]
    for alias, skill_name in SKILL_ALIASES.items():
        lines.append(f"- `/fly {alias} [args]` -- `{skill_name}`")

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "\n".join(lines),
        },
    })

    # Dynamic skill listing from filesystem
    skills = list_available_skills()
    if skills:
        skill_lines = ["\n*All installed skills:*\n"]
        for skill in skills:
            desc = skill["description"] or "(no description)"
            skill_lines.append(f"- *{skill['name']}* -- {desc}")
        skill_lines.append(
            "\n_Use `/fly skills` for the full list. "
            "Your preferences are saved automatically._"
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(skill_lines),
            },
        })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No skills installed yet. Run `/fly start` to get started._",
            },
        })

    return blocks


# ---------------------------------------------------------------------------
# Command parsing
# ---------------------------------------------------------------------------

def parse_command_text(text: str) -> tuple:
    """Parse /fly command text into skill alias and args.

    Supports:
    - "/fly prep Acme" -> ("prep", {"company_name": "Acme"})
    - "/fly prep --company Acme --contact John" -> ("prep", {"company": "Acme", "contact": "John"})
    - "/fly help" -> ("help", {})
    - "/fly" -> ("help", {})

    Args:
        text: Raw command text after /fly.

    Returns:
        Tuple of (subcommand, params_dict).
    """
    text = text.strip()
    if not text:
        return ("recommend", {})

    parts = text.split()
    subcommand = parts[0].lower()

    if subcommand == "help":
        return ("help", {})

    # Recognized subcommands that don't resolve to skill aliases
    if subcommand in ("skills", "start", "connect", "login", "settings", "cost"):
        return (subcommand, {})

    # Parse remaining args
    args = parts[1:]
    params = {}

    if not args:
        return (subcommand, params)

    # Check for --key value pattern
    i = 0
    positional_args = []
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            key = args[i][2:]  # strip --
            params[key] = args[i + 1]
            i += 2
        else:
            positional_args.append(args[i])
            i += 1

    # If positional args remain, join as input_text
    if positional_args:
        params["input_text"] = " ".join(positional_args)
        # Also set common parameter names for convenience
        if len(positional_args) == 1:
            params["company_name"] = positional_args[0]
            params["contact_name"] = positional_args[0]

    return (subcommand, params)


# ---------------------------------------------------------------------------
# DM onboarding
# ---------------------------------------------------------------------------

async def send_onboarding_dm(client, user_id: str):
    """Send a welcome DM to a new user with example commands.

    Args:
        client: Slack WebClient instance.
        user_id: Slack user ID.
    """
    try:
        dm_response = await client.conversations_open(users=user_id)
        channel_id = dm_response["channel"]["id"]

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Hey! :wave: I'm the Flywheel bot. "
                        "I can help you with:\n\n"
                        "- `/fly prep [company]` -- meeting briefing\n"
                        "- `/fly score [company]` -- company fit scoring\n"
                        "- `/fly pipeline` -- pipeline update\n\n"
                        "Try one now! Your preferences are saved automatically."
                    ),
                },
            }
        ]

        await client.chat_postMessage(
            channel=channel_id,
            text="Welcome to Flywheel!",
            blocks=blocks,
        )
    except Exception as e:
        logger.error("Failed to send onboarding DM to %s: %s", user_id, e)


# ---------------------------------------------------------------------------
# Guided mode helpers
# ---------------------------------------------------------------------------

def _get_session_key(user_id: str, channel_id: str) -> tuple:
    """Get the guided session key for a user+channel pair."""
    return (user_id, channel_id)


async def _start_guided_session(
    client, user_id: str, channel_id: str,
    skill_name: str, resolved: dict, missing: list
):
    """Start a guided mode session, asking the first missing parameter.

    Args:
        client: Slack WebClient.
        user_id: Slack user ID.
        channel_id: Channel to send questions in (DM).
        skill_name: Skill being executed.
        resolved: Already resolved parameters.
        missing: List of missing parameter dicts.
    """
    session_key = _get_session_key(user_id, channel_id)
    GUIDED_SESSIONS[session_key] = {
        "skill_name": skill_name,
        "resolved": resolved,
        "missing": missing,
        "current_question_idx": 0,
    }

    # Ask the first question
    first_param = missing[0]
    prompt_text = first_param.get("prompt", f"Please provide {first_param['name']}")
    default = first_param.get("default", "")
    if default:
        prompt_text += f"\n_(Last used: {default})_"

    await client.chat_postMessage(
        channel=channel_id,
        text=prompt_text,
    )


async def _handle_guided_answer(client, user_id: str, channel_id: str, answer: str):
    """Process a guided mode answer and advance or execute.

    Args:
        client: Slack WebClient.
        user_id: Slack user ID.
        channel_id: Channel ID.
        answer: User's answer text.
    """
    session_key = _get_session_key(user_id, channel_id)
    session = GUIDED_SESSIONS.get(session_key)
    if not session:
        return

    # Record the answer
    idx = session["current_question_idx"]
    param_info = session["missing"][idx]
    session["resolved"][param_info["name"]] = answer

    # Move to next question
    session["current_question_idx"] = idx + 1

    if session["current_question_idx"] < len(session["missing"]):
        # More questions to ask
        next_param = session["missing"][session["current_question_idx"]]
        prompt_text = next_param.get("prompt", f"Please provide {next_param['name']}")
        default = next_param.get("default", "")
        if default:
            prompt_text += f"\n_(Last used: {default})_"

        await client.chat_postMessage(
            channel=channel_id,
            text=prompt_text,
        )
    else:
        # All answers collected -- execute the skill
        skill_name = session["skill_name"]
        resolved = session["resolved"]

        # Save preferences for next time
        try:
            save_preferences_batch(user_id, skill_name, resolved)
        except Exception as e:
            logger.error("Failed to save preferences: %s", e)

        # Clean up session
        del GUIDED_SESSIONS[session_key]

        # Execute skill
        await client.chat_postMessage(
            channel=channel_id,
            text=f"Got it! Running `{skill_name}`...",
        )

        input_text = resolved.get("input_text", "")
        try:
            result = await asyncio.to_thread(
                execute_skill, skill_name, input_text, user_id, resolved
            )
            blocks = format_result_blocks(result)
            await client.chat_postMessage(
                channel=channel_id,
                text=result.output[:200] if result.output else "Done",
                blocks=blocks,
            )
        except Exception as e:
            await client.chat_postMessage(
                channel=channel_id,
                text=f"Something went wrong: {e}. Try again or use `/fly help`.",
            )


# ---------------------------------------------------------------------------
# Skills list and recommendation blocks
# ---------------------------------------------------------------------------


def _build_skills_list_blocks() -> list:
    """Build Block Kit blocks listing all installed skills with descriptions."""
    skills = list_available_skills()
    if not skills:
        return [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No skills installed yet. Run `/fly start` to get started._",
            },
        }]

    blocks = [{
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Installed Skills",
            "emoji": True,
        },
    }]

    for skill in skills:
        desc = skill["description"] or "(no description)"
        dir_name = skill["dir_name"]
        # Check if there's a shortcut alias for this skill
        alias_hint = ""
        for alias, skill_name in SKILL_ALIASES.items():
            if skill_name == dir_name:
                alias_hint = f"  (shortcut: `/fly {alias}`)"
                break

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{skill['name']}*{alias_hint}\n{desc}\n`/fly {dir_name} [args]`",
            },
        })

    return blocks


def _build_recommendation_blocks() -> list:
    """Build Block Kit blocks showing smart skill recommendation.

    This is the primary CTA when user types /fly with no args.
    Plan 04 will compose a contextual suggestion before this block.
    """
    rec = recommend_skill()

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Try this:* `{rec['example_prompt']}`\n"
                    f"{rec['reason']}"
                ),
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "Type `/fly skills` to see all available skills, "
                        "or `/fly help` for shortcuts."
                    ),
                }
            ],
        },
    ]

    return blocks


# ---------------------------------------------------------------------------
# Onboarding flow (/fly start)
# ---------------------------------------------------------------------------


async def _handle_start_onboarding(client, user_id: str, respond):
    """Handle /fly start -- initiate the onboarding flow.

    If user already has onboarding data, shows existing profile.
    Otherwise opens a DM and asks for company URL.

    Args:
        client: Slack WebClient.
        user_id: Slack user ID.
        respond: Slack respond function for ephemeral messages.
    """
    # Check if already onboarded
    try:
        positioning = context_utils.read_context("positioning.md", agent_id="onboarding")
        if positioning and positioning.strip():
            # Existing user -- show profile and offer update
            await respond(
                text=(
                    "You already have a company profile set up. "
                    "Your profile data is in the context store.\n\n"
                    "To update it, just run `/fly start` again after clearing your profile, "
                    "or use `/fly` to see what you can do next."
                )
            )
            return
    except Exception:
        pass

    # New user -- open DM for onboarding
    try:
        dm_response = await client.conversations_open(users=user_id)
        dm_channel = dm_response["channel"]["id"]

        ONBOARDING_SESSIONS[user_id] = {
            "state": "awaiting_url",
            "channel_id": dm_channel,
        }

        await respond(
            text="Let's get started! Check your DMs for the next step."
        )

        await client.chat_postMessage(
            channel=dm_channel,
            text=(
                "Welcome to Flywheel! Let's set up your company profile.\n\n"
                "Please paste your company website URL (e.g. https://example.com) "
                "and I'll pull in your company info automatically."
            ),
        )
    except Exception as e:
        logger.error("Failed to start onboarding for %s: %s", user_id, e)
        await respond(text=f"Something went wrong starting onboarding: {e}")


async def _handle_onboarding_message(client, user_id: str, channel_id: str, text: str):
    """Handle a DM message during onboarding flow.

    Routes to the appropriate handler based on the current onboarding state.

    Args:
        client: Slack WebClient.
        user_id: Slack user ID.
        channel_id: Channel ID (DM).
        text: User's message text.
    """
    session = ONBOARDING_SESSIONS.get(user_id)
    if not session:
        return

    state = session.get("state", "")

    if state == "awaiting_url":
        await _onboarding_handle_url(client, user_id, channel_id, text)
    elif state == "confirming_profile":
        await _onboarding_handle_confirmation(client, user_id, channel_id, text)
    elif state == "tier2_upload":
        # File upload handled by file_shared event (Task 2b)
        # Text messages in this state offer Tier 3 fallback
        lower = text.strip().lower()
        if lower in ("questions", "q", "ask me", "tier 3", "manual"):
            await _onboarding_start_guided(client, user_id, channel_id)
        else:
            await client.chat_postMessage(
                channel=channel_id,
                text=(
                    "Upload a company document (PDF, Word, or text file), "
                    "or type *questions* to answer a few quick questions instead."
                ),
            )
    elif state == "tier3_questions":
        await _onboarding_handle_guided_answer(client, user_id, channel_id, text)


async def _onboarding_handle_url(client, user_id: str, channel_id: str, text: str):
    """Handle URL input during onboarding (awaiting_url state).

    Attempts to crawl the URL. On success, shows profile for confirmation.
    On failure, offers Tier 2 (doc upload) or Tier 3 (guided questions).
    """
    url = text.strip()

    # Basic URL validation
    if not url.startswith("http://") and not url.startswith("https://"):
        if "." in url:
            url = "https://" + url
        else:
            await client.chat_postMessage(
                channel=channel_id,
                text="That doesn't look like a URL. Please paste your company website URL (e.g. https://example.com).",
            )
            return

    # Update state to crawling
    ONBOARDING_SESSIONS[user_id]["state"] = "crawling"

    await client.chat_postMessage(
        channel=channel_id,
        text=f"Crawling {url}... this may take a moment.",
    )

    try:
        crawl_result = await asyncio.to_thread(
            lambda: asyncio.run(company_intel.crawl_company(url))
        )

        if crawl_result.get("success") and crawl_result.get("raw_pages"):
            # Combine crawled pages into raw text
            raw_text = "\n\n".join(crawl_result["raw_pages"].values())

            # Structure the intelligence
            intelligence = await asyncio.to_thread(
                company_intel.structure_intelligence, raw_text, "website-crawl"
            )

            ONBOARDING_SESSIONS[user_id]["state"] = "confirming_profile"
            ONBOARDING_SESSIONS[user_id]["intelligence"] = intelligence

            # Show profile summary
            profile_text = _format_intelligence_summary(intelligence)
            await client.chat_postMessage(
                channel=channel_id,
                text=(
                    f"Here's what I found:\n\n{profile_text}\n\n"
                    "Does this look right? (yes/no)"
                ),
            )
        else:
            # Crawl failed -- offer fallbacks
            ONBOARDING_SESSIONS[user_id]["state"] = "tier2_upload"
            await client.chat_postMessage(
                channel=channel_id,
                text=(
                    "I couldn't pull info from that URL. No worries, you have two options:\n\n"
                    "1. *Upload a document* -- drop a pitch deck, about page, or company doc (PDF, Word, or text)\n"
                    "2. *Type 'questions'* -- I'll ask a few quick questions instead"
                ),
            )
    except Exception as e:
        logger.error("Crawl failed for %s: %s", url, e)
        ONBOARDING_SESSIONS[user_id]["state"] = "tier2_upload"
        await client.chat_postMessage(
            channel=channel_id,
            text=(
                "Something went wrong with the crawl. No worries, you have two options:\n\n"
                "1. *Upload a document* -- drop a pitch deck, about page, or company doc\n"
                "2. *Type 'questions'* -- I'll ask a few quick questions instead"
            ),
        )


async def _onboarding_handle_confirmation(
    client, user_id: str, channel_id: str, text: str
):
    """Handle profile confirmation (confirming_profile state).

    On confirmation: writes to context store, marks onboarding complete,
    shows smart recommendation.
    """
    lower = text.strip().lower()

    if lower in ("yes", "y", "looks good", "correct", "right", "yep", "yeah"):
        session = ONBOARDING_SESSIONS[user_id]
        intelligence = session.get("intelligence", {})

        # Write to context store
        try:
            await asyncio.to_thread(
                company_intel.write_company_intelligence, intelligence
            )
        except Exception as e:
            logger.error("Failed to write intelligence: %s", e)

        # Mark onboarding complete in user memory
        try:
            save_user_preference(user_id, "_onboarding", "complete", "true")
        except Exception as e:
            logger.error("Failed to save onboarding state: %s", e)

        # Clean up session
        del ONBOARDING_SESSIONS[user_id]

        # Show smart recommendation
        rec = recommend_skill()
        await client.chat_postMessage(
            channel=channel_id,
            text=(
                "Your company profile is saved!\n\n"
                f"*Try this next:* `{rec['example_prompt']}`\n"
                f"{rec['reason']}\n\n"
                "Type `/fly skills` to see everything available."
            ),
        )
    elif lower in ("no", "n", "wrong", "nope"):
        await client.chat_postMessage(
            channel=channel_id,
            text=(
                "No problem. You can:\n"
                "1. Type corrections and I'll update the profile\n"
                "2. Upload a document with better info\n"
                "3. Type 'questions' to answer manually\n\n"
                "Or just run `/fly start` again anytime."
            ),
        )
        # Keep in confirming_profile state for corrections
    else:
        # Treat as corrections -- re-structure
        await client.chat_postMessage(
            channel=channel_id,
            text="Got it, let me re-process with your corrections...",
        )
        session = ONBOARDING_SESSIONS[user_id]
        old_intel = session.get("intelligence", {})
        correction_text = text
        if old_intel.get("raw_text"):
            correction_text = old_intel["raw_text"] + "\n\nCorrections: " + text

        try:
            intelligence = await asyncio.to_thread(
                company_intel.structure_intelligence, correction_text, "user-correction"
            )
            ONBOARDING_SESSIONS[user_id]["intelligence"] = intelligence
            profile_text = _format_intelligence_summary(intelligence)
            await client.chat_postMessage(
                channel=channel_id,
                text=f"Updated profile:\n\n{profile_text}\n\nDoes this look right? (yes/no)",
            )
        except Exception as e:
            logger.error("Re-structuring failed: %s", e)
            await client.chat_postMessage(
                channel=channel_id,
                text="Hmm, I had trouble processing that. Type 'yes' to save what we have, or 'questions' to start fresh.",
            )


async def _onboarding_start_guided(client, user_id: str, channel_id: str):
    """Start Tier 3 guided questions for onboarding."""
    questions = company_intel.build_guided_questions()
    ONBOARDING_SESSIONS[user_id]["state"] = "tier3_questions"
    ONBOARDING_SESSIONS[user_id]["questions"] = questions
    ONBOARDING_SESSIONS[user_id]["answers"] = {}
    ONBOARDING_SESSIONS[user_id]["current_question_idx"] = 0

    first_q = questions[0]
    await client.chat_postMessage(
        channel=channel_id,
        text=f"Great, let's do this! Question 1/{len(questions)}:\n\n{first_q['question']}",
    )


async def _onboarding_handle_guided_answer(
    client, user_id: str, channel_id: str, text: str
):
    """Handle a guided question answer during Tier 3 onboarding."""
    session = ONBOARDING_SESSIONS[user_id]
    questions = session["questions"]
    idx = session["current_question_idx"]

    # Record answer
    q = questions[idx]
    session["answers"][q["context_key"]] = text.strip()
    session["current_question_idx"] = idx + 1

    if session["current_question_idx"] < len(questions):
        # Ask next question
        next_q = questions[session["current_question_idx"]]
        next_idx = session["current_question_idx"] + 1
        await client.chat_postMessage(
            channel=channel_id,
            text=f"Question {next_idx}/{len(questions)}:\n\n{next_q['question']}",
        )
    else:
        # All answers collected -- structure and confirm
        answers = session["answers"]
        intelligence = company_intel.structure_from_answers(answers)

        ONBOARDING_SESSIONS[user_id]["state"] = "confirming_profile"
        ONBOARDING_SESSIONS[user_id]["intelligence"] = intelligence

        profile_text = _format_intelligence_summary(intelligence)
        await client.chat_postMessage(
            channel=channel_id,
            text=f"Here's your profile:\n\n{profile_text}\n\nDoes this look right? (yes/no)",
        )


def _format_intelligence_summary(intelligence: dict) -> str:
    """Format intelligence dict as a readable summary for Slack.

    Args:
        intelligence: Dict with company intelligence fields.

    Returns:
        Formatted string summary.
    """
    if intelligence.get("structured") is False:
        raw = intelligence.get("raw_text", "")
        return f"(Raw text, could not structure):\n{raw[:500]}"

    lines = []
    if intelligence.get("company_name"):
        lines.append(f"*Company:* {intelligence['company_name']}")
    if intelligence.get("tagline"):
        lines.append(f"*Tagline:* {intelligence['tagline']}")
    if intelligence.get("what_they_do"):
        lines.append(f"*What they do:* {intelligence['what_they_do']}")
    if intelligence.get("products"):
        products = intelligence["products"]
        if isinstance(products, list):
            lines.append(f"*Products:* {', '.join(str(p) for p in products)}")
        else:
            lines.append(f"*Products:* {products}")
    if intelligence.get("target_customers"):
        targets = intelligence["target_customers"]
        if isinstance(targets, list):
            lines.append(f"*Target customers:* {', '.join(str(t) for t in targets)}")
        else:
            lines.append(f"*Target customers:* {targets}")
    if intelligence.get("industries"):
        industries = intelligence["industries"]
        if isinstance(industries, list):
            lines.append(f"*Industries:* {', '.join(str(i) for i in industries)}")
    if intelligence.get("competitors"):
        competitors = intelligence["competitors"]
        if isinstance(competitors, list):
            lines.append(f"*Competitors:* {', '.join(str(c) for c in competitors)}")
    if intelligence.get("pricing_model"):
        lines.append(f"*Pricing:* {intelligence['pricing_model']}")
    if intelligence.get("key_differentiators"):
        diffs = intelligence["key_differentiators"]
        if isinstance(diffs, list):
            lines.append(f"*Differentiators:* {', '.join(str(d) for d in diffs)}")

    return "\n".join(lines) if lines else "(no structured data)"


# ---------------------------------------------------------------------------
# Integration settings and cost blocks
# ---------------------------------------------------------------------------


def _build_integration_settings_blocks(user_id: str) -> list:
    """Build Slack blocks showing integration settings with toggle buttons.

    Shows each integration with its current enabled/disabled state and
    a toggle button to change it.

    Args:
        user_id: Slack user ID.

    Returns:
        List of Slack Block Kit blocks.
    """
    if _integration_framework is None:
        return [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Integration framework not available.",
            },
        }]

    settings = _integration_framework.get_integration_settings(user_id)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Integration Settings",
            },
        },
    ]

    for key, info in settings.items():
        status = ":white_check_mark: Enabled" if info.get("enabled") else ":no_entry_sign: Disabled"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{info.get('name', key)}*\n"
                    f"{info.get('description', '')}\n"
                    f"Scope: {info.get('scope', 'N/A')} | Est. cost: {info.get('est_cost', 'N/A')}\n"
                    f"Status: {status}"
                ),
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Disable" if info.get("enabled") else "Enable",
                },
                "action_id": f"toggle_integration_{key}",
                "style": "danger" if info.get("enabled") else "primary",
            },
        })

    # Nudge type toggles
    if _nudge_engine is not None:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Nudge Preferences*\n"
                    "Control which types of proactive nudges you receive.\n"
                    "Use `/fly settings` after toggling to see updated state."
                ),
            },
        })

    return blocks


def _build_cost_blocks(user_id: str) -> list:
    """Build Slack blocks showing cost summary for the user.

    Args:
        user_id: Slack user ID.

    Returns:
        List of Slack Block Kit blocks.
    """
    if _integration_framework is None:
        return [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Integration framework not available.",
            },
        }]

    summary = _integration_framework.get_cost_summary(user_id)

    # Build per-integration breakdown lines
    breakdown_lines = []
    for integ, count in summary.get("by_integration", {}).items():
        breakdown_lines.append(f"  - {integ}: {count} triggers")

    breakdown_text = "\n".join(breakdown_lines) if breakdown_lines else "  (no triggers today)"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Cost Dashboard",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Today's auto-triggers:* {summary.get('today_triggers', 0)} / "
                    f"{summary.get('daily_cap', 0)}\n"
                    f"*Estimated cost:* ${summary.get('today_cost_estimate', 0):.4f}\n"
                    f"*Remaining triggers:* {summary.get('remaining_triggers', 0)}\n\n"
                    f"*Per-integration breakdown:*\n{breakdown_text}"
                ),
            },
        },
    ]

    return blocks


async def _handle_connect(user_id: str, text: str, respond):
    """Handle /fly connect {service} command.

    Runs OAuth flow for calendar or email. For meeting notes,
    shows instructions for configuring watch path.

    Args:
        user_id: Slack user ID.
        text: Full command text (e.g., "connect calendar").
        respond: Slack respond function.
    """
    parts = text.strip().split()
    service = parts[1].lower() if len(parts) > 1 else ""

    if service == "calendar":
        if _watcher_calendar is None:
            await respond(text="Calendar integration module not available.")
            return
        try:
            success = await asyncio.to_thread(_watcher_calendar.connect_calendar, user_id)
            if success:
                await respond(
                    text=":white_check_mark: Google Calendar connected! "
                    "Your upcoming external meetings will auto-trigger meeting prep."
                )
            else:
                await respond(text="Calendar connection failed. Check logs for details.")
        except FileNotFoundError as e:
            await respond(text=f"Setup needed: {e}")
        except Exception as e:
            await respond(text=f"Calendar connection error: {e}")

    elif service == "email":
        if _watcher_email is None:
            await respond(text="Email integration module not available.")
            return
        try:
            success = await asyncio.to_thread(_watcher_email.connect_email, user_id)
            if success:
                await respond(
                    text=":white_check_mark: Gmail connected! "
                    "Replies to your outreach emails will be tracked automatically."
                )
            else:
                await respond(text="Email connection failed. Check logs for details.")
        except Exception as e:
            await respond(text=f"Email connection error: {e}")

    elif service == "meetings":
        # Meeting notes uses local file watching, no OAuth needed
        path_hint = ""
        if len(parts) > 3 and parts[2] == "--path":
            path_hint = parts[3]
        if path_hint:
            await respond(
                text=f":white_check_mark: Meeting notes will be watched at: {path_hint}\n"
                "Enable the integration with `/fly settings` to start auto-processing."
            )
        else:
            await respond(
                text=(
                    "Meeting notes integration watches your Granola/Fathom export directory.\n"
                    "Default paths: ~/Documents/Granola, ~/Library/Application Support/Granola\n\n"
                    "To use a custom path: `/fly connect meetings --path /your/path`\n"
                    "Enable it with `/fly settings`."
                )
            )
    else:
        await respond(
            text=(
                "Usage: `/fly connect {service}`\n"
                "Services: `calendar`, `email`, `meetings`"
            )
        )


async def _handle_login(user_id: str, text: str, respond):
    """Handle /fly login {service} command.

    Launches headed browser for LinkedIn/other login via browser_sessions.

    Args:
        user_id: Slack user ID.
        text: Full command text (e.g., "login linkedin").
        respond: Slack respond function.
    """
    parts = text.strip().split()
    service = parts[1].lower() if len(parts) > 1 else ""

    if not service:
        services = list(_browser_sessions.SERVICE_URLS.keys()) if _browser_sessions else ["linkedin", "google", "github"]
        await respond(
            text=f"Usage: `/fly login {{service}}`\nServices: {', '.join(services)}"
        )
        return

    if _browser_sessions is None:
        await respond(text="Browser sessions module not available. Install Playwright.")
        return

    if service not in _browser_sessions.SERVICE_URLS:
        await respond(
            text=f"Unknown service: {service}. Available: {', '.join(_browser_sessions.SERVICE_URLS.keys())}"
        )
        return

    await respond(
        text=(
            f"Opening a browser window for {service} login. "
            "Please log in, then return here. The window will close automatically."
        )
    )

    try:
        success = await _browser_sessions.login_session(user_id, service)
        if success:
            await respond(text=f":white_check_mark: {service.title()} session saved!")
        else:
            await respond(
                text=f"Login timed out or failed for {service}. Try again with `/fly login {service}`."
            )
    except Exception as e:
        await respond(text=f"Login error: {e}")


# ---------------------------------------------------------------------------
# /fly command handler
# ---------------------------------------------------------------------------

if app is not None:
    @app.command("/fly")
    async def handle_fly(ack, command, respond, client):
        """Handle /fly slash command.

        For fast responses (help, skills, recommend): ack with the answer.
        For slow operations (skill execution): ack with "Processing...",
        then use respond() or DM to deliver results.
        """
        user_id = command.get("user_id", "")
        channel_id = command.get("channel_id", "")
        text = command.get("text", "")

        # Parse command BEFORE ack so we can respond appropriately
        subcommand, provided_params = parse_command_text(text)
        logger.info("Command from %s: subcommand=%s", user_id, subcommand)

        # --- Fast responses: answer directly in ack ---

        if subcommand == "help":
            try:
                blocks = _build_help_blocks()
                await ack(blocks=blocks)
            except Exception as e:
                logger.error("Help failed: %s", e, exc_info=True)
                await ack(text=f"Help error: {e}")
            return

        if subcommand == "skills":
            try:
                blocks = _build_skills_list_blocks()
                await ack(blocks=blocks)
            except Exception as e:
                logger.error("Skills list failed: %s", e, exc_info=True)
                await ack(text=f"Skills error: {e}")
            return

        if subcommand == "recommend":
            try:
                blocks = []
                suggestion = retention.get_contextual_suggestion()
                if suggestion:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":bulb: {suggestion}",
                        },
                    })
                blocks.extend(_build_recommendation_blocks())
                await ack(blocks=blocks)
            except Exception as e:
                logger.error("Recommend failed: %s", e, exc_info=True)
                await ack(text=f"Recommendation error: {e}")
            return

        if subcommand == "settings":
            try:
                blocks = _build_integration_settings_blocks(user_id)
                await ack(blocks=blocks)
            except Exception as e:
                logger.error("Settings failed: %s", e, exc_info=True)
                await ack(text=f"Settings error: {e}")
            return

        if subcommand == "cost":
            try:
                blocks = _build_cost_blocks(user_id)
                await ack(blocks=blocks)
            except Exception as e:
                logger.error("Cost failed: %s", e, exc_info=True)
                await ack(text=f"Cost error: {e}")
            return

        # --- Slow operations: ack first, then process ---

        await ack("Processing your request...")

        if subcommand == "start":
            await _handle_start_onboarding(client, user_id, respond)
            return

        if subcommand == "connect":
            await _handle_connect(user_id, text, respond)
            return

        if subcommand == "login":
            await _handle_login(user_id, text, respond)
            return

        # Resolve skill name from alias
        skill_name = SKILL_ALIASES.get(subcommand, subcommand)

        # Check if new user (fire-and-forget onboarding)
        try:
            is_new = ensure_user_initialized(user_id)
            if is_new:
                asyncio.create_task(send_onboarding_dm(client, user_id))
        except Exception as e:
            logger.error("User initialization failed: %s", e)

        # Convert skill to get parameter declarations
        try:
            spec = convert_skill(skill_name)
        except FileNotFoundError:
            available = ", ".join(sorted(SKILL_ALIASES.keys()))
            await respond(
                text=f"I don't know the skill '{skill_name}'. Available shortcuts: {available}\n\nType `/fly skills` for the full list."
            )
            return

        # Resolve parameters (Mode 1 vs Mode 2)
        resolved, missing = resolve_parameters(
            spec.parameters, provided_params, user_id, skill_name
        )

        if missing:
            # Mode 2: guided mode -- open DM and start asking
            try:
                dm_response = await client.conversations_open(users=user_id)
                dm_channel = dm_response["channel"]["id"]
                await respond(
                    text=f"I need a few more details for `{skill_name}`. Check your DMs!"
                )
                await _start_guided_session(
                    client, user_id, dm_channel, skill_name, resolved, missing
                )
            except Exception as e:
                logger.error("Failed to start guided mode: %s", e)
                await respond(
                    text=f"Something went wrong starting guided mode: {e}"
                )
            return

        # Mode 1: all params resolved -- execute skill
        input_text = provided_params.get("input_text", text)

        try:
            result = await asyncio.to_thread(
                execute_skill, skill_name, input_text, user_id, resolved
            )
            blocks = format_result_blocks(result)

            # Retention: increment run counter and check what's changed
            try:
                retention.increment_run_counter(user_id)
                whats_changed = retention.get_whats_changed(user_id)
                if whats_changed:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":chart_with_upwards_trend: *What's changed:* {whats_changed}",
                        },
                    })
            except Exception as e:
                logger.error("Retention tracking failed: %s", e)

            # Send result via respond (uses response_url, no channel membership needed)
            await respond(
                text=result.output[:200] if result.output else "Done",
                blocks=blocks,
            )
        except Exception as e:
            logger.error("Skill execution failed: %s", e, exc_info=True)
            await respond(
                text=f"Something went wrong: {e}. Try again or use `/fly help`."
            )

    # ---------------------------------------------------------------------------
    # DM message handler (for guided mode)
    # ---------------------------------------------------------------------------

    @app.event("message")
    async def handle_message(event, client):
        """Handle DM messages for guided mode/onboarding and channel messages for monitoring."""
        # Ignore bot messages
        if event.get("bot_id") or event.get("subtype"):
            return

        channel_type = event.get("channel_type", "")
        user_id = event.get("user", "")
        channel_id = event.get("channel", "")
        text = event.get("text", "")

        # --- DM messages: guided mode and onboarding ---
        if channel_type == "im":
            # Check onboarding sessions first (takes priority)
            if user_id in ONBOARDING_SESSIONS:
                await _handle_onboarding_message(client, user_id, channel_id, text)
                return

            # Check guided mode sessions
            session_key = _get_session_key(user_id, channel_id)
            if session_key in GUIDED_SESSIONS:
                await _handle_guided_answer(client, user_id, channel_id, text)
            return

        # --- Channel messages: Slack channel monitoring ---
        if channel_type in ("channel", "group") and _watcher_slack_channels is not None:
            try:
                result = await _watcher_slack_channels.handle_channel_message(event, user_id)
                if result and result.get("status") == "ok":
                    logger.info(
                        "Channel intelligence extracted from %s for user %s",
                        channel_id, user_id,
                    )
            except Exception as e:
                logger.error("Channel message handling failed: %s", e)

    # ---------------------------------------------------------------------------
    # File upload handler (Tier 2 onboarding)
    # ---------------------------------------------------------------------------

    @app.event("file_shared")
    async def handle_file_shared(event, client):
        """Handle file uploads for Tier 2 onboarding document processing.

        Only processes files from users with an active onboarding session
        in the tier2_upload state. All other file events are ignored.
        """
        user_id = event.get("user_id", "")

        # Only process if user has an active Tier 2 onboarding session
        session = ONBOARDING_SESSIONS.get(user_id)
        if not session or session.get("state") != "tier2_upload":
            return

        file_id = event.get("file_id", "")
        channel_id = session.get("channel_id", "")

        if not file_id or not channel_id:
            return

        try:
            # Get file info
            file_info_resp = await client.files_info(file=file_id)
            file_data = file_info_resp.get("file", {})
            mimetype = file_data.get("mimetype", "")
            size = file_data.get("size", 0)

            # Validate mimetype
            if mimetype not in company_intel.ACCEPTED_MIMETYPES:
                await client.chat_postMessage(
                    channel=channel_id,
                    text=(
                        "I can handle PDFs, Word docs, or text files up to 10MB. "
                        "That file type isn't supported. Try another file, "
                        "or type *questions* to answer manually."
                    ),
                )
                return

            # Validate size
            if size > company_intel.MAX_FILE_SIZE:
                await client.chat_postMessage(
                    channel=channel_id,
                    text=(
                        "That file is too large (max 10MB). "
                        "Try a smaller file or type *questions* to answer manually."
                    ),
                )
                return

            # Download file content
            url_private = file_data.get("url_private_download", "")
            if not url_private:
                url_private = file_data.get("url_private", "")

            token = os.environ.get("SLACK_BOT_TOKEN", "")
            if _httpx is None:
                logger.error("httpx not installed, cannot download file")
                return
            async with _httpx.AsyncClient() as http_client:
                resp = await http_client.get(
                    url_private,
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                content_bytes = resp.content

            await client.chat_postMessage(
                channel=channel_id,
                text="Processing your document...",
            )

            # Extract text from document
            extracted_text = await asyncio.to_thread(
                company_intel.extract_from_document, content_bytes, mimetype
            )

            # Structure the intelligence
            intelligence = await asyncio.to_thread(
                company_intel.structure_intelligence, extracted_text, "uploaded-doc"
            )

            ONBOARDING_SESSIONS[user_id]["state"] = "confirming_profile"
            ONBOARDING_SESSIONS[user_id]["intelligence"] = intelligence

            profile_text = _format_intelligence_summary(intelligence)
            await client.chat_postMessage(
                channel=channel_id,
                text=(
                    f"Here's what I found from your document:\n\n{profile_text}\n\n"
                    "Does this look right? (yes/no)"
                ),
            )

        except Exception as e:
            logger.error("File processing failed: %s", e)
            await client.chat_postMessage(
                channel=channel_id,
                text=(
                    "Something went wrong processing that file. "
                    "Try another file, or type *questions* to answer manually."
                ),
            )


    # ---------------------------------------------------------------------------
    # Integration toggle button handler
    # ---------------------------------------------------------------------------

    @app.action({"action_id": "toggle_integration_meeting_notes"})
    @app.action({"action_id": "toggle_integration_calendar"})
    @app.action({"action_id": "toggle_integration_email"})
    @app.action({"action_id": "toggle_integration_slack_channels"})
    async def handle_toggle_integration(ack, body, client):
        """Handle integration toggle button clicks.

        Extracts integration key from action_id, toggles the integration,
        and updates the message with new settings state.
        """
        await ack()

        if _integration_framework is None:
            return

        action = body.get("actions", [{}])[0]
        action_id = action.get("action_id", "")
        user_id = body.get("user", {}).get("id", "")
        channel_id = body.get("channel", {}).get("id", "")

        # Extract integration key from action_id: toggle_integration_{key}
        prefix = "toggle_integration_"
        if not action_id.startswith(prefix):
            return
        integration_key = action_id[len(prefix):]

        try:
            current = _integration_framework.is_integration_enabled(user_id, integration_key)
            _integration_framework.toggle_integration(user_id, integration_key, not current)

            # Update the message with new settings state
            new_blocks = _build_integration_settings_blocks(user_id)
            message_ts = body.get("message", {}).get("ts", "")
            if message_ts and channel_id:
                await client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    blocks=new_blocks,
                    text="Integration Settings",
                )
        except Exception as e:
            logger.error("Toggle integration failed: %s", e)

    # ---------------------------------------------------------------------------
    # Nudge feedback button handlers
    # ---------------------------------------------------------------------------

    @app.action({"action_id": re.compile(r"^nudge_helpful_")})
    async def handle_nudge_helpful(ack, body, client):
        """Handle 'Helpful' button click on a nudge message."""
        await ack()
        if _nudge_engine is None:
            return

        action = body.get("actions", [{}])[0]
        action_id = action.get("action_id", "")
        nudge_id = action_id.replace("nudge_helpful_", "")
        user_id = body.get("user", {}).get("id", "")
        channel_id = body.get("channel", {}).get("id", "")

        try:
            engine = _nudge_engine.NudgeEngine(user_id)
            engine.record_feedback(nudge_id, helpful=True)
            message_ts = body.get("message", {}).get("ts", "")
            if message_ts and channel_id:
                await client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    text=":thumbsup: Thanks for the feedback!",
                    blocks=[{
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":thumbsup: Thanks for the feedback! This helps improve future nudges.",
                        },
                    }],
                )
        except Exception as e:
            logger.error("Nudge helpful feedback failed: %s", e)

    @app.action({"action_id": re.compile(r"^nudge_unhelpful_")})
    async def handle_nudge_unhelpful(ack, body, client):
        """Handle 'Not helpful' button click on a nudge message."""
        await ack()
        if _nudge_engine is None:
            return

        action = body.get("actions", [{}])[0]
        action_id = action.get("action_id", "")
        nudge_id = action_id.replace("nudge_unhelpful_", "")
        user_id = body.get("user", {}).get("id", "")
        channel_id = body.get("channel", {}).get("id", "")

        try:
            engine = _nudge_engine.NudgeEngine(user_id)
            engine.record_feedback(nudge_id, helpful=False)
            # Check if any nudge type was auto-muted by the feedback
            nudge_type = None
            for s in engine.state.get("sent", []):
                if s.get("id") == nudge_id:
                    nudge_type = s.get("type")
                    break
            auto_muted = nudge_type in engine.state.get("disabled_types", []) if nudge_type else False
            msg = ":thumbsdown: Got it, noted."
            if auto_muted:
                msg += " This nudge type has been auto-muted due to low helpfulness."
            message_ts = body.get("message", {}).get("ts", "")
            if message_ts and channel_id:
                await client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    text=msg,
                    blocks=[{
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": msg},
                    }],
                )
        except Exception as e:
            logger.error("Nudge unhelpful feedback failed: %s", e)

    # ---------------------------------------------------------------------------
    # Email draft button handlers
    # ---------------------------------------------------------------------------

    @app.action({"action_id": re.compile(r"^email_approve_")})
    async def handle_email_approve(ack, body, client):
        """Handle 'Send' button click on an email draft."""
        await ack()
        if _email_sender is None:
            return

        action = body.get("actions", [{}])[0]
        action_id = action.get("action_id", "")
        draft_id = action_id.replace("email_approve_", "")
        channel_id = body.get("channel", {}).get("id", "")

        try:
            result = _email_sender.approve_draft(draft_id)
            if "error" in result:
                msg = f":x: Send failed: {result['error']}"
            else:
                msg = ":white_check_mark: Email sent successfully!"
            message_ts = body.get("message", {}).get("ts", "")
            if message_ts and channel_id:
                await client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    text=msg,
                    blocks=[{
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": msg},
                    }],
                )
        except KeyError:
            if channel_id:
                await client.chat_postMessage(
                    channel=channel_id,
                    text="Draft not found. It may have already been sent or cancelled.",
                )
        except Exception as e:
            logger.error("Email approve failed: %s", e)

    @app.action({"action_id": re.compile(r"^email_edit_")})
    async def handle_email_edit(ack, body, client):
        """Handle 'Edit' button click on an email draft -- transition to guided mode."""
        await ack()
        user_id = body.get("user", {}).get("id", "")
        channel_id = body.get("channel", {}).get("id", "")

        if channel_id:
            await client.chat_postMessage(
                channel=channel_id,
                text=(
                    "To edit this draft, reply with your changes and I'll update it.\n"
                    "Or use `/fly` to compose a new email."
                ),
            )

    @app.action({"action_id": re.compile(r"^email_cancel_")})
    async def handle_email_cancel(ack, body, client):
        """Handle 'Cancel' button click on an email draft."""
        await ack()
        if _email_sender is None:
            return

        action = body.get("actions", [{}])[0]
        action_id = action.get("action_id", "")
        draft_id = action_id.replace("email_cancel_", "")
        channel_id = body.get("channel", {}).get("id", "")

        try:
            _email_sender.cancel_draft(draft_id)
            msg = ":no_entry_sign: Draft cancelled."
            message_ts = body.get("message", {}).get("ts", "")
            if message_ts and channel_id:
                await client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    text=msg,
                    blocks=[{
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": msg},
                    }],
                )
        except KeyError:
            if channel_id:
                await client.chat_postMessage(
                    channel=channel_id,
                    text="Draft not found. It may have already been sent or cancelled.",
                )
        except Exception as e:
            logger.error("Email cancel failed: %s", e)

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main():
    """Start the Slack bot via Socket Mode."""
    if app is None:
        raise ImportError(
            "slack-bolt is required. Install with: pip3 install slack-bolt"
        )

    # Ensure skills directory is git-tracked for rollback
    init_skills_repo()

    # Start daily digest scheduler
    scheduler = retention.setup_scheduler(app.client)
    if scheduler is not None:
        scheduler.start()
        logger.info("Daily digest scheduler started (9 AM)")

    # ---------------------------------------------------------------------------
    # Integration watcher startup
    # ---------------------------------------------------------------------------
    integration_manager = None

    try:
        if _integration_framework is not None:
            integration_manager = _integration_framework.IntegrationManager()
            loop = asyncio.get_event_loop()

            # Provide Slack client to nudge engine for delivery
            if _nudge_engine is not None:
                _nudge_engine.set_slack_client(app.client)

            # Discover users from USERS_ROOT directory listing
            from user_memory import USERS_ROOT
            user_ids = []
            users_path = Path(USERS_ROOT)
            if users_path.is_dir():
                for entry in users_path.iterdir():
                    if entry.is_dir() and not entry.name.startswith("_"):
                        user_ids.append(entry.name)

            for uid in user_ids:
                # Register meeting notes file watcher (background thread)
                try:
                    if _watcher_meeting_notes is not None:
                        _watcher_meeting_notes.start_file_watcher(uid, loop)
                except Exception as e:
                    logger.warning("Meeting notes watcher failed for %s: %s", uid, e)

                # Register calendar watcher
                try:
                    if _watcher_calendar is not None:
                        _watcher_calendar.register_calendar_watcher(integration_manager, uid)
                except Exception as e:
                    logger.warning("Calendar watcher failed for %s: %s", uid, e)

                # Register email watcher (reply detection)
                try:
                    if _watcher_email is not None and _integration_framework.is_integration_enabled(uid, "email"):
                        from watcher_email import EmailWatcher, POLL_INTERVAL_MINUTES as EMAIL_POLL
                        email_watcher = EmailWatcher(uid)
                        integration_manager.register_watcher(email_watcher, interval_minutes=EMAIL_POLL)
                except Exception as e:
                    logger.warning("Email watcher failed for %s: %s", uid, e)

                # Register nudge evaluator (proactive intelligence)
                try:
                    if _nudge_engine is not None:
                        _nudge_engine.register_nudge_evaluator(integration_manager, uid)
                except Exception as e:
                    logger.warning("Nudge evaluator failed for %s: %s", uid, e)

            # Start the integration manager scheduler
            integration_manager.start()
            logger.info(
                "IntegrationManager started with %d registered watcher(s)",
                len(integration_manager._watchers),
            )
    except Exception as e:
        logger.warning("Integration watcher startup failed (non-fatal): %s", e)

    handler = AsyncSocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    logging.basicConfig(level=logging.INFO, force=True, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("Starting Flywheel Slack bot...")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
