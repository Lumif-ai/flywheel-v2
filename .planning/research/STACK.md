# Technology Stack

**Project:** Broker Redesign -- Skills, Portal Automation, Frontend Polish, Claude Code Hooks
**Researched:** 2026-04-15

## Recommended Stack Additions

This milestone requires additions across three layers: Python backend (portal automation), frontend (AG Grid upgrade, animations), and Claude Code configuration (hooks, skills). Five specific additions are needed.

### 1. Playwright (Python) -- Portal Automation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| playwright | >=1.58.0 | Carrier portal form-filling automation | Already architected in `portal_submitter.py` and `scripts/portals/mapfre_mx.py`. Codebase imports `playwright.async_api` with a `HAS_PLAYWRIGHT` guard. Not yet in `pyproject.toml` -- needs to be added as optional dependency |

**Current state:** The engine exists (`backend/src/flywheel/engines/portal_submitter.py`) and one carrier script exists (`backend/scripts/portals/mapfre_mx.py`). Both import Playwright but it is NOT listed in `pyproject.toml` dependencies. The engine runs locally on the broker's machine, not on the API server.

**Installation approach:** Add as optional dependency group, not core dependency. Portal scripts run on Claude Code's local machine, not the deployed API server.

```toml
# In pyproject.toml [dependency-groups]
portals = [
    "playwright>=1.58.0",
]
```

```bash
# On broker's machine only
uv sync --group portals
playwright install chromium
```

**Confidence: HIGH** -- Playwright 1.58.0 confirmed on PyPI (Jan 2026). Python >=3.9 required, project uses 3.12. Async API (`async_playwright`) already used in existing code.

### 2. AG Grid Enterprise -- Row Grouping

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| ag-grid-enterprise | >=35.2.0 | Row grouping, grouped column rendering, aggregation | Row Grouping is Enterprise-only. Community edition does NOT include it. Current codebase uses ag-grid-community 35.2.0 |
| ag-grid-react | >=35.2.0 | React wrapper (already installed) | Already present, version stays the same |

**Critical finding:** Row Grouping is an Enterprise-only feature. AG Grid's official Community vs Enterprise comparison explicitly lists "Row Grouping" under Enterprise Features only. The current codebase uses `ag-grid-community@35.2.0` which does NOT support row grouping.

**Decision required:** If row grouping is essential (e.g., grouping quotes by carrier, coverages by type), AG Grid Enterprise license is needed. If not, client-side "visual grouping" can be faked using custom row rendering with Community edition.

**Alternative -- No Enterprise license:**
- Use `pinnedTopRowData` for group headers (Community feature)
- Sort data by group key and insert visual separator rows
- Custom cell renderers can show expand/collapse UI without actual grouping API
- This is a workaround, not a replacement -- no built-in aggregation, no drag-to-group

**Custom cell renderers and theming:** Both are Community features. The codebase already has:
- Shared renderers: `frontend/src/shared/grid/cell-renderers/` (4 renderers)
- Pipeline renderers: `frontend/src/features/pipeline/components/cell-renderers/` (8 renderers)
- Theme: `frontend/src/shared/grid/theme.ts` using `themeQuartz.withParams()`

No new library needed for custom cell renderers or theming -- these are Community features already in use.

```bash
# Only if Enterprise license acquired:
npm install ag-grid-enterprise@35.2.0

# In code, add module registration:
import { LicenseManager } from 'ag-grid-enterprise'
LicenseManager.setLicenseKey('YOUR-KEY')
```

**Confidence: HIGH** -- Verified via official AG Grid docs that Row Grouping is Enterprise-only. Custom cell renderers and theming are confirmed Community.

### 3. Claude Code Hooks -- Configuration Only (No Library)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Claude Code hooks | Current | PreToolUse, PostToolUse, Stop event automation | Built into Claude Code, configured via `.claude/settings.json` or `.claude/settings.local.json`. No library to install |

**No dependency needed.** Hooks are a Claude Code built-in feature configured via JSON in settings files.

**Configuration location:** `.claude/settings.json` (project-level, shareable) or `.claude/settings.local.json` (local-only).

**Relevant hook events for broker skills:**

| Event | Use Case | Can Block? |
|-------|----------|-----------|
| `PreToolUse` | Validate portal automation commands before execution, block destructive DB ops | Yes (exit code 2) |
| `PostToolUse` | Log portal submission results, trigger notifications after skill completion | No |
| `Stop` | Ensure all portal changes are saved/committed before Claude stops | Yes (exit code 2) |
| `SubagentStop` | Validate sub-agent skill output before accepting | Yes |

**Handler types available:** `command` (shell script), `http` (webhook), `prompt` (LLM check), `agent` (sub-agent verification).

**Hook scripts location:** `.claude/hooks/` directory with executable bash scripts.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/validate-portal-cmd.sh",
            "statusMessage": "Validating portal command..."
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/ensure-saved.sh"
          }
        ]
      }
    ]
  }
}
```

**Confidence: HIGH** -- Verified via official Claude Code docs at code.claude.com/docs/en/hooks.

### 4. Claude Code Skills -- SKILL.md Format (No Library)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SKILL.md format | N/A | Skill definitions for contract parsing, quote extraction, portal automation | File-based convention, no library. Skills live in `~/.claude/skills/` or project `skills/` directory |

**No dependency needed.** Skills are markdown files with frontmatter following the 14 engineering standards already defined in the project's `SKILL-REVIEW-SPEC.md`.

**Existing skill infrastructure:**
- Skill router: `~/.claude/skills/skill-router/SKILL.md` (30+ skills catalogued)
- Shared references: `~/.claude/skills/_shared/` (advisors, protocols)
- GTM skills: `skills/gtm-web-scraper-extractor/`, `skills/gtm-outbound-messenger/`

**New broker skills to create (file-only, no packages):**
1. `skills/broker-contract-parser/SKILL.md` -- Parse uploaded contract PDFs
2. `skills/broker-quote-extractor/SKILL.md` -- Extract structured quote data from carrier responses
3. `skills/broker-portal-submitter/SKILL.md` -- Orchestrate Playwright portal automation
4. `skills/broker-recommendation-builder/SKILL.md` -- Generate client recommendation letters

**Confidence: HIGH** -- Existing skill system verified in codebase. No new tooling needed.

### 5. CSS Animations -- Already In Place (No Library)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| tw-animate-css | ^1.4.0 | Tailwind animation utilities | Already installed and imported in index.css |
| Custom keyframes | N/A | fadeUp, shimmer, stagger, page transitions | Already defined in `frontend/src/index.css` and `frontend/src/lib/animations.ts` |

**No dependency needed.** The animation system is already comprehensive:

**Already defined in `index.css`:**
- `@keyframes fade-slide-up` -- 12px translateY + opacity
- `@keyframes shimmer` -- skeleton loading effect
- `@keyframes page-fade-in` -- page entry animation
- `.stagger-1` through `.stagger-5` -- 50ms stagger delays
- Task exit animations (confirm/dismiss/later)
- Focus card animations (enter/exit with rotation)
- `.animate-shimmer` with CSS custom properties for theming

**Already defined in `lib/animations.ts`:**
- `fadeSlideUp` object with initial/animate/transition
- `staggerDelay(index)` function
- `animationClasses` constants

**What to add for the redesign (CSS-only, no library):**
- New keyframes can be added directly to `index.css` `@layer utilities` block
- `prefers-reduced-motion` media query already handled (line 313)
- Dark mode shimmer variables already defined (lines 130-131)

**Confidence: HIGH** -- All verified in codebase. No new animation library needed.

## Summary: What to Install

| Layer | Package | Required? | Notes |
|-------|---------|-----------|-------|
| Python | `playwright>=1.58.0` | YES | Optional dep group for portal scripts |
| Frontend | `ag-grid-enterprise@35.2.0` | CONDITIONAL | Only if row grouping feature is required. Needs license |
| Frontend | N/A for animations | NO | Already have tw-animate-css + custom keyframes |
| Claude Code | N/A for hooks | NO | JSON configuration only |
| Claude Code | N/A for skills | NO | SKILL.md files only |

## What NOT to Add

| Package | Why Not |
|---------|---------|
| framer-motion | Overkill. CSS keyframes + Tailwind classes handle all needed animations. The codebase already uses pure CSS animations extensively (20+ keyframes defined). Framer adds 32KB gzipped for spring physics not needed here |
| puppeteer | Playwright is already chosen, architected, and coded. Portal engine imports Playwright. Switching would rewrite existing code for no benefit |
| ag-grid-enterprise (without license) | Enterprise watermark + console warnings in production. Either get the license or use Community workarounds for grouping |
| react-spring / motion | Same rationale as framer-motion. CSS animations are performant and already established |
| Selenium | Playwright is the modern standard. Already in use. Selenium would be a downgrade |
| animate.css | tw-animate-css already provides this and integrates with Tailwind v4 |
| Any animation orchestration library | CSS stagger delays + animation-delay handle sequencing. No JS animation runtime needed |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Portal automation | Playwright (Python async) | Puppeteer, Selenium | Playwright already architected and coded in the engine. Python async API matches backend patterns |
| Row grouping | AG Grid Enterprise (if licensed) OR Community visual grouping workaround | TanStack Table | AG Grid already deeply integrated (30+ files use it). Migration cost is prohibitive |
| CSS animations | Custom keyframes in index.css | framer-motion | Existing pattern works. 20+ keyframes already defined. No JS animation runtime overhead |
| Hooks | Claude Code built-in hooks | Custom MCP tool wrappers | Hooks are the official mechanism. MCP tools serve a different purpose (data access, not workflow control) |
| Skills | SKILL.md file format | Backend-managed skill definitions | SKILL.md is the established pattern with 30+ skills. Backend stores execution results, not skill definitions |

## Installation

```bash
# Python (portal automation -- optional group, broker machine only)
cd backend
# Add to pyproject.toml under [dependency-groups]:
# portals = ["playwright>=1.58.0"]
uv sync --group portals
playwright install chromium

# Frontend (only if AG Grid Enterprise license acquired)
cd frontend
npm install ag-grid-enterprise@35.2.0

# Claude Code hooks (configuration only)
mkdir -p .claude/hooks
# Add hooks configuration to .claude/settings.json

# Skills (file creation only)
mkdir -p skills/broker-contract-parser
mkdir -p skills/broker-quote-extractor
mkdir -p skills/broker-portal-submitter
mkdir -p skills/broker-recommendation-builder
```

## Sources

- [AG Grid Community vs Enterprise](https://www.ag-grid.com/react-data-grid/community-vs-enterprise/) -- Row Grouping confirmed Enterprise-only (HIGH confidence)
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks) -- Full hook event list, configuration format, exit codes (HIGH confidence)
- [Playwright on PyPI](https://pypi.org/project/playwright/) -- v1.58.0 latest, Python >=3.9 (HIGH confidence)
- Codebase: `backend/src/flywheel/engines/portal_submitter.py` -- Playwright already architected (HIGH confidence)
- Codebase: `backend/scripts/portals/mapfre_mx.py` -- Carrier script pattern established (HIGH confidence)
- Codebase: `frontend/src/shared/grid/theme.ts` -- AG Grid theming with themeQuartz (HIGH confidence)
- Codebase: `frontend/src/index.css` lines 187-293 -- 20+ keyframes already defined (HIGH confidence)
- Codebase: `frontend/src/lib/animations.ts` -- Animation utilities established (HIGH confidence)
- Codebase: `frontend/package.json` -- ag-grid-community@35.2.0, tw-animate-css@1.4.0 confirmed (HIGH confidence)
- Codebase: `~/.claude/skills/skill-router/SKILL.md` -- 30+ skills catalogued (HIGH confidence)
