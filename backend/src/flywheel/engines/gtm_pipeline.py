"""
gtm_pipeline.py - Bidirectional GTM pipeline engine for ctx-gtm-pipeline.

First bidirectional skill engine: reads enriched context from 7 context store
files to inform outreach personalization, and writes outreach-discovered data
(new contacts, new objections, validated insights) back to the context store.

The SKILL.md prompt handles LLM-dependent outreach personalization;
this module handles deterministic context store I/O for both read and write-back.
"""

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

from flywheel.storage_backend import (
    append_entry,
    list_context_files,
    log_event,
    parse_context_file,
    read_context,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENT_ID = "ctx-gtm-pipeline"

# Outreach tracker (read-only source for effectiveness signals)
_TRACKER_DIR = os.environ.get(
    "FLYWHEEL_GTM_TRACKER",
    str(Path.home() / ".claude" / "gtm-stack" / "outreach-tracker.csv"),
)
TRACKER_PATH = Path(_TRACKER_DIR)

# Learning directory for effectiveness data
_DATA_DIR = os.environ.get("FLYWHEEL_DATA_DIR", str(Path.home() / "lumifai"))
LEARNING_DIR = Path(_DATA_DIR) / "_learning"

# Cold-start protection threshold
MINIMUM_SAMPLE_SIZE = 5

# Outcome classification for effectiveness signals
POSITIVE_OUTCOMES = {"Replied - Interested", "Meeting Booked"}
NEGATIVE_OUTCOMES = {"Replied - Not Interested", "Replied - Using Competitor"}
NEUTRAL_OUTCOMES = {"No Response", "Bounced", "Wrong Contact"}

# Context files this skill reads from
READ_TARGETS = [
    "pain-points.md",
    "icp-profiles.md",
    "contacts.md",
    "positioning.md",
    "competitive-intel.md",
    "objections.md",
    "insights.md",
]

# Context files this skill writes back to
WRITE_TARGETS = [
    "contacts.md",
    "insights.md",
    "objections.md",
]


# ---------------------------------------------------------------------------
# 1. pre_read_context
# ---------------------------------------------------------------------------


def pre_read_context(agent_id: str = AGENT_ID) -> Dict[str, str]:
    """Read all context files and return a dict keyed by filename.

    This snapshot provides the full context store knowledge base for
    outreach personalization. Returns {filename: raw_content_string}
    for each context file. Skips files that fail silently (partial
    success acceptable).

    Args:
        agent_id: Agent ID for context store reads.

    Returns:
        Dict of {filename: content_string} for all readable context files.
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
# 2. find_contact_context
# ---------------------------------------------------------------------------


def find_contact_context(
    contact_name: str,
    company: str,
    context_snapshot: Dict[str, str],
) -> Dict[str, List[str]]:
    """Search context snapshot for mentions of a contact or company.

    Uses simple case-insensitive string matching (same approach as
    meeting_prep.py). Searches across all files in the snapshot.

    Args:
        contact_name: Name of the contact to search for.
        company: Company name to search for.
        context_snapshot: Dict from pre_read_context().

    Returns:
        Dict of {filename: [matching_lines]} with all lines that
        mention the contact or company.
    """
    results = {}

    # Build search terms (skip empty/short terms)
    search_terms = []
    if contact_name and len(contact_name.strip()) >= 3:
        search_terms.append(contact_name.strip().lower())
    if company and len(company.strip()) >= 3:
        search_terms.append(company.strip().lower())

    if not search_terms:
        return results

    for filename, content in context_snapshot.items():
        if not content:
            continue

        matching_lines = []
        for line in content.splitlines():
            line_lower = line.lower()
            for term in search_terms:
                if term in line_lower:
                    matching_lines.append(line.strip())
                    break  # avoid duplicate line for multiple term matches

        if matching_lines:
            results[filename] = matching_lines

    return results


# ---------------------------------------------------------------------------
# 3. synthesize_outreach_context
# ---------------------------------------------------------------------------


def synthesize_outreach_context(context_snapshot: Dict[str, str]) -> str:
    """Produce a formatted summary of context store knowledge for outreach.

    Organizes by: pain points (with evidence counts), ICP segments,
    competitive landscape, known objections, positioning angles.
    This string is what the SKILL.md prompt uses for personalization.

    Caps output at 4000 chars with truncation.

    Args:
        context_snapshot: Dict from pre_read_context().

    Returns:
        Formatted markdown string summarizing outreach-relevant context.
    """
    sections = []

    # --- Pain Points ---
    pain_content = context_snapshot.get("pain-points.md", "")
    if pain_content:
        entries = parse_context_file(pain_content)
        if entries:
            lines = ["### Pain Points (%d entries)" % len(entries)]
            for entry in entries:
                evidence = entry.evidence_count if entry.evidence_count else 1
                confidence = entry.confidence or "low"
                detail = entry.detail or "unknown"
                lines.append(
                    "- **%s** (evidence: %d, confidence: %s)"
                    % (detail, evidence, confidence)
                )
                for cl in entry.content[:3]:  # max 3 content lines per entry
                    lines.append("  - %s" % cl)
            sections.append("\n".join(lines))

    # --- ICP Segments ---
    icp_content = context_snapshot.get("icp-profiles.md", "")
    if icp_content:
        entries = parse_context_file(icp_content)
        if entries:
            lines = ["### ICP Segments (%d entries)" % len(entries)]
            for entry in entries:
                for cl in entry.content[:4]:
                    lines.append("- %s" % cl)
            sections.append("\n".join(lines))

    # --- Competitive Landscape ---
    comp_content = context_snapshot.get("competitive-intel.md", "")
    if comp_content:
        entries = parse_context_file(comp_content)
        if entries:
            lines = ["### Competitive Landscape (%d entries)" % len(entries)]
            for entry in entries:
                for cl in entry.content[:3]:
                    lines.append("- %s" % cl)
            sections.append("\n".join(lines))

    # --- Known Objections ---
    obj_content = context_snapshot.get("objections.md", "")
    if obj_content:
        entries = parse_context_file(obj_content)
        if entries:
            lines = ["### Known Objections (%d entries)" % len(entries)]
            for entry in entries:
                for cl in entry.content[:3]:
                    lines.append("- %s" % cl)
            sections.append("\n".join(lines))

    # --- Positioning Angles ---
    pos_content = context_snapshot.get("positioning.md", "")
    if pos_content:
        entries = parse_context_file(pos_content)
        if entries:
            lines = ["### Positioning Angles (%d entries)" % len(entries)]
            for entry in entries:
                for cl in entry.content[:3]:
                    lines.append("- %s" % cl)
            sections.append("\n".join(lines))

    # --- Existing Contacts ---
    contacts_content = context_snapshot.get("contacts.md", "")
    if contacts_content:
        entries = parse_context_file(contacts_content)
        if entries:
            lines = ["### Known Contacts (%d entries)" % len(entries)]
            for entry in entries:
                for cl in entry.content[:3]:
                    lines.append("- %s" % cl)
            sections.append("\n".join(lines))

    # --- Insights ---
    insights_content = context_snapshot.get("insights.md", "")
    if insights_content:
        entries = parse_context_file(insights_content)
        if entries:
            lines = ["### Insights (%d entries)" % len(entries)]
            for entry in entries:
                for cl in entry.content[:2]:
                    lines.append("- %s" % cl)
            sections.append("\n".join(lines))

    if not sections:
        return "No context store data available for outreach enrichment."

    header = "## Outreach Context Summary\n\n"
    header += (
        "_Compiled from %d context files for outreach personalization._\n\n"
        % len(context_snapshot)
    )

    output = header + "\n\n".join(sections)

    # Cap at 4000 chars with truncation
    if len(output) > 4000:
        output = output[:3950] + "\n\n_[Truncated -- %d chars total]_" % len(
            header + "\n\n".join(sections)
        )

    return output


# ---------------------------------------------------------------------------
# 4. format_outcome_entry
# ---------------------------------------------------------------------------


def format_outcome_entry(
    outcome_type: str,
    content_lines: List[str],
    detail: str,
) -> Optional[dict]:
    """Format an outcome entry dict for append_entry().

    Builds a properly structured entry dict for writing outreach outcomes
    back to the context store.

    Args:
        outcome_type: Type of outcome (e.g., "new-contact", "new-objection",
            "validated-insight"). Used for event logging.
        content_lines: List of content strings for the entry body.
        detail: Detail string for the entry header (e.g.,
            "outreach-new-contact" or "outreach-new-objection").

    Returns:
        Dict ready for append_entry(), or None if content_lines is empty.
    """
    if not content_lines:
        return None

    today = datetime.now().strftime("%Y-%m-%d")

    entry = {
        "date": today,
        "source": AGENT_ID,
        "detail": detail,
        "content": content_lines,
        "confidence": "low",  # single-observation outcomes start at low
        "evidence_count": 1,
    }

    # Size check -- trim content lines if total exceeds 4000 chars
    entry_size = len(str(entry))
    while entry_size > 4000 and len(entry["content"]) > 1:
        entry["content"] = entry["content"][:-1]
        entry_size = len(str(entry))

    return entry


# ---------------------------------------------------------------------------
# 5. write_outreach_outcomes
# ---------------------------------------------------------------------------


def write_outreach_outcomes(
    outcomes_by_file: Dict[str, dict],
    agent_id: str = AGENT_ID,
) -> Dict[str, str]:
    """Write outcome entries to context store files.

    Takes dict of {filename: entry_dict} and calls append_entry() for each.
    Follows the gtm_company.py write pattern: independent writes per file,
    partial success acceptable.

    Args:
        outcomes_by_file: Dict of {filename: entry_dict}. Entry dicts
            should be from format_outcome_entry().
        agent_id: Agent ID for context store writes.

    Returns:
        Dict of {filename: 'OK'|'DEDUP'|'ERROR: msg'} with write results.
    """
    results = {}

    for filename, entry_dict in outcomes_by_file.items():
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

            # Log event for each successful write
            log_event(
                event_type="outreach-write-back",
                file=filename,
                agent_id=agent_id,
                detail=json.dumps({
                    "outcome_detail": entry_dict.get("detail", ""),
                    "content_lines": len(entry_dict.get("content", [])),
                    "agent": agent_id,
                }),
            )

        except Exception as e:
            results[filename] = "ERROR: %s" % str(e)

    return results


# ---------------------------------------------------------------------------
# 6. generate_pipeline_report
# ---------------------------------------------------------------------------


def generate_pipeline_report(
    context_snapshot: Dict[str, str],
    write_results: Dict[str, str],
) -> str:
    """Generate a human-readable report of the pipeline run.

    Summarizes: what context was read (file counts, entry counts),
    what was written back (files, entry summaries), any errors.

    Args:
        context_snapshot: Dict from pre_read_context().
        write_results: Dict from write_outreach_outcomes().

    Returns:
        Formatted markdown report string.
    """
    lines = []
    lines.append("## GTM Pipeline Report")
    lines.append("")

    # --- Read summary ---
    lines.append("### Context Read")
    total_entries = 0
    files_with_data = 0
    for filename in READ_TARGETS:
        content = context_snapshot.get(filename, "")
        if content:
            entries = parse_context_file(content)
            entry_count = len(entries)
            total_entries += entry_count
            files_with_data += 1
            lines.append("- **%s**: %d entries" % (filename, entry_count))
        else:
            lines.append("- **%s**: no data" % filename)

    lines.append("")
    lines.append(
        "**Total:** %d entries read from %d/%d files"
        % (total_entries, files_with_data, len(READ_TARGETS))
    )
    lines.append("")

    # --- Write-back summary ---
    lines.append("### Write-Back Results")
    if not write_results:
        lines.append("No outcomes to write back.")
    else:
        success_count = 0
        error_count = 0
        for filename, result in write_results.items():
            status = result if isinstance(result, str) else str(result)
            if status.startswith("ERROR"):
                error_count += 1
                lines.append("- **%s**: FAILED -- %s" % (filename, status))
            else:
                success_count += 1
                lines.append("- **%s**: %s" % (filename, status))

        lines.append("")
        lines.append(
            "**Total:** %d successful, %d failed"
            % (success_count, error_count)
        )

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. parse_tracker_outcomes
# ---------------------------------------------------------------------------


def parse_tracker_outcomes(
    tracker_path: Path = TRACKER_PATH,
) -> List[dict]:
    """Read the outreach tracker CSV and extract outcome signals.

    Only includes rows where Status == "Sent". Skips rows with neutral
    outcomes (No Response, Bounced, Wrong Contact) -- these carry no
    effectiveness signal.

    The tracker CSV is READ-ONLY -- this function never writes to it.

    Args:
        tracker_path: Path to the outreach tracker CSV file.

    Returns:
        List of outcome dicts with: date, company, contact, fit_tier,
        outcome, is_positive. Returns empty list if file does not exist.
    """
    if not tracker_path.exists():
        return []

    outcomes = []

    try:
        with open(tracker_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Only include sent outreach
                status = row.get("Status", "").strip()
                if status != "Sent":
                    continue

                outcome = row.get("Outcome", "").strip()

                # Skip neutral outcomes -- no effectiveness signal
                if outcome in NEUTRAL_OUTCOMES or not outcome:
                    continue

                is_positive = outcome in POSITIVE_OUTCOMES

                outcomes.append({
                    "date": row.get("Date", "").strip(),
                    "company": row.get("Company", "").strip(),
                    "contact": row.get("Contact_Name", "").strip(),
                    "fit_tier": row.get("Fit_Tier", "").strip(),
                    "outcome": outcome,
                    "is_positive": is_positive,
                })
    except Exception:
        # Tracker read failure should not block pipeline
        return []

    return outcomes


# ---------------------------------------------------------------------------
# 8. aggregate_tactic_stats
# ---------------------------------------------------------------------------


def aggregate_tactic_stats(
    outcomes: List[dict],
    context_snapshot: Dict[str, str],
) -> Dict[str, dict]:
    """Group outcomes by tactic and count positive/negative signals.

    A "tactic" is a pain point, positioning angle, or ICP segment that
    was likely used in outreach. Since the tracker does not record which
    specific tactic was used, this uses keyword matching:

    - Pain points: search pain-points.md entries for company/industry overlap
    - ICP segments: use fit_tier as proxy
    - Positioning: match positioning.md entry keywords

    Args:
        outcomes: List of outcome dicts from parse_tracker_outcomes().
        context_snapshot: Dict from pre_read_context().

    Returns:
        Dict of {tactic_name: {"sent": N, "positive": M, "negative": K}}.
    """
    tactic_stats = {}

    # Extract pain point keywords from context
    pain_keywords = []
    pain_content = context_snapshot.get("pain-points.md", "")
    if pain_content:
        entries = parse_context_file(pain_content)
        for entry in entries:
            detail = entry.detail or ""
            if detail:
                pain_keywords.append(detail.lower())

    # Extract positioning keywords from context
    positioning_keywords = []
    pos_content = context_snapshot.get("positioning.md", "")
    if pos_content:
        entries = parse_context_file(pos_content)
        for entry in entries:
            detail = entry.detail or ""
            if detail:
                positioning_keywords.append(detail.lower())

    def _update_tactic(name, is_positive):
        """Helper to increment tactic counters."""
        if name not in tactic_stats:
            tactic_stats[name] = {"sent": 0, "positive": 0, "negative": 0}
        tactic_stats[name]["sent"] += 1
        if is_positive:
            tactic_stats[name]["positive"] += 1
        else:
            tactic_stats[name]["negative"] += 1

    for outcome in outcomes:
        company_lower = outcome.get("company", "").lower()
        is_positive = outcome.get("is_positive", False)

        # --- ICP segment tactic (fit_tier as proxy) ---
        fit_tier = outcome.get("fit_tier", "").strip()
        if fit_tier:
            tactic_name = "icp-%s" % fit_tier.lower().replace(" ", "-")
            _update_tactic(tactic_name, is_positive)

        # --- Pain point tactics (keyword match on company name) ---
        for keyword in pain_keywords:
            # Check if any pain keyword words appear in company context
            kw_words = keyword.split("-")
            if any(w in company_lower for w in kw_words if len(w) >= 3):
                tactic_name = "pain-%s" % keyword
                _update_tactic(tactic_name, is_positive)

        # --- Positioning tactics (keyword match) ---
        for keyword in positioning_keywords:
            kw_words = keyword.split("-")
            if any(w in company_lower for w in kw_words if len(w) >= 3):
                tactic_name = "pos-%s" % keyword
                _update_tactic(tactic_name, is_positive)

    return tactic_stats


# ---------------------------------------------------------------------------
# 9. apply_cold_start_gate
# ---------------------------------------------------------------------------


def apply_cold_start_gate(
    tactic_stats: Dict[str, dict],
) -> Dict[str, dict]:
    """Apply cold-start protection to tactic effectiveness scores.

    For each tactic, calculates effectiveness_score = positive / (positive + negative)
    only when sample_size >= MINIMUM_SAMPLE_SIZE. Otherwise suppresses with
    score=None and a note indicating how many more data points are needed.

    Sample size = positive + negative (only explicit signals count, not total sent).

    Implements LRNG-04 (cold-start protection) and architecture spec V10.

    Args:
        tactic_stats: Dict from aggregate_tactic_stats().

    Returns:
        Dict of {tactic_name: {effectiveness_score, sample_size, suppressed, note}}.
    """
    results = {}

    for tactic_name, stats in tactic_stats.items():
        positive = stats.get("positive", 0)
        negative = stats.get("negative", 0)
        sample_size = positive + negative

        if sample_size >= MINIMUM_SAMPLE_SIZE:
            score = positive / sample_size if sample_size > 0 else 0.0
            results[tactic_name] = {
                "effectiveness_score": score,
                "sample_size": sample_size,
                "suppressed": False,
                "note": None,
            }
        else:
            needed = MINIMUM_SAMPLE_SIZE - sample_size
            results[tactic_name] = {
                "effectiveness_score": None,
                "sample_size": sample_size,
                "suppressed": True,
                "note": "Need %d more data points" % needed,
            }

    return results


# ---------------------------------------------------------------------------
# 10. write_effectiveness_data
# ---------------------------------------------------------------------------


def write_effectiveness_data(
    effectiveness_results: Dict[str, dict],
    agent_id: str = AGENT_ID,
) -> dict:
    """Write effectiveness results to _learning/gtm-learning.md.

    Creates _learning/ directory if it does not exist. Formats results as
    a standard context entry with one content line per tactic showing its
    score, sample size, and suppression status.

    Effectiveness write failure should NOT block the main pipeline.

    Args:
        effectiveness_results: Dict from apply_cold_start_gate().
        agent_id: Agent ID for context store writes.

    Returns:
        Dict with write status: {"written": bool, "result": str, "error": str|None}.
    """
    # Create _learning/ directory if needed
    LEARNING_DIR.mkdir(parents=True, exist_ok=True)

    # Format content lines -- one per tactic
    content_lines = []
    for tactic_name, data in sorted(effectiveness_results.items()):
        score = data.get("effectiveness_score")
        sample_size = data.get("sample_size", 0)
        suppressed = data.get("suppressed", False)

        if suppressed:
            note = data.get("note", "insufficient data")
            content_lines.append(
                "%s: SUPPRESSED (sample=%d, %s)" % (tactic_name, sample_size, note)
            )
        else:
            content_lines.append(
                "%s: score=%.2f (sample=%d)" % (tactic_name, score, sample_size)
            )

    if not content_lines:
        return {"written": False, "result": "no data", "error": None}

    today = datetime.now().strftime("%Y-%m-%d")

    entry = {
        "date": today,
        "source": agent_id,
        "detail": "outreach-effectiveness-batch",
        "content": content_lines,
        "confidence": "medium",
        "evidence_count": 1,
    }

    try:
        result = append_entry(
            file="_learning/gtm-learning.md",
            entry=entry,
            source=agent_id,
            agent_id=agent_id,
        )

        log_event(
            event_type="effectiveness-write",
            file="_learning/gtm-learning.md",
            agent_id=agent_id,
            detail=json.dumps({
                "tactic_count": len(effectiveness_results),
                "suppressed_count": sum(
                    1 for d in effectiveness_results.values() if d.get("suppressed")
                ),
            }),
        )

        return {"written": True, "result": result, "error": None}

    except Exception as e:
        # Effectiveness write failure should not block pipeline
        return {"written": False, "result": "ERROR", "error": str(e)}


# ---------------------------------------------------------------------------
# 11. run_effectiveness_tracking
# ---------------------------------------------------------------------------


def run_effectiveness_tracking(
    context_snapshot: Optional[Dict[str, str]] = None,
    agent_id: str = AGENT_ID,
) -> dict:
    """Run the full effectiveness tracking pipeline.

    Orchestrates: parse tracker -> aggregate tactics -> apply cold-start gate ->
    write effectiveness data. Returns a summary dict.

    Args:
        context_snapshot: Pre-loaded context snapshot. If None, calls
            pre_read_context() to load fresh data.
        agent_id: Agent ID for context store operations.

    Returns:
        Dict with: tactic_count, suppressed_count, written, outcomes_parsed.
    """
    # Step 1: Parse tracker outcomes
    outcomes = parse_tracker_outcomes()

    if not outcomes:
        return {
            "outcomes_parsed": 0,
            "tactic_count": 0,
            "suppressed_count": 0,
            "written": False,
        }

    # Step 2: Load context if not provided
    if context_snapshot is None:
        context_snapshot = pre_read_context(agent_id)

    # Step 3: Aggregate tactic stats
    tactic_stats = aggregate_tactic_stats(outcomes, context_snapshot)

    if not tactic_stats:
        return {
            "outcomes_parsed": len(outcomes),
            "tactic_count": 0,
            "suppressed_count": 0,
            "written": False,
        }

    # Step 4: Apply cold-start gate
    effectiveness_results = apply_cold_start_gate(tactic_stats)

    # Step 5: Write effectiveness data
    write_result = write_effectiveness_data(effectiveness_results, agent_id)

    # Step 6: Return summary
    suppressed_count = sum(
        1 for d in effectiveness_results.values() if d.get("suppressed")
    )

    return {
        "outcomes_parsed": len(outcomes),
        "tactic_count": len(effectiveness_results),
        "suppressed_count": suppressed_count,
        "written": write_result.get("written", False),
    }
