# Testing Patterns

**Analysis Date:** 2026-03-26

## Test Framework

**Runner:**
- pytest `>=8.0` with `pytest-asyncio>=0.24`
- Config: `pyproject.toml` `[tool.pytest.ini_options]`
- `asyncio_mode = "auto"` — all async test functions run automatically, no `@pytest.mark.asyncio` required on most tests (some files still add it explicitly)

**Assertion Library:**
- pytest `assert` statements for most tests
- `unittest.TestCase` for legacy `context_utils` tests (`src/tests/test_context_utils.py`, `src/tests/test_storage_backend.py`)

**Run Commands:**
```bash
uv run pytest                        # Run all tests (flatfile backend)
uv run pytest src/tests/             # Explicit path
uv run pytest -m "not postgres"      # Skip Postgres integration tests
uv run pytest -m postgres            # Run only Postgres tests (requires Docker on port 5434)
uv run pytest src/tests/test_auth.py # Single file
```

## Test File Organization

**Location:**
- All tests live in `src/tests/` — NOT co-located with source
- One test file per source module/feature: `test_context_api.py`, `test_auth.py`, `test_skills_api.py`

**Naming:**
- Files: `test_{feature}.py`
- Classes: `Test{Feature}` — always class-based grouping (no bare test functions in newer tests)
- Methods: `test_{scenario_description}` — descriptive, no abbreviations

**Structure:**
```
src/tests/
├── conftest.py               # Fixtures: pg_engine, pg_seed, tenant_a_session, tenant_b_session
├── test_auth.py              # Unit tests (JWT, encryption, ORM model structure)
├── test_auth_endpoints.py    # Integration tests (FastAPI TestClient)
├── test_context_api.py       # Integration tests (FastAPI TestClient + mock DB)
├── test_context_batch.py     # Integration tests (batch endpoint)
├── test_context_utils.py     # Unit tests (legacy, unittest.TestCase style)
├── test_files_api.py         # Integration tests (file upload/list endpoints)
├── test_integrations_api.py  # Integration tests (OAuth integrations)
├── test_migration_tool.py    # Unit tests (v1→v2 migration parser)
├── test_onboarding_sse.py    # Integration tests (SSE streaming endpoint)
├── test_rate_limit.py        # Unit + integration tests (rate limiting, run limits)
├── test_skills_api.py        # Integration tests (skill list, run, stream)
├── test_storage.py           # Postgres integration tests (real DB, marked @postgres)
├── test_storage_backend.py   # Unit tests (backend selector, unittest.TestCase style)
├── test_tenant_endpoints.py  # Integration tests (tenant CRUD, invites, members)
└── test_work_items_api.py    # Integration tests (work item CRUD + run skill)
```

Total: 291 test functions across 16 test files.

## Test Structure

**Class-based grouping (preferred pattern for newer tests):**
```python
class TestContextFiles:
    def test_list_files(self, client):
        """GET /context/files returns catalog items."""
        ...

    def test_list_files_requires_auth(self, client):
        """GET /context/files without auth returns error with {error, message, code}."""
        ...
```

**Legacy unittest.TestCase pattern (context_utils, storage_backend tests):**
```python
class TestContextEntry(unittest.TestCase):
    def test_dataclass_defaults(self):
        entry = ContextEntry(...)
        self.assertEqual(...)
```

**Test method docstrings:**
- Every test method has a one-line docstring: `"""GET /context/files returns catalog items."""`
- The docstring describes both the action and expected outcome

**Setup/Teardown:**
- Fixtures via `conftest.py` — no `setUp/tearDown` in newer tests
- `_TempRootMixin` in `test_context_utils.py` provides isolation via temp directories
- `client` fixture resets `app.dependency_overrides` before and after each test

## Mocking

**Framework:** `unittest.mock` — `AsyncMock`, `MagicMock`, `patch`

**FastAPI dependency overrides (primary pattern for API tests):**
```python
app.dependency_overrides[require_tenant] = lambda: user
app.dependency_overrides[get_tenant_db] = lambda: mock_db
```

**Mock DB pattern (repeated across test files — not yet extracted to conftest):**
```python
class MockResult:
    def __init__(self, value=None, values=None, scalar_val=None):
        self._value = value
        self._values = values or []
        self._scalar_val = scalar_val

    def scalar_one_or_none(self): return self._value
    def scalar(self): return self._scalar_val
    def scalars(self): return self
    def all(self): return self._values

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
```

Note: `MockResult` and `_mock_db` are duplicated in `test_context_api.py`, `test_rate_limit.py`, `test_tenant_endpoints.py`, and others — this is a known issue (see CONCERNS.md).

**Patching settings/external services:**
```python
@patch("flywheel.auth.jwt.settings")
def test_decode_valid_token(self, mock_settings):
    mock_settings.supabase_jwt_secret = TEST_JWT_SECRET
    ...
```

**Token payload helper (per file, not shared):**
```python
def _make_user(tenant_id=TEST_TENANT_ID, is_anonymous=False):
    return TokenPayload(
        sub=TEST_USER_ID,
        email="test@example.com",
        is_anonymous=is_anonymous,
        app_metadata={"tenant_id": str(tenant_id), "role": "admin"},
    )
```

**What to mock:**
- DB sessions (`AsyncSession`) — always mocked in API tests
- External service calls (Supabase admin, Google, Slack) — patched with `patch()`
- File system paths (`patch("flywheel.api.skills.SKILLS_DIR", tmp_path)`)
- Settings object when testing auth that reads secrets

**What NOT to mock:**
- ORM models — use `MockContextEntry`, `MockContextCatalog` plain Python objects
- Pydantic models — instantiate directly: `TokenPayload(...)`
- `TestClient` — use real FastAPI app with dependency overrides instead

## Fixtures and Factories

**Shared fixtures (`src/tests/conftest.py`):**
```python
@pytest.fixture
def tenant_ids():
    """Fixed UUIDs for Tenant A and Tenant B."""
    return {"a": TENANT_A_ID, "b": TENANT_B_ID}

@pytest.fixture
async def tenant_a_session(pg_session_factory, pg_seed):
    """AsyncSession with RLS context for Tenant A / User A."""
    session = await get_tenant_session(pg_session_factory, TENANT_A_ID, USER_A_ID)
    try:
        yield session
    finally:
        await session.close()
```

**Deterministic test UUIDs:**
```python
_NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")
TENANT_A_ID = str(uuid.uuid5(_NAMESPACE, "tenant-a"))
USER_A_ID = str(uuid.uuid5(_NAMESPACE, "user-a"))
```

**Mock ORM objects (inline in each test file):**
```python
class MockContextEntry:
    def __init__(self, id=None, file_name="company-intel", ...):
        self.id = id or uuid4()
        self.date = date or datetime.date(2026, 3, 20)
        ...
```

**Location:**
- Shared DB fixtures: `src/tests/conftest.py`
- Mock ORM objects: inline in each test file (not shared)
- Test constants (`TEST_USER_ID`, `TEST_TENANT_ID`): module-level in each test file

## Coverage

**Requirements:** Not enforced — no coverage threshold configured

**Run coverage:**
```bash
uv run pytest --cov=flywheel --cov-report=html
```

## Test Types

**Unit Tests:**
- Scope: single function/class, no I/O
- Files: `test_auth.py`, `test_context_utils.py`, `test_storage_backend.py`, `test_migration_tool.py`, `test_rate_limit.py` (key function tests)
- Pattern: instantiate directly, call function, assert result

**Integration Tests (FastAPI + mock DB):**
- Scope: full HTTP request/response cycle with mocked database
- Pattern: `TestClient(app)` + `app.dependency_overrides`
- Files: all `test_*_endpoints.py` and `test_*_api.py` files
- Advantages: tests routing, authentication chain, serialization, status codes

**Postgres Integration Tests:**
- Scope: real SQLAlchemy queries against Docker Postgres (port 5434)
- Marker: `@pytest.mark.postgres` (set via `pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]`)
- Files: `src/tests/test_storage.py`
- Fixtures: `tenant_a_session`, `tenant_b_session`, `admin_session`, `pg_seed`
- Skipped by default: run with `pytest -m postgres`

**E2E Tests:** Not present.

## Async Testing

```python
# asyncio_mode = "auto" in pyproject.toml means these just work:
async def test_anonymous_under_limit(self):
    db = _mock_db([MockResult(scalar_val=2)])
    await check_anonymous_run_limit(TEST_USER_ID, True, db)

# Postgres tests use async fixtures from conftest:
async def test_read_single_entry(self, tenant_a_session):
    await append_entry(tenant_a_session, "company-intel", {...}, "research-skill")
    await tenant_a_session.commit()
    result = await read_context(tenant_a_session, "company-intel")
    assert "source: research-skill" in result
```

## Error Testing

```python
# Test HTTPException status codes and error format:
def test_update_entry_not_found(self, client):
    resp = client.patch(f"/api/v1/context/entries/{uuid4()}", json={"content": "Updated"})
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == 404
    assert "error" in data
    assert "message" in data

# Test raised exceptions directly:
with pytest.raises(HTTPException) as exc_info:
    await check_anonymous_run_limit(TEST_USER_ID, True, db)
assert exc_info.value.status_code == 429

# Test error format for validation failures:
resp = client.get("/api/v1/context/search")  # missing required `q`
assert resp.status_code == 422
assert resp.json()["error"] == "ValidationError"
```

---

*Testing analysis: 2026-03-26*
