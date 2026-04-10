"""Integration tests for the document-production contract (Standard 15).

Verifies that POST /documents/from-content enforces:
1. account_id is set and validated against pipeline_entries
2. Human-readable titles (no UUID patterns)
3. Non-empty tags array with validation
4. 400 when account_id references a non-existent pipeline_entry

Uses FastAPI TestClient with dependency overrides -- no real DB.
"""

from __future__ import annotations

import datetime
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
VALID_ACCOUNT_ID = uuid4()
NONEXISTENT_ACCOUNT_ID = "00000000-0000-0000-0000-000000000000"


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
    """Minimal result proxy for mocked db.execute() calls."""

    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class MockDocument:
    """Fake Document ORM object returned after db.flush/commit."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.title = kwargs.get("title", "")
        self.document_type = kwargs.get("document_type", "")
        self.tags = kwargs.get("tags", [])
        self.account_id = kwargs.get("account_id")
        self.skill_run_id = kwargs.get("skill_run_id")
        self.tenant_id = kwargs.get("tenant_id")
        self.user_id = kwargs.get("user_id")
        self.storage_path = kwargs.get("storage_path")
        self.file_size_bytes = kwargs.get("file_size_bytes", 0)
        self.metadata_ = kwargs.get("metadata_", {})
        self.created_at = kwargs.get("created_at", datetime.datetime.now(datetime.timezone.utc))
        self.deleted_at = None


def _mock_db(execute_side_effects=None):
    """Build a mock AsyncSession with configurable execute responses."""
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
# TestDocumentContract -- Standard 15 enforcement
# ===========================================================================


class TestDocumentContract:
    """Verify the document-production contract on POST /documents/from-content."""

    def test_save_with_valid_account_id(self, client):
        """Document save with a valid account_id succeeds and returns document_id."""
        user = _make_user()

        # Two execute calls:
        #   1. Account lookup (PipelineEntry.id) -> found
        #   2. Dedup query -> no match
        mock_db_inst = _mock_db(
            execute_side_effects=[
                MockResult(value=VALID_ACCOUNT_ID),   # account exists
                MockResult(value=None),               # no dedup match
            ]
        )

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db_inst

        with patch("flywheel.engines.output_renderer.render_output", return_value="<p>rendered</p>"):
            resp = client.post(
                "/api/v1/documents/from-content",
                json={
                    "title": "Meeting Prep: Acme Corp — Q4 Review",
                    "skill_name": "meeting-prep",
                    "markdown_content": "# Q4 Review\nKey metrics...",
                    "account_id": str(VALID_ACCOUNT_ID),
                    "tags": ["sales"],
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert "document_id" in data
        assert "skill_run_id" in data

    def test_save_with_human_readable_title(self, client):
        """Document title is preserved as-is (human-readable, no UUIDs)."""
        user = _make_user()
        mock_db_inst = _mock_db(
            execute_side_effects=[
                MockResult(value=None),  # dedup query -> no match
            ]
        )

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db_inst

        human_title = "Meeting Prep: Acme Corp \u2014 Q4 Review"

        with patch("flywheel.engines.output_renderer.render_output", return_value="<p>rendered</p>"):
            resp = client.post(
                "/api/v1/documents/from-content",
                json={
                    "title": human_title,
                    "skill_name": "meeting-prep",
                    "markdown_content": "# Content",
                },
            )

        assert resp.status_code == 201
        # Verify the Document was created with the correct title by inspecting
        # what was passed to db.add(). The second add call is the Document.
        added_objects = [call.args[0] for call in mock_db_inst.add.call_args_list]
        doc = added_objects[-1]  # Last added object is the Document
        assert doc.title == human_title

    def test_save_with_tags_array(self, client):
        """Document save with tags persists validated tags on the document."""
        user = _make_user()
        mock_db_inst = _mock_db(
            execute_side_effects=[
                MockResult(value=None),  # dedup query -> no match
            ]
        )

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db_inst

        with patch("flywheel.engines.output_renderer.render_output", return_value="<p>rendered</p>"):
            resp = client.post(
                "/api/v1/documents/from-content",
                json={
                    "title": "Competitive Analysis: Gong vs Chorus",
                    "skill_name": "account-research",
                    "markdown_content": "# Analysis",
                    "tags": ["sales", "q4-review"],
                },
            )

        assert resp.status_code == 201
        # Verify the Document was created with the correct tags
        added_objects = [call.args[0] for call in mock_db_inst.add.call_args_list]
        doc = added_objects[-1]
        assert doc.tags == ["sales", "q4-review"]

    def test_save_with_invalid_account_id_returns_400(self, client):
        """Document save with a non-existent account_id returns 400."""
        user = _make_user()

        # Account lookup returns None -> not found
        mock_db_inst = _mock_db(
            execute_side_effects=[
                MockResult(value=None),  # account does NOT exist
            ]
        )

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db_inst

        with patch("flywheel.engines.output_renderer.render_output", return_value="<p>rendered</p>"):
            resp = client.post(
                "/api/v1/documents/from-content",
                json={
                    "title": "Should Fail: Bad Account",
                    "skill_name": "meeting-prep",
                    "markdown_content": "# Content",
                    "account_id": NONEXISTENT_ACCOUNT_ID,
                    "tags": ["sales"],
                },
            )

        assert resp.status_code == 400
        body = resp.json()
        error_text = body.get("detail", body.get("message", "")).lower()
        assert "not found" in error_text
