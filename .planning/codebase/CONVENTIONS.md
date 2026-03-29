# Coding Conventions

**Analysis Date:** 2026-03-26

## Naming Patterns

**Files:**
- `snake_case.py` for all Python modules: `chat_orchestrator.py`, `circuit_breaker.py`, `email_dispatch.py`
- API routers match the resource noun: `context.py`, `skills.py`, `tenant.py`
- Service files use `noun_verb.py` or `noun.py`: `gmail_sync.py`, `entity_extraction.py`, `job_queue.py`

**Functions:**
- `snake_case` for all functions: `get_current_user`, `claim_next_job`, `append_entry`
- Private helpers prefixed with `_`: `_entry_to_dict`, `_mock_db`, `_make_user`, `_paginated_response`
- Async functions named same as sync equivalents — no `async_` prefix

**Variables:**
- `snake_case` for all variables: `tenant_id`, `session_factory`, `skill_run`
- Module-level singletons use lowercase: `logger`, `settings`, `anthropic_breaker`
- Module-level constants use `UPPER_SNAKE_CASE`: `POLL_INTERVAL`, `TEST_JWT_SECRET`

**Types/Classes:**
- `PascalCase` for all classes: `CircuitBreaker`, `TokenPayload`, `ContextEntry`
- Pydantic request models suffixed `Request`: `AppendEntryRequest`, `BatchEntriesRequest`
- Pydantic response models suffixed `Response`: `OnboardingCacheResponse`, `OnboardingRefreshResponse`
- ORM models are noun-only: `Tenant`, `Profile`, `SkillRun`, `ContextEntry`
- Custom exceptions suffixed with `Error` or `Open`: `CircuitBreakerOpen`, `ContractViolation`
- Enum classes use `PascalCase` with `str, Enum` mixin: `class CircuitState(str, Enum)`

**Routers:**
- Named `router` in every API module and imported as `{noun}_router` in `main.py`

## Code Style

**Formatting:**
- Tool: Ruff (`ruff>=0.8` in dev dependencies)
- Line length: 100 characters (configured in `pyproject.toml`)
- Target: Python 3.12
- Ruff excludes: `src/flywheel/engines/*` and `src/flywheel/context_utils.py` (legacy code)

**Linting:**
- Ruff for lint (replaces flake8)
- mypy for type checking (`warn_return_any = true`, `warn_unused_configs = true`)
- mypy ignores errors in `flywheel.engines.*` and `flywheel.context_utils` (legacy)

**Type annotations:**
- `from __future__ import annotations` is used in every `.py` file under `src/flywheel/` — this is required
- Python 3.10+ union syntax preferred: `str | None` instead of `Optional[str]`
- SQLAlchemy uses `Mapped[T]` and `mapped_column()` — do not use legacy Column() style
- Collection types from `collections.abc` preferred over `typing`: `AsyncGenerator`, not `typing.AsyncGenerator`

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first)
2. Standard library imports
3. Third-party imports (fastapi, sqlalchemy, pydantic, etc.)
4. Internal imports (`flywheel.*`)

**Pattern:**
```python
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import ContextEntry
```

**Deferred imports:**
- Heavy or optional imports (e.g., `entity_extraction`, `streams`) are imported inline inside functions to keep startup fast and avoid circular imports
- Example pattern: `from flywheel.services.entity_extraction import process_entry_for_graph` inside the endpoint body with `except Exception: pass` wrapper

**No barrel files** — each module imports directly from the source module.

## Error Handling

**API layer (`src/flywheel/api/`):**
- Raise `fastapi.HTTPException` with explicit `status_code` and `detail` string
- Use `status.HTTP_*` constants for status codes: `status.HTTP_401_UNAUTHORIZED`
- All HTTP errors return JSON `{"error": str, "message": str, "code": int}` via global handlers in `src/flywheel/api/errors.py`
- 404 pattern: query → `scalar_one_or_none()` → `if entry is None: raise HTTPException(404)`

**Non-blocking operations:**
- Graph extraction and density recompute in `src/flywheel/api/context.py` are wrapped with bare `except Exception:` and `pass` — failures are intentionally swallowed for non-critical paths
- Warning-level exceptions logged with `exc_info=True` before being swallowed:
  ```python
  except Exception:
      logging.getLogger(__name__).warning("...", exc_info=True)
  ```

**Service layer:**
- Services raise plain Python exceptions (`ValueError`, custom exceptions)
- Services that call external APIs use circuit breaker pattern (`src/flywheel/services/circuit_breaker.py`)
- Graceful degradation pattern: check config first, log and return `None` if not configured (e.g., `src/flywheel/services/email.py`)

**Validation errors:**
- Pydantic field constraints via `Field(..., min_length=1, max_length=50)` — raises 422 automatically
- Custom validation in Pydantic validators

## Logging

**Framework:** Python standard library `logging`

**Setup:**
- Module-level logger: `logger = logging.getLogger(__name__)` — present in all 52+ source files
- App-level config in `src/flywheel/main.py`:
  ```python
  logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
  ```

**Patterns:**
- `logger.info(...)` for lifecycle events (startup, job claims, circuit breaker state changes)
- `logger.warning("...", exc_info=True)` for swallowed non-critical exceptions
- `logger.exception(...)` for unhandled exceptions in the global error handler

## Comments

**Module docstrings:**
- Every module has a top-level docstring describing its purpose and public API
- API modules list all endpoints with HTTP method and path
- Service modules describe their architecture (e.g., 3-state circuit breaker)

**Section separators:**
- Sections within large files use `# ---` comment banners:
  ```python
  # ---------------------------------------------------------------------------
  # Request / Response models
  # ---------------------------------------------------------------------------
  ```

**Inline comments:**
- Used to explain non-obvious decisions ("SKIP LOCKED so multiple workers can compete")
- TODOs are sparse and left in-place: `# TODO: Remove filesystem fallback after confirming all skills are seeded`

## Function Design

**Size:** No hard rule, but API handlers are typically 20–50 lines. Services can be larger.

**Parameters:**
- FastAPI endpoints use dependency injection via `Depends()` for auth and DB
- All Depends go at the end of function parameters after request body

**Return Values:**
- API endpoints return plain dicts (not Pydantic models), relying on FastAPI serialization
- `response_model=` is used selectively (e.g., `OnboardingCacheResponse`) where strict schema validation matters
- Soft deletes return `{"deleted": True, "id": str(entry_id)}`
- List endpoints return `{"items": [...]}` or paginated envelope from `_paginated_response()`
- Paginated envelope shape: `{"items": [...], "total": int, "offset": int, "limit": int, "has_more": bool}`

## Module Design

**Exports:**
- `__all__` is defined in modules that serve as public APIs (e.g., `storage_backend.py`)
- Modules without `__all__` rely on convention (prefixed `_` = private)

**Configuration:**
- All settings in `src/flywheel/config.py` as a single `Settings` (pydantic-settings) instance
- Imported as `from flywheel.config import settings` — singleton, not passed as argument

**Dependency injection chain (FastAPI):**
```
get_current_user → require_tenant → require_admin
get_tenant_db (uses require_tenant internally)
get_db_unscoped (no RLS)
```

---

*Convention analysis: 2026-03-26*
