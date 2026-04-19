#!/usr/bin/env python3
"""Phase 152.1 Plan 02 Task 1 -- one-shot migration of broker auto-memory to Supabase.

Reads ~/.claude/skills/broker/auto-memory/broker.md (if present and non-empty after strip)
and writes its contents to the Flywheel context store via the flywheel_write_context
MCP-tool-equivalent (FlywheelClient.write_context), tagged inline with the migration
marker so the write is distinguishable from future context-store entries.

The MCP-side write_context API does not yet accept a first-class `tags` list, so we
embed the dated migration marker in the content body (first line) -- this keeps the
migration tag durable for idempotency checks (a subsequent run searches the returned
entries for the marker string).

Idempotent:
  - If file absent -> no-op, exit 0.
  - If file is scaffold-only (comments + placeholder headers) -> no-op, exit 0.
  - If re-run on the same day -> script reads existing 'broker' context-file entries
    first, spots the MIGRATION_TAG marker, and skips re-write.

Usage:
    python3 scripts/migrate_broker_auto_memory.py [--dry-run] [--verbose]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

AUTO_MEM = Path.home() / ".claude" / "skills" / "broker" / "auto-memory" / "broker.md"
MIGRATION_TAG = "migrated-from-local-mirror-2026-04-19"
CONTEXT_FILE = "broker"

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent


def _strip_scaffold(raw: str) -> str:
    """Remove HTML comments and common placeholder headings.

    Returns the meaningful content (whitespace-stripped) or '' if only scaffold remained.
    """
    # Drop HTML comments (including multiline)
    text = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)

    placeholder_patterns = [
        r"^#+\s*Broker\s+Skill\s+Memory\s*$",
        r"^#+\s*Auto-Memory.*$",
        r"^#+\s*Learned\s+Preferences\s*$",
        r"^#+\s*Session\s+History\s*$",
        r"^#+\s*Carrier\s+Notes\s*$",
        r"^\*\(entries will be appended here\)\*\s*$",
    ]
    placeholder_re = re.compile("|".join(placeholder_patterns), re.IGNORECASE)

    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            # keep blank lines; we'll strip leading/trailing at the end
            kept.append("")
            continue
        if placeholder_re.match(stripped):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _load_flywheel_client():
    """Import FlywheelClient the same way seed_skills.py does (cli/ on path)."""
    cli_dir = _REPO_ROOT / "cli"
    if str(cli_dir) not in sys.path:
        sys.path.insert(0, str(cli_dir))
    from flywheel_mcp.api_client import FlywheelClient  # noqa: E402
    return FlywheelClient()


def _existing_has_migration_marker(client, verbose: bool = False) -> bool:
    """Return True if a previous migration already wrote the dated marker."""
    try:
        resp = client.read_context_file(CONTEXT_FILE, limit=100, offset=0)
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"(read_context_file pre-check failed -- proceeding with write: {exc!r})")
        return False

    items = resp.get("items", []) if isinstance(resp, dict) else []
    for it in items:
        content = (it.get("content") if isinstance(it, dict) else "") or ""
        if MIGRATION_TAG in content:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not AUTO_MEM.exists():
        print(
            f"NO AUTO-MEMORY FILE at {AUTO_MEM} -- skipping migration; "
            "nothing to preserve before Plan 03 mirror delete."
        )
        return 0

    raw = AUTO_MEM.read_text(encoding="utf-8")
    if args.verbose:
        print(f"Read {len(raw)} bytes from {AUTO_MEM}")

    stripped = _strip_scaffold(raw)
    if args.verbose:
        print(f"After scaffold strip: {len(stripped)} bytes")

    if not stripped or len(stripped) < 20:
        print(
            f"NO AUTO-MEMORY CONTENT TO MIGRATE "
            f"(file was scaffold-only, {len(raw)} bytes raw, {len(stripped)} bytes stripped)."
        )
        return 0

    # Build tagged content (marker first line so it survives in the content body)
    tagged_content = (
        f"<!-- {MIGRATION_TAG} -->\n"
        f"# Migrated from ~/.claude/skills/broker/auto-memory/broker.md (Phase 152.1-02)\n\n"
        f"{stripped}\n"
    )

    client = _load_flywheel_client()

    # Idempotency: check for migration marker in existing entries
    if _existing_has_migration_marker(client, verbose=args.verbose):
        print(
            f"SKIPPED: migration tag '{MIGRATION_TAG}' already present in context store "
            f"'{CONTEXT_FILE}' -- not writing again."
        )
        return 0

    if args.dry_run:
        print(
            f"DRY-RUN: would write {len(tagged_content)} chars to "
            f"file_name='{CONTEXT_FILE}' with marker '{MIGRATION_TAG}'"
        )
        return 0

    resp = client.write_context(
        file_name=CONTEXT_FILE,
        content=tagged_content,
        source="migration-script",
        confidence="high",
        metadata={
            "phase": "152.1-02",
            "migration_tag": MIGRATION_TAG,
            "source_path": str(AUTO_MEM),
            "tags": ["broker", MIGRATION_TAG],
        },
    )
    if args.verbose:
        print(f"write_context response: {resp}")

    # Verify via read-back
    try:
        readback = client.read_context_file(CONTEXT_FILE, limit=100, offset=0)
        items = readback.get("items", []) if isinstance(readback, dict) else []
        # Look for migration marker in any recent entry
        found = False
        for it in items:
            c = (it.get("content") if isinstance(it, dict) else "") or ""
            if MIGRATION_TAG in c and stripped[:80] in c:
                found = True
                break
        if not found:
            print("FAIL: write-verified read-back did not find migrated content with marker")
            return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: read-back error after write: {exc!r}")
        return 1

    print(
        f"MIGRATED ({len(stripped)} chars of meaningful content, "
        f"{len(tagged_content)} chars total) to file_name='{CONTEXT_FILE}' "
        f"with inline marker '{MIGRATION_TAG}'."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
