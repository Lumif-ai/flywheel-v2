"""Tests for flywheel_cli.auth module."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from pathlib import Path
from unittest import mock

import click
import pytest

# Patch config before importing auth so FLYWHEEL_DIR points to temp dir
_tmp = tempfile.mkdtemp()
_PATCH_DIR = Path(_tmp) / ".flywheel"


@pytest.fixture(autouse=True)
def _isolate_credentials(monkeypatch):
    """Redirect credentials to a temp directory for every test."""
    test_dir = Path(tempfile.mkdtemp()) / ".flywheel"
    monkeypatch.setattr("flywheel_cli.config.FLYWHEEL_DIR", test_dir)
    monkeypatch.setattr("flywheel_cli.config.CREDENTIALS_FILE", test_dir / "credentials.json")
    monkeypatch.setattr("flywheel_cli.auth.FLYWHEEL_DIR", test_dir)
    monkeypatch.setattr("flywheel_cli.auth.CREDENTIALS_FILE", test_dir / "credentials.json")
    yield
    # cleanup
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)


from flywheel_cli.auth import (
    clear_credentials,
    get_token,
    is_logged_in,
    load_credentials,
    save_credentials,
)


class TestSaveCredentials:
    def test_creates_file_with_600_permissions(self):
        path = save_credentials("tok_access", "tok_refresh", time.time() + 3600)
        assert path.exists()
        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_content_is_valid_json(self):
        path = save_credentials("a", "r", 999.0)
        data = json.loads(path.read_text())
        assert data["access_token"] == "a"
        assert data["refresh_token"] == "r"
        assert data["expires_at"] == 999.0


class TestLoadCredentials:
    def test_returns_none_for_missing_file(self):
        assert load_credentials() is None

    def test_returns_none_for_malformed_json(self):
        from flywheel_cli.auth import CREDENTIALS_FILE, FLYWHEEL_DIR

        FLYWHEEL_DIR.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text("not json")
        assert load_credentials() is None

    def test_returns_none_for_missing_keys(self):
        from flywheel_cli.auth import CREDENTIALS_FILE, FLYWHEEL_DIR

        FLYWHEEL_DIR.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text(json.dumps({"access_token": "a"}))
        assert load_credentials() is None

    def test_returns_dict_for_valid_creds(self):
        save_credentials("a", "r", 1000.0)
        creds = load_credentials()
        assert creds is not None
        assert creds["access_token"] == "a"


class TestClearCredentials:
    def test_removes_file(self):
        save_credentials("a", "r", 1000.0)
        from flywheel_cli.auth import CREDENTIALS_FILE

        assert CREDENTIALS_FILE.exists()
        clear_credentials()
        assert not CREDENTIALS_FILE.exists()

    def test_no_error_if_file_missing(self):
        clear_credentials()  # Should not raise


class TestGetToken:
    def test_raises_when_not_logged_in(self):
        with pytest.raises(click.ClickException, match="Not logged in"):
            get_token()

    def test_returns_token_if_not_expired(self):
        save_credentials("valid_tok", "ref", time.time() + 3600)
        assert get_token() == "valid_tok"


class TestIsLoggedIn:
    def test_false_when_no_creds(self):
        assert is_logged_in() is False

    def test_true_when_creds_exist(self):
        save_credentials("a", "r", 1000.0)
        assert is_logged_in() is True
