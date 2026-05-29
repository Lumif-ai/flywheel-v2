---
phase: 148-backend-asset-endpoint
plan: 01
subsystem: api
tags: [fastapi, slowapi, base64, bytea, pydantic-v2, sqlalchemy-async, skill-assets]

# Dependency graph
requires:
  - phase: 146-schema-foundation
    provides: skill_assets table (bundle bytea, bundle_sha256, bundle_size_bytes, bundle_format, updated_at) + SkillAsset ORM model + 1:1 SkillDefinition.asset relationship + uq_skill_assets_skill_id unique INDEX
  - phase: 147-seed-pipeline-extension
    provides: seeded skill_assets rows (deterministic DEFLATE zip, content-addressed sha256) for every skill with assets:+depends_on frontmatter; library-skill injection (_shared/gtm-shared with enabled=false + tags=['library'])
provides:
  - "GET /api/v1/skills/{name}/assets HTTP endpoint returning base64-encoded zip bundle + sha256 + size + format + version + updated_at"
  - "SkillAssetsResponse Pydantic v2 model (first base64-in-JSON wire format in this codebase)"
  - "TestAssetEndpoint integration test class (8 tests; first tests ever written against get_skill_prompt code-path family)"
  - "Two-step query pattern with protected-skill short-circuit BETWEEN queries (no selectinload; bundle bytes never read for protected skills)"
  - "limiter.reset() hygiene pattern applied per-test (not just in rate-limit test) to prevent cross-test slowapi in-memory pollution"
affects:
  - "Phase 149 (broker scripts migration) — broker-parse-contract/broker-analyze-quotes/broker-generate-comparison bundles can now be verified fetchable over HTTP"
  - "Phase 150 (MCP tool + FlywheelClient.fetch_skill_assets) — live endpoint to call; version+updated_at fields pre-shipped for cache keys"
  - "Phase 151 (resilience/caching) — version+updated_at already on wire, ETag/If-None-Match layer can be added without breaking v22.0 clients"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "base64-in-JSON wire format (stdlib base64.b64encode standard alphabet + .decode('ascii'))"
    - "Two-step DB query separated by protected-skill gate (no selectinload) — defense-in-depth for code-ship-prevention"
    - "bytes(asset.bundle) wrapper defending against asyncpg memoryview quirk (matches test_skill_assets_model.py:54)"
    - "limiter.reset() inside each test method (not just setup) for slowapi in-memory test isolation"

key-files:
  created:
    - .planning/phases/148-backend-asset-endpoint/148-01-SUMMARY.md
  modified:
    - backend/src/flywheel/api/skills.py (+116 LOC: base64 import, SkillAsset import, SkillAssetsResponse model, get_skill_assets handler)
    - backend/src/tests/test_skills_api.py (+241 LOC: base64/hashlib/io/zipfile imports, MockSkillDefinition, MockSkillAsset, _build_test_bundle helper, TestAssetEndpoint class with 8 tests)

key-decisions:
  - "Added optional version (from SkillDefinition.version) + updated_at (from SkillAsset.updated_at) to response — Claude's discretion per CONTEXT; ~60 bytes/response cost, future-proofs Phase 151 caching before Phase 150 clients start caching; impossible to add later without wire-format break"
  - "Preserved 404 (NOT 403) for tenant-override denial — research-corrected parity with get_skill_prompt; deviating would create two inconsistent error shapes for 'tenant can't access skill' and require larger cross-cutting change to prompt endpoint too"
  - "Kept two separate db.execute calls with 403 short-circuit between them — rejected selectinload(SkillDefinition.asset) optimization because eager-load would read bundle bytes for protected skills before the 403 check, defeating DELIVER-03 'no skill_assets read if protected'"
  - "Integration tests use TestClient + AsyncMock-based _mock_db (NOT @pytest.mark.postgres admin_session) — faster, consistent with existing test_skills_api.py surface, no Docker dependency; belt-and-suspenders Postgres test deferred"
  - "Added limiter.reset() to EVERY test method in TestAssetEndpoint (not just rate-limit + auth tests per plan) — defensive against slowapi in-memory state leaking across success tests sharing the same user sub within the class; Rule 3 deviation (prevents intermittent class-ordering flakes)"
  - "Logger line 'asset_fetch tenant=%s skill=%s user=%s size=%d sha256=%s' mirrors prompt_fetch shape with sha256[:12] prefix only (no full hash in logs) — stays consistent with existing observability; no new PII beyond what prompt endpoint already logs"

patterns-established:
  - "base64-in-JSON wire format (first use in this codebase; all prior endpoints either return JSON-native types or signed URLs for Supabase Storage)"
  - "Response-level protected-skill 403 (distinct from prompt endpoint's 200-with-stub handling) — assets/executable-code must never ship, unlike system_prompt which can be replaced with a safe orchestration stub"
  - "TestAssetEndpoint establishes test shape for any future /skills/{name}/* endpoint: MockSkillDefinition with configurable protected flag, three-result side_effects list (override probe → skill → asset), await_count assertion for no-touch-DB proof"

# Metrics
duration: 3min
completed: 2026-04-17
---

# Phase 148 Plan 01: Backend Asset Endpoint Summary

**GET /api/v1/skills/{name}/assets endpoint ships base64-encoded skill zip bundles with byte-identical auth/tenant-override/rate-limit parity to get_skill_prompt, plus a 403 short-circuit for protected skills that guarantees bundle bytes are NEVER read from DB for server-side-execution skills.**

## Performance

- **Duration:** 3 min (191 seconds — canonical-template porting pattern; minimal new logic)
- **Started:** 2026-04-17T16:45:08Z
- **Completed:** 2026-04-17T16:48:19Z
- **Tasks:** 3/3
- **Files modified:** 2 (both target files from plan frontmatter)

## Accomplishments
- `GET /api/v1/skills/{skill_name}/assets` registered on the skills router; returns `{bundle_b64, sha256, size, format, version, updated_at}` JSON
- Protected-skill 403 short-circuit enforced at code AND test level — `test_fetch_assets_protected_returns_403` asserts `mock_db.execute.await_count == 2` (proves no SkillAsset SELECT)
- Full end-to-end round-trip verified: `test_fetch_assets_success` decodes base64 → unzips → reads `hello.py` bytes matching fixture — catches double-encoding (Pitfall 4) and memoryview bytes-handling (Pitfall 6) at test level
- Tenant-override branch parity verified both ways: `test_fetch_assets_tenant_override_parity_allows` (has-overrides + skill-present = 200) and `test_fetch_assets_tenant_override_excludes` (has-overrides + skill-absent = 404)
- Rate-limit 429 verified with full response shape: `{"error": "RateLimitExceeded", "code": 429}` body + `Retry-After` header; `limiter.reset()` hygiene at setup AND cleanup prevents cross-test pollution
- 404 messages distinguishable between "skill not found or not available for this tenant" and "has no asset bundle — this is a prompt-only skill" — asserted with non-overlapping substrings

## Task Commits

Single per-plan commit covering all 3 tasks (commit_strategy=per-plan):

1. **Task 1: Add imports and SkillAssetsResponse Pydantic model** — part of `073f8dc`
2. **Task 2: Implement get_skill_assets handler** — part of `073f8dc`
3. **Task 3: Add TestAssetEndpoint integration test class** — part of `073f8dc`

**Plan commit:** `073f8dc` (feat(148-01): add GET /api/v1/skills/{name}/assets endpoint)

## Files Created/Modified
- `backend/src/flywheel/api/skills.py` — added `base64` stdlib import (line 18), extended `flywheel.db.models` import to include `SkillAsset` (line 36), added `SkillAssetsResponse` Pydantic model (lines 62-77), added `get_skill_assets` handler (lines 366-461, 97 LOC)
- `backend/src/tests/test_skills_api.py` — added `base64`/`hashlib`/`io`/`zipfile` imports (lines 10-15), added `MockSkillDefinition` + `MockSkillAsset` + `_build_test_bundle` helpers (lines 96-122), added `TestAssetEndpoint` class with 8 tests (lines 404-606, 202 LOC + 39 LOC of helpers = 241 LOC total)

## Decisions Made
- **Added optional `version` + `updated_at` to response body** — CONTEXT marked this as Claude's discretion; Phase 151 caching strategy can now use these without wire-format break. ~60 bytes/response cost is trivial for a ~215 KB payload.
- **Preserved 404 (not 403) for tenant-override denial** — research-corrected parity with `get_skill_prompt`. Research §4 confirmed `get_skill_prompt` returns 404 when `tenant_skills` override filters the skill out, not 403. Introducing 403 here would create inconsistent 403/404 shapes for "tenant can't access this skill" across the two endpoints.
- **Two separate `db.execute()` calls with protected-skill gate between them** — rejected `selectinload(SkillDefinition.asset)` optimization because eager-load would read bundle bytes for protected skills before the 403 check, defeating DELIVER-03. Comment in code explicitly documents this as intentional non-optimization.
- **`bytes(asset.bundle)` wrapper on base64 encode** — asyncpg driver sometimes returns `memoryview` for `LargeBinary`; `base64.b64encode(memoryview)` is undefined across CPython implementations. Matches pattern at `test_skill_assets_model.py:54` (`assert bytes(row.bundle) == payload`).
- **Logger line mirrors `prompt_fetch` exactly** — event name `asset_fetch` instead of `prompt_fetch`, sha256 truncated to first 12 chars (no full-hash leakage), same PII boundary as prompt endpoint. Single `logger.info` call, no new metrics pipeline.
- **TestClient + dependency-override (not `@pytest.mark.postgres`)** — consistent with existing 5 test classes in `test_skills_api.py`, no Docker dependency, runs in <1s. Postgres-backed integration test deferred (not needed since Phase 146/147 already exercise the DB round-trip for bytea/cascade/uniqueness).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `limiter.reset()` to every test method (plan only required it on 2 tests)**
- **Found during:** Task 3 (TestAssetEndpoint integration tests)
- **Issue:** Plan required `limiter.reset()` only on `test_fetch_assets_rate_limit` (per-test-setup + cleanup) and `test_fetch_assets_requires_auth` (implicitly via the no-override setup). But slowapi uses `user.sub` as the rate-limit key — all TestAssetEndpoint tests in the class share `TEST_USER_ID` via `_make_user()`. If pytest reorders tests (e.g., `test_fetch_assets_rate_limit` runs BEFORE `test_fetch_assets_success`), the success test inherits an exhausted rate-limit bucket from the prior run and fails with spurious 429. This is the exact cross-test pollution pattern called out in Research §Common Pitfalls #3.
- **Fix:** Added `from flywheel.middleware.rate_limit import limiter; limiter.reset()` at the start of every test method in `TestAssetEndpoint` (8 total: success, requires_auth, protected, skill_not_found, no_bundle_row, override_allows, override_excludes, rate_limit). Kept the plan-required cleanup reset in `test_fetch_assets_rate_limit`.
- **Files modified:** backend/src/tests/test_skills_api.py
- **Verification:** Full class runs 8/8 passed in both isolation (`pytest TestAssetEndpoint -v`) and alongside rate-limit suite (`pytest test_skills_api.py::TestAssetEndpoint test_rate_limit.py -v` → 17 passed in asset+rate_limit, with the 2 pre-existing test_rate_limit failures unchanged from baseline).
- **Committed in:** 073f8dc (part of Task 3)

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking class-order flake prevention)
**Impact on plan:** Zero scope creep. Purely a defensive hygiene addition that prevents an intermittent test-order flake the plan's 2-test scope would have missed. All original plan assertions preserved verbatim.

## Issues Encountered

- **Pre-existing test failures on main unrelated to this plan**: 6 tests in `test_skills_api.py` (2× TestListSkills, 2× TestStartRun, 2× TestSSEStream) and 2 tests in `test_rate_limit.py` (TestAnonymousRunLimit, TestConcurrentRunLimit) fail on clean `main` branch before my changes. Verified via `git stash && pytest` → same 6+2 failures. Root causes: 401 leakage between tests (likely `app.dependency_overrides` fixture scoping issue) + `AttributeError` on `flywheel.api.skills.SKILLS_DIR` patch (SKILLS_DIR was removed/renamed in an earlier phase but tests weren't updated). These are out-of-scope for Phase 148 and should be addressed in a dedicated test-hygiene chore-PR. No regressions introduced by this plan — all 6+2 failures exist identically before and after my commit.
- **Pre-existing ruff violations unrelated to this plan**: 5 warnings (F401 unused `json` import, F841 unused `data_lines`, 3× E741 ambiguous `l` variable) exist on main before my changes in TestSSEStream + module imports I did not touch. Ruff clean on all lines I added (`./.venv/bin/ruff check src/flywheel/api/skills.py` → all checks passed; warnings on test file are all in untouched pre-existing code).

## User Setup Required

None — no external service configuration required. No migration, no env var, no new dependency, no frontend change. Endpoint is live on the skills router the moment backend restarts.

## Next Phase Readiness

**Phase 149 (broker scripts migration)** — UNBLOCKED. The broker skill bundles seeded by Phase 147 can now be verified fetchable over HTTP via a smoke test against a running dev server:
```bash
curl -s -H "Authorization: Bearer $TENANT_JWT" \
  http://localhost:8000/api/v1/skills/broker-parse-contract/assets \
  | jq -r '.bundle_b64' | base64 -D | file -
# expected: "/dev/stdin: Zip archive data, at least v2.0 to extract, compression method=deflate"
```

**Phase 150 (MCP tool + FlywheelClient.fetch_skill_assets)** — UNBLOCKED. Live endpoint exists; `version` + `updated_at` response fields already on the wire for Phase 151 cache-key strategies; SHA-256 passthrough matches client-side verification pattern in the MCP tool spec.

**Phase 151 (resilience/caching)** — No wire-format break needed for ETag/If-None-Match layer. Add `ETag: "<sha256>"` response header in Phase 151; clients already have `sha256` in body for cache comparison. `updated_at` enables `If-Modified-Since` semantics if preferred over ETag.

### Open questions for future phases

- **Module-gating 403 semantic** (not addressed in Phase 148, preserved from get_skill_prompt parity): if product intent ever requires "broker module missing → 403 (not 404)" to make denied-access observable in client telemetry, it becomes its own cross-cutting phase touching BOTH `get_skill_prompt` and `get_skill_assets` simultaneously. Research §4 flagged; Phase 148 explicitly preserves 404 parity.
- **Postgres-backed @pytest.mark.postgres integration test** deferred. TestClient + AsyncMock coverage + Phase 146/147's existing Postgres bytea roundtrip tests provide sufficient coverage. Add belt-and-suspenders test only if Phase 150 MCP smoke reveals driver-level surprises.

## Self-Check: PASSED

- backend/src/flywheel/api/skills.py: FOUND (117 line diff, +116/-1)
- backend/src/tests/test_skills_api.py: FOUND (241 line diff, +241/-0)
- .planning/phases/148-backend-asset-endpoint/148-01-SUMMARY.md: created (this file)
- Commit 073f8dc: FOUND in git log
- All 8 TestAssetEndpoint tests: PASSED (verified via `pytest src/tests/test_skills_api.py::TestAssetEndpoint -v`)
- All 5 ROADMAP SCs reachable: PASSED (SC-1 test_fetch_assets_success, SC-2 test_fetch_assets_requires_auth + test_fetch_assets_skill_not_found + test_fetch_assets_tenant_override_excludes, SC-3 test_fetch_assets_protected_returns_403, SC-4 test_fetch_assets_rate_limit, SC-5 test_fetch_assets_tenant_override_parity_allows + test_fetch_assets_tenant_override_excludes)
- Ruff clean on all new code: PASSED (zero new warnings; 5 pre-existing warnings unchanged)
- Zero regressions: PASSED (6 pre-existing failures in test_skills_api.py + 2 in test_rate_limit.py verified identical on main baseline)

---
*Phase: 148-backend-asset-endpoint*
*Completed: 2026-04-17*
