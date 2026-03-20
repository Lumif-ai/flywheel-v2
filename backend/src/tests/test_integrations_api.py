"""Integration tests for integration endpoints.

Uses FastAPI TestClient with dependency overrides -- no real DB.
Verifies: list, connect stub (501), disconnect, sync stub (501), error format.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock
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
TEST_INTEGRATION_ID = uuid4()


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


class MockIntegration:
    def __init__(
        self,
        id=None,
        provider="google_calendar",
        status="connected",
        settings=None,
        last_synced_at=None,
        created_at=None,
        updated_at=None,
    ):
        self.id = id or uuid4()
        self.provider = provider
        self.status = status
        self.settings = settings or {}
        self.last_synced_at = last_synced_at
        self.created_at = created_at or datetime.datetime(2026, 3, 20, tzinfo=datetime.timezone.utc)
        self.updated_at = updated_at or datetime.datetime(2026, 3, 20, tzinfo=datetime.timezone.utc)


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
    return db


@pytest.fixture
def client():
    app.dependency_overrides = {}
    yield TestClient(app)
    app.dependency_overrides = {}


# ===========================================================================
# TestIntegrations
# ===========================================================================


class TestIntegrations:
    def test_list_integrations(self, client):
        """GET /integrations/ returns list of integrations."""
        user = _make_user()
        integrations = [MockIntegration(), MockIntegration(provider="slack")]
        mock_db = _mock_db([
            MockResult(values=integrations),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/integrations/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2

    def test_list_integrations_empty(self, client):
        """GET /integrations/ with no integrations returns empty list."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(values=[]),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/integrations/")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_connect_google_calendar_returns_501(self, client):
        """POST /integrations/google-calendar returns 501 stub."""
        user = _make_user()
        app.dependency_overrides[require_tenant] = lambda: user

        resp = client.post("/api/v1/integrations/google-calendar")
        assert resp.status_code == 501
        data = resp.json()
        assert data["error"] == "NotImplemented"
        assert data["code"] == 501
        assert "future release" in data["message"]

    def test_disconnect_integration(self, client):
        """DELETE /integrations/{id} sets status to disconnected."""
        user = _make_user()
        integration = MockIntegration(id=TEST_INTEGRATION_ID)
        mock_db = _mock_db([
            MockResult(value=integration),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.delete(f"/api/v1/integrations/{TEST_INTEGRATION_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["disconnected"] is True
        assert integration.status == "disconnected"

    def test_disconnect_not_found(self, client):
        """DELETE /integrations/{id} returns 404 with error format."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(value=None),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.delete(f"/api/v1/integrations/{uuid4()}")
        assert resp.status_code == 404
        data = resp.json()
        assert data["code"] == 404
        assert "error" in data

    def test_sync_returns_501(self, client):
        """POST /integrations/{id}/sync returns 501 stub."""
        user = _make_user()
        app.dependency_overrides[require_tenant] = lambda: user

        resp = client.post(f"/api/v1/integrations/{TEST_INTEGRATION_ID}/sync")
        assert resp.status_code == 501
        data = resp.json()
        assert data["error"] == "NotImplemented"
        assert data["code"] == 501
