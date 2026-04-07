# Phase 78: MCP Infrastructure - Research

**Researched:** 2026-03-30
**Domain:** FastMCP tool transport layer, httpx REST client, middleware logging
**Confidence:** HIGH

## Summary

Phase 78 adds 10 new methods to the existing `FlywheelClient` class and wires invocation logging for all MCP tool calls. The codebase already has a clean, well-established pattern: `FlywheelClient` wraps httpx with token refresh and error handling via a `_request()` helper, and the MCP server uses `@mcp.tool()` decorators with try/except blocks returning strings.

The backend API endpoints for all 10 methods already exist. The mapping is straightforward -- each client method corresponds to one REST endpoint. FastMCP 2.9+ provides built-in `Middleware` subclassing with an `on_call_tool` hook that captures tool name, arguments, and timing without modifying individual tool functions.

**Primary recommendation:** Follow the existing `_request()` pattern exactly for all 10 new methods; add a single custom `Middleware` subclass for invocation logging; change the `FLYWHEEL_FRONTEND_URL` default from port 5175 to 5173.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastmcp | >=2.0 (pinned in pyproject.toml) | MCP server framework | Already in use, has middleware system |
| httpx | >=0.27 | Synchronous HTTP client | Already in use via FlywheelClient |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging (stdlib) | N/A | Structured log output | For tool invocation logs |
| time (stdlib) | N/A | Duration measurement | For timing tool calls |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom Middleware | Built-in LoggingMiddleware | Built-in is opaque; custom gives exact log format control |
| stdlib logging | structlog | Over-engineering for this scope; stdlib is fine |

## Architecture Patterns

### Existing FlywheelClient Pattern (FOLLOW EXACTLY)

Every method in `FlywheelClient` follows this pattern:
```python
def method_name(self, param1: str, param2: int = 10) -> dict:
    """HTTP_METHOD /api/v1/resource -- short description."""
    return self._request(
        "get",  # or "post", "patch"
        "/api/v1/resource/path",
        params={"key": value},  # for GET
        json={"key": value},    # for POST/PATCH
    )
```

Key details:
- All methods return `dict` (from `resp.json()`)
- `_request()` handles token refresh, HTTP errors, 401 logout, and timeout
- Methods are thin -- no business logic, just endpoint mapping
- Docstring format: `"""HTTP_METHOD /api/v1/path -- description."""`

### Existing MCP Tool Pattern (FOLLOW EXACTLY)

```python
@mcp.tool()
def tool_name(param: str = "default") -> str:
    """Tool description for Claude.

    Multi-line docstring becomes the tool description.
    """
    try:
        client = FlywheelClient()
        result = client.some_method(param)
        # Format result as human-readable string
        return formatted_string
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error doing thing: {exc}"
```

Key details:
- Each tool creates a fresh `FlywheelClient()` instance
- Return type is always `str` (MCP tools return text)
- Two-level exception handling: `FlywheelAPIError` then generic `Exception`
- Never raises -- always returns error as string

### Middleware Pattern for Logging

```python
import logging
import time
from fastmcp.server.middleware import Middleware, MiddlewareContext

logger = logging.getLogger("flywheel_mcp")

class InvocationLogger(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.name
        args = context.message.arguments
        start = time.time()
        try:
            result = await call_next(context)
            duration = time.time() - start
            logger.info(
                "tool_call",
                extra={
                    "tool": tool_name,
                    "params": args,
                    "duration_ms": round(duration * 1000),
                    "success": True,
                },
            )
            return result
        except Exception as exc:
            duration = time.time() - start
            logger.error(
                "tool_call_failed",
                extra={
                    "tool": tool_name,
                    "params": args,
                    "duration_ms": round(duration * 1000),
                    "success": False,
                    "error": str(exc),
                },
            )
            raise

mcp = FastMCP("Flywheel")
mcp.add_middleware(InvocationLogger())
```

### Anti-Patterns to Avoid
- **Logging inside each tool function:** Use middleware instead -- single point of concern
- **Async client methods:** FlywheelClient uses sync httpx.Client (MCP tools are called from sync context via FastMCP)
- **Raising exceptions from tools:** MCP tools must return strings, never raise

## Method-to-Endpoint Mapping

This is the critical reference for implementation. All endpoints are prefixed with `/api/v1`.

| # | Client Method | HTTP | Endpoint | Notes |
|---|--------------|------|----------|-------|
| 1 | `fetch_skills()` | GET | `/skills/` | Returns `{"items": [...]}` |
| 2 | `fetch_skill_prompt(skill_name)` | GET | `/skills/{skill_name}/prompt` | Returns `{"skill_name": ..., "system_prompt": ...}` |
| 3 | `fetch_meetings(time=None, limit=50)` | GET | `/meetings/?time=past&limit=50` | time: "upcoming"/"past"/None |
| 4 | `fetch_upcoming(limit=10)` | GET | `/meetings/?time=upcoming&limit={limit}` | Convenience wrapper for fetch_meetings |
| 5 | `fetch_tasks(status=None, limit=50)` | GET | `/tasks/?status={status}&limit={limit}` | Filters: status, priority, meeting_id, account_id |
| 6 | `fetch_account(account_id)` | GET | `/accounts/{account_id}` | Returns full detail with contacts + timeline |
| 7 | `sync_meetings()` | POST | `/meetings/sync` | Triggers Granola sync, returns counts |
| 8 | `save_document(title, skill_name, markdown_content, metadata={})` | POST | `/documents/from-content` | Creates SkillRun + Document from markdown |
| 9 | `save_meeting_summary(meeting_id, ai_summary, processing_status)` | PATCH | `/meetings/{meeting_id}` | Writes back AI-generated summary |
| 10 | `update_task(task_id, **fields)` | PATCH | `/tasks/{task_id}` | Updates allowed fields: title, description, priority, status, etc. |

## Port Change

The `FLYWHEEL_FRONTEND_URL` default on line 30 of `api_client.py` is currently:
```python
self.frontend_url = os.environ.get(
    "FLYWHEEL_FRONTEND_URL", "http://localhost:5175"
)
```

Change to `"http://localhost:5173"` per success criteria INFRA-04.

This is the ONLY place 5175 appears in the cli/ directory (verified via grep).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tool invocation logging | Per-tool logging code | FastMCP Middleware subclass with `on_call_tool` | Single point of concern, captures ALL tools including existing 3 |
| HTTP error handling | Per-method try/except | Existing `_request()` helper | Already handles 401, timeouts, JSON parsing |
| Token refresh | Manual token management | Existing `_ensure_token()` in `_request()` | Already handles auto-refresh |

## Common Pitfalls

### Pitfall 1: Sync vs Async Mismatch
**What goes wrong:** FastMCP 2.9 middleware uses `async def on_call_tool` but FlywheelClient is synchronous httpx
**Why it happens:** FastMCP internally handles the sync/async bridge for tool functions but middleware is always async
**How to avoid:** The tool functions themselves are sync (as existing code shows) and FastMCP handles this. Middleware must be async. This is not a conflict -- FastMCP runs sync tools in a thread pool.
**Warning signs:** `RuntimeError: cannot call sync function from async context`

### Pitfall 2: Middleware Catches Tool Return Strings, Not Exceptions
**What goes wrong:** Tools return error strings instead of raising, so middleware `except` block never fires for business errors
**Why it happens:** MCP tool pattern catches all exceptions and returns `str(exc)`
**How to avoid:** The middleware logs success=True for ALL tool completions (since tools never raise). To detect failures, middleware could inspect the return value for error patterns, but the simpler approach is: middleware logs timing/invocation, tools handle their own error reporting.
**Warning signs:** All tool calls show success=True even when the API returned an error

### Pitfall 3: Missing Query Parameters in GET Methods
**What goes wrong:** Forgetting to pass optional filters (time, status, limit) as `params=` dict
**Why it happens:** Copy-paste from POST methods that use `json=`
**How to avoid:** GET methods use `params={}`, POST/PATCH methods use `json={}`
**Warning signs:** 422 Validation Error from FastAPI

### Pitfall 4: Frontend URL Used for Generating Links
**What goes wrong:** `frontend_url` is used in `flywheel_run_skill` to generate "View results" links
**Why it happens:** The port change from 5175 to 5173 could break existing link generation if not updated
**How to avoid:** Single change on line 30 of api_client.py covers all usages since `self.frontend_url` is set once
**Warning signs:** Links pointing to wrong port in MCP tool responses

## Code Examples

### New Client Method (GET with params)
```python
# Source: follows existing pattern from api_client.py lines 91-95
def fetch_meetings(self, time: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    """GET /api/v1/meetings/ -- list meetings with optional time filter."""
    params = {"limit": limit, "offset": offset}
    if time is not None:
        params["time"] = time
    return self._request("get", "/api/v1/meetings/", params=params)
```

### New Client Method (POST with json)
```python
# Source: follows existing pattern from api_client.py lines 79-85
def save_document(self, title: str, skill_name: str, markdown_content: str, metadata: dict | None = None) -> dict:
    """POST /api/v1/documents/from-content -- create document from markdown."""
    return self._request(
        "post",
        "/api/v1/documents/from-content",
        json={
            "title": title,
            "skill_name": skill_name,
            "markdown_content": markdown_content,
            "metadata": metadata or {},
        },
    )
```

### New Client Method (PATCH with json)
```python
# Source: follows existing pattern, matches PATCH /meetings/{id} schema
def save_meeting_summary(self, meeting_id: str, ai_summary: str, processing_status: str = "completed") -> dict:
    """PATCH /api/v1/meetings/{meeting_id} -- write back AI summary."""
    return self._request(
        "patch",
        f"/api/v1/meetings/{meeting_id}",
        json={"ai_summary": ai_summary, "processing_status": processing_status},
    )
```

### Middleware Registration
```python
# Source: FastMCP 2.9 middleware docs
from fastmcp import FastMCP
from flywheel_mcp.logging_middleware import InvocationLogger

mcp = FastMCP("Flywheel")
mcp.add_middleware(InvocationLogger())
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual logging in each tool | FastMCP Middleware `on_call_tool` | FastMCP 2.9 | Single logging point for all tools |
| Per-tool timing with `time.time()` | Middleware-based timing | FastMCP 2.9 | Consistent, automatic for all tools |

## Open Questions

1. **FastMCP version compatibility**
   - What we know: pyproject.toml pins `fastmcp>=2.0`, middleware requires 2.9+
   - What's unclear: Exact installed version (could not check in env)
   - Recommendation: Verify `pip show fastmcp` in the dev environment. If <2.9, update pin to `>=2.9`. If middleware import fails, fall back to a simple decorator-based logger.

2. **Log destination**
   - What we know: MCP server runs via stdio transport; stderr is available for logging
   - What's unclear: Whether there is an existing logging configuration
   - Recommendation: Use `logging.getLogger("flywheel_mcp")` with a StreamHandler to stderr. MCP uses stdout for protocol; logs must go to stderr.

## Sources

### Primary (HIGH confidence)
- `cli/flywheel_mcp/api_client.py` - Existing FlywheelClient pattern (6 methods)
- `cli/flywheel_mcp/server.py` - Existing 3 MCP tools with @mcp.tool() pattern
- `cli/pyproject.toml` - FastMCP version pin (>=2.0)
- `backend/src/flywheel/api/skills.py` - GET /skills/, GET /skills/{name}/prompt
- `backend/src/flywheel/api/meetings.py` - GET /meetings/, POST /sync, PATCH /{id}
- `backend/src/flywheel/api/tasks.py` - GET /tasks/, PATCH /{task_id}
- `backend/src/flywheel/api/accounts.py` - GET /accounts/{id}
- `backend/src/flywheel/api/documents.py` - POST /from-content

### Secondary (MEDIUM confidence)
- [FastMCP middleware docs](https://gofastmcp.com/servers/middleware) - Middleware class API, on_call_tool hook
- [FastMCP 2.9 blog post](https://www.jlowin.dev/blog/fastmcp-2-9-middleware) - Middleware system introduction
- [FastMCP logging middleware](https://gofastmcp.com/python-sdk/fastmcp-server-middleware-logging) - Built-in LoggingMiddleware reference

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use, no new dependencies
- Architecture: HIGH - exact patterns visible in existing code, 10 methods are mechanical
- Middleware: MEDIUM - FastMCP middleware API verified from docs but version compatibility needs runtime check
- Pitfalls: HIGH - identified from reading existing code patterns

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable domain, no fast-moving dependencies)
