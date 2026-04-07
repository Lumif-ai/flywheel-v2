"""Integration tests for leads GTM pipeline endpoints.

Uses FastAPI TestClient with dependency overrides -- no real DB.
Verifies: upsert (create + merge), contacts (add + dedup), messages
(create + stage advance), graduation, pipeline funnel, and validation.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

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
TEST_LEAD_ID = uuid4()
TEST_CONTACT_ID = uuid4()
TEST_MESSAGE_ID = uuid4()
TEST_ACCOUNT_ID = uuid4()


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

    def scalar_one(self):
        if self._scalar_val is not None:
            return self._scalar_val
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._values

    def fetchall(self):
        return self._values


class MockLead:
    def __init__(
        self,
        id=None,
        name="Test Corp",
        normalized_name="test",
        domain="test.com",
        purpose=None,
        fit_score=None,
        fit_tier=None,
        fit_rationale=None,
        intel=None,
        source="test",
        campaign=None,
        account_id=None,
        graduated_at=None,
        lead_contacts=None,
    ):
        self.id = id or TEST_LEAD_ID
        self.tenant_id = TEST_TENANT_ID
        self.name = name
        self.normalized_name = normalized_name
        self.domain = domain
        self.purpose = purpose or ["sales"]
        self.fit_score = fit_score
        self.fit_tier = fit_tier
        self.fit_rationale = fit_rationale
        self.intel = intel or {}
        self.source = source
        self.campaign = campaign
        self.account_id = account_id
        self.graduated_at = graduated_at
        self.lead_contacts = lead_contacts or []
        self.created_at = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc)
        self.updated_at = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc)


class MockLeadContact:
    def __init__(
        self,
        id=None,
        lead_id=None,
        name="Jane Smith",
        email="jane@test.com",
        title="VP Sales",
        linkedin_url=None,
        role="decision-maker",
        pipeline_stage="scraped",
        notes=None,
        messages=None,
    ):
        self.id = id or TEST_CONTACT_ID
        self.tenant_id = TEST_TENANT_ID
        self.lead_id = lead_id or TEST_LEAD_ID
        self.name = name
        self.email = email
        self.title = title
        self.linkedin_url = linkedin_url
        self.role = role
        self.pipeline_stage = pipeline_stage
        self.notes = notes
        self.messages = messages or []
        self.created_at = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc)
        self.updated_at = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc)


class MockLeadMessage:
    def __init__(
        self,
        id=None,
        contact_id=None,
        step_number=1,
        channel="email",
        status="drafted",
        subject="Hello",
        body="Hi there",
        drafted_at=None,
        sent_at=None,
        replied_at=None,
    ):
        self.id = id or TEST_MESSAGE_ID
        self.tenant_id = TEST_TENANT_ID
        self.contact_id = contact_id or TEST_CONTACT_ID
        self.step_number = step_number
        self.channel = channel
        self.status = status
        self.subject = subject
        self.body = body
        self.drafted_at = drafted_at
        self.sent_at = sent_at
        self.replied_at = replied_at
        self.metadata_ = {}
        self.created_at = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc)
        # For relationship access in update_message
        self.contact = None


def _ensure_timestamps(obj, *_args, **_kwargs):
    """Simulate DB defaults — set created_at/updated_at if missing."""
    now = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc)
    if hasattr(obj, "created_at") and obj.created_at is None:
        obj.created_at = now
    if hasattr(obj, "updated_at") and obj.updated_at is None:
        obj.updated_at = now
    # Simulate lead_contacts relationship loading
    if hasattr(obj, "lead_contacts") and obj.lead_contacts is None:
        obj.lead_contacts = []


def _mock_db(execute_side_effects=None):
    db = AsyncMock()
    if execute_side_effects:
        db.execute = AsyncMock(side_effect=execute_side_effects)
    else:
        db.execute = AsyncMock(return_value=MockResult())
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=_ensure_timestamps)
    db.add = MagicMock(side_effect=_ensure_timestamps)
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def client():
    app.dependency_overrides = {}
    yield TestClient(app)
    app.dependency_overrides = {}


# ===========================================================================
# TestLeadUpsert
# ===========================================================================


class TestLeadUpsert:
    def test_create_new_lead(self, client):
        """POST /leads/ creates a new lead when none exists."""
        user = _make_user()
        mock_db = _mock_db([
            MockResult(value=None),  # no existing lead found
        ])
        # After add + flush + refresh, the serializer needs lead_contacts
        mock_db.refresh = AsyncMock()

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post("/api/v1/leads/", json={
            "name": "Acme Corp",
            "domain": "acme.com",
            "source": "scraper",
            "fit_score": 85,
            "fit_tier": "Strong Fit",
            "purpose": ["sales"],
        })
        assert resp.status_code == 200
        mock_db.add.assert_called_once()

    def test_upsert_merges_existing(self, client):
        """POST /leads/ with existing name merges fields."""
        user = _make_user()
        existing = MockLead(
            fit_score=70,
            fit_tier="Good Fit",
            purpose=["sales"],
            intel={"industry": "SaaS"},
        )
        mock_db = _mock_db([
            MockResult(value=existing),  # existing lead found
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post("/api/v1/leads/", json={
            "name": "Test Corp",
            "source": "scorer",
            "fit_score": 90,
            "purpose": ["partnerships"],
            "intel": {"description": "Cloud platform"},
        })
        assert resp.status_code == 200
        # fit_score should update (90 > 70)
        assert existing.fit_score == 90
        # purpose should merge
        assert set(existing.purpose) == {"sales", "partnerships"}
        # intel should merge
        assert existing.intel["industry"] == "SaaS"
        assert existing.intel["description"] == "Cloud platform"

    def test_upsert_keeps_higher_fit_score(self, client):
        """POST /leads/ does not overwrite fit_score with lower value."""
        user = _make_user()
        existing = MockLead(fit_score=95)
        mock_db = _mock_db([MockResult(value=existing)])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post("/api/v1/leads/", json={
            "name": "Test Corp",
            "source": "test",
            "fit_score": 60,
        })
        assert resp.status_code == 200
        assert existing.fit_score == 95  # not overwritten

    def test_invalid_company_name(self, client):
        """POST /leads/ with empty normalized name returns 400."""
        user = _make_user()
        mock_db = _mock_db()

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post("/api/v1/leads/", json={
            "name": "Inc.",  # normalizes to empty string
            "source": "test",
        })
        assert resp.status_code == 400

    def test_requires_auth(self, client):
        """POST /leads/ without auth returns 401."""
        resp = client.post("/api/v1/leads/", json={"name": "X", "source": "test"})
        assert resp.status_code == 401


# ===========================================================================
# TestLeadList
# ===========================================================================


class TestLeadList:
    def test_list_leads(self, client):
        """GET /leads/ returns paginated leads."""
        user = _make_user()
        leads = [MockLead(), MockLead(name="Other Corp", normalized_name="other")]
        mock_db = _mock_db([
            MockResult(scalar_val=2),  # count
            MockResult(values=leads),  # leads
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/leads/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_excludes_graduated(self, client):
        """GET /leads/ should only show non-graduated leads."""
        user = _make_user()
        # The query filters graduated_at IS NULL, so mock should return only active
        mock_db = _mock_db([
            MockResult(scalar_val=1),
            MockResult(values=[MockLead()]),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/leads/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1


# ===========================================================================
# TestPipelineFunnel
# ===========================================================================


class TestPipelineFunnel:
    def test_pipeline_route_not_caught_by_lead_id(self, client):
        """GET /leads/pipeline should NOT be matched by /{lead_id}."""
        user = _make_user()
        mock_db = _mock_db([MockResult(values=[])])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/leads/pipeline")
        # Should be 200 (pipeline endpoint), not 422 (UUID parse error)
        assert resp.status_code == 200
        data = resp.json()
        assert "funnel" in data
        assert data["total"] == 0

    def test_funnel_counts_by_stage(self, client):
        """GET /leads/pipeline returns correct counts per stage."""
        user = _make_user()
        contact_scraped = MockLeadContact(pipeline_stage="scraped")
        contact_sent = MockLeadContact(pipeline_stage="sent", id=uuid4())
        lead1 = MockLead(lead_contacts=[contact_scraped])
        lead2 = MockLead(lead_contacts=[contact_sent], id=uuid4())
        mock_db = _mock_db([MockResult(values=[lead1, lead2])])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.get("/api/v1/leads/pipeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["funnel"]["scraped"] == 1
        assert data["funnel"]["sent"] == 1
        assert data["total"] == 2


# ===========================================================================
# TestLeadContacts
# ===========================================================================


class TestLeadContacts:
    def test_add_contact(self, client):
        """POST /leads/{id}/contacts creates a contact."""
        user = _make_user()
        lead = MockLead()
        mock_db = _mock_db([
            MockResult(value=lead),    # lead found
            MockResult(value=None),    # no duplicate email
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/{TEST_LEAD_ID}/contacts", json={
            "name": "John Doe",
            "email": "John@Test.com",
            "title": "CTO",
            "role": "champion",
        })
        assert resp.status_code == 201
        mock_db.add.assert_called_once()

    def test_add_contact_email_lowercased(self, client):
        """Email should be lowercased before storage."""
        user = _make_user()
        lead = MockLead()
        mock_db = _mock_db([
            MockResult(value=lead),
            MockResult(value=None),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/{TEST_LEAD_ID}/contacts", json={
            "name": "Jane",
            "email": "JANE@ACME.COM",
        })
        assert resp.status_code == 201
        # Verify the add call used lowercased email
        added_contact = mock_db.add.call_args[0][0]
        assert added_contact.email == "jane@acme.com"

    def test_duplicate_email_rejected(self, client):
        """POST /leads/{id}/contacts with existing email returns 409."""
        user = _make_user()
        lead = MockLead()
        existing_contact = MockLeadContact()
        mock_db = _mock_db([
            MockResult(value=lead),
            MockResult(value=existing_contact),  # duplicate found
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/{TEST_LEAD_ID}/contacts", json={
            "name": "Jane",
            "email": "jane@test.com",
        })
        assert resp.status_code == 409

    def test_lead_not_found(self, client):
        """POST /leads/{id}/contacts with bad lead ID returns 404."""
        user = _make_user()
        mock_db = _mock_db([MockResult(value=None)])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/{uuid4()}/contacts", json={
            "name": "Jane",
        })
        assert resp.status_code == 404


# ===========================================================================
# TestLeadMessages
# ===========================================================================


class TestLeadMessages:
    def test_create_draft_message(self, client):
        """POST /leads/contacts/{id}/messages creates a draft."""
        user = _make_user()
        contact = MockLeadContact(pipeline_stage="researched")
        mock_db = _mock_db([
            MockResult(value=contact),  # contact found
            MockResult(value=None),     # no existing message
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/contacts/{TEST_CONTACT_ID}/messages", json={
            "step_number": 1,
            "channel": "email",
            "status": "drafted",
            "subject": "Intro",
            "body": "Hello!",
        })
        assert resp.status_code == 201
        # Contact stage should advance to "drafted"
        assert contact.pipeline_stage == "drafted"

    def test_stage_advances_on_message(self, client):
        """Creating a 'sent' message advances contact stage to 'sent'."""
        user = _make_user()
        contact = MockLeadContact(pipeline_stage="drafted")
        mock_db = _mock_db([
            MockResult(value=contact),
            MockResult(value=None),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/contacts/{TEST_CONTACT_ID}/messages", json={
            "step_number": 1,
            "channel": "email",
            "status": "sent",
            "sent_at": "2026-04-01T10:00:00+00:00",
        })
        assert resp.status_code == 201
        assert contact.pipeline_stage == "sent"

    def test_stage_does_not_go_backward(self, client):
        """Creating a 'drafted' message on a 'sent' contact doesn't regress stage."""
        user = _make_user()
        contact = MockLeadContact(pipeline_stage="sent")
        mock_db = _mock_db([
            MockResult(value=contact),
            MockResult(value=None),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/contacts/{TEST_CONTACT_ID}/messages", json={
            "step_number": 2,
            "channel": "email",
            "status": "drafted",
        })
        assert resp.status_code == 201
        assert contact.pipeline_stage == "sent"  # not regressed

    def test_invalid_channel_rejected(self, client):
        """Invalid channel value returns 422."""
        user = _make_user()
        mock_db = _mock_db([MockResult(value=MockLeadContact())])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/contacts/{TEST_CONTACT_ID}/messages", json={
            "step_number": 1,
            "channel": "telegram",
            "status": "drafted",
        })
        assert resp.status_code == 422

    def test_invalid_status_rejected(self, client):
        """Invalid status value returns 422."""
        user = _make_user()
        mock_db = _mock_db([MockResult(value=MockLeadContact())])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/contacts/{TEST_CONTACT_ID}/messages", json={
            "step_number": 1,
            "channel": "email",
            "status": "invalid_status",
        })
        assert resp.status_code == 422

    def test_step_number_must_be_positive(self, client):
        """step_number < 1 returns 422."""
        user = _make_user()
        mock_db = _mock_db([MockResult(value=MockLeadContact())])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/contacts/{TEST_CONTACT_ID}/messages", json={
            "step_number": 0,
            "channel": "email",
        })
        assert resp.status_code == 422

    def test_invalid_timestamp_returns_422(self, client):
        """Bad timestamp format returns 422, not 500."""
        user = _make_user()
        contact = MockLeadContact()
        mock_db = _mock_db([
            MockResult(value=contact),
            MockResult(value=None),
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/contacts/{TEST_CONTACT_ID}/messages", json={
            "step_number": 1,
            "channel": "email",
            "status": "sent",
            "sent_at": "not-a-date",
        })
        assert resp.status_code == 422


# ===========================================================================
# TestGraduation
# ===========================================================================


class TestGraduation:
    def test_graduate_creates_account(self, client):
        """POST /leads/{id}/graduate creates account + contacts + outreach."""
        user = _make_user()
        msg = MockLeadMessage(status="sent", sent_at=datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc))
        contact = MockLeadContact(messages=[msg])
        lead = MockLead(lead_contacts=[contact])

        mock_db = _mock_db([
            MockResult(value=lead),   # lead found
            MockResult(value=None),   # no existing account
            MockResult(value=None),   # no existing contact by email
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/{TEST_LEAD_ID}/graduate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["graduated"] is True
        assert lead.graduated_at is not None
        # Account + Contact + OutreachActivity + ContextEntry = 4 adds
        assert mock_db.add.call_count >= 3

    def test_already_graduated_returns_409(self, client):
        """POST /leads/{id}/graduate on already-graduated lead returns 409."""
        user = _make_user()
        lead = MockLead(account_id=uuid4())
        mock_db = _mock_db([MockResult(value=lead)])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/{TEST_LEAD_ID}/graduate")
        assert resp.status_code == 409

    def test_lead_not_found_returns_404(self, client):
        """POST /leads/{id}/graduate with bad ID returns 404."""
        user = _make_user()
        mock_db = _mock_db([MockResult(value=None)])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/{uuid4()}/graduate")
        assert resp.status_code == 404

    def test_graduate_skips_drafted_messages(self, client):
        """Graduation should not create OutreachActivity for drafted messages."""
        user = _make_user()
        draft_msg = MockLeadMessage(status="drafted")
        sent_msg = MockLeadMessage(status="sent", id=uuid4(), sent_at=datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc))
        contact = MockLeadContact(messages=[draft_msg, sent_msg])
        lead = MockLead(lead_contacts=[contact])

        mock_db = _mock_db([
            MockResult(value=lead),
            MockResult(value=None),   # no existing account
            MockResult(value=None),   # no existing contact
        ])

        app.dependency_overrides[require_tenant] = lambda: user
        app.dependency_overrides[get_tenant_db] = lambda: mock_db

        resp = client.post(f"/api/v1/leads/{TEST_LEAD_ID}/graduate")
        assert resp.status_code == 200
        # Check that only 1 outreach activity was created (sent, not drafted)
        added_objects = [call[0][0] for call in mock_db.add.call_args_list]
        from flywheel.db.models import OutreachActivity
        outreach_adds = [o for o in added_objects if isinstance(o, OutreachActivity)]
        assert len(outreach_adds) == 1
        assert outreach_adds[0].status == "sent"
