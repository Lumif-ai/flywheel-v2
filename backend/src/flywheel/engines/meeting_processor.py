"""
meeting_processor.py - Meeting intelligence extraction engine for ctx-meeting-processor.

Handles all mechanical context store I/O for meeting processing:
pre-reading existing context, formatting entries, writing to context store,
cross-referencing entities, archiving raw notes, maintaining the meeting log,
generating enriched output with cross-references, and event logging.

The SKILL.md prompt handles LLM-dependent extraction/classification;
this module handles deterministic I/O and data manipulation.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flywheel.storage_backend import (
    append_entry,
    list_context_files,
    log_event,
    parse_context_file,
    query_context,
    read_context,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENT_ID = "ctx-meeting-processor"
_MEETINGS_BASE = os.environ.get(
    "FLYWHEEL_MEETINGS_DIR", str(Path.home() / ".claude" / "meetings")
)
MEETINGS_ROOT = Path(_MEETINGS_BASE)
RAW_NOTES_DIR = MEETINGS_ROOT / "raw"
MEETING_LOG_PATH = MEETINGS_ROOT / "_meeting-log.md"

# Context files this processor writes to
WRITE_TARGETS = [
    "competitive-intel.md",
    "pain-points.md",
    "icp-profiles.md",
    "contacts.md",
    "insights.md",
    "action-items.md",
    "product-feedback.md",
]

# Meeting type definitions with primary/secondary write targets
MEETING_TYPE_WEIGHTS = {
    "discovery": {
        "primary": ["pain-points.md", "icp-profiles.md", "contacts.md", "competitive-intel.md"],
        "secondary": ["insights.md", "action-items.md", "product-feedback.md"],
    },
    "expert": {
        "primary": ["pain-points.md", "competitive-intel.md", "insights.md"],
        "secondary": ["contacts.md", "icp-profiles.md", "action-items.md"],
    },
    "advisor": {
        "primary": ["insights.md", "action-items.md"],
        "secondary": ["competitive-intel.md", "contacts.md", "product-feedback.md"],
    },
    "investor-pitch": {
        "primary": ["insights.md", "action-items.md", "product-feedback.md"],
        "secondary": ["contacts.md", "competitive-intel.md"],
    },
    "internal": {
        "primary": ["action-items.md", "insights.md"],
        "secondary": ["product-feedback.md"],
    },
    "customer-feedback": {
        "primary": ["product-feedback.md", "pain-points.md", "contacts.md"],
        "secondary": ["insights.md", "action-items.md", "competitive-intel.md"],
    },
    "team-meeting": {
        "primary": ["action-items.md", "insights.md"],
        "secondary": ["product-feedback.md"],
    },
    "prospect": {
        "primary": ["contacts.md", "pain-points.md", "icp-profiles.md", "competitive-intel.md"],
        "secondary": ["insights.md", "action-items.md", "product-feedback.md"],
    },
}


# ---------------------------------------------------------------------------
# 1. pre_read_context
# ---------------------------------------------------------------------------


def pre_read_context(agent_id: str = AGENT_ID) -> dict:
    """Read all context files and return a dict keyed by filename.

    This snapshot enables cross-referencing during processing.
    Returns {filename: raw_content_string} for each context file.
    """
    context_snapshot = {}

    for f in list_context_files():
        try:
            content = read_context(f, agent_id)
            context_snapshot[f] = content
        except Exception:
            # Partial read failure is acceptable -- skip file
            context_snapshot[f] = ""

    return context_snapshot


# ---------------------------------------------------------------------------
# 2a. lookup_contact_relationship
# ---------------------------------------------------------------------------


def lookup_contact_relationship(name: str, agent_id: str = AGENT_ID) -> Optional[str]:
    """Check if a person is a known contact and return their relationship type.

    Reads contacts.md via read_context(), parses entries looking for a matching
    name (case-insensitive substring match on "Name:" field or entry content).
    Returns relationship type string ("customer", "advisor", "prospect", etc.)
    or None if not found.

    Uses simple string matching per decision [03-01].
    Silently returns None on any error (file not found, parse error).
    """
    try:
        content = read_context("contacts.md", agent_id)
        if not content or not content.strip():
            return None

        entries = parse_context_file(content)
        name_lower = name.strip().lower()

        if len(name_lower) < 2:
            return None

        for entry in entries:
            entry_text = " ".join(entry.content).lower()
            # Check if the name appears in the entry content
            if name_lower in entry_text:
                # Look for "Relationship:" field in content lines
                for line in entry.content:
                    line_lower = line.lower().strip()
                    if line_lower.startswith("relationship:"):
                        rel_value = line_lower.replace("relationship:", "").strip()
                        if rel_value:
                            return rel_value
                # If no explicit Relationship field, check detail for contact type
                detail_lower = entry.detail.lower() if entry.detail else ""
                if "contact:" in detail_lower:
                    # Entry exists but no explicit relationship -- return generic
                    return "known"
        return None
    except Exception:
        # Silently fall back to keyword-only inference
        return None


def _extract_attendee_names(notes: str) -> list:
    """Extract attendee names from meeting notes.

    Looks for patterns like 'Meeting with:', 'Attendees:', or first-line
    name patterns. Returns a list of name strings (may be empty).
    """
    names = []
    notes_lines = notes.split("\n")

    for line in notes_lines:
        stripped = line.strip()
        # Check for "Attendees:" or "Meeting with:" patterns
        for prefix in ("**Attendees:**", "Attendees:", "Meeting with:", "**Meeting with:**"):
            if stripped.startswith(prefix):
                name_part = stripped[len(prefix):].strip()
                # Split by comma, "and", "&"
                parts = re.split(r",|\band\b|&", name_part)
                for part in parts:
                    clean = part.strip().strip("*").strip()
                    if clean and len(clean) > 2:
                        names.append(clean)

        # Check for "Name <> Company" title pattern (common meeting title format)
        name_match = re.match(r"^#?\s*(.+?)\s*<>\s*", stripped)
        if name_match:
            candidate = name_match.group(1).strip()
            if candidate and len(candidate) > 2:
                names.append(candidate)

    return names


# ---------------------------------------------------------------------------
# 2b. infer_meeting_type
# ---------------------------------------------------------------------------


def infer_meeting_type(notes: str, agent_id: str = AGENT_ID) -> str:
    """Infer meeting type from content signals and contacts.md lookup.

    Returns one of: discovery, expert, advisor, investor-pitch,
    internal, customer-feedback, team-meeting, prospect.

    First checks contacts.md for known relationships (contact-based
    classification takes priority over keyword scoring). If no match,
    falls back to keyword scoring.

    This provides a suggestion; the SKILL.md prompt may override.
    """
    notes_lower = notes.lower()

    # --- Phase 1: Contact-based classification (takes priority) ---
    attendee_names = _extract_attendee_names(notes)
    if attendee_names:
        for name in attendee_names:
            relationship = lookup_contact_relationship(name, agent_id)
            if relationship:
                # Known relationships override keyword scoring
                if relationship == "prospect":
                    return "prospect"
                elif relationship == "customer":
                    return "customer-feedback"
                elif relationship == "advisor":
                    return "advisor"
                # For other relationship types (admin, known, etc.),
                # fall through to keyword scoring

    # --- Phase 2: Keyword scoring (fallback) ---

    # Score each type based on signal keywords
    scores = {
        "discovery": 0,
        "expert": 0,
        "prospect": 0,
        "advisor": 0,
        "investor-pitch": 0,
        "internal": 0,
        "customer-feedback": 0,
        "team-meeting": 0,
    }

    # Discovery signals
    discovery_signals = [
        "discovery", "demo", "first call", "initial meeting",
        "prospect", "pipeline", "sales call", "intro call",
        "learn about", "pain point", "current process", "how do you",
    ]
    for signal in discovery_signals:
        if signal in notes_lower:
            scores["discovery"] += 1

    # Prospect signals (distinct from discovery -- implies existing relationship)
    prospect_signals = [
        "proposal", "pricing", "quote", "trial",
        "pilot", "contract", "renewal", "follow-up demo",
        "next steps", "decision", "budget",
    ]
    for signal in prospect_signals:
        if signal in notes_lower:
            scores["prospect"] += 1

    # Expert/industry signals
    expert_signals = [
        "expert", "industry", "domain expert", "sme", "subject matter",
        "research", "deep dive", "technical review", "architecture",
        "interview", "knowledge session",
    ]
    for signal in expert_signals:
        if signal in notes_lower:
            scores["expert"] += 1

    # Advisor signals
    advisor_signals = [
        "advisor", "advisory", "board", "mentor", "guidance",
        "strategic", "counsel", "coaching", "feedback session",
    ]
    for signal in advisor_signals:
        if signal in notes_lower:
            scores["advisor"] += 1

    # Investor signals
    investor_signals = [
        "investor", "pitch", "fundrais", "valuation", "term sheet",
        "round", "series", "cap table", "dilution", "raise",
        "venture", "vc", "angel",
    ]
    for signal in investor_signals:
        if signal in notes_lower:
            scores["investor-pitch"] += 1

    # Internal/standup signals
    internal_signals = [
        "standup", "stand-up", "sprint", "retro", "retrospective",
        "internal", "team sync", "weekly sync", "daily sync",
        "status update", "blockers", "todo",
    ]
    for signal in internal_signals:
        if signal in notes_lower:
            scores["internal"] += 1

    # Customer feedback signals
    feedback_signals = [
        "customer feedback", "user feedback", "feature request",
        "bug report", "support call", "customer call", "nps",
        "satisfaction", "usability", "ux feedback",
    ]
    for signal in feedback_signals:
        if signal in notes_lower:
            scores["customer-feedback"] += 1

    # Team meeting signals
    team_signals = [
        "team meeting", "all hands", "all-hands", "company meeting",
        "planning session", "brainstorm", "offsite", "kickoff",
    ]
    for signal in team_signals:
        if signal in notes_lower:
            scores["team-meeting"] += 1

    # Return highest scoring type, default to "discovery"
    max_score = max(scores.values())
    if max_score == 0:
        return "discovery"  # Default for unclassified

    # In case of tie, prefer in this order
    priority = [
        "discovery", "prospect", "customer-feedback", "expert", "advisor",
        "investor-pitch", "internal", "team-meeting",
    ]
    for mt in priority:
        if scores[mt] == max_score:
            return mt

    return "discovery"


# ---------------------------------------------------------------------------
# 3. format_context_entry
# ---------------------------------------------------------------------------


def format_context_entry(
    date: str,
    detail: str,
    content_lines: list,
    confidence: str = "medium",
) -> dict:
    """Build the entry dict for append_entry().

    Source is always 'ctx-meeting-processor'.
    Confidence defaults to 'medium' per locked decision.
    Detail format: 'meeting-{date}-{slugified-company-or-topic}'.
    Validates total entry size stays under 4000 chars (headroom below 5000 MAX_ENTRY_SIZE).

    Args:
        date: Date string in YYYY-MM-DD format.
        detail: Description for the entry header (will be used as-is).
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

    # Truncate content if total size would exceed 4000 chars
    entry = {
        "date": date,
        "source": AGENT_ID,
        "detail": detail,
        "content": content_lines,
        "confidence": confidence,
        "evidence_count": 1,
    }

    # Size check -- trim content lines if needed
    entry_size = len(str(entry))
    while entry_size > 4000 and len(entry["content"]) > 1:
        entry["content"] = entry["content"][:-1]
        entry_size = len(str(entry))

    return entry


# ---------------------------------------------------------------------------
# 4. write_to_context_store
# ---------------------------------------------------------------------------


def write_to_context_store(
    entries_by_file: dict,
    agent_id: str = AGENT_ID,
) -> dict:
    """Write entries to context store files via append_entry().

    Takes a dict of {filename: entry_dict} and calls append_entry()
    individually for each file. Returns {filename: 'OK'|'DEDUP'|'ERROR: msg'}.

    Per locked decision: individual calls, partial success is acceptable.
    Skips files where entry_dict is None or empty (no empty writes).
    """
    results = {}

    for filename, entry_dict in entries_by_file.items():
        # Skip None/empty entries (locked decision: no empty writes)
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
# 5. cross_reference
# ---------------------------------------------------------------------------


def cross_reference(extracted_data: dict, existing_context: dict) -> list:
    """Compare extracted entities against existing context store data.

    Finds connections between newly extracted data and what already exists
    in the context store. This is the flywheel proof -- compounded data
    enables richer output.

    Args:
        extracted_data: Dict of {category: list_of_strings} representing
            extracted entities (contacts, companies, pain points, competitors).
        existing_context: Dict of {filename: raw_content} from pre_read_context().

    Returns:
        List of cross-reference findings, each a dict with:
        - type: kind of cross-reference found
        - entity: the entity that was matched
        - details: additional context about the match
        - files: list of files where the entity was found
    """
    cross_refs = []

    # Extract names and entities from extracted data
    extracted_names = set()
    extracted_companies = set()
    extracted_pain_points = set()
    extracted_competitors = set()

    # Gather entities from extracted data
    for category, items in extracted_data.items():
        if not isinstance(items, list):
            continue
        for item in items:
            item_str = str(item).lower()

            if category in ("contacts", "attendees", "people"):
                # Extract name patterns (Name: ..., or just names)
                name_match = re.findall(r"name:\s*([^,|]+)", item_str, re.IGNORECASE)
                for name in name_match:
                    clean = name.strip()
                    if len(clean) > 2:
                        extracted_names.add(clean)
                # Also try the raw item as a name
                if len(item_str.strip()) > 2 and ":" not in item_str:
                    extracted_names.add(item_str.strip())

            elif category in ("companies", "organizations"):
                if len(item_str.strip()) > 1:
                    extracted_companies.add(item_str.strip())

            elif category in ("pain_points", "problems", "challenges"):
                extracted_pain_points.add(item_str.strip())

            elif category in ("competitors", "competitive"):
                extracted_competitors.add(item_str.strip())

    # Search existing context for matches
    for filename, content in existing_context.items():
        if not content:
            continue
        content_lower = content.lower()

        # Check contact name matches
        for name in extracted_names:
            if name in content_lower:
                # Count occurrences across entries
                entries = parse_context_file(content)
                mention_count = sum(
                    1 for e in entries if name in " ".join(e.content).lower()
                )
                if mention_count > 0:
                    cross_refs.append({
                        "type": "contact_seen_before",
                        "entity": name,
                        "mention_count": mention_count,
                        "files": [filename],
                        "details": "Found in %d previous entries in %s" % (mention_count, filename),
                    })

        # Check company matches
        for company in extracted_companies:
            if company in content_lower and len(company) > 2:
                entries = parse_context_file(content)
                mention_count = sum(
                    1 for e in entries if company in " ".join(e.content).lower()
                )
                if mention_count > 0:
                    cross_refs.append({
                        "type": "company_seen_before",
                        "entity": company,
                        "mention_count": mention_count,
                        "files": [filename],
                        "details": "Company referenced in %d entries in %s" % (mention_count, filename),
                    })

        # Check pain point pattern matches
        for pain_point in extracted_pain_points:
            # Use key phrases (3+ words) for matching
            words = pain_point.split()
            if len(words) >= 3:
                key_phrase = " ".join(words[:4])
                if key_phrase in content_lower:
                    entries = parse_context_file(content)
                    evidence_total = sum(e.evidence_count for e in entries if key_phrase in " ".join(e.content).lower())
                    if evidence_total > 0:
                        cross_refs.append({
                            "type": "pain_point_recurring",
                            "entity": pain_point,
                            "evidence_count": evidence_total,
                            "files": [filename],
                            "details": "Similar pain point with %d evidence in %s" % (evidence_total, filename),
                        })

        # Check competitor matches
        for competitor in extracted_competitors:
            if competitor in content_lower and len(competitor) > 2:
                cross_refs.append({
                    "type": "competitor_mentioned",
                    "entity": competitor,
                    "files": [filename],
                    "details": "Competitor previously tracked in %s" % filename,
                })

    # Deduplicate cross-refs by (type, entity) -- keep first occurrence
    seen = set()
    deduped = []
    for ref in cross_refs:
        key = (ref["type"], ref["entity"])
        if key not in seen:
            seen.add(key)
            deduped.append(ref)

    return deduped


# ---------------------------------------------------------------------------
# 6. archive_raw_notes
# ---------------------------------------------------------------------------


def archive_raw_notes(notes: str, meeting_id: str) -> str:
    """Save raw meeting notes to ~/.claude/meetings/raw/{meeting_id}.md.

    Creates directory if needed. Returns the saved file path.
    Raw notes are NOT saved to context store (locked decision).
    """
    RAW_NOTES_DIR.mkdir(parents=True, exist_ok=True)

    # Sanitize meeting_id for filename safety
    safe_id = re.sub(r"[^\w\-.]", "-", meeting_id)
    file_path = RAW_NOTES_DIR / ("%s.md" % safe_id)

    with open(str(file_path), "w", encoding="utf-8") as f:
        f.write("# Raw Meeting Notes: %s\n\n" % meeting_id)
        f.write("_archived: %s_\n\n" % datetime.now().strftime("%Y-%m-%d %H:%M"))
        f.write(notes)

    return str(file_path)


# ---------------------------------------------------------------------------
# 7. append_meeting_log
# ---------------------------------------------------------------------------


def append_meeting_log(
    meeting_id: str,
    meeting_type: str,
    date: str,
    attendees: list,
    files_written: list,
    entry_count: int,
) -> None:
    """Append an entry to ~/.claude/meetings/_meeting-log.md.

    Format: markdown table row with date, meeting_id, type, attendees, files, entry count.
    Creates the log file with header if it doesn't exist.
    """
    MEETINGS_ROOT.mkdir(parents=True, exist_ok=True)

    attendees_joined = ", ".join(attendees) if attendees else "unknown"
    files_joined = ", ".join(files_written) if files_written else "none"

    row = "| %s | %s | %s | %s | %s | %d |" % (
        date, meeting_id, meeting_type, attendees_joined, files_joined, entry_count,
    )

    if not MEETING_LOG_PATH.exists():
        header = (
            "# Meeting Log\n\n"
            "_Processed meetings index maintained by ctx-meeting-processor._\n\n"
            "| Date | Meeting ID | Type | Attendees | Files Written | Entries |\n"
            "|------|-----------|------|-----------|---------------|--------|\n"
        )
        with open(str(MEETING_LOG_PATH), "w", encoding="utf-8") as f:
            f.write(header)

    with open(str(MEETING_LOG_PATH), "a", encoding="utf-8") as f:
        f.write(row + "\n")


# ---------------------------------------------------------------------------
# 8. generate_enriched_output
# ---------------------------------------------------------------------------


def generate_enriched_output(
    extracted: dict,
    cross_refs: list,
    write_results: dict,
    meeting_type: str,
) -> str:
    """Generate standalone enriched output with context store cross-references.

    This is the legacy-replacement output that ALSO includes a
    'Context Store Cross-References' section showing connections found
    in existing data. The cross-references section is the flywheel proof.

    Args:
        extracted: Dict with keys like 'summary', 'date', 'attendees',
            'sentiment', 'insights', 'action_items', etc.
        cross_refs: List of cross-reference dicts from cross_reference().
        write_results: Dict of {filename: result} from write_to_context_store().
        meeting_type: The classified meeting type string.

    Returns:
        Formatted markdown string for standalone output.
    """
    lines = []

    # Meeting metadata header
    summary = extracted.get("summary", "Meeting processed")
    date = extracted.get("date", datetime.now().strftime("%Y-%m-%d"))
    attendees = extracted.get("attendees", [])
    sentiment = extracted.get("sentiment", "neutral")

    lines.append("# Meeting Intelligence Report")
    lines.append("")
    lines.append("**Date:** %s" % date)
    lines.append("**Type:** %s" % meeting_type)
    lines.append("**Attendees:** %s" % (", ".join(attendees) if attendees else "Not specified"))
    lines.append("**Sentiment:** %s" % sentiment)
    lines.append("")

    # Meeting summary
    lines.append("## Summary")
    lines.append("")
    lines.append(summary)
    lines.append("")

    # Key insights by category
    lines.append("## Key Insights Extracted")
    lines.append("")

    category_labels = {
        "pain_points": "Pain Points",
        "competitive_intel": "Competitive Intelligence",
        "icp_signals": "ICP Signals",
        "contacts": "Contacts",
        "product_feedback": "Product Feedback",
        "strategic_insights": "Strategic Insights",
    }

    for key, label in category_labels.items():
        items = extracted.get(key, [])
        if items:
            lines.append("### %s" % label)
            lines.append("")
            for item in items:
                lines.append("- %s" % item)
            lines.append("")

    # Context Store Cross-References (THE FLYWHEEL PROOF)
    lines.append("## Context Store Cross-References")
    lines.append("")
    if cross_refs:
        lines.append("*The following connections were found by cross-referencing "
                      "this meeting's data against the compounded context store:*")
        lines.append("")
        for ref in cross_refs:
            ref_type = ref.get("type", "unknown")
            entity = ref.get("entity", "unknown")
            details = ref.get("details", "")

            if ref_type == "contact_seen_before":
                count = ref.get("mention_count", 0)
                lines.append("- **Returning Contact:** %s -- appeared in %d previous entries. %s" % (
                    entity.title(), count, details))
            elif ref_type == "company_seen_before":
                count = ref.get("mention_count", 0)
                lines.append("- **Known Company:** %s -- referenced in %d previous entries. %s" % (
                    entity.title(), count, details))
            elif ref_type == "pain_point_recurring":
                ev = ref.get("evidence_count", 0)
                lines.append("- **Recurring Pain Point:** \"%s\" -- %d evidence count across context store. %s" % (
                    entity, ev, details))
            elif ref_type == "competitor_mentioned":
                lines.append("- **Tracked Competitor:** %s -- previously recorded in context store. %s" % (
                    entity.title(), details))
            else:
                lines.append("- **%s:** %s -- %s" % (ref_type, entity, details))
        lines.append("")
    else:
        lines.append("*No cross-references found -- this may be the first meeting "
                      "covering these entities. Future meetings will benefit from "
                      "today's data.*")
        lines.append("")

    # Action items
    action_items = extracted.get("action_items", [])
    if action_items:
        lines.append("## Action Items")
        lines.append("")
        for item in action_items:
            lines.append("- [ ] %s" % item)
        lines.append("")

    # Context store writes summary
    lines.append("## Context Store Writes")
    lines.append("")
    if write_results:
        lines.append("| File | Result |")
        lines.append("|------|--------|")
        for filename, result in sorted(write_results.items()):
            lines.append("| %s | %s |" % (filename, result))
        lines.append("")
    else:
        lines.append("*No context store writes performed.*")
        lines.append("")

    # Flywheel comparison
    lines.append("## What the Flywheel Added")
    lines.append("")
    if cross_refs:
        lines.append("This report includes **%d cross-references** from the compounded "
                      "context store that would not appear in a standalone meeting summary. "
                      "Each processed meeting makes future reports smarter." % len(cross_refs))
    else:
        lines.append("This is an early flywheel run. As more meetings are processed, "
                      "cross-references will accumulate and enrich future reports.")
    lines.append("")

    # Processing metadata
    lines.append("---")
    lines.append("*Processed by ctx-meeting-processor v1.0 at %s*" %
                  datetime.now().strftime("%Y-%m-%d %H:%M"))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 9. generate_processing_report
# ---------------------------------------------------------------------------


def generate_processing_report(
    meeting_id: str,
    write_results: dict,
    cross_refs: list,
) -> str:
    """Short summary shown after each meeting processing run.

    Reports what was extracted, where it went, and how many
    cross-references were found.
    """
    lines = []
    lines.append("## Processing Report: %s" % meeting_id)
    lines.append("")

    # Write summary
    ok_count = sum(1 for r in write_results.values() if r == "OK")
    dedup_count = sum(1 for r in write_results.values() if r == "DEDUP")
    error_count = sum(1 for r in write_results.values() if str(r).startswith("ERROR"))
    total = len(write_results)

    lines.append("**Context Store Writes:** %d files updated (%d new, %d dedup, %d errors)" % (
        total, ok_count, dedup_count, error_count))

    if write_results:
        for filename, result in sorted(write_results.items()):
            status = "OK" if result == "OK" else ("DEDUP" if result == "DEDUP" else "ERR")
            lines.append("  - %s: %s" % (filename, status))

    lines.append("")

    # Cross-reference summary
    lines.append("**Cross-References Found:** %d" % len(cross_refs))
    if cross_refs:
        type_counts = {}
        for ref in cross_refs:
            t = ref.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, count in sorted(type_counts.items()):
            lines.append("  - %s: %d" % (t, count))

    lines.append("")
    lines.append("*Processing complete.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 10. log_processor_event
# ---------------------------------------------------------------------------


def log_processor_event(
    meeting_id: str,
    meeting_type: str,
    files_written: list,
    entry_count: int,
    cross_ref_count: int,
) -> None:
    """Log a summary event to _events.jsonl via context_utils.

    Event type: 'meeting-processed'. Called once per meeting run.
    """
    detail = json.dumps({
        "meeting_id": meeting_id,
        "meeting_type": meeting_type,
        "files_written": files_written,
        "entry_count": entry_count,
        "cross_ref_count": cross_ref_count,
    })

    log_event(
        event_type="meeting-processed",
        file="_meeting-log.md",
        agent_id=AGENT_ID,
        detail=detail,
    )
