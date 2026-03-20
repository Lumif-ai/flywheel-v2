"""
meeting_prep.py - Bidirectional meeting preparation engine for meeting-prep.

Reads compounded knowledge from the context store to produce enriched meeting
preparation briefings, and writes research intelligence back to 4 context
files (contacts, competitive-intel, industry-signals, icp-profiles).

Cross-references contacts, pain points, competitive intelligence, and
positioning data across all context files.

The SKILL.md prompt handles web research and briefing assembly;
this module handles deterministic context store I/O and synthesis.
"""

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
    query_context,
    read_context,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENT_ID = "ctx-meeting-prep"

# Context files this skill reads from (all non-system context files)
READ_TARGETS = [
    "contacts.md",
    "pain-points.md",
    "competitive-intel.md",
    "icp-profiles.md",
    "objections.md",
    "positioning.md",
    "insights.md",
    "action-items.md",
    "product-feedback.md",
]

# Context files this skill writes research intelligence to
WRITE_TARGETS = [
    "contacts.md",
    "competitive-intel.md",
    "industry-signals.md",
    "icp-profiles.md",
]

# Distinct source tag for research writes (vs meeting-processor writes)
RESEARCH_SOURCE = "meeting-prep-research"


# ---------------------------------------------------------------------------
# 1. pre_read_context
# ---------------------------------------------------------------------------


def pre_read_context(agent_id: str = AGENT_ID) -> dict:
    """Read all context files and return a dict keyed by filename.

    This snapshot enables cross-referencing during preparation.
    Returns {filename: raw_content_string} for each context file.
    Handles missing/empty files gracefully.
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
# 2. find_contact_context
# ---------------------------------------------------------------------------


def find_contact_context(name: str, existing_context: dict) -> dict:
    """Search all context files for mentions of a contact name.

    Case-insensitive matching with 3+ character minimum per Phase 3 pattern.
    Returns dict with categorized results from each context file.

    Args:
        name: Contact name to search for.
        existing_context: Dict from pre_read_context().

    Returns:
        Dict with keys: prior_meetings, pain_points, competitive_intel,
        icp_signals, objections, action_items. Each value is a list of
        matching ContextEntry-derived dicts.
    """
    results = {
        "prior_meetings": [],
        "pain_points": [],
        "competitive_intel": [],
        "icp_signals": [],
        "objections": [],
        "action_items": [],
    }

    if not name or len(name.strip()) < 3:
        return results

    name_lower = name.strip().lower()

    # Map context filenames to result categories
    file_to_category = {
        "insights.md": "prior_meetings",
        "contacts.md": "prior_meetings",
        "pain-points.md": "pain_points",
        "competitive-intel.md": "competitive_intel",
        "icp-profiles.md": "icp_signals",
        "objections.md": "objections",
        "action-items.md": "action_items",
    }

    for filename, content in existing_context.items():
        if not content:
            continue

        category = file_to_category.get(filename)
        if not category:
            continue

        # Parse into structured entries
        entries = parse_context_file(content)
        for entry in entries:
            content_text = " ".join(entry.content).lower()
            header_text = (entry.detail or "").lower()

            if name_lower in content_text or name_lower in header_text:
                results[category].append(_entry_to_dict(entry, filename))

    return results


# ---------------------------------------------------------------------------
# 3. find_company_context
# ---------------------------------------------------------------------------


def find_company_context(company_name: str, existing_context: dict) -> dict:
    """Search all context files for mentions of a company name.

    Same as find_contact_context but matching on company name.

    Args:
        company_name: Company name to search for.
        existing_context: Dict from pre_read_context().

    Returns:
        Dict with same structure as find_contact_context results.
    """
    results = {
        "prior_meetings": [],
        "pain_points": [],
        "competitive_intel": [],
        "icp_signals": [],
        "objections": [],
        "action_items": [],
    }

    if not company_name or len(company_name.strip()) < 3:
        return results

    company_lower = company_name.strip().lower()

    file_to_category = {
        "insights.md": "prior_meetings",
        "contacts.md": "prior_meetings",
        "pain-points.md": "pain_points",
        "competitive-intel.md": "competitive_intel",
        "icp-profiles.md": "icp_signals",
        "objections.md": "objections",
        "action-items.md": "action_items",
    }

    for filename, content in existing_context.items():
        if not content:
            continue

        category = file_to_category.get(filename)
        if not category:
            continue

        entries = parse_context_file(content)
        for entry in entries:
            content_text = " ".join(entry.content).lower()
            header_text = (entry.detail or "").lower()

            if company_lower in content_text or company_lower in header_text:
                results[category].append(_entry_to_dict(entry, filename))

    return results


# ---------------------------------------------------------------------------
# 4. synthesize_meeting_context
# ---------------------------------------------------------------------------


def synthesize_meeting_context(
    contact_name: str,
    company_name: str,
    existing_context: dict,
) -> dict:
    """Combine contact and company context into a unified synthesis.

    Merges results from find_contact_context and find_company_context,
    deduplicating entries that appear in both searches.

    Args:
        contact_name: Name of the person being met.
        company_name: Name of their company.
        existing_context: Dict from pre_read_context().

    Returns:
        Dict with keys: prior_meetings, known_pain_points, competitive_landscape,
        icp_fit_signals, prior_objections, action_items_pending,
        positioning_current. Each value is a list of entry dicts.
    """
    contact_results = find_contact_context(contact_name, existing_context)
    company_results = find_company_context(company_name, existing_context)

    # Also search positioning.md and product-feedback.md directly
    positioning_entries = []
    product_feedback_entries = []

    for filename, content in existing_context.items():
        if not content:
            continue

        if filename == "positioning.md":
            entries = parse_context_file(content)
            # Include all positioning entries (they're always relevant)
            for entry in entries:
                positioning_entries.append(_entry_to_dict(entry, filename))

        elif filename == "product-feedback.md":
            entries = parse_context_file(content)
            name_lower = (contact_name or "").strip().lower()
            company_lower = (company_name or "").strip().lower()
            for entry in entries:
                content_text = " ".join(entry.content).lower()
                header_text = (entry.detail or "").lower()
                # Include if matches contact or company
                if (name_lower and len(name_lower) >= 3 and
                        (name_lower in content_text or name_lower in header_text)):
                    product_feedback_entries.append(_entry_to_dict(entry, filename))
                elif (company_lower and len(company_lower) >= 3 and
                        (company_lower in content_text or company_lower in header_text)):
                    product_feedback_entries.append(_entry_to_dict(entry, filename))

    # Merge and deduplicate
    synthesis = {
        "prior_meetings": _merge_dedup(
            contact_results["prior_meetings"],
            company_results["prior_meetings"],
        ),
        "known_pain_points": _merge_dedup(
            contact_results["pain_points"],
            company_results["pain_points"],
        ),
        "competitive_landscape": _merge_dedup(
            contact_results["competitive_intel"],
            company_results["competitive_intel"],
        ),
        "icp_fit_signals": _merge_dedup(
            contact_results["icp_signals"],
            company_results["icp_signals"],
        ),
        "prior_objections": _merge_dedup(
            contact_results["objections"],
            company_results["objections"],
        ),
        "action_items_pending": _merge_dedup(
            contact_results["action_items"],
            company_results["action_items"],
        ),
        "positioning_current": positioning_entries,
    }

    return synthesis


# ---------------------------------------------------------------------------
# 5. format_context_briefing
# ---------------------------------------------------------------------------


def format_context_briefing(synthesis: dict) -> str:
    """Format the synthesis dict into a readable markdown section.

    Groups by category, sorts by recency (newest first), includes
    evidence counts and confidence levels. Omits empty categories
    (no "No data" messages).

    Args:
        synthesis: Dict from synthesize_meeting_context().

    Returns:
        Formatted markdown string for inclusion in meeting prep output.
    """
    sections = []

    category_config = {
        "prior_meetings": {
            "title": "Prior Meeting History",
            "icon": "meetings",
        },
        "known_pain_points": {
            "title": "Known Pain Points",
            "icon": "pain",
        },
        "competitive_landscape": {
            "title": "Competitive Landscape",
            "icon": "competitive",
        },
        "icp_fit_signals": {
            "title": "ICP Fit Signals",
            "icon": "icp",
        },
        "prior_objections": {
            "title": "Prior Objections",
            "icon": "objections",
        },
        "action_items_pending": {
            "title": "Pending Action Items",
            "icon": "actions",
        },
        "positioning_current": {
            "title": "Current Positioning",
            "icon": "positioning",
        },
    }

    for key, config in category_config.items():
        entries = synthesis.get(key, [])
        if not entries:
            continue

        # Sort by date descending (newest first)
        sorted_entries = sorted(
            entries,
            key=lambda e: e.get("date", ""),
            reverse=True,
        )

        lines = []
        lines.append("### %s" % config["title"])
        lines.append("")

        for entry in sorted_entries:
            date = entry.get("date", "unknown")
            confidence = entry.get("confidence", "unknown")
            evidence = entry.get("evidence", 1)
            source_file = entry.get("source_file", "unknown")
            content = entry.get("content", [])

            lines.append("**[%s]** _(confidence: %s, evidence: %d, from: %s)_" % (
                date, confidence, evidence, source_file))
            for line in content:
                lines.append("- %s" % line)
            lines.append("")

        sections.append("\n".join(lines))

    if not sections:
        return ""

    header = "## Context Store Intelligence\n\n"
    header += ("_This intelligence was automatically compiled from the "
               "compounded context store across multiple previous interactions._\n\n")

    return header + "\n".join(sections)


# ---------------------------------------------------------------------------
# 6. generate_prep_report
# ---------------------------------------------------------------------------


def generate_prep_report(
    contact_name: str,
    company_name: str,
    synthesis: dict,
    context_file_count: int,
) -> str:
    """Generate a short summary of what context store data was found.

    Reports: N files searched, M entries matched, top categories with data.
    Shown to the user as proof of flywheel value.

    Args:
        contact_name: Name of the contact.
        company_name: Name of the company.
        synthesis: Dict from synthesize_meeting_context().
        context_file_count: Number of context files that were read.

    Returns:
        Formatted summary string.
    """
    total_entries = 0
    categories_with_data = []

    category_labels = {
        "prior_meetings": "Prior Meetings",
        "known_pain_points": "Pain Points",
        "competitive_landscape": "Competitive Intel",
        "icp_fit_signals": "ICP Signals",
        "prior_objections": "Objections",
        "action_items_pending": "Action Items",
        "positioning_current": "Positioning",
    }

    for key, label in category_labels.items():
        entries = synthesis.get(key, [])
        count = len(entries)
        total_entries += count
        if count > 0:
            categories_with_data.append("%s (%d)" % (label, count))

    lines = []
    lines.append("## Context Store Prep Report")
    lines.append("")
    lines.append("**Preparing for:** %s at %s" % (contact_name, company_name))
    lines.append("**Files searched:** %d context files" % context_file_count)
    lines.append("**Entries matched:** %d relevant entries found" % total_entries)
    lines.append("")

    if categories_with_data:
        lines.append("**Data found in:** %s" % ", ".join(categories_with_data))
        lines.append("")
        lines.append(
            "This intelligence was automatically compiled from %d previous "
            "interactions across %d context files." % (total_entries, context_file_count)
        )
    else:
        lines.append(
            "No prior context found for this contact/company. "
            "The briefing will rely on web research only. "
            "After this meeting is processed, future preps will benefit from today's data."
        )

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. format_research_entry
# ---------------------------------------------------------------------------


def format_research_entry(
    date: str,
    detail: str,
    content_lines: list,
    confidence: str = "low",
) -> dict:
    """Build entry dict for research intelligence writes.

    Follows the same pattern as meeting_processor.format_context_entry()
    but uses RESEARCH_SOURCE as source to distinguish research writes
    from meeting-processor writes.

    Default confidence is 'low' (single-observation research data).

    Args:
        date: Date string in YYYY-MM-DD format.
        detail: Description for the entry header (will be used as-is).
        content_lines: List of content strings (each becomes a bullet).
        confidence: One of 'high', 'medium', 'low'. Defaults to 'low'.

    Returns:
        Dict ready for append_entry(), or None if content_lines is empty.
    """
    if not content_lines:
        return None

    # Validate date format
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise ValueError("Invalid date format: '%s'. Expected YYYY-MM-DD." % date)

    entry = {
        "date": date,
        "source": RESEARCH_SOURCE,
        "detail": detail,
        "content": content_lines,
        "confidence": confidence,
        "evidence_count": 1,
    }

    # Size check -- trim content lines if needed (headroom below 5000 MAX_ENTRY_SIZE)
    entry_size = len(str(entry))
    while entry_size > 4000 and len(entry["content"]) > 1:
        entry["content"] = entry["content"][:-1]
        entry_size = len(str(entry))

    return entry


# ---------------------------------------------------------------------------
# 8. write_research_to_context_store
# ---------------------------------------------------------------------------


def write_research_to_context_store(
    research_data: dict,
    agent_id: str = AGENT_ID,
) -> dict:
    """Write research intelligence to 4 context files.

    research_data keys map to target files:
      - "contacts" -> contacts.md
      - "competitive_intel" -> competitive-intel.md
      - "industry_signals" -> industry-signals.md
      - "icp_signals" -> icp-profiles.md

    Each value is a list of dicts with {detail, content_lines, confidence}.

    Write failures do NOT block the main preparation pipeline (logged, not raised).

    Args:
        research_data: Dict with research entries per category.
        agent_id: Agent ID for event logging. Defaults to AGENT_ID.

    Returns:
        Dict of {target_file: list_of_results} where each result is
        'OK', 'DEDUP', or 'ERROR: msg'.
    """
    key_to_file = {
        "contacts": "contacts.md",
        "competitive_intel": "competitive-intel.md",
        "industry_signals": "industry-signals.md",
        "icp_signals": "icp-profiles.md",
    }

    today = datetime.now().strftime("%Y-%m-%d")
    results = {}

    for key, target_file in key_to_file.items():
        entries = research_data.get(key, [])
        file_results = []

        for entry_data in entries:
            detail = entry_data.get("detail", "research-finding")
            content_lines = entry_data.get("content_lines", [])
            confidence = entry_data.get("confidence", "low")

            entry = format_research_entry(
                date=today,
                detail=detail,
                content_lines=content_lines,
                confidence=confidence,
            )

            if entry is None:
                file_results.append("SKIP: empty content")
                continue

            try:
                result = append_entry(target_file, entry, RESEARCH_SOURCE, agent_id)
                file_results.append(result)
            except Exception as exc:
                # Write failures are non-blocking per locked decision
                error_msg = "ERROR: %s" % str(exc)
                file_results.append(error_msg)
                try:
                    log_event("write_error", target_file, agent_id,
                              detail="source=%s error=%s" % (RESEARCH_SOURCE, exc))
                except Exception:
                    pass  # Event logging failure is also non-blocking

        results[target_file] = file_results

    return results


# ---------------------------------------------------------------------------
# 9. write_contact_profile
# ---------------------------------------------------------------------------


def write_contact_profile(
    name: str,
    title: str,
    company: str,
    relationship: str = "prospect",
    role: str = "unknown",
    notes: str = "",
    agent_id: str = AGENT_ID,
) -> str:
    """Write a single contact profile to contacts.md using per-person schema.

    Constructs the entry with detail="contact: firstname-lastname" and
    the full schema content lines (Name, Title, Company, Relationship,
    Role, Notes).

    Write failures are non-blocking (returns error string, does not raise).

    Args:
        name: Full name of the contact.
        title: Job title.
        company: Company name.
        relationship: One of 'prospect', 'customer', 'advisor', 'admin'.
        role: One of 'decision-maker', 'champion', 'influencer', 'evaluator', 'unknown'.
        notes: Free text observations.
        agent_id: Agent ID for event logging.

    Returns:
        'OK', 'DEDUP', or 'ERROR: msg'.
    """
    # Build detail slug: contact: firstname-lastname
    name_slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    detail = "contact: %s" % name_slug

    content_lines = [
        "Name: %s" % name,
        "Title: %s" % title,
        "Company: %s" % company,
        "Relationship: %s" % relationship,
        "Role: %s" % role,
    ]

    if notes:
        content_lines.append("Notes: %s" % notes)

    today = datetime.now().strftime("%Y-%m-%d")

    entry = format_research_entry(
        date=today,
        detail=detail,
        content_lines=content_lines,
        confidence="low",
    )

    if entry is None:
        return "SKIP: empty content"

    try:
        result = append_entry("contacts.md", entry, RESEARCH_SOURCE, agent_id)
        return result
    except Exception as exc:
        error_msg = "ERROR: %s" % str(exc)
        try:
            log_event("write_error", "contacts.md", agent_id,
                      detail="source=%s error=%s" % (RESEARCH_SOURCE, exc))
        except Exception:
            pass
        return error_msg


# ---------------------------------------------------------------------------
# Helper: _entry_to_dict
# ---------------------------------------------------------------------------


def _entry_to_dict(entry, source_file: str) -> dict:
    """Convert a ContextEntry to a plain dict for synthesis.

    Extracts date, confidence, evidence_count, content, and source_file.
    """
    date_str = ""
    if entry.date:
        try:
            date_str = entry.date.strftime("%Y-%m-%d")
        except (AttributeError, ValueError):
            date_str = str(entry.date)

    return {
        "date": date_str,
        "source": entry.source or "",
        "detail": entry.detail or "",
        "content": list(entry.content) if entry.content else [],
        "confidence": entry.confidence or "low",
        "evidence": entry.evidence_count if entry.evidence_count else 1,
        "source_file": source_file,
    }


# ---------------------------------------------------------------------------
# Helper: _merge_dedup
# ---------------------------------------------------------------------------


def _merge_dedup(list_a: list, list_b: list) -> list:
    """Merge two lists of entry dicts, deduplicating by (date, detail, source_file).

    Keeps first occurrence when duplicates found.
    """
    seen = set()
    merged = []

    for item in list_a + list_b:
        key = (item.get("date", ""), item.get("detail", ""), item.get("source_file", ""))
        if key not in seen:
            seen.add(key)
            merged.append(item)

    return merged


# ---------------------------------------------------------------------------
# 10. Transcript Discovery (Cross-Meeting Synthesis)
# ---------------------------------------------------------------------------

TRANSCRIPT_DIRS = [
    Path.home() / ".claude" / "meetings" / "raw",
    Path.home() / "Projects" / "lumifai" / "transcripts",
]


def discover_transcripts(
    company_name: str,
    person_name: str = "",
) -> list:
    """Discover transcript files matching a company and optionally a person.

    Scans configured transcript directories for .md files with matching
    company/person name slugs in the filename. Skips underscore-prefixed
    files and non-.md files. Gracefully handles missing directories.

    Person name matching requires >= 4 character slug (short name safety
    per Pitfall 3 in research doc).

    Args:
        company_name: Company name to match in filenames.
        person_name: Optional person name to match in filenames.

    Returns:
        List of dicts [{path, date, filename, match_type}] sorted by
        date ascending (oldest first).
    """
    results = []
    company_slug = ""
    if company_name:
        company_slug = re.sub(
            r"[^a-z0-9]+", "-", company_name.strip().lower()
        ).strip("-")

    person_slug = ""
    if person_name:
        person_slug = re.sub(
            r"[^a-z0-9]+", "-", person_name.strip().lower()
        ).strip("-")

    for transcript_dir in TRANSCRIPT_DIRS:
        if not transcript_dir.exists():
            continue
        for f in transcript_dir.iterdir():
            if not f.is_file() or f.suffix != ".md" or f.name.startswith("_"):
                continue
            fname_lower = f.name.lower()

            # Extract date from filename (YYYY-MM-DD prefix)
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
            date_str = date_match.group(1) if date_match else ""

            # Match company name in filename
            if company_slug and company_slug in fname_lower:
                results.append({
                    "path": f,
                    "date": date_str,
                    "filename": f.name,
                    "match_type": "company",
                })
            # Match person name in filename (only if slug >= 4 chars)
            elif person_slug and len(person_slug) >= 4 and person_slug in fname_lower:
                results.append({
                    "path": f,
                    "date": date_str,
                    "filename": f.name,
                    "match_type": "person",
                })

    # Sort by date ascending
    results.sort(key=lambda x: x.get("date", ""))
    return results


# ---------------------------------------------------------------------------
# 11. Synthesis Depth Determination
# ---------------------------------------------------------------------------


def determine_synthesis_depth(
    transcript_count: int,
    relationship: str = "unknown",
    role: str = "unknown",
    user_override: str = "",
) -> str:
    """Determine synthesis tier based on transcript count and relationship.

    Tiers:
    - "none": No transcripts found.
    - "quick": 1-2 transcripts, low-stakes contact.
    - "pattern": 3-5 transcripts, OR high-value contact with 1-2 transcripts.
    - "deep": 6+ transcripts, OR user override.

    User override keywords take absolute precedence:
    - "deep"/"detailed"/"full" -> "deep"
    - "quick"/"brief"/"short" -> "quick"
    - "pattern"/"standard" -> "pattern"

    High-value escalation: customers and decision-makers get at least
    "pattern" tier even with only 1-2 transcripts.

    Args:
        transcript_count: Number of discovered transcripts.
        relationship: Contact relationship from contacts.md.
        role: Contact role from contacts.md.
        user_override: Raw user input to check for tier keywords.

    Returns:
        One of "none", "quick", "pattern", "deep".
    """
    # User override takes absolute precedence
    if user_override:
        override_lower = user_override.lower()
        if any(kw in override_lower for kw in ("deep", "detailed", "full")):
            return "deep"
        elif any(kw in override_lower for kw in ("quick", "brief", "short")):
            return "quick"
        elif any(kw in override_lower for kw in ("pattern", "standard")):
            return "pattern"

    if transcript_count == 0:
        return "none"

    # High-value contacts get escalated
    is_high_value = (
        relationship == "customer"
        or role == "decision-maker"
    )

    if transcript_count >= 6:
        return "deep"
    elif transcript_count >= 3:
        return "pattern"
    elif is_high_value:
        return "pattern"  # Escalate 1-2 meetings for high-value
    else:
        return "quick"


# ---------------------------------------------------------------------------
# 12. Transcript Section Extraction
# ---------------------------------------------------------------------------


def extract_transcript_sections(filepath: Path) -> dict:
    """Extract key sections from a transcript file.

    Handles both formats:
    1. Granola format: ## Metadata table, ## Key Insights, ## Full Transcript
    2. Simple notes format: no sections, just raw content

    Parses defensively -- missing sections produce empty values, never crash.

    Args:
        filepath: Path to the transcript .md file.

    Returns:
        Dict with keys: raw, metadata (dict), key_insights (list),
        full_notes (str), date (str), person (str), company (str).

    Raises:
        FileNotFoundError: If the transcript file does not exist.
    """
    content = filepath.read_text(encoding="utf-8")
    sections = {
        "raw": content,
        "metadata": {},
        "key_insights": [],
        "full_notes": "",
        "date": "",
        "person": "",
        "company": "",
    }

    # Extract date from filename
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filepath.name)
    if date_match:
        sections["date"] = date_match.group(1)

    # Parse metadata table if present
    meta_match = re.search(
        r"## Metadata\s*\n\|.*\n\|.*\n((?:\|.*\n)*)", content
    )
    if meta_match:
        for line in meta_match.group(1).strip().split("\n"):
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                sections["metadata"][parts[0]] = parts[1]
                # Extract person and company from metadata
                if parts[0].lower() == "person":
                    sections["person"] = parts[1]
                elif parts[0].lower() == "company":
                    sections["company"] = parts[1]

    # Extract Key Insights section
    insights_match = re.search(
        r"## Key Insights.*?\n(.*?)(?=\n## |\Z)",
        content,
        re.DOTALL,
    )
    if insights_match:
        lines = insights_match.group(1).strip().split("\n")
        sections["key_insights"] = [
            line.strip().lstrip("- ")
            for line in lines
            if line.strip() and line.strip() != "(TL;DR)"
        ]

    # Extract Full Transcript / Notes section
    notes_match = re.search(
        r"## (?:Full Transcript|Full Transcript / Notes|Meeting Notes|Notes).*?\n(.*)",
        content,
        re.DOTALL,
    )
    if notes_match:
        sections["full_notes"] = notes_match.group(1).strip()

    return sections


# ---------------------------------------------------------------------------
# 13. Relationship Summary Writeback
# ---------------------------------------------------------------------------

SYNTHESIS_SOURCE = "meeting-prep-synthesis"


def write_relationship_summary(
    company_name: str,
    summary_lines: list,
    meeting_count: int,
    last_date: str,
    agent_id: str = AGENT_ID,
) -> str:
    """Write a relationship summary to contacts.md.

    Uses a stable detail slug ("relationship-summary: company-slug") so
    that dedup replaces rather than piles up entries for the same company.

    Non-blocking: wraps in try/except, returns result string.

    Args:
        company_name: Company name for the summary.
        summary_lines: List of summary content lines (relationship arc, etc.).
        meeting_count: Number of meetings synthesized.
        last_date: Date of last interaction (YYYY-MM-DD).
        agent_id: Agent ID for event logging.

    Returns:
        'OK', 'DEDUP', or 'ERROR: msg'.
    """
    company_slug = re.sub(
        r"[^a-z0-9]+", "-", company_name.strip().lower()
    ).strip("-")
    detail = "relationship-summary: %s" % company_slug

    content_lines = [
        "Meeting count: %d" % meeting_count,
        "Last interaction: %s" % last_date,
    ] + list(summary_lines)

    today = datetime.now().strftime("%Y-%m-%d")

    entry = {
        "date": today,
        "source": SYNTHESIS_SOURCE,
        "detail": detail,
        "content": content_lines,
        "confidence": "medium",
        "evidence_count": meeting_count,
    }

    try:
        result = append_entry("contacts.md", entry, SYNTHESIS_SOURCE, agent_id)
        return result
    except Exception as exc:
        error_msg = "ERROR: %s" % str(exc)
        try:
            log_event("write_error", "contacts.md", agent_id,
                      detail="source=%s error=%s" % (SYNTHESIS_SOURCE, exc))
        except Exception:
            pass  # Event logging failure is also non-blocking
        return error_msg


def complete_synthesis(
    company_name: str,
    synthesis_lines: list,
    transcripts: list,
    agent_id: str = AGENT_ID,
) -> str:
    """Complete the synthesis flow by writing relationship summary back to contacts.md.

    This is the single function the LLM calls after generating synthesis text.
    Writeback is handled internally — the LLM cannot skip it.

    Args:
        company_name: Company name for the relationship summary.
        synthesis_lines: List of synthesis content lines from the LLM
            (relationship arc, key themes, last discussed topic).
        transcripts: List of transcript dicts from discover_transcripts()
            (used for meeting_count and last_date).
        agent_id: Agent ID for event logging.

    Returns:
        'OK', 'DEDUP', 'SKIP: no transcripts', or 'ERROR: msg' from write_relationship_summary.
    """
    if not transcripts:
        return "SKIP: no transcripts"

    meeting_count = len(transcripts)
    last_date = transcripts[-1].get("date", datetime.now().strftime("%Y-%m-%d"))

    return write_relationship_summary(
        company_name=company_name,
        summary_lines=synthesis_lines,
        meeting_count=meeting_count,
        last_date=last_date,
        agent_id=agent_id,
    )
