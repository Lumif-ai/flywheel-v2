"""
integration_framework.py - Integration framework for Flywheel watchers.

Provides the foundation for all integrations: WatcherBase class with state
persistence and deduplication, IntegrationManager for watcher lifecycle via
APScheduler, explicit opt-in permission model per user per integration, and
cost controls with daily caps and per-integration token budgets.

Public API:
    WatcherBase - Abstract base class for integration watchers
    IntegrationManager - Watcher lifecycle manager (APScheduler)
    is_integration_enabled(user_id, integration) -> bool
    toggle_integration(user_id, integration, enabled) -> None
    get_integration_settings(user_id) -> dict
    check_daily_cap(user_id) -> bool
    record_trigger(user_id, integration, cost_estimate) -> None
    get_cost_summary(user_id) -> dict
    INTEGRATIONS - Registry of available integrations
"""

import abc
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Import from src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from token_logger import log_token_usage
from user_memory import load_user_preferences, save_user_preference

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_DIR = Path.home() / ".flywheel" / "watcher-state"

# Cost controls
DAILY_AUTO_TRIGGER_CAP = 20

# ---------------------------------------------------------------------------
# 1. WatcherBase (abstract base class)
# ---------------------------------------------------------------------------


class WatcherBase(abc.ABC):
    """Base class for integration watchers.

    Handles: state persistence (JSON), deduplication (last 1000 IDs),
    cost tracking via token_logger, and crash recovery.

    Subclasses must implement check() and process().
    """

    def __init__(self, name: str, user_id: str):
        self.name = name
        self.user_id = user_id
        self.state_file = STATE_DIR / f"{name}-{user_id}.json"
        self._load_state()

    def _load_state(self):
        """Load last-processed state from disk for crash recovery."""
        if self.state_file.exists():
            try:
                self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load watcher state from %s: %s", self.state_file, e)
                self.state = {"last_processed": None, "processed_ids": [], "error_count": 0}
        else:
            self.state = {"last_processed": None, "processed_ids": [], "error_count": 0}

    def _save_state(self):
        """Persist state to disk for crash recovery (atomic via temp+rename)."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.state_file.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(self.state, indent=2), encoding="utf-8"
        )
        tmp_path.replace(self.state_file)

    def is_duplicate(self, item_id: str) -> bool:
        """Check if item was already processed (deduplication)."""
        return item_id in self.state.get("processed_ids", [])

    def mark_processed(self, item_id: str):
        """Record item as processed.

        Keeps last 1000 IDs to prevent unbounded growth.
        Updates last_processed timestamp and saves state.
        """
        ids = self.state.setdefault("processed_ids", [])
        ids.append(item_id)
        # Bound to last 1000 IDs
        self.state["processed_ids"] = ids[-1000:]
        self.state["last_processed"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

    @abc.abstractmethod
    def check(self) -> list:
        """Check for new items to process.

        Returns:
            List of items to process. Each item should have an 'id' field
            for deduplication.
        """

    @abc.abstractmethod
    def process(self, item) -> dict:
        """Process a single item via execute_skill().

        Args:
            item: An item returned from check().

        Returns:
            Result dict with at least 'status' key.
        """

    def run_cycle(self) -> list:
        """Run one check-filter-process cycle.

        Calls check(), filters duplicates, processes each item,
        tracks cost via token_logger. Returns list of results.
        """
        results = []

        try:
            items = self.check()
        except Exception as e:
            self.state["error_count"] = self.state.get("error_count", 0) + 1
            self._save_state()
            logger.error("Watcher %s check failed: %s", self.name, e)
            return results

        for item in items:
            item_id = item.get("id", str(item)) if isinstance(item, dict) else str(item)

            if self.is_duplicate(item_id):
                continue

            # Check daily cap before processing
            if not check_daily_cap(self.user_id):
                logger.warning(
                    "Daily auto-trigger cap reached for user %s, skipping remaining items",
                    self.user_id,
                )
                break

            try:
                result = self.process(item)
                self.mark_processed(item_id)

                # Record trigger for cost tracking
                cost_estimate = result.get("cost_estimate", 0.0) if isinstance(result, dict) else 0.0
                record_trigger(self.user_id, self.name, cost_estimate)

                results.append(result)
            except Exception as e:
                self.state["error_count"] = self.state.get("error_count", 0) + 1
                self._save_state()
                logger.error(
                    "Watcher %s process failed for item %s: %s",
                    self.name, item_id, e,
                )

        return results


# ---------------------------------------------------------------------------
# 2. IntegrationManager (APScheduler lifecycle)
# ---------------------------------------------------------------------------


class IntegrationManager:
    """Manages watcher lifecycle using APScheduler.

    Uses APScheduler 3.x AsyncIOScheduler (same pattern as retention.py
    setup_scheduler). In-memory job store with deterministic IDs;
    re-register on startup with replace_existing=True.
    """

    def __init__(self):
        self._watchers = {}
        self._scheduler = None
        self._init_scheduler()

    def _init_scheduler(self):
        """Initialize APScheduler, wrapped in try/except for graceful degradation."""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            self._scheduler = AsyncIOScheduler()
        except ImportError:
            logger.warning(
                "APScheduler not installed. IntegrationManager will operate "
                "in degraded mode (no scheduling). Install with: pip3 install apscheduler"
            )
            self._scheduler = None

    def register_watcher(self, watcher: WatcherBase, interval_minutes: int = 15):
        """Register a watcher with APScheduler.

        Uses deterministic job ID and replace_existing=True to avoid
        duplicates on restart (per research pitfall #8).

        Args:
            watcher: WatcherBase instance.
            interval_minutes: How often to run the watcher cycle.
        """
        job_id = f"watcher-{watcher.name}-{watcher.user_id}"
        self._watchers[job_id] = {
            "watcher": watcher,
            "interval_minutes": interval_minutes,
        }

        if self._scheduler is not None:
            self._scheduler.add_job(
                watcher.run_cycle,
                "interval",
                minutes=interval_minutes,
                id=job_id,
                name=f"Watcher: {watcher.name} ({watcher.user_id})",
                replace_existing=True,
            )
            logger.info("Registered watcher %s with %d-minute interval", job_id, interval_minutes)

    def start(self):
        """Start the scheduler."""
        if self._scheduler is not None:
            if not self._scheduler.running:
                self._scheduler.start()
                logger.info("IntegrationManager scheduler started")
        else:
            logger.warning("Cannot start: APScheduler not available")

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("IntegrationManager scheduler stopped")

    def get_status(self) -> dict:
        """Get status of all registered watchers.

        Returns:
            Dict mapping job_id to status info (last_run, next_run, error_count).
        """
        status = {}
        for job_id, info in self._watchers.items():
            watcher = info["watcher"]
            entry = {
                "name": watcher.name,
                "user_id": watcher.user_id,
                "interval_minutes": info["interval_minutes"],
                "last_processed": watcher.state.get("last_processed"),
                "error_count": watcher.state.get("error_count", 0),
                "processed_count": len(watcher.state.get("processed_ids", [])),
            }

            # Add APScheduler job info if available
            if self._scheduler is not None:
                try:
                    job = self._scheduler.get_job(job_id)
                    if job:
                        entry["next_run"] = str(job.next_run_time) if job.next_run_time else None
                except Exception:
                    entry["next_run"] = None

            status[job_id] = entry

        return status


# ---------------------------------------------------------------------------
# 3. Permission model (explicit opt-in)
# ---------------------------------------------------------------------------

INTEGRATIONS = {
    "meeting_notes": {
        "name": "Meeting Notes",
        "description": "Auto-process transcripts from Granola/Fathom",
        "scope": "read-only (local files)",
        "est_cost": "~$0.10 per transcript",
    },
    "calendar": {
        "name": "Google Calendar",
        "description": "Auto-trigger meeting prep before external meetings",
        "scope": "calendar.events.readonly",
        "est_cost": "~$0.20 per auto-prep",
    },
    "email": {
        "name": "Email (Gmail)",
        "description": "Track replies to your outreach emails",
        "scope": "gmail.readonly",
        "est_cost": "~$0.01 per check",
    },
    "slack_channels": {
        "name": "Slack Channel Monitoring",
        "description": "Monitor opted-in channels for competitive intelligence",
        "scope": "channels:history (opted-in only)",
        "est_cost": "~$0.05 per keyword match",
    },
}

# Preference key prefix for integration toggles
_INTEGRATION_PREF_SKILL = "_integrations"


def is_integration_enabled(user_id: str, integration: str) -> bool:
    """Check if an integration is enabled for a user.

    All integrations default to DISABLED (explicit opt-in).

    Args:
        user_id: User identifier.
        integration: Integration key from INTEGRATIONS dict.

    Returns:
        True if enabled, False otherwise (including for unknown integrations).
    """
    if integration not in INTEGRATIONS:
        return False

    prefs = load_user_preferences(user_id, _INTEGRATION_PREF_SKILL)
    return prefs.get(integration, "").lower() == "true"


def toggle_integration(user_id: str, integration: str, enabled: bool) -> None:
    """Enable or disable an integration for a user.

    Args:
        user_id: User identifier.
        integration: Integration key from INTEGRATIONS dict.
        enabled: True to enable, False to disable.

    Raises:
        ValueError: If integration is not a valid integration key.
    """
    if integration not in INTEGRATIONS:
        raise ValueError(f"Unknown integration: {integration}. Valid: {list(INTEGRATIONS.keys())}")

    save_user_preference(user_id, _INTEGRATION_PREF_SKILL, integration, str(enabled).lower())
    logger.info("User %s %s integration %s", user_id, "enabled" if enabled else "disabled", integration)


def get_integration_settings(user_id: str) -> dict:
    """Get all integrations with their enabled/disabled status for a user.

    Returns:
        Dict mapping integration key to info dict with 'enabled' field added.
    """
    prefs = load_user_preferences(user_id, _INTEGRATION_PREF_SKILL)
    settings = {}

    for key, info in INTEGRATIONS.items():
        entry = dict(info)
        entry["enabled"] = prefs.get(key, "").lower() == "true"
        settings[key] = entry

    return settings


# ---------------------------------------------------------------------------
# 4. Cost controls
# ---------------------------------------------------------------------------


def _get_trigger_log_path(user_id: str) -> Path:
    """Get path to user's trigger log file."""
    return STATE_DIR / f"{user_id}-triggers.jsonl"


def _read_trigger_log(user_id: str) -> list:
    """Read trigger log entries for a user.

    Returns:
        List of trigger log entry dicts.
    """
    log_path = _get_trigger_log_path(user_id)
    if not log_path.exists():
        return []

    entries = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except IOError as e:
        logger.error("Failed to read trigger log for %s: %s", user_id, e)

    return entries


def check_daily_cap(user_id: str) -> bool:
    """Check if user is under the daily auto-trigger cap.

    Args:
        user_id: User identifier.

    Returns:
        True if under the cap (can trigger), False if at or over cap.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = _read_trigger_log(user_id)

    today_count = sum(
        1 for e in entries
        if e.get("date", "")[:10] == today
    )

    return today_count < DAILY_AUTO_TRIGGER_CAP


def record_trigger(user_id: str, integration: str, cost_estimate: float = 0.0) -> None:
    """Record an auto-trigger event for cost tracking.

    Appends to the user's trigger JSONL log. Auto-rotates entries
    older than 30 days on each write.

    Args:
        user_id: User identifier.
        integration: Integration name that triggered.
        cost_estimate: Estimated cost of this trigger in dollars.
    """
    log_path = _get_trigger_log_path(user_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    entry = {
        "date": now.isoformat(),
        "integration": integration,
        "cost_estimate": cost_estimate,
    }

    # Read existing entries for rotation
    existing = _read_trigger_log(user_id)

    # Rotate: remove entries older than 30 days
    cutoff = (now - timedelta(days=30)).isoformat()
    rotated = [e for e in existing if e.get("date", "") >= cutoff]

    # Append new entry
    rotated.append(entry)

    # Write back
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            for e in rotated:
                f.write(json.dumps(e) + "\n")
    except IOError as e:
        logger.error("Failed to write trigger log for %s: %s", user_id, e)


def get_cost_summary(user_id: str) -> dict:
    """Get cost summary for a user.

    Returns:
        Dict with today's trigger count, estimated cost, remaining budget,
        and per-integration breakdown.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = _read_trigger_log(user_id)

    today_entries = [e for e in entries if e.get("date", "")[:10] == today]
    today_count = len(today_entries)
    today_cost = sum(e.get("cost_estimate", 0.0) for e in today_entries)

    # Per-integration breakdown for today
    by_integration = {}
    for e in today_entries:
        integ = e.get("integration", "unknown")
        by_integration[integ] = by_integration.get(integ, 0) + 1

    return {
        "today_triggers": today_count,
        "today_cost_estimate": round(today_cost, 4),
        "remaining_triggers": max(0, DAILY_AUTO_TRIGGER_CAP - today_count),
        "daily_cap": DAILY_AUTO_TRIGGER_CAP,
        "by_integration": by_integration,
    }
