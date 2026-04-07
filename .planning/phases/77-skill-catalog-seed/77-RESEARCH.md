# Phase 77: Skill Catalog Seed - Research

**Researched:** 2026-03-30
**Domain:** Seed pipeline (SKILL.md parsing, PostgreSQL upsert, JSONB parameters)
**Confidence:** HIGH

## Summary

The seed pipeline (`scripts/seed_skills.py` -> `backend/src/flywheel/db/seed.py`) already handles full SKILL.md parsing, upsert into `skill_definitions`, and tenant_skills population. The core infrastructure is solid. The gap is that most of the 20 target skills lack `triggers` and `tags` in their YAML frontmatter -- these need to be added. Additionally, 4 of the 20 target skills don't exist yet (outreach-drafter, brainstorm, pricing, demo), so their SKILL.md files must be created. The seed pipeline also currently marks ALL parsed skills as `enabled=True` with no exclusion mechanism for dev tools -- this needs to change.

The `parameters` JSONB column on `skill_definitions` is already mapped in the seed pipeline. The frontmatter `parameters:` dict flows directly into it. The success criteria say "triggers go into parameters JSONB" and "tags[0] as category" -- this means triggers extracted from SKILL.md should be stored in `parameters.triggers` and tags should be populated with the first tag being a category label.

**Primary recommendation:** Add `triggers` and `tags` to all 20 target SKILL.md frontmatter files, create the 4 missing SKILL.md files, modify seed.py to support an exclusion list (or `enabled: false` in frontmatter), and extract trigger phrases from descriptions where triggers aren't explicit.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | installed | Parse SKILL.md frontmatter | Already imported in seed.py with fallback parser |
| SQLAlchemy | 2.x (asyncpg) | Upsert via `pg_insert().on_conflict_do_update()` | Already used in seed pipeline |
| asyncpg | installed | PostgreSQL async driver | Already configured |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | stdlib | CLI flags (--dry-run, --verbose) | Already in seed_skills.py |

No new dependencies needed. The entire pipeline is already built.

## Architecture Patterns

### Existing Seed Pipeline Flow
```
scripts/seed_skills.py (CLI entry)
  -> flywheel.db.seed.scan_skills(skills_dir)
     -> For each dir in skills/:
        -> Skip _archived, _shared, gtm-shared, dot-prefixed
        -> Parse SKILL.md frontmatter (YAML)
        -> Extract: name, version, description, web_tier, system_prompt,
                    contract_reads, contract_writes, engine_module,
                    tags, token_budget, parameters
        -> Return list[SkillData]
  -> flywheel.db.seed.seed_skills(session, skills_dir)
     -> Compare parsed vs existing DB rows
     -> pg_insert().on_conflict_do_update() on "uq_skill_defs_name"
     -> Populate tenant_skills for new skills
     -> Return SeedResult (added/updated/unchanged/orphaned/errors)
```

### SkillDefinition Model (relevant columns)
```
name           TEXT (unique, indexed)
version        TEXT
description    TEXT
web_tier       INTEGER (1/2/3)
system_prompt  TEXT (full SKILL.md body after frontmatter)
contract_reads TEXT[] (PostgreSQL array)
contract_writes TEXT[] (PostgreSQL array)
tags           TEXT[] (PostgreSQL array)
parameters     JSONB (dict, currently empty for most skills)
enabled        BOOLEAN (default true)
```

### SKILL.md Frontmatter Format (YAML)
```yaml
---
name: skill-name
version: "1.0"
description: >
  Multi-line description text.
context-aware: true
triggers:
  - "phrase one"
  - "phrase two"
  - manual
tags:
  - category-name
  - subcategory
contract_reads:
  - context-file-1
  - context-file-2
contract_writes:
  - context-file-1
web_tier: 1
---
```

### Key Design Decision: Where Triggers Live

Success criteria state: "triggers go into parameters JSONB column". Two options:

1. **Frontmatter `triggers:` -> `parameters.triggers`** (seed extracts and nests)
2. **Frontmatter `parameters: {triggers: [...]}` directly** (no transformation)

**Recommendation:** Use option 1. Keep `triggers:` as a top-level frontmatter field (consistent with existing skills like demo-prep, meeting-prep). Have the seed pipeline copy `triggers` into `parameters["triggers"]` during upsert. This keeps SKILL.md clean and readable.

### Skill Exclusion Strategy

Currently the seed marks ALL parsed skills as `enabled=True`. To exclude dev tools:

**Recommendation:** Add an `enabled: false` frontmatter field to dev-tool SKILL.md files. The seed already reads arbitrary frontmatter. Modify the upsert to read `data.get("enabled", True)` and pass it through. This is minimally invasive.

Alternative: Maintain a hardcoded exclusion list in seed.py. Less flexible but simpler.

### Anti-Patterns to Avoid
- **Don't parse trigger phrases from description text at seed time.** That's fragile regex. Instead, add explicit `triggers:` to each SKILL.md frontmatter.
- **Don't create a separate triggers table.** The JSONB column is the right place per the success criteria.
- **Don't duplicate contract_reads/writes into parameters.** They already have dedicated array columns.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom regex parser | PyYAML (already imported) | Edge cases with multiline, quoting, lists |
| Upsert logic | Raw SQL INSERT ON CONFLICT | pg_insert().on_conflict_do_update() | Already working in seed.py |
| Trigger extraction from prose | NLP/regex description parser | Manual addition of `triggers:` to frontmatter | Brittle, inconsistent, unmaintainable |

## Common Pitfalls

### Pitfall 1: Field Name Inconsistency
**What goes wrong:** Some skills use `reads:` / `writes:` (e.g., demo-prep) while others use `contract_reads:` / `contract_writes:` (e.g., flywheel). The seed only looks for `contract_reads` / `contract_writes`.
**How to avoid:** Either normalize all SKILL.md files to use `contract_reads`/`contract_writes`, or update the seed to check both field names (with `data.get("contract_reads", data.get("reads", []))`).

### Pitfall 2: Duplicate Frontmatter Markers
**What goes wrong:** meeting-prep has a spurious extra `---` after the closing frontmatter marker. The regex `r"^---\s*\n(.*?\n)---"` uses non-greedy match so it works, but subsequent `---` in the body could confuse things.
**How to avoid:** The current regex is fine (non-greedy `.*?`). Just be aware when editing SKILL.md files.

### Pitfall 3: 4 Missing Skills
**What goes wrong:** outreach-drafter, brainstorm, pricing, demo have no SKILL.md. The seed skips directories without SKILL.md, so these won't be seeded.
**How to avoid:** Create minimal SKILL.md files for these 4 skills. They need at minimum: name, version, description, triggers, tags, web_tier.

### Pitfall 4: Orphan Detection Noise
**What goes wrong:** The seed reports skills in DB but not on disk as "orphaned". If we're selectively seeding 20 skills and others were previously seeded, they show as orphans.
**How to avoid:** The current seed scans ALL non-skipped directories, not just target 20. Orphan detection compares all-parsed vs all-in-DB. This is fine -- orphans are informational, not errors.

### Pitfall 5: enabled Column Default
**What goes wrong:** The seed currently hardcodes `"enabled": True` for all upserted skills. Dev tools (dogfood, agent-browser, skill-creator, etc.) get enabled.
**How to avoid:** Read `enabled` from frontmatter with `data.get("enabled", True)` and pass through to upsert.

## Current State Audit: The 20 Target Skills

### Exist with SKILL.md (16 of 20)

| Skill | Has triggers: | Has tags: | Has contract_reads: | Has contract_writes: | Trigger Source |
|-------|:---:|:---:|:---:|:---:|---|
| flywheel | NO | NO | YES (4) | YES (2) | Description mentions "flywheel_run_skill" |
| meeting-prep | YES (manual) | NO | NO | NO | Frontmatter |
| meeting-processor | YES (manual, mcp-webhook) | NO | NO | NO | Frontmatter |
| call-intelligence | YES (manual) | NO | NO | NO | Frontmatter |
| account-research | YES (manual) | NO | NO | NO | Frontmatter |
| sales-collateral | NO | NO | NO | NO | Description has 6 quoted trigger phrases |
| gtm-pipeline | YES (manual, after outreach) | NO | NO | NO | Frontmatter |
| gtm-my-company | YES (manual) | NO | NO | NO | Frontmatter |
| gtm-company-fit-analyzer | NO | NO | NO | NO | Description has 5 quoted trigger phrases |
| gtm-web-scraper-extractor | NO | NO | NO | NO | Description has 3 quoted trigger phrases |
| gtm-outbound-messenger | NO | NO | NO | NO | Description has 10+ quoted trigger phrases |
| legal | NO | NO | NO | NO | Description has 20+ quoted trigger phrases |
| investor-update | YES (manual) | NO | NO | NO | Frontmatter |
| spec | NO | NO | NO | NO | Description has 10 quoted trigger phrases |
| social-media-manager | NO | NO | NO | NO | Description has 15+ quoted trigger phrases |
| demo-prep | YES (6 phrases) | NO | YES (reads: 3) | YES (writes: 1) | Frontmatter |

### Missing (4 of 20) -- Need SKILL.md Created

| Skill | Directory Exists? | Notes |
|-------|:-:|---|
| outreach-drafter | NO | No directory at all |
| brainstorm | NO | No directory at all |
| pricing | NO | No directory at all |
| demo | NO | No directory at all |

### Skills to EXCLUDE (not in target 20, should be disabled or not seeded)

**Dev tools:** dogfood, dogfood-deep, agent-browser, browse, skill-creator, ship, review, retro, gstack, plan-ceo-review, plan-eng-review, frontend-design, frontend-slides, content-critic, pii-redactor, slack

**Duplicates/superseded:** company-fit-analyzer (superseded by gtm-company-fit-analyzer), web-scraper-extractor (superseded by gtm-web-scraper-extractor), account-competitive, account-strategy (sub-skills of account pipeline), gtm-dashboard, gtm-leads-pipeline, email-drafter, email-scorer, legal-doc-advisor, quick-valuation, valuation-expert

## Required Changes Summary

### 1. SKILL.md Frontmatter Additions (16 existing skills)

Every target skill needs:
- `triggers:` -- YAML list of trigger phrases (extract from description where already embedded)
- `tags:` -- YAML list where first element is category. Proposed categories:
  - `operations` (flywheel)
  - `meetings` (meeting-prep, meeting-processor, call-intelligence)
  - `research` (account-research)
  - `sales` (sales-collateral, demo-prep)
  - `gtm` (gtm-pipeline, gtm-my-company, gtm-company-fit-analyzer, gtm-web-scraper-extractor, gtm-outbound-messenger)
  - `legal` (legal)
  - `investor-relations` (investor-update)
  - `strategy` (brainstorm, spec, pricing)
  - `marketing` (social-media-manager)
  - `demos` (demo)

### 2. New SKILL.md Files (4 missing skills)

Create minimal SKILL.md for: outreach-drafter, brainstorm, pricing, demo.
Each needs: name, version, description, triggers, tags, web_tier.

### 3. Seed Pipeline Changes (seed.py)

- Read `triggers` from frontmatter and inject into `parameters["triggers"]` before upsert
- Read `enabled` from frontmatter (default True) to support disabling dev tools
- Normalize `reads:`/`writes:` field names to `contract_reads`/`contract_writes`
- Optionally: add a `--target` flag or `FOUNDER_SKILLS` allowlist

### 4. Dev Tool SKILL.md Updates (27 non-target skills)

Add `enabled: false` to frontmatter of all non-target skills, OR add a SKIP list in seed.py.

## Code Examples

### Current Upsert (seed.py line 411-445)
```python
values = {
    "name": skill.name,
    "version": skill.version,
    "description": skill.description,
    "web_tier": skill.web_tier,
    "system_prompt": skill.system_prompt,
    "contract_reads": skill.contract_reads,
    "contract_writes": skill.contract_writes,
    "engine_module": skill.engine_module,
    "tags": skill.tags,
    "token_budget": skill.token_budget,
    "parameters": skill.parameters,
    "enabled": True,  # <-- hardcoded, needs to come from frontmatter
}
```

### Proposed Trigger Extraction in scan_skills()
```python
# After parsing frontmatter, before appending SkillData:
triggers = data.get("triggers", [])
if not isinstance(triggers, list):
    triggers = []

# Merge triggers into parameters dict
parameters = data.get("parameters", {})
if not isinstance(parameters, dict):
    parameters = {}
if triggers:
    parameters["triggers"] = triggers

# Read enabled from frontmatter
enabled = data.get("enabled", True)
if not isinstance(enabled, bool):
    enabled = True
```

### Proposed SKILL.md Frontmatter for Missing Skill (brainstorm)
```yaml
---
name: brainstorm
version: "1.0"
description: >
  Structured brainstorming and ideation sessions for founders. Takes a topic
  or challenge and generates structured ideas using multiple frameworks
  (first principles, analogies, inversion, constraints). Produces ranked
  ideas with feasibility assessment.
triggers:
  - "brainstorm"
  - "ideate"
  - "generate ideas"
  - "help me think through"
  - "brainstorming session"
tags:
  - strategy
  - ideation
web_tier: 1
---
```

## Open Questions

1. **What content goes in the 4 missing SKILL.md files?**
   - What we know: They need name, version, description, triggers, tags, web_tier at minimum
   - What's unclear: Should they have full system_prompt bodies or just frontmatter stubs?
   - Recommendation: Create frontmatter-only stubs with descriptive triggers. The system_prompt can be added later when these skills are actually built.

2. **Should non-target skills be set `enabled: false` or just not seeded?**
   - What we know: Current seed parses all directories and upserts everything
   - What's unclear: Whether existing DB rows for non-target skills should be disabled or left as-is
   - Recommendation: Use `enabled: false` in frontmatter -- this way the seed handles it idempotently and it's visible in the SKILL.md files themselves.

3. **How should the `contract_reads`/`contract_writes` vs `reads`/`writes` inconsistency be resolved?**
   - What we know: demo-prep uses `reads:`/`writes:`, flywheel uses `contract_reads:`/`contract_writes:`, seed.py only checks `contract_reads`/`contract_writes`
   - Recommendation: Update seed.py to check both with fallback: `data.get("contract_reads", data.get("reads", []))`

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/db/seed.py` -- full seed pipeline source, lines 1-475
- `backend/src/flywheel/db/models.py` -- SkillDefinition model, lines 801-841
- `backend/src/flywheel/api/skills.py` -- GET /skills endpoint, returns name/description/version/tags/web_tier
- `scripts/seed_skills.py` -- CLI entry point, lines 1-160
- All 20 target SKILL.md files -- frontmatter parsed with PyYAML

### Secondary (MEDIUM confidence)
- None needed -- this is all first-party code inspection

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- entirely existing code, no new libraries
- Architecture: HIGH -- seed pipeline fully inspected, clear modification points
- Pitfalls: HIGH -- identified from actual code inspection and frontmatter audit

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable internal codebase)
