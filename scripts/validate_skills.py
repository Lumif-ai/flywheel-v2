#!/usr/bin/env python3
"""
validate_skills.py - Validate SKILL.md frontmatter for database seeding readiness.

Scans all skill directories under skills/, parses YAML frontmatter from each
SKILL.md, and validates required fields exist with correct types/values.

Usage:
    python3 scripts/validate_skills.py [--verbose]

Exit codes:
    0 - All skills valid
    1 - One or more validation errors found
"""

import argparse
import os
import re
import sys

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
REQUIRED_FIELDS = ["name", "version", "description", "web_tier"]
VALID_WEB_TIERS = {1, 2, 3}


# ---------------------------------------------------------------------------
# YAML parsing
# ---------------------------------------------------------------------------


def parse_frontmatter(filepath):
    """Parse YAML frontmatter from a SKILL.md file.

    Reads content between the first pair of '---' markers and parses as YAML.

    Args:
        filepath: Path to the SKILL.md file.

    Returns:
        Dict of parsed frontmatter fields.

    Raises:
        ValueError: If frontmatter markers are missing or YAML is invalid.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Find frontmatter between --- markers
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
        # Simple fallback parser for key: value pairs
        data = _simple_yaml_parse(raw_yaml)

    if not isinstance(data, dict):
        raise ValueError("Frontmatter did not parse as a dict")

    return data


def _simple_yaml_parse(raw):
    """Minimal YAML-like parser for simple key: value frontmatter.

    Handles single-line values and multi-line strings (using > or |).
    Does NOT handle nested structures beyond simple lists.

    Args:
        raw: Raw YAML string.

    Returns:
        Dict of parsed key-value pairs.
    """
    data = {}
    lines = raw.split("\n")
    current_key = None
    current_value = []
    multiline = False

    for line in lines:
        # Check for new key: value pair
        kv_match = re.match(r"^(\w[\w_-]*)\s*:\s*(.*)", line)
        if kv_match and not line.startswith(" ") and not line.startswith("\t"):
            # Save previous multiline value
            if current_key and multiline:
                data[current_key] = " ".join(current_value).strip()

            key = kv_match.group(1)
            value = kv_match.group(2).strip()

            if value in (">", "|"):
                current_key = key
                current_value = []
                multiline = True
            elif value.startswith('"') and value.endswith('"'):
                data[key] = value.strip('"')
                current_key = None
                multiline = False
            elif value.startswith("'") and value.endswith("'"):
                data[key] = value.strip("'")
                current_key = None
                multiline = False
            else:
                # Try numeric
                try:
                    data[key] = int(value)
                except ValueError:
                    try:
                        data[key] = float(value)
                    except ValueError:
                        data[key] = value if value else None
                current_key = None
                multiline = False
        elif multiline and (line.startswith("  ") or line.startswith("\t")):
            current_value.append(line.strip())

    # Save last multiline value
    if current_key and multiline:
        data[current_key] = " ".join(current_value).strip()

    return data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_skill(filepath):
    """Validate a single SKILL.md file.

    Args:
        filepath: Path to the SKILL.md file.

    Returns:
        Tuple of (frontmatter_dict_or_None, list_of_error_strings).
    """
    errors = []

    try:
        data = parse_frontmatter(filepath)
    except ValueError as e:
        return None, [str(e)]

    # Library skills (tagged "library" or explicitly enabled: false) are not directly
    # invokable and do not need web_tier. They still need name/version/description.
    tags = data.get("tags") or []
    is_library = (
        (isinstance(tags, list) and "library" in tags)
        or data.get("enabled") is False
    )
    required = [f for f in REQUIRED_FIELDS if not (is_library and f == "web_tier")]

    # Check required fields exist
    for field in required:
        if field not in data or data[field] is None:
            errors.append("missing required field: %s" % field)

    # Validate field values (only if present)
    if "name" in data and data["name"] is not None:
        if not isinstance(data["name"], str) or not data["name"].strip():
            errors.append("name must be a non-empty string")

    if "version" in data and data["version"] is not None:
        val = data["version"]
        if not isinstance(val, (str, int, float)) or not str(val).strip():
            errors.append("version must be a non-empty string")

    if "description" in data and data["description"] is not None:
        if not isinstance(data["description"], str) or not data["description"].strip():
            errors.append("description must be a non-empty string")

    if "web_tier" in data and data["web_tier"] is not None:
        tier = data["web_tier"]
        if tier not in VALID_WEB_TIERS:
            errors.append(
                "web_tier must be 1, 2, or 3 (got: %s)" % repr(tier)
            )

    return data, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Validate SKILL.md frontmatter for all skills"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print parsed frontmatter for each skill"
    )
    parser.add_argument(
        "--skills-dir", default=None,
        help="Override skills directory path"
    )
    args = parser.parse_args()

    skills_dir = os.path.abspath(args.skills_dir or SKILLS_DIR)

    print("Validating SKILL.md files in %s/" % skills_dir)
    print()

    if not os.path.isdir(skills_dir):
        print("ERROR: Skills directory not found: %s" % skills_dir)
        sys.exit(1)

    total = 0
    valid = 0
    all_errors = []  # List of (skill_name, errors)

    # Sort for consistent output
    entries = sorted(os.listdir(skills_dir))

    for entry in entries:
        # Skip non-directories, hidden dirs, and excluded dirs
        entry_path = os.path.join(skills_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        if entry.startswith(".") or entry in SKIP_DIRS:
            continue

        skill_md = os.path.join(entry_path, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue

        total += 1
        data, errors = validate_skill(skill_md)

        if errors:
            status = "ERRORS: %s" % "; ".join(errors)
            all_errors.append((entry, errors))
        else:
            status = "OK"
            valid += 1

        # Format output with dots for alignment
        dots = "." * max(1, 40 - len(entry))
        print("  %s %s %s" % (entry, dots, status))

        if args.verbose and data:
            for key in REQUIRED_FIELDS:
                val = data.get(key, "<missing>")
                if isinstance(val, str) and len(val) > 60:
                    val = val[:60] + "..."
                print("    %s: %s" % (key, val))
            print()

    print()
    error_count = sum(len(errs) for _, errs in all_errors)
    print(
        "Summary: %d skills scanned, %d valid, %d errors"
        % (total, valid, error_count)
    )

    if all_errors:
        print()
        print("Skills with errors:")
        for skill_name, errors in all_errors:
            for err in errors:
                print("  - %s: %s" % (skill_name, err))
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
