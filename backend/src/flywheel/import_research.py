"""Import company and market research files into Flywheel v2.

Imports from two source directories:
  - Company research (~claude-outputs/companies/) — linked to Account records
  - Market research (~claude-outputs/research/) — standalone documents

Files are stored as UploadedFile records with provenance in metadata_ JSONB.
Source files are copied to a local data directory so they survive source deletion.

Dedup: content SHA-256 hash + source_path in metadata. Idempotent re-runs.

Usage:
    python -m flywheel.import_research \\
        --tenant-id <uuid> --user-id <uuid> \\
        [--companies-dir ~/claude-outputs/companies/] \\
        [--research-dir ~/claude-outputs/research/] \\
        [--data-dir backend/data/uploads/] \\
        [--dry-run] [--verbose]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import mimetypes
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.dialects.postgresql import JSONB

from flywheel.db.models import PipelineEntry, UploadedFile
from flywheel.utils.normalize import normalize_company_name

logger = logging.getLogger("flywheel.import_research")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FileRecord:
    source_path: Path          # absolute path to source file
    relative_path: str         # e.g. "companies/amphibious-group/report.md"
    source_type: str           # "company-research" or "market-research"
    account_name: str | None   # folder name for company research
    content_hash: str          # SHA-256 hex digest
    size_bytes: int
    mimetype: str


@dataclass
class ImportSummary:
    inserted: int = 0
    skipped: int = 0
    copied: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Mimetypes we can extract text from
_TEXT_MIMETYPES = {
    "text/markdown", "text/html", "text/plain", "text/csv",
}
_EXTRACTABLE_MIMETYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Register .md as text/markdown
mimetypes.add_type("text/markdown", ".md")


def _hash_file(path: Path) -> str:
    """SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _guess_mimetype(path: Path) -> str:
    """Guess mimetype from file extension."""
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def _extract_text_simple(path: Path, mimetype: str) -> str | None:
    """Extract text from text-based files. Returns None for binary formats."""
    if mimetype in _TEXT_MIMETYPES:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
    return None


async def _extract_text_binary(path: Path, mimetype: str) -> str | None:
    """Extract text from PDF/DOCX using the existing extraction service."""
    if mimetype not in _EXTRACTABLE_MIMETYPES:
        return None
    try:
        from flywheel.services.file_extraction import extract_text
        content = path.read_bytes()
        return await extract_text(content, mimetype)
    except Exception as e:
        logger.warning("Text extraction failed for %s: %s", path.name, e)
        return None


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def discover_company_files(companies_dir: Path) -> list[FileRecord]:
    """Discover all files in company research subdirectories."""
    records = []
    if not companies_dir.is_dir():
        return records

    for company_dir in sorted(companies_dir.iterdir()):
        if not company_dir.is_dir():
            continue
        for file_path in sorted(company_dir.iterdir()):
            if file_path.is_dir() or file_path.name.startswith("."):
                continue
            records.append(FileRecord(
                source_path=file_path,
                relative_path=f"companies/{company_dir.name}/{file_path.name}",
                source_type="company-research",
                account_name=company_dir.name,
                content_hash=_hash_file(file_path),
                size_bytes=file_path.stat().st_size,
                mimetype=_guess_mimetype(file_path),
            ))
    return records


def discover_research_files(research_dir: Path) -> list[FileRecord]:
    """Discover all files in market research directory (non-recursive)."""
    records = []
    if not research_dir.is_dir():
        return records

    for file_path in sorted(research_dir.iterdir()):
        if file_path.is_dir() or file_path.name.startswith("."):
            continue
        records.append(FileRecord(
            source_path=file_path,
            relative_path=f"research/{file_path.name}",
            source_type="market-research",
            account_name=None,
            content_hash=_hash_file(file_path),
            size_bytes=file_path.stat().st_size,
            mimetype=_guess_mimetype(file_path),
        ))
    return records


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

async def _find_account_id(
    session: AsyncSession, tenant_id: str, account_name: str | None,
) -> str | None:
    """Match folder name to PipelineEntry. Returns pipeline_entry id or None."""
    if not account_name:
        return None
    normalized = normalize_company_name(account_name)
    if not normalized:
        return None
    result = await session.execute(
        select(PipelineEntry.id).where(
            PipelineEntry.tenant_id == tenant_id,
            PipelineEntry.normalized_name == normalized,
        )
    )
    row = result.scalar_one_or_none()
    return str(row) if row else None


async def _check_existing(
    session: AsyncSession, tenant_id: str, content_hash: str, source_path: str,
) -> bool:
    """Check if a file with this hash+path already exists for this tenant."""
    result = await session.execute(
        select(UploadedFile.id).where(
            UploadedFile.tenant_id == tenant_id,
            UploadedFile.metadata_["content_hash"].astext == content_hash,
            UploadedFile.metadata_["source_path"].astext == source_path,
        )
    )
    return result.scalar_one_or_none() is not None


async def import_research(
    companies_dir: Path | None,
    research_dir: Path | None,
    data_dir: Path,
    tenant_id: str,
    user_id: str,
    database_url: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> ImportSummary:
    """Import company and market research files."""
    summary = ImportSummary()

    # Discover files
    records: list[FileRecord] = []
    if companies_dir:
        company_files = discover_company_files(companies_dir)
        records.extend(company_files)
        print(f"Found {len(company_files)} company research files")
    if research_dir:
        research_files = discover_research_files(research_dir)
        records.extend(research_files)
        print(f"Found {len(research_files)} market research files")

    if not records:
        print("No files to import.")
        return summary

    total = len(records)
    print(f"Total: {total} files to process")

    if dry_run:
        for r in records:
            print(f"  [DRY-RUN] {r.relative_path} ({r.mimetype}, {r.size_bytes} bytes, account={r.account_name})")
        return summary

    # Ensure data directory exists
    dest_root = data_dir / tenant_id
    dest_root.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            for i, rec in enumerate(records, 1):
                prefix = f"[{i}/{total}]"

                # Dedup check
                if await _check_existing(session, tenant_id, rec.content_hash, rec.relative_path):
                    summary.skipped += 1
                    if verbose:
                        print(f"  {prefix} SKIP {rec.relative_path} (already exists)")
                    continue

                # Account linking for company research
                account_id = None
                if rec.account_name:
                    account_id = await _find_account_id(session, tenant_id, rec.account_name)

                # Extract text
                extracted_text = _extract_text_simple(rec.source_path, rec.mimetype)
                if extracted_text is None and rec.mimetype in _EXTRACTABLE_MIMETYPES:
                    try:
                        extracted_text = await _extract_text_binary(rec.source_path, rec.mimetype)
                    except Exception as e:
                        summary.errors.append(f"Text extraction failed for {rec.relative_path}: {e}")

                # Copy file to data directory
                dest_path = dest_root / rec.relative_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(rec.source_path, dest_path)
                    summary.copied += 1
                except Exception as e:
                    summary.errors.append(f"File copy failed for {rec.relative_path}: {e}")
                    continue

                storage_path = f"local://{tenant_id}/{rec.relative_path}"

                # Insert UploadedFile
                now_iso = datetime.now(timezone.utc).isoformat()
                uploaded = UploadedFile(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    filename=rec.source_path.name,
                    mimetype=rec.mimetype,
                    size_bytes=rec.size_bytes,
                    extracted_text=extracted_text,
                    storage_path=storage_path,
                    metadata_={
                        "content_hash": rec.content_hash,
                        "source_path": rec.relative_path,
                        "source_type": rec.source_type,
                        "account_name": rec.account_name,
                        "account_id": account_id,
                        "imported_by": str(user_id),
                        "imported_at": now_iso,
                    },
                )
                session.add(uploaded)
                summary.inserted += 1

                status = rec.relative_path
                if account_id:
                    status += f" → account:{rec.account_name}"
                elif rec.account_name:
                    status += f" (no account match for '{rec.account_name}')"
                print(f"  {prefix} INSERT {status}")

            await session.commit()
            print(f"\nCommitted {summary.inserted} files.")

    finally:
        await engine.dispose()

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import company and market research files into Flywheel v2.",
        prog="python -m flywheel.import_research",
    )
    parser.add_argument("--tenant-id", required=True, help="Target tenant UUID")
    parser.add_argument("--user-id", required=True, help="User UUID for file ownership")
    parser.add_argument(
        "--companies-dir", type=Path,
        default=Path.home() / "claude-outputs" / "companies",
        help="Company research directory (default: ~/claude-outputs/companies/)",
    )
    parser.add_argument(
        "--research-dir", type=Path,
        default=Path.home() / "claude-outputs" / "research",
        help="Market research directory (default: ~/claude-outputs/research/)",
    )
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path(__file__).resolve().parent.parent.parent.parent / "data" / "uploads",
        help="Local storage root for file copies (default: backend/data/uploads/)",
    )
    parser.add_argument("--database-url", default=None, help="Async Postgres URL")
    parser.add_argument("--dry-run", action="store_true", help="Discover only, no DB writes or file copies")
    parser.add_argument("--verbose", action="store_true", help="Show skip details")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    companies_dir = args.companies_dir.expanduser() if args.companies_dir else None
    research_dir = args.research_dir.expanduser() if args.research_dir else None

    if companies_dir and not companies_dir.is_dir():
        print(f"Warning: companies dir does not exist: {companies_dir}", file=sys.stderr)
        companies_dir = None
    if research_dir and not research_dir.is_dir():
        print(f"Warning: research dir does not exist: {research_dir}", file=sys.stderr)
        research_dir = None

    if not companies_dir and not research_dir:
        print("Error: no valid source directories found.", file=sys.stderr)
        return 1

    db_url = args.database_url
    if db_url is None:
        if not args.dry_run:
            from flywheel.config import settings
            db_url = settings.database_url
        else:
            db_url = "postgresql+asyncpg://localhost/flywheel"

    summary = asyncio.run(
        import_research(
            companies_dir=companies_dir,
            research_dir=research_dir,
            data_dir=args.data_dir,
            tenant_id=args.tenant_id,
            user_id=args.user_id,
            database_url=db_url,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    )

    print(f"\nImport complete: {summary.inserted} inserted, {summary.skipped} skipped, {summary.copied} files copied")
    if summary.errors:
        print(f"Errors ({len(summary.errors)}):")
        for err in summary.errors:
            print(f"  - {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
