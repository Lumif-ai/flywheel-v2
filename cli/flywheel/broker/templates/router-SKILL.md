---
name: broker
version: "2.0"
description: Broker module skill router — fetches skill bodies via flywheel_fetch_skill_prompt MCP tool at runtime (Phase 152.1).
context-aware: true
triggers:
  - /broker:parse-contract
  - /broker:parse-policies
  - /broker:gap-analysis
  - /broker:analyze-gaps
  - /broker:select-carriers
  - /broker:fill-portal
  - /broker:draft-emails
  - /broker:extract-quote
  - /broker:draft-recommendation
  - /broker:process-project
  - /broker:compare-quotes
dependencies:
  python_packages:
    - "flywheel-ai>=0.4.0"
---

# Broker Skill Router (v2.0 — MCP-fetch)

> **Version:** 2.0 | **Phase:** 152.1
> **Changelog:** Phase 152.1 — router now dispatches via `flywheel_fetch_skill_prompt` MCP
> tool. Local `~/.claude/skills/broker/steps/*.md` and `pipelines/*.md` files have been
> removed. Shared Python helpers (`api_client`, `field_validator`, Playwright portals)
> ship via the `flywheel-ai` PyPI package's `flywheel.broker` namespace subpackage.

You are the broker skill router. When a `/broker:*` trigger fires, fetch the corresponding
SKILL.md body from Supabase via the `flywheel_fetch_skill_prompt` MCP tool, then execute
that body verbatim against the trigger's arguments. Do NOT look for local files under
`~/.claude/skills/broker/`; the mirror was removed in Phase 152.1.

---

## Prerequisites

- **`flywheel-ai>=0.4.0`** installed (`uv tool install flywheel-ai` or
  `pip install --upgrade flywheel-ai`). Provides the `flywheel.broker` namespace package
  (`api_client`, `field_validator`, Playwright portals) that every fetched broker body
  imports via `from flywheel.broker import ...`.
- **Authenticated Flywheel session.** The MCP fetch needs a valid token from
  `~/.flywheel/credentials.json`. Run `flywheel login` once; `api_client.py` auto-refreshes
  during runs.

---

## Dispatch Flow (what Claude does when a `/broker:*` trigger fires)

1. **Read the environment flag.** `FLYWHEEL_SKILL_SOURCE = os.environ.get("FLYWHEEL_SKILL_SOURCE", "mcp")`.
2. **Reject `local`.** If the value equals `"local"`, emit the mirror-removed error
   (below) and halt. No fallback path exists after Phase 152.1.
3. **Reject unknown values.** If the value is anything other than `"mcp"` or `"local"`
   (and is not unset), emit:
   ```
   FLYWHEEL_SKILL_SOURCE must be 'mcp' or 'local' (unset = 'mcp'). Got: <value>
   ```
   and halt.
4. **Resolve the slug.** Otherwise (`"mcp"` or unset — default) look up the MCP slug from
   the dispatch table below using the trigger name.
5. **Fetch via MCP.** Call `mcp__flywheel__flywheel_fetch_skill_prompt(skill_name=<slug>)`.
   The tool returns the SKILL.md body string from Supabase's `skill_definitions.system_prompt`.
6. **Detect error strings before treating the return value as a body.** If the returned
   string starts with any of these patterns, treat it as a fetch failure (NOT a body):
   - `"No prompt found for skill"`
   - `"Error fetching skill prompt:"`
   - `"API error"`
   - `"Authentication expired"`
7. **Retry once on failure.** On exception OR error-string match, retry the fetch exactly
   once against the same slug.
8. **Hard fail on second failure.** If the second attempt also fails, emit the hard-fail
   error contract (below) and halt. No local-file fallback.
9. **Execute the body.** On success, execute the returned SKILL.md body verbatim, passing
   through the arguments from the original `/broker:<trigger>` invocation. Claude treats
   the body as skill instructions (same as if it were a local SKILL.md file).

---

## Trigger Dispatch Table

11 triggers resolve to 10 distinct MCP slugs (`/broker:analyze-gaps` is an alias for
`/broker:gap-analysis` and shares the `broker-gap-analysis` slug).

| Trigger                        | MCP slug                       |
| ------------------------------ | ------------------------------ |
| `/broker:parse-contract`       | `broker-parse-contract`        |
| `/broker:parse-policies`       | `broker-parse-policies`        |
| `/broker:gap-analysis`         | `broker-gap-analysis`          |
| `/broker:analyze-gaps`         | `broker-gap-analysis` (alias)  |
| `/broker:select-carriers`      | `broker-select-carriers`       |
| `/broker:fill-portal`          | `broker-fill-portal`           |
| `/broker:draft-emails`         | `broker-draft-emails`          |
| `/broker:extract-quote`        | `broker-extract-quote`         |
| `/broker:draft-recommendation` | `broker-draft-recommendation`  |
| `/broker:process-project`      | `broker-process-project`       |
| `/broker:compare-quotes`       | `broker-compare-quotes`        |

---

## Error Contracts

These are locked strings — do not paraphrase. Downstream tooling and tests match on
substrings from these contracts.

### Hard-fail (retries exhausted in `mcp` mode)

```
ERROR: Failed to fetch SKILL.md from MCP for /broker:<trigger>
       Retries exhausted. Hard fail (FLYWHEEL_SKILL_SOURCE=mcp, strict mode).
       Check MCP connectivity; run `flywheel login` if the auth chain is broken.
```

### Mirror-removed (`local` mode — no fallback)

```
FLYWHEEL_SKILL_SOURCE=local is no longer supported. Mirror removed in Phase 152.1.
Set FLYWHEEL_SKILL_SOURCE=mcp or unset it.
```

---

## Environment Flag Reference

| Value             | Behavior                                                                |
| ----------------- | ----------------------------------------------------------------------- |
| unset (default)   | Fetch via MCP. Retry once on transient failure. Hard fail on exhaust.   |
| `mcp`             | Same as unset. Explicit opt-in to MCP fetch.                            |
| `local`           | Emit mirror-removed error + halt. No fallback (Phase 152.1 retirement). |
| anything else     | Emit "must be 'mcp' or 'local'" error + halt.                           |

---

## Operator Notes

- **Adding a new trigger:** add both a row to the dispatch table above and a corresponding
  row in Supabase's `skill_definitions` table (via `scripts/seed_skills.py`). Frontmatter
  `triggers:` list must also include the new `/broker:<name>` entry so Claude Code
  registers it.
- **Changing a slug's body:** edit `skills/broker-<slug>/SKILL.md` in the repo and run
  `scripts/seed_skills.py`. Live router picks up the new body on next MCP fetch
  (no router redeploy needed).
- **Aliases (like `/broker:analyze-gaps` → `broker-gap-analysis`):** declared in this
  router's dispatch table only. No sibling slug exists in `skill_definitions` — the alias
  resolves here and issues a single fetch against the shared slug.
