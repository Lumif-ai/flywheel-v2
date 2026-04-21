#!/usr/bin/env python3
"""
validate_skill_tools.py - Validate skill prompts for forbidden server-side tool names.

Scans all active skill directories under skills/, normalizes each prompt via
normalize_for_mcp(), then checks for forbidden tool names that should have been
rewritten by the normalizer.

This is a CI guardrail: any skill prompt that references a server-side tool name
after normalization is a regression (NORM-05).

Usage:
    python3 scripts/validate_skill_tools.py [--verbose] [--skill NAME]

Exit codes:
    0 - All skills clean (no forbidden tool names found)
    1 - One or more violations found
"""

import argparse
import os
import re
import sys

# Add backend/src to path so we can import the normalizer
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "backend", "src"),
)

from flywheel.services.prompt_normalizer import normalize_for_mcp  # noqa: E402

# Try PyYAML first, fall back to simple parser
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")
SKIP_DIRS = {"_archived"}

# Forbidden tool names -- these should NEVER appear in a normalized prompt.
# The normalizer should have rewritten all of them to MCP equivalents.
FORBIDDEN_TOOLS = [
    # Server-side tool names (should be MCP equivalents after normalization)
    "context_read",
    "read_context",
    "context_write",
    "append_entry",
    "context_query",
    # Native capability server names (should be WebSearch/WebFetch/etc)
    "web_search",
    "web_fetch",
    "file_write",
    "file_read",
    "read_file",
    "write_file",
    "python_execute",
    # Deprecated lead tools (should be pipeline equivalents)
    "flywheel_list_leads",
    "flywheel_upsert_lead",
    "flywheel_add_lead_contact",
    "flywheel_draft_lead_message",
    "flywheel_send_lead_message",
    "flywheel_graduate_lead",
    "flywheel_fetch_account",
    # MCP namespace prefix (should be stripped)
    "mcp__flywheel__",
]

# Pre-compile regexes: word-boundary for all except mcp__flywheel__ (prefix check)
_FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = []
for _tool in FORBIDDEN_TOOLS:
    if _tool == "mcp__flywheel__":
        _FORBIDDEN_PATTERNS.append((_tool, re.compile(re.escape(_tool))))
    else:
        _FORBIDDEN_PATTERNS.append((_tool, re.compile(rf"\b{re.escape(_tool)}\b")))


# ---------------------------------------------------------------------------
# Frontmatter / prompt parsing
# ---------------------------------------------------------------------------


def parse_frontmatter(filepath: str) -> dict:
    """Parse YAML frontmatter from a SKILL.md file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.match(r"^---\s*\n(.*?\n)---", content, re.DOTALL)
    if not match:
        raise ValueError("No YAML frontmatter found (missing --- markers)")

    raw_yaml = match.group(1)

    if HAS_YAML:
        try:
            data = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as e:
            raise ValueError("Invalid YAML: %s" % str(e))
    else:
        data = {}
        for line in raw_yaml.split("\n"):
            kv = re.match(r"^(\w[\w_-]*)\s*:\s*(.*)", line)
            if kv:
                key = kv.group(1)
                val = kv.group(2).strip().strip("\"'")
                if val.lower() == "true":
                    data[key] = True
                elif val.lower() == "false":
                    data[key] = False
                else:
                    data[key] = val if val else None

    if not isinstance(data, dict):
        raise ValueError("Frontmatter did not parse as a dict")

    return data


def extract_system_prompt(filepath: str) -> str:
    """Extract the system prompt (everything after closing --- of frontmatter)."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.match(r"^---\s*\n.*?\n---\s*\n?", content, re.DOTALL)
    if not match:
        raise ValueError("No YAML frontmatter found")

    return content[match.end() :]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def check_forbidden_tools(
    normalized_prompt: str, skill_name: str
) -> list[str]:
    """Check a normalized prompt for forbidden tool names.

    Returns a list of violation strings.
    """
    violations: list[str] = []
    lines = normalized_prompt.split("\n")

    for tool_name, pattern in _FORBIDDEN_PATTERNS:
        for line_num, line in enumerate(lines, start=1):
            if pattern.search(line):
                violations.append(
                    "FAIL: %s -- found forbidden tool '%s' (line %d)"
                    % (skill_name, tool_name, line_num)
                )

    return violations


def is_library_skill(frontmatter: dict) -> bool:
    """Check if a skill is a library/shared skill (should be skipped)."""
    if frontmatter.get("enabled") is False:
        return True
    tags = frontmatter.get("tags") or []
    if isinstance(tags, list) and "library" in tags:
        return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate skill prompts for forbidden server-side tool names"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show each skill being checked",
    )
    parser.add_argument(
        "--skill",
        type=str,
        default=None,
        help="Check a single skill only (by directory name)",
    )
    parser.add_argument(
        "--skills-dir",
        default=None,
        help="Override skills directory path",
    )
    args = parser.parse_args()

    skills_dir = os.path.abspath(args.skills_dir or SKILLS_DIR)

    if not os.path.isdir(skills_dir):
        print("ERROR: Skills directory not found: %s" % skills_dir)
        sys.exit(1)

    total = 0
    all_violations: list[str] = []

    # Determine which skills to check
    if args.skill:
        entries = [args.skill]
    else:
        entries = sorted(os.listdir(skills_dir))

    for entry in entries:
        entry_path = os.path.join(skills_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        if entry.startswith(".") or entry in SKIP_DIRS:
            continue

        skill_md = os.path.join(entry_path, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue

        # Parse frontmatter to check if library skill
        try:
            frontmatter = parse_frontmatter(skill_md)
        except ValueError as e:
            print("WARN: %s -- could not parse frontmatter: %s" % (entry, e))
            continue

        if is_library_skill(frontmatter):
            if args.verbose:
                print("  SKIP: %s (library/disabled)" % entry)
            continue

        # Extract and normalize prompt
        try:
            raw_prompt = extract_system_prompt(skill_md)
        except ValueError as e:
            print("WARN: %s -- could not extract prompt: %s" % (entry, e))
            continue

        normalized = normalize_for_mcp(raw_prompt)
        violations = check_forbidden_tools(normalized, entry)

        total += 1

        if violations:
            for v in violations:
                print(v)
            all_violations.extend(violations)
        elif args.verbose:
            print("  OK: %s" % entry)

    print()
    print(
        "%d skills checked, %d violations found"
        % (total, len(all_violations))
    )

    sys.exit(1 if all_violations else 0)


if __name__ == "__main__":
    main()
