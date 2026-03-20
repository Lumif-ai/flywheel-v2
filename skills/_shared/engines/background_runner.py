"""
background_runner.py - Background skill pre-computation for Flywheel.

Runs as a daemon thread alongside the web app. Scans for work items with
approaching due dates and auto-triggers skill execution so outputs are
ready before the user asks.

Public API:
    BackgroundRunner - Daemon thread class with queue-based execution
    queue_execution(user_id, item_id) - Manually enqueue a work item
    start_runner() - Start the background runner
    stop_runner() - Stop the background runner
"""

import logging
import os
import queue
import sys
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# sys.path setup (same pattern as other src/ modules)
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONCURRENT = 2
SCAN_INTERVAL_SECONDS = 30
TRIGGER_HOURS_BEFORE_DUE = 24
AUTO_PREPARE_DELAY_MINUTES = 5
MAX_RETRIES = 1


# ---------------------------------------------------------------------------
# BackgroundRunner
# ---------------------------------------------------------------------------


class BackgroundRunner:
    """Daemon thread that scans for and executes pending work items.

    Runs a loop every SCAN_INTERVAL_SECONDS that:
    1. Drains the manual queue and spawns execution threads.
    2. Scans for auto-trigger candidates (upcoming items near due date).

    Limits concurrent executions to MAX_CONCURRENT.
    """

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self._queue = queue.Queue()
        self._running = {}  # item_id -> thread
        self._lock = threading.Lock()  # protects _running

    def start(self):
        """Start the background runner daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.info("Background runner already running")
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="flywheel-bg-runner", daemon=True
        )
        self._thread.start()
        logger.info("Background runner started")

    def stop(self):
        """Stop the background runner, joining with 5s timeout."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            logger.info("Background runner stopped")
            self._thread = None

    @property
    def is_running(self) -> bool:
        """Check if the background runner thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def enqueue(self, user_id: str, item_id: str):
        """Add a work item to the execution queue.

        Args:
            user_id: User identifier.
            item_id: Work item ID to execute.
        """
        self._queue.put({"user_id": user_id, "item_id": item_id})
        logger.debug("Enqueued work item %s for user %s", item_id, user_id)

    # -----------------------------------------------------------------------
    # Internal loop
    # -----------------------------------------------------------------------

    def _run(self):
        """Main loop: process queue and scan for triggers on each cycle."""
        logger.info("Background runner loop started")
        while not self._stop.is_set():
            try:
                self._cleanup_finished()
                self._process_queue()
                self._scan_for_triggers()
            except Exception as e:
                logger.error("Background runner cycle error: %s", e)

            # Wait for next cycle or until stopped
            self._stop.wait(SCAN_INTERVAL_SECONDS)

        logger.info("Background runner loop exited")

    def _cleanup_finished(self):
        """Remove finished threads from _running."""
        with self._lock:
            finished = [
                item_id
                for item_id, t in self._running.items()
                if not t.is_alive()
            ]
            for item_id in finished:
                del self._running[item_id]

    def _process_queue(self):
        """Drain the queue and spawn execution threads for each item."""
        while not self._queue.empty():
            with self._lock:
                if len(self._running) >= MAX_CONCURRENT:
                    logger.debug("Max concurrent executions reached, deferring queue")
                    break

            try:
                item_dict = self._queue.get_nowait()
            except queue.Empty:
                break

            item_id = item_dict.get("item_id", "")
            with self._lock:
                if item_id in self._running:
                    continue  # Already running

                t = threading.Thread(
                    target=_execute_item,
                    args=(item_dict,),
                    daemon=True,
                    name=f"bg-exec-{item_id[:8]}",
                )
                self._running[item_id] = t
                t.start()

    def _scan_for_triggers(self):
        """Scan all users for work items that should auto-trigger."""
        try:
            from work_items import WORK_ITEMS_ROOT, list_work_items
        except ImportError:
            return

        root = WORK_ITEMS_ROOT
        if not root.exists():
            return

        now = datetime.now()
        trigger_threshold = now + timedelta(hours=TRIGGER_HOURS_BEFORE_DUE)
        auto_prepare_cutoff = now - timedelta(minutes=AUTO_PREPARE_DELAY_MINUTES)

        try:
            user_dirs = [d.name for d in root.iterdir() if d.is_dir()]
        except OSError:
            return

        for user_id in user_dirs:
            try:
                items = list_work_items(user_id, status="upcoming")
            except Exception as e:
                logger.debug("Error listing items for %s: %s", user_id, e)
                continue

            for item in items:
                item_id = item.id

                # Skip if already running or queued
                with self._lock:
                    if item_id in self._running:
                        continue

                # Skip if no skill to run
                if not item.skill_name:
                    continue

                should_trigger = False

                # Rule 1: Meeting with due_date within 24 hours
                if item.due_date and item.type == "meeting":
                    try:
                        due = datetime.fromisoformat(item.due_date)
                        if due <= trigger_threshold:
                            should_trigger = True
                    except (ValueError, TypeError):
                        pass

                # Rule 2: Item created > 5 minutes ago with auto_prepare flag
                if not should_trigger and item.skill_params.get("auto_prepare"):
                    try:
                        created = datetime.fromisoformat(item.created_at)
                        if created <= auto_prepare_cutoff:
                            should_trigger = True
                    except (ValueError, TypeError):
                        pass

                if should_trigger:
                    self.enqueue(user_id, item_id)


# ---------------------------------------------------------------------------
# Execution function
# ---------------------------------------------------------------------------


def _execute_item(item_dict: dict):
    """Execute a skill for a work item. Runs in a background thread.

    On success: stores result, updates work item to 'ready'.
    On failure: resets to 'upcoming', logs error. Retries once.

    Args:
        item_dict: Dict with 'user_id' and 'item_id' keys.
    """
    user_id = item_dict.get("user_id", "")
    item_id = item_dict.get("item_id", "")

    # Lazy imports to avoid circular dependencies
    try:
        from execution_gateway import execute_skill
        from skill_runner_web import store_result
        from work_items import get_work_item, transition_status, update_work_item
    except ImportError as e:
        logger.error("Cannot execute item %s: missing module: %s", item_id, e)
        return

    item = get_work_item(user_id, item_id)
    if item is None:
        logger.warning("Work item %s not found for user %s", item_id, user_id)
        return

    # Transition to preparing
    try:
        transition_status(user_id, item_id, "preparing")
    except ValueError:
        pass  # May already be past upcoming

    retries = 0
    while retries <= MAX_RETRIES:
        try:
            input_text = item.skill_params.get("input_text", item.title)
            result = execute_skill(
                item.skill_name,
                input_text,
                user_id,
                item.skill_params,
            )

            # Store result
            run_id = store_result(user_id, result)

            # Update work item to ready
            update_work_item(
                user_id,
                item_id,
                status="ready",
                skill_output_id=run_id,
            )

            logger.info(
                "Background execution complete for %s (item %s), run_id=%s",
                item.skill_name,
                item_id[:8],
                run_id,
            )
            return  # Success

        except Exception as e:
            retries += 1
            if retries > MAX_RETRIES:
                logger.error(
                    "Background execution failed for item %s after %d retries: %s",
                    item_id[:8],
                    MAX_RETRIES + 1,
                    e,
                )
                # Reset to upcoming so it can be retried later
                try:
                    update_work_item(user_id, item_id, status="upcoming")
                except Exception:
                    pass
            else:
                logger.warning(
                    "Background execution retry %d for item %s: %s",
                    retries,
                    item_id[:8],
                    e,
                )
                time.sleep(2)  # Brief pause before retry


# ---------------------------------------------------------------------------
# Public API (module-level singleton)
# ---------------------------------------------------------------------------

_runner = None
_runner_lock = threading.Lock()


def queue_execution(user_id: str, item_id: str):
    """Add a work item to the background execution queue.

    Called by web routes when a user creates a work item that should
    be pre-computed. Safe to call even if runner is not started.

    Args:
        user_id: User identifier.
        item_id: Work item ID.
    """
    global _runner
    with _runner_lock:
        if _runner is not None and _runner.is_running:
            _runner.enqueue(user_id, item_id)
        else:
            logger.debug("Runner not active, item %s not queued", item_id)


def start_runner():
    """Create and start the background runner if not already running."""
    global _runner
    with _runner_lock:
        if _runner is None:
            _runner = BackgroundRunner()
        if not _runner.is_running:
            _runner.start()


def stop_runner():
    """Stop the background runner if running."""
    global _runner
    with _runner_lock:
        if _runner is not None:
            _runner.stop()
