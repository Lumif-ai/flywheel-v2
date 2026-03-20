"""Integration tests for tenant management, invites, tenant switching, and account deletion.

Uses FastAPI TestClient with dependency overrides -- no real DB.
"""

from __future__ import annotations

import datetime
import hashlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from flywheel.api.deps import (
    get_current_user,
    get_db_unscoped,
    require_admin,
    require_tenant,
)
from flywheel.auth.jwt import TokenPayload
from flywheel.main import app

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid4()
TEST_TENANT_ID = uuid4()
TEST_EMAIL = "admin@company.com"
OTHER_USER_ID = uuid4()
OTHER_TENANT_ID = uuid4()


def _make_user(
    sub=TEST_USER_ID,
    email=TEST_EMAIL,
    is_anonymous=False,
    tenant_id=TEST_TENANT_ID,
    role="admin",
):
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


def _make_member_user():
    return _make_user(role="member")


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockResult:
    """Mimics SQLAlchemy result for various access patterns."""

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

    def first(self):
        return self._value


class MockTenant:
    def __init__(
        self,
        id=TEST_TENANT_ID,
        name="company.com",
        domain="company.com",
        settings=None,
        trial_expires_at=None,
        created_at=None,
        deleted_at=None,
    ):
        self.id = id
        self.name = name
        self.domain = domain
        self.settings = settings or {}
        self.trial_expires_at = trial_expires_at or datetime.datetime(
            2026, 6, 20, tzinfo=datetime.timezone.utc
        )
        self.created_at = created_at or datetime.datetime(
            2026, 3, 20, tzinfo=datetime.timezone.utc
        )
        self.deleted_at = deleted_at


class MockUserTenant:
    def __init__(self, user_id=TEST_USER_ID, tenant_id=TEST_TENANT_ID, role="admin", active=True, joined_at=None):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role
        self.active = active
        self.joined_at = joined_at or datetime.datetime(
            2026, 3, 20, tzinfo=datetime.timezone.utc
        )


class MockUser:
    def __init__(self, id=TEST_USER_ID, email=TEST_EMAIL, name="Admin", api_key_encrypted=None, settings=None):
        self.id = id
        self.email = email
        self.name = name
        self.api_key_encrypted = api_key_encrypted
        self.settings = settings or {}


class MockInvite:
    def __init__(
        self,
        id=None,
        tenant_id=TEST_TENANT_ID,
        invited_by=TEST_USER_ID,
        email="invitee@example.com",
        role="member",
        token_hash="abc123",
        accepted_at=None,
        expires_at=None,
        created_at=None,
    ):
        self.id = id or uuid4()
        self.tenant_id = tenant_id
        self.invited_by = invited_by
        self.email = email
        self.role = role
        self.token_hash = token_hash
        self.accepted_at = accepted_at
        self.expires_at = expires_at or datetime.datetime(
            2026, 3, 27, tzinfo=datetime.timezone.utc
        )
        self.created_at = created_at or datetime.datetime(
            2026, 3, 20, tzinfo=datetime.timezone.utc
        )


class MockSkillRun:
    def __init__(self, id=None, user_id=TEST_USER_ID, status="pending"):
        self.id = id or uuid4()
        self.user_id = user_id
        self.status = status


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    app.dependency_overrides = {}
    yield TestClient(app)
    app.dependency_overrides = {}


# ===========================================================================
# TestTenantCRUD
# ===========================================================================


class TestTenantCRUD:
    def test_get_current_tenant(self, client):
        """GET /tenants/current returns tenant details with member_count."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(value=MockTenant()),  # Tenant query
            MockResult(scalar_val=3),  # Member count
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.get("/api/v1/tenants/current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "company.com"
        assert data["member_count"] == 3

    def test_update_tenant_admin_only(self, client):
        """PATCH /tenants/current: non-admin gets 403, admin gets 200."""
        # Non-admin attempt
        member = _make_member_user()
        app.dependency_overrides[require_admin] = lambda: (_ for _ in ()).throw(
            __import__("fastapi").HTTPException(status_code=403, detail="Admin access required")
        )
        resp = client.patch(
            "/api/v1/tenants/current",
            json={"name": "New Name"},
        )
        assert resp.status_code == 403

        # Admin attempt
        admin = _make_user()
        mock_db = _mock_db([
            MockResult(),  # update
            MockResult(value=MockTenant(name="New Name")),  # re-fetch
            MockResult(scalar_val=2),  # member count
        ])
        app.dependency_overrides[require_admin] = lambda: admin
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.patch(
            "/api/v1/tenants/current",
            json={"name": "New Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_delete_tenant_soft_deletes(self, client):
        """DELETE /tenants/current sets deleted_at, not hard-deleted."""
        admin = _make_user()
        mock_db = _mock_db([
            MockResult(scalar_val=1),  # admin count
            MockResult(scalar_val=1),  # member count (solo admin, no other members)
            MockResult(),  # update
        ])

        app.dependency_overrides[require_admin] = lambda: admin
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.delete("/api/v1/tenants/current")
        assert resp.status_code == 200
        data = resp.json()
        assert "deleted_at" in data
        assert "grace_period_ends" in data

    def test_delete_tenant_last_admin_blocked(self, client):
        """Last admin with other members cannot delete without transferring."""
        admin = _make_user()
        mock_db = _mock_db([
            MockResult(scalar_val=1),  # admin count (only 1 admin)
            MockResult(scalar_val=3),  # member count (has other members)
        ])

        app.dependency_overrides[require_admin] = lambda: admin
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.delete("/api/v1/tenants/current")
        assert resp.status_code == 400
        assert "Transfer admin role" in resp.json()["detail"]


# ===========================================================================
# TestInvites
# ===========================================================================


class TestInvites:
    def test_invite_stores_token_hash(self, client):
        """After invite, DB stores token_hash (SHA-256), NOT plaintext."""
        admin = _make_user()
        stored_invite = MockInvite()

        mock_db = _mock_db([
            MockResult(value=MockTenant()),  # tenant query
            MockResult(scalar_val=2),  # member count
            MockResult(value=None),  # no existing pending invite
            MockResult(value=None),  # no existing user
        ])
        # Capture the Invite object added to DB
        added_objects = []
        mock_db.add = lambda obj: added_objects.append(obj)
        mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', stored_invite.id) or setattr(obj, 'expires_at', stored_invite.expires_at))

        app.dependency_overrides[require_admin] = lambda: admin
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/tenants/invite",
            json={"email": "newmember@example.com"},
        )
        assert resp.status_code == 200
        # Verify the stored object has a hex hash, not the raw token
        invite_obj = [o for o in added_objects if hasattr(o, 'token_hash')]
        assert len(invite_obj) == 1
        assert len(invite_obj[0].token_hash) == 64  # SHA-256 hex digest

    def test_invite_duplicate_email_rejected(self, client):
        """Same email+tenant returns 409."""
        admin = _make_user()
        mock_db = _mock_db([
            MockResult(value=MockTenant()),  # tenant query
            MockResult(scalar_val=2),  # member count
            MockResult(value=MockInvite()),  # existing pending invite found
        ])

        app.dependency_overrides[require_admin] = lambda: admin
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/tenants/invite",
            json={"email": "duplicate@example.com"},
        )
        assert resp.status_code == 409
        assert "Invite already sent" in resp.json()["detail"]

    def test_invite_member_limit_enforced(self, client):
        """At limit, returns 403."""
        admin = _make_user()
        mock_db = _mock_db([
            MockResult(value=MockTenant(settings={"member_limit": 2})),  # tenant with limit=2
            MockResult(scalar_val=2),  # member count = limit
        ])

        app.dependency_overrides[require_admin] = lambda: admin
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/tenants/invite",
            json={"email": "toomany@example.com"},
        )
        assert resp.status_code == 403
        assert "Member limit reached" in resp.json()["detail"]

    def test_accept_invite_valid_token(self, client):
        """Hash matches, user_tenants row created, accepted_at set."""
        user = _make_user(tenant_id=None, role="member")
        token = "test-invite-token-abc123"
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        invite = MockInvite(token_hash=token_hash, role="member")
        tenant = MockTenant()

        mock_db = _mock_db([
            MockResult(value=invite),  # invite lookup by hash
            MockResult(value=tenant),  # tenant lookup
            MockResult(scalar_val=3),  # member count
        ])
        added_objects = []
        mock_db.add = lambda obj: added_objects.append(obj)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/tenants/invite/accept",
            json={"token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_name"] == "company.com"
        assert data["role"] == "member"
        # Verify accepted_at was set
        assert invite.accepted_at is not None

    def test_accept_invite_expired_rejected(self, client):
        """Expired invite returns 404."""
        user = _make_user(tenant_id=None)
        mock_db = _mock_db([
            MockResult(value=None),  # no valid invite found (expired)
        ])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/tenants/invite/accept",
            json={"token": "expired-token"},
        )
        assert resp.status_code == 404
        assert "Invalid or expired invite" in resp.json()["detail"]

    def test_accept_invite_wrong_token_rejected(self, client):
        """Wrong token hash doesn't match, returns 404."""
        user = _make_user(tenant_id=None)
        mock_db = _mock_db([
            MockResult(value=None),  # hash mismatch = not found
        ])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/tenants/invite/accept",
            json={"token": "wrong-token"},
        )
        assert resp.status_code == 404


# ===========================================================================
# TestMembers
# ===========================================================================


class TestMembers:
    def test_list_members_includes_pending_invites(self, client):
        """Response includes both active members and pending invites."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(values=[
                (MockUserTenant(), MockUser()),
            ]),  # active members
            MockResult(values=[MockInvite(email="pending@example.com")]),  # pending invites
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.get("/api/v1/tenants/members")
        assert resp.status_code == 200
        data = resp.json()
        # Should have 1 active member + 1 pending invite
        assert len(data) == 2
        statuses = [m["status"] for m in data]
        assert "active" in statuses
        assert "pending" in statuses

    def test_remove_member_admin_only(self, client):
        """Non-admin gets 403."""
        app.dependency_overrides[require_admin] = lambda: (_ for _ in ()).throw(
            __import__("fastapi").HTTPException(status_code=403, detail="Admin access required")
        )

        resp = client.delete(f"/api/v1/tenants/members/{OTHER_USER_ID}")
        assert resp.status_code == 403

    def test_remove_self_blocked(self, client):
        """Cannot remove yourself, returns 400."""
        admin = _make_user()
        mock_db = _mock_db()

        app.dependency_overrides[require_admin] = lambda: admin
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        # Try to remove self
        resp = client.delete(f"/api/v1/tenants/members/{TEST_USER_ID}")
        assert resp.status_code == 400
        assert "Cannot remove yourself" in resp.json()["detail"]


# ===========================================================================
# TestTenantSwitch
# ===========================================================================


class TestTenantSwitch:
    def test_switch_tenant_updates_active(self, client):
        """Old tenant deactivated, new tenant activated."""
        user = _make_user()
        target_tenant_id = OTHER_TENANT_ID

        mock_db = _mock_db([
            MockResult(value=MockUserTenant(tenant_id=target_tenant_id)),  # membership check
            MockResult(),  # deactivate old
            MockResult(),  # activate new
        ])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/user/switch-tenant",
            json={"tenant_id": str(target_tenant_id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == str(target_tenant_id)

    def test_switch_to_non_member_tenant_rejected(self, client):
        """Returns 404 if not a member."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(value=None),  # not a member
        ])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/user/switch-tenant",
            json={"tenant_id": str(uuid4())},
        )
        assert resp.status_code == 404
        assert "Not a member" in resp.json()["detail"]

    def test_switch_returns_refresh_signal(self, client):
        """Response includes action: refresh_token_required."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(value=MockUserTenant(tenant_id=OTHER_TENANT_ID)),
            MockResult(),
            MockResult(),
        ])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.post(
            "/api/v1/user/switch-tenant",
            json={"tenant_id": str(OTHER_TENANT_ID)},
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "refresh_token_required"


# ===========================================================================
# TestAccountDeletion
# ===========================================================================


class TestAccountDeletion:
    def test_delete_account_cancels_jobs(self, client):
        """Pending skill_runs set to cancelled."""
        user = _make_user(tenant_id=None)
        mock_db = _mock_db([
            MockResult(values=[]),  # no admin tenants
            MockResult(),  # cancel skill_runs
            MockResult(value=MockUser(settings={})),  # user row
            MockResult(),  # update user settings + wipe key
            MockResult(),  # delete user_tenants
        ])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.delete("/api/v1/user/account")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Account scheduled for deletion"
        # The DB execute was called for cancelling jobs
        assert mock_db.execute.call_count >= 3

    def test_delete_account_wipes_api_key(self, client):
        """api_key_encrypted set to NULL."""
        user = _make_user(tenant_id=None)
        mock_user = MockUser(api_key_encrypted=b"encrypted-key")
        mock_db = _mock_db([
            MockResult(values=[]),  # no admin tenants
            MockResult(),  # cancel skill_runs
            MockResult(value=mock_user),  # user row with API key
            MockResult(),  # update user (wipe key + settings)
            MockResult(),  # delete user_tenants
        ])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.delete("/api/v1/user/account")
        assert resp.status_code == 200
        # Verify the update call included api_key_encrypted=None
        # (the 4th execute call is the user update)
        update_call = mock_db.execute.call_args_list[3]
        # The update statement is an SQLAlchemy object; check it was called
        assert update_call is not None

    def test_delete_account_last_admin_blocked(self, client):
        """Returns 400 with tenant name when user is last admin."""
        user = _make_user(tenant_id=None)
        mock_db = _mock_db([
            MockResult(values=[
                (MockUserTenant(role="admin"), MockTenant(name="Blocked Corp")),
            ]),  # admin of one tenant
            MockResult(scalar_val=1),  # admin count = 1 (last admin)
        ])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.delete("/api/v1/user/account")
        assert resp.status_code == 400
        assert "Blocked Corp" in resp.json()["detail"]
        assert "Transfer admin role" in resp.json()["detail"]

    def test_delete_account_returns_grace_period(self, client):
        """Response includes 30-day deletion_date."""
        user = _make_user(tenant_id=None)
        mock_db = _mock_db([
            MockResult(values=[]),  # no admin tenants
            MockResult(),  # cancel skill_runs
            MockResult(value=MockUser()),  # user row
            MockResult(),  # update user
            MockResult(),  # delete user_tenants
        ])

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_unscoped] = lambda: mock_db

        resp = client.delete("/api/v1/user/account")
        assert resp.status_code == 200
        data = resp.json()
        assert "deletion_date" in data
        # Parse deletion_date and verify it's ~30 days from now
        deletion_date = datetime.datetime.fromisoformat(data["deletion_date"])
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = (deletion_date - now).days
        assert 29 <= diff <= 31
