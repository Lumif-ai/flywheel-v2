"""
scheduler.py - Recurring skill execution scheduler for Flywheel.

Provides schedule management (CRUD) and a daemon SchedulerThread that
fires skill runs at configured times. Schedules persist as JSON per user.

Public API:
    Schedule - Pydantic model for a recurring schedule
    SchedulerThread - Daemon thread that checks and triggers due schedules
    create_schedule(user_id, skill_name, frequency, **kwargs) -> Schedule
    list_schedules(user_id) -> list[Schedule]
    update_schedule(user_id, schedule_id, **updates) -> Optional[Schedule]
    delete_schedule(user_id, schedule_id) -> bool
    compute_next_run(schedule) -> str
"""

import json
import logging
import os
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# sys.path setup (same pattern as other src/ modules)
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

# ---------------------------------------------------------------------------
# Configurable root for test isolation (same pattern as work_items.py)
# ---------------------------------------------------------------------------

SCHEDULES_ROOT = Path.home() / ".claude" / "users"

# ---------------------------------------------------------------------------
# Schedule model
# ---------------------------------------------------------------------------


class Schedule(BaseModel):
    """A recurring skill execution schedule."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    skill_name: str
    params: dict = Field(default_factory=dict)
    frequency: str  # "daily" | "weekly" | "biweekly" | "monthly"
    day_of_week: Optional[int] = None  # 0=Monday, 6=Sunday (for weekly/biweekly)
    time: str = "06:00"  # HH:MM
    enabled: bool = True
    last_run: Optional[str] = None  # ISO datetime
    next_run: Optional[str] = None  # ISO datetime
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    description: str = ""  # Human-readable description


# ---------------------------------------------------------------------------
# Suggested schedule templates
# ---------------------------------------------------------------------------

SUGGESTED_SCHEDULES = [
    {
        "skill_name": "meeting-prep",
        "frequency": "daily",
        "time": "06:00",
        "description": "Prepare briefs for today's meetings",
    },
    {
        "skill_name": "company-fit-analyzer",
        "frequency": "weekly",
        "day_of_week": 0,
        "time": "08:00",
        "description": "Refresh competitive intelligence",
    },
    {
        "skill_name": "investor-update",
        "frequency": "monthly",
        "time": "09:00",
        "description": "Generate monthly investor update",
    },
]

# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _schedules_path(user_id: str) -> Path:
    """Return the path to a user's schedules.json file."""
    return Path(SCHEDULES_ROOT) / user_id / "schedules.json"


def _load_schedules(user_id: str) -> list:
    """Load schedules from JSON file. Returns empty list on error."""
    path = _schedules_path(user_id)
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            return data
        logger.warning("schedules.json for %s is not a list, returning empty", user_id)
        return []
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load schedules.json for %s: %s", user_id, e)
        return []


def _save_schedules(user_id: str, schedules: list) -> None:
    """Atomic write of schedules list to JSON file."""
    path = _schedules_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(schedules, indent=2, default=str)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix="schedules_"
    )
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Next-run computation
# ---------------------------------------------------------------------------


def compute_next_run(schedule: Schedule) -> str:
    """Compute the next run time for a schedule.

    Based on frequency, day_of_week, time:
    - daily: tomorrow at configured time
    - weekly: next occurrence of day_of_week at configured time
    - biweekly: 14 days from last_run (or next day_of_week if no last_run)
    - monthly: same day next month at configured time

    Returns:
        ISO format datetime string.
    """
    now = datetime.now()

    # Parse configured time
    try:
        hour, minute = map(int, schedule.time.split(":"))
    except (ValueError, AttributeError):
        hour, minute = 6, 0

    freq = schedule.frequency

    if freq == "daily":
        # Next day at configured time
        next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_dt <= now:
            next_dt += timedelta(days=1)
        return next_dt.isoformat()

    elif freq == "weekly":
        target_dow = schedule.day_of_week if schedule.day_of_week is not None else 0
        next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = target_dow - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        # If same day but time passed, go to next week
        if days_ahead == 0 and next_dt <= now:
            days_ahead = 7
        next_dt += timedelta(days=days_ahead)
        return next_dt.isoformat()

    elif freq == "biweekly":
        if schedule.last_run:
            try:
                last = datetime.fromisoformat(schedule.last_run)
                next_dt = last + timedelta(days=14)
                next_dt = next_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_dt <= now:
                    # If past, schedule for tomorrow
                    next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    next_dt += timedelta(days=1)
                return next_dt.isoformat()
            except (ValueError, TypeError):
                pass
        # No last_run: fall back to weekly logic
        target_dow = schedule.day_of_week if schedule.day_of_week is not None else 0
        next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = target_dow - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_dt += timedelta(days=days_ahead)
        return next_dt.isoformat()

    elif freq == "monthly":
        # Same day next month
        year = now.year
        month = now.month + 1
        if month > 12:
            month = 1
            year += 1
        day = min(now.day, 28)  # Safe day for all months
        next_dt = datetime(year, month, day, hour, minute, 0)
        return next_dt.isoformat()

    # Fallback: tomorrow
    next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    next_dt += timedelta(days=1)
    return next_dt.isoformat()


# ---------------------------------------------------------------------------
# CRUD functions
# ---------------------------------------------------------------------------


def create_schedule(
    user_id: str,
    skill_name: str,
    frequency: str,
    **kwargs,
) -> Schedule:
    """Create and persist a new schedule.

    Args:
        user_id: User identifier.
        skill_name: Skill to execute on schedule.
        frequency: "daily" | "weekly" | "biweekly" | "monthly".
        **kwargs: Additional Schedule fields (time, day_of_week, params, description).

    Returns:
        The newly created Schedule.
    """
    schedule = Schedule(
        user_id=user_id,
        skill_name=skill_name,
        frequency=frequency,
        **kwargs,
    )
    schedule.next_run = compute_next_run(schedule)

    schedules = _load_schedules(user_id)
    schedules.append(schedule.model_dump())
    _save_schedules(user_id, schedules)

    logger.info(
        "Created schedule %s for user %s: %s %s at %s",
        schedule.id[:8],
        user_id,
        schedule.frequency,
        schedule.skill_name,
        schedule.time,
    )
    return schedule


def list_schedules(user_id: str) -> list:
    """List all schedules for a user.

    Returns:
        List of Schedule objects, sorted by next_run ascending.
    """
    raw = _load_schedules(user_id)
    result = []
    for data in raw:
        try:
            result.append(Schedule(**data))
        except Exception as e:
            logger.warning("Skipping invalid schedule: %s", e)

    result.sort(key=lambda s: s.next_run or "")
    return result


def update_schedule(
    user_id: str, schedule_id: str, **updates
) -> Optional[Schedule]:
    """Update fields on a schedule.

    Recomputes next_run if frequency, time, or day_of_week changes.

    Returns:
        Updated Schedule if found, None otherwise.
    """
    raw = _load_schedules(user_id)
    recompute_fields = {"frequency", "time", "day_of_week"}

    for i, data in enumerate(raw):
        if data.get("id") == schedule_id:
            data.update(updates)
            raw[i] = data

            # Recompute next_run if schedule timing changed
            if recompute_fields & set(updates.keys()):
                try:
                    sched = Schedule(**data)
                    data["next_run"] = compute_next_run(sched)
                    raw[i] = data
                except Exception:
                    pass

            _save_schedules(user_id, raw)
            try:
                return Schedule(**data)
            except Exception:
                return None

    return None


def delete_schedule(user_id: str, schedule_id: str) -> bool:
    """Remove a schedule by ID.

    Returns:
        True if found and deleted, False otherwise.
    """
    raw = _load_schedules(user_id)
    original_len = len(raw)
    raw = [d for d in raw if d.get("id") != schedule_id]

    if len(raw) < original_len:
        _save_schedules(user_id, raw)
        logger.info("Deleted schedule %s for user", schedule_id[:8])
        return True
    return False


# ---------------------------------------------------------------------------
# SchedulerThread (daemon thread)
# ---------------------------------------------------------------------------


class SchedulerThread:
    """Daemon thread that checks schedules every 60 seconds and triggers due runs.

    Uses the same start/stop pattern as BackgroundRunner.
    """

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        """Start the scheduler daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.info("Scheduler already running")
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="flywheel-scheduler", daemon=True
        )
        self._thread.start()
        logger.info("Scheduler thread started")

    def stop(self):
        """Stop the scheduler, joining with 5s timeout."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            logger.info("Scheduler thread stopped")
            self._thread = None

    @property
    def is_running(self) -> bool:
        """Check if the scheduler thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        """Main loop: check all schedules every 60 seconds."""
        logger.info("Scheduler loop started")
        while not self._stop.is_set():
            try:
                self._check_all_schedules()
            except Exception as e:
                logger.error("Scheduler cycle error: %s", e)

            self._stop.wait(60)  # Check every 60 seconds

        logger.info("Scheduler loop exited")

    def _check_all_schedules(self):
        """Scan all users and trigger due schedules."""
        # Lazy imports to avoid circular dependencies
        try:
            from work_items import create_work_item, WORK_TYPE_SKILLS
            from background_runner import queue_execution
        except ImportError as e:
            logger.debug("Scheduler missing dependency: %s", e)
            return

        root = Path(SCHEDULES_ROOT)
        if not root.exists():
            return

        now = datetime.now()
        now_iso = now.isoformat()

        try:
            user_dirs = [d.name for d in root.iterdir() if d.is_dir()]
        except OSError:
            return

        for user_id in user_dirs:
            try:
                schedules = list_schedules(user_id)
            except Exception as e:
                logger.debug("Error listing schedules for %s: %s", user_id, e)
                continue

            for sched in schedules:
                if not sched.enabled:
                    continue
                if not sched.next_run:
                    continue

                try:
                    next_run_dt = datetime.fromisoformat(sched.next_run)
                except (ValueError, TypeError):
                    continue

                if next_run_dt > now:
                    continue  # Not due yet

                # Schedule is due -- trigger execution
                logger.info(
                    "Triggering scheduled run: %s for user %s (schedule %s)",
                    sched.skill_name,
                    user_id,
                    sched.id[:8],
                )

                # Determine work item type from skill name
                item_type = "custom"
                for wtype, skill in WORK_TYPE_SKILLS.items():
                    if skill == sched.skill_name:
                        item_type = wtype
                        break

                try:
                    # Create a work item for the scheduled run
                    today_str = now.strftime("%Y-%m-%d")
                    work_item = create_work_item(
                        user_id=user_id,
                        type=item_type,
                        title=f"{sched.skill_name} - {today_str}",
                        skill_name=sched.skill_name,
                        skill_params=sched.params,
                    )

                    # Queue for background execution
                    queue_execution(user_id, work_item.id)

                    logger.info(
                        "Queued work item %s for schedule %s",
                        work_item.id[:8],
                        sched.id[:8],
                    )
                except Exception as e:
                    logger.error(
                        "Failed to create work item for schedule %s: %s",
                        sched.id[:8],
                        e,
                    )

                # Update schedule: last_run = now, recompute next_run
                try:
                    updated_sched = Schedule(**sched.model_dump())
                    updated_sched.last_run = now_iso
                    updated_sched.next_run = compute_next_run(updated_sched)
                    update_schedule(
                        user_id,
                        sched.id,
                        last_run=now_iso,
                        next_run=updated_sched.next_run,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to update schedule %s after trigger: %s",
                        sched.id[:8],
                        e,
                    )
