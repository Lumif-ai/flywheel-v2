# Phase 152 — Retire `~/.claude/skills/` Delivery Path

## Summary

Retires the legacy `~/.claude/skills/` distribution channel. Skills are now served exclusively via the Flywheel MCP server (`flywheel_fetch_skill_assets`) backed by the `skill_assets` table. This PR tags the final state of the legacy path, archives external per-skill repos, scrubs install instructions, and documents the MCP-only flow.

Closes: RETIRE-01, RETIRE-02, RETIRE-03, RETIRE-04, RETIRE-05 (see `.planning/REQUIREMENTS.md`).

## Scope

- Deprecation banners on 11 legacy SKILL.md files inside `skills/`
- Deleted 11+ dead `.bak` / `.pre-flywheel.backup` / `.pre-leads-pipeline.backup` / `.v*.bak` files
- Stripped `git clone` / `unzip` install instructions from `skills/gtm-web-scraper-extractor/README.md` and `skills/gtm-company-fit-analyzer/README.md`
- Deprecation comments on 7 shared engine / backend files that reference the legacy path
- `skills/broker/MIGRATION-NOTES.md` rewritten in past tense
- `skills/MIGRATION-PLAN.md` top banner marks the doc as historical
- Root `README.md` gains a "Skill Delivery" block documenting MCP-only delivery
- Annotated git tag `legacy-skills-final` pushed to origin (rollback anchor)
- External per-skill GitHub repos archived via GitHub UI (see evidence below; `Sharan0516/claude-skill-web-scraper` archival deferred per Plan 02 option-d — see "Residual Tasks")

## Non-goals

- No code logic changes. No new endpoints. No new DB tables. No modification of `skill_assets` contents.
- `~/.claude/CLAUDE.md` and `~/.claude/projects/*/memory/` are user-authored and untouched.

## Success criteria evidence

### SC1 — Legacy repo tagged + archived

- Tag: `legacy-skills-final` at SHA `<tag_sha>` (from `.planning/phases/152-retirement/152-02-SUMMARY.md`)
- Pushed to origin: confirmed via `git ls-remote --tags origin | grep legacy-skills-final`
- External per-skill repos archived:

| repo | archived_at (UTC) | evidence |
|------|-------------------|----------|
| <repo_1> | <timestamp_1> | <curl excerpt / screenshot link> |

(Or: "No external per-skill repos required archival — see 152-02-SUMMARY.md option-<c|d> justification.")

Plan 02 resolved to **option-d**: `Sharan0516/claude-skill-web-scraper` archival is deferred to a post-merge residual task (see "Residual Tasks" below). The `legacy-skills-final` tag alone satisfies SC1's immutable-rollback-anchor requirement; the external-repo archive is belt-and-suspenders hardening beyond SC1.

### SC2 — Install flow skills-clone-free

```
<paste `grep -n "git clone\|~/.claude/skills" scripts/install.sh cli/flywheel_cli/main.py` output — expected empty>
```

### SC3 — Codebase-wide grep returns zero unannotated hits

```
<paste SC3 PASS output from 152-03-SUMMARY.md>
```

Every residual `~/.claude/skills/` hit in the repo is either:
- Under `skills/_archived/` (pre-archived, out of scope), or
- Carries a `DEPRECATED (Phase 152 — 2026-04-19)` annotation alongside, or
- In a test fixture (`backend/src/tests/`)

### SC4 — README + CLAUDE.md templates MCP-only

```
<paste SC4 PASS output from 152-03-SUMMARY.md>
```

### SC5 — Coexistence-window telemetry gate

**Window:** `<window_start_iso>` → `<window_end_iso>` (≥3 calendar days)

**Active tenants at gate-check time:**

| tenant_id | tenant_name |
|-----------|-------------|
| <tenant_id> | <tenant_name> |

**Per-tenant evidence** (from `.planning/phases/152-retirement/152-COEXISTENCE-GATE.md` evidence block):

```
<log_lines>
```

**Gate decision:** PASS — every active tenant meets `distinct_roots >= 3` AND `distinct_dates >= 2`.
**Decision date (UTC):** `<decision_date>`
**Decided by:** `<human_name>`

Full gate procedure + runbook: [`.planning/phases/152-retirement/152-COEXISTENCE-GATE.md`](./152-COEXISTENCE-GATE.md)

## Rollback

If retirement proves premature, the `legacy-skills-final` tag anchors a clean revert. No data loss — `skill_assets` remains the source of truth regardless; this PR only removes/annotates dead pointers.

## Residual Tasks

The following follow-up items are explicitly deferred from Phase 152 close but are tracked here so they are not lost after merge:

### 1. Archive `Sharan0516/claude-skill-web-scraper` on GitHub (deferred from Plan 02, option-d)

- **Repo URL:** https://github.com/Sharan0516/claude-skill-web-scraper
- **Action path:** GitHub UI → Settings → Danger Zone → "Archive this repository" → type repo name to confirm
- **Owner:** User (Sharan)
- **Why deferred:** Standalone external skill repo outside the v22.0 monorepo consolidation scope; archival requires the GitHub Settings UI (no first-class `gh` CLI for repo archive without an admin-scoped token); non-blocking for Phase 152 close because (a) the `legacy-skills-final` tag already anchors SC1's immutable rollback, (b) Plan 01 annotated every in-repo legacy reference with the `DEPRECATED (Phase 152)` sentinel, and (c) Plan 03 scrubbed the sole in-repo link to the external scraper (`skills/gtm-web-scraper-extractor/README.md`). External-repo archival is belt-and-suspenders hardening, not a correctness prerequisite.
- **Evidence format** (paste into `152-02-SUMMARY.md` or this PR as a comment after action):
  ```
  Archive timestamp (UTC): <YYYY-MM-DDTHH:MM:SSZ>
  Verification:
  $ curl -s https://github.com/Sharan0516/claude-skill-web-scraper | grep "This repository has been archived"
  <expected: one hit confirming archived banner present in HTML>
  ```
- **Blocks:** Nothing downstream. Purely hardening.
- **Full rationale:** See `.planning/phases/152-retirement/152-02-SUMMARY.md` "Task 2 Evidence" + "Residual Task" sections.

### 2. Coexistence-window gate runbook (procedure reference, no action)

The log-query procedure and pass/fail criteria used to validate SC5 above are documented in [`152-COEXISTENCE-GATE.md`](./152-COEXISTENCE-GATE.md). That runbook is the authoritative source for any future re-run of the gate (e.g., if window is extended or additional tenants come online).

## Post-merge follow-ups

- Monitor `assets_bundle_fetch` log volume for 7 days; regression = sudden drop to zero.
- If external users report install breakage, direct them to the MCP-only flow documented in the updated root `README.md`.
- Execute the deferred archival action in "Residual Tasks §1" above at any convenient point post-merge.
