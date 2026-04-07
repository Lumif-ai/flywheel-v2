# Phase 81: Platform Setup - Research

**Researched:** 2026-03-30
**Domain:** CLAUDE.md template for Flywheel MCP integration rules
**Confidence:** HIGH

## Summary

Phase 81 creates a CLAUDE.md template file that teaches Claude Code how to use Flywheel -- context routing, skill-first lookup, and output saving. The template references 13 MCP tools already built in Phase 79 and will be manually copied into a founder's project for now (install script deferred).

The research confirms exact MCP tool names from `server.py`, validates CLAUDE.md best practices from official Anthropic docs, and determines the optimal template format. The key finding is that CLAUDE.md rules should be concise (under 300 lines total), use imperative language, and reference specific tool names -- Claude Code follows concrete instructions better than abstract guidance.

**Primary recommendation:** Create a focused ~50-line CLAUDE.md template at `cli/flywheel_mcp/templates/CLAUDE.md` with three rule sections that reference exact MCP tool names, use imperative tone, and include concrete examples of what qualifies as "business intelligence."

## Standard Stack

### Core

This phase produces a single Markdown template file. No libraries needed.

| Artifact | Type | Purpose | Location |
|----------|------|---------|----------|
| CLAUDE.md template | Markdown | Integration rules for Claude Code | `cli/flywheel_mcp/templates/CLAUDE.md` |

### No Dependencies

This phase has zero code dependencies. It produces a static Markdown file.

## Architecture Patterns

### MCP Tool Names (Exact, from server.py)

These are the 13 tools the CLAUDE.md template should reference. Verified from `cli/flywheel_mcp/server.py`:

**Context Store (read/write):**
- `flywheel_read_context` -- search business knowledge base
- `flywheel_write_context` -- store business knowledge (file_name param for categorization)

**Skill Discovery & Execution:**
- `flywheel_fetch_skills` -- list all available skills with triggers
- `flywheel_fetch_skill_prompt` -- load full execution prompt for a skill
- `flywheel_run_skill` -- run a skill via backend (for scheduled/cron path)

**Data Read:**
- `flywheel_fetch_meetings` -- unprocessed meetings with transcripts
- `flywheel_fetch_upcoming` -- today's upcoming meetings
- `flywheel_fetch_tasks` -- pending/confirmed tasks
- `flywheel_fetch_account` -- account details by ID or name

**Actions:**
- `flywheel_sync_meetings` -- trigger Granola calendar sync

**Write-back:**
- `flywheel_save_document` -- save skill output to library
- `flywheel_save_meeting_summary` -- save processed meeting summary
- `flywheel_update_task` -- update task status/priority

### Template Location

**Recommended:** `cli/flywheel_mcp/templates/CLAUDE.md`

Rationale:
- Lives in the MCP package (the thing being installed)
- When the install script is built later, it reads from this location
- For now, founders can manually copy it to their project root
- No `templates/` directory exists yet -- create it

### CLAUDE.md Structure (Three Sections from Spec)

From `SPEC-flywheel-platform-architecture.md` requirement SEED-01 and the concept brief:

1. **Context Store -- Business Intelligence Routing**
   - Business intel -> `flywheel_write_context`
   - Non-business data -> local files (fine)
   - Read before write -> `flywheel_read_context` to avoid duplicates

2. **Skill Discovery -- Flywheel First**
   - Check `flywheel_fetch_skills` first
   - Load prompt via `flywheel_fetch_skill_prompt`
   - Fall back to local skills, then general Claude Code

3. **Output -- Save to Library**
   - Deliverables -> `flywheel_save_document`
   - Meeting summaries -> `flywheel_save_meeting_summary`
   - Local copies also fine (both, not either/or)

### CLAUDE.md Writing Best Practices

From official Anthropic docs (code.claude.com/docs/en/best-practices) and community sources:

| Principle | Application |
|-----------|-------------|
| **Keep it short** | Target ~50 lines for the Flywheel section. Under 300 lines total including any existing content |
| **Imperative tone** | "Save deliverables via flywheel_save_document" not "You might want to consider saving..." |
| **Concrete examples** | List what counts as business intel: contacts, companies, competitive intel, pricing signals |
| **Only non-obvious rules** | Don't tell Claude how to code. Only Flywheel-specific routing rules |
| **Use emphasis sparingly** | "IMPORTANT" or "ALWAYS" for critical rules (context routing, skill-first lookup) |
| **Reference tool names exactly** | `flywheel_write_context` not "write to the context store" |
| **Compliance ~80%** | CLAUDE.md is advisory. Critical rules should also have clear tool descriptions (already done in server.py) |

**Key insight from Anthropic:** "For each line, ask: Would removing this cause Claude to make mistakes? If not, cut it." The CLAUDE.md should ONLY contain rules Claude wouldn't follow without being told.

### Pattern: Tool Descriptions + CLAUDE.md Reinforce Each Other

The MCP tool descriptions in `server.py` already contain routing hints:
- `flywheel_read_context`: "NOT for code documentation, README files, or project configs"
- `flywheel_write_context`: "NOT for coding preferences, tool configs, or project setup"
- `flywheel_run_skill`: "NOT for coding, file operations, or development tasks"
- `flywheel_fetch_skills`: "Call this to discover what Flywheel can do"

The CLAUDE.md template reinforces these at the conversation level. Tool descriptions tell Claude WHEN to use each tool; CLAUDE.md tells Claude the overall routing philosophy.

### Anti-Patterns to Avoid

- **Too verbose:** A 200-line CLAUDE.md with explanations of why each rule exists. Claude ignores the important parts.
- **Too abstract:** "Use Flywheel when appropriate." Claude doesn't know what "appropriate" means.
- **Duplicating tool descriptions:** Don't re-explain what each tool does. The MCP server already does this.
- **Rigid ordering:** Don't tell Claude a specific sequence of tool calls. Let it compose tools naturally based on the task.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detecting business intel in conversation | Complex regex or keyword matching | CLAUDE.md rules with examples | Claude's LLM reasoning already understands business vs non-business context |
| Skill routing logic | A routing function that maps intents to skills | `flywheel_fetch_skills` + Claude's matching | The tool already returns triggers; Claude matches naturally |
| Template interpolation | Dynamic template with variables | Static markdown file | No variables needed -- tool names are fixed, rules are universal |

## Common Pitfalls

### Pitfall 1: Over-Engineering the Template
**What goes wrong:** Adding conditional logic, placeholders, or per-user customization to the template.
**Why it happens:** Temptation to make it "configurable."
**How to avoid:** The template is static markdown. Every founder gets the same rules. Customization happens in the founder's own CLAUDE.md additions.

### Pitfall 2: Rules Too Long / Claude Ignores Them
**What goes wrong:** Claude stops following context routing rules because they're buried in a wall of text.
**Why it happens:** CLAUDE.md over 300 lines, or the Flywheel section is too verbose.
**How to avoid:** Target ~50 lines for the Flywheel section. Use bullet points, not paragraphs. Test by running a conversation and checking if Claude actually routes business intel to the context store.
**Warning signs:** Claude saves business intel to local files instead of calling `flywheel_write_context`.

### Pitfall 3: Not Listing Concrete Examples of Business Intel
**What goes wrong:** Claude doesn't recognize casual mentions of competitor pricing or contact details as "business intelligence."
**Why it happens:** The rule says "business intelligence" but doesn't give examples.
**How to avoid:** Explicitly list categories: contacts, companies, competitive intel, pain points, pricing signals, meeting outcomes, positioning insights, market signals.

### Pitfall 4: Forgetting the "Read Before Write" Rule
**What goes wrong:** Duplicate entries in context store because Claude writes without checking existing context.
**Why it happens:** The CLAUDE.md only says "write to context store" without the read-first instruction.
**How to avoid:** Include the read-before-write rule explicitly: "Before writing to context store, read existing context via `flywheel_read_context` to enrich rather than duplicate."

### Pitfall 5: Appendability
**What goes wrong:** Install script (future) overwrites the founder's existing CLAUDE.md.
**Why it happens:** Template designed as a complete file, not an appendable section.
**How to avoid:** Structure the template as a clearly bounded section with a header (`# Flywheel Integration`) that can be appended to an existing CLAUDE.md. For now this is manual; the future install script should check for existing content and append.

## Code Examples

### Recommended CLAUDE.md Template Content

Based on the spec (SEED-01), concept brief, and CLAUDE.md best practices:

```markdown
# Flywheel Integration

## Context Store -- Business Intelligence Routing

IMPORTANT: Business intelligence discovered during ANY conversation should be
saved to Flywheel via `flywheel_write_context`.

Business intelligence includes: contacts, company details, competitive intel,
pain points, positioning insights, pricing signals, market signals, meeting
outcomes, deal context, relationship notes.

- Before writing, call `flywheel_read_context` to check for existing entries
  and enrich rather than duplicate.
- Non-business data (code, personal notes, scratch work) stays in local files.

## Skill Discovery -- Flywheel First

When the user asks to perform a business task, ALWAYS check Flywheel first:

1. Call `flywheel_fetch_skills` to see available skills and match by triggers
2. If a skill matches, call `flywheel_fetch_skill_prompt` to load its instructions
3. Execute the skill following the loaded prompt
4. Only fall back to general Claude Code if no Flywheel skill matches

## Output -- Save to Library

- Deliverables (documents, briefings, reports, collateral) MUST be saved via
  `flywheel_save_document` so they appear in the Flywheel UI.
- Meeting summaries MUST be saved via `flywheel_save_meeting_summary`.
- Local copies are also fine -- save to both Flywheel and local, not either/or.
```

Source: Adapted from SPEC requirement SEED-01 and concept brief section "CLAUDE.md Rules (auto-written on install)."

### File Structure

```
cli/flywheel_mcp/
├── __init__.py
├── api_client.py
├── server.py
└── templates/
    └── CLAUDE.md          # <-- new template file
```

## State of the Art

| Aspect | Current State | Impact |
|--------|--------------|--------|
| CLAUDE.md compliance | ~80% advisory, not deterministic | Critical rules should be reinforced by tool descriptions (already done) |
| `@import` syntax | CLAUDE.md supports `@path/to/file` imports | Could reference the template from a parent CLAUDE.md, but manual copy is simpler for now |
| Hooks (deterministic) | Hooks run 100% of the time vs CLAUDE.md ~80% | For Phase 81, CLAUDE.md is sufficient. If compliance drops, consider adding a hook later |

## Open Questions

1. **Should the template use `@import` syntax?**
   - What we know: CLAUDE.md supports `@path/to/import` for referencing other files
   - What's unclear: Whether founders would prefer `@~/.flywheel/claude-rules.md` (stored once, referenced everywhere) vs a copy in each project
   - Recommendation: For now, use a standalone section that gets copied/appended. The import pattern can be added when the install script is built.

2. **Should `flywheel_run_skill` be mentioned in the CLAUDE.md?**
   - What we know: `flywheel_run_skill` runs skills via the backend (scheduled path). The interactive path uses `flywheel_fetch_skill_prompt` + Claude Code execution.
   - What's unclear: Whether founders will ever invoke `flywheel_run_skill` from Claude Code interactively
   - Recommendation: Do NOT mention `flywheel_run_skill` in the CLAUDE.md template. The skill discovery flow (fetch_skills -> fetch_skill_prompt -> execute) is the interactive path. `flywheel_run_skill` is for cron/scheduled execution.

## Sources

### Primary (HIGH confidence)
- `cli/flywheel_mcp/server.py` -- all 13 MCP tool names and descriptions verified directly from source
- `.planning/SPEC-flywheel-platform-architecture.md` -- SEED-01 acceptance criteria, three rules defined
- `.planning/CONCEPT-BRIEF-flywheel-platform-architecture.md` -- CLAUDE.md template content, skill lookup hierarchy

### Secondary (MEDIUM confidence)
- [Best Practices for Claude Code](https://code.claude.com/docs/en/best-practices) -- official Anthropic CLAUDE.md guidance: keep short, imperative, prune ruthlessly
- [How to Write a Good CLAUDE.md](https://www.builder.io/blog/claude-md-guide) -- community best practices on format and compliance
- [Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md) -- ~300 line limit, concrete examples over abstract rules

## Metadata

**Confidence breakdown:**
- Template content: HIGH -- spec and concept brief define exact rules
- MCP tool names: HIGH -- verified directly from server.py source code
- CLAUDE.md best practices: HIGH -- official Anthropic docs + community consensus
- Template location: MEDIUM -- reasonable convention, no prior art in this repo

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable -- CLAUDE.md format unlikely to change quickly)
