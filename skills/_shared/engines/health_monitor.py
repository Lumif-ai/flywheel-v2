"""
health_monitor.py - Phase 9 Health Dashboard & Startup Validation.

Provides observable health metrics for the Flywheel context store and
integrity verification checks suitable for running on every skill invocation.

Public API:
  - get_health_dashboard() -> dict       Full health snapshot (expensive)
  - format_dashboard(dict) -> str        Human-readable dashboard output
  - run_startup_checks() -> StartupValidationResult  Lightweight integrity checks
  - compute_manifest_checksum() -> str   SHA-256 of current manifest
  - save_manifest_checksum(str) -> None  Persist checksum for later verification
  - verify_manifest_integrity() -> bool  Compare stored vs computed checksum
  - validate_write(file, entry, source) -> ValidationResult  Enhanced pre-write gate
  - validated_append(file, entry, source, agent_id) -> str  Validate-then-append convenience

This is a LEAF module: it imports from context_utils, learning_engine,
and event_advisor. Nothing imports from it.
"""

import hashlib
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import context_utils
from context_utils import (
    parse_manifest,
    safe_read,
    parse_context_file,
    read_event_log,
)

from learning_engine import (
    detect_contradictions_in_file,
    detect_contradictions_across_files,
    check_synthesizer_health,
    _get_context_files,
)

from event_advisor import check_staleness

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_ID = "health-monitor"
STARTUP_CHECK_TIMEOUT_MS = 500

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class StartupValidationResult:
    """Result of startup integrity checks."""
    ok: bool                      # True if all critical checks pass
    checks: List[dict] = field(default_factory=list)   # Each: {name, status, detail}
    warnings: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Manifest checksum functions
# ---------------------------------------------------------------------------


def compute_manifest_checksum() -> str:
    """Compute SHA-256 hex digest of _manifest.md contents.

    Returns empty string if manifest file is missing.
    """
    root = context_utils.CONTEXT_ROOT
    manifest_path = root / "_manifest.md"
    try:
        content = safe_read(manifest_path)
        if not content:
            return ""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    except (FileNotFoundError, PermissionError, OSError):
        return ""


def save_manifest_checksum(checksum: str) -> None:
    """Persist manifest checksum to _manifest-checksum.txt via atomic write."""
    root = context_utils.CONTEXT_ROOT
    target = root / "_manifest-checksum.txt"
    try:
        root.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(root), suffix=".tmp")
        try:
            os.write(fd, checksum.encode("utf-8"))
            os.close(fd)
            os.replace(tmp_path, str(target))
        except Exception:
            os.close(fd) if not os.get_inheritable(fd) else None
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except (PermissionError, OSError) as exc:
        logger.warning("Failed to save manifest checksum: %s", exc)


def verify_manifest_integrity() -> bool:
    """Compare stored checksum against computed.

    Returns True if:
    - Checksums match, OR
    - Checksum file doesn't exist yet (fresh install)
    """
    root = context_utils.CONTEXT_ROOT
    checksum_path = root / "_manifest-checksum.txt"
    try:
        if not checksum_path.exists():
            return True  # Fresh install
        stored = checksum_path.read_text().strip()
        computed = compute_manifest_checksum()
        if not computed:
            return True  # No manifest to check
        return stored == computed
    except (FileNotFoundError, PermissionError, OSError):
        return True  # Can't read = treat as fresh


# ---------------------------------------------------------------------------
# Enhanced write validation (HLTH-02)
# ---------------------------------------------------------------------------

# Source format: alphanumeric, hyphens, underscores, dots
_SOURCE_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")


def validate_write(file: str, entry: dict, source: str) -> context_utils.ValidationResult:
    """Enhanced pre-write validation gate.

    Called BY skills BEFORE append_entry(). Not injected into append_entry()
    itself -- existing callers that skip this function are unaffected.

    Checks (in order):
      1. Base validation (delegates to context_utils.validate_entry_format)
      2. Path traversal prevention
      3. Future date rejection (>1 day ahead for timezone tolerance)
      4. Source format validation
      5. Content line validation
      6. File extension check (.md required)
      7. System file protection (no _ prefix)
      8. Duplicate header detection (warning, not error)

    Returns ValidationResult with ok=True if all checks pass, or ok=False
    with accumulated errors. Warnings (e.g., duplicates) are appended to
    errors list with a "[warning]" prefix but do NOT set ok=False.
    """
    errors = []  # type: List[str]
    warnings = []  # type: List[str]

    # 1. Base validation first -- if it fails, return its errors immediately
    base_result = context_utils.validate_entry_format(entry)
    if not base_result.ok:
        return base_result

    # 2. Path traversal prevention
    if ".." in file:
        errors.append(f"Path traversal attempt detected: {file}")
    if file.startswith("/"):
        errors.append(f"Path traversal attempt detected: {file}")
    if not errors:
        # Only do resolve check if no obvious traversal found
        root = context_utils.CONTEXT_ROOT
        try:
            resolved = (root / file).resolve()
            root_resolved = root.resolve()
            if not str(resolved).startswith(str(root_resolved)):
                errors.append(f"Path traversal attempt detected: {file}")
        except (ValueError, OSError):
            errors.append(f"Path traversal attempt detected: {file}")

    # 3. Future date rejection
    date_str = entry.get("date", "")
    if date_str:
        try:
            entry_date = datetime.strptime(str(date_str), "%Y-%m-%d").date()
            tomorrow = (datetime.now() + timedelta(days=1)).date()
            if entry_date > tomorrow:
                errors.append(f"Entry date {date_str} is in the future")
        except ValueError:
            pass  # Date format already validated by base validation

    # 4. Source format validation
    if not source:
        errors.append("Invalid source format: (empty)")
    elif not _SOURCE_PATTERN.match(source):
        errors.append(f"Invalid source format: {source}")

    # 5. Content line validation
    content = entry.get("content")
    if content is None or (isinstance(content, list) and len(content) == 0):
        errors.append("Entry has no content lines")
    elif isinstance(content, list):
        has_non_whitespace = any(
            isinstance(line, str) and line.strip() for line in content
        )
        if not has_non_whitespace:
            errors.append("Entry has only empty content lines")

    # 6. File extension check
    if not file.endswith(".md"):
        errors.append(f"Context file must have .md extension: {file}")

    # 7. System file protection
    basename = os.path.basename(file)
    if basename.startswith("_"):
        errors.append(f"Cannot write to system file: {file}")

    # 8. Duplicate header detection (warning only, does not block writes)
    if not errors:
        _check_duplicate_header(file, entry, warnings)

    # Build result: warnings are appended with prefix but don't affect ok
    all_messages = list(errors)
    for w in warnings:
        all_messages.append(f"[warning] {w}")

    return context_utils.ValidationResult(ok=len(errors) == 0, errors=all_messages)


def _check_duplicate_header(file: str, entry: dict, warnings: List[str]) -> None:
    """Check if an entry with the same (date, source, detail) already exists."""
    root = context_utils.CONTEXT_ROOT
    target_path = root / file
    try:
        if not target_path.exists():
            return
        content = context_utils.safe_read(target_path)
        if not content:
            return
        existing_entries = context_utils.parse_context_file(content)
        entry_date_str = str(entry.get("date", ""))
        entry_source = str(entry.get("source", ""))
        entry_detail = str(entry.get("detail", ""))
        for existing in existing_entries:
            existing_date_str = existing.date.strftime("%Y-%m-%d")
            if (existing_date_str == entry_date_str
                    and existing.source == entry_source
                    and existing.detail == entry_detail):
                warnings.append(
                    f"Duplicate entry detected: ({entry_date_str}, {entry_source}, {entry_detail})"
                )
                return
    except Exception:
        pass  # Duplicate detection is best-effort


def validated_append(file: str, entry: dict, source: str, agent_id: str) -> str:
    """Convenience: validate then append. Raises ValueError if validation fails."""
    result = validate_write(file, entry, source)
    if not result.ok:
        raise ValueError(f"Write validation failed: {'; '.join(result.errors)}")
    return context_utils.append_entry(file, entry, source, agent_id)


# ---------------------------------------------------------------------------
# Private metric helpers
# ---------------------------------------------------------------------------


def _count_context_files() -> int:
    """Count .md files in CONTEXT_ROOT excluding _ prefix (system files)."""
    root = context_utils.CONTEXT_ROOT
    if not root.is_dir():
        return 0
    count = 0
    try:
        for p in root.iterdir():
            if p.is_file() and p.suffix == ".md" and not p.name.startswith("_"):
                count += 1
    except (PermissionError, OSError):
        pass
    return count


def _count_total_entries() -> int:
    """Sum entry counts across all context files."""
    root = context_utils.CONTEXT_ROOT
    if not root.is_dir():
        return 0
    total = 0
    try:
        for p in root.iterdir():
            if p.is_file() and p.suffix == ".md" and not p.name.startswith("_"):
                try:
                    content = safe_read(p)
                    entries = parse_context_file(content)
                    total += len(entries)
                except Exception:
                    pass
    except (PermissionError, OSError):
        pass
    return total


def _compute_staleness_pct() -> float:
    """Compute percentage of tracked files that are stale.

    Returns 0.0 if no tracked files or staleness check disabled.
    """
    try:
        results = check_staleness()
        if not results:
            return 0.0
        stale_count = sum(1 for r in results if r.get("status") == "stale")
        return (stale_count / len(results)) * 100.0
    except Exception:
        return 0.0


def _count_contradictions() -> int:
    """Count total contradictions across all context files.

    This is expensive -- for dashboard only, NOT startup checks.
    """
    total = 0
    try:
        files = _get_context_files()
        for filename in files:
            try:
                contras = detect_contradictions_in_file(filename)
                total += len(contras)
            except Exception:
                pass
        try:
            cross = detect_contradictions_across_files()
            total += len(cross)
        except Exception:
            pass
    except Exception:
        pass
    return total


def _get_last_backup_time() -> Optional[str]:
    """Find most recent manifest backup snapshot.

    Looks in CONTEXT_ROOT/_backups/manifest-snapshots/ for snapshot files
    and parses timestamp from filename.
    """
    root = context_utils.CONTEXT_ROOT
    snapshot_dir = root / "_backups" / "manifest-snapshots"
    try:
        if not snapshot_dir.is_dir():
            return None
        snapshots = sorted(snapshot_dir.iterdir(), reverse=True)
        if not snapshots:
            return None
        # Try to parse timestamp from filename (e.g., manifest-2026-03-12T08:30:00.md)
        name = snapshots[0].name
        # Strip prefix and suffix to get timestamp portion
        ts_part = name.replace("manifest-", "").replace(".md", "").replace(".txt", "")
        # Try ISO-like parsing
        try:
            dt = datetime.fromisoformat(ts_part)
            return dt.isoformat()
        except (ValueError, TypeError):
            # Fall back to file modification time
            mtime = snapshots[0].stat().st_mtime
            return datetime.fromtimestamp(mtime).isoformat()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def _check_catalog_sync() -> Tuple[bool, List[str]]:
    """Check if _catalog.md matches actual files on disk.

    Returns (in_sync: bool, issues: list of mismatch descriptions).
    """
    root = context_utils.CONTEXT_ROOT
    issues = []
    try:
        catalog_path = root / "_catalog.md"
        if not catalog_path.exists():
            return (True, [])  # No catalog = nothing to check

        content = safe_read(catalog_path)
        if not content:
            return (True, [])

        # Parse catalog table: extract filenames from first column after header
        catalog_files = set()
        in_table = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("| File"):
                in_table = True
                continue
            if in_table and stripped.startswith("|---"):
                continue
            if in_table and stripped.startswith("|"):
                cols = [c.strip() for c in stripped.split("|")]
                # cols[0] is empty (before first |), cols[1] is filename
                if len(cols) >= 2 and cols[1] and cols[1] != "File":
                    catalog_files.add(cols[1])
            elif in_table and not stripped.startswith("|"):
                in_table = False

        # Get actual files on disk
        disk_files = set()
        if root.is_dir():
            for p in root.iterdir():
                if p.is_file() and p.suffix == ".md" and not p.name.startswith("_"):
                    disk_files.add(p.name)

        # Compare
        in_catalog_not_disk = catalog_files - disk_files
        on_disk_not_catalog = disk_files - catalog_files

        for f in sorted(in_catalog_not_disk):
            issues.append(f"In catalog but not on disk: {f}")
        for f in sorted(on_disk_not_catalog):
            issues.append(f"On disk but not in catalog: {f}")

        return (len(issues) == 0, issues)

    except (FileNotFoundError, PermissionError, OSError):
        return (True, [])


def _check_orphan_files() -> List[str]:
    """Find orphan .lock and .tmp files in CONTEXT_ROOT."""
    root = context_utils.CONTEXT_ROOT
    orphans = []
    try:
        if not root.is_dir():
            return []
        for p in root.iterdir():
            if p.is_file() and (p.suffix == ".lock" or p.suffix == ".tmp"):
                orphans.append(p.name)
    except (PermissionError, OSError):
        pass
    return sorted(orphans)


def _check_event_log_parseable() -> bool:
    """Try to read the event log. Return True if no exception."""
    try:
        read_event_log()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API -- get_health_dashboard()
# ---------------------------------------------------------------------------


def get_health_dashboard() -> dict:
    """Return full health snapshot of the context store.

    Returns dict with keys: file_count, total_entries, staleness_percentage,
    contradiction_count, last_backup_time, synthesizer_health, catalog_sync,
    manifest_integrity, timestamp.
    """
    synth_health = {}
    try:
        synth_health = check_synthesizer_health()
    except Exception:
        synth_health = {"status": "ERROR", "message": "Failed to check"}

    catalog_ok, _catalog_issues = _check_catalog_sync()

    # Recipe store health (lazy import to avoid circular deps)
    recipe_health = None
    try:
        import recipe_store
        recipe_health = recipe_store.get_recipe_health()
    except ImportError:
        recipe_health = None

    report = {
        "file_count": _count_context_files(),
        "total_entries": _count_total_entries(),
        "staleness_percentage": _compute_staleness_pct(),
        "contradiction_count": _count_contradictions(),
        "last_backup_time": _get_last_backup_time(),
        "synthesizer_health": synth_health,
        "catalog_sync": catalog_ok,
        "manifest_integrity": verify_manifest_integrity(),
        "timestamp": datetime.now().isoformat(),
    }

    if recipe_health:
        report["recipe_store"] = {
            "total_recipes": recipe_health["total_recipes"],
            "by_status": recipe_health["by_status"],
            "oldest_unverified": recipe_health["oldest_unverified"],
            "most_used_recipe": (
                "%s:%s (%d uses)" % (
                    recipe_health["most_used"]["domain"],
                    recipe_health["most_used"]["task"],
                    recipe_health["most_used"]["use_count"],
                ) if recipe_health["most_used"] else "none"
            ),
            "visit_log_entries": recipe_health["visit_log_entries"],
        }

    return report


# ---------------------------------------------------------------------------
# Public API -- format_dashboard()
# ---------------------------------------------------------------------------


def format_dashboard(dashboard: dict) -> str:
    """Format dashboard dict into human-readable multi-line string."""
    synth = dashboard.get("synthesizer_health", {})
    synth_status = synth.get("status", "UNKNOWN")
    synth_msg = synth.get("message", "")
    synth_line = synth_status
    if synth_msg:
        synth_line = f"{synth_status} ({synth_msg})"

    backup = dashboard.get("last_backup_time") or "No backups found"
    catalog = "OK" if dashboard.get("catalog_sync") else "OUT OF SYNC"
    manifest = "OK" if dashboard.get("manifest_integrity") else "INTEGRITY FAILURE"

    lines = [
        "=== Context Store Health Dashboard ===",
        f"Timestamp: {dashboard.get('timestamp', 'unknown')}",
        "",
        f"Files: {dashboard.get('file_count', 0)} context files",
        f"Entries: {dashboard.get('total_entries', 0)} total entries",
        f"Staleness: {dashboard.get('staleness_percentage', 0.0):.1f}% of tracked files stale",
        f"Contradictions: {dashboard.get('contradiction_count', 0)} detected",
        f"Last Backup: {backup}",
        f"Synthesizer: {synth_line}",
        f"Catalog Sync: {catalog}",
        f"Manifest Integrity: {manifest}",
    ]

    # Recipe store section (if available)
    recipe_store_data = dashboard.get("recipe_store")
    if recipe_store_data:
        by_status = recipe_store_data.get("by_status", {})
        lines.append("")
        lines.append("Recipe Store:")
        lines.append(f"  Total recipes: {recipe_store_data.get('total_recipes', 0)}")
        lines.append(
            f"  Active: {by_status.get('active', 0)}, "
            f"Suspect: {by_status.get('suspect', 0)}, "
            f"Stale: {by_status.get('stale', 0)}, "
            f"Broken: {by_status.get('broken', 0)}"
        )
        lines.append(f"  Most used: {recipe_store_data.get('most_used_recipe', 'none')}")
        lines.append(f"  Visit log: {recipe_store_data.get('visit_log_entries', 0)} entries")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API -- run_startup_checks()
# ---------------------------------------------------------------------------


def run_startup_checks() -> StartupValidationResult:
    """Run lightweight integrity checks on context store.

    Checks are pure reads -- NEVER modifies state.
    Does NOT run contradiction scanning (too expensive for startup).
    """
    start = time.monotonic()
    checks = []
    warnings = []

    root = context_utils.CONTEXT_ROOT

    # Check 1: context_store_exists
    store_exists = root.is_dir()
    checks.append({
        "name": "context_store_exists",
        "status": "pass" if store_exists else "fail",
        "detail": str(root) if store_exists else f"Directory not found: {root}",
    })

    # Check 2: catalog_exists
    catalog_path = root / "_catalog.md"
    catalog_exists = False
    try:
        catalog_exists = catalog_path.exists()
    except (PermissionError, OSError):
        pass
    checks.append({
        "name": "catalog_exists",
        "status": "pass" if catalog_exists else "fail",
        "detail": "Found" if catalog_exists else "Missing _catalog.md",
    })

    # Check 3: catalog_sync
    try:
        in_sync, catalog_issues = _check_catalog_sync()
        if in_sync:
            checks.append({
                "name": "catalog_sync",
                "status": "pass",
                "detail": "Catalog matches files on disk",
            })
        else:
            checks.append({
                "name": "catalog_sync",
                "status": "fail",
                "detail": "; ".join(catalog_issues),
            })
    except Exception as exc:
        checks.append({
            "name": "catalog_sync",
            "status": "fail",
            "detail": f"Error checking catalog sync: {exc}",
        })

    # Check 4: manifest_exists
    manifest_path = root / "_manifest.md"
    manifest_exists = False
    try:
        manifest_exists = manifest_path.exists()
    except (PermissionError, OSError):
        pass
    checks.append({
        "name": "manifest_exists",
        "status": "pass" if manifest_exists else "fail",
        "detail": "Found" if manifest_exists else "Missing _manifest.md",
    })

    # Check 5: manifest_integrity
    try:
        integrity_ok = verify_manifest_integrity()
        checks.append({
            "name": "manifest_integrity",
            "status": "pass" if integrity_ok else "fail",
            "detail": "Checksum matches" if integrity_ok else "Manifest has been modified since last checksum",
        })
    except Exception as exc:
        checks.append({
            "name": "manifest_integrity",
            "status": "fail",
            "detail": f"Error verifying integrity: {exc}",
        })

    # Check 6: no_orphan_files
    try:
        orphans = _check_orphan_files()
        if orphans:
            checks.append({
                "name": "no_orphan_files",
                "status": "warn",
                "detail": f"Found orphan files: {', '.join(orphans)}",
            })
            for o in orphans:
                warnings.append(f"Orphan file found: {o}")
        else:
            checks.append({
                "name": "no_orphan_files",
                "status": "pass",
                "detail": "No orphan .lock or .tmp files",
            })
    except Exception as exc:
        checks.append({
            "name": "no_orphan_files",
            "status": "warn",
            "detail": f"Error checking orphan files: {exc}",
        })

    # Check 7: event_log_parseable
    try:
        parseable = _check_event_log_parseable()
        checks.append({
            "name": "event_log_parseable",
            "status": "pass" if parseable else "warn",
            "detail": "Event log readable" if parseable else "Event log could not be parsed",
        })
        if not parseable:
            warnings.append("Event log could not be parsed")
    except Exception as exc:
        checks.append({
            "name": "event_log_parseable",
            "status": "warn",
            "detail": f"Error checking event log: {exc}",
        })

    duration_ms = (time.monotonic() - start) * 1000.0
    ok = all(c["status"] != "fail" for c in checks)

    return StartupValidationResult(
        ok=ok,
        checks=checks,
        warnings=warnings,
        duration_ms=duration_ms,
    )
