"""Phase 150.1 Plan 02 — zero-Anthropic regression test.

This is the centerpiece invariant of Phase 150.1: for every broker
/extract/* and /save/* integration flow, the backend must make ZERO
AsyncAnthropic instantiations.

PATCH STRATEGY:
---------------
Two shapes of Anthropic binding live in the broker engines today:

1. PACKAGE-LEVEL:   contract_analyzer.py + quote_extractor.py do
                    ``import anthropic`` then call
                    ``anthropic.AsyncAnthropic(api_key=...)``. A patch at
                    ``flywheel.engines.{module}.anthropic.AsyncAnthropic``
                    rebinds the name because the attribute lookup runs at
                    call time.

2. MODULE-LOCAL:    solicitation_drafter.py + recommendation_drafter.py do
                    ``from anthropic import AsyncAnthropic`` at module
                    import time, then call ``AsyncAnthropic()`` (no api_key
                    kwarg — the "env-var leak" shape). A patch at
                    ``anthropic.AsyncAnthropic`` alone does NOT rebind the
                    already-imported ``AsyncAnthropic`` name in those
                    modules. Tests MUST patch the module-local symbol
                    ``flywheel.engines.{module}.AsyncAnthropic`` directly.

This test fixture patches ALL FOUR module-local paths with a sentinel
MagicMock whose instantiation raises AssertionError — so any future
refactor that accidentally reintroduces a server-side LLM call FAILS LOUD
at this test.

Run: ``cd backend && PYTHONPATH=src ./.venv/bin/pytest \
        src/tests/test_broker_zero_anthropic.py -v``
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from flywheel.api.broker._enforcement import SubsidyDecision, require_subsidy_decision
from flywheel.api.deps import get_tenant_db, require_module, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.main import app


# ---------------------------------------------------------------------------
# Test identifiers
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid4()
TEST_TENANT_ID = uuid4()
TEST_PROJECT_ID = uuid4()
TEST_QUOTE_ID = uuid4()
TEST_CARRIER_ID = uuid4()
TEST_FILE_ID = uuid4()


def _make_user(tenant_id: UUID = TEST_TENANT_ID) -> TokenPayload:
    return TokenPayload(
        sub=TEST_USER_ID,
        email="test@example.com",
        is_anonymous=False,
        app_metadata={"tenant_id": str(tenant_id), "role": "admin"},
    )


# ---------------------------------------------------------------------------
# Sentinel builder — raises loudly on instantiation
# ---------------------------------------------------------------------------


def _make_sentinel(site_name: str) -> MagicMock:
    """Return a MagicMock that raises AssertionError when called."""

    def _fail(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(
            f"AsyncAnthropic was instantiated at site={site_name} — "
            "CC-as-Brain invariant violated. Pattern 3a requires zero "
            "backend LLM calls during broker flows."
        )

    return MagicMock(side_effect=_fail)


# ---------------------------------------------------------------------------
# DB + dependency overrides — minimal mocks to exercise each endpoint path
# ---------------------------------------------------------------------------


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
        self.name = "Test Project"
        self.project_type = "construction"
        self.description = "test"
        self.contract_value = 1000000
        self.currency = "MXN"
        self.location = "MX"
        self.country_code = "MX"
        self.line_of_business = "construction"
        self.language = "es"
        self.status = "analyzing"
        self.client_id = None
        self.metadata_ = {"documents": []}
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
# Fixture: patch AsyncAnthropic at FIVE module-local paths + sentinel DB
# ---------------------------------------------------------------------------


@pytest.fixture
def zero_anthropic_guards(monkeypatch):
    """Patch AsyncAnthropic bindings at all broker-engine module paths.

    Yields the sentinel dict so tests can assert call_count == 0 per site.
    """
    sentinels = {
        "contract_analyzer_package": _make_sentinel("contract_analyzer.anthropic.AsyncAnthropic"),
        "quote_extractor_package": _make_sentinel("quote_extractor.anthropic.AsyncAnthropic"),
        "solicitation_drafter_module_local": _make_sentinel(
            "solicitation_drafter.AsyncAnthropic (module-local from-import)"
        ),
        "recommendation_drafter_module_local": _make_sentinel(
            "recommendation_drafter.AsyncAnthropic (module-local from-import)"
        ),
        "package_level_belt_and_suspenders": _make_sentinel("anthropic.AsyncAnthropic"),
    }

    # PACKAGE-LEVEL bindings (contract_analyzer + quote_extractor do
    # `import anthropic` then call anthropic.AsyncAnthropic(...) — patching
    # the .anthropic attribute on each module works because attribute
    # lookup happens at call time).
    monkeypatch.setattr(
        "flywheel.engines.contract_analyzer.anthropic.AsyncAnthropic",
        sentinels["contract_analyzer_package"],
    )
    monkeypatch.setattr(
        "flywheel.engines.quote_extractor.anthropic.AsyncAnthropic",
        sentinels["quote_extractor_package"],
    )

    # MODULE-LOCAL bindings (solicitation_drafter + recommendation_drafter
    # do `from anthropic import AsyncAnthropic` at module import time;
    # patching the package-level `anthropic.AsyncAnthropic` does NOT rebind
    # these already-imported module-local names).
    monkeypatch.setattr(
        "flywheel.engines.solicitation_drafter.AsyncAnthropic",
        sentinels["solicitation_drafter_module_local"],
    )
    monkeypatch.setattr(
        "flywheel.engines.recommendation_drafter.AsyncAnthropic",
        sentinels["recommendation_drafter_module_local"],
    )

    # Belt-and-suspenders: also patch the package-level anthropic module so
    # any future call site that does `anthropic.AsyncAnthropic(...)` gets
    # blocked too.
    monkeypatch.setattr(
        "anthropic.AsyncAnthropic",
        sentinels["package_level_belt_and_suspenders"],
    )

    yield sentinels


@pytest.fixture
def override_app(zero_anthropic_guards):
    """Override app deps with mocks so endpoints can execute without real DB."""
    mock_user = _make_user()

    async def _override_require_tenant() -> TokenPayload:
        return mock_user

    async def _override_require_module() -> TokenPayload:
        return mock_user

    # Build a stateful mock DB that returns appropriate rows for each endpoint.
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()

    project = _MockProject()
    quote = _MockQuote()
    carrier = _MockCarrier()

    # Return appropriate mock row based on the first filter clause.
    call_count = {"n": 0}

    async def _execute(stmt: Any, *args: Any, **kwargs: Any) -> _Result:
        call_count["n"] += 1
        # SQLAlchemy statements render as `SELECT broker_projects.id, ...
        # FROM broker_projects WHERE ...` — match on the table name in the
        # FROM clause specifically.
        stmt_str = str(stmt).lower()
        # Look at the FROM clause to identify the primary table.
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

    # Override require_module factory by replacing the returned dep at
    # each broker endpoint — easier path is to directly override the
    # factory output for "broker" that's already wired into app.
    from flywheel.api.deps import require_module as _real_require_module

    # Replace dependency_overrides entries so FastAPI uses our overrides.
    app.dependency_overrides[require_tenant] = _override_require_tenant
    app.dependency_overrides[get_tenant_db] = _override_get_tenant_db

    # require_module returns a NEW function each call; we have to override
    # each one. Iterate app.routes and override any Depends(require_module("broker")).
    # Simpler: just short-circuit require_module by inspecting routes.
    for route in app.routes:
        if not hasattr(route, "dependant"):
            continue
        for dep in route.dependant.dependencies:
            if dep.call is not None and getattr(dep.call, "__name__", "") == "_check_module":
                app.dependency_overrides[dep.call] = _override_require_module

    yield app

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: common request headers — caller-identified via X-Flywheel-Skill
# ---------------------------------------------------------------------------


def _headers(skill: str = "broker-parse-contract") -> dict[str, str]:
    return {"x-flywheel-skill": skill}


def _byok_body(extra: dict[str, Any]) -> dict[str, Any]:
    """Build a request body carrying a BYOK api_key so the subsidy allowlist
    gate passes (non-allowlisted skill + BYOK = Cell 4 → allowed).
    """
    return {"api_key": "sk-ant-BYOK-TEST", **extra}


def _assert_zero_anthropic(sentinels: dict[str, MagicMock]) -> None:
    for name, sentinel in sentinels.items():
        assert sentinel.call_count == 0, (
            f"AsyncAnthropic sentinel at {name} was called "
            f"{sentinel.call_count} time(s) — CC-as-Brain invariant violated."
        )


# ---------------------------------------------------------------------------
# Tests — one per extract/save pair, 10 total + 1 env-var-leak smoke
# ---------------------------------------------------------------------------


class TestBrokerZeroAnthropicInvariant:
    """Zero AsyncAnthropic instantiation across every broker extract/save flow."""

    def test_extract_contract_analysis_makes_zero_llm_calls(
        self, override_app, zero_anthropic_guards
    ):
        client = TestClient(override_app)
        r = client.post(
            "/api/v1/broker/extract/contract-analysis",
            json=_byok_body({"project_id": str(TEST_PROJECT_ID)}),
            headers=_headers(),
        )
        # Endpoint may 200 (empty docs) or 404 (project lookup path); what
        # matters is zero LLM calls on the happy path.
        assert r.status_code in (200, 404), r.text
        _assert_zero_anthropic(zero_anthropic_guards)

    def test_save_contract_analysis_makes_zero_llm_calls(
        self, override_app, zero_anthropic_guards
    ):
        client = TestClient(override_app)
        r = client.post(
            "/api/v1/broker/save/contract-analysis",
            json=_byok_body(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "tool_schema_version": "1.0",
                    "coverages": [],
                    "contract_language": "es",
                    "contract_summary": "",
                    "total_coverages_found": 0,
                    "primary_contract_filename": "",
                    "misrouted_documents": [],
                }
            ),
            headers=_headers(),
        )
        assert r.status_code in (200, 404, 500), r.text
        _assert_zero_anthropic(zero_anthropic_guards)

    def test_extract_policy_extraction_makes_zero_llm_calls(
        self, override_app, zero_anthropic_guards
    ):
        client = TestClient(override_app)
        r = client.post(
            "/api/v1/broker/extract/policy-extraction",
            json=_byok_body({"project_id": str(TEST_PROJECT_ID)}),
            headers=_headers(),
        )
        assert r.status_code in (200, 404), r.text
        _assert_zero_anthropic(zero_anthropic_guards)

    def test_save_policy_extraction_makes_zero_llm_calls(
        self, override_app, zero_anthropic_guards
    ):
        client = TestClient(override_app)
        r = client.post(
            "/api/v1/broker/save/policy-extraction",
            json=_byok_body(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "tool_schema_version": "1.0",
                    "documents": [],
                    "policies": [],
                    "total_policies_found": 0,
                }
            ),
            headers=_headers(),
        )
        assert r.status_code in (200, 404, 500), r.text
        _assert_zero_anthropic(zero_anthropic_guards)

    def test_extract_quote_extraction_makes_zero_llm_calls(
        self, override_app, zero_anthropic_guards
    ):
        client = TestClient(override_app)
        r = client.post(
            "/api/v1/broker/extract/quote-extraction",
            json=_byok_body({"quote_id": str(TEST_QUOTE_ID)}),
            headers=_headers(),
        )
        assert r.status_code in (200, 404, 422), r.text
        _assert_zero_anthropic(zero_anthropic_guards)

    def test_save_quote_extraction_makes_zero_llm_calls(
        self, override_app, zero_anthropic_guards
    ):
        client = TestClient(override_app)
        r = client.post(
            "/api/v1/broker/save/quote-extraction",
            json=_byok_body(
                {
                    "quote_id": str(TEST_QUOTE_ID),
                    "tool_schema_version": "1.0",
                    "carrier_name": "TestCarrier",
                    "line_items": [],
                }
            ),
            headers=_headers(),
        )
        assert r.status_code in (200, 404, 500), r.text
        _assert_zero_anthropic(zero_anthropic_guards)

    def test_extract_solicitation_draft_makes_zero_llm_calls(
        self, override_app, zero_anthropic_guards
    ):
        client = TestClient(override_app)
        r = client.post(
            "/api/v1/broker/extract/solicitation-draft",
            json=_byok_body(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "carrier_config_id": str(TEST_CARRIER_ID),
                }
            ),
            headers=_headers(),
        )
        assert r.status_code in (200, 404), r.text
        _assert_zero_anthropic(zero_anthropic_guards)

    def test_save_solicitation_draft_makes_zero_llm_calls(
        self, override_app, zero_anthropic_guards
    ):
        client = TestClient(override_app)
        r = client.post(
            "/api/v1/broker/save/solicitation-draft",
            json=_byok_body(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "carrier_config_id": str(TEST_CARRIER_ID),
                    "tool_schema_version": "1.0",
                    "subject": "Quote request",
                    "body_html": "<p>Please quote.</p>",
                }
            ),
            headers=_headers(),
        )
        assert r.status_code in (200, 404, 500), r.text
        _assert_zero_anthropic(zero_anthropic_guards)

    def test_extract_recommendation_draft_makes_zero_llm_calls(
        self, override_app, zero_anthropic_guards
    ):
        client = TestClient(override_app)
        r = client.post(
            "/api/v1/broker/extract/recommendation-draft",
            json=_byok_body({"project_id": str(TEST_PROJECT_ID)}),
            headers=_headers(),
        )
        assert r.status_code in (200, 404), r.text
        _assert_zero_anthropic(zero_anthropic_guards)

    def test_save_recommendation_draft_makes_zero_llm_calls(
        self, override_app, zero_anthropic_guards
    ):
        client = TestClient(override_app)
        r = client.post(
            "/api/v1/broker/save/recommendation-draft",
            json=_byok_body(
                {
                    "project_id": str(TEST_PROJECT_ID),
                    "tool_schema_version": "1.0",
                    "subject": "Recommendation",
                    "body_html": "<p>We recommend Acme.</p>",
                }
            ),
            headers=_headers(),
        )
        assert r.status_code in (200, 404, 500), r.text
        _assert_zero_anthropic(zero_anthropic_guards)

    def test_env_var_leak_shapes_blocked(self, override_app, zero_anthropic_guards):
        """Even with ANTHROPIC_API_KEY set in env, solicitation + recommendation
        paths must not silently construct AsyncAnthropic() and leak the
        subsidy key.

        This is the explicit regression for the two hidden env-var leak
        shapes at solicitation_drafter.py:135 and recommendation_drafter.py:153,
        both of which use `from anthropic import AsyncAnthropic` module-local
        bindings. A test that only patches `anthropic.AsyncAnthropic` would
        give a false pass — this fixture patches the module-local paths.
        """
        client = TestClient(override_app)

        old_env = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-FAKE-SHOULD-NEVER-BE-USED"
        try:
            r1 = client.post(
                "/api/v1/broker/extract/solicitation-draft",
                json=_byok_body(
                    {
                        "project_id": str(TEST_PROJECT_ID),
                        "carrier_config_id": str(TEST_CARRIER_ID),
                    }
                ),
                headers=_headers(),
            )
            r2 = client.post(
                "/api/v1/broker/extract/recommendation-draft",
                json=_byok_body({"project_id": str(TEST_PROJECT_ID)}),
                headers=_headers(),
            )
            assert r1.status_code < 500, r1.text
            assert r2.status_code < 500, r2.text

            # Zero LLM calls across all 5 sentinels despite env-var present
            _assert_zero_anthropic(zero_anthropic_guards)
        finally:
            if old_env is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = old_env
