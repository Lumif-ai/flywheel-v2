---
phase: 151-broker-dogfood-resilience
plan: 02
subsystem: infra
tags: [resilience, mcp, error-copy, regression-tests, tamper-auto-heal, offline-fallback, cli, python, fastmcp]

# Dependency graph
requires:
  - phase: 151-01
    provides: BundleCache.refresh(name?, *, fetcher) hook + CacheEntry tamper auto-delete + _has_any_cache_trace helper + BundleCacheError now actually raised on offline+stale path
  - phase: 150-mcp-tool-unpack-helper
    provides: BundleError taxonomy (BundleFetchError/BundleCacheError/BundleIntegrityError/BundleSecurityError) + flywheel_fetch_skill_assets MCP tool pattern + FastMCP ToolResult contract
  - phase: 148-assets-endpoint-fanout
    provides: GET /api/v1/skills/{name}/assets/bundle endpoint (called with bypass_cache=True by refresh tool)
provides:
  - cli/flywheel_mcp/errors.py — 6 locked user-facing error-string constants (7 counting 503 retry + terminal) as module-level names + ALL_ERROR_MESSAGES convenience list for parametrized regression tests
  - cli/flywheel_mcp/server.py::flywheel_refresh_skills MCP tool — signature (name: str | None = None) -> ToolResult, structured_content shape {evicted, refetched, tampered, per_skill}
  - BundleIntegrityError gains keyword-only `reason` override so raise sites can plug in ERR_CHECKSUM_TEMPLATE without forcing the materializer to import errors.py
  - cache.refresh() now performs pre-refresh tamper detection via _load_entry_from_index (auto-delete + stderr cache_entry_tampered line + status='tampered-healed' in per_skill) before calling fetcher
  - api_client.py raises ALL bundle errors with locked user-facing copy from errors.py (ERR_401/ERR_403/ERR_404_TEMPLATE/ERR_503_RETRY_TEMPLATE/ERR_503_TERMINAL/ERR_OFFLINE_EXPIRED)
  - ERR_503_RETRY_TEMPLATE stderr line now emitted before each pre-retry sleep (user sees "Retrying in 0.5s..." → pause → retry, not a silent gap)
affects: [151-03, 151-04, Phase 152 retirement]

# Tech tracking
tech-stack:
  added: []  # stdlib-only per CONTEXT lock; zero new runtime deps
  patterns:
    - Byte-exact regression tests with literal RHS (hard-coded expected string on RHS of ==, NOT the constant — prevents false-green tautology when constant drifts)
    - Dual-form invocation copy (underscored `flywheel_refresh_skills` for MCP-tool form in 404/503-terminal; hyphenated `flywheel refresh-skills` for CLI-subcommand form in checksum/offline-expired) — deliberate per CONTEXT
    - Tamper auto-heal via pre-refresh validation pass (attempt _load_entry_from_index before fetcher; BundleIntegrityError auto-deletes dir + stderr cache_entry_tampered line + refetch repopulates)
    - FastMCP deferred imports inside tool body (BundleCache, FlywheelClient) — matches flywheel_fetch_skill_assets pattern; keeps top-of-module import graph clean
    - Keyword-only reason override on BundleIntegrityError — raise sites customize user-facing copy without forcing base class to import errors.py (leaf-module invariant preserved)
    - Retry-loop stderr progress lines emitted BEFORE sleep (user sees backoff progress in real time, not post-hoc)

key-files:
  created:
    - cli/flywheel_mcp/errors.py
    - cli/tests/test_error_messages.py
    - cli/tests/test_refresh_skills.py
    - .planning/phases/151-broker-dogfood-resilience/151-02-SUMMARY.md
  modified:
    - cli/flywheel_mcp/api_client.py
    - cli/flywheel_mcp/bundle.py
    - cli/flywheel_mcp/cache.py
    - cli/flywheel_mcp/server.py

key-decisions:
  - Preserved CONTEXT's dual-form invocation copy (underscored MCP-tool form vs hyphenated CLI-subcommand form) — both are valid UX surface areas and normalizing would break the locked copy contract; added a dedicated `test_underscored_form_in_404_and_503_terminal` + `test_hyphenated_form_in_checksum_and_offline_expired` pair asserting form-placement is mutually exclusive
  - Added keyword-only `reason` override to BundleIntegrityError (plan allowed "add it with a sensible default") — preserves Phase 150 default shape with diagnostic SHA tail for operator forensics, while letting api_client.py + cache.py raise sites plug in ERR_CHECKSUM_TEMPLATE verbatim for byte-exact regression
  - Refresh tool's tamper-auto-heal path runs a PRE-refresh validation pass (`_load_entry_from_index` catching BundleIntegrityError) before calling fetcher — this is how SC4's "old dir gone + new dir exists + stderr line emitted" contract surfaces; without this pass the fetcher just overwrites without detecting that the cached bytes were tampered
  - ERR_503_RETRY_TEMPLATE emitted via sys.stderr.write BEFORE each pre-retry sleep (not AFTER) — matches CONTEXT's UX: user sees "Retrying in 0.5s..." then the pause, not silence followed by a stale status update
  - Byte-exact regression tests hard-code the full expected literal on RHS of `==` (plan's critical rule) — every `test_err_*_string_byte_exact` + the `test_all_error_messages_matches_individual_constants` meta-test triangulate drift detection from three angles (individual-constant literal, form-placement exclusivity, ALL_ERROR_MESSAGES lookup parity)
  - cache.refresh() preserves the `except Exception as exc:` fallback inside the per-skill loop even after adding pre-refresh tamper detection — prevents one offline skill from crashing the whole refresh walk (user wants to see which skills healed vs which are still errored)
  - Offline simulation uses `FLYWHEEL_API_URL=http://127.0.0.1:1` (RST-ing port) as CONTEXT specifies — combined with mocked `_client.get` raising httpx.ConnectError, this exercises the Plan 01 offline-fallback paths without depending on real network flakiness

patterns-established:
  - "Locked-copy regression pattern: every user-facing string lives in errors.py as a module-level constant + has a test asserting byte-exact equality against a hard-coded literal RHS. Two forms deliberately coexist (MCP-tool form + CLI-subcommand form); tests assert form-placement is mutually exclusive (a 404 message never contains the hyphenated form; a checksum message never contains the underscored form)."
  - "Tamper auto-heal via double-validation: cache.refresh() attempts _load_entry_from_index BEFORE calling fetcher; BundleIntegrityError auto-deletes the <sha>/ dir + drops index entry, then fetcher repopulates with authoritative bytes. Forensic trace line `cache_entry_tampered: skill=... old_sha=... authoritative_sha=... correlation_id=...` emitted to stderr for operator grep-ability."
  - "FastMCP tool registration pattern: @mcp.tool(output_schema=None) decorator → ToolResult return with structured_content envelope for metadata + optional content list for human-readable messages. BundleError / FlywheelAPIError caught at MCP boundary and surfaced as TextContent (not traceback) unless FLYWHEEL_DEBUG=1. Matches the flywheel_fetch_skill_assets pattern from Phase 150.3."

# Metrics
duration: 22min
completed: 2026-04-18
---

# Phase 151 Plan 02: Locked Error Messages + flywheel_refresh_skills MCP Tool Summary

**Ships the last two pieces of the Phase 151 resilience surface: (1) 6 locked user-facing error-message constants (ERR_401/ERR_403/ERR_404_TEMPLATE/ERR_503_RETRY_TEMPLATE/ERR_503_TERMINAL/ERR_CHECKSUM_TEMPLATE/ERR_OFFLINE_EXPIRED) wired into every bundle-error raise site in api_client.py + cache.py with byte-exact regression tests; and (2) the `flywheel_refresh_skills(name?)` MCP tool that force re-fetches cached bundles, auto-heals tampered entries with forensic stderr logging, and surfaces refresh results as ToolResult.structured_content. Plus the keyword-only `reason` override on BundleIntegrityError that lets the locked copy flow from raise sites into `str(exc)` verbatim.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-04-18T15:20Z
- **Completed:** 2026-04-18T15:42Z
- **Tasks:** 2
- **Files modified:** 4 (api_client.py, bundle.py, cache.py, server.py)
- **Files created:** 3 (errors.py 81 LOC, test_error_messages.py 382 LOC, test_refresh_skills.py 594 LOC) = 1057 LOC

## Accomplishments

- **6 locked user-facing error constants in `cli/flywheel_mcp/errors.py`** (7 counting 503 retry + terminal): ERR_401/ERR_403/ERR_404_TEMPLATE/ERR_503_RETRY_TEMPLATE/ERR_503_TERMINAL/ERR_CHECKSUM_TEMPLATE/ERR_OFFLINE_EXPIRED. All match CONTEXT §Error taxonomy byte-for-byte. CONTEXT's dual invocation-form copy preserved exactly: UNDERSCORED `flywheel_refresh_skills` (MCP-tool form) in 404+503-terminal; HYPHENATED `flywheel refresh-skills` (CLI-subcommand form) in checksum+offline-expired. `ALL_ERROR_MESSAGES` convenience list exports `[(id, msg), ...]` tuples pre-interpolated for parametrized regression tests.

- **`flywheel_refresh_skills(name: str | None = None) -> ToolResult` MCP tool** registered in server.py immediately after `flywheel_fetch_skill_assets` (matches critical directive's placement). Return shape per plan spec: `ToolResult.structured_content = {evicted: int, refetched: int, tampered: int, per_skill: list[dict]}` where each per_skill entry is `{name, old_sha, new_sha, status}` with status ∈ {refreshed, unchanged, new, tampered-healed, tampered, "error: ..."}. Stderr summary emits `OK: Refreshed N skills (M evicted, K tampered-auto-healed).` for no-arg and `OK: Refreshed <name>.` for per-skill. Tool delegates to `BundleCache.refresh(name, fetcher=FlywheelClient().fetch_skill_assets_bundle-bound)` per Plan 01's caller-injected-fetcher pattern (preserves the cache-doesn't-know-about-FlywheelClient invariant).

- **api_client.py error raise sites rewired to use locked copy:**
  - **401 terminal:** `BundleFetchError(name, 401, ERR_401)` after one-shot token refresh still returns 401
  - **403:** `BundleFetchError(name, 403, ERR_403)` (fail-fast, no retry — replaces Phase 150's "runs server-side only" copy)
  - **404:** `BundleFetchError(name, 404, ERR_404_TEMPLATE.format(name=name))` (interpolates skill name + UNDERSCORED form)
  - **503 retry stderr line:** `sys.stderr.write(ERR_503_RETRY_TEMPLATE.format(delay=delay) + "\n")` emitted BEFORE each pre-retry sleep (user sees backoff progress in real time)
  - **503 terminal:** `BundleFetchError(name, None, ERR_503_TERMINAL)` after 3 failed attempts (exhausts retry loop)
  - **Offline + expired cache:** `BundleCacheError(skill_name=name, reason=ERR_OFFLINE_EXPIRED)` — replaces Plan 01's close-enough placeholder with byte-exact CONTEXT copy
  - **Checksum:** cache.py's `_load_bundle_with_validation` passes `reason=ERR_CHECKSUM_TEMPLATE.format(skill=skill_name_hint)` to BundleIntegrityError (new keyword-only kwarg)

- **BundleIntegrityError extended with keyword-only `reason: str | None = None` kwarg** — preserves Phase 150's default shape (includes diagnostic SHA tail for operators) when `reason=None`, but allows raise sites to plug in the locked user-facing ERR_CHECKSUM_TEMPLATE verbatim. The materializer in bundle.py doesn't need to import errors.py (leaf-module invariant preserved). `self.reason` attribute exposed for introspection.

- **cache.refresh() now includes pre-refresh tamper detection:** before calling `fetcher(skill_name, bypass_cache=True)`, the method attempts `self._load_entry_from_index(skill_name)` which SHA-validates every cached bundle in the chain. On BundleIntegrityError, the loader has already auto-deleted the tampered `<sha>/` dir + dropped the index entry; refresh() emits the locked `cache_entry_tampered: skill=... old_sha=... authoritative_sha=... correlation_id=...` stderr line, increments `tampered_count`, and then calls fetcher to repopulate with authoritative bytes. Per-skill status is `tampered-healed` when both tamper-detected and refetched succeed. Preserves the `except Exception as exc:` fallback so one offline skill doesn't crash the whole walk.

- **34 new regression tests across two files** (cli/tests/test_error_messages.py 382 LOC / 24 tests + cli/tests/test_refresh_skills.py 594 LOC / 10 tests) — zero regressions on Plan 01 cache suite (18/18 still green) or Phase 150 bundle/MCP suites (15 bundle + 5 MCP contract tests still green).

## Test Results

**Full cli/tests/ suite:** `pytest tests/` → **104 passed / 6 skipped** (e2e opt-in) in 1.52s. Zero regressions vs Plan 01 baseline.

**Phase 151 resilience suite:** `pytest tests/test_cache.py tests/test_error_messages.py tests/test_refresh_skills.py -v` → **52 passed** (18 Plan 01 + 24 errors + 10 refresh) in 1.00s.

**Byte-exact constant tests (Plan 02):**
- `test_err_401_string_byte_exact` — PASS (literal RHS match)
- `test_err_403_string_byte_exact` — PASS
- `test_err_404_template_interpolates` — PASS (substitution + UNDERSCORED form)
- `test_err_503_retry_template_interpolates` — PASS
- `test_err_503_terminal_string_byte_exact` — PASS (UNDERSCORED form)
- `test_err_checksum_template_interpolates` — PASS (HYPHENATED form)
- `test_err_offline_expired_string_byte_exact` — PASS (HYPHENATED form)

**Form-placement exclusivity tests:**
- `test_underscored_form_in_404_and_503_terminal` — PASS (underscored present; hyphenated absent)
- `test_hyphenated_form_in_checksum_and_offline_expired` — PASS (hyphenated present; underscored absent)

**Raise-site integration tests:**
- `test_401_terminal_raise_uses_locked_message` — PASS (ERR_401 in str(exc))
- `test_403_raise_uses_locked_message` — PASS
- `test_404_raise_uses_locked_message_with_name` — PASS (name interpolated + UNDERSCORED form)
- `test_503_terminal_after_3_retries_uses_locked_message` — PASS (ERR_503_TERMINAL in str(exc) + 3 retry stderr lines)
- `test_checksum_raise_uses_locked_message` — PASS (str(exc) == ERR_CHECKSUM_TEMPLATE.format(skill=...) exactly)
- `test_offline_expired_raise_uses_locked_message` — PASS (ERR_OFFLINE_EXPIRED in str(exc) via FLYWHEEL_API_URL=http://127.0.0.1:1)

**Refresh tool tests (all 10 green):**
- `test_refresh_no_arg_walks_all_cached_skills` — PASS (3 skills → 3 GETs → refetched=3)
- `test_refresh_with_name_targets_single_skill` — PASS (only target hit, other 2 cached skills untouched)
- `test_refresh_empty_cache_noop` — PASS (refetched=0, evicted=0, tampered=0, zero GETs)
- `test_refresh_tampered_entry_auto_heal` — PASS (tampered dir GONE + new dir exists + stderr regex match + tampered=1)
- `test_refresh_per_skill_dict_shape` — PASS ({name, old_sha, new_sha, status} on every entry)
- `test_refresh_stderr_summary_format` — PASS (regex `OK: Refreshed \d+ skills \(\d+ evicted, \d+ tampered-auto-healed\)\.`)
- `test_refresh_per_skill_stderr_shorter_format` — PASS (regex `OK: Refreshed <name>\.`)
- `test_refresh_backend_down_propagates_error` — PASS (per_skill status="error: ...", no silent "0 refreshed")
- `test_offline_simulation_fresh_cache_serves_cached_bundle` — PASS (WARN + serve on stale cache + ConnectError)
- `test_offline_simulation_expired_cache_raises_locked_error` — PASS (BundleCacheError + ERR_OFFLINE_EXPIRED verbatim)

**MCP tool registration verification:**
- `asyncio.run(server.mcp.list_tools())` reports 31 tools, both `flywheel_refresh_skills` AND `flywheel_fetch_skill_assets` present
- `inspect.signature(server.flywheel_refresh_skills)` → `(name: 'str | None' = None) -> 'ToolResult'` (matches plan spec exactly)

**Regression guards:**
- `grep -c 'ERR_' cli/flywheel_mcp/api_client.py` → 14 references (well above the 6-site minimum from plan's verify criteria)
- Phase 150 tests: 15 bundle tests + 5 MCP contract tests all green; Plan 01 cache tests: 18/18 green
- Zero new runtime dependencies (stdlib-only per CONTEXT lock)

## Task Commits

Per `commit_strategy=per-plan`: ONE atomic commit for both tasks.

1. **Task 1:** errors.py + wire locked copy into api_client.py + BundleIntegrityError.reason override + test_error_messages.py (24 tests)
2. **Task 2:** flywheel_refresh_skills MCP tool + cache.refresh() pre-refresh tamper detection + test_refresh_skills.py (10 tests)

**Plan commit:** `PENDING` (this SUMMARY.md + STATE.md roll-up commit happens next)

## Decisions Made

All decisions followed plan. No architectural deviations (Rule 4 did NOT trigger).

- Kept CONTEXT's dual-form invocation copy verbatim (UNDERSCORED MCP-tool form vs HYPHENATED CLI-subcommand form) — both appear in distinct error classes per CONTEXT §Error taxonomy locked table. Added a pair of form-placement exclusivity tests to catch future drift where someone "normalizes" one form into the other.
- Added `reason: str | None = None` keyword-only kwarg to BundleIntegrityError — preserves Phase 150's default shape (includes diagnostic SHA tail for operators) while allowing raise sites to plug in the locked user-facing ERR_CHECKSUM_TEMPLATE.
- Moved tamper detection INTO cache.refresh() as a pre-fetcher pass (plan said "if a load during refresh raises BundleIntegrityError..." which required a load to exist in the refresh path — the original implementation only called fetcher and never loaded the cached bytes for validation). Auto-heal now works end-to-end: pre-refresh load detects tamper → dir auto-deleted → fetcher repopulates → per_skill status = 'tampered-healed'.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] cache.refresh() needed pre-refresh tamper-detection pass to satisfy SC4**
- **Found during:** Task 2 (writing test_refresh_tampered_entry_auto_heal)
- **Issue:** The plan's SC4 contract ("tampered dir GONE after refresh + new dir exists + stderr `cache_entry_tampered` line with old_sha/authoritative_sha/correlation_id + tampered count == 1") requires SHA validation of the CACHED bytes during refresh. Plan 01's original cache.refresh() only called the fetcher and never loaded cached bytes — so a tampered byte flipped in bundle.zip would go undetected: the fetcher would overwrite with authoritative bytes, the per_skill status would be 'new' (not 'tampered-healed'), and no `cache_entry_tampered` line would fire.
- **Fix:** Added a `self._load_entry_from_index(skill_name)` call inside cache.refresh() BEFORE the fetcher invocation; on BundleIntegrityError (raised by the cache's SHA-validate-on-load path) the loader has already auto-deleted the tampered dir + dropped the index entry. refresh() logs the locked `cache_entry_tampered: skill=... old_sha=... authoritative_sha=... correlation_id=...` stderr line, increments `tampered_count`, and then still calls fetcher (to complete the auto-heal). Per-skill status becomes 'tampered-healed' on successful refetch after tamper detection.
- **Files modified:** `cli/flywheel_mcp/cache.py` (+~30 LOC in refresh method)
- **Verification:** `test_refresh_tampered_entry_auto_heal` PASS — regex-matches stderr line shape + old_sha/authoritative_sha/correlation_id fields present + old dir gone + new dir exists + structured_content.tampered == 1 + per_skill status == 'tampered-healed'
- **Committed in:** single per-plan commit

**2. [Rule 3 — Blocking] Restored `except Exception as exc:` fallback inside cache.refresh() loop after adding pre-refresh tamper pass**
- **Found during:** Task 2 (first run of test_refresh_backend_down_propagates_error failed with `TypeError: 'NoneType' object is not subscriptable` because a BundleFetchError propagated up through cache.refresh() → server tool's `except BundleError` → returned ToolResult with only `content`, no `structured_content`)
- **Issue:** My rewrite of cache.refresh() inadvertently removed the `except Exception` catch-all around the fetcher call, which was needed to keep one offline-skill failure from crashing the whole refresh walk. CONTEXT specifies refresh should return a RefreshResult even when individual skills fail (per_skill entry gets `status: "error: <msg>"`), so the user sees exactly which skills healed vs errored.
- **Fix:** Restored the `except Exception as exc:` handler that records per-skill error status and continues the loop. Tamper detection remains as a separate earlier try/except block.
- **Files modified:** `cli/flywheel_mcp/cache.py` (+~10 LOC)
- **Verification:** `test_refresh_backend_down_propagates_error` now PASS — structured_content.refetched == 0, per_skill[0].status starts with "error:", no silent "0 refreshed" response
- **Committed in:** same single per-plan commit

**3. [Rule 1 — Bug] BundleFetchError(None, None, ERR_503_TERMINAL) initially used a plain `raise` after the retry loop exhausted — fixed to `raise ... from last_exc`**
- **Found during:** Task 1 (review during wire-up)
- **Issue:** The plan's `_do_get()` sentinel retry loop accumulated `last_exc` across retries but then did `assert last_exc is not None; raise last_exc`. Replacing this with the locked ERR_503_TERMINAL message meant losing the retry-context chaining. `raise ... from last_exc` preserves the cause chain for operators while surfacing the locked user-facing copy at the top.
- **Fix:** `raise BundleFetchError(name, None, ERR_503_TERMINAL) from last_exc`
- **Files modified:** `cli/flywheel_mcp/api_client.py` (1 LOC change)
- **Verification:** `test_503_terminal_after_3_retries_uses_locked_message` passes; no `assert last_exc is not None` gate needed (Python raises a clean TypeError if `last_exc` is None, which would indicate a logic bug elsewhere)
- **Committed in:** same single per-plan commit

---

**Total deviations:** 3 auto-fixed (all Rule 3 blocking or Rule 1 bug fixes). All are strictly implementation-level; zero scope creep or plan-spec changes.

## Issues Encountered

- FastMCP's `@mcp.tool` decorator wraps the decorated function in a Tool object — the docstring is accessed via `Tool.description`, not `function.__doc__`. Verified registration via `asyncio.run(server.mcp.list_tools())` returning 31 tools including `flywheel_refresh_skills`. `inspect.signature(server.flywheel_refresh_skills)` still works on the decorated function because FastMCP preserves the original callable attributes.
- `cache.refresh()` has a `target_names = [name] if name is not None else list(index.keys())` branch — if user passes a `name` that's not in the index yet, we still iterate once (correct behavior: refresh can warm a never-cached skill). Verified by `test_refresh_with_name_targets_single_skill`.

## User Setup Required

None — no external service configuration required. Plan 02 is purely internal (CLI library changes + MCP tool registration). Existing MCP server restart picks up the new `flywheel_refresh_skills` tool automatically on next startup.

## Next Phase Readiness

**Plan 03 (Dogfood + Latency Baseline) receives:**
- `flywheel_refresh_skills(name?)` MCP tool available for cache-priming before the 5-step broker dogfood (can pre-warm broker-parse-contract + 4 siblings). Dogfood script can call it to guarantee fresh bytes before offline-mode simulation.
- All 6 locked error messages are regression-tested byte-exact — Plan 03's dogfood smoke failures will now produce distinct actionable strings instead of generic "something went wrong" copy. Offline-simulation test in Plan 03 can assert `ERR_OFFLINE_EXPIRED` appears verbatim in stderr.
- `cache_entry_tampered: skill=... old_sha=... authoritative_sha=... correlation_id=...` stderr forensic line is live — Plan 03's dogfood log capture will surface any integrity drift between prod authoritative bytes and local cache.
- Pre-refresh tamper-detection pass in `cache.refresh()` proves the belt-and-suspenders contract from Phase 150 CONTEXT: cache SHA-validate on load + materializer SHA-validate before extract = two independent integrity gates.

**Plan 04 (Latency Regression Baseline) receives:**
- ERR_503_RETRY_TEMPLATE stderr line emitted during 3x backoff is grep-able for measure_latency.py's tail analysis — any p99 cold anomaly can be cross-referenced against retry-count from this line.
- ToolResult.structured_content shape for `flywheel_refresh_skills` is stable — measure_latency.py can warm cache via programmatic call (`flywheel_refresh_skills.fn(name="broker-parse-contract")`) if benchmark needs a known-fresh-cache baseline.

**No blockers for Plan 03.** Phase 151 resilience surface area is complete (cache foundation from Plan 01 + error taxonomy lock + refresh tool from Plan 02). Dogfood can proceed.

## Self-Check: PASSED

- `cli/flywheel_mcp/errors.py` exists: FOUND (81 LOC)
- `cli/tests/test_error_messages.py` exists: FOUND (382 LOC, 24 tests)
- `cli/tests/test_refresh_skills.py` exists: FOUND (594 LOC, 10 tests)
- `.planning/phases/151-broker-dogfood-resilience/151-02-SUMMARY.md` exists: FOUND (this file)
- ERR_401/ERR_403/ERR_404_TEMPLATE/ERR_503_RETRY_TEMPLATE/ERR_503_TERMINAL/ERR_CHECKSUM_TEMPLATE/ERR_OFFLINE_EXPIRED all exported from errors.py: VERIFIED via `python -c "from flywheel_mcp.errors import *"` success + ALL_ERROR_MESSAGES has 7 entries
- 6 locked constants match CONTEXT byte-for-byte: VERIFIED via 7 byte-exact tests (all pass)
- UNDERSCORED vs HYPHENATED form placement correct: VERIFIED via 2 form-exclusivity tests (all pass)
- Every ERR_ constant appears at raise site in api_client.py: VERIFIED (grep count 14 references)
- cache.py BundleIntegrityError raise uses ERR_CHECKSUM_TEMPLATE: VERIFIED via test_checksum_raise_uses_locked_message (str(exc) == expected exactly)
- flywheel_refresh_skills MCP tool registered: VERIFIED via server.mcp.list_tools() includes it + get_tool('flywheel_refresh_skills') returns Tool object
- Return shape ToolResult{structured_content:{evicted, refetched, tampered, per_skill}}: VERIFIED via test_refresh_per_skill_dict_shape + all refresh tests asserting sc["refetched"] / sc["tampered"] / sc["evicted"] / sc["per_skill"]
- Tamper auto-heal + stderr line + correlation_id: VERIFIED via test_refresh_tampered_entry_auto_heal regex match on `cache_entry_tampered: skill=... old_sha=<8+ hex> authoritative_sha=<8+ hex> correlation_id=\S+`
- Offline sim FLYWHEEL_API_URL=http://127.0.0.1:1: VERIFIED via test_offline_simulation_fresh_cache_serves_cached_bundle + test_offline_simulation_expired_cache_raises_locked_error (both use monkeypatch.setenv + httpx.ConnectError mock)
- Zero Plan 01 regressions: VERIFIED (`pytest tests/test_cache.py` → 18 passed)
- Zero Phase 150 regressions: VERIFIED (`pytest tests/test_bundle.py tests/test_mcp_assets_tool.py` → 15 + 5 passed + 6 e2e skipped)
- Full cli suite: 104 passed / 6 skipped — VERIFIED

---
*Phase: 151-broker-dogfood-resilience*
*Completed: 2026-04-18*
