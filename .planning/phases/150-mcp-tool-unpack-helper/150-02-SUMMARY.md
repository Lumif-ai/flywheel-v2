---
phase: 150-mcp-tool-unpack-helper
plan: 02
subsystem: cli

tags: [cli, mcp, bundle, materializer, zip-slip, sha256, sys-path, contextmanager, stdlib-only]

# Dependency graph
requires:
  - phase: 150-01
    provides: GET /api/v1/skills/{name}/assets/bundle fanout endpoint + {skill, deps, rollup_sha, bundles:[{name, size, bundle_b64, sha256}]} wire shape + byte-identity guarantee across DB -> server -> b64 -> wire

provides:
  - flywheel_mcp.bundle module with materialize_skill_bundle context manager
  - Four-class exception taxonomy rooted at BundleError: BundleFetchError, BundleIntegrityError, BundleSecurityError, BundleCacheError
  - _safe_extract helper with Path.resolve().is_relative_to() traversal guard + defensive backslash rejection
  - FlywheelClient.fetch_skill_assets_bundle method with 3x exp-backoff retry, one-shot 401 refresh, and terminal 4xx -> BundleFetchError mapping
  - Verify-before-extract SHA-256 ordering (zip bombs & tampered archives halt before zipfile construction)
  - sys.path lifecycle with .remove()-by-value tolerance for user mutation
  - 15 unit tests (14 planned + 1 bonus exception-hierarchy sanity) covering success, tamper, 4 zip-slip variants, cleanup on exit & exception, sys.path restore, fetch-error propagation, 401 one-shot refresh

affects: [150-03, 151, 152]

# Tech tracking
tech-stack:
  added: []  # zero new third-party dependencies; stdlib + existing httpx/FlywheelClient only
  patterns:
    - Four-class exception taxonomy defined up-front (BundleCacheError shipped as Phase 152 placeholder to avoid API break)
    - Verify-before-extract: hashlib.sha256 re-hash compared to server-provided SHA BEFORE zipfile.ZipFile(...) constructor
    - _safe_extract separation: traversal guard lives in helper, not inlined in materializer (architectural guardrail)
    - sys.path.remove() by value not by index (tolerant to user mutation; ValueError swallowed so original exception propagates)
    - TemporaryDirectory WITHOUT ignore_cleanup_errors (SC5 demands zero-byte invariant; silent cleanup failures would mask a leak)
    - io.BytesIO wrapper on zipfile so malformed bundle never leaves partial tempfile on disk
    - Defensive backslash rejection in _safe_extract (POSIX-safe but cross-platform fail-closed against Windows-separator attacks)
    - Hand-rolled 3x fixed-schedule retry (0.5s/1s/2s) vs tenacity/httpx-retries: 10 LOC vs a new dep

key-files:
  created:
    - cli/flywheel_mcp/bundle.py (~190 LOC: 4 exception classes, _safe_extract, materialize_skill_bundle)
    - cli/tests/test_bundle.py (~460 LOC: 15 tests covering full contract)
    - .planning/phases/150-mcp-tool-unpack-helper/150-02-SUMMARY.md (this file)
  modified:
    - cli/flywheel_mcp/api_client.py (+123 LOC: fetch_skill_assets_bundle method + base64/time imports)

key-decisions:
  - "REQUIREMENTS.md path lock honored: cli/flywheel_mcp/bundle.py (NOT cli/src/flywheel/bundle.py from CONTEXT). Matches actual package layout at cli/pyproject.toml:packages and Plan 01's path correction."
  - "Verify-before-extract ordering is enforced via test_integrity_check_detects_tamper which monkeypatches zipfile.ZipFile to count invocations and asserts call_count == 0 on SHA mismatch. This is a hard architectural invariant, not just a comment."
  - "_safe_extract helper pattern over inline guard: the structural spot-check in verify step 3 assertively checks that is_relative_to is NOT in materialize_skill_bundle.getsource() and IS in _safe_extract.getsource() — prevents 'convenience' regressions where a future editor inlines the check."
  - "Backslash rejection added to _safe_extract as a pre-resolve check: on POSIX, `..\\..\\evil.exe` is a safe literal filename (backslashes are not separators), but on Windows it would escape. Reject entries with backslashes unconditionally — Phase 147 deterministic seeds never ship backslash filenames, so this is fail-closed with zero legitimate-bundle impact."
  - "401 refresh is exactly one-shot: inside fetch_skill_assets_bundle, after the initial _do_get() returns 401, _ensure_token() runs once, _do_get() runs once more. Still-401 triggers clear_credentials + BundleFetchError with 'flywheel login' hint. No recursion, no loop. Test asserts get_token called exactly 2x and HTTP get called exactly 2x in the fetch path."
  - "BundleCacheError shipped empty in Phase 150 — placeholder so Phase 152's cache layer can extend the class without breaking any imports or isinstance checks that Phase 151 might introduce. Defined at module top alongside its siblings for discoverability."
  - "No ignore_cleanup_errors on TemporaryDirectory — SC5 requires zero bytes remain on disk; silent cleanup failures would mask a real leak. Plan 02's test_no_bytes_under_tmp_after_exit asserts the /tmp/flywheel-skill-* glob stays bounded by pre-test baseline."
  - "Bundle bytes ship VERBATIM through the client — base64.b64decode in api_client returns raw bytes, passed unchanged to materialize_skill_bundle which re-hashes them. Preserves Phase 147 byte-determinism / Phase 149 captured SHA / Plan 01 byte-identity contract end-to-end."
  - "Exception hierarchy rooted at BundleError so callers can catch all bundle-delivery errors with a single except clause — test_exception_hierarchy_rooted_at_bundle_error enforces this structurally (issubclass check on every concrete class)."
  - "Deferred FlywheelClient import in materialize_skill_bundle: the import happens at enter-time (inside the @contextmanager function body), not at module load. Prevents a circular import where bundle.py's exception classes are imported by api_client.py."

patterns-established:
  - "Client-side materializer contract: FlywheelClient returns (metadata_dict, bundles_list) where bundles_list is [(name, sha256_hex, raw_bytes)] in topological order. Bytes are verbatim from wire; SHA verification is the caller's responsibility."
  - "Zip-slip defense: Path.resolve().is_relative_to(root) for the .. / absolute-path vectors, PLUS explicit backslash rejection for the Windows-separator vector. 4 attack variants covered; test parametrization makes it trivial to add more."
  - "Context manager with sys.path lifecycle: insert(0, ...) INSIDE try, remove() BY VALUE in finally, ValueError swallowed. User code can replace sys.path wholesale without breaking exit."

# Metrics
duration: ~5min
completed: 2026-04-18
---

# Phase 150 Plan 02: Client Materializer + Exception Taxonomy Summary

**Client-side `materialize_skill_bundle` context manager with SHA-256 verify-before-extract ordering, path-traversal-safe extraction via `_safe_extract` + `Path.is_relative_to` guard, four-class exception taxonomy rooted at `BundleError`, `FlywheelClient.fetch_skill_assets_bundle` with 3x exp-backoff retry + one-shot 401 refresh, and 15 hermetic unit tests covering success, tamper, 4 zip-slip variants, cleanup on exit + exception, sys.path restoration, and fetch-error propagation. Zero new dependencies — stdlib + existing httpx/FlywheelClient only.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-18 07:11:19Z
- **Completed:** 2026-04-18 07:16:30Z
- **Tasks:** 2 (both complete)
- **Files:** 3 created, 1 modified

## Public API Surface

### Exception classes (all subclass `BundleError`)

```python
class BundleFetchError(skill_name: str, status_code: int | None, message: str):
    # HTTP/transport-level failure. Raised after retry exhaustion or on
    # terminal 4xx (401-post-refresh, 403, 404, 429, etc).
    # User message: "<message> (skill=<name>, status=<code>)"

class BundleIntegrityError(skill_name: str, expected_sha: str, actual_sha: str):
    # SHA-256 mismatch on received bytes. Raised BEFORE zipfile.ZipFile(...)
    # is constructed — zip-bomb + malformed-archive protection.
    # User message: "Bundle integrity check failed for <name>. Run
    #  `flywheel refresh-skills` to re-fetch, or contact support if this
    #  persists. (expected sha256=<short>..., got sha256=<short>...)"

class BundleSecurityError(skill_name: str, entry_path: str):
    # Zip entry escapes bundle root. Single malicious entry aborts the
    # entire bundle (fail-closed).
    # User message: "Refused to extract <name>: entry '<path>' escapes
    #  bundle root."

class BundleCacheError(skill_name: str, reason: str):
    # Phase 152 offline-cache placeholder. NOT raised in Phase 150;
    # shipped empty so Phase 152 can extend without breaking API.
```

### `materialize_skill_bundle(name: str) -> Iterator[Path]`

Context manager. On enter: fetches bundle chain via `FlywheelClient.fetch_skill_assets_bundle`, SHA-verifies every bundle BEFORE extraction, extracts each zip (library-first, consumer-last) into a single `TemporaryDirectory`, and prepends `sys.path`. On exit (success OR exception): pops `sys.path` entry and cleans the temp dir.

Yields: `pathlib.Path` to the temp root (also `sys.path[0]` during the with-block).

```python
with materialize_skill_bundle("broker-parse-contract") as tmp:
    # tmp is an absolute pathlib.Path; contains flattened library +
    # consumer contents. sys.path[0] == str(tmp).
    from api_client import post
    post("/broker/projects/abc-123/analyze")
# On exit: tmp deleted, sys.path[0] restored to prior value.
```

### `FlywheelClient.fetch_skill_assets_bundle(name: str) -> tuple[dict, list[tuple[str, str, bytes]]]`

- Calls `GET /api/v1/skills/{name}/assets/bundle`.
- 3x exponential backoff (0.5s/1s/2s) on network errors + 5xx.
- One-shot 401 refresh: initial 401 -> `_ensure_token()` -> retry once. Still-401 -> clear credentials + raise `BundleFetchError(status_code=401, "Session expired. Run `flywheel login` and retry.")`.
- 403 -> `BundleFetchError("This skill runs server-side only and does not ship assets.")`.
- 404 -> `BundleFetchError("Skill '<name>' not found. Check the skill name for typos.")`.
- Returns `(metadata, bundles)` where metadata = `{"skill", "deps", "rollup_sha"}` and bundles = `[(name, sha256_hex, raw_bytes), ...]` in topological order.
- SHA verification is NOT done in the client — raw bytes + server-reported SHA flow to the materializer which re-hashes.

### `_safe_extract(zf: zipfile.ZipFile, dest: Path, skill_name: str) -> None`

Internal helper. Before `zf.extractall(dest)`: iterates `zf.infolist()`, rejects any entry containing a backslash (cross-platform defense), resolves `(dest / entry.filename).resolve()` and verifies it `.is_relative_to(dest)`. Single malicious entry aborts whole extraction via `BundleSecurityError`.

## Test Results

| # | Test | Result |
|---|------|--------|
| 1 | `test_success_single_bundle_extracts_and_imports` | PASS |
| 2 | `test_multi_bundle_flat_merge_dep_first` | PASS |
| 3 | `test_integrity_check_detects_tamper` (zipfile call_count == 0) | PASS |
| 4 | `test_path_traversal_rejected[dotdot]` (`../etc/passwd`) | PASS |
| 5 | `test_path_traversal_rejected[absolute]` (`/etc/passwd`) | PASS |
| 6 | `test_path_traversal_rejected[nested]` (`subdir/../../etc/passwd`) | PASS |
| 7 | `test_path_traversal_rejected[windows_sep]` (`..\\..\\evil.exe`) | PASS |
| 8 | `test_tempdir_deleted_after_normal_exit` | PASS |
| 9 | `test_tempdir_deleted_after_exception` | PASS |
| 10 | `test_sys_path_restored_on_exception` | PASS |
| 11 | `test_sys_path_tolerates_user_mutation` | PASS |
| 12 | `test_no_bytes_under_tmp_after_exit` (/tmp glob invariant) | PASS |
| 13 | `test_fetch_error_propagates` (no tempdir on BundleFetchError) | PASS |
| 14 | `test_401_refresh_one_shot_then_raise` (get_token x2, get x2) | PASS |
| 15 | `test_exception_hierarchy_rooted_at_bundle_error` (bonus) | PASS |

**Summary: 15/15 passing. Zero regressions vs Plan 01 baseline (47/47 across the full cli/tests suite).**

Runtime: 0.09s for `cli/tests/test_bundle.py -v` (hermetic — no network, no DB, no I/O outside tempfile).

## Task Commits

Single atomic commit per `commit_strategy=per-plan`:

- **Plan 02 (Task 1 + Task 2 combined)** — see `## Self-Check` below for commit hash (committed after this SUMMARY is written + state advance).

## Files Created/Modified

**Created:**
- `cli/flywheel_mcp/bundle.py` (~190 LOC)
  - Four exception classes with the documented messages from CONTEXT.md
  - `_safe_extract` helper: backslash reject + `is_relative_to` resolve-guard
  - `materialize_skill_bundle` context manager: deferred FlywheelClient import, verify-before-extract, sys.path lifecycle with `.remove()`-by-value, `TemporaryDirectory` auto-cleanup
  - `__all__` exposes all 4 exception classes + `BundleError` root + `materialize_skill_bundle`
- `cli/tests/test_bundle.py` (~460 LOC)
  - `_isolate_credentials` autouse fixture (mirrors `test_auth.py` pattern): redirects credential paths to per-test tmp dir, stubs `flywheel_mcp.api_client.get_token` so `FlywheelClient()` constructor succeeds without creds
  - `_build_deterministic_bundle` helper matching Phase 147 seed contract (sorted entries, fixed epoch, `external_attr = 0o644 << 16`)
  - `_evil_zip` helper for the 4 path-traversal variants
  - `_FakeClient` stand-in for `FlywheelClient` (avoids network + refresh plumbing)
  - 15 test functions covering success, tamper (with zipfile call_count==0 assertion), 4 zip-slip variants (parametrized), 2 cleanup-invariant tests, 2 sys.path lifecycle tests, 1 fetch-error propagation test, 1 401-one-shot test, 1 exception-hierarchy sanity
- `.planning/phases/150-mcp-tool-unpack-helper/150-02-SUMMARY.md` — this file

**Modified:**
- `cli/flywheel_mcp/api_client.py`
  - Imports: added `base64`, `time`
  - New method `fetch_skill_assets_bundle(name)` inserted after `fetch_skill_prompt` at the same indent level
  - 3x exponential backoff in an inner `_do_get()` helper: schedule `[0.0, 0.5, 1.0, 2.0]` yielding 4 attempts total (initial + 3 retries). Retries on `httpx.RequestError` + `status_code >= 500`.
  - 401 path: after `_do_get()` returns 401, call `_ensure_token()` once, then `_do_get()` once more. Still-401 -> `clear_credentials()` + `BundleFetchError(401, "Session expired. Run `flywheel login` and retry.")`.
  - 403/404 terminal mapping with actionable messages matching CONTEXT.md wording.
  - Generic 4xx fallback with response body snippet.
  - Success parses `body["bundles"]` into `[(name, sha256, base64.b64decode(bundle_b64)), ...]` and returns `(metadata, bundles)`.
  - Deferred `from flywheel_mcp.bundle import BundleFetchError` inside the method body to avoid any possibility of circular-import surprises.

## Decisions Made

See frontmatter `key-decisions` for the full list (10 decisions). Most load-bearing:

1. **Path correction locked: `cli/flywheel_mcp/bundle.py`** — matches Plan 01's path decision and the actual `cli/pyproject.toml` `packages = ["flywheel_cli", "flywheel_mcp"]` layout. Ignored CONTEXT.md's `cli/src/flywheel/bundle.py` reference (no `src/` subdirectory exists).
2. **Verify-before-extract enforced structurally, not just by convention** — `test_integrity_check_detects_tamper` monkeypatches `zipfile.ZipFile` to count constructor invocations and asserts the counter is `0` when SHA mismatches. A future change that accidentally reverses the order (or adds a zipfile call before the SHA check) will fail the test immediately.
3. **_safe_extract helper pattern is an architectural guardrail** — verify step 3 positively asserts `is_relative_to` is NOT in `materialize_skill_bundle.getsource()` and step 4 asserts it IS in `_safe_extract.getsource()`. This prevents future refactors from inlining the check (which would couple the traversal guard to the materializer and make it harder to reason about).
4. **Backslash rejection is defensive, not strictly necessary on POSIX** — on macOS/Linux, `..\\..\\evil.exe` is a safe literal filename because `\\` is not a separator. On Windows, the same string would traverse. Rejecting backslash filenames unconditionally is fail-closed, costs nothing (no legitimate Phase 147 bundle has backslash filenames — the sorted-deterministic seed pipeline uses forward slashes), and closes a cross-platform attack vector.
5. **401 handling is exactly one-shot** — the test asserts `get_token` is called exactly 2x (initial + one refresh) and `_client.get` is called exactly 2x. No infinite loop possible (Pitfall 9 guard).
6. **BundleCacheError shipped empty** — defined with `__init__(skill_name, reason)` matching the Phase 152 cache-layer spec. Having the class in the public API now means Phase 152 can raise `BundleCacheError(name, "stale cache")` etc. without `from flywheel_mcp.bundle import BundleCacheError` becoming a new public-API addition (it's already there).
7. **Bundle bytes ship VERBATIM through the client path** — `base64.b64decode(entry["bundle_b64"])` in `fetch_skill_assets_bundle` returns the raw zip bytes, which flow unchanged to `materialize_skill_bundle` which then re-hashes via `hashlib.sha256(bundle_bytes).hexdigest()`. No re-serialization, no intermediate buffer. Preserves Phase 147 byte-determinism through the whole pipeline.

## Deviations from Plan

**None — plan executed exactly as written, with two minor clarifications noted below.**

**Clarification 1 (structural only):** The plan said "14 unit tests". The file contains 15 test functions because I added `test_exception_hierarchy_rooted_at_bundle_error` as a cheap sanity check that all four concrete exception classes subclass `BundleError`. This aligns with the phase-level verification step 3 ("exception class hierarchy matches CONTEXT.md taxonomy") and turns it from a manual shell assertion into a persistent regression guard. Test count: 14 planned + 1 bonus = 15 total. All 15 pass.

**Clarification 2 (verification note):** The plan's verification step 3 asserts `'is_relative_to' not in materialize_skill_bundle.getsource()`. The plan's verification step 4 asserts `'is_relative_to' in _safe_extract.getsource()`. Both still pass as worded. The plan's phase-level verification step 4 ("grep -c 'is_relative_to' cli/flywheel_mcp/bundle.py returns 1") needed a minor note: the actual count is 2 (one in a docstring reference inside `_safe_extract`, one in the actual code). That's not a "duplicated guard" — it's one executable check plus one doc mention. The architectural intent (single source of truth for the guard logic) is preserved and verified by the code-level structural checks in steps 3 and 4.

## Issues Encountered

**1. `pytest` not in `cli/.venv`.** Initial test run failed with `No module named pytest`. Ran `./cli/.venv/bin/python -m ensurepip` then `-m pip install pytest` (pytest-9.0.3). No change to `pyproject.toml` — this is a dev-time dep, not a runtime dep. Zero new runtime third-party dependencies introduced.

**2. Windows-separator test initially failed on macOS.** First iteration of `_safe_extract` used only `Path.resolve().is_relative_to()`, which correctly handled POSIX traversal but let `..\\..\\evil.exe` through as a literal filename (since backslash is not a separator on POSIX). Fix: added an explicit backslash-in-filename reject as the first check in `_safe_extract`, raised `BundleSecurityError` before the resolve step. Pure defensive addition — cost-free on legitimate bundles (Phase 147 never ships backslash filenames), closes the Windows attack surface.

**3. 401 test `_client.headers["Authorization"] = ...` on plain Mock failed.** `mock.Mock()` doesn't support item assignment on auto-generated attributes; `mock.MagicMock()` does. Additionally, `FlywheelClient.__init__` calls `get_token` once on construction, which inflated the `token_calls["n"] == 2` assertion to `3`. Fix: (a) switched the replacement client to `mock.MagicMock(get=get_mock)`; (b) reset `token_calls["n"] = 0` immediately after `FlywheelClient()` construction so the assertion measures only fetch-path invocations. Also returned the same stub token from `_counting_get_token` so `_ensure_token`'s "token changed" branch (which writes to `_client.headers`) doesn't fire — keeps the test focused on the 401-loop shape.

## Self-Check

**Files created:**
- FOUND: /Users/sharan/Projects/flywheel-v2/cli/flywheel_mcp/bundle.py
- FOUND: /Users/sharan/Projects/flywheel-v2/cli/tests/test_bundle.py
- FOUND: /Users/sharan/Projects/flywheel-v2/.planning/phases/150-mcp-tool-unpack-helper/150-02-SUMMARY.md (this file)

**Files modified:**
- FOUND: /Users/sharan/Projects/flywheel-v2/cli/flywheel_mcp/api_client.py (+123 LOC; `fetch_skill_assets_bundle` method present, `base64` + `time` imports added)

**Test results:**
- `cli/tests/test_bundle.py`: 15 passed, 0 failed (0.09s)
- `cli/tests/` full suite: 47 passed, 0 failed (0.11s) — zero regressions vs Plan 01 baseline

**Structural verification:**
- `materialize_skill_bundle.getsource()` contains `hashlib.sha256` (verify-before-extract): OK
- `materialize_skill_bundle.getsource()` does NOT contain `is_relative_to` (guard architecturally lives in helper): OK
- `_safe_extract.getsource()` contains both `is_relative_to` and `.resolve()`: OK
- `flywheel_mcp.bundle.__all__` == `['BundleCacheError', 'BundleError', 'BundleFetchError', 'BundleIntegrityError', 'BundleSecurityError', 'materialize_skill_bundle']`: OK
- All four exception classes subclass `BundleError`: OK
- `cli/pyproject.toml` unchanged (zero new runtime deps): OK

**## Self-Check: PASSED**

## SC Coverage (Phase 150 ROADMAP, Plan 02 portion)

| SC | Description | Status |
|----|-------------|--------|
| SC1 | Client end-to-end fetch-verify-extract pipeline | CODE COMPLETE — unit tests cover the contract; live prod smoke is Plan 03's job |
| SC2 | Dual SHA-256 verification (client-side re-hash) | COMPLETE — `test_integrity_check_detects_tamper` proves SHA mismatch raises BundleIntegrityError BEFORE zipfile constructor runs |
| SC3 | Path-traversal protection | COMPLETE — 4 parametrized tests cover `../etc/passwd`, `/etc/passwd`, `subdir/../../etc/passwd`, `..\\..\\evil.exe` |
| SC4 | Full error taxonomy (4 classes) | COMPLETE — all 4 classes defined, all subclass BundleError, `test_exception_hierarchy_rooted_at_bundle_error` structurally enforces |
| SC5 | Zero bytes remain on disk post-exit | COMPLETE — `test_tempdir_deleted_after_normal_exit`, `test_tempdir_deleted_after_exception`, `test_no_bytes_under_tmp_after_exit` (glob invariant), no `ignore_cleanup_errors=True` anywhere |

All 5 Plan-02-scoped ROADMAP SCs GREEN. Plan 03 (MCP tool registration + live end-to-end prod smoke) is the remaining work for Phase 150 completion.

## Next Phase Readiness

**Plan 03 inputs ready:**
- `from flywheel_mcp.bundle import materialize_skill_bundle` works from any skill Python.
- `materialize_skill_bundle(name)` is a `@contextmanager` yielding `pathlib.Path`; call pattern is `with materialize_skill_bundle("broker-parse-contract") as tmp: ...`.
- 4 exception classes exposed at module top; catch-all is `except BundleError: ...`.
- `FlywheelClient.fetch_skill_assets_bundle(name)` is the single HTTP call path; both the MCP tool and the materializer share it (DRY across the consumer surfaces).
- Wire contract with Plan 01 byte-verified end-to-end: `base64.b64decode(bundle_b64)` -> raw zip bytes -> `hashlib.sha256(...).hexdigest()` == `sha256` field.

**State of the codebase after Plan 02:**
- `cli/flywheel_mcp/bundle.py` is the single source of truth for the client materializer and its exceptions.
- `cli/flywheel_mcp/api_client.py::FlywheelClient.fetch_skill_assets_bundle` is the HTTP call path.
- No MCP tool is registered yet — that's Plan 03.
- No broker SKILL.md has been rewritten to use the new path — that's Phase 151 (CC-as-Brain / Broker Dogfood).
- Live prod smoke has not been run — Plan 03's job.

**Handoff note to Plan 03:**
1. **Register the MCP tool** in `cli/flywheel_mcp/server.py` at the same level as `flywheel_fetch_skill_prompt`. Signature per RESEARCH.md Pattern 1:
   ```python
   @mcp.tool(output_schema=None)
   def flywheel_fetch_skill_assets(name: str) -> ToolResult:
       client = FlywheelClient()
       metadata, bundles = client.fetch_skill_assets_bundle(name)
       files = [
           File(data=b, format="zip", name=f"{skill_name}.zip")
           for (skill_name, _sha, b) in bundles
       ]
       return ToolResult(
           content=files,
           structured_content={
               "skill": metadata["skill"],
               "deps": metadata["deps"],
               "shas": {name: sha for (name, sha, _) in bundles},
               "rollup_sha": metadata["rollup_sha"],
           },
       )
   ```
   Note: use `ToolResult` (not the CONTEXT-locked `tuple[dict, list[File]]` — RESEARCH Pitfall 5 flagged tuple returns as not-FastMCP-supported).
2. **Catch `BundleError` at the MCP-tool boundary** and re-raise as `FlywheelAPIError` (or equivalent MCP-friendly error) so Claude Code sees a clean error message without a Python traceback. Respect the `FLYWHEEL_DEBUG=1` env var to surface full tracebacks when set.
3. **Live prod smoke assertions** (Plan 03's verification):
   - `with materialize_skill_bundle("broker-parse-contract") as tmp:` against prod Supabase succeeds.
   - `(tmp / "api_client.py").exists()` (broker library contents).
   - Post-exit: `not tmp.exists()`.
   - `sys.path` restored to prior value post-exit.
   - MCP tool returns `ToolResult` with correct `structured_content` shape and `content=[File(..., format="zip")]` list matching `bundles[]` topological order.
4. **No breaking changes to Plan 02 surface** — the public API (`materialize_skill_bundle` + 4 exception classes + `__all__`) is locked. If Plan 03 needs richer metadata (e.g. skill name, deps list), it can read `client.fetch_skill_assets_bundle` directly from the tool and pass whatever subset to `structured_content`.

---
*Phase: 150-mcp-tool-unpack-helper*
*Completed: 2026-04-18*
