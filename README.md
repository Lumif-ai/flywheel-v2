# Flywheel v2

**Compound intelligence operating system for teams.**

GTM is the beachhead — pipeline, briefing, email, document library — but the architecture is domain-agnostic. A shared intelligence layer accumulates structured knowledge from every meeting, email, and interaction across any business function.

## Skill Delivery

As of Phase 152 (2026-04-19), Flywheel skills are delivered exclusively through the Flywheel MCP server. Claude Code fetches skill bundles on demand via `flywheel_fetch_skill_assets`; skill content is stored server-side in the `skill_assets` table and versioned by content SHA.

Do not clone skill repositories into `~/.claude/skills/`. That delivery path has been retired and is no longer supported — the `~/.claude/skills/` directory tree, if present on a machine, is inert and will not be consulted by Claude Code.

Installation is a single command:

```
./scripts/install.sh
```

This installs `flywheel-ai` from PyPI, registers the Flywheel MCP server with Claude Code, and completes authentication. No per-skill cloning, unzipping, or path management is required.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 |
| Frontend | React 19, Vite, shadcn/ui, Tailwind, AG Grid |
| Database | PostgreSQL (Supabase) with Row-Level Security |
| AI | Anthropic Claude SDK (BYOK) |
| Integration | MCP Server (30+ tools), Gmail, Calendar, Outlook, Granola, Slack, Apollo |
| Export | WeasyPrint (PDF), python-docx (DOCX) |

## Architecture

```
frontend/          React SPA (localhost:5173)
backend/           FastAPI API + Services + AI Engines (port 8000)
cli/               MCP Server (FastMCP) — 30+ tools for Claude Code
skills/            Declarative skill definitions (SKILL.md format)
docs/              Architecture documentation
```

## Development

```bash
./start-dev.sh     # Backend + Frontend + ngrok tunnel
./stop-dev.sh      # Stop all services
```

## Documentation

Architecture document available at the [GitHub Pages site](https://lumif-ai.github.io/flywheel-v2/) (password protected).

---

Lumif.ai — Confidential
