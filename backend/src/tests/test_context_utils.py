"""
Comprehensive test suite for context_utils.

Covers: unit tests for all public functions, concurrent access,
edge cases, and round-trip parse/serialize tests.
"""

import os
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# Add src/ to path so `import context_utils` resolves to the compatibility shim
# This is needed both here and in multiprocessing subprocesses
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import context_utils
from context_utils import (
    BatchOperation,
    ContextEntry,
    ContractViolation,
    FileHeader,
    ValidationResult,
    acquire_lock,
    append_entry,
    atomic_write,
    backup_manifest,
    batch_context,
    check_read_allowed,
    check_write_allowed,
    format_entry,
    increment_evidence_in_content,
    load_agent_contract,
    log_event,
    normalize_source_key,
    parse_context_file,
    parse_file_header,
    parse_manifest,
    query_context,
    read_context,
    release_lock,
    safe_read,
    serialize_entries,
    serialize_manifest,
    should_increment_evidence,
    update_manifest,
    validate_entry_format,
)


class _TempRootMixin:
    """Mixin that sets CONTEXT_ROOT to a temp directory for test isolation."""

    def setUp(self):
        self._orig_root = context_utils.CONTEXT_ROOT
        self._orig_strict = context_utils.STRICT_MODE
        self._tmpdir = tempfile.mkdtemp(prefix="ctx_test_")
        context_utils.CONTEXT_ROOT = Path(self._tmpdir)
        context_utils.STRICT_MODE = False

    def tearDown(self):
        context_utils.CONTEXT_ROOT = self._orig_root
        context_utils.STRICT_MODE = self._orig_strict
        shutil.rmtree(self._tmpdir, ignore_errors=True)


# =========================================================================
# TestContextEntry
# =========================================================================


class TestContextEntry(unittest.TestCase):
    """Test ContextEntry dataclass defaults and all-fields construction."""

    def test_dataclass_defaults(self):
        entry = ContextEntry(
            date=datetime(2026, 3, 9),
            source="test-source",
            detail="",
        )
        self.assertEqual(entry.evidence_count, 1)
        self.assertEqual(entry.confidence, "low")
        self.assertEqual(entry.content, [])
        self.assertIsNone(entry.last_validated)
        self.assertIsNone(entry.supersedes)
        self.assertIsNone(entry.effectiveness_score)

    def test_dataclass_all_fields(self):
        entry = ContextEntry(
            date=datetime(2026, 3, 9),
            source="meeting-processor",
            detail="call: John Smith @ ABC Corp",
            content=["Finding 1", "Finding 2"],
            evidence_count=3,
            confidence="high",
            last_validated=datetime(2026, 3, 9),
            supersedes="older-entry-ref",
            effectiveness_score=0.85,
        )
        self.assertEqual(entry.source, "meeting-processor")
        self.assertEqual(entry.detail, "call: John Smith @ ABC Corp")
        self.assertEqual(len(entry.content), 2)
        self.assertEqual(entry.evidence_count, 3)
        self.assertEqual(entry.confidence, "high")
        self.assertEqual(entry.last_validated, datetime(2026, 3, 9))
        self.assertEqual(entry.supersedes, "older-entry-ref")
        self.assertAlmostEqual(entry.effectiveness_score, 0.85)


# =========================================================================
# TestValidation
# =========================================================================


class TestValidation(unittest.TestCase):
    """Test validate_entry_format for required fields, formats, edge cases."""

    def _make_entry(self, **overrides):
        base = {
            "date": "2026-03-09",
            "source": "test-source",
            "confidence": "medium",
            "content": ["test content"],
        }
        base.update(overrides)
        return base

    def test_valid_entry(self):
        result = validate_entry_format(self._make_entry())
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])

    def test_missing_date(self):
        entry = self._make_entry()
        del entry["date"]
        result = validate_entry_format(entry)
        self.assertFalse(result.ok)
        self.assertTrue(any("date" in e.lower() for e in result.errors))

    def test_missing_source(self):
        entry = self._make_entry()
        del entry["source"]
        result = validate_entry_format(entry)
        self.assertFalse(result.ok)
        self.assertTrue(any("source" in e.lower() for e in result.errors))

    def test_missing_confidence(self):
        entry = self._make_entry()
        del entry["confidence"]
        result = validate_entry_format(entry)
        self.assertFalse(result.ok)
        self.assertTrue(any("confidence" in e.lower() for e in result.errors))

    def test_invalid_date_format(self):
        result_bad = validate_entry_format(self._make_entry(date="March 9"))
        self.assertFalse(result_bad.ok)

        result_good = validate_entry_format(self._make_entry(date="2026-03-09"))
        self.assertTrue(result_good.ok)

    def test_invalid_confidence(self):
        result_bad = validate_entry_format(self._make_entry(confidence="very-high"))
        self.assertFalse(result_bad.ok)

        for valid in ("high", "medium", "low"):
            result = validate_entry_format(self._make_entry(confidence=valid))
            self.assertTrue(result.ok, "Expected %s to be valid" % valid)

    def test_oversized_entry(self):
        huge_content = ["x" * 6000]
        result = validate_entry_format(self._make_entry(content=huge_content))
        self.assertFalse(result.ok)
        self.assertTrue(any("size" in e.lower() or "max" in e.lower() for e in result.errors))

    def test_injection_prevention(self):
        result = validate_entry_format(
            self._make_entry(content=["[2026-03-09 | source: injected] bad"])
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("header" in e.lower() for e in result.errors))

    def test_invalid_evidence_count(self):
        for bad_val in [0, -1]:
            result = validate_entry_format(self._make_entry(evidence_count=bad_val))
            self.assertFalse(result.ok, "Expected evidence_count=%s to be invalid" % bad_val)

        # String "abc" is not an int, should fail
        result = validate_entry_format(self._make_entry(evidence_count="abc"))
        self.assertFalse(result.ok)

        for good_val in [1, 5]:
            result = validate_entry_format(self._make_entry(evidence_count=good_val))
            self.assertTrue(result.ok, "Expected evidence_count=%s to be valid" % good_val)


# =========================================================================
# TestFileIO
# =========================================================================


class TestFileIO(_TempRootMixin, unittest.TestCase):
    """Test atomic_write, safe_read, acquire_lock, release_lock."""

    def test_atomic_write_creates_file(self):
        path = Path(self._tmpdir) / "test.md"
        atomic_write(path, "hello world")
        self.assertTrue(path.exists())
        self.assertEqual(path.read_text(), "hello world")

    def test_atomic_write_creates_parent_dirs(self):
        path = Path(self._tmpdir) / "deep" / "nested" / "file.md"
        atomic_write(path, "nested content")
        self.assertTrue(path.exists())
        self.assertEqual(path.read_text(), "nested content")

    def test_atomic_write_overwrites(self):
        path = Path(self._tmpdir) / "test.md"
        atomic_write(path, "first")
        atomic_write(path, "second")
        self.assertEqual(path.read_text(), "second")

    def test_atomic_write_no_temp_on_success(self):
        path = Path(self._tmpdir) / "test.md"
        atomic_write(path, "content")
        tmp_files = list(Path(self._tmpdir).glob("*.tmp"))
        self.assertEqual(len(tmp_files), 0)

    def test_safe_read_existing(self):
        path = Path(self._tmpdir) / "existing.md"
        path.write_text("known content", encoding="utf-8")
        self.assertEqual(safe_read(path), "known content")

    def test_safe_read_nonexistent(self):
        path = Path(self._tmpdir) / "nope.md"
        self.assertEqual(safe_read(path), "")

    def test_acquire_release_lock(self):
        path = Path(self._tmpdir) / "locktest.md"
        path.write_text("", encoding="utf-8")
        fd = acquire_lock(path)
        try:
            self.assertIsInstance(fd, int)
        finally:
            release_lock(fd)

    def test_lock_timeout(self):
        path = Path(self._tmpdir) / "locktest2.md"
        path.write_text("", encoding="utf-8")
        fd1 = acquire_lock(path)
        try:
            with self.assertRaises(TimeoutError):
                acquire_lock(path, timeout=0.2)
        finally:
            release_lock(fd1)


# =========================================================================
# TestParsing
# =========================================================================


class TestParsing(unittest.TestCase):
    """Test parse_context_file and serialize_entries."""

    SAMPLE_ENTRY_TEXT = (
        "[2026-03-09 | source: meeting-processor | call: John Smith @ ABC Corp]\n"
        "- Key finding about the market\n"
        "- Evidence: \"direct quote\"\n"
        "- Evidence_count: 3\n"
        "- Confidence: high\n"
        "- Last_validated: 2026-03-09\n"
        "- Supersedes: older-ref\n"
        "- Effectiveness_score: 0.85\n"
    )

    SAMPLE_FILE = (
        "# Test Context\n"
        "_owner: test-agent_\n"
        "_last_updated: 2026-03-09_\n"
        "_updated_by: test-agent_\n"
        "_entry_cap: 50_\n\n"
    )

    def test_parse_single_entry(self):
        entries = parse_context_file(self.SAMPLE_ENTRY_TEXT)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e.date, datetime(2026, 3, 9))
        self.assertEqual(e.source, "meeting-processor")
        self.assertEqual(e.detail, "call: John Smith @ ABC Corp")
        self.assertEqual(e.evidence_count, 3)
        self.assertEqual(e.confidence, "high")
        self.assertEqual(e.last_validated, datetime(2026, 3, 9))
        self.assertEqual(e.supersedes, "older-ref")
        self.assertAlmostEqual(e.effectiveness_score, 0.85)

    def test_parse_multiple_entries(self):
        content = self.SAMPLE_FILE
        for i in range(3):
            content += (
                "\n[2026-03-0%d | source: src%d]\n"
                "- Content %d\n"
                "- Confidence: medium\n" % (i + 1, i, i)
            )
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 3)
        # Verify order preserved
        self.assertEqual(entries[0].date, datetime(2026, 3, 1))
        self.assertEqual(entries[2].date, datetime(2026, 3, 3))

    def test_parse_file_header(self):
        header = parse_file_header(self.SAMPLE_FILE)
        self.assertEqual(header.owner, "test-agent")
        self.assertEqual(header.last_updated, "2026-03-09")
        self.assertEqual(header.updated_by, "test-agent")
        self.assertEqual(header.entry_cap, 50)

    def test_parse_empty_content(self):
        self.assertEqual(parse_context_file(""), [])
        self.assertEqual(parse_context_file("   "), [])

    def test_parse_no_entries(self):
        content = self.SAMPLE_FILE  # Header only, no entries
        entries = parse_context_file(content)
        self.assertEqual(entries, [])

    def test_parse_multiline_content(self):
        content = (
            "[2026-03-09 | source: test]\n"
            "- Line 1\n"
            "- Line 2\n"
            "- Line 3\n"
            "- Line 4\n"
            "- Line 5\n"
            "- Confidence: high\n"
        )
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 1)
        # 5 content lines (Confidence is metadata, not content)
        self.assertEqual(len(entries[0].content), 5)

    def test_serialize_single_entry(self):
        entry = ContextEntry(
            date=datetime(2026, 3, 9),
            source="meeting-processor",
            detail="call: John Smith",
            content=["Finding 1"],
            confidence="high",
        )
        text = serialize_entries([entry])
        self.assertIn("[2026-03-09 | source: meeting-processor | call: John Smith]", text)
        self.assertIn("- Finding 1", text)
        self.assertIn("- Confidence: high", text)

    def test_serialize_multiple_entries(self):
        entries = []
        for i in range(3):
            entries.append(ContextEntry(
                date=datetime(2026, 3, i + 1),
                source="src%d" % i,
                detail="",
                content=["Content %d" % i],
                confidence="medium",
            ))
        text = serialize_entries(entries)
        # All three entries present
        self.assertEqual(text.count("[2026-03-0"), 3)


# =========================================================================
# TestReadContext
# =========================================================================


class TestReadContext(_TempRootMixin, unittest.TestCase):
    """Test read_context public API."""

    def test_read_existing_file(self):
        file_path = context_utils.CONTEXT_ROOT / "test.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("seeded content", encoding="utf-8")
        result = read_context("test.md", "test-agent")
        self.assertEqual(result, "seeded content")

    def test_read_nonexistent_file(self):
        result = read_context("does-not-exist.md", "test-agent")
        self.assertEqual(result, "")

    def test_read_empty_file(self):
        file_path = context_utils.CONTEXT_ROOT / "empty.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("", encoding="utf-8")
        result = read_context("empty.md", "test-agent")
        self.assertEqual(result, "")


# =========================================================================
# TestAppendEntry
# =========================================================================


class TestAppendEntry(_TempRootMixin, unittest.TestCase):
    """Test append_entry public API."""

    def _make_entry(self, **overrides):
        base = {
            "date": "2026-03-09",
            "source": "test-source",
            "confidence": "medium",
            "content": ["test finding"],
        }
        base.update(overrides)
        return base

    def test_append_to_new_file(self):
        result = append_entry("new-file.md", self._make_entry(), "test-source", "test-agent")
        self.assertEqual(result, "OK")
        content = read_context("new-file.md", "test-agent")
        self.assertIn("[2026-03-09 | source: test-source]", content)
        # File header present
        self.assertIn("# new-file", content)

    def test_append_to_existing_file(self):
        append_entry("existing.md", self._make_entry(date="2026-03-08"), "test-source", "test-agent")
        append_entry("existing.md", self._make_entry(date="2026-03-09", detail="second"), "test-source", "test-agent")
        content = read_context("existing.md", "test-agent")
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 2)

    def test_append_creates_parent_dirs(self):
        result = append_entry(
            "nested/deep/path.md", self._make_entry(), "test-source", "test-agent"
        )
        self.assertEqual(result, "OK")
        file_path = context_utils.CONTEXT_ROOT / "nested" / "deep" / "path.md"
        self.assertTrue(file_path.exists())

    def test_append_rejects_invalid(self):
        bad_entry = {"content": ["no date or source"]}
        with self.assertRaises(ValueError):
            append_entry("fail.md", bad_entry, "test-source", "test-agent")

    def test_append_post_write_validates(self):
        result = append_entry("validated.md", self._make_entry(), "test-source", "test-agent")
        self.assertEqual(result, "OK")
        # Post-write: file should be parseable
        content = read_context("validated.md", "test-agent")
        entries = parse_context_file(content)
        self.assertGreaterEqual(len(entries), 1)

    def test_multiple_appends(self):
        for i in range(5):
            append_entry(
                "multi.md",
                self._make_entry(date="2026-03-0%d" % (i + 1), detail="entry%d" % i),
                "test-source",
                "test-agent",
            )
        content = read_context("multi.md", "test-agent")
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 5)


# =========================================================================
# TestQueryContext
# =========================================================================


class TestQueryContext(_TempRootMixin, unittest.TestCase):
    """Test query_context filtering."""

    def setUp(self):
        super().setUp()
        # Seed file with entries
        for i, (date, src, conf, kw) in enumerate([
            ("2026-03-01", "alpha", "low", "market research"),
            ("2026-03-05", "beta", "medium", "pricing data"),
            ("2026-03-09", "alpha", "high", "customer feedback"),
        ]):
            append_entry(
                "query-test.md",
                {
                    "date": date,
                    "source": src,
                    "confidence": conf,
                    "content": [kw],
                    "detail": "entry%d" % i,
                },
                src,
                "test-agent",
            )

    def test_query_no_filters(self):
        entries = query_context("query-test.md", "test-agent")
        self.assertEqual(len(entries), 3)

    def test_query_by_date(self):
        entries = query_context("query-test.md", "test-agent", since="2026-03-04")
        self.assertEqual(len(entries), 2)
        dates = [e.date for e in entries]
        self.assertTrue(all(d >= datetime(2026, 3, 4) for d in dates))

    def test_query_by_source(self):
        entries = query_context("query-test.md", "test-agent", source="alpha")
        self.assertEqual(len(entries), 2)

    def test_query_by_keyword(self):
        entries = query_context("query-test.md", "test-agent", keyword="pricing")
        self.assertEqual(len(entries), 1)
        self.assertIn("pricing data", entries[0].content)

    def test_query_by_confidence(self):
        entries = query_context("query-test.md", "test-agent", min_confidence="medium")
        self.assertEqual(len(entries), 2)
        for e in entries:
            self.assertIn(e.confidence, ("medium", "high"))

    def test_query_combined_filters(self):
        entries = query_context(
            "query-test.md", "test-agent",
            since="2026-03-04", min_confidence="medium", keyword="customer",
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].confidence, "high")

    def test_query_empty_file(self):
        entries = query_context("nonexistent.md", "test-agent")
        self.assertEqual(entries, [])


# =========================================================================
# TestBatchContext
# =========================================================================


class TestBatchContext(_TempRootMixin, unittest.TestCase):
    """Test batch_context and BatchOperation."""

    def _make_entry(self, date="2026-03-09", **overrides):
        base = {
            "date": date,
            "source": "batch-source",
            "confidence": "medium",
            "content": ["batch content"],
        }
        base.update(overrides)
        return base

    def test_batch_commit(self):
        with batch_context("batch-source", "test-agent") as batch:
            batch.append_entry("file-a.md", self._make_entry())
            batch.append_entry("file-b.md", self._make_entry(date="2026-03-10"))

        # Both files should exist
        self.assertTrue((context_utils.CONTEXT_ROOT / "file-a.md").exists())
        self.assertTrue((context_utils.CONTEXT_ROOT / "file-b.md").exists())
        entries_a = parse_context_file(read_context("file-a.md", "test-agent"))
        entries_b = parse_context_file(read_context("file-b.md", "test-agent"))
        self.assertEqual(len(entries_a), 1)
        self.assertEqual(len(entries_b), 1)

    def test_batch_rollback_on_invalid(self):
        with self.assertRaises(ValueError):
            with batch_context("batch-source", "test-agent") as batch:
                batch.append_entry("rollback.md", self._make_entry())
                batch.append_entry("rollback2.md", {"content": ["invalid, no date"]})

    def test_batch_empty(self):
        # Empty batch should not raise
        with batch_context("batch-source", "test-agent") as batch:
            pass
        # Nothing should have been written

    def test_batch_single_file(self):
        with batch_context("batch-source", "test-agent") as batch:
            batch.append_entry("single.md", self._make_entry())
        content = read_context("single.md", "test-agent")
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 1)

    def test_batch_same_file_rejected(self):
        """Batch with two entries for the same file raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            with batch_context("batch-source", "test-agent") as batch:
                batch.append_entry("contacts.md", self._make_entry())
                batch.append_entry("contacts.md", self._make_entry(date="2026-03-10"))
        self.assertIn("duplicate target files", str(ctx.exception))
        self.assertIn("contacts.md", str(ctx.exception))

    def test_batch_distinct_files_still_works(self):
        """Batch with different files continues to work after guard added."""
        with batch_context("batch-source", "test-agent") as batch:
            batch.append_entry("file-x.md", self._make_entry())
            batch.append_entry("file-y.md", self._make_entry(date="2026-03-10"))
            batch.append_entry("file-z.md", self._make_entry(date="2026-03-11"))
        self.assertTrue((context_utils.CONTEXT_ROOT / "file-x.md").exists())
        self.assertTrue((context_utils.CONTEXT_ROOT / "file-y.md").exists())
        self.assertTrue((context_utils.CONTEXT_ROOT / "file-z.md").exists())


# =========================================================================
# TestEvidenceDedup
# =========================================================================


class TestEvidenceDedup(_TempRootMixin, unittest.TestCase):
    """Test evidence deduplication via normalize_source_key."""

    def test_dedup_same_source_increments(self):
        entry = {
            "date": "2026-03-09",
            "source": "meeting-processor",
            "detail": "call: John Smith",
            "confidence": "medium",
            "content": ["finding 1"],
        }
        append_entry("dedup.md", entry, "meeting-processor", "test-agent")
        result = append_entry("dedup.md", entry, "meeting-processor", "test-agent")
        self.assertEqual(result, "DEDUP")
        content = read_context("dedup.md", "test-agent")
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 1)
        self.assertGreaterEqual(entries[0].evidence_count, 2)

    def test_dedup_different_source_appends(self):
        entry1 = {
            "date": "2026-03-09",
            "source": "src-a",
            "confidence": "medium",
            "content": ["finding 1"],
        }
        entry2 = {
            "date": "2026-03-09",
            "source": "src-b",
            "confidence": "medium",
            "content": ["finding 2"],
        }
        append_entry("dedup2.md", entry1, "src-a", "test-agent")
        result = append_entry("dedup2.md", entry2, "src-b", "test-agent")
        self.assertEqual(result, "OK")
        content = read_context("dedup2.md", "test-agent")
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 2)

    def test_normalize_source_key_case(self):
        k1 = normalize_source_key("Meeting Processor", "John Smith", "2026-03-09")
        k2 = normalize_source_key("meeting processor", "john smith", "2026-03-09")
        self.assertEqual(k1, k2)

    def test_normalize_source_key_whitespace(self):
        # Leading/trailing whitespace stripped, spaces become hyphens
        k1 = normalize_source_key(" meeting processor ", " John Smith ", "2026-03-09")
        k2 = normalize_source_key("meeting processor", "John Smith", "2026-03-09")
        self.assertEqual(k1, k2)
        # Hyphens and single spaces produce same result
        k3 = normalize_source_key("meeting-processor", "John-Smith", "2026-03-09")
        k4 = normalize_source_key("meeting processor", "John Smith", "2026-03-09")
        self.assertEqual(k3, k4)


# =========================================================================
# TestManifest
# =========================================================================


class TestManifest(_TempRootMixin, unittest.TestCase):
    """Test manifest creation, update, backup, and round-trip."""

    def test_manifest_created_on_first_write(self):
        append_entry(
            "mtest.md",
            {"date": "2026-03-09", "source": "test", "confidence": "low", "content": ["x"]},
            "test-source",
            "test-agent",
        )
        manifest_path = context_utils.CONTEXT_ROOT / "_manifest.md"
        self.assertTrue(manifest_path.exists())

    def test_manifest_updated_on_write(self):
        append_entry(
            "mtest2.md",
            {"date": "2026-03-09", "source": "test", "confidence": "low", "content": ["x"]},
            "test-source",
            "test-agent",
        )
        content = safe_read(context_utils.CONTEXT_ROOT / "_manifest.md")
        self.assertIn("mtest2.md", content)

    def test_manifest_backup_on_write(self):
        append_entry(
            "mtest3.md",
            {"date": "2026-03-09", "source": "test", "confidence": "low", "content": ["x"]},
            "test-source",
            "test-agent",
        )
        bak_path = context_utils.CONTEXT_ROOT / "_manifest.md.bak"
        self.assertTrue(bak_path.exists())

    def test_manifest_daily_snapshot(self):
        append_entry(
            "mtest4.md",
            {"date": "2026-03-09", "source": "test", "confidence": "low", "content": ["x"]},
            "test-source",
            "test-agent",
        )
        snapshot_dir = context_utils.CONTEXT_ROOT / "_backups" / "manifest-snapshots"
        snapshots = list(snapshot_dir.glob("*.md"))
        self.assertGreaterEqual(len(snapshots), 1)

    def test_manifest_parse_serialize_roundtrip(self):
        manifest = {
            "schema_version": 1,
            "registry": {
                "file-a.md": {
                    "updated": "2026-03-09 12:00:00",
                    "updated_by": "agent-a",
                    "operation": "write",
                },
                "file-b.md": {
                    "updated": "2026-03-09 13:00:00",
                    "updated_by": "agent-b",
                    "operation": "batch_committed",
                },
            },
        }
        serialized = serialize_manifest(manifest)
        parsed = parse_manifest(serialized)
        self.assertEqual(parsed["schema_version"], 1)
        self.assertIn("file-a.md", parsed["registry"])
        self.assertIn("file-b.md", parsed["registry"])
        self.assertEqual(parsed["registry"]["file-a.md"]["updated_by"], "agent-a")


# =========================================================================
# TestContractEnforcement
# =========================================================================


class TestContractEnforcement(_TempRootMixin, unittest.TestCase):
    """Test contract enforcement in dev and strict modes."""

    def test_dev_mode_allows_all(self):
        context_utils.STRICT_MODE = False
        # Should not raise
        check_read_allowed("any-file.md", "unknown-agent")
        check_write_allowed("any-file.md", "unknown-agent")

    def test_strict_mode_blocks_undeclared(self):
        context_utils.STRICT_MODE = True
        # Create a SKILL.md with restricted access
        skill_dir = Path.home() / ".claude" / "skills" / "restricted-agent"
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\nreads:\n  - allowed.md\nwrites:\n  - allowed.md\n---\n",
            encoding="utf-8",
        )
        self.addCleanup(shutil.rmtree, str(skill_dir), True)

        with self.assertRaises(ContractViolation):
            check_read_allowed("forbidden.md", "restricted-agent")

        with self.assertRaises(ContractViolation):
            check_write_allowed("forbidden.md", "restricted-agent")

    def test_admin_default_allows_all(self):
        context_utils.STRICT_MODE = True
        # Agent with no SKILL.md gets admin (full access)
        contract = load_agent_contract("nonexistent-agent-xyz")
        self.assertEqual(contract["reads"], ["*"])
        self.assertEqual(contract["writes"], ["*"])
        # Should not raise
        check_read_allowed("any-file.md", "nonexistent-agent-xyz")
        check_write_allowed("any-file.md", "nonexistent-agent-xyz")


# =========================================================================
# TestConcurrentAccess (TEST-03)
# =========================================================================

# Module-level worker functions for multiprocessing (cannot be nested/lambda)


def _worker_append(context_root_str, worker_id, count):
    """Worker that appends entries to a shared file."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    import context_utils as _cu

    _cu.CONTEXT_ROOT = Path(context_root_str)
    _cu.STRICT_MODE = False

    for i in range(count):
        _cu.append_entry(
            "concurrent.md",
            {
                "date": "2026-03-09",
                "source": "worker-%d" % worker_id,
                "detail": "item-%d" % i,
                "confidence": "medium",
                "content": ["data from worker %d item %d" % (worker_id, i)],
            },
            "worker-%d" % worker_id,
            "test-agent",
        )


def _worker_reader(context_root_str, read_count, results_list):
    """Worker that continuously reads a file and checks for corruption."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    import context_utils as _cu

    _cu.CONTEXT_ROOT = Path(context_root_str)
    _cu.STRICT_MODE = False

    for _ in range(read_count):
        content = _cu.read_context("concurrent-rw.md", "test-agent")
        if content.strip():
            entries = _cu.parse_context_file(content)
            # If we got content, it should be parseable (no partial/corrupt reads)
            results_list.append(len(entries))
        time.sleep(0.01)


def _worker_rw_writer(context_root_str, count):
    """Worker that writes to concurrent-rw.md."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    import context_utils as _cu

    _cu.CONTEXT_ROOT = Path(context_root_str)
    _cu.STRICT_MODE = False

    for i in range(count):
        _cu.append_entry(
            "concurrent-rw.md",
            {
                "date": "2026-03-09",
                "source": "writer",
                "detail": "rw-%d" % i,
                "confidence": "medium",
                "content": ["write %d" % i],
            },
            "writer",
            "test-agent",
        )
        time.sleep(0.01)


def _contention_writer(context_root_str, entry_id):
    """Worker for lock contention test."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    import context_utils as _cu

    _cu.CONTEXT_ROOT = Path(context_root_str)
    _cu.STRICT_MODE = False

    _cu.append_entry(
        "contention.md",
        {
            "date": "2026-03-09",
            "source": "contention-writer",
            "detail": "entry-%d" % entry_id,
            "confidence": "medium",
            "content": ["contention test %d" % entry_id],
        },
        "contention-writer",
        "test-agent",
    )


class TestConcurrentAccess(_TempRootMixin, unittest.TestCase):
    """Test concurrent multi-process access to context files."""

    def test_concurrent_writes_no_data_loss(self):
        import multiprocessing

        num_workers = 5
        entries_per_worker = 10
        processes = []

        for w in range(num_workers):
            p = multiprocessing.Process(
                target=_worker_append,
                args=(str(context_utils.CONTEXT_ROOT), w, entries_per_worker),
            )
            processes.append(p)

        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=30)

        # Verify all entries present
        content = read_context("concurrent.md", "test-agent")
        entries = parse_context_file(content)
        self.assertEqual(
            len(entries),
            num_workers * entries_per_worker,
            "Expected %d entries, got %d (data loss)" % (
                num_workers * entries_per_worker, len(entries)
            ),
        )

        # All entries should be parseable
        for e in entries:
            self.assertIsNotNone(e.date)
            self.assertIn(e.confidence, ("high", "medium", "low"))

    def test_concurrent_read_during_write(self):
        import multiprocessing

        # Seed file first so reader has something to parse
        append_entry(
            "concurrent-rw.md",
            {
                "date": "2026-03-09",
                "source": "seed",
                "confidence": "low",
                "content": ["initial"],
            },
            "seed",
            "test-agent",
        )

        manager = multiprocessing.Manager()
        read_results = manager.list()

        writer = multiprocessing.Process(
            target=_worker_rw_writer,
            args=(str(context_utils.CONTEXT_ROOT), 20),
        )
        reader = multiprocessing.Process(
            target=_worker_reader,
            args=(str(context_utils.CONTEXT_ROOT), 30, read_results),
        )

        writer.start()
        reader.start()
        writer.join(timeout=30)
        reader.join(timeout=30)

        # Reader should have gotten valid counts every time (no corrupt reads)
        for count in read_results:
            self.assertGreaterEqual(count, 1, "Reader got corrupt/partial content")

    def test_lock_contention_resolves(self):
        import multiprocessing

        p1 = multiprocessing.Process(
            target=_contention_writer,
            args=(str(context_utils.CONTEXT_ROOT), 1),
        )
        p2 = multiprocessing.Process(
            target=_contention_writer,
            args=(str(context_utils.CONTEXT_ROOT), 2),
        )
        p1.start()
        p2.start()
        p1.join(timeout=15)
        p2.join(timeout=15)

        content = read_context("contention.md", "test-agent")
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 2, "Both contention writers should succeed")


# =========================================================================
# TestEdgeCases (TEST-04)
# =========================================================================


class TestEdgeCases(_TempRootMixin, unittest.TestCase):
    """Test graceful handling of edge cases and adversarial inputs."""

    def test_empty_file(self):
        entries = parse_context_file("")
        self.assertEqual(entries, [])

    def test_file_with_only_header(self):
        content = (
            "# Test\n"
            "_owner: agent_\n"
            "_last_updated: 2026-03-09_\n"
        )
        entries = parse_context_file(content)
        self.assertEqual(entries, [])

    def test_malformed_entry_header(self):
        content = (
            "[bad date | source: x]\n"
            "- Some content\n"
            "- Confidence: medium\n"
        )
        # Should not crash; gracefully skip malformed header
        entries = parse_context_file(content)
        # "bad date" does not match YYYY-MM-DD, so it should be skipped
        self.assertEqual(len(entries), 0)

    def test_missing_metadata_in_entry(self):
        content = (
            "[2026-03-09 | source: test-src]\n"
            "- Just a finding, no metadata lines\n"
        )
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 1)
        # Should use defaults
        self.assertEqual(entries[0].evidence_count, 1)
        self.assertEqual(entries[0].confidence, "low")

    def test_extra_whitespace(self):
        content = (
            "[2026-03-01 | source: src1]\n"
            "- Content 1\n"
            "- Confidence: high\n"
            "\n\n\n"
            "[2026-03-02 | source: src2]\n"
            "- Content 2\n"
            "- Confidence: medium\n"
        )
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 2)

    def test_unicode_content(self):
        entry = {
            "date": "2026-03-09",
            "source": "test",
            "confidence": "medium",
            "content": ["Rene met cafe patron", "Data point with accents"],
        }
        append_entry("unicode.md", entry, "test", "test-agent")
        content = read_context("unicode.md", "test-agent")
        self.assertIn("Rene met cafe patron", content)
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 1)

    def test_very_long_content(self):
        content_lines = ["Line %d: some data here" % i for i in range(100)]
        content = (
            "[2026-03-09 | source: long-content]\n"
            + "\n".join("- %s" % line for line in content_lines)
            + "\n- Confidence: high\n"
        )
        entries = parse_context_file(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(entries[0].content), 100)

    def test_manifest_corrupt_recovery(self):
        # Corrupt manifest content should not crash parse_manifest
        corrupt = "this is not a valid manifest at all @@@@"
        result = parse_manifest(corrupt)
        self.assertIsInstance(result, dict)
        self.assertIn("schema_version", result)
        self.assertIn("registry", result)

    def test_orphaned_tmp_cleanup(self):
        # Create an orphaned .tmp file
        tmp_file = context_utils.CONTEXT_ROOT / "orphan.tmp"
        tmp_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file.write_text("orphan", encoding="utf-8")
        # Normal operations should not be disrupted
        append_entry(
            "normal.md",
            {"date": "2026-03-09", "source": "test", "confidence": "low", "content": ["ok"]},
            "test",
            "test-agent",
        )
        content = read_context("normal.md", "test-agent")
        self.assertIn("ok", content)

    def test_lock_file_cleanup(self):
        # Perform multiple writes and check .lock files don't accumulate excessively
        for i in range(5):
            append_entry(
                "locktest.md",
                {
                    "date": "2026-03-0%d" % (i + 1),
                    "source": "lock-test",
                    "detail": "round%d" % i,
                    "confidence": "low",
                    "content": ["data %d" % i],
                },
                "lock-test",
                "test-agent",
            )
        # There should be lock files for locktest.md and _manifest.md only (not accumulating)
        lock_files = list(context_utils.CONTEXT_ROOT.rglob("*.lock"))
        # Lock files exist but should be a bounded, small number (not 5x)
        self.assertLessEqual(len(lock_files), 5)


# =========================================================================
# TestRoundTrip (TEST-05, CORE-09)
# =========================================================================


class TestRoundTrip(unittest.TestCase):
    """Test parse -> serialize -> parse identity for all entry formats."""

    def _compare_entries(self, original, roundtripped):
        """Compare two ContextEntry objects field by field."""
        self.assertEqual(original.date, roundtripped.date)
        self.assertEqual(original.source, roundtripped.source)
        self.assertEqual(original.detail, roundtripped.detail)
        self.assertEqual(original.content, roundtripped.content)
        self.assertEqual(original.evidence_count, roundtripped.evidence_count)
        self.assertEqual(original.confidence, roundtripped.confidence)
        self.assertEqual(original.last_validated, roundtripped.last_validated)
        self.assertEqual(original.supersedes, roundtripped.supersedes)
        if original.effectiveness_score is not None:
            self.assertAlmostEqual(
                original.effectiveness_score,
                roundtripped.effectiveness_score,
                places=5,
            )
        else:
            self.assertIsNone(roundtripped.effectiveness_score)

    def test_roundtrip_single_entry(self):
        entry = ContextEntry(
            date=datetime(2026, 3, 9),
            source="meeting-processor",
            detail="call: John Smith",
            content=["Key finding"],
            evidence_count=2,
            confidence="high",
        )
        serialized = serialize_entries([entry])
        parsed = parse_context_file(serialized)
        self.assertEqual(len(parsed), 1)
        self._compare_entries(entry, parsed[0])

    def test_roundtrip_multiple_entries(self):
        entries = [
            ContextEntry(
                date=datetime(2026, 3, i + 1),
                source="src-%d" % i,
                detail="detail %d" % i,
                content=["Finding %d" % i],
                evidence_count=i + 1,
                confidence=["low", "medium", "high", "medium", "low"][i],
            )
            for i in range(5)
        ]
        serialized = serialize_entries(entries)
        parsed = parse_context_file(serialized)
        self.assertEqual(len(parsed), 5)
        for orig, rt in zip(entries, parsed):
            self._compare_entries(orig, rt)

    def test_roundtrip_with_file_header(self):
        header = FileHeader(
            owner="test-agent",
            last_updated="2026-03-09",
            updated_by="test-agent",
            entry_cap=50,
        )
        entry = ContextEntry(
            date=datetime(2026, 3, 9),
            source="test",
            detail="",
            content=["Content"],
            confidence="medium",
        )
        serialized = serialize_entries([entry], header=header, title="Test Context")
        # Parse header
        parsed_header = parse_file_header(serialized)
        self.assertEqual(parsed_header.owner, "test-agent")
        self.assertEqual(parsed_header.last_updated, "2026-03-09")
        self.assertEqual(parsed_header.updated_by, "test-agent")
        self.assertEqual(parsed_header.entry_cap, 50)
        # Parse entries
        parsed_entries = parse_context_file(serialized)
        self.assertEqual(len(parsed_entries), 1)
        self._compare_entries(entry, parsed_entries[0])

    def test_roundtrip_full_file_format(self):
        """Test with exact format from ARCHITECTURE.md Layer 4a File Format Standard."""
        arch_format = (
            "# Test Context\n"
            "_owner: meeting-processor_\n"
            "_last_updated: 2026-03-09_\n"
            "_updated_by: meeting-processor_\n"
            "_entry_cap: 50_\n"
            "\n"
            "[2026-03-09 | source: meeting-processor | call: John Smith @ ABC Corp]\n"
            "- Finding or data point\n"
            '- Evidence: "direct quote from source"\n'
            "- Supersedes: older-entry-ref\n"
            "- Evidence_count: 4\n"
            "- Confidence: high\n"
            "- Last_validated: 2026-03-09\n"
            "\n"
            "[2026-02-15 | source: meeting-processor | call: Sarah Lee @ XYZ Insurance]\n"
            "- Finding or data point\n"
            "- Evidence_count: 1\n"
            "- Confidence: medium\n"
        )
        # Parse
        entries1 = parse_context_file(arch_format)
        header1 = parse_file_header(arch_format)
        self.assertEqual(len(entries1), 2)
        self.assertEqual(entries1[0].evidence_count, 4)
        self.assertEqual(entries1[0].confidence, "high")
        self.assertEqual(entries1[0].supersedes, "older-entry-ref")
        self.assertEqual(entries1[1].confidence, "medium")

        # Serialize
        serialized = serialize_entries(entries1, header=header1, title="Test Context")

        # Parse again
        entries2 = parse_context_file(serialized)
        self.assertEqual(len(entries2), 2)

        for orig, rt in zip(entries1, entries2):
            self._compare_entries(orig, rt)

    def test_roundtrip_minimal_entry(self):
        entry = ContextEntry(
            date=datetime(2026, 3, 9),
            source="minimal",
            detail="",
            content=["one content line"],
            confidence="low",
        )
        serialized = serialize_entries([entry])
        parsed = parse_context_file(serialized)
        self.assertEqual(len(parsed), 1)
        self._compare_entries(entry, parsed[0])

    def test_roundtrip_all_optional_fields(self):
        entry = ContextEntry(
            date=datetime(2026, 3, 9),
            source="full-entry",
            detail="all fields present",
            content=["Finding 1", "Finding 2"],
            evidence_count=5,
            confidence="high",
            last_validated=datetime(2026, 3, 9),
            supersedes="old-ref-123",
            effectiveness_score=0.92,
        )
        serialized = serialize_entries([entry])
        parsed = parse_context_file(serialized)
        self.assertEqual(len(parsed), 1)
        self._compare_entries(entry, parsed[0])

    def test_roundtrip_preserves_content_order(self):
        lines = ["Line %d" % i for i in range(5)]
        entry = ContextEntry(
            date=datetime(2026, 3, 9),
            source="order-test",
            detail="",
            content=lines,
            confidence="medium",
        )
        serialized = serialize_entries([entry])
        parsed = parse_context_file(serialized)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].content, lines)


# =========================================================================
# TestVerifyWrites
# =========================================================================


class TestVerifyWrites(_TempRootMixin, unittest.TestCase):
    """Test verify_writes() — post-run write verification against _events.jsonl."""

    def test_verify_writes_all_present(self):
        """Log 2 events, verify both declared files are found."""
        log_event("append", "contacts.md", "test-skill", "wrote contact")
        log_event("append", "insights.md", "test-skill", "wrote insight")

        result = context_utils.verify_writes(
            declared=["contacts.md", "insights.md"],
            agent_id="test-skill",
            since_minutes=5,
        )
        self.assertEqual(result["missing"], [])
        self.assertIn("contacts.md", result["actual"])
        self.assertIn("insights.md", result["actual"])

    def test_verify_writes_missing_one(self):
        """Log 1 event, verify the other declared file is missing."""
        log_event("append", "contacts.md", "test-skill", "wrote contact")

        result = context_utils.verify_writes(
            declared=["contacts.md", "insights.md"],
            agent_id="test-skill",
            since_minutes=5,
        )
        self.assertIn("insights.md", result["missing"])
        self.assertIn("contacts.md", result["actual"])

    def test_verify_writes_none_declared(self):
        """Empty declared list returns no missing."""
        result = context_utils.verify_writes(
            declared=[],
            agent_id="test-skill",
            since_minutes=5,
        )
        self.assertEqual(result["missing"], [])

    def test_verify_writes_no_events(self):
        """No events logged, all declared files are missing."""
        result = context_utils.verify_writes(
            declared=["contacts.md"],
            agent_id="test-skill",
            since_minutes=5,
        )
        self.assertIn("contacts.md", result["missing"])

    def test_verify_writes_filters_by_agent(self):
        """Events from different agents are filtered correctly."""
        log_event("append", "contacts.md", "skill-a", "wrote contact")
        log_event("append", "insights.md", "skill-b", "wrote insight")

        result = context_utils.verify_writes(
            declared=["contacts.md", "insights.md"],
            agent_id="skill-a",
            since_minutes=5,
        )
        # skill-a only wrote contacts.md
        self.assertIn("contacts.md", result["actual"])
        self.assertIn("insights.md", result["missing"])

    def test_verify_writes_filters_by_time(self):
        """Old events outside time window are not counted."""
        # Manually write an old event to _events.jsonl
        events_path = context_utils.CONTEXT_ROOT / "_events.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        old_ts = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        import json as _json
        old_event = _json.dumps({
            "timestamp": old_ts,
            "event_type": "append",
            "file": "contacts.md",
            "agent_id": "test-skill",
            "detail": "old event",
        })
        with open(str(events_path), "w", encoding="utf-8") as f:
            f.write(old_event + "\n")

        result = context_utils.verify_writes(
            declared=["contacts.md"],
            agent_id="test-skill",
            since_minutes=5,
        )
        # Old event should be outside the window
        self.assertIn("contacts.md", result["missing"])


# =========================================================================
# TestPathContainment
# =========================================================================


class TestPathContainment(_TempRootMixin, unittest.TestCase):
    """Test path traversal prevention in core API."""

    def _make_entry(self):
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "test",
            "detail": "test-entry",
            "content": ["test content"],
            "confidence": "low",
            "evidence_count": 1,
        }

    def test_path_traversal_blocked_on_append(self):
        """append_entry rejects '../escape.md'."""
        with self.assertRaises(ValueError) as ctx:
            append_entry("../escape.md", self._make_entry(), "test", "test-agent")
        self.assertIn("Path traversal blocked", str(ctx.exception))

    def test_path_traversal_blocked_on_read(self):
        """read_context rejects '../escape.md'."""
        with self.assertRaises(ValueError) as ctx:
            read_context("../escape.md", "test-agent")
        self.assertIn("Path traversal blocked", str(ctx.exception))

    def test_path_traversal_blocked_on_query(self):
        """query_context rejects '../escape.md'."""
        with self.assertRaises(ValueError) as ctx:
            query_context("../escape.md", "test-agent")
        self.assertIn("Path traversal blocked", str(ctx.exception))

    def test_absolute_path_blocked(self):
        """append_entry rejects absolute paths."""
        with self.assertRaises(ValueError) as ctx:
            append_entry("/etc/passwd", self._make_entry(), "test", "test-agent")
        self.assertIn("Path traversal blocked", str(ctx.exception))

    def test_subdirectory_paths_allowed(self):
        """_learning/ subdirectory paths are valid (under CONTEXT_ROOT)."""
        result = append_entry(
            "_learning/test-log.md", self._make_entry(), "test", "test-agent"
        )
        self.assertEqual(result, "OK")

    def test_normal_file_allowed(self):
        """Normal context file paths work fine."""
        result = append_entry(
            "contacts.md", self._make_entry(), "test", "test-agent"
        )
        self.assertEqual(result, "OK")

    def test_double_dot_in_middle_blocked(self):
        """Paths with '../' in the middle are blocked."""
        with self.assertRaises(ValueError) as ctx:
            append_entry("subdir/../../escape.md", self._make_entry(), "test", "test-agent")
        self.assertIn("Path traversal blocked", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
