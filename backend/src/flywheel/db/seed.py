"""Seed pipeline: parse SKILL.md files and upsert into skill_definitions.

Provides:
- seed_skills(): Async function that scans SKILL.md files, upserts into
  skill_definitions, populates tenant_skills for new skills, and detects orphans.
- SeedResult: Dataclass with add/update/unchanged/orphan/error counts.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import SkillDefinition, TenantSkill

# Try PyYAML first, fall back to simple parser
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKIP_DIRS = {"_archived", "_shared", "gtm-shared"}

# Default skills directory: flywheel-v2/skills/
_DEFAULT_SKILLS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "skills"
)

# Fields used to detect whether a row has changed
_CHANGE_FIELDS = ("version", "description", "web_tier", "system_prompt")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SkillData:
    """Parsed skill data from a SKILL.md file."""

    name: str
    version: str
    description: str | None
    web_tier: int
    system_prompt: str | None
    contract_reads: list[str] = field(default_factory=list)
    contract_writes: list[str] = field(default_factory=list)
    engine_module: str | None = None
    tags: list[str] = field(default_factory=list)
    token_budget: int | None = None
    parameters: dict = field(default_factory=dict)
    enabled: bool = True
    protected: bool = True


@dataclass
class SkillStatus:
    """Status of a single skill during seed."""

    name: str
    action: str  # "added", "updated", "unchanged"
    old_version: str | None = None
    new_version: str | None = None


@dataclass
class SeedResult:
    """Result of a seed_skills() run."""

    added: int = 0
    updated: int = 0
    unchanged: int = 0
    orphaned: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    details: list[SkillStatus] = field(default_factory=list)


# ---------------------------------------------------------------------------
# YAML parsing (copied from scripts/validate_skills.py -- scripts/ is not a package)
# ---------------------------------------------------------------------------


def parse_frontmatter(filepath: str) -> dict:
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

    return data, content


def _simple_yaml_parse(raw: str) -> dict:
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


def _extract_system_prompt(full_content: str) -> str | None:
    """Extract content after the closing --- frontmatter marker as system_prompt."""
    match = re.match(r"^---\s*\n.*?\n---\s*\n?(.*)", full_content, re.DOTALL)
    if not match:
        return None
    prompt = match.group(1).strip()
    return prompt if prompt else None


# ---------------------------------------------------------------------------
# Skill scanning
# ---------------------------------------------------------------------------


def scan_skills(skills_dir: str) -> tuple[list[SkillData], list[str]]:
    """Scan a skills directory and parse all SKILL.md files.

    Args:
        skills_dir: Absolute path to the skills directory.

    Returns:
        Tuple of (list of SkillData, list of error strings).
    """
    skills: list[SkillData] = []
    errors: list[str] = []

    if not os.path.isdir(skills_dir):
        errors.append("Skills directory not found: %s" % skills_dir)
        return skills, errors

    entries = sorted(os.listdir(skills_dir))

    for entry in entries:
        entry_path = os.path.join(skills_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        if entry.startswith(".") or entry.startswith("_") or entry in SKIP_DIRS:
            continue

        skill_md = os.path.join(entry_path, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue

        try:
            data, full_content = parse_frontmatter(skill_md)
        except ValueError as e:
            errors.append("%s: %s" % (entry, str(e)))
            continue

        # Extract required fields
        name = data.get("name")
        if not name or not isinstance(name, str):
            errors.append("%s: missing or invalid 'name' field" % entry)
            continue

        version = str(data.get("version", "0.0.0"))
        description = data.get("description")
        if isinstance(description, str):
            description = description.strip()

        web_tier = data.get("web_tier", 1)
        if not isinstance(web_tier, int) or web_tier not in (1, 2, 3):
            web_tier = 1

        system_prompt = _extract_system_prompt(full_content)

        # Optional fields
        contract_reads = data.get("contract_reads", data.get("reads", []))
        if not isinstance(contract_reads, list):
            contract_reads = []

        contract_writes = data.get("contract_writes", data.get("writes", []))
        if not isinstance(contract_writes, list):
            contract_writes = []

        engine_module = data.get("engine")
        if not isinstance(engine_module, str):
            engine_module = None

        tags = data.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        token_budget = data.get("token_budget")
        if token_budget is not None:
            try:
                token_budget = int(token_budget)
            except (ValueError, TypeError):
                token_budget = None

        parameters = data.get("parameters", {})
        if not isinstance(parameters, dict):
            parameters = {}

        # Extract triggers from frontmatter and inject into parameters JSONB
        triggers = data.get("triggers", [])
        if isinstance(triggers, list) and triggers:
            parameters["triggers"] = triggers

        # Read enabled flag from frontmatter (default True)
        enabled = data.get("enabled", True)
        if not isinstance(enabled, bool):
            enabled = True

        # Read public flag from frontmatter (default False = protected by default)
        is_public = data.get("public", False)
        if not isinstance(is_public, bool):
            is_public = False
        protected = not is_public

        skills.append(
            SkillData(
                name=name,
                version=version,
                description=description,
                web_tier=web_tier,
                system_prompt=system_prompt,
                contract_reads=contract_reads,
                contract_writes=contract_writes,
                engine_module=engine_module,
                tags=tags,
                token_budget=token_budget,
                parameters=parameters,
                enabled=enabled,
                protected=protected,
            )
        )

    return skills, errors


# ---------------------------------------------------------------------------
# Core seed function
# ---------------------------------------------------------------------------


async def seed_skills(
    session: AsyncSession,
    skills_dir: str | None = None,
    dry_run: bool = False,
) -> SeedResult:
    """Parse SKILL.md files and upsert into skill_definitions.

    Uses service role (no RLS SET ROLE) since skill_definitions has a
    service-role-only manage policy. The session should be a plain session
    from get_db(), NOT a tenant session.

    Args:
        session: AsyncSession (plain, not tenant-scoped).
        skills_dir: Override skills directory path.
        dry_run: If True, parse and compare but do NOT write to DB.

    Returns:
        SeedResult with add/update/unchanged/orphan counts and details.
    """
    if skills_dir is None:
        skills_dir = os.path.abspath(_DEFAULT_SKILLS_DIR)
    else:
        skills_dir = os.path.abspath(skills_dir)

    result = SeedResult()

    # 1. Parse SKILL.md files
    parsed_skills, parse_errors = scan_skills(skills_dir)
    result.errors.extend(parse_errors)

    if not parsed_skills:
        return result

    # 2. Fetch existing rows for change detection
    existing_rows = await session.execute(
        select(
            SkillDefinition.id,
            SkillDefinition.name,
            SkillDefinition.version,
            SkillDefinition.description,
            SkillDefinition.web_tier,
            SkillDefinition.system_prompt,
        )
    )
    existing_map: dict[str, dict] = {}
    for row in existing_rows:
        existing_map[row.name] = {
            "id": row.id,
            "version": row.version,
            "description": row.description,
            "web_tier": row.web_tier,
            "system_prompt": row.system_prompt,
        }

    # 3. Classify each skill as added/updated/unchanged
    new_skill_names: list[str] = []

    for skill in parsed_skills:
        existing = existing_map.get(skill.name)
        if existing is None:
            result.added += 1
            new_skill_names.append(skill.name)
            result.details.append(
                SkillStatus(name=skill.name, action="added", new_version=skill.version)
            )
        else:
            # Check if any change field differs
            changed = (
                existing["version"] != skill.version
                or (existing["description"] or "") != (skill.description or "")
                or existing["web_tier"] != skill.web_tier
                or (existing["system_prompt"] or "") != (skill.system_prompt or "")
            )
            if changed:
                result.updated += 1
                result.details.append(
                    SkillStatus(
                        name=skill.name,
                        action="updated",
                        old_version=existing["version"],
                        new_version=skill.version,
                    )
                )
            else:
                result.unchanged += 1
                result.details.append(
                    SkillStatus(name=skill.name, action="unchanged")
                )

    # 4. Orphan detection
    parsed_names = {s.name for s in parsed_skills}
    all_db_names = set(existing_map.keys())
    orphaned = sorted(all_db_names - parsed_names)
    result.orphaned = orphaned

    if dry_run:
        return result

    # 5. Upsert into skill_definitions
    for skill in parsed_skills:
        values = {
            "name": skill.name,
            "version": skill.version,
            "description": skill.description,
            "web_tier": skill.web_tier,
            "system_prompt": skill.system_prompt,
            "contract_reads": skill.contract_reads,
            "contract_writes": skill.contract_writes,
            "engine_module": skill.engine_module,
            "tags": skill.tags,
            "token_budget": skill.token_budget,
            "parameters": skill.parameters,
            "enabled": skill.enabled,
            "protected": skill.protected,
        }

        stmt = pg_insert(SkillDefinition).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_skill_defs_name",
            set_={
                "version": stmt.excluded.version,
                "description": stmt.excluded.description,
                "web_tier": stmt.excluded.web_tier,
                "system_prompt": stmt.excluded.system_prompt,
                "contract_reads": stmt.excluded.contract_reads,
                "contract_writes": stmt.excluded.contract_writes,
                "engine_module": stmt.excluded.engine_module,
                "tags": stmt.excluded.tags,
                "token_budget": stmt.excluded.token_budget,
                "parameters": stmt.excluded.parameters,
                "enabled": stmt.excluded.enabled,
                "protected": stmt.excluded.protected,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)

    # 6. Populate tenant_skills for newly added skills
    if new_skill_names:
        # Get IDs of newly added skill_definitions
        new_skill_rows = await session.execute(
            select(SkillDefinition.id).where(
                SkillDefinition.name.in_(new_skill_names)
            )
        )
        new_skill_ids = [row.id for row in new_skill_rows]

        if new_skill_ids:
            # Get all tenant IDs
            tenant_ids_result = await session.execute(
                text("SELECT id FROM tenants")
            )
            tenant_ids = [row.id for row in tenant_ids_result]

            # Insert tenant_skills via cross-product with ON CONFLICT DO NOTHING
            for tid in tenant_ids:
                for sid in new_skill_ids:
                    ts_stmt = pg_insert(TenantSkill).values(
                        tenant_id=tid, skill_id=sid
                    )
                    ts_stmt = ts_stmt.on_conflict_do_nothing()
                    await session.execute(ts_stmt)

    await session.commit()
    return result
