"""Content-addressed disk cache for Flywheel skill bundles.

Phase 151 Plan 01 — sits between :meth:`FlywheelClient.fetch_skill_assets_bundle`
and :func:`materialize_skill_bundle` (Phase 150). Enables:

- **Offline resilience (SC2):** if the backend is unreachable but the cache
  has a fresh entry, the client can serve bytes from disk.
- **Cheap freshness checks (SC5):** after TTL expiry the client asks the
  backend for SHAs only (``?shas_only=true``) and, on match, extends the
  TTL without re-downloading bundle bytes.
- **Forensic tracing:** every entry records the ``correlation_id`` of the
  fetch that populated it, so later cache hits can be traced back to the
  originating request.

Design invariants:

1. **Content-addressed layout:** ``~/.cache/flywheel/skills/<sha256>/`` holds
   verbatim ``bundle.zip`` + ``metadata.json``. Two skills with identical
   bundle bytes (Phase 147 byte-determinism) share one ``<sha>/`` dir —
   ``index.json`` is the skill-name → SHA lookup.
2. **SHA-256 validation on every load:** ``get_fresh`` / ``get_stale``
   recompute SHA of the stored bytes and compare to ``metadata.bundle_sha256``.
   Mismatch raises :class:`BundleIntegrityError` (from :mod:`bundle`) AND
   auto-deletes the tampered ``<sha>/`` dir. Belt-and-suspenders: the
   materializer re-validates again before extractall.
3. **Atomic writes:** ``bundle.zip``, ``metadata.json``, ``index.json`` all
   use ``tempfile + os.replace`` for crash-safe replacement within a single
   filesystem (``os.replace`` is atomic on POSIX).
4. **LRU eviction at 100 MB hard cap:** ``put`` always calls ``evict_lru``.
   Soft warn at 80 MB to stderr.
5. **24-hour TTL** with opportunistic extension via SHA pre-check.
6. **Stdlib only.** No new runtime deps (matches Phase 151 CONTEXT lock).

Permissions: ``<cache_dir>`` is created with default umask (typically
``0o755``). This is deliberate, NOT ``0o700``: bundle bytes already travel
over HTTPS, and tightening perms creates friction for multi-user dev
setups without a real attack surface.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants (module-level; override via ``BundleCache(cache_dir=...)`` in tests)
# ---------------------------------------------------------------------------

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "flywheel" / "skills"
_TTL_SECONDS = 24 * 60 * 60
_SOFT_CAP_BYTES = 80 * 1024 * 1024
_HARD_CAP_BYTES = 100 * 1024 * 1024


__all__ = [
    "BundleCache",
    "CacheEntry",
    "RefreshResult",
    "_DEFAULT_CACHE_DIR",
    "_TTL_SECONDS",
    "_SOFT_CAP_BYTES",
    "_HARD_CAP_BYTES",
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CacheEntry:
    """One cached skill bundle chain, loaded from disk.

    Shape matches :meth:`FlywheelClient.fetch_skill_assets_bundle` return
    tuple — use :meth:`as_tuple` for drop-in substitution.

    Attributes:
        skill_name: Root skill name.
        metadata: ``{"skill", "deps", "rollup_sha"}`` — same as the client's
            metadata dict.
        bundles: ``[(name, sha256, bytes), ...]`` in topological order.
        cached_at: Wall-clock timestamp of the oldest entry in the chain
            (drives TTL checks — any expired entry stales the whole chain).
        correlation_id: 8-hex-char ID of the fetch that populated the cache.
    """

    skill_name: str
    metadata: dict
    bundles: list[tuple[str, str, bytes]]
    cached_at: float
    correlation_id: str

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.cached_at)

    @property
    def ttl_remaining(self) -> float:
        return _TTL_SECONDS - self.age_seconds

    @property
    def is_fresh(self) -> bool:
        return self.ttl_remaining > 0

    @property
    def age_human(self) -> str:
        secs = self.age_seconds
        if secs >= 3600:
            return f"{int(secs // 3600)}h"
        if secs >= 60:
            return f"{int(secs // 60)}m"
        return f"{int(secs)}s"

    @property
    def ttl_remaining_human(self) -> str:
        remaining = self.ttl_remaining
        if remaining <= 0:
            return "expired"
        if remaining >= 3600:
            return f"{int(remaining // 3600)}h left"
        if remaining >= 60:
            return f"{int(remaining // 60)}m left"
        return f"{int(remaining)}s left"

    def as_tuple(self) -> tuple[dict, list[tuple[str, str, bytes]]]:
        """Return ``(metadata, bundles)`` — drop-in for
        :meth:`FlywheelClient.fetch_skill_assets_bundle`."""
        return self.metadata, self.bundles


@dataclass
class RefreshResult:
    """Return value of :meth:`BundleCache.refresh`."""

    evicted: int = 0
    refetched: int = 0
    tampered_count: int = 0
    per_skill: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Atomic-write helper
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically via ``tempfile + os.replace``.

    Within the same filesystem, ``os.replace`` is atomic on POSIX (per
    IEEE Std 1003.1). Reader either sees the old file or the new file —
    never a partial write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# BundleCache
# ---------------------------------------------------------------------------


class BundleCache:
    """Content-addressed on-disk cache for skill bundles.

    Public API:
        - :meth:`get_fresh` — TTL-valid cache hit or ``None``.
        - :meth:`get_stale` — any cache hit (fresh or stale) or ``None``.
        - :meth:`has_stale` — cheap existence probe (no SHA validation).
        - :meth:`put` — atomic write + LRU eviction.
        - :meth:`extend_ttl_if_sha_match` — bump ``cached_at`` when server
          confirms cached SHAs are still authoritative.
        - :meth:`remove` — delete one skill's entry (preserves shared-SHA
          dirs while another skill still references them).
        - :meth:`evict_lru` — LRU eviction to the hard cap.
        - :meth:`refresh` — force refetch via injected callable.

    Design notes:
        - No circular import with :class:`FlywheelClient`: the refresh
          method accepts a ``fetcher`` callable from the caller, NOT a
          client instance directly.
        - SHA validation on load short-circuits via
          :class:`~flywheel_mcp.bundle.BundleIntegrityError` so the same
          exception taxonomy covers both cache-layer and materializer
          tamper detection.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._dir = Path(cache_dir) if cache_dir is not None else _DEFAULT_CACHE_DIR
        # Default umask (usually 0o022) -> 0o755. Deliberate; see module docstring.
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Index helpers
    # ------------------------------------------------------------------

    @property
    def _index_path(self) -> Path:
        return self._dir / "index.json"

    def _load_index(self) -> dict:
        """Return the index.json dict, or {} if missing/unreadable."""
        if not self._index_path.exists():
            return {}
        try:
            return json.loads(self._index_path.read_text())
        except (json.JSONDecodeError, OSError):
            # Corrupt index is recoverable: treat as empty, next put rewrites.
            return {}

    def _save_index(self, index: dict) -> None:
        _atomic_write(self._index_path, json.dumps(index, indent=2).encode("utf-8"))

    # ------------------------------------------------------------------
    # SHA-addressed dir helpers
    # ------------------------------------------------------------------

    def _sha_dir(self, sha: str) -> Path:
        return self._dir / sha

    def _bundle_path(self, sha: str) -> Path:
        return self._sha_dir(sha) / "bundle.zip"

    def _metadata_path(self, sha: str) -> Path:
        return self._sha_dir(sha) / "metadata.json"

    def _delete_sha_dir(self, sha: str) -> None:
        """Delete a <sha>/ dir; survives already-gone case."""
        shutil.rmtree(self._sha_dir(sha), ignore_errors=True)

    def _load_bundle_with_validation(
        self, sha: str, skill_name_hint: str
    ) -> tuple[bytes, dict]:
        """Load bundle bytes + metadata, SHA-validating on the way.

        Raises :class:`~flywheel_mcp.bundle.BundleIntegrityError` and
        deletes the tampered dir if the recomputed SHA doesn't match the
        one recorded in ``metadata.json`` or the addressed dir name.
        """
        # Deferred import: avoid circular dependency with bundle.py (which
        # imports FlywheelClient lazily).
        from flywheel_mcp.bundle import BundleIntegrityError

        bundle_bytes = self._bundle_path(sha).read_bytes()
        meta = json.loads(self._metadata_path(sha).read_text())
        actual_sha = hashlib.sha256(bundle_bytes).hexdigest()
        expected_sha = meta.get("bundle_sha256", sha)
        if actual_sha != expected_sha or actual_sha != sha:
            # Tamper detected — delete evidence + raise.
            self._delete_sha_dir(sha)
            # Also rip the skill out of the index to avoid dangling refs.
            index = self._load_index()
            changed = False
            for name in list(index.keys()):
                entry = index[name]
                if entry.get("root_sha") == sha or any(
                    pb.get("sha") == sha for pb in entry.get("per_bundle", [])
                ):
                    index.pop(name, None)
                    changed = True
            if changed:
                self._save_index(index)
            raise BundleIntegrityError(
                skill_name=skill_name_hint,
                expected_sha=expected_sha,
                actual_sha=actual_sha,
            )
        return bundle_bytes, meta

    # ------------------------------------------------------------------
    # Public: read path
    # ------------------------------------------------------------------

    def _load_entry_from_index(self, skill_name: str) -> CacheEntry | None:
        """Shared get_fresh/get_stale/helper — SHA-validates every bundle.

        Returns None if the skill is absent from the index OR any required
        ``<sha>/`` dir is missing on disk. Raises
        :class:`BundleIntegrityError` on tamper (via
        ``_load_bundle_with_validation``).
        """
        index = self._load_index()
        entry = index.get(skill_name)
        if entry is None:
            return None
        per_bundle = entry.get("per_bundle", [])
        if not per_bundle:
            return None

        bundles: list[tuple[str, str, bytes]] = []
        cached_ats: list[float] = []
        correlation_id = ""
        # Topological order is persisted in per_bundle list order.
        for pb in per_bundle:
            name = pb["name"]
            sha = pb["sha"]
            if not self._bundle_path(sha).exists() or not self._metadata_path(sha).exists():
                # Partial cache — surface as miss so caller re-fetches cleanly.
                return None
            bundle_bytes, meta = self._load_bundle_with_validation(sha, name)
            bundles.append((name, sha, bundle_bytes))
            cached_ats.append(float(meta.get("cached_at", 0)))
            if not correlation_id:
                correlation_id = meta.get("correlation_id", "") or ""

        # TTL is driven by the OLDEST entry — any stale piece stales the chain.
        oldest = min(cached_ats) if cached_ats else 0.0
        return CacheEntry(
            skill_name=skill_name,
            metadata={
                "skill": skill_name,
                "deps": [b[0] for b in bundles if b[0] != skill_name],
                "rollup_sha": entry.get("root_sha", ""),
            },
            bundles=bundles,
            cached_at=oldest,
            correlation_id=correlation_id,
        )

    def get_fresh(self, skill_name: str) -> CacheEntry | None:
        """Return a TTL-valid cache entry, or ``None``.

        Raises :class:`~flywheel_mcp.bundle.BundleIntegrityError` on
        tamper (the tampered dir is auto-deleted as a side effect).
        """
        entry = self._load_entry_from_index(skill_name)
        if entry is None:
            return None
        return entry if entry.is_fresh else None

    def has_stale(self, skill_name: str) -> bool:
        """True if the cache has ANY entry for ``skill_name``, fresh or not.

        Cheap existence probe — does not read bundle bytes or validate SHA.
        Useful before deciding whether a SHA pre-check is worth attempting.
        """
        index = self._load_index()
        entry = index.get(skill_name)
        if entry is None:
            return False
        for pb in entry.get("per_bundle", []):
            if not self._bundle_path(pb["sha"]).exists():
                return False
        return bool(entry.get("per_bundle"))

    def get_stale(self, skill_name: str) -> CacheEntry | None:
        """Return the cache entry regardless of TTL (offline fallback path).

        Still SHA-validates — tampered bytes never get served, even in
        offline mode.
        """
        return self._load_entry_from_index(skill_name)

    # ------------------------------------------------------------------
    # Public: write path
    # ------------------------------------------------------------------

    def put(
        self,
        skill_name: str,
        metadata: dict,
        bundles: list[tuple[str, str, bytes]],
        *,
        correlation_id: str,
    ) -> None:
        """Write a chain atomically to the cache + run LRU eviction.

        For each ``(name, sha, bytes)`` in ``bundles``:
            1. Defense-in-depth: recompute SHA and verify match. If the
               caller lied, raise ``ValueError`` — this should never
               happen in production but is cheap to catch here.
            2. Write ``<sha>/bundle.zip`` + ``<sha>/metadata.json`` via
               atomic ``tempfile + os.replace``.

        Then update ``index.json`` atomically mapping ``skill_name`` to
        the ordered per-bundle SHAs, and call :meth:`evict_lru`.
        """
        now = time.time()
        for name, sha, byts in bundles:
            actual = hashlib.sha256(byts).hexdigest()
            if actual != sha:
                raise ValueError(
                    f"put(): claimed sha {sha[:12]}... does not match bytes "
                    f"(actual {actual[:12]}...) for {name}"
                )
            sha_dir = self._sha_dir(sha)
            sha_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write(self._bundle_path(sha), byts)
            meta_doc = {
                "skill_name": name,
                "version": metadata.get("version") if name == skill_name else None,
                "cached_at": now,
                "deps": metadata.get("deps", []) if name == skill_name else [],
                "bundle_sha256": sha,
                "bundle_size_bytes": len(byts),
                "correlation_id": correlation_id,
            }
            _atomic_write(
                self._metadata_path(sha),
                json.dumps(meta_doc, indent=2).encode("utf-8"),
            )

        # Update index atomically.
        index = self._load_index()
        index[skill_name] = {
            "root_sha": metadata.get("rollup_sha", ""),
            "per_bundle": [{"name": n, "sha": s} for n, s, _ in bundles],
        }
        self._save_index(index)

        # LRU eviction at cap.
        self.evict_lru()

    def extend_ttl_if_sha_match(
        self, skill_name: str, server_shas: dict[str, str]
    ) -> bool:
        """Bump ``cached_at`` on every bundle iff cached SHAs == server SHAs.

        Returns True on match (TTL extended), False on any mismatch (caller
        should do a full refetch). Noop if the skill is absent from the
        cache.
        """
        index = self._load_index()
        entry = index.get(skill_name)
        if entry is None:
            return False
        per_bundle = entry.get("per_bundle", [])
        if not per_bundle:
            return False
        # Every cached bundle name must be present + match.
        for pb in per_bundle:
            if server_shas.get(pb["name"]) != pb["sha"]:
                return False
        # All match — bump cached_at on every metadata.json.
        now = time.time()
        for pb in per_bundle:
            sha = pb["sha"]
            meta_path = self._metadata_path(sha)
            if not meta_path.exists():
                return False
            try:
                meta = json.loads(meta_path.read_text())
            except (json.JSONDecodeError, OSError):
                return False
            meta["cached_at"] = now
            _atomic_write(meta_path, json.dumps(meta, indent=2).encode("utf-8"))
        return True

    def remove(self, skill_name: str) -> None:
        """Remove one skill's entry from the index.

        Preserves ``<sha>/`` dirs still referenced by other skill names
        (Phase 147 byte-determinism guarantees cross-skill dedup). Only
        deletes dirs that become orphaned after the removal.
        """
        index = self._load_index()
        entry = index.pop(skill_name, None)
        if entry is None:
            return
        shas_to_check = {pb["sha"] for pb in entry.get("per_bundle", [])}
        # Compute which SHAs are still referenced by any remaining skill.
        still_referenced: set[str] = set()
        for other in index.values():
            for pb in other.get("per_bundle", []):
                still_referenced.add(pb["sha"])
        # Delete orphaned dirs.
        for sha in shas_to_check - still_referenced:
            self._delete_sha_dir(sha)
        self._save_index(index)

    # ------------------------------------------------------------------
    # LRU eviction
    # ------------------------------------------------------------------

    def _iter_sha_dirs(self) -> list[tuple[str, float, int]]:
        """Return [(sha_dir_name, cached_at, total_bytes), ...] for every
        ``<sha>/`` dir currently on disk.

        ``cached_at`` defaults to ``inf`` for dirs missing metadata.json
        (keeps them from being evicted first — we haven't decided anything
        about them yet; likely fresh or being written).
        """
        out: list[tuple[str, float, int]] = []
        if not self._dir.exists():
            return out
        for child in self._dir.iterdir():
            if not child.is_dir():
                continue
            bundle_path = child / "bundle.zip"
            meta_path = child / "metadata.json"
            if not bundle_path.exists():
                continue
            try:
                size = bundle_path.stat().st_size
            except OSError:
                continue
            cached_at = float("inf")
            if meta_path.exists():
                try:
                    cached_at = float(
                        json.loads(meta_path.read_text()).get("cached_at", float("inf"))
                    )
                except (json.JSONDecodeError, OSError, TypeError, ValueError):
                    pass
            out.append((child.name, cached_at, size))
        return out

    def evict_lru(self) -> int:
        """Enforce the 100 MB hard cap with LRU eviction.

        Scans every ``<sha>/`` dir, sums bundle sizes. If total exceeds
        :data:`_HARD_CAP_BYTES`, deletes the oldest entries (by
        ``metadata.cached_at`` ascending) until total drops below the cap.

        Emits a stderr WARN if total exceeds the soft cap (80 MB) AFTER
        eviction (or if already below hard cap but above soft cap) —
        signals the user should consider running ``flywheel_refresh_skills``
        to prune.

        Returns the count of ``<sha>/`` dirs removed.
        """
        entries = self._iter_sha_dirs()
        total = sum(e[2] for e in entries)
        removed = 0

        if total > _HARD_CAP_BYTES:
            # Oldest first.
            entries.sort(key=lambda e: e[1])
            # Also remove any skill-name references in the index that point
            # at the SHAs we delete, to keep index coherent.
            index = self._load_index()
            index_dirty = False
            for sha, _cached_at, size in entries:
                if total <= _HARD_CAP_BYTES:
                    break
                self._delete_sha_dir(sha)
                total -= size
                removed += 1
                # Drop any index entry referencing this SHA.
                for name in list(index.keys()):
                    refs = index[name].get("per_bundle", [])
                    if any(pb.get("sha") == sha for pb in refs):
                        index.pop(name, None)
                        index_dirty = True
            if index_dirty:
                self._save_index(index)

        if total > _SOFT_CAP_BYTES:
            size_mb = total / (1024 * 1024)
            sys.stderr.write(
                f"WARN: Flywheel skill cache at {size_mb:.1f}MB — consider "
                f"`flywheel_refresh_skills` to prune.\n"
            )
        return removed

    # ------------------------------------------------------------------
    # Refresh — caller injects a fetcher to avoid FlywheelClient import cycle
    # ------------------------------------------------------------------

    def refresh(self, name: str | None = None, *, fetcher) -> RefreshResult:
        """Force re-fetch of one or all cached skills.

        Args:
            name: If None, refresh every entry currently in the index.
                Otherwise refresh just ``name`` (caller handles transitive
                deps by calling us per root skill).
            fetcher: Callable ``(skill_name, *, bypass_cache=True) ->
                (metadata, bundles)``. Caller injects
                :meth:`FlywheelClient.fetch_skill_assets_bundle` bound to
                an authenticated client — avoids a circular import.

        Returns:
            :class:`RefreshResult` with counts + per-skill status dicts.

        Tamper handling:
            If a load during refresh raises
            :class:`~flywheel_mcp.bundle.BundleIntegrityError`, the dir
            has already been auto-deleted by the loader. We log a stderr
            line (``cache_entry_tampered: ...``), increment
            ``tampered_count``, and refetch authoritative bytes via the
            injected fetcher.
        """
        # Import deferred so non-refresh code paths don't pay for it.
        from flywheel_mcp.bundle import BundleIntegrityError

        index = self._load_index()
        target_names = [name] if name is not None else list(index.keys())
        result = RefreshResult()

        for skill_name in target_names:
            old_sha = ""
            entry = index.get(skill_name)
            if entry is not None:
                old_sha = entry.get("root_sha", "")

            try:
                metadata, bundles = fetcher(skill_name, bypass_cache=True)
            except BundleIntegrityError as exc:
                # Shouldn't happen — fetcher pulls from network, not cache.
                # Still: handle defensively to avoid crashing the whole loop.
                sys.stderr.write(
                    f"cache_entry_tampered: skill={skill_name} "
                    f"old_sha={exc.expected_sha[:12]}... "
                    f"authoritative_sha={exc.actual_sha[:12]}... "
                    f"correlation_id={getattr(exc, 'correlation_id', '-')}\n"
                )
                result.tampered_count += 1
                result.per_skill.append(
                    {"name": skill_name, "old_sha": old_sha,
                     "new_sha": "", "status": "tampered"}
                )
                continue
            except Exception as exc:
                # Network / backend failure — record and move on.
                result.per_skill.append(
                    {"name": skill_name, "old_sha": old_sha,
                     "new_sha": "", "status": f"error: {exc}"}
                )
                continue

            correlation_id = metadata.get("correlation_id", "")
            self.put(
                skill_name, metadata, bundles, correlation_id=correlation_id
            )
            new_sha = metadata.get("rollup_sha", "")
            status = "refetched" if old_sha and old_sha != new_sha else (
                "unchanged" if old_sha == new_sha else "new"
            )
            result.refetched += 1
            result.per_skill.append(
                {"name": skill_name, "old_sha": old_sha,
                 "new_sha": new_sha, "status": status}
            )

        return result
