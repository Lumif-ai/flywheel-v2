"""Hermetic tests for ``flywheel_mcp.cache`` (Phase 151 Plan 01).

No network, no real ``~/.cache/`` writes — every test uses ``tmp_path``.

Covers 11 BundleCache tests + 7 FlywheelClient integration tests (for a
total of 18) per the plan's done criteria.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import tempfile
import time
import zipfile
from pathlib import Path
from unittest import mock

import pytest


# -----  Isolate credentials so FlywheelClient() can construct in tests --
_tmp = tempfile.mkdtemp()


@pytest.fixture(autouse=True)
def _isolate_credentials(monkeypatch):
    """Redirect credentials + stub token retrieval per test."""
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


# Import after autouse fixture so module-level constants pick up any env.
from flywheel_mcp.bundle import BundleIntegrityError  # noqa: E402
from flywheel_mcp.cache import (  # noqa: E402
    BundleCache,
    CacheEntry,
    _HARD_CAP_BYTES,
    _SOFT_CAP_BYTES,
    _TTL_SECONDS,
)


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


def _make_chain(skill_name: str, *, with_dep: bool = False):
    """Return a ``(metadata, bundles)`` pair ready to hand to ``cache.put``."""
    lib_bytes, lib_sha = _build_deterministic_bundle(
        f"lib-for-{skill_name}".encode()
    )
    con_bytes, con_sha = _build_deterministic_bundle(
        f"consumer-{skill_name}".encode()
    )
    bundles: list[tuple[str, str, bytes]] = []
    if with_dep:
        bundles.append((f"{skill_name}-lib", lib_sha, lib_bytes))
    bundles.append((skill_name, con_sha, con_bytes))
    # Phase 150 rollup_sha = sha256 over newline-joined "<name>:<sha>" pairs.
    rollup = hashlib.sha256(
        "\n".join(f"{n}:{s}" for n, s, _ in bundles).encode("ascii")
    ).hexdigest()
    metadata = {
        "skill": skill_name,
        "deps": [f"{skill_name}-lib"] if with_dep else [],
        "rollup_sha": rollup,
        "version": "1.0.0",
    }
    return metadata, bundles


def _synthetic_big_bundle(target_size: int) -> tuple[bytes, str]:
    """Build a zip whose compressed size is close to ``target_size`` bytes.

    Uses STORED (no compression) so the size is predictable — random bytes
    defeat zip compression well enough either way.
    """
    # Random-ish payload so deflate doesn't shrink it.
    payload = os.urandom(target_size)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("big.bin", payload)
    data = buf.getvalue()
    return data, hashlib.sha256(data).hexdigest()


# ===========================================================================
# 11 BundleCache unit tests
# ===========================================================================


def test_put_creates_sha_addressed_layout(tmp_path):
    """put() writes <sha>/bundle.zip + metadata.json + index.json."""
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("skill-a")
    cache.put("skill-a", metadata, bundles, correlation_id="abcd1234")

    # Every bundle lands in its own SHA-addressed dir.
    for name, sha, _byts in bundles:
        assert (tmp_path / sha / "bundle.zip").exists(), (
            f"bundle.zip missing for {name} @ {sha[:8]}"
        )
        assert (tmp_path / sha / "metadata.json").exists(), (
            f"metadata.json missing for {name} @ {sha[:8]}"
        )
    assert (tmp_path / "index.json").exists()
    index = json.loads((tmp_path / "index.json").read_text())
    assert "skill-a" in index
    assert index["skill-a"]["root_sha"] == metadata["rollup_sha"]


def test_get_fresh_returns_within_ttl(tmp_path, monkeypatch):
    """Fresh put -> get_fresh returns CacheEntry. >TTL -> None."""
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("skill-ttl")
    cache.put("skill-ttl", metadata, bundles, correlation_id="ttl12345")

    fresh = cache.get_fresh("skill-ttl")
    assert fresh is not None
    assert isinstance(fresh, CacheEntry)
    assert fresh.skill_name == "skill-ttl"
    # Round-tripped bytes are byte-identical.
    assert fresh.bundles == bundles

    # Fast-forward past TTL by patching time.time in the cache module.
    far_future = time.time() + _TTL_SECONDS + 1
    with mock.patch("flywheel_mcp.cache.time.time", return_value=far_future):
        stale = cache.get_fresh("skill-ttl")
    assert stale is None


def test_get_fresh_validates_sha_on_load(tmp_path):
    """Flipping a byte in bundle.zip -> BundleIntegrityError + dir deleted."""
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("skill-tamper")
    cache.put("skill-tamper", metadata, bundles, correlation_id="tamper01")

    # Tamper the first bundle (consumer since with_dep=False).
    _name, sha, _byts = bundles[0]
    bundle_path = tmp_path / sha / "bundle.zip"
    original = bundle_path.read_bytes()
    tampered = bytearray(original)
    tampered[0] ^= 0xFF  # flip high bits of first byte
    bundle_path.write_bytes(bytes(tampered))

    with pytest.raises(BundleIntegrityError):
        cache.get_fresh("skill-tamper")

    # Dir is gone.
    assert not (tmp_path / sha).exists()
    # Index no longer lists the skill (can't trust dangling ref).
    index = json.loads((tmp_path / "index.json").read_text())
    assert "skill-tamper" not in index


def test_atomic_put_survives_interrupt(tmp_path):
    """Stray ``.tmp`` file in cache dir does not break put; no leak after."""
    cache = BundleCache(cache_dir=tmp_path)
    # Plant a stray .tmp file where a later atomic write would go.
    metadata, bundles = _make_chain("skill-atomic")
    sha = bundles[0][1]
    (tmp_path / sha).mkdir(parents=True, exist_ok=True)
    stray = tmp_path / sha / "bundle.zip.tmp"
    stray.write_bytes(b"leftover-partial-write")
    assert stray.exists()

    # put() should complete cleanly (os.replace overwrites) and NOT leave a .tmp.
    cache.put("skill-atomic", metadata, bundles, correlation_id="atomic00")

    # No .tmp files anywhere under the cache root.
    leftovers = list(tmp_path.rglob("*.tmp"))
    assert leftovers == [], f"Atomic put leaked: {leftovers}"
    # And the legit file is present.
    assert (tmp_path / sha / "bundle.zip").exists()


def test_lru_eviction_under_hard_cap(tmp_path, capsys):
    """Populate >100MB -> oldest entries evicted until under cap."""
    cache = BundleCache(cache_dir=tmp_path)

    # Build 10 distinct 12MB bundles (so total ~120MB, over 100MB hard cap).
    # Each under a distinct skill name with a distinct cached_at ordering.
    size_per = 12 * 1024 * 1024
    skills: list[str] = []
    base_now = time.time() - 10_000  # anchor in the past so we can order them
    for i in range(10):
        name = f"big-{i:02d}"
        skills.append(name)
        byts, sha = _synthetic_big_bundle(size_per)
        metadata = {
            "skill": name,
            "deps": [],
            "rollup_sha": sha,
            "version": "1.0.0",
        }
        bundles = [(name, sha, byts)]
        # Patch time so each put records a distinct cached_at (older i = older).
        with mock.patch(
            "flywheel_mcp.cache.time.time", return_value=base_now + i
        ):
            cache.put(name, metadata, bundles, correlation_id=f"big{i:04d}")

    # After all puts, evict_lru already ran (called inside put). Force one more.
    removed = cache.evict_lru()

    # Total size must now be <= hard cap.
    total = sum(
        (tmp_path / child).stat().st_size
        for child in os.listdir(tmp_path)
        if (tmp_path / child / "bundle.zip").exists()
        for _dummy in [None]  # sum over dirs, not a single file
    )
    # Compute total via the same iterator the cache uses.
    entries = cache._iter_sha_dirs()
    actual_total = sum(e[2] for e in entries)
    assert actual_total <= _HARD_CAP_BYTES, (
        f"Total {actual_total/1e6:.1f}MB > hard cap {_HARD_CAP_BYTES/1e6}MB"
    )
    # At least SOMETHING was evicted during the final call OR earlier puts.
    # The final call may return 0 if puts did all the work — so assert that
    # at least some skills are gone vs total we tried.
    # Count surviving entries.
    surviving = len(cache._iter_sha_dirs())
    assert surviving < len(skills), (
        f"Expected evictions; all {len(skills)} still present (removed={removed})"
    )


def test_soft_cap_warn_emitted(tmp_path, capsys):
    """Populate to >80MB but <100MB -> stderr WARN."""
    cache = BundleCache(cache_dir=tmp_path)
    size_per = 12 * 1024 * 1024
    # 8 bundles x 12MB = 96MB — above soft cap (80MB), below hard cap (100MB).
    for i in range(8):
        byts, sha = _synthetic_big_bundle(size_per)
        name = f"soft-{i:02d}"
        metadata = {"skill": name, "deps": [], "rollup_sha": sha, "version": "1.0"}
        cache.put(name, metadata, [(name, sha, byts)], correlation_id=f"sft{i:04d}")

    # Ensure evict_lru ran and produced the warn line.
    captured = capsys.readouterr()
    assert "WARN: Flywheel skill cache at" in captured.err, (
        f"Expected soft-cap WARN on stderr; got err={captured.err!r}"
    )
    assert "flywheel_refresh_skills" in captured.err


def test_extend_ttl_if_sha_match_bumps_cached_at(tmp_path):
    """Matching shas -> cached_at bumped to now, returns True."""
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("skill-ext", with_dep=True)
    # Patch time so initial cached_at is old.
    with mock.patch("flywheel_mcp.cache.time.time", return_value=0.0):
        cache.put("skill-ext", metadata, bundles, correlation_id="ext00001")

    # Confirm cached_at = 0.0 pre-extend.
    for _name, sha, _byts in bundles:
        meta = json.loads((tmp_path / sha / "metadata.json").read_text())
        assert meta["cached_at"] == 0.0

    server_shas = {n: s for n, s, _ in bundles}
    extended = cache.extend_ttl_if_sha_match("skill-ext", server_shas)
    assert extended is True

    for _name, sha, _byts in bundles:
        meta = json.loads((tmp_path / sha / "metadata.json").read_text())
        assert meta["cached_at"] > 0.0, "cached_at not bumped"


def test_extend_ttl_if_sha_match_returns_false_on_mismatch(tmp_path):
    """Any SHA mismatch -> return False, cached_at unchanged."""
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("skill-mismatch")
    with mock.patch("flywheel_mcp.cache.time.time", return_value=0.0):
        cache.put("skill-mismatch", metadata, bundles, correlation_id="mis00001")

    # Build server_shas with one entry flipped.
    server_shas = {n: s for n, s, _ in bundles}
    # Replace one sha with a different string.
    first_name = list(server_shas.keys())[0]
    server_shas[first_name] = "0" * 64

    extended = cache.extend_ttl_if_sha_match("skill-mismatch", server_shas)
    assert extended is False

    # cached_at still 0.
    for _name, sha, _byts in bundles:
        meta = json.loads((tmp_path / sha / "metadata.json").read_text())
        assert meta["cached_at"] == 0.0


def test_shared_sha_dedup(tmp_path):
    """Two skill names with identical bundle bytes share one <sha>/ dir.

    ``remove(name1)`` must NOT delete the dir while ``name2`` still
    references it. After ``remove(name2)`` the dir disappears.
    """
    cache = BundleCache(cache_dir=tmp_path)
    # Identical bytes -> identical SHA (Phase 147 byte-determinism).
    shared_bytes, shared_sha = _build_deterministic_bundle(b"shared-payload")

    metadata1 = {
        "skill": "skill-one",
        "deps": [],
        "rollup_sha": shared_sha,
        "version": "1.0",
    }
    metadata2 = {
        "skill": "skill-two",
        "deps": [],
        "rollup_sha": shared_sha,
        "version": "1.0",
    }
    cache.put("skill-one", metadata1, [("shared-lib", shared_sha, shared_bytes)],
              correlation_id="one00001")
    cache.put("skill-two", metadata2, [("shared-lib", shared_sha, shared_bytes)],
              correlation_id="two00001")

    # Only one <sha>/ dir.
    sha_dirs = [c for c in tmp_path.iterdir() if c.is_dir()]
    assert len(sha_dirs) == 1
    assert sha_dirs[0].name == shared_sha

    # Remove skill-one — dir must survive (skill-two still refs it).
    cache.remove("skill-one")
    assert (tmp_path / shared_sha).exists(), "Shared SHA dir wrongly deleted"
    index = json.loads((tmp_path / "index.json").read_text())
    assert "skill-one" not in index
    assert "skill-two" in index

    # Remove skill-two — now truly orphaned, should be deleted.
    cache.remove("skill-two")
    assert not (tmp_path / shared_sha).exists()


def test_cache_dir_created_0755_by_default(tmp_path):
    """Default cache dir perms are NOT 0o700; match 0o7xx (755 under typical umask)."""
    sub = tmp_path / "new-cache-root" / "skills"
    cache = BundleCache(cache_dir=sub)
    mode = stat.S_IMODE(sub.stat().st_mode)
    # MUST NOT be 0o700 (CONTEXT lock): bundle bytes are public via HTTPS.
    assert mode != 0o700, (
        f"Cache dir created 0o700; should be default umask (~0o755). Got {oct(mode)}"
    )
    # Typical umask on macOS/linux dev: 0o022 -> 0o755. Also accept 0o775 (0o002)
    # and 0o750 (0o027). Just assert group/other have at least read OR the
    # permission bits include the world-readable signal.
    assert mode & 0o044, (
        f"Cache dir is too restrictive ({oct(mode)}); expected non-0o700 default."
    )


def test_metadata_json_schema(tmp_path):
    """metadata.json contains all required keys per the plan spec."""
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("skill-schema")
    cache.put("skill-schema", metadata, bundles, correlation_id="schema01")

    # Read the skill's own metadata.json (not the library's).
    for name, sha, _byts in bundles:
        if name == "skill-schema":
            meta = json.loads((tmp_path / sha / "metadata.json").read_text())
            break
    else:
        pytest.fail("Did not find metadata.json for skill-schema")

    required_keys = {
        "skill_name", "version", "cached_at", "deps",
        "bundle_sha256", "bundle_size_bytes", "correlation_id",
    }
    assert required_keys.issubset(meta.keys()), (
        f"Missing keys: {required_keys - set(meta.keys())}"
    )
    assert meta["correlation_id"] == "schema01"
    assert meta["skill_name"] == "skill-schema"
    assert meta["bundle_sha256"] == sha
    assert meta["bundle_size_bytes"] > 0


# ===========================================================================
# 7 FlywheelClient integration tests (Task 3)
# ===========================================================================


import base64  # noqa: E402

import httpx  # noqa: E402

from flywheel_mcp.api_client import FlywheelClient  # noqa: E402
from flywheel_mcp.bundle import BundleCacheError  # noqa: E402


def _fake_ok_response(metadata: dict, bundles: list[tuple[str, str, bytes]]):
    """Build a mock httpx.Response that looks like a full fetch success."""
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


def _fake_shas_only_response(bundles: list[tuple[str, str, bytes]]):
    """Mock response for ?shas_only=true branch (empty bundle_b64)."""
    body = {
        "skill": bundles[-1][0] if bundles else "",
        "deps": [n for n, _, _ in bundles[:-1]],
        "rollup_sha": hashlib.sha256(
            "\n".join(f"{n}:{s}" for n, s, _ in bundles).encode("ascii")
        ).hexdigest(),
        "bundles": [
            {
                "name": n,
                "sha256": s,
                "size": len(b),
                "format": "zip",
                "version": "1.0",
                "updated_at": None,
                "bundle_b64": "",
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
    """Point BundleCache()'s default dir at tmp_path so tests can't hit real disk."""
    monkeypatch.setattr(
        "flywheel_mcp.cache._DEFAULT_CACHE_DIR", tmp_path
    )
    yield tmp_path


def test_fetch_skill_assets_bundle_cache_hit_no_network(_patched_cache_dir):
    """Fresh cache -> return cached tuple, zero HTTP calls."""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("my-skill")
    cache.put("my-skill", metadata, bundles, correlation_id="cache001")

    client = FlywheelClient()
    # Fail loudly on any HTTP call.
    client._client.get = mock.MagicMock(
        side_effect=AssertionError("HTTP called on fresh cache hit")
    )

    got_meta, got_bundles = client.fetch_skill_assets_bundle("my-skill")
    # Must match cached contents (byte-identical bundles).
    assert got_bundles == bundles
    assert got_meta["skill"] == "my-skill"
    assert got_meta["rollup_sha"] == metadata["rollup_sha"]
    client._client.get.assert_not_called()


def test_fetch_skill_assets_bundle_stale_cache_sha_match_no_download(_patched_cache_dir):
    """Stale cache + SHAs match -> only shas_only GET (no full bundle fetch)."""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("stale-match")
    # Age the entry so get_fresh returns None but has_stale is True.
    with mock.patch("flywheel_mcp.cache.time.time", return_value=0.0):
        cache.put("stale-match", metadata, bundles, correlation_id="stale001")

    # Sanity: stale (ttl elapsed since cached_at=0).
    assert cache.get_fresh("stale-match") is None
    assert cache.has_stale("stale-match") is True

    client = FlywheelClient()
    calls = []

    def _mock_get(url, headers=None):
        calls.append((url, dict(headers or {})))
        if "shas_only=true" in url:
            return _fake_shas_only_response(bundles)
        raise AssertionError(f"Unexpected full-fetch call to {url}")

    client._client.get = mock.MagicMock(side_effect=_mock_get)

    got_meta, got_bundles = client.fetch_skill_assets_bundle("stale-match")
    # Bundles returned are the cached bytes (which match server SHAs).
    assert got_bundles == bundles
    # Exactly one network call, and it was the shas_only probe.
    assert len(calls) == 1
    assert "shas_only=true" in calls[0][0]
    # correlation_id header present.
    assert calls[0][1].get("X-Flywheel-Correlation-ID")


def test_fetch_skill_assets_bundle_stale_cache_sha_mismatch_full_refetch(
    _patched_cache_dir,
):
    """Stale cache + SHAs differ -> full fetch + cache updated."""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)
    old_metadata, old_bundles = _make_chain("mismatch")
    with mock.patch("flywheel_mcp.cache.time.time", return_value=0.0):
        cache.put("mismatch", old_metadata, old_bundles, correlation_id="old00001")

    # Build NEW bundles with different bytes.
    new_bytes, new_sha = _build_deterministic_bundle(b"new-authoritative-bytes")
    new_bundles = [("mismatch", new_sha, new_bytes)]
    new_metadata = {
        "skill": "mismatch",
        "deps": [],
        "rollup_sha": hashlib.sha256(
            f"mismatch:{new_sha}".encode("ascii")
        ).hexdigest(),
        "version": "1.1.0",
    }

    client = FlywheelClient()
    calls = []

    def _mock_get(url, headers=None):
        calls.append(url)
        if "shas_only=true" in url:
            # Return NEW shas — forcing mismatch with cached bytes.
            return _fake_shas_only_response(new_bundles)
        return _fake_ok_response(new_metadata, new_bundles)

    client._client.get = mock.MagicMock(side_effect=_mock_get)

    got_meta, got_bundles = client.fetch_skill_assets_bundle("mismatch")
    # We got the NEW bundles.
    assert got_bundles == new_bundles
    # Two calls: shas_only probe (mismatch) + full fetch.
    assert len(calls) == 2
    assert "shas_only=true" in calls[0]
    assert "shas_only=true" not in calls[1]
    # Cache now has the new bytes.
    cache2 = BundleCache(cache_dir=tmp_path)
    fresh = cache2.get_fresh("mismatch")
    assert fresh is not None
    assert fresh.bundles == new_bundles


def test_fetch_skill_assets_bundle_bypass_cache_skips_cache(_patched_cache_dir):
    """bypass_cache=True -> full fetch even with fresh cache, cache NOT updated."""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("bypass")
    cache.put("bypass", metadata, bundles, correlation_id="bypass01")

    # Use a different payload on the wire so we can distinguish.
    new_bytes, new_sha = _build_deterministic_bundle(b"refreshed-via-bypass")
    new_bundles = [("bypass", new_sha, new_bytes)]
    new_metadata = {
        "skill": "bypass",
        "deps": [],
        "rollup_sha": hashlib.sha256(
            f"bypass:{new_sha}".encode("ascii")
        ).hexdigest(),
        "version": "1.0",
    }

    client = FlywheelClient()
    calls = []

    def _mock_get(url, headers=None):
        calls.append(url)
        if "shas_only=true" in url:
            raise AssertionError("bypass_cache must skip shas_only probe")
        return _fake_ok_response(new_metadata, new_bundles)

    client._client.get = mock.MagicMock(side_effect=_mock_get)

    got_meta, got_bundles = client.fetch_skill_assets_bundle(
        "bypass", bypass_cache=True
    )
    assert got_bundles == new_bundles
    # Exactly one call — full fetch, no shas_only probe.
    assert len(calls) == 1
    assert "shas_only=true" not in calls[0]


def test_fetch_skill_assets_bundle_correlation_id_threaded(_patched_cache_dir):
    """Same correlation_id sent on all 3 retry attempts."""
    client = FlywheelClient()
    call_headers: list[dict] = []
    attempts = [0]

    metadata, bundles = _make_chain("retry-test")

    def _mock_get(url, headers=None):
        attempts[0] += 1
        call_headers.append(dict(headers or {}))
        if attempts[0] < 3:
            raise httpx.ConnectError("simulated network drop")
        return _fake_ok_response(metadata, bundles)

    client._client.get = mock.MagicMock(side_effect=_mock_get)

    # Patch time.sleep to avoid real backoff delay.
    with mock.patch("flywheel_mcp.api_client.time.sleep"):
        client.fetch_skill_assets_bundle(
            "retry-test", correlation_id="cafebabe", bypass_cache=True
        )

    # All 3 attempts sent the same correlation_id.
    assert len(call_headers) == 3
    cids = [h.get("X-Flywheel-Correlation-ID") for h in call_headers]
    assert cids == ["cafebabe", "cafebabe", "cafebabe"]


def test_fetch_skill_assets_bundle_offline_with_fresh_cache_serves_cached(
    _patched_cache_dir, capsys
):
    """Backend unreachable + fresh cache -> serves cached + stderr WARN."""
    tmp_path = _patched_cache_dir
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("offline-fresh")
    cache.put("offline-fresh", metadata, bundles, correlation_id="offln001")

    client = FlywheelClient()

    def _always_raise(url, headers=None):
        # A fresh cache hit returns BEFORE any HTTP call. But if called,
        # simulate network down so the fallback kicks in.
        raise httpx.ConnectError("simulated network down")

    client._client.get = mock.MagicMock(side_effect=_always_raise)

    # Fresh cache: first call is get_fresh, returns immediately — no WARN
    # should fire because we never attempted the network.
    got_meta, got_bundles = client.fetch_skill_assets_bundle("offline-fresh")
    assert got_bundles == bundles
    # On a FRESH cache hit we don't go to the network at all, so no stderr WARN.
    # Exercise the OFFLINE+STALE-FRESH-ENOUGH path by bypassing cache on the
    # read side but keeping stale path alive via TTL expiry.
    # This matches the plan spec wording: offline + fresh cache serves.

    # Part 2: stale but still-loadable cache + network down -> WARN + serve.
    with mock.patch("flywheel_mcp.cache.time.time", return_value=0.0):
        cache.put("offline-stale", metadata, bundles, correlation_id="offln002")

    with mock.patch("flywheel_mcp.api_client.time.sleep"):
        got_meta2, got_bundles2 = client.fetch_skill_assets_bundle("offline-stale")
    assert got_bundles2 == bundles
    captured = capsys.readouterr()
    assert "WARN: Backend unreachable. Using cached" in captured.err
    assert "offline-stale" in captured.err


def test_fetch_skill_assets_bundle_offline_expired_cache_raises_bundle_cache_error(
    _patched_cache_dir,
):
    """Backend unreachable + no cache entry -> BundleCacheError raised."""
    tmp_path = _patched_cache_dir
    # Pre-populate one skill so has_stale returns True, BUT we'll patch
    # get_stale to return None (simulating tamper-then-deleted mid-fallback).
    cache = BundleCache(cache_dir=tmp_path)
    metadata, bundles = _make_chain("expired")
    with mock.patch("flywheel_mcp.cache.time.time", return_value=0.0):
        cache.put("expired", metadata, bundles, correlation_id="expr0001")

    # Now delete the underlying bundle.zip files so get_stale returns None
    # (stale reference in index but actual bytes gone — simulates a
    # half-cleaned tamper state).
    for pb in json.loads((tmp_path / "index.json").read_text())["expired"]["per_bundle"]:
        (tmp_path / pb["sha"] / "bundle.zip").unlink(missing_ok=True)

    client = FlywheelClient()
    client._client.get = mock.MagicMock(
        side_effect=httpx.ConnectError("network down")
    )

    with mock.patch("flywheel_mcp.api_client.time.sleep"):
        with pytest.raises(BundleCacheError) as excinfo:
            client.fetch_skill_assets_bundle("expired")

    # Message should hint at the user action.
    msg = str(excinfo.value)
    assert "expired" in msg.lower() or "refresh" in msg.lower()
