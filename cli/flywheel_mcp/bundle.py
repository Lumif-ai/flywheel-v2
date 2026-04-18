"""Client-side skill-bundle materializer.

Provides :func:`materialize_skill_bundle`, a context manager that fetches a
consumer + transitive library bundle chain from the Flywheel backend
(:func:`FlywheelClient.fetch_skill_assets_bundle`), verifies SHA-256 on every
bundle BEFORE extraction, extracts each zip through a path-traversal-safe
helper into a single ephemeral :class:`tempfile.TemporaryDirectory`, prepends
``sys.path`` for the duration of the ``with`` block, and cleans both
``sys.path`` and the temp dir on exit (success *or* exception).

The four exception classes are defined here so that Phase 152 (offline cache
layer) can extend :class:`BundleCacheError` without breaking the public API
of ``cli.flywheel_mcp.bundle``.

This module uses **stdlib + existing CLI surface only** — no new
third-party dependencies.
"""

from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

__all__ = [
    "BundleError",
    "BundleFetchError",
    "BundleIntegrityError",
    "BundleSecurityError",
    "BundleCacheError",
    "materialize_skill_bundle",
]


# ---------------------------------------------------------------------------
# Exception taxonomy
# ---------------------------------------------------------------------------


class BundleError(Exception):
    """Base class for all bundle-delivery errors."""

    pass


class BundleFetchError(BundleError):
    """HTTP or transport-level failure fetching a bundle.

    Raised after the retry loop exhausts or when a non-retryable status
    (401 post-refresh, 403, 404) is returned by the backend.
    """

    def __init__(self, skill_name: str, status_code: int | None, message: str):
        self.skill_name = skill_name
        self.status_code = status_code
        self.message = message
        super().__init__(
            f"{message} (skill={skill_name}, status={status_code})"
        )


class BundleIntegrityError(BundleError):
    """SHA-256 mismatch on received bundle bytes.

    Raised by :func:`materialize_skill_bundle` BEFORE any extraction
    occurs — protects against zip bombs and malformed archives by
    refusing to let :class:`zipfile.ZipFile` touch tampered bytes.
    """

    def __init__(self, skill_name: str, expected_sha: str, actual_sha: str):
        self.skill_name = skill_name
        self.expected_sha = expected_sha
        self.actual_sha = actual_sha
        super().__init__(
            f"Bundle integrity check failed for {skill_name}. "
            f"Run `flywheel refresh-skills` to re-fetch, or contact support "
            f"if this persists. "
            f"(expected sha256={expected_sha[:12]}..., "
            f"got sha256={actual_sha[:12]}...)"
        )


class BundleSecurityError(BundleError):
    """Path-traversal attempt detected in a zip entry.

    Raised by :func:`_safe_extract` BEFORE any call to ``zf.extractall`` —
    a single malicious entry aborts the whole bundle (fail-closed).
    """

    def __init__(self, skill_name: str, entry_path: str):
        self.skill_name = skill_name
        self.entry_path = entry_path
        super().__init__(
            f"Refused to extract {skill_name}: entry '{entry_path}' "
            f"escapes bundle root."
        )


class BundleCacheError(BundleError):
    """Placeholder for Phase 152 offline-cache errors.

    Not raised in Phase 150 — defined here so the class is part of the
    public API surface from day one and Phase 152 can ship the cache
    layer without breaking import order.
    """

    def __init__(self, skill_name: str, reason: str):
        self.skill_name = skill_name
        self.reason = reason
        super().__init__(f"Bundle cache error for {skill_name}: {reason}")


# ---------------------------------------------------------------------------
# Path-traversal guard
# ---------------------------------------------------------------------------


def _safe_extract(
    zf: zipfile.ZipFile, dest: Path, skill_name: str
) -> None:
    """Extract ``zf`` into ``dest`` after verifying every entry stays in-root.

    The guard uses :py:meth:`pathlib.Path.is_relative_to` (Python 3.9+) after
    :py:meth:`pathlib.Path.resolve` normalizes both absolute paths and
    ``..``-traversal segments.

    If any entry escapes ``dest``, :class:`BundleSecurityError` is raised
    BEFORE ``zf.extractall`` runs. Single malicious entry aborts the entire
    extraction.

    Tested attack vectors: ``../etc/passwd``, ``/etc/passwd``,
    ``subdir/../../etc/passwd``, ``..\\..\\evil.exe``.
    """
    dest = dest.resolve()
    for member in zf.infolist():
        # Defensive: on POSIX, Python treats backslashes as literal filename
        # characters, so ``..\..\evil.exe`` would be a single safe filename.
        # On Windows, however, backslashes are path separators and the same
        # entry WOULD escape. Reject any entry containing backslashes as a
        # fail-closed cross-platform guard (no legitimate Phase 147 bundle
        # ships filenames with backslashes — sorted+deterministic seeds use
        # forward slashes or no separator).
        if "\\" in member.filename:
            raise BundleSecurityError(
                skill_name=skill_name,
                entry_path=member.filename,
            )
        # Resolve the target path: handles both absolute-path entries and
        # ``..`` segments in one call.
        target = (dest / member.filename).resolve()
        if not target.is_relative_to(dest):
            raise BundleSecurityError(
                skill_name=skill_name,
                entry_path=member.filename,
            )
    # All entries verified in-root. Extract in a single call.
    zf.extractall(dest)


# ---------------------------------------------------------------------------
# Materializer
# ---------------------------------------------------------------------------


@contextmanager
def materialize_skill_bundle(name: str) -> Iterator[Path]:
    """Fetch, verify, extract, and stage a skill bundle chain.

    Flow:
        1. Create a fresh :class:`FlywheelClient` and call
           ``fetch_skill_assets_bundle(name)``. Any
           :class:`BundleFetchError` propagates unchanged.
        2. Create a :class:`tempfile.TemporaryDirectory` (prefix
           ``flywheel-skill-``).
        3. For each ``(skill_name, expected_sha, bundle_bytes)`` in
           topological order (library-first, consumer-last as returned
           by the backend):

           a. **Verify-before-extract:** compute
              ``hashlib.sha256(bundle_bytes).hexdigest()`` and compare to
              the server-provided SHA. On mismatch, raise
              :class:`BundleIntegrityError` — :class:`zipfile.ZipFile` is
              never constructed on tampered bytes.
           b. Open :class:`zipfile.ZipFile` on an :class:`io.BytesIO`
              wrapper (malformed bundle never touches disk as partial
              tempfile) and call :func:`_safe_extract`.

        4. Prepend the temp root to ``sys.path`` inside a
           ``try``/``finally`` so the entry is popped on both normal
           exit AND any exception raised by user code.
        5. :class:`TemporaryDirectory.__exit__` deletes the temp root.

    Yields:
        pathlib.Path: absolute path to the temp root, which is also
        ``sys.path[0]`` for the duration of the ``with`` block.

    Raises:
        BundleFetchError: HTTP or transport failures (after retry +
            one-shot 401 refresh, propagated from the client).
        BundleIntegrityError: SHA-256 mismatch on any bundle in the chain.
        BundleSecurityError: zip-slip attempt detected in any entry.
    """
    # Import lazily so the exception classes above are importable even if
    # the rest of the CLI surface is not yet initialized (e.g. in unit tests
    # that monkeypatch FlywheelClient).
    from flywheel_mcp.api_client import FlywheelClient

    client = FlywheelClient()
    metadata, bundles = client.fetch_skill_assets_bundle(name)

    # DO NOT use ignore_cleanup_errors=True — SC5 depends on zero bytes
    # remaining on disk; silent cleanup failures would mask a leak.
    with tempfile.TemporaryDirectory(prefix="flywheel-skill-") as tmp:
        tmp_path = Path(tmp).resolve()

        for skill_name, expected_sha, bundle_bytes in bundles:
            # -----  Verify BEFORE extract (zip-bomb / tampered-bytes guard)
            actual_sha = hashlib.sha256(bundle_bytes).hexdigest()
            if actual_sha != expected_sha:
                raise BundleIntegrityError(
                    skill_name=skill_name,
                    expected_sha=expected_sha,
                    actual_sha=actual_sha,
                )

            # -----  Open from BytesIO so malformed bundle doesn't leave
            # a partial tempfile on disk before zipfile rejects it.
            with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
                _safe_extract(zf, tmp_path, skill_name)

        # -----  sys.path lifecycle: insert INSIDE try, remove in finally.
        # Any exception raised by the caller still unwinds both the
        # TemporaryDirectory context (cleanup) and the sys.path entry.
        sys.path.insert(0, str(tmp_path))
        try:
            yield tmp_path
        finally:
            # Use .remove() (by value) not .pop(0): safer if user code
            # mutated sys.path. Swallow ValueError — original exception
            # (if any) must propagate.
            try:
                sys.path.remove(str(tmp_path))
            except ValueError:
                pass
