"""
retention.py - Retention and compounding-proof mechanisms for Flywheel.

Provides attribution rendering, daily digest, contextual suggestions,
and "what's changed" summaries. These features bring users back by
showing them the value of accumulated context.

Public API:
    format_attribution_blocks(attribution) -> list
    get_contextual_suggestion() -> Optional[str]
    get_whats_changed(user_id) -> Optional[str]
    increment_run_counter(user_id) -> int
    send_daily_digest(slack_client, users_root) -> None
    setup_scheduler(slack_client) -> scheduler or None
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Import from src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import context_utils
from event_advisor import check_staleness
from health_monitor import get_health_dashboard
from user_memory import (
    load_user_preferences,
    save_user_preference,
    USERS_ROOT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stale file -> skill suggestion mapping
# ---------------------------------------------------------------------------

_STALE_FILE_SUGGESTIONS = {
    "competitive-intel.md": {
        "action": "pipeline scan",
        "command": "/fly pipeline",
    },
    "contacts.md": {
        "action": "meeting processing",
        "command": "/fly process",
    },
    "positioning.md": {
        "action": "company profile refresh",
        "command": "/fly company",
    },
    "pain-points.md": {
        "action": "meeting processing",
        "command": "/fly process",
    },
    "icp-profiles.md": {
        "action": "company profile update",
        "command": "/fly company",
    },
}


# ---------------------------------------------------------------------------
# 1. Attribution blocks
# ---------------------------------------------------------------------------


def format_attribution_blocks(attribution: dict) -> list:
    """Convert context_attribution dict into Slack Block Kit blocks.

    Args:
        attribution: Dict mapping filename -> {"entry_count": int, "chars_read": int}.

    Returns:
        List of Slack Block Kit block dicts. Empty list if attribution is empty.
    """
    if not attribution:
        return []

    blocks = []

    # Divider
    blocks.append({"type": "divider"})

    # Sources header
    source_lines = ["*Sources used in this output:*"]
    total_entries = 0
    file_count = 0

    for filename, info in sorted(attribution.items()):
        entry_count = info.get("entry_count", 0)
        if entry_count > 0:
            source_lines.append(f"- {entry_count} entries from `{filename}`")
            total_entries += entry_count
            file_count += 1

    if file_count == 0:
        return []

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "\n".join(source_lines),
        },
    })

    # Total context block
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Context store: {total_entries} entries used across {file_count} files",
            }
        ],
    })

    return blocks


# ---------------------------------------------------------------------------
# 2. Contextual suggestion
# ---------------------------------------------------------------------------


def get_contextual_suggestion() -> Optional[str]:
    """Get a contextual suggestion based on stale context files.

    Checks staleness of context files and maps stale files to skill
    suggestions that would refresh them.

    Returns:
        Suggestion string like "Your contacts haven't been updated in 18 days.
        Run `/fly process` with a recent meeting to refresh."
        Returns None if nothing is stale.
    """
    try:
        stale_results = check_staleness()
    except Exception:
        return None

    if not stale_results:
        return None

    # Find stale files that have a suggestion mapping
    for result in stale_results:
        if result.get("status") != "stale":
            continue
        filename = result.get("file", "")
        actual_days = result.get("actual_days")
        if filename in _STALE_FILE_SUGGESTIONS and actual_days is not None:
            suggestion = _STALE_FILE_SUGGESTIONS[filename]
            display_name = filename.replace(".md", "").replace("-", " ")
            return (
                f"Your {display_name} haven't been updated in {actual_days} days. "
                f"Run `{suggestion['command']}` to refresh."
            )

    return None


# ---------------------------------------------------------------------------
# 3. What's changed
# ---------------------------------------------------------------------------


def get_whats_changed(user_id: str) -> Optional[str]:
    """Get a "what's changed" summary if this is the user's 3rd run.

    Triggers every 3rd skill run per user. Uses event log to summarize
    recent context store activity.

    Args:
        user_id: Slack user ID.

    Returns:
        Summary string or None if not the 3rd run.
    """
    try:
        prefs = load_user_preferences(user_id, "_run_counter")
        count_str = prefs.get("count", "0")
        count = int(count_str)
    except (ValueError, TypeError):
        return None

    if count == 0 or count % 3 != 0:
        return None

    # Build summary from recent events (last 7 days)
    try:
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        events = context_utils.read_event_log(since=since)

        if not events:
            return None

        # Count entries added per file
        file_counts = {}
        for event in events:
            if event.get("event") in ("entry_added", "entry_appended"):
                fname = event.get("file", "unknown")
                file_counts[fname] = file_counts.get(fname, 0) + 1

        if not file_counts:
            return None

        total_entries = sum(file_counts.values())
        file_count = len(file_counts)
        return f"{total_entries} new entries added across {file_count} files since your last check"

    except Exception:
        return None


# ---------------------------------------------------------------------------
# 4. Run counter
# ---------------------------------------------------------------------------


def increment_run_counter(user_id: str) -> int:
    """Increment and persist the run counter for a user.

    Args:
        user_id: Slack user ID.

    Returns:
        New counter value.
    """
    try:
        prefs = load_user_preferences(user_id, "_run_counter")
        count = int(prefs.get("count", "0"))
    except (ValueError, TypeError):
        count = 0

    count += 1
    save_user_preference(user_id, "_run_counter", "count", str(count))
    return count


# ---------------------------------------------------------------------------
# 5. Daily digest
# ---------------------------------------------------------------------------


async def send_daily_digest(slack_client, users_root: Path = None):
    """Send daily digest DM to active users.

    Lists user directories, checks activity, and sends a context store
    summary DM to users who have been active in the last 7 days.

    Uses conversations_open to get DM channel ID before sending.

    Args:
        slack_client: Slack AsyncWebClient instance.
        users_root: Root directory for user data. Defaults to USERS_ROOT.
    """
    root = users_root or USERS_ROOT
    if not root.exists():
        logger.info("No users directory found, skipping daily digest")
        return

    try:
        user_dirs = [d for d in root.iterdir() if d.is_dir()]
    except (PermissionError, OSError) as e:
        logger.error("Failed to list user directories: %s", e)
        return

    now = datetime.now()
    cutoff = now - timedelta(days=7)

    for user_dir in user_dirs:
        user_id = user_dir.name
        memory_dir = user_dir / "memory"

        # Check last activity (most recent preference file mtime)
        if not memory_dir.exists():
            continue

        try:
            most_recent = None
            for pref_file in memory_dir.iterdir():
                if pref_file.is_file():
                    mtime = datetime.fromtimestamp(pref_file.stat().st_mtime)
                    if most_recent is None or mtime > most_recent:
                        most_recent = mtime

            if most_recent is None or most_recent < cutoff:
                continue  # Skip inactive users (per research pitfall #8)
        except (PermissionError, OSError):
            continue

        # Build digest
        try:
            dashboard = get_health_dashboard()
        except Exception:
            dashboard = {}

        suggestion = get_contextual_suggestion()

        # Build blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Daily Flywheel Digest",
                    "emoji": True,
                },
            },
        ]

        # Stats section
        file_count = dashboard.get("file_count", 0)
        total_entries = dashboard.get("total_entries", 0)
        staleness = dashboard.get("staleness_percentage", 0.0)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Context Store:* {total_entries} entries across {file_count} files\n"
                    f"*Staleness:* {staleness:.0f}% of tracked files need refresh"
                ),
            },
        })

        # Recent activity
        try:
            since_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
            recent_events = context_utils.read_event_log(since=since_24h)
            if recent_events:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Last 24h:* {len(recent_events)} events recorded",
                    },
                })
        except Exception:
            pass

        # Contextual suggestion
        if suggestion:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":bulb: {suggestion}",
                },
            })

        # Pause note
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_To pause daily updates, let us know._",
                }
            ],
        })

        # Send DM using conversations_open (same pattern as send_onboarding_dm)
        try:
            dm_response = await slack_client.conversations_open(users=user_id)
            dm_channel = dm_response["channel"]["id"]
            await slack_client.chat_postMessage(
                channel=dm_channel,
                text="Daily Flywheel Digest",
                blocks=blocks,
            )
        except Exception as e:
            logger.error("Failed to send digest to %s: %s", user_id, e)


# ---------------------------------------------------------------------------
# 6. Scheduler setup
# ---------------------------------------------------------------------------


def setup_scheduler(slack_client):
    """Set up APScheduler for daily digest at 9 AM.

    Args:
        slack_client: Slack client to pass to send_daily_digest.

    Returns:
        AsyncIOScheduler instance (not started), or None if APScheduler
        is not installed.
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning(
            "APScheduler not installed. Daily digest scheduler disabled. "
            "Install with: pip3 install apscheduler"
        )
        return None

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_digest,
        CronTrigger(hour=9, minute=0),
        args=[slack_client],
        id="daily_digest",
        name="Daily Flywheel Digest",
    )
    return scheduler
