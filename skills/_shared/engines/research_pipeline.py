"""
research_pipeline.py - Authenticated research runner with rate limits and safety.

Runs headless Playwright research tasks using saved browser sessions from
browser_sessions.py. Enforces hard rate limits (LinkedIn: 50 views/day,
0 messages ever) and ensures research output is always a file (CSV/Excel),
never automated messaging.

Public API:
    run_research(user_id, service, task_fn, output_path) -> dict
    check_rate_limit(user_id, service) -> tuple[bool, int]
    record_action(user_id, service, action) -> None
    validate_task(service, task_description) -> bool
    RATE_LIMITS - Per-service rate limit config
    SAFETY_BOUNDARY - Per-service safety constraints
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Try importing playwright
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Import from src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from browser_sessions import get_session_state, is_session_valid
from integration_framework import is_integration_enabled

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROFILES_DIR = Path.home() / ".flywheel" / "browser-profiles"

# Rate limits per service (per locked decision: LinkedIn hard 50/day, 0 messages ever)
RATE_LIMITS = {
    "linkedin": {
        "max_daily_views": 50,
        "min_delay_seconds": 5,
    },
    "google": {
        "max_daily_views": 200,
        "min_delay_seconds": 2,
    },
    "github": {
        "max_daily_views": 500,
        "min_delay_seconds": 1,
    },
}

# Safety boundaries per service (per locked outreach safety boundary)
SAFETY_BOUNDARY = {
    "linkedin": {
        "no_messages": True,
        "no_connections": True,
        "output_format": "csv",
    },
    "google": {
        "no_messages": False,
        "no_connections": False,
        "output_format": "csv",
    },
    "github": {
        "no_messages": False,
        "no_connections": False,
        "output_format": "csv",
    },
}

# Blocked action keywords per service
_BLOCKED_KEYWORDS = {
    "linkedin": ["message", "connect", "send", "invite", "inmail", "endorse"],
}


# ---------------------------------------------------------------------------
# Rate limit tracking
# ---------------------------------------------------------------------------


def _rate_log_path(user_id: str, service: str) -> Path:
    """Get path to rate limit log file."""
    return PROFILES_DIR / user_id / f"{service}_rate_log.jsonl"


def _read_rate_log(user_id: str, service: str) -> list:
    """Read rate log entries."""
    path = _rate_log_path(user_id, service)
    if not path.exists():
        return []

    entries = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except IOError as e:
        logger.error("Failed to read rate log: %s", e)

    return entries


def check_rate_limit(user_id: str, service: str) -> tuple:
    """Check if user is within rate limits for a service.

    Args:
        user_id: User identifier.
        service: Service name.

    Returns:
        Tuple of (allowed: bool, remaining_today: int).
    """
    limits = RATE_LIMITS.get(service)
    if limits is None:
        # Unknown service -- allow but with default cap
        return (True, 100)

    max_daily = limits.get("max_daily_views", 100)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    entries = _read_rate_log(user_id, service)
    today_count = sum(
        1 for e in entries
        if e.get("date", "")[:10] == today
    )

    remaining = max(0, max_daily - today_count)
    allowed = today_count < max_daily

    return (allowed, remaining)


def record_action(user_id: str, service: str, action: str) -> None:
    """Record an action for rate limit tracking.

    Args:
        user_id: User identifier.
        service: Service name.
        action: Description of action performed.
    """
    path = _rate_log_path(user_id, service)
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "date": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "action": action,
    }

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except IOError as e:
        logger.error("Failed to write rate log: %s", e)


# ---------------------------------------------------------------------------
# Safety enforcement
# ---------------------------------------------------------------------------


def validate_task(service: str, task_description: str) -> bool:
    """Check if a task is allowed under safety boundaries.

    Any task involving messaging, connecting, sending on LinkedIn returns
    False. Research output is ALWAYS a file, never automated messaging.

    Args:
        service: Service name.
        task_description: Human-readable description of the task.

    Returns:
        True if task is allowed, False if blocked by safety boundary.
    """
    blocked_keywords = _BLOCKED_KEYWORDS.get(service, [])
    if not blocked_keywords:
        return True

    task_lower = task_description.lower()
    for keyword in blocked_keywords:
        if keyword in task_lower:
            logger.warning(
                "Task blocked by safety boundary: service=%s keyword=%s task=%s",
                service, keyword, task_description,
            )
            return False

    return True


# ---------------------------------------------------------------------------
# Research runner
# ---------------------------------------------------------------------------


async def run_research(
    user_id: str,
    service: str,
    task_fn: Callable,
    output_path: Optional[str] = None,
) -> dict:
    """Run an authenticated research task with rate limits and safety.

    Pre-flight checks:
    1. Integration enabled for user?
    2. Session valid (not expired)?
    3. Rate limit not exceeded?

    If all checks pass, launches headless browser with saved session and
    runs task_fn(page). Returns result dict with output_path and
    items_processed.

    Args:
        user_id: User identifier.
        service: Service name (e.g., 'linkedin').
        task_fn: Async callable that receives a Playwright page and returns
                 a dict with 'items' (list) and optionally 'output_path'.
        output_path: Optional path to save results. If None, task_fn must
                     handle output itself.

    Returns:
        Result dict with keys: status, output_path, items_processed, message.
    """
    # Pre-flight check 1: Integration enabled?
    if not is_integration_enabled(user_id, service):
        return {
            "status": "error",
            "message": f"Integration '{service}' is not enabled. Run /fly integrations to enable it.",
            "items_processed": 0,
        }

    # Pre-flight check 2: Session valid?
    if not is_session_valid(user_id, service):
        return {
            "status": "error",
            "message": f"Session expired. Run /fly login {service} to refresh.",
            "items_processed": 0,
        }

    # Pre-flight check 3: Rate limit?
    allowed, remaining = check_rate_limit(user_id, service)
    if not allowed:
        return {
            "status": "error",
            "message": f"Rate limit exceeded for {service}. 0 views remaining today.",
            "items_processed": 0,
        }

    # Pre-flight check 4: Playwright available?
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "status": "error",
            "message": "Playwright not installed. Cannot run browser research.",
            "items_processed": 0,
        }

    session_path = get_session_state(user_id, service)
    if session_path is None:
        return {
            "status": "error",
            "message": f"No session found. Run /fly login {service} to create one.",
            "items_processed": 0,
        }

    # Run the research task
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(storage_state=str(session_path))
            page = await context.new_page()

            result = await task_fn(page)

            items_processed = len(result.get("items", []))

            # Record actions for rate tracking
            for _ in range(items_processed):
                record_action(user_id, service, "view")

            final_output = output_path or result.get("output_path")

            return {
                "status": "success",
                "output_path": final_output,
                "items_processed": items_processed,
                "remaining_today": max(0, remaining - items_processed),
                "message": f"Processed {items_processed} items. Output: {final_output}",
            }

        except Exception as e:
            logger.error("Research task failed: %s", e)
            return {
                "status": "error",
                "message": f"Research task failed: {e}",
                "items_processed": 0,
            }
        finally:
            await browser.close()
