"""Integration tests for work item CRUD endpoints.

Uses FastAPI TestClient with dependency overrides -- no real DB.
Verifies: list, create, get, update, delete, run-skill, and error format.
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
TEST_ITEM_ID = uuid4()


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


class MockWorkItem:
    def __init__(
        self,
        id=None,
        type="meeting",
        title="Team standup",
        status="upcoming",
        data=None,
        source="manual",
        external_id=None,
        scheduled_at=None,
        created_at=None,
    ):
        self.id = id or uuid4()
        self.type = type
        self.title = title
        self.status = status
        self.data = data or {}
        self.source = source
        self.external_id = external_id
        self.scheduled_at = scheduled_at
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
# TestWorkItemCRUD
# ===========================================================================


class TestWorkItemCRUD:
    def test_list_work_items(self, client):
        """GET /work-items/ returns paginated items."""
        user = _make_user()
        items = [MockWorkItem(), MockWorkItem(title="Sprint review")]
        mock_db = _mock_db([
            MockResult(scalar_val=2),  # total
            MockResult(values=items),  # items
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/work-items/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_with_status_filter(self, client):
        """GET /work-items/?status=upcoming filters by status."""
        user = _make_user()
        items = [MockWorkItem(status="upcoming")]
        mock_db = _mock_db([
            MockResult(scalar_val=1),
            MockResult(values=items),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/work-items/?status=upcoming")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_create_work_item(self, client):
        """POST /work-items/ returns 201 with created item."""
        user = _make_user()
        mock_db = _mock_db()

        def mock_refresh(obj):
            obj.id = uuid4()
            obj.status = "upcoming"
            obj.source = "manual"
            obj.external_id = None
            obj.created_at = datetime.datetime(2026, 3, 20, tzinfo=datetime.timezone.utc)

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(
            "/api/v1/work-items/",
            json={"type": "meeting", "title": "New meeting"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "New meeting"
        assert data["type"] == "meeting"

    def test_get_work_item(self, client):
        """GET /work-items/{id} returns single item."""
        user = _make_user()
        item = MockWorkItem(id=TEST_ITEM_ID)
        mock_db = _mock_db([
            MockResult(value=item),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get(f"/api/v1/work-items/{TEST_ITEM_ID}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Team standup"

    def test_get_work_item_not_found(self, client):
        """GET /work-items/{id} returns 404 with error format."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(value=None),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get(f"/api/v1/work-items/{uuid4()}")
        assert resp.status_code == 404
        data = resp.json()
        assert data["code"] == 404
        assert "error" in data
        assert "message" in data

    def test_update_work_item(self, client):
        """PATCH /work-items/{id} updates fields."""
        user = _make_user()
        item = MockWorkItem(id=TEST_ITEM_ID)
        mock_db = _mock_db([
            MockResult(value=item),
        ])
        mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.patch(
            f"/api/v1/work-items/{TEST_ITEM_ID}",
            json={"title": "Updated standup", "status": "completed"},
        )
        assert resp.status_code == 200
        assert item.title == "Updated standup"
        assert item.status == "completed"

    def test_delete_work_item(self, client):
        """DELETE /work-items/{id} hard deletes."""
        user = _make_user()
        item = MockWorkItem(id=TEST_ITEM_ID)
        mock_db = _mock_db([
            MockResult(value=item),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.delete(f"/api/v1/work-items/{TEST_ITEM_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True

    def test_delete_work_item_not_found(self, client):
        """DELETE /work-items/{id} returns 404 for missing item."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(value=None),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.delete(f"/api/v1/work-items/{uuid4()}")
        assert resp.status_code == 404


# ===========================================================================
# TestRunSkill
# ===========================================================================


class TestRunSkill:
    def test_run_skill_for_item(self, client):
        """POST /work-items/{id}/run creates a pending SkillRun."""
        user = _make_user()
        item = MockWorkItem(id=TEST_ITEM_ID, data={"description": "Prepare for meeting"})
        mock_db = _mock_db([
            MockResult(scalar_val=0),  # check_concurrent_run_limit count
            MockResult(value=item),
        ])

        def mock_refresh(obj):
            obj.id = uuid4()

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(
            f"/api/v1/work-items/{TEST_ITEM_ID}/run",
            json={"skill_name": "meeting-prep"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert "run_id" in data

    def test_run_skill_item_not_found(self, client):
        """POST /work-items/{id}/run returns 404 if item missing."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(scalar_val=0),  # check_concurrent_run_limit count
            MockResult(value=None),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(
            f"/api/v1/work-items/{uuid4()}/run",
            json={"skill_name": "meeting-prep"},
        )
        assert resp.status_code == 404
