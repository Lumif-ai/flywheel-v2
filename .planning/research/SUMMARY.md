# Project Research Summary

**Project:** v22.0 Skill Platform Consolidation
**Domain:** Server-hosted skill asset delivery + ephemeral fetch-to-exec for Claude Code
**Researched:** 2026-04-17
**Confidence:** HIGH

---

## Executive Summary

v22.0 converts Flywheel skill scripts from a user-managed git-clone model (`~/.claude/skills/`) to server-hosted ZIP bundles delivered via a new MCP tool, extracted to an ephemeral temp directory, and executed by Claude Code without leaving any files on the user's disk. The migration is motivated by a real operational pain: broker portal scripts change weekly, but only users who remember to `git pull` get the fixes. Server-push delivery solves this, but it also inverts the trust model — moving from user-initiated pull of auditable git commits to server-push of executable Python. Every design decision in this milestone must reckon with that inversion.

The recommended implementation is deliberately minimal: a new `skill_assets` Postgres table (bytea column, stdlib zip, no new dependencies), a single new MCP tool returning `fastmcp.utilities.types.File`, a new backend endpoint that copies the auth pattern from `get_skill_prompt`, and a `materialize_skill_bundle()` helper using `tempfile.TemporaryDirectory` + `zipfile`. Zero new frameworks. The only architectural novelty is "first binary-returning MCP tool in this server," which FastMCP handles transparently. Shared modules (`_shared/`, `gtm-shared/`) become first-class library skills with `enabled: false` and `tags: ['library']` — fetched via `depends_on:` declarations in consuming skills, never inlined.

The dominant risk is not technical complexity — it is the security boundary change. A compromised `skill_assets` table means attacker-controlled Python runs on every user's machine. SHA-256 integrity verification (verified over the authenticated transport) is sufficient for the internal dogfood window; Ed25519 bundle signing must be implemented before any multi-tenant rollout. The second major risk is the Playwright persistent-session pattern: broker portal scripts MUST resolve their `user_data_dir` via `Path.home() / ".flywheel" / "broker" / "portals" / "<carrier>"`, never relative to `__file__`, or brokers will be re-prompted for login on every portal invocation.

---

## Conflict Resolutions

Five conflicts were identified across research files. Resolutions are definitive.

### CR-1: Storage — bytea vs Supabase Storage

**Conflicting positions:**
- STACK: bytea in new `skill_assets` table (sub-MB, no second auth hop, existing LargeBinary pattern)
- ARCHITECTURE: Supabase Storage (reuse `document_storage.py` pattern)
- FEATURES: bytea for now, revisit at 500KB
- PITFALLS: Supabase Storage for streamability (also flags signed-URL CDN cache as moderate pitfall M1)

**Resolution: bytea.** Measured bundle is 160KB (broker dir); all 42 .py files total 24.6K LOC. PostgreSQL bytea has a 1GB hard limit — four orders of magnitude of headroom. The existing codebase already uses `LargeBinary` for four production columns (encrypted credentials, portal credentials). A single `SELECT bundle FROM skill_assets WHERE skill_id = ?` is atomic with the skill catalog row; Supabase Storage adds a second auth hop, a second network round-trip, and two places to keep in sync. Critically, PITFALLS M1 (signed URL CDN cache mismatch silently serves revoked content) disappears entirely with bytea. Revisit if any single bundle crosses 20MB.

### CR-2: Phase Count — 4 (STACK) vs 11 (ARCHITECTURE) vs 6 (FEATURES) vs 5 (PITFALLS)

**Resolution: 7 phases.** ARCHITECTURE's 11 are implementation tickets, not planning phases. STACK's 4 are too coarse to carry pitfall-mitigation context. The 7-phase structure below maps to natural delivery checkpoints (schema → seed → serve → migrate → consume → dogfood+resilience → retire) with each phase having a clear deliverable and rollback point. See Implications for Roadmap.

### CR-3: Bundle Signing — Ed25519 (PITFALLS C1) vs SHA-256 only (STACK/ARCHITECTURE/FEATURES)

**Resolution: deferred to pre-multi-tenant gate, not skipped.** PITFALLS C1 is correct that the threat model changed (server-push inverts pull-with-audit-trail). However, at the internal dogfood stage (3 users, first-party backend, no external tenants), SHA-256 integrity over an authenticated HTTPS+JWT transport is an acceptable interim posture — the same authenticated session that allows skill fetch also allows full API access, so bundle trust is equivalent to API trust. Ed25519 signing is a hard gate before external tenant enablement. FEATURES' AF-06 argument ("signing is overkill for first-party-only system") is valid for v22.0 dogfood but not for general availability.

### CR-4: Playwright State Path — PITFALLS C4 vs ARCHITECTURE silence

**Resolution: PITFALLS C4 is authoritative.** Every broker portal script MUST declare `STATE_DIR = Path.home() / ".flywheel" / "broker" / "portals" / "<carrier>"` and resolve `user_data_dir` from this stable path — never from `__file__` or `os.getcwd()`. This is a hard migration requirement for Phase 4. Code review must reject any portal script that resolves Playwright state relative to the script location. PITFALLS verified the current `mapfre.py` uses `sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))` and will break if not explicitly rewritten.

### CR-5: Shared Module Resolution — library skills pattern (ARCHITECTURE) vs silence elsewhere

**Resolution: confirmed.** ARCHITECTURE's recommendation to treat `_shared/` and `gtm-shared/` as library skills (first-class `skill_definitions` rows with `enabled: false` and `tags: ['library']`) holds. `seed.py`'s `SKIP_DIRS` narrows from `{"_archived", "_shared", "gtm-shared"}` to just `{"_archived"}`. Library skills are fetched via `depends_on: ["_shared"]` in consumer skill frontmatter; the exec helper resolves one level of `depends_on` (shared modules themselves cannot have `depends_on`). Inlining is rejected: `context_utils.py` is 958 lines; 8 consumers × 958 = 7,664 lines of duplication with version skew.

---

## Key Findings

### Recommended Stack

No new frameworks or dependencies. The full implementation uses existing codebase primitives plus Python stdlib. The only version action is optionally bumping FastMCP 3.2.2 → 3.2.4 (within the existing `>=3.2.2,<4` pin).

**Core technologies:**

- **PostgreSQL `bytea` + new `skill_assets` table** — stores the zipped skill bundle; FK to `skill_definitions(id) ON DELETE CASCADE`; `bundle_sha256 TEXT`, `bundle_size_bytes INT`, `bundle_format TEXT DEFAULT 'zip'`, `updated_at TIMESTAMPTZ`; separate table avoids SELECT * footgun on skill catalog queries
- **Python stdlib `zipfile` + `io.BytesIO` + `hashlib.sha256`** — in-memory zip at publish time (DEFLATE built-in, ~3-5x on Python source); SHA-256 for content-addressed cache and integrity gate; no new deps
- **`fastmcp.utilities.types.File(data=bytes, format="zip", name=f"{skill}.zip")`** — wraps binary return as base64 `BlobResourceContents`; verified against installed fastmcp 3.2.2 via `inspect.signature`; first binary-returning tool in this MCP server
- **`tempfile.TemporaryDirectory(ignore_cleanup_errors=True)` + `zipfile.ZipFile.extractall()`** — secure auto-cleanup temp dir per skill invocation; path-traversal guard required before `extractall`
- **Alembic migration `064_skill_assets_table.py`** — per-statement `op.execute()` + `alembic stamp` per PgBouncer DDL workaround (template: `063_skill_protected_default.py`)
- **Extended `seed.py` pipeline** — `_build_bundle(entry_path) -> bytes` helper; SHA-256 skip-if-unchanged; `on_conflict_do_update` upsert; reads `assets:` and `depends_on:` from SKILL.md frontmatter

### Expected Features

**Must have (table stakes):**
- **TS-01 Version-pinned bundle identifier** — `(name, version)` tuple; prevents silent mid-run updates
- **TS-02 SHA-256 checksum gate** — client recomputes locally; refuses exec on mismatch; no silent fallback ever
- **TS-03 Atomic swap** — entire bundle fetched before any file used; no mixed-version state mid-pipeline
- **TS-04 Actionable error messages** — distinct errors for 401/403/404/503/checksum/offline; no generic -32603
- **TS-05 Offline last-known-good cache** — content-addressed cache at `~/.cache/flywheel/skills/<sha256>/`; TTL + conditional revalidate; without this, server-hosted is strictly worse than local git
- **TS-06 Ephemeral execution** — code lands in `/tmp/flywheel-skill-<hash>/`; cleaned after invocation
- **TS-07 Module gating server-side** — 403 if tenant lacks `broker` module; reuses existing `@require_module`
- **TS-08 Dependency closure in single fetch** — `depends_on:` resolved by exec helper; no N sequential round-trips

**Should have (differentiators):**
- **DIFF-01 Instant central update** — next invocation after publish picks up new version automatically
- **DIFF-02 Zero-drift across machines** — same `(tenant, skill, version)` = same bytes on all devices
- **DIFF-03 Retraction/kill-switch** — `revoked_at` column + 410 Gone; clients refuse cached revoked bundles
- **DIFF-05 Usage telemetry** — fetch log per tenant; informs deprecation decisions

**Defer to v23+:**
- Ed25519 bundle signing — required before multi-tenant GA; not for internal dogfood (see CR-3)
- Per-tenant customized bundles (DIFF-04) — architecture shaped to allow it; don't build now
- `flywheel skill cache` CLI subcommands — nice UX; not required for MCP path
- Third-party publishers (AF-01), transitive dep resolution (AF-02), user-uploaded skills (AF-03) — explicitly out of scope

### Architecture Approach

The architecture is additive: one new table, one new endpoint, one new MCP tool, one new CLI helper module, all copying existing patterns. Data flow: `seed.py` walks `skills/` → zips per-skill bundle in memory → upserts into `skill_assets` (bytea); on invocation, CC calls `flywheel_fetch_skill_assets` → backend returns base64-encoded zip → FastMCP unwraps as `File` → `materialize_skill_bundle()` extracts to temp dir with path-traversal guard → CC executes via subprocess with `PYTHONPATH=/tmp/flywheel-skill-<hash>/` → temp dir auto-deleted on context exit.

**Major components:**

1. **`skill_assets` table + `SkillAsset` ORM** — one row per skill; `bundle BYTEA NOT NULL`; FK to `skill_definitions(id) ON DELETE CASCADE`; separate from `skill_definitions` to avoid SELECT * footgun
2. **Extended `seed.py` pipeline** — reads `assets:` glob list and `depends_on:` from SKILL.md frontmatter; builds zip in-memory; SHA-256 skip-if-unchanged; upserts `skill_assets`; `SKIP_DIRS` narrows to `{"_archived"}` so `_shared/` and `gtm-shared/` become library skills
3. **`GET /api/v1/skills/{name}/assets` endpoint** — copies auth + tenant-override + rate-limit shape from `get_skill_prompt` (lines 283-344); returns `{"bundle_b64": str, "sha256": str, "size": int, "format": "zip"}`; 403 for `protected=true` skills
4. **`flywheel_fetch_skill_assets` MCP tool** — returns `fastmcp.utilities.types.File(data=bytes, format="zip", name=f"{skill_name}.zip")`; added to `_GTM_TOOLS` set
5. **`cli/flywheel_mcp/bundle.py`** — `materialize_skill_bundle(bundle_bytes) -> TemporaryDirectory`; path-traversal guard; lifetime bounded to single skill invocation
6. **Library skills pattern** — `_shared/` and `gtm-shared/` seeded with `enabled: false`, `tags: ['library']`; resolved via `depends_on:` in consumer skill frontmatter
7. **Migration path** — broker content moves to `flywheel-v2/skills/`; `~/.claude/skills/` archived at retirement; `setup-claude-code` drops git-clone step

**Patterns reused verbatim:**
- PgBouncer DDL workaround: per-statement `op.execute()` + `alembic stamp` (template: `063_skill_protected_default.py`)
- Tenant-override check: `has_overrides` + `tenant_skills` branching from `api/skills.py:296-322`
- `FlywheelClient._request()` HTTP pattern for new `fetch_skill_assets()` method

### Critical Pitfalls

1. **Unsigned remote code execution pipeline (C1)** — server-push of executable Python is a fundamentally different threat model than user-pull git. SHA-256 over authenticated HTTPS is the minimum viable gate for internal dogfood. Ed25519 signing is a hard gate before multi-tenant rollout. Log every asset fetch with `(user_id, skill_name, version, sha256, timestamp)`.

2. **PgBouncer silent DDL rollback (C2)** — guaranteed to bite `skill_assets` migration if each DDL statement is not its own `session.execute() + session.commit()`. Template in `063_skill_protected_default.py`. Verify after migration: `SELECT COUNT(*) FROM skill_assets` must return 0, not an error.

3. **Playwright persistent session obliterated by ephemeral temp dir (C4)** — portal scripts using `launch_persistent_context(user_data_dir=...)` MUST resolve the profile path via `Path.home() / ".flywheel" / "broker" / "portals" / "<carrier>"`, never relative to `__file__`. Code-review rejection criterion.

4. **Prompt/asset version drift (C5)** — prompt and bundle can be updated independently, creating a window where a prompt calls a function that doesn't exist in the asset bundle. Prevention: `seed.py` inserts/updates `skill_assets` BEFORE `skill_definitions`; CI integration test parses each prompt for function calls and verifies they exist in the bundle via `inspect.signature`.

5. **Dropping `~/.claude/skills/` breaks active users (C3)** — minimum one full milestone coexistence window. Codebase-wide grep for `~/.claude/skills/`, `expanduser("~/.claude")`, `Path.home() / ".claude"` before retirement.

---

## Implications for Roadmap

Suggested 7-phase structure sequenced schema → seed → serve → migrate → consume → dogfood+resilience → retire. Rollback is possible at every phase through Phase 6; Phase 7 is one-way.

### Phase 1: Schema Foundation
**Rationale:** Everything downstream requires the table to exist. PgBouncer DDL risk is highest here — must be addressed first.
**Delivers:** `skill_assets` table live; `SkillAsset` ORM wired; Alembic migration stamped; smoke test `SELECT COUNT(*) FROM skill_assets` passes.
**Implements:** `064_skill_assets_table.py` (PgBouncer per-statement pattern), `SkillAsset` ORM in `db/models.py`.
**Avoids:** C2 (PgBouncer DDL).
**Research flag:** None — PgBouncer workaround fully documented and templated.

### Phase 2: Seed Pipeline Extension
**Rationale:** No bundles to serve until the pipeline can produce them. Establishes the `assets:` + `depends_on:` frontmatter contract all subsequent phases assume.
**Delivers:** `flywheel db seed` on `skills/` produces idempotent `skill_assets` rows; SHA-256 skip-if-unchanged; library skills (`_shared`, `gtm-shared`) seeded with `enabled: false`, `tags: ['library']`.
**Implements:** `SkillData.assets`, `SkillData.depends_on`; `_build_bundle()` helper; `SKIP_DIRS` narrowed to `{"_archived"}`; upsert loop in `seed_skills()`.
**Avoids:** C5 (seed inserts assets before skill_definitions update), M3 (concurrent seed via `pg_advisory_lock`), M7 (partial backfill).
**Research flag:** None — extends established patterns in `seed.py:432-469`.

### Phase 3: Backend Asset Endpoint
**Rationale:** Expose bundles via an endpoint before wiring the MCP client, so the endpoint can be tested independently.
**Delivers:** `GET /api/v1/skills/{name}/assets` returning base64-encoded bundle JSON; 403 for protected skills; integration test verifying a real seeded skill returns valid bytes.
**Implements:** New handler in `api/skills.py` (copies tenant-override check from lines 296-322); same `@limiter.limit("10/minute")` as prompt endpoint.
**Avoids:** M2 (same auth guard as existing endpoints, no new surface).
**Research flag:** None — copies `get_skill_prompt` shape verbatim. Confirm: protected skills return 403 (they execute server-side; returning assets would be wrong).

### Phase 4: Broker Scripts Migration
**Rationale:** Migrate actual broker content into the repo before wiring CC-side delivery. This phase enforces the Playwright state path contract, which is the highest-severity migration risk.
**Delivers:** `skills/broker/`, `skills/_shared/`, `skills/gtm-shared/` checked into `flywheel-v2/skills/`; each SKILL.md has `assets:` + `depends_on:` stanzas; every portal script declares `STATE_DIR = Path.home() / ".flywheel" / "broker" / "portals" / "<carrier>"`; `~/.claude/skills/` git-tagged `legacy-skills-final` (soft freeze, not deleted); seed run confirms all broker assets in DB.
**Avoids:** C4 (Playwright state path), C3 (no deletion yet — coexistence maintained).
**Migration requirement:** grep for `sys.path.insert` + `expanduser("~/.claude/skills/broker")` in every portal script before merge. CI smoke test on a clean machine (no `~/.claude/skills/`) must pass.
**Research flag:** Needs careful review. Playwright state path is a verified breakage site in current `mapfre.py`.

### Phase 5: MCP Tool + Unpack Helper
**Rationale:** Wire the CC-side delivery chain. First end-to-end test of fetch → verify → extract → exec flow.
**Delivers:** `flywheel_fetch_skill_assets` MCP tool returning `fastmcp.utilities.types.File`; `fetch_skill_assets()` method in `api_client.py`; `cli/flywheel_mcp/bundle.py` with `materialize_skill_bundle()` (path-traversal guard + `TemporaryDirectory`); smoke test verifying SHA-256, extraction, and import of one function.
**Implements:** TS-02 (SHA-256 gate), TS-03 (atomic swap), TS-06 (ephemeral temp dir), TS-08 (`depends_on` resolution for library skills).
**Avoids:** C1 (SHA-256 verify before exec), M4 (/tmp collision — unique-suffix temp dir per invocation), m4 (unit tests use `FakeSkillFetcher`, never real network).
**Research flag:** Highest pitfall density (C1, M4, M5, M6). Subprocess-per-skill-run vs in-process import must be decided here — subprocess is safer (eliminates `sys.modules` pollution). Verify `fastmcp.utilities.types.File` return handling in a live MCP session before committing.

### Phase 6: Broker Dogfood + Resilience
**Rationale:** First live end-to-end run of a real broker skill via the v22.0 path. Resilience features (offline cache, error taxonomy) need real latency data to tune TTLs.
**Delivers:** `/broker:parse-contract` runs successfully with no local `~/.claude/skills/broker/` on disk; content-addressed cache at `~/.cache/flywheel/skills/<sha256>/` with TTL + conditional revalidation; distinct error strings for each failure class; `flywheel_refresh_skills` MCP cache-buster tool; p99 fetch latency under 500ms measured.
**Implements:** TS-04 (actionable errors), TS-05 (offline cache), DIFF-01 (central update verified), DIFF-02 (zero drift).
**Avoids:** M5 (manifest cache TTL), M6 (exponential backoff, fail-fast timeouts, proactive token refresh), C3 (both paths still work during this phase).
**Research flag:** Cache TTL values (60s skill list, 24h bundles) are estimates — validate against actual ngrok + Supabase latency. Offline fallback interacts with DIFF-03 (retraction); short max-age required if revocation is needed.

### Phase 7: Retirement
**Rationale:** One-way. Only execute after Phase 6 has run in production for a full milestone (2+ weeks) with no regressions.
**Delivers:** `~/.claude/skills/` git repo archived; `setup-claude-code` drops git-clone step; README updated; codebase-wide grep for hardcoded `~/.claude/skills/` paths returns zero hits; DIFF-05 telemetry confirms all active tenants on server-hosted path.
**Avoids:** C3 (coexistence period sufficient before this phase).
**Gate:** Ed25519 bundle signing must be complete before expanding beyond internal users. Retirement does not block on signing for the internal dogfood team, but signing is a prerequisite for any external tenant enablement.
**Research flag:** None — retirement is mechanical if Phase 6 is stable.

### Phase Ordering Rationale

- Schema before seed before serve: no bundles to fetch until the table exists and is populated; no endpoint to call until bundles exist
- Broker migration before MCP wiring (Phase 4 before Phase 5): ensures the full real-world bundle is in the DB when the MCP tool is first exercised end-to-end, avoiding "works with test fixtures but not real broker content" surprises
- Resilience in same phase as dogfood (Phase 6): offline behavior and error messages can only be tuned with real latency data from a live broker workflow
- Retirement last and gated: the coexistence period is the safety net; never retire the legacy path until telemetry confirms zero active use

### Research Flags

Phases needing deeper research during planning:
- **Phase 5 (MCP Tool + Unpack Helper):** highest pitfall density; subprocess-vs-in-process decision has architectural consequences; `fastmcp.utilities.types.File` return should be verified in a running MCP session before implementation starts
- **Phase 4 (Broker Migration):** Playwright persistent-context state path requires line-by-line audit of every portal script; verified breakage sites exist in `mapfre.py`

Phases with standard patterns (skip research-phase):
- **Phase 1 (Schema):** PgBouncer workaround documented and templated
- **Phase 2 (Seed):** extends a 499-line pipeline with well-understood semantics
- **Phase 3 (Endpoint):** copies `get_skill_prompt` verbatim; no novel auth
- **Phase 7 (Retirement):** mechanical cleanup checklist; no novel decisions

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All claims verified against local codebase (`inspect.signature` on installed FastMCP, existing LargeBinary columns, 063 migration template). Bundle size measured (160KB). Zero new dependencies. |
| Features | HIGH | Grounded in six reference systems (npm, Homebrew, Lambda Layers, Cloudflare Workers, Deno, pip). Table-stakes features are non-negotiable by analogy to every mature fetch-and-run system. |
| Architecture | HIGH (existing surface), MEDIUM (new components) | Integration points verified file-by-file against HEAD. New components (bundle endpoint, exec_helper) informed by existing patterns but not yet implemented. |
| Pitfalls | HIGH for Supabase/Playwright/PgBouncer (codebase-verified + current docs), MEDIUM-HIGH for CC/MCP cache behavior (verified via Anthropic issue tracker) | Playwright state path verified in live `mapfre.py`. MCP cache pitfall backed by open GitHub issues. |

**Overall confidence:** HIGH

### Gaps to Address

- **Subprocess vs in-process import model:** PITFALLS recommends subprocess-per-skill-run to eliminate `sys.modules` pollution (M4). STACK/ARCHITECTURE assume in-process `sys.path.insert`. Must be resolved in Phase 5 planning before implementation. Subprocess is the safer default.

- **Ed25519 signing key custody:** PITFALLS C1 specifies "generate offline, store on airgapped machine or KMS." The operational details (who holds the key, how CI signs, how to rotate) are not specified in any research file. Must be designed before Phase 7 gate.

- **Version number source of truth:** STACK uses `updated_at`, FEATURES uses `version_semver`, ARCHITECTURE uses `bundle_version` mirroring `SkillDefinition.version`. Recommendation: `SkillDefinition.version` is the bundle version (already exists); `bundle_sha256` is the content-addressed cache key; `updated_at` on `skill_assets` is for observability only.

- **Protected-skill asset endpoint behavior (403 vs 404):** Logic-derived, not explicitly specced. Recommendation: 403 is correct — protected skills execute server-side; returning their assets would be wrong. Confirm in Phase 3 plan.

- **FastMCP 3.2.4 bump:** MEDIUM confidence it is a safe non-breaking bump. Validate with smoke test in Phase 5 before relying on it in production.

---

## Sources

### Primary (HIGH confidence — local codebase verified)
- `backend/src/flywheel/db/models.py:80,402,811-884,1981` — existing `LargeBinary` columns + `SkillDefinition` ORM
- `backend/src/flywheel/db/seed.py:1-499` — existing scan + upsert pipeline
- `backend/src/flywheel/api/skills.py:283-344` — `get_skill_prompt` auth+tenant-access shape to copy
- `backend/alembic/versions/063_skill_protected_default.py` — PgBouncer per-statement DDL template
- `cli/flywheel_mcp/server.py:82-337` — MCP tool signatures
- `cli/flywheel_mcp/api_client.py:1-151` — REST client pattern
- `cli/.venv/lib/python3.12/site-packages/fastmcp/utilities/types.py` — `File` signature verified via `inspect.signature`
- `~/.claude/skills/broker/portals/mapfre.py` — confirmed `sys.path.insert` + Playwright persistent context usage

### Primary (HIGH confidence — official docs)
- [PostgreSQL Limits — bytea 1GB](https://www.postgresql.org/docs/current/limits.html)
- [FastMCP Tools — binary content handling](https://gofastmcp.com/servers/tools)
- [Python tempfile docs](https://docs.python.org/3/library/tempfile.html)
- [Python zipfile docs](https://docs.python.org/3/library/zipfile.html)
- [Playwright persistent context + user_data_dir](https://playwright.dev/python/docs/api/class-browsertype)
- [Supabase Storage Access Control](https://supabase.com/docs/guides/storage/security/access-control)
- [AWS Lambda Layers](https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html)
- [Cloudflare Workers — atomic deployment](https://developers.cloudflare.com/workers/configuration/versions-and-deployments/)
- [npm package-lock.json — SHA-512 integrity](https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/)
- [pip caching — ETag + conditional revalidate](https://pip.pypa.io/en/stable/topics/caching/)

### Secondary (MEDIUM-HIGH confidence — verified issue trackers)
- [Claude Code Issue #7519 — MCP manifest cache no refresh mechanism](https://github.com/anthropics/claude-code/issues/7519)
- [Claude Code Issue #27142 — MCP session invalidation](https://github.com/anthropics/claude-code/issues/27142)
- [Playwright Issue #35466 — profile corruption with concurrent instances](https://github.com/microsoft/playwright/issues/35466)
- [CPython Issue 143650 — importlib race with stale module refs](https://github.com/python/cpython/issues/143650)
- [Supabase Storage signed URL + CDN cache behavior](https://github.com/orgs/supabase/discussions/6458)

### Tertiary (supporting context)
- [Axios npm supply-chain compromise March 2026](https://www.microsoft.com/en-us/security/blog/2026/04/01/mitigating-the-axios-npm-supply-chain-compromise/) — unsigned-code-delivery risk class
- [Homebrew Bottles — SHA-256 verification](https://docs.brew.sh/Bottles)
- [Deno DENO_DIR cache](https://denolib.gitbook.io/guide/advanced/deno_dir-code-fetch-and-cache)
- [OpenAI Agents SDK — retry/backoff config](https://openai.github.io/openai-agents-python/ref/mcp/server/)

---
*Research completed: 2026-04-17*
*Ready for roadmap: yes*
