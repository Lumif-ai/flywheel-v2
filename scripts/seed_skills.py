#!/usr/bin/env python3
"""
seed_skills.py - Parse SKILL.md files and upsert into skill_definitions table.

CLI entry point for the seed pipeline. Scans all skill directories, parses
frontmatter, and upserts into the database with idempotent behavior.

Usage:
    python3 scripts/seed_skills.py [--dry-run] [--verbose] [--skills-dir PATH]

Exit codes:
    0 - Success (even if orphans exist -- orphans are informational)
    1 - Errors occurred (parse failures, DB errors)
"""

import argparse
import asyncio
import os
import sys

# Add backend/src to path so we can import flywheel modules
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_SCRIPT_DIR, "..", "backend")
sys.path.insert(0, os.path.join(_BACKEND_DIR, "src"))

# Ensure .env is loaded from backend/ directory (where DATABASE_URL lives)
_env_file = os.path.join(_BACKEND_DIR, ".env")
if os.path.isfile(_env_file):
    os.environ.setdefault("_PYDANTIC_ENV_FILE", _env_file)
    # Also manually load key vars so pydantic-settings finds them
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key = _key.strip()
                _val = _val.strip()
                if _key and _key not in os.environ:
                    os.environ[_key] = _val

from flywheel.db.seed import seed_skills  # noqa: E402
from flywheel.db.session import get_session_factory  # noqa: E402


async def main(args: argparse.Namespace) -> int:
    """Run the seed pipeline."""
    skills_dir = args.skills_dir
    if skills_dir is None:
        skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills")
    skills_dir = os.path.abspath(skills_dir)

    print("Seed Skills: parsing SKILL.md files...")
    print()

    try:
        factory = get_session_factory()
    except Exception as e:
        print("ERROR: Could not connect to database.")
        print("  %s" % str(e))
        print()
        print("Hint: Ensure DATABASE_URL is set in your environment or .env file.")
        print("  Example: DATABASE_URL=postgresql+asyncpg://flywheel:flywheel@localhost:5432/flywheel")
        return 1

    async with factory() as session:
        try:
            result = await seed_skills(
                session=session,
                skills_dir=skills_dir,
                dry_run=args.dry_run,
            )
        except Exception as e:
            print("ERROR: Seed failed: %s" % str(e))
            return 1

    # Print per-skill details in verbose mode
    if args.verbose and result.details:
        for detail in result.details:
            dots = "." * max(1, 40 - len(detail.name))
            if detail.action == "updated" and detail.old_version and detail.new_version:
                status = "updated (version: %s -> %s)" % (
                    detail.old_version,
                    detail.new_version,
                )
            else:
                status = detail.action
            print("  %s %s %s" % (detail.name, dots, status))
        print()

    # Print summary
    if args.dry_run:
        print("[DRY RUN] No changes written.")
        print()

    print("Summary:")
    print("  Added:     %d" % result.added)
    print("  Updated:   %d" % result.updated)
    print("  Unchanged: %d" % result.unchanged)

    if result.orphaned:
        print(
            "  Orphaned:  %d (%s)" % (len(result.orphaned), ", ".join(result.orphaned))
        )
    else:
        print("  Orphaned:  0")

    print("  Errors:    %d" % len(result.errors))

    if result.errors:
        print()
        print("Errors:")
        for err in result.errors:
            print("  - %s" % err)

    print()
    if result.errors:
        print("Done with errors. Check the list above.")
        return 1
    else:
        if args.dry_run:
            print("Done. No changes were written (dry run).")
        else:
            print("Done. skill_definitions table is up to date.")
        return 0


def cli():
    parser = argparse.ArgumentParser(
        description="Parse SKILL.md files and seed skill_definitions table"
    )
    parser.add_argument(
        "--skills-dir",
        default=None,
        help="Override skills directory path (default: ../skills relative to script)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and compare without writing to DB",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print each skill's status (added/updated/unchanged)",
    )
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
