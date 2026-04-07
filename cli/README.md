# Flywheel AI

Business intelligence CLI and MCP server for [Claude Code](https://claude.ai/download).

Flywheel connects your meetings, contacts, pipeline, and business context to Claude Code — so your AI assistant knows your business as well as you do.

## Quick Install

```bash
curl -sSL https://gist.githubusercontent.com/Sharan0516/8fb4a3755b3c3e2a2abfae1c949b574a/raw/install.sh | bash
```

Or install manually:

```bash
pip install flywheel-ai
flywheel login
flywheel setup-claude-code
```

## What You Get

### CLI Commands

| Command | Description |
|---------|-------------|
| `flywheel login` | Authenticate via Google OAuth |
| `flywheel status` | Check login state and tenant info |
| `flywheel focus list` | List your focuses (departments/teams) |
| `flywheel focus switch <name>` | Switch active focus |
| `flywheel agent setup` | Install browser automation deps |
| `flywheel agent start` | Start local browser agent |
| `flywheel setup-claude-code` | Register MCP servers with Claude Code |

### MCP Tools (available in Claude Code)

Once registered, Claude Code gains access to:

- **flywheel_run_skill** — Run meeting-prep, company-intel, and other skills
- **flywheel_read_context** — Search your business knowledge base
- **flywheel_write_context** — Store business intelligence
- **flywheel_fetch_meetings** — List meetings from your calendar
- **flywheel_sync_meetings** — Sync meetings from connected providers
- **flywheel_list_leads** — View your pipeline contacts
- **flywheel_draft_lead_message** — Draft outreach messages
- And more — run `flywheel setup-claude-code` to see the full list

## Requirements

- macOS (Apple Silicon or Intel)
- Python 3.10+
- [Claude Code](https://claude.ai/download) (for MCP tools)

## Configuration

All configuration is handled automatically. No `.env` file needed.

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `FLYWHEEL_API_URL` | Hosted backend | Override API endpoint |
| `FLYWHEEL_DIR` | `~/.flywheel/` | Local config directory |

## Publishing & Maintenance

- **PyPI package:** https://pypi.org/project/flywheel-ai/
- **Install script (public gist):** https://gist.github.com/Sharan0516/8fb4a3755b3c3e2a2abfae1c949b574a

When you update `scripts/install.sh`, sync the gist:
```bash
gh gist edit 8fb4a3755b3c3e2a2abfae1c949b574a scripts/install.sh
```

To publish a new CLI version to PyPI:
```bash
# 1. Bump version in cli/pyproject.toml
# 2. Run:
UV_PUBLISH_TOKEN=pypi-XXXX ./scripts/publish-cli.sh
```

## License

MIT
