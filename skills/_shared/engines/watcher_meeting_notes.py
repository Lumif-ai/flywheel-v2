"""
watcher_meeting_notes.py - Meeting notes file watcher integration.

Monitors Granola/Fathom export directories for new transcript files (.md, .txt)
and auto-processes them via execute_skill('meeting-processor'). Uses content-hash
deduplication to handle file moves and prevent reprocessing after restarts.

Public API:
    MeetingNotesWatcher - WatcherBase subclass for meeting transcript files
    TranscriptHandler - watchdog FileSystemEventHandler for real-time detection
    create_observer(watcher, loop) -> Observer
    start_file_watcher(user_id, loop) -> Optional[Observer]
"""

import asyncio
import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Import from src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from integration_framework import WatcherBase, is_integration_enabled

logger = logging.getLogger(__name__)

# Graceful import of watchdog (may not be installed)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent

    _WATCHDOG_AVAILABLE = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    FileCreatedEvent = None
    _WATCHDOG_AVAILABLE = False
    logger.warning(
        "watchdog not installed. File watcher will operate in poll-only mode. "
        "Install with: pip3 install watchdog"
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default watch paths for known transcript tools
DEFAULT_WATCH_PATHS = [
    Path.home() / "Documents" / "Granola",
    Path.home() / "Library" / "Application Support" / "Granola",
]

# File extensions to watch for transcripts
TRANSCRIPT_EXTENSIONS = {".md", ".txt"}


# ---------------------------------------------------------------------------
# 1. MeetingNotesWatcher (extends WatcherBase)
# ---------------------------------------------------------------------------


class MeetingNotesWatcher(WatcherBase):
    """Watches for new meeting transcript files in configured directories.

    Extends WatcherBase with file-content-hash deduplication to handle
    file moves (same content at a new path) and restart resilience.

    Args:
        user_id: User identifier.
        custom_paths: Optional list of additional directory paths to watch.
    """

    def __init__(self, user_id: str, custom_paths: list = None):
        self.watch_paths = list(DEFAULT_WATCH_PATHS)
        if custom_paths:
            self.watch_paths.extend([Path(p) for p in custom_paths])
        super().__init__(name="meeting-notes", user_id=user_id)

    def check(self) -> list:
        """Scan watch directories for new transcript files.

        Returns list of dicts with 'id' (content hash), 'path', and 'name'
        for each unprocessed transcript file found.
        """
        items = []
        for watch_dir in self.watch_paths:
            if not watch_dir.is_dir():
                continue
            for entry in watch_dir.iterdir():
                if not entry.is_file():
                    continue
                if entry.suffix.lower() not in TRANSCRIPT_EXTENSIONS:
                    continue
                content_hash = _hash_file(entry)
                if content_hash and not self.is_duplicate(content_hash):
                    items.append({
                        "id": content_hash,
                        "path": str(entry),
                        "name": entry.name,
                    })
        return items

    def process(self, item) -> dict:
        """Process a single transcript file via execute_skill.

        Reads file content and invokes the meeting-processor skill.

        Args:
            item: Dict with 'id', 'path', and 'name' keys.

        Returns:
            Dict with execution result and metadata.
        """
        file_path = Path(item["path"])
        try:
            content = file_path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError) as e:
            logger.error("Failed to read transcript %s: %s", file_path, e)
            return {"status": "error", "error": str(e), "path": str(file_path)}

        # Lazy import to avoid circular dependency at module load
        from execution_gateway import execute_skill

        result = execute_skill(
            "meeting-processor",
            input_text=content,
            user_id=self.user_id,
            params={"source": "auto-watcher", "file_name": item["name"]},
        )

        return {
            "status": "ok",
            "path": str(file_path),
            "name": item["name"],
            "mode": result.mode,
            "duration_ms": result.duration_ms,
            "cost_estimate": 0.10,  # per INTEGRATIONS registry estimate
        }

    def initial_scan(self) -> list:
        """Scan for existing files on startup to catch those created while offline.

        Calls check() to find unprocessed files, then processes each.
        Respects daily cost cap and records triggers for cost tracking.
        Returns list of results from processing.
        """
        from integration_framework import check_daily_cap, record_trigger

        items = self.check()
        results = []
        for item in items:
            try:
                if not check_daily_cap(self.user_id):
                    logger.info("Daily cap reached during initial scan, stopping")
                    break
                result = self.process(item)
                self.mark_processed(item["id"])
                record_trigger(self.user_id, "meeting_notes", 0.10)
                results.append(result)
            except Exception as e:
                logger.error("Initial scan failed for %s: %s", item.get("path"), e)
        return results


# ---------------------------------------------------------------------------
# 2. TranscriptHandler (watchdog FileSystemEventHandler)
# ---------------------------------------------------------------------------


class TranscriptHandler(FileSystemEventHandler):
    """Handles watchdog file creation events for transcript files.

    Schedules watcher.process() on the asyncio event loop when new
    .md/.txt files are created in watched directories.

    Args:
        watcher: MeetingNotesWatcher instance.
        loop: asyncio event loop for scheduling coroutines.
    """

    def __init__(self, watcher: MeetingNotesWatcher, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.watcher = watcher
        self.loop = loop

    def on_created(self, event):
        """Handle file creation events.

        Ignores directories and non-transcript file extensions.
        For valid transcript files, hashes content and schedules processing
        if not already processed.
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path.suffix.lower() not in TRANSCRIPT_EXTENSIONS:
            return

        content_hash = _hash_file(file_path)
        if not content_hash:
            return

        if self.watcher.is_duplicate(content_hash):
            logger.debug("Skipping duplicate file: %s", file_path)
            return

        item = {
            "id": content_hash,
            "path": str(file_path),
            "name": file_path.name,
        }

        # Schedule processing on the event loop
        async def _process():
            try:
                from integration_framework import check_daily_cap, record_trigger
                if not check_daily_cap(self.watcher.user_id):
                    logger.info("Daily cap reached, skipping %s", file_path.name)
                    return None
                result = self.watcher.process(item)
                self.watcher.mark_processed(item["id"])
                record_trigger(self.watcher.user_id, "meeting_notes", 0.10)
                logger.info("Auto-processed transcript: %s", file_path.name)
                return result
            except Exception as e:
                logger.error("Failed to process %s: %s", file_path.name, e)

        asyncio.run_coroutine_threadsafe(_process(), self.loop)


# ---------------------------------------------------------------------------
# 3. Setup functions
# ---------------------------------------------------------------------------


def create_observer(
    watcher: MeetingNotesWatcher, loop: asyncio.AbstractEventLoop
) -> "Optional[Observer]":
    """Create a watchdog Observer for the watcher's directories.

    Attaches a TranscriptHandler to each valid watch directory.
    Returns the Observer (not started) or None if no valid directories
    or watchdog is not installed.

    Args:
        watcher: MeetingNotesWatcher instance.
        loop: asyncio event loop for the TranscriptHandler.

    Returns:
        Observer instance (not started) or None.
    """
    if not _WATCHDOG_AVAILABLE:
        logger.warning("Cannot create observer: watchdog not installed")
        return None

    handler = TranscriptHandler(watcher, loop)
    observer = Observer()

    valid_dirs = 0
    for watch_dir in watcher.watch_paths:
        if watch_dir.is_dir():
            observer.schedule(handler, str(watch_dir), recursive=False)
            valid_dirs += 1
            logger.info("Watching directory: %s", watch_dir)

    if valid_dirs == 0:
        logger.warning(
            "No valid watch directories found. Checked: %s",
            [str(p) for p in watcher.watch_paths],
        )
        return None

    return observer


def start_file_watcher(
    user_id: str, loop: asyncio.AbstractEventLoop, custom_paths: list = None
) -> "Optional[Observer]":
    """Start the meeting notes file watcher for a user.

    Checks integration permission, creates watcher and observer,
    performs initial scan for files created while offline, then
    starts the observer for real-time monitoring.

    Args:
        user_id: User identifier.
        loop: asyncio event loop.
        custom_paths: Optional additional directories to watch.

    Returns:
        Running Observer instance, or None if disabled/unavailable.
    """
    if not is_integration_enabled(user_id, "meeting_notes"):
        logger.info(
            "Meeting notes integration disabled for user %s", user_id
        )
        return None

    watcher = MeetingNotesWatcher(user_id, custom_paths=custom_paths)
    observer = create_observer(watcher, loop)

    if observer is None:
        return None

    # Initial scan for files created while watcher was offline
    logger.info("Running initial scan for user %s...", user_id)
    scan_results = watcher.initial_scan()
    if scan_results:
        logger.info(
            "Initial scan processed %d transcript(s) for user %s",
            len(scan_results),
            user_id,
        )

    # Start real-time monitoring
    observer.start()
    logger.info("Meeting notes file watcher started for user %s", user_id)

    return observer


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _hash_file(path: Path) -> Optional[str]:
    """Compute MD5 hash of file content for deduplication.

    Uses content hash (not path) so file moves are detected as duplicates.

    Args:
        path: Path to the file.

    Returns:
        Hex digest string, or None if file cannot be read.
    """
    try:
        content = path.read_bytes()
        return hashlib.md5(content).hexdigest()
    except (IOError, OSError) as e:
        logger.warning("Cannot hash file %s: %s", path, e)
        return None
