"""Tests for the storage_backend Strangler Fig selector."""

import importlib
import os
import sys
import unittest


class TestStorageBackendFlatfile(unittest.TestCase):
    """Test that flatfile backend correctly re-exports context_utils functions."""

    def test_exports_read_context(self):
        """storage_backend exposes read_context from context_utils."""
        from flywheel import storage_backend
        from flywheel import context_utils

        self.assertIs(storage_backend.read_context, context_utils.read_context)

    def test_exports_append_entry(self):
        """storage_backend exposes append_entry from context_utils."""
        from flywheel import storage_backend
        from flywheel import context_utils

        self.assertIs(storage_backend.append_entry, context_utils.append_entry)

    def test_exports_query_context(self):
        """storage_backend exposes query_context from context_utils."""
        from flywheel import storage_backend
        from flywheel import context_utils

        self.assertIs(storage_backend.query_context, context_utils.query_context)

    def test_exports_batch_context(self):
        """storage_backend exposes batch_context from context_utils."""
        from flywheel import storage_backend
        from flywheel import context_utils

        self.assertIs(storage_backend.batch_context, context_utils.batch_context)

    def test_all_exports(self):
        """__all__ contains the 7 public API functions."""
        from flywheel import storage_backend

        self.assertEqual(
            set(storage_backend.__all__),
            {
                "read_context",
                "append_entry",
                "query_context",
                "batch_context",
                "list_context_files",
                "parse_context_file",
                "log_event",
            },
        )

    def test_exports_list_context_files(self):
        """storage_backend exposes list_context_files from context_utils."""
        from flywheel import storage_backend
        from flywheel import context_utils

        self.assertIs(storage_backend.list_context_files, context_utils.list_context_files)

    def test_exports_parse_context_file(self):
        """storage_backend exposes parse_context_file from context_utils."""
        from flywheel import storage_backend
        from flywheel import context_utils

        self.assertIs(storage_backend.parse_context_file, context_utils.parse_context_file)

    def test_exports_log_event(self):
        """storage_backend exposes log_event from context_utils."""
        from flywheel import storage_backend
        from flywheel import context_utils

        self.assertIs(storage_backend.log_event, context_utils.log_event)


class TestStorageBackendPostgres(unittest.TestCase):
    """Test that postgres backend imports storage.py functions."""

    def test_postgres_imports_storage(self):
        """Setting FLYWHEEL_BACKEND=postgres imports from flywheel.storage."""
        original_backend = os.environ.get("FLYWHEEL_BACKEND")
        original_module = sys.modules.pop("flywheel.storage_backend", None)

        try:
            os.environ["FLYWHEEL_BACKEND"] = "postgres"
            mod = importlib.import_module("flywheel.storage_backend")
            # Should have the 4 API functions from storage.py
            self.assertTrue(callable(mod.read_context))
            self.assertTrue(callable(mod.append_entry))
            self.assertTrue(callable(mod.query_context))
            self.assertTrue(callable(mod.batch_context))
        finally:
            if original_backend is not None:
                os.environ["FLYWHEEL_BACKEND"] = original_backend
            else:
                os.environ.pop("FLYWHEEL_BACKEND", None)
            sys.modules.pop("flywheel.storage_backend", None)
            if original_module is not None:
                sys.modules["flywheel.storage_backend"] = original_module

    def test_invalid_backend_raises_value_error(self):
        """Setting FLYWHEEL_BACKEND to unknown value raises ValueError."""
        original_backend = os.environ.get("FLYWHEEL_BACKEND")
        original_module = sys.modules.pop("flywheel.storage_backend", None)

        try:
            os.environ["FLYWHEEL_BACKEND"] = "redis"
            with self.assertRaises(ValueError) as ctx:
                importlib.import_module("flywheel.storage_backend")
            self.assertIn("redis", str(ctx.exception))
        finally:
            if original_backend is not None:
                os.environ["FLYWHEEL_BACKEND"] = original_backend
            else:
                os.environ.pop("FLYWHEEL_BACKEND", None)
            sys.modules.pop("flywheel.storage_backend", None)
            if original_module is not None:
                sys.modules["flywheel.storage_backend"] = original_module


if __name__ == "__main__":
    unittest.main()
