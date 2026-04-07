#!/usr/bin/env python3
"""Smoke tests for log_run.py pipeline run logger."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

# Patch GTM_DIR and RUNS_PATH before importing log_run
_tmpdir = None


def _patch_paths(tmp):
    """Monkey-patch log_run module paths to use a temp directory."""
    import log_run
    log_run.GTM_DIR = tmp
    log_run.RUNS_PATH = os.path.join(tmp, "pipeline-runs.json")


# Add scripts dir to path so we can import log_run
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)
import log_run  # noqa: E402


class TestLogRun(unittest.TestCase):
    """Smoke tests for pipeline run logger."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _patch_paths(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # -- Core functionality --

    def test_log_run_creates_json(self):
        """log_pipeline_run() creates pipeline-runs.json with a run entry."""
        run_id = log_run.log_pipeline_run({"source": "Test Source", "unique_companies": 5})
        runs_path = os.path.join(self.tmpdir, "pipeline-runs.json")
        self.assertTrue(os.path.exists(runs_path))
        with open(runs_path) as f:
            runs = json.load(f)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["source"], "Test Source")
        self.assertEqual(runs[0]["id"], run_id)

    def test_log_run_appends(self):
        """Calling log_pipeline_run() twice should result in 2 entries."""
        log_run.log_pipeline_run({"source": "Run 1"})
        log_run.log_pipeline_run({"source": "Run 2"})
        with open(os.path.join(self.tmpdir, "pipeline-runs.json")) as f:
            runs = json.load(f)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0]["source"], "Run 1")
        self.assertEqual(runs[1]["source"], "Run 2")

    def test_run_id_format(self):
        """Generated run ID starts with 'run_' and has timestamp format."""
        run_id = log_run.log_pipeline_run({"source": "Test"})
        self.assertTrue(run_id.startswith("run_"))
        # Expect format like run_20260313_143022
        timestamp_part = run_id[4:]  # strip "run_"
        self.assertTrue(
            re.match(r"\d{8}_\d{6}", timestamp_part),
            f"Run ID timestamp part '{timestamp_part}' doesn't match expected YYYYMMDD_HHMMSS format"
        )

    # -- Normalization & defaults --

    def test_tier_name_normalization(self):
        """Old tier names (hot/warm/cool/pass) get mapped to new names."""
        log_run.log_pipeline_run({
            "source": "Test", "hot": 10, "warm": 20, "cool": 30, "pass": 40
        })
        with open(os.path.join(self.tmpdir, "pipeline-runs.json")) as f:
            runs = json.load(f)
        entry = runs[0]
        self.assertEqual(entry["strong_fit"], 10)
        self.assertEqual(entry["moderate_fit"], 20)
        self.assertEqual(entry["low_fit"], 30)
        self.assertEqual(entry["no_fit"], 40)
        # Old keys should be removed
        for old_key in ("hot", "warm", "cool", "pass"):
            self.assertNotIn(old_key, entry)

    def test_default_date_added(self):
        """If date not provided, it defaults to today."""
        from datetime import datetime
        log_run.log_pipeline_run({"source": "Test"})
        with open(os.path.join(self.tmpdir, "pipeline-runs.json")) as f:
            runs = json.load(f)
        self.assertEqual(runs[0]["date"], datetime.now().strftime("%Y-%m-%d"))

    def test_default_status(self):
        """Status defaults to 'complete'."""
        log_run.log_pipeline_run({"source": "Test"})
        with open(os.path.join(self.tmpdir, "pipeline-runs.json")) as f:
            runs = json.load(f)
        self.assertEqual(runs[0]["status"], "complete")

    # -- CLI interface --

    def test_cli_interface(self):
        """Running the script via CLI with --source and --no-post-run creates a run entry."""
        runs_path = os.path.join(self.tmpdir, "pipeline-runs.json")
        script_path = os.path.join(SCRIPTS_DIR, "log_run.py")
        env = os.environ.copy()
        # We need to patch the paths for the subprocess. We do this by wrapping
        # the call with a small Python snippet that patches before main().
        wrapper = (
            f"import sys; sys.path.insert(0, '{SCRIPTS_DIR}'); "
            f"import log_run; "
            f"log_run.GTM_DIR = '{self.tmpdir}'; "
            f"log_run.RUNS_PATH = '{runs_path}'; "
            f"sys.argv = ['log_run.py', '--source', 'CLI Test', '--unique-companies', '42', '--no-post-run']; "
            f"log_run.main()"
        )
        result = subprocess.run(
            [sys.executable, "-c", wrapper],
            capture_output=True, text=True, env=env, timeout=10
        )
        self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")
        self.assertTrue(os.path.exists(runs_path), "pipeline-runs.json not created by CLI")
        with open(runs_path) as f:
            runs = json.load(f)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["source"], "CLI Test")
        self.assertEqual(runs[0]["unique_companies"], 42)

    # -- load_runs edge cases --

    def test_load_runs_empty_file(self):
        """load_runs() handles missing/empty file gracefully."""
        # Missing file
        self.assertEqual(log_run.load_runs(), [])
        # Empty file
        runs_path = os.path.join(self.tmpdir, "pipeline-runs.json")
        with open(runs_path, "w") as f:
            f.write("")
        self.assertEqual(log_run.load_runs(), [])

    def test_load_runs_corrupt_json(self):
        """load_runs() returns empty list for corrupt JSON."""
        runs_path = os.path.join(self.tmpdir, "pipeline-runs.json")
        with open(runs_path, "w") as f:
            f.write("{not valid json!!! [[[")
        self.assertEqual(log_run.load_runs(), [])


if __name__ == "__main__":
    unittest.main()
