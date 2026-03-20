#!/usr/bin/env python3
"""
Context Store Utilities — Programmatic interface to the shared context store.

This is the core module for context-aware skills. It implements the protocol
defined in context-protocol.md as callable Python functions.

Provides:
  - read_catalog(): Parse _catalog.md into structured inventory
  - match_tags(): Find context files matching given tags
  - load_recent_entries(): Load last N entries from a context file
  - format_entry(): Format an entry per the standard entry format
  - check_duplicate(): Composite key dedup check before writes
  - append_entry(): Append entry with backup + dedup + atomic write
  - discover_customer_file(): Auto-discover customer-specific files
  - pre_read(): Full pre-read workflow (catalog -> match -> load)
  - post_write(): Full post-write workflow (match -> dedup -> append)

Usage from skills (via bash):
  python3 ~/.claude/skills/_shared/context_utils.py pre-read --tags sales,outreach
  python3 ~/.claude/skills/_shared/context_utils.py append contacts.md --source meeting-prep --detail "john-smith" --content "- Name: John Smith\\n- Title: CTO"
  python3 ~/.claude/skills/_shared/context_utils.py check-dup contacts.md --source meeting-prep --detail "john-smith" --date 2026-03-13

Location: ~/.claude/skills/_shared/context_utils.py
Protocol: ~/.claude/skills/_shared/context-protocol.md
Catalog:  ~/.claude/context/_catalog.md
Store:    ~/.claude/context/
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime
from glob import glob


# =============================================
# FLYWHEEL CORE DELEGATION
# =============================================

_ENGINES_PATH = os.path.expanduser("~/.claude/skills/_shared/engines")
if os.path.isdir(_ENGINES_PATH) and os.path.realpath(_ENGINES_PATH) not in sys.path:
    sys.path.insert(0, os.path.realpath(_ENGINES_PATH))

try:
    import context_utils as _core
    _HAS_CORE = True
except ImportError:
    _core = None
    _HAS_CORE = False

_AGENT_ID = "context-protocol"


# =============================================
# PATHS
# =============================================

CONTEXT_DIR = os.path.expanduser("~/.claude/context")
CATALOG_PATH = os.path.join(CONTEXT_DIR, "_catalog.md")
INBOX_PATH = os.path.join(CONTEXT_DIR, "_inbox.md")

MAX_ENTRY_SIZE = 4000  # characters
MAX_RECENT_ENTRIES = 10


# =============================================
# BACKUP (reuses pattern from gtm_utils.py)
# =============================================

def backup_file(filepath, max_backups=3):
    """
    Create a timestamped backup before overwriting a context file.
    Keeps at most `max_backups` recent backups. Returns backup path or None.
    """
    if not os.path.exists(filepath):
        return None

    backup_dir = os.path.join(os.path.dirname(filepath), ".backups")
    os.makedirs(backup_dir, exist_ok=True)

    base = os.path.basename(filepath)
    name, ext = os.path.splitext(base)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{name}_{timestamp}{ext}")

    shutil.copy2(filepath, backup_path)

    # Prune old backups
    pattern = os.path.join(backup_dir, f"{name}_*{ext}")
    existing = sorted(glob(pattern), reverse=True)
    for old in existing[max_backups:]:
        try:
            os.remove(old)
        except OSError:
            pass

    return backup_path


# =============================================
# CATALOG PARSING
# =============================================

def read_catalog(catalog_path=None):
    """
    Parse _catalog.md markdown table into a list of dicts.

    Returns list of:
        {
            "file": "contacts.md",
            "description": "Per-person relationship profiles...",
            "tags": ["people", "outreach"],
            "status": "active",
            "format": "Append-style, one entry per person",
            "primary_enricher": "meeting-processor",
            "consumers": ["meeting-prep", "gtm-pipeline"]
        }
    """
    path = catalog_path or CATALOG_PATH
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    in_table = False
    headers = []

    for line in content.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue

        cells = [c.strip() for c in line.split("|")[1:-1]]

        # Header row
        if not in_table and "File" in cells[0]:
            headers = [c.lower().replace(" ", "_") for c in cells]
            in_table = True
            continue

        # Separator row
        if in_table and all(c.startswith("-") for c in cells if c):
            continue

        # Data row
        if in_table and len(cells) >= 4:
            entry = {}
            for i, header in enumerate(headers):
                val = cells[i] if i < len(cells) else ""
                entry[header] = val

            # Parse tags into list
            tags_raw = entry.get("tags", "")
            entry["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]

            # Parse consumers into list
            consumers_raw = entry.get("consumers", "")
            entry["consumers"] = [c.strip() for c in consumers_raw.split(",") if c.strip()]

            # Normalize file field
            entry["file"] = entry.get("file", "").strip()

            entries.append(entry)

    return entries


def match_tags(tags, catalog=None, include_empty=False):
    """
    Find context files whose tags overlap with the given tags.

    Args:
        tags: list of tag strings (e.g., ["sales", "outreach"])
        catalog: pre-loaded catalog (optional, reads from disk if None)
        include_empty: if False (default), skip files with status "empty"

    Returns:
        list of catalog entries matching at least one tag
    """
    if catalog is None:
        catalog = read_catalog()

    tag_set = set(t.lower().strip() for t in tags)
    matches = []

    for entry in catalog:
        entry_tags = set(t.lower() for t in entry.get("tags", []))
        if entry_tags & tag_set:
            if include_empty or entry.get("status", "").lower() != "empty":
                matches.append(entry)

    # positioning.md is always relevant for outward-facing tasks
    positioning = [e for e in catalog if e.get("file") == "positioning.md"]
    if positioning and positioning[0] not in matches:
        if include_empty or positioning[0].get("status", "").lower() != "empty":
            matches.append(positioning[0])

    return matches


def discover_customer_file(customer_name, catalog=None):
    """
    Auto-discover a customer-specific context file.

    Args:
        customer_name: customer name (e.g., "acme" or "Acme Corp")

    Returns:
        catalog entry dict if found, None otherwise
    """
    if catalog is None:
        catalog = read_catalog()

    # Normalize: lowercase, replace spaces with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', customer_name.lower().strip()).strip('-')

    for entry in catalog:
        fname = entry.get("file", "")
        if fname.startswith("customer-") and slug in fname.lower():
            return entry

    # Check if file exists on disk even if not in catalog
    candidate = f"customer-{slug}.md"
    candidate_path = os.path.join(CONTEXT_DIR, candidate)
    if os.path.exists(candidate_path):
        return {"file": candidate, "tags": ["customer"], "status": "active"}

    return None


# =============================================
# ENTRY PARSING & FORMATTING
# =============================================

# Pattern matching entry headers:
# [2026-03-13 | source: meeting-prep | contact: john-smith] confidence: high | evidence: 3
_ENTRY_HEADER = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2})\s*\|\s*source:\s*([^|]+?)\s*\|\s*([^\]]+?)\]'
)


def _parse_header_metadata(header_line):
    """Extract confidence and evidence from the header line's trailing metadata."""
    confidence = "low"
    evidence = 1
    # Look for metadata after the closing bracket
    bracket_end = header_line.find("]")
    if bracket_end >= 0:
        tail = header_line[bracket_end + 1:]
        conf_match = re.search(r'confidence:\s*(\w+)', tail, re.IGNORECASE)
        if conf_match:
            confidence = conf_match.group(1).lower()
        ev_match = re.search(r'evidence:\s*(\d+)', tail, re.IGNORECASE)
        if ev_match:
            evidence = int(ev_match.group(1))
    return confidence, evidence


def _entry_text_to_core_dict(entry_text):
    """Convert a formatted wrapper entry_text string to a core-compatible entry dict."""
    lines = entry_text.strip().split("\n")
    if not lines:
        return None

    header_line = lines[0]
    match = _ENTRY_HEADER.match(header_line.strip())
    if not match:
        return None

    date_str = match.group(1)
    source = match.group(2).strip()
    detail = match.group(3).strip()
    confidence, evidence = _parse_header_metadata(header_line)

    content_lines = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("- "):
            content_lines.append(stripped[2:])
        elif stripped.startswith("-"):
            content_lines.append(stripped[1:].strip())
        elif stripped:
            content_lines.append(stripped)

    return {
        "date": date_str,
        "source": source,
        "detail": detail,
        "content": content_lines,
        "confidence": confidence,
        "evidence_count": evidence,
    }


def _core_entry_to_wrapper_dict(ce):
    """Convert a core ContextEntry dataclass to a wrapper-format dict."""
    date_str = ce.date.strftime("%Y-%m-%d") if hasattr(ce.date, 'strftime') else str(ce.date)
    detail_tag = ce.detail if ce.detail else ""

    # Reconstruct header in wrapper format
    header = f"[{date_str} | source: {ce.source} | {detail_tag}] confidence: {ce.confidence} | evidence: {ce.evidence_count}"

    # Reconstruct content lines with "- " prefix
    content = [f"- {line}" for line in ce.content]

    # Reconstruct raw
    raw = "\n".join([header] + content)

    return {
        "date": date_str,
        "source": ce.source,
        "detail_tag": detail_tag,
        "header": header,
        "content": content,
        "raw": raw,
    }


def parse_entries(filepath):
    """
    Parse a context file into a list of entry dicts.

    Returns list of:
        {
            "date": "2026-03-13",
            "source": "meeting-prep",
            "detail_tag": "contact: john-smith",
            "header": "[full header line]",
            "content": ["- line 1", "- line 2"],
            "raw": "full entry text"
        }
    """
    if not os.path.isabs(filepath):
        filepath = os.path.join(CONTEXT_DIR, filepath)

    if _HAS_CORE:
        try:
            rel_path = os.path.relpath(filepath, CONTEXT_DIR)
            content = _core.read_context(rel_path, agent_id=_AGENT_ID)
            if not content or not content.strip():
                return []
            core_entries = _core.parse_context_file(content)
            return [_core_entry_to_wrapper_dict(ce) for ce in core_entries]
        except Exception as e:
            print(f"[context_utils] Core parse_entries delegation failed, using fallback: {e}", file=sys.stderr)

    return _fallback_parse_entries(filepath)


def _fallback_parse_entries(filepath):
    """Original parse_entries implementation as fallback."""
    if not os.path.exists(filepath):
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    current_entry = None

    for line in content.split("\n"):
        match = _ENTRY_HEADER.match(line.strip())
        if match:
            # Save previous entry
            if current_entry:
                current_entry["raw"] = "\n".join(
                    [current_entry["header"]] + current_entry["content"]
                )
                entries.append(current_entry)

            current_entry = {
                "date": match.group(1),
                "source": match.group(2).strip(),
                "detail_tag": match.group(3).strip(),
                "header": line.strip(),
                "content": [],
            }
        elif current_entry and line.strip().startswith("- "):
            current_entry["content"].append(line.rstrip())
        elif current_entry and line.strip().startswith("- **"):
            current_entry["content"].append(line.rstrip())
        elif current_entry and line.strip() and not line.strip().startswith("#"):
            # Continuation of content (e.g., confidence line on same header)
            if "confidence:" in line.lower() or "evidence:" in line.lower():
                current_entry["header"] = current_entry["header"]  # already captured
            else:
                current_entry["content"].append(line.rstrip())

    # Don't forget the last entry
    if current_entry:
        current_entry["raw"] = "\n".join(
            [current_entry["header"]] + current_entry["content"]
        )
        entries.append(current_entry)

    return entries


def load_recent_entries(filepath, n=None):
    """
    Load the last N entries from a context file.
    Default: MAX_RECENT_ENTRIES (10). Returns list of entry dicts.
    """
    if n is None:
        n = MAX_RECENT_ENTRIES

    # Resolve relative filenames to context dir
    if not os.path.isabs(filepath):
        filepath = os.path.join(CONTEXT_DIR, filepath)

    entries = parse_entries(filepath)
    return entries[-n:] if entries else []


def format_entry(source, detail_tag, content_lines, confidence="low", evidence=1):
    """
    Format an entry per the standard context store entry format.

    Args:
        source: skill name (e.g., "meeting-prep")
        detail_tag: short descriptor (e.g., "contact: john-smith")
        content_lines: list of strings (will be prefixed with "- " if not already)
        confidence: "low", "medium", or "high"
        evidence: integer (default 1)

    Returns:
        formatted entry string
    """
    if _HAS_CORE:
        try:
            date = datetime.now().strftime("%Y-%m-%d")
            # Strip "- " prefix from content lines for core (core adds its own)
            clean_lines = []
            for line in content_lines:
                line = line.strip()
                if line.startswith("- "):
                    clean_lines.append(line[2:])
                else:
                    clean_lines.append(line)

            entry_dict = {
                "date": date,
                "source": source,
                "detail": detail_tag,
                "content": clean_lines,
                "confidence": confidence,
                "evidence_count": evidence,
            }
            return _core.format_entry(entry_dict, source=source)
        except Exception as e:
            print(f"[context_utils] Core format_entry delegation failed, using fallback: {e}", file=sys.stderr)

    return _fallback_format_entry(source, detail_tag, content_lines, confidence, evidence)


def _fallback_format_entry(source, detail_tag, content_lines, confidence="low", evidence=1):
    """Original format_entry implementation as fallback."""
    date = datetime.now().strftime("%Y-%m-%d")
    header = f"[{date} | source: {source} | {detail_tag}] confidence: {confidence} | evidence: {evidence}"

    lines = []
    for line in content_lines:
        line = line.strip()
        if not line.startswith("- "):
            line = f"- {line}"
        lines.append(line)

    entry = header + "\n" + "\n".join(lines)

    # Enforce max entry size
    if len(entry) > MAX_ENTRY_SIZE:
        entry = entry[:MAX_ENTRY_SIZE - 20] + "\n- [truncated]"

    return entry


# =============================================
# DEDUPLICATION
# =============================================

def check_duplicate(filepath, source, detail_tag, date=None):
    """
    Check if an entry with the same composite key exists.
    Composite key: source + detail_tag + date.

    Args:
        filepath: context file path (absolute or relative to context dir)
        source: skill name
        detail_tag: entry detail tag
        date: date string (default: today)

    Returns:
        True if duplicate exists, False otherwise
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    if not os.path.isabs(filepath):
        filepath = os.path.join(CONTEXT_DIR, filepath)

    if _HAS_CORE:
        try:
            rel_path = os.path.relpath(filepath, CONTEXT_DIR)
            existing = _core.read_context(rel_path, agent_id=_AGENT_ID)
            if not existing or not existing.strip():
                return False
            entry_dict = {
                "date": date,
                "source": source,
                "detail": detail_tag,
                "content": [],
                "confidence": "low",
                "evidence_count": 1,
            }
            return _core.should_increment_evidence(existing, entry_dict, source)
        except Exception as e:
            print(f"[context_utils] Core check_duplicate delegation failed, using fallback: {e}", file=sys.stderr)

    return _fallback_check_duplicate(filepath, source, detail_tag, date)


def _fallback_check_duplicate(filepath, source, detail_tag, date):
    """Original check_duplicate implementation as fallback."""
    entries = _fallback_parse_entries(filepath)

    for entry in entries:
        if (entry["date"] == date and
            entry["source"].lower() == source.lower() and
            entry["detail_tag"].lower() == detail_tag.lower()):
            return True

    return False


# =============================================
# WRITE OPERATIONS
# =============================================

def append_entry(filepath, entry_text, source=None, detail_tag=None, skip_dedup=False):
    """
    Append an entry to a context file with backup and dedup.

    Args:
        filepath: context file (absolute or relative to context dir)
        entry_text: formatted entry string (from format_entry())
        source: for dedup check (extracted from entry_text if not provided)
        detail_tag: for dedup check (extracted from entry_text if not provided)
        skip_dedup: skip duplicate check (default False)

    Returns:
        dict: {"status": "written"|"duplicate"|"error", "path": filepath, "backup": backup_path}
    """
    if not os.path.isabs(filepath):
        filepath = os.path.join(CONTEXT_DIR, filepath)

    # Extract source and detail_tag from entry text if not provided
    if source is None or detail_tag is None:
        match = _ENTRY_HEADER.match(entry_text.strip())
        if match:
            source = source or match.group(2).strip()
            detail_tag = detail_tag or match.group(3).strip()

    if _HAS_CORE:
        try:
            return _delegated_append(filepath, entry_text, source, detail_tag, skip_dedup)
        except Exception as e:
            print(f"[context_utils] Core delegation failed, using fallback: {e}", file=sys.stderr)

    return _fallback_append(filepath, entry_text, source, detail_tag, skip_dedup)


def _delegated_append(filepath, entry_text, source, detail_tag, skip_dedup):
    """Delegate append to flywheel core for locking, validation, and atomic writes."""
    rel_path = os.path.relpath(filepath, CONTEXT_DIR)

    # Parse the entry_text into a core-compatible dict
    entry_dict = _entry_text_to_core_dict(entry_text)
    if entry_dict is None:
        raise ValueError("Could not parse entry_text into core dict")

    # Ensure required fields for core validation
    if "source" not in entry_dict or not entry_dict["source"]:
        entry_dict["source"] = source or "unknown"
    if "confidence" not in entry_dict or not entry_dict["confidence"]:
        entry_dict["confidence"] = "low"

    src = entry_dict.get("source", source or "unknown")

    result = _core.append_entry(
        file=rel_path,
        entry=entry_dict,
        source=src,
        agent_id=_AGENT_ID,
    )

    if result == "DEDUP":
        return {"status": "duplicate", "path": filepath, "backup": None}
    else:
        return {"status": "written", "path": filepath, "backup": None}


def _fallback_append(filepath, entry_text, source, detail_tag, skip_dedup):
    """Original append_entry implementation as fallback when core is unavailable."""
    # Dedup check
    if not skip_dedup and source and detail_tag:
        if _fallback_check_duplicate(filepath, source, detail_tag, datetime.now().strftime("%Y-%m-%d")):
            return {"status": "duplicate", "path": filepath, "backup": None}

    # Backup before write
    backup_path = backup_file(filepath)

    # Append
    try:
        # Ensure file exists with at least a newline
        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {os.path.splitext(os.path.basename(filepath))[0].replace('-', ' ').title()}\n\n")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Ensure trailing newline before appending
        if not content.endswith("\n\n"):
            if content.endswith("\n"):
                content += "\n"
            else:
                content += "\n\n"

        content += entry_text + "\n\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return {"status": "written", "path": filepath, "backup": backup_path}

    except Exception as e:
        return {"status": "error", "path": filepath, "backup": backup_path, "error": str(e)}


def write_to_inbox(source, proposed_file, reasoning, content):
    """
    Write knowledge overflow to _inbox.md.

    Args:
        source: skill name
        proposed_file: suggested filename for the knowledge
        reasoning: why this doesn't fit existing files
        content: the actual knowledge
    """
    date = datetime.now().strftime("%Y-%m-%d")
    entry = f"""[{date} | source: {source} | inbox-proposal]
- **Proposed file:** {proposed_file}
- **Reasoning:** {reasoning}
- **Content:** {content}
"""
    return append_entry(INBOX_PATH, entry, source=source,
                       detail_tag="inbox-proposal", skip_dedup=True)


# =============================================
# HIGH-LEVEL WORKFLOWS
# =============================================

def pre_read(tags, customer=None, catalog=None):
    """
    Full pre-read workflow per context-protocol.md.

    1. Read catalog
    2. Match tags to find relevant files
    3. Skip empty files
    4. Load recent entries from each
    5. Auto-discover customer file if specified

    Args:
        tags: list of tag strings
        customer: optional customer name for auto-discovery

    Returns:
        dict: {
            "catalog": [...],
            "matched_files": [...],
            "entries": {"contacts.md": [...], "positioning.md": [...]},
            "customer_file": {...} or None,
            "summary": "Loaded N entries from M files"
        }
    """
    if catalog is None:
        catalog = read_catalog()

    matched = match_tags(tags, catalog=catalog, include_empty=False)
    entries = {}
    total_entries = 0

    for item in matched:
        fname = item.get("file", "")
        if not fname or fname.startswith("_"):
            continue
        recent = load_recent_entries(fname)
        if recent:
            entries[fname] = recent
            total_entries += len(recent)

    customer_file = None
    if customer:
        customer_file = discover_customer_file(customer, catalog=catalog)
        if customer_file:
            fname = customer_file.get("file", "")
            if fname and fname not in entries:
                recent = load_recent_entries(fname)
                if recent:
                    entries[fname] = recent
                    total_entries += len(recent)

    return {
        "catalog": catalog,
        "matched_files": [m.get("file") for m in matched],
        "entries": entries,
        "customer_file": customer_file,
        "summary": f"Loaded {total_entries} entries from {len(entries)} files",
    }


def post_write(knowledge_items, source, catalog=None):
    """
    Full post-write workflow per context-protocol.md.

    Args:
        knowledge_items: list of dicts, each with:
            {
                "target_file": "contacts.md",  # or None for auto-match
                "detail_tag": "contact: john-smith",
                "content_lines": ["Name: John Smith", "Title: CTO"],
                "confidence": "low",  # optional, default "low"
                "tags": ["people"]  # for auto-matching if target_file is None
            }
        source: skill name

    Returns:
        list of result dicts from append_entry()
    """
    if catalog is None:
        catalog = read_catalog()

    results = []

    for item in knowledge_items:
        target = item.get("target_file")

        # Auto-match target file from tags if not specified
        if not target and item.get("tags"):
            matched = match_tags(item["tags"], catalog=catalog, include_empty=True)
            if matched:
                target = matched[0].get("file")

        if not target:
            # Overflow to inbox
            result = write_to_inbox(
                source=source,
                proposed_file=item.get("detail_tag", "unknown"),
                reasoning="No matching catalog file found for tags: " + str(item.get("tags", [])),
                content="\n".join(item.get("content_lines", []))
            )
            results.append(result)
            continue

        # Format and write
        entry_text = format_entry(
            source=source,
            detail_tag=item.get("detail_tag", "unknown"),
            content_lines=item.get("content_lines", []),
            confidence=item.get("confidence", "low"),
            evidence=item.get("evidence", 1),
        )

        result = append_entry(target, entry_text)
        results.append(result)

        # Learning engine hook -- record effectiveness data
        if result.get("status") == "written":
            try:
                from learning_engine import record_learning
                record_learning(
                    source=source,
                    target_file=target or "unknown",
                    detail=item.get("detail_tag", "unknown"),
                    operation="write",
                )
            except Exception:
                pass  # Learning hook is best-effort

    return results


# =============================================
# CLI INTERFACE
# =============================================

def _cli_pre_read(args):
    """CLI: python3 context_utils.py pre-read --tags sales,outreach [--customer acme]"""
    import argparse
    parser = argparse.ArgumentParser(description="Pre-read context store")
    parser.add_argument("--tags", required=True, help="Comma-separated tags")
    parser.add_argument("--customer", default=None, help="Customer name for auto-discovery")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parsed = parser.parse_args(args)

    tags = [t.strip() for t in parsed.tags.split(",")]
    result = pre_read(tags, customer=parsed.customer)

    if parsed.json:
        # Serialize entries for JSON output
        output = {
            "matched_files": result["matched_files"],
            "summary": result["summary"],
            "entries": {},
        }
        for fname, entries in result["entries"].items():
            output["entries"][fname] = [e["raw"] for e in entries]
        print(json.dumps(output, indent=2))
    else:
        print(f"Context Store Pre-Read: {result['summary']}")
        print(f"Matched files: {', '.join(result['matched_files'])}")
        for fname, entries in result["entries"].items():
            print(f"\n--- {fname} ({len(entries)} entries) ---")
            for e in entries[-3:]:  # Show last 3 for brevity
                print(e["header"])


def _cli_append(args):
    """CLI: python3 context_utils.py append contacts.md --source meeting-prep --detail "john-smith" --content "- Name: John"  """
    import argparse
    parser = argparse.ArgumentParser(description="Append entry to context file")
    parser.add_argument("file", help="Context file name (e.g., contacts.md)")
    parser.add_argument("--source", required=True, help="Skill name")
    parser.add_argument("--detail", required=True, help="Detail tag")
    parser.add_argument("--content", required=True, help="Content lines (newline-separated)")
    parser.add_argument("--confidence", default="low", choices=["low", "medium", "high"])
    parser.add_argument("--evidence", type=int, default=1)
    parser.add_argument("--skip-dedup", action="store_true")
    parsed = parser.parse_args(args)

    content_lines = parsed.content.replace("\\n", "\n").split("\n")
    entry_text = format_entry(
        source=parsed.source,
        detail_tag=parsed.detail,
        content_lines=content_lines,
        confidence=parsed.confidence,
        evidence=parsed.evidence,
    )

    result = append_entry(parsed.file, entry_text, skip_dedup=parsed.skip_dedup)
    print(json.dumps(result, indent=2))


def _cli_check_dup(args):
    """CLI: python3 context_utils.py check-dup contacts.md --source meeting-prep --detail "john-smith" [--date 2026-03-13]"""
    import argparse
    parser = argparse.ArgumentParser(description="Check for duplicate entry")
    parser.add_argument("file", help="Context file name")
    parser.add_argument("--source", required=True)
    parser.add_argument("--detail", required=True)
    parser.add_argument("--date", default=None)
    parsed = parser.parse_args(args)

    is_dup = check_duplicate(parsed.file, parsed.source, parsed.detail, parsed.date)
    print(json.dumps({"duplicate": is_dup}))
    sys.exit(0 if not is_dup else 1)


def _cli_catalog(args):
    """CLI: python3 context_utils.py catalog [--json]"""
    import argparse
    parser = argparse.ArgumentParser(description="Show catalog")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--tags", default=None, help="Filter by tags")
    parsed = parser.parse_args(args)

    catalog = read_catalog()

    if parsed.tags:
        tags = [t.strip() for t in parsed.tags.split(",")]
        catalog = match_tags(tags, catalog=catalog, include_empty=True)

    if parsed.json:
        print(json.dumps(catalog, indent=2))
    else:
        for entry in catalog:
            status = entry.get("status", "?")
            tags = ", ".join(entry.get("tags", []))
            print(f"  {entry.get('file', '?'):30s}  [{status:6s}]  tags: {tags}")


def _cli_verify_writes(args):
    """CLI: python3 context_utils.py verify-writes --agent-id meeting-prep --declared contacts.md,insights.md [--since-minutes 10]"""
    import argparse
    parser = argparse.ArgumentParser(description="Verify declared writes happened")
    parser.add_argument("--agent-id", required=True, help="Agent/skill identifier")
    parser.add_argument("--declared", required=True, help="Comma-separated list of declared write files")
    parser.add_argument("--since-minutes", type=int, default=10, help="Time window in minutes (default 10)")
    parsed = parser.parse_args(args)

    declared = [f.strip() for f in parsed.declared.split(",") if f.strip()]

    if _HAS_CORE:
        result = _core.verify_writes(
            declared=declared,
            agent_id=parsed.agent_id,
            since_minutes=parsed.since_minutes,
        )
    else:
        # Fallback: no core available, report all as missing
        result = {
            "declared": declared,
            "actual": [],
            "missing": declared,
            "error": "Flywheel core not available -- cannot verify writes",
        }

    print(json.dumps(result, indent=2))

    # Human-readable warnings
    for f in result.get("missing", []):
        print(f"WARNING: Declared write to {f} did not execute. Data may not have compounded.", file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 context_utils.py <command> [args]")
        print("Commands: pre-read, append, check-dup, catalog, verify-writes")
        sys.exit(1)

    command = sys.argv[1]
    remaining = sys.argv[2:]

    commands = {
        "pre-read": _cli_pre_read,
        "append": _cli_append,
        "check-dup": _cli_check_dup,
        "catalog": _cli_catalog,
        "verify-writes": _cli_verify_writes,
    }

    if command in commands:
        commands[command](remaining)
    else:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(commands.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
