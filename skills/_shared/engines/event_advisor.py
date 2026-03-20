"""
event_advisor.py - Staleness detection and advisory startup notifications.

Provides check_staleness() to flag context files past their refresh interval,
and get_startup_advisory() to surface pending events and stale files at skill
startup in advisory (non-blocking) mode.

Implements EVNT-04 (staleness alerts) and EVNT-05 (advisory mode).
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import context_utils
from context_utils import (
    get_pending_events,
    parse_manifest,
    safe_read,
)

logger = logging.getLogger("event_advisor")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_REFRESH_INTERVALS: Dict[str, int] = {
    "competitive-intel.md": 14,
    "pain-points.md": 14,
    "icp-profiles.md": 14,
    "contacts.md": 14,
    "objections.md": 14,
    "insights.md": 14,
    "action-items.md": 14,
    "product-feedback.md": 14,
    "positioning.md": 30,
}

STALENESS_CHECK_ENABLED = True

# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------


def check_staleness(
    refresh_intervals: Optional[Dict[str, int]] = None,
) -> List[dict]:
    """Check context files for staleness based on refresh intervals.

    Reads _manifest.md to determine when each file was last updated,
    then compares against expected refresh intervals.

    Args:
        refresh_intervals: Dict mapping filename to expected refresh days.
            Defaults to DEFAULT_REFRESH_INTERVALS if not provided.

    Returns:
        List of dicts with keys: file, last_updated, expected_days,
        actual_days, status (one of 'fresh', 'stale', 'never_updated').
        Returns empty list if STALENESS_CHECK_ENABLED is False.
    """
    if not STALENESS_CHECK_ENABLED:
        return []

    intervals = refresh_intervals or DEFAULT_REFRESH_INTERVALS

    # Read and parse manifest
    manifest_path = context_utils.CONTEXT_ROOT / "_manifest.md"
    content = safe_read(manifest_path)
    manifest = parse_manifest(content)
    registry = manifest.get("registry", {})

    now = datetime.now()
    results = []

    for filename, expected_days in intervals.items():
        entry = registry.get(filename)

        if entry is None:
            results.append({
                "file": filename,
                "last_updated": None,
                "expected_days": expected_days,
                "actual_days": None,
                "status": "never_updated",
            })
            continue

        # Parse the updated timestamp from manifest
        updated_str = entry.get("updated", "")
        try:
            last_updated = datetime.strptime(updated_str, "%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            # Try legacy format (pre-fix manifests wrote this format)
            try:
                last_updated = datetime.strptime(updated_str, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                # Try date-only format as final fallback
                try:
                    last_updated = datetime.strptime(updated_str, "%Y-%m-%d")
                except (ValueError, TypeError):
                    results.append({
                        "file": filename,
                        "last_updated": updated_str,
                        "expected_days": expected_days,
                        "actual_days": None,
                        "status": "never_updated",
                    })
                    continue

        age_days = (now - last_updated).days

        if age_days > expected_days:
            status = "stale"
        else:
            status = "fresh"

        results.append({
            "file": filename,
            "last_updated": updated_str,
            "expected_days": expected_days,
            "actual_days": age_days,
            "status": status,
        })

    return results


# ---------------------------------------------------------------------------
# Startup advisory
# ---------------------------------------------------------------------------


def get_startup_advisory(
    agent_id: str,
    skill_reads: Optional[List[str]] = None,
) -> Optional[str]:
    """Generate a concise advisory for skill startup.

    Combines pending events (changes since last run) and staleness
    information into a formatted string. Returns None if nothing to report.

    This is advisory-only -- it never blocks execution or raises exceptions.

    Args:
        agent_id: Unique identifier for the polling agent/skill.
        skill_reads: Optional list of context filenames this skill reads.
            When provided, only events and staleness for these files are shown.

    Returns:
        Formatted advisory string, or None if no changes and no stale files.
    """
    try:
        # Get pending events
        pending = get_pending_events(agent_id)

        # Get staleness info
        stale_results = check_staleness()

        # Filter by skill_reads if provided
        if skill_reads:
            pending = [e for e in pending if e.get("file") in skill_reads]
            stale_results = [r for r in stale_results if r["file"] in skill_reads]

        # Only include stale files (not fresh ones)
        stale_files = [r for r in stale_results if r["status"] == "stale"]

        if not pending and not stale_files:
            return None

        lines = ["--- Context Store Advisory ---"]

        # Pending events section
        if pending:
            lines.append("Changes since your last run:")
            # Group by file with count
            file_counts: Dict[str, int] = {}
            for event in pending:
                fname = event.get("file", "unknown")
                file_counts[fname] = file_counts.get(fname, 0) + 1
            for fname in sorted(file_counts.keys()):
                lines.append("  %s: %d update(s)" % (fname, file_counts[fname]))

        # Stale files section
        if stale_files:
            lines.append("Stale context files:")
            for r in sorted(stale_files, key=lambda x: x["file"]):
                lines.append(
                    "  %s: last updated %d days ago (expected every %d days)"
                    % (r["file"], r["actual_days"], r["expected_days"])
                )

        lines.append("---")
        return "\n".join(lines)

    except Exception as exc:
        # Advisory is informational only -- never block execution
        logger.warning("Advisory generation failed: %s", exc)
        return None
