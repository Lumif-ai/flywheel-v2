# Phase 134: Skills Infrastructure - Research

**Researched:** 2026-04-15
**Domain:** Claude Code skills architecture, Playwright portal automation, Claude Code hooks system
**Confidence:** HIGH

## Summary

Phase 134 builds the complete skill execution environment for the broker vertical at `~/.claude/skills/broker/`. The work spans three categories: (1) skill directory structure with a router SKILL.md and shared Python utilities (api_client.py, field_validator.py), (2) Playwright-based portal automation for Mapfre with a shared base module, and (3) five Claude Code hooks (post-coverage-write, post-quote-write, pipeline-check Stop hook, pre-portal-validate PreToolUse hook, and an auth helper).

The skills infrastructure is entirely local to the broker's Claude Code instance — nothing in `~/.claude/skills/broker/` runs on the server. The backend already has the portal submitter engine at `backend/src/flywheel/engines/portal_submitter.py` and portal scripts at `backend/scripts/portals/mapfre_mx.py`, which serve as reference implementations. The skills in `~/.claude/skills/broker/` are Claude Code skill files (SKILL.md + supporting Python) that Claude Code executes locally. Hooks live in `~/.claude/hooks/` and are registered in `~/.claude/settings.json`.

Key design insight: the pipeline-mode sentinel is a critical correctness mechanism. Without it, writing a coverage row would trigger post-coverage-write, which calls analyze-gaps, but during pipeline execution (where you write 5 coverages in sequence) you'd fire the hook 5 times. The sentinel pattern uses an environment variable or temp file to suppress hooks during pipeline execution, then fires once at the end.

**Primary recommendation:** Build api_client.py using httpx (already installed v0.28.1), use `async_playwright` for portal scripts matching the existing engine's pattern, and implement pipeline sentinels as environment variable checks (`BROKER_PIPELINE_MODE=1`) so hooks can be suppressed without inter-process coordination.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 | HTTP client for API calls from skills | Already installed; supports async; used in existing portal_submitter.py |
| playwright (python) | 1.58.0 | Browser automation for portal scripts | Already installed and verified working (Chromium launches ok) |
| PyYAML | 6.0.3 | Load carrier field maps (mapfre.yaml) | Already installed; standard for config files |
| asyncio | stdlib | Async runtime for Playwright scripts | Required by playwright.async_api |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json | stdlib | Parse hook stdin events, format output | All hooks |
| os | stdlib | Read env vars (FLYWHEEL_API_URL, FLYWHEEL_API_TOKEN) | All hooks and api_client |
| sys | stdlib | Exit codes for hook control | All hooks |
| pathlib | stdlib | Path handling for screenshots | Portal scripts |
| datetime | stdlib | Timestamps for screenshots/checkpoints | Portal scripts, hooks |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx (async) | requests (sync) | httpx already installed and used in portal_submitter.py; prefer consistency |
| asyncio playwright | sync playwright | async is required by portal_submitter.py pattern; sync would need separate event loop per call |
| env var sentinel | temp file sentinel | Env var cleaner for subprocess inheritance; temp file would need cleanup |
| YAML for field maps | JSON for field maps | YAML is more human-editable for field mappings that need carrier-specific comments |

**Installation:**
```bash
# Already installed — no new packages needed
pip3 install playwright  # v1.58.0 already present
playwright install chromium  # run once per machine to install browser
pip3 install httpx pyyaml  # v0.28.1 and v6.0.3 already present
```

## Architecture Patterns

### Recommended Project Structure
```
~/.claude/skills/broker/
├── SKILL.md                    # Router: maps /broker:* triggers to sub-skills
├── api_client.py               # Shared: Bearer auth HTTP helper (httpx)
├── field_validator.py          # Shared: input validation for all skills
├── portals/
│   ├── base.py                 # Shared: Playwright helpers (wait, fill, screenshot)
│   ├── mapfre.py               # Carrier: Mapfre portal script
│   └── mapfre.yaml             # Carrier: Mapfre field map
├── tests/
│   ├── test_smoke_api_client.py
│   └── test_smoke_field_validator.py
└── auto-memory/
    └── broker.md               # Skill memory (Standard 1)

~/.claude/hooks/                # Existing hooks dir
├── broker-post-coverage-write.py   # HOOK-01
├── broker-post-quote-write.py      # HOOK-02
├── broker-pipeline-check.py        # HOOK-03 (Stop hook)
├── broker-pre-portal-validate.py   # HOOK-04 (PreToolUse hook)
└── broker-auth-helper.py           # HOOK-05 (auth utility, not a hook itself)
```

### Pattern 1: Claude Code Hook Input/Output Contract

**What:** Hooks receive JSON on stdin, communicate via exit codes and stdout/stderr.
**When to use:** All broker hooks must follow this pattern exactly.

```python
# Source: https://code.claude.com/docs/en/hooks-guide
import json, sys, os

def main():
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        event = {}
    
    # Exit 0 = allow, Exit 2 = block with stderr message
    # For PostToolUse/Stop: return {"decision": "block"} via stdout to block
    # For PreToolUse: return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny"}}

if __name__ == "__main__":
    main()
```

**Exit code semantics:**
- `exit 0` = allow the action to proceed
- `exit 2` = block the action; stderr becomes Claude's feedback
- Any other non-zero = action proceeds, but shows `<hook name> hook error` in transcript

**For Stop hooks specifically:**
```python
# Stop hooks fire whenever Claude finishes responding
# Must check stop_hook_active to prevent infinite loops
INPUT = json.load(sys.stdin)
if INPUT.get("stop_hook_active"):
    sys.exit(0)  # Allow Claude to stop — already in a hook continuation
```

**For PreToolUse hooks to deny:**
```python
# Return JSON to stdout with permissionDecision
result = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "Playwright not installed. Run: pip3 install playwright && playwright install chromium"
    }
}
print(json.dumps(result))
sys.exit(0)  # Exit 0 when using JSON output (not exit 2)
```

### Pattern 2: api_client.py — Bearer Auth HTTP Helper

**What:** Shared async HTTP client that reads FLYWHEEL_API_URL and FLYWHEEL_API_TOKEN from env.
**When to use:** Any skill or hook making REST API calls to the backend.

```python
# Source: backend/src/flywheel/engines/portal_submitter.py (existing pattern)
import httpx, os

API_URL = os.environ.get("FLYWHEEL_API_URL", "http://localhost:8000")
API_TOKEN = os.environ.get("FLYWHEEL_API_TOKEN", "")

async def api_post(path: str, payload: dict) -> dict:
    """POST to backend with Bearer auth. Raises on HTTP error."""
    if not API_TOKEN:
        raise RuntimeError("FLYWHEEL_API_TOKEN not set")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_URL}/broker/{path.lstrip('/')}",
            json=payload,
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()
```

**Silent exit pattern for hooks (HOOK-05):**
```python
# Hooks must exit silently when env vars missing — never crash in non-broker contexts
API_URL = os.environ.get("FLYWHEEL_API_URL", "")
API_TOKEN = os.environ.get("FLYWHEEL_API_TOKEN", "")
if not API_URL or not API_TOKEN:
    sys.exit(0)  # Silent exit — not a broker context
```

### Pattern 3: Pipeline-Mode Sentinel

**What:** Environment variable `BROKER_PIPELINE_MODE=1` suppresses hooks during pipeline execution.
**When to use:** post-coverage-write and post-quote-write hooks; pipeline skill sets sentinel before batch writes.

```python
# In broker-post-coverage-write.py
PIPELINE_MODE = os.environ.get("BROKER_PIPELINE_MODE", "0") == "1"
if PIPELINE_MODE:
    sys.exit(0)  # Suppress during pipeline — will fire once at end

# In broker pipeline skill (pseudocode)
# export BROKER_PIPELINE_MODE=1
# ... write all 5 coverages ...
# unset BROKER_PIPELINE_MODE
# POST /projects/{id}/analyze-gaps  (explicit single call)
```

### Pattern 4: Playwright Portal Script Interface

**What:** Each carrier script implements `async def fill_portal(page, project, coverages, documents)`.
**When to use:** mapfre.py and all future carrier scripts.

```python
# Source: backend/scripts/portals/mapfre_mx.py (existing reference)
from playwright.async_api import Page

async def fill_portal(page: Page, project: dict, coverages: list[dict], documents: list[dict]) -> dict:
    """Fill carrier portal. Returns {"fields_filled": [...], "status": "ready_for_review"}."""
    fields_filled = []
    # Use try/except per field — portals change and scripts must be resilient
    try:
        await page.fill("#project-name", project.get("name", ""))
        fields_filled.append("project_name")
    except Exception:
        pass  # Field may not exist on this portal version
    return {"fields_filled": fields_filled, "status": "ready_for_review"}
```

**Key constraint:** Scripts NEVER click submit/confirm buttons. Only fill fields.

### Pattern 5: Broker SKILL.md Router

**What:** A router SKILL.md that maps `/broker:*` triggers to individual skill files.
**When to use:** The top-level SKILL.md at `~/.claude/skills/broker/SKILL.md`.

```markdown
---
name: broker
version: "1.0"
description: Broker module skill router — maps /broker:* triggers to individual skills
context-aware: true
triggers:
  - /broker:fill-portal
  - /broker:analyze-gaps
  - /broker:compare-quotes
---

# Broker Skill Router

When a `/broker:*` trigger is received, dispatch to the corresponding skill:

| Trigger | Skill File | Description |
|---------|-----------|-------------|
| /broker:fill-portal | portals/mapfre.py + base.py | Fill Mapfre portal form |
| /broker:analyze-gaps | (calls API directly) | POST /projects/{id}/analyze-gaps |
| /broker:compare-quotes | (calls API directly) | GET /projects/{id}/comparison |

## Context Store
This skill is context-aware. Follow the protocol in
~/.claude/skills/_shared/context-protocol.md
```

### Pattern 6: Hook Registration in settings.json

**What:** Add broker hooks to `~/.claude/settings.json` under the appropriate hook events.
**When to use:** Plan 134-03 must register all 5 hooks.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/sharan/.claude/hooks/broker-post-coverage-write.py"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/sharan/.claude/hooks/broker-post-quote-write.py"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/sharan/.claude/hooks/broker-pre-portal-validate.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/sharan/.claude/hooks/broker-pipeline-check.py"
          }
        ]
      }
    ]
  }
}
```

**CRITICAL:** The existing `~/.claude/settings.json` already has `PostToolUse`, `PreToolUse`, and `Stop` hooks. New hooks must be APPENDED to existing arrays, not replacing them.

### Anti-Patterns to Avoid

- **Stop hook infinite loop:** A Stop hook that returns `additionalContext` causes Claude to keep working. Always check `stop_hook_active` field and exit 0 immediately if true.
- **Exit 2 with JSON output:** When outputting JSON to control behavior, always `exit 0`. Exit 2 ignores stdout JSON; only stderr message is shown.
- **Blocking hooks in non-broker contexts:** All broker hooks must check FLYWHEEL_API_URL and FLYWHEEL_API_TOKEN first and exit silently (exit 0) if missing.
- **Replacing existing hook arrays:** When editing settings.json, append to existing arrays. Replacing them would remove critical security hooks (block-no-verify.sh, security-deny.sh, etc.).
- **credentials in skills/hooks:** Portal scripts must never store credentials. The broker logs in manually; Claude Code never handles credentials.
- **Hardcoded API paths in skills:** Use api_client.py which reads FLYWHEEL_API_URL from env. Never hardcode `localhost:8000`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP auth | Custom auth flow | api_client.py + FLYWHEEL_API_TOKEN env var | Consistent with portal_submitter.py pattern; token already managed |
| Browser automation | Custom webdriver code | playwright.async_api (v1.58.0) | Already installed; existing mapfre_mx.py reference implementation exists |
| YAML parsing for field maps | Custom parser | PyYAML (already installed) | Standard; supports comments for carrier-specific notes |
| Hook stdin parsing | Custom JSON reader | `json.load(sys.stdin)` with try/except | Standard pattern from all existing hooks; see hook_utils.py |
| Gap analysis logic | Custom detector in skills | POST /projects/{id}/analyze-gaps via api_client.py | Backend already has gap_detector engine; skills call it, don't replicate it |
| Quote comparison logic | Custom comparator in skills | GET /projects/{id}/comparison via api_client.py | Backend already has quote_comparator engine |
| Context store writes | Custom file writes | `~/.claude/skills/_shared/context_utils.py` | Existing utility with dedup, backup, and atomic writes |

**Key insight:** The architecture principle is "skills call backend API endpoints" — the backend owns all business logic. Skills are coordination layers, not logic layers.

## Common Pitfalls

### Pitfall 1: Stop Hook Infinite Loop
**What goes wrong:** Stop hook returns `additionalContext` telling Claude to do more work. Claude does the work, then stops again. The hook fires again. Infinite loop.
**Why it happens:** Stop hooks fire on EVERY Claude response completion, not just at "task done" moments.
**How to avoid:** Always parse stdin and check `stop_hook_active`. Exit 0 immediately if true. The broker-pipeline-check Stop hook should only add context if `stop_hook_active` is False AND the pipeline state indicates incomplete work.
**Warning signs:** Claude keeps working in loops without stopping.

### Pitfall 2: settings.json Hook Registration Overwrites
**What goes wrong:** Adding broker hooks by replacing the entire `hooks` object in settings.json removes existing security and cost-tracking hooks.
**Why it happens:** Easy mistake when editing JSON by hand.
**How to avoid:** Read the full settings.json first, then append to existing arrays. Current settings.json has: block-no-verify.sh, security-deny.sh, config-protection.sh (PreToolUse); auto-open-html.py, post-write-validate.py, attribution-track.py (PostToolUse); cost-verify.py, cost-tracker.sh, desktop-notify.sh (Stop).
**Warning signs:** Security hooks stop firing, cost tracking disappears.

### Pitfall 3: PostToolUse Hook Detecting API Calls Too Broadly
**What goes wrong:** post-coverage-write fires on every Bash command, not just coverage write API calls. Adds latency and spurious analyze-gaps calls.
**Why it happens:** Bash matcher catches everything.
**How to avoid:** Hook must parse `tool_input.command` from stdin JSON and only act when the command contains a coverage write API call pattern (e.g., POST to `/broker/projects/.*/coverages`).
**Warning signs:** Frequent spurious API calls to analyze-gaps.

### Pitfall 4: Playwright headless vs headed for Portal
**What goes wrong:** Using `headless=True` means broker can't see the browser to log in manually.
**Why it happens:** Default Playwright assumption is headless for automation.
**How to avoid:** Always use `headless=False` for portal scripts. Broker must see the browser. Reference: `portal_submitter.py` uses `headless=False`.
**Warning signs:** Portal opens and immediately fails because broker isn't logged in.

### Pitfall 5: FLYWHEEL_API_TOKEN Source Confusion
**What goes wrong:** Skills/hooks use a JWT token from the web app, which expires. Or use the service role key, which has admin access.
**Why it happens:** Multiple token types exist in the system.
**How to avoid:** FLYWHEEL_API_TOKEN should be the broker's Supabase JWT from their active session. Skills must document that the user needs to obtain this from their session. The token is NOT the Supabase service key (which is admin-level). The auth pattern from portal_submitter.py passes it as a CLI argument.
**Warning signs:** 401 errors from API calls, or unexpected admin access.

### Pitfall 6: api_client.py in Hooks vs Skills
**What goes wrong:** Hooks import api_client.py from a relative path that breaks when the hook runs from a different working directory.
**Why it happens:** Claude Code hooks run from the project's working directory, which may differ from the skill directory.
**How to avoid:** Use absolute path for imports in hooks: `sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))`. Same pattern used by existing hooks for hook_utils.py.
**Warning signs:** ImportError in hook logs.

### Pitfall 7: mapfre.yaml Field Map vs mapfre.py Script Separation
**What goes wrong:** Hard-coding Mapfre CSS selectors directly in mapfre.py instead of in mapfre.yaml. Makes selector updates require code changes.
**Why it happens:** Quick implementation shortcut.
**How to avoid:** mapfre.yaml contains selector mappings (field_name → CSS selector). mapfre.py loads the YAML and uses selectors from it. When Mapfre updates their portal, only the YAML needs updating.
**Warning signs:** Multiple places to change when the portal updates.

## Code Examples

Verified patterns from official sources:

### Hook reads stdin and exits silently if not in broker context
```python
# Source: ~/.claude/hooks/flywheel/lib/hook_utils.py (existing pattern)
import json, os, sys

def main():
    # 1. Read event (never crash on bad JSON)
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, IOError):
        event = {}
    
    # 2. Exit silently if not in broker context (HOOK-05 pattern)
    api_url = os.environ.get("FLYWHEEL_API_URL", "")
    api_token = os.environ.get("FLYWHEEL_API_TOKEN", "")
    if not api_url or not api_token:
        sys.exit(0)
    
    # 3. Check pipeline mode sentinel (HOOK-01, HOOK-02)
    if os.environ.get("BROKER_PIPELINE_MODE", "0") == "1":
        sys.exit(0)
    
    # 4. Parse command from event
    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")
    
    # 5. Act only on relevant commands
    # ... specific pattern matching ...
    
    sys.exit(0)
```

### api_client.py base structure
```python
# Source: backend/src/flywheel/engines/portal_submitter.py (existing pattern)
import asyncio, httpx, os, sys
from typing import Optional

API_URL = os.environ.get("FLYWHEEL_API_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.environ.get("FLYWHEEL_API_TOKEN", "")


def _headers() -> dict:
    if not API_TOKEN:
        raise RuntimeError("FLYWHEEL_API_TOKEN not set in environment")
    return {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}


async def post(path: str, payload: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_URL}/broker/{path.lstrip('/')}",
            json=payload or {},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{API_URL}/broker/{path.lstrip('/')}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


def run(coro):
    """Sync wrapper for use from non-async contexts (e.g., hooks)."""
    return asyncio.run(coro)
```

### Playwright base.py shared helpers
```python
# Source: backend/src/flywheel/engines/portal_submitter.py (existing pattern, extended)
from playwright.async_api import async_playwright, Page
import asyncio, os
from pathlib import Path
from datetime import datetime, timezone


async def launch_browser(headless: bool = False):
    """Launch Chromium. Always headless=False for portal scripts (broker must log in)."""
    p = await async_playwright().__aenter__()
    browser = await p.chromium.launch(headless=headless)
    return p, browser


async def wait_for_login(page: Page, prompt: str = "Please log in manually. Press Enter when ready..."):
    """Wait for broker to log in manually."""
    print(f"\n{'='*60}\n{prompt}\n{'='*60}")
    await asyncio.get_event_loop().run_in_executor(None, input)


async def safe_fill(page: Page, selector: str, value: str, field_name: str, fields_filled: list):
    """Fill a field with error resilience. Appends to fields_filled on success."""
    try:
        await page.fill(selector, value)
        fields_filled.append(field_name)
    except Exception:
        pass  # Field may not exist on this portal version


async def take_screenshot(page: Page, carrier_name: str) -> str:
    """Take full-page screenshot. Returns local path."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = f"/tmp/portal_screenshot_{carrier_name}_{timestamp}.png"
    await page.screenshot(path=path, full_page=True)
    print(f"Screenshot saved: {path}")
    return path


async def wait_for_confirmation(message: str = "Review the screenshot. Press Enter to confirm or Ctrl+C to abort..."):
    """Wait for human confirmation after screenshot."""
    print(f"\n{message}")
    await asyncio.get_event_loop().run_in_executor(None, input)
```

### Hook registration JSON structure (append to existing)
```json
// Source: https://code.claude.com/docs/en/hooks-guide
// IMPORTANT: Append to existing arrays in ~/.claude/settings.json
// Never replace entire hook event arrays
{
  "hooks": {
    "PostToolUse": [
      // ... existing hooks preserved ...
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "python3 /Users/sharan/.claude/hooks/broker-post-coverage-write.py"
        }]
      }
    ]
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global hooks only | Project-level `.claude/settings.json` hooks | Claude Code 2026 | Broker hooks should be in global settings (they apply regardless of project) |
| Shell script hooks | Python hooks with JSON output | Claude Code 2026 | Python hooks can make API calls; JSON output enables structured decisions |
| Exit code only | JSON structured output via stdout | Claude Code 2026 | Richer control: `permissionDecision`, `additionalContext`, `decision: "block"` |
| sync playwright | async playwright (async_api) | playwright-python 1.x | Better performance; matches existing portal_submitter.py pattern |

**Deprecated/outdated:**
- `playwright.sync_api`: Works but the existing codebase uses `async_api`. Stick with async for consistency.
- Exit 2 for everything: Exit 2 is appropriate for blocking with a plain message. For structured JSON decisions (PreToolUse deny with reason), use exit 0 + JSON stdout.

## Open Questions

1. **FLYWHEEL_API_TOKEN acquisition workflow**
   - What we know: Skills need a JWT from the broker's authenticated session. The portal_submitter.py accepts it as a `--auth-token` CLI arg.
   - What's unclear: How does the broker obtain and set this token for skills/hooks to use? Is there a session env var, or does the broker copy-paste from the browser dev tools?
   - Recommendation: Document in SKILL.md that broker must set `export FLYWHEEL_API_TOKEN=<jwt>` in their shell before running broker skills. This is a user-workflow question, not a code question. Add to skill dependency check (Standard 2).

2. **PostToolUse hook detection of coverage writes**
   - What we know: The hook matches on Bash tool calls and must detect when a coverage write API call was made.
   - What's unclear: Coverage writes happen via MCP tools (flywheel_* tools), not Bash commands. If MCP tools are the primary write path, a `PostToolUse` hook on Bash won't fire.
   - Recommendation: Clarify whether coverage writes are done via MCP tool calls or Bash+curl/httpx. If MCP tools, the matcher should be `mcp__flywheel__*` not `Bash`. Given that the architecture is "skills call API", this likely means the hook should also match `mcp__.*` patterns.

3. **mapfre.yaml selector accuracy**
   - What we know: The existing `mapfre_mx.py` uses placeholder selectors (`#project-name`, `#contract-value`). Real selectors require testing against the actual portal.
   - What's unclear: What are the real Mapfre portal selectors?
   - Recommendation: Plan 134-02 should create the YAML with clearly marked placeholder selectors and a note that real selectors require testing. This is acceptable for Phase 134 — the infrastructure pattern matters, not selector accuracy.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/engines/portal_submitter.py` — existing Playwright pattern, auth token usage, headless=False decision
- `backend/scripts/portals/mapfre_mx.py` — existing carrier script interface definition
- `backend/scripts/portals/README.md` — portal script contract (fill_portal interface, no-submit rule)
- `~/.claude/settings.json` — existing hook registrations (must not be overwritten)
- `~/.claude/hooks/flywheel/lib/hook_utils.py` — stdin reading pattern, session ID
- `~/.claude/hooks/flywheel/post-write-validate.py` — PostToolUse hook pattern
- `~/.claude/hooks/flywheel/contract-enforce.py` — PreToolUse hook pattern
- `~/.claude/skill-vault/investor-update/SKILL.md` — gold standard skill structure
- `/Users/sharan/.claude/projects/-Users-sharan-Projects/memory/skill-standards.md` — full 14 engineering standards
- `~/.claude/skills/_shared/context_utils.py` — context store utility (Standard 14)
- `python3 -m pip show playwright` — confirmed v1.58.0, chromium launches ok
- `python3 -m pip show httpx` — confirmed v0.28.1
- `python3 -m pip show pyyaml` — confirmed v6.0.3

### Secondary (MEDIUM confidence)
- https://code.claude.com/docs/en/hooks-guide — official Claude Code hooks guide, verified current; full event table, exit code semantics, JSON output format, stop_hook_active field

### Tertiary (LOW confidence)
- None — all critical claims verified from primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified installed versions; confirmed Chromium works
- Architecture: HIGH — based on existing portal_submitter.py, mapfre_mx.py, and hook_utils.py patterns
- Hook patterns: HIGH — verified against official docs + existing hook implementations
- Pitfalls: HIGH — stop hook infinite loop, settings.json overwrite risk are well-documented
- FLYWHEEL_API_TOKEN workflow: LOW — implementation detail not yet defined

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (30 days — stable internal codebase)
