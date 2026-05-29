# Feature Landscape — v22.0 Skill Platform Consolidation

**Domain:** Server-hosted skill asset delivery + ephemeral remote-code execution for Claude Code
**Researched:** 2026-04-17
**Overall confidence:** HIGH — grounded in six well-documented reference systems (npm, Homebrew, AWS Lambda layers, Cloudflare Workers, Deno, pip)

---

## Executive Summary

Every mature "fetch-and-run" system converges on the **same four primitives**: (1) a content-addressed artifact, (2) a pinned version identifier, (3) a checksum gate before execution, (4) an isolated/ephemeral execution surface. Variations are about *caching strategy* (permanent vs TTL vs per-invocation) and *trust model* (signed publisher vs first-party only vs zero-trust).

For Flywheel v22.0 — broker Python helpers served to one trusted party (the user's own Claude Code) from a first-party backend the user is already authenticated to — the design lives closer to the **Cloudflare Worker / Lambda Layer** end of the spectrum (tight publisher trust, version-pinned, deterministic) than the **npm/npx** end (open registry, transitive deps, arbitrary publishers).

The critical design choice is **caching policy**. Three options:
1. **No cache (pure ephemeral):** every `/broker:*` run fetches fresh — highest freshness, worst latency, breaks offline.
2. **TTL + ETag (pip model):** fetch on first use, conditional revalidate thereafter — best balance for Flywheel.
3. **Persistent with manual invalidate (Homebrew model):** only refetch on explicit version bump — fastest but drifts.

**Recommendation: Option 2 (TTL-with-revalidate, backed by content-addressed cache keyed on `sha256:<hash>`).** The cache is an optimisation, not a persistence model — the bundle is still "ephemeral" in the sense that it is not managed by the user, is invalidated centrally, and is re-verifiable from the server at any time.

---

## Feature Categories

Features are grouped as:

| Category | Definition |
|----------|------------|
| **Table Stakes** | MUST-HAVE. Without these, the system is a regression from today's local `~/.claude/skills/broker/` setup. |
| **Differentiators** | NICE-TO-HAVE that make the server-hosted model *better* than local files, justifying the migration. |
| **Anti-Features** | Explicitly OUT OF SCOPE. Listed to prevent scope creep during roadmap planning. |

---

## Table Stakes

Features whose absence would make v22.0 *worse* than the current local filesystem setup.

### TS-01 — Version-pinned bundle identifier

| Attribute | Value |
|-----------|-------|
| What | Every skill has a resolvable `(name, version)` tuple; MCP fetch accepts an explicit version or "latest-stable" |
| Why | Without version pinning, a silently pushed server update breaks an in-flight `/broker:process-project` pipeline mid-run. This is the #1 Lambda Layer production footgun. |
| Complexity | **Moderate** — requires `skill_version` column + foreign-key on bundle, plus server-side semver ordering |
| Depends on | Alembic migration, existing `skills` table from Phase 77 |
| User-visible behaviour | `flywheel_fetch_skill_bundle("broker/portals/mapfre", version="1.2.3")` always returns the same bytes |
| Reference systems | Lambda Layers (version-ARN pinning); npm lockfile; Deno `--lock` |

### TS-02 — SHA-256 checksum verification before execution

| Attribute | Value |
|-----------|-------|
| What | Bundle payload includes `sha256:<hex>`; client recomputes locally and refuses to exec on mismatch |
| Why | Without this we have unauthenticated remote code execution from whatever the transport returns. Every reference system has had *at least one* CVE teach this lesson (npm EINTEGRITY, Homebrew manifest checksum errors, axios supply-chain March 2026). |
| Complexity | **Trivial** — 10 lines of Python using `hashlib.sha256()`; server pre-computes on publish |
| Depends on | Nothing new |
| User-visible behaviour | On mismatch: clear error "Skill bundle checksum failed — refusing to run. Re-authenticate or contact support." No silent fallback. |
| Reference systems | npm `integrity` field; Homebrew bottle `sha256`; pip wheel hash mode |

### TS-03 — Atomic swap (either the new version runs, or the old one does — never a mix)

| Attribute | Value |
|-----------|-------|
| What | Fetch resolves the *entire* bundle (all files together) before any file is used; no partial writes |
| Why | Today's local setup is atomic because git pulls are atomic. A naive "download file-by-file on demand" would let `portals/mapfre.py v1.2` import `_shared/api_client.py v1.3` mid-run. This is the AWS Lambda layer-merge failure mode. |
| Complexity | **Moderate** — server returns bundle as manifest + tarball or multi-file JSON; client writes to a fresh tempdir then atomically swaps |
| Depends on | TS-01, TS-02 |
| User-visible behaviour | Mid-pipeline version updates are deferred to the next invocation; no "already running" process ever sees a mixed state |
| Reference systems | Cloudflare Workers "all-at-once deployment"; Lambda layer immutability; git checkout |

### TS-04 — Actionable error messages when fetch fails

| Attribute | Value |
|-----------|-------|
| What | Clear, distinct error strings for each failure class: network unreachable, 401 auth, 404 not found, 403 module-not-subscribed, 409 version-not-pinned, checksum mismatch |
| Why | Today, if the broker skill has a bug, the user sees a Python traceback pointing at a local file — easy to debug. If v22.0 fails with "MCP error: -32603" or a generic `OSError`, the user has no recovery path and blames the feature. |
| Complexity | **Trivial** — structured MCP error codes + a router in the ephemeral-exec helper |
| Depends on | Nothing new |
| User-visible behaviour | `"Skill broker/portals/mapfre could not be fetched: 403 Forbidden — your tenant does not have the 'broker' module enabled. Contact admin."` |
| Reference systems | pip's explicit error taxonomy; Homebrew's "Couldn't find manifest matching bottle checksum" (still imperfect but diagnostic) |

### TS-05 — Offline behaviour: last-known-good cached bundle usable when server unreachable

| Attribute | Value |
|-----------|-------|
| What | Client keeps the most recently verified bundle under a content-addressed cache; if the backend is unreachable *and* the user has a recent cached bundle, run it with a clear warning |
| Why | Broker placement is time-sensitive. A carrier portal appointment at 14:00 cannot fail because the Flywheel backend is rebooting. Without offline fallback, server-hosted skills are *strictly worse* than local files. This is the #1 objection to this entire migration. |
| Complexity | **Moderate** — cache directory under `~/.cache/flywheel/skills/<sha>`, TTL metadata, fallback logic, clear UX |
| Depends on | TS-02 (cache is keyed on sha256), TS-04 |
| User-visible behaviour | `"Warning: offline — using cached broker/portals/mapfre@1.2.3 (fetched 2 hours ago). Online refresh will be attempted next invocation."` |
| Reference systems | pip `--prefer-offline`; npm `--offline`; Deno DENO_DIR cache; Homebrew local tap |

### TS-06 — Ephemeral execution — no persistent writes under user's home

| Attribute | Value |
|-----------|-------|
| What | Fetched code runs from a tempdir (or OS cache dir), NOT from `~/.claude/skills/`; tempdir cleaned up after each skill invocation |
| Why | The whole point of the milestone. If we leave files in `~/.claude/skills/broker/`, we have *both* a local and server-hosted copy, which is worse than either alone. |
| Complexity | **Trivial** — `tempfile.TemporaryDirectory()` context manager; `sys.path.insert()` scoped to that context |
| Depends on | TS-03 |
| User-visible behaviour | `ls ~/.claude/skills/broker/` returns empty; `ps` during skill run shows Python importing from `/tmp/flywheel-skill-<hash>/` |
| Reference systems | Lambda `/tmp` (512MB ephemeral); Deno runtime isolates; npx temporary install dir |

### TS-07 — Module gating enforced server-side

| Attribute | Value |
|-----------|-------|
| What | `flywheel_fetch_skill_bundle("broker/*")` rejects with 403 if tenant does not have `modules.broker = true` |
| Why | Today, a non-broker tenant who stumbles into `~/.claude/skills/broker/` can still run the code (the backend API will reject, but the Python runs locally). Moving to server delivery lets us enforce access at source. Also a prerequisite for any future commercial tier. |
| Complexity | **Trivial** — reuse existing `@require_module` dependency from v15.0 |
| Depends on | Existing module-gating from v15.0 Phase 112 |
| User-visible behaviour | `"Skill broker/portals/mapfre requires the 'broker' module. Enable it in tenant settings."` |
| Reference systems | Stripe "products gated by subscription tier"; AWS IAM resource-level perms on Lambda Layers |

### TS-08 — Dependency closure in a single fetch

| Attribute | Value |
|-----------|-------|
| What | Fetching `broker/portals/mapfre` automatically includes its declared deps (`broker/api_client.py`, `broker/field_validator.py`, `_shared/context-protocol.md`); not N round-trips |
| Why | Today, a skill imports 3 files. If v22.0 makes 3 sequential MCP round-trips, a `/broker:fill-portal` adds ~600ms of fetch latency over baseline. Bundle-level closure keeps it at ~200ms. |
| Complexity | **Moderate** — server-side dependency graph at publish time; client fetches one blob |
| Depends on | TS-01, TS-03 |
| User-visible behaviour | Single MCP call returns a manifest listing all files + content; client extracts whole tree to tempdir |
| Reference systems | Cloudflare Workers bundler (esbuild); Webpack; Lambda "one layer, many files" |

---

## Differentiators

Features that make server-hosted notably *better* than the current local setup and justify the migration cost.

### DIFF-01 — Instant central update — no user action needed

| Attribute | Value |
|-----------|-------|
| What | When we fix a bug in `portals/mapfre.py`, every user on the next `/broker:fill-portal` run gets the fix — no `git pull`, no reinstall |
| Why | Today, pushing a fix requires every user to `cd ~/.claude/skills/broker && git pull`. In practice half of users never do this and run stale code for weeks. For a broker portal that we reverse-engineer and update weekly, this is *the* reason to build v22.0. |
| Complexity | **Trivial** (free from TS-01 design) |
| Depends on | TS-01, TS-02 |
| User-visible behaviour | Next invocation after a publish picks up v1.2.4 automatically; user sees `"(using broker/portals/mapfre v1.2.4)"` in skill output |
| Reference systems | Cloudflare Workers "push and it's live globally"; server-rendered apps |

### DIFF-02 — Zero-drift guarantee across machines

| Attribute | Value |
|-----------|-------|
| What | A user on MacBook and MacMini runs the exact same bytes for the same `(tenant, skill, version)` tuple. No "works on my machine." |
| Why | Local git clones drift silently (user edited a file and forgot, or a merge conflict was auto-resolved wrong). Server-hosted with checksum verification makes drift impossible. |
| Complexity | **Trivial** (free from TS-02) |
| Depends on | TS-02 |
| User-visible behaviour | Skill output includes `bundle_sha256` — support debugging can say "are you on the same hash?" |
| Reference systems | Docker image digests; Lambda version-ARNs |

### DIFF-03 — Retraction / kill-switch for IP leak or security incident

| Attribute | Value |
|-----------|-------|
| What | Server can mark a bundle version as `revoked=true`; MCP fetch returns 410 Gone; clients refuse to run a cached revoked bundle |
| Why | If we discover our reverse-engineered `portals/mapfre.py` has been leaked or copied into a competitor product, we need to stop serving it without shipping a new CLI release. Also essential if a published bundle contains a vulnerability (think March 2026 axios incident). |
| Complexity | **Moderate** — server-side `is_revoked` + revocation check on every exec, even for cached bundles (requires a lightweight server round-trip, OR revocation expiry time baked into the cache) |
| Depends on | TS-01, TS-05 (interacts with offline policy) |
| User-visible behaviour | `"Skill broker/portals/mapfre v1.2.3 has been revoked: use v1.2.4 or later. Contact support if this is unexpected."` |
| Reference systems | RubyGems yanked versions; npm unpublish; TLS certificate revocation lists |
| Risk | Revocation-check on every run can violate TS-05 (offline). Mitigation: cache bundles with a short max-age (e.g., 24h) after which revocation must be re-checked online. |

### DIFF-04 — Per-tenant customisation (future-proof)

| Attribute | Value |
|-----------|-------|
| What | Server can return a tenant-specific variant of a bundle (e.g., `portals/mapfre.py` with the user's agency-specific field mappings baked in) |
| Why | Today every broker gets the same `mapfre.py`. As we onboard more agencies, each has slightly different field defaults. Server-side variant selection makes this clean. Not needed for v22.0 ship, but the architecture should not preclude it. |
| Complexity | **Do not build in v22.0** — just ensure the fetch API is `(tenant, skill, version)` keyed, not global |
| Depends on | TS-01 (API shape) |
| User-visible behaviour | None for now — this is architectural headroom |
| Reference systems | Shopify private apps; Salesforce managed packages |

### DIFF-05 — Telemetry on skill usage

| Attribute | Value |
|-----------|-------|
| What | Backend knows exactly which skill versions each tenant is running and how often |
| Why | Today, skill usage is invisible server-side. Server-hosted fetches produce an authoritative log. This informs deprecation decisions ("nobody uses v1.1, safe to drop") and billing (future). |
| Complexity | **Trivial** — log the fetch in an existing `skill_runs` or new `skill_bundle_fetches` table |
| Depends on | TS-01 |
| User-visible behaviour | None |
| Reference systems | PyPI download stats; Docker Hub pull counts |

### DIFF-06 — Asset types beyond Python — prompts, YAML configs, test fixtures, reference docs

| Attribute | Value |
|-----------|-------|
| What | The bundle contract is generic: any file type the skill declares. Not Python-specific. |
| Why | Broker skills today include `portals/mapfre.yaml` (field mappings), `_shared/context-protocol.md`, test fixtures. A Python-only delivery channel would leave these stranded. |
| Complexity | **Trivial** — bundle is a file tree, not a Python package |
| Depends on | TS-03 |
| User-visible behaviour | `.yaml`, `.md`, `.json`, `.txt`, `.py` all flow through the same endpoint |
| Reference systems | Lambda layers (any content); Homebrew bottles (arbitrary file trees) |

---

## Anti-Features

Scope discipline — things we should *explicitly not* build in v22.0, even if tempting.

### AF-01 — A package registry for arbitrary third-party skill publishers

**What it would be:** A public or community skill registry where any developer can publish skills, with namespace reservation, author reputation, etc.

**Why avoid:** The v22.0 use case is "Flywheel-owned broker skills delivered to authenticated Flywheel users." We are a first-party publisher, not a registry. Going full-registry adds: publisher identity (sign-ups, OAuth), namespace rules, trust-on-first-use model, dependency conflict resolution across untrusted authors, take-down process for malicious packages. All of that is 10x the scope of v22.0 and violates YAGNI.

**What to do instead:** Keep the API shape tenant+skill+version so we *could* add publisher_id later, but only Flywheel publishes for now.

**Reference systems we are NOT building:** npm, PyPI, RubyGems, Cargo crates.io.

### AF-02 — Transitive dependency resolution between independent skills

**What it would be:** Skill A declares "depends on skill B@^2.0"; client resolves a DAG, locks, etc.

**Why avoid:** Bundler/pip-style semver dependency resolution is one of the hardest problems in package management (Bundler took from 2012–2016 to converge on the compact index format). Our dependencies are *intra-skill* (broker's own files depend on broker's own `api_client.py`) — that's a file tree, not a graph.

**What to do instead:** Flatten deps into the bundle. If two skills need `_shared/context-protocol.md`, each bundle ships its own copy. Duplicate bytes are cheap; dep-solver bugs are not.

**Reference systems we are NOT building:** npm's node_modules resolution, Bundler's compact index.

### AF-03 — User-uploaded custom skills ("bring your own Python")

**What it would be:** A broker agency uploads their own `portals/zurich.py` via Flywheel UI; it gets delivered to all their users.

**Why avoid:** Arbitrary user-uploaded code that then runs inside every user's Claude Code session is a security nightmare (think: malicious agency admin, compromised tenant account, persistent code injection). The Flywheel CLAUDE.md memory explicitly flags the March 2026 supply-chain incidents.

**What to do instead:** Keep publishing Flywheel-internal only. If a broker needs a new portal, they file a request and Flywheel engineering builds + publishes it.

### AF-04 — Multiple concurrent versions executing on the same machine

**What it would be:** User A's `/broker:fill-portal` runs v1.2.3 while user B's concurrent invocation runs v1.2.4 on the same box.

**Why avoid:** Adds version-isolation complexity (venvs? process isolation? sys.path fragility?) with no real use case. At most one Claude Code session per user per machine in practice.

**What to do instead:** One user = one active skill cache generation at a time. If the server publishes a new version mid-run, the current run completes on the old bundle; the *next* invocation picks up new.

### AF-05 — In-place skill editing / hot-reload

**What it would be:** User edits `portals/mapfre.py` in their editor, Claude Code picks up the edit live.

**Why avoid:** The whole premise of v22.0 is "no local files to edit." If we support hot-reload we re-invent the local-files problem. If a user wants to patch a skill, they file an issue and we publish v1.2.4.

**What to do instead:** Document the workflow: "Skills are server-delivered. For bugs, file an issue. For custom behaviour, discuss with Flywheel."

### AF-06 — Signed bundles / cryptographic publisher identity

**What it would be:** Each bundle signed with Flywheel's private key; client verifies against pinned public key.

**Why avoid (in v22.0):** We are already relying on authenticated HTTPS + tenant JWT + first-party CA. Adding signing is belt-and-suspenders for a first-party-only system. Ship integrity (sha256) for correctness; defer signing for when we have third-party publishers (which per AF-01 is never, or at least far out).

**What to do instead:** TS-02 (sha256 integrity) is sufficient because the transport is already authenticated. Revisit only if AF-01 is ever reconsidered.

### AF-07 — Automatic skill upgrade prompts in Claude Code UI

**What it would be:** Claude Code notices a new bundle version is available and prompts "update?"

**Why avoid:** With server-hosted delivery there is no concept of "update" — the server decides. Prompting the user re-creates the local-files mental model we are leaving behind.

**What to do instead:** Next invocation silently uses new version (DIFF-01). If a breaking change is shipped, the server exposes it through a new major version and the skill prompt (the markdown) documents migration.

### AF-08 — Skill sandboxing (cgroups/seccomp/wasm)

**What it would be:** Fetched Python runs inside a restricted sandbox that cannot touch the user's filesystem, network, etc.

**Why avoid:** Our threat model is "Flywheel is a trusted first-party publisher." Flywheel already has API-level authority to read every tenant's data. Sandboxing Python from itself is security theatre in this model — the same Flywheel employee could exfiltrate via the backend API.

**What to do instead:** Focus security budget on publish-time review (code review, CI tests, automated scans) rather than runtime sandboxing.

---

## User-Visible Behaviours (Success Criteria Concrete Enough for QA)

Given a broker running `/broker:process-project` against a project with 3 coverages and 1 portal carrier:

### UVB-01 — First invocation ever (empty cache, online)

1. User runs `/broker:process-project 67de-...`
2. Claude Code calls MCP `flywheel_fetch_skill_bundle(name="broker", version="latest-stable")`
3. MCP returns bundle manifest: 9 Python files, 2 markdown, 1 yaml, `sha256:abc...`, `~48 KB gzipped`
4. Client verifies sha256, extracts to `/tmp/flywheel-skill-<sha>/`
5. Python imports from that tempdir
6. Pipeline runs; final artefacts written to the user's normal output dirs
7. Tempdir removed at session end (NOT at each step — steps share the bundle)
8. **Observed latency added:** 200–400 ms on first invocation (single fetch, ~50 KB)

### UVB-02 — Subsequent invocation, same day (cache hit, online)

1. Client checks cache for `sha256:abc...`; finds it
2. Client makes a conditional HEAD request to server with `If-None-Match: abc...`
3. Server returns 304 Not Modified
4. Client uses cached bundle, extracts to tempdir
5. **Observed latency added:** 20–40 ms (cache revalidation round-trip only)

### UVB-03 — Invocation while offline

1. Client checks cache; finds `sha256:abc...` with cached-at timestamp 4h ago
2. Client attempts conditional revalidate; fails (no network)
3. If cache age < max-age (e.g., 24h): use cached bundle with warning
4. If cache age > max-age: refuse with actionable error "Last cached 3 days ago, need network to revalidate. Retry when online, or run `flywheel skill cache extend` to accept risk."
5. **Behaviour:** predictable, loud, no silent execution of expired cache

### UVB-04 — Invocation after central fix published

1. Flywheel engineer publishes `broker@1.2.4` with mapfre-portal fix
2. User runs next `/broker:fill-portal`
3. Client conditionally revalidates; server returns new bundle, new sha256
4. Client verifies new sha256, extracts to new tempdir, runs
5. Skill output shows `(broker@1.2.4)` banner
6. **No user action required** — DIFF-01 achieved

### UVB-05 — Retracted bundle attempted

1. Server marks `broker@1.2.3` as revoked
2. User has `1.2.3` in cache, age 2h
3. User runs `/broker:*`
4. Revalidation returns 410 Gone + `replaced_by: 1.2.4`
5. Client auto-fetches 1.2.4, verifies, runs
6. User sees `"Note: broker@1.2.3 was retracted; using broker@1.2.4."`

### UVB-06 — Checksum tampering detected

1. MITM attacker (or disk corruption) mangles bytes between server and client
2. Client computes sha256 on received payload; mismatch
3. Client refuses to execute
4. Error: `"Skill bundle checksum failed. Cached result discarded. Please check network and retry."`
5. **No fallback to running unverified code, ever**

### UVB-07 — Partial outage (catalog reachable, asset delivery down)

1. User runs `/broker:*`
2. Catalog API returns skill definition including prompt
3. Asset delivery endpoint returns 503
4. Client checks cache; uses if valid (TS-05 path)
5. Otherwise: clear error `"Skill asset delivery temporarily unavailable (503). Status: status.flywheel.ai"`

---

## Feature Complexity Summary

| Feature | Complexity | Critical Path | Depends on |
|---------|------------|---------------|------------|
| TS-01 Version pinning | Moderate | YES | Alembic migration |
| TS-02 Checksum gate | Trivial | YES | — |
| TS-03 Atomic swap | Moderate | YES | TS-01, TS-02 |
| TS-04 Actionable errors | Trivial | YES | — |
| TS-05 Offline cache + TTL | Moderate | YES | TS-02 |
| TS-06 Ephemeral exec | Trivial | YES | TS-03 |
| TS-07 Module gating | Trivial | YES | v15.0 existing |
| TS-08 Dep closure | Moderate | YES | TS-01, TS-03 |
| DIFF-01 Central update | Trivial | Free from TS-01 | — |
| DIFF-02 Zero drift | Trivial | Free from TS-02 | — |
| DIFF-03 Retraction | Moderate | NO (can ship TS-only first) | TS-01, TS-05 |
| DIFF-04 Tenant variants | — | NO — architectural only | TS-01 |
| DIFF-05 Telemetry | Trivial | NO | TS-01 |
| DIFF-06 Any-file bundle | Trivial | Free from TS-03 | — |

---

## Dependencies on Existing Systems

### Supabase Storage
- **Likely bundle storage backend.** 20–50 KB bundles per skill, ~20 skills, versioning — fits well within Storage limits and pricing.
- **Alternative:** bytea column in a `skill_bundles` table. Simpler ops (no separate service), fine for small bundles. Recommendation: bytea for now; migrate to Storage only if bundles exceed ~500 KB or total storage > 1 GB.
- Existing Supabase Storage pattern from v21.0 document renditions can be reused.

### MCP server (existing from v8.0 / v15.0)
- New MCP tool: `flywheel_fetch_skill_bundle(name, version="latest-stable") -> {manifest, files[], sha256}`
- Existing `flywheel_fetch_skill_prompt` keeps working (backward compat).
- Existing `flywheel_fetch_skills` catalog stays the skill-discovery entry point.
- **MCP binary transport:** MCP protocol supports base64-encoded `blob` in resource responses — use this for the bundle tarball or return per-file JSON.

### Alembic migrations
- New tables: `skill_bundles (id, skill_id, version_semver, sha256, size_bytes, storage_ref, published_at, revoked_at, revoked_reason)`
- FK: `skill_bundles.skill_id → skills.id`
- **Remember Supabase DDL workaround** (from global memory): run each DDL statement as its own commit then `alembic stamp`.

### Existing `skills` table (from v8.0 Phase 77 + Phase 95)
- No schema change required; bundles live in a separate table referencing skills.
- `skills.has_bundle` convenience boolean could help MCP routing.

### Module gating (from v15.0 Phase 112)
- Reuse `@require_module("broker")` on the bundle fetch endpoint.
- Skills in `_shared/` and `gtm-shared/` have no module gate (available to all tenants).

### Existing CLI (`flywheel` package)
- New commands (post-MVP, optional): `flywheel skill cache clear`, `flywheel skill cache status`, `flywheel skill pin <name>@<version>`.
- **Not required** to ship the MVP — ephemeral exec runs transparently through MCP.

### Client-side ephemeral-exec helper
- New utility lives in the MCP client path (likely in the Flywheel CLI's MCP handler, not in a user-edited skill file).
- Implementation: `tempfile.TemporaryDirectory()` + `sys.path.insert()` + `importlib.util.spec_from_file_location()`.
- Cleanup at skill-invocation boundary (context manager pattern).

---

## Implications for Roadmap

Suggested phase ordering:

1. **Foundation: bundle schema + publish path** (TS-01 partial, TS-06 infra)
   - Alembic migration for `skill_bundles`
   - Server-side bundle build + upload + sha256 compute
   - Admin CLI/endpoint to publish a bundle for an existing skill

2. **MCP fetch endpoint + ephemeral exec** (TS-02, TS-03, TS-06, TS-08)
   - New MCP tool `flywheel_fetch_skill_bundle`
   - Client-side verify + tempdir + sys.path integration
   - Hard-path: one skill end-to-end (pick `_shared/context-protocol.md` as simplest)

3. **Broker scripts migration** (TS-07, DIFF-06 in practice)
   - Publish broker bundle (9 Python files + yaml + md)
   - Update broker SKILL.md to fetch from MCP instead of file paths
   - Retire `~/.claude/skills/broker/` dependency from the router

4. **Resilience: cache + offline + errors** (TS-04, TS-05)
   - Content-addressed local cache
   - TTL + conditional revalidate
   - Error taxonomy + user-facing messages

5. **Hardening: retraction + telemetry** (DIFF-03, DIFF-05)
   - `revoked_at` column + 410 Gone handling
   - Fetch log table + simple admin dashboard

6. **Cleanup: retire legacy distribution**
   - Remove `~/.claude/skills/broker/` git repo as a distribution channel
   - Update install docs
   - Codebase-wide grep for any lingering file-path references (per user's cleanup-phases preference)

Phase 3 is the "broker dogfood" moment — once that lands, the value of v22.0 is visible and further phases are incremental.

---

## Sources

- [AWS Lambda: Managing Lambda dependencies with layers](https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html) — HIGH (official docs, ephemeral /tmp + layer immutability + version ARN pinning)
- [Layers in AWS Lambda: Production Patterns (2026)](https://thelinuxcode.com/layers-in-aws-lambda-production-patterns-pitfalls-and-practical-workflows-2026/) — MEDIUM (version pinning as production pattern)
- [Cloudflare Workers: How Workers works](https://developers.cloudflare.com/workers/reference/how-workers-works/) — HIGH (isolates + all-at-once deployment)
- [Cloudflare Workers: Versions & Deployments](https://developers.cloudflare.com/workers/configuration/versions-and-deployments/) — HIGH (atomic version semantics)
- [npm: package-lock.json](https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/) — HIGH (SHA-512 integrity verification)
- [Lockfile poisoning and hashes verify integrity](https://medium.com/node-js-cybersecurity/lockfile-poisoning-and-how-hashes-verify-integrity-in-node-js-lockfiles-0f105a6a18cd) — MEDIUM (why checksum gate matters)
- [Homebrew: Bottles documentation](https://docs.brew.sh/Bottles) — HIGH (SHA-256 bottle verification)
- [Homebrew: Checksum Deprecation](https://docs.brew.sh/Checksum_Deprecation) — HIGH (SHA-1/MD5 deprecated, SHA-256 required)
- [pip documentation: Caching](https://pip.pypa.io/en/stable/topics/caching/) — HIGH (ETag + conditional revalidate pattern)
- [MCP: Resources](https://modelcontextprotocol.info/docs/concepts/resources/) — HIGH (base64 blob binary transport)
- [Deno: DENO_DIR, Code Fetch and Cache](https://denolib.gitbook.io/guide/advanced/deno_dir-code-fetch-and-cache) — MEDIUM (remote import + cache-to-disk pattern)
- [Deno: Security and permissions](https://docs.deno.com/runtime/fundamentals/security/) — HIGH (trusted-registries model)
- [Python docs: importlib](https://docs.python.org/3/library/importlib.html) — HIGH (spec_from_file_location dynamic import)
- [Python docs: tempfile](https://docs.python.org/3/library/tempfile.html) — HIGH (context-manager cleanup semantics)
- [The Register: Claude Code collaboration tools allowed remote code execution (Feb 2026)](https://www.theregister.com/2026/02/26/clade_code_cves/) — MEDIUM (recent RCE footgun in adjacent system — motivates TS-02 and AF-08 trade-off)
- [Axios supply-chain incident (March 2026)](https://www.aikido.dev/blog/software-supply-chain-security-vulnerabilities) — MEDIUM (recent maintainer-compromise — motivates AF-01, AF-03, DIFF-03)
- [npx documentation](https://docs.npmjs.com/cli/v11/commands/npx/) — HIGH (fetch-once-run-once pattern reference)
- [Bundler compact index (historical context)](https://nesbitt.io/2025/12/28/the-compact-index.html) — MEDIUM (why transitive dep resolution is hard, motivates AF-02)
