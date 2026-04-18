#!/usr/bin/env python3
"""
Skill Validation Linter
=======================
Validates all SKILL.md files under ~/.claude/skills/ for common violations.

Checks:
  1. No hardcoded context file lists in frontmatter
  2. Frontmatter-body agreement on context-aware
  3. Phantom script references (referenced .py files that don't exist)
  4. Domain skill without context-aware declaration
  5. Phantom engine notes (engine references with no .py files)

Usage:
  python3 ~/.claude/skills/_shared/validate_skills.py
"""

import os
import re
import sys
from pathlib import Path

# DEPRECATED (Phase 152 — 2026-04-19): legacy ~/.claude/skills/ path; skills are served via flywheel_fetch_skill_assets. Retained for developer tooling only; no runtime impact.
SKILLS_ROOT = Path.home() / ".claude" / "skills"

# Domain keywords that should have context-aware: true
DOMAIN_KEYWORDS = ["gtm", "legal", "meeting", "investor", "content"]

# Directories / patterns to exclude
EXCLUDE_DIRS = {"_archived"}
EXCLUDE_SUFFIXES = {".bak", ".backup"}


def find_skill_files():
    """Find all SKILL.md files, excluding archived and backup files."""
    results = []
    for root, dirs, files in os.walk(SKILLS_ROOT):
        # Skip excluded directories
        rel = Path(root).relative_to(SKILLS_ROOT)
        parts = rel.parts
        if parts and parts[0] in EXCLUDE_DIRS:
            continue

        for f in files:
            if f == "SKILL.md":
                fp = Path(root) / f
                # Skip backup files (shouldn't match SKILL.md but just in case)
                if any(str(fp).endswith(s) for s in EXCLUDE_SUFFIXES):
                    continue
                results.append(fp)
    return sorted(results)


def parse_frontmatter(text):
    """Parse YAML frontmatter between --- markers. Returns (dict, body_text)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, text

    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1:])
    fm = _parse_yaml_simple(fm_lines)
    return fm, body


def _parse_yaml_simple(lines):
    """Minimal YAML parser for frontmatter. Handles scalars, lists, and one level of nesting."""
    result = {}
    current_key = None
    current_sub = None

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Detect indentation level
        indent = len(line) - len(line.lstrip())

        # Top-level key
        if indent == 0 and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            current_key = key
            current_sub = None

            if val == "" or val == ">":
                # Could be a block scalar or nested mapping -- peek ahead
                # Check if next line is indented list or mapping
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_stripped = next_line.strip()
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent > 0 and next_stripped.startswith("- "):
                        # It's a list
                        result[key] = []
                        i += 1
                        while i < len(lines):
                            l = lines[i]
                            s = l.strip()
                            li = len(l) - len(l.lstrip())
                            if li == 0 and s and ":" in s:
                                break
                            if s.startswith("- "):
                                item = s[2:].strip().strip('"').strip("'")
                                result[key].append(item)
                            elif li > 0 and not s.startswith("- ") and ":" in s:
                                # Nested mapping
                                break
                            i += 1
                        continue
                    elif next_indent > 0 and ":" in next_stripped:
                        # Nested mapping
                        result[key] = {}
                        i += 1
                        while i < len(lines):
                            l = lines[i]
                            s = l.strip()
                            li = len(l) - len(l.lstrip())
                            if li == 0 and s and ":" in s:
                                break
                            if li > 0 and ":" in s:
                                sk, _, sv = s.partition(":")
                                sk = sk.strip()
                                sv = sv.strip()
                                current_sub = sk
                                if sv.startswith("[") and sv.endswith("]"):
                                    # Inline list
                                    items = sv[1:-1].split(",")
                                    result[key][sk] = [
                                        it.strip().strip('"').strip("'")
                                        for it in items if it.strip()
                                    ]
                                elif sv == "" or sv == ">":
                                    # Check for sub-list
                                    if i + 1 < len(lines):
                                        peek = lines[i + 1].strip()
                                        if peek.startswith("- "):
                                            result[key][sk] = []
                                            i += 1
                                            while i < len(lines):
                                                ll = lines[i]
                                                ss = ll.strip()
                                                lli = len(ll) - len(ll.lstrip())
                                                if lli <= indent + 2 and ss and not ss.startswith("- "):
                                                    break
                                                if ss.startswith("- "):
                                                    result[key][sk].append(
                                                        ss[2:].strip().strip('"').strip("'")
                                                    )
                                                i += 1
                                            continue
                                        else:
                                            result[key][sk] = sv
                                    else:
                                        result[key][sk] = sv
                                else:
                                    result[key][sk] = sv.strip('"').strip("'")
                            elif li > 0 and s.startswith("- "):
                                # List item under current_sub
                                if current_sub and current_sub in result[key]:
                                    if isinstance(result[key][current_sub], list):
                                        result[key][current_sub].append(
                                            s[2:].strip().strip('"').strip("'")
                                        )
                                else:
                                    pass
                            i += 1
                        continue
                    else:
                        # Block scalar -- just store the joined text
                        result[key] = ""
                        i += 1
                        text_parts = []
                        while i < len(lines):
                            l = lines[i]
                            li = len(l) - len(l.lstrip())
                            if li == 0 and l.strip() and ":" in l.strip():
                                break
                            text_parts.append(l.strip())
                            i += 1
                        result[key] = " ".join(text_parts)
                        continue
                else:
                    result[key] = val
            elif val.startswith("[") and val.endswith("]"):
                items = val[1:-1].split(",")
                result[key] = [it.strip().strip('"').strip("'") for it in items if it.strip()]
            elif val.lower() == "true":
                result[key] = True
            elif val.lower() == "false":
                result[key] = False
            else:
                result[key] = val.strip('"').strip("'")
        i += 1

    return result


def check_hardcoded_context(fm):
    """Check 1: No hardcoded context file lists in frontmatter."""
    violations = []
    ctx = fm.get("context")
    if isinstance(ctx, dict):
        for key in ("reads", "writes"):
            val = ctx.get(key)
            if isinstance(val, list) and len(val) > 0:
                violations.append(
                    f"Hardcoded context file lists in frontmatter\n"
                    f"    Found: context.{key} = {val}"
                )
    return violations


def check_context_aware_agreement(fm, body):
    """Check 2: Frontmatter-body agreement on context-aware."""
    violations = []
    fm_context_aware = fm.get("context-aware") is True

    body_lower = body.lower()
    body_mentions = (
        "this skill is context-aware" in body_lower
        or "context-aware" in body_lower
        or "context store" in body_lower
        or "context-protocol" in body_lower
    )
    body_explicit = "this skill is context-aware" in body_lower

    if body_explicit and not fm_context_aware:
        violations.append(
            "Body says 'This skill is context-aware' but frontmatter missing context-aware: true"
        )
    if fm_context_aware and not body_mentions:
        violations.append(
            "Frontmatter has context-aware: true but body never mentions context-aware/context store/context-protocol"
        )
    return violations


def _strip_changelog(body):
    """Return body text with changelog section removed.

    A changelog section starts with '## Changelog' and runs to end of file
    (or next H2 heading). Lines inside changelog tables (starting with |)
    are historical records and should not trigger lint violations.
    """
    lines = body.split("\n")
    result = []
    in_changelog = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("## changelog"):
            in_changelog = True
            continue
        if in_changelog:
            # Exit changelog if we hit another H2 heading
            if stripped.startswith("## ") and not stripped.lower().startswith("## changelog"):
                in_changelog = False
                result.append(line)
            # Otherwise skip everything in changelog
            continue
        result.append(line)
    return "\n".join(result)


def _is_inside_code_block(body, ref):
    """Check if a .py reference appears only inside fenced code blocks (``` ... ```)."""
    in_block = False
    found_outside = False
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
            continue
        if ref in line:
            if not in_block:
                found_outside = True
                break
    return not found_outside


# Common Python stdlib/package module names that are imports, not file references
KNOWN_PACKAGE_NAMES = {
    "spacy", "presidio_analyzer", "presidio_anonymizer", "openpyxl",
    "pdfplumber", "pandas", "numpy", "matplotlib", "seaborn", "plotly",
    "beautifulsoup4", "requests", "httpx", "lxml", "chardet", "html2text",
    "markdown", "qrcode", "dateparser", "tabulate", "reportlab", "xlsxwriter",
    "tqdm", "jinja2", "yaml", "pyyaml", "pillow", "PIL", "flask", "django",
    "fastapi", "uvicorn", "pytest", "unittest", "asyncio", "pathlib",
    "collections", "itertools", "functools", "typing", "dataclasses",
    "json", "csv", "os", "sys", "re", "io", "abc", "enum", "logging",
    "argparse", "subprocess", "shutil", "glob", "tempfile", "hashlib",
    "base64", "urllib", "http", "socket", "threading", "multiprocessing",
    "concurrent", "contextlib", "copy", "math", "random", "time", "datetime",
    "textwrap", "string", "struct", "codecs", "binascii", "pickle",
    "shelve", "sqlite3", "xml", "html", "email", "mimetypes",
}

# Common shared directories to search when resolving relative paths
SHARED_SEARCH_DIRS = [
    "gtm-shared",
    "pii-redactor/scripts",
    "_shared",
]


def _resolve_py_path(ref, skill_dir, skills_root):
    """Try to resolve a .py reference to an existing file.

    Resolution order:
    1. Absolute paths starting with / -- check as-is
    2. Paths starting with ~/ -- expand home directory
    3. Paths starting with ~/.claude/skills/ -- expand and check
    4. Relative paths -- check in order:
       a. Relative to skill's own directory
       b. Relative to skills root (~/.claude/skills/)
       c. In skill's scripts/ subdirectory (by basename)
       d. Common shared locations
    5. For paths containing gtm-stack/ -- strip that prefix and retry
    """
    # 1. Absolute paths
    if ref.startswith("/"):
        if Path(ref).exists():
            return True
        return False

    # 2-3. Home-relative paths
    if ref.startswith("~"):
        expanded = Path(os.path.expanduser(ref))
        if expanded.exists():
            return True
        # For paths with gtm-stack/, try stripping it
        if "gtm-stack/" in ref:
            stripped = ref.replace("gtm-stack/", "")
            expanded2 = Path(os.path.expanduser(stripped))
            if expanded2.exists():
                return True
        return False

    # Skip env variable paths
    if ref.startswith("$"):
        return True  # Can't resolve, assume OK

    # 4. Relative paths -- try multiple locations
    basename = Path(ref).name

    # a. Relative to skill directory (current behavior)
    if (skill_dir / ref).exists():
        return True

    # b. Relative to skills root
    if (skills_root / ref).exists():
        return True

    # c. In skill's scripts/ subdirectory (by basename)
    if (skill_dir / "scripts" / basename).exists():
        return True

    # Also check basename directly in skill dir
    if (skill_dir / basename).exists():
        return True

    # d. Common shared locations
    for shared_dir in SHARED_SEARCH_DIRS:
        candidate = skills_root / shared_dir / basename
        if candidate.exists():
            return True

    # e. Search all sibling skill directories and their scripts/ subdirs for basename
    try:
        for entry in skills_root.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                # Check <sibling>/basename
                if (entry / basename).exists():
                    return True
                # Check <sibling>/scripts/basename
                if (entry / "scripts" / basename).exists():
                    return True
    except OSError:
        pass

    # Also try the full relative ref under each sibling (e.g. "dashboard/scripts/foo.py"
    # under a sibling that has that subdirectory structure)
    if "/" in ref:
        try:
            for entry in skills_root.iterdir():
                if entry.is_dir() and not entry.name.startswith("."):
                    if (entry / ref).exists():
                        return True
        except OSError:
            pass

    # 5. For paths containing gtm-stack/, strip it and retry at skills root
    if "gtm-stack/" in ref:
        stripped_ref = ref.split("gtm-stack/", 1)[1]
        if (skills_root / stripped_ref).exists():
            return True
        # Also try just the basename at skills root level
        if (skills_root / basename).exists():
            return True

    return False


def check_phantom_scripts(body, skill_dir):
    """Check 3: Phantom script references."""
    violations = []
    skills_root = SKILLS_ROOT

    # Strip changelog sections -- historical records should not trigger violations
    body = _strip_changelog(body)

    # Find .py references in the body
    # Match paths like ~/path/to/file.py, ./file.py, scripts/file.py, file.py
    # Must start at a word boundary or after whitespace/backtick/quote/paren
    # Exclude template variables like {SKILL_DIR}/foo.py
    py_refs = re.findall(
        r'(?:^|(?<=[\s`"\'(,|]))([A-Za-z~./][\w/~._-]*\.py)\b',
        body, re.MULTILINE
    )

    # Deduplicate
    seen = set()
    for ref in py_refs:
        if ref in seen:
            continue
        seen.add(ref)

        # Skip false positives
        # - Template variables like {SKILL_DIR}/foo.py
        if "{" in ref or "}" in ref:
            continue
        # - Generic examples
        if ref in ("script.py", "example.py", "test.py", "setup.py", "conftest.py"):
            continue
        # - Python module imports (no path separators, short names)
        if "/" not in ref and "~" not in ref and ref.startswith("__"):
            continue

        # - Known package/stdlib names (e.g. spacy.py -> spacy is a package)
        name_without_ext = ref.rsplit(".py", 1)[0]
        # Handle bare names like "spacy.py" or paths like "some/presidio_analyzer.py"
        bare_name = name_without_ext.rsplit("/", 1)[-1] if "/" in name_without_ext else name_without_ext
        if bare_name.lower() in KNOWN_PACKAGE_NAMES:
            continue

        # Check if this reference appears only inside code block fences
        if _is_inside_code_block(body, ref):
            continue

        # Check if this reference appears in a Python import line
        is_import = False
        for line in body.split("\n"):
            if ref in line:
                stripped = line.strip()
                if stripped.startswith("from ") or stripped.startswith("import "):
                    is_import = True
                    break
                # Also skip `python3 -c "import ..."` patterns
                if "python3 -c" in stripped or "python -c" in stripped:
                    is_import = True
                    break
        if is_import:
            continue

        # Resolve path using multi-location resolution
        if not _resolve_py_path(ref, skill_dir, skills_root):
            # Build a helpful resolved path for the error message
            if ref.startswith("~"):
                resolved = Path(os.path.expanduser(ref))
            elif ref.startswith("/"):
                resolved = Path(ref)
            else:
                resolved = skill_dir / ref
            violations.append(
                f"Referenced script not found: {ref}\n"
                f"    Resolved to: {resolved}"
            )

    return violations


def check_domain_without_context_aware(fm, skill_name):
    """Check 4: Domain skill without context-aware."""
    violations = []
    name_lower = skill_name.lower()
    description = str(fm.get("description", "")).upper()

    is_domain = any(kw in name_lower for kw in DOMAIN_KEYWORDS)
    is_deprecated = "DEPRECATED" in description
    is_context_aware = fm.get("context-aware") is True

    if is_domain and not is_deprecated and not is_context_aware:
        matched = [kw for kw in DOMAIN_KEYWORDS if kw in name_lower]
        violations.append(
            f"Domain skill (keywords: {matched}) missing context-aware: true in frontmatter"
        )
    return violations


def check_phantom_engine(body, skill_dir):
    """Check 5: Phantom engine notes.

    Only flags if "engine" co-occurs with Python-specific constructs
    (e.g., .py, import, context_utils, "Python engine", "engine handles",
    "via the engine", "via Python"). Metaphorical uses like "you are the
    intelligence engine" are allowed.

    Changelog sections are excluded from scanning.
    """
    violations = []

    # Strip changelog sections -- historical records should not trigger violations
    body = _strip_changelog(body)
    body_lower = body.lower()

    # Build a version of the body with code blocks stripped for engine analysis
    # Code blocks contain legitimate .py references (imports etc) that shouldn't
    # trigger this check
    body_no_code = []
    in_code_block = False
    for line in body.split("\n"):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if not in_code_block:
            body_no_code.append(line)
    body_prose = "\n".join(body_no_code)
    body_prose_lower = body_prose.lower()

    # Only flag if "engine" appears alongside Python-specific constructs
    # in prose (not code blocks)
    has_engine = "engine" in body_prose_lower
    if not has_engine:
        return violations

    # Check for Python-specific constructs that indicate a real engine reference
    python_indicators = [
        "context_utils", "python engine", "engine handles",
        "via the engine", "via python",
    ]
    has_python_ref = any(ind in body_prose_lower for ind in python_indicators)

    if not has_python_ref:
        return violations

    # Check for .py files in skill directory (excluding tests/)
    has_py = False
    for root, dirs, files in os.walk(skill_dir):
        # Skip tests directory
        rel = Path(root).relative_to(skill_dir)
        if "tests" in rel.parts or "test" in rel.parts:
            continue
        for f in files:
            if f.endswith(".py"):
                has_py = True
                break
        if has_py:
            break

    if not has_py:
        violations.append(
            f"Phantom engine note references non-existent Python engine\n"
            f"    No .py files found in {skill_dir}/"
        )
    return violations


def derive_skill_name(skill_path):
    """Derive skill name from path."""
    skill_dir = skill_path.parent
    rel = skill_dir.relative_to(SKILLS_ROOT)
    return str(rel).replace("/", "-") if str(rel) != "." else skill_dir.name


def validate_skill(skill_path):
    """Run all checks on a single SKILL.md. Returns (skill_name, list_of_violations)."""
    text = skill_path.read_text(encoding="utf-8", errors="replace")
    skill_dir = skill_path.parent
    skill_name = derive_skill_name(skill_path)

    fm, body = parse_frontmatter(text)

    # Use frontmatter name if available
    if fm.get("name"):
        skill_name = str(fm["name"])

    all_violations = []

    # Check 1
    v1 = check_hardcoded_context(fm)
    for v in v1:
        all_violations.append(("CHECK 1", v))

    # Check 2
    v2 = check_context_aware_agreement(fm, body)
    for v in v2:
        all_violations.append(("CHECK 2", v))

    # Check 3
    v3 = check_phantom_scripts(body, skill_dir)
    for v in v3:
        all_violations.append(("CHECK 3", v))

    # Check 4
    v4 = check_domain_without_context_aware(fm, skill_name)
    for v in v4:
        all_violations.append(("CHECK 4", v))

    # Check 5
    v5 = check_phantom_engine(body, skill_dir)
    for v in v5:
        all_violations.append(("CHECK 5", v))

    return skill_name, all_violations


def main():
    skill_files = find_skill_files()

    if not skill_files:
        print("No SKILL.md files found under", SKILLS_ROOT)
        sys.exit(1)

    print("=== Skill Validation Report ===\n")

    passed = []
    failed = []

    for sf in skill_files:
        name, violations = validate_skill(sf)
        if violations:
            failed.append((name, violations, sf))
        else:
            passed.append(name)

    # Print passes first
    for name in passed:
        print(f"PASS: {name} (5/5 checks)")

    if passed and failed:
        print()

    # Print failures
    for name, violations, path in failed:
        print(f"VIOLATION: {name}")
        for check_id, msg in violations:
            print(f"  [{check_id}] {msg}")
        print()

    # Summary
    total = len(passed) + len(failed)
    print("=== Summary ===")
    print(f"Total skills: {total}")
    print(f"Passed: {len(passed)}")
    print(f"Violations: {len(failed)}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
