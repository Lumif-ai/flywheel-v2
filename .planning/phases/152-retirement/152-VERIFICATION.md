---
phase: 152-retirement
verified: 2026-04-19T00:00:00Z
status: human_needed
score: 4/5 must-haves verified
re_verification: false
human_verification:
  - test: "Execute coexistence-window gate runbook"
    expected: "Every active tenant shows distinct_roots >= 3 AND distinct_dates >= 2 in the window; log excerpts pasted into 152-COEXISTENCE-GATE.md evidence block; Decision field filled in with PASS/date/decided-by; 152-RETIREMENT-PR.md all <...> placeholders replaced with concrete values; retirement PR opened and merged on GitHub"
    why_human: "Gate requires live production log grep on the backend host, production Supabase query for active tenant UUIDs, and GitHub PR UI to open and merge. These require authenticated access to infrastructure that only the repo owner (Sharan) can perform. Gate is explicitly designed as a human checkpoint per Plan 04 Task 3 classification."
---

# Phase 152: Retirement Verification Report

**Phase Goal:** The legacy `~/.claude/skills/` distribution channel is archived read-only, the install flow delivers skills exclusively via MCP, the codebase has zero hardcoded references to the old path, and the cutover is gated by telemetry confirming every active tenant has already exercised the server-hosted path during the coexistence window.

**Verified:** 2026-04-19
**Status:** human_needed
**Re-verification:** No — initial verification.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Legacy `~/.claude/skills/` git repo tagged `legacy-skills-final` + archived read-only; fresh install no longer clones it | VERIFIED | Tag `legacy-skills-final` (annotated, SHA `410a8fa6`) exists locally; pushed to both `origin` (Sharan0516/flywheel-v2) and `lumifai` (Lumif-ai/flywheel-v2); `git ls-remote --tags origin` confirms remote visibility. External-repo archival of `Sharan0516/claude-skill-web-scraper` deferred via option-d (Plan 02), documented as residual task in 152-RETIREMENT-PR.md — tag alone satisfies the rollback-anchor requirement. |
| 2 | `setup-claude-code` completes without ANY `git clone` of skills repo; only MCP registration remains | VERIFIED | `grep -n "git clone" scripts/install.sh` → CLEAN; `grep -n "~/.claude/skills" scripts/install.sh` → CLEAN; `grep -n "~/.claude/skills" cli/flywheel_cli/main.py` → CLEAN; `grep -n "~/.claude/skills" cli/flywheel_mcp/templates/CLAUDE.md` → CLEAN |
| 3 | Codebase-wide grep for `~/.claude/skills/` returns zero hits outside documented legacy-compat paths | VERIFIED | SC3 gate PASS: every file containing `~/.claude/skills/` is either in `skills/_archived/`, `backend/src/tests/`, or carries a `DEPRECATED (Phase 152 — 2026-04-19)` annotation. 18 canonical SKILL.md files all carry banners. 7 Python engine files carry per-call-site deprecation comments. MIGRATION docs carry banners. |
| 4 | README + CLAUDE.md templates contain no instructions to manually manage `~/.claude/skills/`; MCP-only delivery documented | VERIFIED | SC4 gate PASS: `rg "git clone\|git pull\|unzip" README.md cli/flywheel_mcp/templates/CLAUDE.md` returns zero instruction-intent hits after filtering the denial sentence. `README.md` contains a "Skill Delivery" section with `flywheel_fetch_skill_assets` documented as the exclusive delivery path. |
| 5 | Retirement PR only merges after telemetry confirms every active tenant fetched ≥1 bundle from `skill_assets` during coexistence window — gate explicit + auditable in PR description | HUMAN NEEDED | 152-COEXISTENCE-GATE.md runbook exists with complete log-query procedure and pass/fail criteria. 152-RETIREMENT-PR.md template exists with all SC evidence sections. All `<...>` placeholders (`<log_lines>`, `<tenant_id>`, `<decision_date>`, `<human_name>`, etc.) remain unfilled. Gate has not been executed against production logs. PR has not been opened or merged on GitHub. |

**Score:** 4/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| 18 SKILL.md files in `skills/` | Phase 152 deprecation banner | VERIFIED | All 18 (broker-extract-quote through gtm-company-fit-analyzer) contain `DEPRECATED (Phase 152` banner after YAML frontmatter |
| `skills/gtm-web-scraper-extractor/README.md` | MCP-delivery note, no `git clone` | VERIFIED | `git clone` absent; `flywheel_fetch_skill_assets` present |
| `skills/gtm-company-fit-analyzer/README.md` | MCP-delivery note, no `unzip` | VERIFIED | `unzip` absent; `flywheel_fetch_skill_assets` present |
| 7 Python engine + backend files | Deprecation comment at `~/.claude/skills/` references | VERIFIED | All 7 files carry `# DEPRECATED (Phase 152 — 2026-04-19): legacy ~/.claude/skills/ path...` |
| `skills/broker/MIGRATION-NOTES.md` | Past-tense retirement narrative + `Retired on` anchor | VERIFIED | No future-tense `After Phase 152`/`Phase 152 will` found; `Retired on 2026-04-19` present |
| `skills/MIGRATION-PLAN.md` | Historical document banner at top | VERIFIED | First line contains `Historical document (Phase 152 — 2026-04-19) — DEPRECATED (Phase 152 — 2026-04-19)` |
| `README.md` | Skill Delivery section with MCP-only note | VERIFIED | `flywheel_fetch_skill_assets` present; `Phase 152` mentioned; one `~/.claude/skills/` denial reference |
| `.planning/phases/152-retirement/152-COEXISTENCE-GATE.md` | Runbook with query procedure + evidence placeholders | VERIFIED | File exists (86 lines); `assets_bundle_fetch` pattern referenced 3 times; `distinct_roots >= 3` threshold present; `<log_lines>` placeholder present |
| `.planning/phases/152-retirement/152-RETIREMENT-PR.md` | PR template with SC1-SC5 sections + placeholders | VERIFIED | File exists; all 5 SC sections present; `<tenant_id>`, `<log_lines>`, `<tag_sha>`, `<decision_date>` placeholders present (correctly unfilled — awaiting human execution) |
| `legacy-skills-final` git tag | Annotated tag at retirement HEAD, pushed to origin | VERIFIED | Tag SHA `410a8fa6` on commit `2c4450d`; visible on `origin` remote |
| Zero `.bak`/`.backup`/`.v*.bak` files outside `skills/_archived/` | No dead backup files | VERIFIED | `find skills -path skills/_archived -prune -o -type f \( -name '*.bak' ... \)` returns empty |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| SKILL.md files | Phase 152 retirement rationale | Deprecation banner text `DEPRECATED (Phase 152` | WIRED | All 18 canonical SKILL.md files + gtm-web-scraper-extractor confirm pattern |
| Python engine files | Phase 152 retirement rationale | `# DEPRECATED (Phase 152` comment | WIRED | All 7 files carry the comment adjacent to `~/.claude/skills/` references |
| `README.md` | MCP-only delivery | "Skill Delivery" section with `flywheel_fetch_skill_assets` | WIRED | Block present; no legacy install instructions |
| `scripts/install.sh` / `cli/flywheel_cli/main.py` | MCP-only delivery | No `git clone` of skills repo | WIRED | Both confirmed CLEAN |
| `cli/flywheel_mcp/templates/CLAUDE.md` | No legacy path | Absence of `~/.claude/skills/` | WIRED | Confirmed CLEAN |
| `legacy-skills-final` tag | flywheel-v2 HEAD at retirement commit | `git tag -a` + push | WIRED | Tag object `410a8fa6` → commit `2c4450d`; visible on origin |
| `152-COEXISTENCE-GATE.md` evidence block | Production log evidence | Human fills `<log_lines>` at gate-check time | NOT YET WIRED | Placeholder unfilled — awaiting Task 3 human execution |
| `152-RETIREMENT-PR.md` placeholders | Concrete gate evidence | Human substitutes `<...>` values before PR merge | NOT YET WIRED | All placeholders remain template values — awaiting human execution |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| RETIRE-01: legacy-skills-final tag + archived | SATISFIED (partial) | Tag verified; external repo archival deferred option-d (non-blocking per plan design) |
| RETIRE-02: setup-claude-code skills-clone-free | SATISFIED | Install flow clean; no `git clone`; only MCP registration |
| RETIRE-03: zero unannotated legacy-path refs in codebase | SATISFIED | SC3 gate PASS — all refs carry Phase 152 annotations |
| RETIRE-04: README/CLAUDE.md templates MCP-only | SATISFIED | SC4 gate PASS — no manual-skill-management instructions |
| RETIRE-05: retirement PR gated by coexistence-window telemetry | PENDING | Human gate not yet executed; runbook and PR template ready |

### Anti-Patterns Found

No blocker anti-patterns detected. Reviewed:

- SKILL.md files: deprecation banners inserted without altering body content — no truncation, no placeholder bodies
- Python engine files: deprecation comments are code comments only; no business logic modified
- MIGRATION-NOTES.md / MIGRATION-PLAN.md: past-tense rewrites are accurate (no "will" or "After Phase 152" future tense found)
- `152-RETIREMENT-PR.md` placeholders: `<...>` values are INTENTIONALLY unfilled — they are correct as template values awaiting human completion. This is not a stub; it is the designed pre-merge state.
- `152-COEXISTENCE-GATE.md` placeholders: same — correctly unfilled per runbook design.

### Human Verification Required

#### 1. Execute Coexistence-Window Gate + Open and Merge Retirement PR

**Test:**
1. Confirm Phase 151 deploy date and verify today is >= window_start + 3 calendar days.
2. Query `SELECT id, name FROM tenants WHERE is_active = true;` against production Supabase; fill active-tenants table in `.planning/phases/152-retirement/152-COEXISTENCE-GATE.md`.
3. Run the log-grep procedure from the "Query procedure" section of `152-COEXISTENCE-GATE.md` on the backend host; pipe through the awk aggregator.
4. Verify each active tenant shows `distinct_roots >= 3` AND `distinct_dates >= 2`.
5. Paste qualifying log excerpts into the `<log_lines>` evidence block in `152-COEXISTENCE-GATE.md`; fill Decision, date, decided-by fields.
6. Commit filled-in runbook: `git add .planning/phases/152-retirement/152-COEXISTENCE-GATE.md && git commit -m "chore(152): record coexistence-window gate evidence"`.
7. Substitute all `<...>` placeholders in `152-RETIREMENT-PR.md` with concrete values (tag SHA from Plan 02: `410a8fa6…` / commit `2c4450d`; log excerpts; tenant list; decision date).
8. Commit finalized PR template, push branch, open PR on GitHub, paste PR body from `152-RETIREMENT-PR.md`, merge once approved.

**Expected:** Retirement PR merged on GitHub; URL captured. `152-COEXISTENCE-GATE.md` has no remaining `<...>` placeholders. `152-RETIREMENT-PR.md` has no remaining `<...>` placeholders on merge commit.

**Why human:** Requires live backend log access (grep on production host), production Supabase query for active tenant UUIDs, and GitHub PR UI authentication for the merge. No programmatic substitute. This is the explicit design of Plan 04 Task 3 (`checkpoint:human-verify`).

### Gaps Summary

No gaps blocking SC1–SC4. All code, documentation, and infrastructure artifacts for the automated portion of the phase are verified in the codebase.

SC5 is not a gap — it is a by-design human gate that the phase plan explicitly designates as `checkpoint:human-verify`. The runbook (`152-COEXISTENCE-GATE.md`) and PR template (`152-RETIREMENT-PR.md`) are ready and correct. The gate is pending human execution of the log-query procedure and the GitHub merge action.

Additional noted item (non-blocking): `Sharan0516/claude-skill-web-scraper` external repo archival was deferred via Plan 02 option-d. It is tracked as Residual Task §1 in `152-RETIREMENT-PR.md` and `152-02-SUMMARY.md`. This is a post-merge belt-and-suspenders action, not a phase-close prerequisite.

---

_Verified: 2026-04-19_
_Verifier: Claude (gsd-verifier)_
