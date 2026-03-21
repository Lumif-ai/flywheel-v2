"""Tests for POST /context/batch endpoint.

Uses FastAPI TestClient with dependency overrides -- no real DB.
Verifies: atomic batch insert, catalog upsert, validation, auth requirement.
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


def _mock_db(execute_side_effects=None):
    db = AsyncMock()
    if execute_side_effects:
        db.execute = AsyncMock(side_effect=execute_side_effects)
    else:
        db.execute = AsyncMock(return_value=MockResult())
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    db.delete = AsyncMock()

    # refresh populates DB-generated fields on entries
    def _refresh(obj):
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid4()
        if not hasattr(obj, "date") or obj.date is None:
            obj.date = datetime.date(2026, 3, 21)
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.datetime(2026, 3, 21, tzinfo=datetime.timezone.utc)
        if not hasattr(obj, "updated_at") or obj.updated_at is None:
            obj.updated_at = datetime.datetime(2026, 3, 21, tzinfo=datetime.timezone.utc)
        if not hasattr(obj, "evidence_count") or obj.evidence_count is None:
            obj.evidence_count = 1

    db.refresh = AsyncMock(side_effect=_refresh)
    return db


@pytest.fixture
def client():
    app.dependency_overrides = {}
    yield TestClient(app)
    app.dependency_overrides = {}


# ===========================================================================
# TestContextBatch
# ===========================================================================


class TestContextBatch:
    def test_batch_creates_multiple_entries(self, client):
        """POST /context/batch creates entries and returns them with count."""
        user = _make_user()
        mock_db = _mock_db()

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(
            "/api/v1/context/batch",
            json={
                "entries": [
                    {
                        "file_name": "contacts.md",
                        "content": "Alice at Acme Corp",
                        "source": "research-skill",
                        "confidence": "high",
                    },
                    {
                        "file_name": "companies.md",
                        "content": "Acme Corp is in manufacturing",
                        "source": "research-skill",
                    },
                ]
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["count"] == 2
        assert len(data["entries"]) == 2
        assert data["entries"][0]["source"] == "research-skill"
        assert data["entries"][1]["confidence"] == "medium"  # default

        # Verify add_all was called (atomic insert)
        mock_db.add_all.assert_called_once()
        mock_db.commit.assert_awaited_once()

    def test_batch_upserts_catalog_per_file(self, client):
        """POST /context/batch upserts catalog for each unique file_name."""
        user = _make_user()
        mock_db = _mock_db()

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(
            "/api/v1/context/batch",
            json={
                "entries": [
                    {"file_name": "contacts.md", "content": "Entry 1", "source": "s1"},
                    {"file_name": "contacts.md", "content": "Entry 2", "source": "s1"},
                    {"file_name": "companies.md", "content": "Entry 3", "source": "s1"},
                ]
            },
        )

        assert resp.status_code == 201
        # 2 unique files = 2 catalog upsert calls
        assert mock_db.execute.await_count == 2

    def test_batch_empty_entries_returns_422(self, client):
        """POST /context/batch with empty entries array returns 422."""
        user = _make_user()
        mock_db = _mock_db()

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(
            "/api/v1/context/batch",
            json={"entries": []},
        )

        assert resp.status_code == 422

    def test_batch_exceeds_max_returns_422(self, client):
        """POST /context/batch with >50 entries returns 422."""
        user = _make_user()
        mock_db = _mock_db()

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        entries = [
            {"file_name": "f.md", "content": f"Entry {i}", "source": "s"}
            for i in range(51)
        ]

        resp = client.post(
            "/api/v1/context/batch",
            json={"entries": entries},
        )

        assert resp.status_code == 422

    def test_batch_requires_auth(self, client):
        """POST /context/batch without auth returns 401."""
        resp = client.post(
            "/api/v1/context/batch",
            json={
                "entries": [
                    {"file_name": "f.md", "content": "test", "source": "s"},
                ]
            },
        )
        assert resp.status_code == 401

    def test_batch_single_entry_works(self, client):
        """POST /context/batch with exactly 1 entry succeeds."""
        user = _make_user()
        mock_db = _mock_db()

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(
            "/api/v1/context/batch",
            json={
                "entries": [
                    {
                        "file_name": "notes.md",
                        "content": "Single note",
                        "source": "cli",
                        "detail": "manual entry",
                        "confidence": "low",
                    },
                ]
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["count"] == 1
        assert data["entries"][0]["detail"] == "manual entry"
        assert data["entries"][0]["confidence"] == "low"
