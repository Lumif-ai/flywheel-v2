#!/usr/bin/env bash
# -----------------------------------------------------------------------
# Flywheel Installer — one-liner setup for a fresh Mac
#
# Usage:
#   curl -sSL https://gist.githubusercontent.com/Sharan0516/8fb4a3755b3c3e2a2abfae1c949b574a/raw/install.sh | bash
#
# What it does:
#   1. Checks/installs Homebrew
#   2. Checks/installs Python 3.10+ (via brew)
#   3. Checks/installs uv (Python package manager)
#   4. Installs flywheel-ai from PyPI (flywheel + flywheel-mcp commands)
#   5. Installs Playwright Chromium (for browser agent)
#   6. Checks/installs Node.js (needed for Claude Code)
#   7. Checks/installs Claude Code CLI
#   8. Runs flywheel setup-claude-code (MCP servers + CLAUDE.md + permissions)
#   9. Runs flywheel login (Google OAuth)
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
PYPI_PACKAGE="flywheel-ai"
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
        export PATH="$HOME/.local/bin:$PATH"
    fi
    success "uv installed: $(uv --version)"
fi

# ========================================================================
# Step 4: Install flywheel-ai from PyPI
# ========================================================================
step "Installing Flywheel CLI"

# Remove previous installation if present (idempotent)
uv tool uninstall flywheel-ai 2>/dev/null || true
uv tool uninstall flywheel-cli 2>/dev/null || true  # legacy name

info "Installing $PYPI_PACKAGE from PyPI ..."
uv tool install "$PYPI_PACKAGE"

# Ensure uv tool bin is on PATH
UV_TOOL_BIN="$HOME/.local/bin"
if ! command -v flywheel &>/dev/null; then
    if [[ -f "$UV_TOOL_BIN/flywheel" ]]; then
        export PATH="$UV_TOOL_BIN:$PATH"
        warn "Added $UV_TOOL_BIN to PATH (add to your shell profile for permanence)"
    else
        fail "flywheel command not found after install. Check uv tool install output above."
    fi
fi
success "flywheel CLI installed: $(which flywheel)"

if ! command -v flywheel-mcp &>/dev/null; then
    fail "flywheel-mcp command not found after install."
fi
success "flywheel-mcp installed: $(which flywheel-mcp)"

# ========================================================================
# Step 5: Playwright Chromium (for browser agent)
# ========================================================================
step "Installing Playwright Chromium (for browser agent)"

# Playwright is inside the uv tool venv — find it there
FLYWHEEL_VENV="$(dirname "$(which flywheel)")/../lib/python*/site-packages"
PLAYWRIGHT_BIN="$(dirname "$(which flywheel)")/../lib/python*/site-packages/playwright"

# Use the flywheel tool's python to run playwright install
FLYWHEEL_PYTHON="$(dirname "$(which flywheel)")/python3"
if [[ -f "$FLYWHEEL_PYTHON" ]]; then
    "$FLYWHEEL_PYTHON" -m playwright install chromium 2>/dev/null && \
        success "Playwright Chromium ready" || \
        warn "Playwright install failed — browser agent may not work. Retry: flywheel agent setup"
else
    # Fallback: try via uv tool run
    uv tool run --from flywheel-ai playwright install chromium 2>/dev/null && \
        success "Playwright Chromium ready" || \
        warn "Playwright install failed — browser agent may not work. Retry: flywheel agent setup"
fi

# ========================================================================
# Step 6: Node.js (needed for Claude Code)
# ========================================================================
step "Checking Node.js"

if command -v node &>/dev/null; then
    success "Node.js found: $(node --version)"
else
    info "Installing Node.js via Homebrew..."
    brew install node
    success "Node.js installed: $(node --version)"
fi

# ========================================================================
# Step 7: Claude Code CLI
# ========================================================================
step "Checking Claude Code CLI"

if command -v claude &>/dev/null; then
    success "Claude Code found: $(which claude)"
else
    info "Installing Claude Code CLI..."
    npm install -g @anthropic-ai/claude-code 2>/dev/null && \
        success "Claude Code installed: $(which claude)" || {
        warn "Claude Code auto-install failed."
        echo -e "  Install manually from: ${BOLD}https://claude.ai/download${NC}"
        echo -e "  Or via npm:            ${BOLD}npm install -g @anthropic-ai/claude-code${NC}"
        echo ""
        echo -e "  After installing, run: ${BOLD}flywheel setup-claude-code${NC}"
    }
fi

# ========================================================================
# Step 8: Setup Claude Code (MCP servers + CLAUDE.md + permissions)
# ========================================================================
if command -v claude &>/dev/null; then
    step "Setting up Claude Code integration"
    flywheel setup-claude-code || {
        warn "Claude Code setup had issues. Run manually: flywheel setup-claude-code"
    }
fi

# ========================================================================
# Step 9: Create ~/.flywheel directory
# ========================================================================
mkdir -p "$HOME/.flywheel"

# ========================================================================
# Step 10: Login
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
echo -e "    flywheel upgrade       Update to latest version"
echo ""
if command -v claude &>/dev/null; then
    echo -e "  ${BOLD}Claude Code integration:${NC}"
    echo -e "    MCP servers: flywheel (business intel) + granola (meetings)"
    echo -e "    CLAUDE.md:   Flywheel-first routing rules installed"
    echo -e "    Permissions: Read/write auto-allowed, destructive actions ask first"
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
