"""Flat-file to Postgres migration tool for Flywheel v1 -> v2.

Converts existing ~/.claude/context/ files into Postgres rows with
round-trip fidelity. Preserves original dates, confidence levels,
evidence counts, and content exactly as-is.

Usage:
    python -m flywheel.migration_tool \
        --context-root ~/.claude/context \
        --tenant-id <uuid> \
        --user-id <uuid> \
        [--dry-run] \
        [--force] \
        [--verbose]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flywheel.db.models import ContextCatalog, ContextEntry

logger = logging.getLogger("flywheel.migration_tool")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ParsedEntry:
    """A single parsed v1 context entry."""

    date: str  # YYYY-MM-DD
    source: str
    detail: str
    confidence: str
    evidence_count: int
    content: list[str]  # Content lines (without "- " prefix)


@dataclass
class ParseError:
    """A line that failed to parse."""

    file_path: str
    line_number: int
    raw_text: str


@dataclass
class MigrationResult:
    """Result of migrating a single file."""

    file_name: str
    entries_found: int = 0
    entries_inserted: int = 0
    skipped: bool = False
    errors: list[ParseError] = field(default_factory=list)


@dataclass
class MigrationSummary:
    """Summary of the full migration run."""

    files_processed: int = 0
    total_entries: int = 0
    total_inserted: int = 0
    total_errors: int = 0
    total_skipped: int = 0
    file_results: list[MigrationResult] = field(default_factory=list)
    all_errors: list[ParseError] = field(default_factory=list)


# ---------------------------------------------------------------------------
# V1 entry parsing
# ---------------------------------------------------------------------------

# V1 header: [YYYY-MM-DD | source: skill-name | detail text]
_V1_HEADER_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2})\s*\|\s*source:\s*([^|\]]+?)(?:\s*\|\s*(.+?))?\]"
)

# Inline confidence/evidence on header line (alternative format):
# [YYYY-MM-DD | source: name | detail] confidence: high | evidence: 3
_INLINE_META_RE = re.compile(
    r"\]\s*confidence:\s*(\w+)\s*\|\s*evidence:\s*(\d+)"
)

# V1 metadata lines within entry body
_EVIDENCE_COUNT_RE = re.compile(r"-\s*Evidence_count:\s*(\d+)", re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r"-\s*Confidence:\s*(\w+)", re.IGNORECASE)


def parse_v1_file(
    file_path: Path,
) -> tuple[list[ParsedEntry], list[ParseError]]:
    """Parse a v1 flat-file context file into structured entries.

    Handles both v1 body-metadata format and inline header-metadata format.

    Returns:
        Tuple of (parsed_entries, parse_errors).
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [], [ParseError(str(file_path), 0, f"Cannot read file: {e}")]

    if not content or not content.strip():
        return [], []

    entries: list[ParsedEntry] = []
    errors: list[ParseError] = []

    # Find all header positions
    header_matches = list(_V1_HEADER_RE.finditer(content))
    if not header_matches:
        return [], []

    lines = content.split("\n")
    # Map character offset -> line number for error reporting
    line_offsets: list[int] = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line) + 1  # +1 for newline

    def _char_to_line(char_pos: int) -> int:
        """Convert character position to 1-based line number."""
        for i in range(len(line_offsets) - 1, -1, -1):
            if char_pos >= line_offsets[i]:
                return i + 1
        return 1

    for i, match in enumerate(header_matches):
        header_start = match.start()
        header_end = match.end()
        header_line_num = _char_to_line(header_start)

        if i + 1 < len(header_matches):
            body_end = header_matches[i + 1].start()
        else:
            body_end = len(content)

        # Parse header fields
        date_str = match.group(1)
        source = match.group(2).strip()
        detail = match.group(3).strip() if match.group(3) else ""

        # Validate date
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            errors.append(ParseError(
                str(file_path), header_line_num,
                f"Invalid date in header: {content[header_start:header_end]}"
            ))
            continue

        # Check for inline metadata on the header line
        header_line_end = content.find("\n", header_start)
        if header_line_end == -1:
            header_line_text = content[header_start:]
        else:
            header_line_text = content[header_start:header_line_end]

        inline_match = _INLINE_META_RE.search(header_line_text)

        # Extract body text (after the full header line)
        body_start = header_line_end + 1 if header_line_end != -1 else header_end
        body = content[body_start:body_end]

        # Parse body lines
        evidence_count = 1
        confidence = "medium"
        content_lines: list[str] = []

        if inline_match:
            # Inline format: confidence and evidence on header line
            confidence = inline_match.group(1).lower()
            evidence_count = int(inline_match.group(2))

        for body_line in body.split("\n"):
            stripped = body_line.strip()
            if not stripped:
                continue

            # Check for v1 metadata lines (only if no inline metadata)
            if not inline_match:
                ev_match = _EVIDENCE_COUNT_RE.match(stripped)
                if ev_match:
                    evidence_count = int(ev_match.group(1))
                    continue

                conf_match = _CONFIDENCE_RE.match(stripped)
                if conf_match:
                    confidence = conf_match.group(1).lower()
                    continue

            # Content line -- strip "- " prefix
            if stripped.startswith("- "):
                content_lines.append(stripped[2:])
            elif stripped.startswith("-"):
                content_lines.append(stripped[1:].strip())
            else:
                content_lines.append(stripped)

        entries.append(ParsedEntry(
            date=date_str,
            source=source,
            detail=detail,
            confidence=confidence,
            evidence_count=evidence_count,
            content=content_lines,
        ))

    return entries, errors


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

_EXCLUDED_FILES = {"_manifest.md", "_events.jsonl"}


def discover_context_files(context_root: Path) -> list[tuple[Path, str]]:
    """Walk context_root and find all migratable .md files.

    Excludes _manifest.md, _events.jsonl, and dotfiles.

    Returns:
        List of (absolute_path, relative_name) tuples.
    """
    if not context_root.is_dir():
        return []

    results: list[tuple[Path, str]] = []
    for path in sorted(context_root.rglob("*.md")):
        # Skip dotfiles/dotdirs
        if any(part.startswith(".") for part in path.relative_to(context_root).parts):
            continue
        # Skip excluded files
        if path.name in _EXCLUDED_FILES:
            continue
        rel_name = str(path.relative_to(context_root))
        # Remove .md extension for file_name (context files are referenced without extension)
        if rel_name.endswith(".md"):
            rel_name = rel_name[:-3]
        results.append((path, rel_name))

    return results


# ---------------------------------------------------------------------------
# Migration core
# ---------------------------------------------------------------------------

async def migrate_file(
    session: AsyncSession,
    file_path: Path,
    file_name: str,
    tenant_id: str,
    user_id: str,
    dry_run: bool = False,
    force: bool = False,
) -> MigrationResult:
    """Migrate a single v1 context file to Postgres.

    Inserts entries directly via ORM (not through storage.py append_entry)
    to preserve original dates, evidence_counts, and confidence values.

    Args:
        session: AsyncSession (should be admin/superuser, not RLS-constrained).
        file_path: Absolute path to the v1 .md file.
        file_name: Relative name (without .md extension).
        tenant_id: Target tenant UUID.
        user_id: User UUID to assign as entry owner.
        dry_run: If True, parse and count but don't insert.
        force: If True, delete existing entries before re-inserting.

    Returns:
        MigrationResult with counts and errors.
    """
    result = MigrationResult(file_name=file_name)

    # Parse the file
    entries, errors = parse_v1_file(file_path)
    result.entries_found = len(entries)
    result.errors = errors

    if dry_run:
        return result

    # Idempotency check: see if entries already exist for this file+tenant
    existing_count_stmt = (
        select(func.count())
        .select_from(ContextEntry)
        .where(
            ContextEntry.tenant_id == tenant_id,
            ContextEntry.file_name == file_name,
            ContextEntry.deleted_at.is_(None),
        )
    )
    count_result = await session.execute(existing_count_stmt)
    existing_count = count_result.scalar() or 0

    if existing_count > 0 and not force:
        logger.info(
            "Skipping %s: %d entries already exist for this tenant",
            file_name, existing_count,
        )
        result.skipped = True
        return result

    if existing_count > 0 and force:
        # Delete existing entries for this file+tenant before re-inserting
        from sqlalchemy import delete
        del_stmt = (
            delete(ContextEntry)
            .where(
                ContextEntry.tenant_id == tenant_id,
                ContextEntry.file_name == file_name,
            )
        )
        await session.execute(del_stmt)
        logger.info("Deleted %d existing entries for %s (--force)", existing_count, file_name)

    # Insert entries
    for parsed in entries:
        entry_date = datetime.strptime(parsed.date, "%Y-%m-%d").date()
        content_text = "\n".join(parsed.content)

        new_entry = ContextEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            file_name=file_name,
            source=parsed.source,
            detail=parsed.detail if parsed.detail else None,
            confidence=parsed.confidence,
            evidence_count=parsed.evidence_count,
            content=content_text,
            date=entry_date,
        )
        session.add(new_entry)
        result.entries_inserted += 1

    await session.flush()

    # Upsert catalog entry
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    catalog_stmt = pg_insert(ContextCatalog).values(
        tenant_id=tenant_id,
        file_name=file_name,
        status="active",
    )
    catalog_stmt = catalog_stmt.on_conflict_do_update(
        index_elements=["tenant_id", "file_name"],
        set_={"status": "active"},
    )
    await session.execute(catalog_stmt)

    return result


async def migrate_all(
    context_root: Path,
    tenant_id: str,
    user_id: str,
    database_url: str,
    dry_run: bool = False,
    force: bool = False,
    verbose: bool = False,
) -> MigrationSummary:
    """Migrate all v1 context files to Postgres.

    Args:
        context_root: Path to ~/.claude/context/ directory.
        tenant_id: Target tenant UUID.
        user_id: User UUID.
        database_url: Async Postgres connection URL.
        dry_run: Parse and report without inserting.
        force: Re-migrate files that already have entries.
        verbose: Print per-file details.

    Returns:
        MigrationSummary with aggregate statistics.
    """
    summary = MigrationSummary()

    files = discover_context_files(context_root)
    if not files:
        logger.warning("No context files found in %s", context_root)
        return summary

    total_files = len(files)

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with session_factory() as session:
            for idx, (file_path, file_name) in enumerate(files, 1):
                prefix = f"[{idx}/{total_files}]"

                try:
                    result = await migrate_file(
                        session, file_path, file_name,
                        tenant_id, user_id,
                        dry_run=dry_run, force=force,
                    )
                except Exception as e:
                    logger.error("%s Error migrating %s: %s", prefix, file_name, e)
                    result = MigrationResult(file_name=file_name)
                    result.errors.append(ParseError(str(file_path), 0, str(e)))

                summary.file_results.append(result)
                summary.files_processed += 1
                summary.total_entries += result.entries_found
                summary.total_inserted += result.entries_inserted
                summary.total_errors += len(result.errors)
                summary.all_errors.extend(result.errors)
                if result.skipped:
                    summary.total_skipped += 1

                status = "DRY-RUN" if dry_run else (
                    "SKIPPED" if result.skipped else "OK"
                )
                msg = f"{prefix} {file_name}... {result.entries_found} entries"
                if result.entries_inserted > 0:
                    msg += f" ({result.entries_inserted} inserted)"
                if result.skipped:
                    msg += " (skipped - already exists)"
                if result.errors:
                    msg += f" ({len(result.errors)} errors)"

                if verbose or result.errors:
                    print(msg)
                else:
                    print(f"{prefix} Migrating {file_name}... {result.entries_found} entries [{status}]")

            if not dry_run:
                # Round-trip verification
                if verbose:
                    print("\nVerifying round-trip fidelity...")

                from flywheel.storage import read_context
                from flywheel.db.session import get_tenant_session

                verify_session = await get_tenant_session(
                    session_factory, tenant_id, user_id
                )
                try:
                    for result in summary.file_results:
                        if result.skipped or result.entries_inserted == 0:
                            continue
                        readback = await read_context(verify_session, result.file_name)
                        if not readback:
                            logger.warning(
                                "Round-trip: no data read back for %s",
                                result.file_name,
                            )
                        elif verbose:
                            # Count entries in readback
                            readback_count = len(_V1_HEADER_RE.findall(readback))
                            if readback_count != result.entries_inserted:
                                logger.warning(
                                    "Round-trip: %s inserted %d but read back %d",
                                    result.file_name,
                                    result.entries_inserted,
                                    readback_count,
                                )
                finally:
                    await verify_session.close()

                await session.commit()

    finally:
        await engine.dispose()

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(summary: MigrationSummary, dry_run: bool) -> None:
    """Print human-readable migration summary."""
    mode = "Dry-run" if dry_run else "Migration"
    print(f"\n{mode} complete:")
    print(f"  Files processed: {summary.files_processed}")
    print(f"  Entries {'found' if dry_run else 'migrated'}: {summary.total_entries}")
    if not dry_run:
        print(f"  Entries inserted: {summary.total_inserted}")
    print(f"  Errors: {summary.total_errors}")
    if summary.total_skipped > 0:
        print(f"  Skipped (already exist): {summary.total_skipped}")

    if summary.all_errors:
        print("\nErrors:")
        for err in summary.all_errors:
            print(f"  {err.file_path}:{err.line_number} - {err.raw_text}")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Migrate v1 flat-file context store to Postgres.",
        prog="python -m flywheel.migration_tool",
    )
    parser.add_argument(
        "--context-root",
        type=Path,
        default=Path.home() / ".claude" / "context",
        help="Path to v1 context root (default: ~/.claude/context)",
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Target tenant UUID",
    )
    parser.add_argument(
        "--user-id",
        required=True,
        help="User UUID for entry ownership",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Async Postgres URL (default: from FLYWHEEL settings)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report statistics without inserting",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-migrate files that already have entries (deletes existing first)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-file details and verification results",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.context_root.is_dir():
        print(f"Error: context root does not exist: {args.context_root}", file=sys.stderr)
        return 1

    db_url = args.database_url
    if db_url is None:
        from flywheel.config import settings
        db_url = settings.database_url

    summary = asyncio.run(
        migrate_all(
            context_root=args.context_root,
            tenant_id=args.tenant_id,
            user_id=args.user_id,
            database_url=db_url,
            dry_run=args.dry_run,
            force=args.force,
            verbose=args.verbose,
        )
    )

    _print_summary(summary, args.dry_run)

    return 1 if summary.total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
