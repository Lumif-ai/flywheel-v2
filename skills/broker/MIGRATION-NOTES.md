# Broker Migration Notes — v22.0

**Audience:** existing brokers running `/broker:*` commands; new broker onboarding.
**Applies to:** Phase 149 migration (broker Python from `~/.claude/skills/broker/` into server-hosted `skill_assets`).

## What Changed

Before Phase 149, broker Python helpers (`api_client.py`, `field_validator.py`,
portal drivers) lived in your local git clone at `~/.claude/skills/broker/`. After
Phase 149, the authoritative copy lives in `skill_assets` on the Flywheel
backend and is fetched over MCP at skill invocation time (Phase 150+).

**During the coexistence window** (Phase 149 — Phase 151), BOTH locations work:
- `~/.claude/skills/broker/` remains intact (git tree is NOT deleted)
- Server-hosted copy is the authoritative source going forward

**After Phase 152** (retirement), only the server copy remains. Your local
clone will be tagged `legacy-skills-final` and archived read-only.

## Playwright Profile — First Login After Migration Is Expected

Before Phase 149, `portals/base.py` used ephemeral `chromium.launch()` with no
persistence — every portal run started from a cold browser, and you logged in
manually each time.

After Phase 149, `portals/base.py` uses `chromium.launch_persistent_context(
user_data_dir=...)` with the state directory anchored at:

```
~/.flywheel/broker/portals/<carrier>/
```

For Mapfre specifically: `~/.flywheel/broker/portals/mapfre/`.

### What you need to do

**Nothing pre-migration.** There is no existing profile to copy — the old
`chromium.launch()` call left no persistent state on disk. A defensive
mkdir is already handled inside `mapfre.py` itself (`STATE_DIR.mkdir(
parents=True, exist_ok=True)`).

**First post-migration run:** `/broker:fill-portal` will open a fresh Chromium
with no saved cookies. You will be prompted to log in manually ONE TIME. The
profile (cookies, localStorage) will then persist at
`~/.flywheel/broker/portals/mapfre/` and survive across future runs until
cookie expiry.

This is a **feature** (added in Phase 149), not a regression — brokers were
previously logging in EVERY run because no profile was stored.

### If you want to seed a profile ahead of time

```bash
mkdir -p ~/.flywheel/broker/portals/mapfre
# Then run /broker:fill-portal once and complete login.
# Subsequent runs will reuse the profile until it expires.
```

### Single-instance caveat

Chromium will not launch two instances simultaneously against the same
`user_data_dir`. This means you cannot run `/broker:fill-portal` twice in
parallel for the same carrier. Sequential runs work fine. (Future Phase 151
may add file-locking for better error messaging; today you'd see a Playwright
"user data directory is already in use" error.)

## Errors You Might See

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| "No module named `api_client`" when running a broker skill | Bundle fetch did not complete (pre-Phase 150) or ephemeral unpack failed (post-Phase 150) | Re-run the skill; if persists, file an issue with the full error |
| "user data directory is already in use" | Parallel `/broker:fill-portal` against same carrier | Wait for the first to finish, or kill its Chromium |
| Mapfre portal asks you to log in again after weeks of not using it | Cookie expired on Mapfre's side | Re-login once; profile continues to persist for next expiry window |

## For Operators

Phase 149 ran `scripts/seed_skills.py` against prod Supabase, populating
`skill_assets` with the broker library bundle + _shared + gtm-shared. Re-run
the seed anytime via:

```bash
python3 scripts/seed_skills.py --dry-run --verbose  # preview
python3 scripts/seed_skills.py --verbose             # commit
```

Idempotent (content-addressed); re-seeding is safe.

## v1.1 → v1.2 (2026-04-18, Phase 150.1 — CC-as-Brain Enforcement)

**What changed:**
- `api_client.py` gained 10 new Pattern 3a methods: 5 `extract_*` + 5 `save_*`
  pairs for `contract-analysis`, `policy-extraction`, `quote-extraction`,
  `solicitation-draft`, and `recommendation-draft`. Existing `post` / `get` /
  `patch` / `upload_file` / `run` helpers preserved unchanged; `post` / `get` /
  `patch` gained an optional `extra_headers=` kwarg used by the Pattern 3a
  helpers to emit `X-Flywheel-Skill: <skill-name>` on every request.
- `skills/broker/SKILL.md` version bumped 1.0 → 1.2 (skipped 1.1 — this
  library was not separately versioned in Phase 149; the jump aligns with
  the consumer-skill 1.1 → 1.2 step).
- All 10 `skills/broker-*/SKILL.md` consumer files bumped 1.1 → 1.2.
- 6 of the 10 consumers had their "analyze" step rewritten to Pattern 3a:
  `broker-parse-contract`, `broker-parse-policies`, `broker-extract-quote`,
  `broker-draft-emails`, `broker-compare-quotes`, `broker-draft-recommendation`.
  Each rewrite includes a "Why this is different from v1.1" epilogue
  explaining the compute-boundary shift.

**Behavior change for the library consumer:**
- Previously, `broker_api.post("projects/{id}/analyze", {})` triggered a
  server-side Anthropic call against the backend's subsidy key (the
  backend-pays LLM-billing leak). Now the analysis runs in THIS conversation
  (Claude-in-conversation): `extract_contract_analysis(project_id)` →
  inline tool-use analysis against the returned prompt + schema →
  `save_contract_analysis(project_id, analysis)` persists.
- Backend still owns prompt assembly, tool_schema, PDF retrieval, and
  persistence — only the LLM call itself moves client-side.
- Net latency: slightly higher on the Claude-in-conversation leg (one extra
  round-trip vs. the old server-side polling pattern), but correctness and
  billing profile are unchanged; backend cost = zero LLM calls per run.

**BYOK wire format:** every Pattern 3a helper accepts an optional `api_key=`
kwarg and forwards it via the JSON request body (locked in Plan 01
`_enforcement.py`'s body-double-read dependency). Non-allowlisted skills
(all broker-*) without caller-supplied `api_key` will receive a 403
`subsidy_not_allowed` — this is intentional.

**Frontend migration branch chosen (Blocker-3 provenance):**
- **Branch P3 (warm + Claude Code handoff)** was taken on 2026-04-18.
  Pre-flight grep confirmed `POST /skills/runs` EXISTS
  (backend/src/flywheel/api/skills.py:741), which initially looked like
  Branch P1 territory. However, every broker-* skill has `web_tier=3` in its
  SKILL.md frontmatter, and the `start_run` handler rejects `web_tier=3`
  skills with HTTP 422 ("requires the local Claude Code agent. Run it
  locally with the corresponding /skill command in Claude Code"). A
  warm+enqueue flow would therefore succeed on the warm step but always fail
  on the enqueue step for broker-* — a silent-degradation trap explicitly
  forbidden by the Blocker-3 invariant.
- Frontend therefore migrated to a **warm + Claude Code handoff** pattern:
  each of the 4 call sites (`triggerAnalysis`, `draftSolicitations`,
  `extractQuote`, `draftRecommendation`) warms the corresponding
  `/broker/extract/{op}` endpoint with the `X-Flywheel-Skill` header (proving
  reachability + subsidy enforcement + BYOK wire format) and on mutation
  success opens a `ClaudeCommandModal`
  (`frontend/src/features/broker/components/shared/ClaudeCommandModal.tsx`)
  pre-filled with the correct `/broker:*` slash command and
  copy-to-clipboard affordance. The full Pattern 3a flow runs via the
  corresponding `/broker:*` skill in the user's local Claude Code.
- Handoff mapping per button:
  - `useAnalyzeProject` → `/broker:parse-contract <project_id>`
  - `useExtractQuote` → `/broker:extract-quote <project_id>`
  - `useDraftSolicitations` → `/broker:draft-emails <project_id>`
  - `useDraftRecommendation` → `/broker:draft-recommendation <project_id>`
- Every call site carries a `TODO(150.2)` comment indicating the follow-up
  work: ship a web_tier-safe broker enqueue path (e.g. a background job
  runner that invokes the same Pattern 3a helpers server-side) and swap
  these callers from warm + handoff to warm + enqueue.

**New bundle SHA-256:** `60cb34a0e32ef96b3d1aae8f9ac94c1ab5eda9ece33a8b37fe5fb655ee78ce46` (9283 bytes, re-seeded 2026-04-18)
Previous (Phase 149-02) SHA: `217ebdc1c28416e94104845a7ac0d2e49e71fe77caa60531934d05f2be17a33f` (7239 bytes)
Size delta: +2044 bytes (new Pattern 3a helpers in `api_client.py`).

**Byte-determinism invariant preserved:** the seed pipeline still uses Phase
147's `ZipInfo(date_time=(1980,1,1,0,0,0))` + sorted alphabetical entry walk
+ `external_attr=0o644 << 16`. Re-running `scripts/seed_skills.py --dry-run`
MUST produce the same SHA as the capture above.

**MCP tool clients** — no action required. `flywheel_fetch_skill_assets`
returns the authoritative current bundle by name; cached copies with old SHA
are replaced automatically on next fetch (cache is content-addressed by SHA).
