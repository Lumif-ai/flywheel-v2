"""Regression: GET /api/v1/ping is a clean network baseline -- zero DB queries.

This test asserts TWO invariants for the Phase 151.1 ``/ping`` endpoint:

1. Happy-path: returns 200 with body ``{"ok": True}`` -- byte-identical
   across deploys so same-region comparison in Plan 03 isn't skewed.
2. Zero-DB invariant: ``db_count_cv.get() == 0`` after a /ping request.
   ``db_count_cv`` is the ContextVar maintained by Plan 01's
   :class:`TimingMiddleware`; it tracks DB roundtrips per request via a
   SQLAlchemy ``before_cursor_execute`` hook.

**Hard dependency on Plan 01.** This test imports ``db_count_cv`` from
``flywheel.middleware.timing`` which is created by Plan 01 (same phase,
parallel Wave 1). If Plan 01 hasn't merged when this test runs, the
import will fail. That's expected in parallel Wave-1 execution -- the
phase-level verify step re-runs tests after BOTH plans commit, at which
point this test has access to the middleware and asserts the contract.

Why this test matters: research Pitfall 8 flags ``/health`` as a
CONTAMINATED baseline because it does ``SELECT 1``. If someone later
adds a DB query to ``/ping`` (e.g. "add a build-info check"), this test
fails loudly. Without the test, the regression would silently
invalidate Plan 03's same-region comparison months later.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from flywheel.api.health import router as health_router
from flywheel.middleware.timing import TimingMiddleware, db_count_cv


@pytest.fixture
def app_with_ping() -> FastAPI:
    """Minimal FastAPI app with just the health router + TimingMiddleware.

    Scoped to this test module so we don't pull in the full app's
    dependencies (Depends(require_tenant), DB pool, etc.). ``/ping``
    has zero Depends() by design, so this minimal app is sufficient.
    """
    app = FastAPI()
    app.add_middleware(TimingMiddleware)
    app.include_router(health_router, prefix="/api/v1")
    return app


def test_ping_returns_ok(app_with_ping: FastAPI) -> None:
    """Happy path: /api/v1/ping returns 200 with body {'ok': True}."""
    client = TestClient(app_with_ping)
    resp = client.get("/api/v1/ping")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_ping_does_zero_db_work(app_with_ping: FastAPI) -> None:
    """Research Pitfall 8: /ping must NOT hit the DB (unlike /health).

    ``/health`` does ``SELECT 1`` which contaminates the network baseline.
    ``/ping`` exists specifically to isolate network + TLS + tunnel cost
    from handler + DB cost. If this test fails, someone added a DB query
    to /ping -- revert it, move the query to /health or a new endpoint.
    """
    client = TestClient(app_with_ping)
    # Pre-seed counter to 0 so we can detect increments from /ping only.
    db_count_cv.set(0)
    resp = client.get("/api/v1/ping")
    assert resp.status_code == 200
    # db_count_cv tracks DB roundtrips within the request scope; after
    # the response returns, it still reflects the final per-request count
    # (ContextVars are not reset between TestClient calls unless the
    # middleware explicitly resets them).
    count = db_count_cv.get()
    assert count == 0, (
        f"/ping hit the DB {count} times -- not a clean network baseline. "
        "Revert the DB query or move it to /health."
    )
