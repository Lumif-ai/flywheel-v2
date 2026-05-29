# Domain Pitfalls: v22.0 Skill Platform Consolidation

**Project:** Server-hosted skill asset bundles + ephemeral fetch-to-exec delivery for Flywheel skills
**Researched:** 2026-04-17
**Scope:** Moving Python scripts from `~/.claude/skills/*/` (local git clone) to Flywheel backend (DB-stored or Supabase Storage) delivered on-demand via MCP to an ephemeral temp dir on the user's machine for execution.
**Confidence:** HIGH for Supabase/Playwright/Python/PgBouncer pitfalls (codebase-verified + current docs); MEDIUM-HIGH for CC/MCP caching behaviors (verified via Anthropic issue tracker).

---

## Critical Pitfalls

Mistakes that cause data loss, security compromise, or forced rollback. These MUST be designed away at the plan level — no runtime mitigation can recover from them.

### Pitfall C1: Unsigned Remote Code Execution Pipeline
**Category:** Security
**Phase to address:** Foundation phase (before any fetch-and-exec is wired)

**What goes wrong:**
The new pipeline pulls Python source from the Flywheel backend and `exec`s it (or imports it) on the user's machine. If the backend is compromised — via stolen service-role key, SQL injection into the `skill_assets` table, or a malicious migration merged into `seed.py` — every Flywheel user receives attacker-controlled code and runs it with the user's full local privileges. The Axios npm postinstall attack (March 2026) demonstrated this exact threat: a single compromised package hit millions of machines because installers executed unsigned code without verification. Our attack surface is arguably worse than npm because every `fetch_skill_prompt` call becomes a live RCE vector (not just install-time).

**Why the current local-git-clone model is safer than it looks:**
Users currently pull `~/.claude/skills/` via `git pull`. The git history is auditable, commits are signed (if configured), and a pull is an explicit user action. Moving to server-push inverts this: the user no longer controls when new code arrives.

**Warning signs:**
- No `SHA-256` or `Ed25519` signature field on the skill asset row
- Backend has any path where unauthenticated or low-privilege callers can insert rows into `skill_assets`
- MCP client blindly `exec`s whatever bytes the backend returns
- No pinned version — client always fetches "latest"
- Service-role key used to write assets (no scoped write role)

**Prevention:**
1. **Sign every asset bundle.** Generate an Ed25519 keypair offline; store the private key on an airgapped dev machine or KMS; publish the public key as a constant in the MCP client code (or ship it with the installer). Every bundle row in the DB carries `sha256_checksum` and `ed25519_signature` columns. Client refuses to execute a bundle whose signature doesn't verify against the pinned public key. Ed25519 is immune to side-channel attacks and doesn't need entropy at sign time, making it well-suited to a CI-signing pipeline.
2. **Pin versions, not "latest".** The skill prompt explicitly names the asset version (e.g., `broker/portals/mapfre.py@v3`). Fetching by version + checksum makes silent substitution impossible.
3. **Separate write authority from read authority.** Asset seeding uses a dedicated `skill_publisher` role that has `INSERT` only on `skill_assets` and only from CI. The regular backend service role can `SELECT` but not `INSERT`/`UPDATE`.
4. **Log every fetch.** Asset pulls write an audit row (user_id, skill_name, version, checksum, timestamp). Unexpected fetch patterns (mass download, unknown checksum) trip an alarm.
5. **Tie execution to user consent for first-time new skills.** On first fetch of a never-seen skill version, the MCP client prints the skill name, version, checksum, and signer to stdout and requires a keypress — same pattern Claude Code uses for MCP tool approval.

**Detection:**
- Regularly diff the DB-hosted asset against the authoritative git source-of-truth
- Alert on any `UPDATE` to `skill_assets` rows (bundles should be immutable; new version = new row)
- Monitor signature verification failure rate (>0 is a security incident, not a bug)

### Pitfall C2: PgBouncer Silent DDL Rollback on `skill_assets` Table Creation
**Category:** Storage / Migration
**Phase to address:** Schema phase (first phase of the milestone)

**What goes wrong:**
The memory note and CLAUDE.md both document this: Supabase's PgBouncer commits `alembic_version` but silently rolls back multi-statement DDL in the same transaction. This is guaranteed to bite a `skill_assets` migration because it needs at minimum:
```
CREATE TABLE skill_assets (...)
CREATE INDEX skill_assets_name_version_idx ON skill_assets (skill_name, version)
CREATE INDEX skill_assets_checksum_idx ON skill_assets (sha256_checksum)
ALTER TABLE skill_assets ENABLE ROW LEVEL SECURITY
CREATE POLICY "service_role_all" ON skill_assets ...
```
Run them as one Alembic `upgrade()` and the table appears to exist (alembic_version updated) but actually doesn't. Subsequent seed.py explodes with `relation "skill_assets" does not exist`, and nobody can figure out why until they check with `\dt` directly in SQL Editor.

**Bytea-column amplifier:**
If the schema stores asset bytes as a `BYTEA` column (as opposed to a Supabase Storage path), adding a CHECK constraint on size or a partial index on content hash compounds the problem — each of those statements needs its own commit.

**Warning signs:**
- Alembic migration file has multiple `op.execute()` / `op.create_table()` / `op.create_index()` calls in one `upgrade()`
- Developer claims "the migration ran, I saw alembic stamp the version"
- `seed.py` fails with "relation does not exist" immediately after migration
- Supabase Dashboard `\dt` does not show the new table

**Prevention:**
1. Follow the established `broker_migration.py` pattern exactly: each DDL statement is its own `await session.execute(text(...))` + `await session.commit()`. Don't bundle.
2. After all DDL commits succeed, run `alembic stamp <revision>` to sync state. The `upgrade()` function in the alembic file documents what was done; it is not the execution path.
3. For any BYTEA column, also split out the `ALTER TABLE ... ALTER COLUMN ... SET STORAGE EXTERNAL` statement into its own commit (PostgreSQL TOAST configuration is a DDL operation).
4. Verify immediately after migration: `SELECT COUNT(*) FROM skill_assets;` should return 0, not an error. If it errors, the table didn't actually get created.

**Detection:**
- Add a smoke test in CI that queries `information_schema.tables WHERE table_name = 'skill_assets'` immediately after the migration script finishes
- The test fails fast if PgBouncer silently rolled back

### Pitfall C3: Dropping Legacy `~/.claude/skills/` Git Directory Breaks Active Users
**Category:** Migration
**Phase to address:** Migration / cutover phase (late, with long coexistence window)

**What goes wrong:**
Users are mostly developers with `~/.claude/skills/` as a git repo they pull from. If we retire the git repo (or stop publishing to it) the moment the server-hosted path works, any user who does `git pull` on their next workday gets no new skills — and worse, any user on an old laptop or offline/remote setup has no path to fresh skills at all. Worse still: CLAUDE.md's skill discovery protocol ("check `~/.claude/skills/skill-router/SKILL.md`") will silently read stale router data and miss new skills.

**Specific breakage surfaces:**
- `~/.claude/skills/skill-router/SKILL.md` is hardcoded as the discovery entry point in global CLAUDE.md instructions. If it stops being updated, skill discovery rots.
- Shared helpers (`~/.claude/skills/_shared/context_utils.py`, `~/.claude/skills/_shared/recipe_utils.py`) are imported by absolute path in 20+ skills. Retiring the directory breaks every import.
- `~/.claude/skills/broker/portals/mapfre.py` has `sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))` at module import time. Moving the file to a temp dir while keeping that line makes the script fall back to the wrong path.
- CI and dev environments that pre-provision `~/.claude/skills/` via a setup script will continue to work — masking breakage until a fresh machine is provisioned.

**Warning signs:**
- Any PR that deletes files from `~/.claude/skills/` without a migration flag
- Version mismatch between `skill-router/SKILL.md` in git vs DB
- A fresh-machine bootstrap test not in CI

**Prevention:**
1. **Long coexistence period (minimum one full milestone).** Both paths work: MCP fetches from backend if `skill-platform-server` feature flag is on; else falls back to local `~/.claude/skills/`. Ship server-hosted to a cohort of opt-in users for 2+ weeks before flipping default.
2. **Sync-skills command as mandatory step.** Provide `flywheel sync-skills` (or similar) that refreshes local `~/.claude/skills/` as a read-through cache from the server. Users who `git pull` instead still get content — just stale content with a deprecation warning.
3. **Keep `skill-router/SKILL.md` authoritative.** Either pin the router to git for the whole coexistence window, or publish router contents to a stable URL that both git and server-path can read.
4. **Codebase-wide grep for hardcoded paths.** Before flipping the default, grep for `~/.claude/skills/`, `/.claude/skills/`, `expanduser("~/.claude")`, and `Path.home() / ".claude"`. Every hit is a potential break site — either update to support both modes or mark the file for retirement.
5. **Bootstrap test in CI on a clean container.** A fresh Ubuntu container with no `~/.claude/` dir runs a smoke test that fetches and runs the broker recipe skill end-to-end.

**Detection:**
- Per-user telemetry: which skill code path did they hit (git / server / cache)?
- CI matrix with both "has legacy git skills dir" and "fresh install" scenarios

### Pitfall C4: Playwright Persistent Session Data Obliterated by Ephemeral Temp Dir
**Category:** Execution / Migration
**Phase to address:** Skill packaging phase (before moving any portal script)

**What goes wrong:**
The broker portal scripts (`mapfre.py`) use Playwright with `launch_persistent_context(user_data_dir=...)` so brokers authenticate once to Mapfre and reuse cookies/session across runs. Persistent context functions by saving browser data to `user_data_dir` and loading it again on next launch. Today that directory lives at a stable path (`~/.claude/skills/broker/portals/.mapfre-profile/` or similar). If we move the script to a temp dir for ephemeral execution AND the script resolves `user_data_dir` relative to `__file__`, the profile moves with it and gets destroyed on cleanup. Broker logs back in every single time, and any two-factor/captcha triggers make the workflow unusable.

**Compounding factors:**
- Playwright does not allow two browser instances with the same user_data_dir. If two skill runs overlap (quote-extract + portal-fill), one dies.
- Chromium recent policy changes already make user_data_dir fragile — pointing it at Chrome's main profile doesn't work. Playwright's own docs warn about this.
- Empty string for user_data_dir creates a new temp profile every time — the exact anti-pattern we'd accidentally create.

**Warning signs:**
- Script resolves profile path relative to `__file__` or script location
- Script accepts `user_data_dir` from an environment variable but the env variable is set to something under `/tmp`
- Script uses `tempfile.mkdtemp()` for the profile dir
- Broker reports "I keep getting logged out of Mapfre"
- `launch_persistent_context(user_data_dir="")` with empty string

**Prevention:**
1. **Script code ships ephemerally; persistent state stays stable.** The skill asset bundle contains the Python script and its yaml manifest only. Runtime state — the Playwright user_data_dir, downloaded artifacts, screenshots — lives at a per-user stable path (`~/.flywheel/broker/portals/<carrier>/profile/`) that the script resolves via `Path.home()`, not `__file__`.
2. **Separate "code" from "state" explicitly in the script contract.** Every portal script must declare `STATE_DIR = Path.home() / ".flywheel" / "broker" / "portals" / "<carrier>"` at top of file. Code review rejects any script that resolves state paths relative to the script location.
3. **Single-instance lock on user_data_dir.** The script acquires a file lock (`fcntl.flock` on Linux/Mac, `msvcrt.locking` on Windows) on the profile directory before launching the browser, to prevent concurrent skill runs from corrupting the profile. Playwright GitHub Issue #35466 documents profile corruption when two instances race.
4. **Playwright browser binaries stay globally installed via `playwright install chromium`.** Do NOT bundle Playwright browsers in the skill asset — they're too large, they live at a stable OS-specific path, and we want the user's `playwright install` step to remain valid across skill updates.

**Detection:**
- Every portal script includes a smoke test that: runs → captures screenshot → re-runs → confirms no re-login occurred → persists state across sleep-5-seconds-and-restart
- Telemetry: time-to-first-action in portal scripts. If it spikes (login flow runs every time), profile isn't persisting.

### Pitfall C5: Asset Version Drift from Prompt Version — Prompt Calls Function That Doesn't Exist
**Category:** Versioning
**Phase to address:** Skill packaging + fetch-client phases

**What goes wrong:**
A skill has two parts: the prompt (stored in `skills` table, already server-hosted per the current MCP design) and the Python asset bundle (new — `skill_assets` table). Nothing currently guarantees these two move in lockstep. Scenario: dev updates `broker/portals/mapfre.py` to rename `fill_portal()` → `submit_portal()` and publishes asset v4. They forget to update the prompt. CC receives the new prompt (v7, from `skills` table which refreshed) but calls `fill_portal(...)` — which no longer exists in asset v4. Runtime `AttributeError`.

The inverse is also bad: prompt updated (v8) to call `submit_portal()`, asset still v3, old `fill_portal` signature. Different `AttributeError` — but discovered at a different point in the workflow.

Plugin-store-style manifest architectures handle this by pinning prompt→asset version pairs in a single registry.json, and treating each release as immutable. We need the same.

**Warning signs:**
- Prompt and asset can be updated independently (separate migrations, separate files, separate PRs)
- No compatibility contract encoded in code ("prompt v7 requires asset v3+")
- Asset bundle is versioned globally (v1, v2, v3) instead of per-skill (broker-mapfre-v3)
- No client-side check that prompt-expected asset version matches fetched version

**Prevention:**
1. **Single skill manifest per skill, one versioning lineage.** `skill_assets` row stores `prompt_md` + `python_files[]` + `yaml_configs[]` + `version` + `sha256` as an atomic unit. A new version means a full new row; no in-place updates. The `skills` table references `skill_assets.id` directly — there is no scenario where prompt v7 is live but the asset version it expects is not.
2. **Compatibility range, not floor.** Prompt declares `asset_versions_supported: [3, 4, 5]` in frontmatter. Client refuses to run if the fetched asset is outside the range. Forces deliberate testing of prompt/asset combos.
3. **Seed order discipline.** `seed.py` inserts/updates `skill_assets` BEFORE `skills` (or inserts both atomically in a transaction — but see Pitfall C2, you can't transact DDL but you CAN transact row inserts if using direct connection not PgBouncer). Never a window where prompt is live but asset isn't.
4. **Integration test: every skill fetch-then-invoke round-trip.** CI test loads a skill's prompt, parses it for function calls, fetches the asset bundle, imports it, and asserts every named function exists with the expected signature via `inspect.signature`.

**Detection:**
- `AttributeError: module 'mapfre' has no attribute 'fill_portal'` in production logs is a drift indicator
- Asset-version telemetry per prompt invocation — outliers (old asset + new prompt) are drift indicators

---

## Moderate Pitfalls

Mistakes that cause outages, incident pages, or user-visible slowness. Recoverable, but expensive.

### Pitfall M1: Signed URL Expiry + CDN Cache Mismatch Silently Serves Revoked Content
**Category:** Storage
**Phase to address:** Asset-storage implementation phase

**What goes wrong:**
If the milestone uses Supabase Storage for asset bundles with `createSignedUrl(path, expiresIn=3600)`, the signed URL expires in an hour, BUT the CDN cache keyed on that URL can continue serving the response for however long `cacheControl` says. A revoked/rotated asset (e.g., after the security pitfall above is discovered and we need to pull a bundle) stays reachable through any stale cached URL. Supabase documents this explicitly: token expiry and CDN cache TTL are independent.

**Warning signs:**
- `cacheControl` is set to hours or days (typical naive default)
- Signed URL generated once, reused across multiple skill fetches
- No way to rotate a bundle short of waiting for cache TTL

**Prevention:**
1. Generate signed URLs with short expiry (60–120 seconds) — just long enough for fetch+verify.
2. Set `cacheControl: "no-store"` on asset uploads. Skill assets are rarely-read and small; cache hit rate is irrelevant. Correctness trumps latency.
3. When rotating/revoking a bundle, delete the object (not just the row) so the object key is gone even from cache paths that try to refetch.
4. The signed URL itself is never persisted — MCP generates one per fetch, hands it to the HTTP client, and discards it.

**Detection:**
- After a deliberate rotation test, verify that the old URL returns 404 within 60 seconds.

### Pitfall M2: Missing or Wrong RLS Policies Expose Entire Bundle to Anonymous
**Category:** Storage / Security
**Phase to address:** Schema phase alongside bucket creation

**What goes wrong:**
Supabase Storage RLS is conceptually simple but easy to get wrong in two directions:
- **Too permissive:** Bucket created as "Public" for convenience. Public buckets bypass all RLS and any URL is accessible to anyone who guesses it (and with predictable naming like `/broker/mapfre/v3.tar.gz`, guessing is trivial).
- **Too restrictive:** Bucket private but no SELECT policy defined. Signed URL generation itself may succeed but the fetch with anon key fails. Some Supabase storage errors return 400 (StorageUnknownError) instead of 403, making the root cause hard to diagnose.
- **Service-role-only writes.** The seed.py script uses the service-role key to upload bundles. Service role bypasses RLS — if that key leaks, attacker can upload malicious bundles.

**Warning signs:**
- Bucket configured as Public in the UI or API
- No policies shown when you query `storage.policies` for the bucket
- Seed script uses `SUPABASE_SERVICE_ROLE_KEY`
- 400-range storage errors instead of clear 403s

**Prevention:**
1. Private bucket only. Never public for skill bundles. The intent-signal alone ("skill code is private") justifies this even if we think the code is non-sensitive.
2. RLS policies: SELECT for authenticated users with valid JWT; INSERT/UPDATE/DELETE for the dedicated `skill_publisher` role only (see Pitfall C1).
3. Use signed URLs for fetch, not presigned upload URLs (the presigned upload RLS bug documented in supabase/storage-js #186 bites direct-upload flows).
4. Migration test: spin up a fresh Supabase project, run the migration, and verify with an anon JWT that fetch fails without RLS, and succeeds with a proper auth token.

**Detection:**
- Supabase Advisor lint `0013_rls_disabled_in_public` flags any table/bucket without RLS
- Manual `curl` against the bucket with no auth header on every deploy

### Pitfall M3: Concurrent Seed Re-runs Race on Asset Uploads
**Category:** Storage / Migration
**Phase to address:** Seed pipeline phase

**What goes wrong:**
`seed.py` re-runs are common in dev. If two devs (or CI + a dev) run seed at the same time against the same Supabase, both try to upload `broker/mapfre/v3.tar.gz` concurrently. Supabase Storage has no native idempotency — second upload may overwrite, fail with a race error, or end up half-uploaded. If the DB row for `skill_assets` is inserted before the storage object is confirmed, clients fetch the row and then 404 on the object.

**Warning signs:**
- Seed writes DB row then uploads object (wrong order)
- Seed doesn't check if object already exists with matching checksum before uploading
- Seed runs without a lock — multiple concurrent executions are possible

**Prevention:**
1. **Upload-then-row, verify-then-commit.** Seed uploads the object, reads it back to verify the checksum matches the local file, then inserts the row. If upload fails, no orphan row. If row insert fails, no orphan row either — the object is content-addressed by its checksum so it's safe to leave.
2. **Content-addressed paths.** Store at `skills/<sha256>` not `skills/broker/mapfre/v3.tar.gz`. Same content = same path = safe to re-upload idempotently.
3. **Separate row for "published" status.** The `skill_assets` row has a `status` column (`pending` → `uploaded` → `published`). Clients only resolve `published` rows. Seed sets `pending`, uploads, verifies, flips to `published` in one UPDATE.
4. **Seed-level advisory lock.** `SELECT pg_advisory_lock(hashtext('seed-skills'))` at seed start; unlock at end. Second concurrent seed waits rather than races.

**Detection:**
- Fetch + verify round-trip on every seed as a smoke test
- Alert on `skill_assets.status = 'pending'` rows older than 5 minutes

### Pitfall M4: /tmp Collision Across Concurrent Skill Runs
**Category:** Execution
**Phase to address:** Fetch-client phase

**What goes wrong:**
Simple implementation: `tempfile.mkdtemp(prefix="flywheel-skill-")` + extract bundle → `sys.path.insert(0, tmpdir)` → `import mapfre` → run. Now the user runs another skill that happens to import a different version of the same module name. Python's `sys.modules` cache keeps the first version; the second skill silently uses stale code. Or worse — two parallel CC sessions both run broker skills at the same time; one cleans up its tmpdir while the other is mid-execution.

**Additional gotchas:**
- `tempfile.mktemp()` (without `k`) has a documented race condition — never use it. Always `mkstemp` or `mkdtemp`.
- `importlib` has a known race (CPython issue 143650) where stale module refs escape `sys.modules` under concurrent failed imports.
- `sys.path` pollution is process-global; one skill can poison another's imports.

**Warning signs:**
- `sys.path.insert(0, tmpdir)` with no cleanup of matching `sys.path.remove`
- Bundle structure has generic module names (`utils.py`, `helpers.py`, `base.py`) that collide across skills
- Single persistent Python process serving multiple skill invocations
- Using `exec()` with a shared globals dict

**Prevention:**
1. **Subprocess-per-skill-run.** Each skill invocation runs in a fresh `python -m flywheel.skill_runner <bundle_path>` subprocess. Exit cleans up everything. No sys.modules pollution, no sys.path mutation, no race on import.
2. **Unique per-run tmpdir via `mkdtemp`** (not `mktemp`). Prefix includes skill name AND PID AND a UUID4: `flywheel-mapfre-12345-ab3f.../`. Collisions functionally impossible.
3. **Namespaced module imports.** Bundle extracts to `/tmp/flywheel-.../mapfre_v3/` and is imported as `mapfre_v3` not `mapfre`. Version suffix prevents shadow-loading.
4. **Clean-up on exit via `atexit` + explicit try/finally.** Subprocess model makes this trivial (OS reclaims on exit). If in-process is insisted on, `tempfile.TemporaryDirectory()` context manager is mandatory.

**Detection:**
- Stress test: invoke 10 different skills concurrently from 3 CC sessions. Every run should succeed with no cross-contamination.
- Monitor `/tmp/flywheel-*` directories older than 1 hour — stale tmpdirs indicate cleanup failures.

### Pitfall M5: MCP Client Caches Skill Manifest Forever — New Skills Invisible Until CC Restart
**Category:** CC-side fetch
**Phase to address:** Fetch-client phase

**What goes wrong:**
Anthropic issue #7519 documents exactly this: Claude Desktop MCP client caches manifest/tool metadata in memory at connection time and has no mechanism to force a refresh. Issue #27142 notes that when Mcp-Session-Id becomes invalid, tools silently break and require a full CLI restart. If we land the server-hosted skill platform and then publish a new skill on Tuesday, every CC instance that connected before Tuesday won't see it. Users complain "the skill isn't there" and we chase a non-bug for a week.

**Warning signs:**
- `flywheel_fetch_skills` returns the same list across a 24-hour session
- No TTL on the MCP client's cached skill list
- Adding a new skill requires users to restart CC

**Prevention:**
1. **Cache with short TTL.** `flywheel_fetch_skills` caches for 60–120 seconds max, then re-fetches. Users tolerate a 1-minute latency-to-visibility; they don't tolerate "restart CC".
2. **Cache-buster version header.** Every skill list response includes a manifest version/etag. Prompt fetch includes this etag; mismatch triggers a forced refresh.
3. **Explicit refresh tool.** Expose `flywheel_refresh_skills` as an MCP tool that drops all caches. Document it as "run this if you just published a new skill".
4. **Version-scoped prompt fetches.** `flywheel_fetch_skill_prompt(skill_name, version=None)` — if version is omitted, server returns latest and includes the actual resolved version in the response. CC can then detect version drift.

**Detection:**
- Add a CI test that publishes a skill, calls `flywheel_fetch_skills` via a long-running test harness, and asserts visibility within TTL window.

### Pitfall M6: Slow Network Fetch on CC Invocation Blocks the Skill Call
**Category:** CC-side fetch
**Phase to address:** Fetch-client phase

**What goes wrong:**
CC invokes a skill → MCP fetches prompt → MCP fetches asset bundle from backend → backend hits Supabase Storage → network is slow (office wifi, airplane, ngrok throttled). The user sees "skill starting..." for 8 seconds. Enough retries add up to a minute. If the auth token expires mid-fetch, the retry is not just slow, it's a silent 401 → confused user.

**Additional gotchas:**
- No exponential backoff = retry storm on backend when Supabase has a brief hiccup
- JWT expiry midway through a multi-file fetch leaves some files successful and some 401s
- Backend uses ngrok (per memory: `methodical-jessenia-unannotated.ngrok-free.dev`) which has rate limits on free tier

**Prevention:**
1. **Local read-through cache.** First fetch downloads to `~/.flywheel/cache/skills/<sha256>/`. Subsequent invocations use the cached bundle IF the checksum in the DB still matches. Only re-fetch on checksum mismatch or cache miss.
2. **Exponential backoff with jitter** on fetch retries: 500ms → 1s → 2s → 4s, max 3 retries. OpenAI Agents SDK supports `max_retry_attempts` and `retry_backoff_seconds_base` — mirror that.
3. **Fail-fast timeouts.** 3s connect, 10s total. User sees "skill fetch failed, falling back to local cache or git mirror" in 10s worst case, not infinite hang.
4. **Refresh auth token proactively.** Before a multi-file fetch, check token expiry. If within 5 minutes of expiry, refresh first. Don't let a long-running fetch discover expiry mid-way.
5. **Offline fallback.** If the backend is unreachable AND `~/.claude/skills/` still exists from the coexistence period, fall through to the local path with a stdout warning. User gets degraded service, not zero service.

**Detection:**
- p99 latency metric on `flywheel_fetch_skill_prompt` — should be under 500ms steady-state, under 3s on cold cache.
- Retry-count metric — sustained >0 retry-rate indicates backend or network problem.

### Pitfall M7: Asset Rows Inserted Before Backfill Breaks Existing Users
**Category:** Migration / Versioning
**Phase to address:** Migration cutover phase

**What goes wrong:**
During the coexistence period, a user's local `~/.claude/skills/broker/portals/mapfre.py@v3` and the newly-seeded `skill_assets.broker-portals-mapfre@v4` differ. If the prompt in the `skills` table was updated to v4 but the user's MCP client is on the old version that still reads local, they get a prompt-version mismatch without any signal. Or vice versa — MCP client on new version fetches asset v4 which was seeded from git v4 which was never actually tested against the v4 prompt because of a tagging bug.

**Warning signs:**
- Seed.py source-of-truth is ambiguous (two git branches with different versions)
- No pre-seed integration test
- Seed can run partially (some skills succeed, some fail) without aborting

**Prevention:**
1. **One source of truth for both legacy and new paths during coexistence.** The authoritative skill content lives in the codebase at `skills/` (project path). `seed.py` publishes to `skill_assets` table. `tools/sync-to-claude-home.sh` mirrors to `~/.claude/skills/` for legacy users. Both pipelines run from the same source. Never edit `~/.claude/skills/` directly.
2. **Seed is atomic at the skill-version level.** Each skill+version seed is one transaction: insert all files, verify, mark published. Partial failures don't leave published=true for partial data.
3. **Backfill before flip.** Phase order is strict: (a) schema, (b) upload all current skills to `skill_assets`, (c) verify byte-for-byte match with legacy, (d) wire MCP fetch with opt-in flag, (e) only then enable for cohort, (f) only much later flip default.

**Detection:**
- Byte-diff test: for every skill, assert `sha256(skill_assets.bundle) == sha256(legacy ~/.claude/skills/<skill>/)` immediately after seed.

---

## Minor Pitfalls

Mistakes that cause developer friction, minor bugs, or annoyance. Easy to fix when encountered.

### Pitfall m1: Bundling Playwright Browser Binaries Into Asset
**Category:** Execution / Migration
**Phase:** Skill packaging

**What goes wrong:** Someone tries to bundle `chromium` into the asset tarball for "self-contained portability". Bundles bloat to 300MB, fetches become unacceptably slow, and Chromium path resolution breaks because it depends on OS-specific install layouts.

**Prevention:** Skill assets contain Python source + yaml + small fixtures only. Playwright browsers are a user-local install via `playwright install chromium` as a one-time bootstrap step. Document it in installer README.

### Pitfall m2: Bundle Format Lock-In (tarball vs JSON vs base64-in-bytea)
**Category:** Storage
**Phase:** Schema phase

**What goes wrong:** Picking a bundle format without thinking. If bundles are `BYTEA` in Postgres with base64 encoding inside, payloads inflate 33% for no reason. If bundles are a single `.tar.gz`, diffing between versions is expensive. If bundles are a JSON blob with files as base64 strings, streaming large files is awkward.

**Prevention:** Pick Supabase Storage (object) with a DB row holding metadata + checksum + manifest. Bundle is a plain `.tar.gz` of the skill directory. Simple, streamable, toolable, compressible.

### Pitfall m3: No Offline Development Mode for Skill Authors
**Category:** Testing
**Phase:** Fetch-client phase

**What goes wrong:** A skill author editing `mapfre.py` locally wants to test changes without publishing to the server. If the MCP client always fetches from server, the iteration loop becomes: edit → publish → test → fix → publish → test. Slow and polluting.

**Prevention:**
1. `FLYWHEEL_SKILL_OVERRIDE=/path/to/local/skills` env var. When set, MCP reads local files instead of fetching. Dev-only, loudly logged.
2. Document the flow in `skill-standards.md`.

### Pitfall m4: Unit Tests Hit the Network
**Category:** Testing
**Phase:** Fetch-client phase

**What goes wrong:** Devs wire the MCP client's fetch path with `httpx.AsyncClient()` as a module-level default. Every unit test now requires network access to Supabase to instantiate a test fixture. CI goes flaky.

**Prevention:**
1. Use `pytest-mock` / `mocker` fixture to patch the HTTP client at test-module scope. `mocker` auto-resets after each test.
2. Ship a `FakeSkillFetcher` class in `tests/fixtures/` that returns canned responses from disk. Tests request it as a fixture; production code doesn't know it exists.
3. Test real fetching with a single marked integration test (`@pytest.mark.integration`) that CI runs separately from the unit suite.

### Pitfall m5: Bucket-Not-Found on Fresh Environments
**Category:** Storage
**Phase:** Migration / developer onboarding

**What goes wrong:** A new dev pulls the repo, runs migrations, runs seed — but nobody created the `skill-bundles` bucket in their fresh Supabase project. Seed explodes with "bucket not found". Error is unhelpful; dev wastes 30 minutes.

**Prevention:**
1. Seed script's first step is `supabase.storage.create_bucket("skill-bundles", public=False)` with `if-not-exists` semantics. Idempotent, safe to re-run.
2. Document in README: bucket creation is automatic, no manual Supabase UI step required.

### Pitfall m6: No Cost Monitoring on Storage Bandwidth
**Category:** Storage
**Phase:** Post-launch observation

**What goes wrong:** Skill bundles are small but skill invocations are frequent. At 1k users × 50 skill invocations/day × 500KB avg bundle = 25GB/day egress. Supabase Storage pricing scales linearly. Without cache (Pitfall M6 prevention handles this) costs balloon silently.

**Prevention:**
1. Client cache (see Pitfall M6) cuts egress to near-zero steady state.
2. Alert on Supabase egress > expected baseline.

---

## Phase-Specific Warnings

Map pitfalls to the likely phase structure. Roadmapper uses this to allocate risk work.

| Phase Topic | Pitfalls to Guard | Mitigation Plan |
|-------------|-------------------|-----------------|
| **Schema (new `skill_assets` table + bucket + RLS)** | C2 (PgBouncer), M2 (RLS), m5 (bucket creation) | Per-statement commits; private bucket; idempotent seed |
| **Asset-signing infrastructure** | C1 (unsigned RCE) | Ed25519 keys generated before any asset upload; public key pinned in MCP client source |
| **Seed / publish pipeline** | C1 (write privileges), C5 (version drift), M3 (concurrent seed), M7 (partial backfill) | Dedicated publisher role; one-transaction skill-version seed; pg_advisory_lock; content-addressed paths |
| **Fetch client (MCP-side)** | C1 (signature verify), M4 (/tmp collision), M5 (manifest cache), M6 (network latency), m3 (offline mode), m4 (test isolation) | Verify-before-exec; subprocess-per-run; short-TTL caches; exp backoff; override env var; mock fixtures |
| **Skill packaging (broker skills migrate first)** | C4 (Playwright state), C5 (version drift), m1 (no browsers in bundle) | STATE_DIR at `~/.flywheel/`; compat ranges; bundle = source only |
| **Migration / cutover** | C3 (breaking git users), M7 (legacy drift) | Coexistence flag; sync-skills command; codebase grep before flip |
| **Rotation / security response** | M1 (signed URL + CDN cache) | Short-TTL URLs; delete object on rotate; no-store cacheControl |
| **Testing / CI** | m4 (network in tests), C4 (Playwright integration) | mocker fixture; FakeSkillFetcher; @pytest.mark.integration separation |

### Phases with high risk density
- **Fetch client phase** concentrates four moderate pitfalls (M4, M5, M6) and one critical (C1 verification). Allocate extra research/review budget here.
- **Migration cutover phase** has two critical pitfalls (C3, C5) and one moderate (M7). Must not be rushed; coexistence window should be measured in weeks, not days.

### Phases unlikely to need /gsd:research-phase
- Schema phase: PgBouncer workaround is documented in memory; RLS template is established.
- Asset-signing phase: Ed25519 pattern is standard; no novel research needed beyond key-custody operational decisions.

---

## What Changed From Current Architecture

This section surfaces the explicit delta vs today's model so planning can reason about every changed surface.

| Dimension | Today (legacy local git) | After v22.0 (server-hosted) | New pitfall class introduced |
|-----------|--------------------------|------------------------------|------------------------------|
| Code delivery | User-initiated `git pull` | Server push via MCP fetch | C1 RCE pipeline |
| Integrity | Git history + signed commits (if user configures) | Ed25519 signature in DB | C1 (if not implemented correctly) |
| Locality | `~/.claude/skills/<skill>/` (stable path) | `/tmp/flywheel-.../` (ephemeral) | M4 collision, C4 Playwright state |
| Versioning | File content == version; controlled by git | Explicit version column + row | C5 prompt/asset drift |
| Storage | User's disk | Supabase Storage + Postgres | M1–M3 (URL/RLS/race), m5 (bucket) |
| Discovery | `skill-router/SKILL.md` read from disk | `flywheel_fetch_skills` MCP call | M5 cache stale |
| Fresh-machine install | `git clone ~/.claude/skills` | Server-backed; first invocation fetches | M6 slow fetch, m4 no offline |
| Breakage radius on compromise | One malicious commit affects one git-pulling user until discovered | One malicious row affects all users instantly | C1 amplified |

The critical takeaway: we are inverting who initiates code delivery (from pull to push) and where code lives at execution time (from stable to ephemeral). Both inversions introduce qualitatively new failure modes that no amount of testing against the legacy path will surface.

---

## Sources

### Primary (HIGH confidence)
- Project memory — Supabase PgBouncer DDL workaround documented in `/Users/sharan/Projects/flywheel-v2/.planning/research/SUMMARY.md` line 67 (Pitfall 1) and `/Users/sharan/.claude/projects/-Users-sharan-Projects-flywheel-v2/memory/MEMORY.md` "Supabase DDL workaround"
- Global CLAUDE.md — Database Migrations section confirming PgBouncer silent-rollback behavior
- `/Users/sharan/.claude/skills/broker/portals/mapfre.py` — verified `sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))` + Playwright persistent context usage
- `/Users/sharan/Projects/flywheel-v2/cli/flywheel_mcp/server.py` — confirmed existing `flywheel_fetch_skills` + `flywheel_fetch_skill_prompt` MCP tools
- `/Users/sharan/.claude/skills/_shared/` — confirmed cross-skill shared helpers (context_utils.py, recipe_utils.py) that would break on path migration

### Secondary (HIGH confidence via current docs)
- [Supabase Storage Signed URL + CDN cache behavior](https://github.com/orgs/supabase/discussions/6458)
- [Playwright persistent context + user_data_dir](https://playwright.dev/python/docs/api/class-browsertype)
- [Playwright Issue #35466 — profile corruption with concurrent instances](https://github.com/microsoft/playwright/issues/35466)
- [Supabase Storage Access Control](https://supabase.com/docs/guides/storage/security/access-control)
- [Ed25519 in Python cryptography library](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/)
- [Python tempfile race condition and mktemp vs mkstemp](https://docs.python.org/3/library/tempfile.html)
- [CPython Issue 143650 — importlib race with stale module refs](https://github.com/python/cpython/issues/143650)
- [Claude Code Issue 7519 — MCP manifest cache has no refresh mechanism](https://github.com/anthropics/claude-code/issues/7519)
- [Claude Code Issue 27142 — MCP Streamable HTTP session invalidation](https://github.com/anthropics/claude-code/issues/27142)

### Tertiary (supporting context)
- [Microsoft Security Blog — Mitigating Axios npm supply chain compromise](https://www.microsoft.com/en-us/security/blog/2026/04/01/mitigating-the-axios-npm-supply-chain-compromise/) — reference pattern for install-time code execution attack class
- [Zscaler ThreatLabz — Supply Chain Attacks March 2026](https://www.zscaler.com/blogs/security-research/supply-chain-attacks-surge-march-2026) — attack-class context for unsigned-code-delivery risk
- [Plugin Architecture: Versioning & Distribution](https://oninebx.github.io/blog/architecture/plugin-architecture-in-practice-part-4-versioning-distribution-and-ecosystem/) — registry.json immutability pattern
- [OpenAI Agents SDK MCP retry configuration](https://openai.github.io/openai-agents-python/ref/mcp/server/) — exponential backoff reference

---
*Research completed: 2026-04-17*
*Ready for /gsd:roadmap: yes — all pitfalls mapped to phases with prevention strategies*
