"""Integration tests for auth and onboarding endpoints.

Uses FastAPI TestClient with dependency overrides -- no real Supabase or DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from flywheel.api.deps import get_current_user, get_db_unscoped, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.main import app

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid4()
TEST_TENANT_ID = uuid4()
TEST_EMAIL = "alice@example.com"

ANON_USER_ID = uuid4()


def _make_user(
    sub=TEST_USER_ID,
    email=TEST_EMAIL,
    is_anonymous=False,
    tenant_id=TEST_TENANT_ID,
    role="admin",
):
    """Create a TokenPayload for dependency overrides."""
    app_metadata = {}
    if tenant_id:
        app_metadata["tenant_id"] = str(tenant_id)
        app_metadata["role"] = role
    return TokenPayload(
        sub=sub,
        email=email,
        is_anonymous=is_anonymous,
        app_metadata=app_metadata,
    )


def _make_anon_user():
    return _make_user(
        sub=ANON_USER_ID,
        email=None,
        is_anonymous=True,
        tenant_id=None,
    )


# ---------------------------------------------------------------------------
# Mock DB helpers
# ---------------------------------------------------------------------------


class MockResult:
    """Mimics SQLAlchemy result for scalar_one_or_none and scalars().all()."""

    def __init__(self, value=None, values=None):
        self._value = value
        self._values = values or []

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._values

    def first(self):
        return self._value


class MockUser:
    """Mimics a User ORM row."""

    def __init__(self, id=TEST_USER_ID, email=TEST_EMAIL, name="Alice", api_key_encrypted=None):
        self.id = id
        self.email = email
        self.name = name
        self.api_key_encrypted = api_key_encrypted


class MockUserTenant:
    """Mimics a UserTenant ORM row."""

    def __init__(self, role="admin"):
        self.role = role


class MockTenantObj:
    """Mimics a Tenant ORM row."""

    def __init__(self, id=TEST_TENANT_ID, name="example.com"):
        self.id = id
        self.name = name


def _mock_db_session(execute_side_effects=None):
    """Create a mock AsyncSession."""
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """TestClient with clean dependency overrides."""
    app.dependency_overrides = {}
    yield TestClient(app)
    app.dependency_overrides = {}


# ---------------------------------------------------------------------------
# TestMagicLink
# ---------------------------------------------------------------------------


class TestMagicLink:
    def test_magic_link_sends_email(self, client):
        """POST /auth/magic-link with valid email returns 200."""
        mock_supabase = AsyncMock()
        mock_supabase.auth.sign_in_with_otp = AsyncMock(return_value=None)

        with patch("flywheel.api.auth.get_supabase_admin", return_value=mock_supabase):
            resp = client.post(
                "/api/v1/auth/magic-link",
                json={"email": "test@example.com"},
            )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Magic link sent"

    def test_magic_link_missing_email(self, client):
        """POST /auth/magic-link with empty body returns 422."""
        resp = client.post("/api/v1/auth/magic-link", json={})
        assert resp.status_code == 422

    def test_magic_link_invalid_email(self, client):
        """POST /auth/magic-link with malformed email returns 422."""
        resp = client.post(
            "/api/v1/auth/magic-link",
            json={"email": "not-an-email"},
        )
        assert resp.status_code == 422

    def test_magic_link_does_not_leak_existence(self, client):
        """Same response whether email exists or Supabase raises."""
        mock_supabase = AsyncMock()
        mock_supabase.auth.sign_in_with_otp = AsyncMock(side_effect=Exception("not found"))

        with patch("flywheel.api.auth.get_supabase_admin", return_value=mock_supabase):
            resp = client.post(
                "/api/v1/auth/magic-link",
                json={"email": "unknown@example.com"},
            )
        # Still returns 200 with same message -- no leak
        assert resp.status_code == 200
        assert resp.json()["message"] == "Magic link sent"


# ---------------------------------------------------------------------------
# TestAnonymous
# ---------------------------------------------------------------------------


class TestAnonymous:
    def test_anonymous_creates_session(self, client):
        """POST /auth/anonymous returns access_token."""
        mock_session = MagicMock()
        mock_session.access_token = "test-access-token"
        mock_session.refresh_token = "test-refresh-token"
        mock_user = MagicMock()
        mock_user.id = str(uuid4())
        mock_user.is_anonymous = True

        mock_result = MagicMock()
        mock_result.session = mock_session
        mock_result.user = mock_user

        mock_supabase = AsyncMock()
        mock_supabase.auth.sign_in_anonymously = AsyncMock(return_value=mock_result)

        with patch("flywheel.api.auth.get_supabase_admin", return_value=mock_supabase):
            resp = client.post("/api/v1/auth/anonymous")
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "test-access-token"
        assert data["refresh_token"] == "test-refresh-token"
        assert data["user"]["is_anonymous"] is True


# ---------------------------------------------------------------------------
# TestMe
# ---------------------------------------------------------------------------


class TestMe:
    def test_me_returns_profile(self, client):
        """GET /auth/me with valid JWT returns user fields."""
        user_payload = _make_user()
        mock_db = _mock_db_session([
            MockResult(value=MockUser()),  # User query
            MockResult(value=(MockUserTenant(), MockTenantObj())),  # UserTenant query
        ])

        app.dependency_overrides[get_current_user] = lambda: user_payload
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == str(TEST_USER_ID)
        assert data["email"] == TEST_EMAIL
        assert data["is_anonymous"] is False
        assert data["has_api_key"] is False

    def test_me_shows_has_api_key(self, client):
        """User with api_key_encrypted returns has_api_key=true."""
        user_payload = _make_user()
        mock_db = _mock_db_session([
            MockResult(value=MockUser(api_key_encrypted=b"encrypted")),
            MockResult(value=(MockUserTenant(), MockTenantObj())),
        ])

        app.dependency_overrides[get_current_user] = lambda: user_payload
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json()["has_api_key"] is True

    def test_me_unauthorized(self, client):
        """GET /auth/me without token returns 401."""
        app.dependency_overrides = {}
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# TestAPIKey
# ---------------------------------------------------------------------------


class TestAPIKey:
    def test_store_api_key_encrypts(self, client):
        """POST /auth/api-key with valid key encrypts and stores."""
        user_payload = _make_user()
        mock_db = _mock_db_session()

        app.dependency_overrides[require_tenant] = lambda: user_payload
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        # Mock Anthropic validation (success)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("flywheel.api.auth.httpx.AsyncClient", return_value=mock_http), \
             patch("flywheel.api.auth.encrypt_api_key", return_value=b"encrypted") as mock_enc:
            resp = client.post(
                "/api/v1/auth/api-key",
                json={"api_key": "sk-test-key"},
            )
        assert resp.status_code == 200
        assert resp.json()["has_api_key"] is True
        mock_enc.assert_called_once_with("sk-test-key")

    def test_store_api_key_invalid_rejected(self, client):
        """POST /auth/api-key with invalid key (Anthropic 401) returns 400."""
        user_payload = _make_user()
        mock_db = _mock_db_session()

        app.dependency_overrides[require_tenant] = lambda: user_payload
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("flywheel.api.auth.httpx.AsyncClient", return_value=mock_http):
            resp = client.post(
                "/api/v1/auth/api-key",
                json={"api_key": "sk-invalid-key"},
            )
        assert resp.status_code == 400
        assert "Invalid API key" in resp.json()["detail"]

    def test_delete_api_key(self, client):
        """DELETE /auth/api-key sets api_key_encrypted to NULL."""
        user_payload = _make_user()
        mock_db = _mock_db_session()

        app.dependency_overrides[require_tenant] = lambda: user_payload
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.delete("/api/v1/auth/api-key")
        assert resp.status_code == 200
        assert resp.json()["has_api_key"] is False

    def test_api_key_never_returned(self, client):
        """After storing, GET /auth/me returns has_api_key=true but no key field."""
        user_payload = _make_user()
        mock_db = _mock_db_session([
            MockResult(value=MockUser(api_key_encrypted=b"encrypted")),
            MockResult(value=(MockUserTenant(), MockTenantObj())),
        ])

        app.dependency_overrides[get_current_user] = lambda: user_payload
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.get("/api/v1/auth/me")
        data = resp.json()
        assert data["has_api_key"] is True
        assert "api_key" not in data
        assert "api_key_encrypted" not in data


# ---------------------------------------------------------------------------
# TestPromotion
# ---------------------------------------------------------------------------


class TestPromotion:
    def test_promote_anonymous_creates_tenant(self, client):
        """POST /onboarding/promote with anonymous user creates tenant."""
        anon_user = _make_anon_user()
        mock_db = _mock_db_session([
            MockResult(),  # User select (none found)
            MockResult(values=[]),  # Onboarding sessions
        ])

        app.dependency_overrides[get_current_user] = lambda: anon_user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/onboarding/promote",
            json={"email": "newuser@company.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Account promoted"
        assert "tenant_id" in data

    def test_promote_non_anonymous_rejected(self, client):
        """POST /onboarding/promote with non-anonymous user returns 400."""
        regular_user = _make_user(is_anonymous=False)

        app.dependency_overrides[get_current_user] = lambda: regular_user

        resp = client.post(
            "/api/v1/onboarding/promote",
            json={"email": "user@company.com"},
        )
        assert resp.status_code == 400
        assert "Already authenticated" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# TestSubsidyStatus
# ---------------------------------------------------------------------------


class TestSubsidyStatus:
    def test_subsidy_status_returns_remaining(self, client):
        """GET /onboarding/subsidy-status with anonymous user shows runs."""
        anon_user = _make_anon_user()
        # One session with 1 skill run
        mock_db = _mock_db_session([
            MockResult(values=[{"skill_runs": [{"id": 1}]}]),
        ])

        app.dependency_overrides[get_current_user] = lambda: anon_user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.get("/api/v1/onboarding/subsidy-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["runs_used"] == 1
        assert data["runs_remaining"] == 2
        assert data["limit"] == 3

    def test_subsidy_status_non_anonymous_rejected(self, client):
        """GET /onboarding/subsidy-status with non-anonymous user returns 400."""
        regular_user = _make_user(is_anonymous=False)
        app.dependency_overrides[get_current_user] = lambda: regular_user

        resp = client.get("/api/v1/onboarding/subsidy-status")
        assert resp.status_code == 400
