"""Pytest configuration for the cli test suite.

Registers custom markers + default options:

- ``e2e``: end-to-end tests requiring live Flywheel backend + prod Supabase +
  ``~/.flywheel/credentials.json``. Skipped by default. Opt in with ``-m e2e``.

This mirrors the backend's Phase 146/148/150 pattern where live-infra tests
are marker-gated so CI / fresh-laptop runs don't need prod credentials.
"""

from __future__ import annotations


def pytest_configure(config):
    """Register custom markers to silence pytest's 'unknown marker' warning."""
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end test requiring live Flywheel backend + credentials "
        "(opt in with `-m e2e`)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip ``@pytest.mark.e2e`` tests unless ``-m e2e`` was passed.

    Without this, ``pytest cli/tests/`` would collect and attempt to run
    e2e tests, which require live infra. Marker-based selection (``-m e2e``)
    bypasses this skip.
    """
    import pytest

    markexpr = config.getoption("-m", default="")
    if markexpr and "e2e" in markexpr:
        return  # user explicitly opted in; let them run
    skip_e2e = pytest.mark.skip(
        reason="e2e tests need live backend + creds; opt in with `-m e2e`"
    )
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)
