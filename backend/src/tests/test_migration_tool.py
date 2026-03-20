"""Tests for the v1 flat-file to Postgres migration tool.

Tests are organized into:
- TestParseV1File: Parsing v1 context files (no Postgres needed)
- TestDiscoverContextFiles: File discovery logic (no Postgres needed)
- TestMigrateFile: Postgres insertion with metadata preservation
- TestRoundTripFidelity: Parse -> insert -> read -> compare format
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select, text as sa_text

from flywheel.migration_tool import (
    MigrationResult,
    ParsedEntry,
    discover_context_files,
    migrate_file,
    migrate_all,
    parse_v1_file,
)

# ---------------------------------------------------------------------------
# Sample v1 content fixtures
# ---------------------------------------------------------------------------

SAMPLE_V1_BODY_META = """\
[2025-01-15 | source: ctx-meeting-prep | Quarterly review with Acme Corp]
- CEO mentioned expansion plans for Q2
- Budget approved for new tooling
- Follow-up meeting scheduled for February
- Evidence_count: 3
- Confidence: high

[2025-02-01 | source: ctx-company-enricher | Acme Corp company profile]
- Founded 2015, 50-100 employees
- Series B funded, $12M raised
- Confidence: medium
"""

SAMPLE_V1_INLINE_META = """\
[2025-01-15 | source: ctx-meeting-prep | Quarterly review with Acme Corp] confidence: high | evidence: 3
- CEO mentioned expansion plans for Q2
- Budget approved for new tooling
- Follow-up meeting scheduled for February

[2025-02-01 | source: ctx-company-enricher | Acme Corp company profile] confidence: medium | evidence: 1
- Founded 2015, 50-100 employees
- Series B funded, $12M raised
"""

SAMPLE_SINGLE_ENTRY = """\
[2025-03-10 | source: skill-research | Market analysis for FinTech]
- TAM estimated at $50B by 2027
- Key competitors: Stripe, Square, Adyen
- Confidence: high
- Evidence_count: 2
"""

SAMPLE_MALFORMED = """\
[2025-01-15 | source: ctx-meeting-prep | Valid entry]
- This entry is well-formed
- Confidence: high

This line is not an entry header and should be ignored

[invalid-date | source: bad | Bad date]
- Should fail to parse

[2025-03-01 | source: valid-source | Another valid entry]
- This one should parse fine
- Confidence: low
"""

SAMPLE_MULTILINE = """\
[2025-06-15 | source: ctx-notes | Detailed project notes]
- Line 1: Project kickoff scheduled for next Monday
- Line 2: Team consists of 5 engineers and 2 designers
- Line 3: Budget allocated: $150,000
- Line 4: Timeline: 6 months
- Line 5: Key risk: vendor dependency on CloudCorp
- Confidence: high
- Evidence_count: 4
"""

SAMPLE_SPECIAL_CHARS = """\
[2025-04-20 | source: ctx-intel | Company with pipes | and brackets [test]]
- Revenue: $10M | growing 30% YoY
- CEO said: "We're [definitely] expanding"
- Tech stack: Python | React | Postgres
- Confidence: medium
"""


@pytest.fixture
def tmp_context_root(tmp_path):
    """Create a temporary context root with sample files."""
    ctx = tmp_path / "context"
    ctx.mkdir()
    return ctx


@pytest.fixture
def populated_context_root(tmp_context_root):
    """Context root with several sample files."""
    # Regular context files
    (tmp_context_root / "contacts.md").write_text(SAMPLE_V1_BODY_META)
    (tmp_context_root / "company-intel.md").write_text(SAMPLE_V1_INLINE_META)
    (tmp_context_root / "notes.md").write_text(SAMPLE_SINGLE_ENTRY)

    # Excluded files
    (tmp_context_root / "_manifest.md").write_text("# Manifest\n")
    (tmp_context_root / "_events.jsonl").write_text("{}\n")

    # Dotfile (should be excluded)
    dot_dir = tmp_context_root / ".hidden"
    dot_dir.mkdir()
    (dot_dir / "secret.md").write_text("secret\n")

    return tmp_context_root


# ===========================================================================
# TestParseV1File
# ===========================================================================


class TestParseV1File:
    """Test v1 flat-file parsing logic."""

    def test_parse_single_entry(self, tmp_path):
        """One well-formed entry parses correctly."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_SINGLE_ENTRY)

        entries, errors = parse_v1_file(f)

        assert len(entries) == 1
        assert len(errors) == 0
        e = entries[0]
        assert e.date == "2025-03-10"
        assert e.source == "skill-research"
        assert e.detail == "Market analysis for FinTech"
        assert e.confidence == "high"
        assert e.evidence_count == 2
        assert len(e.content) == 2
        assert "TAM estimated at $50B by 2027" in e.content[0]
        assert "Key competitors: Stripe, Square, Adyen" in e.content[1]

    def test_parse_multiple_entries_body_meta(self, tmp_path):
        """Multiple entries with body-style metadata all parsed."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_V1_BODY_META)

        entries, errors = parse_v1_file(f)

        assert len(entries) == 2
        assert len(errors) == 0

        assert entries[0].date == "2025-01-15"
        assert entries[0].source == "ctx-meeting-prep"
        assert entries[0].confidence == "high"
        assert entries[0].evidence_count == 3
        assert len(entries[0].content) == 3

        assert entries[1].date == "2025-02-01"
        assert entries[1].source == "ctx-company-enricher"
        assert entries[1].confidence == "medium"
        assert entries[1].evidence_count == 1  # default

    def test_parse_multiple_entries_inline_meta(self, tmp_path):
        """Multiple entries with inline header metadata all parsed."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_V1_INLINE_META)

        entries, errors = parse_v1_file(f)

        assert len(entries) == 2
        assert entries[0].confidence == "high"
        assert entries[0].evidence_count == 3
        assert entries[1].confidence == "medium"
        assert entries[1].evidence_count == 1

    def test_parse_various_confidence_levels(self, tmp_path):
        """High, medium, low confidence levels all parsed."""
        content = """\
[2025-01-01 | source: s1 | high conf]
- data
- Confidence: high

[2025-01-02 | source: s2 | medium conf]
- data
- Confidence: medium

[2025-01-03 | source: s3 | low conf]
- data
- Confidence: low
"""
        f = tmp_path / "test.md"
        f.write_text(content)

        entries, errors = parse_v1_file(f)

        assert len(entries) == 3
        assert entries[0].confidence == "high"
        assert entries[1].confidence == "medium"
        assert entries[2].confidence == "low"

    def test_parse_multiline_content(self, tmp_path):
        """Entry with multiple content lines all captured."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_MULTILINE)

        entries, errors = parse_v1_file(f)

        assert len(entries) == 1
        e = entries[0]
        assert len(e.content) == 5  # 5 content lines, 2 metadata lines
        assert "Project kickoff" in e.content[0]
        assert "vendor dependency" in e.content[4]
        assert e.evidence_count == 4
        assert e.confidence == "high"

    def test_parse_malformed_entry(self, tmp_path):
        """Valid entries parsed, malformed headers silently skipped (no regex match)."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_MALFORMED)

        entries, errors = parse_v1_file(f)

        # Two valid entries should parse; [invalid-date | ...] doesn't match regex
        assert len(entries) == 2
        assert entries[0].detail == "Valid entry"
        assert entries[1].detail == "Another valid entry"

    def test_parse_invalid_date_format(self, tmp_path):
        """Entry with regex-matching but invalid date produces error."""
        # Date matches \d{4}-\d{2}-\d{2} but is not a real date
        content = """\
[9999-99-99 | source: bad | Invalid date]
- content
- Confidence: low
"""
        f = tmp_path / "test.md"
        f.write_text(content)

        entries, errors = parse_v1_file(f)
        assert len(entries) == 0
        assert len(errors) == 1
        assert "Invalid date" in errors[0].raw_text

    def test_parse_empty_file(self, tmp_path):
        """Empty file returns no entries and no errors."""
        f = tmp_path / "test.md"
        f.write_text("")

        entries, errors = parse_v1_file(f)
        assert entries == []
        assert errors == []

    def test_parse_special_characters(self, tmp_path):
        """Entries with pipes, brackets, quotes in content survive."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_SPECIAL_CHARS)

        entries, errors = parse_v1_file(f)

        assert len(entries) == 1
        e = entries[0]
        # Content should include the special chars
        assert any("|" in line for line in e.content)
        assert any("[" in line for line in e.content)


# ===========================================================================
# TestDiscoverContextFiles
# ===========================================================================


class TestDiscoverContextFiles:
    """Test context file discovery."""

    def test_discover_md_files(self, populated_context_root):
        """Finds .md files in context root."""
        files = discover_context_files(populated_context_root)
        names = [n for _, n in files]

        assert "contacts" in names
        assert "company-intel" in names
        assert "notes" in names

    def test_discover_excludes_manifest(self, populated_context_root):
        """_manifest.md excluded from discovery."""
        files = discover_context_files(populated_context_root)
        names = [n for _, n in files]

        assert "_manifest" not in names
        assert "_manifest.md" not in names

    def test_discover_excludes_events(self, populated_context_root):
        """_events.jsonl excluded (not .md anyway, but verify)."""
        files = discover_context_files(populated_context_root)
        paths = [str(p) for p, _ in files]

        assert not any("_events.jsonl" in p for p in paths)

    def test_discover_excludes_dotfiles(self, populated_context_root):
        """Dotfiles/dotdirs excluded from discovery."""
        files = discover_context_files(populated_context_root)
        names = [n for _, n in files]

        assert not any(".hidden" in n for n in names)

    def test_discover_nonexistent_root(self, tmp_path):
        """Non-existent root returns empty list."""
        files = discover_context_files(tmp_path / "nonexistent")
        assert files == []


# ===========================================================================
# TestMigrateFile (requires Postgres)
# ===========================================================================


@pytest.mark.postgres
@pytest.mark.asyncio
class TestMigrateFile:
    """Test file migration to Postgres."""

    async def test_migrate_basic_file(
        self, tmp_path, admin_session, tenant_ids, user_ids
    ):
        """Entries inserted into context_entries with correct fields."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_V1_BODY_META)

        result = await migrate_file(
            admin_session, f, "test-contacts",
            tenant_ids["a"], user_ids["a"],
        )

        assert result.entries_found == 2
        assert result.entries_inserted == 2
        assert result.skipped is False
        assert len(result.errors) == 0

        # Verify rows in DB
        from flywheel.db.models import ContextEntry
        stmt = select(func.count()).select_from(ContextEntry).where(
            ContextEntry.file_name == "test-contacts",
            ContextEntry.tenant_id == tenant_ids["a"],
        )
        count = (await admin_session.execute(stmt)).scalar()
        assert count == 2

    async def test_migrate_preserves_metadata(
        self, tmp_path, admin_session, tenant_ids, user_ids
    ):
        """Date, source, detail, confidence, evidence_count all match original."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_V1_BODY_META)

        await migrate_file(
            admin_session, f, "preserve-test",
            tenant_ids["a"], user_ids["a"],
        )

        from flywheel.db.models import ContextEntry
        stmt = (
            select(ContextEntry)
            .where(ContextEntry.file_name == "preserve-test")
            .order_by(ContextEntry.date.asc())
        )
        rows = (await admin_session.execute(stmt)).scalars().all()

        assert len(rows) == 2

        # First entry
        assert rows[0].date == date(2025, 1, 15)
        assert rows[0].source == "ctx-meeting-prep"
        assert rows[0].detail == "Quarterly review with Acme Corp"
        assert rows[0].confidence == "high"
        assert rows[0].evidence_count == 3

        # Second entry
        assert rows[1].date == date(2025, 2, 1)
        assert rows[1].source == "ctx-company-enricher"
        assert rows[1].confidence == "medium"
        assert rows[1].evidence_count == 1

    async def test_migrate_dry_run(
        self, tmp_path, admin_session, tenant_ids, user_ids
    ):
        """No rows inserted in dry-run mode."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_V1_BODY_META)

        result = await migrate_file(
            admin_session, f, "dry-run-test",
            tenant_ids["a"], user_ids["a"],
            dry_run=True,
        )

        assert result.entries_found == 2
        assert result.entries_inserted == 0

        # Verify nothing in DB
        from flywheel.db.models import ContextEntry
        stmt = select(func.count()).select_from(ContextEntry).where(
            ContextEntry.file_name == "dry-run-test",
        )
        count = (await admin_session.execute(stmt)).scalar()
        assert count == 0

    async def test_migrate_idempotent(
        self, tmp_path, admin_session, tenant_ids, user_ids
    ):
        """Second run skips already-migrated file."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_SINGLE_ENTRY)

        # First migration
        r1 = await migrate_file(
            admin_session, f, "idempotent-test",
            tenant_ids["a"], user_ids["a"],
        )
        await admin_session.flush()
        assert r1.entries_inserted == 1

        # Second migration -- should skip
        r2 = await migrate_file(
            admin_session, f, "idempotent-test",
            tenant_ids["a"], user_ids["a"],
        )
        assert r2.skipped is True
        assert r2.entries_inserted == 0

        # Verify only 1 entry exists
        from flywheel.db.models import ContextEntry
        stmt = select(func.count()).select_from(ContextEntry).where(
            ContextEntry.file_name == "idempotent-test",
        )
        count = (await admin_session.execute(stmt)).scalar()
        assert count == 1

    async def test_migrate_force_remigrate(
        self, tmp_path, admin_session, tenant_ids, user_ids
    ):
        """--force deletes and re-inserts entries."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_SINGLE_ENTRY)

        # First migration
        r1 = await migrate_file(
            admin_session, f, "force-test",
            tenant_ids["a"], user_ids["a"],
        )
        await admin_session.flush()
        assert r1.entries_inserted == 1

        # Force re-migrate
        r2 = await migrate_file(
            admin_session, f, "force-test",
            tenant_ids["a"], user_ids["a"],
            force=True,
        )
        assert r2.skipped is False
        assert r2.entries_inserted == 1

        # Still only 1 entry (old deleted, new inserted)
        from flywheel.db.models import ContextEntry
        stmt = select(func.count()).select_from(ContextEntry).where(
            ContextEntry.file_name == "force-test",
            ContextEntry.tenant_id == tenant_ids["a"],
        )
        count = (await admin_session.execute(stmt)).scalar()
        assert count == 1


# ===========================================================================
# TestRoundTripFidelity (requires Postgres)
# ===========================================================================


@pytest.mark.postgres
@pytest.mark.asyncio
class TestRoundTripFidelity:
    """Verify parse -> insert -> read_context produces output matching v1 format."""

    async def test_round_trip_single_file(
        self, tmp_path, admin_session, tenant_a_session, tenant_ids, user_ids
    ):
        """Migrate file -> read_context -> compare format matches original."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_V1_BODY_META)

        await migrate_file(
            admin_session, f, "rt-single",
            tenant_ids["a"], user_ids["a"],
        )
        await admin_session.commit()

        # Read back through storage API
        from flywheel.storage import read_context
        readback = await read_context(tenant_a_session, "rt-single")

        # Verify structure: should have entry headers
        assert "[2025-01-15 | source: ctx-meeting-prep" in readback
        assert "[2025-02-01 | source: ctx-company-enricher" in readback
        assert "confidence: high" in readback
        assert "evidence: 3" in readback
        assert "CEO mentioned expansion plans" in readback
        assert "Founded 2015" in readback

    async def test_round_trip_with_various_entries(
        self, tmp_path, admin_session, tenant_a_session, tenant_ids, user_ids
    ):
        """Different confidence levels, evidence counts, multi-line content survive."""
        content = """\
[2025-01-01 | source: s1 | High confidence item]
- Critical data point
- Confidence: high
- Evidence_count: 5

[2025-02-15 | source: s2 | Low confidence item]
- Unverified claim
- More context needed
- Confidence: low

[2025-03-30 | source: s3 | Medium with many lines]
- Line A
- Line B
- Line C
- Line D
- Confidence: medium
- Evidence_count: 2
"""
        f = tmp_path / "test.md"
        f.write_text(content)

        await migrate_file(
            admin_session, f, "rt-various",
            tenant_ids["a"], user_ids["a"],
        )
        await admin_session.commit()

        from flywheel.storage import read_context
        readback = await read_context(tenant_a_session, "rt-various")

        # All three entries present
        assert "High confidence item" in readback
        assert "Low confidence item" in readback
        assert "Medium with many lines" in readback

        # Confidence and evidence preserved
        assert "confidence: high" in readback
        assert "evidence: 5" in readback
        assert "confidence: low" in readback
        assert "confidence: medium" in readback
        assert "evidence: 2" in readback

        # Content lines preserved
        assert "Critical data point" in readback
        assert "Line A" in readback
        assert "Line D" in readback

    async def test_round_trip_special_characters(
        self, tmp_path, admin_session, tenant_a_session, tenant_ids, user_ids
    ):
        """Entries with pipes, brackets, special chars in content survive."""
        f = tmp_path / "test.md"
        f.write_text(SAMPLE_SPECIAL_CHARS)

        await migrate_file(
            admin_session, f, "rt-special",
            tenant_ids["a"], user_ids["a"],
        )
        await admin_session.commit()

        from flywheel.storage import read_context
        readback = await read_context(tenant_a_session, "rt-special")

        # Special characters in content should survive
        assert "$10M" in readback
        assert "30% YoY" in readback
        assert "[definitely]" in readback
