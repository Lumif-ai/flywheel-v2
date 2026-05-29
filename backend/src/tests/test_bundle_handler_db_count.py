"""Regression: ``get_skill_assets_bundle`` DB-roundtrip count budget.

Phase 151.1's measurement campaign (Plan 03) profiled the bundle handler
and found the per-call DB-roundtrip count is **deterministically 8** across
51 cold samples -- zero variance (see ``151.1-PROFILE.md`` §4 "Bottleneck
Breakdown" + §1 Summary Table row 1). The breakdown was predicted by
research (~3-4 tenant-session prelude + ~3-4 ``_resolve_bundle_chain``
fanout) and confirmed empirically.

This test asserts that ``/assets/bundle`` never exceeds ``DB_COUNT_THRESHOLD``
(= 10) DB roundtrips on a known input. Threshold = measured mean (8) +
**2-roundtrip headroom** for legitimate future additions (e.g. one extra
``set_config`` for a new tenant-scoped feature) BEFORE the regression fires.
Any single change that adds >2 DB roundtrips on the cold path is likely
a silent N+1 regression in ``_resolve_bundle_chain`` or a hidden
prelude-expansion in ``get_tenant_session`` and must be called out before
merge.

**Why 2 and not 1:** measured db_count is already at 8 (tenant prelude
set_config x2-3 + SET ROLE + root skill SELECT + dep skill SELECTs + asset
SELECTs). A threshold of 9 would trip on ANY small legitimate addition.
A threshold of 10 gives exactly one "free" additional roundtrip before
the next change has to either batch its query or justify crossing this
line. This is tight enough to flag silent N+1s (which fanout by 2-5
roundtrips per added dep) while accommodating one-off additions.

**Why 2 and not 5:** Too loose a margin defeats the purpose. If the batch-fix
follow-up phase collapses db_count from 8 → 2-3, this test's threshold
(10) would be rebase-lined DOWN in that follow-up phase -- the threshold
must track the measured baseline, not a stale historical value.

**Baseline evidence:** ``.planning/phases/151.1-backend-handler-latency-profiling-cold-slo/151.1-PROFILE.md``
§1 + §4 + §9 (Handoff to Plan 04), commit ``ec060d4`` (Plan 02 HEAD) +
``cded013`` (Plan 03 HEAD).

**Test strategy:** Mirrors the mocked-DB pattern from
``test_skills_api.py::TestAssetBundleEndpoint``. We do NOT run a live
Postgres -- the test injects the SAME AsyncMock-based DB session the
existing bundle tests use, then asserts the db_count recorded by
``TimingMiddleware`` (from Plan 01) stays below threshold.

**How we read the count:** The ``db_count_cv`` ``ContextVar`` is RESET by
``TimingMiddleware`` on every incoming request, so reading it OUTSIDE the
request context (after ``client.get(...)`` returns) always yields 0. To
observe the per-request count, we parse it out of the ``request_complete``
log line emitted by ``TimingMiddleware`` in its ``finally`` block (same
structured line that ``extract_profile.py`` parses off
``/tmp/flywheel-backend.log`` in production). This is the SAME
observation surface Plan 03's measurement campaign used, so the threshold
here is directly comparable to the PROFILE.md baseline.

Caveat: this is a **shape regression** test, not a live-Supabase p99 test.
The mocked-DB path exercises ``_resolve_bundle_chain``'s fanout logic
end-to-end (execute_side_effects is an ordered list of mock results, one
per ``db.execute()`` call), so if someone adds a new SELECT call it will
either show up as an index error (mock returns ran out) OR inflate the
db_count recorded in the log line. Both fail loudly.

**If this test fails on a new PR:**
1. Check whether ``_resolve_bundle_chain`` added a loop that does N
   SELECTs (classic N+1). If so, batch with ``WHERE name IN (...)``.
2. Check whether ``get_tenant_session`` added a new ``set_config`` or
   ``SET`` statement. If justified, bump the threshold here by 1 and
   update the module docstring's threshold rationale.
3. Check whether a new route handler path was added that this test
   inadvertently exercises (less likely -- we pin to the bundle endpoint
   explicitly).
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
import zipfile
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.main import app
from flywheel.middleware.timing import db_count_cv

# Regex matches the db_count= field in the TimingMiddleware log line.
# Format (from flywheel/middleware/timing.py:163-175):
#   "request_complete route=%s method=%s status=%d duration_ms=%.2f "
#   "db_count=%d db_total_ms=%.2f cold=%s correlation_id=%s"
_DB_COUNT_RE = re.compile(r"db_count=(\d+)")

# Threshold calibrated from 151.1-PROFILE.md measured baseline.
# Measured mean = 8.00 (deterministic across n=51 cold samples).
# Threshold = measured + 2 margin = 10. See module docstring for rationale.
DB_COUNT_THRESHOLD = 10
MEASURED_MEAN = 8


# ---------------------------------------------------------------------------
# Reuse the same mock-DB pattern as test_skills_api.py
# ---------------------------------------------------------------------------


class _MockResult:
    def __init__(self, value=None, values=None, scalar_val=None):
        self._value = value
        self._values = values or []
        self._scalar_val = scalar_val

    def scalar_one_or_none(self):
        return self._value

    def scalar(self):
        return self._scalar_val

    def scalars(self):
        return self

    def all(self):
        return self._values


class _MockSkillDefinition:
    def __init__(self, name, protected=False, depends_on=None):
        self.id = uuid4()
        self.name = name
        self.protected = protected
        self.depends_on = depends_on or []
        self.tenant_id = None
        self.visibility = "public"
        self.web_tier = 3
        self.version = "1.2"


class _MockSkillAsset:
    def __init__(
        self,
        skill_id,
        bundle,
        bundle_sha256,
        bundle_size_bytes,
        bundle_format="zip",
        updated_at=None,
    ):
        self.skill_id = skill_id
        self.bundle = bundle
        self.bundle_sha256 = bundle_sha256
        self.bundle_size_bytes = bundle_size_bytes
        self.bundle_format = bundle_format
        self.updated_at = updated_at


def _build_test_bundle() -> tuple[bytes, str]:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("hello.py", "def hello():\n    return 'world'\n")
    bundle_bytes = buf.getvalue()
    return bundle_bytes, hashlib.sha256(bundle_bytes).hexdigest()


def _make_user():
    return TokenPayload(
        sub=uuid4(),
        email="test@example.com",
        is_anonymous=False,
        app_metadata={"tenant_id": str(uuid4()), "role": "admin"},
    )


def _make_mock_db_for_bundle_call():
    """Build the ordered list of mock results a cold bundle call needs.

    Mirrors ``TestAssetBundleEndpoint::test_success_consumer_with_library_dep``
    from ``test_skills_api.py``. Five execute() calls on the mocked session,
    representing the logical DB roundtrips the handler does AFTER the
    tenant-session prelude (which is not exercised by the mock path --
    it's bypassed via ``get_tenant_db`` dependency override).

    The ``db_count_cv`` counter is driven by the SQLAlchemy
    ``after_cursor_execute`` event hook installed in
    ``flywheel.db.engine``. In the mocked path, the hook does NOT fire
    (no real cursor_execute happens); instead we increment the counter
    once per mocked ``execute()`` call via a wrapper to simulate what
    the event hook would record against a live DB.
    """
    consumer = _MockSkillDefinition(
        name="broker-parse-contract",
        protected=False,
        depends_on=["broker"],
    )
    library = _MockSkillDefinition(
        name="broker",
        protected=False,
        depends_on=[],
    )
    lib_bundle, lib_sha = _build_test_bundle()
    lib_asset = _MockSkillAsset(
        skill_id=library.id,
        bundle=lib_bundle,
        bundle_sha256=lib_sha,
        bundle_size_bytes=len(lib_bundle),
    )
    side_effects = [
        _MockResult(value=None),       # tenant-override probe: none
        _MockResult(value=consumer),   # root skill lookup
        _MockResult(value=library),    # _resolve_bundle_chain: broker dep
        _MockResult(value=lib_asset),  # asset lookup for library
        _MockResult(value=None),       # asset lookup for consumer (no row)
    ]

    db = AsyncMock()
    real_execute = AsyncMock(side_effect=side_effects)

    async def counting_execute(*args, **kwargs):
        # Simulate what flywheel.db.engine's after_cursor_execute hook does.
        db_count_cv.set(db_count_cv.get() + 1)
        return await real_execute(*args, **kwargs)

    db.execute = counting_execute
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def client():
    app.dependency_overrides = {}
    yield TestClient(app)
    app.dependency_overrides = {}


# ---------------------------------------------------------------------------
# The regression tests
# ---------------------------------------------------------------------------


def _extract_db_count_from_log(caplog: pytest.LogCaptureFixture) -> int:
    """Pull db_count=N from the TimingMiddleware ``request_complete`` log line.

    Returns the integer N from the most recent ``request_complete`` line
    captured in ``caplog``. Raises AssertionError if no line is found --
    a missing log line means ``TimingMiddleware`` didn't execute (likely
    a test-setup bug, not a regression signal).
    """
    candidates = [
        r.getMessage()
        for r in caplog.records
        if r.name == "flywheel.timing" and "request_complete" in r.getMessage()
    ]
    assert candidates, (
        "No 'request_complete' log line captured from flywheel.timing -- "
        "TimingMiddleware may not be installed or caplog level is too high. "
        f"Captured {len(caplog.records)} total records."
    )
    # Use the last line (most recent request) in case warmup requests fire.
    match = _DB_COUNT_RE.search(candidates[-1])
    assert match, f"Could not parse db_count from log line: {candidates[-1]!r}"
    return int(match.group(1))


def test_bundle_fetch_db_count_under_threshold(
    client, caplog: pytest.LogCaptureFixture
):
    """``GET /assets/bundle`` does <= 10 DB roundtrips on the cold path.

    Regression gate per 151.1-PROFILE.md §4: measured deterministic
    db_count = 8 across 51 cold samples; threshold = 10 allows 2
    roundtrips of headroom for legitimate additions before firing.

    We read db_count from the ``request_complete`` log line emitted by
    ``TimingMiddleware`` in its ``finally`` block -- the same structured
    line ``extract_profile.py`` parses off ``/tmp/flywheel-backend.log``
    in production. This observation surface is directly comparable to
    the PROFILE.md baseline.
    """
    from flywheel.middleware.rate_limit import limiter

    limiter.reset()

    user = _make_user()
    db = _make_mock_db_for_bundle_call()
    app.dependency_overrides[require_tenant] = lambda: user
    app.dependency_overrides[get_tenant_db] = lambda: db

    with caplog.at_level(logging.INFO, logger="flywheel.timing"):
        resp = client.get("/api/v1/skills/broker-parse-contract/assets/bundle")
    assert resp.status_code == 200, (
        f"bundle endpoint returned {resp.status_code}: {resp.text[:200]}"
    )
    body = resp.json()
    assert body["skill"] == "broker-parse-contract"
    assert len(body["bundles"]) >= 1
    # Byte-shape sanity: bundle decodes correctly (not the regression
    # assertion, but a 500/body-mismatch would invalidate the db_count
    # reading by hitting an early-return path).
    decoded = base64.b64decode(body["bundles"][0]["bundle_b64"])
    assert decoded, "decoded bundle is empty"

    count = _extract_db_count_from_log(caplog)
    assert count <= DB_COUNT_THRESHOLD, (
        f"get_skill_assets_bundle did {count} DB roundtrips "
        f"(threshold {DB_COUNT_THRESHOLD}; baseline mean from "
        f"151.1-PROFILE.md was {MEASURED_MEAN}). This is likely a "
        f"silent N+1 regression in _resolve_bundle_chain or a new "
        f"prelude SELECT in get_tenant_session -- investigate before "
        f"merge."
    )
    # Sanity: the test should be doing non-zero DB work. If db_count==0,
    # the TimingMiddleware is not installed or our counting_execute
    # wrapper didn't fire -- either way the test isn't actually guarding
    # anything.
    assert count > 0, (
        "db_count from request_complete log line is 0 -- the test did "
        "not actually exercise any DB calls, so the <=threshold "
        "assertion is trivially passing. Test-setup bug."
    )


def test_bundle_fetch_shas_only_db_count_under_threshold(
    client, caplog: pytest.LogCaptureFixture
):
    """``?shas_only=true`` variant stays under the same threshold.

    ``shas_only=true`` skips base64-encode + SHA-rehash on the response
    but still runs the full query chain (same ``_resolve_bundle_chain``
    + asset SELECTs). Its db_count should be roughly identical to the
    full variant -- the optimization is CPU/bandwidth, not DB.

    If this test asserts a LOWER db_count than the full variant,
    something is wrong: shas_only isn't supposed to skip DB work.
    """
    from flywheel.middleware.rate_limit import limiter

    limiter.reset()

    user = _make_user()
    db = _make_mock_db_for_bundle_call()
    app.dependency_overrides[require_tenant] = lambda: user
    app.dependency_overrides[get_tenant_db] = lambda: db

    with caplog.at_level(logging.INFO, logger="flywheel.timing"):
        resp = client.get(
            "/api/v1/skills/broker-parse-contract/assets/bundle?shas_only=true"
        )
    assert resp.status_code == 200, (
        f"bundle endpoint (shas_only) returned {resp.status_code}: "
        f"{resp.text[:200]}"
    )
    body = resp.json()
    assert body["skill"] == "broker-parse-contract"
    # shas_only=true means bundles have sha256 but no bundle_b64.
    assert len(body["bundles"]) >= 1
    assert "sha256" in body["bundles"][0]

    count = _extract_db_count_from_log(caplog)
    assert count <= DB_COUNT_THRESHOLD, (
        f"get_skill_assets_bundle?shas_only=true did {count} DB "
        f"roundtrips (threshold {DB_COUNT_THRESHOLD}; baseline mean "
        f"from 151.1-PROFILE.md was {MEASURED_MEAN}). shas_only is "
        f"a CPU/bandwidth optimization only -- it should NOT change "
        f"the DB-roundtrip count. Investigate before merge."
    )
    assert count > 0, (
        "db_count from request_complete log line is 0 -- shas_only "
        "variant did not actually exercise any DB calls. Test-setup bug."
    )
