"""Integration tests for onboarding crawl SSE endpoint.

Uses FastAPI TestClient with dependency overrides -- no real DB.
Verifies: crawl creates SkillRun, invalid URL returns 422, SSE content type.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from flywheel.api.deps import get_current_user, get_db_unscoped
from flywheel.auth.jwt import TokenPayload
from flywheel.main import app

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid4()
TEST_RUN_ID = uuid4()


def _make_anonymous_user():
    return TokenPayload(
        sub=TEST_USER_ID,
        email=None,
        is_anonymous=True,
        app_metadata={},
    )


def _make_user():
    return TokenPayload(
        sub=TEST_USER_ID,
        email="test@example.com",
        is_anonymous=False,
        app_metadata={"tenant_id": str(uuid4()), "role": "admin"},
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
# TestOnboardingCrawl
# ===========================================================================


class TestOnboardingCrawl:
    def test_crawl_creates_skill_run(self, client):
        """POST /onboarding/crawl creates a SkillRun with skill_name='company-intel'."""
        user = _make_anonymous_user()
        mock_db = _mock_db()

        added_objects = []
        original_add = mock_db.add

        def capture_add(obj):
            added_objects.append(obj)
            original_add(obj)

        mock_db.add = MagicMock(side_effect=capture_add)

        def mock_refresh(obj):
            obj.id = TEST_RUN_ID
            obj.status = "pending"

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        # Mock the SSE generator to return immediately (completed run)
        mock_session = AsyncMock()

        class MockCompletedRun:
            id = TEST_RUN_ID
            status = "completed"
            events_log = [{"event": "result", "data": {"company": "Acme"}}]

        mock_session.execute = AsyncMock(return_value=MockResult(value=MockCompletedRun()))
        mock_session.close = AsyncMock()

        with patch("flywheel.api.onboarding.get_session_factory") as mock_factory:
            mock_factory.return_value = MagicMock(return_value=mock_session)

            with client.stream("POST", "/api/v1/onboarding/crawl", json={"url": "https://example.com"}) as resp:
                assert resp.status_code == 200
                # Check content type is SSE
                assert "text/event-stream" in resp.headers.get("content-type", "")

        # Verify SkillRun was created with correct skill_name
        from flywheel.db.models import SkillRun

        skill_runs = [o for o in added_objects if isinstance(o, SkillRun)]
        assert len(skill_runs) == 1
        assert skill_runs[0].skill_name == "company-intel"
        assert skill_runs[0].input_text == "https://example.com"

    def test_crawl_invalid_url(self, client):
        """POST /onboarding/crawl with invalid URL returns 422."""
        user = _make_anonymous_user()
        mock_db = _mock_db()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/onboarding/crawl",
            json={"url": "not-a-url"},
        )
        assert resp.status_code == 422

    def test_crawl_requires_auth(self, client):
        """POST /onboarding/crawl without auth returns 401."""
        resp = client.post(
            "/api/v1/onboarding/crawl",
            json={"url": "https://example.com"},
        )
        assert resp.status_code == 401

    def test_crawl_sse_content_type(self, client):
        """Response is an SSE stream (text/event-stream content type)."""
        user = _make_user()
        mock_db = _mock_db()

        def mock_refresh(obj):
            obj.id = TEST_RUN_ID
            obj.status = "pending"

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        mock_session = AsyncMock()

        class MockCompletedRun:
            id = TEST_RUN_ID
            status = "completed"
            events_log = []

        mock_session.execute = AsyncMock(return_value=MockResult(value=MockCompletedRun()))
        mock_session.close = AsyncMock()

        with patch("flywheel.api.onboarding.get_session_factory") as mock_factory:
            mock_factory.return_value = MagicMock(return_value=mock_session)

            with client.stream("POST", "/api/v1/onboarding/crawl", json={"url": "https://example.com"}) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
