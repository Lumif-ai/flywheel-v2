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
