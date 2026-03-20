"""
gtm_company.py - Company profile enricher engine for ctx-gtm-my-company.

Handles all context store I/O for company profile data:
pre-reading existing context, formatting entries, writing positioning/ICP/
competitive/objection data to the context store, and maintaining the legacy
sender-profile.md for backward compatibility with existing GTM pipeline skills.

The SKILL.md prompt handles LLM-dependent profile structuring;
this module handles deterministic I/O and data manipulation.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Import context_utils from the same src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from context_utils import (
    CONTEXT_ROOT,
    append_entry,
    log_event,
    parse_context_file,
    read_context,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENT_ID = "ctx-gtm-my-company"

# Context files this enricher writes to
WRITE_TARGETS = [
    "positioning.md",
    "icp-profiles.md",
    "competitive-intel.md",
    "objections.md",
    "market-taxonomy.md",
    "product-modules.md",
]

# Legacy sender-profile.md path (for backward compat with gtm-leads-pipeline,
# gtm-company-fit-analyzer, and other legacy GTM skills)
LEGACY_PROFILE_PATH = Path.home() / ".claude" / "gtm-stack" / "sender-profile.md"


# ---------------------------------------------------------------------------
# 1. pre_read_context
# ---------------------------------------------------------------------------


def pre_read_context(agent_id: str = AGENT_ID) -> dict:
    """Read all context files and return a dict keyed by filename.

    This snapshot lets the SKILL.md prompt detect existing positioning data
    before deciding whether to update or start fresh.
    Returns {filename: raw_content_string} for each context file.
    """
    context_snapshot = {}

    if not CONTEXT_ROOT.exists():
        return context_snapshot

    for f in CONTEXT_ROOT.iterdir():
        if f.is_file() and f.suffix == ".md" and not f.name.startswith("_"):
            try:
                content = read_context(f.name, agent_id)
                context_snapshot[f.name] = content
            except Exception:
                # Partial read failure is acceptable -- skip file
                context_snapshot[f.name] = ""

    return context_snapshot


# ---------------------------------------------------------------------------
# 2. format_context_entry
# ---------------------------------------------------------------------------


def format_context_entry(
    date: str,
    detail: str,
    content_lines: list,
    confidence: str = "medium",
) -> dict:
    """Build the entry dict for append_entry().

    Source is always 'ctx-gtm-my-company'.
    Confidence defaults to 'medium' per locked decision.
    Validates date format and auto-truncates at 4000 chars.

    Args:
        date: Date string in YYYY-MM-DD format.
        detail: Description for the entry header.
        content_lines: List of content strings (each becomes a bullet).
        confidence: One of 'high', 'medium', 'low'. Defaults to 'medium'.

    Returns:
        Dict ready for append_entry(), or None if content_lines is empty.
    """
    if not content_lines:
        return None

    # Validate date format
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise ValueError("Invalid date format: '%s'. Expected YYYY-MM-DD." % date)

    # Build entry dict
    entry = {
        "date": date,
        "source": AGENT_ID,
        "detail": detail,
        "content": content_lines,
        "confidence": confidence,
        "evidence_count": 1,
    }

    # Size check -- trim content lines if total exceeds 4000 chars
    entry_size = len(str(entry))
    while entry_size > 4000 and len(entry["content"]) > 1:
        entry["content"] = entry["content"][:-1]
        entry_size = len(str(entry))

    return entry


# ---------------------------------------------------------------------------
# 3. write_to_context_store
# ---------------------------------------------------------------------------


def write_to_context_store(
    entries_by_file: dict,
    agent_id: str = AGENT_ID,
) -> dict:
    """Write entries to context store files via append_entry().

    Takes a dict of {filename: entry_dict} and calls append_entry()
    individually for each file. Returns {filename: 'OK'|'DEDUP'|'ERROR: msg'}.

    Per locked decision: individual calls, partial success is acceptable.
    Skips files where entry_dict is None or empty.
    """
    results = {}

    for filename, entry_dict in entries_by_file.items():
        # Skip None/empty entries
        if not entry_dict:
            continue

        try:
            result = append_entry(
                file=filename,
                entry=entry_dict,
                source=AGENT_ID,
                agent_id=agent_id,
            )
            results[filename] = result
        except Exception as e:
            results[filename] = "ERROR: %s" % str(e)

    return results


# ---------------------------------------------------------------------------
# 4. write_profile_to_context_store
# ---------------------------------------------------------------------------


def write_profile_to_context_store(profile_data: dict, agent_id: str = AGENT_ID) -> dict:
    """Map company profile sections to context store files and write them.

    Maps profile_data keys to context store files:
      - positioning -> positioning.md
      - icp -> icp-profiles.md
      - competitors -> competitive-intel.md
      - objections -> objections.md
      - verticals -> market-taxonomy.md
      - products -> product-modules.md

    All entries use confidence='medium', today's date.

    Args:
        profile_data: Dict with keys 'positioning', 'icp', 'competitors', 'objections',
            'verticals', 'products'. Each value is a list of content line strings.
        agent_id: Agent ID for context store writes.

    Returns:
        Dict of {filename: 'OK'|'DEDUP'|'ERROR: msg'} from write_to_context_store().
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # Map profile sections to context files and detail strings
    section_map = {
        "positioning": ("positioning.md", "company-profile-update"),
        "icp": ("icp-profiles.md", "icp-update-from-profile"),
        "competitors": ("competitive-intel.md", "competitive-landscape-update"),
        "objections": ("objections.md", "objection-handling-update"),
        "verticals": ("market-taxonomy.md", "vertical-strategy-update"),
        "products": ("product-modules.md", "product-inventory-update"),
    }

    entries_by_file = {}
    for section_key, (filename, detail) in section_map.items():
        content_lines = profile_data.get(section_key)
        if content_lines and isinstance(content_lines, list):
            entry = format_context_entry(
                date=today,
                detail=detail,
                content_lines=content_lines,
                confidence="medium",
            )
            if entry is not None:
                entries_by_file[filename] = entry

    return write_to_context_store(entries_by_file, agent_id)


# ---------------------------------------------------------------------------
# 5. write_legacy_sender_profile
# ---------------------------------------------------------------------------


def write_legacy_sender_profile(
    profile_data: dict,
    legacy_path: Optional[Path] = None,
) -> str:
    """Write the complete profile to the legacy sender-profile.md file.

    This is a FULL OVERWRITE (not append) since the legacy format is a single
    document, not entry-based. Creates the directory if it doesn't exist.

    The legacy file is read by gtm-leads-pipeline, gtm-company-fit-analyzer,
    and other existing GTM pipeline skills.

    Args:
        profile_data: Dict with keys matching legacy format sections:
            sender, company, value_props, differentiators,
            competitive_landscape, icps, buyer_personas, fit_scoring.
        legacy_path: Override path for the legacy file. Defaults to
            ~/.claude/gtm-stack/sender-profile.md.

    Returns:
        'OK' on success, 'ERROR: ...' on failure.
    """
    target = legacy_path if legacy_path else LEGACY_PROFILE_PATH

    try:
        # Create directory if needed
        target.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.append("# Sender Profile")
        lines.append("")
        lines.append("_Last updated: %s_" % datetime.now().strftime("%Y-%m-%d %H:%M"))
        lines.append("_Source: ctx-gtm-my-company_")
        lines.append("")

        # Section mapping: profile_data key -> markdown header
        section_headers = {
            "sender": "## Sender",
            "company": "## Company",
            "value_props": "## Value Propositions",
            "differentiators": "## Differentiators",
            "competitive_landscape": "## Competitive Landscape",
            "icps": "## Ideal Customer Profiles",
            "buyer_personas": "## Buyer Personas",
            "fit_scoring": "## Fit Scoring Criteria",
            # Also accept the context-store-style keys
            "positioning": "## Positioning",
            "icp": "## Ideal Customer Profiles",
            "competitors": "## Competitive Landscape",
            "objections": "## Objection Handling",
        }

        for key, header in section_headers.items():
            content = profile_data.get(key)
            if content:
                lines.append(header)
                lines.append("")
                if isinstance(content, list):
                    for item in content:
                        lines.append("- %s" % item)
                elif isinstance(content, str):
                    lines.append(content)
                else:
                    lines.append(str(content))
                lines.append("")

        with open(str(target), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return "OK"

    except Exception as e:
        return "ERROR: %s" % str(e)


# ---------------------------------------------------------------------------
# 6. write_profile
# ---------------------------------------------------------------------------


def write_profile(profile_data: dict, agent_id: str = AGENT_ID) -> dict:
    """Convenience function: write to both context store and legacy file.

    Calls write_profile_to_context_store() and write_legacy_sender_profile()
    independently. If one fails, the other still completes.

    Args:
        profile_data: Dict with profile sections (positioning, icp,
            competitors, objections, and optionally legacy keys).
        agent_id: Agent ID for context store writes.

    Returns:
        Dict with 'context_store_results' and 'legacy_result'.
    """
    # Write to context store (may partially succeed)
    context_results = {}
    try:
        context_results = write_profile_to_context_store(profile_data, agent_id)
    except Exception as e:
        context_results = {"error": "ERROR: %s" % str(e)}

    # Write to legacy file (independent of context store)
    legacy_result = "SKIPPED"
    try:
        legacy_result = write_legacy_sender_profile(profile_data)
    except Exception as e:
        legacy_result = "ERROR: %s" % str(e)

    return {
        "context_store_results": context_results,
        "legacy_result": legacy_result,
    }


# ---------------------------------------------------------------------------
# 7. log_profile_event
# ---------------------------------------------------------------------------


def log_profile_event(files_written: list, entry_count: int) -> None:
    """Log a profile-updated event to _events.jsonl via context_utils.

    Event type: 'profile-updated'. Called once per profile write run.

    Args:
        files_written: List of context store filenames that were written.
        entry_count: Number of entries written.
    """
    detail = json.dumps({
        "files_written": files_written,
        "entry_count": entry_count,
        "agent": AGENT_ID,
    })

    log_event(
        event_type="profile-updated",
        file="positioning.md",
        agent_id=AGENT_ID,
        detail=detail,
    )
