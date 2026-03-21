"""Slack slash command routing and Block Kit response formatting.

Handles:
- /fly subcommand routing via SKILL_ALIASES mapping
- Block Kit formatted results (header, sections, context)
- Multi-tenant: resolves tenant from Slack team_id via Integration table
- Async delayed responses via Slack response_url (30-min validity)

Public API:
    SKILL_ALIASES: dict mapping shortcut names to skill names
    handle_slash_command(payload, db) -> dict
    format_result_blocks(skill_name, result) -> list[dict]
    format_help_blocks() -> list[dict]
    post_to_response_url(response_url, blocks, text) -> None
"""

from __future__ import annotations

import datetime
import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import Integration, SkillRun

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skill alias mapping (ported from v1 slack_bot.py SKILL_ALIASES)
# ---------------------------------------------------------------------------

SKILL_ALIASES: dict[str, str] = {
    "prep": "meeting-prep",
    "score": "gtm-company-fit-analyzer",
    "pipeline": "gtm-pipeline",
    "update": "investor-update",
    "process": "meeting-processor",
    "company": "gtm-my-company",
    "skills": "list-skills",
    "intel": "company-intel",
    "help": "help",
}

# Slack Block Kit text limit per section block
MAX_BLOCK_TEXT = 3000


# ---------------------------------------------------------------------------
# Tenant resolution from Slack team_id
# ---------------------------------------------------------------------------


async def _resolve_tenant(db: AsyncSession, team_id: str) -> tuple[UUID, UUID] | None:
    """Look up tenant_id and user_id from a Slack team_id.

    Queries the Integration table for a connected Slack integration whose
    settings contain the given team_id.

    Returns:
        Tuple of (tenant_id, user_id) or None if no matching integration.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.provider == "slack",
            Integration.status == "connected",
        )
    )
    integrations = result.scalars().all()

    for integration in integrations:
        if integration.settings and integration.settings.get("team_id") == team_id:
            return integration.tenant_id, integration.user_id

    return None


# ---------------------------------------------------------------------------
# Slash command handler
# ---------------------------------------------------------------------------


async def handle_slash_command(payload: dict, db: AsyncSession) -> dict:
    """Route a /fly slash command to the appropriate handler.

    Parses the command text to extract subcommand and arguments, then:
    - help / empty: returns help Block Kit message
    - skills: returns list of available skill aliases
    - recognized alias: queues a skill run and returns immediate ACK
    - unknown: returns error message

    Args:
        payload: Form-encoded Slack command payload with keys:
            command, text, team_id, user_id, response_url, channel_id.
        db: Async database session.

    Returns:
        Slack-compatible response dict (ephemeral or in_channel).
    """
    text = (payload.get("text") or "").strip()
    team_id = payload.get("team_id", "")
    response_url = payload.get("response_url", "")

    # Parse subcommand and arguments
    parts = text.split(None, 1)
    subcommand = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    # Help or empty
    if not subcommand or subcommand == "help":
        return {
            "response_type": "ephemeral",
            "blocks": format_help_blocks(),
            "text": "Flywheel commands help",
        }

    # Skills listing
    if subcommand == "skills":
        return _format_skills_response()

    # Check if subcommand maps to a skill
    skill_name = SKILL_ALIASES.get(subcommand, subcommand)

    # Resolve tenant from team_id
    tenant_info = await _resolve_tenant(db, team_id)
    if tenant_info is None:
        return {
            "response_type": "ephemeral",
            "text": "Workspace not connected. Please install Flywheel via /settings.",
        }

    tenant_id, user_id = tenant_info

    # Queue a skill run
    run = SkillRun(
        tenant_id=tenant_id,
        user_id=user_id,
        skill_name=skill_name,
        input_text=args or None,
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    run_id = run.id
    logger.info(
        "Queued skill run %s (skill=%s, tenant=%s, team=%s)",
        run_id, skill_name, tenant_id, team_id,
    )

    # Fire-and-forget: post full result when ready via response_url
    # In production this would be handled by the job queue worker callback.
    # For now, we store the response_url in the run's input so the worker
    # can POST back when complete.
    if response_url:
        # Store response_url in the run for the worker to use
        run.input_text = f"{args}\n---response_url:{response_url}" if args else f"---response_url:{response_url}"
        await db.commit()

    return {
        "response_type": "ephemeral",
        "text": f"Running {skill_name}... I'll post results when ready.",
    }


# ---------------------------------------------------------------------------
# Block Kit formatting
# ---------------------------------------------------------------------------


def format_result_blocks(skill_name: str, result: dict) -> list[dict]:
    """Format a skill execution result as Slack Block Kit blocks.

    Ported from v1's format_result_blocks. Creates:
    - Header block with skill name and status
    - Section block(s) with result content (respects 3000 char limit)
    - Context block with timestamp and attribution

    Args:
        skill_name: Name of the skill that produced the result.
        result: Dict with at minimum a 'summary' or 'output' key.
            May also have 'status', 'sections' (list of dicts with
            'title' and 'text').

    Returns:
        List of Slack Block Kit block dicts.
    """
    status = result.get("status", "complete")
    is_error = status == "error"
    emoji = ":x:" if is_error else ":white_check_mark:"
    status_label = "Error" if is_error else "Complete"

    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"{emoji} {skill_name} - {status_label}",
            "emoji": True,
        },
    })

    # Main content
    output_text = result.get("summary") or result.get("output") or "(no output)"
    if len(output_text) > MAX_BLOCK_TEXT:
        output_text = output_text[:MAX_BLOCK_TEXT] + "\n\n... (truncated)"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": output_text,
        },
    })

    # Additional sections (if result has structured sections)
    for section in result.get("sections", []):
        section_text = section.get("text", "")
        title = section.get("title", "")
        combined = f"*{title}*\n{section_text}" if title else section_text
        if len(combined) > MAX_BLOCK_TEXT:
            combined = combined[:MAX_BLOCK_TEXT] + "\n\n... (truncated)"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": combined,
            },
        })

    # Context block with timestamp and attribution
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"via Flywheel | {now}",
            },
        ],
    })

    return blocks


def format_help_blocks() -> list[dict]:
    """Build Block Kit help message listing all /fly subcommands.

    Returns:
        List of Slack Block Kit block dicts.
    """
    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Flywheel Commands",
            "emoji": True,
        },
    })

    # Quick commands
    lines = ["*Quick commands (shortcuts):*\n"]
    # Exclude meta-commands from alias listing
    for alias, skill_name in SKILL_ALIASES.items():
        if alias in ("help", "skills"):
            continue
        lines.append(f"  `/fly {alias}` -- {skill_name}")

    lines.append("\n*Meta commands:*")
    lines.append("  `/fly help` -- Show this help message")
    lines.append("  `/fly skills` -- List all available skills")
    lines.append("\n_You can also use full skill names: `/fly meeting-prep Acme Corp`_")

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "\n".join(lines),
        },
    })

    return blocks


def _format_skills_response() -> dict:
    """Format a skills listing response.

    Returns a simple list of available skill aliases. In production,
    this would query the database for tenant-specific skills.
    """
    lines = ["*Available skill shortcuts:*\n"]
    for alias, skill_name in SKILL_ALIASES.items():
        if alias in ("help", "skills"):
            continue
        lines.append(f"  `/fly {alias}` -- {skill_name}")

    lines.append("\n_Use the full skill name for any installed skill: `/fly skill-name [args]`_")

    return {
        "response_type": "ephemeral",
        "text": "\n".join(lines),
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(lines),
                },
            },
        ],
    }


# ---------------------------------------------------------------------------
# Response URL posting (delayed responses)
# ---------------------------------------------------------------------------


async def post_to_response_url(
    response_url: str,
    blocks: list[dict],
    text: str,
) -> None:
    """POST a delayed response to Slack's response_url.

    Slack response_urls are valid for 30 minutes after the original command.
    This is used to send the full skill result after the initial 3-second ACK.

    Args:
        response_url: Slack response URL from the original command payload.
        blocks: Block Kit blocks to include in the response.
        text: Fallback text for notifications and accessibility.
    """
    payload = {
        "response_type": "in_channel",
        "blocks": blocks,
        "text": text,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(response_url, json=payload)
            if resp.status_code != 200:
                logger.warning(
                    "Slack response_url POST returned %d: %s",
                    resp.status_code,
                    resp.text[:200],
                )
            else:
                logger.info("Posted delayed response to Slack response_url")
    except httpx.HTTPError as exc:
        logger.error("Failed to POST to Slack response_url: %s", exc)
