# Concept Brief: Flywheel Platform Architecture — Claude Code as Brain + Skill Catalog

> Generated: 2026-03-30
> Mode: Deep (brainstorm with advisory board)
> Rounds: 4 deliberation rounds
> Active Advisors: 10 core + Ben Thompson (platform dynamics), Frank Slootman (execution intensity), Kelsey Hightower (infra pragmatism), Taiichi Ohno (waste elimination)
> Artifacts Ingested: flywheel_ritual.py, 22 SKILL.md files, skill_definitions schema, MCP tool definitions, frontend routing

## Problem Statement

Flywheel currently runs all LLM work server-side through the user's Anthropic API key,
even when triggered from Claude Code. This leads to:

1. **Wasted API credits** on inferior models (Haiku/Sonnet) producing bad outputs (skills asking
   questions instead of delivering)
2. **No interactivity** — skills can't ask the user clarifying questions mid-execution
3. **Feature bloat** — 46 local skills shown to design partners, many half-baked or internal-only
4. **No discoverability** — skills are local Claude Code files, not part of the Flywheel platform
5. **No portability** — design partners can't install Flywheel and get skills automatically

The brainstorm sharpened the problem into two connected initiatives:

- **Architecture**: Backend = data layer, Claude Code = brain (when interactive)
- **Skill Catalog**: Curate, adapt, and serve skills via Flywheel's MCP server

## Proposed Approach

### Architecture: Two Execution Paths

```
Path 1: Interactive (Claude Code as Brain)
─────────────────────────────────────────
User (Claude Code) → speaks naturally
  → Claude Code reads MCP tool descriptions
  → Fetches data via Flywheel MCP primitives (DB queries only, no LLM)
  → Claude Code (Opus) does ALL reasoning
  → Saves results back via Flywheel MCP write tools
  → User sees results in Flywheel UI (localhost:5173)

Path 2: Scheduled (Backend as Brain)
─────────────────────────────────────
Cron/Scheduler → triggers flywheel_run_skill
  → Backend ritual runs all 5 stages with API key LLM calls
  → Results saved to library automatically
  → No human in loop
```

**Key principle**: Backend NEVER makes LLM calls when Claude Code is the caller.
All LLM reasoning happens through Claude Code's subscription, not the API key.

### MCP Tool Primitives (on existing flywheel MCP server)

New tools to add alongside existing `flywheel_read_context`, `flywheel_write_context`,
`flywheel_run_skill`:

```
Data Fetch (read-only, no LLM):
├── flywheel_sync_meetings          → trigger Granola sync, return count
├── flywheel_fetch_meetings         → unprocessed meetings with transcripts
├── flywheel_fetch_upcoming         → today's meetings with attendees
├── flywheel_fetch_tasks            → pending/confirmed tasks with context
├── flywheel_fetch_account          → account details + linked context
├── flywheel_fetch_skills           → skill catalog (names + descriptions)
└── flywheel_fetch_skill_prompt     → full skill system prompt for execution

Write-back (save results):
├── flywheel_save_meeting_summary   → write processed meeting summary
├── flywheel_save_document          → write skill output to library
├── flywheel_update_task            → update task status/skill assignment
└── flywheel_write_context          → (already exists) write to context store
```

Claude Code sees these tool descriptions and composes them based on the user's ask.
No routing logic needed — Claude Code IS the router.

### Skill Execution via Claude Code

When a user says "create a one-pager for COverage":

1. Claude Code calls `flywheel_fetch_skills` → gets skill catalog with descriptions
2. Matches intent to `sales-collateral` skill
3. Calls `flywheel_fetch_skill_prompt(skill="sales-collateral")` → gets system prompt
4. Calls `flywheel_read_context` → gets positioning, ICP, product modules
5. Calls `flywheel_fetch_account(name="COverage")` → gets account intelligence
6. Opus executes the skill with full context (asks user if clarification needed)
7. Calls `flywheel_save_document(skill="sales-collateral", content=...)` → saves to library
8. User sees result at localhost:5173/library

### Morning Brief via Claude Code

The flywheel skill prompt serves as the "recipe" for the morning brief sequence:

1. `flywheel_sync_meetings` → sync Granola
2. `flywheel_fetch_meetings` → get unprocessed transcripts
3. Opus processes each transcript, extracts insights
4. `flywheel_save_meeting_summary` for each → saves to DB
5. `flywheel_fetch_upcoming` → today's meetings
6. Opus preps each meeting (reads context, researches contacts)
7. `flywheel_save_document` for each prep → saves to library
8. `flywheel_fetch_tasks` → pending tasks
9. For each task: Opus infers skill, presents to user, gets confirmation, executes
10. `flywheel_save_document` + `flywheel_update_task` → saves results

All LLM work (steps 3, 6, 9) happens through Claude Code. Backend only does data I/O.

## Key Decisions Made

| Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|----------|-----------------|------------------|-------------------|---------------------|
| Execution model | Claude Code as brain for interactive | "I don't want anything going via API key when running from Claude Code" | Ohno (waste), Hightower (pragmatism) | Single backend execution for all paths |
| MCP design | Many small primitives, not one fat tool | Claude Code composes tools naturally; surgical fetching vs blob returns | Hickey (composability), Thompson (platform) | Single `flywheel_ritual(mode=interactive)` |
| Morning brief reliability | Primitives + skill prompt recipe | Emergent behavior works 90% of time, but daily ritual must be reliable | Vogels (failure thinking), Slootman (execution) | Pure emergent (no recipe) |
| Skill catalog source | Flywheel DB, not local skills/ directory | "I want design partners to install Flywheel and get skills automatically" | Thompson (platform), Hickey (data not code) | Local SKILL.md files |
| Feature flags | Route-level hiding in frontend | Design partners should see a focused product, not a sprawling one | Chesky (curate aha path), Rams (remove non-essential) | Component-level gating |
| Skill count | 20 founder-facing, rest archived/internal | Every skill must map to a real founder JTBD across a typical week | Bezos (working backward), Slootman (ruthless cut) | Ship all 46 |

## Feature Flags

### Implementation

Simple config-driven route gating. No feature flag service.

```typescript
// frontend/src/config/features.ts
export const FEATURES = {
  email: false,        // Email integration (not ready)
  tasks: false,        // Tasks/commitments UI (not ready)
  // everything else: shown by default
}
```

Routes gated by flag are hidden from nav entirely. Not disabled, not greyed out — invisible.

### Ship Now (no flag)
- Library (all skill outputs)
- Meetings (prep + insights)
- Documents (collateral, briefings)
- Accounts (research)

### Behind Flag
- Email integration (full thread view, drafting, scoring)
- Tasks / Commitments UI
- Focus areas (needs rethinking per CRM UX feedback)

## Skill Catalog: The 20 Founder-Facing Skills

### Dependency Tiers

Skills are organized into tiers based on dependencies. Lower tiers must be adapted
first since higher tiers depend on them.

```
Tier 0: Foundation (no skill dependencies, enables everything)
├── Context Store read/write via MCP
└── flywheel_fetch_skills / flywheel_fetch_skill_prompt

Tier 1: Independent Skills (no inter-skill dependencies)
├── Meeting Processor        → reads transcripts, writes 7 context files
├── Call Intelligence        → reads transcripts, writes decision logs
├── Account Research         → web research + context, writes account profiles
├── Sales Collateral         → reads context store, produces docs
├── Outreach Drafter         → reads context store, produces messages
├── Legal                    → reads uploaded docs, produces reviews/drafts
├── Investor Update          → reads context store + meeting archive
├── Brainstorm               → reads context store, produces concept briefs
├── Spec                     → reads concept briefs, produces specs
├── Pricing                  → reads context store, produces pricing models
├── Social Media Manager     → reads context store + git history
├── Demo Prep                → reads context store, produces demo artifacts
├── GTM My Company           → web research, writes sender profile to context
├── GTM Web Scraper Extractor → browser automation, produces CSVs
└── GTM Company Fit Analyzer  → web research + context, produces scores

Tier 2: Composite Skills (orchestrate Tier 1 skills)
├── Meeting Prep             → consumes: account-research (implicitly)
│                              reads context store, web research, produces briefings
├── GTM Outbound Messenger   → consumes: scored leads from fit-analyzer
│                              sends outreach via browser/email
├── GTM Pipeline             → orchestrates: scraper → fit-analyzer → outbound-messenger
│                              full pipeline with bidirectional context feedback
└── Demo                     → consumes: demo-prep output
                               builds interactive demo experiences

Tier 3: The Flywheel (orchestrates everything)
└── Flywheel (Morning Brief) → orchestrates: meeting-processor, meeting-prep,
                                task detection, skill execution
                                The daily operating rhythm
```

### Dependency Graph (what calls what)

```
flywheel (morning brief)
├── meeting-processor (process transcripts)
├── meeting-prep (prep upcoming meetings)
│   └── [implicitly uses account-research context]
├── task execution
│   └── [infers and runs any Tier 1 skill]
└── call-intelligence (on-demand deep dives)

account-strategy [future, not in initial 20]
├── account-research (company profile)
└── account-competitive (competitor landscape)

gtm-pipeline
├── gtm-web-scraper-extractor (scrape leads)
├── gtm-company-fit-analyzer (score leads)
└── gtm-outbound-messenger (send outreach)

demo
└── demo-prep (research + seed context)
```

### Per-Skill Adaptation Requirements

Each local skill needs these changes to work in Flywheel:

| Adaptation | What Changes | Why |
|-----------|-------------|-----|
| Context read | `~/.claude/context/X.md` → `flywheel_read_context(query)` | Founders don't have local context files |
| Context write | Local file write → `flywheel_write_context(file, entry)` | Writes go to Flywheel DB, not filesystem |
| Output save | Local file write → `flywheel_save_document(content)` | Results appear in Flywheel library |
| Web research | WebSearch/WebFetch → same (available via Claude Code) | No change needed for interactive path |
| Browser automation | Playwright MCP → TBD (may need Flywheel-hosted browser) | GTM skills need this; flag as Phase 2 |
| File paths | `~/.claude/skills/_shared/` → embedded in skill prompt or DB | No filesystem access for remote users |
| Shared utilities | `context_utils.py`, engine files → logic in skill prompt or MCP | Utility scripts won't exist on user's machine |

### Skill Adaptation Priority (recommended order)

**Wave 1: Core daily workflow (adapt first)**
1. Flywheel (morning brief) — the entry point, daily ritual
2. Meeting Processor — ingest transcripts, compound context
3. Meeting Prep — prep for upcoming meetings
4. Sales Collateral — create sales docs on demand
5. Account Research — research prospects

**Wave 2: GTM + outreach**
6. Outreach Drafter — draft personalized messages
7. GTM My Company — build sender profile
8. GTM Company Fit Analyzer — score prospects
9. GTM Web Scraper Extractor — extract lead lists
10. GTM Outbound Messenger — send outreach
11. GTM Pipeline — orchestrate the full flow

**Wave 3: Specialist skills**
12. Call Intelligence — deep call analysis
13. Legal — contract review/drafting
14. Investor Update — monthly updates
15. Brainstorm — idea pressure-testing
16. Spec — ideas to specs
17. Pricing — pricing strategy

**Wave 4: Content + demos**
18. Social Media Manager — LinkedIn/X content
19. Demo Prep — prospect demo preparation
20. Demo — interactive demo builder

### Skills NOT in Catalog (local dev tools or archived)

These stay in your local `skills/` directory for your own use but are NOT
seeded into Flywheel's skill_definitions table:

| Skill | Reason |
|-------|--------|
| gstack, browse, agent-browser | Browser plumbing infrastructure |
| gtm-shared | Shared library, not a skill |
| gtm-dashboard | Replaced by Flywheel UI |
| gtm-leads-pipeline | Subsumed by gtm-pipeline |
| company-fit-analyzer | Non-GTM duplicate |
| web-scraper-extractor | Deprecated |
| legal-doc-advisor | Duplicate of legal |
| content-critic | Internal quality gate, fold into social-media-manager |
| pii-redactor | Utility used by legal, not standalone |
| email-drafter, email-scorer | Behind email feature flag |
| account-competitive | Fold into account-research for now |
| account-strategy | Fold into account-research for now |
| frontend-design, frontend-slides | Dev tooling |
| plan-ceo-review, plan-eng-review | Dev tooling |
| review, ship, retro | Dev workflow |
| skill-creator | Dev tooling (you use this, founders don't) |
| dogfood, dogfood-deep | QA tooling |
| slack | Fragile browser automation |
| quick-valuation, valuation-expert | Niche, not core JTBD |

## MCP Discoverability

### How Claude Code Discovers Skills

When a founder installs Flywheel MCP, Claude Code sees tool descriptions like:

```
flywheel_fetch_skills:
  "List available Flywheel skills with descriptions and categories.
   Returns skill names, one-line descriptions, and usage triggers.
   Call this to discover what Flywheel can do for the user."

flywheel_fetch_skill_prompt:
  "Load the full execution prompt for a Flywheel skill.
   Returns the system prompt that Claude Code uses to execute the skill.
   Call this after identifying which skill to run."
```

Claude Code reads these descriptions, understands it can call `flywheel_fetch_skills`
to see what's available, then `flywheel_fetch_skill_prompt` to load the right one.

### Skill Metadata for Discovery

Each skill in the catalog needs rich metadata for Claude Code to match intents:

```json
{
  "name": "sales-collateral",
  "description": "Create professional B2B sales documents",
  "category": "sales",
  "triggers": ["one-pager", "case study", "value prop", "sales doc", "pitch deck"],
  "reads": ["positioning", "icp-profiles", "product-modules", "competitive-intel"],
  "writes": ["library-document"],
  "requires_browser": false,
  "requires_web_search": true
}
```

The `triggers` array helps Claude Code match natural language to skills without
needing exact skill names. "Create a one-pager for COverage" matches on "one-pager".

### Skill Categories for Grouping

```
meetings     → flywheel, meeting-processor, meeting-prep, call-intelligence
sales        → sales-collateral, outreach-drafter, account-research
gtm          → gtm-pipeline, gtm-my-company, gtm-company-fit-analyzer,
               gtm-web-scraper-extractor, gtm-outbound-messenger
legal        → legal
strategy     → brainstorm, spec, pricing, investor-update
content      → social-media-manager, demo-prep, demo
```

## Tensions Surfaced

### Tension 1: Composable Primitives vs Reliable Workflows
- **Hickey** argues: small MCP tools, let Claude Code compose — maximum flexibility
- **Vogels** argues: the morning brief should be a guaranteed sequence, not emergent
- **Why both are right**: Primitives enable ad-hoc requests; recipes enable daily rituals
- **Resolution**: Both. MCP primitives as the foundation. Skill prompts (like flywheel SKILL.md)
  as recipes that tell Claude Code the sequence. Claude Code follows the recipe when running
  a known workflow, composes primitives for ad-hoc requests.
- **User's reasoning**: "Morning brief is my daily rhythm — it should just work."

### Tension 2: Adapt All Skills vs Ship Minimal
- **Slootman** argues: ship 5 skills that work perfectly, not 20 that work okay
- **Chesky** argues: the full suite across a founder's week is the "aha" moment
- **Resolution**: Wave-based rollout. Wave 1 (5 core skills) ships first. Each wave
  adds more. The catalog grows, but only with adapted + tested skills.
- **User's reasoning**: Implicit in wave prioritization discussion.

### Tension 3: Browser-Dependent Skills
- **Hightower**: GTM skills need Playwright (browser automation). That's a dependency
  founders must install separately. It's friction.
- **Carmack**: Ship the non-browser skills first. Add browser skills when you solve
  the dependency (hosted browser, or clear install guide).
- **Resolution**: GTM skills that need Playwright are Wave 2. By then, either provide
  a hosted browser or a frictionless install path.
- **Status**: OPEN — needs design decision on hosted vs local browser.

### Unresolved Tensions
- **Transcript size**: 5 meeting transcripts could be large in Claude Code context.
  Should MCP return full transcripts or chunked? Board leans full (Opus has 1M context).
- **Write-back auth**: MCP tools need to write to DB. Auth mechanism TBD.
- **Library save format**: HTML? Markdown? Board leans HTML (matches current skill run output).

## Flywheel Install & CLAUDE.md Seeding

### Install Script (one command)

```
flywheel install
  → installs Flywheel MCP server
  → installs Playwright + browser binaries
  → configures auth (API key / session token)
  → seeds CLAUDE.md with Flywheel integration rules
  → done
```

### CLAUDE.md Rules (auto-written on install)

The installer writes project-level CLAUDE.md rules that shape Claude Code's behavior
for every conversation, not just when skills are explicitly invoked:

```markdown
# Flywheel Integration

## Context Store — Business Intelligence Routing
- Business intelligence discovered during ANY conversation (contacts, companies,
  meeting insights, competitive intel, pain points, positioning, pricing signals)
  should be written to Flywheel's context store via flywheel_write_context.
- Local files are fine for non-business data (code, personal notes, scratch work).
- Before writing to context store, read existing context via flywheel_read_context
  to avoid duplicates and to enrich rather than overwrite.

## Skill Discovery — Flywheel First
- When the user asks to perform a task, FIRST check Flywheel's skill catalog
  via flywheel_fetch_skills. Use the matching Flywheel skill if one exists.
- Only fall back to local skills or general Claude Code capabilities if no
  Flywheel skill matches the user's intent.

## Output — Save to Library
- Deliverables (documents, briefings, reports, collateral) should be saved
  to Flywheel's library via flywheel_save_document so they appear in the
  Flywheel UI. Local copies are also fine — both, not either/or.
```

### Why This Matters

These rules create three compounding behaviors:

1. **Passive intelligence capture**: A founder mentions a competitor's pricing in
   casual conversation → Claude Code writes it to context store. The flywheel
   compounds even when no skill is running.

2. **Flywheel-first skill routing**: Ensures the curated, adapted skills always
   take precedence over generic Claude Code behavior, while preserving full
   Claude Code flexibility as a fallback.

3. **Centralized outputs**: Every deliverable ends up in the Flywheel library,
   creating a searchable history of all work product. No artifacts lost in
   terminal sessions.

### Skill Lookup Hierarchy

```
User says something → Claude Code evaluates:
  1. Check Flywheel skill catalog (flywheel_fetch_skills)
     → Match found? Load skill prompt, execute via Flywheel
  2. Check local Claude Code skills (skills/ directory)
     → Match found? Execute locally
  3. No skill match → use general Claude Code capabilities
     → Still route business intel to context store per CLAUDE.md rules
```

## Moat Assessment

**Achievable power(s):**
1. **Switching costs** (Helmer Power #3): The context store compounds over time. After
   3 months of meetings, outreach, and insights, a founder can't leave without losing
   their compounded intelligence.
2. **Scale economies** (Helmer Power #4): Shared skill catalog — Flywheel invests once
   in adapting skills, every founder benefits.

**Future power (aspirational):**
3. **Network effects** (Helmer Power #5): If founders can share user-created skills,
   the platform gets more valuable with every user. Deferred to post-launch.

**Moat status**: Emerging — switching costs are real from day one via context store.

## Resolved Questions

- [x] **Auth for write-back**: Auth lives in MCP server config, set once at install time.
  Founder configures credentials when installing the Flywheel MCP server. Every tool call
  goes through that authenticated connection. Same pattern as flywheel_read_context today.
- [x] **Browser dependency for GTM**: Playwright bundled with Flywheel install. The install
  script handles MCP server + Playwright + browser binaries + auth config + CLAUDE.md seeding
  as one step. Founders never think about dependencies separately.
- [x] **Transcript sizing**: Full transcripts, no chunking. A 30-min meeting ≈ 10K tokens.
  5 meetings = 50K tokens = 5% of Opus 1M context. Even 20 meetings fit comfortably.
  Return full transcripts via MCP and let Opus process them.

## Resolved Questions (Batch 2)

- [x] **Skill versioning**: Latest version always wins. `seed_skills.py` already upserts
  with version tracking. No version pinning — design partners expect latest. Version
  pinning is a post-PMF concern for enterprise customers needing stability guarantees.
- [x] **Context store isolation (multi-tenancy)**: Already solved. `tenant_id` + RLS
  (row-level security) on every table. MCP auth scopes to tenant automatically.
  Founder A never sees Founder B's data. No additional work needed.
- [x] **Pricing model**: Free for design partners. Launch pricing = SaaS subscription
  for platform access (context store, library, skill catalog, MCP server). LLM compute
  costs are the user's via their Claude Code subscription — Flywheel's COGS is just
  database hosting. Exact tiers TBD post-validation, likely Free → Pro ($49-99/mo).
- [x] **Skill creation by founders**: Design is done. Skills declare `contract_reads`
  and `contract_writes` (columns already exist on `skill_definitions`). MCP server
  enforces at runtime. Automated validation on publish (Layer 1) + sandboxed execution
  (Layer 2). Implementation deferred to post-Wave 1.

## Open Questions

None — all questions resolved. Ready for execution.

## Recommendation

**Proceed to /gsd with wave-based execution:**

1. **Wave 0**: MCP primitives (the foundation — 7 new tools on existing server)
2. **Wave 1**: Feature flags + 5 core skills adapted for Flywheel
3. **Wave 2**: GTM skills (browser dependency solved)
4. **Wave 3**: Specialist skills (legal, investor, brainstorm, spec, pricing)
5. **Wave 4**: Content + demos

Wave 0 + 1 is the minimum viable platform. A founder installs Flywheel MCP on Claude Code,
gets 5 skills that work beautifully, and their context compounds from day one.

## Artifacts Referenced

- `backend/src/flywheel/engines/flywheel_ritual.py` — current ritual architecture
- `backend/src/flywheel/db/models.py` — SkillDefinition, Task models
- `backend/src/flywheel/config.py` — backend configuration
- `scripts/seed_skills.py` — skill seeding pipeline
- `frontend/src/features/tasks/components/BriefingTasksWidget.tsx` — tasks widget
- `frontend/vite.config.ts` — proxy configuration
- 22 SKILL.md files analyzed for dependency mapping
- Advisory board deliberation (4 rounds, 14 advisors)
