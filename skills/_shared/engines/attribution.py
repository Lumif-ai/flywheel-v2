"""
attribution.py - Cross-skill attribution analysis for Flywheel.

Traces which skills and context files contributed to a given output,
making the compounding effect visible to users.

Public API:
    build_attribution(context_attribution) -> dict
    trace_skill_sources(context_attribution) -> list[str]
    compute_compound_depth(source_skills) -> int
    format_attribution_text(attribution) -> str
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skill name display mapping (source key -> human-readable name)
# ---------------------------------------------------------------------------

_SKILL_DISPLAY_NAMES = {
    "meeting-processor": "Meeting Processor",
    "meeting-prep-research": "Meeting Prep Research",
    "meeting-prep-synthesis": "Meeting Prep Synthesis",
    "company-intel-onboarding": "Company Intelligence",
    "investor-update": "Investor Update",
    "pre-call-briefing": "Pre-Call Briefing",
    "outreach-optimizer": "Outreach Optimizer",
    "contact-enricher": "Contact Enricher",
    "seed-migration": "Seed Migration",
    "context-protocol": "Context Protocol",
}


def _humanize_skill_name(source: str) -> str:
    """Convert a source key to a human-readable skill name."""
    if source in _SKILL_DISPLAY_NAMES:
        return _SKILL_DISPLAY_NAMES[source]
    # Fallback: capitalize and replace hyphens
    return source.replace("-", " ").title()


# ---------------------------------------------------------------------------
# File description helpers
# ---------------------------------------------------------------------------

def _load_catalog_descriptions() -> dict:
    """Load file descriptions from _catalog.md if available.

    Returns dict of {filename: description}.
    """
    try:
        # Lazy import to avoid circular dependency
        import context_utils
        catalog_path = context_utils.CONTEXT_ROOT / "_catalog.md"
        if not catalog_path.exists():
            return {}

        descriptions = {}
        content = catalog_path.read_text()
        # Parse markdown table rows: | filename | description | ... |
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("|") and not line.startswith("|-"):
                parts = [p.strip() for p in line.split("|")]
                # Skip header row and empty parts
                parts = [p for p in parts if p]
                if len(parts) >= 2 and parts[0] not in ("File", "Filename", "Name"):
                    descriptions[parts[0]] = parts[1]
        return descriptions
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Core attribution functions
# ---------------------------------------------------------------------------

def build_attribution(context_attribution: dict) -> dict:
    """Build enriched attribution data from raw context_attribution.

    Args:
        context_attribution: Dict from ExecutionResult, mapping
            filename -> {"entry_count": int, "chars_read": int}

    Returns:
        Enriched dict with totals, file details, source skills, and depth.
    """
    if not context_attribution:
        return {
            "total_entries": 0,
            "total_files": 0,
            "files": [],
            "source_skills": [],
            "compound_depth": 0,
        }

    total_entries = 0
    total_files = len(context_attribution)
    files = []

    # Load catalog descriptions (best-effort)
    descriptions = _load_catalog_descriptions()

    for filename, info in sorted(context_attribution.items()):
        entry_count = info.get("entry_count", 0) if isinstance(info, dict) else 0
        total_entries += entry_count
        files.append({
            "name": filename,
            "entry_count": entry_count,
            "description": descriptions.get(filename, ""),
        })

    # Trace source skills
    source_skills = trace_skill_sources(context_attribution)
    depth = compute_compound_depth(source_skills)

    return {
        "total_entries": total_entries,
        "total_files": total_files,
        "files": files,
        "source_skills": source_skills,
        "compound_depth": depth,
    }


def trace_skill_sources(context_attribution: dict) -> list:
    """Determine which skills created entries in the read context files.

    Reads _events.jsonl to find which agents wrote to the files that
    were read during execution.

    Args:
        context_attribution: Dict mapping filename -> attribution info.

    Returns:
        Sorted list of human-readable skill names that contributed.
    """
    if not context_attribution:
        return []

    try:
        import context_utils

        # Get write events for the files that were read
        filenames = list(context_attribution.keys())
        events = context_utils.read_event_log(
            event_types=["entry_appended", "evidence_incremented"],
            files=filenames,
        )

        # Extract unique source/agent_id values
        source_keys = set()
        for event in events:
            agent_id = event.get("agent_id", "")
            if agent_id:
                source_keys.add(agent_id)

        # Map to human-readable names
        return sorted(_humanize_skill_name(s) for s in source_keys)

    except Exception as e:
        logger.debug("Could not trace skill sources: %s", e)
        return []


def compute_compound_depth(source_skills: list) -> int:
    """Compute the compounding depth based on contributing skills.

    Depth levels:
        0 - No context files used (standalone)
        1 - Read context but entries from seeds/manual input
        2 - Read entries created by other skills
        3+ - Deep compounding (capped at 3 for V1)

    V1 heuristic: depth = min(len(source_skills), 3)

    Args:
        source_skills: List of contributing skill names.

    Returns:
        Integer depth (0-3).
    """
    if not source_skills:
        return 0
    return min(len(source_skills), 3)


def format_attribution_text(attribution: dict) -> str:
    """Format attribution as human-readable text.

    Used for non-HTML contexts (e.g., Slack messages, text output).

    Args:
        attribution: Dict from build_attribution().

    Returns:
        Human-readable attribution string.
    """
    if not attribution or attribution.get("total_files", 0) == 0:
        return "No context files used."

    total = attribution.get("total_entries", 0)
    files = attribution.get("total_files", 0)
    sources = attribution.get("source_skills", [])

    parts = [f"Built from {total} entries across {files} context files."]

    if sources:
        parts.append(f"Sources: {', '.join(sources)}.")

    depth = attribution.get("compound_depth", 0)
    if depth >= 2:
        parts.append(f"Compound depth: {depth}.")

    return " ".join(parts)
