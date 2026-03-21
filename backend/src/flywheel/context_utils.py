"""
context_utils.py - Core context store API for Flywheel.

Provides atomic file I/O, entry parsing/serialization, validation,
and the public read_context() / append_entry() API, plus query_context,
batch_context (multi-file atomic writes), manifest tracking, evidence
deduplication, and contract enforcement.

Internal layering:
  1. Constants and configuration
  2. Data models (dataclasses)
  3. File I/O primitives (lock, read, atomic write)
  4. Entry parsing and serialization (regex-based)
  5. Entry validation
  6. Evidence deduplication
  7. Contract enforcement
  8. Manifest and event logging
  9. Public API (read_context, append_entry, query_context, batch_context)
"""

import contextlib
import copy
import fcntl
import json
import logging
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. Constants and configuration
# ---------------------------------------------------------------------------

CONTEXT_ROOT = Path.home() / ".claude" / "context"
STRICT_MODE = False  # Development mode default
MAX_ENTRY_SIZE = 5000
CONFIDENCE_ORDER = {"high": 3, "medium": 2, "low": 1}
MANIFEST_SNAPSHOT_RETENTION_DAYS = 365
MAX_EVENT_LOG_LINES = 10000
MAX_EVENT_LOG_ROTATIONS = 3
EVENT_ROTATION_CHECK_INTERVAL = 100
WATERMARK_EXPIRY_DAYS = 90

logger = logging.getLogger("context_utils")
logger.setLevel(logging.DEBUG)

# Add a NullHandler so we don't get "No handlers could be found" warnings
# when the caller hasn't configured logging.
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

# Module-level counter for event log rotation check interval
_event_log_counter = 0


def _enforce_containment(file: str) -> Path:
    """Resolve file path and reject if it escapes CONTEXT_ROOT.

    Prevents path traversal via '../' or absolute paths.
    Returns the resolved Path on success.
    Raises ValueError if the resolved path is outside CONTEXT_ROOT.
    """
    root = CONTEXT_ROOT.resolve()
    resolved = (CONTEXT_ROOT / file).resolve()
    root_str = str(root) + os.sep
    if resolved != root and not str(resolved).startswith(root_str):
        raise ValueError(
            "Path traversal blocked: '%s' resolves outside CONTEXT_ROOT" % file
        )
    return resolved

# ---------------------------------------------------------------------------
# 2. Data models
# ---------------------------------------------------------------------------


@dataclass
class ContextEntry:
    """A single dated entry in a context file."""
    date: datetime
    source: str
    detail: str
    content: List[str] = field(default_factory=list)
    evidence_count: int = 1
    confidence: str = "low"
    last_validated: Optional[datetime] = None
    supersedes: Optional[str] = None
    effectiveness_score: Optional[float] = None


@dataclass
class ValidationResult:
    """Result of validating an entry before write."""
    ok: bool
    errors: List[str]


@dataclass
class FileHeader:
    """File-level metadata extracted from italicized header lines."""
    owner: str = ""
    last_updated: Optional[str] = None
    updated_by: Optional[str] = None
    entry_cap: Optional[int] = None


class ContractViolation(PermissionError):
    """Raised when an agent accesses a file not declared in its contract."""
    pass


# ---------------------------------------------------------------------------
# 3. File I/O primitives
# ---------------------------------------------------------------------------


def acquire_lock(file_path: Path, timeout: float = 5.0, exclusive: bool = True) -> int:
    """Acquire advisory file lock on a separate .lock file.

    Uses fcntl.flock with non-blocking tries and 50ms retry interval.
    Returns the file descriptor for the lock file.
    Raises TimeoutError if lock cannot be acquired within timeout.
    """
    lock_path = Path(str(file_path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT)

    lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    deadline = time.monotonic() + timeout

    while True:
        try:
            fcntl.flock(fd, lock_type | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                raise TimeoutError(
                    "Could not acquire lock on %s within %ss" % (file_path, timeout)
                )
            time.sleep(0.05)


def release_lock(fd: int) -> None:
    """Release advisory file lock and close the file descriptor."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def atomic_write(target_path: Path, content: str) -> None:
    """Write content atomically using temp file + os.fsync + os.replace."""
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = None
    try:
        fd_handle = tempfile.NamedTemporaryFile(
            mode="w", dir=str(target_dir), suffix=".tmp",
            delete=False, encoding="utf-8"
        )
        tmp_path = Path(fd_handle.name)
        fd_handle.write(content)
        fd_handle.flush()
        os.fsync(fd_handle.fileno())
        fd_handle.close()
        os.replace(str(tmp_path), str(target_path))
    except Exception:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
        raise


def safe_read(file_path: Path) -> str:
    """Return file content as string, or empty string if file does not exist."""
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


# ---------------------------------------------------------------------------
# 4. Entry parsing and serialization (regex-based)
# ---------------------------------------------------------------------------

# Entry header: [2026-03-09 | source: meeting-processor | call: John Smith @ ABC Corp]
ENTRY_HEADER_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2})\s*\|\s*source:\s*([^|\]]+?)(?:\s*\|\s*(.+?))?\]"
)

# Metadata lines within entries
EVIDENCE_COUNT_RE = re.compile(r"-\s*Evidence_count:\s*(\d+)", re.IGNORECASE)
CONFIDENCE_RE = re.compile(r"-\s*Confidence:\s*(\w+)", re.IGNORECASE)
SUPERSEDES_RE = re.compile(r"-\s*Supersedes:\s*(.+)", re.IGNORECASE)
LAST_VALIDATED_RE = re.compile(
    r"-\s*Last_validated:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE
)
EFFECTIVENESS_RE = re.compile(
    r"-\s*Effectiveness_score:\s*([\d.]+)", re.IGNORECASE
)

# File header metadata (italicized lines)
FILE_OWNER_RE = re.compile(r"^_owner:\s*(.+?)_$", re.MULTILINE)
FILE_UPDATED_RE = re.compile(r"^_last_updated:\s*(.+?)_$", re.MULTILINE)
FILE_UPDATED_BY_RE = re.compile(r"^_updated_by:\s*(.+?)_$", re.MULTILINE)
FILE_ENTRY_CAP_RE = re.compile(r"^_entry_cap:\s*(\d+)_$", re.MULTILINE)


def parse_file_header(content: str) -> FileHeader:
    """Extract file-level metadata from italicized header lines."""
    header = FileHeader()

    m = FILE_OWNER_RE.search(content)
    if m:
        header.owner = m.group(1).strip()

    m = FILE_UPDATED_RE.search(content)
    if m:
        header.last_updated = m.group(1).strip()

    m = FILE_UPDATED_BY_RE.search(content)
    if m:
        header.updated_by = m.group(1).strip()

    m = FILE_ENTRY_CAP_RE.search(content)
    if m:
        header.entry_cap = int(m.group(1))

    return header


def parse_context_file(content: str) -> List[ContextEntry]:
    """Parse a context file into a list of ContextEntry objects.

    Splits content by entry headers, extracts metadata from each entry body.
    Returns empty list for empty or unparseable content.
    """
    if not content or not content.strip():
        return []

    entries = []  # type: List[ContextEntry]

    # Find all entry header positions
    header_matches = list(ENTRY_HEADER_RE.finditer(content))
    if not header_matches:
        return []

    for i, match in enumerate(header_matches):
        # Extract the body: from end of header line to start of next header (or end of content)
        header_end = match.end()
        if i + 1 < len(header_matches):
            body_end = header_matches[i + 1].start()
        else:
            body_end = len(content)

        body = content[header_end:body_end]

        # Parse header fields
        date_str = match.group(1)
        source = match.group(2).strip()
        detail = match.group(3).strip() if match.group(3) else ""

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue  # Skip entries with unparseable dates

        # Parse metadata from body
        evidence_count = 1
        confidence = "low"
        last_validated = None  # type: Optional[datetime]
        supersedes = None  # type: Optional[str]
        effectiveness_score = None  # type: Optional[float]
        content_lines = []  # type: List[str]

        for line in body.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            # Check metadata patterns first
            ev_match = EVIDENCE_COUNT_RE.match(stripped)
            if ev_match:
                evidence_count = int(ev_match.group(1))
                continue

            conf_match = CONFIDENCE_RE.match(stripped)
            if conf_match:
                confidence = conf_match.group(1).lower()
                continue

            sup_match = SUPERSEDES_RE.match(stripped)
            if sup_match:
                supersedes = sup_match.group(1).strip()
                continue

            lv_match = LAST_VALIDATED_RE.match(stripped)
            if lv_match:
                try:
                    last_validated = datetime.strptime(lv_match.group(1), "%Y-%m-%d")
                except ValueError:
                    pass
                continue

            eff_match = EFFECTIVENESS_RE.match(stripped)
            if eff_match:
                try:
                    effectiveness_score = float(eff_match.group(1))
                except ValueError:
                    pass
                continue

            # Regular content line (strip leading "- " if present)
            if stripped.startswith("- "):
                content_lines.append(stripped[2:])
            elif stripped.startswith("-"):
                content_lines.append(stripped[1:].strip())
            else:
                # Non-list content line; include as-is
                content_lines.append(stripped)

        entry = ContextEntry(
            date=date,
            source=source,
            detail=detail,
            content=content_lines,
            evidence_count=evidence_count,
            confidence=confidence,
            last_validated=last_validated,
            supersedes=supersedes,
            effectiveness_score=effectiveness_score,
        )
        entries.append(entry)

    return entries


def serialize_entries(
    entries: List[ContextEntry],
    header: Optional[FileHeader] = None,
    title: Optional[str] = None,
) -> str:
    """Serialize entries back to markdown format.

    Produces output that round-trips with parse_context_file.
    """
    parts = []  # type: List[str]

    # File header
    if title:
        parts.append("# %s" % title)
        parts.append("")

    if header:
        if header.owner:
            parts.append("_owner: %s_" % header.owner)
        if header.last_updated:
            parts.append("_last_updated: %s_" % header.last_updated)
        if header.updated_by:
            parts.append("_updated_by: %s_" % header.updated_by)
        if header.entry_cap is not None:
            parts.append("_entry_cap: %d_" % header.entry_cap)
        parts.append("")

    # Entries
    for i, entry in enumerate(entries):
        if i > 0 or parts:
            parts.append("")

        # Header line
        date_str = entry.date.strftime("%Y-%m-%d")
        if entry.detail:
            parts.append("[%s | source: %s | %s]" % (date_str, entry.source, entry.detail))
        else:
            parts.append("[%s | source: %s]" % (date_str, entry.source))

        # Content lines
        for line in entry.content:
            parts.append("- %s" % line)

        # Metadata lines
        if entry.evidence_count != 1:
            parts.append("- Evidence_count: %d" % entry.evidence_count)
        parts.append("- Confidence: %s" % entry.confidence)

        if entry.last_validated is not None:
            parts.append("- Last_validated: %s" % entry.last_validated.strftime("%Y-%m-%d"))

        if entry.supersedes is not None:
            parts.append("- Supersedes: %s" % entry.supersedes)

        if entry.effectiveness_score is not None:
            parts.append("- Effectiveness_score: %s" % entry.effectiveness_score)

    result = "\n".join(parts)
    if result and not result.endswith("\n"):
        result += "\n"

    return result


# ---------------------------------------------------------------------------
# 5. Entry validation
# ---------------------------------------------------------------------------


def validate_entry_format(entry: dict) -> ValidationResult:
    """Validate an entry dict before writing. Rejects malformed entries."""
    errors = []  # type: List[str]

    # Required fields
    if "source" not in entry:
        errors.append("Missing required field: 'source'")
    if "date" not in entry:
        errors.append("Missing required field: 'date'")
    if "confidence" not in entry:
        errors.append("Missing required field: 'confidence'")

    # Date format
    date_str = entry.get("date", "")
    if date_str and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_str)):
        errors.append("Invalid date format: '%s'. Expected YYYY-MM-DD." % date_str)

    # Confidence level
    confidence = entry.get("confidence", "")
    if confidence and str(confidence).lower() not in ("high", "medium", "low"):
        errors.append(
            "Invalid confidence: '%s'. Must be high/medium/low." % confidence
        )

    # Size limit
    content_str = str(entry)
    if len(content_str) > MAX_ENTRY_SIZE:
        errors.append(
            "Entry exceeds max size (%d > %d chars)" % (len(content_str), MAX_ENTRY_SIZE)
        )

    # Injection prevention: content cannot contain entry header patterns
    content = entry.get("content", "")
    if isinstance(content, str) and re.search(
        r"^\[?\d{4}-\d{2}-\d{2}\s*\|", content, re.MULTILINE
    ):
        errors.append("Entry content contains patterns that look like entry headers")
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str) and re.search(
                r"^\[?\d{4}-\d{2}-\d{2}\s*\|", item
            ):
                errors.append(
                    "Entry content contains patterns that look like entry headers"
                )
                break

    # Evidence count must be positive integer
    ev_count = entry.get("evidence_count", 1)
    if not isinstance(ev_count, int) or ev_count < 1:
        errors.append(
            "Invalid evidence_count: %s. Must be positive integer." % ev_count
        )

    return ValidationResult(ok=len(errors) == 0, errors=errors)


# ---------------------------------------------------------------------------
# 6. Evidence deduplication (CORE-08)
# ---------------------------------------------------------------------------


def normalize_source_key(source: str, detail: str, date: str) -> str:
    """Normalize source identifiers for dedup comparison.

    Converts to lowercase, strips whitespace, replaces spaces with hyphens.
    Format: "{source_type}:{normalized_detail}:{date}"
    This prevents "meeting:John Smith:2026-03-09" and
    "meeting:john-smith:2026-03-09" from being treated as different sources.
    """
    norm_source = source.strip().lower().replace(" ", "-")
    norm_detail = detail.strip().lower().replace(" ", "-")
    norm_date = date.strip()
    return "%s:%s:%s" % (norm_source, norm_detail, norm_date)


def should_increment_evidence(existing_content: str, entry: dict, source: str) -> bool:
    """Check if this entry duplicates an existing source.

    Parse existing entries and compare normalized source keys.
    Returns True if a matching entry exists (caller should increment
    rather than append).
    """
    existing_entries = parse_context_file(existing_content)
    if not existing_entries:
        return False

    new_key = normalize_source_key(
        source,
        entry.get("detail", ""),
        entry.get("date", ""),
    )

    for existing in existing_entries:
        existing_key = normalize_source_key(
            existing.source,
            existing.detail,
            existing.date.strftime("%Y-%m-%d"),
        )
        if existing_key == new_key:
            return True

    return False


def increment_evidence_in_content(existing_content: str, entry: dict, source: str) -> str:
    """Find the matching entry and increment its Evidence_count.

    Also updates Last_validated to today. Returns modified content string.
    """
    entries = parse_context_file(existing_content)
    file_header = parse_file_header(existing_content)

    new_key = normalize_source_key(
        source,
        entry.get("detail", ""),
        entry.get("date", ""),
    )

    for existing in entries:
        existing_key = normalize_source_key(
            existing.source,
            existing.detail,
            existing.date.strftime("%Y-%m-%d"),
        )
        if existing_key == new_key:
            existing.evidence_count += 1
            existing.last_validated = datetime.now()
            # Merge new content items if they add information
            new_content = entry.get("content", [])
            if isinstance(new_content, str):
                new_content = [new_content]
            for item in new_content:
                if item not in existing.content:
                    existing.content.append(item)
            break

    # Extract title from existing content
    title = None
    title_match = re.match(r"^#\s+(.+)$", existing_content, re.MULTILINE)
    if title_match:
        title = title_match.group(1)

    return serialize_entries(entries, header=file_header, title=title)


# ---------------------------------------------------------------------------
# 7. Contract enforcement (CORE-10)
# ---------------------------------------------------------------------------


def load_agent_contract(agent_id: str) -> dict:
    """Load an agent's declared reads/writes from its SKILL.md.

    Looks for SKILL.md in ~/.claude/skills/{agent_id}/. Parses YAML
    frontmatter to extract context.reads and context.writes lists.
    If no SKILL.md found, returns development default with full access.
    """
    skill_path = Path.home() / ".claude" / "skills" / agent_id / "SKILL.md"

    if not skill_path.exists():
        # Development default: full access (per research Open Question 4)
        return {"reads": ["*"], "writes": ["*"], "auth_level": "admin"}

    try:
        content = skill_path.read_text(encoding="utf-8")
        # Parse YAML frontmatter between --- markers
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            return {"reads": ["*"], "writes": ["*"], "auth_level": "admin"}

        fm_text = fm_match.group(1)

        # Simple YAML parsing for context.reads and context.writes
        reads = []  # type: List[str]
        writes = []  # type: List[str]
        in_reads = False
        in_writes = False

        for line in fm_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("reads:"):
                in_reads = True
                in_writes = False
                continue
            elif stripped.startswith("writes:"):
                in_writes = True
                in_reads = False
                continue
            elif stripped and not stripped.startswith("-"):
                in_reads = False
                in_writes = False

            if in_reads and stripped.startswith("- "):
                reads.append(stripped[2:].strip().strip('"').strip("'"))
            elif in_writes and stripped.startswith("- "):
                writes.append(stripped[2:].strip().strip('"').strip("'"))

        return {
            "reads": reads if reads else ["*"],
            "writes": writes if writes else ["*"],
            "auth_level": "agent",
        }
    except Exception as e:
        logger.warning("Failed to load contract for %s: %s", agent_id, e)
        return {"reads": ["*"], "writes": ["*"], "auth_level": "admin"}


def check_read_allowed(file: str, agent_id: str) -> None:
    """Verify file is in agent's declared reads.

    In STRICT_MODE, raises ContractViolation for undeclared access.
    In development mode (default), logs a warning but allows access.
    """
    contract = load_agent_contract(agent_id)
    reads = contract.get("reads", ["*"])

    if reads == ["*"]:
        return  # Full access

    if file not in reads and not any(_glob_match(file, pattern) for pattern in reads):
        if STRICT_MODE:
            raise ContractViolation(
                "%s not authorized to read %s (declared reads: %s)"
                % (agent_id, file, reads)
            )
        else:
            logger.warning(
                "CONTRACT: %s reading undeclared file %s (dev mode, allowing)",
                agent_id, file,
            )


def check_write_allowed(file: str, agent_id: str) -> None:
    """Verify file is in agent's declared writes.

    In STRICT_MODE, raises ContractViolation for undeclared access.
    In development mode (default), logs a warning but allows access.
    """
    contract = load_agent_contract(agent_id)
    writes = contract.get("writes", ["*"])

    if writes == ["*"]:
        return  # Full access

    if file not in writes and not any(_glob_match(file, pattern) for pattern in writes):
        if STRICT_MODE:
            raise ContractViolation(
                "%s not authorized to write %s (declared writes: %s)"
                % (agent_id, file, writes)
            )
        else:
            logger.warning(
                "CONTRACT: %s writing undeclared file %s (dev mode, allowing)",
                agent_id, file,
            )


def _glob_match(file: str, pattern: str) -> bool:
    """Simple glob matching for contract patterns (supports * and **)."""
    import fnmatch
    return fnmatch.fnmatch(file, pattern)


# ---------------------------------------------------------------------------
# 8. Manifest and event logging (CORE-05, CORE-06)
# ---------------------------------------------------------------------------


def parse_manifest(content: str) -> dict:
    """Parse manifest content into a structured dict.

    Returns dict with schema_version (int) and registry (dict of
    file -> {owner, updated, updated_by, entry_count, operation}).
    """
    manifest = {"schema_version": 1, "registry": {}}  # type: dict

    if not content or not content.strip():
        return manifest

    # Parse schema version
    version_match = re.search(r"schema_version:\s*(\d+)", content)
    if version_match:
        manifest["schema_version"] = int(version_match.group(1))

    # Parse registry table rows: | file | updated | updated_by | operation |
    table_re = re.compile(
        r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
        re.MULTILINE,
    )
    for match in table_re.finditer(content):
        file_name = match.group(1).strip()
        # Skip header row and separator
        if file_name in ("File", "---", "----") or file_name.startswith("---"):
            continue
        manifest["registry"][file_name] = {
            "updated": match.group(2).strip(),
            "updated_by": match.group(3).strip(),
            "operation": match.group(4).strip(),
        }

    return manifest


def serialize_manifest(manifest: dict) -> str:
    """Produce manifest markdown with the registry table."""
    lines = [
        "# Context Manifest",
        "",
        "_schema_version: %d_" % manifest.get("schema_version", 1),
        "",
        "## Registry",
        "",
        "| File | Updated | Updated By | Operation |",
        "|------|---------|------------|-----------|",
    ]

    registry = manifest.get("registry", {})
    for file_name in sorted(registry.keys()):
        entry = registry[file_name]
        lines.append("| %s | %s | %s | %s |" % (
            file_name,
            entry.get("updated", ""),
            entry.get("updated_by", ""),
            entry.get("operation", ""),
        ))

    lines.append("")
    return "\n".join(lines)


def update_manifest(file: str, agent_id: str, operation: str = "write") -> None:
    """Update manifest with file write record.

    Backs up existing manifest, then updates registry entry with
    timestamp, agent_id, and operation type, then creates post-write backup.
    """
    manifest_path = CONTEXT_ROOT / "_manifest.md"

    # 1. Backup existing manifest before modification (if it exists)
    backup_manifest()

    # 2. Acquire lock on manifest (longer timeout than default to avoid
    #    false failures under concurrent skill runs -- see backlog #5)
    lock_fd = acquire_lock(manifest_path, timeout=10.0)

    try:
        # 3. Read and parse (create if not exists)
        content = safe_read(manifest_path)
        manifest = parse_manifest(content)

        # 4. Update registry entry
        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest["registry"][file] = {
            "updated": now_str,
            "updated_by": agent_id,
            "operation": operation,
        }

        # 5. Serialize and write atomically
        new_content = serialize_manifest(manifest)
        atomic_write(manifest_path, new_content)

    finally:
        release_lock(lock_fd)

    # 6. Post-write backup (ensures .bak exists even on first manifest creation)
    backup_manifest()


def backup_manifest() -> None:
    """Backup manifest: .bak on every write, daily snapshot with 365-day retention."""
    manifest_path = CONTEXT_ROOT / "_manifest.md"

    if not manifest_path.exists():
        return

    # 1. Always create .bak copy
    bak_path = CONTEXT_ROOT / "_manifest.md.bak"
    shutil.copy2(str(manifest_path), str(bak_path))

    # 2. Daily snapshot (only if today's does not exist)
    snapshot_dir = CONTEXT_ROOT / "_backups" / "manifest-snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_snapshot = snapshot_dir / ("%s.md" % today_str)

    if not today_snapshot.exists():
        shutil.copy2(str(manifest_path), str(today_snapshot))

    # 3. Clean up snapshots older than retention period
    cutoff = datetime.now() - timedelta(days=MANIFEST_SNAPSHOT_RETENTION_DAYS)
    for snapshot_file in snapshot_dir.iterdir():
        if not snapshot_file.name.endswith(".md"):
            continue
        try:
            snap_date = datetime.strptime(snapshot_file.stem, "%Y-%m-%d")
            if snap_date < cutoff:
                snapshot_file.unlink()
        except ValueError:
            continue  # Skip files with non-date names


def log_event(event_type: str, file: str, agent_id: str, detail: str = "") -> None:
    """Append an event to the _events.jsonl log file.

    One JSON object per line for easy atomic appends and parsing.
    Triggers rotation check every EVENT_ROTATION_CHECK_INTERVAL calls.

    Concurrency note: appends without holding the event log lock. Under
    concurrent multi-process access, events may land in a rotated archive
    if rotation occurs between open() and write(). This is safe —
    read_event_log() scans all files (rotated + current), and POSIX
    guarantees atomic appends under PIPE_BUF (4096 bytes). See backlog #7.
    """
    global _event_log_counter

    events_path = CONTEXT_ROOT / "_events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": event_type,
        "file": file,
        "agent_id": agent_id,
        "detail": detail,
    }

    # Append atomically (single line write is atomic on most filesystems)
    with open(str(events_path), "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

    _event_log_counter += 1
    if _event_log_counter % EVENT_ROTATION_CHECK_INTERVAL == 0:
        rotate_event_log_if_needed()


# ---------------------------------------------------------------------------
# 8b. Event log rotation, reading, and watermark polling
# ---------------------------------------------------------------------------


def rotate_event_log_if_needed() -> bool:
    """Rotate _events.jsonl if it exceeds MAX_EVENT_LOG_LINES.

    Rotation scheme: current -> .1, .1 -> .2, .2 -> .3.
    Keeps at most MAX_EVENT_LOG_ROTATIONS archived files.
    Also cleans up watermarks older than WATERMARK_EXPIRY_DAYS during rotation.
    Returns True if rotation occurred, False otherwise.
    """
    events_path = CONTEXT_ROOT / "_events.jsonl"
    if not events_path.exists():
        return False

    fd = acquire_lock(events_path)
    try:
        # Count lines
        line_count = 0
        with open(str(events_path), "r", encoding="utf-8") as f:
            for _ in f:
                line_count += 1

        if line_count < MAX_EVENT_LOG_LINES:
            return False

        # Rotate: shift existing archives up by one
        for i in range(MAX_EVENT_LOG_ROTATIONS, 0, -1):
            src = Path(str(events_path) + f".{i}")
            if i == MAX_EVENT_LOG_ROTATIONS:
                # Delete the oldest if it exists
                if src.exists():
                    src.unlink()
            else:
                dst = Path(str(events_path) + f".{i + 1}")
                if src.exists():
                    shutil.move(str(src), str(dst))

        # Move current to .1
        shutil.move(str(events_path), str(events_path) + ".1")

        # Create fresh empty file
        events_path.touch()

        # Clean up old watermarks during rotation
        _clean_expired_watermarks()

        return True
    finally:
        release_lock(fd)


def _clean_expired_watermarks() -> None:
    """Remove watermarks older than WATERMARK_EXPIRY_DAYS from _watermarks.json."""
    watermarks_path = CONTEXT_ROOT / "_watermarks.json"
    if not watermarks_path.exists():
        return

    try:
        with open(str(watermarks_path), "r", encoding="utf-8") as f:
            watermarks = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    cutoff = datetime.now() - timedelta(days=WATERMARK_EXPIRY_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    cleaned = {k: v for k, v in watermarks.items() if v > cutoff_str}
    if len(cleaned) < len(watermarks):
        atomic_write(watermarks_path, json.dumps(cleaned, indent=2) + "\n")


def read_event_log(
    since: Optional[str] = None,
    event_types: Optional[List[str]] = None,
    files: Optional[List[str]] = None,
) -> List[dict]:
    """Read events from _events.jsonl and rotated archives.

    Reads rotated files (.3, .2, .1) first (oldest), then current file,
    returning events in chronological order.

    Args:
        since: ISO timestamp string; only return events with timestamp > since.
        event_types: If provided, only return events matching these types.
        files: If provided, only return events for these file names.

    Returns:
        List of event dicts in chronological order.
    """
    events_path = CONTEXT_ROOT / "_events.jsonl"
    results: List[dict] = []

    # Build ordered list of files: oldest rotated first, then current
    paths_to_read: List[Path] = []
    for i in range(MAX_EVENT_LOG_ROTATIONS, 0, -1):
        rotated = Path(str(events_path) + f".{i}")
        if rotated.exists():
            paths_to_read.append(rotated)
    if events_path.exists():
        paths_to_read.append(events_path)

    for path in paths_to_read:
        with open(str(path), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue  # Skip malformed lines

                # Apply filters
                if since is not None and event.get("timestamp", "") <= since:
                    continue
                if event_types is not None and event.get("event_type") not in event_types:
                    continue
                if files is not None and event.get("file") not in files:
                    continue

                results.append(event)

    return results


def get_watermark(agent_id: str) -> Optional[str]:
    """Get the last-read watermark timestamp for an agent.

    Reads from _watermarks.json in CONTEXT_ROOT (accessed at call time
    for test isolation).

    Returns:
        ISO timestamp string, or None if no watermark exists.
    """
    watermarks_path = CONTEXT_ROOT / "_watermarks.json"
    if not watermarks_path.exists():
        return None

    try:
        with open(str(watermarks_path), "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return None
            watermarks = json.loads(content)
    except (json.JSONDecodeError, IOError):
        return None

    return watermarks.get(agent_id)


def set_watermark(agent_id: str, timestamp: str) -> None:
    """Set the last-read watermark timestamp for an agent.

    Persists to _watermarks.json with advisory locking for concurrency safety.
    Uses atomic write (temp + os.replace) for crash safety.
    """
    watermarks_path = CONTEXT_ROOT / "_watermarks.json"
    watermarks_path.parent.mkdir(parents=True, exist_ok=True)

    fd = acquire_lock(watermarks_path)
    try:
        watermarks: Dict[str, str] = {}
        if watermarks_path.exists():
            try:
                with open(str(watermarks_path), "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        watermarks = json.loads(content)
            except (json.JSONDecodeError, IOError):
                watermarks = {}

        watermarks[agent_id] = timestamp
        atomic_write(watermarks_path, json.dumps(watermarks, indent=2) + "\n")
    finally:
        release_lock(fd)


def get_pending_events(
    agent_id: str,
    event_types: Optional[List[str]] = None,
    files: Optional[List[str]] = None,
) -> List[dict]:
    """Get all events since the agent's last watermark.

    Reads events since the agent's watermark, then advances the watermark
    to the timestamp of the last returned event.

    Args:
        agent_id: Unique identifier for the polling agent/skill.
        event_types: Optional filter for event types.
        files: Optional filter for file names.

    Returns:
        List of event dicts since last watermark, in chronological order.
    """
    watermark = get_watermark(agent_id)
    events = read_event_log(since=watermark, event_types=event_types, files=files)

    if events:
        set_watermark(agent_id, events[-1]["timestamp"])

    return events


# ---------------------------------------------------------------------------
# 8c. Write verification
# ---------------------------------------------------------------------------


def verify_writes(
    declared: List[str],
    agent_id: str,
    since_minutes: int = 10,
) -> dict:
    """Verify that declared context store writes actually happened.

    Checks _events.jsonl for write events from the given agent_id
    within the time window. Returns declared vs actual vs missing.

    Args:
        declared: List of context file names the skill declares it writes to.
        agent_id: Agent/skill identifier to filter events by.
        since_minutes: Time window in minutes to search for events.

    Returns:
        {"declared": [...], "actual": [...], "missing": [...]}
    """
    try:
        since = (datetime.now() - timedelta(minutes=since_minutes)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        events = read_event_log(since=since, event_types=["append"])
        # Filter by agent_id
        agent_events = [e for e in events if e.get("agent_id") == agent_id]
        actual = list({e["file"] for e in agent_events if "file" in e})
        missing = [f for f in declared if f not in actual]
        return {"declared": list(declared), "actual": actual, "missing": missing}
    except Exception as exc:
        return {
            "declared": list(declared),
            "actual": [],
            "missing": list(declared),
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# 9. Public API: read_context, append_entry, query_context, batch_context
# ---------------------------------------------------------------------------


def format_entry(entry: dict, source: str) -> str:
    """Format an entry dict as a markdown entry string."""
    date_str = entry.get("date", datetime.now().strftime("%Y-%m-%d"))
    detail = entry.get("detail", "")

    # Header line
    if detail:
        header = "[%s | source: %s | %s]" % (date_str, source, detail)
    else:
        header = "[%s | source: %s]" % (date_str, source)

    lines = [header]

    # Content lines
    content = entry.get("content", [])
    if isinstance(content, str):
        content = [content]
    for item in content:
        lines.append("- %s" % item)

    # Metadata lines
    ev_count = entry.get("evidence_count", 1)
    if ev_count != 1:
        lines.append("- Evidence_count: %d" % ev_count)

    confidence = entry.get("confidence", "low")
    lines.append("- Confidence: %s" % confidence)

    last_validated = entry.get("last_validated")
    if last_validated:
        lines.append("- Last_validated: %s" % last_validated)

    supersedes = entry.get("supersedes")
    if supersedes:
        lines.append("- Supersedes: %s" % supersedes)

    effectiveness = entry.get("effectiveness_score")
    if effectiveness is not None:
        lines.append("- Effectiveness_score: %s" % effectiveness)

    return "\n".join(lines)


def list_context_files() -> List[str]:
    """Return list of context file stems (excluding internal files).

    Scans CONTEXT_ROOT for .md files not starting with '_'.

    Returns:
        List of filename strings (e.g. ['positioning.md', 'contacts.md']).
        Returns empty list if CONTEXT_ROOT does not exist.
    """
    if not CONTEXT_ROOT.exists():
        return []
    return [
        f.name
        for f in CONTEXT_ROOT.iterdir()
        if f.is_file() and f.suffix == ".md" and not f.name.startswith("_")
    ]


def read_context(file: str, agent_id: str) -> str:
    """Read a context file and return its raw content.

    Args:
        file: Path relative to CONTEXT_ROOT.
        agent_id: Identifier of the calling agent.

    Returns:
        Raw file content as string, or empty string if file does not exist.

    Raises:
        ContractViolation: If STRICT_MODE and file not in agent's declared reads.
    """
    # Path containment check
    _enforce_containment(file)

    # Contract check
    check_read_allowed(file, agent_id)

    file_path = CONTEXT_ROOT / file
    logger.debug("read_context: file=%s agent=%s", file, agent_id)

    content = safe_read(file_path)
    if not content:
        logger.info("read_context: file does not exist or is empty: %s", file)
    return content


def append_entry(file: str, entry: dict, source: str, agent_id: str) -> str:
    """Append a dated entry to a context file with full safety.

    Flow: contract check -> validate -> lock -> read -> dedup check ->
          format/increment -> append -> atomic write -> post-validate ->
          manifest update -> event log -> unlock.

    Args:
        file: Path relative to CONTEXT_ROOT.
        entry: Dict with date, source, confidence, content, etc.
        source: Source identifier for the entry header.
        agent_id: Identifier of the calling agent.

    Returns:
        "OK" on success, "DEDUP" if evidence was incremented on existing entry.

    Raises:
        ValueError: If entry fails validation.
        RuntimeError: If post-write validation fails.
        TimeoutError: If lock cannot be acquired.
        ContractViolation: If STRICT_MODE and file not in agent's declared writes.
    """
    # 0. Path containment check
    _enforce_containment(file)

    # 0b. Contract check
    check_write_allowed(file, agent_id)

    # 1. Validate entry format
    validation = validate_entry_format(entry)
    if not validation.ok:
        raise ValueError("Invalid entry format: %s" % validation.errors)

    # 2. Resolve path
    file_path = CONTEXT_ROOT / file
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 3. Acquire exclusive lock
    lock_fd = acquire_lock(file_path)
    dedup_hit = False

    try:
        # 4. Read existing content
        existing = safe_read(file_path)

        # 5. Evidence dedup check
        if existing.strip() and should_increment_evidence(existing, entry, source):
            # Increment existing entry instead of appending new one
            new_content = increment_evidence_in_content(existing, entry, source)
            dedup_hit = True
            logger.info(
                "append_entry: dedup match for %s in %s, incrementing evidence",
                normalize_source_key(source, entry.get("detail", ""), entry.get("date", "")),
                file,
            )
        else:
            # 6. Format new entry
            formatted = format_entry(entry, source)

            # 7. Build new content
            if existing.strip():
                new_content = existing.rstrip("\n") + "\n\n" + formatted + "\n"
            else:
                # Empty file: add minimal file header first
                file_stem = Path(file).stem
                today = datetime.now().strftime("%Y-%m-%d")
                header_lines = [
                    "# %s" % file_stem,
                    "_owner: %s_" % agent_id,
                    "_last_updated: %s_" % today,
                    "_updated_by: %s_" % agent_id,
                    "",
                    formatted,
                    "",
                ]
                new_content = "\n".join(header_lines)

        # 8. Write atomically
        logger.info("append_entry: writing to %s (agent=%s)", file, agent_id)
        atomic_write(file_path, new_content)

        # 9. Post-write validation
        verify_content = safe_read(file_path)
        verify_entries = parse_context_file(verify_content)
        if not verify_entries:
            raise RuntimeError(
                "Post-write validation failed: no entries parsed from %s" % file
            )

        if not dedup_hit:
            # Check the last entry matches what we wrote
            last = verify_entries[-1]
            expected_date = entry.get("date", "")
            if expected_date and last.date.strftime("%Y-%m-%d") != expected_date:
                raise RuntimeError(
                    "Post-write validation failed: last entry date mismatch "
                    "(expected %s, got %s)" % (expected_date, last.date.strftime("%Y-%m-%d"))
                )

        # 10. Update manifest (before releasing lock)
        operation = "evidence_incremented" if dedup_hit else "entry_appended"
        update_manifest(file, agent_id, operation=operation)

        # 11. Log event
        log_event(operation, file, agent_id,
                  "source=%s" % source)

    finally:
        release_lock(lock_fd)

    return "DEDUP" if dedup_hit else "OK"


def query_context(
    file: str,
    agent_id: str,
    since: Optional[str] = None,
    source: Optional[str] = None,
    keyword: Optional[str] = None,
    min_confidence: Optional[str] = None,
) -> List[ContextEntry]:
    """Query a context file with flexible filters.

    Reads and parses the file, then applies filters in order:
      - since: entry.date >= parsed date
      - source: case-insensitive substring match on entry.source
      - keyword: case-insensitive substring match across entry.content
      - min_confidence: filter entries below minimum confidence level

    Args:
        file: Path relative to CONTEXT_ROOT.
        agent_id: Identifier of the calling agent.
        since: Date string (YYYY-MM-DD or flexible format via dateparser).
        source: Substring to match against entry source field.
        keyword: Substring to match across all content lines.
        min_confidence: Minimum confidence level (high, medium, low).

    Returns:
        Filtered list of ContextEntry objects.
    """
    # Path containment check
    _enforce_containment(file)

    # Contract check
    check_read_allowed(file, agent_id)

    file_path = CONTEXT_ROOT / file
    content = safe_read(file_path)
    entries = parse_context_file(content)

    # Filter: since (date range)
    if since:
        since_date = None  # type: Optional[datetime]
        # Try standard format first
        try:
            since_date = datetime.strptime(since, "%Y-%m-%d")
        except ValueError:
            # Try dateparser for flexible input (if available)
            try:
                import dateparser
                since_date = dateparser.parse(since)
            except ImportError:
                logger.warning("dateparser not available, only YYYY-MM-DD supported for 'since'")

        if since_date:
            entries = [e for e in entries if e.date >= since_date]

    # Filter: source (case-insensitive substring)
    if source:
        source_lower = source.lower()
        entries = [e for e in entries if source_lower in e.source.lower()]

    # Filter: keyword (case-insensitive across content)
    if keyword:
        keyword_lower = keyword.lower()
        entries = [
            e for e in entries
            if keyword_lower in " ".join(e.content).lower()
        ]

    # Filter: min_confidence
    if min_confidence:
        min_level = CONFIDENCE_ORDER.get(min_confidence.lower(), 0)
        entries = [
            e for e in entries
            if CONFIDENCE_ORDER.get(e.confidence.lower(), 0) >= min_level
        ]

    logger.debug(
        "query_context: file=%s agent=%s filters(since=%s, source=%s, keyword=%s, min_confidence=%s) results=%d",
        file, agent_id, since, source, keyword, min_confidence, len(entries),
    )

    return entries


# ---------------------------------------------------------------------------
# BatchOperation and batch_context (CORE-03)
# ---------------------------------------------------------------------------


class BatchOperation:
    """Multi-file atomic write with two-phase commit and rollback.

    Usage via batch_context() context manager:
        with batch_context('source', 'agent-id') as batch:
            batch.append_entry('file-a.md', entry_dict_a)
            batch.append_entry('file-b.md', entry_dict_b)
        # commit happens automatically on context manager exit

    NOTE: This provides best-effort multi-file atomicity (per research
    Pitfall 4). If os.replace fails partway through Phase 2, earlier
    renames cannot be undone. Mitigated by manifest updating only after
    all renames succeed.
    """

    def __init__(self, source: str, agent_id: str):
        self.source = source
        self.agent_id = agent_id
        self.pending = []  # type: List[Tuple[str, dict]]  # (file, entry)
        self._tmp_files = []  # type: List[Tuple[Path, Path, int]]  # (tmp, target, lock_fd)
        self._committed = False

    def append_entry(self, file: str, entry: dict) -> None:
        """Queue an entry for batch commit. No disk write yet.

        Validates entry immediately so errors are caught early.
        """
        validation = validate_entry_format(entry)
        if not validation.ok:
            raise ValueError("Invalid entry format: %s" % validation.errors)

        # Contract check
        check_write_allowed(file, self.agent_id)

        self.pending.append((file, entry))

    def commit(self) -> None:
        """Two-phase commit: prepare temp files, then rename all.

        Phase 1: For each pending write, acquire lock, read existing,
                 format entry, write to temp file.
        Phase 2: For each temp file, os.replace to target (commit point).
        Phase 3: Release all locks. Update manifest for each file.

        On ANY failure in Phase 1 or 2: rollback (clean temp files,
        release locks, re-raise).

        NOTE: Same-file batching is not yet supported. Queuing two entries
        for the same target file will raise ValueError. Use separate
        append_entry() calls for multiple writes to one file.
        """
        if not self.pending:
            return

        # Guard: reject same-file batches (causes deadlock — see backlog #6)
        files = [f for f, _ in self.pending]
        if len(files) != len(set(files)):
            dupes = [f for f in files if files.count(f) > 1]
            raise ValueError(
                "Batch contains duplicate target files (not yet supported): %s. "
                "Use separate append_entry() calls instead." % sorted(set(dupes))
            )

        try:
            # Phase 1: Prepare temp files
            for file, entry in self.pending:
                file_path = CONTEXT_ROOT / file
                file_path.parent.mkdir(parents=True, exist_ok=True)

                lock_fd = acquire_lock(file_path)
                existing = safe_read(file_path)

                # Check dedup
                if existing.strip() and should_increment_evidence(existing, entry, self.source):
                    new_content = increment_evidence_in_content(existing, entry, self.source)
                else:
                    formatted = format_entry(entry, self.source)
                    if existing.strip():
                        new_content = existing.rstrip("\n") + "\n\n" + formatted + "\n"
                    else:
                        file_stem = Path(file).stem
                        today = datetime.now().strftime("%Y-%m-%d")
                        header_lines = [
                            "# %s" % file_stem,
                            "_owner: %s_" % self.agent_id,
                            "_last_updated: %s_" % today,
                            "_updated_by: %s_" % self.agent_id,
                            "",
                            formatted,
                            "",
                        ]
                        new_content = "\n".join(header_lines)

                # Write to temp file
                target_dir = file_path.parent
                tmp_handle = tempfile.NamedTemporaryFile(
                    mode="w", dir=str(target_dir), suffix=".tmp",
                    delete=False, encoding="utf-8",
                )
                tmp_path = Path(tmp_handle.name)
                tmp_handle.write(new_content)
                tmp_handle.flush()
                os.fsync(tmp_handle.fileno())
                tmp_handle.close()

                self._tmp_files.append((tmp_path, file_path, lock_fd))

            # Phase 2: Rename all (commit point)
            for tmp_path, target_path, _ in self._tmp_files:
                os.replace(str(tmp_path), str(target_path))

            # Phase 3: Release locks and update manifest
            for tmp_path, target_path, lock_fd in self._tmp_files:
                release_lock(lock_fd)

            # Update manifest for each file (after all renames succeed)
            for file, entry in self.pending:
                update_manifest(file, self.agent_id, operation="batch_committed")
                log_event("batch_committed", file, self.agent_id,
                          "source=%s" % self.source)

            self._committed = True

        except Exception:
            self.rollback()
            raise

    def rollback(self) -> None:
        """Clean up temp files and release locks on failure."""
        for item in self._tmp_files:
            tmp_path, target_path, lock_fd = item
            # Clean up temp file if it still exists
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass

            # Release lock
            try:
                release_lock(lock_fd)
            except OSError:
                pass

        self._tmp_files = []


@contextlib.contextmanager
def batch_context(source: str, agent_id: str) -> Generator[BatchOperation, None, None]:
    """Context manager for multi-file atomic batch writes.

    Usage:
        with batch_context('source', 'agent-id') as batch:
            batch.append_entry('file-a.md', entry_dict_a)
            batch.append_entry('file-b.md', entry_dict_b)

    Commits on success, rolls back on exception.
    """
    batch = BatchOperation(source, agent_id)
    try:
        yield batch
        batch.commit()
    except Exception:
        batch.rollback()
        raise
