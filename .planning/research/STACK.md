# Stack Research — v22.0 Skill Platform Consolidation

**Milestone:** Server-hosted skill Python asset delivery (subsequent milestone on existing Flywheel v2 app)
**Researched:** 2026-04-17
**Mode:** Ecosystem + Feasibility (narrow scope)
**Overall confidence:** HIGH — all load-bearing claims verified against the local codebase, installed package signatures, or official docs.

---

## TL;DR (one line)

Store skill bundles as **ZIP blobs in a new `skill_assets` table (bytea)** written by an extended `seed_skills()` pipeline, serve them via a **new `flywheel_fetch_skill_assets` MCP tool returning a `fastmcp.utilities.types.File(data=..., format="zip")`**, and extract them on the user's machine with **`tempfile.TemporaryDirectory` + `zipfile.ZipFile` (stdlib only)** — no new framework, no new Python dependencies.

---

## Stack Additions

### 1. Server-side storage — `skill_assets` table (bytea) + extended seed pipeline

**Recommended:** New table `skill_assets` with `bundle BYTEA NOT NULL`, one row per skill, FK to `skill_definitions(id)` with `ON DELETE CASCADE`.

| Choice | Type | Version | Purpose | Why |
|---|---|---|---|---|
| New table `skill_assets` | PostgreSQL table | — | One-to-one with `skill_definitions`, stores the zipped bundle + metadata | Keeps `skill_definitions` narrow (one row = one lookup for MCP discovery), lets us add asset-only columns (`bundle_sha256`, `bundle_size_bytes`, `bundle_format`, `updated_at`) without bloating the skill catalog row |
| `bundle BYTEA` column | PostgreSQL column | — | Holds the zipped skill directory | 1 GB hard limit per bytea value (PostgreSQL TOAST 30-bit size); broker skill dir is 160 KB today, all 42 .py files total 24.6K LOC ≈ well under 2 MB zipped — five orders of magnitude of headroom. `LargeBinary` column is an established Flywheel pattern (`UserAccount.api_key_encrypted`, `EmailAccount.credentials_encrypted`, portal credentials, etc.) — no new mental model for the team |
| `bundle_sha256 TEXT` | PostgreSQL column | — | Integrity / change-detection | Lets the MCP tool send `If-None-Match` equivalent, and lets the seed pipeline skip re-uploading unchanged bundles |
| `bundle_size_bytes INTEGER` | PostgreSQL column | — | Observability + cheap sanity gate in the fetch endpoint | — |
| `bundle_format TEXT` default `'zip'` | PostgreSQL column | — | Future-proof (we might add `tar.gz` for larger bundles) | — |
| `updated_at TIMESTAMPTZ` | PostgreSQL column | — | Client-side cache invalidation | — |

**Why not Supabase Storage:** Confirmed available and working in-repo (`services/document_storage.py`) — Pro plan supports up to 500 GB per object [Supabase Docs](https://supabase.com/docs/guides/storage/uploads/file-limits). But for **sub-megabyte bundles that ship on every skill fetch**, Storage adds a **second auth hop (service-role signed URL)**, a **second network roundtrip** (sign → download), and **two places to keep in sync** (DB row for metadata + Storage object for bytes). A single `SELECT bundle FROM skill_assets WHERE skill_id = ?` is simpler and atomic with the skill catalog. Revisit if any single bundle crosses ~20 MB.

**Why not a `bundle` column on `skill_definitions` itself:** Every `GET /skills/` list call would need to explicitly avoid `SELECT *` to skip the bundle column, and the hot-path `list_skills` endpoint already returns the row (see `api/skills.py:125-175` `_get_available_skills_db`). Forgetting `defer(SkillDefinition.bundle)` once would pull megabytes into every list response. Separate table = no such footgun.

**Migration path (one-way, new milestone):** Standard Alembic migration — `CREATE TABLE skill_assets (...)` + indexes. Uses the **existing PgBouncer DDL workaround** (per-statement `op.execute()` commits, see `alembic/versions/063_skill_protected_default.py:36-38` for the pattern). No data backfill needed on first deploy — the seed pipeline populates on first run.

### 2. Bundling format — stdlib `zipfile` writing in-memory via `io.BytesIO`

| Choice | Module | Version | Purpose | Why |
|---|---|---|---|---|
| `zipfile.ZipFile` | Python stdlib | 3.12 (backend), 3.10+ (CLI) | Pack/unpack skill directories | Python stdlib. Supports `BytesIO` as `fileobj` for fully in-memory round-trip. **DEFLATE built-in** — no zstd/lz4 dependency needed |
| `io.BytesIO` | Python stdlib | — | In-memory buffer for the zip | Same — stdlib |
| `hashlib.sha256` | Python stdlib | — | Content hash for `bundle_sha256` | Same — stdlib |

**Why zip over tar.gz:**
1. **Random access** — `zipfile.ZipFile(...).read("api_client.py")` without decompressing the whole archive. Not critical today (CC extracts the whole thing) but useful for future selective loading.
2. **Cross-platform filename handling** — zip handles UTF-8 filenames uniformly; tarfile has legacy encoding quirks on mixed platforms.
3. **Security** — `zipfile` has no tar-style symlink attacks. (Still need path-traversal check on extract; see Pitfalls research.)
4. **Developer familiarity** — every dev can open a .zip with Finder / Explorer for debugging.

**Why not plain multi-file (array of `{path, content}` JSON):**
- Binary files (future: fonts, images shipped with skills) force base64, inflating payload ~33% before the wire compresses it.
- No built-in integrity/manifest concept; we'd reinvent zip poorly.
- JSON parse cost scales with file count, not byte count — hurts if skills eventually bundle 100+ files.

**Existing multi-file blob patterns in flywheel-v2:** Grep confirms **none** — the closest is encrypted OAuth-credentials-in-LargeBinary (`api_key_encrypted`, `credentials_encrypted`, `portal_credentials`). Those are single secrets, not archives. This milestone establishes the archive pattern.

### 3. MCP asset-fetch tool — `fastmcp.utilities.types.File` return

| Choice | Package | Version | Purpose | Why |
|---|---|---|---|---|
| `fastmcp.utilities.types.File` | fastmcp | **3.2.2+** (already pinned `>=3.2.2,<4` in `cli/pyproject.toml:39`) | Return binary bundle from MCP tool with MIME + name | **Verified locally**: `File(path=None, data=bytes|None, format=str|None, name=str|None, annotations=...)` in `cli/.venv/lib/python3.12/site-packages/fastmcp/utilities/types.py`. FastMCP base64-encodes `data` and wraps it as `BlobResourceContents` inside `EmbeddedResource` per MCP spec [FastMCP docs](https://gofastmcp.com/servers/tools). No extra dependency. No extra version bump. |

**Exact return pattern (new tool in `cli/flywheel_mcp/server.py`):**

```python
from fastmcp.utilities.types import File

@mcp.tool(output_schema=None)
def flywheel_fetch_skill_assets(skill_name: str) -> File | str:
    """Fetch the Python asset bundle for a skill as a ZIP archive.

    Returns the bundle bytes wrapped as a File resource (MCP base64-encodes
    automatically). Returns a string error message on failure so the tool
    contract matches the existing MCP tools in this server.
    """
    try:
        client = FlywheelClient()
        payload = client.fetch_skill_assets(skill_name)  # returns {"bundle_b64": "...", "sha256": "...", "size": N, "format": "zip"}
        import base64
        data = base64.b64decode(payload["bundle_b64"])
        return File(data=data, format=payload.get("format", "zip"), name=f"{skill_name}.zip")
    except FlywheelAPIError as exc:
        return str(exc)
```

**Why not stream raw `bytes` return:** FastMCP accepts bare `bytes` too, but the `File` helper gives us a **named archive** (`{skill_name}.zip`) visible to Claude Code's side, which matters for the ephemeral temp-dir unpack flow. Negligible code difference.

**Precedent for binary in existing MCP tools:** Grep confirms **none** — all 40+ existing tools in `cli/flywheel_mcp/server.py` return plain strings or dicts. This is the first binary-returning tool. Low risk because FastMCP does the base64 wrapping transparently.

**Server endpoint shape (new in `backend/src/flywheel/api/skills.py`):**
- `GET /api/v1/skills/{skill_name}/assets` — returns JSON `{"skill_name": "...", "bundle_b64": "...", "sha256": "...", "size": N, "format": "zip", "version": "..."}`.
- Reuses the **exact same auth + tenant-access query pattern** as `get_skill_prompt` (see `api/skills.py:283-344`) — same `require_tenant` dep, same `has_overrides` / `tenant_skills` branching, same 404 behavior.
- Base64-in-JSON (not raw `application/zip` response) because: (a) keeps one JSON-only HTTP client in the MCP layer (existing `_request` in `cli/flywheel_mcp/api_client.py:50-75` always calls `.json()`), (b) avoids a second code path for binary handling in the CLI, (c) 33% inflation is irrelevant at sub-MB payloads.

### 4. CC-side ephemeral temp-dir — `tempfile.TemporaryDirectory` context manager

| Choice | Module | Version | Purpose | Why |
|---|---|---|---|---|
| `tempfile.TemporaryDirectory` | Python stdlib | 3.10+ | Secure, auto-cleanup directory | Creates dir with random suffix in system temp (`$TMPDIR` / `/tmp`) with secure perms (0o700), `__exit__` recursively deletes [Python docs](https://docs.python.org/3/library/tempfile.html#tempfile.TemporaryDirectory) |
| `with ... as tmpdir:` context manager | Python stdlib | — | Guarantee cleanup even on exception | Documented best practice; failsafe against leaked dirs |
| `ignore_cleanup_errors=True` | Python stdlib | Python 3.10+ | Best-effort cleanup on weird FS states | Pass this to tolerate macOS APFS races and file locks during tests |
| `zipfile.ZipFile(...).extractall()` with **path-traversal guard** | Python stdlib | — | Unpack into tmpdir | Stdlib. **Must** validate each member name to reject `../` or absolute paths (tracked in PITFALLS) |

**Canonical pattern (goes wherever CC executes skill Python — probably a helper in `cli/flywheel_mcp/`):**

```python
import base64, io, tempfile, zipfile
from pathlib import Path

def materialize_skill_bundle(bundle_bytes: bytes) -> tempfile.TemporaryDirectory:
    """Extract bundle into a new secure temp dir. Caller uses as context manager:

        with materialize_skill_bundle(data) as tmpdir:
            subprocess.run(["python", Path(tmpdir) / "main.py"], cwd=tmpdir)
        # tmpdir and contents auto-deleted here
    """
    tmp = tempfile.TemporaryDirectory(prefix="flywheel-skill-", ignore_cleanup_errors=True)
    with zipfile.ZipFile(io.BytesIO(bundle_bytes), "r") as zf:
        # Path-traversal guard BEFORE extractall (see PITFALLS)
        for member in zf.namelist():
            if member.startswith("/") or ".." in Path(member).parts:
                raise ValueError(f"Refusing unsafe zip member: {member}")
        zf.extractall(tmp.name)
    return tmp
```

**Why not `atexit.register`:** Works, but couples cleanup to process lifetime rather than scope — if CC holds the dir for the full MCP session, a crashed MCP server leaves it behind. The context-manager scope is bounded by a single skill invocation, which is the correct lifetime. Use `atexit` only as a **backup sweeper** for orphaned `flywheel-skill-*` dirs on MCP server startup (optional hardening, Phase 2).

**Why not `/tmp/flywheel-skills/<skill>`:** Shared parent dir across skill runs creates cleanup races and security issues (one skill could see another's partially-extracted files). `TemporaryDirectory` gives each run a unique random-suffix dir — no sharing.

### 5. Auth boundary — reuse existing Bearer token + tenant RLS

**No new primitives needed.** The new asset endpoint reuses the existing auth stack end-to-end:

| Layer | Existing primitive | Reuse unchanged? |
|---|---|---|
| Token storage | `~/.flywheel/credentials.json` via `flywheel_cli.auth.save_credentials` (600 perms, see `cli/flywheel_cli/auth.py:19-36`) | **Yes** |
| Token retrieval | `flywheel_cli.auth.get_token()` with auto-refresh on near-expiry | **Yes** |
| HTTP header | `Authorization: Bearer {token}` set by `FlywheelClient.__init__` in `cli/flywheel_mcp/api_client.py:33-37` | **Yes** |
| Auto-refresh on 401 | `_ensure_token()` + `clear_credentials()` on 401 in `api_client.py:43-62` | **Yes** |
| Server-side tenant auth | `Depends(require_tenant)` → `TokenPayload` with `tenant_id` | **Yes** |
| Tenant-scoped skill query | `has_overrides` + `tenant_skills` branching (see `api/skills.py:296-323`) | **Yes — copy verbatim from `get_skill_prompt`** |
| `protected` skill handling | Stub response when `skill.protected == True` (see `api/skills.py:337-342`) | **Yes — but decision: return the bundle OR refuse?** Flagged in PITFALLS. Current Phase-95-corrected posture: `protected` applies to the **prompt**, not the code. Code contains no LLM instructions, so fetching assets for a non-protected (default) skill should just work. Protected skills don't need assets shipped client-side anyway (they execute server-side by definition), so returning 403 for protected-skill asset fetches is the right default. |

**Two environment-variable paths, both already supported:**
- **Interactive users:** `flywheel login` populates `credentials.json`. No change.
- **CI / headless:** `FLYWHEEL_API_TOKEN` env var read by `get_token()`. No change.

---

## Integration Points

### Extends (modify existing)

| File | Change | Why |
|---|---|---|
| `backend/src/flywheel/db/models.py` | Add `SkillAsset` ORM class (new table) | One-to-one with `SkillDefinition`; keeps hot-path skill listing fast |
| `backend/src/flywheel/db/seed.py` | Extend `scan_skills()` to collect `.py` files in the skill dir; extend `seed_skills()` to build zip in-memory + upsert into `skill_assets` | Same pipeline already walks the skill dir tree; adding a `_build_bundle(entry_path) -> bytes` helper and a second upsert is low-risk. Reuse `on_conflict_do_update` + `sha256`-based skip-if-unchanged |
| `backend/src/flywheel/api/skills.py` | Add `GET /{skill_name}/assets` endpoint | Copy the exact auth/tenant-access shape of `get_skill_prompt` (lines 283-344) |
| `cli/flywheel_mcp/api_client.py` | Add `fetch_skill_assets(skill_name) -> dict` method | Single new wrapper around `self._request("get", f"/api/v1/skills/{skill_name}/assets")`. Matches the existing 44-method shape |
| `cli/flywheel_mcp/server.py` | Add `flywheel_fetch_skill_assets` MCP tool | Returns `fastmcp.utilities.types.File` (new — first binary tool in this server). Add to `_GTM_TOOLS` set (line 81) so onboarding guard recognizes it |
| `cli/pyproject.toml` | **No change** (fastmcp already pinned ≥3.2.2) | — |
| `backend/pyproject.toml` | **No change** | — |

### New files

| File | Purpose |
|---|---|
| `backend/alembic/versions/064_skill_assets_table.py` | `CREATE TABLE skill_assets` + indexes, PgBouncer-safe (per-statement `op.execute()`) |
| `cli/flywheel_mcp/bundle.py` (or similar) | Pure-stdlib `materialize_skill_bundle(bytes) -> TemporaryDirectory` helper + path-traversal guard |

### Does NOT touch

- Frontend (no UI surface for asset bundles — server-to-CC only).
- MCP server process lifecycle / transport (still stdio).
- Existing `flywheel_fetch_skill_prompt` — orthogonal tool.
- Skill execution engine (`backend/services/skill_executor.py`) — assets are for **CC-side** execution, not server-side.
- User's local `~/.claude/skills/` directory — bundles go to ephemeral `/tmp`, never pollute `~/.claude`.

---

## What NOT to Add

| Do not add | Why |
|---|---|
| **Supabase Storage bucket for skills** (e.g., `skill-bundles` bucket) | Adds a second auth hop (service-role signed URL), a second network roundtrip, and two-places-to-keep-in-sync (DB row + Storage object) for what is a sub-MB payload today. `services/document_storage.py` pattern works for user documents (up to 500 GB) but is overkill here. Revisit only if any single bundle crosses ~20 MB. |
| **`tarfile` / `.tar.gz`** | Zip is already stdlib, has random access, handles Windows filenames better, and has no symlink-attack surface. No perf win from tar for sub-MB bundles. |
| **`zstandard`, `lz4`, `brotli`** or any 3rd-party compressor | DEFLATE (stdlib zip default) gives ~3-5× on Python source. A better ratio on sub-MB payload saves milliseconds — not worth a new dep. |
| **`python-frontmatter`** (already declared in backend deps but unused) | The existing `seed.py` uses `yaml.safe_load` + `_simple_yaml_parse` fallback and works fine. Don't introduce a second parser. |
| **`pydantic` model for the asset payload** on the wire | The payload is `{"bundle_b64": str, "sha256": str, "size": int, "format": str}` — four fields. A `TypedDict` or plain dict matches every other endpoint in `api_client.py` (all 44 methods return `dict`). |
| **A new MCP resource (not tool)** for bundles | MCP resources are addressable URIs, which brings resource-listing semantics, change notifications, caching subscriptions, etc. We want a **parameterized RPC call** (`skill_name -> bundle`), which is exactly what a tool is. Also: no other Flywheel MCP primitive is a resource — keep the surface uniform. |
| **Auto-download on MCP startup** | Lazy per-skill fetch only. Startup-time download would block MCP handshake on a multi-MB transfer if we ever have many skills. The temp-dir lifecycle per invocation is the right grain. |
| **Signing / signature verification of bundles** | `sha256` stored in DB is integrity-over-transport, not integrity-over-server-compromise. Bundle trust inherits from Bearer-token trust of the tenant's Flywheel API endpoint. Full code-signing is a different milestone (if ever). |
| **A `skills` subdomain / separate service** | Single FastAPI process handles it. One more endpoint on the existing `api/skills.py` router. |
| **WebSocket / SSE streaming for bundle download** | Sub-MB payload, one HTTP GET. SSE is already used for long-running skill runs (see `stream_run` in `api/skills.py:477-578`); that pattern doesn't apply here. |

---

## Versions (exact, verified)

| Component | Version | Verification |
|---|---|---|
| FastMCP (CLI/MCP server) | **3.2.2** installed, `>=3.2.2,<4` pinned; latest on PyPI is **3.2.4** | Verified local: `cli/.venv/lib/python3.12/site-packages/fastmcp/__init__.py` reports `3.2.2`. `File(path, data, format, name, annotations)` signature confirmed via `inspect.signature`. Pin range in `cli/pyproject.toml:39`. **Recommend: bump to `>=3.2.4,<4`** along with this milestone to pick up recent bytes-handling fixes (see FastMCP release notes mentioning "materialize generators before result conversion, handle bytes gracefully"). MEDIUM risk — no breaking changes across 3.2.x. |
| `supabase-py` (backend, currently unused for this path) | 2.28.3 on PyPI; backend pins `>=2.28.2` | Not needed for this milestone. Only relevant if we reverse direction and use Storage. |
| PostgreSQL `bytea` | 1 GB hard limit per value (PostgreSQL TOAST, 30-bit size) | [PostgreSQL docs](https://www.postgresql.org/docs/current/limits.html). Bundles are ~160 KB today — 4+ orders of magnitude of headroom. |
| Python stdlib: `zipfile`, `io.BytesIO`, `tempfile.TemporaryDirectory`, `hashlib.sha256`, `base64` | Ships with Python 3.10+ (CLI) / 3.12 (backend) | No version pinning needed — stdlib. `TemporaryDirectory(ignore_cleanup_errors=...)` requires 3.10+, already satisfied by both `requires-python` constraints. |
| Supabase Storage (**not used, reference only**) | 50 MB free / 500 GB Pro per-object | [Supabase file-limits docs](https://supabase.com/docs/guides/storage/uploads/file-limits) |
| Alembic | `>=1.14` (existing pin in `backend/pyproject.toml:9`) | No change. Use the existing per-statement `op.execute()` PgBouncer workaround (see `063_skill_protected_default.py`). |

---

## Confidence Assessment

| Claim | Confidence | Evidence |
|---|---|---|
| `bytea` column is the right storage layer for sub-MB bundles | **HIGH** | PostgreSQL 1 GB bytea limit verified in PG docs; flywheel-v2 already has 4 `LargeBinary` columns in production (`models.py:80, 402, 1981`, plus `profiles` api_key_encrypted); single-query atomicity matches the existing `skill_definitions` access pattern |
| FastMCP `File(data=bytes, format="zip")` works on our pinned version | **HIGH** | Verified via local `inspect.signature` on `fastmcp 3.2.2` in `cli/.venv`; confirmed via official FastMCP docs [gofastmcp.com/servers/tools](https://gofastmcp.com/servers/tools) |
| `tempfile.TemporaryDirectory` + `zipfile.ZipFile.extractall` is the right CC-side pattern | **HIGH** | Python stdlib; documented as the canonical secure pattern [Python docs](https://docs.python.org/3/library/tempfile.html#tempfile.TemporaryDirectory); matches OpenStack's secure-temp-files guidance |
| Reusing `get_skill_prompt` auth+tenant-access shape is correct | **HIGH** | Read the endpoint line-by-line (`api/skills.py:283-344`); the access-control logic is already factored cleanly and handles the tenant-override-vs-default case |
| PgBouncer DDL workaround still applies for the new migration | **HIGH** | Documented in user memory + `063_skill_protected_default.py:1-13`; pattern is in active use |
| Skill bundle sizes stay well under limits | **HIGH** for today (160 KB measured), **MEDIUM** for future growth (no projections exist) |
| Protected-skill asset endpoint should return 403 | **MEDIUM** | Logic-derived from Phase-95 + today's 063 migration, not explicitly specced anywhere. Flagged in PITFALLS research for roadmap discussion. |
| Bumping fastmcp to 3.2.4 has no breaking changes | **MEDIUM** | Semver suggests none; confirmed search results reference 3.2.x improvements only. Should be verified in the implementation phase via a smoke test. |

---

## Integration Summary for Planner

**Phase sketch (4 planner-sized chunks):**
1. **DB migration + model** — `skill_assets` table, `SkillAsset` ORM, Alembic migration using PgBouncer workaround.
2. **Seed pipeline extension** — `_build_bundle(entry_path) -> bytes` (zip of .py files, skip `SKILL.md`, skip `__pycache__`, skip `.pytest_cache`, skip `tests/` if we don't want to ship tests), sha256 skip-if-unchanged, upsert into `skill_assets`.
3. **Backend endpoint + tests** — `GET /api/v1/skills/{name}/assets`, copy auth shape from `get_skill_prompt`, decide 403-for-protected, integration tests.
4. **MCP tool + unpack helper + tests** — `flywheel_fetch_skill_assets` tool returning `File(...)`, `materialize_skill_bundle` helper with path-traversal guard, smoke test that full round-trips a real skill dir.

**Zero new dependencies.** Zero new frameworks. Zero new architecture. The only wire-format novelty is "first MCP tool in this server that returns binary content", and FastMCP's `File` helper handles the base64 wrapping transparently.

---

## Sources

- [PostgreSQL Limits (bytea 1 GB)](https://www.postgresql.org/docs/current/limits.html)
- [FastMCP Tools docs — binary content handling](https://gofastmcp.com/servers/tools)
- [FastMCP GitHub](https://github.com/jlowin/fastmcp)
- [Supabase Storage file-limits](https://supabase.com/docs/guides/storage/uploads/file-limits)
- [Python tempfile docs](https://docs.python.org/3/library/tempfile.html)
- [Python zipfile docs](https://docs.python.org/3/library/zipfile.html)
- [OpenStack secure-temp-files guidance](https://security.openstack.org/guidelines/dg_using-temporary-files-securely.html)
- Local codebase (HIGH-priority evidence):
  - `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/db/models.py` (lines 80, 402, 811-884, 1981 — existing `LargeBinary` + `SkillDefinition`)
  - `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/db/seed.py` (existing skill seed pipeline to extend)
  - `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/skills.py` (lines 283-344 — auth+tenant-access shape to copy)
  - `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/services/document_storage.py` (Supabase Storage reference pattern — not used here)
  - `/Users/sharan/Projects/flywheel-v2/cli/flywheel_mcp/server.py` (MCP tool registration pattern)
  - `/Users/sharan/Projects/flywheel-v2/cli/flywheel_mcp/api_client.py` (lines 43-75 — auth refresh + error handling to reuse)
  - `/Users/sharan/Projects/flywheel-v2/cli/flywheel_cli/auth.py` (credentials.json pattern)
  - `/Users/sharan/Projects/flywheel-v2/backend/alembic/versions/063_skill_protected_default.py` (PgBouncer DDL workaround pattern)
  - `/Users/sharan/Projects/flywheel-v2/cli/.venv/lib/python3.12/site-packages/fastmcp/utilities/types.py` (File class signature verified)
