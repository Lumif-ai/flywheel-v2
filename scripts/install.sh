#!/usr/bin/env bash
# -----------------------------------------------------------------------
# Flywheel Installer — one-liner setup for a fresh Mac
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/Sharan0516/flywheel-v2/main/scripts/install.sh | bash
#
# What it does:
#   1. Checks/installs Homebrew
#   2. Checks/installs Python 3.10+ (via brew)
#   3. Checks/installs uv (Python package manager)
#   4. Installs flywheel-cli (flywheel + flywheel-mcp commands)
#   5. Installs Playwright Chromium (for browser agent)
#   6. Checks for Claude Code CLI
#   7. Registers MCP servers: flywheel (stdio) + granola (HTTP)
#   8. Runs flywheel login (Google OAuth)
# -----------------------------------------------------------------------

set -euo pipefail

# -- Colors / helpers ----------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()    { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }
step()    { echo -e "\n${BOLD}==> $*${NC}"; }

# -- Config --------------------------------------------------------------
REPO_URL="https://github.com/Sharan0516/flywheel-v2.git"
GRANOLA_MCP_URL="https://mcp.granola.ai/mcp"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10

# ========================================================================
# Step 1: Homebrew
# ========================================================================
step "Checking Homebrew"

if command -v brew &>/dev/null; then
    success "Homebrew found: $(brew --prefix)"
else
    info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon Macs
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    success "Homebrew installed"
fi

# ========================================================================
# Step 2: Python 3.10+
# ========================================================================
step "Checking Python 3.10+"

python_ok=false
for py in python3 python; do
    if command -v "$py" &>/dev/null; then
        ver=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [[ "$major" -ge "$MIN_PYTHON_MAJOR" && "$minor" -ge "$MIN_PYTHON_MINOR" ]]; then
            python_ok=true
            success "Python $ver found ($py)"
            break
        fi
    fi
done

if ! $python_ok; then
    info "Installing Python via Homebrew..."
    brew install python@3.12
    success "Python 3.12 installed"
fi

# ========================================================================
# Step 3: uv (Python package manager)
# ========================================================================
step "Checking uv"

if command -v uv &>/dev/null; then
    success "uv found: $(uv --version)"
else
    info "Installing uv..."
    if command -v brew &>/dev/null; then
        brew install uv
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # Add to PATH
        export PATH="$HOME/.local/bin:$PATH"
    fi
    success "uv installed: $(uv --version)"
fi

# ========================================================================
# Step 4: Install flywheel-cli
# ========================================================================
step "Installing Flywheel CLI"

# Remove previous installation if present (idempotent)
uv tool uninstall flywheel-cli 2>/dev/null || true

info "Installing from $REPO_URL ..."
uv tool install "flywheel-cli @ git+${REPO_URL}#subdirectory=cli"

# Verify
if command -v flywheel &>/dev/null; then
    success "flywheel CLI installed: $(which flywheel)"
else
    # uv tool bin may not be on PATH yet
    UV_TOOL_BIN="$HOME/.local/bin"
    if [[ -f "$UV_TOOL_BIN/flywheel" ]]; then
        export PATH="$UV_TOOL_BIN:$PATH"
        warn "Added $UV_TOOL_BIN to PATH. Add this to your shell profile:"
        echo -e "  ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
        success "flywheel CLI installed: $UV_TOOL_BIN/flywheel"
    else
        fail "flywheel command not found after install. Check uv tool install output above."
    fi
fi

if command -v flywheel-mcp &>/dev/null; then
    success "flywheel-mcp installed: $(which flywheel-mcp)"
else
    fail "flywheel-mcp command not found after install."
fi

# ========================================================================
# Step 5: Playwright Chromium
# ========================================================================
step "Installing Playwright Chromium (for browser agent)"

flywheel agent setup 2>/dev/null || {
    info "Fallback: running playwright install chromium directly..."
    uv run playwright install chromium 2>/dev/null || warn "Playwright install failed — browser agent may not work. You can retry: flywheel agent setup"
}
success "Playwright Chromium ready"

# ========================================================================
# Step 6: Claude Code CLI
# ========================================================================
step "Checking Claude Code CLI"

if command -v claude &>/dev/null; then
    success "Claude Code found: $(which claude)"
else
    warn "Claude Code CLI not found."
    echo -e "  Install it from: ${BOLD}https://claude.ai/download${NC}"
    echo -e "  Or via npm:      ${BOLD}npm install -g @anthropic-ai/claude-code${NC}"
    echo ""
    echo -e "  After installing Claude Code, run: ${BOLD}flywheel setup-claude-code${NC}"
    echo -e "  to register MCP servers."
    echo ""
    # Don't exit — CLI is still usable without Claude Code
fi

# ========================================================================
# Step 7: Register MCP servers (only if Claude Code is available)
# ========================================================================
if command -v claude &>/dev/null; then
    step "Registering MCP servers with Claude Code"

    # 7a. Flywheel MCP (stdio)
    MCP_PATH=$(which flywheel-mcp)
    info "Registering flywheel MCP (stdio) ..."
    claude mcp add --transport stdio --scope user flywheel -- "$MCP_PATH" 2>/dev/null && \
        success "Flywheel MCP registered" || \
        warn "Flywheel MCP registration failed — run manually: claude mcp add --transport stdio --scope user flywheel -- $MCP_PATH"

    # 7b. Granola MCP (HTTP)
    info "Registering Granola MCP (HTTP) ..."
    claude mcp add --transport http --scope user granola --url "$GRANOLA_MCP_URL" 2>/dev/null && \
        success "Granola MCP registered" || \
        warn "Granola MCP registration failed — run manually: claude mcp add --transport http --scope user granola --url $GRANOLA_MCP_URL"
fi

# ========================================================================
# Step 8: Create ~/.flywheel directory
# ========================================================================
mkdir -p "$HOME/.flywheel"

# ========================================================================
# Step 9: Login
# ========================================================================
step "Logging in to Flywheel"

echo -e "This will open your browser for Google authentication.\n"
flywheel login || {
    warn "Login skipped or failed. You can login later: flywheel login"
}

# ========================================================================
# Done!
# ========================================================================
echo ""
echo -e "${GREEN}${BOLD}============================================${NC}"
echo -e "${GREEN}${BOLD}  Flywheel installed successfully!          ${NC}"
echo -e "${GREEN}${BOLD}============================================${NC}"
echo ""
echo -e "  ${BOLD}Commands available:${NC}"
echo -e "    flywheel status        Check login & tenant info"
echo -e "    flywheel focus list    List your focuses"
echo -e "    flywheel agent start   Start browser agent"
echo ""
if command -v claude &>/dev/null; then
    echo -e "  ${BOLD}MCP servers registered:${NC}"
    echo -e "    flywheel    Your business intelligence tools"
    echo -e "    granola     Meeting transcripts from Granola"
    echo ""
    echo -e "  ${BOLD}Optional:${NC} Enable Apollo MCP plugin in Claude Code settings"
    echo -e "  for lead enrichment tools."
    echo ""
fi
echo -e "  ${BOLD}Need help?${NC} Run: flywheel --help"
echo ""

# Remind about PATH if needed
if ! command -v flywheel &>/dev/null 2>&1; then
    echo -e "${YELLOW}${BOLD}IMPORTANT:${NC} Add this to your ~/.zshrc or ~/.bashrc:"
    echo -e "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi
