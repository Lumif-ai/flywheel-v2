"""Phase 150.1 Plan 02 — functional/contract tests for the 5 extract/save pairs.

Covers:
- Extract response shape (prompt, tool_schema, documents, metadata)
- tool_schema_version mismatch rejection (400) on every save
- Enforcement on extract (no X-Flywheel-Skill + no BYOK → 403)
- Enforcement on save (no X-Flywheel-Skill + no BYOK → 403) — **Blocker-2**
- BYOK allowlist bypass (body api_key → Cell 4 of truth table)
- tool_schema metadata version field ("1.0")

Run: ``cd backend && PYTHONPATH=src ./.venv/bin/pytest \
        src/tests/test_broker_extract_save_endpoints.py -v``
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.main import app

TEST_USER_ID = uuid4()
TEST_TENANT_ID = uuid4()
TEST_PROJECT_ID = uuid4()
TEST_QUOTE_ID = uuid4()
TEST_CARRIER_ID = uuid4()


def _make_user() -> TokenPayload:
    return TokenPayload(
        sub=TEST_USER_ID,
        email="test@example.com",
        is_anonymous=False,
        app_metadata={"tenant_id": str(TEST_TENANT_ID), "role": "admin"},
    )


class _Result:
    def __init__(self, value: Any = None, values: list[Any] | None = None):
        self._value = value
        self._values = values or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        return self._value

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[Any]:
        return self._values

    def __iter__(self):
        return iter(self._values)


class _MockProject:
    def __init__(self) -> None:
        self.id = TEST_PROJECT_ID
        self.tenant_id = TEST_TENANT_ID
        self.name = "Functional Test Project"
        self.project_type = "construction"
        self.description = "test"
        self.contract_value = 1_000_000
        self.currency = "MXN"
        self.location = "MX"
        self.country_code = "MX"
        self.line_of_business = "construction"
        self.language = "es"
        self.status = "analyzing"
        self.client_id = None
        self.metadata_: dict = {"documents": []}
        self.deleted_at = None
        self.source_document_id = None
        self.analysis_status = "running"
        self.analysis_completed_at = None


class _MockQuote:
    def __init__(self) -> None:
        self.id = TEST_QUOTE_ID
        self.tenant_id = TEST_TENANT_ID
        self.broker_project_id = TEST_PROJECT_ID
        self.carrier_config_id = TEST_CARRIER_ID
        self.source_document_id = None
        self.source_email_id = None
        self.source_hash = None
        self.source = "upload"
        self.import_source = None
        self.carrier_name = "TestCarrier"
        self.carrier_type = "insurer"
        self.premium = None
        self.deductible = None
        self.limit_amount = None
        self.status = "extracted"
        self.has_critical_exclusion = False
        self.critical_exclusion_detail = None


class _MockCarrier:
    def __init__(self) -> None:
        self.id = TEST_CARRIER_ID
        self.tenant_id = TEST_TENANT_ID
        self.carrier_name = "TestCarrier"
        self.carrier_type = "insurer"
        self.submission_method = "email"
        self.portal_url = None
        self.coverage_types = ["general_liability"]
        self.regions = ["MX"]
        self.is_active = True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def override_app():
    """Override dependencies for endpoint functional tests.

    Unlike test_broker_zero_anthropic.py, this fixture does NOT patch
    AsyncAnthropic — these tests exercise shape/validation/enforcement.
    """
    mock_user = _make_user()
    project = _MockProject()
    quote = _MockQuote()
    carrier = _MockCarrier()

    async def _override_require_tenant() -> TokenPayload:
        return mock_user

    async def _override_require_module() -> TokenPayload:
        return mock_user

    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()

    async def _execute(stmt: Any, *args: Any, **kwargs: Any) -> _Result:
        stmt_str = str(stmt).lower()
        if " from broker_projects" in stmt_str or "broker_projects." in stmt_str:
            return _Result(value=project, values=[project])
        if " from carrier_quotes" in stmt_str or "carrier_quotes." in stmt_str:
            return _Result(value=quote, values=[quote])
        if " from carrier_configs" in stmt_str or "carrier_configs." in stmt_str:
            return _Result(value=carrier, values=[carrier])
        if " from carrier_contacts" in stmt_str or "carrier_contacts." in stmt_str:
            return _Result(values=[])
        if " from uploaded_files" in stmt_str or "uploaded_files." in stmt_str:
            return _Result(values=[], value=None)
        if " from project_coverages" in stmt_str or "project_coverages." in stmt_str:
            return _Result(values=[])
        if " from coverage_types" in stmt_str or "coverage_types." in stmt_str:
            return _Result(values=[])
        if " from tenants" in stmt_str or "tenants." in stmt_str:
            tenant_mock = MagicMock()
            tenant_mock.id = TEST_TENANT_ID
            tenant_mock.settings = {"modules": ["broker"]}
            return _Result(value=tenant_mock)
        return _Result()

    db.execute = AsyncMock(side_effect=_execute)

    async def _override_get_tenant_db():
        yield db

    app.dependency_overrides[require_tenant] = _override_require_tenant
    app.dependency_overrides[get_tenant_db] = _override_get_tenant_db

    for route in app.routes:
        if not hasattr(route, "dependant"):
            continue
        for dep in route.dependant.dependencies:
            if dep.call is not None and getattr(dep.call, "__name__", "") == "_check_module":
                app.dependency_overrides[dep.call] = _override_require_module

    yield app

    app.dependency_overrides.clear()


def _headers_byok() -> dict[str, str]:
    """Headers with X-Flywheel-Skill — non-allowlisted skill; BYOK in body."""
    return {"x-flywheel-skill": "broker-parse-contract"}


def _headers_no_skill() -> dict[str, str]:
    """Headers with NO caller identification — forces 403 unless BYOK in body."""
    return {}


def _byok(extra: dict[str, Any]) -> dict[str, Any]:
    return {"api_key": "sk-ant-BYOK-TEST", **extra}


# ===========================================================================
# Contract Analysis
# ===========================================================================


class TestContractAnalysis:
    def test_extract_returns_correct_shape(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/extract/contract-analysis",
            json=_byok({"project_id": str(TEST_PROJECT_ID)}),
            headers=_headers_byok(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"prompt", "tool_schema", "documents", "metadata"}
        assert body["tool_schema"]["name"] == "extract_coverage_requirements"
        assert "input_schema" in body["tool_schema"]
        assert body["metadata"]["tool_schema_version"] == "1.0"
        assert "project_id" in body["metadata"]
        assert body["metadata"]["currency"] == "MXN"
        assert isinstance(body["documents"], list)

    def test_save_rejects_schema_version_mismatch(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/contract-analysis",
            json=_byok(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "tool_schema_version": "9.9.9",  # bad version
                    "coverages": [],
                    "total_coverages_found": 0,
                    "primary_contract_filename": "",
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 400, r.text
        # Global error envelope wraps detail under `message` (errors.py)
        assert "tool_schema_version mismatch" in r.json()["message"]

    def test_save_persists_with_valid_body(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/contract-analysis",
            json=_byok(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "tool_schema_version": "1.0",
                    "coverages": [],
                    "contract_language": "es",
                    "contract_summary": "test",
                    "total_coverages_found": 0,
                    "primary_contract_filename": "",
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "completed"
        assert body["coverages_saved"] == 0

    def test_extract_enforcement_403_without_byok_or_skill(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/extract/contract-analysis",
            json={"project_id": str(TEST_PROJECT_ID)},
            headers=_headers_no_skill(),
        )
        assert r.status_code == 403, r.text
        # Global error envelope wraps dict-detail as stringified dict in message.
        assert "subsidy_not_allowed" in r.json()["message"]

    def test_save_enforcement_blocker2_403_without_byok_or_skill(self, override_app):
        """Blocker-2: save endpoint MUST enforce require_subsidy_decision."""
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/contract-analysis",
            json={
                "project_id": str(TEST_PROJECT_ID),
                "tool_schema_version": "1.0",
                "coverages": [],
                "total_coverages_found": 0,
            },
            headers=_headers_no_skill(),
        )
        assert r.status_code == 403, r.text
        assert "subsidy_not_allowed" in r.json()["message"]


# ===========================================================================
# Policy Extraction
# ===========================================================================


class TestPolicyExtraction:
    def test_extract_returns_correct_shape(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/extract/policy-extraction",
            json=_byok({"project_id": str(TEST_PROJECT_ID)}),
            headers=_headers_byok(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"prompt", "tool_schema", "documents", "metadata"}
        assert body["tool_schema"]["name"] == "extract_current_policies"
        assert body["metadata"]["tool_schema_version"] == "1.0"

    def test_save_rejects_schema_version_mismatch(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/policy-extraction",
            json=_byok(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "tool_schema_version": "2.0",
                    "documents": [],
                    "policies": [],
                    "total_policies_found": 0,
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 400, r.text

    def test_save_persists_with_valid_body(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/policy-extraction",
            json=_byok(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "tool_schema_version": "1.0",
                    "documents": [],
                    "policies": [],
                    "total_policies_found": 0,
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "completed"

    def test_extract_enforcement_403_without_byok_or_skill(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/extract/policy-extraction",
            json={"project_id": str(TEST_PROJECT_ID)},
            headers=_headers_no_skill(),
        )
        assert r.status_code == 403

    def test_save_enforcement_blocker2_403_without_byok_or_skill(self, override_app):
        """Blocker-2: save endpoint MUST enforce require_subsidy_decision."""
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/policy-extraction",
            json={
                "project_id": str(TEST_PROJECT_ID),
                "tool_schema_version": "1.0",
                "documents": [],
                "policies": [],
                "total_policies_found": 0,
            },
            headers=_headers_no_skill(),
        )
        assert r.status_code == 403


# ===========================================================================
# Quote Extraction
# ===========================================================================


class TestQuoteExtraction:
    def test_extract_returns_correct_shape(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/extract/quote-extraction",
            json=_byok({"quote_id": str(TEST_QUOTE_ID)}),
            headers=_headers_byok(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"prompt", "tool_schema", "documents", "metadata"}
        assert body["tool_schema"]["name"] == "extract_quote_terms"
        assert body["metadata"]["tool_schema_version"] == "1.0"
        assert "quote_id" in body["metadata"]

    def test_save_rejects_schema_version_mismatch(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/quote-extraction",
            json=_byok(
                {
                    "quote_id": str(TEST_QUOTE_ID),
                    "tool_schema_version": "9.9.9",
                    "carrier_name": "Acme",
                    "line_items": [],
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 400

    def test_save_persists_with_valid_body(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/quote-extraction",
            json=_byok(
                {
                    "quote_id": str(TEST_QUOTE_ID),
                    "tool_schema_version": "1.0",
                    "carrier_name": "Acme",
                    "line_items": [],
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "extracted"

    def test_extract_enforcement_403_without_byok_or_skill(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/extract/quote-extraction",
            json={"quote_id": str(TEST_QUOTE_ID)},
            headers=_headers_no_skill(),
        )
        assert r.status_code == 403

    def test_save_enforcement_blocker2_403_without_byok_or_skill(self, override_app):
        """Blocker-2: save endpoint MUST enforce require_subsidy_decision."""
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/quote-extraction",
            json={
                "quote_id": str(TEST_QUOTE_ID),
                "tool_schema_version": "1.0",
                "carrier_name": "Acme",
                "line_items": [],
            },
            headers=_headers_no_skill(),
        )
        assert r.status_code == 403


# ===========================================================================
# Solicitation Draft
# ===========================================================================


class TestSolicitationDraft:
    def test_extract_returns_correct_shape(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/extract/solicitation-draft",
            json=_byok(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "carrier_config_id": str(TEST_CARRIER_ID),
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"prompt", "tool_schema", "documents", "metadata"}
        assert body["tool_schema"]["name"] == "draft_solicitation_email"
        assert body["metadata"]["tool_schema_version"] == "1.0"
        assert body["metadata"]["carrier_name"] == "TestCarrier"

    def test_save_rejects_schema_version_mismatch(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/solicitation-draft",
            json=_byok(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "carrier_config_id": str(TEST_CARRIER_ID),
                    "tool_schema_version": "9.9.9",
                    "subject": "Q",
                    "body_html": "<p>t</p>",
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 400

    def test_save_persists_with_valid_body(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/solicitation-draft",
            json=_byok(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "carrier_config_id": str(TEST_CARRIER_ID),
                    "tool_schema_version": "1.0",
                    "subject": "Quote request",
                    "body_html": "<p>Please quote.</p>",
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "solicitation_draft_id" in body

    def test_extract_enforcement_403_without_byok_or_skill(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/extract/solicitation-draft",
            json={
                "project_id": str(TEST_PROJECT_ID),
                "carrier_config_id": str(TEST_CARRIER_ID),
            },
            headers=_headers_no_skill(),
        )
        assert r.status_code == 403

    def test_save_enforcement_blocker2_403_without_byok_or_skill(self, override_app):
        """Blocker-2: save endpoint MUST enforce require_subsidy_decision."""
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/solicitation-draft",
            json={
                "project_id": str(TEST_PROJECT_ID),
                "carrier_config_id": str(TEST_CARRIER_ID),
                "tool_schema_version": "1.0",
                "subject": "X",
                "body_html": "<p>y</p>",
            },
            headers=_headers_no_skill(),
        )
        assert r.status_code == 403


# ===========================================================================
# Recommendation Draft
# ===========================================================================


class TestRecommendationDraft:
    def test_extract_returns_correct_shape(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/extract/recommendation-draft",
            json=_byok({"project_id": str(TEST_PROJECT_ID)}),
            headers=_headers_byok(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"prompt", "tool_schema", "documents", "metadata"}
        assert body["tool_schema"]["name"] == "draft_recommendation_email"
        assert body["metadata"]["tool_schema_version"] == "1.0"
        assert "num_quotes" in body["metadata"]

    def test_save_rejects_schema_version_mismatch(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/recommendation-draft",
            json=_byok(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "tool_schema_version": "9.9.9",
                    "subject": "R",
                    "body_html": "<p>t</p>",
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 400

    def test_save_persists_with_valid_body(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/recommendation-draft",
            json=_byok(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "tool_schema_version": "1.0",
                    "subject": "Recommendation",
                    "body_html": "<p>We recommend Acme.</p>",
                    "recipient_email": "client@example.com",
                }
            ),
            headers=_headers_byok(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "recommendation_id" in body
        assert body["subject"] == "Recommendation"

    def test_extract_enforcement_403_without_byok_or_skill(self, override_app):
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/extract/recommendation-draft",
            json={"project_id": str(TEST_PROJECT_ID)},
            headers=_headers_no_skill(),
        )
        assert r.status_code == 403

    def test_save_enforcement_blocker2_403_without_byok_or_skill(self, override_app):
        """Blocker-2: save endpoint MUST enforce require_subsidy_decision."""
        c = TestClient(override_app)
        r = c.post(
            "/api/v1/broker/save/recommendation-draft",
            json={
                "project_id": str(TEST_PROJECT_ID),
                "tool_schema_version": "1.0",
                "subject": "X",
                "body_html": "<p>y</p>",
            },
            headers=_headers_no_skill(),
        )
        assert r.status_code == 403


# ===========================================================================
# OpenAPI schema assertions (cross-op)
# ===========================================================================


class TestOpenAPISchema:
    def test_ten_endpoints_registered(self):
        paths = set(app.openapi()["paths"].keys())
        expected_extract = {
            "contract-analysis",
            "policy-extraction",
            "quote-extraction",
            "solicitation-draft",
            "recommendation-draft",
        }
        for op in expected_extract:
            assert f"/api/v1/broker/extract/{op}" in paths
            assert f"/api/v1/broker/save/{op}" in paths

    def test_no_asyncanthropic_in_broker_api_files(self):
        """Sanity guard: api/broker/*.py files never import AsyncAnthropic."""
        import pathlib

        broker_dir = pathlib.Path(__file__).parent.parent / "flywheel" / "api" / "broker"
        offenders: list[str] = []
        for py in broker_dir.glob("*.py"):
            if py.name == "_enforcement.py":
                continue  # docstring mentions it; not a leak
            text = py.read_text()
            # Skip comment/docstring mentions (they're prefixed with # or inside
            # triple quotes) — only flag import/construct patterns.
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "AsyncAnthropic(" in stripped or "from anthropic import" in stripped:
                    offenders.append(f"{py.name}: {stripped}")
        assert not offenders, (
            f"api/broker/*.py must never import/construct AsyncAnthropic. "
            f"Offenders: {offenders}"
        )
