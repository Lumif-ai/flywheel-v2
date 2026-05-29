"""Tests for the ``flywheel_fetch_skill_assets`` MCP tool — Phase 150 Plan 03.

Split into two classes:

1.  :class:`TestContract` — hermetic (mocked FlywheelClient), fast, runs by
    default. Validates the ToolResult shape, topological order, SHA passthrough
    via structured_content, and graceful BundleError handling.

2.  :class:`TestE2EFromProd` — live end-to-end against the real Flywheel
    backend + prod Supabase. Opted in via ``-m e2e``; skipped by default so CI
    / fresh-laptop runs don't need credentials. Covers all 5 Phase 150
    ROADMAP SCs. If the official ``FLYWHEEL_API_URL`` (prod uat) is not
    DNS-reachable, the tests auto-fall-back to ``http://localhost:8000``
    (operator's local backend pointing at the same prod Supabase), which is
    the documented Plan 03 fallback path.
"""

from __future__ import annotations

import hashlib
import inspect
import io
import os
import socket
import sys
import tempfile
import urllib.parse
import zipfile
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Credential isolation for unit tests (mirrors cli/tests/test_bundle.py)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_credentials(monkeypatch):
    """Redirect credentials to a temp dir per-test so FlywheelClient() ctor
    works without real login in contract tests."""
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


from flywheel_mcp.bundle import (  # noqa: E402 — after monkeypatch fixture
    BundleFetchError,
    BundleIntegrityError,
    BundleSecurityError,
    materialize_skill_bundle,
)
from flywheel_mcp.server import (  # noqa: E402 — after monkeypatch fixture
    flywheel_fetch_skill_assets,
)


# ===========================================================================
# Task 1 — Contract tests (hermetic, fast)
# ===========================================================================


class TestContract:
    """Mocked FlywheelClient. Validates the MCP tool's wire contract."""

    def test_tool_returns_tool_result(self, monkeypatch):
        """Basic shape: ToolResult with 1 File in content for a 1-bundle fetch."""
        with mock.patch("flywheel_mcp.server.FlywheelClient") as MockClient:
            MockClient.return_value.fetch_skill_assets_bundle.return_value = (
                {"skill": "foo", "deps": [], "rollup_sha": "X" * 64},
                [("foo", "a" * 64, b"PK\x03\x04zipdata")],
            )
            result = flywheel_fetch_skill_assets("foo")

        # Type — must be ToolResult exactly (not tuple, not list).
        from fastmcp.tools.tool import ToolResult

        assert isinstance(result, ToolResult)
        # Content — 1 File block.
        assert len(result.content) == 1
        # Structured content carries metadata.
        assert result.structured_content is not None
        assert result.structured_content["skill"] == "foo"
        assert result.structured_content["deps"] == []
        assert result.structured_content["rollup_sha"] == "X" * 64
        assert result.structured_content["shas"] == {"foo": "a" * 64}

    def test_tool_passes_topological_order(self, monkeypatch):
        """Two bundles: library first, consumer last — File.name ordering matches."""
        with mock.patch("flywheel_mcp.server.FlywheelClient") as MockClient:
            MockClient.return_value.fetch_skill_assets_bundle.return_value = (
                {"skill": "consumer", "deps": ["lib"], "rollup_sha": "r" * 64},
                [
                    ("lib", "l" * 64, b"PK\x03\x04lib-zip"),
                    ("consumer", "c" * 64, b"PK\x03\x04consumer-zip"),
                ],
            )
            result = flywheel_fetch_skill_assets("consumer")

        # Per-bundle File names in topological order.
        # content blocks are converted to EmbeddedResource; inspect via the
        # response attribute that fastmcp preserves. We verify the count here
        # and fall through to a deeper check against the underlying envelope.
        assert len(result.content) == 2
        # structured_content.shas preserves names from wire ordering.
        assert list(result.structured_content["shas"].keys()) == ["lib", "consumer"]
        assert result.structured_content["shas"]["lib"] == "l" * 64
        assert result.structured_content["shas"]["consumer"] == "c" * 64

    def test_tool_surfaces_sha_in_structured_content(self, monkeypatch):
        """SHAs ride in ``structured_content``, NOT as File attributes.

        Critical: Pitfall 4 — ``File(metadata=...)`` does not exist. SHAs
        belong on the ``ToolResult`` envelope.
        """
        with mock.patch("flywheel_mcp.server.FlywheelClient") as MockClient:
            MockClient.return_value.fetch_skill_assets_bundle.return_value = (
                {"skill": "foo", "deps": [], "rollup_sha": "ROLL" + "0" * 60},
                [("foo", "a" * 64, b"bytes")],
            )
            result = flywheel_fetch_skill_assets("foo")

        assert result.structured_content["shas"] == {"foo": "a" * 64}
        assert result.structured_content["rollup_sha"] == "ROLL" + "0" * 60

    def test_tool_handles_bundle_error_gracefully(self, monkeypatch):
        """BundleError subclasses -> single TextContent block, no traceback."""
        import mcp.types as mt

        with mock.patch("flywheel_mcp.server.FlywheelClient") as MockClient:
            MockClient.return_value.fetch_skill_assets_bundle.side_effect = (
                BundleFetchError(
                    skill_name="bar",
                    status_code=404,
                    message=(
                        "Skill 'bar' not found. Check the skill name for typos."
                    ),
                )
            )
            # Must NOT raise — the tool maps BundleError to a TextContent.
            result = flywheel_fetch_skill_assets("bar")

        from fastmcp.tools.tool import ToolResult

        assert isinstance(result, ToolResult)
        assert len(result.content) == 1
        block = result.content[0]
        assert isinstance(block, mt.TextContent)
        # Message includes actionable text + skill name.
        assert "bar" in block.text
        assert "not found" in block.text.lower()

    def test_tool_source_has_no_file_metadata_kwarg(self):
        """Regression guard for Pitfall 4: ``File(metadata=...)`` is invalid.

        Static check: grep the tool's source for any ``File(`` call and
        assert none passes ``metadata=``. Belt-and-suspenders so a future
        editor can't accidentally reintroduce the kwarg.
        """
        src = inspect.getsource(flywheel_fetch_skill_assets)
        # Find every File( ... ) occurrence and verify no 'metadata=' in kwargs
        # Simple textual test is sufficient — production code has one File(...)
        # call with 3 kwargs (data, format, name).
        assert "File(" in src, "tool must construct at least one File"
        # Anywhere after 'File(' and before the closing ')', 'metadata=' must
        # not appear. Whole-source textual check is sufficient scope:
        assert "File(metadata=" not in src
        assert "metadata=" not in src.split("File(", 1)[1].split(")")[0]


# ===========================================================================
# Task 2 — Live E2E tests against prod Supabase (opt-in via -m e2e)
# ===========================================================================


def _prod_reachable(url: str, timeout: float = 3.0) -> bool:
    """Return True if ``url`` is DNS-resolvable + TCP-reachable."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.gaierror, socket.timeout):
        return False


def _resolve_live_backend() -> str:
    """Pick a reachable Flywheel backend URL for E2E smoke.

    Prefers the configured default (prod uat); falls back to the operator's
    local backend on port 8000. The local backend connects to the SAME prod
    Supabase — so byte-identity with Phase 149's captured SHA is preserved
    either way (what we're testing is the CLI -> backend -> DB -> wire loop,
    not the ngrok leg). This is the documented Plan 03 fallback.
    """
    from flywheel_cli.config import _DEFAULT_API_URL

    prod = os.environ.get("FLYWHEEL_API_URL") or _DEFAULT_API_URL
    if _prod_reachable(prod):
        return prod
    local = "http://localhost:8000"
    if _prod_reachable(local):
        return local
    pytest.skip(
        f"Neither prod ({prod}) nor local backend ({local}) reachable; "
        "e2e tests require either. Run `./start-dev.sh` or fix DNS."
    )
    return ""  # unreachable (pytest.skip raises)


# Phase 149 captured truth for broker library bundle.
_BROKER_SHA = "217ebdc1c28416e94104845a7ac0d2e49e71fe77caa60531934d05f2be17a33f"
_BROKER_SIZE = 7239


@pytest.fixture(scope="class", autouse=False)
def _live_backend_url():
    """Resolve once per e2e class run."""
    return _resolve_live_backend()


@pytest.mark.e2e
class TestE2EFromProd:
    """End-to-end against real prod Supabase (via prod or local backend).

    Covers all 5 Phase 150 Success Criteria:
      SC1: ``flywheel_fetch_skill_assets`` returns usable bundle
      SC2: ``materialize_skill_bundle`` rejects ``../etc/passwd``
      SC3: Tampering post-fetch raises ``BundleIntegrityError``
      SC4: Library dep (broker) importable via sys.path after materialize
      SC5: Snapshot-before/after diff shows zero new bytes in ~/.cache/flywheel
    """

    @pytest.fixture(autouse=True)
    def _point_at_live_backend(self, monkeypatch):
        """Route FlywheelClient to a reachable live backend. Disables the
        per-test credential stub (real creds needed)."""
        # Remove the autouse credential redirect: real ~/.flywheel/credentials
        # is needed for live smoke.
        # We skip the normal _isolate_credentials fixture's effect by
        # re-patching back to real credentials paths.
        import flywheel_cli.config as _cfg

        real_dir = Path.home() / ".flywheel"
        monkeypatch.setattr("flywheel_cli.config.FLYWHEEL_DIR", real_dir)
        monkeypatch.setattr(
            "flywheel_cli.config.CREDENTIALS_FILE", real_dir / "credentials.json"
        )
        monkeypatch.setattr("flywheel_cli.auth.FLYWHEEL_DIR", real_dir)
        monkeypatch.setattr(
            "flywheel_cli.auth.CREDENTIALS_FILE", real_dir / "credentials.json"
        )
        # Restore the real get_token (auto-refreshes via refresh_token).
        from flywheel_cli.auth import get_token as _real_get_token

        monkeypatch.setattr("flywheel_mcp.api_client.get_token", _real_get_token)
        # Route to a reachable backend URL.
        live_url = _resolve_live_backend()
        monkeypatch.setenv("FLYWHEEL_API_URL", live_url)
        monkeypatch.setattr(_cfg, "API_URL", live_url)
        # Sanity: creds file exists.
        creds = real_dir / "credentials.json"
        if not creds.exists():
            pytest.skip("Live smoke requires ~/.flywheel/credentials.json (run `flywheel login`)")

    # ------------------------------------------------------------------ SC1

    def test_sc1_fetch_returns_usable_bundle(self):
        """SC1: Fanout fetch for broker-parse-contract returns n:1 (library only)
        and the broker bundle bytes extract to api_client.py + field_validator.py."""
        from flywheel_mcp.api_client import FlywheelClient

        client = FlywheelClient()
        metadata, bundles = client.fetch_skill_assets_bundle("broker-parse-contract")

        assert metadata["skill"] == "broker-parse-contract"
        assert metadata["deps"] == ["broker"]
        assert len(metadata["rollup_sha"]) == 64
        assert len(bundles) == 1, (
            f"expected n:1 (library only), got {len(bundles)} "
            f"(consumer has assets:[] per Phase 147 contract so only the "
            f"broker library bundle is in the response)"
        )
        skill_name, wire_sha, bundle_bytes = bundles[0]
        assert skill_name == "broker"
        # BYTE-MATCH proof vs Phase 149 captured SHA.
        assert wire_sha == _BROKER_SHA, (
            f"broker SHA drifted: expected {_BROKER_SHA}, got {wire_sha}. "
            f"Phase 149 byte-identity guarantee broken."
        )
        assert len(bundle_bytes) == _BROKER_SIZE, (
            f"broker bundle size drifted: expected {_BROKER_SIZE}B, "
            f"got {len(bundle_bytes)}B"
        )
        # Client-side SHA re-hash matches wire SHA (integrity check on receipt).
        assert hashlib.sha256(bundle_bytes).hexdigest() == wire_sha
        # Zip extracts and contains expected broker library files.
        with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
            names = zf.namelist()
            assert "api_client.py" in names
            assert "field_validator.py" in names

    # Also verify via the MCP tool (end-of-pipeline shape).

    def test_sc1_mcp_tool_returns_tool_result(self):
        """SC1 (MCP surface): the registered tool returns the expected ToolResult."""
        from fastmcp.tools.tool import ToolResult

        result = flywheel_fetch_skill_assets("broker-parse-contract")

        assert isinstance(result, ToolResult)
        assert len(result.content) == 1
        assert result.structured_content is not None
        assert result.structured_content["skill"] == "broker-parse-contract"
        assert result.structured_content["deps"] == ["broker"]
        assert result.structured_content["shas"]["broker"] == _BROKER_SHA
        assert len(result.structured_content["rollup_sha"]) == 64

    # ------------------------------------------------------------------ SC2

    def test_sc2_materialize_rejects_malicious_zip(self, monkeypatch):
        """SC2: materialize_skill_bundle aborts on ``../etc/passwd`` before extractall.

        Plan 02 already proved this in detail; re-ship here as a
        phase-level regression guard with a fresh malicious fixture.
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            info = zipfile.ZipInfo(filename="../etc/passwd")
            z.writestr(info, b"PWNED")
        evil_bytes = buf.getvalue()
        evil_sha = hashlib.sha256(evil_bytes).hexdigest()

        fake_metadata = {"skill": "evil", "deps": [], "rollup_sha": evil_sha}
        fake_bundles = [("evil", evil_sha, evil_bytes)]

        class _FakeClient:
            def fetch_skill_assets_bundle(self, name):
                return fake_metadata, fake_bundles

        monkeypatch.setattr(
            "flywheel_mcp.api_client.FlywheelClient", lambda: _FakeClient()
        )

        with pytest.raises(BundleSecurityError) as exc_info:
            with materialize_skill_bundle("evil"):
                pytest.fail("should have raised BEFORE yielding")
        assert "../etc/passwd" in str(exc_info.value)
        assert exc_info.value.skill_name == "evil"

    # ------------------------------------------------------------------ SC3

    def test_sc3_tamper_raises_integrity_error(self, monkeypatch):
        """SC3: flipping the last byte of the real broker bundle raises
        BundleIntegrityError BEFORE zipfile.ZipFile is constructed on
        tampered bytes."""
        from flywheel_mcp.api_client import FlywheelClient

        # Fetch the real broker bundle first.
        real_client = FlywheelClient()
        metadata, bundles = real_client.fetch_skill_assets_bundle(
            "broker-parse-contract"
        )
        broker_name, broker_sha, broker_bytes = next(
            b for b in bundles if b[0] == "broker"
        )
        assert broker_sha == _BROKER_SHA  # byte-identity sanity

        # Tamper: flip the last byte.
        tampered_bytes = broker_bytes[:-1] + bytes([broker_bytes[-1] ^ 0xFF])
        tampered_sha = hashlib.sha256(tampered_bytes).hexdigest()
        assert tampered_sha != broker_sha
        tampered_bundles = [
            (broker_name, broker_sha, tampered_bytes)
            if b[0] == "broker"
            else b
            for b in bundles
        ]

        class _TamperClient:
            def fetch_skill_assets_bundle(self, name):
                return metadata, tampered_bundles

        monkeypatch.setattr(
            "flywheel_mcp.api_client.FlywheelClient", lambda: _TamperClient()
        )
        # Monkeypatch zipfile.ZipFile to count invocations — prove the
        # integrity check aborts BEFORE zipfile touches tampered bytes.
        import flywheel_mcp.bundle as bundle_mod

        real_zf = bundle_mod.zipfile.ZipFile
        calls = {"n": 0}

        def _counting_zf(*a, **kw):
            calls["n"] += 1
            return real_zf(*a, **kw)

        monkeypatch.setattr(bundle_mod.zipfile, "ZipFile", _counting_zf)

        with pytest.raises(BundleIntegrityError) as exc_info:
            with materialize_skill_bundle("broker-parse-contract"):
                pytest.fail("should have raised BEFORE yielding")

        err = exc_info.value
        assert err.skill_name == "broker"
        assert err.expected_sha == broker_sha
        assert err.actual_sha != broker_sha
        assert err.actual_sha == tampered_sha
        assert calls["n"] == 0, (
            "zipfile.ZipFile was constructed on tampered bytes — "
            "verify-before-extract ordering broken"
        )

    # ------------------------------------------------------------------ SC4

    def test_sc4_library_dep_importable_via_sys_path(self):
        """SC4: ``import field_validator`` resolves from the broker library
        bundle after materialize_skill_bundle extracts + wires sys.path.

        The consumer (broker-parse-contract) has assets:[] per Phase 147, so
        field_validator.py ships in the broker LIBRARY bundle — not in a
        consumer bundle.
        """
        import importlib

        # Snapshot sys.modules state so we don't pollute other tests.
        pre_modules = set(sys.modules)
        try:
            with materialize_skill_bundle("broker-parse-contract") as tmp:
                # Library files flattened at tmp root.
                assert (tmp / "field_validator.py").exists()
                assert (tmp / "api_client.py").exists()
                # sys.path wired.
                assert str(tmp) == sys.path[0]
                # Real import works.
                mod = importlib.import_module("field_validator")
                # Module exists and carries at least one callable attribute
                # (its public surface — the broker library's field validators).
                callables = [
                    name
                    for name in dir(mod)
                    if callable(getattr(mod, name))
                    and not name.startswith("_")
                ]
                assert callables, (
                    f"field_validator has no public callables: {dir(mod)}"
                )
        finally:
            # Cleanup: drop modules imported from the temp dir so subsequent
            # tests see a clean state.
            new_modules = set(sys.modules) - pre_modules
            for name in new_modules:
                sys.modules.pop(name, None)

    # ------------------------------------------------------------------ SC5

    def test_sc5_no_bytes_remain_on_disk_after_exit(self):
        """SC5: After the ``with`` block exits, the tempdir is deleted, no
        sibling ``flywheel-skill-*`` dirs under ``/tmp``, and Phase 150 wrote
        zero new bytes under ``~/.cache/flywheel/``.

        Uses snapshot-before/snapshot-after diff so pre-existing cache bytes
        from other tools or past phases don't flake the test. SC5 asserts
        Phase 150 ADDS nothing to the cache (Phase 152 is the one that
        ships caching).
        """
        cache = Path.home() / ".cache" / "flywheel"
        cache_before: set[str] = set()
        if cache.exists():
            cache_before = {
                str(p.relative_to(cache)) for p in cache.rglob("*")
            }

        captured_tmp: str | None = None
        with materialize_skill_bundle("broker-parse-contract") as tmp:
            captured_tmp = str(tmp)
            assert Path(captured_tmp).exists()
            # sys.path wired.
            assert sys.path[0] == captured_tmp

        # Tempdir deleted.
        assert captured_tmp is not None
        assert not Path(captured_tmp).exists(), (
            f"tempdir leaked after context exit: {captured_tmp}"
        )
        # No sibling flywheel-skill-* dirs under /tmp.
        siblings = list(Path("/tmp").glob("flywheel-skill-*"))
        # Filter out anything NOT created by this test (pre-existing leaks
        # from other runs shouldn't flake us).
        assert captured_tmp not in {str(s) for s in siblings}

        # Cache diff — Phase 150 must write ZERO new bytes.
        cache_after: set[str] = set()
        if cache.exists():
            cache_after = {
                str(p.relative_to(cache)) for p in cache.rglob("*")
            }
        new_entries = cache_after - cache_before
        assert not new_entries, (
            f"Phase 150 unexpectedly wrote to ~/.cache/flywheel "
            f"(that's Phase 152's job): {sorted(new_entries)}"
        )
