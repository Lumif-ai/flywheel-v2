"""Tests for flywheel_cli.main CLI commands."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from flywheel_cli.main import cli


@pytest.fixture(autouse=True)
def _isolate_credentials(monkeypatch):
    """Redirect credentials to a temp directory for every test."""
    test_dir = Path(tempfile.mkdtemp()) / ".flywheel"
    monkeypatch.setattr("flywheel_cli.config.FLYWHEEL_DIR", test_dir)
    monkeypatch.setattr("flywheel_cli.config.CREDENTIALS_FILE", test_dir / "credentials.json")
    monkeypatch.setattr("flywheel_cli.auth.FLYWHEEL_DIR", test_dir)
    monkeypatch.setattr("flywheel_cli.auth.CREDENTIALS_FILE", test_dir / "credentials.json")
    yield
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)


class TestLogoutCommand:
    def test_logout_removes_credentials(self):
        from flywheel_cli.auth import save_credentials, CREDENTIALS_FILE

        save_credentials("a", "r", time.time() + 3600)
        assert CREDENTIALS_FILE.exists()

        runner = CliRunner()
        result = runner.invoke(cli, ["logout"])
        assert result.exit_code == 0
        assert "Logged out" in result.output
        assert not CREDENTIALS_FILE.exists()


class TestStatusCommand:
    def test_status_not_logged_in(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Not logged in" in result.output


class TestHelpOutput:
    def test_help_shows_all_commands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "login" in result.output
        assert "status" in result.output
        assert "logout" in result.output

    def test_login_help_shows_headless(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["login", "--help"])
        assert result.exit_code == 0
        assert "--headless" in result.output
