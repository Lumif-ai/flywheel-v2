"""Integration tests for context CRUD endpoints.

Uses FastAPI TestClient with dependency overrides -- no real DB.
Verifies: list files, read entries (paginated), append, search, update,
soft-delete, and consistent {error, message, code} error format.
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
TEST_ENTRY_ID = uuid4()


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


class MockContextCatalog:
    def __init__(self, file_name="company-intel", description="Intel", tags=None, status="active"):
        self.file_name = file_name
        self.description = description
        self.tags = tags or ["intel"]
        self.status = status


class MockContextEntry:
    def __init__(
        self,
        id=None,
        file_name="company-intel",
        date=None,
        source="test-skill",
        detail="test detail",
        confidence="high",
        evidence_count=1,
        content="Test content",
        created_at=None,
        updated_at=None,
        deleted_at=None,
        search_vector=None,
    ):
        self.id = id or uuid4()
        self.file_name = file_name
        self.date = date or datetime.date(2026, 3, 20)
        self.source = source
        self.detail = detail
        self.confidence = confidence
        self.evidence_count = evidence_count
        self.content = content
        self.created_at = created_at or datetime.datetime(2026, 3, 20, tzinfo=datetime.timezone.utc)
        self.updated_at = updated_at or datetime.datetime(2026, 3, 20, tzinfo=datetime.timezone.utc)
        self.deleted_at = deleted_at
        self.search_vector = search_vector


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
# TestContextFiles
# ===========================================================================


class TestContextFiles:
    def test_list_files(self, client):
        """GET /context/files returns catalog items."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(values=[MockContextCatalog(), MockContextCatalog(file_name="meetings")]),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/context/files")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["items"][0]["file_name"] == "company-intel"

    def test_list_files_requires_auth(self, client):
        """GET /context/files without auth returns error with {error, message, code}."""
        resp = client.get("/api/v1/context/files")
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert "message" in data
        assert "code" in data
        assert data["code"] == 401


# ===========================================================================
# TestContextEntries
# ===========================================================================


class TestContextEntries:
    def test_read_entries_paginated(self, client):
        """GET /context/files/{name}/entries returns paginated entries."""
        user = _make_user()
        entries = [MockContextEntry() for _ in range(3)]
        mock_db = _mock_db([
            MockResult(scalar_val=3),  # total count
            MockResult(values=entries),  # entries
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/context/files/company-intel/entries?offset=0&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["offset"] == 0
        assert data["limit"] == 10
        assert data["has_more"] is False
        assert len(data["items"]) == 3

    def test_read_entries_has_more(self, client):
        """has_more is True when there are more entries beyond the page."""
        user = _make_user()
        entries = [MockContextEntry() for _ in range(2)]
        mock_db = _mock_db([
            MockResult(scalar_val=5),  # total count = 5
            MockResult(values=entries),  # 2 entries returned
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/context/files/company-intel/entries?offset=0&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_more"] is True

    def test_append_entry(self, client):
        """POST /context/files/{name}/entries creates and returns entry."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(),  # catalog upsert
        ])

        # Mock refresh to set attributes on the added entry
        def mock_refresh(obj):
            obj.id = uuid4()
            obj.date = datetime.date(2026, 3, 20)
            obj.created_at = datetime.datetime(2026, 3, 20, tzinfo=datetime.timezone.utc)
            obj.updated_at = datetime.datetime(2026, 3, 20, tzinfo=datetime.timezone.utc)
            obj.evidence_count = 1

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(
            "/api/v1/context/files/company-intel/entries",
            json={
                "content": "New insight about company",
                "source": "research-skill",
                "confidence": "high",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "entry" in data
        assert data["entry"]["source"] == "research-skill"
        assert data["entry"]["confidence"] == "high"


# ===========================================================================
# TestContextUpdateDelete
# ===========================================================================


class TestContextUpdateDelete:
    def test_update_entry(self, client):
        """PATCH /context/entries/{id} updates content."""
        user = _make_user()
        entry = MockContextEntry(id=TEST_ENTRY_ID)
        mock_db = _mock_db([
            MockResult(value=entry),  # find entry
        ])
        mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.patch(
            f"/api/v1/context/entries/{TEST_ENTRY_ID}",
            json={"content": "Updated content"},
        )
        assert resp.status_code == 200
        assert entry.content == "Updated content"

    def test_update_entry_not_found(self, client):
        """PATCH /context/entries/{id} returns 404 with error format."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(value=None),  # not found
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.patch(
            f"/api/v1/context/entries/{uuid4()}",
            json={"content": "Updated"},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["code"] == 404
        assert "error" in data
        assert "message" in data

    def test_soft_delete_entry(self, client):
        """DELETE /context/entries/{id} sets deleted_at."""
        user = _make_user()
        entry = MockContextEntry(id=TEST_ENTRY_ID)
        mock_db = _mock_db([
            MockResult(value=entry),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.delete(f"/api/v1/context/entries/{TEST_ENTRY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert entry.deleted_at is not None

    def test_soft_delete_not_found(self, client):
        """DELETE /context/entries/{id} returns 404 for missing entry."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(value=None),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.delete(f"/api/v1/context/entries/{uuid4()}")
        assert resp.status_code == 404


# ===========================================================================
# TestContextSearch
# ===========================================================================


class TestContextSearch:
    def test_cross_file_search(self, client):
        """GET /context/search returns paginated results across files."""
        user = _make_user()
        entries = [
            MockContextEntry(file_name="company-intel"),
            MockContextEntry(file_name="meetings"),
        ]
        mock_db = _mock_db([
            MockResult(scalar_val=2),  # total
            MockResult(values=entries),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/context/search?q=test+query")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        # Results include file_name
        assert data["items"][0]["file_name"] == "company-intel"
        assert data["items"][1]["file_name"] == "meetings"

    def test_search_requires_query(self, client):
        """GET /context/search without q returns 422."""
        user = _make_user()
        mock_db = _mock_db()

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/context/search")
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"] == "ValidationError"
        assert data["code"] == 422


# ===========================================================================
# TestContextStats
# ===========================================================================


class TestContextStats:
    def test_file_stats(self, client):
        """GET /context/files/{name}/stats returns count, last_updated, sources."""
        user = _make_user()
        last_updated = datetime.datetime(2026, 3, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        mock_db = _mock_db([
            MockResult(scalar_val=10),     # entry_count
            MockResult(scalar_val=last_updated),  # last_updated
            MockResult(scalar_val=["skill-a", "skill-b"]),  # sources
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/context/files/company-intel/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entry_count"] == 10
        assert data["last_updated"] is not None
        assert "skill-a" in data["sources"]
