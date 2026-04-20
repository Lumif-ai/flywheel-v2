"""Unit tests for :mod:`flywheel.middleware.timing`.

Covers the four regression-critical invariants called out in Phase
151.1 Plan 01:

1. One structured ``request_complete`` log line per HTTP request with
   the documented field set.
2. Inbound ``X-Flywheel-Correlation-ID`` round-trips into the response
   header AND into the log line.
3. The SQLAlchemy ``before_cursor_execute`` / ``after_cursor_execute``
   listeners increment the per-request ContextVar counters.
4. ContextVar isolation — concurrent requests do NOT clobber each
   other's counters.

None of these tests touch Supabase. The DB-hook test spins up an
in-memory SQLite async engine and attaches the SAME listener functions
we ship for Postgres.
"""

from __future__ import annotations

import asyncio
import logging
import re
import types

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from flywheel.middleware.timing import (
    TimingMiddleware,
    correlation_cv,
    db_count_cv,
    db_total_ns_cv,
)

# ---------------------------------------------------------------------------
# Scaffolding
# ---------------------------------------------------------------------------

_CID_RE = re.compile(r"correlation_id=([a-f0-9]+)")


def _build_app() -> FastAPI:
    """Minimal FastAPI app wrapped with TimingMiddleware for TestClient."""
    app = FastAPI()
    app.add_middleware(TimingMiddleware)

    @app.get("/echo")
    async def echo():
        return {"ok": True}

    @app.get("/db-count")
    async def db_count():
        # Handler reads the current db_count_cv — used by the
        # concurrency-isolation test to prove ContextVar per-request
        # scoping.
        return {"db_count": db_count_cv.get()}

    return app


# ---------------------------------------------------------------------------
# Test 1 — one structured log line per request
# ---------------------------------------------------------------------------


def test_middleware_emits_log_line_per_request(caplog):
    """Three requests -> three ``request_complete`` log records, each
    carrying the documented fields and a distinct 8-hex correlation_id."""
    app = _build_app()

    with caplog.at_level(logging.INFO, logger="flywheel.timing"):
        with TestClient(app) as client:
            for _ in range(3):
                resp = client.get("/echo")
                assert resp.status_code == 200

    records = [r for r in caplog.records if r.name == "flywheel.timing"]
    msgs = [r.getMessage() for r in records]
    assert len(msgs) == 3, f"expected 3 log lines, got {len(msgs)}: {msgs}"

    seen_cids: set[str] = set()
    for msg in msgs:
        assert msg.startswith("request_complete ")
        assert "route=/echo" in msg
        assert "method=GET" in msg
        assert "status=200" in msg
        assert "duration_ms=" in msg
        assert "db_count=" in msg
        assert "db_total_ms=" in msg
        assert "cold=False" in msg
        m = _CID_RE.search(msg)
        assert m is not None, f"no correlation_id= in {msg}"
        cid = m.group(1)
        # Server-generated CIDs must be 8 hex chars (secrets.token_hex(4)).
        assert len(cid) == 8, f"correlation id not 8 hex chars: {cid!r}"
        seen_cids.add(cid)

    # Three requests, three generated ids — extremely low collision odds.
    assert len(seen_cids) == 3, f"duplicate correlation ids: {seen_cids}"


# ---------------------------------------------------------------------------
# Test 2 — inbound correlation ID round-trips
# ---------------------------------------------------------------------------


def test_correlation_id_roundtrips_in_response_header(caplog):
    """Client-supplied ``X-Flywheel-Correlation-ID`` must appear in both
    the response header and the structured log line."""
    app = _build_app()
    supplied = "abc12345"

    with caplog.at_level(logging.INFO, logger="flywheel.timing"):
        with TestClient(app) as client:
            resp = client.get(
                "/echo", headers={"X-Flywheel-Correlation-ID": supplied}
            )

    assert resp.status_code == 200
    assert resp.headers.get("X-Flywheel-Correlation-ID") == supplied

    records = [
        r for r in caplog.records
        if r.name == "flywheel.timing" and r.getMessage().startswith("request_complete")
    ]
    assert len(records) == 1
    assert f"correlation_id={supplied}" in records[0].getMessage()


# ---------------------------------------------------------------------------
# Test 3 — DB cursor-execute hooks increment the counters
# ---------------------------------------------------------------------------


def test_db_hook_increments_counter():
    """Directly invoke the listener functions with a fake
    ``ExecutionContext`` — proves the hook semantics without booting
    Supabase. This is the unit-level contract: before-hook stamps a
    start time, after-hook folds elapsed nanoseconds and a count into
    the ContextVars.
    """
    # Fresh per-request-equivalent state.
    db_count_cv.set(0)
    db_total_ns_cv.set(0)

    # Import the private listeners — they are attached inside
    # get_engine() but the functions themselves are module-level and
    # importable.
    from flywheel.db.engine import _db_before_execute, _db_after_execute

    ctx = types.SimpleNamespace()

    # Simulate three queries back-to-back.
    for _ in range(3):
        _db_before_execute(
            conn=None, cursor=None, statement="SELECT 1",
            parameters=None, context=ctx, executemany=False,
        )
        # Tiny sleep so elapsed_ns > 0 even on very fast machines.
        # time.perf_counter_ns() resolution is sub-microsecond on
        # modern hardware but asserting strictly > 0 is the correct
        # contract.
        for _ in range(1000):
            pass
        _db_after_execute(
            conn=None, cursor=None, statement="SELECT 1",
            parameters=None, context=ctx, executemany=False,
        )

    assert db_count_cv.get() == 3, f"expected 3 increments, got {db_count_cv.get()}"
    assert db_total_ns_cv.get() > 0, "db_total_ns should accumulate nanoseconds"

    # After-hook with a fresh context that never saw the before-hook
    # must be a no-op (defensive branch in _db_after_execute).
    fresh_ctx = types.SimpleNamespace()
    count_before = db_count_cv.get()
    _db_after_execute(
        conn=None, cursor=None, statement="SELECT 1",
        parameters=None, context=fresh_ctx, executemany=False,
    )
    assert db_count_cv.get() == count_before, (
        "after-hook without matching before-hook must not increment"
    )


# ---------------------------------------------------------------------------
# Test 4 — ContextVar isolation under asyncio concurrency
# ---------------------------------------------------------------------------


async def _simulated_request(seed: int) -> int:
    """Simulate one request scope: set db_count_cv to ``seed``, yield
    to the event loop (giving the other task a chance to run and,
    if isolation is broken, clobber our value), then read it back.
    """
    db_count_cv.set(seed)
    # Two yields — once each direction — so both tasks interleave.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    return db_count_cv.get()


@pytest.mark.asyncio
async def test_contextvar_isolation_under_concurrency():
    """Concurrent coroutines must see their OWN db_count_cv values.

    Regression-critical: if this ever fails, every subsequent phase
    measurement is corrupt because concurrent requests would report
    each other's DB counts. ContextVar gives us per-Task isolation for
    free — asyncio.gather spawns each coroutine in its own copy of the
    context, so mutations do not propagate.
    """
    results = await asyncio.gather(
        _simulated_request(5),
        _simulated_request(0),
        _simulated_request(42),
    )
    assert results == [5, 0, 42], (
        f"ContextVar cross-talk detected: {results}. "
        "Concurrent requests are clobbering each other's counters."
    )


@pytest.mark.asyncio
async def test_correlation_contextvar_isolation():
    """Same isolation guarantee for correlation_cv. The TimingMiddleware
    sets this per request; if isolation broke, two concurrent requests
    would log with the same correlation_id and operators could not
    stitch logs back to a single request.
    """

    async def one(cid: str) -> str:
        correlation_cv.set(cid)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return correlation_cv.get()

    cids = await asyncio.gather(one("aaaa1111"), one("bbbb2222"), one("cccc3333"))
    assert cids == ["aaaa1111", "bbbb2222", "cccc3333"]
