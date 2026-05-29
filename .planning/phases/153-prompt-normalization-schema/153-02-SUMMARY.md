---
phase: 153-prompt-normalization-schema
plan: "02"
subsystem: skill-platform
tags: [cc_executable, metadata, seed-pipeline, mcp, api]
dependency_graph:
  requires: []
  provides: [cc_executable-column, cc_executable-api, cc_executable-mcp]
  affects: [skill_definitions, seed-pipeline, skills-api, flywheel-fetch-skills]
tech_stack:
  added: []
  patterns: [pgbouncer-safe-ddl, orthogonal-flags]
key_files:
  created:
    - backend/alembic/versions/066_cc_executable_column.py
  modified:
    - backend/src/flywheel/db/models.py
    - backend/src/flywheel/db/seed.py
    - backend/src/flywheel/api/skills.py
    - cli/flywheel_mcp/server.py
    - skills/broker-compare-quotes/SKILL.md
    - skills/broker-draft-emails/SKILL.md
    - skills/broker-draft-recommendation/SKILL.md
    - skills/broker-extract-quote/SKILL.md
    - skills/broker-fill-portal/SKILL.md
    - skills/broker-gap-analysis/SKILL.md
    - skills/broker-parse-contract/SKILL.md
    - skills/broker-parse-policies/SKILL.md
    - skills/broker-process-project/SKILL.md
    - skills/broker-select-carriers/SKILL.md
    - skills/call-intelligence/SKILL.md
    - skills/gtm-company-fit-analyzer/SKILL.md
    - skills/gtm-outbound-messenger/SKILL.md
    - skills/gtm-pipeline/SKILL.md
    - skills/gtm-web-scraper-extractor/SKILL.md
    - skills/meeting-intelligence/SKILL.md
    - skills/meeting-prep/SKILL.md
    - skills/meeting-processor/SKILL.md
    - skills/one-pager/SKILL.md
    - skills/outreach-drafter/SKILL.md
decisions:
  - cc_executable placed after protected in ORM model to keep boolean flags grouped
  - Used op.execute() with ADD COLUMN IF NOT EXISTS for PgBouncer-safe migration (matches 065 pattern)
  - Added cc_executable after public: in SKILL.md frontmatter for consistent positioning
metrics:
  duration: 170s
  completed: 2026-04-21T15:08:07Z
---

# Phase 153 Plan 02: cc_executable Flag Summary

**BOOLEAN cc_executable column on skill_definitions with full pipeline: migration, ORM, seed (frontmatter parsing + UPSERT), API response, MCP display showing in-context vs server-side execution mode.**

## What Was Built

### Task 1: DB Migration + ORM + Seed Pipeline

- **Migration** (`066_cc_executable_column.py`): PgBouncer-safe single DDL statement adding `cc_executable BOOLEAN NOT NULL DEFAULT false` to `skill_definitions`. Uses `ADD COLUMN IF NOT EXISTS` pattern matching existing migrations.

- **ORM Model**: Added `cc_executable: Mapped[bool]` field to `SkillDefinition` class, positioned after `protected` to group boolean flags. Orthogonal to `protected` -- both flags exist independently (META-02).

- **Seed Pipeline** (4 touch points in seed.py):
  1. `SkillData` dataclass: `cc_executable: bool = False`
  2. `scan_skills()`: parses `cc_executable` from SKILL.md frontmatter
  3. Values dict: includes `cc_executable` in INSERT values
  4. UPSERT `set_`: includes `cc_executable` in ON CONFLICT UPDATE

- **20 SKILL.md files**: Added `cc_executable: true` to all active non-library skills. Zero library skills (_shared, gtm-shared, broker) were touched.

### Task 2: API + MCP Surface

- **Skills API** (`_get_available_skills_db`): Added `"cc_executable": sd.cc_executable` to response dict.

- **MCP Tool** (`flywheel_fetch_skills`): Extracts `cc_executable` from API response and displays execution mode as "(in-context)" or "(server-side)" in the skill listing header.

## Success Criteria Verification

| Criteria | Status |
|----------|--------|
| META-01: cc_executable BOOLEAN DEFAULT false column | PASS |
| META-02: Orthogonal to protected | PASS |
| META-03: flywheel_fetch_skills includes cc_executable | PASS |
| META-04: 20 active non-library skills flagged | PASS |
| Seed pipeline persists through all 4 touch points | PASS |

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| 3a9f7bc | feat(153-02): add cc_executable flag to skill definitions |

## Self-Check: PASSED
