"""Hermetic unit tests for ``flywheel_refresh_skills`` MCP tool +
offline-simulation behavior (Phase 151 Plan 02).

No network, no real ``~/.cache/`` writes — every test uses ``tmp_path``.
Every FlywheelClient under test has its ``_client.get`` patched to either
a controlled mock response or a ``httpx.ConnectError`` sentinel.

Tests:
    1. test_refresh_no_arg_walks_all_cached_skills
    2. test_refresh_with_name_targets_single_skill
    3. test_refresh_empty_cache_noop
    4. test_refresh_tampered_entry_auto_heal
    5. test_refresh_per_skill_dict_shape
    6. test_refresh_stderr_summary_format
    7. test_refresh_per_skill_stderr_shorter_format
    8. test_refresh_backend_down_propagates_error
    9. test_offline_simulation_fresh_cache_serves_cached_bundle
   10. test_offline_simulation_expired_cache_raises_locked_error
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

import httpx
import pytest


# ---------------------------------------------------------------------------
# Credential isolation (autouse — mirrors test_cache.py + test_error_messages.py).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_credentials(monkeypatch):
    """Redirect credentials + stub token retrieval."""
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


# Import after autouse fixture.
from flywheel_mcp.api_client import FlywheelClient  # noqa: E402
from flywheel_mcp.bundle import BundleCacheError, BundleFetchError  # noqa: E402
from flywheel_mcp.cache import BundleCache  # noqa: E402
from flywheel_mcp.errors import ERR_OFFLINE_EXPIRED  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_deterministic_bundle(payload: bytes) -> tuple[bytes, str]:
    """Build a small in-memory zip with ``payload`` at ``file.txt``."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("file.txt", payload)
    data = buf.getvalue()
    return data, hashlib.sha256(data).hexdigest()


def _make_chain(skill_name: str) -> tuple[dict, list]:
    """Minimal ``(metadata, bundles)`` chain — one bundle, no deps."""
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


def _fake_ok_response(metadata: dict, bundles: list):
    """Mock httpx.Response for a full fetch success."""
    body = {
        "skill": metadata["skill"],
        "deps": metadata.get("deps", []),
        "rollup_sha": metadata["rollup_sha"],
        "bundles": [
            {
                "name": n,
                "sha256": s,
                "size": len(b),
                "format": "zip",
                "version": metadata.get("version"),
                "updated_at": None,
                "bundle_b64": base64.b64encode(b).decode("ascii"),
            }
            for n, s, b in bundles
        ],
    }
    resp = mock.MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json = mock.MagicMock(return_value=body)
    return resp


@pytest.fixture
def _patched_cache_dir(tmp_path, monkeypatch):
    """Point BundleCache()'s default dir at tmp_path — zero chance of hitting real disk."""
    monkeypatch.setattr("flywheel_mcp.cache._DEFAULT_CACHE_DIR", tmp_path)
    yield tmp_path


# ===========================================================================
# Test 1: No-arg refresh walks every cached skill
# ===========================================================================


def test_refresh_no_arg_walks_all_cached_skills(_patched_cache_dir):
    """Populate 3 skills, call ``flywheel_refresh_skills()`` — fetcher called 3x."""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)

    # Put 3 skills in the cache.
    chains = {}
    for i, name in enumerate(("sk-a", "sk-b", "sk-c")):
        metadata, bundles = _make_chain(name)
        cache.put(name, metadata, bundles, correlation_id=f"ref00{i:03d}")
        chains[name] = (metadata, bundles)

    # Import the tool AFTER monkeypatching the default cache dir so its
    # internal BundleCache() pick it up.
    from flywheel_mcp.server import flywheel_refresh_skills

    calls = []

    def _mock_get(url, headers=None):
        calls.append(url)
        # Extract skill name from URL path.
        m = re.search(r"/skills/([^/]+)/assets/bundle", url)
        sname = m.group(1) if m else "?"
        metadata, bundles = chains[sname]
        return _fake_ok_response(metadata, bundles)

    # Patch FlywheelClient instances globally — every new() returns a client
    # whose _client.get is our mock.
    _original_init = FlywheelClient.__init__

    def _init(self):
        _original_init(self)
        self._client.get = mock.MagicMock(side_effect=_mock_get)

    with mock.patch.object(FlywheelClient, "__init__", _init):
        # Call the tool (FastMCP wraps decorated tools — we can call .fn if
        # present, otherwise the tool object itself is callable).
        tool = flywheel_refresh_skills
        result = tool.fn(name=None) if hasattr(tool, "fn") else tool(name=None)

    sc = result.structured_content
    assert sc["refetched"] == 3, f"Expected 3 refetched, got {sc}"
    assert sc["tampered"] == 0
    # All 3 skill names appear in per_skill.
    names = {e["name"] for e in sc["per_skill"]}
    assert names == {"sk-a", "sk-b", "sk-c"}
    # Exactly 3 GETs (one per skill, no shas_only probes since bypass_cache=True).
    assert len(calls) == 3, calls


# ===========================================================================
# Test 2: With-name targets single skill
# ===========================================================================


def test_refresh_with_name_targets_single_skill(_patched_cache_dir):
    """Populate 3 skills, refresh one — only that one hits the network."""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)

    chains = {}
    for i, name in enumerate(("broker-parse-contract", "sk-b", "sk-c")):
        metadata, bundles = _make_chain(name)
        cache.put(name, metadata, bundles, correlation_id=f"tgt00{i:03d}")
        chains[name] = (metadata, bundles)

    from flywheel_mcp.server import flywheel_refresh_skills

    calls = []

    def _mock_get(url, headers=None):
        calls.append(url)
        m = re.search(r"/skills/([^/]+)/assets/bundle", url)
        sname = m.group(1) if m else "?"
        metadata, bundles = chains[sname]
        return _fake_ok_response(metadata, bundles)

    _original_init = FlywheelClient.__init__

    def _init(self):
        _original_init(self)
        self._client.get = mock.MagicMock(side_effect=_mock_get)

    with mock.patch.object(FlywheelClient, "__init__", _init):
        tool = flywheel_refresh_skills
        result = (
            tool.fn(name="broker-parse-contract")
            if hasattr(tool, "fn")
            else tool(name="broker-parse-contract")
        )

    sc = result.structured_content
    assert sc["refetched"] == 1
    assert [e["name"] for e in sc["per_skill"]] == ["broker-parse-contract"]
    # Only one GET.
    assert len(calls) == 1
    assert "broker-parse-contract" in calls[0]


# ===========================================================================
# Test 3: Empty cache is a no-op
# ===========================================================================


def test_refresh_empty_cache_noop(_patched_cache_dir):
    """No cached skills + no-arg refresh → refetched=0, tampered=0, no fetcher calls."""
    from flywheel_mcp.server import flywheel_refresh_skills

    calls = []

    def _mock_get(url, headers=None):
        calls.append(url)
        raise AssertionError(f"Unexpected GET: {url}")

    _original_init = FlywheelClient.__init__

    def _init(self):
        _original_init(self)
        self._client.get = mock.MagicMock(side_effect=_mock_get)

    with mock.patch.object(FlywheelClient, "__init__", _init):
        tool = flywheel_refresh_skills
        result = tool.fn(name=None) if hasattr(tool, "fn") else tool(name=None)

    sc = result.structured_content
    assert sc["refetched"] == 0
    assert sc["evicted"] == 0
    assert sc["tampered"] == 0
    assert sc["per_skill"] == []
    assert calls == []


# ===========================================================================
# Test 4: Tampered entry auto-heal (SC4)
# ===========================================================================


def test_refresh_tampered_entry_auto_heal(_patched_cache_dir, capsys):
    """Flip a byte → refresh detects tamper, auto-deletes dir, refetches, emits stderr line."""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)

    # Populate broker-parse-contract.
    metadata, bundles = _make_chain("broker-parse-contract")
    cache.put("broker-parse-contract", metadata, bundles, correlation_id="tmp00001")
    _name, old_sha, _byts = bundles[0]
    assert (tmp_path / old_sha).exists()

    # Tamper: flip one byte of the bundle.zip.
    bp = tmp_path / old_sha / "bundle.zip"
    ba = bytearray(bp.read_bytes())
    ba[0] ^= 0xFF
    bp.write_bytes(bytes(ba))

    # Build NEW authoritative bundle bytes — refetch will deliver these.
    new_bytes, new_sha = _build_deterministic_bundle(b"authoritative-bytes")
    new_bundles = [("broker-parse-contract", new_sha, new_bytes)]
    new_metadata = {
        "skill": "broker-parse-contract",
        "deps": [],
        "rollup_sha": hashlib.sha256(
            f"broker-parse-contract:{new_sha}".encode()
        ).hexdigest(),
        "version": "1.1.0",
    }

    from flywheel_mcp.server import flywheel_refresh_skills

    def _mock_get(url, headers=None):
        return _fake_ok_response(new_metadata, new_bundles)

    _original_init = FlywheelClient.__init__

    def _init(self):
        _original_init(self)
        self._client.get = mock.MagicMock(side_effect=_mock_get)

    with mock.patch.object(FlywheelClient, "__init__", _init):
        tool = flywheel_refresh_skills
        result = (
            tool.fn(name="broker-parse-contract")
            if hasattr(tool, "fn")
            else tool(name="broker-parse-contract")
        )

    sc = result.structured_content
    assert sc["tampered"] == 1
    assert sc["refetched"] == 1
    # per_skill entry for the tampered skill records the heal.
    entry = sc["per_skill"][0]
    assert entry["name"] == "broker-parse-contract"
    assert entry["status"] == "tampered-healed"
    assert entry["new_sha"] != ""

    # Old tampered dir is GONE.
    assert not (tmp_path / old_sha).exists(), "Tampered dir should be auto-deleted"
    # New dir exists with authoritative bytes.
    assert (tmp_path / new_sha / "bundle.zip").exists()
    assert (tmp_path / new_sha / "bundle.zip").read_bytes() == new_bytes

    # Stderr has the cache_entry_tampered line with all 4 fields.
    err = capsys.readouterr().err
    assert "cache_entry_tampered:" in err
    assert "skill=broker-parse-contract" in err
    # old_sha= should carry 8+ hex chars from the tampered (expected) sha.
    m = re.search(
        r"cache_entry_tampered: skill=broker-parse-contract "
        r"old_sha=([0-9a-f]{8,}) "
        r"authoritative_sha=([0-9a-f]{8,}) "
        r"correlation_id=(\S+)",
        err,
    )
    assert m is not None, f"Tamper line not in expected shape; got: {err!r}"


# ===========================================================================
# Test 5: per_skill dict shape
# ===========================================================================


def test_refresh_per_skill_dict_shape(_patched_cache_dir):
    """ToolResult.structured_content.per_skill is list of dicts with required keys."""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("shape-test")
    cache.put("shape-test", metadata, bundles, correlation_id="shape001")

    from flywheel_mcp.server import flywheel_refresh_skills

    def _mock_get(url, headers=None):
        return _fake_ok_response(metadata, bundles)

    _original_init = FlywheelClient.__init__

    def _init(self):
        _original_init(self)
        self._client.get = mock.MagicMock(side_effect=_mock_get)

    with mock.patch.object(FlywheelClient, "__init__", _init):
        tool = flywheel_refresh_skills
        result = tool.fn(name=None) if hasattr(tool, "fn") else tool(name=None)

    per_skill = result.structured_content["per_skill"]
    assert isinstance(per_skill, list)
    assert len(per_skill) >= 1
    required_keys = {"name", "old_sha", "new_sha", "status"}
    for entry in per_skill:
        assert isinstance(entry, dict)
        assert required_keys.issubset(entry.keys()), (
            f"Missing keys: {required_keys - set(entry.keys())}"
        )
        # Status is a known string.
        assert entry["status"] in {
            "refreshed", "unchanged", "new", "tampered-healed", "tampered",
        } or entry["status"].startswith("error:")


# ===========================================================================
# Test 6: Stderr summary format (all-refresh)
# ===========================================================================


def test_refresh_stderr_summary_format(_patched_cache_dir, capsys):
    """No-arg refresh emits ``OK: Refreshed N skills (M evicted, K tampered-auto-healed).``"""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)
    for i, name in enumerate(("fmt-a", "fmt-b")):
        metadata, bundles = _make_chain(name)
        cache.put(name, metadata, bundles, correlation_id=f"fmt{i:04d}")

    from flywheel_mcp.server import flywheel_refresh_skills

    _original_init = FlywheelClient.__init__

    def _init(self):
        _original_init(self)
        # Return a body per-skill based on URL.
        def _mock_get(url, headers=None):
            m = re.search(r"/skills/([^/]+)/assets/bundle", url)
            sname = m.group(1)
            metadata, bundles = _make_chain(sname)
            return _fake_ok_response(metadata, bundles)

        self._client.get = mock.MagicMock(side_effect=_mock_get)

    with mock.patch.object(FlywheelClient, "__init__", _init):
        tool = flywheel_refresh_skills
        tool.fn(name=None) if hasattr(tool, "fn") else tool(name=None)

    err = capsys.readouterr().err
    # Locked format: "OK: Refreshed N skills (M evicted, K tampered-auto-healed)."
    m = re.search(
        r"OK: Refreshed \d+ skills \(\d+ evicted, \d+ tampered-auto-healed\)\.",
        err,
    )
    assert m is not None, f"Expected summary line; got {err!r}"


# ===========================================================================
# Test 7: Stderr summary format (per-skill)
# ===========================================================================


def test_refresh_per_skill_stderr_shorter_format(_patched_cache_dir, capsys):
    """Named refresh emits ``OK: Refreshed <skill>.``"""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("per-fmt")
    cache.put("per-fmt", metadata, bundles, correlation_id="pfmt0001")

    from flywheel_mcp.server import flywheel_refresh_skills

    _original_init = FlywheelClient.__init__

    def _init(self):
        _original_init(self)
        self._client.get = mock.MagicMock(
            side_effect=lambda url, headers=None: _fake_ok_response(
                metadata, bundles
            )
        )

    with mock.patch.object(FlywheelClient, "__init__", _init):
        tool = flywheel_refresh_skills
        tool.fn(name="per-fmt") if hasattr(tool, "fn") else tool(name="per-fmt")

    err = capsys.readouterr().err
    assert re.search(r"OK: Refreshed per-fmt\.", err), (
        f"Expected short summary; got {err!r}"
    )


# ===========================================================================
# Test 8: Backend down propagates (no silent "0 refreshed")
# ===========================================================================


def test_refresh_backend_down_propagates_error(_patched_cache_dir, monkeypatch):
    """Fetcher raises BundleFetchError → per_skill status starts with ``error:``."""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("down-skill")
    cache.put("down-skill", metadata, bundles, correlation_id="down0001")

    from flywheel_mcp.server import flywheel_refresh_skills

    _original_init = FlywheelClient.__init__

    def _init(self):
        _original_init(self)
        self._client.get = mock.MagicMock(
            side_effect=httpx.ConnectError("simulated network down")
        )

    # Skip real sleep in the retry loop.
    monkeypatch.setattr("flywheel_mcp.api_client.time.sleep", lambda _: None)

    with mock.patch.object(FlywheelClient, "__init__", _init):
        tool = flywheel_refresh_skills
        result = tool.fn(name=None) if hasattr(tool, "fn") else tool(name=None)

    # With bypass_cache=True, ConnectError path raises BundleFetchError
    # (no cache trace check — bypass_cache skips that). cache.refresh()
    # catches it at the Exception boundary and records status="error: ...".
    sc = result.structured_content
    assert sc["refetched"] == 0
    assert len(sc["per_skill"]) == 1
    assert sc["per_skill"][0]["status"].startswith("error:"), sc["per_skill"]


# ===========================================================================
# Test 9: Offline sim + fresh cache → WARN + serve (does NOT use refresh tool)
# ===========================================================================


def test_offline_simulation_fresh_cache_serves_cached_bundle(
    _patched_cache_dir, capsys, monkeypatch
):
    """FLYWHEEL_API_URL=http://127.0.0.1:1 + stale cache → WARN + serve.

    Note: a FRESH cache hit returns BEFORE any network call is attempted,
    so no WARN fires. The stale-cache path is what exercises the offline-
    fallback-with-WARN behavior. We exercise the stale path by setting
    ``cached_at`` to an old timestamp so ``get_fresh`` returns None but
    ``get_stale`` still finds the bundle.
    """
    tmp_path = _patched_cache_dir
    monkeypatch.setenv("FLYWHEEL_API_URL", "http://127.0.0.1:1")

    import time as _time

    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("offline-sim")
    # Use a very old cached_at so the entry is stale (not fresh) but the
    # bundle bytes are still loadable for the offline fallback path.
    with mock.patch("flywheel_mcp.cache.time.time", return_value=0.0):
        cache.put(
            "offline-sim", metadata, bundles, correlation_id="off00001"
        )
    # Sanity: stale, loadable.
    assert cache.get_fresh("offline-sim") is None
    assert cache.has_stale("offline-sim") is True

    client = FlywheelClient()
    client._client.get = mock.MagicMock(
        side_effect=httpx.ConnectError("RST (simulated offline)")
    )
    monkeypatch.setattr("flywheel_mcp.api_client.time.sleep", lambda _: None)

    got_meta, got_bundles = client.fetch_skill_assets_bundle("offline-sim")
    # Cached bytes served byte-identically.
    assert got_bundles == bundles

    err = capsys.readouterr().err
    assert "WARN: Backend unreachable. Using cached" in err
    assert "offline-sim" in err


# ===========================================================================
# Test 10: Offline sim + expired cache → BundleCacheError(ERR_OFFLINE_EXPIRED)
# ===========================================================================


def test_offline_simulation_expired_cache_raises_locked_error(
    _patched_cache_dir, monkeypatch
):
    """FLYWHEEL_API_URL=http://127.0.0.1:1 + unusable cache → BundleCacheError.

    "Unusable" here means: index has an entry (so ``_has_any_cache_trace``
    returns True) but the underlying bundle bytes are gone — get_stale
    returns None. This is the strictest form of "offline + expired" and
    the locked ``ERR_OFFLINE_EXPIRED`` must fire verbatim.
    """
    tmp_path = _patched_cache_dir
    monkeypatch.setenv("FLYWHEEL_API_URL", "http://127.0.0.1:1")

    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("expired-sim")
    with mock.patch("flywheel_mcp.cache.time.time", return_value=0.0):
        cache.put(
            "expired-sim", metadata, bundles, correlation_id="exp00001"
        )
    # Delete bundle bytes so get_stale returns None (but index entry remains).
    idx = json.loads((tmp_path / "index.json").read_text())
    for pb in idx["expired-sim"]["per_bundle"]:
        (tmp_path / pb["sha"] / "bundle.zip").unlink(missing_ok=True)

    client = FlywheelClient()
    client._client.get = mock.MagicMock(
        side_effect=httpx.ConnectError("RST (simulated offline)")
    )
    monkeypatch.setattr("flywheel_mcp.api_client.time.sleep", lambda _: None)

    with pytest.raises(BundleCacheError) as exc_info:
        client.fetch_skill_assets_bundle("expired-sim")
    # Exact locked copy appears in exception __str__ verbatim.
    assert ERR_OFFLINE_EXPIRED in str(exc_info.value)
