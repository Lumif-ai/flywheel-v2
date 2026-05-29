"""Byte-exact regression tests for the 6 locked user-facing error strings
(Phase 151 Plan 02).

**CRITICAL test-authoring rule** (from plan): every ``test_err_*_string_byte_exact``
test hard-codes the full expected string as a literal on the RHS of ``==``.
Do NOT reference the constant itself — that becomes a tautology and will
pass even if the constant silently drifts, giving a false-green.

Example (CORRECT — catches drift):

    def test_err_401_string_byte_exact():
        assert ERR_401 == "Session expired. Run `flywheel login` and retry."

Example (WRONG — tautology, false-green):

    def test_wrong():
        assert ERR_401 == ERR_401  # always passes

The whole point of these tests is to catch any future drift of the
constants — if the literal RHS doesn't match the constant, the test fails
loudly, which is exactly the protection the plan wants.
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

import httpx
import pytest


# ---------------------------------------------------------------------------
# Credential isolation (same pattern as test_cache.py autouse fixture).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_credentials(monkeypatch):
    """Redirect credentials + stub token retrieval so FlywheelClient() can
    construct in tests without real ``~/.flywheel/credentials.json``."""
    test_dir = Path(tempfile.mkdtemp()) / ".flywheel"
    monkeypatch.setattr("flywheel_cli.config.FLYWHEEL_DIR", test_dir)
    monkeypatch.setattr(
        "flywheel_cli.config.CREDENTIALS_FILE", test_dir / "credentials.json"
    )
    monkeypatch.setattr("flywheel_cli.auth.FLYWHEEL_DIR", test_dir)
    monkeypatch.setattr(
        "flywheel_cli.auth.CREDENTIALS_FILE", test_dir / "credentials.json"
    )
    monkeypatch.setattr(
        "flywheel_mcp.api_client.get_token", lambda: "stub-token"
    )
    yield
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)


# Import AFTER autouse fixture.
from flywheel_mcp.api_client import FlywheelClient  # noqa: E402
from flywheel_mcp.bundle import (  # noqa: E402
    BundleCacheError,
    BundleFetchError,
    BundleIntegrityError,
)
from flywheel_mcp.cache import BundleCache  # noqa: E402
from flywheel_mcp.errors import (  # noqa: E402
    ALL_ERROR_MESSAGES,
    ERR_401,
    ERR_403,
    ERR_404_TEMPLATE,
    ERR_503_RETRY_TEMPLATE,
    ERR_503_TERMINAL,
    ERR_CHECKSUM_TEMPLATE,
    ERR_OFFLINE_EXPIRED,
)


# ===========================================================================
# Layer 1 — byte-exact constant tests (catch drift via literal RHS)
# ===========================================================================


def test_err_401_string_byte_exact():
    """ERR_401 must match CONTEXT §Error taxonomy verbatim."""
    assert ERR_401 == "Session expired. Run `flywheel login` and retry."


def test_err_403_string_byte_exact():
    """ERR_403 must match CONTEXT §Error taxonomy verbatim."""
    assert ERR_403 == "Skill not licensed for your tenant. Contact your admin."


def test_err_404_template_interpolates():
    """ERR_404_TEMPLATE substitutes ``name`` and uses UNDERSCORED form
    ``flywheel_refresh_skills`` (MCP-tool invocation form)."""
    assert (
        ERR_404_TEMPLATE.format(name="broker-x")
        == "Skill not found: broker-x. Check spelling or run `flywheel_refresh_skills`."
    )


def test_err_503_retry_template_interpolates():
    """ERR_503_RETRY_TEMPLATE substitutes ``delay`` and matches CONTEXT."""
    assert (
        ERR_503_RETRY_TEMPLATE.format(delay=0.5)
        == "Flywheel backend unreachable. Retrying in 0.5s..."
    )


def test_err_503_terminal_string_byte_exact():
    """ERR_503_TERMINAL uses UNDERSCORED form ``flywheel_refresh_skills`` per
    CONTEXT (MCP-tool invocation form)."""
    assert ERR_503_TERMINAL == (
        "Flywheel backend unreachable after 3 attempts. "
        "Retry in a moment or run `flywheel_refresh_skills` when online."
    )


def test_err_checksum_template_interpolates():
    """ERR_CHECKSUM_TEMPLATE uses HYPHENATED form ``flywheel refresh-skills``
    per CONTEXT (CLI subcommand form)."""
    assert (
        ERR_CHECKSUM_TEMPLATE.format(skill="broker-parse-contract")
        == "Bundle integrity check failed for broker-parse-contract. "
        "Run `flywheel refresh-skills` to re-fetch."
    )


def test_err_offline_expired_string_byte_exact():
    """ERR_OFFLINE_EXPIRED uses HYPHENATED form ``flywheel refresh-skills``
    per CONTEXT (CLI subcommand form) — user is diagnosing from terminal."""
    assert ERR_OFFLINE_EXPIRED == (
        "Cached bundle expired (>24h) and backend unreachable. "
        "Connect to network and retry, or run `flywheel refresh-skills` when online."
    )


# ===========================================================================
# Layer 2 — invocation-form distinction (CONTEXT deliberately has both forms)
# ===========================================================================


def test_underscored_form_in_404_and_503_terminal():
    """MCP-tool form ``flywheel_refresh_skills`` (underscored) is used where
    the user is in-context inside Claude Code."""
    assert "`flywheel_refresh_skills`" in ERR_404_TEMPLATE.format(name="x")
    assert "`flywheel_refresh_skills`" in ERR_503_TERMINAL
    # And critically NOT the hyphenated form there (mutually exclusive).
    assert "`flywheel refresh-skills`" not in ERR_404_TEMPLATE.format(name="x")
    assert "`flywheel refresh-skills`" not in ERR_503_TERMINAL


def test_hyphenated_form_in_checksum_and_offline_expired():
    """CLI subcommand form ``flywheel refresh-skills`` (hyphenated) is used
    where the user is diagnosing from a terminal."""
    assert "`flywheel refresh-skills`" in ERR_CHECKSUM_TEMPLATE.format(skill="x")
    assert "`flywheel refresh-skills`" in ERR_OFFLINE_EXPIRED
    # And critically NOT the underscored form there.
    assert "`flywheel_refresh_skills`" not in ERR_CHECKSUM_TEMPLATE.format(skill="x")
    assert "`flywheel_refresh_skills`" not in ERR_OFFLINE_EXPIRED


# ===========================================================================
# Layer 3 — parametrized substring sanity (belt-and-suspenders)
# ===========================================================================


@pytest.mark.parametrize("error_id,expected_msg", ALL_ERROR_MESSAGES)
def test_all_error_messages_substring_sanity(error_id, expected_msg):
    """Meta-test: spot-check the user-facing action phrases are present.

    Catches accidental string drift where someone renames a command (e.g.,
    ``flywheel login`` → ``flywheel auth login``) and forgets to update.
    """
    assert isinstance(expected_msg, str)
    assert len(expected_msg) > 0, f"{error_id}: empty message"
    if error_id == "401":
        assert "`flywheel login`" in expected_msg
    elif error_id == "403":
        assert "admin" in expected_msg.lower()
    elif error_id == "404":
        assert "`flywheel_refresh_skills`" in expected_msg
        # Name must have been interpolated (no literal `{name}` left behind).
        assert "{" not in expected_msg
    elif error_id == "503_retry":
        assert "Retrying" in expected_msg
        assert "{" not in expected_msg
    elif error_id == "503_terminal":
        assert "3 attempts" in expected_msg
        assert "`flywheel_refresh_skills`" in expected_msg
    elif error_id == "checksum":
        assert "integrity" in expected_msg
        assert "`flywheel refresh-skills`" in expected_msg
        assert "{" not in expected_msg
    elif error_id == "offline_expired":
        assert ">24h" in expected_msg
        assert "`flywheel refresh-skills`" in expected_msg


# ===========================================================================
# Layer 4 — integration: raise-site paths actually produce these messages
# ===========================================================================


def _build_deterministic_bundle(payload: bytes) -> tuple[bytes, str]:
    """Build a small in-memory zip with ``payload`` at ``file.txt``."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("file.txt", payload)
    data = buf.getvalue()
    return data, hashlib.sha256(data).hexdigest()


def _make_chain(skill_name: str) -> tuple[dict, list]:
    """Minimal (metadata, bundles) chain — one bundle, no deps."""
    con_bytes, con_sha = _build_deterministic_bundle(
        f"consumer-{skill_name}".encode()
    )
    bundles = [(skill_name, con_sha, con_bytes)]
    rollup = hashlib.sha256(
        "\n".join(f"{n}:{s}" for n, s, _ in bundles).encode("ascii")
    ).hexdigest()
    metadata = {
        "skill": skill_name,
        "deps": [],
        "rollup_sha": rollup,
        "version": "1.0.0",
    }
    return metadata, bundles


def _fake_response(status_code: int, body: dict | None = None):
    """Build a mock httpx.Response with given status + body."""
    resp = mock.MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json = mock.MagicMock(return_value=body or {})
    resp.text = json.dumps(body) if body else ""
    return resp


def test_401_terminal_raise_uses_locked_message(monkeypatch):
    """Two consecutive 401s (original + post-refresh) → BundleFetchError(ERR_401)."""
    client = FlywheelClient()
    # Both GETs return 401 — one-shot refresh path exhausted.
    client._client.get = mock.MagicMock(return_value=_fake_response(401))
    # clear_credentials would try to delete a file — stub it out.
    monkeypatch.setattr(
        "flywheel_mcp.api_client.clear_credentials", lambda: None
    )
    with pytest.raises(BundleFetchError) as exc_info:
        client.fetch_skill_assets_bundle("any-skill", bypass_cache=True)
    # Locked copy appears verbatim in the exception __str__.
    assert ERR_401 in str(exc_info.value)


def test_403_raise_uses_locked_message():
    """403 → fail-fast BundleFetchError(ERR_403)."""
    client = FlywheelClient()
    client._client.get = mock.MagicMock(return_value=_fake_response(403))
    with pytest.raises(BundleFetchError) as exc_info:
        client.fetch_skill_assets_bundle("protected-skill", bypass_cache=True)
    assert ERR_403 in str(exc_info.value)


def test_404_raise_uses_locked_message_with_name():
    """404 → BundleFetchError with {name} interpolated + UNDERSCORED form hint."""
    client = FlywheelClient()
    client._client.get = mock.MagicMock(return_value=_fake_response(404))
    with pytest.raises(BundleFetchError) as exc_info:
        client.fetch_skill_assets_bundle("typo-skill", bypass_cache=True)
    msg = str(exc_info.value)
    assert "typo-skill" in msg
    # Must include the UNDERSCORED MCP-tool form.
    assert "`flywheel_refresh_skills`" in msg


def test_503_terminal_after_3_retries_uses_locked_message(
    monkeypatch, capsys
):
    """3x ConnectError → BundleFetchError(ERR_503_TERMINAL) + retry stderr lines."""
    client = FlywheelClient()
    client._client.get = mock.MagicMock(
        side_effect=httpx.ConnectError("refused")
    )
    # Skip real sleep.
    monkeypatch.setattr("flywheel_mcp.api_client.time.sleep", lambda _: None)
    with pytest.raises(BundleFetchError) as exc_info:
        client.fetch_skill_assets_bundle(
            "any-skill", bypass_cache=True
        )
    msg = str(exc_info.value)
    assert ERR_503_TERMINAL in msg
    # 3 retry stderr lines with locked copy (delays 0.5s, 1.0s, 2.0s).
    err = capsys.readouterr().err
    for delay in (0.5, 1.0, 2.0):
        assert ERR_503_RETRY_TEMPLATE.format(delay=delay) in err


def test_checksum_raise_uses_locked_message(tmp_path):
    """Tampered cache entry → BundleIntegrityError with ERR_CHECKSUM_TEMPLATE."""
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("broker-parse-contract")
    cache.put(
        "broker-parse-contract", metadata, bundles, correlation_id="cksum001"
    )

    # Flip one byte to force SHA mismatch.
    _name, sha, _byts = bundles[0]
    bp = tmp_path / sha / "bundle.zip"
    ba = bytearray(bp.read_bytes())
    ba[0] ^= 0xFF
    bp.write_bytes(bytes(ba))

    with pytest.raises(BundleIntegrityError) as exc_info:
        cache.get_fresh("broker-parse-contract")
    expected = ERR_CHECKSUM_TEMPLATE.format(skill="broker-parse-contract")
    assert str(exc_info.value) == expected


def test_offline_expired_raise_uses_locked_message(tmp_path, monkeypatch):
    """Offline simulation + cache trace but unusable → BundleCacheError(ERR_OFFLINE_EXPIRED)."""
    # Point default cache dir at tmp_path so FlywheelClient picks it up.
    monkeypatch.setattr("flywheel_mcp.cache._DEFAULT_CACHE_DIR", tmp_path)

    # Populate cache then delete bundle bytes — simulates "had cache, now unusable".
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("expired-skill")
    cache.put("expired-skill", metadata, bundles, correlation_id="offln001")
    for pb in json.loads((tmp_path / "index.json").read_text())[
        "expired-skill"
    ]["per_bundle"]:
        (tmp_path / pb["sha"] / "bundle.zip").unlink(missing_ok=True)

    # Point FLYWHEEL_API_URL at a RST-ing port so ConnectError fires.
    monkeypatch.setenv("FLYWHEEL_API_URL", "http://127.0.0.1:1")
    client = FlywheelClient()
    client._client.get = mock.MagicMock(
        side_effect=httpx.ConnectError("connection refused (simulated)")
    )
    monkeypatch.setattr("flywheel_mcp.api_client.time.sleep", lambda _: None)

    with pytest.raises(BundleCacheError) as exc_info:
        client.fetch_skill_assets_bundle("expired-skill")
    # Locked message appears in exception __str__ verbatim.
    assert ERR_OFFLINE_EXPIRED in str(exc_info.value)


# ===========================================================================
# Layer 5 — the constants collection is coherent (no drift between table
# and individual constants)
# ===========================================================================


def test_all_error_messages_matches_individual_constants():
    """ALL_ERROR_MESSAGES values match the individual constants (no drift
    between the list and module-level names)."""
    lookup = dict(ALL_ERROR_MESSAGES)
    assert lookup["401"] == ERR_401
    assert lookup["403"] == ERR_403
    assert lookup["404"] == ERR_404_TEMPLATE.format(name="broker-parse-contract")
    assert lookup["503_retry"] == ERR_503_RETRY_TEMPLATE.format(delay=0.5)
    assert lookup["503_terminal"] == ERR_503_TERMINAL
    assert lookup["checksum"] == ERR_CHECKSUM_TEMPLATE.format(
        skill="broker-parse-contract"
    )
    assert lookup["offline_expired"] == ERR_OFFLINE_EXPIRED


def test_all_error_messages_has_seven_entries():
    """Phase 151 CONTEXT lists 6 classes but 503 has retry + terminal, so 7."""
    assert len(ALL_ERROR_MESSAGES) == 7
    ids = [e[0] for e in ALL_ERROR_MESSAGES]
    assert set(ids) == {
        "401", "403", "404", "503_retry", "503_terminal",
        "checksum", "offline_expired",
    }
