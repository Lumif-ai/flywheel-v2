# Architecture Patterns — v22.0 Skill Platform Consolidation

**Domain:** Server-hosted skill asset delivery — retire `~/.claude/skills/` git repo as distribution channel, migrate Python scripts + shared modules into Flywheel backend, deliver via MCP, execute ephemerally on CC side.
**Researched:** 2026-04-17
**Confidence:** HIGH on existing surface area (verified file-by-file); MEDIUM on recommended new shape (informed by existing patterns but not yet implemented).

**Prior research note:** `.planning/research/ARCHITECTURE.md` previously held v19.0 broker redesign content. This file replaces it with v22.0-specific architecture. Prior content lives in git history and in `.planning/SPEC-BROKER-REDESIGN.md`.

---

## Assumptions (stated, not buried)

1. **Assets are text-dominant.** Of the ~2.8K LoC to migrate, all files are Python/markdown/YAML. Largest single file is `_shared/context_utils.py` at 958 lines (~35 KB). Max realistic asset size per skill < 200 KB. Binary assets (if any future portal captures screenshots or fixtures) are out of scope for v22.0.
2. **Tenant scoping matches the existing skills model.** `skill_definitions` is tenant-neutral (service-role manage policy, `tenant_skills` override table for per-tenant enable/disable). Asset delivery inherits the same shape — assets are attached to skills, not tenants.
3. **Version atomicity.** Prompt and scripts must version together. A skill run picks up the scripts that match the prompt version it was handed — no split-brain.
4. **Fetch-to-temp-exec is the only execution model on CC side.** No persistent `~/.flywheel/skills-cache/`. Each invocation downloads fresh → `tempfile.TemporaryDirectory()` → executes → cleanup.
5. **CC is the executor.** The backend emits assets, CC writes them to tmp, the user's Python interpreter runs them. Backend does **not** execute bundled scripts (aligns with CC-as-brain / `protected=false` default per `063_skill_protected_default`).
6. **Supabase Storage is already plumbed.** `services/document_storage.py` already uses `uploads` and `documents` buckets with signed URL generation + service key. We can piggyback, not build from scratch.
7. **PgBouncer DDL workaround applies** to any new table/column (per-statement commits + `alembic stamp`, see `063_skill_protected_default.py` for template).

---

## Integration Points (existing code touched)

All paths absolute, verified against HEAD.

| # | File | Role in existing system | v22.0 contact point |
|---|------|------------------------|---------------------|
| 1 | `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/db/models.py` (lines 811–858) | `SkillDefinition` ORM | **MODIFY** — add `bundle_version`, `bundle_manifest` columns (JSONB), OR leave untouched and attach via FK from new `skill_assets` table. |
| 2 | `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/db/seed.py` (lines 210–326 `scan_skills`, 432–469 upsert loop) | Parses SKILL.md frontmatter + body, upserts `skill_definitions` | **MODIFY** — extend `SkillData` + `scan_skills` to also collect asset files from the skill directory; upsert asset rows alongside skill rows in the same transaction-group (per-commit pattern). |
| 3 | `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/skills.py` (lines 283–344 `get_skill_prompt`) | Returns `system_prompt` for a skill | **ADD SIBLING ENDPOINT** — `GET /skills/{name}/bundle` returning the asset manifest + signed URLs (or inline base64 content). Reuses the same tenant-override check (lines 296–322). |
| 4 | `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/services/document_storage.py` (lines 35–120) | Supabase Storage wrapper: `get_document_url`, `upload_file`, `download_file` with local fallback | **REUSE AS-IS** for a new `skill-assets` bucket. Factor the generic bits into a `_storage_core.py` if we want cleanliness, else just call directly with a new bucket name constant. |
| 5 | `/Users/sharan/Projects/flywheel-v2/cli/flywheel_mcp/server.py` (lines 322–337 `flywheel_fetch_skill_prompt`) | MCP tool returning `system_prompt` as plain string | **ADD NEW TOOL** — `flywheel_fetch_skill_bundle(skill_name)` returning JSON with manifest + fetch instructions. Prompt tool stays unchanged. |
| 6 | `/Users/sharan/Projects/flywheel-v2/cli/flywheel_mcp/api_client.py` (lines 145–151) | Thin REST client: `fetch_skills`, `fetch_skill_prompt` | **EXTEND** — add `fetch_skill_bundle(skill_name)` method calling the new `/bundle` endpoint. |
| 7 | `/Users/sharan/Projects/flywheel-v2/cli/flywheel_cli/main.py` (click group at line 125) | CLI entry point: `flywheel login`, `flywheel agent`, etc. | **ADD SUBCOMMAND** — `flywheel skill fetch <name> --into <dir>` for out-of-band debugging / CI. The MCP tool remains the normal path. |
| 8 | `/Users/sharan/Projects/flywheel-v2/skills/` (17 skill dirs, mostly SKILL.md-only stubs today) | Flywheel-v2 in-repo skills — already scanned by `seed.py` | **MIGRATION TARGET** — broker/, _shared/, gtm-shared/ move here from `~/.claude/skills/` so `seed.py` picks them up. Becomes source of truth. |
| 9 | `/Users/sharan/.claude/skills/` (~2.8K LoC, separate git repo) | Legacy distribution channel | **RETIRED** — contents migrated into `flywheel-v2/skills/`. Git repo archived, not deleted (rollback safety). |
| 10 | `/Users/sharan/Projects/flywheel-v2/backend/alembic/versions/` (063 is latest) | Migration history | **ADD** — `064_skill_assets.py` with PgBouncer per-statement workaround header (template from 063). |
| 11 | `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/skills.py` top-level imports & router mount | Router registered in main app | **NO CHANGE** — new endpoint is additive under existing `router = APIRouter(prefix="/skills")`. |

---

## New Components

### 1. `skill_assets` table (backend)

**Path:** `backend/src/flywheel/db/models.py` (new class block, after `TenantSkill` at line 884)

```python
class SkillAsset(Base):
    __tablename__ = "skill_assets"
    __table_args__ = (
        UniqueConstraint("skill_id", "path", "bundle_version",
                         name="uq_skill_assets_skill_path_version"),
        Index("idx_skill_assets_skill", "skill_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    skill_id: Mapped[UUID] = mapped_column(ForeignKey("skill_definitions.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(Text, nullable=False)        # "api_client.py", "portals/mapfre.py"
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)  # "<skill_id>/<sha>/api_client.py"
    mime_type: Mapped[str] = mapped_column(Text, server_default="text/plain")
    bundle_version: Mapped[str] = mapped_column(Text, nullable=False)  # mirrors SkillDefinition.version
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
```

**Storage decision — why this shape over alternatives:**

| Option | Verdict | Rationale |
|--------|---------|-----------|
| A. `bytea` column on `skill_definitions` | Rejected | Single-row BLOB forces re-upload of every asset on any edit. No per-file change detection. Kills `seed.py` idempotency (current seed only re-writes `system_prompt`; bytea would churn the whole row). |
| B. `skill_assets` rows with inline TEXT `content` column | Rejected | Works for ≤ 1 MB totals but tips PG row sizes into TOAST territory on `context_utils.py` (958 lines). Query ergonomics bad (every listing pulls content). |
| **C. `skill_assets` metadata rows + Supabase Storage for bytes** | **RECOMMENDED** | Reuses `services/document_storage.py` (lines 60–120). DB rows are cheap to query/list. Atomic versioning via the `bundle_version` column matching `SkillDefinition.version`. Signed URL delivery mirrors how broker documents are served today. Idempotent on content (SHA-indexed paths). |

The `bundle_version` column is the atomicity hook: bumping `SkillDefinition.version` means new rows with new storage paths, old rows kept until garbage-collected. A skill-run that reads manifest at version N gets only version-N assets, regardless of concurrent updates.

### 2. `skill-assets` Supabase Storage bucket

**Layout:** `<skill_id>/<bundle_version>/<path>` (path may contain slashes: `portals/mapfre.py`).

**Service:** reuse `backend/src/flywheel/services/document_storage.py` functions. Add a `SKILL_ASSETS_BUCKET = "skill-assets"` constant and thin wrappers `upload_skill_asset(...)`, `get_skill_asset_url(...)` that call the existing `httpx`-based Supabase REST endpoints. Local fallback (`local://`) already exists — free reliability in dev.

### 3. `GET /api/v1/skills/{name}/bundle` endpoint

**Path:** `backend/src/flywheel/api/skills.py` — new handler right after `get_skill_prompt` (around line 345).

**Response shape:**
```json
{
  "skill_name": "broker",
  "bundle_version": "1.1",
  "assets": [
    {
      "path": "api_client.py",
      "sha256": "...",
      "size": 5421,
      "url": "https://<supabase>/storage/v1/object/sign/skill-assets/...",
      "url_expires_at": "2026-04-17T12:30:00Z"
    },
    {"path": "portals/mapfre.py", "...": "..."},
    {"path": "steps/parse-contract.md", "...": "..."}
  ],
  "depends_on": ["_shared"]
}
```

**Auth:** reuses `require_tenant` + `get_tenant_db` dependencies already on `get_skill_prompt`. Same tenant-override gate (lines 296–322).

**Rate limit:** mirror the `@limiter.limit("10/minute")` already on the prompt endpoint.

**Tier check:** web_tier 3 skills (local-only) still qualify — bundles are specifically for local execution.

### 4. `flywheel_fetch_skill_bundle` MCP tool

**Path:** `cli/flywheel_mcp/server.py` — new `@mcp.tool(output_schema=None)` block near `flywheel_fetch_skill_prompt` (around line 338).

**Signature:**
```python
def flywheel_fetch_skill_bundle(skill_name: str) -> str:
    """Fetch script bundle (Python/markdown files) for a skill.

    Returns a JSON string with the manifest and instructions for the
    bundled exec helper. CC does NOT download bytes directly — it calls
    the exec helper with the manifest JSON.
    """
```

**Returns:** JSON string identical to the REST response shape (tools return strings per existing pattern at lines 154–217, 322–337). CC receives it as a tool result and passes it verbatim to the exec helper.

**Why not return raw bytes?** MCP tool results are JSON-encoded text. Base64-encoding every asset in the tool response works but bloats token budget (Claude would see 35 KB+ of base64 per invocation). Signed URLs keep tool payload small; CC's exec helper handles the download out-of-band over plain HTTP.

### 5. CLI helper: `flywheel skill fetch` (optional convenience)

**Path:** `cli/flywheel_cli/main.py` — new click subcommand group around line 804.

```
flywheel skill fetch <skill_name> --into <dir>
```

For CI and debugging: downloads a bundle to a persistent directory. Not the normal path — the MCP tool + exec helper is.

### 6. Ephemeral exec helper (new module)

**Path:** `cli/flywheel_mcp/exec_helper.py` (new file, ~120 lines).

**Responsibilities:**
1. Accept a bundle manifest JSON (from `flywheel_fetch_skill_bundle`).
2. Create `tempfile.TemporaryDirectory()` — auto-cleans on context exit.
3. Download each asset over HTTPS (concurrent, verify SHA256).
4. Also resolve `depends_on` shared modules recursively (single-level fanout — shared modules themselves cannot `depends_on`).
5. Write files preserving relative paths.
6. Inject the tmp dir onto `sys.path` via an `.envrc`-style wrapper OR expose the path so CC can pass it to subprocesses.
7. Yield the tmp dir; caller runs whatever subprocess needs it.
8. Cleanup: `TemporaryDirectory.__exit__` unlinks everything. No persistence.

**Why in `flywheel_mcp/` not `flywheel_cli/`?** The MCP server is the only caller today. `flywheel_cli/` can import from `flywheel_mcp/` (it already does — see `flywheel_mcp.api_client` importing `flywheel_cli.auth` at api_client.py line 9). Keep the helper near the tool that uses it.

**Why not embedded into each skill prompt?** Every skill would have to duplicate ~80 lines of "create tmp dir, fetch, verify, clean up." That is exactly the kind of cross-cutting concern the MCP layer should own. Skills just call `flywheel_fetch_skill_bundle` and then use the paths the helper yields.

**Why not a `flywheel` CLI subcommand only?** That would force every `/broker:*` invocation to shell out, losing structured MCP context and making testing harder. The CLI subcommand exists (item 5) but is the fallback, not the default.

### 7. Manifest model — SKILL.md frontmatter extension

**Recommended shape** (extends existing frontmatter parsed by `seed.py` lines 239–323):

```yaml
---
name: broker
version: "1.2"
description: ...
triggers: [...]
contract_reads: [...]
contract_writes: [...]
# NEW in v22.0:
assets:
  - api_client.py
  - field_validator.py
  - portals/base.py
  - portals/mapfre.py
  - portals/mapfre.yaml
  - steps/*.md
  - pipelines/*.md
depends_on:
  - _shared
---
```

**Why explicit manifest over filesystem-derived (the `seed.py` currently walks dirs):**

| Option | Verdict | Rationale |
|--------|---------|-----------|
| Filesystem-derived (seed walks dir) | Rejected | `seed.py` already skips `_shared/` and `_archived/` via `SKIP_DIRS` (line 33). It never descends into per-skill subdirs (`portals/`, `steps/`). Extending it to "walk everything" means walking test files, `__pycache__`, `.pytest_cache` — noise. Also silently pulls in files the author didn't intend to ship. |
| **Explicit manifest in frontmatter** | **RECOMMENDED** | Glob-friendly (`steps/*.md`), auditable (reviewers see the asset list in PR diffs), drop-in compatible with existing `parse_frontmatter` (dict with lists — works today in `_simple_yaml_parse`). Explicit `depends_on` makes cross-skill relationships visible. |
| DB-only (rows with no SKILL.md declaration) | Rejected | Forces out-of-band DB editing. Breaks the "SKILL.md is source of truth, seed.py is a one-way pipe" model that has worked across 6 milestones. |

**`seed.py` extension** (lines 308–324, where `SkillData` is constructed): add `assets: list[str]` and `depends_on: list[str]` fields, resolve globs against the skill directory, compute SHA256 + size for each resolved file, upload to storage bucket, and `pg_insert(SkillAsset).on_conflict_do_nothing()` per file. Per-statement commit pattern for DDL-adjacent changes (PgBouncer workaround).

### 8. Shared module resolution — first-class "library skills"

**Recommendation:** treat `_shared` and `gtm-shared` as **library skills** (first-class `skill_definitions` rows with `tags: ['library']`, `enabled: false` so they don't appear in user-facing catalogs).

**Why:**
- `seed.py` already handles them uniformly — no new code path.
- `_shared/context_utils.py` (958 lines) is imported by ~8 skills. Inlining it per skill multiplies storage 8× and creates version skew (skill A gets updated utils, skill B gets stale). Libraries ensure one version, one source.
- `depends_on: ["_shared"]` in a consumer skill's manifest is a clear, explicit declaration. The exec helper resolves it with a single extra `fetch_skill_bundle("_shared")` call.
- The `SKIP_DIRS = {"_archived", "_shared", "gtm-shared"}` in `seed.py` (line 33) gets narrowed to just `_archived`. `_shared` and `gtm-shared` become scannable as regular skills but with `enabled: false` and a `tags: ['library']` hint in their SKILL.md frontmatter.

**Alternatives considered:**

| Option | Verdict | Why not |
|--------|---------|---------|
| Inline-bundle duplicate per skill | Rejected | 8× storage inflation, version skew, diff noise on every shared-module update. |
| Hand-rolled shared-module table separate from skills | Rejected | Duplicates the tooling we already have for skills. Two seed loops, two APIs, two caches. |
| Single global "shared" skill with all shared code | Rejected | Can't evolve `_shared` and `gtm-shared` independently — they're used by different skill cohorts (broker vs GTM). |

### 9. Onboarding hook — retire local skills repo

**Path:** `cli/flywheel_cli/main.py` setup-claude-code command at line 624.

**Changes:** remove any git-clone-of-~/.claude/skills step from the install flow. The install becomes: "install MCP server → `flywheel login` → done." Skills are pulled on demand.

---

## Modified Components (change-summary)

| Component | File | Lines | Change |
|-----------|------|-------|--------|
| `SkillData` dataclass | `backend/src/flywheel/db/seed.py:49–65` | ~65 | Add `assets: list[str] = field(default_factory=list)`, `depends_on: list[str] = field(default_factory=list)`. |
| `scan_skills` | `backend/src/flywheel/db/seed.py:210–326` | ~110 | After constructing `SkillData`, resolve `assets` globs against the skill dir, compute SHA256 + size, collect into list. Parse new `depends_on` field. |
| `seed_skills` | `backend/src/flywheel/db/seed.py:334–498` | ~160 | After the upsert loop (line 469), add a second pass: for each skill, upload asset bytes to storage bucket and upsert `skill_assets` rows. Stay inside the existing function — same commit cadence. |
| `SKIP_DIRS` | `backend/src/flywheel/db/seed.py:33` | 1 | Narrow from `{"_archived", "_shared", "gtm-shared"}` to `{"_archived"}`. `_shared` and `gtm-shared` become normal-scanned library skills. |
| Skills endpoint | `backend/src/flywheel/api/skills.py:283–344` | ~60 | Add sibling `@router.get("/{skill_name}/bundle")` handler. Same auth/tenant-override/404 pattern as `get_skill_prompt`. |
| MCP server | `cli/flywheel_mcp/server.py:322–337` | ~20 | Add `@mcp.tool` for `flywheel_fetch_skill_bundle`. Add to `_GTM_TOOLS` set (line 81) so onboarding guard treats it as a skill-flow tool. |
| MCP api client | `cli/flywheel_mcp/api_client.py:145–151` | ~5 | Add `fetch_skill_bundle(skill_name) -> dict`. |
| CLI | `cli/flywheel_cli/main.py:125 (group), ~804 (new subcommand)` | ~40 | Add `flywheel skill` group with `fetch` subcommand. |
| Install docs | README / `flywheel setup-claude-code` copy | ~20 | Remove git-clone step. |

---

## Data Flow (single skill invocation, end-to-end)

Scenario: user types `/broker:process-project` in Claude Code. No local skill files exist; CC discovers and executes everything via Flywheel.

```
1. USER INPUT
   User → Claude Code: "/broker:process-project PROJECT_ID=..."

2. SKILL DISCOVERY
   CC → MCP: flywheel_fetch_skills()
   MCP → backend: GET /api/v1/skills/              (api_client.py:146)
   backend → DB: SELECT ... FROM skill_definitions JOIN tenant_skills
   backend → MCP: JSON {items: [{name:"broker", triggers:[...], ...}]}
   MCP → CC: text with skill list + trigger match

3. PROMPT FETCH
   CC → MCP: flywheel_fetch_skill_prompt(skill_name="broker")
   MCP → backend: GET /api/v1/skills/broker/prompt (api/skills.py:283)
   backend → CC: {system_prompt: "<SKILL.md body>"}

   [CC reads prompt, sees: "dispatch /broker:process-project →
    pipelines/process-project.md. Uses api_client.py, steps/*.md"]

4. BUNDLE FETCH (NEW in v22.0)
   CC → MCP: flywheel_fetch_skill_bundle(skill_name="broker")
   MCP → backend: GET /api/v1/skills/broker/bundle  (NEW endpoint)
   backend → DB: SELECT * FROM skill_assets
                 WHERE skill_id=<broker.id>
                 AND bundle_version = skill_definitions.version
   backend → Supabase: POST /storage/v1/object/sign/skill-assets/...  (batch)
                       for each asset
   backend → MCP: {
     bundle_version: "1.2",
     depends_on: ["_shared"],
     assets: [
       {path:"api_client.py", url:"https://...", sha256:"..."},
       {path:"portals/mapfre.py", ...},
       {path:"steps/parse-contract.md", ...}, ...
     ]
   }
   MCP → CC: same JSON as string

5. RECURSIVE DEPENDENCY FETCH
   (exec_helper detects depends_on: ["_shared"], recurses)
   CC → MCP: flywheel_fetch_skill_bundle(skill_name="_shared")
   MCP → backend → ... → MCP → CC: _shared manifest (context_utils.py etc)

6. EPHEMERAL MATERIALIZATION
   exec_helper creates tempfile.TemporaryDirectory()
     e.g. /var/folders/.../tmpAb9x/
   exec_helper downloads each asset concurrently (httpx), verifies SHA256
   exec_helper writes files:
     /var/.../tmpAb9x/broker/api_client.py
     /var/.../tmpAb9x/broker/portals/mapfre.py
     /var/.../tmpAb9x/_shared/context_utils.py
     ...
   exec_helper yields the tmp path to CC

7. PYTHON EXECUTION
   CC spawns subprocess:
     PYTHONPATH=/var/.../tmpAb9x python3 -m broker.pipelines.process_project \
       --project-id <uuid>
   The broker pipeline runs; api_client.py calls backend endpoints
   with the bearer token from ~/.flywheel/credentials.json (unchanged auth);
   portal scripts launch Playwright; steps read/write context store.

8. CLEANUP
   exec_helper context exits → TemporaryDirectory.__exit__ → rm -rf tmpAb9x
   No residue. Next invocation fetches fresh bytes.

9. RESULT
   CC reports to user via normal skill output channels.
```

**Per-invocation cost:** 3–4 MCP tool calls (1 list + 1 prompt + 1–2 bundles), 8–15 HTTPS fetches for asset bytes (one per file), one tmp dir creation + deletion. Bundle fetch is the only new latency. Rough budget: ~300 ms for backend manifest query + signed URL minting, ~800 ms for parallel asset downloads = ~1.1 s added to existing flow.

**Failure modes handled:**
- Asset SHA mismatch → abort, user sees "bundle tampering detected"
- Signed URL expired → exec_helper refetches manifest with one retry
- Supabase 5xx → fall back to `local://` path (already in `document_storage.py:92`)
- Network down → clear error from `api_client.py:72` ("Cannot reach Flywheel API")

---

## Patterns to Follow

### Pattern 1: Per-statement DDL commits (PgBouncer workaround)

**What:** Each DDL statement in a migration gets its own `session.execute(text(...))` + `session.commit()`, then `alembic stamp` to sync state.
**When:** Every new table or column in `skill_assets` migration.
**Template:** `backend/alembic/versions/063_skill_protected_default.py` (header comment + body).

### Pattern 2: Tenant-override check before serving skill data

**What:** Before returning a skill's data, check whether the tenant has any `tenant_skills` overrides; if so, filter by them; otherwise, return all enabled skills.
**Where:** `api/skills.py:125–175` (`_get_available_skills_db`), replicated at 296–322 (`get_skill_prompt`).
**New bundle endpoint MUST use the same check** — copy-paste the block or extract to a helper.

### Pattern 3: Signed-URL delivery for Supabase Storage bytes

**What:** Backend mints short-TTL signed URLs; client (CC or frontend) downloads bytes directly from Supabase. Backend never streams bytes through its own process.
**Where:** `services/document_storage.py:35–57` (`get_document_url`).
**Apply to:** skill asset manifest response — each asset's `url` field is a signed URL with `expires_in: 300` (5 min is enough; a cold user might take longer to read a prompt but exec_helper downloads in seconds).

### Pattern 4: MCP tool returns string (JSON-encoded)

**What:** MCP tools return strings. Structured data becomes a JSON string the calling agent parses.
**Where:** All 30+ tools in `server.py` follow this. `flywheel_fetch_skill_prompt` returns the prompt text directly; `flywheel_fetch_meetings` returns a formatted text listing; some return `json.dumps(...)`.
**For bundle tool:** return `json.dumps(manifest_dict)` so the exec_helper can `json.loads(...)` it. Document the shape in the tool docstring.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Streaming bytes through MCP tool result

**Why bad:** MCP tool results consume Claude context tokens. A 35 KB Python file base64-encoded is ~47 KB of tokens. Across 10 assets per bundle, that's ~100K tokens on every skill invocation before the skill has done anything. Signed URLs sidestep this entirely.

### Anti-Pattern 2: Persistent local cache under `~/.flywheel/skills/`

**Why bad:** Breaks the milestone promise ("nothing persists on user disk"). Creates version-skew debugging headaches (stale cache from a week ago bites you). Ephemeral tmp dir is simpler, reliable, and testable.
**Exception:** if v22.0 stretch-goal work reveals a real latency problem, consider a content-addressed cache keyed by `sha256` (not by filename). Deferred, not built.

### Anti-Pattern 3: Inlining `_shared` into every consumer skill

**Why bad:** `context_utils.py` is 958 lines. 8 consumers × 958 = 7,664 lines of duplication. Version skew (which skill has the fixed bug?). Storage bloat. Diff noise. Use the `depends_on` library-skill pattern.

### Anti-Pattern 4: Letting `seed.py` walk arbitrary file trees

**Why bad:** You end up shipping `__pycache__/`, `.pytest_cache/`, editor swap files, dev-only test fixtures. Explicit `assets:` list in SKILL.md gives the author control and reviewers a clear audit surface.

### Anti-Pattern 5: Executing bundled code inside the backend

**Why bad:** The whole architecture is "CC is the brain, backend is the data layer." Running user-uploaded (or even admin-uploaded) Python on the backend inverts trust and re-opens the `protected=true` mistake that was just reverted in `063_skill_protected_default`. Backend delivers, CC executes.

---

## Scalability Considerations

v22.0 is single-tenant-dogfooding-scale (3 users, ~20 skills, ~2.8K LoC total). Still worth mapping the growth path:

| Concern | At v22.0 (today) | At 100 tenants | At 10K tenants |
|---------|------------------|----------------|----------------|
| `skill_assets` row count | ~80 rows (20 skills × ~4 assets avg) | ~80 rows (skill_assets is tenant-neutral) | ~80 rows (unchanged — skills are global) |
| Storage bucket size | ~300 KB total | ~300 KB | ~300 KB |
| Bundle-fetch RPS | ~1 per skill invocation, ~10/day | ~1K/day | ~100K/day |
| Hot path | Signed URL minting (Supabase call) | Cache signed URLs per (skill, version) for 4 min in backend memory | Move to a CDN + permanent public URLs with integrity hashes; invalidate on version bump |
| Asset version churn | Low — bump on every prompt/script edit | Same | Introduce `cdn_url` column once Storage → CDN migration happens |

No scalability blockers. The shape inherits whatever scaling Supabase Storage + Postgres already give the broker documents flow.

---

## Build Order (with dependencies stated)

Each phase name is a GSD-roadmap-ready label. Dependencies are hard: phase N+1 must not start until phase N is green.

**Phase 1 — Schema (backend-only, no consumer impact)**
- Add `skill_assets` table (`alembic/versions/064_skill_assets.py` with PgBouncer per-statement workaround).
- Add `SkillAsset` ORM class in `db/models.py`.
- Wire into SQLAlchemy metadata.
- Deliverable: `alembic stamp` succeeds, integration test `tests/test_skill_assets_model.py` passes.
- **Blocks:** everything below.

**Phase 2 — Storage service wrapper**
- Add `SKILL_ASSETS_BUCKET = "skill-assets"` constant to `services/document_storage.py`.
- Add `upload_skill_asset(skill_id, bundle_version, path, content)` + `get_skill_asset_url(storage_path)` thin wrappers.
- Smoke test: upload a fake asset, mint URL, download via the URL, assert bytes match.
- **Depends on:** Phase 1.
- **Blocks:** Phase 3.

**Phase 3 — Seed pipeline extension**
- Extend `SkillData` with `assets`, `depends_on`.
- Extend `scan_skills` to parse new frontmatter fields and resolve globs.
- Extend `seed_skills` to upload bytes + upsert `skill_assets` rows.
- Narrow `SKIP_DIRS` from `{"_archived", "_shared", "gtm-shared"}` to `{"_archived"}` (shared dirs become library skills once their SKILL.md has `enabled: false` + `tags: ['library']`).
- Deliverable: `flywheel db seed` on the current `flywheel-v2/skills/` dir succeeds idempotently.
- **Depends on:** Phase 1, 2.
- **Blocks:** Phase 5 (no bundles to serve until seeded).

**Phase 4 — Migrate `~/.claude/skills/` content into `flywheel-v2/skills/`**
- Move `broker/`, `_shared/`, `gtm-shared/` into the repo.
- Add `assets:` + `depends_on:` stanzas to each SKILL.md frontmatter.
- Add library-skill SKILL.md stubs for `_shared` and `gtm-shared` (with `enabled: false`, `tags: ['library']`).
- No deletion from `~/.claude/skills/` yet — soft freeze only. Git tag legacy-skills-final.
- **Depends on:** Phase 3 (seed must accept the new frontmatter).
- **Parallelizable with:** Phase 5 (different surface areas).

**Phase 5 — Bundle API endpoint**
- Add `GET /api/v1/skills/{name}/bundle` in `api/skills.py`.
- Reuses tenant-override check + rate limit + protected-skill handling.
- Returns manifest with signed URLs.
- E2E test: call endpoint for seeded broker skill, verify URLs resolve.
- **Depends on:** Phase 3.
- **Blocks:** Phase 6.

**Phase 6 — MCP tool + api_client method**
- Add `fetch_skill_bundle` to `cli/flywheel_mcp/api_client.py`.
- Add `flywheel_fetch_skill_bundle` MCP tool in `server.py`.
- Unit test with mocked backend.
- **Depends on:** Phase 5.
- **Blocks:** Phase 7.

**Phase 7 — Exec helper**
- New `cli/flywheel_mcp/exec_helper.py`.
- `TemporaryDirectory` lifecycle, concurrent httpx fetches, SHA256 verify, `depends_on` resolution, sys.path injection.
- Integration test: fetch → write → import → cleanup, all in one test.
- **Depends on:** Phase 6.
- **Blocks:** Phase 8.

**Phase 8 — End-to-end smoke: one real broker skill runs via v22.0 path**
- Pick `/broker:parse-contract` (simplest step) as the canary.
- Disable its local copy (temporarily move `~/.claude/skills/broker/` aside).
- Invoke via CC, confirm fetch → temp → exec → cleanup loop works end-to-end.
- **Depends on:** Phase 7.

**Phase 9 — Migrate remaining consumer skills**
- Update broker pipeline skills, GTM skills to use the bundle path.
- Each skill's prompt gets an updated "dependency check" section that calls the bundle tool.
- **Depends on:** Phase 8.

**Phase 10 — CLI subcommand + install-flow update**
- Add `flywheel skill fetch` click command.
- Update `setup-claude-code` to drop any legacy clone step.
- Update README.
- **Depends on:** Phase 8 (smoke must pass before we change install docs).

**Phase 11 — Retirement**
- Archive `~/.claude/skills/` legacy repo.
- Remove the tolerance/back-compat scan code added in Phase 4.
- **Depends on:** Phase 9.

Critical ordering rationale: schema → storage → seed → serve → consume → smoke → migrate → retire. At every step prior to Phase 11, rollback is "revert the phase, old `~/.claude/skills/` still works." Only Phase 11 is one-way.

---

## Sources

- `backend/src/flywheel/db/models.py:811–884` — SkillDefinition + TenantSkill ORM (verified HEAD)
- `backend/src/flywheel/db/seed.py:1–499` — existing scan + upsert loop (verified HEAD)
- `backend/src/flywheel/api/skills.py:1–819` — prompt/bundle-adjacent endpoints (verified HEAD)
- `backend/src/flywheel/services/document_storage.py:1–120` — Supabase Storage wrapper pattern (verified HEAD)
- `backend/alembic/versions/063_skill_protected_default.py` — PgBouncer per-statement DDL template (verified HEAD)
- `cli/flywheel_mcp/server.py:82–337` — MCP tool signatures + prompt fetch shape (verified HEAD)
- `cli/flywheel_mcp/api_client.py:1–151` — REST client pattern (verified HEAD)
- `cli/flywheel_cli/main.py:125+` — click CLI structure (verified HEAD)
- `~/.claude/skills/broker/{SKILL.md, api_client.py, portals/base.py, pipelines/process-project.md}` — legacy skill layout to migrate (verified HEAD)
- `~/.claude/skills/_shared/context_utils.py` (958 lines) — largest shared-module asset (line-count verified)
- `.planning/PROJECT.md` v22.0 section — milestone goal and target features (verified HEAD)
