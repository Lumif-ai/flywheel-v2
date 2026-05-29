"""Tests for ``flywheel_mcp.bundle`` — Phase 150 Plan 02.

All tests are fully hermetic: no network, no DB, no filesystem outside
``tempfile``. Mocks :class:`FlywheelClient` to return canned bundles and
verifies the full materializer contract (SHA verify-before-extract, zip-slip
guard, sys.path lifecycle, tempdir cleanup).

Covers 14 named test functions grouped into the following buckets:

1.  Success paths — single bundle + multi-bundle flat merge.
2.  Tamper detection — SHA mismatch raises BundleIntegrityError.
3.  Path traversal — 4 attack variants all raise BundleSecurityError.
4.  Cleanup invariants — tempdir deleted, sys.path restored on normal exit
    AND on user-raised exception.
5.  sys.path mutation tolerance — user code can replace sys.path without
    breaking exit.
6.  Error propagation — BundleFetchError from the client bubbles up.
7.  401 handling — refresh-then-retry in FlywheelClient.
"""

from __future__ import annotations

import glob
import hashlib
import importlib
import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

import pytest

# -----  Patch config so FlywheelClient can be instantiated without a real
# credentials file. Matches the pattern in cli/tests/test_auth.py.
_tmp = tempfile.mkdtemp()
_PATCH_DIR = Path(_tmp) / ".flywheel"


@pytest.fixture(autouse=True)
def _isolate_credentials(monkeypatch):
    """Redirect credentials to a temp dir per-test and stub token retrieval."""
    test_dir = Path(tempfile.mkdtemp()) / ".flywheel"
    monkeypatch.setattr("flywheel_cli.config.FLYWHEEL_DIR", test_dir)
    monkeypatch.setattr(
        "flywheel_cli.config.CREDENTIALS_FILE", test_dir / "credentials.json"
    )
    monkeypatch.setattr("flywheel_cli.auth.FLYWHEEL_DIR", test_dir)
    monkeypatch.setattr(
        "flywheel_cli.auth.CREDENTIALS_FILE", test_dir / "credentials.json"
    )
    # Stub get_token so FlywheelClient() constructor succeeds without creds.
    monkeypatch.setattr(
        "flywheel_mcp.api_client.get_token", lambda: "stub-token"
    )
    yield
    import shutil

    shutil.rmtree(test_dir, ignore_errors=True)


from flywheel_mcp.bundle import (  # noqa: E402 — after monkeypatch fixture
    BundleCacheError,
    BundleError,
    BundleFetchError,
    BundleIntegrityError,
    BundleSecurityError,
    _safe_extract,
    materialize_skill_bundle,
)


# ---------------------------------------------------------------------------
# Zip-building helpers (deterministic + malicious variants)
# ---------------------------------------------------------------------------


def _build_deterministic_bundle(files: dict[str, bytes]) -> tuple[bytes, str]:
    """Build a deterministic zip matching Phase 147's seed contract.

    Sorted entry order + fixed epoch timestamp + stable external_attr so
    repeated calls with the same content produce byte-identical output
    (and thus the same SHA-256).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files.keys()):
            info = zipfile.ZipInfo(
                filename=name, date_time=(1980, 1, 1, 0, 0, 0)
            )
            info.external_attr = 0o644 << 16
            zf.writestr(info, files[name])
    data = buf.getvalue()
    return data, hashlib.sha256(data).hexdigest()


def _evil_zip(filename: str) -> tuple[bytes, str]:
    """Build a malicious zip whose single entry uses ``filename`` verbatim."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        info = zipfile.ZipInfo(filename=filename)
        z.writestr(info, b"PWNED")
    data = buf.getvalue()
    return data, hashlib.sha256(data).hexdigest()


class _FakeClient:
    """Minimal stand-in for FlywheelClient in the materializer tests.

    Used via ``monkeypatch.setattr`` on
    ``flywheel_mcp.api_client.FlywheelClient`` so
    :func:`materialize_skill_bundle`'s deferred import picks it up.
    """

    def __init__(self, metadata, bundles):
        self._metadata = metadata
        self._bundles = bundles
        self.calls: list[str] = []

    def fetch_skill_assets_bundle(self, name):
        self.calls.append(name)
        return self._metadata, self._bundles


def _patch_client(monkeypatch, fake: _FakeClient) -> None:
    """Replace FlywheelClient with a factory returning ``fake``."""
    monkeypatch.setattr(
        "flywheel_mcp.api_client.FlywheelClient", lambda: fake
    )


# ---------------------------------------------------------------------------
# 1.  Success paths
# ---------------------------------------------------------------------------


def test_success_single_bundle_extracts_and_imports(monkeypatch):
    """Single bundle: file extracted, sys.path prepended, import works."""
    bundle, sha = _build_deterministic_bundle(
        {"hello_mod.py": b"def greet():\n    return 'hi'\n"}
    )
    fake = _FakeClient(
        metadata={"skill": "s", "deps": [], "rollup_sha": sha},
        bundles=[("s", sha, bundle)],
    )
    _patch_client(monkeypatch, fake)

    captured_path: str | None = None
    initial_path = list(sys.path)

    with materialize_skill_bundle("s") as tmp:
        captured_path = str(tmp)
        assert (tmp / "hello_mod.py").exists()
        assert sys.path[0] == captured_path
        # Prove imports work from tmp_path.
        mod = importlib.import_module("hello_mod")
        try:
            assert mod.greet() == "hi"
        finally:
            # Cleanup importlib caches so subsequent tests aren't confused.
            sys.modules.pop("hello_mod", None)

    # Post-exit invariants.
    assert not os.path.exists(captured_path), "tempdir leaked"
    assert sys.path == initial_path, "sys.path not restored"


def test_multi_bundle_flat_merge_dep_first(monkeypatch):
    """Library bundle extracts first, consumer bundle merges on top.

    Proves:
    - Flat merge into single tmp dir.
    - Topological order: library files visible when consumer references them.
    - Single sys.path insert covers both.
    """
    lib_bundle, lib_sha = _build_deterministic_bundle(
        {"lib_util.py": b"X = 42\n"}
    )
    consumer_bundle, cons_sha = _build_deterministic_bundle(
        {"consumer_mod.py": b"from lib_util import X\nanswer = X\n"}
    )
    fake = _FakeClient(
        metadata={"skill": "consumer", "deps": ["lib"], "rollup_sha": "x"},
        bundles=[("lib", lib_sha, lib_bundle), ("consumer", cons_sha, consumer_bundle)],
    )
    _patch_client(monkeypatch, fake)

    with materialize_skill_bundle("consumer") as tmp:
        assert (tmp / "lib_util.py").exists()
        assert (tmp / "consumer_mod.py").exists()
        try:
            mod = importlib.import_module("consumer_mod")
            assert mod.answer == 42
        finally:
            sys.modules.pop("consumer_mod", None)
            sys.modules.pop("lib_util", None)


# ---------------------------------------------------------------------------
# 2.  Tamper detection
# ---------------------------------------------------------------------------


def test_integrity_check_detects_tamper(monkeypatch):
    """SHA mismatch raises BundleIntegrityError BEFORE zipfile touches bytes."""
    bundle, sha = _build_deterministic_bundle({"a.py": b"ok\n"})
    tampered = bundle[:-1] + bytes([bundle[-1] ^ 0xFF])
    assert hashlib.sha256(tampered).hexdigest() != sha

    fake = _FakeClient(
        metadata={"skill": "t", "deps": [], "rollup_sha": ""},
        bundles=[("t", sha, tampered)],
    )
    _patch_client(monkeypatch, fake)

    # Count ZipFile invocations to prove verify-before-extract ordering.
    original_zipfile = zipfile.ZipFile
    call_counter = {"n": 0}

    def _counting_zipfile(*args, **kwargs):
        call_counter["n"] += 1
        return original_zipfile(*args, **kwargs)

    monkeypatch.setattr("flywheel_mcp.bundle.zipfile.ZipFile", _counting_zipfile)

    with pytest.raises(BundleIntegrityError) as exc_info:
        with materialize_skill_bundle("t") as _:
            pytest.fail("body should not run")

    exc = exc_info.value
    assert exc.skill_name == "t"
    assert exc.expected_sha == sha
    assert exc.actual_sha == hashlib.sha256(tampered).hexdigest()
    assert "t" in str(exc)
    # Critical: zipfile was never constructed on tampered bytes.
    assert call_counter["n"] == 0, (
        "ZipFile was invoked on tampered bytes — verify-before-extract broken"
    )


# ---------------------------------------------------------------------------
# 3.  Path traversal — 4 attack variants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evil_filename",
    [
        "../etc/passwd",
        "/etc/passwd",
        "subdir/../../etc/passwd",
        "..\\..\\evil.exe",
    ],
    ids=["dotdot", "absolute", "nested", "windows_sep"],
)
def test_path_traversal_rejected(monkeypatch, evil_filename):
    """Each of the 4 attack vectors must raise BundleSecurityError.

    This is a single parametrized function but counts as 4 distinct test
    cases (tests 4, 5, 6, 7 in the plan's enumeration) and is reported as
    4 separate rows by pytest.
    """
    evil, sha = _evil_zip(evil_filename)
    fake = _FakeClient(
        metadata={"skill": "evil", "deps": [], "rollup_sha": ""},
        bundles=[("evil", sha, evil)],
    )
    _patch_client(monkeypatch, fake)

    with pytest.raises(BundleSecurityError) as exc_info:
        with materialize_skill_bundle("evil") as _:
            pytest.fail("body should not run")

    exc = exc_info.value
    assert exc.skill_name == "evil"
    assert "evil" in str(exc)
    # Entry path is surfaced exactly as declared in the zip — operators
    # need the raw attack payload in the error for incident response.
    assert exc.entry_path == evil_filename


# ---------------------------------------------------------------------------
# 4.  Cleanup invariants
# ---------------------------------------------------------------------------


def test_tempdir_deleted_after_normal_exit(monkeypatch):
    """Normal exit: TemporaryDirectory cleaned up."""
    bundle, sha = _build_deterministic_bundle({"x.py": b""})
    fake = _FakeClient(
        metadata={"skill": "s", "deps": [], "rollup_sha": ""},
        bundles=[("s", sha, bundle)],
    )
    _patch_client(monkeypatch, fake)

    captured: str | None = None
    with materialize_skill_bundle("s") as tmp:
        captured = str(tmp)
        assert os.path.exists(captured)
    assert not os.path.exists(captured)


def test_tempdir_deleted_after_exception(monkeypatch):
    """Exception inside with-block: TemporaryDirectory still cleaned up."""
    bundle, sha = _build_deterministic_bundle({"x.py": b""})
    fake = _FakeClient(
        metadata={"skill": "s", "deps": [], "rollup_sha": ""},
        bundles=[("s", sha, bundle)],
    )
    _patch_client(monkeypatch, fake)

    captured: str | None = None
    with pytest.raises(ValueError, match="intentional"):
        with materialize_skill_bundle("s") as tmp:
            captured = str(tmp)
            assert os.path.exists(captured)
            raise ValueError("intentional")
    assert captured is not None
    assert not os.path.exists(captured), "tempdir leaked on exception"


def test_sys_path_restored_on_exception(monkeypatch):
    """sys.path fully restored after user-raised exception."""
    bundle, sha = _build_deterministic_bundle({"x.py": b""})
    fake = _FakeClient(
        metadata={"skill": "s", "deps": [], "rollup_sha": ""},
        bundles=[("s", sha, bundle)],
    )
    _patch_client(monkeypatch, fake)

    captured = list(sys.path)
    with pytest.raises(ValueError, match="intentional"):
        with materialize_skill_bundle("s") as tmp:
            assert sys.path[0] == str(tmp)
            raise ValueError("intentional")
    assert sys.path == captured


def test_sys_path_tolerates_user_mutation(monkeypatch):
    """User code replacing sys.path in-with shouldn't break exit.

    The materializer uses .remove() by value — if the inserted entry is
    no longer present (user replaced sys.path wholesale), the ValueError
    is swallowed and exit proceeds cleanly.
    """
    bundle, sha = _build_deterministic_bundle({"x.py": b""})
    fake = _FakeClient(
        metadata={"skill": "s", "deps": [], "rollup_sha": ""},
        bundles=[("s", sha, bundle)],
    )
    _patch_client(monkeypatch, fake)

    original = list(sys.path)
    try:
        with materialize_skill_bundle("s") as tmp:
            # Wholesale replace — removes the inserted entry without an
            # explicit .remove() call.
            sys.path = ["/completely/unrelated"]
        # Exit did not raise. User's mutation is what sys.path currently is.
        assert sys.path == ["/completely/unrelated"]
    finally:
        sys.path[:] = original  # restore for subsequent tests


# ---------------------------------------------------------------------------
# 5.  Additional SC5 belt-and-suspenders
# ---------------------------------------------------------------------------


def test_no_bytes_under_tmp_after_exit(monkeypatch):
    """After exit, no flywheel-skill-* dirs remain under /tmp."""
    bundle, sha = _build_deterministic_bundle({"x.py": b""})
    fake = _FakeClient(
        metadata={"skill": "s", "deps": [], "rollup_sha": ""},
        bundles=[("s", sha, bundle)],
    )
    _patch_client(monkeypatch, fake)

    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "flywheel-skill-*")))
    with materialize_skill_bundle("s") as _:
        pass
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "flywheel-skill-*")))
    # Allow preexisting dirs from parallel or prior runs; just verify no
    # NEW directory leaked.
    assert after.issubset(before), f"Leaked flywheel-skill-* dirs: {after - before}"


# ---------------------------------------------------------------------------
# 6.  Fetch error propagation
# ---------------------------------------------------------------------------


def test_fetch_error_propagates(monkeypatch):
    """BundleFetchError from the client bubbles without creating a tempdir."""

    class _RaisingClient:
        def fetch_skill_assets_bundle(self, name):
            raise BundleFetchError(
                name,
                500,
                "Flywheel backend unreachable. Retry in a moment.",
            )

    monkeypatch.setattr(
        "flywheel_mcp.api_client.FlywheelClient", lambda: _RaisingClient()
    )

    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "flywheel-skill-*")))
    with pytest.raises(BundleFetchError) as exc_info:
        with materialize_skill_bundle("s") as _:
            pytest.fail("should not enter body")
    assert exc_info.value.status_code == 500
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "flywheel-skill-*")))
    assert after == before, "tempdir created despite fetch error"


# ---------------------------------------------------------------------------
# 7.  FlywheelClient.fetch_skill_assets_bundle — 401 refresh-one-shot
# ---------------------------------------------------------------------------


def test_401_refresh_one_shot_then_raise(monkeypatch):
    """401 refresh-then-401 raises BundleFetchError; no infinite loop."""
    from flywheel_mcp import api_client as api_client_mod
    from flywheel_mcp.api_client import FlywheelClient

    # Count refresh attempts. _ensure_token calls get_token each time.
    token_calls = {"n": 0}

    def _counting_get_token():
        token_calls["n"] += 1
        # Return the same token every time so _ensure_token's "changed"
        # branch (which writes to _client.headers) doesn't fire — keeps
        # the test focused on 401-loop behavior, not header plumbing.
        return "stub-token"

    monkeypatch.setattr(api_client_mod, "get_token", _counting_get_token)
    clear_count = {"n": 0}

    def _count_clear():
        clear_count["n"] += 1

    monkeypatch.setattr(api_client_mod, "clear_credentials", _count_clear)

    client = FlywheelClient()
    # FlywheelClient.__init__ calls get_token once; reset counter so the
    # assertion below measures only the fetch-path invocations.
    token_calls["n"] = 0

    # Replace _client.get with a tracker that ALWAYS returns 401.
    get_mock = mock.Mock(
        return_value=mock.Mock(status_code=401, text="")
    )
    client._client = mock.MagicMock(get=get_mock)

    with pytest.raises(BundleFetchError) as exc_info:
        client.fetch_skill_assets_bundle("s")

    exc = exc_info.value
    assert exc.status_code == 401
    assert "Session expired" in exc.message
    assert "flywheel login" in exc.message
    # One-shot refresh: initial _ensure_token + one more after the first
    # 401. get_token is called exactly 2x in the fetch path; clear_credentials
    # exactly once.
    assert token_calls["n"] == 2, (
        f"expected get_token called exactly 2x (initial + one refresh), "
        f"got {token_calls['n']}"
    )
    assert clear_count["n"] == 1, "clear_credentials should fire once on terminal 401"
    # The HTTP GET itself was called twice (once before refresh, once after)
    # — NOT more. Proves no infinite loop (Pitfall 9).
    assert get_mock.call_count == 2, (
        f"expected 2 HTTP GETs (initial + one retry after refresh), "
        f"got {get_mock.call_count}"
    )


# ---------------------------------------------------------------------------
# 8.  Exception hierarchy sanity (not in the 14-count, but cheap to assert)
# ---------------------------------------------------------------------------


def test_exception_hierarchy_rooted_at_bundle_error():
    """All four error classes subclass BundleError for a single catch root."""
    for cls in (
        BundleFetchError,
        BundleIntegrityError,
        BundleSecurityError,
        BundleCacheError,
    ):
        assert issubclass(cls, BundleError), cls
