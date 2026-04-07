#!/usr/bin/env python3
"""
End-to-end tests for PII Redactor script.
Validates the full pipeline: input file -> redacted output + audit log + mapping,
seed mapping consistency, different modes, and --entities flag.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
REDACT_SCRIPT = os.path.join(SCRIPTS_DIR, "redact.py")
SPACY_MODEL = "en_core_web_sm"

SAMPLE_TEXT = (
    "John Smith called at 555-123-4567. "
    "His SSN is 078-05-1120. "
    "Contact him at john@example.com"
)

MULTI_PII_TEXT = (
    "Dear Jane Doe,\n\n"
    "Your account has been flagged. Please call us at 800-555-9999.\n"
    "We have your SSN on file: 219-09-9999.\n"
    "Your email address is jane.doe@corporate.org.\n"
    "Also, Robert Johnson (robert.j@mail.com) was CC'd on this notice.\n\n"
    "Regards,\nCompliance Team"
)


def run_redactor(input_path, extra_args=None):
    """Helper to run the redactor script as a subprocess."""
    cmd = [
        sys.executable, REDACT_SCRIPT,
        input_path,
        "--spacy-model", SPACY_MODEL,
        "--threshold", "0.35",
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


class TestFullPipeline(unittest.TestCase):
    """E2E: full redaction pipeline produces redacted output + audit log + mapping."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.input_path = os.path.join(self.tmpdir, "document.txt")
        with open(self.input_path, "w") as f:
            f.write(SAMPLE_TEXT)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_pipeline_creates_output_and_audit(self):
        result = run_redactor(self.input_path)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

        redacted_path = os.path.join(self.tmpdir, "document_redacted.md")
        audit_path = os.path.join(self.tmpdir, "document_pii_audit.md")

        self.assertTrue(os.path.exists(redacted_path), "Redacted file not created")
        self.assertTrue(os.path.exists(audit_path), "Audit log not created")

    def test_pipeline_with_mapping(self):
        result = run_redactor(self.input_path, ["--save-mapping"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

        mapping_path = os.path.join(self.tmpdir, "document_mapping.json")
        self.assertTrue(os.path.exists(mapping_path), "Mapping file not created")

        with open(mapping_path) as f:
            mapping = json.load(f)
        self.assertIsInstance(mapping, dict)
        self.assertGreater(len(mapping), 0)

    def test_redacted_file_no_original_pii(self):
        run_redactor(self.input_path)
        redacted_path = os.path.join(self.tmpdir, "document_redacted.md")

        with open(redacted_path) as f:
            content = f.read()

        self.assertNotIn("John Smith", content)
        self.assertNotIn("john@example.com", content)
        # SSN may be partially detected; check core digits
        self.assertNotIn("078-05-1120", content)

    def test_mapping_can_reconstruct_entities(self):
        """Verify mapping.json contains tag->original pairs that allow reconstruction."""
        run_redactor(self.input_path, ["--save-mapping"])
        mapping_path = os.path.join(self.tmpdir, "document_mapping.json")

        with open(mapping_path) as f:
            mapping = json.load(f)

        redacted_path = os.path.join(self.tmpdir, "document_redacted.md")
        with open(redacted_path) as f:
            redacted = f.read()

        # Every tag in the mapping should appear in the redacted text
        for tag in mapping.keys():
            self.assertIn(tag, redacted, f"Tag {tag} from mapping not found in redacted text")

        # Reconstruct and verify originals are present
        reconstructed = redacted
        for tag, original in mapping.items():
            reconstructed = reconstructed.replace(tag, original)

        # At minimum the person name should be reconstructed
        originals = list(mapping.values())
        person_names = [v for v in originals if any(c.isalpha() for c in v) and " " in v]
        if person_names:
            for name in person_names:
                self.assertIn(name, reconstructed)


class TestMultiplePIITypes(unittest.TestCase):
    """E2E: document with multiple PII types is fully processed."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.input_path = os.path.join(self.tmpdir, "multi.txt")
        with open(self.input_path, "w") as f:
            f.write(MULTI_PII_TEXT)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_multiple_pii_types_detected(self):
        result = run_redactor(self.input_path, ["--save-mapping"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

        audit_path = os.path.join(self.tmpdir, "multi_pii_audit.md")
        with open(audit_path) as f:
            audit = f.read()

        # Should detect at least PERSON and EMAIL_ADDRESS
        self.assertIn("PERSON", audit)
        self.assertIn("EMAIL_ADDRESS", audit)

    def test_multiple_entity_types_get_unique_tags(self):
        """Multiple distinct PII types each get their own numbered tags."""
        run_redactor(self.input_path, ["--save-mapping"])
        mapping_path = os.path.join(self.tmpdir, "multi_mapping.json")

        with open(mapping_path) as f:
            mapping = json.load(f)

        # en_core_web_sm may not detect all persons (e.g. misses "Jane Doe" in
        # salutation), but should find multiple entity types overall
        entity_types_found = set()
        for tag in mapping.keys():
            import re
            m = re.match(r"<([A-Z_]+)_\d+>", tag)
            if m:
                entity_types_found.add(m.group(1))

        # Should have at least 3 different entity types (PERSON, EMAIL_ADDRESS, and
        # one of PHONE_NUMBER/US_SSN)
        self.assertGreaterEqual(
            len(entity_types_found), 3,
            f"Expected 3+ entity types, got: {entity_types_found}"
        )


class TestSeedMappingConsistency(unittest.TestCase):
    """E2E: seed mapping ensures same entity gets same tag across documents."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

        # Doc 1: contains John Smith
        self.doc1 = os.path.join(self.tmpdir, "doc1.txt")
        with open(self.doc1, "w") as f:
            f.write("John Smith emailed john@example.com about the project.")

        # Doc 2: also contains John Smith in different context
        self.doc2 = os.path.join(self.tmpdir, "doc2.txt")
        with open(self.doc2, "w") as f:
            f.write("Meeting notes: John Smith presented the quarterly results.")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_seed_mapping_reuses_tags(self):
        # Redact doc1 and save mapping
        result1 = run_redactor(self.doc1, ["--save-mapping"])
        self.assertEqual(result1.returncode, 0, f"Doc1 stderr: {result1.stderr}")

        mapping1_path = os.path.join(self.tmpdir, "doc1_mapping.json")
        self.assertTrue(os.path.exists(mapping1_path))

        with open(mapping1_path) as f:
            mapping1 = json.load(f)

        # Find John Smith's tag in first mapping
        john_tag = None
        for tag, original in mapping1.items():
            if "John Smith" in original:
                john_tag = tag
                break

        # Redact doc2 using doc1's mapping as seed
        result2 = run_redactor(self.doc2, [
            "--save-mapping",
            "--seed-mapping", mapping1_path,
            "--output", os.path.join(self.tmpdir, "doc2_redacted.md"),
            "--audit", os.path.join(self.tmpdir, "doc2_pii_audit.md"),
        ])
        self.assertEqual(result2.returncode, 0, f"Doc2 stderr: {result2.stderr}")

        mapping2_path = os.path.join(self.tmpdir, "doc2_mapping.json")
        with open(mapping2_path) as f:
            mapping2 = json.load(f)

        # If John Smith was detected in both, the tag should be the same
        if john_tag:
            john_tag_in_doc2 = None
            for tag, original in mapping2.items():
                if "John Smith" in original:
                    john_tag_in_doc2 = tag
                    break
            if john_tag_in_doc2:
                self.assertEqual(john_tag, john_tag_in_doc2,
                    f"Seed mapping failed: same person got different tags: {john_tag} vs {john_tag_in_doc2}")


class TestRedactionModes(unittest.TestCase):
    """E2E: different redaction modes produce expected output formats."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.input_path = os.path.join(self.tmpdir, "modes.txt")
        with open(self.input_path, "w") as f:
            f.write(SAMPLE_TEXT)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_mode(self, mode):
        output = os.path.join(self.tmpdir, f"{mode}_redacted.md")
        audit = os.path.join(self.tmpdir, f"{mode}_audit.md")
        result = run_redactor(self.input_path, [
            "--mode", mode,
            "--output", output,
            "--audit", audit,
            "--save-mapping",
        ])
        self.assertEqual(result.returncode, 0, f"Mode {mode} failed: {result.stderr}")
        with open(output) as f:
            return f.read()

    def test_replace_mode(self):
        content = self._run_mode("replace")
        import re
        tags = re.findall(r"<[A-Z_]+_\d+>", content)
        self.assertGreater(len(tags), 0, "Replace mode should produce <TYPE_N> tags")
        self.assertNotIn("John Smith", content)

    def test_mask_mode(self):
        content = self._run_mode("mask")
        # Mask mode keeps first and last char with * in between
        # Should not contain original PII
        self.assertNotIn("John Smith", content)
        # Should contain asterisks
        self.assertIn("*", content)

    def test_hash_mode(self):
        content = self._run_mode("hash")
        import re
        # Hash mode produces [hex_hash] patterns
        hashes = re.findall(r"\[[a-f0-9]{12}\]", content)
        self.assertGreater(len(hashes), 0, "Hash mode should produce [hex] patterns")
        self.assertNotIn("John Smith", content)

    def test_redact_mode(self):
        content = self._run_mode("redact")
        self.assertIn("[REDACTED]", content)
        self.assertNotIn("John Smith", content)


class TestEntitiesFlag(unittest.TestCase):
    """E2E: --entities flag limits detection scope."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.input_path = os.path.join(self.tmpdir, "entities.txt")
        with open(self.input_path, "w") as f:
            f.write(SAMPLE_TEXT)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_entities_limits_detection(self):
        """When only PERSON is requested, email/phone should not be redacted."""
        output = os.path.join(self.tmpdir, "person_only_redacted.md")
        audit = os.path.join(self.tmpdir, "person_only_audit.md")
        result = run_redactor(self.input_path, [
            "--entities", "PERSON",
            "--output", output,
            "--audit", audit,
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

        with open(audit) as f:
            audit_content = f.read()

        # Audit should mention PERSON but not EMAIL_ADDRESS or PHONE_NUMBER
        self.assertIn("PERSON", audit_content)
        self.assertNotIn("EMAIL_ADDRESS", audit_content)
        self.assertNotIn("PHONE_NUMBER", audit_content)

        # The redacted file should still contain the email and phone (not redacted)
        with open(output) as f:
            redacted = f.read()
        self.assertIn("john@example.com", redacted)
        self.assertIn("555-123-4567", redacted)

    def test_email_only_detection(self):
        """When only EMAIL_ADDRESS is requested, only emails should be redacted."""
        output = os.path.join(self.tmpdir, "email_only_redacted.md")
        audit = os.path.join(self.tmpdir, "email_only_audit.md")
        result = run_redactor(self.input_path, [
            "--entities", "EMAIL_ADDRESS",
            "--output", output,
            "--audit", audit,
        ])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

        with open(output) as f:
            redacted = f.read()

        # Email should be redacted, person name should remain
        self.assertNotIn("john@example.com", redacted)
        self.assertIn("John Smith", redacted)


if __name__ == "__main__":
    unittest.main()
