"""Integration tests for skill endpoints.

Uses FastAPI TestClient with dependency overrides -- no real DB.
Verifies: list skills, start run, run detail, execution history,
SSE stream with late-connect replay.
"""

from __future__ import annotations

import datetime
import json
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
