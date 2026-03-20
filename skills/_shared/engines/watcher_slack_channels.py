"""
watcher_slack_channels.py - Slack channel monitoring for competitive intelligence.

Watches opted-in channels for competitive intelligence keywords and auto-extracts
intelligence via the execution gateway. Event-driven via Slack Events API (Socket
Mode) -- the bot already receives message events; this module adds keyword filtering
and extraction logic.

Key design:
- Keyword pre-filtering happens BEFORE any LLM call (cost control)
- Only opted-in channels are monitored (explicit opt-in)
- Deduplication via message timestamp (bounded set of last 1000)
- Daily cap (MAX_CHANNEL_CAPTURES_PER_DAY = 20) aligned with global DAILY_AUTO_TRIGGER_CAP

Public API:
    handle_channel_message(event, user_id) -> Optional[dict]
    get_monitored_channels(user_id) -> list[str]
    set_monitored_channels(user_id, channels) -> None
    get_custom_keywords(user_id) -> list[str]
    add_keyword(user_id, keyword) -> None
    remove_keyword(user_id, keyword) -> None
    extract_competitive_intel(text, channel, user_id) -> dict
"""

import logging
import os
import sys
from collections import OrderedDict
from typing import Optional

# Import from src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from integration_framework import check_daily_cap, is_integration_enabled, record_trigger
from user_memory import load_user_preferences, save_user_preference

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_KEYWORDS = [
    "competitor",
    "alternative to",
    "switching from",
    "better than",
    "compared to",
    "versus",
    "replaced",
    "moving to",
    "tried",
]

# Per-integration daily cap, aligned with global DAILY_AUTO_TRIGGER_CAP = 20
MAX_CHANNEL_CAPTURES_PER_DAY = 20

# Preference keys
_PREF_SKILL = "_slack_channel_monitor"
_PREF_CHANNELS_KEY = "monitored_channels"
_PREF_KEYWORDS_KEY = "custom_keywords"

# Integration key in INTEGRATIONS registry
_INTEGRATION_KEY = "slack_channels"

# ---------------------------------------------------------------------------
# Deduplication (bounded set of last 1000 message timestamps)
# ---------------------------------------------------------------------------

# Module-level dedup store, keyed by user_id -> OrderedDict of ts -> True
_MAX_DEDUP_SIZE = 1000
_processed_messages: dict[str, OrderedDict] = {}


def _is_duplicate(user_id: str, message_ts: str) -> bool:
    """Check if a message timestamp was already processed."""
    user_set = _processed_messages.get(user_id)
    if user_set is None:
        return False
    return message_ts in user_set


def _mark_processed(user_id: str, message_ts: str) -> None:
    """Record a message timestamp as processed. Bounded to last 1000."""
    if user_id not in _processed_messages:
        _processed_messages[user_id] = OrderedDict()

    user_set = _processed_messages[user_id]
    user_set[message_ts] = True

    # Trim to last _MAX_DEDUP_SIZE
    while len(user_set) > _MAX_DEDUP_SIZE:
        user_set.popitem(last=False)


# ---------------------------------------------------------------------------
# Channel management
# ---------------------------------------------------------------------------


def get_monitored_channels(user_id: str) -> list:
    """Get list of channel IDs being monitored for a user.

    Args:
        user_id: User identifier.

    Returns:
        List of Slack channel ID strings. Empty list if none configured.
    """
    prefs = load_user_preferences(user_id, _PREF_SKILL)
    channels_str = prefs.get(_PREF_CHANNELS_KEY, "")
    if not channels_str.strip():
        return []
    return [c.strip() for c in channels_str.split(",") if c.strip()]


def set_monitored_channels(user_id: str, channels: list) -> None:
    """Set the list of monitored channel IDs for a user.

    Args:
        user_id: User identifier.
        channels: List of Slack channel ID strings.
    """
    channels_str = ",".join(channels)
    save_user_preference(user_id, _PREF_SKILL, _PREF_CHANNELS_KEY, channels_str)
    logger.info("User %s set monitored channels: %s", user_id, channels)


# ---------------------------------------------------------------------------
# Keyword management
# ---------------------------------------------------------------------------


def get_custom_keywords(user_id: str) -> list:
    """Get keywords for a user (custom merged with defaults).

    Args:
        user_id: User identifier.

    Returns:
        List of keyword strings (defaults + user custom keywords).
    """
    prefs = load_user_preferences(user_id, _PREF_SKILL)
    custom_str = prefs.get(_PREF_KEYWORDS_KEY, "")

    # Start with defaults
    keywords = list(DEFAULT_KEYWORDS)

    # Merge custom keywords
    if custom_str.strip():
        custom = [k.strip() for k in custom_str.split(",") if k.strip()]
        for kw in custom:
            if kw.lower() not in [k.lower() for k in keywords]:
                keywords.append(kw)

    return keywords


def add_keyword(user_id: str, keyword: str) -> None:
    """Add a custom keyword for a user.

    Args:
        user_id: User identifier.
        keyword: Keyword string to add.
    """
    prefs = load_user_preferences(user_id, _PREF_SKILL)
    custom_str = prefs.get(_PREF_KEYWORDS_KEY, "")
    existing = [k.strip() for k in custom_str.split(",") if k.strip()] if custom_str.strip() else []

    if keyword.lower() not in [k.lower() for k in existing]:
        existing.append(keyword)
        save_user_preference(user_id, _PREF_SKILL, _PREF_KEYWORDS_KEY, ",".join(existing))
        logger.info("User %s added keyword: %s", user_id, keyword)


def remove_keyword(user_id: str, keyword: str) -> None:
    """Remove a custom keyword for a user.

    Args:
        user_id: User identifier.
        keyword: Keyword string to remove.
    """
    prefs = load_user_preferences(user_id, _PREF_SKILL)
    custom_str = prefs.get(_PREF_KEYWORDS_KEY, "")
    if not custom_str.strip():
        return

    existing = [k.strip() for k in custom_str.split(",") if k.strip()]
    filtered = [k for k in existing if k.lower() != keyword.lower()]

    save_user_preference(user_id, _PREF_SKILL, _PREF_KEYWORDS_KEY, ",".join(filtered))
    logger.info("User %s removed keyword: %s", user_id, keyword)


# ---------------------------------------------------------------------------
# Keyword matching
# ---------------------------------------------------------------------------


def _matches_keywords(text: str, keywords: list) -> bool:
    """Check if text contains any keyword (case-insensitive).

    Args:
        text: Message text to search.
        keywords: List of keyword strings.

    Returns:
        True if any keyword found in text.
    """
    if not text:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


# ---------------------------------------------------------------------------
# Intelligence extraction
# ---------------------------------------------------------------------------


def extract_competitive_intel(text: str, channel: str, user_id: str) -> dict:
    """Extract competitive intelligence from a Slack message.

    Calls execute_skill with a generic extraction prompt. Uses lazy import
    to avoid circular dependency at module load time.

    Args:
        text: Message text to analyze.
        channel: Slack channel ID where message was found.
        user_id: User identifier.

    Returns:
        Dict with extraction result, including 'output' and 'status' keys.
    """
    from execution_gateway import execute_skill

    # meeting-processor is used as a generic extraction runner here —
    # its LLM path handles arbitrary text extraction via the system prompt
    result = execute_skill(
        skill_name="meeting-processor",
        input_text=f"Extract competitive intelligence from this Slack message: {text}",
        user_id=user_id,
        params={"source": "slack-channel", "channel": channel},
    )

    return {
        "output": result.output,
        "status": "ok" if result.mode != "error" else "error",
        "channel": channel,
        "source": "slack-channel-monitor",
        "cost_estimate": 0.05,
    }


# ---------------------------------------------------------------------------
# Message handler (main entry point)
# ---------------------------------------------------------------------------


async def handle_channel_message(event: dict, user_id: str) -> Optional[dict]:
    """Handle a Slack channel message event for competitive intelligence.

    Called by the Slack bot's message event handler. Checks:
    1. Channel is in user's monitored list
    2. Message text matches any keyword (case-insensitive)
    3. Integration is enabled for user
    4. Daily cap not exceeded
    5. Message not already processed (dedup by ts)

    If all pass, extracts intelligence via execute_skill.

    Args:
        event: Slack message event dict with 'channel', 'text', 'ts' keys.
        user_id: User identifier.

    Returns:
        Extraction result dict, or None if message filtered out.
    """
    channel = event.get("channel", "")
    text = event.get("text", "")
    message_ts = event.get("ts", "")

    # Gate 1: Channel must be in monitored list
    monitored = get_monitored_channels(user_id)
    if channel not in monitored:
        return None

    # Gate 2: Text must match a keyword (pre-filter before LLM call)
    keywords = get_custom_keywords(user_id)
    if not _matches_keywords(text, keywords):
        return None

    # Gate 3: Integration must be enabled
    if not is_integration_enabled(user_id, _INTEGRATION_KEY):
        return None

    # Gate 4: Daily cap not exceeded
    if not check_daily_cap(user_id):
        logger.warning(
            "Daily cap reached for user %s, skipping channel message",
            user_id,
        )
        return None

    # Gate 5: Deduplication by message timestamp
    if _is_duplicate(user_id, message_ts):
        return None

    # All gates passed -- extract intelligence
    _mark_processed(user_id, message_ts)

    try:
        result = extract_competitive_intel(text, channel, user_id)

        # Record trigger for cost tracking
        record_trigger(user_id, _INTEGRATION_KEY, result.get("cost_estimate", 0.05))

        return result
    except Exception as e:
        logger.error(
            "Failed to extract intelligence from channel %s for user %s: %s",
            channel, user_id, e,
        )
        return None
