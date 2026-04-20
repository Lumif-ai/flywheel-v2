"""Per-request timing + DB-roundtrip profiling middleware.

Pure-ASGI class-based middleware (NOT ``BaseHTTPMiddleware`` /
``@app.middleware("http")``): those add an additional task-scheduling
layer on every request, which adds ~1-2 ms of overhead AND perturbs the
exact measurement we're trying to take. See research §5 Pattern 1 +
Pitfall 1.

What this module provides (Phase 151.1 Plan 01):

1. Three module-level ``ContextVar``\\s that isolate per-request state
   across asyncio concurrency:

   - ``correlation_cv`` — the ``X-Flywheel-Correlation-ID`` header value
     for the current request (generated if the client didn't send one).
     Default is ``"-"`` which matches the fallback sentinel already used
     in ``flywheel.api.skills`` structured logs.
   - ``db_count_cv`` — number of DB round-trips the current request has
     made so far. Incremented by the SQLAlchemy ``after_cursor_execute``
     event hook in :mod:`flywheel.db.engine`.
   - ``db_total_ns_cv`` — cumulative DB time for the current request, in
     nanoseconds. Same hook increments it.

2. :class:`TimingMiddleware` — a pure-ASGI callable that:

   - Generates or reads the correlation ID, stamps it into
     ``correlation_cv``, and echoes it back in the response's
     ``X-Flywheel-Correlation-ID`` header so clients can stitch their
     own timing with our server-side log line.
   - Reads the ``X-Flywheel-Cache-State`` header (emitted by the client
     measurement tool in Plan 02). ``"cold"`` marks the request as the
     cold-path sentinel.
   - Resets the ``db_count_cv`` / ``db_total_ns_cv`` counters per
     request (so concurrent requests don't see each other's totals).
   - Wraps the downstream call in ``try/finally`` so the log line fires
     even on handler exception.
   - Emits exactly one structured ``logger.info`` line per completed
     HTTP request with: route, method, status, duration_ms, db_count,
     db_total_ms, cold, correlation_id.

Non-HTTP scope types (``lifespan``, ``websocket``) pass through
untouched — we only time HTTP requests.

Why ContextVar and not a plain dict keyed by request: Starlette does
not give the SQLAlchemy event hook a reference to the current Request,
and threading a ``request_state`` arg through every DB call site would
require rewriting half the codebase. ``ContextVar`` is asyncio-native
and propagates automatically to any coroutine / task spawned inside
the request scope.

Why ``time.perf_counter_ns`` and not ``time.time`` / ``time.monotonic``:
``perf_counter_ns`` is the highest-resolution monotonic clock available
on every supported platform and does not suffer from wall-clock jumps
(NTP adjustments, DST, leap seconds). Research §"Don't Hand-Roll" last
row.
"""

from __future__ import annotations

import logging
import secrets
import time
from contextvars import ContextVar

logger = logging.getLogger("flywheel.timing")

# Per-request isolated state. ContextVar is the asyncio-native way to
# keep these counters separate between concurrent requests — a plain
# module global would clobber across requests (research Pitfall 2).
correlation_cv: ContextVar[str] = ContextVar("correlation_id", default="-")
db_count_cv: ContextVar[int] = ContextVar("db_count", default=0)
db_total_ns_cv: ContextVar[int] = ContextVar("db_total_ns", default=0)

# Header constants. Kept as module-level bytes for cheap comparisons in
# the hot path (ASGI headers are bytes tuples).
_CORRELATION_HEADER = b"x-flywheel-correlation-id"
_CACHE_STATE_HEADER = b"x-flywheel-cache-state"
_COLD_VALUE = b"cold"


class TimingMiddleware:
    """Pure-ASGI middleware that emits one structured log line per HTTP request.

    Registration: ``app.add_middleware(TimingMiddleware)``. Must be
    added FIRST (before GZip / CORS / security headers) so LIFO
    ordering places it INNERMOST on the request path — its
    ``duration_ms`` then reflects only handler + DB time, excluding
    compression, CORS preflight, and security-header overhead.

    The middleware never raises. If the wrapped app raises, the ``try/
    finally`` still emits the log line with ``status=500`` (or whatever
    ``http.response.start`` carried before the exception).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Pass through non-HTTP scope types (lifespan, websocket). We
        # only time HTTP requests; websocket "duration" is
        # connection-lifetime which is a different concept entirely.
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # ---- Extract correlation ID + cold-path marker from request headers ----
        # ASGI headers are a list[tuple[bytes, bytes]]; names are
        # already lowercase per the spec so no case-fold needed.
        headers = scope.get("headers") or []
        incoming_cid: str | None = None
        cold = False
        for name, value in headers:
            if name == _CORRELATION_HEADER:
                try:
                    incoming_cid = value.decode("ascii", errors="replace")
                except Exception:
                    incoming_cid = None
            elif name == _CACHE_STATE_HEADER:
                if value == _COLD_VALUE:
                    cold = True

        # Generate an 8-hex-char correlation ID when the client didn't
        # send one. secrets.token_hex(4) => 8 chars, same scheme used
        # elsewhere in the codebase (flywheel.api.skills).
        cid = incoming_cid if incoming_cid else secrets.token_hex(4)

        # ---- Reset per-request ContextVars ----
        # Three independent ContextVar.set() calls; we don't use tokens
        # to reset because each request runs in its own asyncio Task
        # context and the vars won't leak upward.
        correlation_cv.set(cid)
        db_count_cv.set(0)
        db_total_ns_cv.set(0)

        # ---- Wrap send() to (a) capture status and (b) inject response header ----
        # We need the status for the log line. We also echo the
        # correlation ID in the response so the client can stitch its
        # own client-side timing with the server's structured log line.
        status_code = 500  # default if http.response.start never arrives (exception)
        cid_header = (_CORRELATION_HEADER, cid.encode("ascii", errors="replace"))

        async def send_wrapper(message):
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
                # Inject the correlation-id response header. ASGI
                # message["headers"] may be absent or a list; normalize.
                msg_headers = list(message.get("headers") or [])
                msg_headers.append(cid_header)
                message["headers"] = msg_headers
            await send(message)

        # ---- Time the handler and always emit the log line ----
        start_ns = time.perf_counter_ns()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter_ns() - start_ns) / 1e6
            route = scope.get("path", "-") or "-"
            method = scope.get("method", "-") or "-"
            db_count = db_count_cv.get()
            db_total_ms = db_total_ns_cv.get() / 1e6
            logger.info(
                "request_complete route=%s method=%s status=%d "
                "duration_ms=%.2f db_count=%d db_total_ms=%.2f "
                "cold=%s correlation_id=%s",
                route,
                method,
                status_code,
                duration_ms,
                db_count,
                db_total_ms,
                cold,
                cid,
            )
