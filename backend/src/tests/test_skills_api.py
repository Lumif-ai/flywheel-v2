"""Integration tests for skill endpoints.

Uses FastAPI TestClient with dependency overrides -- no real DB.
Verifies: list skills, start run, run detail, execution history,
SSE stream with late-connect replay.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import io
import json
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.main import app

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid4()
TEST_TENANT_ID = uuid4()
TEST_RUN_ID = uuid4()


def _make_user(tenant_id=TEST_TENANT_ID):
    return TokenPayload(
        sub=TEST_USER_ID,
        email="test@example.com",
        is_anonymous=False,
        app_metadata={"tenant_id": str(tenant_id), "role": "admin"},
    )


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockResult:
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


class MockSkillRun:
    def __init__(
        self,
        id=None,
        skill_name="meeting-prep",
        status="pending",
        input_text="test input",
        output=None,
        rendered_html=None,
        attribution=None,
        tokens_used=None,
        cost_estimate=None,
        duration_ms=None,
        events_log=None,
        error=None,
        created_at=None,
    ):
        self.id = id or uuid4()
        self.skill_name = skill_name
        self.status = status
        self.input_text = input_text
        self.output = output
        self.rendered_html = rendered_html
        self.attribution = attribution or {}
        self.tokens_used = tokens_used
        self.cost_estimate = cost_estimate
        self.duration_ms = duration_ms
        self.events_log = events_log or []
        self.error = error
        self.created_at = created_at or datetime.datetime(2026, 3, 20, tzinfo=datetime.timezone.utc)


class MockSkillDefinition:
    def __init__(
        self,
        id=None,
        name="test-skill",
        protected=False,
        version="1.2.3",
        depends_on=None,
    ):
        self.id = id or uuid4()
        self.name = name
        self.protected = protected
        self.version = version
        # Phase 150 Plan 01: fanout walker reads depends_on. Mock defaults
        # to empty list for backwards compat with pre-fanout tests.
        self.depends_on = list(depends_on) if depends_on else []


class MockSkillAsset:
    def __init__(self, skill_id, bundle, bundle_sha256, bundle_size_bytes, bundle_format="zip", updated_at=None):
        self.id = uuid4()
        self.skill_id = skill_id
        self.bundle = bundle
        self.bundle_sha256 = bundle_sha256
        self.bundle_size_bytes = bundle_size_bytes
        self.bundle_format = bundle_format
        self.updated_at = updated_at or datetime.datetime(2026, 4, 10, tzinfo=datetime.timezone.utc)


def _build_test_bundle():
    """Build an in-memory zip with one known .py file. Returns (bytes, sha256_hex)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("hello.py", "def hello():\n    return 'world'\n")
    bundle_bytes = buf.getvalue()
    digest = hashlib.sha256(bundle_bytes).hexdigest()
    return bundle_bytes, digest


def _mock_db(execute_side_effects=None):
    db = AsyncMock()
    if execute_side_effects:
        db.execute = AsyncMock(side_effect=execute_side_effects)
    else:
        db.execute = AsyncMock(return_value=MockResult())
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


# ===========================================================================
# TestListSkills
# ===========================================================================


class TestListSkills:
    def test_list_skills_empty(self, client):
        """GET /skills/ returns empty list when no skills directory."""
        user = _make_user()
        app.dependency_overrides[require_tenant] = lambda: user

        with patch("flywheel.api.skills.SKILLS_DIR") as mock_dir:
            mock_dir.is_dir.return_value = False
            resp = client.get("/api/v1/skills/")
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []

    def test_list_skills_with_entries(self, client, tmp_path):
        """GET /skills/ returns skills parsed from SKILL.md files."""
        user = _make_user()
        app.dependency_overrides[require_tenant] = lambda: user

        # Create a temp skill directory with SKILL.md
        skill_dir = tmp_path / "meeting-prep"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: meeting-prep\ndescription: Prepare for meetings\nversion: 1.0.0\ntags: [meetings]\n---\n# Meeting Prep"
        )

        with patch("flywheel.api.skills.SKILLS_DIR", tmp_path):
            resp = client.get("/api/v1/skills/")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["name"] == "meeting-prep"
            assert data["items"][0]["version"] == "1.0.0"

    def test_list_skills_requires_auth(self, client):
        """GET /skills/ without auth returns 401."""
        resp = client.get("/api/v1/skills/")
        assert resp.status_code == 401


# ===========================================================================
# TestStartRun
# ===========================================================================


class TestStartRun:
    def test_create_run(self, client, tmp_path):
        """POST /skills/runs returns 201 with run_id."""
        user = _make_user()
        mock_db = _mock_db()

        def mock_refresh(obj):
            obj.id = TEST_RUN_ID
            obj.status = "pending"

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        # Create skill dir so validation passes
        skill_dir = tmp_path / "meeting-prep"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: meeting-prep\ndescription: test\n---\n")

        with patch("flywheel.api.skills.SKILLS_DIR", tmp_path):
            resp = client.post(
                "/api/v1/skills/runs",
                json={"skill_name": "meeting-prep", "input_text": "test"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["run_id"] == str(TEST_RUN_ID)
            assert data["status"] == "pending"
            assert "stream_url" in data

    def test_create_run_skill_not_found(self, client):
        """POST /skills/runs with unknown skill returns 404."""
        user = _make_user()
        mock_db = _mock_db()

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        with patch("flywheel.api.skills.SKILLS_DIR") as mock_dir:
            mock_dir.is_dir.return_value = False
            resp = client.post(
                "/api/v1/skills/runs",
                json={"skill_name": "nonexistent"},
            )
            assert resp.status_code == 404


# ===========================================================================
# TestRunDetail
# ===========================================================================


class TestRunDetail:
    def test_get_run(self, client):
        """GET /skills/runs/{id} returns full run detail."""
        user = _make_user()
        run = MockSkillRun(id=TEST_RUN_ID, output="Result text", events_log=[{"event": "started"}])
        mock_db = _mock_db([MockResult(value=run)])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get(f"/api/v1/skills/runs/{TEST_RUN_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(TEST_RUN_ID)
        assert data["output"] == "Result text"
        assert data["events_log"] == [{"event": "started"}]

    def test_get_run_not_found(self, client):
        """GET /skills/runs/{id} returns 404 for missing run."""
        user = _make_user()
        mock_db = _mock_db([MockResult(value=None)])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get(f"/api/v1/skills/runs/{uuid4()}")
        assert resp.status_code == 404
        data = resp.json()
        assert data["code"] == 404


# ===========================================================================
# TestExecutionHistory
# ===========================================================================


class TestExecutionHistory:
    def test_list_runs_paginated(self, client):
        """GET /skills/runs returns paginated results."""
        user = _make_user()
        runs = [MockSkillRun() for _ in range(3)]
        mock_db = _mock_db([
            MockResult(scalar_val=3),
            MockResult(values=runs),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/runs?offset=0&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["has_more"] is False

    def test_list_runs_with_filter(self, client):
        """GET /skills/runs?status=completed filters by status."""
        user = _make_user()
        runs = [MockSkillRun(status="completed")]
        mock_db = _mock_db([
            MockResult(scalar_val=1),
            MockResult(values=runs),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/runs?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_list_runs_has_more(self, client):
        """has_more is True when total exceeds offset + limit."""
        user = _make_user()
        runs = [MockSkillRun()]
        mock_db = _mock_db([
            MockResult(scalar_val=10),
            MockResult(values=runs),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/runs?offset=0&limit=1")
        assert resp.status_code == 200
        assert resp.json()["has_more"] is True


# ===========================================================================
# TestSSEStream
# ===========================================================================


class TestSSEStream:
    def test_stream_completed_run(self, client):
        """SSE stream of a completed run replays events and sends done."""
        user = _make_user()
        app.dependency_overrides[require_tenant] = lambda: user

        run = MockSkillRun(
            id=TEST_RUN_ID,
            status="completed",
            events_log=[
                {"event": "started", "data": {"msg": "Starting"}},
                {"event": "progress", "data": {"pct": 50}},
                {"event": "result", "data": {"output": "Done"}},
            ],
        )

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MockResult(value=run))
        mock_session.close = AsyncMock()

        with patch("flywheel.api.skills.get_session_factory") as mock_factory, \
             patch("flywheel.api.skills.get_tenant_session", return_value=mock_session):
            mock_factory.return_value = MagicMock()

            with client.stream("GET", f"/api/v1/skills/runs/{TEST_RUN_ID}/stream") as resp:
                assert resp.status_code == 200
                lines = list(resp.iter_lines())

        # Verify SSE events were received
        events = [l for l in lines if l.startswith("event:")]
        data_lines = [l for l in lines if l.startswith("data:")]

        # Should have 3 replay events + 1 done event = 4 events
        assert len(events) == 4
        assert events[-1] == "event: done"

    def test_stream_run_not_found(self, client):
        """SSE stream for nonexistent run yields error event."""
        user = _make_user()
        app.dependency_overrides[require_tenant] = lambda: user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MockResult(value=None))
        mock_session.close = AsyncMock()

        with patch("flywheel.api.skills.get_session_factory") as mock_factory, \
             patch("flywheel.api.skills.get_tenant_session", return_value=mock_session):
            mock_factory.return_value = MagicMock()

            with client.stream("GET", f"/api/v1/skills/runs/{uuid4()}/stream") as resp:
                assert resp.status_code == 200
                lines = list(resp.iter_lines())

        events = [l for l in lines if l.startswith("event:")]
        assert any("error" in e for e in events)


# ===========================================================================
# TestAssetEndpoint
# ===========================================================================


class TestAssetEndpoint:
    def test_fetch_assets_success(self, client):
        """Valid tenant + public skill + asset row -> 200 with decodable bundle."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        skill = MockSkillDefinition(name="broker-parse-contract", protected=False)
        bundle_bytes, digest = _build_test_bundle()
        asset = MockSkillAsset(
            skill_id=skill.id,
            bundle=bundle_bytes,
            bundle_sha256=digest,
            bundle_size_bytes=len(bundle_bytes),
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),       # tenant-override probe: no overrides
            MockResult(value=skill),      # skill lookup
            MockResult(value=asset),      # asset lookup
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/broker-parse-contract/assets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["sha256"] == digest
        assert body["size"] == len(bundle_bytes)
        assert body["format"] == "zip"
        assert body["version"] == "1.2.3"
        # Round-trip: decode, unzip, inspect contents
        decoded = base64.b64decode(body["bundle_b64"])
        assert decoded == bundle_bytes
        with zipfile.ZipFile(io.BytesIO(decoded)) as zf:
            assert zf.namelist() == ["hello.py"]
            assert zf.read("hello.py") == b"def hello():\n    return 'world'\n"

    def test_fetch_assets_requires_auth(self, client):
        """No Authorization header -> 401 (from require_tenant)."""
        # Deliberately DO NOT override require_tenant.
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()
        resp = client.get("/api/v1/skills/any-skill/assets")
        assert resp.status_code == 401

    def test_fetch_assets_protected_returns_403(self, client):
        """Protected skill -> 403 BEFORE any skill_assets read."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        skill = MockSkillDefinition(name="company-intel", protected=True)
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),       # override probe: none
            MockResult(value=skill),      # skill row: protected=True
            # NO third side_effect -- the handler must NOT query skill_assets
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/company-intel/assets")
        assert resp.status_code == 403
        body = resp.json()
        assert "server-side" in body["message"].lower()
        # Verify no asset lookup happened (only 2 execute calls, not 3)
        assert mock_db.execute.await_count == 2

    def test_fetch_assets_skill_not_found(self, client):
        """Skill name not in DB -> 404 with 'not found' message (prompt-endpoint parity)."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),       # override probe: none
            MockResult(value=None),       # skill lookup: no row
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/does-not-exist/assets")
        assert resp.status_code == 404
        body = resp.json()
        assert "not found or not available for this tenant" in body["message"]

    def test_fetch_assets_no_bundle_row(self, client):
        """Skill exists but skill_assets row missing -> 404 with DISTINCT prompt-only message."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        skill = MockSkillDefinition(name="prompt-only-skill", protected=False)
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),       # override probe: none
            MockResult(value=skill),      # skill row exists
            MockResult(value=None),       # asset row: missing
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/prompt-only-skill/assets")
        assert resp.status_code == 404
        body = resp.json()
        # Distinct from the "not found" message above
        assert "prompt-only" in body["message"]
        assert "not found or not available" not in body["message"]

    def test_fetch_assets_tenant_override_parity_allows(self, client):
        """Tenant has overrides + skill IS in override list -> 200 (override branch hit)."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        skill = MockSkillDefinition(name="scoped-skill", protected=False)
        bundle_bytes, digest = _build_test_bundle()
        asset = MockSkillAsset(
            skill_id=skill.id,
            bundle=bundle_bytes,
            bundle_sha256=digest,
            bundle_size_bytes=len(bundle_bytes),
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=uuid4()),    # override probe: HAS overrides (some skill_id)
            MockResult(value=skill),      # join-based skill lookup succeeds
            MockResult(value=asset),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/scoped-skill/assets")
        assert resp.status_code == 200
        assert resp.json()["sha256"] == digest

    def test_fetch_assets_tenant_override_excludes(self, client):
        """Tenant has overrides + skill NOT in override list -> 404 (same 'not found' message)."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=uuid4()),    # override probe: HAS overrides
            MockResult(value=None),       # join-based skill lookup: no row
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/hidden-skill/assets")
        assert resp.status_code == 404
        body = resp.json()
        assert "not found or not available for this tenant" in body["message"]

    def test_fetch_assets_rate_limit(self, client):
        """11 rapid requests from same user -> 429 on/around the 11th."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        skill = MockSkillDefinition(name="rate-test-skill", protected=False)
        bundle_bytes, digest = _build_test_bundle()
        asset = MockSkillAsset(
            skill_id=skill.id,
            bundle=bundle_bytes,
            bundle_sha256=digest,
            bundle_size_bytes=len(bundle_bytes),
        )

        # Build enough side_effects for 15 attempts worth of DB calls
        # Each successful call uses 3 executes; once 429 hits, no DB call happens.
        side_effects = []
        for _ in range(15):
            side_effects.extend([
                MockResult(value=None),
                MockResult(value=skill),
                MockResult(value=asset),
            ])
        mock_db = _mock_db(execute_side_effects=side_effects)

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        hit_429 = False
        for _ in range(15):
            resp = client.get("/api/v1/skills/rate-test-skill/assets")
            if resp.status_code == 429:
                body = resp.json()
                assert body["error"] == "RateLimitExceeded"
                assert body["code"] == 429
                assert "Retry-After" in resp.headers
                hit_429 = True
                break
        # slowapi timing in tests can occasionally miss, but the handler format is
        # what we most care about. Mirror test_rate_limit.py lines 147-161 tolerance.
        assert hit_429, "Expected to hit 429 within 15 rapid requests"
        # Cleanup so other tests aren't polluted
        limiter.reset()


# ===========================================================================
# TestAssetBundleEndpoint -- Phase 150 Plan 01 fanout endpoint
# ===========================================================================


class TestAssetBundleEndpoint:
    """GET /api/v1/skills/{name}/assets/bundle -- consumer + transitive libs.

    Covers all 5 ROADMAP SCs for Phase 150 Plan 01:
    SC1: endpoint returns topologically-ordered bundles with per-bundle SHA
    SC2: server-side SHA-256 re-hash before shipping bytes (500 on mismatch)
    SC3: protected-in-chain short-circuits with 403 (bytes never leave server)
    SC4: missing-dep and cycle errors surface 500 with actionable detail
    SC5: tenant-override + rate-limit parity with get_skill_assets

    Every test calls `limiter.reset()` both to defend against class-order
    flake (shared TEST_USER_ID bucket) and to match the Phase 148 v22.0
    148-01 decision: limiter.reset() in EVERY method, not just 2 per plan.
    """

    def test_success_consumer_with_library_dep_returns_library_only(self, client):
        """broker-parse-contract (depends_on=['broker'], assets:[]) -> bundles=[broker].

        n:1 case — the consumer skill itself declared `assets: []` in SKILL.md
        (Phase 147 contract for prompt-only skills), so no SkillAsset row for
        the consumer. The fanout walker resolves the chain (broker library +
        consumer) but only the library's bundle bytes ship, preserving the
        Phase 147 byte-determinism invariant captured in Phase 149
        (broker SHA = 217ebdc1c28416e94104845a7ac0d2e49e71fe77caa60531934d05f2be17a33f).
        """
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="broker-parse-contract",
            protected=False,
            depends_on=["broker"],
        )
        library = MockSkillDefinition(
            name="broker",
            protected=False,
            depends_on=[],
        )
        lib_bundle, lib_sha = _build_test_bundle()
        lib_asset = MockSkillAsset(
            skill_id=library.id,
            bundle=lib_bundle,
            bundle_sha256=lib_sha,
            bundle_size_bytes=len(lib_bundle),
        )

        # Asset lookups iterate in TOPOLOGICAL order (deepest-first per
        # graphlib.TopologicalSorter): library 'broker' FIRST, then consumer.
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),           # tenant-override probe: none
            MockResult(value=consumer),       # root skill lookup
            MockResult(value=library),        # _resolve_bundle_chain: broker dep
            MockResult(value=lib_asset),      # asset for broker (library): found
            MockResult(value=None),           # asset for consumer: no row (assets:[])
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/broker-parse-contract/assets/bundle")
        assert resp.status_code == 200
        body = resp.json()
        assert body["skill"] == "broker-parse-contract"
        assert body["deps"] == ["broker"]
        assert len(body["bundles"]) == 1
        assert body["bundles"][0]["name"] == "broker"
        assert body["bundles"][0]["sha256"] == lib_sha
        assert body["bundles"][0]["size"] == len(lib_bundle)
        # rollup_sha = sha256("broker:<sha>")
        expected_rollup = hashlib.sha256(f"broker:{lib_sha}".encode("ascii")).hexdigest()
        assert body["rollup_sha"] == expected_rollup
        # Byte-identity: decoded bundle matches DB bytes verbatim.
        decoded = base64.b64decode(body["bundles"][0]["bundle_b64"])
        assert decoded == lib_bundle

    def test_success_consumer_and_library_both_have_bundles_topological_order(self, client):
        """Consumer WITH own assets + library dep -> both bundles, library FIRST."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="consumer-skill",
            protected=False,
            depends_on=["library-skill"],
        )
        library = MockSkillDefinition(
            name="library-skill",
            protected=False,
            depends_on=[],
        )
        lib_bundle, lib_sha = _build_test_bundle()
        lib_asset = MockSkillAsset(
            skill_id=library.id,
            bundle=lib_bundle,
            bundle_sha256=lib_sha,
            bundle_size_bytes=len(lib_bundle),
        )
        # Build distinct consumer bundle
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("consumer.py", "def consume(): return 42\n")
        con_bundle = buf.getvalue()
        con_sha = hashlib.sha256(con_bundle).hexdigest()
        con_asset = MockSkillAsset(
            skill_id=consumer.id,
            bundle=con_bundle,
            bundle_sha256=con_sha,
            bundle_size_bytes=len(con_bundle),
        )

        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),           # override probe: none
            MockResult(value=consumer),       # root lookup
            MockResult(value=library),        # dep lookup
            # Asset lookups happen in topological order (library first)
            MockResult(value=lib_asset),
            MockResult(value=con_asset),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/consumer-skill/assets/bundle")
        assert resp.status_code == 200
        body = resp.json()
        assert body["skill"] == "consumer-skill"
        assert body["deps"] == ["library-skill"]
        assert len(body["bundles"]) == 2
        # Topological order: library FIRST, consumer LAST
        assert body["bundles"][0]["name"] == "library-skill"
        assert body["bundles"][1]["name"] == "consumer-skill"

    def test_rollup_sha_deterministic_across_calls(self, client):
        """Same chain -> identical rollup_sha on repeated requests."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="broker-parse-contract",
            depends_on=["broker"],
        )
        library = MockSkillDefinition(name="broker")
        lib_bundle, lib_sha = _build_test_bundle()
        lib_asset = MockSkillAsset(
            skill_id=library.id,
            bundle=lib_bundle,
            bundle_sha256=lib_sha,
            bundle_size_bytes=len(lib_bundle),
        )

        def _side_effects():
            # Library first (topological order), consumer last
            return [
                MockResult(value=None),
                MockResult(value=consumer),
                MockResult(value=library),
                MockResult(value=lib_asset),     # library asset first
                MockResult(value=None),          # consumer has no asset row
            ]

        app.dependency_overrides[require_tenant] = lambda: user

        # Call 1
        mock_db_1 = _mock_db(execute_side_effects=_side_effects())
        app.dependency_overrides[get_tenant_db] = lambda: mock_db_1
        r1 = client.get("/api/v1/skills/broker-parse-contract/assets/bundle")
        assert r1.status_code == 200

        # Call 2
        mock_db_2 = _mock_db(execute_side_effects=_side_effects())
        app.dependency_overrides[get_tenant_db] = lambda: mock_db_2
        r2 = client.get("/api/v1/skills/broker-parse-contract/assets/bundle")
        assert r2.status_code == 200

        assert r1.json()["rollup_sha"] == r2.json()["rollup_sha"]

    def test_per_bundle_sha_matches_raw_bytes(self, client):
        """Client-side: sha256(base64.b64decode(bundle_b64)) == response.sha256."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(name="c", depends_on=["lib"])
        library = MockSkillDefinition(name="lib")
        bundle, sha = _build_test_bundle()
        asset = MockSkillAsset(
            skill_id=library.id,
            bundle=bundle,
            bundle_sha256=sha,
            bundle_size_bytes=len(bundle),
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),
            MockResult(value=consumer),
            MockResult(value=library),
            MockResult(value=asset),     # library asset first (topological)
            MockResult(value=None),      # consumer has no asset
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/c/assets/bundle")
        assert resp.status_code == 200
        body = resp.json()
        for entry in body["bundles"]:
            decoded = base64.b64decode(entry["bundle_b64"])
            recomputed = hashlib.sha256(decoded).hexdigest()
            assert recomputed == entry["sha256"]
            assert len(decoded) == entry["size"]

    def test_protected_root_returns_403(self, client):
        """Root consumer with protected=True -> 403 before fanout walk."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="internal-skill",
            protected=True,
            depends_on=[],
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),         # override probe: none
            MockResult(value=consumer),     # root lookup
            # No further executes: _resolve_bundle_chain must not be called
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/internal-skill/assets/bundle")
        assert resp.status_code == 403
        # Only 2 execute calls: override probe + root lookup. Walker never ran.
        assert mock_db.execute.await_count == 2

    def test_protected_dep_in_chain_returns_403(self, client):
        """Consumer depends on a protected library -> 403 with actionable detail."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="public-consumer",
            protected=False,
            depends_on=["secret-library"],
        )
        protected_library = MockSkillDefinition(
            name="secret-library",
            protected=True,
            depends_on=[],
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),                  # override probe
            MockResult(value=consumer),              # root lookup
            MockResult(value=protected_library),     # dep lookup -> protected!
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/public-consumer/assets/bundle")
        assert resp.status_code == 403
        body = resp.json()
        assert "protected" in body["message"].lower()
        assert "secret-library" in body["message"]

    def test_missing_dep_returns_500(self, client):
        """Consumer declares depends_on=['ghost'] but no row -> 500 naming both."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="broken-consumer",
            protected=False,
            depends_on=["ghost-library"],
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),           # override probe
            MockResult(value=consumer),       # root lookup
            MockResult(value=None),           # dep lookup: MISSING
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/broken-consumer/assets/bundle")
        assert resp.status_code == 500
        body = resp.json()
        assert "ghost-library" in body["message"]
        assert "broken-consumer" in body["message"]

    def test_cycle_returns_500(self, client):
        """A -> B -> A cycle -> 500 with 'Cycle' detail."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        skill_a = MockSkillDefinition(name="a", depends_on=["b"])
        skill_b = MockSkillDefinition(name="b", depends_on=["a"])
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),          # override probe
            MockResult(value=skill_a),       # root lookup: a
            MockResult(value=skill_b),       # dep lookup: b
            # When BFS processes b, it sees dep 'a' but 'a' is already in
            # visited (it's the root), so no additional fetch happens — the
            # cycle is detected by TopologicalSorter.static_order() instead.
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/a/assets/bundle")
        assert resp.status_code == 500
        body = resp.json()
        assert "Cycle" in body["message"] or "cycle" in body["message"]

    def test_404_on_unknown_skill(self, client):
        """Root skill not in DB -> 404 with standard message."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),    # override probe
            MockResult(value=None),    # root lookup: missing
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/does-not-exist/assets/bundle")
        assert resp.status_code == 404
        assert "not found or not available" in resp.json()["message"]

    def test_requires_auth(self, client):
        """No auth header -> 401 (require_tenant gate)."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()
        # Deliberately do NOT override require_tenant.
        resp = client.get("/api/v1/skills/any/assets/bundle")
        assert resp.status_code == 401

    def test_tenant_override_allows(self, client):
        """Tenant has overrides + skill in list -> 200."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="allowed-consumer",
            depends_on=["allowed-lib"],
        )
        library = MockSkillDefinition(name="allowed-lib")
        bundle, sha = _build_test_bundle()
        asset = MockSkillAsset(
            skill_id=library.id,
            bundle=bundle,
            bundle_sha256=sha,
            bundle_size_bytes=len(bundle),
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=uuid4()),       # override probe: HAS overrides
            MockResult(value=consumer),      # root lookup (join branch)
            MockResult(value=library),       # dep lookup (no enabled filter)
            MockResult(value=asset),         # library asset (topo order first)
            MockResult(value=None),          # consumer asset: none
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/allowed-consumer/assets/bundle")
        assert resp.status_code == 200

    def test_tenant_override_excludes(self, client):
        """Tenant has overrides + skill NOT in list -> 404."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=uuid4()),       # override probe: HAS overrides
            MockResult(value=None),          # root lookup (join branch): none
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/hidden/assets/bundle")
        assert resp.status_code == 404
        assert "not found or not available" in resp.json()["message"]

    def test_server_side_sha_mismatch_returns_500(self, client):
        """DB bundle bytes don't match stored bundle_sha256 -> 500 + operator log."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="corrupt-consumer",
            depends_on=["corrupt-lib"],
        )
        library = MockSkillDefinition(name="corrupt-lib")
        bundle, real_sha = _build_test_bundle()
        # Deliberately mismatched SHA — as if DB/storage flipped a bit.
        wrong_sha = "0" * 64
        bad_asset = MockSkillAsset(
            skill_id=library.id,
            bundle=bundle,
            bundle_sha256=wrong_sha,     # <- DB column says this, but bytes say real_sha
            bundle_size_bytes=len(bundle),
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),
            MockResult(value=consumer),
            MockResult(value=library),
            MockResult(value=bad_asset),   # library asset first (topo order) — mismatch
            MockResult(value=None),        # consumer has no asset (never reached)
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/skills/corrupt-consumer/assets/bundle")
        assert resp.status_code == 500
        body = resp.json()
        assert "integrity check failed" in body["message"].lower()
        assert "corrupt-lib" in body["message"]
        # And bundle_b64 must NOT leak in the response
        assert "bundle_b64" not in body
        assert real_sha not in body["message"]  # real hash stays in logs, not response

    # ---------------------------------------------------------------
    # Phase 151 Plan 01: ?shas_only=true query param + correlation-id
    # ---------------------------------------------------------------

    def test_shas_only_returns_empty_bundle_b64(self, client):
        """shas_only=true branch: full envelope, empty bundle_b64, zero base64 bytes."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="broker-parse-contract",
            protected=False,
            depends_on=["broker"],
        )
        library = MockSkillDefinition(
            name="broker",
            protected=False,
            depends_on=[],
        )
        lib_bundle, lib_sha = _build_test_bundle()
        lib_asset = MockSkillAsset(
            skill_id=library.id,
            bundle=lib_bundle,
            bundle_sha256=lib_sha,
            bundle_size_bytes=len(lib_bundle),
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),        # override probe
            MockResult(value=consumer),    # root lookup
            MockResult(value=library),     # dep lookup
            MockResult(value=lib_asset),   # library asset (topo)
            MockResult(value=None),        # consumer asset: none
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get(
            "/api/v1/skills/broker-parse-contract/assets/bundle?shas_only=true"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["skill"] == "broker-parse-contract"
        assert body["deps"] == ["broker"]
        assert len(body["bundles"]) == 1
        # Per-bundle metadata still present.
        assert body["bundles"][0]["name"] == "broker"
        assert body["bundles"][0]["sha256"] == lib_sha
        assert body["bundles"][0]["size"] == len(lib_bundle)
        # Bundle bytes EMPTY — signals shas-only branch to client.
        assert body["bundles"][0]["bundle_b64"] == ""

    def test_shas_only_matches_full_fetch_shas(self, client):
        """shas_only SHAs byte-match the full-fetch SHAs for the same chain."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="broker-parse-contract",
            depends_on=["broker"],
        )
        library = MockSkillDefinition(name="broker")
        lib_bundle, lib_sha = _build_test_bundle()
        lib_asset = MockSkillAsset(
            skill_id=library.id,
            bundle=lib_bundle,
            bundle_sha256=lib_sha,
            bundle_size_bytes=len(lib_bundle),
        )

        def _side_effects():
            return [
                MockResult(value=None),
                MockResult(value=consumer),
                MockResult(value=library),
                MockResult(value=lib_asset),
                MockResult(value=None),
            ]

        app.dependency_overrides[require_tenant] = lambda: user

        # Full fetch first.
        mock_db_full = _mock_db(execute_side_effects=_side_effects())
        app.dependency_overrides[get_tenant_db] = lambda: mock_db_full
        r_full = client.get("/api/v1/skills/broker-parse-contract/assets/bundle")
        assert r_full.status_code == 200
        full_body = r_full.json()

        # shas_only fetch.
        mock_db_sha = _mock_db(execute_side_effects=_side_effects())
        app.dependency_overrides[get_tenant_db] = lambda: mock_db_sha
        r_sha = client.get(
            "/api/v1/skills/broker-parse-contract/assets/bundle?shas_only=true"
        )
        assert r_sha.status_code == 200
        sha_body = r_sha.json()

        # Per-bundle SHAs identical.
        assert len(full_body["bundles"]) == len(sha_body["bundles"])
        full_shas = {b["name"]: b["sha256"] for b in full_body["bundles"]}
        sha_shas = {b["name"]: b["sha256"] for b in sha_body["bundles"]}
        assert full_shas == sha_shas
        # Rollup sha matches too.
        assert full_body["rollup_sha"] == sha_body["rollup_sha"]
        # And deps identical.
        assert full_body["deps"] == sha_body["deps"]

    def test_shas_only_still_enforces_protected(self, client):
        """Protected root -> 403 on shas_only=true (no bypass of security gate)."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="company-intel",
            protected=True,
            depends_on=[],
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),
            MockResult(value=consumer),
            # Walker must NOT run for protected root — 403 short-circuits.
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get(
            "/api/v1/skills/company-intel/assets/bundle?shas_only=true"
        )
        assert resp.status_code == 403
        # Only 2 execute calls — protected gate fires before fanout walk
        # AND before shas_only branch. Security invariant intact.
        assert mock_db.execute.await_count == 2

    def test_asset_bundle_logs_correlation_id_when_header_present(self, client, caplog):
        """X-Flywheel-Correlation-ID request header -> logged as structured extra."""
        import logging
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(
            name="broker-parse-contract",
            depends_on=["broker"],
        )
        library = MockSkillDefinition(name="broker")
        lib_bundle, lib_sha = _build_test_bundle()
        lib_asset = MockSkillAsset(
            skill_id=library.id,
            bundle=lib_bundle,
            bundle_sha256=lib_sha,
            bundle_size_bytes=len(lib_bundle),
        )
        mock_db = _mock_db(execute_side_effects=[
            MockResult(value=None),
            MockResult(value=consumer),
            MockResult(value=library),
            MockResult(value=lib_asset),
            MockResult(value=None),
        ])
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        with caplog.at_level(logging.INFO, logger="flywheel.api.skills"):
            resp = client.get(
                "/api/v1/skills/broker-parse-contract/assets/bundle",
                headers={"X-Flywheel-Correlation-ID": "deadbeef"},
            )
        assert resp.status_code == 200
        # At least one LogRecord from this handler must carry correlation_id="deadbeef"
        # as a structured field (not just substring-match inside message).
        matching = [
            r for r in caplog.records
            if getattr(r, "correlation_id", None) == "deadbeef"
            and "assets_bundle_fetch" in r.getMessage()
        ]
        assert matching, (
            "Expected a LogRecord with correlation_id='deadbeef' structured extra; "
            f"saw {[(r.name, r.getMessage(), getattr(r, 'correlation_id', '<missing>')) for r in caplog.records]}"
        )

    def test_rate_limit(self, client):
        """11 rapid requests from same user -> 429 within 15 attempts."""
        from flywheel.middleware.rate_limit import limiter
        limiter.reset()

        user = _make_user()
        consumer = MockSkillDefinition(name="ratebundle", depends_on=["lib"])
        library = MockSkillDefinition(name="lib")
        bundle, sha = _build_test_bundle()
        asset = MockSkillAsset(
            skill_id=library.id,
            bundle=bundle,
            bundle_sha256=sha,
            bundle_size_bytes=len(bundle),
        )

        # Each successful call uses 5 executes (override probe + root +
        # dep lookup + consumer-asset lookup + library-asset lookup);
        # once 429 hits, no DB call happens. Pad enough for 15 attempts.
        side_effects = []
        for _ in range(15):
            side_effects.extend([
                MockResult(value=None),
                MockResult(value=consumer),
                MockResult(value=library),
                MockResult(value=asset),     # library first (topo)
                MockResult(value=None),      # consumer: no asset
            ])
        mock_db = _mock_db(execute_side_effects=side_effects)
        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        hit_429 = False
        for _ in range(15):
            resp = client.get("/api/v1/skills/ratebundle/assets/bundle")
            if resp.status_code == 429:
                body = resp.json()
                assert body["error"] == "RateLimitExceeded"
                assert body["code"] == 429
                assert "Retry-After" in resp.headers
                hit_429 = True
                break
        assert hit_429, "Expected to hit 429 within 15 rapid requests"
        limiter.reset()
