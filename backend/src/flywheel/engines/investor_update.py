"""
investor_update.py - Context store consumer engine for ctx-investor-update.

Read-only consumer that reads compounded knowledge from the context store
to generate intelligence for monthly investor updates. Synthesizes meeting
intelligence, competitive landscape, positioning data, and product signals
without manual file reconciliation.

The SKILL.md prompt handles user interaction and document generation;
this module handles deterministic context store reads and data synthesis.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from flywheel.storage_backend import (
    list_context_files,
    parse_context_file,
    query_context,
    read_context,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENT_ID = "ctx-investor-update"

# Skill-local state file for cumulative cross-invocation context.
# This is NOT a context store file -- it stores promise ledger, narrative arc,
# prior months data, and stale threads that don't fit the append-only entry format.
_DATA_DIR = os.environ.get("FLYWHEEL_DATA_DIR", str(Path.home() / "lumifai"))
UPDATE_CONTEXT_PATH = Path(_DATA_DIR) / "investor-updates" / "_update-context.md"

# Context files read by category
MEETING_INTEL_FILES = [
    "insights.md",
    "contacts.md",
    "pain-points.md",
    "competitive-intel.md",
    "action-items.md",
]

POSITIONING_FILES = [
    "positioning.md",
    "icp-profiles.md",
    "competitive-intel.md",
]

PRODUCT_SIGNAL_FILES = [
    "product-feedback.md",
    "pain-points.md",
]


# ---------------------------------------------------------------------------
# Helper: date filtering
# ---------------------------------------------------------------------------


def _parse_entry_date(entry) -> Optional[datetime]:
    """Safely extract datetime from a ContextEntry."""
    if hasattr(entry, "date") and isinstance(entry.date, datetime):
        return entry.date
    return None


def _is_after(entry, since_date: datetime) -> bool:
    """Check if an entry's date is on or after since_date."""
    entry_dt = _parse_entry_date(entry)
    if entry_dt is None:
        return False
    return entry_dt >= since_date


def _parse_since_date(since_date: str) -> datetime:
    """Parse a YYYY-MM-DD string into datetime."""
    return datetime.strptime(since_date, "%Y-%m-%d")


def _safe_read_file(filename: str, context_snapshot: dict) -> str:
    """Get file content from snapshot, returning empty string if missing."""
    return context_snapshot.get(filename, "")


# ---------------------------------------------------------------------------
# 1. pre_read_context
# ---------------------------------------------------------------------------


def pre_read_context(agent_id: str = AGENT_ID) -> dict:
    """Read all context files and return a dict keyed by filename.

    Same pattern as meeting_processor.py. Returns {filename: raw_content_string}
    for each context file. This snapshot is passed to all gather functions.
    """
    context_snapshot = {}

    try:
        files = list_context_files()
    except Exception:
        return context_snapshot

    for filename in files:
        try:
            content = read_context(filename, agent_id)
            context_snapshot[filename] = content
        except Exception:
            # Partial read failure is acceptable -- skip file
            context_snapshot[filename] = ""

    return context_snapshot


# ---------------------------------------------------------------------------
# 2. gather_meeting_intelligence
# ---------------------------------------------------------------------------


def gather_meeting_intelligence(
    existing_context: dict,
    since_date: str,
) -> dict:
    """Extract meeting-derived intelligence from the context store for a period.

    Parses entries from insights.md, contacts.md, pain-points.md,
    competitive-intel.md, and action-items.md. Filters by date.

    Args:
        existing_context: Dict from pre_read_context().
        since_date: YYYY-MM-DD string -- only entries on or after this date.

    Returns:
        Dict with keys: key_meetings, new_contacts, pain_point_trends,
        competitive_moves, open_actions.
    """
    result = {
        "key_meetings": [],
        "new_contacts": [],
        "pain_point_trends": [],
        "competitive_moves": [],
        "open_actions": [],
    }

    cutoff = _parse_since_date(since_date)

    # Key meetings from insights.md
    content = _safe_read_file("insights.md", existing_context)
    if content:
        entries = parse_context_file(content)
        for entry in entries:
            if _is_after(entry, cutoff):
                summary = "; ".join(entry.content) if entry.content else entry.detail
                result["key_meetings"].append({
                    "date": entry.date.strftime("%Y-%m-%d"),
                    "detail": entry.detail,
                    "summary": summary,
                    "confidence": entry.confidence,
                    "source": entry.source,
                })

    # New contacts from contacts.md
    content = _safe_read_file("contacts.md", existing_context)
    if content:
        entries = parse_context_file(content)
        for entry in entries:
            if _is_after(entry, cutoff):
                result["new_contacts"].append({
                    "date": entry.date.strftime("%Y-%m-%d"),
                    "detail": entry.detail,
                    "contacts": entry.content,
                    "source": entry.source,
                })

    # Pain point trends from pain-points.md
    content = _safe_read_file("pain-points.md", existing_context)
    if content:
        entries = parse_context_file(content)
        for entry in entries:
            if _is_after(entry, cutoff):
                result["pain_point_trends"].append({
                    "date": entry.date.strftime("%Y-%m-%d"),
                    "detail": entry.detail,
                    "points": entry.content,
                    "evidence": entry.evidence_count,
                    "source": entry.source,
                })

    # Competitive moves from competitive-intel.md
    content = _safe_read_file("competitive-intel.md", existing_context)
    if content:
        entries = parse_context_file(content)
        for entry in entries:
            if _is_after(entry, cutoff):
                result["competitive_moves"].append({
                    "date": entry.date.strftime("%Y-%m-%d"),
                    "detail": entry.detail,
                    "intel": entry.content,
                    "source": entry.source,
                })

    # Open actions from action-items.md
    content = _safe_read_file("action-items.md", existing_context)
    if content:
        entries = parse_context_file(content)
        for entry in entries:
            if _is_after(entry, cutoff):
                result["open_actions"].append({
                    "date": entry.date.strftime("%Y-%m-%d"),
                    "detail": entry.detail,
                    "actions": entry.content,
                    "source": entry.source,
                })

    return result


# ---------------------------------------------------------------------------
# 3. gather_positioning_snapshot
# ---------------------------------------------------------------------------


def gather_positioning_snapshot(existing_context: dict) -> dict:
    """Read current positioning, ICP data, and competitive landscape.

    Uses the most recent entries (sorted by date) to get current state.

    Args:
        existing_context: Dict from pre_read_context().

    Returns:
        Dict with current_positioning, icp_summary, competitive_landscape.
    """
    result = {
        "current_positioning": [],
        "icp_summary": [],
        "competitive_landscape": [],
    }

    # Current positioning from positioning.md (latest entry)
    content = _safe_read_file("positioning.md", existing_context)
    if content:
        entries = parse_context_file(content)
        if entries:
            # Sort by date descending, take latest
            sorted_entries = sorted(
                entries,
                key=lambda e: e.date if isinstance(e.date, datetime) else datetime.min,
                reverse=True,
            )
            latest = sorted_entries[0]
            result["current_positioning"] = latest.content

    # ICP summary from icp-profiles.md (latest entries)
    content = _safe_read_file("icp-profiles.md", existing_context)
    if content:
        entries = parse_context_file(content)
        if entries:
            sorted_entries = sorted(
                entries,
                key=lambda e: e.date if isinstance(e.date, datetime) else datetime.min,
                reverse=True,
            )
            # Take up to 5 most recent ICP entries
            for entry in sorted_entries[:5]:
                result["icp_summary"].append({
                    "date": entry.date.strftime("%Y-%m-%d") if isinstance(entry.date, datetime) else "unknown",
                    "detail": entry.detail,
                    "profile": entry.content,
                    "confidence": entry.confidence,
                })

    # Competitive landscape from competitive-intel.md (all recent, deduplicated)
    content = _safe_read_file("competitive-intel.md", existing_context)
    if content:
        entries = parse_context_file(content)
        if entries:
            sorted_entries = sorted(
                entries,
                key=lambda e: e.date if isinstance(e.date, datetime) else datetime.min,
                reverse=True,
            )
            # Take up to 10 most recent competitive intel entries
            for entry in sorted_entries[:10]:
                result["competitive_landscape"].append({
                    "date": entry.date.strftime("%Y-%m-%d") if isinstance(entry.date, datetime) else "unknown",
                    "detail": entry.detail,
                    "intel": entry.content,
                    "source": entry.source,
                })

    return result


# ---------------------------------------------------------------------------
# 4. gather_product_signals
# ---------------------------------------------------------------------------


def gather_product_signals(
    existing_context: dict,
    since_date: str,
) -> dict:
    """Read product-relevant signals from context store.

    Reads product-feedback.md and pain-points.md for the given period.

    Args:
        existing_context: Dict from pre_read_context().
        since_date: YYYY-MM-DD string.

    Returns:
        Dict with feature_requests, pain_points_addressed, product_feedback.
    """
    result = {
        "feature_requests": [],
        "pain_points_addressed": [],
        "product_feedback": [],
    }

    cutoff = _parse_since_date(since_date)

    # Product feedback from product-feedback.md
    content = _safe_read_file("product-feedback.md", existing_context)
    if content:
        entries = parse_context_file(content)
        for entry in entries:
            if _is_after(entry, cutoff):
                # Classify feedback lines
                for line in entry.content:
                    line_lower = line.lower()
                    if any(kw in line_lower for kw in ["request", "want", "need", "wish", "would like", "feature"]):
                        result["feature_requests"].append({
                            "date": entry.date.strftime("%Y-%m-%d"),
                            "request": line,
                            "source": entry.source,
                            "detail": entry.detail,
                        })
                    else:
                        result["product_feedback"].append({
                            "date": entry.date.strftime("%Y-%m-%d"),
                            "feedback": line,
                            "source": entry.source,
                            "detail": entry.detail,
                        })

    # Pain points addressed from pain-points.md
    content = _safe_read_file("pain-points.md", existing_context)
    if content:
        entries = parse_context_file(content)
        for entry in entries:
            if _is_after(entry, cutoff):
                result["pain_points_addressed"].append({
                    "date": entry.date.strftime("%Y-%m-%d"),
                    "detail": entry.detail,
                    "points": entry.content,
                    "evidence": entry.evidence_count,
                })

    return result


# ---------------------------------------------------------------------------
# 5. synthesize_update_sections
# ---------------------------------------------------------------------------


def synthesize_update_sections(
    meeting_intel: dict,
    positioning: dict,
    product_signals: dict,
) -> dict:
    """Combine gather results into structured sections for the investor update.

    Each section is a list of formatted strings ready for the update narrative.

    Args:
        meeting_intel: From gather_meeting_intelligence().
        positioning: From gather_positioning_snapshot().
        product_signals: From gather_product_signals().

    Returns:
        Dict with traction_signals, market_intelligence, product_evolution,
        key_themes.
    """
    sections = {
        "traction_signals": [],
        "market_intelligence": [],
        "product_evolution": [],
        "key_themes": [],
    }

    # -- Traction Signals: meetings, contacts, pipeline --
    meetings = meeting_intel.get("key_meetings", [])
    contacts = meeting_intel.get("new_contacts", [])
    actions = meeting_intel.get("open_actions", [])

    if meetings:
        sections["traction_signals"].append(
            "%d meetings/interactions recorded in the period" % len(meetings)
        )
        for m in meetings[:5]:  # Top 5
            sections["traction_signals"].append(
                "  - [%s] %s" % (m["date"], m["summary"][:200])
            )

    if contacts:
        total_contacts = sum(len(c.get("contacts", [])) for c in contacts)
        sections["traction_signals"].append(
            "%d new contacts added from %d interactions" % (total_contacts, len(contacts))
        )

    if actions:
        total_actions = sum(len(a.get("actions", [])) for a in actions)
        sections["traction_signals"].append(
            "%d action items tracked across meetings" % total_actions
        )

    # -- Market Intelligence: competitive, positioning --
    competitive = meeting_intel.get("competitive_moves", [])
    landscape = positioning.get("competitive_landscape", [])
    current_pos = positioning.get("current_positioning", [])

    if current_pos:
        sections["market_intelligence"].append("Current positioning:")
        for line in current_pos[:5]:
            sections["market_intelligence"].append("  - %s" % line)

    if competitive:
        sections["market_intelligence"].append(
            "%d competitive intelligence entries from meetings" % len(competitive)
        )
        for c in competitive[:3]:
            intel_summary = "; ".join(c.get("intel", []))[:200]
            sections["market_intelligence"].append(
                "  - [%s] %s" % (c["date"], intel_summary)
            )

    if landscape:
        sections["market_intelligence"].append(
            "%d total competitive landscape entries tracked" % len(landscape)
        )

    # -- Product Evolution: feedback, pain points --
    feature_reqs = product_signals.get("feature_requests", [])
    feedback = product_signals.get("product_feedback", [])
    pain_points = product_signals.get("pain_points_addressed", [])

    if feature_reqs:
        sections["product_evolution"].append(
            "%d feature requests captured" % len(feature_reqs)
        )
        for fr in feature_reqs[:5]:
            sections["product_evolution"].append(
                "  - %s" % fr["request"][:200]
            )

    if feedback:
        sections["product_evolution"].append(
            "%d product feedback items recorded" % len(feedback)
        )

    if pain_points:
        total_evidence = sum(pp.get("evidence", 1) for pp in pain_points)
        sections["product_evolution"].append(
            "%d pain point entries with %d total evidence points" % (
                len(pain_points), total_evidence
            )
        )

    # -- Key Themes: cross-cutting patterns --
    # Identify recurring themes across all data sources
    all_content = []
    for m in meetings:
        all_content.append(m.get("summary", ""))
    for c in competitive:
        all_content.extend(c.get("intel", []))
    for fr in feature_reqs:
        all_content.append(fr.get("request", ""))
    for pp in pain_points:
        all_content.extend(pp.get("points", []))

    if all_content:
        # Simple theme detection via word frequency
        word_counts = {}
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "and", "but", "or", "nor", "not", "so",
            "yet", "both", "either", "neither", "each", "every", "all",
            "any", "few", "more", "most", "other", "some", "such", "no",
            "only", "own", "same", "than", "too", "very", "just", "that",
            "this", "these", "those", "it", "its", "they", "them", "their",
            "we", "us", "our", "you", "your", "he", "him", "his", "she",
            "her", "i", "me", "my", "about", "up", "out", "one", "also",
        }
        for text in all_content:
            words = re.findall(r"\b[a-z]{4,}\b", text.lower())
            for w in words:
                if w not in stop_words:
                    word_counts[w] = word_counts.get(w, 0) + 1

        # Top themes (words appearing 2+ times)
        themes = sorted(
            [(w, c) for w, c in word_counts.items() if c >= 2],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        if themes:
            sections["key_themes"].append("Recurring themes across data sources:")
            for word, count in themes:
                sections["key_themes"].append(
                    "  - \"%s\" (mentioned %d times)" % (word, count)
                )

    return sections


# ---------------------------------------------------------------------------
# 6. format_context_intelligence_section
# ---------------------------------------------------------------------------


def format_context_intelligence_section(
    meeting_intel: dict,
    positioning: dict,
    product_signals: dict,
    context_file_count: int,
) -> str:
    """Format a 'Context Store Intelligence' section for the investor update.

    Shows what was auto-populated from the context store as proof that
    the flywheel is working. Includes stats and grouped categories.

    Args:
        meeting_intel: From gather_meeting_intelligence().
        positioning: From gather_positioning_snapshot().
        product_signals: From gather_product_signals().
        context_file_count: Number of context files read.

    Returns:
        Formatted markdown string for the intelligence section.
    """
    lines = []
    lines.append("## Context Store Intelligence")
    lines.append("")

    # Calculate totals
    total_entries = 0
    period_entries = 0

    # Meeting intel counts
    for key in ["key_meetings", "new_contacts", "pain_point_trends",
                "competitive_moves", "open_actions"]:
        items = meeting_intel.get(key, [])
        period_entries += len(items)
        total_entries += len(items)

    # Positioning counts (these are current snapshot, not period-filtered)
    for key in ["current_positioning", "icp_summary", "competitive_landscape"]:
        items = positioning.get(key, [])
        if isinstance(items, list):
            total_entries += len(items)

    # Product signal counts
    for key in ["feature_requests", "pain_points_addressed", "product_feedback"]:
        items = product_signals.get(key, [])
        period_entries += len(items)
        total_entries += len(items)

    lines.append("**Auto-populated from context store:** %d files read, "
                  "%d total entries, %d entries from reporting period" % (
                      context_file_count, total_entries, period_entries))
    lines.append("")

    # Group by category
    lines.append("### Meeting Intelligence")
    meetings = meeting_intel.get("key_meetings", [])
    contacts = meeting_intel.get("new_contacts", [])
    actions = meeting_intel.get("open_actions", [])
    lines.append("- %d meetings recorded" % len(meetings))
    lines.append("- %d contact entries" % len(contacts))
    lines.append("- %d action item entries" % len(actions))
    lines.append("")

    lines.append("### Competitive & Positioning")
    competitive_period = meeting_intel.get("competitive_moves", [])
    competitive_all = positioning.get("competitive_landscape", [])
    pos = positioning.get("current_positioning", [])
    icp = positioning.get("icp_summary", [])
    lines.append("- %d competitive intel entries (period)" % len(competitive_period))
    lines.append("- %d total competitive landscape entries" % len(competitive_all))
    lines.append("- %d positioning lines" % len(pos))
    lines.append("- %d ICP profile entries" % len(icp))
    lines.append("")

    lines.append("### Product Signals")
    feature_reqs = product_signals.get("feature_requests", [])
    feedback = product_signals.get("product_feedback", [])
    pain_points = product_signals.get("pain_points_addressed", [])
    lines.append("- %d feature requests" % len(feature_reqs))
    lines.append("- %d product feedback items" % len(feedback))
    lines.append("- %d pain point entries" % len(pain_points))
    lines.append("")

    lines.append("*This data was gathered automatically from the context store. "
                  "No manual file reconciliation required.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. generate_intelligence_report
# ---------------------------------------------------------------------------


def generate_intelligence_report(
    existing_context: dict,
    since_date: str,
) -> Tuple[dict, dict, dict, str]:
    """Main entry point: gather all intelligence and return formatted report.

    Calls gather_meeting_intelligence, gather_positioning_snapshot,
    gather_product_signals, and formats the intelligence report.

    Args:
        existing_context: Dict from pre_read_context().
        since_date: YYYY-MM-DD string for the reporting period start.

    Returns:
        Tuple of (meeting_intel, positioning, product_signals, report_string).
    """
    meeting_intel = gather_meeting_intelligence(existing_context, since_date)
    positioning = gather_positioning_snapshot(existing_context)
    product_signals = gather_product_signals(existing_context, since_date)

    context_file_count = len(existing_context)

    report = format_context_intelligence_section(
        meeting_intel, positioning, product_signals, context_file_count
    )

    return meeting_intel, positioning, product_signals, report


# ---------------------------------------------------------------------------
# 8. Cumulative context: read/write _update-context.md
# ---------------------------------------------------------------------------


def _empty_update_context() -> dict:
    """Return the default empty structure for cumulative update context.

    Used on cold start when _update-context.md does not exist yet.
    """
    return {
        "promises": [],
        "narrative_arc": {
            "chapter_number": 1,
            "title": "Getting Started",
            "months_covered": "",
            "key_theme": "",
        },
        "prior_months": [],
        "stale_threads": [],
        "metrics": [],
        "positioning_evolution": [],
    }


def read_update_context() -> dict:
    """Read cumulative update context from skill-local state file.

    Returns dict with keys: promises, narrative_arc, prior_months,
    stale_threads, metrics, positioning_evolution.

    Returns empty dict structure if file doesn't exist (cold start).
    """
    if not UPDATE_CONTEXT_PATH.exists():
        return _empty_update_context()

    try:
        raw = UPDATE_CONTEXT_PATH.read_text(encoding="utf-8")
    except (OSError, IOError):
        return _empty_update_context()

    ctx = _empty_update_context()

    # Parse structured markdown sections
    current_section = None
    current_item = {}

    for line in raw.splitlines():
        stripped = line.strip()

        # Section headers
        if stripped.startswith("## Promises") or stripped.startswith("## Promise Ledger"):
            current_section = "promises"
            current_item = {}
            continue
        elif stripped.startswith("## Narrative Arc"):
            current_section = "narrative_arc"
            continue
        elif stripped.startswith("## Prior Months"):
            current_section = "prior_months"
            continue
        elif stripped.startswith("## Stale Threads"):
            current_section = "stale_threads"
            continue
        elif stripped.startswith("## Metrics"):
            current_section = "metrics"
            continue
        elif stripped.startswith("## Positioning"):
            current_section = "positioning_evolution"
            continue
        elif stripped.startswith("## "):
            current_section = None
            continue

        if not stripped:
            # Flush any accumulated promise item
            if current_section == "promises" and current_item.get("text"):
                ctx["promises"].append(current_item)
                current_item = {}
            continue

        # Parse content based on section
        if current_section == "promises":
            if stripped.startswith("- text:"):
                if current_item.get("text"):
                    ctx["promises"].append(current_item)
                current_item = {"text": stripped[7:].strip(), "date": "", "status": "open", "evidence": ""}
            elif stripped.startswith("  date:") or stripped.startswith("date:"):
                current_item["date"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("  status:") or stripped.startswith("status:"):
                current_item["status"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("  evidence:") or stripped.startswith("evidence:"):
                current_item["evidence"] = stripped.split(":", 1)[1].strip()

        elif current_section == "narrative_arc":
            if stripped.startswith("- chapter:") or stripped.startswith("chapter:"):
                try:
                    ctx["narrative_arc"]["chapter_number"] = int(stripped.split(":", 1)[1].strip())
                except (ValueError, IndexError):
                    pass
            elif stripped.startswith("- title:") or stripped.startswith("title:"):
                ctx["narrative_arc"]["title"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- months:") or stripped.startswith("months:"):
                ctx["narrative_arc"]["months_covered"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- theme:") or stripped.startswith("theme:"):
                ctx["narrative_arc"]["key_theme"] = stripped.split(":", 1)[1].strip()

        elif current_section == "prior_months":
            if stripped.startswith("- "):
                # Each prior month entry: "- YYYY-MM: topic1, topic2, topic3"
                parts = stripped[2:].split(":", 1)
                if len(parts) == 2:
                    month_id = parts[0].strip()
                    topics = [t.strip() for t in parts[1].split(",") if t.strip()]
                    ctx["prior_months"].append({"month": month_id, "topics": topics})

        elif current_section == "stale_threads":
            if stripped.startswith("- "):
                parts = stripped[2:].split("|")
                if len(parts) >= 2:
                    ctx["stale_threads"].append({
                        "topic": parts[0].strip(),
                        "last_mentioned": parts[1].strip() if len(parts) > 1 else "",
                        "months_stale": int(parts[2].strip()) if len(parts) > 2 else 0,
                    })
                else:
                    ctx["stale_threads"].append({
                        "topic": stripped[2:].strip(),
                        "last_mentioned": "",
                        "months_stale": 0,
                    })

        elif current_section == "metrics":
            if stripped.startswith("- "):
                ctx["metrics"].append(stripped[2:])

        elif current_section == "positioning_evolution":
            if stripped.startswith("- "):
                ctx["positioning_evolution"].append(stripped[2:])

    # Flush last promise if pending
    if current_section == "promises" and current_item.get("text"):
        ctx["promises"].append(current_item)

    return ctx


def write_update_context(context: dict) -> str:
    """Write updated cumulative context back to skill-local state file.

    Creates investor-updates/ directory under FLYWHEEL_DATA_DIR if needed.

    Args:
        context: Dict with keys matching read_update_context() output.

    Returns:
        Path string where the file was written.
    """
    UPDATE_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# Investor Update Cumulative Context")
    lines.append("")
    lines.append("This file is managed by the investor-update skill engine.")
    lines.append("Do not edit manually unless you know what you're doing.")
    lines.append("")

    # Promises
    lines.append("## Promise Ledger")
    lines.append("")
    promises = context.get("promises", [])
    for p in promises:
        lines.append("- text: %s" % p.get("text", ""))
        lines.append("  date: %s" % p.get("date", ""))
        lines.append("  status: %s" % p.get("status", "open"))
        lines.append("  evidence: %s" % p.get("evidence", ""))
        lines.append("")

    # Narrative Arc
    lines.append("## Narrative Arc")
    lines.append("")
    arc = context.get("narrative_arc", {})
    lines.append("- chapter: %s" % arc.get("chapter_number", 1))
    lines.append("- title: %s" % arc.get("title", ""))
    lines.append("- months: %s" % arc.get("months_covered", ""))
    lines.append("- theme: %s" % arc.get("key_theme", ""))
    lines.append("")

    # Prior Months
    lines.append("## Prior Months")
    lines.append("")
    for pm in context.get("prior_months", []):
        topics_str = ", ".join(pm.get("topics", []))
        lines.append("- %s: %s" % (pm.get("month", ""), topics_str))
    lines.append("")

    # Stale Threads
    lines.append("## Stale Threads")
    lines.append("")
    for st in context.get("stale_threads", []):
        lines.append("- %s | %s | %s" % (
            st.get("topic", ""),
            st.get("last_mentioned", ""),
            st.get("months_stale", 0),
        ))
    lines.append("")

    # Metrics
    lines.append("## Metrics")
    lines.append("")
    for m in context.get("metrics", []):
        lines.append("- %s" % m)
    lines.append("")

    # Positioning Evolution
    lines.append("## Positioning Evolution")
    lines.append("")
    for pe in context.get("positioning_evolution", []):
        lines.append("- %s" % pe)
    lines.append("")

    content = "\n".join(lines)
    UPDATE_CONTEXT_PATH.write_text(content, encoding="utf-8")
    return str(UPDATE_CONTEXT_PATH)


# ---------------------------------------------------------------------------
# 9. Promise ledger functions
# ---------------------------------------------------------------------------


def read_promise_ledger() -> list:
    """Extract promise entries from update context.

    Each promise is a dict with keys: text, date, status, evidence.
    Returns empty list on cold start.
    """
    ctx = read_update_context()
    return ctx.get("promises", [])


def update_promise_status(promises: list, current_data: dict) -> list:
    """Check current context store data for evidence that promises were delivered.

    Updates status field:
    - open -> delivered (if evidence found in current data)
    - open -> stale (if >2 months old with no progress)
    Status already 'delivered' or 'dropped' is not changed.

    Args:
        promises: List of promise dicts from read_promise_ledger().
        current_data: Dict from pre_read_context() (context store snapshot).

    Returns:
        Updated list of promise dicts with status changes applied.
    """
    if not promises:
        return []

    # Build a search corpus from all context store content
    corpus = ""
    for filename, content in current_data.items():
        corpus += " " + content.lower()

    now = datetime.now()
    updated = []

    for promise in promises:
        p = dict(promise)  # Don't mutate original

        # Skip already-resolved promises
        if p.get("status") in ("delivered", "dropped"):
            updated.append(p)
            continue

        # Check for evidence in context store
        promise_text = p.get("text", "").lower()
        # Extract key phrases (words 4+ chars) from the promise
        key_words = re.findall(r"\b[a-z]{4,}\b", promise_text)
        # Remove common stop words
        stop = {"that", "this", "with", "from", "will", "have", "been", "more",
                "than", "they", "each", "also", "into", "over", "such", "after"}
        key_words = [w for w in key_words if w not in stop]

        if key_words:
            # Count how many key words appear in corpus
            matches = sum(1 for w in key_words if w in corpus)
            match_ratio = matches / len(key_words) if key_words else 0

            if match_ratio >= 0.6:
                p["status"] = "delivered"
                p["evidence"] = "Key terms found in context store (%d/%d matched)" % (
                    matches, len(key_words)
                )
                updated.append(p)
                continue

        # Check for staleness (>2 months old with no progress)
        promise_date_str = p.get("date", "")
        if promise_date_str:
            try:
                promise_date = datetime.strptime(promise_date_str, "%Y-%m-%d")
                months_old = (now.year - promise_date.year) * 12 + (now.month - promise_date.month)
                if months_old >= 2:
                    p["status"] = "stale"
                    p["evidence"] = "No evidence found, %d months since promise date" % months_old
            except (ValueError, TypeError):
                pass

        updated.append(p)

    return updated


# ---------------------------------------------------------------------------
# 10. Stale thread detection
# ---------------------------------------------------------------------------


def detect_stale_threads(
    current_topics: list,
    prior_months: list,
    threshold_months: int = 2,
) -> list:
    """Find topics mentioned in prior months but not in current_topics.

    Args:
        current_topics: List of topic strings from the current month.
        prior_months: List of dicts with 'month' and 'topics' keys,
                      from read_update_context()['prior_months'].
        threshold_months: How many months of absence before a topic is stale.

    Returns:
        List of dicts with keys: topic, last_mentioned, months_stale.
    """
    if not prior_months:
        return []

    # Normalize current topics for comparison
    current_lower = set()
    for t in current_topics:
        if t:
            current_lower.add(t.lower().strip())

    # Build a map of all prior topics -> last month mentioned
    topic_last_seen = {}  # topic_lower -> (month_str, index)
    for i, pm in enumerate(prior_months):
        month_str = pm.get("month", "")
        for topic in pm.get("topics", []):
            topic_lower = topic.lower().strip()
            if topic_lower:
                # Later entries override earlier ones (more recent)
                topic_last_seen[topic_lower] = (month_str, i)

    if not topic_last_seen:
        return []

    # Calculate staleness
    total_months = len(prior_months)
    stale = []

    for topic_lower, (last_month, index) in topic_last_seen.items():
        # Check if topic appears in current month
        in_current = any(topic_lower in ct for ct in current_lower) or \
                     any(ct in topic_lower for ct in current_lower if len(ct) > 3)

        if not in_current:
            months_since = total_months - index
            if months_since >= threshold_months:
                stale.append({
                    "topic": topic_lower,
                    "last_mentioned": last_month,
                    "months_stale": months_since,
                })

    # Sort by staleness descending
    stale.sort(key=lambda x: x["months_stale"], reverse=True)
    return stale


# ---------------------------------------------------------------------------
# 11. Narrative arc tracking
# ---------------------------------------------------------------------------


def get_current_chapter(update_context: dict) -> dict:
    """Determine current narrative chapter from update context history.

    Returns dict with chapter_number, title, months_covered, key_theme.
    On cold start, returns a default Chapter 1 structure.

    Args:
        update_context: Dict from read_update_context().

    Returns:
        Dict with chapter_number, title, months_covered, key_theme.
    """
    arc = update_context.get("narrative_arc", {})
    return {
        "chapter_number": arc.get("chapter_number", 1),
        "title": arc.get("title", "Getting Started"),
        "months_covered": arc.get("months_covered", ""),
        "key_theme": arc.get("key_theme", ""),
    }
