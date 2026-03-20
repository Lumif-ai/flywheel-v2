#!/usr/bin/env python3
"""
Smoke tests for PII Redactor script.
Validates core functions in isolation: extraction, detection, anonymization,
audit log generation, dry-run, error handling, and edge cases.
"""

import os
import sys
import tempfile
import unittest

# Add the scripts directory to the path so we can import redact module
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import redact

SPACY_MODEL = "en_core_web_sm"
SAMPLE_TEXT = (
    "John Smith called at 555-123-4567. "
    "His SSN is 078-05-1120. "
    "Contact him at john@example.com"
)


class TestTextExtraction(unittest.TestCase):
    """Smoke: text extraction from plain text file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.txt_path = os.path.join(self.tmpdir, "sample.txt")
        with open(self.txt_path, "w") as f:
            f.write(SAMPLE_TEXT)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_extract_text_from_txt(self):
        text = redact.extract_text(self.txt_path)
        self.assertEqual(text, SAMPLE_TEXT)

    def test_extract_preserves_content(self):
        text = redact.extract_text(self.txt_path)
        self.assertIn("John Smith", text)
        self.assertIn("555-123-4567", text)
        self.assertIn("john@example.com", text)


class TestPIIDetection(unittest.TestCase):
    """Smoke: PII detection returns expected entity types."""

    @classmethod
    def setUpClass(cls):
        # Run detection once for all tests in this class (expensive operation)
        # Use threshold=0.35 because en_core_web_sm scores phone numbers at ~0.4
        redact.ensure_spacy_model(SPACY_MODEL)
        cls.results = redact.detect_pii(
            SAMPLE_TEXT,
            entities=redact.DEFAULT_ENTITIES,
            threshold=0.35,
            spacy_model=SPACY_MODEL,
        )
        cls.entity_types = [r.entity_type for r in cls.results]

    def test_detects_person(self):
        self.assertIn("PERSON", self.entity_types)

    def test_detects_phone(self):
        self.assertIn("PHONE_NUMBER", self.entity_types)

    def test_detects_email(self):
        self.assertIn("EMAIL_ADDRESS", self.entity_types)

    def test_results_sorted_by_position(self):
        starts = [r.start for r in self.results]
        self.assertEqual(starts, sorted(starts))

    def test_results_have_scores(self):
        for r in self.results:
            self.assertGreater(r.score, 0.0)
            self.assertLessEqual(r.score, 1.0)


class TestAnonymizationReplaceMode(unittest.TestCase):
    """Smoke: anonymization in 'replace' mode produces numbered tags."""

    @classmethod
    def setUpClass(cls):
        redact.ensure_spacy_model(SPACY_MODEL)
        results = redact.detect_pii(
            SAMPLE_TEXT,
            entities=redact.DEFAULT_ENTITIES,
            threshold=0.35,
            spacy_model=SPACY_MODEL,
        )
        cls.anonymized, cls.findings, cls.reverse_map = redact.anonymize_text(
            SAMPLE_TEXT, results, mode="replace"
        )

    def test_replace_produces_numbered_tags(self):
        # Should have tags like <PERSON_1>, <PHONE_NUMBER_1>, etc.
        import re
        tags = re.findall(r"<[A-Z_]+_\d+>", self.anonymized)
        self.assertGreater(len(tags), 0)

    def test_person_tag_present(self):
        self.assertIn("<PERSON_1>", self.anonymized)

    def test_original_pii_removed(self):
        self.assertNotIn("John Smith", self.anonymized)
        self.assertNotIn("john@example.com", self.anonymized)

    def test_findings_have_required_keys(self):
        required_keys = {"entity_type", "original", "replacement", "confidence", "start", "end", "line"}
        for f in self.findings:
            self.assertTrue(required_keys.issubset(f.keys()), f"Missing keys in finding: {f.keys()}")

    def test_reverse_map_populated(self):
        self.assertGreater(len(self.reverse_map), 0)
        # Each key should be a tag, each value the original text
        for tag, original in self.reverse_map.items():
            self.assertTrue(tag.startswith("<"))
            self.assertTrue(tag.endswith(">"))
            self.assertIsInstance(original, str)


class TestAuditLogGeneration(unittest.TestCase):
    """Smoke: audit log contains expected sections."""

    def test_audit_log_structure(self):
        findings = [
            {
                "entity_type": "PERSON",
                "original": "John Smith",
                "replacement": "<PERSON_1>",
                "confidence": 0.85,
                "start": 0,
                "end": 10,
                "line": 1,
            }
        ]
        log = redact.generate_audit_log(
            source_file="test.txt",
            findings=findings,
            threshold=0.7,
            spacy_model=SPACY_MODEL,
            mode="replace",
            entities_used=["PERSON"],
            entities_excluded=[],
        )
        self.assertIn("# PII Audit Log", log)
        self.assertIn("## Summary", log)
        self.assertIn("## Detailed Findings", log)
        self.assertIn("## Settings Used", log)
        self.assertIn("PERSON", log)
        self.assertIn("John Smith", log)
        self.assertIn("test.txt", log)


class TestDryRun(unittest.TestCase):
    """Smoke: dry-run mode exits cleanly without writing files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.txt_path = os.path.join(self.tmpdir, "sample.txt")
        with open(self.txt_path, "w") as f:
            f.write(SAMPLE_TEXT)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dry_run_no_output_files(self):
        """Dry run should exit(0) and not create output files."""
        import subprocess
        result = subprocess.run(
            [
                sys.executable, os.path.join(SCRIPTS_DIR, "redact.py"),
                self.txt_path,
                "--dry-run",
                "--spacy-model", SPACY_MODEL,
                "--threshold", "0.35",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        # No redacted or audit files should be created
        files_after = os.listdir(self.tmpdir)
        self.assertEqual(files_after, ["sample.txt"])


class TestFileNotFound(unittest.TestCase):
    """Smoke: missing file exits with error code 1."""

    def test_nonexistent_file_exits_1(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, os.path.join(SCRIPTS_DIR, "redact.py"),
                "/nonexistent/path/to/file.txt",
                "--spacy-model", SPACY_MODEL,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Error", result.stderr)


class TestEmptyDocument(unittest.TestCase):
    """Smoke: empty document handling."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.empty_path = os.path.join(self.tmpdir, "empty.txt")
        with open(self.empty_path, "w") as f:
            f.write("")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_file_exits_with_error(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, os.path.join(SCRIPTS_DIR, "redact.py"),
                self.empty_path,
                "--spacy-model", SPACY_MODEL,
            ],
            capture_output=True,
            text=True,
        )
        # The script exits with code 1 for empty text
        self.assertEqual(result.returncode, 1)
        self.assertIn("No text extracted", result.stderr)


if __name__ == "__main__":
    unittest.main()
