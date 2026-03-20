"""
nudge_engine.py - Proactive nudge engine for Flywheel.

Evaluates trigger conditions, scores relevance, enforces throttling
(max 3/day, confidence > 0.7), delivers nudges via Slack DM with
feedback buttons, and auto-mutes low-value nudge types.

Nudge tiers (highest to lowest priority):
  Tier 1: meeting_upcoming, meeting_followup
  Tier 2: relationship_stale, relationship_milestone
  Tier 3: pattern_competitive, pattern_effectiveness

Public API:
    NudgeEngine - Per-user nudge state, throttling, feedback, delivery
    register_nudge_evaluator(manager, user_id) - Schedule periodic evaluation
    run_nudge_cycle(user_id) - Evaluate all triggers and deliver top nudge
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Import from src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import context_utils
from user_memory import load_user_preferences, save_user_preference

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_NUDGES_PER_DAY = 3
MIN_CONFIDENCE = 0.7
COOLDOWN_DAYS = 7
AUTO_MUTE_THRESHOLD = 0.3
AUTO_MUTE_MIN_RATINGS = 10
NUDGE_STATE_DIR = Path.home() / ".flywheel" / "nudge-state"

# Nudge type definitions with tier assignments
NUDGE_TYPES = {
    "meeting_upcoming": {"tier": 1, "label": "Upcoming Meeting Prep"},
    "meeting_followup": {"tier": 1, "label": "Meeting Follow-up"},
    "relationship_stale": {"tier": 2, "label": "Stale Relationship Alert"},
    "relationship_milestone": {"tier": 2, "label": "Relationship Milestone"},
    "pattern_competitive": {"tier": 3, "label": "Competitive Intelligence"},
    "pattern_effectiveness": {"tier": 3, "label": "Effectiveness Change"},
}

# Relationship staleness threshold in days
STALE_RELATIONSHIP_DAYS = 30


# ---------------------------------------------------------------------------
# NudgeEngine
# ---------------------------------------------------------------------------


class NudgeEngine:
    """Per-user nudge engine with throttling, feedback, and auto-mute.

    State persisted to NUDGE_STATE_DIR/{user_id}.json with schema:
    {
        "sent": [{"id", "type", "date", "content_preview"}],
        "feedback": [{"nudge_id", "helpful", "date"}],
        "disabled_types": [],
        "settings": {"digest_mode": false}
    }
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.state_file = NUDGE_STATE_DIR / f"{user_id}.json"
        self._load_state()

    def _load_state(self):
        """Load nudge state from disk."""
        if self.state_file.exists():
            try:
                self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load nudge state from %s: %s", self.state_file, e)
                self.state = self._default_state()
        else:
            self.state = self._default_state()

    @staticmethod
    def _default_state() -> dict:
        return {
            "sent": [],
            "feedback": [],
            "disabled_types": [],
            "settings": {"digest_mode": False},
        }

    def _save_state(self):
        """Persist nudge state to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self.state, indent=2), encoding="utf-8"
        )

    # -------------------------------------------------------------------
    # Throttling
    # -------------------------------------------------------------------

    def _today_count(self) -> int:
        """Count nudges sent today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return sum(
            1 for s in self.state.get("sent", [])
            if s.get("date", "")[:10] == today
        )

    def _last_sent_of_type(self, nudge_type: str) -> Optional[datetime]:
        """Find when the most recent nudge of this type was sent."""
        for s in reversed(self.state.get("sent", [])):
            if s.get("type") == nudge_type:
                try:
                    return datetime.fromisoformat(s["date"])
                except (ValueError, KeyError):
                    continue
        return None

    def should_send(self, nudge_type: str, confidence: float) -> bool:
        """Check if a nudge should be sent, applying all throttling rules.

        Checks in order:
        a. Daily count < MAX_NUDGES_PER_DAY
        b. confidence >= MIN_CONFIDENCE
        c. nudge_type not in disabled_types
        d. Cooldown: no nudge of same type in last COOLDOWN_DAYS
        e. Auto-mute check: helpfulness rate >= AUTO_MUTE_THRESHOLD (with min ratings)

        Returns:
            True if nudge should be sent, False otherwise.
        """
        # a. Daily cap
        if self._today_count() >= MAX_NUDGES_PER_DAY:
            logger.debug("Nudge blocked: daily cap reached (%d/%d)", self._today_count(), MAX_NUDGES_PER_DAY)
            return False

        # b. Confidence threshold
        if confidence < MIN_CONFIDENCE:
            logger.debug("Nudge blocked: confidence %.2f < %.2f threshold", confidence, MIN_CONFIDENCE)
            return False

        # c. Disabled type
        if nudge_type in self.state.get("disabled_types", []):
            logger.debug("Nudge blocked: type %s is disabled", nudge_type)
            return False

        # d. Cooldown
        last_sent = self._last_sent_of_type(nudge_type)
        if last_sent is not None:
            # Ensure timezone-aware comparison
            now = datetime.now(timezone.utc)
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=timezone.utc)
            cooldown_cutoff = now - timedelta(days=COOLDOWN_DAYS)
            if last_sent > cooldown_cutoff:
                logger.debug("Nudge blocked: type %s in cooldown (last sent %s)", nudge_type, last_sent.isoformat())
                return False

        # e. Auto-mute check
        if self.check_auto_mute(nudge_type):
            logger.debug("Nudge blocked: type %s auto-muted due to low helpfulness", nudge_type)
            return False

        return True

    # -------------------------------------------------------------------
    # Trigger evaluators
    # -------------------------------------------------------------------

    def evaluate_meeting_triggers(self, upcoming_meetings: list) -> list:
        """Evaluate meeting-related triggers.

        For each upcoming meeting, check if prep exists in context store.
        If not, generate a nudge with confidence based on meeting importance.

        Args:
            upcoming_meetings: List of meeting dicts with keys:
                - id: unique meeting identifier
                - title: meeting title
                - start_time: ISO datetime string
                - attendees: list of attendee dicts with 'email' field
                - is_external: bool (external=True means prospect/customer)

        Returns:
            List of nudge dicts with: type, confidence, content, meeting_id
        """
        nudges = []

        for meeting in upcoming_meetings:
            meeting_id = meeting.get("id", "")
            title = meeting.get("title", "Unknown Meeting")
            is_external = meeting.get("is_external", False)

            # Check if meeting prep already exists in context store
            has_prep = False
            try:
                content = context_utils.read_context("action-items.md", agent_id="nudge-engine")
                if meeting_id in content or title.lower() in content.lower():
                    has_prep = True
            except Exception:
                pass  # Context read failures are non-blocking

            if not has_prep:
                confidence = 0.9 if is_external else 0.5
                nudges.append({
                    "type": "meeting_upcoming",
                    "confidence": confidence,
                    "content": f"You have '{title}' coming up with no prep. Run `/fly prep` to get briefed.",
                    "meeting_id": meeting_id,
                })

        return nudges

    def evaluate_relationship_triggers(self) -> list:
        """Evaluate relationship staleness triggers.

        Reads contacts.md and checks last interaction dates. If a prospect
        or customer hasn't been engaged in 30+ days, generates a nudge.

        Returns:
            List of nudge dicts with: type, confidence, content, contact_name
        """
        nudges = []

        try:
            content = context_utils.read_context("contacts.md", agent_id="nudge-engine")
        except Exception:
            return nudges

        if not content:
            return nudges

        # Parse contact entries for staleness
        now = datetime.now(timezone.utc)
        entries = context_utils.parse_context_file(content)

        for entry in entries:
            # Extract date from entry (parse as UTC-aware for consistent comparison)
            try:
                entry_date = datetime.strptime(entry.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue

            age_days = (now - entry_date).days

            if age_days >= STALE_RELATIONSHIP_DAYS:
                # Determine relationship type from detail field
                detail = entry.detail.lower() if entry.detail else ""
                if "customer" in detail:
                    confidence = 0.9
                elif "prospect" in detail:
                    confidence = 0.8
                else:
                    confidence = 0.7

                contact_name = entry.detail or "Unknown"
                nudges.append({
                    "type": "relationship_stale",
                    "confidence": confidence,
                    "content": f"{contact_name} hasn't been engaged in {age_days} days. Consider reaching out.",
                    "contact_name": contact_name,
                })

        return nudges

    def evaluate_pattern_triggers(self) -> list:
        """Evaluate pattern-based triggers (competitive intel, effectiveness).

        Reads event log for recent competitive intel additions or
        effectiveness score changes.

        Returns:
            List of nudge dicts with: type, confidence, content
        """
        nudges = []

        try:
            since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
            events = context_utils.read_event_log(since=since)
        except Exception:
            return nudges

        if not events:
            return nudges

        # Check for competitive intel accumulation
        competitive_events = [
            e for e in events
            if e.get("file") == "competitive-intel.md"
            and e.get("event") in ("entry_added", "entry_appended", "evidence_incremented")
        ]
        if len(competitive_events) >= 3:
            nudges.append({
                "type": "pattern_competitive",
                "confidence": 0.7,
                "content": f"{len(competitive_events)} competitive intel updates this week. Review with `/fly pipeline`.",
            })

        # Check for effectiveness changes
        effectiveness_events = [
            e for e in events
            if "effectiveness" in e.get("file", "").lower()
            and e.get("event") in ("entry_added", "entry_appended")
        ]
        if effectiveness_events:
            nudges.append({
                "type": "pattern_effectiveness",
                "confidence": 0.7,
                "content": "Outreach effectiveness data updated. Check trends with `/fly effectiveness`.",
            })

        return nudges

    # -------------------------------------------------------------------
    # Delivery
    # -------------------------------------------------------------------

    @staticmethod
    def format_nudge_blocks(nudge: dict) -> list:
        """Format a nudge as Slack Block Kit blocks with feedback buttons.

        Args:
            nudge: Nudge dict with at least 'type', 'content', and 'id'.

        Returns:
            List of Slack Block Kit block dicts.
        """
        nudge_id = nudge.get("id", "unknown")
        nudge_type = nudge.get("type", "unknown")
        label = NUDGE_TYPES.get(nudge_type, {}).get("label", nudge_type)
        content = nudge.get("content", "")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{label}*\n{content}",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Helpful"},
                        "action_id": f"nudge_helpful_{nudge_id}",
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Not Helpful"},
                        "action_id": f"nudge_unhelpful_{nudge_id}",
                    },
                ],
            },
        ]

        return blocks

    def record_sent(self, nudge_type: str, content: str) -> str:
        """Record a sent nudge in state.

        Args:
            nudge_type: Type of nudge sent.
            content: Preview of nudge content.

        Returns:
            Generated nudge ID.
        """
        nudge_id = str(uuid.uuid4())[:8]
        self.state.setdefault("sent", []).append({
            "id": nudge_id,
            "type": nudge_type,
            "date": datetime.now(timezone.utc).isoformat(),
            "content_preview": content[:200],
        })
        self._save_state()
        return nudge_id

    # -------------------------------------------------------------------
    # Feedback loop
    # -------------------------------------------------------------------

    def record_feedback(self, nudge_id: str, helpful: bool):
        """Record user feedback on a nudge.

        Args:
            nudge_id: ID of the nudge being rated.
            helpful: True if user found it helpful, False otherwise.
        """
        self.state.setdefault("feedback", []).append({
            "nudge_id": nudge_id,
            "helpful": helpful,
            "date": datetime.now(timezone.utc).isoformat(),
        })

        # Determine nudge type from sent history for auto-mute check
        nudge_type = None
        for s in self.state.get("sent", []):
            if s.get("id") == nudge_id:
                nudge_type = s.get("type")
                break

        self._save_state()

        # Check auto-mute after recording feedback
        if nudge_type:
            self.check_auto_mute(nudge_type)

    def get_helpfulness_rate(self, nudge_type: str) -> float:
        """Calculate helpfulness rate for a nudge type.

        Args:
            nudge_type: Type to calculate rate for.

        Returns:
            Ratio of helpful ratings to total ratings (0.0-1.0).
            Returns 1.0 if no ratings exist (benefit of the doubt).
        """
        # Map nudge_ids to types from sent history
        type_map = {}
        for s in self.state.get("sent", []):
            type_map[s.get("id")] = s.get("type")

        # Filter feedback for this nudge type
        type_feedback = [
            f for f in self.state.get("feedback", [])
            if type_map.get(f.get("nudge_id")) == nudge_type
        ]

        if not type_feedback:
            return 1.0  # Default: no data means benefit of the doubt

        helpful_count = sum(1 for f in type_feedback if f.get("helpful"))
        return helpful_count / len(type_feedback)

    def check_auto_mute(self, nudge_type: str) -> bool:
        """Check if a nudge type should be auto-muted.

        Auto-mutes if helpfulness rate < AUTO_MUTE_THRESHOLD over
        AUTO_MUTE_MIN_RATINGS or more ratings.

        Args:
            nudge_type: Type to check.

        Returns:
            True if type was auto-muted (or already muted), False otherwise.
        """
        # Map nudge_ids to types
        type_map = {}
        for s in self.state.get("sent", []):
            type_map[s.get("id")] = s.get("type")

        # Count ratings for this type
        type_feedback = [
            f for f in self.state.get("feedback", [])
            if type_map.get(f.get("nudge_id")) == nudge_type
        ]

        if len(type_feedback) < AUTO_MUTE_MIN_RATINGS:
            return False

        rate = self.get_helpfulness_rate(nudge_type)
        if rate < AUTO_MUTE_THRESHOLD:
            # Auto-mute this type
            disabled = self.state.setdefault("disabled_types", [])
            if nudge_type not in disabled:
                disabled.append(nudge_type)
                self._save_state()
                logger.info(
                    "Auto-muted nudge type %s for user %s (helpfulness %.0f%% over %d ratings)",
                    nudge_type, self.user_id, rate * 100, len(type_feedback),
                )
            return True

        return False

    def toggle_nudge_type(self, nudge_type: str, enabled: bool):
        """Manually enable or disable a nudge type.

        Args:
            nudge_type: Type to toggle.
            enabled: True to enable, False to disable.
        """
        disabled = self.state.setdefault("disabled_types", [])
        if enabled and nudge_type in disabled:
            disabled.remove(nudge_type)
        elif not enabled and nudge_type not in disabled:
            disabled.append(nudge_type)
        self._save_state()


# ---------------------------------------------------------------------------
# Scheduler integration
# ---------------------------------------------------------------------------


def register_nudge_evaluator(manager, user_id: str):
    """Register periodic nudge evaluation with IntegrationManager.

    Registers a 30-minute interval job that runs the nudge evaluation
    cycle for the given user.

    Args:
        manager: IntegrationManager instance.
        user_id: User to evaluate nudges for.
    """
    job_id = f"nudge-eval-{user_id}"

    if manager._scheduler is not None:
        manager._scheduler.add_job(
            lambda: _sync_nudge_cycle(user_id),
            "interval",
            minutes=30,
            id=job_id,
            name=f"Nudge evaluator ({user_id})",
            replace_existing=True,
        )
        logger.info("Registered nudge evaluator for user %s (30-min interval)", user_id)
    else:
        logger.warning("Cannot register nudge evaluator: APScheduler not available")


def _get_upcoming_meetings_from_calendar(user_id: str) -> list:
    """Read upcoming meetings from calendar watcher state.

    Loads the CalendarWatcher's state to get recently detected external
    meetings. Falls back to empty list if calendar not connected.
    """
    try:
        from watcher_calendar import CalendarWatcher
        watcher = CalendarWatcher(user_id)
        upcoming = watcher.check()
        return upcoming
    except Exception as e:
        logger.debug("Cannot read calendar for nudge triggers: %s", e)
        return []


# Global Slack client reference — set by slack_bot.py during startup
_slack_client = None


def set_slack_client(client):
    """Set the Slack client for nudge delivery.

    Called by slack_bot.py during startup to provide the client reference.
    """
    global _slack_client
    _slack_client = client


def _sync_nudge_cycle(user_id: str) -> Optional[dict]:
    """Synchronous wrapper for nudge cycle (used by APScheduler)."""
    import asyncio
    try:
        # Check if an event loop is already running
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Schedule on the running loop (e.g. Slack bot's event loop)
            future = asyncio.run_coroutine_threadsafe(
                run_nudge_cycle(user_id, _slack_client), loop
            )
            return future.result(timeout=30)
        else:
            return asyncio.run(run_nudge_cycle(user_id, _slack_client))
    except Exception as e:
        logger.error("Nudge cycle failed for user %s: %s", user_id, e)
        return None


async def run_nudge_cycle(user_id: str, slack_client=None) -> Optional[dict]:
    """Evaluate all triggers and deliver the top nudge.

    Evaluates all trigger types, filters by should_send(), and delivers
    the single highest-tier nudge via Slack DM. Only one nudge per cycle
    to avoid burst.

    Args:
        user_id: User to evaluate nudges for.
        slack_client: Slack AsyncWebClient for delivery. If None, nudge is
            evaluated but not delivered (useful for testing).

    Returns:
        Delivered nudge dict with 'id' field, or None if nothing to send.
    """
    engine = NudgeEngine(user_id)

    # Collect all candidate nudges from all trigger types
    candidates = []

    # Tier 1: Meeting triggers — read upcoming meetings from calendar watcher state
    try:
        upcoming_meetings = _get_upcoming_meetings_from_calendar(user_id)
        meeting_nudges = engine.evaluate_meeting_triggers(upcoming_meetings)
        candidates.extend(meeting_nudges)
    except Exception as e:
        logger.error("Meeting trigger evaluation failed: %s", e)

    # Tier 2: Relationship triggers
    try:
        relationship_nudges = engine.evaluate_relationship_triggers()
        candidates.extend(relationship_nudges)
    except Exception as e:
        logger.error("Relationship trigger evaluation failed: %s", e)

    # Tier 3: Pattern triggers
    try:
        pattern_nudges = engine.evaluate_pattern_triggers()
        candidates.extend(pattern_nudges)
    except Exception as e:
        logger.error("Pattern trigger evaluation failed: %s", e)

    if not candidates:
        return None

    # Sort by tier (lowest number = highest priority), then by confidence
    def sort_key(nudge):
        tier = NUDGE_TYPES.get(nudge.get("type", ""), {}).get("tier", 99)
        confidence = nudge.get("confidence", 0)
        return (tier, -confidence)

    candidates.sort(key=sort_key)

    # Try to deliver the highest-priority nudge that passes throttling
    for nudge in candidates:
        nudge_type = nudge.get("type", "")
        confidence = nudge.get("confidence", 0)

        if engine.should_send(nudge_type, confidence):
            # Record and deliver
            nudge_id = engine.record_sent(nudge_type, nudge.get("content", ""))
            nudge["id"] = nudge_id

            # Deliver via Slack DM if client available
            if slack_client is not None:
                try:
                    blocks = engine.format_nudge_blocks(nudge)
                    await slack_client.chat_postMessage(
                        channel=user_id,
                        text=nudge.get("content", "You have a new nudge"),
                        blocks=blocks,
                    )
                    logger.info(
                        "Delivered nudge %s (type=%s, confidence=%.2f) to user %s via Slack",
                        nudge_id, nudge_type, confidence, user_id,
                    )
                except Exception as e:
                    logger.error("Failed to deliver nudge %s via Slack: %s", nudge_id, e)
            else:
                logger.info(
                    "Nudge %s (type=%s, confidence=%.2f) ready for user %s (no Slack client)",
                    nudge_id, nudge_type, confidence, user_id,
                )

            return nudge

    return None
