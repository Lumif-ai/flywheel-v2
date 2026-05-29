"""
skill_promoter.py - Promotion automation for ctx- skills to primary names.

Handles the 6-step promotion process: scan references, archive legacy,
rename ctx- skill, update SKILL.md frontmatter, update catalog references,
and pre-promotion validation.

All functions accept skills_root and context_root parameters for testability.
No external dependencies beyond stdlib.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Promotion Map
# ---------------------------------------------------------------------------

PROMOTION_MAP = [
    {
        "ctx": "ctx-meeting-processor",
        "legacy": "lumifai-meeting-processor",
        "promoted": "meeting-processor",
    },
    {
        "ctx": "ctx-meeting-prep",
        "legacy": "lumifai-meeting-prep",
        "promoted": "meeting-prep",
    },
    {
        "ctx": "ctx-investor-update",
        "legacy": "lumifai-investor-update",
        "promoted": "investor-update",
    },
    {
        "ctx": "ctx-gtm-my-company",
        "legacy": "gtm-my-company",
        "promoted": "gtm-my-company",
        "legacy_archive_name": "gtm-my-company-legacy",
    },
    {
        "ctx": "ctx-gtm-pipeline",
        "legacy": None,
        "promoted": "gtm-pipeline",
    },
]

# Default paths
# DEPRECATED (Phase 152 — 2026-04-19): legacy ~/.claude/skills/ path; skills are served via flywheel_fetch_skill_assets. Retained for developer tooling only; no runtime impact.
DEFAULT_SKILLS_ROOT = Path.home() / ".claude" / "skills"
DEFAULT_CONTEXT_ROOT = Path.home() / ".claude" / "context"


# ---------------------------------------------------------------------------
# 1. scan_references
# ---------------------------------------------------------------------------


def scan_references(
    skill_name: str,
    skills_root: Path = DEFAULT_SKILLS_ROOT,
    context_root: Path = DEFAULT_CONTEXT_ROOT,
) -> List[dict]:
    """Scan all SKILL.md files and _catalog.md for references to skill_name.

    Uses simple string matching (not regex) -- sufficient for skill name
    references.

    Args:
        skill_name: The skill name to search for.
        skills_root: Root directory of skills.
        context_root: Root directory of context store.

    Returns:
        List of {"file": path, "line_number": int, "line": str} for each
        reference found.
    """
    references = []
    skills_root = Path(skills_root)
    context_root = Path(context_root)

    # Scan all SKILL.md files in skills_root
    if skills_root.exists():
        for skill_dir in sorted(skills_root.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                try:
                    with open(str(skill_md), "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            if skill_name in line:
                                references.append({
                                    "file": str(skill_md),
                                    "line_number": line_num,
                                    "line": line.rstrip(),
                                })
                except (IOError, UnicodeDecodeError):
                    pass

    # Scan _catalog.md
    catalog_path = context_root / "_catalog.md"
    if catalog_path.exists():
        try:
            with open(str(catalog_path), "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if skill_name in line:
                        references.append({
                            "file": str(catalog_path),
                            "line_number": line_num,
                            "line": line.rstrip(),
                        })
        except (IOError, UnicodeDecodeError):
            pass

    return references


# ---------------------------------------------------------------------------
# 2. archive_skill
# ---------------------------------------------------------------------------


def archive_skill(
    skill_name: str,
    skills_root: Path = DEFAULT_SKILLS_ROOT,
    archive_name: Optional[str] = None,
) -> str:
    """Move a skill directory to _archived/.

    Args:
        skill_name: Name of the skill directory to archive.
        skills_root: Root directory of skills.
        archive_name: Optional custom name in _archived/. Defaults to
            skill_name.

    Returns:
        The archive destination path as a string.

    Raises:
        FileNotFoundError: If source skill directory does not exist.
        FileExistsError: If archive destination already exists.
    """
    skills_root = Path(skills_root)
    source = skills_root / skill_name
    dest_name = archive_name if archive_name else skill_name
    archive_dir = skills_root / "_archived"
    dest = archive_dir / dest_name

    if not source.exists():
        raise FileNotFoundError(
            "Source skill directory does not exist: %s" % str(source)
        )

    if dest.exists():
        raise FileExistsError(
            "Archive destination already exists: %s" % str(dest)
        )

    # Create _archived/ if it doesn't exist
    archive_dir.mkdir(parents=True, exist_ok=True)

    shutil.move(str(source), str(dest))
    return str(dest)


# ---------------------------------------------------------------------------
# 3. rename_skill
# ---------------------------------------------------------------------------


def rename_skill(
    old_name: str,
    new_name: str,
    skills_root: Path = DEFAULT_SKILLS_ROOT,
) -> str:
    """Rename a skill directory.

    Args:
        old_name: Current directory name.
        new_name: New directory name.
        skills_root: Root directory of skills.

    Returns:
        The new path as a string.

    Raises:
        FileNotFoundError: If source does not exist.
        FileExistsError: If destination already exists.
    """
    skills_root = Path(skills_root)
    source = skills_root / old_name
    dest = skills_root / new_name

    if not source.exists():
        raise FileNotFoundError(
            "Source skill directory does not exist: %s" % str(source)
        )

    if dest.exists():
        raise FileExistsError(
            "Destination already exists: %s" % str(dest)
        )

    shutil.move(str(source), str(dest))
    return str(dest)


# ---------------------------------------------------------------------------
# 4. update_skill_md
# ---------------------------------------------------------------------------


def update_skill_md(
    skill_dir: str,
    promoted_name: str,
    new_version: str = "2.0",
) -> dict:
    """Update SKILL.md frontmatter and remove coexistence notes.

    Args:
        skill_dir: Path to the skill directory containing SKILL.md.
        promoted_name: The new name to set in frontmatter.
        new_version: The new version to set. Defaults to "2.0".

    Returns:
        {"updated_fields": [...], "removed_lines": int}
    """
    skill_md_path = Path(skill_dir) / "SKILL.md"

    with open(str(skill_md_path), "r", encoding="utf-8") as f:
        content = f.read()

    updated_fields = []
    removed_lines = 0

    lines = content.split("\n")
    new_lines = []
    in_frontmatter = False
    frontmatter_count = 0

    # Coexistence phrases to detect (case-insensitive)
    coexistence_phrases = [
        "coexists with",
        "legacy",
        "both can be triggered",
        "this skill replaces the legacy",
    ]

    i = 0
    while i < len(lines):
        line = lines[i]

        # Track frontmatter boundaries
        if line.strip() == "---":
            frontmatter_count += 1
            in_frontmatter = (frontmatter_count == 1)
            new_lines.append(line)
            i += 1
            continue

        if in_frontmatter:
            # Update name field
            name_match = re.match(r'^(\s*name:\s*)(.*)', line)
            if name_match:
                new_lines.append("%s%s" % (name_match.group(1), promoted_name))
                updated_fields.append("name")
                i += 1
                continue

            # Update version field
            version_match = re.match(r'^(\s*version:\s*)(.*)', line)
            if version_match:
                new_lines.append('%sversion: "%s"' % (
                    "" if not line.startswith(" ") else re.match(r'^(\s*)', line).group(1),
                    new_version,
                ))
                updated_fields.append("version")
                i += 1
                continue

        # Outside frontmatter: check for coexistence notes
        if frontmatter_count >= 2:
            line_lower = line.lower()
            is_coexistence = any(
                phrase in line_lower for phrase in coexistence_phrases
            )

            if is_coexistence:
                removed_lines += 1
                i += 1
                # Also skip blank line after removed line if present
                if i < len(lines) and lines[i].strip() == "":
                    i += 1
                continue

        new_lines.append(line)
        i += 1

    with open(str(skill_md_path), "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))

    return {"updated_fields": updated_fields, "removed_lines": removed_lines}


# ---------------------------------------------------------------------------
# 5. update_catalog
# ---------------------------------------------------------------------------


def update_catalog(
    context_root: Path,
    old_name: str,
    new_name: str,
) -> int:
    """Replace all occurrences of old_name with new_name in _catalog.md.

    Args:
        context_root: Root directory of context store.
        old_name: The old skill name to replace.
        new_name: The new skill name.

    Returns:
        Count of replacements made.
    """
    context_root = Path(context_root)
    catalog_path = context_root / "_catalog.md"

    if not catalog_path.exists():
        return 0

    with open(str(catalog_path), "r", encoding="utf-8") as f:
        content = f.read()

    count = content.count(old_name)

    if count > 0:
        updated = content.replace(old_name, new_name)
        with open(str(catalog_path), "w", encoding="utf-8") as f:
            f.write(updated)

    return count


# ---------------------------------------------------------------------------
# 6. promote_skill
# ---------------------------------------------------------------------------


def promote_skill(
    entry: dict,
    skills_root: Path = DEFAULT_SKILLS_ROOT,
    context_root: Path = DEFAULT_CONTEXT_ROOT,
    dry_run: bool = True,
) -> dict:
    """Orchestrate the full promotion for one skill entry from PROMOTION_MAP.

    Steps: scan refs -> archive legacy (if exists) -> rename ctx- ->
    update SKILL.md -> update catalog.

    Args:
        entry: One dict from PROMOTION_MAP.
        skills_root: Root directory of skills.
        context_root: Root directory of context store.
        dry_run: If True, report what WOULD happen without making changes.

    Returns:
        {"skill": name, "status": "promoted"|"dry_run",
         "archived": path|None, "renamed_to": path,
         "refs_updated": int, "refs_found": [...]}
    """
    skills_root = Path(skills_root)
    context_root = Path(context_root)

    ctx_name = entry["ctx"]
    legacy_name = entry.get("legacy")
    promoted_name = entry["promoted"]
    archive_name = entry.get("legacy_archive_name")

    # Step 1: Scan references
    refs_found = []
    refs_found.extend(scan_references(ctx_name, skills_root, context_root))
    if legacy_name:
        refs_found.extend(scan_references(legacy_name, skills_root, context_root))

    result = {
        "skill": ctx_name,
        "status": "dry_run" if dry_run else "promoted",
        "archived": None,
        "renamed_to": None,
        "refs_updated": 0,
        "refs_found": refs_found,
    }

    if dry_run:
        # Report what would happen
        if legacy_name and (skills_root / legacy_name).exists():
            result["archived"] = str(
                skills_root / "_archived" / (archive_name or legacy_name)
            )
        if (skills_root / ctx_name).exists():
            result["renamed_to"] = str(skills_root / promoted_name)
        return result

    # Step 2: Archive legacy (if exists and not None)
    if legacy_name and (skills_root / legacy_name).exists():
        archived_path = archive_skill(
            legacy_name, skills_root, archive_name=archive_name
        )
        result["archived"] = archived_path

    # Step 3: Rename ctx- to promoted name
    if (skills_root / ctx_name).exists():
        new_path = rename_skill(ctx_name, promoted_name, skills_root)
        result["renamed_to"] = new_path

        # Step 4: Update SKILL.md
        update_skill_md(new_path, promoted_name)

    # Step 5: Update catalog
    refs_updated = 0
    refs_updated += update_catalog(context_root, ctx_name, promoted_name)
    if legacy_name:
        refs_updated += update_catalog(context_root, legacy_name, promoted_name)
    result["refs_updated"] = refs_updated

    return result


# ---------------------------------------------------------------------------
# 7. promote_all
# ---------------------------------------------------------------------------


def promote_all(
    skills_root: Path = DEFAULT_SKILLS_ROOT,
    context_root: Path = DEFAULT_CONTEXT_ROOT,
    dry_run: bool = True,
) -> List[dict]:
    """Run promote_skill for each entry in PROMOTION_MAP in order.

    Args:
        skills_root: Root directory of skills.
        context_root: Root directory of context store.
        dry_run: If True, report what WOULD happen without making changes.

    Returns:
        List of result dicts from promote_skill().
    """
    results = []
    for entry in PROMOTION_MAP:
        result = promote_skill(entry, skills_root, context_root, dry_run)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# 8. validate_pre_promotion
# ---------------------------------------------------------------------------


def validate_pre_promotion(
    skills_root: Path = DEFAULT_SKILLS_ROOT,
    context_root: Path = DEFAULT_CONTEXT_ROOT,
) -> dict:
    """Pre-flight check before any live promotion.

    Verifies:
    - Each ctx- directory exists
    - Each legacy directory exists (if not None)
    - No naming conflicts at destination
    - ctx-gtm-my-company SKILL.md declares write access to sender-profile.md

    Args:
        skills_root: Root directory of skills.
        context_root: Root directory of context store.

    Returns:
        {"ready": bool, "checks": [...], "blockers": [...]}
    """
    skills_root = Path(skills_root)
    context_root = Path(context_root)

    checks = []
    blockers = []

    for entry in PROMOTION_MAP:
        ctx_name = entry["ctx"]
        legacy_name = entry.get("legacy")
        promoted_name = entry["promoted"]
        archive_name = entry.get("legacy_archive_name")

        # Check ctx- directory exists
        ctx_path = skills_root / ctx_name
        if ctx_path.exists():
            checks.append("OK: %s exists" % ctx_name)
        else:
            blockers.append("MISSING: %s directory not found" % ctx_name)

        # Check legacy directory exists (if applicable)
        if legacy_name:
            legacy_path = skills_root / legacy_name
            if legacy_path.exists():
                checks.append("OK: %s (legacy) exists" % legacy_name)
            else:
                blockers.append(
                    "MISSING: %s (legacy) directory not found" % legacy_name
                )

        # Check no naming conflict at promoted destination
        # (Only if promoted name differs from ctx name AND differs from legacy)
        if promoted_name != ctx_name:
            promoted_path = skills_root / promoted_name
            # For gtm-my-company, the legacy dir occupies the promoted name
            # -- that's expected (we archive first)
            if promoted_path.exists() and promoted_name != legacy_name:
                blockers.append(
                    "CONFLICT: %s already exists at destination" % promoted_name
                )
            else:
                checks.append("OK: %s destination clear" % promoted_name)

        # Check archive destination doesn't already exist
        if legacy_name:
            dest_name = archive_name if archive_name else legacy_name
            archive_path = skills_root / "_archived" / dest_name
            if archive_path.exists():
                blockers.append(
                    "CONFLICT: archive destination _archived/%s already exists"
                    % dest_name
                )
            else:
                checks.append("OK: archive _archived/%s clear" % dest_name)

    # Special check: ctx-gtm-my-company must declare sender-profile.md write
    gtm_skill_md = skills_root / "ctx-gtm-my-company" / "SKILL.md"
    if gtm_skill_md.exists():
        try:
            with open(str(gtm_skill_md), "r", encoding="utf-8") as f:
                content = f.read()

            # Check for sender-profile.md reference in the file
            if "sender-profile" in content.lower():
                checks.append(
                    "OK: ctx-gtm-my-company declares sender-profile.md compatibility"
                )
            else:
                blockers.append(
                    "MISSING: ctx-gtm-my-company SKILL.md does not reference "
                    "sender-profile.md -- backward compatibility at risk"
                )
        except (IOError, UnicodeDecodeError):
            blockers.append(
                "ERROR: cannot read ctx-gtm-my-company SKILL.md"
            )
    else:
        # If directory doesn't exist, already flagged above
        checks.append(
            "SKIP: ctx-gtm-my-company SKILL.md check (directory missing)"
        )

    return {
        "ready": len(blockers) == 0,
        "checks": checks,
        "blockers": blockers,
    }
