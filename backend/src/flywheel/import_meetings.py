"""Import meeting archive files into Flywheel v2.

Parses markdown meeting notes from ~/.claude/context/meeting-archive/
and inserts them as Meeting rows. Handles three source formats:

  Format A (YAML frontmatter with inline company):
    ---
    meeting_id: meeting-YYYY-MM-DD-slug
    date: YYYY-MM-DD
    type: customer
    attendees: Name1, Name2, Name3 (Company)
    source: granola
    ---

  Format B (YAML frontmatter with organization field):
    ---
    meeting_id: meeting-YYYY-MM-DD-slug
    type: Discovery Call
    date: YYYY-MM-DD
    attendees: Name1, Name2
    organization: CompanyName, email@company.com
    source: granola
    processed: YYYY-MM-DD
    ---

  Format C (bold markdown headers, no YAML frontmatter):
    # Title
    **Date:** YYYY-MM-DD
    **Type:** advisor
    **Attendees:** Name1, Name2, Name3 (email)
    **Meeting ID:** meeting-YYYY-MM-DD-slug

Dedup: (tenant_id, provider="archive", external_id) via existing unique index.
Account linking: matches company names against Account.normalized_name.

Usage:
    python -m flywheel.import_meetings \\
        --tenant-id <uuid> --user-id <uuid> \\
        [--archive-dir ~/.claude/context/meeting-archive/] \\
        [--dry-run] [--verbose]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flywheel.db.models import Meeting, PipelineEntry
from flywheel.utils.normalize import normalize_company_name

logger = logging.getLogger("flywheel.import_meetings")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ParsedMeeting:
    """A parsed meeting from a markdown file."""
    source_file: str
    external_id: str
    title: str
    meeting_date: datetime
    meeting_type: str
    attendees: list[dict]
    company_name: str | None
    body: str
    original_meeting_id: str | None = None


@dataclass
class ImportSummary:
    inserted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_YAML_FENCE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_BOLD_FIELD = re.compile(r"-?\s*\*\*(\w[\w\s]*):\*\*\s*(.*)")
# Pipe-separated inline format: **Date:** 2026-02-05 | **Type:** customer | **ID:** abc123
_PIPE_FIELDS = re.compile(r"\*\*(\w[\w\s]*):\*\*\s*([^|]+)")
_COMPANY_PAREN = re.compile(r"\(([^)]+)\)\s*$")
_EMAIL_PAREN = re.compile(r"\(([^)]*@[^)]+)\)")
# Parenthetical notes that are NOT company names
_NOT_COMPANY = {
    "solo note", "did not join", "no-show", "invited, did not join",
    "no show", "cancelled", "rescheduled",
}
# Pattern to extract company from H1 title like "Company x Lumif.ai" or "Company <> Lumif.ai"
_TITLE_COMPANY = re.compile(r"^#\s*(.+?)(?:\s*(?:x|<>|vs\.?|—|-)\s*lumif)", re.IGNORECASE)


def _parse_attendee_string(raw: str, organization: str | None = None) -> tuple[list[dict], str | None]:
    """Parse attendee string into structured list + extract company name.

    Returns (attendees_list, company_name).
    """
    attendees = []
    company_name = None

    # Check for company in parentheses at end of attendee string
    # e.g., "Name1, Name2, Name3 (Satguru Travel)"
    company_match = _COMPANY_PAREN.search(raw)
    if company_match:
        candidate = company_match.group(1).strip()
        # Only treat as company if it's not an email and not a note
        if "@" not in candidate and candidate.lower() not in _NOT_COMPANY:
            company_name = candidate
            raw = raw[:company_match.start()].strip().rstrip(",")

    # Split attendees
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue

        # Extract email if present: "Name (email@co.com)"
        email = None
        email_match = _EMAIL_PAREN.search(part)
        if email_match:
            email = email_match.group(1).strip()
            part = part[:email_match.start()].strip()

        attendees.append({
            "name": part,
            **({"email": email} if email else {}),
        })

    # Organization field overrides company detection
    if organization:
        # "CompanyName, email@company.com" or "Murphy Resources CEO, chorney@..."
        org_parts = [p.strip() for p in organization.split(",")]
        org_name = org_parts[0]
        # Strip common title suffixes from org name
        for suffix in (" CEO", " CTO", " COO", " CFO", " CIO", " VP", " Director"):
            if org_name.endswith(suffix):
                org_name = org_name[:-len(suffix)].strip()
                break
        company_name = org_name
        # If there's an email in the org field, attach to first non-team attendee
        if len(org_parts) > 1 and "@" in org_parts[1]:
            org_email = org_parts[1]
            for att in attendees:
                if "email" not in att and att["name"] != "Sharan JM":
                    att["email"] = org_email
                    break

    return attendees, company_name


def _extract_h1(body: str) -> str | None:
    """Extract first H1 heading from markdown body."""
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return None


def parse_meeting_file(file_path: Path) -> ParsedMeeting | None:
    """Parse a single meeting archive file. Returns None on parse failure."""
    content = file_path.read_text(encoding="utf-8")
    filename = file_path.name
    stem = file_path.stem

    # Try YAML frontmatter first
    yaml_match = _YAML_FENCE.match(content)
    if yaml_match:
        try:
            fm = yaml.safe_load(yaml_match.group(1))
        except yaml.YAMLError:
            fm = None

        if fm and isinstance(fm, dict):
            body = content[yaml_match.end():]
            date_str = str(fm.get("date", ""))
            attendees_raw = fm.get("attendees", "")
            organization = fm.get("organization")
            attendees, company = _parse_attendee_string(attendees_raw, organization)

            # Title: from H1 or humanized filename
            title = _extract_h1(body) or stem.replace("-", " ").title()

            try:
                meeting_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                return None

            return ParsedMeeting(
                source_file=filename,
                external_id=f"archive:{stem}",
                title=title,
                meeting_date=meeting_date,
                meeting_type=fm.get("type", "external"),
                attendees=attendees,
                company_name=company,
                body=body.strip(),
                original_meeting_id=fm.get("meeting_id"),
            )

    # Fallback: bold markdown headers (Format C, D, E)
    lines = content.split("\n")
    fields: dict[str, str] = {}
    header_end = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Try pipe-separated inline: **Date:** X | **Type:** Y | **ID:** Z
        if "|" in stripped and "**" in stripped:
            for pm in _PIPE_FIELDS.finditer(stripped):
                fields[pm.group(1).strip().lower()] = pm.group(2).strip()
            header_end = i + 1
            continue
        # Try bold field: **Key:** value  or  - **Key:** value
        m = _BOLD_FIELD.match(stripped)
        if m:
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            # Handle "Participants" as "Attendees"
            if key == "participants":
                key = "attendees"
            fields[key] = val
            header_end = i + 1
        elif stripped.startswith("# "):
            fields["_title"] = stripped[2:].strip()
            header_end = i + 1
        elif stripped.startswith("## "):
            # Hit a section header — stop parsing metadata
            break

    if not fields.get("date") and not fields.get("id"):
        return None

    date_str = fields.get("date", "")
    try:
        meeting_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    attendees_raw = fields.get("attendees", "")
    attendees, company = _parse_attendee_string(attendees_raw)

    # For bold-format files, try to extract company from H1 title
    # e.g., "Satguru (SA Team) x Lumif.ai" → "Satguru (SA Team)"
    # Skip single-word matches (likely person names in advisor meetings)
    if not company and fields.get("_title"):
        title_match = _TITLE_COMPANY.match("# " + fields["_title"])
        if title_match:
            candidate = title_match.group(1).strip()
            if " " in candidate:  # at least 2 words = likely a company
                company = candidate

    body = "\n".join(lines[header_end:]).strip()
    title = fields.get("_title") or stem.replace("-", " ").title()

    return ParsedMeeting(
        source_file=filename,
        external_id=f"archive:{stem}",
        title=title,
        meeting_date=meeting_date,
        meeting_type=fields.get("type", "external"),
        attendees=attendees,
        company_name=company,
        body=body,
        original_meeting_id=fields.get("meeting id") or fields.get("id"),
    )


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

async def _find_account_id(
    session: AsyncSession, tenant_id: str, company_name: str | None
) -> str | None:
    """Match company name to an existing PipelineEntry. Returns pipeline_entry id or None."""
    if not company_name:
        return None
    normalized = normalize_company_name(company_name)
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


async def import_meetings(
    archive_dir: Path,
    tenant_id: str,
    user_id: str,
    database_url: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> ImportSummary:
    """Import all meeting archive files for a tenant."""
    summary = ImportSummary()

    files = sorted(archive_dir.glob("*.md"))
    if not files:
        logger.warning("No .md files found in %s", archive_dir)
        return summary

    total = len(files)
    print(f"Found {total} meeting files in {archive_dir}")

    # Parse all files first
    meetings: list[ParsedMeeting] = []
    for f in files:
        parsed = parse_meeting_file(f)
        if parsed:
            meetings.append(parsed)
        else:
            summary.errors.append(f"Failed to parse: {f.name}")

    print(f"Parsed {len(meetings)} meetings ({len(summary.errors)} parse errors)")

    if dry_run:
        for m in meetings:
            print(f"  [DRY-RUN] {m.source_file} → {m.title} ({m.meeting_type}) company={m.company_name}")
        return summary

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            for i, m in enumerate(meetings, 1):
                # Dedup check
                result = await session.execute(
                    select(Meeting.id).where(
                        Meeting.tenant_id == tenant_id,
                        Meeting.provider == "archive",
                        Meeting.external_id == m.external_id,
                    )
                )
                if result.scalar_one_or_none():
                    summary.skipped += 1
                    if verbose:
                        print(f"  [{i}/{total}] SKIP {m.source_file} (already exists)")
                    continue

                # Pipeline entry linking
                pipeline_entry_id = await _find_account_id(session, tenant_id, m.company_name)

                # Meeting model has no metadata_ column — store provenance in description
                provenance = f"Imported from {m.source_file}"
                if m.original_meeting_id:
                    provenance += f" (original_id: {m.original_meeting_id})"

                meeting = Meeting(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    provider="archive",
                    external_id=m.external_id,
                    title=m.title,
                    meeting_date=m.meeting_date,
                    attendees=m.attendees,
                    meeting_type=m.meeting_type,
                    ai_summary=m.body,
                    pipeline_entry_id=pipeline_entry_id,
                    processing_status="complete",
                    description=provenance,
                )
                session.add(meeting)
                summary.inserted += 1

                status = f"→ {m.title}"
                if pipeline_entry_id:
                    status += f" (account: {m.company_name})"
                else:
                    status += " (no account match)"
                print(f"  [{i}/{total}] INSERT {m.source_file} {status}")

            await session.commit()
            print(f"\nCommitted {summary.inserted} meetings.")

    finally:
        await engine.dispose()

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import meeting archive files into Flywheel v2.",
        prog="python -m flywheel.import_meetings",
    )
    parser.add_argument("--tenant-id", required=True, help="Target tenant UUID")
    parser.add_argument("--user-id", required=True, help="User UUID for meeting ownership")
    parser.add_argument(
        "--archive-dir", type=Path,
        default=Path.home() / ".claude" / "context" / "meeting-archive",
        help="Meeting archive directory (default: ~/.claude/context/meeting-archive/)",
    )
    parser.add_argument("--database-url", default=None, help="Async Postgres URL")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no DB writes")
    parser.add_argument("--verbose", action="store_true", help="Show skip details")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.archive_dir.is_dir():
        print(f"Error: archive dir does not exist: {args.archive_dir}", file=sys.stderr)
        return 1

    db_url = args.database_url
    if db_url is None:
        if not args.dry_run:
            from flywheel.config import settings
            db_url = settings.database_url
        else:
            db_url = "postgresql+asyncpg://localhost/flywheel"

    summary = asyncio.run(
        import_meetings(
            archive_dir=args.archive_dir,
            tenant_id=args.tenant_id,
            user_id=args.user_id,
            database_url=db_url,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    )

    print(f"\nImport complete: {summary.inserted} inserted, {summary.skipped} skipped")
    if summary.errors:
        print(f"Errors ({len(summary.errors)}):")
        for err in summary.errors:
            print(f"  - {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
